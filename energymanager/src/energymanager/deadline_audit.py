"""Independent arithmetic checks for explicit cautious PV source contexts."""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

from .domain import Snapshot, instant, json_data
from .reservations import reservations
from .validation import TOL, validate


def cautious_context(nominal: Snapshot, flows: dict[str, list[float]], checkpoint: int) -> Snapshot:
    intervals = []
    for t, interval in enumerate(nominal.intervals):
        margin = .2 if t < checkpoint else 0.0
        protected_ac = flows["guard_ac_house"][t] + flows["guard_ac_store"][t]
        protected_dc = flows["guard_dc_house"][t] + flows["guard_dc_store"][t]
        intervals.append(replace(interval, pv_ac_kw=(1 - margin) * interval.pv_ac_kw + margin * protected_ac,
                                 pv_dc_kw=(1 - margin) * interval.pv_dc_kw + margin * protected_dc))
    return replace(nominal, intervals=tuple(intervals), forecast_id=nominal.forecast_id + ":cautious80",
                   provenance=nominal.provenance + " · cautious future usable PV (80%)")


def audit_deadline_context(nominal: Snapshot, context: Snapshot, flows: dict[str, list[float]],
                           checkpoint: int, terminal_house: float = 0.0,
                           service: dict[str, float] | None = None) -> list[str]:
    errors = validate(context, flows, service)
    for name in ("guard_house_stock", "guard_ac_house", "guard_ac_store", "guard_dc_house",
                 "guard_dc_store", "guard_house_discharge"):
        size = len(nominal.intervals) + int(name == "guard_house_stock")
        if len(flows[name]) != size or any(not math.isfinite(value) for value in flows[name]):
            return errors + [f"Invalid cautious source ledger {name}"]
    c = nominal.capabilities
    expected = cautious_context(nominal, flows, checkpoint)
    if json_data(expected) != json_data(context):
        errors.append("Cautious forecast context mismatch")
    h = flows["guard_house_stock"]
    if abs(h[0]) > TOL or h[-1] > terminal_house + TOL or h[-1] > flows["ess_solar"][-1] + TOL:
        errors.append("Protected future household stock endpoints")
    for t, interval in enumerate(nominal.intervals):
        ah, ac, dh, dc, discharge = (flows[name][t] for name in
            ("guard_ac_house", "guard_ac_store", "guard_dc_house", "guard_dc_store", "guard_house_discharge"))
        if (min(ah, ac, dh, dc, discharge, h[t]) < -TOL
                or ah + ac > interval.pv_ac_kw + TOL or dh + dc > interval.pv_dc_kw + TOL
                or ah + dh * c.ac_discharge_efficiency > flows["pv_house"][t] + TOL
                or ac > flows["pv_store"][t] + TOL or dc > flows["dc_store"][t] + TOL
                or dh > flows["dc_invert"][t] + TOL or discharge > flows["solar_dis_house"][t] + TOL):
            errors.append(f"Protected PV allocation {t}")
        after = h[t] + interval.hours * (ac * c.ac_charge_efficiency + dc * c.dc_efficiency
                                        - discharge / c.ac_discharge_efficiency)
        if abs(h[t + 1] - after) > TOL or h[t] > flows["ess_solar"][t] + TOL:
            errors.append(f"Protected household stock conservation {t}")
        if flows["solar_dis_ev"][t] * interval.hours / c.ac_discharge_efficiency > flows["ess_solar"][t] - h[t] + TOL:
            errors.append(f"Protected future household PV used by EV {t}")
    return errors


def validate_certificate(certificate: dict[str, Any]) -> list[str]:
    try:
        nominal = Snapshot.from_dict(certificate["nominal_context"])
        context = Snapshot.from_dict(certificate["context"])
        flows, scope, checkpoint = certificate["flows"], certificate["scope"], certificate["checkpoint"]
        errors = audit_deadline_context(nominal, context, flows, checkpoint,
                                        certificate.get("terminal_house_kwh", 0), certificate.get("service"))
        deadline, activation = instant(scope["deadline"]), instant(certificate["activation_at"])
        goal = next((g for g in nominal.goals if g.id == scope["goal_id"] and g.revision == scope["revision"]
                     and g.deadline == deadline), None)
        if (goal is None or abs(goal.target(nominal.capabilities, nominal.policy) - scope["target_kwh"]) > TOL
                or checkpoint != nominal.checkpoint_index(deadline)
                or not 0 < checkpoint <= len(nominal.intervals)
                or flows["ev_energy"][checkpoint] + TOL < scope["target_kwh"]):
            errors.append("Cautious deadline scope or required outcome mismatch")
        if certificate["progress_kwh"] != flows["ev_energy"]:
            errors.append("Cautious required progress mismatch")
        if activation not in {i.start for i in context.intervals} or activation >= deadline:
            errors.append("Cautious activation outside the charging horizon")
        if any(flows["grid_ev"][t] > TOL and i.start < activation
               and not (nominal.hold_until and i.start < nominal.hold_until)
               for t, i in enumerate(context.intervals)):
            errors.append("Cautious grid work precedes its certified activation")
        if certificate["reservations"] != reservations(context, flows):
            errors.append("Cautious reservation ledger mismatch")
        running = (nominal.execution or {}).get("running_task")
        if running:
            opposite = "three" if running["phase"] == 1 else "one"
            changed = any(flows[opposite][t] > .5 for t, interval in enumerate(nominal.intervals)
                          if interval.start < instant(running["deadline"]))
            proof = certificate.get("phase_necessity", {})
            if changed and (certificate.get("phase_preference") != "necessary_phase"
                    or proof.get("status") != "Infeasible" or proof.get("phase") != running["phase"]
                    or proof.get("deadline") != running["deadline"] or proof.get("input_digest") != nominal.digest
                    or proof.get("service") != certificate.get("service", {})):
                errors.append("Cautious phase change lacks matching required-service infeasibility evidence")
        return errors
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        return [f"Invalid cautious certificate: {type(exc).__name__}"]
