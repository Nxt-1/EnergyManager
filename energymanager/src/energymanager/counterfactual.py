"""Bounded, read-only interventions on frozen inputs; no live control dependencies."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CounterfactualRequest:
    kind: str
    start_index: int
    end_index: int

    def restriction(self):
        return self.kind, self.start_index, self.end_index


def constrain(model, variables, restrictions, count):
    if len(restrictions) > 1:
        raise ValueError("at most one counterfactual intervention per solve")
    for kind, start, end in restrictions:
        if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= count:
            raise ValueError("counterfactual window outside snapshot")
        if kind not in {"forbid_ev", "continuous_ev", "no_grid_import"}:
            raise ValueError("unsupported counterfactual; source-specific EV grid attribution is not identifiable")
        for i in range(start, end):
            if kind == "no_grid_import":
                # Deliberately stronger than 'grid-powered EV': AC energy is fungible.
                model.addConstr(variables.grid_import_kw[i] == 0)
            elif kind == "forbid_ev":
                for currents in (variables.ev_single_phase_a, variables.ev_three_phase_a):
                    if i in currents:
                        model.addConstr(currents[i] == 0)
            elif i not in variables.ev_active:
                raise ValueError("continuous session includes an unavailable EV interval")
            else:
                model.addConstr(variables.ev_active[i] == 1)


def compare(snapshot, request: CounterfactualRequest):
    data = snapshot.inputs()
    if len(data["frame"].intervals) > 672 or data["policy"].total_seconds > 60:
        raise ValueError("counterfactual budget: at most 672 intervals and 60 seconds per solve")
    baseline = snapshot.solve()
    alternative = snapshot.solve(restrictions=(request.restriction(),))
    delta = None
    if baseline.adoption_ready and alternative.adoption_ready:
        def window_energy(plan):
            return sum(i.scheduled_load_w for i in plan.intervals[request.start_index:request.end_index]) * .25 / 1000

        def first_slot(plan):
            return next((i for i, slot in enumerate(plan.intervals) if slot.scheduled_load_w > 1), None)

        before_slot, after_slot = first_slot(baseline.plan), first_slot(alternative.plan)
        delta = {
            "objective_eur": alternative.milp_objective_eur - baseline.milp_objective_eur,
            "ev_sessions": alternative.ev_session_count - baseline.ev_session_count,
            "ev_energy_in_window_kwh": window_energy(alternative.plan) - window_energy(baseline.plan),
            "first_ev_start_shift_slots": (after_slot - before_slot
                                          if before_slot is not None and after_slot is not None else None),
            "grid_import_kwh": alternative.milp_cost.import_kwh - baseline.milp_cost.import_kwh,
            "incremental_capacity_eur": (
                alternative.milp_cost.incremental_capacity_cost_eur - baseline.milp_cost.incremental_capacity_cost_eur
            ),
        }
    return {
        "snapshot_id": snapshot.snapshot_id,
        "request": request,
        "baseline": baseline,
        "alternative": alternative,
        "delta": delta,
        "interpretation": "Measured differences under one frozen intervention; not a unique causal explanation.",
        "infeasibility": (
            "Joint constraints infeasible; no minimal conflicting subset was computed."
            if alternative.status == "infeasible"
            else None
        ),
    }
