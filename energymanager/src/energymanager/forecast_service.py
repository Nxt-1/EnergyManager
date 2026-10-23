"""Build installation forecasts without making measurement polling wait for weather HTTP."""

from __future__ import annotations

import asyncio
import math
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

import aiohttp

from .adapters import HomeAssistantAdapter
from .domain import Observation, json_data
from .load_forecast import BackgroundLoadModel, LoadSample, MODEL_VERSION
from .open_meteo import FORECAST_MODEL, FORECAST_URL, LOCAL_TIMEZONE, OpenMeteoClient
from .pv_forecast import CALIBRATION_VERSION, PV_PLANES, PvForecast, build_pv_forecast
from .store import Store


class InstallationForecast:
    """Original four-plane PV and measured household baseline, sharing the V4 evidence store."""

    def __init__(self, ha: HomeAssistantAdapter, store: Store, *, allow_remote: bool = False,
                 weather_url: str = FORECAST_URL, max_age_seconds: float = 7200,
                 measurement_max_age_seconds: float = 30) -> None:
        self.ha, self.store = ha, store
        self.weather = OpenMeteoClient(url=weather_url, allow_remote=allow_remote)
        self.synthetic = urlsplit(weather_url).hostname in ("localhost", "127.0.0.1", "::1")
        self.max_age_seconds = max_age_seconds
        self.measurement_max_age_seconds = measurement_max_age_seconds
        self.weather_task: asyncio.Task[None] | None = None
        self.pv: PvForecast | None = None
        self.data: dict[str, Any] | None = None
        self.last_attempt: datetime | None = None
        self.last_sample = self.store.load_samples(datetime.now(UTC) - timedelta(days=35))[-1:]
        self.status: dict[str, Any] = {
            "source": "Open-Meteo", "model": FORECAST_MODEL, "location": "Home Assistant zone.home",
            "calibration": CALIBRATION_VERSION, "load_model": MODEL_VERSION,
            "weather_error": None, "load_stage": "awaiting measurements", "synthetic": self.synthetic,
        }

    async def close(self) -> None:
        if self.weather_task:
            self.weather_task.cancel()
            await asyncio.gather(self.weather_task, return_exceptions=True)
        await self.weather.close()

    async def refresh_weather(self, at: datetime) -> None:
        try:
            zone = await self.ha.entity_state("zone.home")
            attributes = zone["attributes"]
            series = await self.weather.fetch_planes(float(attributes["latitude"]),
                                                     float(attributes["longitude"]), PV_PLANES)
            pv = await asyncio.to_thread(build_pv_forecast, series, generated_at_utc=at)
            # Do not adopt a partial new forecast in place of a still-valid previous one.
            self.check_coverage(pv, at)
            self.pv = pv
            self.data = None
            self.status.update(weather_at=at.isoformat(), weather_error=None)
            self.store.put("pv_forecast_evidence", {
                "source": "Open-Meteo", "model": FORECAST_MODEL,
                "location_source": "zone.home", "synthetic": self.synthetic,
                "calibration_version": CALIBRATION_VERSION,
                "planes": [asdict(plane) for plane in PV_PLANES], "forecast": json_data(pv),
            })
        except (ValueError, KeyError, TypeError, RuntimeError, OSError, aiohttp.ClientError, TimeoutError) as exc:
            self.status["weather_error"] = f"{type(exc).__name__}: {exc}"
            self.store.event("weather_error", {"reason": self.status["weather_error"]})

    @staticmethod
    def check_coverage(pv: PvForecast, at: datetime) -> None:
        ends = [point.period_end_local.astimezone(UTC) for point in pv.points]
        if (not ends or ends[0] - timedelta(hours=1) > at or ends[-1] < at + timedelta(hours=169)
                or any((right - left).total_seconds() != 3600 for left, right in zip(ends, ends[1:]))):
            raise ValueError("Open-Meteo must cover seven rolling days plus the refresh buffer; no extrapolation")

    async def read(self, observation: Observation, at: datetime) -> dict[str, Any]:
        at = at.astimezone(UTC)
        if (observation.quality != "measured" or not math.isfinite(observation.house_kw)
                or observation.house_kw < 0
                or not -5 <= (at - observation.at).total_seconds() <= self.measurement_max_age_seconds):
            raise ValueError("Household forecast requires validated inputs from a recent HA read")
        if not self.last_sample or (observation.at - self.last_sample[0].observed_at_utc).total_seconds() >= 300:
            sample = LoadSample(observation.at.astimezone(UTC), observation.house_kw * 1000)
            self.store.record_load(sample)
            self.last_sample = (sample,)
        due = self.pv is None or (at - self.pv.generated_at_utc).total_seconds() >= 1800
        retry = self.last_attempt is None or (at - self.last_attempt).total_seconds() >= 60
        if due and retry and (self.weather_task is None or self.weather_task.done()):
            self.last_attempt = at
            self.weather_task = asyncio.create_task(self.refresh_weather(at))
        if self.pv is None:
            raise ValueError(self.status["weather_error"] or "Weather retrieval in progress")
        if not 0 <= (at - self.pv.generated_at_utc).total_seconds() <= self.max_age_seconds:
            raise ValueError("Cached weather is stale; awaiting a successful refresh")
        if self.data is None or (at - datetime.fromisoformat(self.data["load_generated_at"])).total_seconds() >= 1800:
            samples = self.store.load_samples(at - timedelta(days=35))
            while True:
                pv = self.pv
                data = await asyncio.to_thread(self.build_data, pv, samples, at)
                if self.pv is pv:
                    self.data = data
                    break  # A weather refresh may have completed while the load model was building.
            self.status.update(self.data["forecast_status"])
            self.store.put("forecast", self.data)
        return self.data

    def build_data(self, pv: PvForecast, samples: tuple[LoadSample, ...], at: datetime) -> dict[str, Any]:
        start = datetime.fromtimestamp(int(at.timestamp()) // 900 * 900, UTC)
        # Include the current partial quarter; the legacy predictor otherwise starts at the next one.
        # Only the slot selection changes. Its historical medians and recent baseline stay intact.
        load = BackgroundLoadModel().build(samples, now_local=at.astimezone(LOCAL_TIMEZONE),
                                            generated_at_utc=at, include_current_quarter=True)
        solar = {point.period_end_local.astimezone(UTC): point for point in pv.points}
        intervals = []
        for point in load.points:
            left = point.period_start_local.astimezone(UTC)
            if left >= start + timedelta(hours=169):
                break
            hour_end = datetime.fromtimestamp((int(left.timestamp()) // 3600 + 1) * 3600, UTC)
            if hour_end not in solar:
                raise ValueError("Missing PV hour; forecast cannot be completed with zeros")
            power = solar[hour_end]
            intervals.append({"start": left.isoformat(), "end": (left + timedelta(minutes=15)).isoformat(),
                              "house_kw": point.power_w / 1000,
                              "pv_ac_kw": (power.front_power_w + power.rear_power_w) / 1000,
                              "pv_dc_kw": power.shed_power_w / 1000})
        methods = sorted({point.method for point in load.points})
        prefix = "SYNTHETIC local weather fixture · " if self.synthetic else ""
        provenance = (f"{prefix}Open-Meteo KNMI · four installed PV planes · correction {CALIBRATION_VERSION} · "
                      f"household baseline {load.model_stage.replace('connected', 'learned')} "
                      f"(samples: {load.history_sample_count})")
        return {"issued_at": pv.generated_at_utc.isoformat(), "revision": uuid4().hex,
                "provenance": provenance, "load_generated_at": at.isoformat(), "intervals": intervals,
                "forecast_status": {"load_stage": load.model_stage, "load_methods": methods,
                                    "load_samples": load.history_sample_count, "history_days": load.history_days}}
