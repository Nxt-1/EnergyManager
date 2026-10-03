"""Energy Manager shadow-mode application lifecycle."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from .config import Settings
from .diagnostics import DiagnosticsPublisher
from .ha_client import HomeAssistantClient, HomeAssistantError
from .power import PowerStateError, grid_net_power_w, power_w_from_state

_LOGGER = logging.getLogger(__name__)


class EnergyManagerApp:
    """Observe separate grid import/export entities and publish a canonical read-only grid state."""

    def __init__(self, settings: Settings, client: HomeAssistantClient) -> None:
        self._settings = settings
        self._client = client
        self._diagnostics = DiagnosticsPublisher(
            client,
            settings.grid_import_power_entity,
            settings.grid_export_power_entity,
        )
        self._grid_values: dict[str, float | None] = {"import": None, "export": None}
        self._grid_states: dict[str, dict[str, Any] | None] = {"import": None, "export": None}
        self._grid_errors: dict[str, str | None] = {"import": None, "export": None}
        self._last_status: tuple[str, str | None] | None = None

    async def run(self, stop_event: asyncio.Event) -> None:
        """Run until Home Assistant stops the app."""
        await self._safe_publish_status("starting")

        if not self._settings.grid_power_configured:
            missing = []
            if self._settings.grid_import_power_entity is None:
                missing.append("grid_import_power_entity")
            if self._settings.grid_export_power_entity is None:
                missing.append("grid_export_power_entity")
            message = f"Missing required grid configuration: {', '.join(missing)}"
            _LOGGER.warning("%s; waiting in read-only idle mode", message)
            await self._safe_publish_status("waiting_for_configuration", error=message)
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
            except Exception as exc:  # noqa: BLE001 - keep daemon alive on unforeseen integration failures.
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
        import_entity = self._settings.grid_import_power_entity
        export_entity = self._settings.grid_export_power_entity
        if import_entity is None or export_entity is None:
            return

        import_state, export_state = await asyncio.gather(
            self._client.get_state(import_entity),
            self._client.get_state(export_entity),
        )
        await self._process_grid_state("import", import_state)
        await self._process_grid_state("export", export_state)
        await self._publish_grid_health()

        _LOGGER.info(
            "Connected to Home Assistant; observing grid import %s and export %s",
            import_entity,
            export_entity,
        )

        state_changes = self._client.state_changes((import_entity, export_entity))
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

                entity_id, new_state = next_state_task.result()
                kind = "import" if entity_id == import_entity else "export"
                await self._process_grid_state(kind, new_state)
                await self._publish_grid_health()
        finally:
            await state_changes.aclose()

    async def _process_grid_state(self, kind: str, state: dict[str, Any]) -> None:
        self._grid_states[kind] = state
        try:
            power_w = power_w_from_state(state)
            if power_w < 0:
                raise PowerStateError(f"Grid {kind} power cannot be negative: {power_w} W")
        except PowerStateError as exc:
            self._grid_values[kind] = None
            self._grid_errors[kind] = str(exc)
            _LOGGER.warning("Grid %s input is unavailable: %s", kind, exc)
            if kind == "import":
                await self._diagnostics.publish_import_unavailable(str(exc), state)
            else:
                await self._diagnostics.publish_export_unavailable(str(exc), state)
            return

        self._grid_values[kind] = power_w
        self._grid_errors[kind] = None
        _LOGGER.debug("Observed grid %s power: %.3f W", kind, power_w)
        if kind == "import":
            await self._diagnostics.publish_grid_import_power(power_w, state)
        else:
            await self._diagnostics.publish_grid_export_power(power_w, state)

    async def _publish_grid_health(self) -> None:
        import_power = self._grid_values["import"]
        export_power = self._grid_values["export"]
        import_state = self._grid_states["import"]
        export_state = self._grid_states["export"]

        if import_power is None or export_power is None or import_state is None or export_state is None:
            errors = [
                f"{kind}: {error}"
                for kind, error in self._grid_errors.items()
                if error is not None
            ]
            reason = "; ".join(errors) if errors else "Waiting for valid import and export measurements"
            await self._diagnostics.publish_grid_power_unavailable(reason)
            await self._safe_publish_status("degraded", error=reason)
            return

        try:
            net_power = grid_net_power_w(import_power, export_power)
        except PowerStateError as exc:
            await self._diagnostics.publish_grid_power_unavailable(str(exc))
            await self._safe_publish_status("degraded", error=str(exc))
            return

        await self._diagnostics.publish_grid_power(net_power, import_state, export_state)
        await self._safe_publish_status("connected")
        _LOGGER.debug("Derived net grid power: %.3f W", net_power)

    async def _safe_publish_status(self, status: str, *, error: str | None = None) -> None:
        signature = (status, error)
        if signature == self._last_status:
            return
        try:
            await self._diagnostics.publish_status(status, error=error)
        except Exception as exc:  # noqa: BLE001 - diagnostics must never terminate the controller process.
            _LOGGER.debug("Unable to publish status %s: %s", status, exc)
            return
        self._last_status = signature
