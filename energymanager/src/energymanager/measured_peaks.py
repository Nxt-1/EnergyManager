"""Measured billing-peak episodes, independent of planning and control availability."""

from __future__ import annotations

import asyncio
import math
from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from .domain import instant

if TYPE_CHECKING:
    from .service import Application


class MeasuredPeaks:
    def __init__(self, app: Application) -> None:
        self.app = app
        self.task: asyncio.Task[None] | None = None
        self.last_read: datetime | None = None

    def start(self) -> None:
        if not self.app.demo:
            self.task = asyncio.create_task(self.loop())

    async def close(self) -> None:
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)

    def observe(self, at: datetime, peak_kw: float) -> None:
        if not math.isfinite(peak_kw) or peak_kw < 0:
            return
        store = self.app.store
        state = store.get("measured_peak", {})
        if state and at <= instant(state["at"]):
            return
        month = at.astimezone(ZoneInfo(self.app.policy.timezone)).strftime("%Y-%m")
        same_month = state.get("month") == month
        baseline = max(self.app.policy.billing_floor_kw, state["peak_kw"] if same_month else 0)
        pending = state.get("pending", {})
        last_increase = state.get("last_increase") if same_month else None
        if state and peak_kw > baseline:
            if last_increase is None or at - instant(last_increase) >= timedelta(minutes=15):
                key = f"measured-peak:{month}:{at.isoformat()}"
                pending[key] = {
                    "kind": "measured_peak", "at": at.isoformat(), "peak_kw": peak_kw,
                    "previous_billable_kw": baseline,
                    "message": f"Measured monthly grid-import peak increased from {baseline:.3f} to "
                               f"{peak_kw:.3f} kW (15-minute average).",
                }
            last_increase = at.isoformat()
        # Within a month, a lower transient reading cannot create duplicate rises.
        store.put("measured_peak", {"month": month, "at": at.isoformat(),
                  "peak_kw": max(peak_kw, state["peak_kw"]) if same_month else peak_kw,
                  "last_increase": last_increase, "pending": pending})

    def sample(self) -> None:
        app = self.app
        reading = app.ha.inputs.readings.get("monthly_peak_kw") if app.ha else None
        if reading is None or reading.received_at == self.last_read:
            return
        self.last_read = reading.received_at
        valid = reading.issue(app.now()) is None and isinstance(reading.value, (float, int))
        value = reading.value if valid else None
        # A partial measurement preserves this sensor even if unrelated inputs fail.
        app.store.event("measurement", {"at": reading.received_at, "quality": "unknown",
                        "monthly_peak_valid": valid, "monthly_peak_kw": value})
        if valid and isinstance(value, (float, int)):
            self.observe(reading.received_at, float(value))

    async def deliver(self) -> None:
        state = self.app.store.get("measured_peak", {})
        for key, body in list(state.get("pending", {}).items()):
            if await self.app.notifications.inform(key, body):
                # Reads can arrive while mobile delivery awaits I/O.
                current = self.app.store.get("measured_peak", {})
                current.get("pending", {}).pop(key, None)
                self.app.store.put("measured_peak", current)

    async def loop(self) -> None:
        while True:
            self.sample()
            await self.deliver()
            await asyncio.sleep(1)
