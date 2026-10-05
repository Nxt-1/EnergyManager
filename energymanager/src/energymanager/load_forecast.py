"""Background household-load history and forecast model."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from statistics import median
from zoneinfo import ZoneInfo

LOCAL_TIMEZONE = ZoneInfo("Europe/Brussels")
MODEL_VERSION = "2026-10-04-baseline"
FORECAST_INTERVAL_MINUTES = 15
FORECAST_DAYS = 7
_HISTORY_DAYS = 35


@dataclass(frozen=True, slots=True)
class LoadSample:
    """One observed background-load sample."""

    observed_at_utc: datetime
    power_w: float


@dataclass(frozen=True, slots=True)
class BackgroundLoadForecastPoint:
    """Predicted mean background load for one 15-minute interval."""

    period_start_local: datetime
    power_w: float
    method: str


@dataclass(frozen=True, slots=True)
class BackgroundLoadDailyEnergy:
    """Predicted background energy for one complete local calendar day."""

    target_date: date
    energy_kwh: float


@dataclass(frozen=True, slots=True)
class BackgroundLoadForecast:
    """Rolling background-load forecast retained for the future planner."""

    generated_at_utc: datetime
    points: tuple[BackgroundLoadForecastPoint, ...]
    history_sample_count: int
    history_days: float
    model_stage: str

    def next_hour_average_power_w(self) -> float | None:
        """Return the mean power of the first four 15-minute forecast intervals."""
        points = self.points[:4]
        if not points:
            return None
        return sum(point.power_w for point in points) / len(points)

    def next_24_hours_energy_kwh(self) -> float | None:
        """Return forecast energy for the first 24 hours of future intervals."""
        points = self.points[:96]
        if not points:
            return None
        return sum(point.power_w for point in points) * FORECAST_INTERVAL_MINUTES / 60.0 / 1000.0

    def daily_energy(self, target_date: date) -> BackgroundLoadDailyEnergy | None:
        """Return forecast energy for one complete local calendar day when available."""
        points = [point for point in self.points if point.period_start_local.date() == target_date]
        if not points:
            return None
        timezone = points[0].period_start_local.tzinfo
        if timezone is None or len(points) != _expected_daily_points(target_date, timezone):
            return None
        energy = sum(point.power_w for point in points) * FORECAST_INTERVAL_MINUTES / 60.0 / 1000.0
        return BackgroundLoadDailyEnergy(target_date=target_date, energy_kwh=energy)


@dataclass(frozen=True, slots=True)
class _Bucket:
    target_date: date
    slot: int
    power_w: float


class BackgroundLoadModel:
    """Robust time-of-day baseline model that improves as local history accumulates."""

    def build(
        self,
        samples: tuple[LoadSample, ...],
        *,
        now_local: datetime,
        generated_at_utc: datetime | None = None,
    ) -> BackgroundLoadForecast:
        if now_local.tzinfo is None:
            raise ValueError("now_local must be timezone-aware")
        if not samples:
            raise ValueError("At least one background-load sample is required")

        cutoff_utc = (now_local.astimezone(UTC) - timedelta(days=_HISTORY_DAYS)).replace(microsecond=0)
        usable = tuple(sample for sample in samples if sample.observed_at_utc >= cutoff_utc)
        if not usable:
            usable = samples[-1:]

        buckets = _aggregate_buckets(usable)
        fallback = _recent_baseline(usable)
        start_local = _ceil_quarter_hour(now_local)
        end_date = now_local.date() + timedelta(days=FORECAST_DAYS + 1)
        end_local = datetime.combine(end_date, time.min, tzinfo=now_local.tzinfo)
        cursor_utc = start_local.astimezone(UTC)
        end_utc = end_local.astimezone(UTC)

        points: list[BackgroundLoadForecastPoint] = []
        while cursor_utc < end_utc:
            cursor_local = cursor_utc.astimezone(now_local.tzinfo)
            power, method = _predict_bucket(cursor_local, buckets, fallback)
            points.append(
                BackgroundLoadForecastPoint(
                    period_start_local=cursor_local,
                    power_w=max(0.0, power),
                    method=method,
                )
            )
            cursor_utc += timedelta(minutes=FORECAST_INTERVAL_MINUTES)

        first = min(sample.observed_at_utc for sample in usable)
        last = max(sample.observed_at_utc for sample in usable)
        history_days = max(0.0, (last - first).total_seconds() / 86400.0)
        stage = "connected" if history_days >= 7.0 else "learning"
        return BackgroundLoadForecast(
            generated_at_utc=generated_at_utc or datetime.now(UTC),
            points=tuple(points),
            history_sample_count=len(usable),
            history_days=history_days,
            model_stage=stage,
        )


def _aggregate_buckets(samples: tuple[LoadSample, ...]) -> tuple[_Bucket, ...]:
    grouped: dict[tuple[date, int], list[float]] = defaultdict(list)
    for sample in samples:
        local = sample.observed_at_utc.astimezone(LOCAL_TIMEZONE)
        slot = local.hour * 4 + local.minute // FORECAST_INTERVAL_MINUTES
        grouped[(local.date(), slot)].append(max(0.0, sample.power_w))
    return tuple(
        _Bucket(target_date=target_date, slot=slot, power_w=float(median(values)))
        for (target_date, slot), values in sorted(grouped.items())
    )


def _predict_bucket(
    target: datetime,
    buckets: tuple[_Bucket, ...],
    fallback: float,
) -> tuple[float, str]:
    slot = target.hour * 4 + target.minute // FORECAST_INTERVAL_MINUTES
    same_slot = [bucket for bucket in buckets if bucket.slot == slot and bucket.target_date < target.date()]

    same_weekday = [bucket.power_w for bucket in same_slot if bucket.target_date.weekday() == target.weekday()]
    if len(same_weekday) >= 2:
        return float(median(same_weekday)), "same_weekday"

    target_weekend = target.weekday() >= 5
    same_day_type = [
        bucket.power_w
        for bucket in same_slot
        if (bucket.target_date.weekday() >= 5) == target_weekend
    ]
    if len(same_day_type) >= 3:
        return float(median(same_day_type)), "weekday_weekend"

    any_day = [bucket.power_w for bucket in same_slot]
    if len(any_day) >= 3:
        return float(median(any_day)), "time_of_day"

    return fallback, "recent_baseline"


def _recent_baseline(samples: tuple[LoadSample, ...]) -> float:
    latest = max(sample.observed_at_utc for sample in samples)
    recent = [
        max(0.0, sample.power_w)
        for sample in samples
        if latest - sample.observed_at_utc <= timedelta(hours=3)
    ]
    values = recent if recent else [max(0.0, sample.power_w) for sample in samples]
    return float(median(values))


def _ceil_quarter_hour(value: datetime) -> datetime:
    base = value.replace(second=0, microsecond=0)
    remainder = base.minute % FORECAST_INTERVAL_MINUTES
    if remainder == 0 and value.second == 0 and value.microsecond == 0:
        return base
    minutes = FORECAST_INTERVAL_MINUTES - remainder if remainder else FORECAST_INTERVAL_MINUTES
    return base + timedelta(minutes=minutes)


def _expected_daily_points(target_date: date, timezone: tzinfo) -> int:
    start_local = datetime.combine(target_date, time.min, tzinfo=timezone)
    end_local = datetime.combine(target_date + timedelta(days=1), time.min, tzinfo=timezone)
    seconds = (end_local.astimezone(UTC) - start_local.astimezone(UTC)).total_seconds()
    return int(seconds // (FORECAST_INTERVAL_MINUTES * 60))
