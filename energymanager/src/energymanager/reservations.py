"""Forecast-peak and EV allocations, distinct from routine stored inventory."""

from __future__ import annotations

from collections import defaultdict
from zoneinfo import ZoneInfo

from .domain import Snapshot


def reservations(snapshot: Snapshot, flows: dict[str, list[float]]) -> list[dict[str, float]]:
    s, c, p, o = snapshot, snapshot.capabilities, snapshot.policy, snapshot.observation
    n = len(s.intervals)
    protected_house = [0.0] * n
    quarters: dict[str, list[int]] = defaultdict(list)
    zone = ZoneInfo(p.timezone)
    initial_month = s.intervals[0].start.astimezone(zone).strftime("%Y-%m")
    for t, i in enumerate(s.intervals):
        key = i.start.replace(minute=i.start.minute // 15 * 15, second=0, microsecond=0).isoformat()
        quarters[key].append(t)
    for slots in quarters.values():
        month = s.intervals[slots[0]].start.astimezone(zone).strftime("%Y-%m")
        baseline = (
            max(p.billing_floor_kw, o.monthly_peak_kw) if month == initial_month else p.billing_floor_kw
        )
        without_storage = sum(
            (flows["grid_house"][t] + flows["solar_dis_house"][t] + flows["grid_dis_house"][t])
            * s.intervals[t].hours
            for t in slots
        )
        supplied = sum(
            (flows["solar_dis_house"][t] + flows["grid_dis_house"][t]) * s.intervals[t].hours for t in slots
        )
        prefix = o.quarter_import_kwh if slots[0] == 0 else 0
        needed = max(0, without_storage + prefix - baseline * 0.25)
        fraction = min(1, needed / supplied) if supplied > 1e-9 else 0
        for t in slots:
            protected_house[t] = fraction
    rows = [{"solar_ev_kwh": 0.0, "solar_house_kwh": 0.0, "grid_house_kwh": 0.0} for _ in range(n + 1)]
    for t in range(n - 1, -1, -1):
        dt = s.intervals[t].hours
        solar_in = (
            flows["pv_store"][t] * c.ac_charge_efficiency + flows["dc_store"][t] * c.dc_efficiency
        ) * dt
        ev_need = rows[t + 1]["solar_ev_kwh"] + flows["solar_dis_ev"][t] / c.ac_discharge_efficiency * dt
        house_need = (
            rows[t + 1]["solar_house_kwh"]
            + flows["solar_dis_house"][t] / c.ac_discharge_efficiency * dt * protected_house[t]
        )
        # Shared replenishment is counted once, protecting EV work before bill preferences.
        ev_replenished = min(ev_need, solar_in)
        rows[t]["solar_ev_kwh"] = max(0, ev_need - ev_replenished)
        rows[t]["solar_house_kwh"] = max(0, house_need - (solar_in - ev_replenished))
        rows[t]["grid_house_kwh"] = max(
            0,
            rows[t + 1]["grid_house_kwh"]
            + flows["grid_dis_house"][t] / c.ac_discharge_efficiency * dt * protected_house[t]
            - flows["grid_store"][t] * c.ac_charge_efficiency * dt,
        )
    return rows
