"""Actual flow, client, entities, persisted refresh and unload; mock HTTP only."""

from unittest.mock import patch

import httpx
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType


async def test_real_flow_transport_refresh_and_unload(hass, hass_ws_client):
    requests = []

    def server(request):
        requests.append(request)
        assert request.url.host == "example.ouderportaal.nl"
        path = request.url.path
        if path == "/auth-api/captcha":
            return httpx.Response(200, json={"result": True, "payload": None})
        if path == "/auth-api/login":
            return httpx.Response(200, json={"authToken": "a1", "refreshToken": "r1"})
        if path == "/auth-api/token":
            return httpx.Response(200, json={"authToken": "a2", "refreshToken": "r2"})
        assert "Authorization" in request.headers
        if path == "/auth-api/user":
            return httpx.Response(200, json={"username": "parent@example.invalid"})
        if path == "/restservices-parent/parent":
            return httpx.Response(200, json={"fullname": "Synthetic Parent"})
        if path == "/restservices-parent/children/":
            return httpx.Response(200, json={"activeChildren": [{"id": "c1"}]})
        if path == "/restservices-parent/notification/notifications":
            return httpx.Response(200, json={"nrOfNewMessages": 2})
        if path == "/restservices-parent/timeline/cards/v2/0":
            if request.headers["Authorization"] == "Bearer a1":
                return httpx.Response(401)
            return httpx.Response(
                200,
                json=[
                    {
                        "type": "journal",
                        "journal": {
                            "journalContent": "<p>SYNTHETIC-PRIVATE-TIMELINE</p>",
                            "photos": [],
                        },
                    }
                ],
            )
        raise AssertionError(f"Unexpected route: {path}")

    with patch.object(
        httpx.AsyncClient, "_transport_for_url", return_value=httpx.MockTransport(server)
    ):
        result = await hass.config_entries.flow.async_init("ouderapp", context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "portal": "example",
                "username": "typed",
                "password": "SYNTHETIC-SECRET",
            },
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
        entry = result["result"]
        assert entry.state is ConfigEntryState.LOADED
        assert len(hass.states.async_all()) == 5
        assert not any("timeline" in r.url.path or "logbook" in r.url.path for r in requests)
        with patch.object(hass.config_entries, "async_reload") as reload:
            client = await hass_ws_client(hass)
            await client.send_json_auto_id(
                {"type": "ouderapp/content", "kind": "timeline", "config_entry_id": entry.entry_id}
            )
            response = await client.receive_json()
            assert response["success"]
            items = response["result"]["items"]
            await hass.async_block_till_done()
            reload.assert_not_called()
        assert items[0]["contents"] == "SYNTHETIC-PRIVATE-TIMELINE"
        assert entry.data["session"]["refresh_token"] == "r2"
        dump = str([s.as_dict() for s in hass.states.async_all()])
        for secret in ("SYNTHETIC-PRIVATE", "parent@example.invalid", "SYNTHETIC-SECRET"):
            assert secret not in dump
        assert "SYNTHETIC-SECRET" not in str(entry.data)
        api = entry.runtime_data.api
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert api.client.is_closed
