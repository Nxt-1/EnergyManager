"""Sparse joint EV/ESS MILP. All powers are kW; storage and flows use kWh."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from datetime import timedelta
from time import monotonic
from typing import Any
from zoneinfo import ZoneInfo

import highspy
import numpy as np

from .domain import Snapshot

INF = highspy.kHighsInf


class LinearModel:
    """Collect sparse rows once rather than making thousands of Python solver calls."""

    def __init__(self) -> None:
        self.lower: list[float] = []
        self.upper: list[float] = []
        self.integer: list[int] = []
        self.cost: list[float] = []
        self.row_lower: list[float] = []
        self.row_upper: list[float] = []
        self.starts: list[int] = [0]
        self.indices: list[int] = []
        self.values: list[float] = []
        self.variables: dict[str, list[int]] = {}

    def variable(
        self, name: str, count: int, upper: float = INF, lower: float = 0, integer: bool = False
    ) -> list[int]:
        indexes = list(range(len(self.lower), len(self.lower) + count))
        self.variables[name] = indexes
        self.lower.extend([lower] * count)
        self.upper.extend([upper] * count)
        self.cost.extend([0.0] * count)
        if integer:
            self.integer.extend(indexes)
        return indexes

    def row(self, terms: Sequence[tuple[int, float]], lower: float = -INF, upper: float = INF) -> None:
        combined: dict[int, float] = defaultdict(float)
        for index, coefficient in terms:
            combined[index] += coefficient
        for index, coefficient in combined.items():
            if abs(coefficient) > 1e-14:
                self.indices.append(index)
                self.values.append(coefficient)
        self.starts.append(len(self.indices))
        self.row_lower.append(lower)
        self.row_upper.append(upper)

    def equality(self, terms: Sequence[tuple[int, float]], value: float = 0) -> None:
        self.row(terms, value, value)

    def solver(self) -> highspy.Highs:
        model = highspy.Highs()
        for name, value in (
            ("output_flag", False),
            ("threads", 1),
            ("random_seed", 7),
            ("mip_rel_gap", 0.0001),
            ("mip_feasibility_tolerance", 1e-7),
        ):
            model.setOptionValue(name, value)
        count = len(self.lower)
        model.addCols(
            count,
            np.asarray(self.cost),
            np.asarray(self.lower),
            np.asarray(self.upper),
            0,
            np.zeros(count + 1, dtype=np.int32),
            np.array([], dtype=np.int32),
            np.array([]),
        )
        if self.integer:
            model.changeColsIntegrality(
                len(self.integer),
                np.asarray(self.integer, dtype=np.int32),
                np.ones(len(self.integer), dtype=np.uint8),
            )
        model.addRows(
            len(self.row_lower),
            np.asarray(self.row_lower),
            np.asarray(self.row_upper),
            len(self.values),
            np.asarray(self.starts, dtype=np.int32),
            np.asarray(self.indices, dtype=np.int32),
            np.asarray(self.values),
        )
        return model


class JointModel:
    def __init__(
        self,
        snapshot: Snapshot,
        *,
        optional: bool = False,
        ceilings: list[float] | None = None,
        grid_ess: bool = False,
        service: dict[str, float] | None = None,
        relaxed_service: bool = False,
        ev_total_limit: float | None = None,
        tight_ceilings: bool = False,
    ) -> None:
        self.snapshot = snapshot
        self.linear = LinearModel()
        self.optional = optional
        self.seed_issue: str | None = None
        self.service = service or {}
        self.relaxed_service = relaxed_service
        self.tight_ceilings = tight_ceilings
        self.ceilings = ceilings
        self.goal_slack: dict[str, int] = {}
        self.quarters: dict[str, list[int]] = defaultdict(list)
        self.months: dict[str, int] = {}
        self.rolling_metadata: dict[int, tuple[int, int, list[tuple[list[int], float]]]] = {}
        self.build(ceilings, grid_ess, ev_total_limit)

    def build(self, ceilings: list[float] | None, grid_ess: bool, ev_total_limit: float | None) -> None:
        s, m = self.snapshot, self.linear
        c, p, o = s.capabilities, s.policy, s.observation
        n = len(s.intervals)
        # Explicit solar allocation includes DC PV routed directly through the inverter.
        for name in (
            "pv_ev",
            "pv_house",
            "pv_store",
            "export",
            "curtail",
            "grid_ev",
            "grid_house",
            "grid_store",
            "solar_dis_ev",
            "solar_dis_house",
            "grid_dis_house",
            "dc_store",
            "dc_invert",
        ):
            m.variable(name, n, c.grid_connection_kw + c.dc_charge_kw)
        ev = m.variable("ev_energy", n + 1, c.ev_capacity_kwh)
        solar = m.variable("ess_solar", n + 1, c.ess_capacity_kwh - c.ess_min_kwh)
        grid = m.variable("ess_grid", n + 1, c.ess_capacity_kwh - c.ess_min_kwh)
        for name in (
            "one",
            "three",
            "battery_charge",
            "converter_charge",
            "grid_direction",
            "pv_store_mode",
            "start",
        ):
            m.variable(name, n, 1, integer=name != "start")
        for name in ("amps_one", "amps_three"):
            m.variable(name, n, c.maximum_current_a, integer=True)
        m.variable("variation", n, c.voltage * 3 * c.maximum_current_a / 1000)
        m.variable("phase_change", n, 1)
        m.variable("non_grid_cumulative", n + 1)
        m.variable("grid_cumulative", n + 1)
        v = m.variables
        m.equality([(ev[0], 1)], o.ev_kwh)
        m.equality([(solar[0], 1)], o.ess_kwh - c.ess_min_kwh - o.ess_grid_kwh)
        m.equality([(grid[0], 1)], o.ess_grid_kwh)
        m.equality([(v["non_grid_cumulative"][0], 1)])
        m.equality([(v["grid_cumulative"][0], 1)])
        self.economic: dict[int, float] = defaultdict(float)
        self.cash: dict[int, float] = defaultdict(float)
        self.operations: dict[int, float] = defaultdict(float)
        total_withdrawal = 0.0
        for t, interval in enumerate(s.intervals):
            dt = interval.hours

            def get(name: str) -> int:
                return v[name][t]

            power_terms = [(get("amps_one"), c.voltage / 1000), (get("amps_three"), c.voltage * 3 / 1000)]
            charge_terms = [(get(name), 1) for name in ("pv_ev", "grid_ev", "solar_dis_ev")]
            m.equality(charge_terms + [(index, -coef) for index, coef in power_terms])
            for phase, phase_allowed in (("one", 1 in c.phases), ("three", 3 in c.phases)):
                phase_active, amps = get(phase), get(f"amps_{phase}")
                m.row([(amps, 1), (phase_active, -c.maximum_current_a)], upper=0)
                m.row([(amps, 1), (phase_active, -c.minimum_current_a)], lower=0)
                if not phase_allowed or not interval.available:
                    m.upper[phase_active] = 0
                if (interval.start - s.intervals[0].start).total_seconds() < 15 and (phase == "three") != (
                    o.ev_phases == 3
                ):
                    m.upper[phase_active] = 0
            m.row([(get("one"), 1), (get("three"), 1)], upper=1)
            if s.hold_until and interval.start < s.hold_until:
                phase = "three" if s.hold_phases == 3 else "one"
                amps = round(s.hold_ev_kw * 1000 / (s.hold_phases * c.voltage)) if interval.available else 0
                for mode in ("one", "three"):
                    hold_active = float(amps > 0 and mode == phase)
                    m.equality([(get(mode), 1)], hold_active)
                    m.equality([(get(f"amps_{mode}"), 1)], amps if hold_active else 0)
            # The converter direction is separate from net battery direction.
            ac_charge = [(get("pv_store"), 1), (get("grid_store"), 1)]
            battery_dis = [
                (get(name), 1 / c.ac_discharge_efficiency)
                for name in ("solar_dis_ev", "solar_dis_house", "grid_dis_house")
            ]
            converter_out: list[tuple[int, float]] = [
                (get(name), 1) for name in ("solar_dis_ev", "solar_dis_house", "grid_dis_house")
            ]
            converter_out.append((get("dc_invert"), c.ac_discharge_efficiency))
            m.row(ac_charge + [(get("converter_charge"), -c.ac_charge_kw)], upper=0)
            m.row(converter_out + [(get("converter_charge"), c.ac_discharge_kw)], upper=c.ac_discharge_kw)
            m.row([(get("dc_store"), 1), (get("dc_invert"), 1)], upper=interval.pv_dc_kw)
            m.upper[get("dc_store")] = c.dc_charge_kw
            m.row(
                [(get("dc_store"), c.dc_efficiency)]
                + [(index, coef * c.ac_charge_efficiency) for index, coef in ac_charge]
                + [(get("battery_charge"), -c.battery_charge_kw)],
                upper=0,
            )
            m.row(
                battery_dis + [(get("battery_charge"), c.battery_discharge_kw)], upper=c.battery_discharge_kw
            )
            m.row([(solar[t], 1), (grid[t], 1)], upper=c.ess_capacity_kwh - c.ess_min_kwh)
            m.equality(
                [
                    (solar[t + 1], 1),
                    (solar[t], -1),
                    (get("pv_store"), -dt * c.ac_charge_efficiency),
                    (get("dc_store"), -dt * c.dc_efficiency),
                    (get("solar_dis_ev"), dt / c.ac_discharge_efficiency),
                    (get("solar_dis_house"), dt / c.ac_discharge_efficiency),
                ]
            )
            m.equality(
                [
                    (grid[t + 1], 1),
                    (grid[t], -1),
                    (get("grid_store"), -dt * c.ac_charge_efficiency),
                    (get("grid_dis_house"), dt / c.ac_discharge_efficiency),
                ]
            )
            m.equality(
                [(get(name), 1) for name in ("pv_ev", "pv_house", "pv_store", "export", "curtail")]
                + [(get("dc_invert"), -c.ac_discharge_efficiency)],
                interval.pv_ac_kw,
            )
            # Canonical AC provenance: household imports cannot hide nominally solar ESS precharging.
            m.row([(get("pv_store"), 1), (get("pv_store_mode"), -c.ac_charge_kw)], upper=0)
            m.row(
                [(get("grid_house"), 1), (get("pv_store_mode"), interval.house_kw)], upper=interval.house_kw
            )
            m.equality(
                [(get(name), 1) for name in ("pv_house", "grid_house", "solar_dis_house", "grid_dis_house")],
                interval.house_kw,
            )
            m.equality(
                [(ev[t + 1], 1), (ev[t], -1)]
                + [(index, -coef * dt * c.ev_efficiency) for index, coef in charge_terms],
                -interval.withdrawal_kwh,
            )
            total_withdrawal += interval.withdrawal_kwh
            m.equality(
                [
                    (v["non_grid_cumulative"][t + 1], 1),
                    (v["non_grid_cumulative"][t], -1),
                    (get("pv_ev"), -dt * c.ev_efficiency),
                    (get("solar_dis_ev"), -dt * c.ev_efficiency),
                ]
            )
            m.equality(
                [
                    (v["grid_cumulative"][t + 1], 1),
                    (v["grid_cumulative"][t], -1),
                    (get("grid_ev"), -dt * c.ev_efficiency),
                ]
            )
            if ceilings:
                # This restricts new charging; an initially high SoC does not force discharge.
                inactive_headroom = max(0.0, c.ev_capacity_kwh - ceilings[t])
                m.row(
                    [(ev[t + 1], 1), (get("one"), inactive_headroom), (get("three"), inactive_headroom)],
                    upper=c.ev_capacity_kwh,
                )
                if self.tight_ceilings:
                    m.upper[ev[t + 1]] = max(ceilings[t], o.ev_kwh - total_withdrawal)
            future_support = grid_ess and (
                any(
                    interval.start < later.start <= interval.start + timedelta(hours=24)
                    and later.house_kw - later.pv_ac_kw > max(p.billing_floor_kw, o.monthly_peak_kw)
                    for later in s.intervals[t:]
                )
                or any(interval.start < g.deadline <= interval.start + timedelta(hours=24) for g in s.goals)
            )
            if not grid_ess or not future_support:
                m.upper[get("grid_store")] = 0
            imp = [(get(name), 1) for name in ("grid_ev", "grid_house", "grid_store")]
            m.row(imp + [(get("grid_direction"), -c.grid_connection_kw)], upper=0)
            m.row(
                [(get("export"), 1), (get("grid_direction"), c.grid_connection_kw)],
                upper=c.grid_connection_kw,
            )
            for index, coefficient in imp:
                self.cash[index] += dt * p.import_eur_kwh * coefficient
            self.cash[get("export")] -= dt * p.export_eur_kwh
            for name in (
                "pv_store",
                "grid_store",
                "dc_store",
                "solar_dis_ev",
                "solar_dis_house",
                "grid_dis_house",
            ):
                self.operations[get(name)] += dt / max(1, c.ess_capacity_kwh)
            self.operations[get("start")] = 10.0
            self.operations[get("phase_change")] = 5.0
            self.operations[get("variation")] = 0.1
            # Explicit readiness: prefer earlier delivery, without changing required quantity.
            self.operations[get("amps_one")] = dt * t / max(1, n) * c.voltage / 1000 * 0.01
            self.operations[get("amps_three")] = self.operations[get("amps_one")] * 3
            active = [(get("one"), 1), (get("three"), 1)]
            if t:
                active += [(v["one"][t - 1], -1), (v["three"][t - 1], -1)]
                old_power = [
                    (v["amps_one"][t - 1], c.voltage / 1000),
                    (v["amps_three"][t - 1], c.voltage * 3 / 1000),
                ]
                for sign in (-1, 1):
                    m.row(
                        [(index, sign * coef) for index, coef in power_terms]
                        + [(index, -sign * coef) for index, coef in old_power]
                        + [(get("variation"), -1)],
                        upper=0,
                    )
                m.row([(get("three"), 1), (v["three"][t - 1], -1), (get("phase_change"), -1)], upper=0)
                m.row([(get("three"), -1), (v["three"][t - 1], 1), (get("phase_change"), -1)], upper=0)
            m.row(active + [(get("start"), -1)], upper=0 if t or o.ev_power_kw < 0.1 else 1)
            previous = t - 1
            while (
                previous >= 0
                and (interval.start - s.intervals[previous].start).total_seconds() < c.phase_dwell_seconds
            ):
                m.row([(get("one"), 1), (v["three"][previous], 1)], upper=1)
                m.row([(get("three"), 1), (v["one"][previous], 1)], upper=1)
                previous -= 1
            quarter = interval.start.replace(minute=interval.start.minute // 15 * 15, second=0, microsecond=0)
            self.quarters[quarter.isoformat()].append(t)
        m.row([(solar[n], 1), (grid[n], 1)], upper=c.ess_capacity_kwh - c.ess_min_kwh)
        self.economic.update(self.cash)
        if s.ev_known_at(n):
            self.economic[ev[-1]] -= p.ev_value_eur_kwh
        self.economic[solar[-1]] -= p.ess_value_eur_kwh
        self.economic[grid[-1]] -= p.ess_value_eur_kwh
        deficits: list[tuple[int, float]] = []
        deficit_slacks: list[int | None] = []
        for goal in s.goals:
            k = s.checkpoint_index(goal.deadline)
            if not s.ev_known_at(k):
                continue
            if not s.intervals[0].start <= goal.deadline <= s.intervals[-1].end:
                continue
            target = self.service.get(goal.id, goal.target(c, p))
            terms: list[tuple[int, float]] = [(ev[k], 1)]
            slack = None
            if self.relaxed_service:
                slack = m.variable(f"shortfall_{goal.id}", 1, target)[0]
                terms.append((slack, 1))
                self.goal_slack[goal.id] = slack
            m.row(terms, lower=target)
            margin_at = max(
                s.intervals[0].start, goal.deadline - timedelta(minutes=p.completion_margin_minutes)
            )
            margin_index = s.checkpoint_index(margin_at)
            if margin_index < k and not self.relaxed_service:
                shortage = m.variable(f"margin_shortfall_{goal.id}", 1, target)[0]
                m.row([(ev[margin_index], 1), (shortage, 1)], lower=target)
                self.operations[shortage] = 10000 / c.ev_capacity_kwh
            withdrawals = sum(i.withdrawal_kwh for i in s.intervals[:k])
            deficits.append((k, target + withdrawals - o.ev_kwh))
            deficit_slacks.append(slack)
        energy_need = max([0.0] + [value for _, value in deficits])
        if self.optional and energy_need <= 1e-7:
            for t in range(n):
                elapsed = 0.0
                k = t
                while k < n and elapsed < 5 / 60 - 1e-9:
                    m.row([(v["start"][t], 1), (v["one"][k], -1), (v["three"][k], -1)], upper=0)
                    elapsed += s.intervals[k].hours
                    k += 1
                if elapsed < 5 / 60 - 1e-9:
                    m.upper[v["start"][t]] = 0
        quantum = min(c.phases) * c.voltage / 1000 * c.ev_efficiency * max(i.hours for i in s.intervals)
        # Integer amperes require a final increment. Zero-deficit witness still permits no grid.
        rounding = quantum * c.minimum_current_a
        if not self.optional:
            delivered = [(v["non_grid_cumulative"][-1], 1), (v["grid_cumulative"][-1], 1)]
            if self.relaxed_service:
                maximum = m.variable("service_energy_maximum", 1, energy_need)[0]
                witnesses = m.variable("service_energy_witness", len(deficits) + 1, 1, integer=True)
                m.equality([(index, 1) for index in witnesses], 1)
                big_service = max(1, c.ev_capacity_kwh + total_withdrawal + energy_need)
                m.row([(maximum, 1), (witnesses[0], big_service)], upper=big_service)
                for j, (_, deficit) in enumerate(deficits):
                    shortfall = deficit_slacks[j]
                    terms = [(maximum, 1.0)] + ([(shortfall, 1.0)] if shortfall is not None else [])
                    m.row(terms, lower=deficit)
                    m.row(terms + [(witnesses[j + 1], big_service)], upper=deficit + big_service)
                m.row(delivered + [(maximum, -1), (witnesses[0], rounding)], upper=rounding)
            else:
                cap = energy_need + rounding if energy_need > 1e-7 else 0.0
                m.row(delivered, upper=cap if ev_total_limit is None else ev_total_limit)
        # A witness makes the maximum causal deficit exact, preventing source-label laundering.
        witness = m.variable("causal_witness", len(deficits) + 1, 1, integer=True)
        m.equality([(index, 1) for index in witness], 1)
        big = max(1.0, c.ev_capacity_kwh + total_withdrawal + energy_need)
        m.row([(v["grid_cumulative"][-1], 1), (witness[0], big)], upper=big)
        for j, (k, deficit) in enumerate(deficits):
            shortfall_index = deficit_slacks[j]
            shortfall_terms: list[tuple[int, float]] = (
                [(shortfall_index, 1.0)] if shortfall_index is not None else []
            )
            m.row(
                [(v["grid_cumulative"][-1], 1), (v["non_grid_cumulative"][k], 1), (witness[j + 1], big)]
                + shortfall_terms,
                upper=deficit + big + rounding,
            )
            m.row(
                [(v["non_grid_cumulative"][k], 1), (witness[j + 1], big)] + shortfall_terms,
                upper=deficit + big - 1e-6,
            )
        zone = ZoneInfo(p.timezone)
        for quarter_key, slots in self.quarters.items():
            first = s.intervals[slots[0]]
            month = first.start.astimezone(zone).strftime("%Y-%m")
            if month not in self.months:
                peak = m.variable(
                    f"peak_{month}",
                    1,
                    c.grid_connection_kw,
                    max(p.billing_floor_kw, o.monthly_peak_kw) if not self.months else p.billing_floor_kw,
                )[0]
                self.months[month] = peak
                self.cash[peak] = p.capacity_eur_kw_month
                self.economic[peak] = p.capacity_eur_kw_month
            prefix = o.quarter_import_kwh if slots[0] == 0 else 0
            terms = [
                (v[name][t], s.intervals[t].hours)
                for t in slots
                for name in ("grid_ev", "grid_house", "grid_store")
            ]
            m.row(terms + [(self.months[month], -0.25)], upper=-prefix)
            baseline = (
                max(p.billing_floor_kw, o.monthly_peak_kw)
                if month == s.intervals[0].start.astimezone(zone).strftime("%Y-%m")
                else p.billing_floor_kw
            )
            eligible = [
                g
                for g in s.goals
                if first.start < g.deadline and (g.earliest is None or first.start >= g.earliest)
            ]
            automatic = max(baseline, p.automatic_peak_kw)
            big_quarter = c.grid_connection_kw * 0.25
            for resource in ("grid_ev", "grid_store"):
                controlled = m.variable(f"quarter_control_{resource}_{quarter_key}", 1, 1, integer=True)[0]
                m.row(
                    [(v[resource][t], s.intervals[t].hours) for t in slots] + [(controlled, -big_quarter)],
                    upper=0,
                )
                extensions: list[tuple[int, float]] = []
                if resource == "grid_ev":
                    for g in eligible:
                        if (
                            g.approval_state != "granted"
                            or g.approval_revision != g.revision
                            or (g.approved_peak_kw or 0) <= automatic
                        ):
                            continue
                        k = s.checkpoint_index(g.deadline)
                        deficit = g.target(c, p) + sum(i.withdrawal_kwh for i in s.intervals[:k]) - o.ev_kwh
                        if deficit <= 0:
                            continue
                        use = m.variable(f"quarter_grant_{quarter_key}_{g.id}", 1, 1, integer=True)[0]
                        # A higher ceiling buys only energy still attributable to this exact goal.
                        end = slots[-1] + 1
                        m.row(
                            [
                                (v["non_grid_cumulative"][end], 1),
                                (v["grid_cumulative"][end], 1),
                                (use, c.ev_capacity_kwh * 4),
                            ],
                            upper=deficit + rounding + c.ev_capacity_kwh * 4,
                        )
                        extensions.append((use, -((g.approved_peak_kw or automatic) - automatic) * 0.25))
                else:
                    for grant in s.peak_permissions:
                        if (
                            grant.state == "granted"
                            and grant.forecast_id == s.forecast_id
                            and first.start < grant.deadline <= first.start + timedelta(hours=24)
                            and grant.peak_kw > automatic
                        ):
                            use = m.variable(f"quarter_grant_{quarter_key}_{grant.id}", 1, 1, integer=True)[0]
                            extensions.append((use, -(grant.peak_kw - automatic) * 0.25))
                if extensions:
                    m.row([(index, 1) for index, _ in extensions], upper=1)
                allowed = automatic if (eligible or resource == "grid_store" and grid_ess) else baseline
                # Uncontrollable house demand may exceed permission, but controlled purchases cannot add to it.
                m.row(
                    terms + [(controlled, big_quarter)] + extensions,
                    upper=allowed * 0.25 - prefix + big_quarter,
                )
        self.economic = dict(self.economic)
        self.cash = dict(self.cash)

    def add_optional_peak_limits(self, reference: dict[str, list[float]]) -> None:
        s, m = self.snapshot, self.linear
        p, o = s.policy, s.observation
        zone = ZoneInfo(p.timezone)
        initial_month = s.intervals[0].start.astimezone(zone).strftime("%Y-%m")
        for _, slots in self.quarters.items():
            month = s.intervals[slots[0]].start.astimezone(zone).strftime("%Y-%m")
            baseline = (
                max(p.billing_floor_kw, o.monthly_peak_kw) if month == initial_month else p.billing_floor_kw
            )
            prefix = o.quarter_import_kwh if slots[0] == 0 else 0.0
            ref_energy = (
                sum(
                    sum(reference[name][t] for name in ("grid_ev", "grid_house", "grid_store"))
                    * s.intervals[t].hours
                    for t in slots
                )
                + prefix
            )
            ref_house = sum(reference["grid_house"][t] * s.intervals[t].hours for t in slots) + prefix
            terms = [
                (m.variables[name][t], s.intervals[t].hours)
                for t in slots
                for name in ("grid_ev", "grid_house", "grid_store")
            ]
            m.row(terms, upper=max(baseline * 0.25, ref_energy) - prefix)
            house = [(m.variables["grid_house"][t], s.intervals[t].hours) for t in slots]
            m.row(house, upper=max(baseline * 0.25, ref_house) - prefix)

    def add_rolling_limits(self, reference: dict[str, list[float]], origins: set[int] | None = None) -> None:
        """Constrain joint cash/inventories in every rolling window, rather than reject a good solve afterward."""
        from datetime import timedelta
        from .validation import accounting

        s, m = self.snapshot, self.linear
        p, o, n = s.policy, s.observation, len(s.intervals)
        v = m.variables
        prefix = m.variable("rolling_cash_prefix", n + 1, lower=-INF)
        m.equality([(prefix[0], 1)])
        for t, interval in enumerate(s.intervals):
            m.equality(
                [
                    (prefix[t + 1], 1),
                    (prefix[t], -1),
                    *[
                        (v[name][t], -interval.hours * p.import_eur_kwh)
                        for name in ("grid_ev", "grid_house", "grid_store")
                    ],
                    (v["export"][t], interval.hours * p.export_eur_kwh),
                ]
            )
        averages: dict[str, int] = {}
        for key, slots in self.quarters.items():
            average = m.variable(f"rolling_quarter_{key}", 1)[0]
            averages[key] = average
            terms = [
                (v[name][t], -s.intervals[t].hours * 4)
                for t in slots
                for name in ("grid_ev", "grid_house", "grid_store")
            ]
            m.equality([(average, 1)] + terms, o.quarter_import_kwh * 4 if slots[0] == 0 else 0)
        zone = ZoneInfo(p.timezone)
        initial_month = s.intervals[0].start.astimezone(zone).strftime("%Y-%m")
        for start, interval in enumerate(s.intervals):
            if origins is not None and start not in origins:
                continue
            end_time = interval.start + timedelta(hours=24)
            end = next((k for k in range(start + 1, n) if s.intervals[k].start >= end_time), n)
            peaks: dict[str, int] = {}
            baseline_sum = 0.0
            metadata: list[tuple[list[int], float]] = []
            for key, all_slots in self.quarters.items():
                if all_slots[-1] < start or all_slots[0] >= end:
                    continue
                slots = [t for t in all_slots if start <= t < end]
                month = s.intervals[slots[0]].start.astimezone(zone).strftime("%Y-%m")
                baseline = (
                    max(p.billing_floor_kw, o.monthly_peak_kw)
                    if month == initial_month
                    else p.billing_floor_kw
                )
                if month not in peaks:
                    peaks[month] = m.variable(f"rolling_peak_{start}_{month}", 1, lower=baseline)[0]
                    baseline_sum += baseline * p.capacity_eur_kw_month
                peak = peaks[month]
                if slots == all_slots:
                    m.row([(averages[key], 1), (peak, -1)], upper=0)
                else:
                    m.row(
                        [
                            (v[name][t], s.intervals[t].hours * 4)
                            for t in slots
                            for name in ("grid_ev", "grid_house", "grid_store")
                        ]
                        + [(peak, -1)],
                        upper=0,
                    )
                metadata.append((slots, baseline))
            terms = [
                (prefix[end], 1),
                (prefix[start], -1),
                (v["ev_energy"][start], p.ev_value_eur_kwh if s.ev_known_at(start) else 0),
                (v["ev_energy"][end], -p.ev_value_eur_kwh if s.ev_known_at(end) else 0),
            ]
            for name in ("ess_solar", "ess_grid"):
                terms += [(v[name][start], p.ess_value_eur_kwh), (v[name][end], -p.ess_value_eur_kwh)]
            terms += [(index, p.capacity_eur_kw_month) for index in peaks.values()]
            m.row(terms, upper=accounting(s, reference, start, end)["comparison_eur"] + baseline_sum + 1e-6)
            self.rolling_metadata[start] = (start, end, metadata)

    def complete_warm(self, initial: list[float] | None) -> list[float] | None:
        if initial is None:
            return None
        values = initial[: len(self.linear.lower)] + [0.0] * max(0, len(self.linear.lower) - len(initial))
        if not self.rolling_metadata:
            return values
        s, v = self.snapshot, self.linear.variables
        p = s.policy
        prefix = v["rolling_cash_prefix"]
        zone = ZoneInfo(p.timezone)
        for t, interval in enumerate(s.intervals):
            imp = sum(values[v[name][t]] for name in ("grid_ev", "grid_house", "grid_store"))
            values[prefix[t + 1]] = values[prefix[t]] + interval.hours * (
                imp * p.import_eur_kwh - values[v["export"][t]] * p.export_eur_kwh
            )
        for key, slots in self.quarters.items():
            values[v[f"rolling_quarter_{key}"][0]] = sum(
                sum(values[v[name][t]] for name in ("grid_ev", "grid_house", "grid_store"))
                * s.intervals[t].hours
                * 4
                for t in slots
            ) + (s.observation.quarter_import_kwh * 4 if slots[0] == 0 else 0)
        for origin, (_, _, metadata) in self.rolling_metadata.items():
            for slots, baseline in metadata:
                month = s.intervals[slots[0]].start.astimezone(zone).strftime("%Y-%m")
                index = v[f"rolling_peak_{origin}_{month}"][0]
                average = sum(
                    sum(values[v[name][t]] for name in ("grid_ev", "grid_house", "grid_store"))
                    * s.intervals[t].hours
                    * 4
                    for t in slots
                )
                if slots[0] == 0:
                    average += s.observation.quarter_import_kwh * 4
                values[index] = max(values[index], baseline, average)
        return values

    def canonical_values(self, initial: list[float]) -> list[float]:
        """Tighten unpriced auxiliary indicators without altering any physical decision."""
        values = self.complete_warm(initial)
        assert values is not None
        v, c, o = self.linear.variables, self.snapshot.capabilities, self.snapshot.observation
        previous_on = o.ev_power_kw > 0.1
        previous_power = o.ev_power_kw
        previous_three = float(o.ev_phases == 3 and previous_on)
        for t in range(len(self.snapshot.intervals)):
            on = values[v["one"][t]] + values[v["three"][t]] > 0.5
            power = (values[v["amps_one"][t]] + 3 * values[v["amps_three"][t]]) * c.voltage / 1000
            values[v["start"][t]] = float(on and not previous_on)
            values[v["variation"][t]] = abs(power - previous_power) if t else 0.0
            values[v["phase_change"][t]] = abs(values[v["three"][t]] - previous_three) if t else 0.0
            previous_on, previous_power, previous_three = on, power, values[v["three"][t]]
            if "ess_change" in v:
                values[v["ess_change"][t]] = (
                    abs(values[v["battery_charge"][t]] - values[v["battery_charge"][t - 1]]) if t else 0
                )
        for goal in self.snapshot.goals:
            name = f"margin_shortfall_{goal.id}"
            if name in v:
                at = max(
                    self.snapshot.intervals[0].start,
                    goal.deadline - timedelta(minutes=self.snapshot.policy.completion_margin_minutes),
                )
                k = self.snapshot.checkpoint_index(at)
                target = self.service.get(goal.id, goal.target(c, self.snapshot.policy))
                values[v[name][0]] = max(0, target - values[v["ev_energy"][k]])
        s, p = self.snapshot, self.snapshot.policy
        service_deficits = []
        causal_deficits = []
        for goal in s.goals:
            if not s.intervals[0].start <= goal.deadline <= s.intervals[-1].end:
                continue
            k = s.checkpoint_index(goal.deadline)
            if not s.ev_known_at(k):
                continue
            shortfall = values[self.goal_slack[goal.id]] if goal.id in self.goal_slack else 0
            deficit = (
                self.service.get(goal.id, goal.target(c, p))
                + sum(i.withdrawal_kwh for i in s.intervals[:k])
                - o.ev_kwh
                - shortfall
            )
            service_deficits.append(deficit)
            causal_deficits.append(deficit - values[v["non_grid_cumulative"][k]])
        for name, deficit_values in (
            ("causal_witness", causal_deficits),
            ("service_energy_witness", service_deficits),
        ):
            if name in v:
                choice = (
                    max(range(len(deficit_values)), key=deficit_values.__getitem__) + 1
                    if deficit_values and max(deficit_values) > 1e-6
                    else 0
                )
                for j, index in enumerate(v[name]):
                    values[index] = float(j == choice)
        if "service_energy_maximum" in v:
            values[v["service_energy_maximum"][0]] = max([0.0] + service_deficits)
        rounding = (
            min(c.phases)
            * c.voltage
            / 1000
            * c.ev_efficiency
            * max(i.hours for i in s.intervals)
            * c.minimum_current_a
        )
        for key, slots in self.quarters.items():
            month = s.intervals[slots[0]].start.astimezone(ZoneInfo(p.timezone)).strftime("%Y-%m")
            baseline = self.linear.lower[self.months[month]]
            total = sum(
                sum(values[v[name][t]] for name in ("grid_ev", "grid_house", "grid_store"))
                * s.intervals[t].hours
                for t in slots
            ) + (o.quarter_import_kwh if slots[0] == 0 else 0)
            for resource in ("grid_ev", "grid_store"):
                values[v[f"quarter_control_{resource}_{key}"][0]] = float(
                    any(values[v[resource][t]] > 1e-8 for t in slots)
                )
            used = False
            charged = (
                values[v["non_grid_cumulative"][slots[-1] + 1]] + values[v["grid_cumulative"][slots[-1] + 1]]
            )
            for goal in s.goals:
                name = f"quarter_grant_{key}_{goal.id}"
                if name not in v:
                    continue
                k = s.checkpoint_index(goal.deadline)
                deficit = goal.target(c, p) + sum(i.withdrawal_kwh for i in s.intervals[:k]) - o.ev_kwh
                use = (
                    not used
                    and total * 4 > max(baseline, p.automatic_peak_kw) + 1e-7
                    and charged <= deficit + rounding + 1e-7
                )
                values[v[name][0]] = float(use)
                used = used or use
        return values

    def warm_from(self, flows: dict[str, list[float]]) -> list[float]:
        """Transfer by contract name; diagnostics can have different auxiliary columns."""
        values = [0.0] * len(self.linear.lower)
        for name, indexes in self.linear.variables.items():
            for index, value in zip(indexes, flows.get(name, [])):
                values[index] = value
        return self.canonical_values(values)

    def run(
        self,
        seconds: float,
        objective: dict[int, float] | None = None,
        warm: list[float] | None = None,
        bounds: list[tuple[dict[int, float], float]] | None = None,
    ) -> dict[str, Any]:
        before = monotonic()
        m = self.linear
        if objective is self.operations and "ess_change" not in m.variables:
            changes = m.variable("ess_change", len(self.snapshot.intervals), 1)
            modes = m.variables["battery_charge"]
            for t in range(1, len(changes)):
                for sign in (-1, 1):
                    m.row([(modes[t], sign), (modes[t - 1], -sign), (changes[t], -1)], upper=0)
                self.operations[changes[t]] = 2.0
        for terms, upper in bounds or []:
            m.row(list(terms.items()), upper=upper)
        m.cost = [0.0] * len(m.cost)
        for index, value in (objective if objective is not None else self.economic).items():
            m.cost[index] = value
        model = m.solver()
        if objective is self.operations:
            model.setOptionValue("mip_heuristic_effort", 0.5)
        if warm:
            warm = self.canonical_values(warm)
            model.setSolution(len(warm), np.arange(len(warm), dtype=np.int32), np.asarray(warm))
        model.setOptionValue("time_limit", max(0.001, seconds - (monotonic() - before)))
        model.run()
        info = model.getInfo()
        status = model.modelStatusToString(model.getModelStatus())
        feasible = info.primal_solution_status == highspy.SolutionStatus.kSolutionStatusFeasible
        result: dict[str, Any] = {
            "status": status,
            "feasible": feasible,
            "seconds": monotonic() - before,
            "columns": model.getNumCol(),
            "rows": model.getNumRow(),
            "integers": len(m.integer),
            "objective": None,
            "bound": None,
            "gap": None,
        }
        for key, value in (
            ("objective", info.objective_function_value),
            ("bound", info.mip_dual_bound),
            ("gap", info.mip_gap),
        ):
            if math.isfinite(value):
                result[key] = value
        if feasible:
            values = self.canonical_values(list(model.getSolution().col_value))
            result["canonical_objective"] = self.value(
                objective if objective is not None else self.economic, values
            )
            result["values"] = values
            result["flows"] = {
                name: [max(0.0, values[index]) for index in indexes]
                for name, indexes in m.variables.items()
                if not name.startswith("quarter_")
            }
        return result

    @staticmethod
    def value(objective: dict[int, float], values: list[float]) -> float:
        return sum(coefficient * values[index] for index, coefficient in objective.items())
