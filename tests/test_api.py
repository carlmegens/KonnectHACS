"""Exercise actual HTTP contracts and recovery against a synthetic transport."""

import asyncio
import json
from unittest.mock import AsyncMock

import httpx
import pytest

from custom_components.ouderapp.api import (
    OuderAppApi,
    OuderAppAuthError,
    OuderAppConnectionError,
    OuderAppError,
    OuderAppInteractionRequired,
    normalize_portal,
)


@pytest.mark.parametrize(
    "value", ["example", "EXAMPLE", "example.ouderportaal.nl", "https://example.ouderportaal.nl/"]
)
def test_portal_normalization(value):
    assert normalize_portal(value) == "example"


@pytest.mark.parametrize(
    "value",
    [
        "https://evil.invalid",
        "../example",
        "example/path",
        "https://example.ouderportaal.nl:443",
        "https://a@example.ouderportaal.nl",
        "https://example.ouderportaal.nl/?a=1",
        "http://example.ouderportaal.nl",
        "a.b",
        "-example",
        "example-",
        "",
        "a" * 64,
    ],
)
def test_portal_rejects_arbitrary_destinations(value):
    with pytest.raises(ValueError):
        normalize_portal(value)


async def test_login_contract_and_password_not_persisted():
    requests = []

    def handle(request):
        requests.append(request)
        path = request.url.path
        assert request.url.host == "example.ouderportaal.nl"
        if path == "/auth-api/captcha":
            return httpx.Response(200, json={"result": True, "payload": None})
        if path == "/auth-api/login":
            assert request.method == "PUT"
            assert json.loads(request.content) == {
                "username": "typed",
                "password": "private-password",
                "deviceInfo": {"uuid": "test"},
            }
            return httpx.Response(
                200,
                json={
                    "authToken": "new-access",
                    "refreshToken": "new-refresh",
                    "domainServerName": "example.ouderportaal.nl",
                    "redirectUrl": "/parent",
                },
            )
        assert request.headers["Authorization"] == "Bearer new-access"
        return httpx.Response(200, json={"username": "verified@example.invalid"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        api = OuderAppApi(client, "example")
        result = await api.async_login("typed", "private-password", {"uuid": "test"})
        assert result.username == "verified@example.invalid"
        assert "private-password" not in json.dumps(result.storage())
        assert "new-access" not in repr(result)
        assert [r.url.path for r in requests] == [
            "/auth-api/captcha",
            "/auth-api/login",
            "/auth-api/user",
            "/restservices-parent/parent",
        ]


async def test_captcha_does_not_attempt_credentials():
    def handle(request):
        assert request.url.path == "/auth-api/captcha"
        return httpx.Response(200, json={"result": True, "payload": {"blockedUntil": 123}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(OuderAppInteractionRequired):
            await OuderAppApi(client, "example").async_login("a", "secret", {})


@pytest.mark.parametrize(
    "extra",
    [
        {"domainServerName": "evil.invalid"},
        {"redirectUrl": "https://evil.invalid/parent"},
        {"redirectUrl": "/employee"},
        {"mustResetPassword": True},
    ],
)
async def test_auth_destination_and_account_steps_are_not_followed(extra):
    requests = []

    def handle(request):
        requests.append(request.url.path)
        if request.url.path == "/auth-api/captcha":
            return httpx.Response(200, json={})
        return httpx.Response(200, json={"authToken": "a", "refreshToken": "r", **extra})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(OuderAppError):
            await OuderAppApi(client, "example").async_login("a", "secret", {})
        assert len(requests) == 2


async def test_refresh_rotates_and_persists_verified_session(session):
    seen = []
    saved = AsyncMock()

    def handle(request):
        seen.append(request)
        if request.url.path == "/auth-api/token":
            data = json.loads(request.content)
            assert data["refreshToken"] == "refresh-test"
            assert "password" not in data
            return httpx.Response(
                200, json={"authToken": "rotated", "refreshToken": "rotated-refresh"}
            )
        if request.url.path == "/auth-api/user":
            return httpx.Response(200, json={"username": session.username})
        if request.headers["Authorization"] == "Bearer access-test":
            return httpx.Response(401)
        return httpx.Response(
            200,
            json={"activeChildren": []}
            if request.url.path.endswith("/children/")
            else {"nrOfNewMessages": 4, "nrOfNewNewsItems": 0},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        api = OuderAppApi(client, "example", session, saved)
        assert await api.async_fetch_summary() == {
            "children_count": 0,
            "unread_messages": 4,
            "unread_news": 0,
        }
        saved.assert_awaited_once()
        assert saved.call_args.args[0].refresh_token == "rotated-refresh"
        assert sum(r.url.path == "/auth-api/token" for r in seen) == 1


async def test_concurrent_401_uses_one_refresh(session):
    gate = asyncio.Event()
    old_reads = 0
    refreshes = 0

    async def handle(request):
        nonlocal old_reads, refreshes
        if request.url.path == "/auth-api/token":
            refreshes += 1
            return httpx.Response(200, json={"authToken": "rotated", "refreshToken": "r2"})
        if request.url.path == "/auth-api/user":
            return httpx.Response(200, json={"username": session.username})
        if request.headers["Authorization"] == "Bearer access-test":
            old_reads += 1
            if old_reads == 2:
                gate.set()
            await gate.wait()
            return httpx.Response(401)
        return httpx.Response(200, json=[])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        api = OuderAppApi(client, "example", session)
        assert await asyncio.gather(api.async_get_timeline(), api.async_get_messages()) == [[], []]
        assert refreshes == 1


async def test_refresh_account_change_blocks_all_future_reads(session):
    calls = []

    def handle(request):
        calls.append(request.url.path)
        if request.url.path == "/auth-api/token":
            return httpx.Response(200, json={"authToken": "rotated", "refreshToken": "r2"})
        if request.url.path == "/auth-api/user":
            return httpx.Response(200, json={"username": "different@example.invalid"})
        return httpx.Response(401)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        api = OuderAppApi(client, "example", session)
        with pytest.raises(OuderAppAuthError):
            await api.async_get_timeline()
        count = len(calls)
        with pytest.raises(OuderAppAuthError):
            await api.async_get_messages()
        assert len(calls) == count


@pytest.mark.parametrize("status", [429, 500, 503])
async def test_transient_failure_does_not_refresh_or_disclose_body(session, status):
    def handle(request):
        assert request.url.path == "/restservices-parent/timeline/cards/v2/0"
        return httpx.Response(status, text="secret child content")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        api = OuderAppApi(client, "example", session)
        with pytest.raises(OuderAppConnectionError) as error:
            await api.async_get_timeline()
        assert "secret" not in str(error.value)
        assert not api.auth_failed


@pytest.mark.parametrize("value", [None, True, -1, "4", 4.0])
async def test_missing_or_invalid_counts_are_unknown(session, value):
    def handle(request):
        return httpx.Response(
            200,
            json={"activeChildren": []}
            if request.url.path.endswith("/children/")
            else {"nrOfNewMessages": value},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        result = await OuderAppApi(client, "example", session).async_fetch_summary()
        assert result["unread_messages"] is None
        assert result["unread_news"] is None


async def test_unknown_shape_does_not_silently_become_empty(session):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"unexpected": []}))
    ) as client:
        with pytest.raises(OuderAppError):
            await OuderAppApi(client, "example", session).async_get_timeline()


async def test_oversize_response_and_redirect_rejected(session):
    for response in (
        httpx.Response(200, content=b"x" * (2 * 1024 * 1024 + 1)),
        httpx.Response(302, headers={"Location": "https://evil.invalid"}),
    ):
        calls = []

        def handle(request):
            calls.append(request)
            return response

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            with pytest.raises(OuderAppError):
                await OuderAppApi(client, "example", session).async_get_timeline()
            assert len(calls) == 1


@pytest.mark.parametrize("limit", [0, 51, True, "10", -1])
async def test_invalid_limits_do_not_reach_network(session, limit):
    def handle(request):
        pytest.fail("Invalid limit reached the network")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError):
            await OuderAppApi(client, "example", session).async_get_timeline(limit)


@pytest.mark.parametrize(
    "method,path,payload,kwargs,expected",
    [
        (
            "async_get_news",
            "/restservices-parent/htmlnews/view",
            [{"title": "News"}],
            {"limit": 1},
            [{"title": "News"}],
        ),
        (
            "async_get_newsletters",
            "/restservices-parent/newsletter",
            {"newsletterItems": [{"mailSubject": "Letter"}]},
            {"limit": 1},
            [{"mailSubject": "Letter"}],
        ),
        (
            "async_get_messages",
            "/restservices-parent/logbook/overview",
            [{"logMessageMessageId": 12}],
            {"limit": 1},
            [{"logMessageMessageId": 12}],
        ),
        (
            "async_get_conversation",
            "/restservices-parent/logbook/details/12/summary/true",
            {
                "summary": {"subject": "Title"},
                "messages": [{"message": "First"}, {"message": "Last"}],
            },
            {"conversation": "12", "limit": 1},
            [{"message": "Last"}],
        ),
    ],
)
async def test_observed_content_routes_are_bounded_gets(
    session, method, path, payload, kwargs, expected
):
    def handle(request):
        assert request.method == "GET"
        assert request.url.path == path
        assert request.headers["Authorization"] == "Bearer access-test"
        if method in ("async_get_messages", "async_get_newsletters"):
            assert request.url.params["index"] == "0"
        return httpx.Response(200, json={"result": True, "payload": payload, "messages": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        api = OuderAppApi(client, "example", session)
        assert await getattr(api, method)(**kwargs) == expected


@pytest.mark.parametrize(
    "identifier", [None, True, 12, "0", "-1", "../12", "12/summary/false", "12\n", "1" * 21]
)
async def test_conversation_identifier_never_changes_api_path(session, identifier):
    def handle(request):
        pytest.fail("Invalid identifier reached network")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError):
            await OuderAppApi(client, "example", session).async_get_conversation(identifier)
