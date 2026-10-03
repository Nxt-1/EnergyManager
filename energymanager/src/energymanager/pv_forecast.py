"""Four-plane PV forecast model and empirical group-level calibration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Mapping
from zoneinfo import ZoneInfo

LOCAL_TIMEZONE = ZoneInfo("Europe/Brussels")
CALIBRATION_VERSION = "2026-10-03-seed"


@dataclass(frozen=True, slots=True)
class PvPlane:
    """Physical PV plane used by the predictor."""

    key: str
    group: str
    peak_power_w: float
    tilt_deg: float
    azimuth_deg: float
    temperature_coefficient_per_c: float
    cell_temperature_rise_c_per_wm2: float = 0.0275


PV_PLANES: tuple[PvPlane, ...] = (
    PvPlane("front_roof", "front", 3280.0, 38.0, 50.0, -0.0034),
    PvPlane("rear_roof", "rear", 1640.0, 46.0, -130.0, -0.0034),
    PvPlane("rear_flat", "rear", 820.0, 13.0, -130.0, -0.0034),
    PvPlane("shed", "shed", 6180.0, 9.5, -40.0, -0.0029),
)


@dataclass(frozen=True, slots=True)
class PlaneWeatherHour:
    """One Open-Meteo hourly record for one PV plane."""

    period_end_local: datetime
    global_tilted_irradiance_wm2: float
    temperature_c: float
    cloud_cover_pct: float | None = None
    direct_radiation_wm2: float | None = None
    diffuse_radiation_wm2: float | None = None


@dataclass(frozen=True, slots=True)
class PlaneWeatherSeries:
    """Aligned weather/irradiance series for one PV plane."""

    plane_key: str
    hours: tuple[PlaneWeatherHour, ...]


@dataclass(frozen=True, slots=True)
class PvForecastPoint:
    """Predicted mean PV power for one preceding-hour interval."""

    period_end_local: datetime
    front_power_w: float
    rear_power_w: float
    shed_power_w: float
    total_power_w: float
    front_raw_power_w: float
    rear_raw_power_w: float
    shed_raw_power_w: float
    cloud_cover_pct: float | None
    direct_radiation_wm2: float | None
    diffuse_radiation_wm2: float | None

    @property
    def energy_date(self) -> date:
        """Return the local calendar day containing the represented hour."""
        return (self.period_end_local - timedelta(microseconds=1)).date()


@dataclass(frozen=True, slots=True)
class PvDailyEnergy:
    """Daily forecast energy split by measurable PV group."""

    target_date: date
    front_kwh: float
    rear_kwh: float
    shed_kwh: float
    total_kwh: float


@dataclass(frozen=True, slots=True)
class PvForecast:
    """Complete forecast horizon used later by the planner."""

    generated_at_utc: datetime
    points: tuple[PvForecastPoint, ...]

    def daily_energy(self, target_date: date) -> PvDailyEnergy | None:
        """Return daily energy from all points whose represented hour belongs to target_date."""
        points = [point for point in self.points if point.energy_date == target_date]
        if not points:
            return None

        front = sum(point.front_power_w for point in points) / 1000.0
        rear = sum(point.rear_power_w for point in points) / 1000.0
        shed = sum(point.shed_power_w for point in points) / 1000.0
        return PvDailyEnergy(target_date, front, rear, shed, front + rear + shed)

    def next_hour(self, now_local: datetime) -> PvForecastPoint | None:
        """Return the first forecast interval ending after the supplied local time."""
        if now_local.tzinfo is None:
            raise ValueError("now_local must be timezone-aware")
        for point in self.points:
            if point.period_end_local > now_local:
                return point
        return None


@dataclass(frozen=True, slots=True)
class PvSnapshot:
    """Persisted evening day-ahead forecast."""

    target_date: date
    captured_at_utc: datetime
    front_kwh: float
    rear_kwh: float
    shed_kwh: float
    total_kwh: float

    @classmethod
    def from_daily_energy(cls, daily: PvDailyEnergy, *, captured_at_utc: datetime) -> PvSnapshot:
        return cls(
            target_date=daily.target_date,
            captured_at_utc=captured_at_utc,
            front_kwh=daily.front_kwh,
            rear_kwh=daily.rear_kwh,
            shed_kwh=daily.shed_kwh,
            total_kwh=daily.total_kwh,
        )


def build_pv_forecast(
    series_by_plane: Mapping[str, PlaneWeatherSeries],
    *,
    generated_at_utc: datetime | None = None,
) -> PvForecast:
    """Build a calibrated four-plane forecast from aligned Open-Meteo series."""
    plane_map = {plane.key: plane for plane in PV_PLANES}
    missing = set(plane_map) - set(series_by_plane)
    if missing:
        raise ValueError(f"Missing PV plane forecast data: {', '.join(sorted(missing))}")

    hour_maps: dict[str, dict[datetime, PlaneWeatherHour]] = {
        key: {hour.period_end_local: hour for hour in series_by_plane[key].hours}
        for key in plane_map
    }
    common_times = sorted(set.intersection(*(set(values) for values in hour_maps.values())))
    if not common_times:
        raise ValueError("PV plane forecasts have no aligned hourly timestamps")

    front_weather = hour_maps["front_roof"]
    previous_temperature: float | None = None
    points: list[PvForecastPoint] = []

    for period_end in common_times:
        weather = {key: hour_maps[key][period_end] for key in plane_map}
        current_temperature = front_weather[period_end].temperature_c
        ambient_temperature = (
            current_temperature
            if previous_temperature is None
            else (previous_temperature + current_temperature) / 2.0
        )
        previous_temperature = current_temperature

        raw_by_plane = {
            key: _plane_power_w(plane_map[key], weather[key], ambient_temperature)
            for key in plane_map
        }
        front_raw = raw_by_plane["front_roof"]
        rear_raw = raw_by_plane["rear_roof"] + raw_by_plane["rear_flat"]
        shed_raw = raw_by_plane["shed"]

        front_gti = weather["front_roof"].global_tilted_irradiance_wm2
        rear_gti = _weighted_rear_irradiance(weather)
        front_factor = calibrated_group_factor("front", period_end, front_gti)
        rear_factor = calibrated_group_factor("rear", period_end, rear_gti)

        front = max(0.0, front_raw * front_factor)
        rear = max(0.0, rear_raw * rear_factor)
        shed = max(0.0, shed_raw)
        source = front_weather[period_end]
        points.append(
            PvForecastPoint(
                period_end_local=period_end,
                front_power_w=front,
                rear_power_w=rear,
                shed_power_w=shed,
                total_power_w=front + rear + shed,
                front_raw_power_w=front_raw,
                rear_raw_power_w=rear_raw,
                shed_raw_power_w=shed_raw,
                cloud_cover_pct=source.cloud_cover_pct,
                direct_radiation_wm2=source.direct_radiation_wm2,
                diffuse_radiation_wm2=source.diffuse_radiation_wm2,
            )
        )

    generated = generated_at_utc or datetime.now(UTC)
    return PvForecast(generated_at_utc=generated, points=tuple(points))


def calibrated_group_factor(group: str, period_end_local: datetime, irradiance_wm2: float) -> float:
    """Return seeded empirical correction for a measurable PV group.

    The seed calibration is intentionally conservative. It was derived from the user's
    2026-08-20 through 2026-10-03 front/rear string history. The rear group is allowed
    to vary with season within that observed window; outside the window it is clamped
    rather than extrapolated into an unobserved season.
    """
    hour_bucket = _hour_bucket(period_end_local.hour)
    if hour_bucket is None or group == "shed":
        return 1.0

    if group == "front":
        base = _FRONT_FACTORS[hour_bucket]
    elif group == "rear":
        base = _interpolated_rear_factor(period_end_local.timetuple().tm_yday, hour_bucket)
    else:
        raise ValueError(f"Unknown PV calibration group: {group}")

    # Under weak/diffuse conditions the historical shade penalty largely disappeared.
    # Blend smoothly back toward an uncorrected physical model below ~350 W/m².
    strength = _clamp((irradiance_wm2 - 75.0) / 275.0, 0.0, 1.0)
    return 1.0 - strength * (1.0 - _clamp(base, 0.0, 1.0))


def _plane_power_w(plane: PvPlane, weather: PlaneWeatherHour, ambient_temperature_c: float) -> float:
    irradiance = max(0.0, weather.global_tilted_irradiance_wm2)
    cell_temperature = ambient_temperature_c + plane.cell_temperature_rise_c_per_wm2 * irradiance
    temperature_factor = 1.0 + plane.temperature_coefficient_per_c * (cell_temperature - 25.0)
    return plane.peak_power_w * irradiance / 1000.0 * max(0.0, temperature_factor)


def _weighted_rear_irradiance(weather: Mapping[str, PlaneWeatherHour]) -> float:
    roof = weather["rear_roof"].global_tilted_irradiance_wm2
    flat = weather["rear_flat"].global_tilted_irradiance_wm2
    return (1640.0 * roof + 820.0 * flat) / 2460.0


def _hour_bucket(hour: int) -> str | None:
    if 8 <= hour <= 10:
        return "morning"
    if 11 <= hour <= 12:
        return "late_morning"
    if 13 <= hour <= 14:
        return "early_afternoon"
    if 15 <= hour <= 18:
        return "late_afternoon"
    if 19 <= hour <= 20:
        return "dusk"
    return None


_FRONT_FACTORS = {
    "morning": 0.68,
    "late_morning": 0.81,
    "early_afternoon": 0.98,
    "late_afternoon": 1.00,
    "dusk": 0.57,
}

_REAR_FACTOR_ANCHORS: tuple[tuple[int, dict[str, float]], ...] = (
    (
        239,
        {
            "morning": 0.93,
            "late_morning": 0.93,
            "early_afternoon": 0.76,
            "late_afternoon": 0.57,
            "dusk": 0.54,
        },
    ),
    (
        254,
        {
            "morning": 0.91,
            "late_morning": 0.88,
            "early_afternoon": 0.71,
            "late_afternoon": 0.61,
            "dusk": 0.45,
        },
    ),
    (
        269,
        {
            "morning": 0.82,
            "late_morning": 0.91,
            "early_afternoon": 0.63,
            "late_afternoon": 0.50,
            "dusk": 0.52,
        },
    ),
)


def _interpolated_rear_factor(day_of_year: int, bucket: str) -> float:
    first_day, first_profile = _REAR_FACTOR_ANCHORS[0]
    last_day, last_profile = _REAR_FACTOR_ANCHORS[-1]
    if day_of_year <= first_day:
        return first_profile[bucket]
    if day_of_year >= last_day:
        return last_profile[bucket]

    for (left_day, left), (right_day, right) in zip(
        _REAR_FACTOR_ANCHORS,
        _REAR_FACTOR_ANCHORS[1:],
        strict=True,
    ):
        if left_day <= day_of_year <= right_day:
            weight = (day_of_year - left_day) / (right_day - left_day)
            return left[bucket] + weight * (right[bucket] - left[bucket])
    return last_profile[bucket]


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
