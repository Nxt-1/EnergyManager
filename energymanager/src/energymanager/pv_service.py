"""Runtime PV forecast service and persistent day-ahead snapshot handling."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import aiohttp

from .diagnostics import DiagnosticsPublisher
from .ha_client import HomeAssistantClient, HomeAssistantError
from .open_meteo import OpenMeteoClient, OpenMeteoError
from .pv_forecast import PV_PLANES, PvForecast, PvSnapshot, build_pv_forecast

_LOGGER = logging.getLogger(__name__)
_LOCAL_TZ = ZoneInfo("Europe/Brussels")
_REFRESH_SECONDS = 1800.0
_RETRY_SECONDS = 300.0
_SNAPSHOT_TIME = time(20, 15)
_DEFAULT_SNAPSHOT_PATH = Path("/data/pv_forecast_snapshots.json")


class PvSnapshotStore:
    """Persist evening day-ahead forecasts across app restarts/updates."""

    def __init__(self, path: Path = _DEFAULT_SNAPSHOT_PATH) -> None:
        self._path = path
        self._snapshots: dict[date, PvSnapshot] = {}
        self._load()

    def get(self, target_date: date) -> PvSnapshot | None:
        return self._snapshots.get(target_date)

    def capture_if_needed(self, forecast: PvForecast, now_local: datetime) -> PvSnapshot | None:
        """Capture tomorrow once the local day-ahead snapshot time has passed."""
        if now_local.timetz().replace(tzinfo=None) < _SNAPSHOT_TIME:
            return None

        target = now_local.date() + timedelta(days=1)
        existing = self._snapshots.get(target)
        if existing is not None:
            return existing

        daily = forecast.daily_energy(target)
        if daily is None:
            return None
        snapshot = PvSnapshot.from_daily_energy(daily, captured_at_utc=datetime.now(UTC))
        self._snapshots[target] = snapshot
        self._prune(now_local.date() - timedelta(days=90))
        self._save()
        return snapshot

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            _LOGGER.warning("Could not read PV snapshot store %s: %s", self._path, exc)
            return

        if not isinstance(raw, list):
            _LOGGER.warning("Ignoring malformed PV snapshot store %s", self._path)
            return

        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                snapshot = PvSnapshot(
                    target_date=date.fromisoformat(str(item["target_date"])),
                    captured_at_utc=datetime.fromisoformat(str(item["captured_at_utc"])),
                    front_kwh=float(item["front_kwh"]),
                    rear_kwh=float(item["rear_kwh"]),
                    shed_kwh=float(item["shed_kwh"]),
                    total_kwh=float(item["total_kwh"]),
                )
            except (KeyError, TypeError, ValueError):
                continue
            self._snapshots[snapshot.target_date] = snapshot

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = []
        for snapshot in sorted(self._snapshots.values(), key=lambda item: item.target_date):
            item = asdict(snapshot)
            item["target_date"] = snapshot.target_date.isoformat()
            item["captured_at_utc"] = snapshot.captured_at_utc.isoformat()
            payload.append(item)
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(self._path)

    def _prune(self, oldest_date: date) -> None:
        self._snapshots = {
            target_date: snapshot
            for target_date, snapshot in self._snapshots.items()
            if target_date >= oldest_date
        }


class PvForecastService:
    """Fetch, calculate, persist and publish the live four-plane PV forecast."""

    def __init__(
        self,
        ha_client: HomeAssistantClient,
        meteo_client: OpenMeteoClient,
        *,
        snapshot_store: PvSnapshotStore | None = None,
    ) -> None:
        self._ha = ha_client
        self._meteo = meteo_client
        self._diagnostics = DiagnosticsPublisher(ha_client)
        self._snapshots = snapshot_store or PvSnapshotStore()
        self._forecast: PvForecast | None = None

    @property
    def forecast(self) -> PvForecast | None:
        """Expose the latest forecast for the future planner."""
        return self._forecast

    async def run(self, stop_event: asyncio.Event) -> None:
        """Refresh continuously without allowing forecast failures to stop Energy Manager."""
        while not stop_event.is_set():
            delay = _REFRESH_SECONDS
            try:
                await self.update_once()
            except asyncio.CancelledError:
                raise
            except (HomeAssistantError, OpenMeteoError, aiohttp.ClientError, OSError, TimeoutError) as exc:
                _LOGGER.warning("PV forecast update failed: %s", exc)
                await self._diagnostics.publish_pv_forecast_status("error", error=str(exc))
                delay = _RETRY_SECONDS
            except Exception as exc:  # noqa: BLE001 - forecast failure must not stop the daemon.
                _LOGGER.exception("Unexpected PV forecast error")
                await self._diagnostics.publish_pv_forecast_status(
                    "error",
                    error=f"{type(exc).__name__}: {exc}",
                )
                delay = _RETRY_SECONDS

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=delay)
            except TimeoutError:
                pass

    async def update_once(self, *, now_local: datetime | None = None) -> PvForecast:
        """Run one complete forecast update; useful for runtime and tests."""
        latitude, longitude = await self._home_coordinates()
        series = await self._meteo.fetch_planes(latitude, longitude, PV_PLANES)
        forecast = build_pv_forecast(series)
        self._forecast = forecast

        local_now = now_local or datetime.now(_LOCAL_TZ)
        self._snapshots.capture_if_needed(forecast, local_now)
        await self._diagnostics.publish_pv_forecast(
            forecast,
            today_snapshot=self._snapshots.get(local_now.date()),
            tomorrow_snapshot=self._snapshots.get(local_now.date() + timedelta(days=1)),
            now_local=local_now,
        )
        await self._diagnostics.publish_pv_forecast_status(
            "connected",
            generated_at_utc=forecast.generated_at_utc,
        )
        _LOGGER.info(
            "PV forecast updated: today %.2f kWh, tomorrow %.2f kWh",
            _total_or_zero(forecast, local_now.date()),
            _total_or_zero(forecast, local_now.date() + timedelta(days=1)),
        )
        return forecast

    async def _home_coordinates(self) -> tuple[float, float]:
        state = await self._ha.get_state("zone.home")
        attributes = state.get("attributes") or {}
        try:
            return float(attributes["latitude"]), float(attributes["longitude"])
        except (KeyError, TypeError, ValueError) as exc:
            raise HomeAssistantError("zone.home has no usable latitude/longitude") from exc


def _total_or_zero(forecast: PvForecast, target_date: date) -> float:
    daily = forecast.daily_energy(target_date)
    return daily.total_kwh if daily else 0.0
