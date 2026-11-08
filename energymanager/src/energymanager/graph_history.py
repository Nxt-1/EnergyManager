"""Bounded graph projections of archived measurements; never controller inputs."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .domain import instant
from .energy import measurements, power_components


SERIES = ("grid", "ess", "solar", "house", "ev", "ess_soc", "ev_soc", "monthly_peak")


def graph_values(sample: dict[str, Any], ev_capacity: float, ess_capacity: float,
                 demo: bool) -> dict[str, float | None]:
    values: dict[str, float | None] = dict.fromkeys(SERIES)
    peak = sample.get("monthly_peak_kw")
    peak_valid = sample.get("monthly_peak_valid", sample.get("quality") == "measured")
    if (not demo and peak_valid and isinstance(peak, (int, float)) and not isinstance(peak, bool)
            and math.isfinite(peak) and peak >= 0):
        values["monthly_peak"] = peak * 1000
    if sample.get("quality") != ("SYNTHETIC" if demo else "measured"):
        return values
    powers = power_components(sample)
    if powers is not None:
        grid_kw = powers["house"] + powers["ev"] - float(sample["pv_ac_kw"]) - float(sample["ess_power_kw"])
        values.update(grid=grid_kw * 1000,
                      ess=float(sample["ess_power_kw"]) * 1000, solar=powers["solar"] * 1000,
                      house=powers["house"] * 1000, ev=powers["ev"] * 1000)
    for name, fallback in (("ev", ev_capacity), ("ess", ess_capacity)):
        energy = sample.get(f"{name}_kwh")
        capacity = sample.get(f"{name}_capacity_kwh", fallback)
        if (isinstance(energy, (int, float)) and isinstance(capacity, (int, float))
                and math.isfinite(energy) and math.isfinite(capacity) and 0 <= energy <= capacity
                and capacity > 0 and (name != "ev" or sample.get("ev_state_known") is not False)):
            values[f"{name}_soc"] = energy / capacity * 100
    return values


class SeriesBucket:
    """Keep temporal endpoints/extrema, or a break if this bucket contains missing data."""

    def __init__(self) -> None:
        self.first: tuple[float, float] | None = None
        self.last: tuple[float, float] | None = None
        self.low: tuple[float, float] | None = None
        self.high: tuple[float, float] | None = None
        self.gap_at: float | None = None

    def add(self, at: float, value: float | None) -> None:
        if value is None:
            self.gap_at = at
            return
        point = (at, value)
        self.first = self.first or point
        self.last = point
        if self.low is None or value < self.low[1]:
            self.low = point
        if self.high is None or value > self.high[1]:
            self.high = point

    def points(self) -> list[tuple[float, float | None]]:
        if self.gap_at is not None:
            # Suppress a mixed bucket rather than join readings across a hidden outage.
            return [(self.gap_at, None)]
        return sorted({point for point in (self.first, self.low, self.high, self.last) if point is not None})


class StepBucket:
    """Keep exact change timestamps; blank an overloaded bucket rather than move steps."""

    def __init__(self) -> None:
        self.changes: list[tuple[float, float | None]] = []
        self.last: tuple[float, float | None] | None = None
        self.overflow = False

    def add(self, at: float, value: float | None) -> None:
        if not self.last or value != self.last[1]:
            if len(self.changes) < 4:
                self.changes.append((at, value))
            else:
                self.overflow = True
        self.last = (at, value)

    def points(self) -> list[tuple[float, float | None]]:
        points = list(self.changes)
        if self.last and self.last != points[-1]:
            points.append(self.last)
        if self.overflow or len(points) > 4:
            return [(points[0][0], None)]
        return points


def graph_history(path: Path, start: datetime, end: datetime, now: datetime, points: int,
                  max_age_seconds: float, ev_capacity: float, ess_capacity: float,
                  demo: bool) -> dict[str, Any]:
    start, end, now = instant(start), instant(end), instant(now)
    if not 0 < (end - start).total_seconds() <= 8 * 86400:
        raise ValueError("Graph history ranges must be positive and at most eight elapsed days")
    if not 100 <= points <= 2000:
        raise ValueError("Graph history points must be between100 and2000 per series")
    stop = min(end, now)
    width = max(1.0, (end - start).total_seconds() / (points // 4))
    buckets: dict[str, dict[int, SeriesBucket | StepBucket]] = {name: {} for name in SERIES}
    count = 0
    capacity_fallback = False

    def add(at: datetime, values: dict[str, float | None]) -> None:
        if not start <= at <= stop:
            return
        index = min(points // 4 - 1, int((at - start).total_seconds() / width))
        for name in SERIES:
            bucket = buckets[name].setdefault(index, StepBucket() if name == "monthly_peak" else SeriesBucket())
            bucket.add(at.timestamp() * 1000, values[name])

    previous: datetime | None = None
    empty: dict[str, float | None] = dict.fromkeys(SERIES)
    if stop >= start:
        for sample in measurements(path, start - timedelta(seconds=max_age_seconds), stop,
                                   timeout_seconds=5):
            at = instant(sample["at"])
            if previous is not None and (at - previous).total_seconds() > max_age_seconds:
                add(previous + timedelta(seconds=max_age_seconds), empty)
            values = graph_values(sample, ev_capacity, ess_capacity, demo)
            if at < start and values["monthly_peak"] is not None:
                buckets["monthly_peak"].setdefault(0, StepBucket()).add(
                    start.timestamp() * 1000, values["monthly_peak"])
            add(at, values)
            if start <= at <= stop and any(value is not None for value in values.values()):
                count += 1
                if values["ev_soc"] is not None or values["ess_soc"] is not None:
                    capacity_fallback |= "ev_capacity_kwh" not in sample or "ess_capacity_kwh" not in sample
            previous = at
        if previous is not None and (stop - previous).total_seconds() > max_age_seconds:
            add(previous + timedelta(seconds=max_age_seconds), empty)
        if previous is not None and stop - previous <= timedelta(seconds=max_age_seconds):
            tail = dict(empty)
            tail["monthly_peak"] = values["monthly_peak"]
            # Extend only this sensor, without invalidating other series in the same bucket.
            index = min(points // 4 - 1, int((stop - start).total_seconds() / width))
            buckets["monthly_peak"].setdefault(index, StepBucket()).add(stop.timestamp() * 1000, tail["monthly_peak"])
    return {"start": start.isoformat(), "end": end.isoformat(), "as_of": now.isoformat(),
            "bucket_seconds": width, "sample_count": count, "capacity_fallback": capacity_fallback,
            "series": {name: [point for _, bucket in sorted(groups.items()) for point in bucket.points()]
                       for name, groups in buckets.items()}}
