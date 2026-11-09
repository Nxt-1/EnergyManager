"""Independent arithmetic audits; this module does not import the model builder."""

from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import math

from .domain import Snapshot
from .execution import PHASE_SWITCH_SECONDS, RESTART_SECONDS
from .appliance_plan import resolved_power, selected_start

TOL = 2e-5


def accounting(
    s: Snapshot, flows: dict[str, list[float]], start: int = 0, end: int | None = None
) -> dict[str, float]:
    end = len(s.intervals) if end is None else end
    p, o = s.policy, s.observation
    imports = exports = 0.0
    quarters: dict[str, float] = defaultdict(float)
    for t in range(start, end):
        interval = s.intervals[t]
        imp = sum(flows[name][t] for name in ("grid_ev", "grid_house", "grid_store")) * interval.hours
        imports += imp
        exports += flows["export"][t] * interval.hours
        quarter = interval.start.replace(minute=interval.start.minute // 15 * 15, second=0, microsecond=0)
        quarters[quarter.isoformat()] += imp
    if start == 0 and quarters:
        quarters[next(iter(quarters))] += o.quarter_import_kwh
    peaks: dict[str, float] = {}
    zone = ZoneInfo(p.timezone)
    initial_month = s.intervals[0].start.astimezone(zone).strftime("%Y-%m")
    for quarter_key, energy in quarters.items():
        month = datetime.fromisoformat(quarter_key).astimezone(zone).strftime("%Y-%m")
        baseline = (
            max(p.billing_floor_kw, o.monthly_peak_kw) if month == initial_month else p.billing_floor_kw
        )
        peaks[month] = max(peaks.get(month, baseline), energy * 4)
    capacity = sum(
        max(
            0.0,
            peak
            - (max(p.billing_floor_kw, o.monthly_peak_kw) if month == initial_month else p.billing_floor_kw),
        )
        * p.capacity_eur_kw_month
        for month, peak in peaks.items()
    )

    def stored(index: int) -> float:
        return (flows["ev_energy"][index] * p.ev_value_eur_kwh if s.ev_known_at(index) else 0) + (
            flows["ess_solar"][index] + flows["ess_grid"][index]
        ) * p.ess_value_eur_kwh

    bill = imports * p.import_eur_kwh - exports * p.export_eur_kwh + capacity
    return {
        "imports_kwh": imports,
        "exports_kwh": exports,
        "import_cost_eur": imports * p.import_eur_kwh,
        "export_income_eur": exports * p.export_eur_kwh,
        "capacity_cost_eur": capacity,
        "predicted_bill_eur": bill,
        "stored_start_eur": stored(start),
        "stored_end_eur": stored(end),
        "inventory_change_eur": stored(end) - stored(start),
        "comparison_eur": bill + stored(start) - stored(end),
        "peak_kw": max(peaks.values(), default=0),
    }


def validate(
    s: Snapshot, flows: dict[str, list[float]], service: dict[str, float] | None = None
) -> list[str]:
    c, p, o = s.capabilities, s.policy, s.observation
    try:
        dishwasher = resolved_power(s,flows)
    except (ValueError, KeyError, TypeError) as exc:
        return [str(exc)]
    errors: list[str] = []
    n = len(s.intervals)
    needed = (
        "ev_energy",
        "ess_solar",
        "ess_grid",
        "pv_ev",
        "pv_house",
        "pv_store",
        "grid_ev",
        "grid_house",
        "grid_store",
        "dc_store",
        "dc_invert",
        "export",
        "curtail",
        "solar_dis_ev",
        "solar_dis_house",
        "grid_dis_house",
        "one",
        "three",
        "amps_one",
        "amps_three",
    )
    for name in needed:
        values = flows.get(name, [])
        if len(values) != n + (name in ("ev_energy", "ess_solar", "ess_grid")) or any(
            not math.isfinite(value) or value < -TOL for value in values
        ):
            errors.append(f"Malformed trajectory: {name}")
    if s.appliance:
        actual = flows.get("dishwasher_power",[])
        if len(actual) != n or any(not math.isfinite(value) or abs(value-expected)>TOL for value,expected in zip(actual,dishwasher)):
            errors.append("Dishwasher curve/energy conservation")
    if errors:
        return errors

    def check(condition: bool, message: str) -> None:
        if not condition and len(errors) < 100:
            errors.append(message)

    def close(a: float, b: float) -> bool:
        return abs(a - b) <= TOL

    check(close(flows["ev_energy"][0], o.ev_kwh), "Initial EV state")
    check(close(flows["ess_solar"][0] + flows["ess_grid"][0], o.ess_kwh - c.ess_min_kwh), "Initial ESS state")
    check(close(flows["ess_grid"][0], o.ess_grid_kwh), "Initial provenance")
    source_prefix = [0.0]
    charged_prefix = [0.0]
    withdrawal_prefix = [0.0]
    interval_starts = [i.start for i in s.intervals]
    goal_indices = {g.deadline: s.checkpoint_index(g.deadline) for g in s.goals}
    grid_total = 0.0
    execution_phase = s.execution["initial_phase"] if s.execution else o.ev_phases
    execution_on = o.ev_power_kw > .1
    execution_waits: list[tuple[datetime, datetime]] = []
    quarters: dict[datetime, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
    for t, interval in enumerate(s.intervals):
        f = {name: flows[name][t] for name in needed}
        ev_power = f["pv_ev"] + f["grid_ev"] + f["solar_dis_ev"]
        ac_in = f["pv_store"] + f["grid_store"]
        ac_out = (
            f["solar_dis_ev"]
            + f["solar_dis_house"]
            + f["grid_dis_house"]
            + f["dc_invert"] * c.ac_discharge_efficiency
        )
        check(ac_in <= c.ac_charge_kw + TOL and ac_out <= c.ac_discharge_kw + TOL, f"Converter limit {t}")
        check(ac_in < TOL or ac_out < TOL, f"Converter direction {t}")
        check(f["pv_store"] < TOL or f["grid_house"] < TOL, f"AC ESS source relabelling {t}")
        if s.appliance and f["grid_store"]>TOL:
            support = any(interval.start<future.start<=interval.start+timedelta(hours=24)
                          and future.house_kw+dishwasher[j]-future.pv_ac_kw>max(p.billing_floor_kw,o.monthly_peak_kw if future.start.astimezone(ZoneInfo(p.timezone)).strftime("%Y-%m")==s.intervals[0].start.astimezone(ZoneInfo(p.timezone)).strftime("%Y-%m") else 0)
                          for j,future in enumerate(s.intervals[t:],t))
            support = support or any(interval.start<g.deadline<=interval.start+timedelta(hours=24) for g in s.goals)
            check(support,"ESS precharge lacks selected dishwasher/household support within 24 hours")
        charge = ac_in * c.ac_charge_efficiency + f["dc_store"] * c.dc_efficiency
        discharge = (
            f["solar_dis_ev"] + f["solar_dis_house"] + f["grid_dis_house"]
        ) / c.ac_discharge_efficiency
        check(
            charge <= c.battery_charge_kw + TOL and discharge <= c.battery_discharge_kw + TOL,
            f"Battery rate {t}",
        )
        check(charge < TOL or discharge < TOL, f"Battery cycling {t}")
        check(
            f["dc_store"] <= c.dc_charge_kw + TOL
            and f["dc_store"] + f["dc_invert"] <= interval.pv_dc_kw + TOL,
            f"DC solar {t}",
        )
        check(
            close(
                f["pv_ev"] + f["pv_house"] + f["pv_store"] + f["export"] + f["curtail"],
                interval.pv_ac_kw + f["dc_invert"] * c.ac_discharge_efficiency,
            ),
            f"Solar conservation {t}",
        )
        check(
            close(
                f["pv_house"] + f["grid_house"] + f["solar_dis_house"] + f["grid_dis_house"],
                interval.house_kw+dishwasher[t],
            ),
            f"House conservation {t}",
        )
        check(
            close(
                flows["ev_energy"][t + 1],
                f["ev_energy"] + ev_power * interval.hours * c.ev_efficiency - interval.withdrawal_kwh,
            ),
            f"EV energy conservation {t}",
        )
        solar_next = (
            f["ess_solar"]
            + (
                f["pv_store"] * c.ac_charge_efficiency
                + f["dc_store"] * c.dc_efficiency
                - (f["solar_dis_ev"] + f["solar_dis_house"]) / c.ac_discharge_efficiency
            )
            * interval.hours
        )
        grid_next = (
            f["ess_grid"]
            + (f["grid_store"] * c.ac_charge_efficiency - f["grid_dis_house"] / c.ac_discharge_efficiency)
            * interval.hours
        )
        check(
            close(solar_next, flows["ess_solar"][t + 1]) and close(grid_next, flows["ess_grid"][t + 1]),
            f"ESS provenance {t}",
        )
        check(ev_power < TOL or interval.available, f"Away charging {t}")
        amps1, amps3 = f["amps_one"], f["amps_three"]
        for amps, phase in ((amps1, 1), (amps3, 3)):
            check(
                amps < TOL
                or phase in c.phases
                and c.minimum_current_a - TOL <= amps <= c.maximum_current_a + TOL
                and abs(amps - round(amps)) < TOL,
                f"Unsupported current {t}",
            )
        check(amps1 < TOL or amps3 < TOL, f"Simultaneous EV modes {t}")
        fraction = 1.0
        if s.execution is not None:
            check(close(f["one"], float(amps1 > TOL)) and close(f["three"], float(amps3 > TOL)),
                  f"EV requested mode/current {t}")
            on = amps1 + amps3 > TOL
            phase = 3 if amps3 > TOL else 1 if on else execution_phase
            wait = 0.0
            if on and phase != execution_phase:
                wait = PHASE_SWITCH_SECONDS
            elif on and not execution_on:
                prior_off = s.intervals[t - 1].hours * 3600 if t else RESTART_SECONDS
                wait = max(0, RESTART_SECONDS - prior_off)
            if wait:
                check(not execution_waits or interval.start >= execution_waits[-1][1],
                      f"Overlapping EV transitions {t}")
                execution_waits.append((interval.start, interval.start + timedelta(seconds=wait)))
            lost = sum(max(0.0, (min(interval.end, end) - max(interval.start, start)).total_seconds())
                       for start, end in execution_waits if end > interval.start)
            fraction = max(0.0, 1 - lost / (interval.hours * 3600))
            check(not lost or on, f"EV transition request interrupted before readiness {t}")
            execution_phase, execution_on = phase, on
            commitment = s.ev_commitment(t)
            if commitment is not None:
                expected_kw, expected_phase = commitment
                check(close((amps1 + 3 * amps3) * c.voltage / 1000, expected_kw)
                      and (not on or phase == expected_phase), f"Frozen EV execution commitment {t}")
            if fraction > TOL:
                check(f["grid_ev"] / fraction + f["grid_house"] + f["grid_store"] <= c.grid_connection_kw + TOL,
                      f"Instantaneous EV grid supply {t}")
                check(f["pv_ev"] / fraction + f["pv_house"] + f["pv_store"]
                      <= interval.pv_ac_kw + f["dc_invert"] * c.ac_discharge_efficiency + TOL,
                      f"Instantaneous EV solar supply {t}")
                check(f["solar_dis_ev"] / fraction + f["solar_dis_house"] + f["grid_dis_house"]
                      + f["dc_invert"] * c.ac_discharge_efficiency <= c.ac_discharge_kw + TOL,
                      f"Instantaneous EV converter supply {t}")
                check((f["solar_dis_ev"] / fraction + f["solar_dis_house"] + f["grid_dis_house"])
                      / c.ac_discharge_efficiency <= c.battery_discharge_kw + TOL,
                      f"Instantaneous EV battery supply {t}")
        check(close(ev_power, (amps1 + 3 * amps3) * c.voltage / 1000 * fraction), f"EV mode power {t}")
        imp = f["grid_ev"] + f["grid_house"] + f["grid_store"]
        check(
            imp <= c.grid_connection_kw + TOL and (imp < TOL or f["export"] < TOL),
            f"Grid direction/limit {t}",
        )
        quarter = interval.start.replace(minute=interval.start.minute // 15 * 15, second=0, microsecond=0)
        quarters[quarter][0] += imp * interval.hours
        quarters[quarter][1] += f["grid_ev"] * interval.hours
        quarters[quarter][2] += f["grid_store"] * interval.hours
        source_prefix.append(
            source_prefix[-1] + (f["pv_ev"] + f["solar_dis_ev"]) * interval.hours * c.ev_efficiency
        )
        charged_prefix.append(charged_prefix[-1] + ev_power * interval.hours * c.ev_efficiency)
        withdrawal_prefix.append(withdrawal_prefix[-1] + interval.withdrawal_kwh)
        grid_total += f["grid_ev"] * interval.hours * c.ev_efficiency
    for t in range(n + 1):
        check(flows["ev_energy"][t] <= c.ev_capacity_kwh + TOL, f"EV capacity {t}")
        check(
            flows["ess_solar"][t] + flows["ess_grid"][t] <= c.ess_capacity_kwh - c.ess_min_kwh + TOL,
            f"ESS capacity {t}",
        )
    causal_deficit = 0.0
    for goal in s.goals:
        if not s.intervals[0].start <= goal.deadline <= s.intervals[-1].end:
            continue
        k = goal_indices[goal.deadline]
        if not s.ev_known_at(k):
            continue
        target = (service or {}).get(goal.id, goal.target(c, p))
        check(flows["ev_energy"][k] + TOL >= target, f"Required outcome {goal.id}")
        withdrawals = withdrawal_prefix[k]
        causal_deficit = max(causal_deficit, target + withdrawals - o.ev_kwh - source_prefix[k])
    rounding = (
        min(c.phases)
        * c.voltage
        / 1000
        * c.ev_efficiency
        * max(i.hours for i in s.intervals)
        * c.minimum_current_a
    )
    check(
        grid_total <= max(0, causal_deficit) + (rounding if causal_deficit > TOL else 0) + TOL,
        "Unnecessary direct EV grid purchase",
    )
    first_quarter = next(iter(quarters))
    quarters[first_quarter][0] += o.quarter_import_kwh
    initial_month = s.intervals[0].start.astimezone(ZoneInfo(p.timezone)).strftime("%Y-%m")
    for at, (energy, ev_purchase, ess_purchase) in quarters.items():
        month = at.astimezone(ZoneInfo(p.timezone)).strftime("%Y-%m")
        baseline = (
            max(p.billing_floor_kw, o.monthly_peak_kw) if month == initial_month else p.billing_floor_kw
        )
        eligible = [g for g in s.goals if at < g.deadline and (g.earliest is None or at >= g.earliest)]
        automatic = max(baseline, p.automatic_peak_kw)
        if s.appliance and s.appliance.get("points") and not s.appliance.get("started_at"):
            beginning = selected_start(s,flows)
            if beginning and beginning < at+timedelta(minutes=15) and beginning+timedelta(seconds=s.appliance["curve_seconds"])>at:
                check(energy*4 <= max(automatic,s.appliance.get("approved_peak_kw") or 0)+TOL,"Dishwasher peak permission")
        charged = charged_prefix[bisect_left(interval_starts, at + timedelta(minutes=15))]
        ev_limits = [automatic if eligible else baseline]
        for g in eligible:
            deficit = (
                g.target(c, p)
                + withdrawal_prefix[goal_indices[g.deadline]]
                - o.ev_kwh
            )
            if (
                g.approval_state == "granted"
                and g.approval_revision == g.revision
                and deficit > 0
                and charged <= deficit + rounding + TOL
            ):
                ev_limits.append(g.approved_peak_kw or baseline)
        dishwasher_limit = None
        if s.appliance and s.appliance.get("points") and s.appliance.get("approved_peak_kw"):
            beginning = selected_start(s,flows)
            if beginning and beginning < at+timedelta(minutes=15) and beginning+timedelta(seconds=s.appliance["curve_seconds"])>at:
                dishwasher_limit = s.appliance["approved_peak_kw"]
                ev_limits.append(dishwasher_limit)
        ess_limits = [automatic] + ([dishwasher_limit] if dishwasher_limit is not None else []) + [
            g.peak_kw
            for g in s.peak_permissions
            if g.state == "granted"
            and g.forecast_id == s.forecast_id
            and at < g.deadline <= at + timedelta(hours=24)
        ]
        check(ev_purchase < TOL or energy * 4 <= max(ev_limits) + TOL,
              f"Unapproved EV peak {at}: {energy * 4000:.0f} W quarter-hour average exceeds {max(ev_limits) * 1000:.0f} W allowance")
        check(ess_purchase < TOL or energy * 4 <= max(ess_limits) + TOL,
              f"Unapproved ESS peak {at}: {energy * 4000:.0f} W quarter-hour average exceeds {max(ess_limits) * 1000:.0f} W allowance")
    return errors


def rolling_comparison_errors(
    s: Snapshot, reference: dict[str, list[float]], candidate: dict[str, list[float]]
) -> list[str]:
    """Audit interacting changes together at every charging origin, across midnight."""
    errors: list[str] = []
    for start, interval in enumerate(s.intervals):
        extra_solar_ev = (
            candidate["pv_ev"][start]
            + candidate["solar_dis_ev"][start]
            - reference["pv_ev"][start]
            - reference["solar_dis_ev"][start]
        )
        extra_grid_store = candidate["grid_store"][start] - reference["grid_store"][start]
        if extra_solar_ev < TOL and extra_grid_store < TOL:
            continue
        boundary = interval.start + timedelta(hours=24)
        end = next(
            (t for t in range(start + 1, len(s.intervals)) if s.intervals[t].start >= boundary),
            len(s.intervals),
        )
        ref = accounting(s, reference, start, end)
        proposed = accounting(s, candidate, start, end)
        if proposed["comparison_eur"] > ref["comparison_eur"] + TOL:
            errors.append(f"24-hour combined comparison worsens at {interval.start.isoformat()}")
        if extra_grid_store > TOL and (
            proposed["peak_kw"] >= ref["peak_kw"] - TOL
            or proposed["comparison_eur"] >= ref["comparison_eur"] - TOL
        ):
            errors.append(
                f"ESS purchase lacks an economical avoided peak within 24 hours at {interval.start.isoformat()}"
            )
    return errors
