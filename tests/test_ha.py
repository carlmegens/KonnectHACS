"""Validate lifecycle and config flows in Home Assistant Core 2026.8.3."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType

from custom_components.ouderapp.api import (
    OuderAppAuthError,
    OuderAppConnectionError,
    OuderAppError,
    OuderAppInteractionRequired,
    account_key,
)
from custom_components.ouderapp.diagnostics import async_get_config_entry_diagnostics


async def test_setup_entities_failure_and_recovery(hass, config_entry, mock_api):
    config_entry.add_to_hass(hass)
    with patch("custom_components.ouderapp.async_create_api", return_value=mock_api):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    states = {s.entity_id: s for s in hass.states.async_all()}
    assert len(states) == 5
    assert any(s.state == "2" for s in states.values())
    assert any(s.state == "3" for s in states.values())
    assert any(s.state == "unknown" for s in states.values())
    state_dump = json.dumps({k: dict(v.attributes) for k, v in states.items()})
    assert "synthetic@example.invalid" not in state_dump
    assert "access-test" not in state_dump
    coordinator = config_entry.runtime_data
    first_success = coordinator.last_success
    mock_api.async_fetch_summary.side_effect = OuderAppConnectionError("safe")
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.last_success == first_success
    assert next(s for s in hass.states.async_all() if s.domain == "binary_sensor").state == "off"
    assert sum(s.state == "unavailable" for s in hass.states.async_all()) == 3
    mock_api.async_fetch_summary.side_effect = None
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert next(s for s in hass.states.async_all() if s.domain == "binary_sensor").state == "on"
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    mock_api.async_close.assert_awaited_once()


async def test_refresh_save_does_not_reload_options_do(hass, config_entry, mock_api, session):
    config_entry.add_to_hass(hass)
    with patch("custom_components.ouderapp.async_create_api", return_value=mock_api) as factory:
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    callback = factory.call_args.args[3]
    with patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock) as reload:
        session.access_token = "new-access"
        await callback(session)
        await hass.async_block_till_done()
        reload.assert_not_called()
        hass.config_entries.async_update_entry(config_entry, options={"poll_interval": 45})
        await hass.async_block_till_done()
        reload.assert_awaited_once_with(config_entry.entry_id)


@pytest.mark.parametrize(
    "error,state",
    [
        (OuderAppAuthError("safe"), ConfigEntryState.SETUP_ERROR),
        (OuderAppConnectionError("safe"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_failed_setup_closes_client(hass, config_entry, mock_api, error, state):
    config_entry.add_to_hass(hass)
    mock_api.async_validate_account.side_effect = error
    with patch("custom_components.ouderapp.async_create_api", return_value=mock_api):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    assert config_entry.state is state
    mock_api.async_close.assert_awaited_once()


async def test_config_flow_no_password_storage_and_duplicate(hass, session):
    values = {"portal": "EXAMPLE.ouderportaal.nl", "username": "typed", "password": "secret"}
    with patch("custom_components.ouderapp.config_flow.async_login", return_value=session):
        with patch("custom_components.ouderapp.async_setup_entry", return_value=True):
            result = await hass.config_entries.flow.async_init(
                "ouderapp", context={"source": config_entries.SOURCE_USER}, data=values
            )
            await hass.async_block_till_done()
            assert result["type"] is FlowResultType.CREATE_ENTRY
            assert "secret" not in json.dumps(result["data"])
            duplicate = await hass.config_entries.flow.async_init(
                "ouderapp", context={"source": config_entries.SOURCE_USER}, data=values
            )
            assert duplicate["reason"] == "already_configured"


@pytest.mark.parametrize(
    "error,key",
    [
        (OuderAppAuthError("safe"), "invalid_auth"),
        (OuderAppInteractionRequired("safe"), "interaction_required"),
        (OuderAppConnectionError("safe"), "cannot_connect"),
        (OuderAppError("safe"), "unsupported_response"),
    ],
)
async def test_flow_safe_errors(hass, error, key):
    with patch("custom_components.ouderapp.config_flow.async_login", side_effect=error):
        result = await hass.config_entries.flow.async_init(
            "ouderapp",
            context={"source": config_entries.SOURCE_USER},
            data={"portal": "example", "username": "typed", "password": "secret"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": key}


async def test_invalid_portal_never_submits_credentials(hass):
    with patch("custom_components.ouderapp.config_flow.async_login") as login:
        result = await hass.config_entries.flow.async_init(
            "ouderapp",
            context={"source": config_entries.SOURCE_USER},
            data={"portal": "https://evil.invalid", "username": "typed", "password": "secret"},
        )
    login.assert_not_called()
    assert result["errors"] == {"portal": "invalid_portal"}


async def test_diagnostics_allowlist(hass, config_entry):
    data = await async_get_config_entry_diagnostics(hass, config_entry)
    assert set(data) == {"version", "poll_interval_minutes", "loaded", "last_update_success"}
    assert "access-test" not in json.dumps(data)
    assert "synthetic" not in json.dumps(data)


@pytest.mark.parametrize("same_account", [True, False])
async def test_reauth_rejects_account_swap(hass, config_entry, session, same_account):
    config_entry.add_to_hass(hass)
    old = dict(config_entry.data)
    result = await hass.config_entries.flow.async_init(
        "ouderapp",
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": config_entry.entry_id,
        },
        data=dict(config_entry.data),
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "user"
    session.access_token = "new-token"
    if not same_account:
        session.username = "someone-else@example.invalid"
        session.account_id = account_key(session.portal, session.username)
    with (
        patch("custom_components.ouderapp.config_flow.async_login", return_value=session),
        patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock) as reload,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "portal": "example",
                "username": "typed",
                "password": "private",
            },
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    if same_account:
        assert result["reason"] == "reauth_successful"
        assert config_entry.data["session"]["access_token"] == "new-token"
        reload.assert_awaited_once()
    else:
        assert result["reason"] == "unique_id_mismatch"
        assert config_entry.data == old
        reload.assert_not_called()


@pytest.mark.parametrize("interval", [15, 30, 240])
async def test_poll_options(hass, config_entry, interval):
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "poll_interval": interval,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options["poll_interval"] == interval


@pytest.mark.parametrize("interval", [0, 14, 241, "bad"])
async def test_poll_schema_rejects_invalid_values(hass, config_entry, interval):
    import voluptuous as vol

    config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    with pytest.raises(vol.Invalid):
        result["data_schema"]({"poll_interval": interval})


async def test_viewer_options_validate_users_and_keep_sources_separate(
    hass, config_entry, hass_read_only_user
):
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "poll_interval": 30,
            "dashboard_viewers": [hass_read_only_user.id],
            "message_viewers": [],
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options["dashboard_viewers"] == [hass_read_only_user.id]
    assert config_entry.options["message_viewers"] == []
