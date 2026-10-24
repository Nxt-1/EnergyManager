"""Read-only daily energy estimates from the existing measurement archive."""

from __future__ import annotations

import json
import math
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo

from .domain import instant


def measurements(path: Path, start: datetime, end: datetime) -> Iterator[dict[str, Any]]:
    """Stream timestamp-ordered records using a separate, read-only SQLite connection."""
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT body FROM events WHERE kind='measurement' "
            "AND julianday(json_extract(body,'$.at')) BETWEEN julianday(?) AND julianday(?) "
            "ORDER BY julianday(json_extract(body,'$.at')), sequence",
            (start.isoformat(), end.isoformat()),
        )
        previous: dict[str, Any] | None = None
        for (body,) in rows:
            sample = json.loads(body)
            # The loop archives cached snapshots too. Count a validated read only once.
            if previous is not None and instant(sample["at"]) != instant(previous["at"]):
                yield previous
            elif previous is not None and previous.get("quality") in ("measured", "SYNTHETIC"):
                # Later watchdog failures can archive the same old timestamp as unknown.
                # They must not erase the originally valid read's short coverage.
                continue
            previous = sample
        if previous is not None:
            yield previous
    finally:
        connection.close()


def power_components(sample: dict[str, Any]) -> dict[str, float] | None:
    keys = ("house_kw", "pv_ac_kw", "pv_dc_kw", "ev_power_kw", "ess_power_kw")
    values: list[float] = []
    for key in keys:
        value = sample.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return None
        values.append(float(value))
    house, ac, dc, ev, ess = values
    if min(house, ac, dc, ev) < 0:
        return None
    grid = house + ev - ac - ess
    return {"import": max(0, grid), "export": max(0, -grid), "solar": ac + dc,
            "solar_ac": ac, "solar_dc": dc, "house": house, "ev": ev,
            "ess_charge": max(0, -ess), "ess_discharge": max(0, ess)}


def daily_energy(path: Path, now: datetime, timezone: str, max_age_seconds: float,
                 demo: bool) -> dict[str, Any]:
    """Integrate sample-held power only while its validated read is still fresh."""
    now = instant(now)
    local = now.astimezone(ZoneInfo(timezone))
    start = local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)
    totals = dict.fromkeys(("import", "export", "solar", "solar_ac", "solar_dc", "house", "ev",
                            "ess_charge", "ess_discharge"), 0.0)
    covered = 0.0
    previous: dict[str, Any] | None = None

    def integrate(sample: dict[str, Any], until: datetime) -> None:
        nonlocal covered
        at = instant(sample["at"])
        left = max(start, at)
        right = min(now, until, at + timedelta(seconds=max_age_seconds))
        if right <= left or sample.get("quality") != ("SYNTHETIC" if demo else "measured"):
            return
        powers = power_components(sample)
        if powers is None:
            return
        seconds = (right - left).total_seconds()
        covered += seconds
        for key, power in powers.items():
            totals[key] += power * seconds / 3600

    for sample in measurements(path, start - timedelta(seconds=max_age_seconds), now):
        if previous is not None:
            integrate(previous, instant(sample["at"]))
        previous = sample
    if previous is not None:
        integrate(previous, now)
    elapsed = (now - start).total_seconds()
    return {"date": local.date().isoformat(), "timezone": timezone, "as_of": now.isoformat(),
            "kwh": totals if covered > 0 else None, "covered_seconds": covered,
            "elapsed_seconds": elapsed, "partial": elapsed - covered > 1,
            "source": "SYNTHETIC power integration" if demo else "Recorded power integration"}
