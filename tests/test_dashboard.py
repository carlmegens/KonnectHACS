"""Exercise actual HA HTTP/WebSocket authentication and per-source rights."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Context
from homeassistant.exceptions import Unauthorized
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ouderapp.api import OuderAppAuthError

FEED = {"items": [{"contents": "PRIVATE-CONTENT", "images": []}], "stale": False}


@pytest.fixture
async def account(hass, config_entry, mock_api):
    config_entry.add_to_hass(hass)
    with patch("custom_components.ouderapp.async_create_api", return_value=mock_api):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    coordinator = config_entry.runtime_data
    with (
        patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock),
        patch.object(coordinator.content, "async_get_content", AsyncMock(return_value=FEED)),
        patch.object(coordinator.messages, "async_get_content", AsyncMock(return_value=FEED)),
        patch.object(
            coordinator.content,
            "async_get_image",
            AsyncMock(return_value=(b"PRIVATE-PHOTO", "image/jpeg")),
        ),
    ):
        yield config_entry


async def ws(client, entry, **fields):
    await client.send_json_auto_id(
        {
            "type": "ouderapp/content",
            "config_entry_id": entry.entry_id,
            "kind": "timeline",
            **fields,
        }
    )
    return await client.receive_json()


@pytest.mark.parametrize("allowed", [False, True])
async def test_accounts_and_content_rights(
    hass, account, hass_read_only_user, hass_read_only_access_token, hass_ws_client, allowed
):
    hidden = MockConfigEntry(domain="ouderapp", title="Hidden", unique_id="other", data={})
    hidden.add_to_hass(hass)
    if allowed:
        hass.config_entries.async_update_entry(
            account, options={"dashboard_viewers": [hass_read_only_user.id]}
        )
    client = await hass_ws_client(hass, access_token=hass_read_only_access_token)
    await client.send_json_auto_id({"type": "ouderapp/accounts"})
    result = (await client.receive_json())["result"]
    assert result["accounts"] == (
        [{"config_entry_id": account.entry_id, "title": account.title}] if allowed else []
    )
    response = await ws(client, account)
    assert response["success"] is allowed
    assert (await ws(client, account, kind="conversations"))["error"]["code"] == "unauthorized"
    assert (await ws(client, hidden))["error"]["code"] == "unauthorized"
    account.runtime_data.messages.async_get_content.assert_not_awaited()


async def test_message_viewer_cannot_read_timeline_or_other_account(
    hass, account, hass_read_only_user, hass_read_only_access_token, hass_ws_client
):
    hass.config_entries.async_update_entry(
        account, options={"message_viewers": [hass_read_only_user.id]}
    )
    client = await hass_ws_client(hass, access_token=hass_read_only_access_token)
    assert (await ws(client, account, kind="conversations"))["success"]
    assert (await ws(client, account))["error"]["code"] == "unauthorized"


@pytest.mark.parametrize("suffix", ["content?kind=timeline", "image/timeline/" + "x" * 32])
async def test_http_auth_and_private_headers(account, hass_client, hass_client_no_auth, suffix):
    no_auth = await hass_client_no_auth()
    assert (await no_auth.get(f"/api/ouderapp/{account.entry_id}/{suffix}")).status == 401
    client = await hass_client()
    response = await client.get(f"/api/ouderapp/{account.entry_id}/{suffix}")
    assert response.status == 200
    assert response.headers["Cache-Control"] == "private, no-store"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


@pytest.mark.parametrize(
    "fields",
    [
        {"limit": True},
        {"limit": 21},
        {"limit": "1"},
        {"kind": "unknown"},
        {"conversation": "../1"},
        {"source_url": "https://evil.invalid"},
    ],
)
async def test_ws_invalid_input_is_rejected_before_fetch(hass, account, hass_ws_client, fields):
    client = await hass_ws_client(hass)
    assert (await ws(client, account, **fields))["error"]["code"] == "invalid_format"
    account.runtime_data.content.async_get_content.assert_not_awaited()


@pytest.mark.parametrize(
    "query",
    [
        "kind=timeline&limit=1&limit=2",
        "kind=timeline&kind=news",
        "kind=unknown",
        "kind=timeline&url=private",
        "kind=timeline&limit=0",
    ],
)
async def test_http_invalid_queries(account, hass_client, query):
    client = await hass_client()
    response = await client.get(f"/api/ouderapp/{account.entry_id}/content?{query}")
    assert response.status == 400
    account.runtime_data.content.async_get_content.assert_not_awaited()


@pytest.mark.parametrize("image", [False, True])
@pytest.mark.parametrize("change", ["revoke", "disable", "unload", "reload", "auth"])
async def test_access_change_during_read_withholds_content(
    hass, account, hass_client, hass_read_only_user, hass_read_only_access_token, image, change
):
    hass.config_entries.async_update_entry(
        account, options={"dashboard_viewers": [hass_read_only_user.id]}
    )
    coordinator = account.runtime_data

    async def changing(*args, **kwargs):
        if change == "revoke":
            hass.config_entries.async_update_entry(account, options={})
        elif change == "disable":
            await hass.auth.async_update_user(hass_read_only_user, is_active=False)
        elif change == "unload":
            account.mock_state(hass, ConfigEntryState.NOT_LOADED)
        elif change == "reload":
            account.runtime_data = object()
        else:
            coordinator.invalidate_auth()
        return (b"PRIVATE-PHOTO", "image/jpeg") if image else FEED

    method = coordinator.content.async_get_image if image else coordinator.content.async_get_content
    method.side_effect = changing
    client = await hass_client(hass_read_only_access_token)
    suffix = "image/timeline/" + "x" * 32 if image else "content?kind=timeline"
    try:
        response = await client.get(f"/api/ouderapp/{account.entry_id}/{suffix}")
        assert response.status in (403, 503)
        assert "PRIVATE" not in await response.text()
    finally:
        account.runtime_data = coordinator
        account.mock_state(hass, ConfigEntryState.LOADED)


async def test_auth_failure_revokes_both_sources(hass, account, hass_ws_client, caplog):
    coordinator = account.runtime_data
    coordinator.messages._media_id("https://resource.kidskonnect.cloud/private")
    coordinator.content.async_get_content.side_effect = OuderAppAuthError("PRIVATE-TOKEN")
    client = await hass_ws_client(hass)
    response = await ws(client, account)
    assert response["error"]["code"] == "authentication_expired"
    assert not coordinator.messages._refs
    assert coordinator.content_auth_failed
    assert "PRIVATE-TOKEN" not in caplog.text + str(response)
    assert (await ws(client, account, kind="conversations"))["error"][
        "code"
    ] == "authentication_expired"


async def test_content_action_requires_admin_but_supports_automation(
    hass, account, hass_read_only_user, hass_admin_user
):
    args = {"config_entry_id": account.entry_id, "kind": "timeline"}
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            "ouderapp",
            "get_content",
            args,
            blocking=True,
            return_response=True,
            context=Context(user_id=hass_read_only_user.id),
        )
    for context in (Context(), Context(user_id=hass_admin_user.id)):
        assert (
            await hass.services.async_call(
                "ouderapp",
                "get_content",
                args,
                blocking=True,
                return_response=True,
                context=context,
            )
            == FEED
        )
