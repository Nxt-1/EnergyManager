"""Conservative feasible starting point for the joint solve, never published directly."""

from __future__ import annotations

from zoneinfo import ZoneInfo
from datetime import timedelta

from .optimization import JointModel


def seed(model: JointModel, peak_limit_kw: float | None = None) -> list[float] | None:
    s, m = model.snapshot, model.linear
    c, p, o = s.capabilities, s.policy, s.observation
    n = len(s.intervals)
    values = [0.0] * len(m.lower)
    final_rounding_kwh = (
        min(c.phases) * c.voltage / 1000 * c.ev_efficiency
        * max(i.hours for i in s.intervals) * c.minimum_current_a
    )

    def put(name: str, t: int, value: float) -> None:
        values[m.variables[name][t]] = value

    ev, solar, grid = o.ev_kwh, o.ess_kwh - c.ess_min_kwh - o.ess_grid_kwh, o.ess_grid_kwh
    non_grid = grid_ev = 0.0
    last_power = o.ev_power_kw
    previous_on = o.ev_power_kw > 0.1
    previous_phase = o.ev_phases
    previous_active_at = s.intervals[0].start - timedelta(seconds=c.phase_dwell_seconds)
    for t, interval in enumerate(s.intervals):
        put("ev_energy", t, ev)
        put("ess_solar", t, solar)
        put("ess_grid", t, grid)
        put("non_grid_cumulative", t, non_grid)
        put("grid_cumulative", t, grid_ev)
        future = [g for g in s.goals if interval.start < g.deadline <= s.intervals[-1].end]
        next_deadline = min((g.deadline for g in future), default=interval.end)
        target = max(
            [0.0] + [model.service.get(g.id, g.target(c, p)) for g in future if g.deadline == next_deadline]
        )
        allowed = max(p.billing_floor_kw, o.monthly_peak_kw, p.automatic_peak_kw if future else 0)
        allowed = max(
            [allowed]
            + [
                g.approved_peak_kw or 0
                for g in future
                if g.approval_state == "granted" and g.approval_revision == g.revision
            ]
        )
        if peak_limit_kw is not None:
            allowed = min(allowed, peak_limit_kw)
        available_pv = interval.pv_ac_kw + min(
            c.ac_discharge_kw, interval.pv_dc_kw * c.ac_discharge_efficiency
        )
        surplus = max(0.0, available_pv - interval.house_kw)
        grid_house = max(0.0, interval.house_kw - available_pv)
        power = 0.0
        amps = 0
        charge_target = (
            max(target, p.normal_soc_percent / 100 * c.ev_capacity_kwh) if model.optional else target
        )
        later_solar = sum(
            max(0.0, i.pv_ac_kw + min(c.ac_discharge_kw, i.pv_dc_kw * c.ac_discharge_efficiency) - i.house_kw)
            * i.hours
            * c.ev_efficiency
            for i in s.intervals[t + 1 :]
            if i.available and i.end <= next_deadline
        )
        use_grid = ev < target - 1e-7 and later_solar < target - ev - 1e-7
        phases = 1
        if interval.available and ev < charge_target - 1e-7:
            headroom = surplus + (max(0.0, allowed - grid_house) if use_grid else 0)
            phases = (
                3
                if 3 in c.phases
                and headroom >= c.minimum_current_a * 3 * c.voltage / 1000
                and (1 not in c.phases or headroom > c.maximum_current_a * c.voltage / 1000)
                else 1
            )
            if (
                1 in c.phases
                and charge_target - ev
                < c.minimum_current_a * 3 * c.voltage / 1000 * interval.hours * c.ev_efficiency
            ):
                phases = 1
            if (
                phases != previous_phase
                and (interval.start - previous_active_at).total_seconds() < c.phase_dwell_seconds
            ):
                phases = previous_phase
            amps = min(c.maximum_current_a, int((headroom + 1e-8) * 1000 / (c.voltage * phases)))
            if amps >= c.minimum_current_a and phases in c.phases:
                # Smallest integer-current final interval rather than excessive overdelivery.
                active_target = target if use_grid else charge_target
                needed = (
                    (active_target - ev) / (interval.hours * c.ev_efficiency) * 1000 / (c.voltage * phases)
                )
                if use_grid and needed > amps and 0 < needed - amps < c.minimum_current_a:
                    amps = max(c.minimum_current_a, int(needed + 0.999999) - c.minimum_current_a)
                maximum_final = (
                    max(c.minimum_current_a, int(needed + 0.999999)) if use_grid else int(needed + 1e-8)
                )
                amps = min(amps, max(0, maximum_final))
                if use_grid:
                    # A locked three-phase mode may need to pause before its final small increment.
                    energy_per_amp = interval.hours * c.ev_efficiency * phases * c.voltage / 1000
                    final_current_limit = int((target - ev + final_rounding_kwh + 1e-8) / energy_per_amp)
                    amps = min(amps, final_current_limit)
                power = amps * phases * c.voltage / 1000 if amps >= c.minimum_current_a else 0
        if s.hold_until and interval.start < s.hold_until:
            phases = s.hold_phases
            amps = round(s.hold_ev_kw * 1000 / (phases * c.voltage)) if interval.available else 0
            power = amps * phases * c.voltage / 1000
        if (interval.start - s.intervals[0].start).total_seconds() < 15 and phases != o.ev_phases:
            amps = 0
            power = 0
        dc_invert = min(
            interval.pv_dc_kw,
            c.ac_discharge_kw / c.ac_discharge_efficiency,
            max(0, interval.house_kw + power - interval.pv_ac_kw) / c.ac_discharge_efficiency,
        )
        pv_available = interval.pv_ac_kw + dc_invert * c.ac_discharge_efficiency
        solar_house = min(pv_available, interval.house_kw)
        pv_ev = min(max(0, pv_available - solar_house), power)
        direct = power - pv_ev
        remaining_house = interval.house_kw - solar_house
        solar_dis_house = min(
            remaining_house,
            max(0, c.ac_discharge_kw - dc_invert * c.ac_discharge_efficiency),
            solar * c.ac_discharge_efficiency / interval.hours,
            c.battery_discharge_kw * c.ac_discharge_efficiency,
        )
        remaining_house -= solar_dis_house
        grid_house = remaining_house
        surplus = max(0, pv_available - solar_house - pv_ev)
        storage_headroom = max(0, c.ess_capacity_kwh - c.ess_min_kwh - solar - grid)
        dc_store = min(
            max(0, interval.pv_dc_kw - dc_invert),
            c.dc_charge_kw,
            c.battery_charge_kw / c.dc_efficiency,
            storage_headroom / interval.hours / c.dc_efficiency,
        )
        if solar_dis_house > 1e-8:
            dc_store = 0
        ac_store = min(
            surplus,
            c.ac_charge_kw,
            max(0, c.battery_charge_kw - dc_store * c.dc_efficiency) / c.ac_charge_efficiency,
            max(0, storage_headroom / interval.hours - dc_store * c.dc_efficiency) / c.ac_charge_efficiency,
        )
        if dc_invert > 1e-8 or solar_dis_house > 1e-8:
            ac_store = 0
        surplus -= ac_store
        put("pv_house", t, solar_house)
        put("grid_house", t, grid_house)
        put("pv_ev", t, pv_ev)
        put("grid_ev", t, direct)
        put("dc_invert", t, dc_invert)
        put("dc_store", t, dc_store)
        put("pv_store", t, ac_store)
        put("pv_store_mode", t, float(ac_store > 1e-8))
        put("solar_dis_house", t, solar_dis_house)
        put("battery_charge", t, float(dc_store + ac_store > 1e-8))
        put("converter_charge", t, float(ac_store > 1e-8))
        put("export", t, surplus if direct < 1e-8 and grid_house < 1e-8 else 0)
        put("curtail", t, surplus if direct >= 1e-8 or grid_house >= 1e-8 else 0)
        put("one", t, float(power > 0 and phases == 1))
        put("three", t, float(power > 0 and phases == 3))
        put("amps_one", t, amps if power and phases == 1 else 0)
        put("amps_three", t, amps if power and phases == 3 else 0)
        put("grid_direction", t, float(grid_house + direct > 1e-8))
        put("start", t, float(power > 0 and not previous_on))
        put("variation", t, abs(power - last_power))
        put(
            "phase_change",
            t,
            abs(float(power > 0 and phases == 3) - float(previous_on and previous_phase == 3)) if t else 0,
        )
        ev += power * interval.hours * c.ev_efficiency - interval.withdrawal_kwh
        non_grid += pv_ev * interval.hours * c.ev_efficiency
        grid_ev += direct * interval.hours * c.ev_efficiency
        solar += (
            dc_store * c.dc_efficiency
            + ac_store * c.ac_charge_efficiency
            - solar_dis_house / c.ac_discharge_efficiency
        ) * interval.hours
        if ev < -1e-8 or ev > c.ev_capacity_kwh + 1e-8:
            return None
        last_power, previous_on = power, power > 0
        if power > 0:
            previous_phase, previous_active_at = phases, interval.start
    for name, value in (
        ("ev_energy", ev),
        ("ess_solar", solar),
        ("ess_grid", grid),
        ("non_grid_cumulative", non_grid),
        ("grid_cumulative", grid_ev),
    ):
        put(name, n, value)
    deficits = []
    for goal in s.goals:
        if s.intervals[0].start <= goal.deadline <= s.intervals[-1].end:
            k = s.checkpoint_index(goal.deadline)
            if not s.ev_known_at(k):
                continue
            desired = model.service.get(goal.id, goal.target(c, p))
            delivered = values[m.variables["ev_energy"][k]]
            if goal.id in model.goal_slack:
                # An unmet original goal is valid input to the service maximization.
                values[model.goal_slack[goal.id]] = max(0, desired - delivered)
                desired = min(desired, delivered)
            elif delivered < desired - 1e-6:
                model.seed_issue = f"Goal {goal.id}: {delivered} < {desired}"
                return None
            deficit = desired + sum(i.withdrawal_kwh for i in s.intervals[:k]) - o.ev_kwh
            deficits.append(deficit - values[m.variables["non_grid_cumulative"][k]])
    witness = (
        max(range(len(deficits)), key=lambda i: deficits[i]) + 1 if deficits and max(deficits) > 1e-6 else 0
    )
    put("causal_witness", witness, 1)
    for month, index in model.months.items():
        peak = m.lower[index]
        for key, slots in model.quarters.items():
            at = s.intervals[slots[0]].start
            if at.astimezone(ZoneInfo(p.timezone)).strftime("%Y-%m") != month:
                continue
            energy = sum(
                (values[m.variables["grid_ev"][t]] + values[m.variables["grid_house"][t]])
                * s.intervals[t].hours
                for t in slots
            )
            if slots[0] == 0:
                energy += o.quarter_import_kwh
            peak = max(peak, energy * 4)
            for resource in ("grid_ev", "grid_store"):
                put(
                    f"quarter_control_{resource}_{key}",
                    0,
                    float(any(values[m.variables[resource][t]] > 1e-8 for t in slots)),
                )
        values[index] = peak
    values = model.canonical_values(values)
    # Check every row/bound independently before handing this to HiGHS.
    for index, value in enumerate(values):
        if value < m.lower[index] - 1e-6 or value > m.upper[index] + 1e-6:
            model.seed_issue = f"Variable {index} outside bounds: {value}"
            return None
    for row in range(len(m.row_lower)):
        total = sum(values[m.indices[k]] * m.values[k] for k in range(m.starts[row], m.starts[row + 1]))
        if not m.row_lower[row] - 1e-6 <= total <= m.row_upper[row] + 1e-6:
            model.seed_issue = f"Row {row}: {total} outside [{m.row_lower[row]}, {m.row_upper[row]}]"
            return None
    return values
