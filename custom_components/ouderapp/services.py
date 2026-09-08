"""Administrator-only, bounded content response action for trusted automations."""

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.service import async_register_admin_service

from .api import OuderAppAuthError, OuderAppError
from .const import DOMAIN
from .dashboard import CONTENT_SCHEMA, DashboardError, read_content, source_for


@callback
def async_register_services(hass: HomeAssistant) -> None:
    async def get_content(call: ServiceCall) -> dict:
        values = dict(call.data)
        entry_id = values.pop("config_entry_id")
        if call.context.user_id:
            try:
                return await read_content(hass, entry_id, call.context.user_id, **values)
            except DashboardError as err:
                raise HomeAssistantError(f"OuderApp: {err.code}") from None
        # A trusted automation has no user identity. Still require the same loaded
        # account and recheck runtime after awaits (e.g. unload during download).
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError("OuderApp account is not loaded")
        coordinator = entry.runtime_data
        if coordinator.content_auth_failed:
            raise HomeAssistantError("OuderApp requires sign-in")
        feed = (
            coordinator.messages
            if source_for(values["kind"]) == "messages"
            else coordinator.content
        )
        try:
            result = await feed.async_get_content(**values)
        except OuderAppAuthError:
            coordinator.invalidate_auth()
            entry.async_start_reauth(hass)
            raise HomeAssistantError("OuderApp requires sign-in") from None
        except OuderAppError:
            raise HomeAssistantError("OuderApp content is unavailable") from None
        if (
            hass.config_entries.async_get_entry(entry_id) is not entry
            or entry.state is not ConfigEntryState.LOADED
            or entry.runtime_data is not coordinator
            or coordinator.content_auth_failed
        ):
            raise HomeAssistantError("OuderApp account is not loaded")
        return result

    async_register_admin_service(
        hass,
        DOMAIN,
        "get_content",
        get_content,
        schema=vol.Schema(CONTENT_SCHEMA),
        supports_response=SupportsResponse.ONLY,
    )
