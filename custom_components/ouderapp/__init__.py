"""OuderApp (Konnect) for Home Assistant."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .api import OuderAppAuthError, OuderAppError, Session
from .const import CONF_SESSION
from .coordinator import OuderAppCoordinator
from .dashboard import async_register_dashboard
from .frontend import async_setup_frontend
from .runtime import async_create_api
from .services import async_register_services

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    async_register_dashboard(hass)
    async_register_services(hass)
    await async_setup_frontend(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[OuderAppCoordinator],
) -> bool:
    """Validate account before creating entities; clean up failed setup."""
    try:
        session = Session(**entry.data[CONF_SESSION])
    except TypeError, KeyError:
        raise ConfigEntryAuthFailed("Sign in to OuderApp again") from None
    if entry.unique_id != session.account_id:
        raise ConfigEntryAuthFailed("Account identity mismatch")

    async def save_session(current: Session) -> None:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_SESSION: current.storage()}
        )

    try:
        api = await async_create_api(hass, session.portal, session, save_session)
    except OuderAppAuthError, ValueError:
        raise ConfigEntryAuthFailed("Sign in to OuderApp again") from None
    coordinator = OuderAppCoordinator(hass, entry, api)
    try:
        try:
            await api.async_validate_account()
        except OuderAppAuthError:
            raise ConfigEntryAuthFailed("Sign in to OuderApp again") from None
        except OuderAppError:
            raise ConfigEntryNotReady("Unable to validate OuderApp account") from None
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await coordinator.async_shutdown()
        raise

    original_options = dict(entry.options)

    async def options_changed(hass: HomeAssistant, updated: ConfigEntry) -> None:
        # Persisting a rotated token must not reload the integration.
        if dict(updated.options) != original_options:
            await hass.config_entries.async_reload(updated.entry_id)

    entry.async_on_unload(entry.add_update_listener(options_changed))
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[OuderAppCoordinator],
) -> bool:
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.async_shutdown()
    return True
