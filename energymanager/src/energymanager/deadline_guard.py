"""Joint cautious source witnesses and bounded, precomputed EV deadline fallbacks."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from time import monotonic
from typing import Any

from .deadline_audit import audit_deadline_context, cautious_context
from .domain import Snapshot, json_data
from .optimization import JointModel
from .reservations import reservations
from .validation import TOL
from .running_task import phase_lock


def cautious_model(snapshot: Snapshot, checkpoint: int, terminal_house: float = 0.0,
                   service: dict[str, float] | None = None) -> JointModel:
    """Protected household paths stay full-credit; the remaining PV is reduced once.

    Protected future storage is separately conserved and cannot supply EV charging.
    Its initial stock is zero: already-known solar retains its ordinary full credit.
    Protection is a joint choice, rather than a frozen optional nominal ESS dispatch.
    """
    model = JointModel(snapshot, service=service, grid_ess=True)
    m, v, c, n = model.linear, model.linear.variables, snapshot.capabilities, len(snapshot.intervals)
    stock = m.variable("guard_house_stock", n + 1, c.ess_capacity_kwh)
    for name in ("guard_ac_house", "guard_ac_store", "guard_dc_house", "guard_dc_store", "guard_house_discharge"):
        m.variable(name, n, c.grid_connection_kw + c.ac_discharge_kw + c.dc_charge_kw)
    ac_rows = {frozenset(v[name][t] for name in ("pv_ev", "pv_house", "pv_store", "export", "curtail", "dc_invert")): t
               for t in range(n)}
    dc_rows = {frozenset((v["dc_store"][t], v["dc_invert"][t])): t for t in range(n)}
    starts, indexes, values = [0], [], []
    changed_ac = changed_dc = 0
    for row in range(len(m.row_lower)):
        terms = list(zip(m.indices[m.starts[row]:m.starts[row + 1]], m.values[m.starts[row]:m.starts[row + 1]]))
        signature = frozenset(index for index, _ in terms)
        if signature in ac_rows and m.row_lower[row] == m.row_upper[row]:
            t = ac_rows[signature]
            margin = .2 if t < checkpoint else 0.0
            terms += [(v[name][t], -margin) for name in ("guard_ac_house", "guard_ac_store")]
            m.row_lower[row] = m.row_upper[row] = snapshot.intervals[t].pv_ac_kw * (1 - margin)
            changed_ac += 1
        elif signature in dc_rows and m.row_upper[row] == snapshot.intervals[dc_rows[signature]].pv_dc_kw:
            t = dc_rows[signature]
            margin = .2 if t < checkpoint else 0.0
            terms += [(v[name][t], -margin) for name in ("guard_dc_house", "guard_dc_store")]
            m.row_upper[row] *= 1 - margin
            changed_dc += 1
        for index, coefficient in terms:
            indexes.append(index)
            values.append(coefficient)
        starts.append(len(indexes))
    if changed_ac != n or changed_dc != n:
        raise ValueError("Cautious model could not identify all source conservation rows")
    m.starts, m.indices, m.values = starts, indexes, values
    m.equality([(stock[0], 1)])
    m.row([(stock[-1], 1)], upper=terminal_house)
    for t, interval in enumerate(snapshot.intervals):
        ah, ac, dh, dc, discharge = (v[name][t] for name in
            ("guard_ac_house", "guard_ac_store", "guard_dc_house", "guard_dc_store", "guard_house_discharge"))
        m.row([(ah, 1), (ac, 1)], upper=interval.pv_ac_kw)
        m.row([(dh, 1), (dc, 1)], upper=interval.pv_dc_kw)
        m.row([(ah, 1), (dh, c.ac_discharge_efficiency), (v["pv_house"][t], -1)], upper=0)
        for protected, supplied in ((ac, "pv_store"), (dc, "dc_store"), (dh, "dc_invert"), (discharge, "solar_dis_house")):
            m.row([(protected, 1), (v[supplied][t], -1)], upper=0)
        m.equality([(stock[t + 1], 1), (stock[t], -1), (ac, -interval.hours * c.ac_charge_efficiency),
                    (dc, -interval.hours * c.dc_efficiency), (discharge, interval.hours / c.ac_discharge_efficiency)])
        m.row([(stock[t], 1), (v["ess_solar"][t], -1)], upper=0)
        m.row([(v["solar_dis_ev"][t], interval.hours / c.ac_discharge_efficiency),
               (stock[t], 1), (v["ess_solar"][t], -1)], upper=0)
    m.row([(stock[-1], 1), (v["ess_solar"][-1], -1)], upper=0)
    return model


def deadline_certificate(snapshot: Snapshot, reference: dict[str, list[float]], budget: float,
                         service: dict[str, float] | None = None) -> dict[str, Any]:
    started = monotonic()
    deadline = started + max(0, budget)
    s, c = snapshot, snapshot.capabilities
    relevant = [g for g in sorted(s.goals, key=lambda g: g.deadline)
                if s.intervals[0].start < g.deadline <= s.intervals[-1].end
                and s.ev_known_at(s.checkpoint_index(g.deadline))
                and g.target(c, s.policy) + sum(i.withdrawal_kwh for i in s.intervals if i.start < g.deadline)
                > s.observation.ev_kwh + TOL]
    if not relevant:
        return {"status": "not_needed", "seconds": monotonic() - started}
    goal = relevant[0]
    k = s.checkpoint_index(goal.deadline)
    scope = {"goal_id": goal.id, "revision": goal.revision, "deadline": goal.deadline.isoformat(),
             "target_kwh": goal.target(c, s.policy), "title": goal.title}
    record: dict[str, Any] = {"status": "unverified", "scope": scope, "margin": .2, "attempts": [],
                              "withdrawals": [{"at": i.start.isoformat(), "kwh": i.withdrawal_kwh}
                                              for i in s.intervals[:k] if i.withdrawal_kwh > 0]}
    running = (s.execution or {}).get("running_task")
    if running:
        record["phase_preference"] = "same_phase"
    opposite = "three" if running and running["phase"] == 1 else "one"
    reference_changes_phase = bool(running and any(reference[opposite][t] > .5
        for t, interval in enumerate(s.intervals) if interval.start < goal.deadline))
    if reference["ev_energy"][k] + TOL < goal.target(c, s.policy):
        return {**record, "status": "nominal_shortfall"}
    if not reference_changes_phase and not any(i.pv_ac_kw > 0 or i.pv_dc_kw > 0 for i in s.intervals):
        # No uncertain generation: retain the already checked coherent reference,
        # including its held/partial slots, rather than inventing a bursty new task.
        flows = {name: list(values) for name, values in reference.items()}
        n = len(s.intervals)
        for name in ("guard_ac_house", "guard_ac_store", "guard_dc_house", "guard_dc_store", "guard_house_discharge"):
            flows[name] = [0.0] * n
        flows["guard_house_stock"] = [0.0] * (n + 1)
        cautious = cautious_context(s, flows, k)
        if not audit_deadline_context(s, cautious, flows, k, service=service):
            record.update(status="certified", checkpoint=k, nominal_context=json_data(s),
                          context=json_data(cautious), flows=flows, service=service or {},
                          terminal_house_kwh=0.0, activation_at=s.intervals[0].start.isoformat(),
                          progress_kwh=flows["ev_energy"], latest_start_resolved=True,
                          seconds=monotonic() - started, reservations=reservations(cautious, flows))
            return record
    end_quarter = goal.deadline.replace(minute=goal.deadline.minute // 15 * 15, second=0, microsecond=0)
    if end_quarter < goal.deadline:
        end_quarter += timedelta(minutes=15)
    end = next((t + 1 for t, i in enumerate(s.intervals) if i.end >= end_quarter), len(s.intervals))
    if s.appliance:
        end = len(s.intervals)
    context = replace(s, intervals=s.intervals[:end], goals=tuple(g for g in s.goals if g.deadline <= goal.deadline))
    reserve = reservations(s, reference)[end]
    model = cautious_model(context, k, reserve["solar_house_kwh"], service)
    # Preserve future required stock, without declaring optional nominal dispatch immutable.
    for name, required in (("ess_solar", reserve["solar_house_kwh"] + reserve["solar_ev_kwh"]),
                           ("ess_grid", reserve["grid_house_kwh"])):
        model.linear.row([(model.linear.variables[name][-1], 1)], lower=required)
    if s.appliance:
        for name in ("dishwasher_start", "dishwasher_power"):
            for index, value in zip(model.linear.variables.get(name, []), reference.get(name, [])):
                model.linear.lower[index] = model.linear.upper[index] = value

    def solve(base: JointModel, grid_from: int, warm: list[float] | None = None) -> dict[str, Any]:
        trial = deepcopy(base)
        for t in range(grid_from):
            if s.hold_until and context.intervals[t].start < s.hold_until:
                continue
            trial.linear.upper[trial.linear.variables["grid_ev"][t]] = 0.0
        remaining = max(0.0, deadline - monotonic() - .15)
        if remaining < .1:
            return {"feasible": False, "status": "Time limit reached"}
        objective = {trial.linear.variables["grid_cumulative"][-1]: 1000.0}
        objective.update({trial.linear.variables["grid_ev"][t]: i.hours * (t + 1) / max(1, len(context.intervals))
                          for t, i in enumerate(context.intervals)})
        outcome = trial.run(min(2.5, remaining), objective=objective, warm=warm)
        if (warm is not None and trial.linear.accepts(warm)
                and (not outcome["feasible"] and outcome["status"] == "Time limit reached")):
            outcome.update(feasible=True, retained_starting_candidate=True, values=warm,
                           flows={name: [warm[index] for index in indexes]
                                  for name, indexes in trial.linear.variables.items()})
        evidence = {key: value for key, value in outcome.items() if key not in ("flows", "values")}
        record["attempts"].append({"grid_from": grid_from, **evidence})
        if outcome["feasible"]:
            cautious = cautious_context(context, outcome["flows"], k)
            errors = audit_deadline_context(context, cautious, outcome["flows"], k, reserve["solar_house_kwh"], service)
            if errors:
                record["attempts"][-1]["audit_errors"] = errors
                return {"feasible": False, "status": "invalid_certificate"}
            outcome["context"] = cautious
        return outcome

    if running:
        phase_lock(model,running["phase"],running["deadline"])
        record["phase_preference"] = "same_phase"
    best = solve(model, 0)
    if not best["feasible"]:
        # A restricted witness cannot prove general infeasibility. Release future
        # reserve/appliance restrictions and retain all joint horizon alternatives.
        if best["status"] == "Infeasible" and deadline - monotonic() > .2:
            context = s
            reserve = {"solar_house_kwh": 0.0}
            model = cautious_model(context, k, service=service)
            if running:
                phase_lock(model,running["phase"],running["deadline"])
            best = solve(model, 0)
            if running and not best["feasible"] and best["status"] == "Infeasible" and deadline-monotonic() > .35:
                # Only a global same-phase required-service failure, after releasing
                # future reserve restrictions, permits the phase-changing witness.
                record["phase_preference"] = "necessary_phase"
                record["phase_necessity"] = {"status":"Infeasible", "phase":running["phase"],
                    "deadline":running["deadline"], "input_digest":context.digest, "service":service or {}}
                model = cautious_model(context,k,service=service)
                best = solve(model,0)
            if not best["feasible"] and best["status"] == "Infeasible":
                record["status"] = "margin_shortfall"
        if not best["feasible"]:
            record["seconds"] = monotonic() - started
            return record
        if s.appliance and any(abs(a - b) > TOL for name in ("dishwasher_start", "dishwasher_power")
                               for a, b in zip(best["flows"].get(name, []), reference.get(name, []))):
            # A joint alternative disproves infeasibility, but cannot silently
            # replace an appliance commitment already accepted by its controller.
            record.update(reason="Joint witness requires a different appliance commitment",
                          seconds=monotonic() - started)
            return record
    low, high = 0, k
    future_pv = any(i.pv_ac_kw > 0 or i.pv_dc_kw > 0 for i in context.intervals[:k])
    if future_pv:
        for _ in range(9):
            if high - low <= 1 or deadline - monotonic() < .4:
                break
            middle = (low + high) // 2
            trial = solve(model, middle, best["values"])
            if trial["feasible"]:
                low, best = middle, trial
            elif trial["status"] == "Infeasible":
                high = middle
            else:
                break
    activation = context.intervals[min(low, len(context.intervals) - 1)].start
    record.update(status="certified", checkpoint=k, nominal_context=json_data(context),
                  context=json_data(best["context"]), flows=best["flows"],
                  service=service or {}, terminal_house_kwh=reserve["solar_house_kwh"], activation_at=activation.isoformat(),
                  progress_kwh=best["flows"]["ev_energy"], latest_start_resolved=high - low <= 1,
                  seconds=monotonic() - started, reservations=reservations(best["context"], best["flows"]))
    return record
