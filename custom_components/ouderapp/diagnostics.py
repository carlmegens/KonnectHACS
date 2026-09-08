"""Allowlisted technical diagnostics, never account data or server responses."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL, VERSION


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry):
    coordinator = getattr(entry, "runtime_data", None)
    return {
        "version": VERSION,
        "poll_interval_minutes": entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
        "loaded": coordinator is not None,
        "last_update_success": coordinator.last_update_success if coordinator else None,
    }
