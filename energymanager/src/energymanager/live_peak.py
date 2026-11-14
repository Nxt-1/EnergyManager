"""Measured quarter energy and conservative response-aware import projection."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any

from .domain import Capabilities, Observation, Policy, instant


@dataclass(frozen=True)
class PeakProjection:
    ev_kw: float
    import_kw: float
    threatened: bool
    unavoidable_kwh: float
    prefix_kwh: float


class LivePeak:
    def __init__(self, capabilities: Capabilities, policy: Policy) -> None:
        self.c, self.p = capabilities, policy
        self.quarter: datetime | None = None
        self.at: datetime | None = None
        self.import_kw = 0.0
        self.prefix_kwh = 0.0

    def project(self, o: Observation, at: datetime, plan: dict[str, Any] | None,
                position: int | None, limit: float, requested_ev: float,
                ev_controllable: bool = True) -> PeakProjection:
        if not ev_controllable:
            # External charging is demand throughout the projection, not curtailment capacity.
            o = replace(o, house_kw=o.house_kw + o.ev_power_kw, ev_power_kw=0)
            requested_ev = 0
        quarter = at.replace(minute=at.minute // 15 * 15, second=0, microsecond=0)
        end = quarter + timedelta(minutes=15)
        measured_import = max(0.0, o.house_kw + o.ev_power_kw - o.pv_ac_kw - o.ess_power_kw)
        if quarter != self.quarter:
            self.prefix_kwh = 0.0
            self.quarter = quarter
        if self.at is not None:
            elapsed = max(0.0, (at - max(self.at, quarter)).total_seconds()) / 3600
            # A newer low meter prefix cannot erase energy already observed between reads.
            self.prefix_kwh += max(self.import_kw, measured_import) * elapsed
        if o.at >= quarter:
            # Reject a previous-quarter carryover that cannot physically belong to this quarter.
            maximum = self.c.grid_connection_kw * max(0.0, (at - quarter).total_seconds()) / 3600
            if o.quarter_import_kwh <= maximum + 1e-5:
                self.prefix_kwh = max(self.prefix_kwh, o.quarter_import_kwh)
        self.at, self.import_kw = at, measured_import
        hours = max(1e-9, (end - at).total_seconds() / 3600)
        budget = limit * .25 - self.prefix_kwh
        # This is a conservative allowance from the existing read watchdog, not a
        # claim about installed charger latency. Actual unconfirmed power is retained.
        delay_h = min(hours, (self.p.measurement_max_age_seconds + self.p.control_period_seconds) / 3600)
        confirmed_discharge = min(
            max(0.0, o.ess_power_kw), self.c.ac_discharge_kw,
            max(0.0, o.ess_kwh - self.c.ess_min_kwh) * self.c.ac_discharge_efficiency / hours,
        )
        shape: list[tuple[float, float, float]] = []
        household_energy = 0.0
        if plan is not None and position is not None:
            for t in range(position, len(plan["intervals"])):
                interval = plan["intervals"][t]
                left, right = max(at, instant(interval["start"])), min(end, instant(interval["end"]))
                if left >= end:
                    break
                if right <= left:
                    continue
                net = max(o.house_kw - o.pv_ac_kw,
                          interval["house_kw"] - min(interval["pv_ac_kw"], o.pv_ac_kw))
                household_energy += (right - left).total_seconds() / 3600 * max(0.0, net)
                f = plan["flows"]
                net += max(0.0, f["grid_store"][t])
                ev = 0 if not ev_controllable else requested_ev if t == position else sum(f[name][t] for name in
                                                            ("grid_ev", "pv_ev", "solar_dis_ev"))
                shape.append(((right - left).total_seconds() / 3600, net, max(0.0, ev)))
        covered = sum(row[0] for row in shape)
        if covered < hours - 1e-9:
            household_energy += (hours - covered) * max(0.0, o.house_kw - o.pv_ac_kw)
            shape.append((hours - covered, o.house_kw - o.pv_ac_kw, 0.0))

        def imports(scale: float) -> float:
            projected = sum(duration * max(0.0, net + ev * scale - confirmed_discharge)
                            for duration, net, ev in shape)
            # An issued reduction does not reduce observed import until its response arrives.
            projected += max(0.0, o.ev_power_kw - requested_ev * scale) * delay_h
            return projected

        low, high = 0.0, 1.0
        if imports(1.0) > budget + 1e-9:
            for _ in range(35):
                middle = (low + high) / 2
                if imports(middle) <= budget:
                    low = middle
                else:
                    high = middle
        else:
            low = 1.0
        ev_limit = max(0.0, requested_ev * low)
        tail_h = max(0.0, (self.p.measurement_max_age_seconds + self.p.control_period_seconds) / 3600 - hours)
        if tail_h > 0:
            # A late pulse must also leave room for its delayed stop after the reset.
            next_net = o.house_kw - o.pv_ac_kw
            if plan is not None and position is not None:
                following = next((i for i in plan["intervals"][position:]
                                  if instant(i["start"]) <= end < instant(i["end"])), None)
                if following is not None:
                    next_net = max(next_net, following["house_kw"] - min(following["pv_ac_kw"], o.pv_ac_kw))
            next_house = max(0.0, next_net - confirmed_discharge)
            next_room = max(0.0, limit - next_house) * .25
            ev_limit = min(ev_limit, next_room / tail_h)
            low = min(low, ev_limit / requested_ev) if requested_ev > 0 else low
        grid_charge = (max(0.0, plan["flows"]["grid_store"][position])
                       if plan is not None and position is not None else 0.0)
        house_limit = min(max(0.0, o.house_kw - o.pv_ac_kw + grid_charge - confirmed_discharge),
                          max(0.0, budget / hours))
        import_limit = min(self.c.grid_connection_kw, house_limit + ev_limit)
        # Attribute only demand that remains beyond physical EV/ESS mitigation.
        direct_dc = min(self.c.ac_discharge_kw, o.pv_dc_kw * self.c.ac_discharge_efficiency)
        physical_support = min(self.c.ac_discharge_kw * hours,
                               (self.c.battery_discharge_kw * self.c.ac_discharge_efficiency + direct_dc) * hours,
                               max(0.0, o.ess_kwh - self.c.ess_min_kwh) * self.c.ac_discharge_efficiency
                               + direct_dc * hours)
        unavoidable = max(0.0, self.prefix_kwh + household_energy - physical_support - limit * .25)
        return PeakProjection(ev_limit, import_limit, ev_limit < requested_ev - 1e-7 or imports(0.0) > budget + 1e-9,
                              unavoidable, self.prefix_kwh)
