"""Persist one immutable energy baseline per installation-local day and operating mode."""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from .energy import daily_energy, end_of_day_energy

if TYPE_CHECKING:
    from .service import Application


class DailyEstimates:
    def __init__(self, application: Application) -> None:
        self.application = application
        self.task: asyncio.Task[None] | None = None
        self.read_lock = asyncio.Lock()
        self.actual: dict[str, Any] | None = None
        self.actual_key: str | None = None
        self.read_at = 0.0
        self.error: str | None = None

    def key(self, at: datetime) -> str:
        app = self.application
        day = at.astimezone(ZoneInfo(app.policy.timezone)).date().isoformat()
        return f"daily_estimate:{app.demo}:{app.policy.timezone}:{day}"

    def view(self, at: datetime) -> dict[str, Any] | None:
        return self.application.store.get(self.key(at))

    def start(self) -> None:
        self.task = asyncio.create_task(self.run())

    async def close(self) -> None:
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)

    async def recorded(self, at: datetime) -> dict[str, Any]:
        """Coalesce archive readers and keep expensive integration outside the control loop."""
        async with self.read_lock:
            key = self.key(at)
            if self.actual is not None and key == self.actual_key and monotonic() - self.read_at < 30:
                return dict(self.actual)
            app = self.application
            result = await asyncio.to_thread(daily_energy, app.store.path, at, app.policy.timezone,
                                             app.policy.measurement_max_age_seconds, app.demo)
            self.actual, self.actual_key, self.read_at = result, key, monotonic()
            return dict(result)

    async def capture(self) -> None:
        app = self.application
        now = app.now()
        if self.view(now) is not None:
            return
        plan, revision = app.accepted, app.revision
        age = (now - app.observation.at).total_seconds()
        quality = "SYNTHETIC" if app.demo else "measured"
        if not app.ess_valid or app.observation.quality != quality or not -5 <= age <= app.policy.measurement_max_age_seconds:
            return
        if not plan or not plan.get("valid") or plan.get("revision") != revision:
            return
        timezone = app.policy.timezone
        local = now.astimezone(ZoneInfo(timezone))
        midnight = local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)
        summary: dict[str, Any] = {
            "date": local.date().isoformat(), "timezone": timezone, "as_of": midnight.isoformat(),
            "kwh": dict.fromkeys(("import", "export", "solar_ac", "solar_dc", "solar", "house", "ev",
                                  "ess_charge", "ess_discharge"), 0.0), "partial": False,
        }
        maximum_age = app.policy.forecast_max_age_seconds
        efficiency = app.snapshot.capabilities.ac_discharge_efficiency
        totals = end_of_day_energy(summary, plan, revision, maximum_age, efficiency)
        kind = "midnight"
        if totals is None:
            # Starting/upgrading later cannot manufacture a forecast that existed at midnight.
            summary = await self.recorded(now)
            totals = end_of_day_energy(summary, plan, revision, maximum_age, efficiency)
            kind = "first_available"
        if totals is None or self.key(now) != self.key(app.now()) or plan is not app.accepted or revision != app.revision:
            return
        if not app.ess_valid or app.observation.quality != quality:
            return
        record = {"date": local.date().isoformat(), "timezone": timezone, "demo": app.demo,
                  "captured_at": app.now().isoformat(), "basis_at": summary["as_of"], "kind": kind,
                  "partial": summary["partial"], "plan_id": plan["id"], "revision": revision, "kwh": totals}
        app.store.put(self.key(now), record)
        app.store.event("daily_energy_estimate", record)

    async def run(self) -> None:
        while True:
            try:
                await self.capture()
                self.error = None
            except (OSError, sqlite3.Error, TimeoutError, ValueError, KeyError) as exc:
                message = f"Daily estimate unavailable: {type(exc).__name__}: {exc}"
                if message != self.error:
                    self.application.store.event("daily_estimate_error", {"reason": message})
                self.error = message
            now = self.application.now()
            local = now.astimezone(ZoneInfo(self.application.policy.timezone))
            midnight = (local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).astimezone(UTC)
            await asyncio.sleep(min(5, max(0.01, (midnight - now).total_seconds())))
