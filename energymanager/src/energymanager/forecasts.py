"""Deterministic demo inputs and conservative, configured forecast preparation."""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from statistics import median
from uuid import uuid4
from zoneinfo import ZoneInfo

from .domain import Capabilities, Goal, Interval, Observation, Policy, Snapshot, daily_goals, time_grid


def background_sample(total_house_kw: float, ev_kw: float, controlled_other_kw: float = 0) -> float:
    if not all(math.isfinite(v) and v >= 0 for v in (total_house_kw, ev_kw, controlled_other_kw)):
        raise ValueError("Missing or invalid controlled-load telemetry")
    if total_house_kw + 0.05 < ev_kw + controlled_other_kw:
        raise ValueError("Load channels are inconsistent; background cannot be inferred")
    return max(0.0, total_house_kw - ev_kw - controlled_other_kw)


class MedianLoadForecast:
    """Use local time/day-type medians, then a visibly labelled recent baseline."""

    def __init__(self, samples: tuple[tuple[datetime, float], ...], timezone: str) -> None:
        if not samples or any(not math.isfinite(power) or power < 0 for _, power in samples):
            raise ValueError("Valid background observations are required")
        self.samples = samples
        self.zone = ZoneInfo(timezone)

    def predict(self, target: datetime) -> tuple[float, str]:
        local = target.astimezone(self.zone)
        past = [(at.astimezone(self.zone), value) for at, value in self.samples if at < target]
        bucket = [
            (at, value)
            for at, value in past
            if at.hour == local.hour and at.minute // 15 == local.minute // 15
        ]
        same = [value for at, value in bucket if at.weekday() == local.weekday()]
        day_type = [value for at, value in bucket if (at.weekday() >= 5) == (local.weekday() >= 5)]
        for values, label, minimum in (
            (same, "weekday", 2),
            (day_type, "day_type", 3),
            ([v for _, v in bucket], "time_of_day", 3),
        ):
            if len(values) >= minimum:
                return float(median(values)), label
        recent = [value for at, value in past if at >= target - timedelta(days=35)]
        if not recent:
            raise ValueError("No usable past background observations")
        return float(median(recent[-96:])), "recent baseline; limited history"


def pv_plane_kw(
    irradiance_wm2: float, ambient_c: float, peak_kw: float, temperature_coefficient: float = -0.0034
) -> float:
    """Adapt the inspected PV plane mechanics without installation-specific calibration."""
    if not all(math.isfinite(v) for v in (irradiance_wm2, ambient_c, peak_kw, temperature_coefficient)):
        raise ValueError("Invalid weather input")
    cell_c = ambient_c + 0.0275 * max(0, irradiance_wm2)
    return max(0, peak_kw * max(0, irradiance_wm2) / 1000 * (1 + temperature_coefficient * (cell_c - 25)))


def apply_requirements(
    intervals: tuple[Interval, ...],
    goals: tuple[Goal, ...],
    observation: Observation,
    c: Capabilities,
    p: Policy,
) -> tuple[Interval, ...]:
    result: list[Interval] = []
    trips = sorted((g for g in goals if g.kind == "trip"), key=lambda g: g.deadline)
    for interval in intervals:
        if not observation.ev_state_known:
            result.append(replace(interval, available=False, withdrawal_kwh=0, ev_state_known=False))
            continue
        available = observation.connected
        unknown = False
        withdrawal = 0.0
        for trip in trips:
            if trip.deadline < observation.at and observation.connected:
                continue  # Actual reconnection supersedes an old unknown return.
            if interval.start >= trip.deadline:
                external = (
                    trip.withdrawal(p) + p.arrival_reserve_km * p.consumption_kwh_per_100km / 100
                    > c.ev_capacity_kwh
                )
                if trip.return_at is None or interval.start < trip.return_at or external:
                    available = False
                    unknown |= external
                elif not unknown:
                    available = True
            if interval.start == trip.deadline and not unknown:
                withdrawal += trip.withdrawal(p)
        result.append(
            replace(
                interval,
                available=available and not unknown,
                withdrawal_kwh=withdrawal,
                ev_state_known=not unknown,
            )
        )
    return tuple(result)


def demo_snapshot(
    *,
    start: datetime | None = None,
    hours: float = 168,
    goals: tuple[Goal, ...] | None = None,
    revision: int = 1,
    season: str = "mixed",
    policy: Policy | None = None,
) -> Snapshot:
    start = start or datetime(2026, 10, 23, 8, tzinfo=UTC)
    c, p = Capabilities(), policy or Policy()
    explicit = (
        goals
        if goals is not None
        else (
            Goal(
                "trip-weekend",
                "Weekend journey · 120 km return included",
                start + timedelta(hours=25),
                kind="trip",
                distance_km=120,
                return_at=start + timedelta(hours=34),
                priority=70,
            ),
        )
    )
    end = start + timedelta(hours=hours)
    external_start = min(
        (
            g.deadline
            for g in explicit
            if g.kind == "trip"
            and g.withdrawal(p) + p.arrival_reserve_km * p.consumption_kwh_per_100km / 100 > c.ev_capacity_kwh
        ),
        default=end + timedelta(seconds=1),
    )
    generated = daily_goals(start, min(end, external_start), p, explicit)
    all_goals = explicit + generated
    boundaries = tuple(t for g in all_goals for t in (g.deadline, g.return_at, g.earliest) if t)
    grid = time_grid(start, hours, boundaries)
    intervals: list[Interval] = []
    for left, right in zip(grid, grid[1:]):
        local = left.astimezone(ZoneInfo(p.timezone))
        daytime = local.hour + local.minute / 60
        solar = max(0.0, math.sin((daytime - 8) / 10 * math.pi)) if 8 <= daytime <= 18 else 0.0
        day = (left - start).days
        strength = 0.15 if season == "winter" else (0.75, 0.35, 0.95, 0.4, 0.85, 0.65, 0.25)[day % 7]
        house = 0.42 + (0.95 if 17 <= daytime < 21 else 0) + (0.55 if 6 <= daytime < 8 else 0)
        intervals.append(Interval(left, right, house, solar * strength * 4.0, solar * strength * 4.8))
    first = intervals[0]
    observation = Observation(
        start, 25.2, 7.0, True, first.house_kw, first.pv_ac_kw, first.pv_dc_kw, quality="SYNTHETIC"
    )
    prepared = apply_requirements(tuple(intervals), all_goals, observation, c, p)
    return Snapshot(
        uuid4().hex, revision, observation, start, f"synthetic-{season}-v1", prepared, all_goals, c, p
    )
