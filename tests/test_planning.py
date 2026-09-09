"""Planning API bounds, Dutch date handling, projection and real HA authorization."""

from copy import deepcopy
from datetime import datetime
from unittest.mock import patch

import httpx
import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError, Unauthorized

from custom_components.ouderapp.api import OuderAppApi, OuderAppAuthError, OuderAppError
from custom_components.ouderapp.planning import period_for, project_planning


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


async def call_planning(hass, account, context):
    return await hass.services.async_call(
        "ouderapp",
        "get_planning",
        {"config_entry_id": account.entry_id, "start_date": "2026-10-25", "end_date": "2026-10-26"},
        blocking=True,
        return_response=True,
        context=context,
    )


async def test_planning_service_is_admin_only_and_not_in_sensor_states(
    hass, planning_account, mock_api, hass_read_only_user, hass_admin_user
):
    with pytest.raises(Unauthorized):
        await call_planning(hass, planning_account, Context(user_id=hass_read_only_user.id))
    mock_api.async_get_planning.assert_not_awaited()
    for context in (Context(), Context(user_id=hass_admin_user.id)):
        result = await call_planning(hass, planning_account, context)
        assert result["events"][0]["child"] == "Synthetic child"
    assert "Synthetic child" not in str([state.as_dict() for state in hass.states.async_all()])


@pytest.mark.parametrize("change", ["unload", "replace", "disable", "auth"])
async def test_planning_access_rechecked_after_await(
    hass, planning_account, mock_api, hass_admin_user, change
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
            await call_planning(hass, planning_account, Context(user_id=hass_admin_user.id))
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
