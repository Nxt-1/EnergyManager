"""Daily grid energy from P1 counters, independent of archived power coverage."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import aiohttp

from .domain import instant
from .live_inputs import Reading

if TYPE_CHECKING:
    from .service import Application


class GridEnergy:
    """Persist midnight counter baselines; never fill missing meter data with power."""

    def __init__(self, application: Application) -> None:
        self.application = application
        self.lock = asyncio.Lock()
        self.cache_key: tuple[Any, ...] | None = None
        self.read_at = 0.0
        self.channels: dict[str, Any] = {}

    async def refresh(self, at: datetime) -> dict[str, Any]:
        app = self.application
        local = at.astimezone(ZoneInfo(app.policy.timezone))
        midnight = local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)
        entities = app.ha.entities if app.ha and not app.demo else {}
        key = (app.demo, app.policy.timezone, local.date().isoformat(),
               entities.get("grid_import_kwh"), entities.get("grid_export_kwh"))
        async with self.lock:
            if key == self.cache_key and monotonic() - self.read_at < 30:
                return self.channels
            rows = await asyncio.gather(*(self.read(direction, entities.get(f"grid_{direction}_kwh"),
                                                   midnight, at) for direction in ("import", "export")))
            self.channels = dict(zip(("import", "export"), rows))
            self.cache_key, self.read_at = key, monotonic()
            return self.channels

    async def read(self, direction: str, entity: str | None,
                   midnight: datetime, at: datetime) -> dict[str, Any]:
        app = self.application
        result: dict[str, Any] = {"kwh": None, "partial": False, "entity_id": entity,
                                  "source": "P1 cumulative energy counter", "as_of": at.isoformat(),
                                  "error": None}
        if app.demo or not entity or not app.ha:
            result["error"] = ("P1 energy is unavailable in synthetic demo mode" if app.demo else
                               f"Select the P1 cumulative {direction} energy sensor in Settings")
            return result
        if app.ha.session is None:
            result["error"] = "Home Assistant input connection is not open"
            return result
        try:
            row = await app.ha.entity_state(entity)
            # Available unchanged counters are valid; HA metadata is not an input freshness gate.
            reading = Reading.parse(entity, row, at, "kWh", app.policy.measurement_max_age_seconds,
                                    nonnegative=True)
            current = float(reading.require(at))
            identity = f"grid_energy:{app.policy.timezone}:{midnight.isoformat()}:{entity}"
            baseline = app.store.get(identity)
            if baseline is None:
                history = await app.ha.entity_history(entity, midnight, midnight + timedelta(seconds=1))
                candidates = [item for group in history for item in group
                              if isinstance(item, dict) and item.get("entity_id") == entity
                              and instant(item["last_changed"]) <= midnight]
                if not candidates:
                    raise ValueError("Midnight P1 reading unavailable in HA history; no power fallback")
                initial = max(candidates, key=lambda item: instant(item["last_changed"]))
                start = float(Reading.parse(entity, initial, at, "kWh",
                              app.policy.measurement_max_age_seconds, nonnegative=True).require(at))
                baseline = {"kwh": start, "last_kwh": start, "invalid": False,
                            "last_reset": initial.get("attributes", {}).get("last_reset")}
            reset = row.get("attributes", {}).get("last_reset")
            reset_changed = reset != baseline.get("last_reset") and reset is not None
            if current < baseline["last_kwh"] or reset_changed:
                baseline = {**baseline, "invalid": True}
            baseline = {**baseline, "last_kwh": current, "last_read_at": at.isoformat()}
            app.store.put(identity, baseline)
            if baseline["invalid"]:
                raise ValueError("P1 counter reset or decreased; today's total is unavailable")
            result.update(kwh=current - baseline["kwh"], baseline_at=midnight.isoformat())
        except (aiohttp.ClientError, TimeoutError, ValueError, TypeError, KeyError, AttributeError) as exc:
            result["error"] = f"{entity}: {type(exc).__name__}: {exc}"
        return result
