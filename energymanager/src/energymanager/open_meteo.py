"""Open-Meteo client used by the PV predictor."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp

from .pv_forecast import PlaneWeatherHour, PlaneWeatherSeries, PvPlane

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FORECAST_MODEL = "knmi_seamless"
FORECAST_DAYS = 8
FORECAST_TIMEZONE = "Europe/Brussels"
_LOCAL_TZ = ZoneInfo(FORECAST_TIMEZONE)


class OpenMeteoError(RuntimeError):
    """Raised when Open-Meteo forecast data are unavailable or malformed."""


class OpenMeteoClient:
    """Small async client for per-plane tilted irradiance forecasts."""

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> OpenMeteoClient:
        timeout = aiohttp.ClientTimeout(total=30)
        self._session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def fetch_planes(
        self,
        latitude: float,
        longitude: float,
        planes: tuple[PvPlane, ...],
    ) -> dict[str, PlaneWeatherSeries]:
        """Fetch all PV planes concurrently."""
        results = await asyncio.gather(
            *(self.fetch_plane(latitude, longitude, plane) for plane in planes)
        )
        return {series.plane_key: series for series in results}

    async def fetch_plane(
        self,
        latitude: float,
        longitude: float,
        plane: PvPlane,
    ) -> PlaneWeatherSeries:
        """Fetch today plus seven full future calendar days for one PV plane."""
        session = self._require_session()
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": (
                "global_tilted_irradiance,temperature_2m,cloud_cover,"
                "direct_radiation,diffuse_radiation"
            ),
            "tilt": plane.tilt_deg,
            "azimuth": plane.azimuth_deg,
            "models": FORECAST_MODEL,
            "forecast_days": FORECAST_DAYS,
            "timezone": FORECAST_TIMEZONE,
        }
        async with session.get(FORECAST_URL, params=params) as response:
            if response.status != 200:
                body = await response.text()
                raise OpenMeteoError(
                    f"Open-Meteo returned HTTP {response.status} for {plane.key}: {body}"
                )
            payload = await response.json()
        return _parse_plane_response(plane.key, payload)

    def _require_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            raise RuntimeError("OpenMeteoClient must be used as an async context manager")
        return self._session


def _parse_plane_response(plane_key: str, payload: dict[str, Any]) -> PlaneWeatherSeries:
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict):
        raise OpenMeteoError(f"Open-Meteo response for {plane_key} has no hourly data")

    times = _list(hourly, "time", plane_key)
    gti = _list(hourly, "global_tilted_irradiance", plane_key)
    temperatures = _list(hourly, "temperature_2m", plane_key)
    clouds = _optional_list(hourly, "cloud_cover")
    direct = _optional_list(hourly, "direct_radiation")
    diffuse = _optional_list(hourly, "diffuse_radiation")

    length = len(times)
    if len(gti) != length or len(temperatures) != length:
        raise OpenMeteoError(f"Open-Meteo arrays for {plane_key} are not aligned")

    hours: list[PlaneWeatherHour] = []
    for index, timestamp in enumerate(times):
        try:
            local_time = datetime.fromisoformat(str(timestamp)).replace(tzinfo=_LOCAL_TZ)
            irradiance = float(gti[index])
            temperature = float(temperatures[index])
        except (TypeError, ValueError) as exc:
            raise OpenMeteoError(
                f"Invalid Open-Meteo value for {plane_key} at index {index}"
            ) from exc

        hours.append(
            PlaneWeatherHour(
                period_end_local=local_time,
                global_tilted_irradiance_wm2=irradiance,
                temperature_c=temperature,
                cloud_cover_pct=_optional_float(clouds, index),
                direct_radiation_wm2=_optional_float(direct, index),
                diffuse_radiation_wm2=_optional_float(diffuse, index),
            )
        )
    return PlaneWeatherSeries(plane_key=plane_key, hours=tuple(hours))


def _list(hourly: dict[str, Any], key: str, plane_key: str) -> list[Any]:
    value = hourly.get(key)
    if not isinstance(value, list):
        raise OpenMeteoError(f"Open-Meteo response for {plane_key} has no {key} array")
    return value


def _optional_list(hourly: dict[str, Any], key: str) -> list[Any] | None:
    value = hourly.get(key)
    return value if isinstance(value, list) else None


def _optional_float(values: list[Any] | None, index: int) -> float | None:
    if values is None or index >= len(values) or values[index] is None:
        return None
    try:
        return float(values[index])
    except (TypeError, ValueError):
        return None
