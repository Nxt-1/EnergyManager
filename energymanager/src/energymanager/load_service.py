"""Persistent background-load sampling and rolling forecast service."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .diagnostics import DiagnosticsPublisher
from .ha_client import HomeAssistantClient, HomeAssistantError
from .house_state import HouseState
from .load_forecast import MODEL_VERSION, BackgroundLoadForecast, BackgroundLoadModel, LoadSample

_LOGGER = logging.getLogger(__name__)
_LOCAL_TZ = ZoneInfo("Europe/Brussels")
_SAMPLE_INTERVAL = timedelta(minutes=5)
_FORECAST_INTERVAL = timedelta(minutes=30)
_HISTORY_RETENTION = timedelta(days=35)
_DEFAULT_HISTORY_PATH = Path("/data/background_load_history.jsonl")
_DEFAULT_ARCHIVE_PATH = Path("/data/background_load_forecast_revisions.jsonl")


class BackgroundLoadHistory:
    """Small persistent history store for canonical background-load observations."""

    def __init__(self, path: Path = _DEFAULT_HISTORY_PATH) -> None:
        self._path = path
        self._samples = self._load()

    @property
    def samples(self) -> tuple[LoadSample, ...]:
        return tuple(self._samples)

    @property
    def last_sample_at_utc(self) -> datetime | None:
        return self._samples[-1].observed_at_utc if self._samples else None

    def record(self, sample: LoadSample) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "observed_at_utc": sample.observed_at_utc.isoformat(),
            "power_w": round(sample.power_w, 3),
        }
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, separators=(",", ":")))
            handle.write("\n")
        self._samples.append(sample)

    def compact(self, now_utc: datetime) -> None:
        cutoff = now_utc - _HISTORY_RETENTION
        self._samples = [sample for sample in self._samples if sample.observed_at_utc >= cutoff]
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as handle:
            for sample in self._samples:
                payload = {
                    "observed_at_utc": sample.observed_at_utc.isoformat(),
                    "power_w": round(sample.power_w, 3),
                }
                handle.write(json.dumps(payload, separators=(",", ":")))
                handle.write("\n")

    def _load(self) -> list[LoadSample]:
        if not self._path.exists():
            return []
        samples: list[LoadSample] = []
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            _LOGGER.warning("Could not read background-load history: %s", exc)
            return []
        for line in lines:
            try:
                payload = json.loads(line)
                observed = datetime.fromisoformat(payload["observed_at_utc"])
                if observed.tzinfo is None:
                    observed = observed.replace(tzinfo=UTC)
                samples.append(LoadSample(observed.astimezone(UTC), float(payload["power_w"])))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                _LOGGER.warning("Ignoring invalid background-load history record")
        samples.sort(key=lambda item: item.observed_at_utc)
        return samples


class BackgroundLoadForecastArchive:
    """Archive compact forecast revisions for later accuracy analysis."""

    def __init__(self, path: Path = _DEFAULT_ARCHIVE_PATH) -> None:
        self._path = path

    def record(self, forecast: BackgroundLoadForecast, now_local: datetime) -> None:
        daily = []
        for offset in range(1, 8):
            target = now_local.date() + timedelta(days=offset)
            item = forecast.daily_energy(target)
            if item is not None:
                daily.append(
                    {
                        "target_date": item.target_date.isoformat(),
                        "energy_kwh": round(item.energy_kwh, 4),
                    }
                )
        payload = {
            "issued_at_utc": forecast.generated_at_utc.isoformat(),
            "issued_at_local": now_local.isoformat(),
            "model_version": MODEL_VERSION,
            "history_sample_count": forecast.history_sample_count,
            "history_days": round(forecast.history_days, 3),
            "daily": daily,
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, separators=(",", ":")))
            handle.write("\n")


class BackgroundLoadService:
    """Collect background load and maintain a planner-ready rolling forecast."""

    def __init__(
        self,
        ha_client: HomeAssistantClient,
        *,
        history: BackgroundLoadHistory | None = None,
        archive: BackgroundLoadForecastArchive | None = None,
        model: BackgroundLoadModel | None = None,
    ) -> None:
        self._diagnostics = DiagnosticsPublisher(ha_client)
        self._history = history or BackgroundLoadHistory()
        self._archive = archive or BackgroundLoadForecastArchive()
        self._model = model or BackgroundLoadModel()
        self._forecast: BackgroundLoadForecast | None = None
        self._last_forecast_at_utc: datetime | None = None
        self._last_compact_at_utc: datetime | None = None

    @property
    def forecast(self) -> BackgroundLoadForecast | None:
        return self._forecast

    async def update_from_house_state(
        self,
        house_state: HouseState,
        *,
        now_utc: datetime | None = None,
    ) -> None:
        """Sample a valid background load and refresh the rolling forecast when due."""
        now = (now_utc or datetime.now(UTC)).astimezone(UTC)
        value = house_state.background_load_power_w
        if value is None:
            if self._forecast is None:
                await self._safe_publish_status("waiting_for_data")
            return

        try:
            if self._sample_due(now):
                self._history.record(LoadSample(now, max(0.0, value)))
            if self._compact_due(now):
                self._history.compact(now)
                self._last_compact_at_utc = now
            if self._forecast_due(now):
                await self._refresh_forecast(now)
        except (OSError, HomeAssistantError, ValueError) as exc:
            _LOGGER.warning("Background-load forecast update failed: %s", exc)
            await self._safe_publish_status("error", error=str(exc))
        except Exception as exc:  # noqa: BLE001 - predictor failure must not stop Energy Manager.
            _LOGGER.exception("Unexpected background-load forecast error")
            await self._safe_publish_status("error", error=f"{type(exc).__name__}: {exc}")

    def _sample_due(self, now_utc: datetime) -> bool:
        last = self._history.last_sample_at_utc
        return last is None or now_utc - last >= _SAMPLE_INTERVAL

    def _forecast_due(self, now_utc: datetime) -> bool:
        return self._last_forecast_at_utc is None or now_utc - self._last_forecast_at_utc >= _FORECAST_INTERVAL

    def _compact_due(self, now_utc: datetime) -> bool:
        return self._last_compact_at_utc is None or now_utc - self._last_compact_at_utc >= timedelta(days=1)

    async def _refresh_forecast(self, now_utc: datetime) -> None:
        now_local = now_utc.astimezone(_LOCAL_TZ)
        forecast = self._model.build(
            self._history.samples,
            now_local=now_local,
            generated_at_utc=now_utc,
        )
        self._forecast = forecast
        self._last_forecast_at_utc = now_utc
        try:
            self._archive.record(forecast, now_local)
        except OSError as exc:
            _LOGGER.warning("Could not archive background-load forecast revision: %s", exc)
        await self._diagnostics.publish_background_load_forecast(forecast, now_local=now_local)
        await self._diagnostics.publish_background_load_forecast_status(forecast.model_stage, forecast=forecast)
        _LOGGER.info(
            "Background-load forecast updated: next hour %.0f W, next 24 h %.2f kWh, history %.1f days",
            forecast.next_hour_average_power_w() or 0.0,
            forecast.next_24_hours_energy_kwh() or 0.0,
            forecast.history_days,
        )

    async def _safe_publish_status(self, status: str, *, error: str | None = None) -> None:
        try:
            await self._diagnostics.publish_background_load_forecast_status(status, error=error)
        except HomeAssistantError as exc:
            _LOGGER.warning("Could not publish background-load forecast status: %s", exc)
