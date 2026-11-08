"""Measured constant household background with explicit dishwasher separation/coverage."""

from __future__ import annotations

import bisect
import math
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING, Any

from .domain import Observation, instant

if TYPE_CHECKING:
    from .bosch import BoschDishwasher
    from .store import Store

MODEL = "measured-constant-7d-v1"
MAX_SAMPLE_GAP = 315  # Five-minute persistence cadence plus one 15-second observation-match tolerance.


class BackgroundCoverageError(ValueError):
    def __init__(self, summary: dict[str, Any]) -> None:
        self.summary = summary
        super().__init__(f"Insufficient measured background coverage: {summary['covered_seconds']/3600:.2f} h, {summary['five_minute_bins']} five-minute bins; require 1 covered hour and 13 bins")


class MeasuredBackground:
    def __init__(self, store: Store) -> None:
        self.store = store
        self.bosch: BoschDishwasher | None = None
        self.last_at: datetime | None = None

    @property
    def meter(self) -> str | None:
        return self.bosch.profiles.settings["machines"]["dishwasher"]["entity_id"] if self.bosch and self.bosch.enabled else None

    def matched(self, observation: Observation) -> float | None:
        if not self.meter:
            return observation.house_kw
        if self.bosch is None or self.bosch.at is None:
            return None
        if abs((observation.at - instant(self.bosch.at)).total_seconds()) > 15:
            return None
        meter = self.bosch.readings.get("meter", {})
        power = meter.get("power_w")
        if power is None or observation.house_kw * 1000 < power:
            return None
        return observation.house_kw - power / 1000

    def record(self, observation: Observation) -> None:
        if self.last_at and (observation.at - self.last_at).total_seconds() < 300:
            return
        background = self.matched(observation)
        meter = (observation.house_kw - background) * 1000 if background is not None and self.meter else None
        with self.store.connection:
            self.store.connection.execute(
                "INSERT OR IGNORE INTO background_samples VALUES (?,?,?,?,?,?)",
                (observation.at.timestamp(), observation.house_kw * 1000, meter,
                 background * 1000 if background is not None else None,
                 self.meter or "unseparated", "matched successful reads" if background is not None else "meter missing/mismatched"))
        self.last_at = observation.at


def constant_estimate(path: Path, at: datetime, meter: str | None) -> dict[str, Any]:
    """Use retained measured points only; run on a bounded read-only SQLite worker."""
    end = at.timestamp()
    start = end - timedelta(days=7).total_seconds()
    deadline = monotonic() + 10
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as connection:
        connection.set_progress_handler(lambda: int(monotonic() > deadline), 5000)
        rows = connection.execute("SELECT at,house_w,meter_w,background_w,source FROM background_samples WHERE at>=? AND at<=? ORDER BY at", (start, end)).fetchall()
        eligible = {time: background for time, _, _, background, source in rows
                    if source == (meter or "unseparated") and background is not None}
        historical = connection.execute("SELECT at,power_w FROM load_samples WHERE at>=? AND at<=? ORDER BY at", (start, end)).fetchall()
        if meter:
            readings = connection.execute(
                "SELECT DISTINCT s.at,s.power_w,s.error FROM appliance_samples s JOIN appliance_recordings r ON r.id=s.recording_id "
                "WHERE r.mode='configured' AND json_extract(r.body,'$.machine')='dishwasher' "
                "AND json_extract(r.body,'$.entity_id')=? AND s.at>=? AND s.at<=? ORDER BY s.at", (meter, start-15, end+15)).fetchall()
            grouped: dict[float,list[tuple[Any,...]]] = {}
            for row in readings:
                grouped.setdefault(row[0],[]).append(row)
            readings = [values[0] if len(values)==1 else (time,None,"ambiguous retained meter evidence")
                        for time,values in sorted(grouped.items())]
            times = [row[0] for row in readings]
            for time, house in historical:
                index = bisect.bisect_right(times, time)
                left = readings[index-1] if index else None
                right = readings[index] if index < len(readings) else left
                if (left and right and 0 <= time-left[0] <= 15 and 0 <= right[0]-time <= 15
                        and left[1] is not None and right[1] is not None and not left[2] and not right[2]
                        and house >= left[1]):
                    eligible.setdefault(time, house-left[1])
        else:
            for time, house in historical:
                eligible.setdefault(time, house)
        points = sorted((time, value) for time, value in eligible.items()
                        if math.isfinite(value) and value >= 0)
    covered = energy_ws = 0.0
    bins = {int(time // 300) for time, _ in points}
    for (left, power), (right, _) in zip(points, points[1:]):
        seconds = right-left
        if 0 < seconds <= MAX_SAMPLE_GAP:
            covered += seconds
            energy_ws += power*seconds
    span = points[-1][0]-points[0][0] if points else 0
    result = {"model": MODEL, "meter": meter, "separated": bool(meter), "generated_at": at.isoformat(),
              "window_start": datetime.fromtimestamp(start, UTC).isoformat(), "window_end": at.isoformat(),
              "samples": len(points), "five_minute_bins": len(bins), "covered_seconds": covered,
              "gap_seconds": max(0, span-covered), "window_coverage": covered/(7*86400),
              "eligible": covered >= 3600-1e-6 and len(bins) >= 13,
              "power_w": energy_ws/covered if covered else None}
    if not result["eligible"]:
        raise BackgroundCoverageError(result)
    return result
