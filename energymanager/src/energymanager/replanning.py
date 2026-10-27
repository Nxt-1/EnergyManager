"""Planning evidence from sustained forecast bias and unexpected stored-energy loss."""

from __future__ import annotations

from collections import deque
from dataclasses import replace
from datetime import datetime
from typing import Any

from .domain import Observation, Snapshot, instant


class ReplanningEvidence:
    """Keep ordinary power noise out of the solver; change assumptions before requesting work."""

    def __init__(self) -> None:
        self.forecast_id: str | None = None
        self.previous_forecast: Snapshot | None = None
        self.samples: deque[tuple[datetime, datetime, tuple[float, ...]]] = deque()
        self.previous: tuple[datetime, tuple[float, ...]] | None = None
        self.bias: tuple[float, ...] = (0.0, 0.0, 0.0)
        self.bias_at: datetime | None = None
        self.plan_id: str | None = None
        self.reported_deficits: tuple[float, ...] = (0.0, 0.0)

    def forecast(self, observation: Observation, snapshot: Snapshot) -> dict[str, Any] | None:
        """Require a covered fifteen-minute energy discrepancy, separately tracking house and PV."""
        at = observation.at
        interval = next((i for i in snapshot.intervals if i.start <= at < i.end), None)
        if (interval is None and 0 <= (snapshot.intervals[0].start - at).total_seconds()
                <= snapshot.policy.measurement_max_age_seconds):
            interval = snapshot.intervals[0]  # Snapshot construction follows the successful HA read.
        if snapshot.forecast_id != self.forecast_id:
            previous_interval = None
            if self.previous_forecast:
                previous_interval = next((i for i in self.previous_forecast.intervals if i.start <= at < i.end), None)
            if (previous_interval and interval and self.bias_at and self.previous
                    and 0 <= (at - self.previous[0]).total_seconds() <= snapshot.policy.measurement_max_age_seconds):
                # A new issuance is already a planning event. Keep its corrected starting
                # assumption consistent; remove only the bias the new forecast accounts for.
                carried = tuple(self.bias[k] + getattr(previous_interval, name) - getattr(interval, name)
                                for k, name in enumerate(("house_kw", "pv_ac_kw", "pv_dc_kw")))
                self.bias = tuple(0.0 if abs(value) < 1e-9 else value for value in carried)
                self.bias_at = at
            else:
                self.bias = (0.0, 0.0, 0.0)
                self.bias_at = None
            self.forecast_id = snapshot.forecast_id
            self.samples.clear()
            self.previous = None
        self.previous_forecast = snapshot
        if interval is None or observation.quality not in ("measured", "SYNTHETIC"):
            self.samples.clear()
            self.previous = None
            self.bias, self.bias_at = (0.0, 0.0, 0.0), None
            return None
        residual = (observation.house_kw - interval.house_kw,
                    observation.pv_ac_kw - interval.pv_ac_kw,
                    observation.pv_dc_kw - interval.pv_dc_kw)
        if self.previous:
            before, values = self.previous
            elapsed = (at - before).total_seconds()
            if elapsed <= 0:
                return None  # Repeated reads cannot manufacture energy or coverage.
            if elapsed <= snapshot.policy.measurement_max_age_seconds:
                self.samples.append((before, at, values))
            else:
                self.samples.clear()
                self.bias, self.bias_at = (0.0, 0.0, 0.0), None
        self.previous = (at, residual)
        cutoff = at.timestamp() - 900
        while self.samples and self.samples[0][1].timestamp() <= cutoff:
            self.samples.popleft()
        coverage = sum(end.timestamp() - max(start.timestamp(), cutoff) for start, end, _ in self.samples)
        if coverage < 900 - 1e-6:
            return None
        means = tuple(sum(values[k] * (end.timestamp() - max(start.timestamp(), cutoff))
                          for start, end, values in self.samples) / coverage for k in range(3))
        delta = tuple(value - old for value, old in zip(means, self.bias))
        net_change = max(abs(delta[0] - delta[1]), abs(delta[2]))
        if net_change < 0.5 or net_change * coverage / 3600 < 0.1:
            return None
        latest = tuple(value - old for value, old in zip(residual, self.bias))
        if not ((delta[0] - delta[1]) * (latest[0] - latest[1]) >= 0.25
                or delta[2] * latest[2] >= 0.25):
            return None  # An appliance/PV excursion that has already ended is no future assumption.
        if self.bias_at and (at - self.bias_at).total_seconds() < 900:
            return None
        self.bias, self.bias_at = means, at
        return {"house_kw": means[0], "pv_ac_kw": means[1], "pv_dc_kw": means[2],
                "coverage_seconds": coverage, "changed_energy_kwh": net_change * coverage / 3600}

    def adjusted(self, snapshot: Snapshot) -> Snapshot:
        """Apply observed bias for thirty minutes, fading to the original forecast after one hour."""
        if (self.bias_at is None or self.previous is None or not any(self.bias)
                or snapshot.forecast_id != self.forecast_id
                or not 0 <= (snapshot.intervals[0].start - self.previous[0]).total_seconds()
                <= snapshot.policy.measurement_max_age_seconds):
            return snapshot
        start = snapshot.intervals[0].start
        intervals = []
        for interval in snapshot.intervals:
            midpoint = interval.start + (interval.end - interval.start) / 2
            seconds = (midpoint - start).total_seconds()
            weight = max(0.0, min(1.0, (3600 - seconds) / 1800))
            intervals.append(replace(interval, **{
                name: max(0.0, getattr(interval, name) + self.bias[k] * weight)
                for k, name in enumerate(("house_kw", "pv_ac_kw", "pv_dc_kw"))
            }))
        return replace(snapshot, intervals=tuple(intervals),
                       forecast_id=f"{snapshot.forecast_id}:bias:{self.bias_at.isoformat()}",
                       provenance=snapshot.provenance + " · measured near-term forecast correction")

    def resources(self, observation: Observation, plan: dict[str, Any] | None,
                  snapshot: Snapshot) -> dict[str, float] | None:
        """React to new material inventory deficits, never ordinary charging/discharging progress."""
        if not plan or observation.quality not in ("measured", "SYNTHETIC"):
            return None
        if plan["id"] != self.plan_id:
            self.plan_id = plan["id"]
            self.reported_deficits = (0.0, 0.0)
        at = observation.at
        position = next((t for t, i in enumerate(plan["intervals"])
                         if instant(i["start"]) <= at < instant(i["end"])), None)
        if position is None:
            return None
        interval, flows = plan["intervals"][position], plan["flows"]
        start, end = instant(interval["start"]), instant(interval["end"])
        fraction = (at - start).total_seconds() / (end - start).total_seconds()

        def expected(name: str) -> float:
            return flows[name][position] + fraction * (flows[name][position + 1] - flows[name][position])

        deficits = (max(0.0, expected("ev_energy") - observation.ev_kwh),
                    max(0.0, expected("ess_solar") + expected("ess_grid")
                        + snapshot.capabilities.ess_min_kwh - observation.ess_kwh))
        thresholds = (max(0.5, snapshot.capabilities.ev_capacity_kwh * 0.01),
                      max(0.5, snapshot.capabilities.ess_capacity_kwh * 0.02))
        if not any(value >= old + threshold for value, old, threshold
                   in zip(deficits, self.reported_deficits, thresholds)):
            return None
        self.reported_deficits = tuple(value if value >= old + threshold else old
                                       for value, old, threshold
                                       in zip(deficits, self.reported_deficits, thresholds))
        return {"ev_shortfall_kwh": deficits[0], "ess_shortfall_kwh": deficits[1]}
