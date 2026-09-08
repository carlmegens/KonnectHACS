"""Create isolated transports without blocking the Home Assistant event loop."""

from functools import partial
from typing import Any
from uuid import uuid4

import httpx
from homeassistant.core import HomeAssistant

from .api import OuderAppApi, Session
from .const import VERSION


async def async_create_api(
    hass: HomeAssistant,
    portal: str,
    session: Session | None = None,
    on_session=None,
) -> OuderAppApi:
    # SSL context creation reads certificate files; do that outside the event loop.
    client = await hass.async_add_executor_job(
        partial(
            httpx.AsyncClient,
            timeout=30,
            follow_redirects=False,
            trust_env=False,
            headers={"User-Agent": f"HomeAssistant-OuderApp/{VERSION}"},
        )
    )
    try:
        return OuderAppApi(client, portal, session, on_session)
    except BaseException:
        await client.aclose()
        raise


async def async_login(
    hass: HomeAssistant,
    portal: str,
    username: str,
    password: str,
) -> Session:
    api = await async_create_api(hass, portal)
    device: dict[str, Any] = {
        "name": "Home Assistant",
        "platform": "web",
        "uuid": str(uuid4()),
        "version": VERSION,
        "model": "Home Assistant integration",
        "screenHeight": 0,
        "screenWidth": 0,
    }
    try:
        return await api.async_login(username, password, device)
    finally:
        await api.async_close()
