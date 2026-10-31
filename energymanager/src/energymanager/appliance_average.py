"""Equal-weight start-aligned means of complete, reviewed appliance cycles."""

from __future__ import annotations

import json
import math
import sqlite3
from collections import defaultdict
from contextlib import closing
from pathlib import Path
from time import monotonic
from typing import Any

from .domain import instant


def average_recordings(path: Path, mode: str, machine: str, program: str,
                       identities: list[str]) -> dict[str, Any]:
    """Average real-time sample holds; completed cycles contribute zero in the tail."""
    changes: dict[float, float] = defaultdict(float)
    changes[0] = 0
    durations: list[float] = []
    energies: list[float] = []
    deadline = monotonic() + 10
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.set_progress_handler(lambda: int(monotonic() > deadline), 1000)
        connection.execute("BEGIN")
        for identity in identities:
            row = connection.execute("SELECT body FROM appliance_recordings WHERE id=? AND mode=?",
                                     (identity, mode)).fetchone()
            if not row:
                raise ValueError("A profile contributor is unavailable")
            recording = json.loads(row[0])
            if (recording["status"] != "saved" or recording["interrupted"]
                    or recording["machine"] != machine or recording["program"] != program):
                raise ValueError("Only complete reviewed recordings of the same program can be averaged")
            summary = recording["summary"]
            start, end = summary["start_seconds"], summary["end_seconds"]
            duration = end - start
            if duration <= 0 or not summary["complete"]:
                raise ValueError("A profile contributor has incomplete coverage")
            origin = instant(recording["started_at"]).timestamp()
            points = connection.execute(
                "SELECT at,power_w FROM appliance_samples WHERE recording_id=? "
                "AND at BETWEEN ? AND ? ORDER BY at",
                (identity, origin + start - 15, origin + end + 15))
            previous: tuple[float, float | None] | None = None
            covered = 0.0
            energy = 0.0
            for at, power in points:
                if monotonic() > deadline:
                    raise TimeoutError("Profile averaging exceeded its read budget")
                if previous is not None:
                    left, right = max(origin + start, previous[0]), min(origin + end, at)
                    if (right > left and previous[1] is not None and power is not None
                            and at - previous[0] <= 15):
                        value = float(previous[1])
                        if not math.isfinite(value) or value < 0:
                            raise ValueError("A contributor has an invalid power sample")
                        relative_left = 0.0 if left == origin + start else left - origin - start
                        relative_right = duration if right == origin + end else right - origin - start
                        changes[relative_left] += value
                        changes[relative_right] -= value
                        covered += right - left
                        energy += (right - left) * value
                previous = (at, power)
            if abs(covered - duration) > .001:
                raise ValueError("A profile contributor contains missing measurements")
            durations.append(duration)
            energies.append(energy / 3600000)
    count = len(identities)
    duration = max(durations)
    changes[duration] += 0
    points_out: list[dict[str, float]] = []
    power_sum = 0.0
    peak = 0.0
    for seconds, change in sorted(changes.items()):
        power_sum += change
        mean = max(0.0, power_sum / count)
        if seconds == duration:
            mean = 0.0
        peak = max(peak, mean)
        if not points_out or abs(points_out[-1]["power_w"] - mean) > 1e-9 or seconds == duration:
            points_out.append({"seconds": seconds, "power_w": mean})
    energy_kwh = math.fsum(energies) / count
    return {"points": points_out, "summary": {"start_seconds": 0, "end_seconds": duration,
            "duration_seconds": duration, "mean_duration_seconds": math.fsum(durations) / count,
            "energy_kwh": energy_kwh, "average_w": energy_kwh * 3600000 / duration,
            "peak_w": peak, "complete": True, "covered_seconds": duration}}
