"""Runtime PV forecast service and rolling forecast revision archive."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import aiohttp

from .database import EnergyManagerStore, InfluxDatabaseError
from .diagnostics import DiagnosticsPublisher
from .ha_client import HomeAssistantClient, HomeAssistantError
from .open_meteo import FORECAST_MODEL, OpenMeteoClient, OpenMeteoError
from .pv_forecast import CALIBRATION_VERSION, PV_PLANES, PvForecast, build_pv_forecast

_LOGGER = logging.getLogger(__name__)
_LOCAL_TZ = ZoneInfo("Europe/Brussels")
_REFRESH_SECONDS = 1800.0
_RETRY_SECONDS = 300.0
_DEFAULT_ARCHIVE_PATH = Path("/data/pv_forecast_revisions.jsonl")


class PvForecastArchive:
    """Append compact daily forecast revisions for later accuracy analysis."""

    def __init__(self, path: Path = _DEFAULT_ARCHIVE_PATH) -> None:
        self._path = path

    def record(self, forecast: PvForecast, now_local: datetime) -> None:
        """Append one revision containing daily totals for the complete current horizon."""
        daily = forecast.daily_energies()
        if not daily:
            return

        payload = {
            "issued_at_utc": forecast.generated_at_utc.isoformat(),
            "issued_at_local": now_local.isoformat(),
            "model": FORECAST_MODEL,
            "calibration_version": CALIBRATION_VERSION,
            "daily": [
                {
                    "target_date": item.target_date.isoformat(),
                    "front_kwh": round(item.front_kwh, 4),
                    "rear_kwh": round(item.rear_kwh, 4),
                    "shed_kwh": round(item.shed_kwh, 4),
                    "total_kwh": round(item.total_kwh, 4),
                }
                for item in daily
            ],
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, separators=(",", ":")))
            handle.write("\n")


class PvForecastService:
    """Fetch, calculate, archive and publish the live four-plane PV forecast."""

    def __init__(
        self,
        ha_client: HomeAssistantClient,
        meteo_client: OpenMeteoClient,
        *,
        archive: PvForecastArchive | None = None,
        store: EnergyManagerStore | None = None,
    ) -> None:
        self._ha = ha_client
        self._meteo = meteo_client
        self._diagnostics = DiagnosticsPublisher(ha_client)
        self._archive = archive or PvForecastArchive()
        self._store = store
        self._forecast: PvForecast | None = None

    @property
    def forecast(self) -> PvForecast | None:
        """Expose the latest rolling forecast for the future planner."""
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
        """Run one complete rolling forecast update; useful for runtime and tests."""
        latitude, longitude = await self._home_coordinates()
        series = await self._meteo.fetch_planes(latitude, longitude, PV_PLANES)
        forecast = build_pv_forecast(series)
        self._forecast = forecast

        local_now = now_local or datetime.now(_LOCAL_TZ)
        try:
            if self._store is not None:
                await self._store.record_pv_forecast(forecast, local_now)
            else:
                self._archive.record(forecast, local_now)
        except (InfluxDatabaseError, OSError) as exc:
            _LOGGER.warning("Could not archive PV forecast revision: %s", exc)

        await self._diagnostics.publish_pv_forecast(forecast, now_local=local_now)
        await self._diagnostics.publish_pv_forecast_status(
            "connected",
            generated_at_utc=forecast.generated_at_utc,
        )
        _LOGGER.info(
            "PV forecast updated: today %.2f kWh, tomorrow %.2f kWh, next 7 days %.2f kWh",
            _total_or_zero(forecast, local_now.date()),
            _total_or_zero(forecast, local_now.date() + timedelta(days=1)),
            _future_week_total(forecast, local_now.date()),
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


def _future_week_total(forecast: PvForecast, today: date) -> float:
    total = 0.0
    for offset in range(1, 8):
        daily = forecast.daily_energy(today + timedelta(days=offset))
        if daily is not None:
            total += daily.total_kwh
    return total
