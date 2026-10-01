"""Energy Manager shadow-mode application lifecycle."""

from __future__ import annotations

import asyncio
import logging

import aiohttp

from .config import Settings
from .diagnostics import DiagnosticsPublisher
from .ha_client import HomeAssistantClient, HomeAssistantError
from .power import PowerStateError, power_w_from_state

_LOGGER = logging.getLogger(__name__)


class EnergyManagerApp:
    """First Energy Manager milestone: observe one power entity and prove HA round-trip communication."""

    def __init__(self, settings: Settings, client: HomeAssistantClient) -> None:
        self._settings = settings
        self._client = client
        self._diagnostics = DiagnosticsPublisher(client, settings.grid_power_entity)

    async def run(self, stop_event: asyncio.Event) -> None:
        """Run until Home Assistant stops the app."""
        await self._safe_publish_status("starting")

        if self._settings.grid_power_entity is None:
            _LOGGER.warning("No grid_power_entity configured; waiting in read-only idle mode")
            await self._safe_publish_status("waiting_for_configuration")
            await stop_event.wait()
            await self._safe_publish_status("stopping")
            return

        retry_delay = 1.0
        while not stop_event.is_set():
            try:
                await self._observe_grid_power(stop_event)
                retry_delay = 1.0
            except asyncio.CancelledError:
                raise
            except (HomeAssistantError, aiohttp.ClientError, OSError, TimeoutError) as exc:
                _LOGGER.warning("Home Assistant connection failed: %s", exc)
                await self._safe_publish_status("reconnecting", error=str(exc))
            except Exception as exc:  # noqa: BLE001 - keep daemon alive on unforeseen input/integration failures.
                _LOGGER.exception("Unexpected Energy Manager runtime error")
                await self._safe_publish_status("reconnecting", error=f"{type(exc).__name__}: {exc}")

            if stop_event.is_set():
                break

            _LOGGER.info("Retrying Home Assistant connection in %.1f s", retry_delay)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=retry_delay)
            except TimeoutError:
                pass
            retry_delay = min(retry_delay * 2.0, 30.0)

        await self._safe_publish_status("stopping")

    async def _observe_grid_power(self, stop_event: asyncio.Event) -> None:
        entity_id = self._settings.grid_power_entity
        if entity_id is None:
            return

        current_state = await self._client.get_state(entity_id)
        await self._process_grid_state(current_state)
        await self._diagnostics.publish_status("connected")
        _LOGGER.info("Connected to Home Assistant; observing %s", entity_id)

        state_changes = self._client.state_changes(entity_id)
        try:
            while not stop_event.is_set():
                next_state_task = asyncio.create_task(anext(state_changes))
                stop_task = asyncio.create_task(stop_event.wait())
                done, pending = await asyncio.wait(
                    {next_state_task, stop_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)

                if stop_task in done:
                    return

                new_state = next_state_task.result()
                await self._process_grid_state(new_state)
        finally:
            await state_changes.aclose()

    async def _process_grid_state(self, state: dict) -> None:
        try:
            power_w = power_w_from_state(state)
        except PowerStateError as exc:
            _LOGGER.warning("Ignoring grid-power update: %s", exc)
            return

        _LOGGER.debug("Observed grid power: %.3f W", power_w)
        await self._diagnostics.publish_grid_power(power_w, state)

    async def _safe_publish_status(self, status: str, *, error: str | None = None) -> None:
        try:
            await self._diagnostics.publish_status(status, error=error)
        except Exception as exc:  # noqa: BLE001 - diagnostics must never terminate the controller process.
            _LOGGER.debug("Unable to publish status %s: %s", status, exc)

