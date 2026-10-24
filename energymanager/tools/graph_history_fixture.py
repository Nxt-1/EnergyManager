"""Explicitly SYNTHETIC archive fixtures for local graph verification only."""

from __future__ import annotations

import math
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from energymanager.domain import Capabilities, Observation, encode, json_data
from energymanager.store import Store


def seed_history(store: Store, now: datetime, capabilities: Capabilities, *, days: int = 2) -> int:
    """Seed old fake readings; do not alter live inputs, learned baselines or authority."""
    zone = ZoneInfo("Europe/Brussels")
    local = now.astimezone(zone)
    first = (local.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)).astimezone(UTC)
    end = now - timedelta(hours=1)
    count = 0

    def rows() -> Iterator[tuple[str, str]]:
        nonlocal count
        at = first
        while at < end:
            day = at.astimezone(zone)
            seconds = day.hour * 3600 + day.minute * 60 + day.second
            # Deliberate outage and EV-only unknowns must remain visible, not interpolated.
            if not 12 * 3600 <= seconds < 13 * 3600:
                solar = max(0, math.sin((seconds - 6 * 3600) / (12 * 3600) * math.pi)) * 2
                spike = day.hour == 10 and day.minute == 5 and day.second == 0
                house = 4.8 if spike else 0.4 + (0.2 if day.minute % 20 < 3 else 0)
                observation = Observation(at, capabilities.ev_capacity_kwh * 0.45,
                    capabilities.ess_capacity_kwh * (0.5 + 0.1 * math.sin(seconds / 86400 * 2 * math.pi)),
                    True, house, solar, solar * 0.5, ess_power_kw=0.2,
                    ev_state_known=not (15 * 3600 <= seconds < 15 * 3600 + 900))
                body = {**json_data(observation),
                        "provenance": "SYNTHETIC archived graph fixture; no installation measurements",
                        "ev_capacity_kwh": capabilities.ev_capacity_kwh,
                        "ess_capacity_kwh": capabilities.ess_capacity_kwh}
                count += 1
                yield (now.isoformat(), encode(body))
            at += timedelta(seconds=5)

    with store.connection:
        store.connection.executemany("INSERT INTO events(at,kind,body) VALUES (?, 'measurement',?)", rows())
    return count
