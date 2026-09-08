"""Sign in through Home Assistant; keep passwords out of saved configuration."""

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .api import (
    OuderAppAuthError,
    OuderAppConnectionError,
    OuderAppError,
    OuderAppInteractionRequired,
    normalize_portal,
)
from .const import (
    CONF_DASHBOARD_VIEWERS,
    CONF_MESSAGE_VIEWERS,
    CONF_POLL_INTERVAL,
    CONF_PORTAL,
    CONF_SESSION,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MAX_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
)
from .runtime import async_login


class OuderAppConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure a tenant and a verified parent account."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors = {}
        portal_default = "deeerstestap"
        if self.source == config_entries.SOURCE_REAUTH:
            portal_default = self._get_reauth_entry().data[CONF_SESSION][CONF_PORTAL]
        if user_input is not None:
            try:
                portal = normalize_portal(user_input[CONF_PORTAL])
                session = await async_login(
                    self.hass, portal, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            except ValueError:
                errors[CONF_PORTAL] = "invalid_portal"
            except OuderAppInteractionRequired:
                errors["base"] = "interaction_required"
            except OuderAppAuthError:
                errors["base"] = "invalid_auth"
            except OuderAppConnectionError:
                errors["base"] = "cannot_connect"
            except OuderAppError:
                errors["base"] = "unsupported_response"
            else:
                await self.async_set_unique_id(session.account_id)
                data = {CONF_SESSION: session.storage()}
                if self.source == config_entries.SOURCE_REAUTH:
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), data_updates=data
                    )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=f"OuderApp — {portal}", data=data)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PORTAL, default=portal_default): str,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        if user_input is not None:
            return await self.async_step_user()
        return self.async_show_form(step_id="reauth_confirm", data_schema=vol.Schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> "OuderAppOptionsFlow":
        return OuderAppOptionsFlow()


class OuderAppOptionsFlow(config_entries.OptionsFlow):
    """Configure polling and explicit read access to the account dashboard."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        users = [
            user
            for user in await self.hass.auth.async_get_users()
            if user.is_active and not user.is_admin and not user.system_generated
        ]
        user_ids = {user.id for user in users}
        errors: dict[str, str] = {}
        if user_input is not None:
            data = dict(user_input)
            for key in (CONF_DASHBOARD_VIEWERS, CONF_MESSAGE_VIEWERS):
                viewers = user_input.get(key, [])
                if not isinstance(viewers, list) or any(
                    viewer not in user_ids for viewer in viewers
                ):
                    errors[key] = "invalid_viewers"
                else:
                    data[key] = list(dict.fromkeys(viewers))
            if not errors:
                return self.async_create_entry(title="", data=data)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_POLL_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                        ),
                    ): vol.All(
                        vol.Coerce(int), vol.Range(min=MIN_POLL_INTERVAL, max=MAX_POLL_INTERVAL)
                    ),
                    **{
                        vol.Optional(
                            key,
                            default=[
                                viewer
                                for viewer in self.config_entry.options.get(key, [])
                                if viewer in user_ids
                            ],
                        ): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=[
                                    {"value": user.id, "label": user.name or user.id}
                                    for user in users
                                ],
                                multiple=True,
                                mode=selector.SelectSelectorMode.DROPDOWN,
                            )
                        )
                        for key in (CONF_DASHBOARD_VIEWERS, CONF_MESSAGE_VIEWERS)
                    },
                }
            ),
            errors=errors,
        )
