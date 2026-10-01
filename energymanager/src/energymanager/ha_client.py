"""Minimal asynchronous Home Assistant API client for the Energy Manager app."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import quote

import aiohttp

REST_BASE_URL = "http://supervisor/core/api"
WEBSOCKET_URL = "ws://supervisor/core/websocket"


class HomeAssistantError(RuntimeError):
    """Raised when communication with Home Assistant fails."""


class HomeAssistantClient:
    """Read Home Assistant state and publish diagnostics through the Supervisor proxy."""

    def __init__(self, token: str) -> None:
        if not token:
            raise ValueError("SUPERVISOR_TOKEN is required")
        self._token = token
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> "HomeAssistantClient":
        timeout = aiohttp.ClientTimeout(total=15)
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        self._session = aiohttp.ClientSession(timeout=timeout, headers=headers)
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def get_state(self, entity_id: str) -> dict[str, Any]:
        """Return the current Home Assistant state object for one entity."""
        session = self._require_session()
        encoded_entity = quote(entity_id, safe="._-")
        url = f"{REST_BASE_URL}/states/{encoded_entity}"

        async with session.get(url) as response:
            if response.status == 404:
                raise HomeAssistantError(f"Home Assistant entity not found: {entity_id}")
            if response.status != 200:
                body = await response.text()
                raise HomeAssistantError(f"GET {url} returned HTTP {response.status}: {body}")
            return await response.json()

    async def set_state(self, entity_id: str, state: str | int | float, attributes: dict[str, Any]) -> None:
        """Create or update a Home Assistant state-machine entity used for diagnostics."""
        session = self._require_session()
        encoded_entity = quote(entity_id, safe="._-")
        url = f"{REST_BASE_URL}/states/{encoded_entity}"
        payload = {"state": str(state), "attributes": attributes}

        async with session.post(url, json=payload) as response:
            if response.status not in {200, 201}:
                body = await response.text()
                raise HomeAssistantError(f"POST {url} returned HTTP {response.status}: {body}")

    async def state_changes(self, entity_id: str) -> AsyncIterator[dict[str, Any]]:
        """Yield new state objects whenever the selected entity changes."""
        session = self._require_session()

        async with session.ws_connect(WEBSOCKET_URL, heartbeat=30) as websocket:
            await self._authenticate_websocket(websocket)
            subscription_id = 1
            await websocket.send_json(
                {
                    "id": subscription_id,
                    "type": "subscribe_trigger",
                    "trigger": {
                        "platform": "state",
                        "entity_id": entity_id,
                    },
                }
            )

            subscription_result = await self._receive_json(websocket)
            if (
                subscription_result.get("type") != "result"
                or subscription_result.get("id") != subscription_id
                or not subscription_result.get("success")
            ):
                raise HomeAssistantError(f"Unable to subscribe to {entity_id}: {subscription_result}")

            async for message in websocket:
                if message.type == aiohttp.WSMsgType.TEXT:
                    payload = json.loads(message.data)
                    if payload.get("type") != "event" or payload.get("id") != subscription_id:
                        continue

                    trigger = payload.get("event", {}).get("variables", {}).get("trigger", {})
                    new_state = trigger.get("to_state")
                    if isinstance(new_state, dict):
                        yield new_state
                    continue

                if message.type in {
                    aiohttp.WSMsgType.CLOSE,
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.CLOSING,
                    aiohttp.WSMsgType.ERROR,
                }:
                    break

        raise HomeAssistantError("Home Assistant WebSocket connection closed")

    async def _authenticate_websocket(self, websocket: aiohttp.ClientWebSocketResponse) -> None:
        """Perform the Home Assistant WebSocket authentication phase."""
        auth_required = await self._receive_json(websocket)
        if auth_required.get("type") != "auth_required":
            raise HomeAssistantError(f"Unexpected WebSocket authentication message: {auth_required}")

        await websocket.send_json({"type": "auth", "access_token": self._token})
        auth_result = await self._receive_json(websocket)
        if auth_result.get("type") != "auth_ok":
            raise HomeAssistantError(f"Home Assistant WebSocket authentication failed: {auth_result}")

    @staticmethod
    async def _receive_json(websocket: aiohttp.ClientWebSocketResponse) -> dict[str, Any]:
        """Receive exactly one JSON WebSocket message or raise a useful error."""
        message = await websocket.receive()
        if message.type != aiohttp.WSMsgType.TEXT:
            raise HomeAssistantError(f"Unexpected WebSocket message type: {message.type}")

        try:
            payload = json.loads(message.data)
        except json.JSONDecodeError as exc:
            raise HomeAssistantError("Home Assistant returned invalid WebSocket JSON") from exc

        if not isinstance(payload, dict):
            raise HomeAssistantError(f"Unexpected WebSocket payload: {payload!r}")
        return payload

    def _require_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            raise RuntimeError("HomeAssistantClient must be used as an async context manager")
        return self._session
