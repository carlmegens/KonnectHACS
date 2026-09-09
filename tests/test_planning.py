"""Planning API bounds, Dutch date handling, projection and real HA authorization."""

from copy import deepcopy
from datetime import datetime
from unittest.mock import patch

import httpx
import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from icalendar import Calendar

from custom_components.ouderapp.api import (
    OuderAppApi,
    OuderAppAuthError,
    OuderAppError,
    OuderAppResponseError,
)
from custom_components.ouderapp.calendar_export import CalendarExportError, export_calendar
from custom_components.ouderapp.planning import child_identifier, period_for, project_planning


def millis(value):
    return int(datetime.fromisoformat(value).timestamp() * 1000)


def slot(start="2026-10-25T01:30:00+02:00", end="2026-10-25T03:30:00+01:00", status="tentative"):
    return {
        "startTime": millis(start),
        "endTime": millis(end),
        "plannedAttendanceCode": {"code": status},
        "toConfirmProduct": True,
    }


def payload(slots=None):
    return {
        "days": [
            {
                "children": [
                    {
                        "child": {"id": 7, "firstName": "Synthetic child"},
                        "combinedPlanningParts": [
                            {"planningParts": slots if slots is not None else [slot()]}
                        ],
                    }
                ]
            }
        ],
        "data_connector_offline": False,
    }


@pytest.mark.parametrize(
    "start,end",
    [
        ("2026-02-30", "2026-03-02"),
        ("20261025", "2026-10-26"),
        ("2026-10-25T00:00:00", "2026-10-26"),
        ("../private", "2026-10-26"),
        ("2026-10-25", "2026-10-25"),
        ("2026-10-26", "2026-10-25"),
        ("2026-10-01", "2026-11-02"),
        ("2101-01-01", "2101-01-02"),
    ],
)
async def test_invalid_period_never_reaches_network(session, start, end):
    def handle(request):
        pytest.fail("Invalid date reached network")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError):
            await OuderAppApi(client, "example", session).async_get_planning(start, end)


