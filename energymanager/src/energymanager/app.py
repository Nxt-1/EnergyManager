"""Energy Manager read-only house-state application lifecycle."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import aiohttp

from .config import Settings
from .diagnostics import DiagnosticsPublisher
from .ha_client import HomeAssistantClient, HomeAssistantError
from .house_state import HouseState
from .inputs import InputSpec, build_input_specs
from .power import PowerStateError

if TYPE_CHECKING:
    from .pv_service import PvForecastService

_LOGGER = logging.getLogger(__name__)
_REFRESH_INTERVAL = 30.0
_STALE_AFTER = timedelta(seconds=90)


class EnergyManagerApp:
    """Observe configured Home Assistant inputs and maintain a normalized house state."""

    def __init__(
        self,
        settings: Settings,
        client: HomeAssistantClient,
        pv_forecast_service: PvForecastService | None = None,
    ) -> None:
        self._settings = settings
        self._client = client
        self._pv_forecast_service = pv_forecast_service
        self._diagnostics = DiagnosticsPublisher(client)
        self._house_state = HouseState()
        self._specs = build_input_specs(settings)
        self._specs_by_entity: dict[str, list[InputSpec]] = defaultdict(list)
        self._last_status: tuple[str, str | None] | None = None

        for spec in self._specs:
            self._house_state.ensure_input(spec.key, spec.entity_id)
            if spec.entity_id is not None:
                self._specs_by_entity[spec.entity_id].append(spec)

    @property
    def house_state(self) -> HouseState:
        """Expose the canonical state for later predictors/planner code."""
        return self._house_state

    async def run(self, stop_event: asyncio.Event) -> None:
        """Run until Home Assistant stops the app."""
        await self._safe_publish_status("starting")
        await self._migrate_legacy_configuration()
        await self._cleanup_legacy_diagnostics()

        pv_task = None
        if self._pv_forecast_service is not None:
            pv_task = asyncio.create_task(self._pv_forecast_service.run(stop_event))

        try:
            retry_delay = 1.0
            while not stop_event.is_set():
                try:
                    await self._observe_inputs(stop_event)
                    retry_delay = 1.0
                except asyncio.CancelledError:
                    raise
                except (HomeAssistantError, aiohttp.ClientError, OSError, TimeoutError) as exc:
                    _LOGGER.warning("Home Assistant connection failed: %s", exc)
                    await self._safe_publish_status("reconnecting", error=str(exc))
                except Exception as exc:  # noqa: BLE001 - daemon should survive unforeseen integration failures.
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
        finally:
            if pv_task is not None and not pv_task.done():
                pv_task.cancel()
                await asyncio.gather(pv_task, return_exceptions=True)

        await self._safe_publish_status("stopping")

    async def _observe_inputs(self, stop_event: asyncio.Event) -> None:
        entities = tuple(self._specs_by_entity)
        await self._refresh_all_inputs()
        await self._publish_house_state()

        if not entities:
            _LOGGER.warning("No Home Assistant input entities are configured")
            await stop_event.wait()
            return

        _LOGGER.info("Connected to Home Assistant; observing %d configured entities", len(entities))
        state_changes = self._client.state_changes(entities)
        try:
            next_state_task = asyncio.create_task(anext(state_changes))
            refresh_task = asyncio.create_task(asyncio.sleep(_REFRESH_INTERVAL))
            stop_task = asyncio.create_task(stop_event.wait())

            while not stop_event.is_set():
                done, _ = await asyncio.wait(
                    {next_state_task, refresh_task, stop_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if stop_task in done:
                    break

                if next_state_task in done:
                    entity_id, new_state = next_state_task.result()
                    self._process_entity_state(entity_id, new_state)
                    await self._publish_house_state()
                    next_state_task = asyncio.create_task(anext(state_changes))

                if refresh_task in done:
                    await self._refresh_all_inputs()
                    self._house_state.update_staleness(_STALE_AFTER)
                    await self._publish_house_state()
                    refresh_task = asyncio.create_task(asyncio.sleep(_REFRESH_INTERVAL))
        finally:
            for task in (locals().get("next_state_task"), locals().get("refresh_task"), locals().get("stop_task")):
                if isinstance(task, asyncio.Task) and not task.done():
                    task.cancel()
            await asyncio.gather(
                *[
                    task
                    for task in (
                        locals().get("next_state_task"),
                        locals().get("refresh_task"),
                        locals().get("stop_task"),
                    )
                    if isinstance(task, asyncio.Task)
                ],
                return_exceptions=True,
            )
            await state_changes.aclose()

    async def _refresh_all_inputs(self) -> None:
        """Refresh all configured inputs so unchanged HA states also stay fresh."""
        entities = tuple(self._specs_by_entity)
        if not entities:
            return

        results = await asyncio.gather(
            *(self._client.get_state(entity_id) for entity_id in entities),
            return_exceptions=True,
        )
        now = datetime.now(UTC)
        for entity_id, result in zip(entities, results, strict=True):
            if isinstance(result, Exception):
                self._mark_entity_invalid(entity_id, str(result), observed_at_utc=now)
                continue
            self._process_entity_state(entity_id, result, observed_at_utc=now)

    def _process_entity_state(
        self,
        entity_id: str,
        state: dict[str, Any],
        *,
        observed_at_utc: datetime | None = None,
    ) -> None:
        observed_at = observed_at_utc or datetime.now(UTC)
        source_last_updated = state.get("last_updated") or state.get("last_reported")
        for spec in self._specs_by_entity.get(entity_id, ()):
            reading = self._house_state.reading(spec.key)
            try:
                value = spec.parser(state)
            except PowerStateError as exc:
                reading.set_invalid(
                    str(exc),
                    observed_at_utc=observed_at,
                    source_last_updated=source_last_updated,
                )
                _LOGGER.warning("Input %s (%s) is unavailable: %s", spec.key, entity_id, exc)
                continue

            reading.set_valid(
                value,
                unit=spec.unit,
                observed_at_utc=observed_at,
                source_last_updated=source_last_updated,
            )
            _LOGGER.debug("Observed %s from %s: %r %s", spec.key, entity_id, value, spec.unit or "")

    def _mark_entity_invalid(self, entity_id: str, reason: str, *, observed_at_utc: datetime) -> None:
        for spec in self._specs_by_entity.get(entity_id, ()):
            self._house_state.reading(spec.key).set_invalid(reason, observed_at_utc=observed_at_utc)
        _LOGGER.warning("Unable to refresh %s: %s", entity_id, reason)

    async def _publish_house_state(self) -> None:
        for reading in self._house_state.readings.values():
            await self._diagnostics.publish_reading(reading)
        await self._diagnostics.publish_derived(self._house_state)

        status, error = self._current_health()
        health = "healthy" if status == "connected" else status
        await self._diagnostics.publish_input_health(self._house_state, health)
        await self._safe_publish_status(status, error=error)

    def _current_health(self) -> tuple[str, str | None]:
        if not self._settings.grid.configured:
            return "waiting_for_configuration", "Grid import/export entities are not both configured"

        problems = self._house_state.invalid_or_stale
        if problems:
            summary = "; ".join(f"{reading.key}: {reading.error or reading.status.value}" for reading in problems)
            return "degraded", summary
        return "connected", None

    async def _migrate_legacy_configuration(self) -> None:
        if not self._settings.legacy_options_detected:
            return
        try:
            await self._client.replace_own_options(self._settings.as_options())
        except HomeAssistantError as exc:
            _LOGGER.warning("Could not migrate v0.2 flat configuration to grouped options: %s", exc)
            return
        _LOGGER.info("Migrated v0.2 grid options to grouped v0.3 configuration")

    async def _cleanup_legacy_diagnostics(self) -> None:
        try:
            await self._diagnostics.cleanup_legacy_entities()
        except HomeAssistantError as exc:
            _LOGGER.warning("Could not remove legacy Energy Manager diagnostics: %s", exc)

    async def _safe_publish_status(self, status: str, *, error: str | None = None) -> None:
        signature = (status, error)
        if signature == self._last_status:
            return
        try:
            await self._diagnostics.publish_status(status, house_state=self._house_state, error=error)
        except Exception as exc:  # noqa: BLE001 - diagnostics must never terminate the controller process.
            _LOGGER.debug("Unable to publish status %s: %s", status, exc)
            return
        self._last_status = signature
