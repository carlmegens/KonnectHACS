"""Poll compact counters without storing private content in HA state."""

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import OuderAppApi, OuderAppAuthError, OuderAppConnectionError, OuderAppError
from .const import CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL, DOMAIN
from .content import OuderAppContent

_LOGGER = logging.getLogger(__name__)


class OuderAppCoordinator(DataUpdateCoordinator[dict[str, int | None]]):
    """One coordinator and transport per account."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: OuderAppApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(
                minutes=entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
            ),
        )
        self.api = api
        self.content = OuderAppContent(hass, api)
        self.messages = OuderAppContent(hass, api, messages=True)
        self.content_auth_failed = False
        self.last_success = None
        self._closed = False

    async def _async_update_data(self) -> dict[str, int | None]:
        try:
            data = await self.api.async_fetch_summary()
        except OuderAppAuthError:
            self.invalidate_auth()
            raise ConfigEntryAuthFailed("Sign in to OuderApp again") from None
        except OuderAppConnectionError:
            raise UpdateFailed("Unable to reach OuderApp") from None
        except OuderAppError:
            raise UpdateFailed("Unsupported OuderApp response") from None
        self.last_success = dt_util.utcnow()
        return data

    def invalidate_auth(self) -> None:
        self.content_auth_failed = True
        self.content.invalidate()
        self.messages.invalidate()
        self.async_set_update_error(ConfigEntryAuthFailed("Sign in to OuderApp again"))

    async def async_shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.content.invalidate()
        self.messages.invalidate()
        await super().async_shutdown()
        await self.content.async_close()
        await self.messages.async_close()
        await self.api.async_close()