@pytest.mark.parametrize("offline", [False, True])
async def test_planning_keeps_warning_without_provider_messages(session, offline):
    def handle(request):
        assert request.method == "GET"
        assert request.url.path == "/restservices-parent/calendar/20261025/until/20261026"
        assert request.url.query == b""
        assert request.headers["Authorization"] == "Bearer access-test"
        return httpx.Response(
            200,
            json={
                "result": True,
                "payload": payload(),
                "messages": [
                    {
                        "messageCode": "web.general.message.data_connector.child_planning.offline.possible_incorrect_data"
                        if offline
                        else "other",
                        "text": "PRIVATE-WARNING",
                    }
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        result = await OuderAppApi(client, "example", session).async_get_planning(
            "2026-10-25", "2026-10-26"
        )
        assert result["data_connector_offline"] is offline
        assert "PRIVATE-WARNING" not in str(result)


async def test_planning_warning_survives_session_refresh(session):
    calls = []

    def handle(request):
        calls.append(request.url.path)
        if request.url.path == "/auth-api/token":
            return httpx.Response(200, json={"authToken": "new", "refreshToken": "new-r"})
        if request.url.path == "/auth-api/user":
            return httpx.Response(200, json={"username": session.username})
        if request.headers["Authorization"] == "Bearer access-test":
            return httpx.Response(401)
        return httpx.Response(
            200,
            json={
                "result": True,
                "payload": payload(),
                "messages": [
                    {
                        "messageCode": "web.general.message.data_connector.child_planning.offline.possible_incorrect_data"
                    }
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        result = await OuderAppApi(client, "example", session).async_get_planning(
            "2026-10-25", "2026-10-26"
        )
        assert result["data_connector_offline"]
        assert calls.count("/auth-api/token") == 1


def test_dst_offsets_status_and_stable_account_bound_identity():
    period = period_for("2026-10-25", "2026-10-26")
    data = payload()
    event = project_planning(data, "account-a", period)["events"][0]
    assert event["start"].endswith("+02:00")
    assert event["end"].endswith("+01:00")
    assert (
        datetime.fromisoformat(event["end"]) - datetime.fromisoformat(event["start"])
    ).total_seconds() == 3 * 3600
    assert event["status"] == "tentative"
    assert event["confirmation_required"] is True
    assert project_planning(data, "account-a", period)["events"][0]["id"] == event["id"]
    assert project_planning(data, "account-b", period)["events"][0]["id"] != event["id"]
    data["days"][0]["children"][0]["combinedPlanningParts"][0]["planningParts"][0][
        "plannedAttendanceCode"
    ]["code"] = "absent"
    absent = project_planning(data, "account-a", period)["events"][0]
    assert absent["status"] == "absent" and absent["id"] == event["id"]


def test_exclusive_end_and_spring_dst_date_window():
    period = period_for("2026-03-29", "2026-03-30")
    assert period.end_time.timestamp() - period.start_time.timestamp() == 23 * 3600
    data = payload(
        [
            slot("2026-03-28T22:00:00+01:00", "2026-03-29T00:00:00+01:00"),
            slot("2026-03-29T23:00:00+02:00", "2026-03-30T00:30:00+02:00"),
            slot("2026-03-30T00:00:00+02:00", "2026-03-30T01:00:00+02:00"),
        ]
    )
    result = project_planning(data, "a", period)
    assert result["returned"] == 1  # Overlap retained; boundary-only contacts excluded.
    assert result["events"][0]["start"].startswith("2026-03-29T23")


def test_sort_limit_dedup_unknown_status_and_plain_text():
    early = slot(status="UNKNOWN-PROVIDER-SECRET")
    del early["toConfirmProduct"]
    late = slot("2026-10-25T10:00:00+01:00", "2026-10-25T11:00:00+01:00")
    data = payload([late, early, deepcopy(early)])
    data["days"][0]["children"][0]["child"]["firstName"] = (
        "<script>SECRET</script>A https://private.invalid"
    )
    result = project_planning(data, "a", period_for("2026-10-25", "2026-10-26"), 1)
    assert result["truncated"] and result["returned"] == 1
    assert result["events"][0]["status"] == "unknown"
    assert result["events"][0]["confirmation_required"] is None
    assert result["events"][0]["child"] == "A"
    assert "SECRET" not in str(result) and "https://" not in str(result)


@pytest.mark.parametrize("bad", [None, True, "2026-10-25T01:00:00Z", float("nan"), 10**100])
def test_bad_planning_times_are_errors(bad):
    data = payload()
    data["days"][0]["children"][0]["combinedPlanningParts"][0]["planningParts"][0]["startTime"] = (
        bad
    )
    with pytest.raises(OuderAppError):
        project_planning(data, "a", period_for("2026-10-25", "2026-10-26"))


@pytest.mark.parametrize("data", [{}, {"days": None}, {"days": [None]}, {"days": [{}] * 34}])
def test_bad_planning_shape_not_silently_empty(data):
    with pytest.raises(OuderAppError):
        project_planning(data, "a", period_for("2026-10-25", "2026-10-26"))


def test_child_identifiers_are_opaque_and_never_exposed():
    period = period_for("2026-10-25", "2026-10-26")
    data = payload()
    group = data["days"][0]["children"][0]
    identifiers = []
    for identity in [7, "7", "kid_abc-def", "e7f0a431-7ba2-4e70-aa6e-b560ea5d3390"]:
        group["child"]["id"] = identity
        result = project_planning(data, "a", period)
        assert len(result["events"]) == 1
        assert len(result["events"][0]["id"]) == 64
        identifiers.append(result["events"][0]["id"])
        if isinstance(identity, str) and len(identity) > 1:
            assert identity not in str(result)
    assert identifiers[0] == identifiers[1]
    assert len(set(identifiers)) == 3
    for identity in [None, True, {}, "", "../private", "a\nPRIVATE", "a" * 129]:
        group["child"]["id"] = identity
        with pytest.raises(OuderAppError, match="child"):
            project_planning(data, "a", period)


@pytest.mark.parametrize("value", [0, -1, 10**40, 1.5, False, "é", "a b", "a/b", "a\x00b"])
def test_child_identifier_rejects_unsupported_values(value):
    assert child_identifier(value) is None


def test_opaque_child_identity_keeps_account_separation_and_calendar_uid():
    data = payload()
    data["days"][0]["children"][0]["child"]["id"] = "opaque_child-id"
    period = period_for("2026-10-25", "2026-10-26")
    first = project_planning(data, "account-a", period)
    repeated = project_planning(data, "account-a", period)
    other = project_planning(data, "account-b", period)
    assert first["events"][0]["id"] == repeated["events"][0]["id"]
    assert first["events"][0]["id"] != other["events"][0]["id"]
    calendar = export_calendar(first)
    assert "opaque_child-id" not in calendar
    assert len(Calendar.from_ical(calendar).walk("VEVENT")) == 1


def test_empty_and_conflicting_slots():
    period = period_for("2026-10-25", "2026-10-26")
    assert project_planning({"days": []}, "a", period)["events"] == []
    with pytest.raises(OuderAppError, match="Conflicting"):
        project_planning(payload([slot(status="absent"), slot(status="tentative")]), "a", period)


@pytest.fixture
async def planning_account(hass, config_entry, mock_api):
    config_entry.add_to_hass(hass)
    mock_api.async_get_planning.return_value = payload()
    with patch("custom_components.ouderapp.async_create_api", return_value=mock_api):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    return config_entry


async def call_planning(hass, account, context, **options):
    return await hass.services.async_call(
        "ouderapp",
        "get_planning",
        {
            "config_entry_id": account.entry_id,
            "start_date": "2026-10-25",
            "end_date": "2026-10-26",
            **options,
        },
        blocking=True,
        return_response=True,
        context=context,
    )


@pytest.mark.parametrize("format", ["json", "ics"])
async def test_planning_service_is_admin_only_and_not_in_sensor_states(
    hass, planning_account, mock_api, hass_read_only_user, hass_admin_user, format
):
    with pytest.raises(Unauthorized):
        await call_planning(
            hass, planning_account, Context(user_id=hass_read_only_user.id), format=format
        )
    mock_api.async_get_planning.assert_not_awaited()
    for context in (Context(), Context(user_id=hass_admin_user.id)):
        result = await call_planning(hass, planning_account, context, format=format)
        assert result["events"][0]["child"] == "Synthetic child"
        if format == "ics":
            parsed = Calendar.from_ical(result["calendar"])
            assert len(parsed.walk("VEVENT")) == 1
            assert result["filename"] == "ouderapp-2026-10-25-2026-10-26.ics"
            assert result["content_type"] == "text/calendar; charset=utf-8"
        else:
            assert "calendar" not in result
    assert "Synthetic child" not in str([state.as_dict() for state in hass.states.async_all()])


@pytest.mark.parametrize("change", ["unload", "replace", "disable", "auth"])
@pytest.mark.parametrize("format", ["json", "ics"])
async def test_planning_access_rechecked_after_await(
    hass, planning_account, mock_api, hass_admin_user, change, format
):
    coordinator = planning_account.runtime_data

    async def changing(*args):
        if change == "unload":
            planning_account.mock_state(hass, ConfigEntryState.NOT_LOADED)
        elif change == "replace":
            planning_account.runtime_data = object()
        elif change == "disable":
            await hass.auth.async_update_user(hass_admin_user, is_active=False)
        else:
            coordinator.invalidate_auth()
        return payload()

    mock_api.async_get_planning.side_effect = changing
    try:
        with pytest.raises(HomeAssistantError):
            await call_planning(
                hass, planning_account, Context(user_id=hass_admin_user.id), format=format
            )
    finally:
        planning_account.runtime_data = coordinator
        planning_account.mock_state(hass, ConfigEntryState.LOADED)


async def test_planning_auth_error_revokes_content_and_hides_provider_error(
    hass, planning_account, mock_api, caplog
):
    mock_api.async_get_planning.side_effect = OuderAppAuthError("PRIVATE-TOKEN")
    with pytest.raises(HomeAssistantError) as error:
        await call_planning(hass, planning_account, Context())
    assert planning_account.runtime_data.content_auth_failed
    assert "PRIVATE-TOKEN" not in str(error.value) + caplog.text


@pytest.mark.parametrize(
    "failure,diagnostic",
    [
        (OuderAppError("Unsupported planning time"), "planning.time"),
        (OuderAppError("PRIVATE-TOKEN"), "planning.source"),
        (RuntimeError("PRIVATE-TOKEN"), "planning.internal"),
    ],
)
async def test_planning_failure_reports_only_finite_diagnostic(
    hass, planning_account, mock_api, failure, diagnostic
):
    mock_api.async_get_planning.side_effect = failure
    with pytest.raises(HomeAssistantError) as error:
        await call_planning(hass, planning_account, Context())
    assert diagnostic in str(error.value)
    assert "PRIVATE-TOKEN" not in str(error.value)


async def test_planning_response_diagnostic_revalidates_mutable_fields(
    hass, planning_account, mock_api, caplog
):
    failure = OuderAppResponseError("invalid_json", "content")
    mock_api.async_get_planning.side_effect = failure
    with pytest.raises(HomeAssistantError, match="content.invalid_json"):
        await call_planning(hass, planning_account, Context())
    failure.reason = "PRIVATE-TOKEN"
    failure.stage = "PRIVATE-ACCOUNT"
    with pytest.raises(HomeAssistantError, match="unknown.unknown") as error:
        await call_planning(hass, planning_account, Context())
    assert "PRIVATE" not in str(error.value) + caplog.text


def test_calendar_parser_roundtrip_unicode_escaping_and_no_injected_components():
    data = payload()
    # Exercise untrusted text through the real planning projection first.
    name = "Zoë, 李; \\" + "🧒" * 65 + "\r\nBEGIN:VALARM\r\nACTION:DISPLAY\x01"
    data["days"][0]["children"][0]["child"]["firstName"] = name
    planning = project_planning(data, "account-a", period_for("2026-10-25", "2026-10-26"))
    encoded = export_calendar(planning)
    assert encoded.endswith("\r\n")
    assert "\n" not in encoded.replace("\r\n", "")
    for line in encoded.split("\r\n"):
        assert len(line.encode("utf-8")) <= 75
    parsed = Calendar.from_ical(encoded)
    assert not parsed.errors
    assert not parsed.walk("VALARM")
    (event,) = parsed.walk("VEVENT")
    assert not event.errors
    child = planning["events"][0]["child"].replace("\x01", "")
    assert str(event["SUMMARY"]) == f"Opvang — Voorlopig — {child}"
    assert str(event["CLASS"]) == "PRIVATE"
    assert str(event["TRANSP"]) == "TRANSPARENT"
    assert str(event["STATUS"]) == "TENTATIVE"
    assert "Bevestiging vereist" in str(event["DESCRIPTION"])
    assert "\n" in str(event["DESCRIPTION"])
    assert "ATTENDEE" not in event and "ORGANIZER" not in event and "URL" not in event
    assert "METHOD" not in parsed


@pytest.mark.parametrize(
    "start,end,start_utc,end_utc",
    [
        (
            "2026-10-25T01:30:00+02:00",
            "2026-10-25T03:30:00+01:00",
            "2026-10-24T23:30:00+00:00",
            "2026-10-25T02:30:00+00:00",
        ),
        (
            "2026-03-29T01:30:00+01:00",
            "2026-03-29T03:30:00+02:00",
            "2026-03-29T00:30:00+00:00",
            "2026-03-29T01:30:00+00:00",
        ),
    ],
)
def test_calendar_dst_instants_and_exclusive_end(start, end, start_utc, end_utc):
    period = period_for(start[:10], start[:8] + str(int(start[8:10]) + 1))
    planning = project_planning(payload([slot(start, end)]), "a", period)
    (event,) = Calendar.from_ical(export_calendar(planning)).walk("VEVENT")
    assert event.decoded("DTSTART") == datetime.fromisoformat(start_utc)
    assert event.decoded("DTEND") == datetime.fromisoformat(end_utc)
    assert event.decoded("DTSTAMP").utcoffset().total_seconds() == 0


def test_calendar_identity_and_status_do_not_invent_confirmation_or_cancellation():
    period = period_for("2026-10-25", "2026-10-26")
    uids = []
    for status, label in (
        ("attend", "Gepland"),
        ("absent", "Afwezig"),
        ("tentative", "Voorlopig"),
        ("new", "Status onbekend"),
    ):
        planning = project_planning(payload([slot(status=status)]), "a", period)
        (event,) = Calendar.from_ical(export_calendar(planning)).walk("VEVENT")
        assert label in str(event["SUMMARY"])
        assert str(event["X-OUDERAPP-STATUS"]) == planning["events"][0]["status"]
        if status != "tentative":
            assert "STATUS" not in event
        uids.append(str(event["UID"]))
    assert len(set(uids)) == 1
    other = project_planning(payload(), "b", period)
    (event,) = Calendar.from_ical(export_calendar(other)).walk("VEVENT")
    assert str(event["UID"]) != uids[0]


def test_calendar_removes_invalid_text_codepoints():
    data = payload()
    data["days"][0]["children"][0]["child"]["firstName"] = "A\ud800\x7fB"
    planning = project_planning(data, "a", period_for("2026-10-25", "2026-10-26"))
    (event,) = Calendar.from_ical(export_calendar(planning).encode("utf-8")).walk("VEVENT")
    assert str(event["SUMMARY"]) == "Opvang — Voorlopig — AB"


@pytest.mark.parametrize("problem", ["offline", "truncated", "empty"])
async def test_calendar_refuses_incomplete_or_empty_snapshots_but_json_still_works(
    hass, planning_account, mock_api, problem
):
    data = payload([slot(), slot("2026-10-25T10:00:00+01:00", "2026-10-25T11:00:00+01:00")])
    if problem == "offline":
        data["data_connector_offline"] = True
    elif problem == "empty":
        data["days"] = []
    mock_api.async_get_planning.return_value = data
    limit = 1 if problem == "truncated" else 50
    result = await call_planning(hass, planning_account, Context(), limit=limit)
    assert "calendar" not in result
    with pytest.raises(CalendarExportError):
        export_calendar(result)
    with pytest.raises(HomeAssistantError):
        await call_planning(hass, planning_account, Context(), limit=limit, format="ics")


@pytest.mark.parametrize("admin", [False, True])
async def test_planning_native_websocket_service_response_contract(
    hass,
    planning_account,
    mock_api,
    hass_ws_client,
    hass_access_token,
    hass_read_only_access_token,
    admin,
):
    client = await hass_ws_client(
        hass, access_token=hass_access_token if admin else hass_read_only_access_token
    )
    await client.send_json_auto_id(
        {
            "type": "call_service",
            "domain": "ouderapp",
            "service": "get_planning",
            "return_response": True,
            "service_data": {
                "config_entry_id": planning_account.entry_id,
                "start_date": "2026-10-25",
                "end_date": "2026-10-26",
                "format": "ics",
            },
        }
    )
    result = await client.receive_json()
    assert result["success"] is admin
    if admin:
        response = result["result"]["response"]
        assert len(Calendar.from_ical(response["calendar"]).walk("VEVENT")) == 1
    else:
        mock_api.async_get_planning.assert_not_awaited()


@pytest.mark.parametrize("confirmation", [True, False, None])
def test_attend_is_planned_and_confirmation_remains_independent(confirmation):
    part = slot(status="attend")
    part["toConfirmProduct"] = confirmation
    planning = project_planning(payload([part]), "a", period_for("2026-10-25", "2026-10-26"))
    event = planning["events"][0]
    assert event["status"] == "attend"
    assert event["confirmation_required"] is confirmation
    (exported,) = Calendar.from_ical(export_calendar(planning)).walk("VEVENT")
    assert "Gepland" in str(exported["SUMMARY"])
    assert "STATUS" not in exported
    assert ("Bevestiging vereist" in str(exported["DESCRIPTION"])) is (confirmation is True)
