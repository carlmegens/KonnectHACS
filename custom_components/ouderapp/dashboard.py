"""Authenticated content and media reads with per-account, per-source permissions."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from aiohttp import web
from homeassistant.auth.models import User
from homeassistant.components import websocket_api
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv

from .api import OuderAppAuthError, OuderAppConnectionError, OuderAppError
from .const import (
    CONF_DASHBOARD_VIEWERS,
    CONF_MESSAGE_VIEWERS,
    CONTENT_KINDS,
    CONTENT_LIMIT,
    DEFAULT_CONTENT_LIMIT,
    DOMAIN,
)
from .content import conversation_id

PRIVATE_HEADERS = {
    "Cache-Control": "private, no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


class DashboardError(Exception):
    def __init__(self, code: str, status: int = 502) -> None:
        super().__init__(code)
        self.code, self.status = code, status


def limit_value(value: Any) -> int:
    if type(value) is not int or not 1 <= value <= CONTENT_LIMIT:
        raise vol.Invalid("Invalid limit")
    return value


def conversation_value(value: Any) -> str:
    if not isinstance(value, str) or conversation_id(value) is None:
        raise vol.Invalid("Invalid conversation")
    return value


def source_for(kind: str) -> str:
    return "messages" if kind in ("conversations", "messages") else "timeline"


@callback
def can_view(entry: ConfigEntry, user: User | None, source: str) -> bool:
    key = CONF_MESSAGE_VIEWERS if source == "messages" else CONF_DASHBOARD_VIEWERS
    return bool(
        user and user.is_active and (user.is_admin or user.id in entry.options.get(key, []))
    )


async def entry_for_user(
    hass: HomeAssistant, entry_id: str, user_id: str, source: str
) -> ConfigEntry:
    user = await hass.auth.async_get_user(user_id)
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN or not can_view(entry, user, source):
        raise DashboardError("unauthorized", 403)
    if entry.state is not ConfigEntryState.LOADED:
        raise DashboardError("not_loaded", 503)
    if getattr(entry.runtime_data, "content_auth_failed", False):
        raise DashboardError("authentication_expired", 503)
    return entry


async def read_content(
    hass: HomeAssistant, entry_id: str, user_id: str, kind: str, **kwargs: Any
) -> dict[str, Any]:
    source = source_for(kind)
    entry = await entry_for_user(hass, entry_id, user_id, source)
    coordinator = entry.runtime_data
    try:
        feed = coordinator.messages if source == "messages" else coordinator.content
        result = await feed.async_get_content(kind, **kwargs)
    except OuderAppAuthError:
        coordinator.invalidate_auth()
        entry.async_start_reauth(hass)
        raise DashboardError("authentication_expired", 503) from None
    except OuderAppConnectionError:
        raise DashboardError("cannot_connect", 503) from None
    except OuderAppError:
        raise DashboardError("unsupported_response") from None
    except Exception:
        # No provider content or signed media addresses in logs or error messages.
        raise DashboardError("unsupported_response") from None
    current = await entry_for_user(hass, entry_id, user_id, source)
    if current is not entry or current.runtime_data is not coordinator:
        raise DashboardError("not_loaded", 503)
    return result


CONTENT_SCHEMA = {
    vol.Required("config_entry_id"): cv.string,
    vol.Required("kind"): vol.In(CONTENT_KINDS),
    vol.Optional("limit", default=DEFAULT_CONTENT_LIMIT): limit_value,
    vol.Optional("conversation"): conversation_value,
    vol.Optional("article"): conversation_value,
}


@callback
@websocket_api.websocket_command(
    {
        vol.Required("type"): "ouderapp/accounts",
        vol.Optional("source", default="timeline"): vol.In(("timeline", "messages")),
    }
)
@websocket_api.async_response
async def websocket_accounts(hass: HomeAssistant, connection: Any, msg: dict[str, Any]) -> None:
    user = await hass.auth.async_get_user(connection.user.id)
    connection.send_result(
        msg["id"],
        {
            "accounts": [
                {"config_entry_id": entry.entry_id, "title": entry.title or "OuderApp"}
                for entry in hass.config_entries.async_entries(DOMAIN)
                if can_view(entry, user, msg["source"])
            ]
        },
    )


@callback
@websocket_api.websocket_command({vol.Required("type"): "ouderapp/content", **CONTENT_SCHEMA})
@websocket_api.async_response
async def websocket_content(hass: HomeAssistant, connection: Any, msg: dict[str, Any]) -> None:
    try:
        result = await read_content(
            hass,
            msg["config_entry_id"],
            connection.user.id,
            msg["kind"],
            limit=msg["limit"],
            conversation=msg.get("conversation"),
            article=msg.get("article"),
        )
    except DashboardError as err:
        connection.send_error(msg["id"], err.code, "OuderApp content is unavailable")
        return
    connection.send_result(msg["id"], result)


class OuderAppContentView(HomeAssistantView):
    url = "/api/ouderapp/{config_entry_id}/content"
    name = "api:ouderapp:content"

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request, config_entry_id: str) -> web.Response:
        try:
            if set(request.query) - {"kind", "limit", "conversation", "article"} or any(
                len(request.query.getall(key)) > 1 for key in request.query
            ):
                raise ValueError
            args = vol.Schema(CONTENT_SCHEMA)(
                {
                    "config_entry_id": config_entry_id,
                    **request.query,
                    "limit": int(request.query.get("limit", str(DEFAULT_CONTENT_LIMIT))),
                }
            )
        except ValueError, vol.Invalid:
            return self.json({"code": "invalid_request"}, 400, headers=PRIVATE_HEADERS)
        user = request.get("hass_user")
        if user is None:
            return self.json({"code": "unauthorized"}, 401, headers=PRIVATE_HEADERS)
        try:
            args.pop("config_entry_id")
            result = await read_content(self.hass, config_entry_id, user.id, **args)
        except DashboardError as err:
            return self.json({"code": err.code}, err.status, headers=PRIVATE_HEADERS)
        return self.json(result, headers=PRIVATE_HEADERS)


class OuderAppImageView(HomeAssistantView):
    url = "/api/ouderapp/{config_entry_id}/image/{source}/{media_id}"
    name = "api:ouderapp:image"

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(
        self, request: web.Request, config_entry_id: str, source: str, media_id: str
    ) -> web.Response:
        user = request.get("hass_user")
        if user is None:
            return self.json({"code": "unauthorized"}, 401, headers=PRIVATE_HEADERS)
        if source not in ("timeline", "messages") or request.query:
            return self.json({"code": "invalid_request"}, 400, headers=PRIVATE_HEADERS)
        try:
            entry = await entry_for_user(self.hass, config_entry_id, user.id, source)
            coordinator = entry.runtime_data
            feed = coordinator.messages if source == "messages" else coordinator.content
            try:
                data, content_type = await feed.async_get_image(media_id)
            except Exception:
                raise DashboardError("image_unavailable", 404) from None
            current = await entry_for_user(self.hass, config_entry_id, user.id, source)
            if current is not entry or current.runtime_data is not coordinator:
                raise DashboardError("not_loaded", 503)
        except DashboardError as err:
            return self.json({"code": err.code}, err.status, headers=PRIVATE_HEADERS)
        return web.Response(body=data, content_type=content_type, headers=PRIVATE_HEADERS)


@callback
def async_register_dashboard(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, websocket_accounts)
    websocket_api.async_register_command(hass, websocket_content)
    hass.http.register_view(OuderAppContentView(hass))
    hass.http.register_view(OuderAppImageView(hass))
