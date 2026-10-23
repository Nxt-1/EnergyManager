"""The installation's original Open-Meteo KNMI source, with unambiguous UTC hours."""

from __future__ import annotations

import asyncio
import math
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp

from .adapters import checked_url
from .pv_forecast import PlaneWeatherHour, PlaneWeatherSeries, PvPlane

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FORECAST_MODEL = "knmi_seamless"
FORECAST_TIMEZONE = "Europe/Brussels"
# An extra calendar day covers 168 rolling hours even when started late in the evening.
FORECAST_DAYS = 9
LOCAL_TIMEZONE = ZoneInfo(FORECAST_TIMEZONE)


class OpenMeteoError(RuntimeError):
    """Weather is unavailable or cannot safely cover the planning horizon."""


class OpenMeteoClient:
    def __init__(self, *, url: str = FORECAST_URL, allow_remote: bool = False) -> None:
        self.url = checked_url(url, allow_remote=True)
        self.allow_remote = allow_remote
        self.session: aiohttp.ClientSession | None = None

    async def close(self) -> None:
        if self.session:
            await self.session.close()
            self.session = None

    async def fetch_planes(
        self, latitude: float, longitude: float, planes: tuple[PvPlane, ...]
    ) -> dict[str, PlaneWeatherSeries]:
        checked_url(self.url, self.allow_remote)
        if not (math.isfinite(latitude) and math.isfinite(longitude)
                and -90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise OpenMeteoError("zone.home must supply valid latitude and longitude")
        if self.session is None:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        results = await asyncio.gather(*(self.fetch_plane(latitude, longitude, plane) for plane in planes))
        timestamps = [tuple(h.period_end_local.astimezone(UTC) for h in series.hours) for series in results]
        if not timestamps or any(times != timestamps[0] for times in timestamps):
            raise OpenMeteoError("PV plane weather hours are not aligned")
        return {series.plane_key: series for series in results}

    async def fetch_plane(self, latitude: float, longitude: float, plane: PvPlane) -> PlaneWeatherSeries:
        assert self.session is not None
        params: dict[str, str | int | float] = {
            "latitude": latitude, "longitude": longitude,
            "hourly": "global_tilted_irradiance,temperature_2m,cloud_cover,direct_radiation,diffuse_radiation",
            "tilt": plane.tilt_deg, "azimuth": plane.azimuth_deg,
            "models": FORECAST_MODEL, "forecast_days": FORECAST_DAYS,
            "timezone": FORECAST_TIMEZONE, "timeformat": "unixtime",
        }
        async with self.session.get(self.url, params=params, allow_redirects=False) as response:
            response.raise_for_status()
            payload = await response.json()
        return parse_plane_response(plane.key, payload)


def parse_plane_response(plane_key: str, payload: dict[str, Any]) -> PlaneWeatherSeries:
    if not isinstance(payload, dict):
        raise OpenMeteoError(f"Invalid weather response for {plane_key}")
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict):
        raise OpenMeteoError(f"No hourly weather for {plane_key}")
    keys = ("time", "global_tilted_irradiance", "temperature_2m")
    if any(not isinstance(hourly.get(key), list) for key in keys):
        raise OpenMeteoError(f"Missing required weather array for {plane_key}")
    length = len(hourly["time"])
    if not length or any(len(hourly[key]) != length for key in keys):
        raise OpenMeteoError(f"Unaligned weather arrays for {plane_key}")
    hours = []
    previous: float | None = None
    for index in range(length):
        try:
            timestamp = float(hourly["time"][index])
            irradiance = float(hourly["global_tilted_irradiance"][index])
            temperature = float(hourly["temperature_2m"][index])
            if not all(math.isfinite(value) for value in (timestamp, irradiance, temperature)):
                raise ValueError("Nonfinite weather")
            if previous is not None and timestamp - previous != 3600:
                raise ValueError("Weather hours must be consecutive and unique")
            period_end = datetime.fromtimestamp(timestamp, UTC).astimezone(LOCAL_TIMEZONE)
        except (ValueError, TypeError, OverflowError, OSError) as exc:
            raise OpenMeteoError(f"Invalid weather for {plane_key} at row {index}") from exc
        previous = timestamp

        def optional(key: str) -> float | None:
            values = hourly.get(key)
            if not isinstance(values, list) or index >= len(values) or values[index] is None:
                return None
            value = float(values[index])
            return value if math.isfinite(value) else None

        hours.append(PlaneWeatherHour(period_end, irradiance, temperature, optional("cloud_cover"),
                                      optional("direct_radiation"), optional("diffuse_radiation")))
    return PlaneWeatherSeries(plane_key, tuple(hours))
