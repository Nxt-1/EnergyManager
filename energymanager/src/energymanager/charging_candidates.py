"""Reference-based EV candidates; restrictions never escape their bounded search."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .optimization import JointModel


def fixed_grid_reference(model: JointModel, reference: dict[str, list[float]]) -> tuple[JointModel | None, dict[str, Any]]:
    s, c = model.snapshot, model.snapshot.capabilities
    record: dict[str, Any] = {"applied": False}
    goal = next((g for g in sorted(s.goals, key=lambda g: g.deadline)
                 if s.intervals[0].start < g.deadline <= s.intervals[-1].end
                 and s.ev_known_at(s.checkpoint_index(g.deadline))
                 and g.target(c, s.policy) + sum(i.withdrawal_kwh for i in s.intervals
                                                if i.start < g.deadline) > s.observation.ev_kwh + 1e-6), None)
    if goal is None:
        record["reason"] = "No unmet known deadline"
        return None, record
    checkpoint = s.checkpoint_index(goal.deadline)
    record.update(goal_id=goal.id, deadline=goal.deadline.isoformat(), intervals=checkpoint,
                  partial_intervals=sum(abs(i.hours - 5 / 60) > 1e-9 for i in s.intervals[:checkpoint]))
    pv_windows = [t for t, i in enumerate(s.intervals[:checkpoint]) if i.available
                  and i.pv_ac_kw + min(c.ac_discharge_kw, i.pv_dc_kw * c.ac_discharge_efficiency) > i.house_kw + 1e-6]
    record["pv_windows"] = pv_windows
    if pv_windows or any(i.withdrawal_kwh for i in s.intervals[:checkpoint]):
        record["reason"] = "Keep PV/travel choices in the joint wider search"
        return None, record
    on = [reference["one"][t] + reference["three"][t] > .5 for t in range(checkpoint)]
    starts = sum(active and (t == 0 or not on[t - 1]) for t, active in enumerate(on))
    if (1 not in c.phases
            or any(reference[name][t] > 1e-6 for name in ("pv_ev", "solar_dis_ev") for t in range(checkpoint))
            or s.hold_until and s.hold_ev_kw > .1 and s.hold_phases != 1):
        record["reason"] = "The reference source/held phase does not support this single-phase candidate"
        return None, record
    candidate = deepcopy(model)
    if starts == 1 and not any(reference["three"][:checkpoint]):
        for name in ("one", "three", "amps_one", "amps_three"):
            for t in range(checkpoint):
                index = candidate.linear.variables[name][t]
                candidate.linear.lower[index] = candidate.linear.upper[index] = reference[name][t]
        record["construction"] = "checked reference profile"
    else:
        # A fragmented fresh reference is a quantity, not a required placement.
        # Offer one continuous phase-one block; the joint model chooses its exact
        # fractional/held-slot currents and sources before the unrestricted search.
        for t in range(checkpoint):
            candidate.linear.upper[candidate.linear.variables["three"][t]] = 0
            candidate.linear.upper[candidate.linear.variables["amps_three"][t]] = 0
        candidate.linear.row([(candidate.linear.variables["one"][0], 1)]
                             + [(candidate.linear.variables["start"][t], 1) for t in range(1, checkpoint)], upper=1)
        candidate.linear.equality([(candidate.linear.variables["ev_energy"][checkpoint], 1)],
                                   reference["ev_energy"][checkpoint])
        record["construction"] = "joint one-session profile at exact reference energy"
    # Fix only this EV profile. Sources, ESS and later EV work remain joint choices.
    record.update(applied=True, battery_kwh=sum(reference["grid_ev"][t] * s.intervals[t].hours
                                               * c.ev_efficiency for t in range(checkpoint)))
    return candidate, record


def reachable_deadline_bounds(model: JointModel) -> dict[str, int]:
    """Backward stock floors use upper physical delivery bounds, never forecast preferences."""
    if model.relaxed_service:
        return {"stock_floors": 0}
    s, c, m = model.snapshot, model.snapshot.capabilities, model.linear
    v = m.variables
    floors = [0.0] * (len(s.intervals) + 1)
    for goal in s.goals:
        if s.intervals[0].start <= goal.deadline <= s.intervals[-1].end:
            k = s.checkpoint_index(goal.deadline)
            if s.ev_known_at(k):
                floors[k] = max(floors[k], model.service.get(goal.id, goal.target(c, s.policy)))
    tightened = 0
    for t in range(len(s.intervals) - 1, -1, -1):
        if not s.ev_known_at(t) or not s.ev_known_at(t + 1):
            continue
        capacity = max((m.upper[v[f"amps_{name}"][t]] * phases * c.voltage / 1000
                        for name, phases in (("one", 1), ("three", 3))
                        if phases in c.phases and m.upper[v[name][t]] > 0), default=0.0)
        if not s.intervals[t].available:
            capacity = 0.0
        floors[t] = max(floors[t], floors[t + 1] + s.intervals[t].withdrawal_kwh
                        - capacity * s.intervals[t].hours * c.ev_efficiency)
        index = v["ev_energy"][t]
        if floors[t] > m.lower[index] + 1e-8:
            # A row preserves a valid infeasibility proof even when the floor exceeds
            # physical capacity; do not create contradictory solver column bounds.
            m.row([(index, 1.0)], lower=floors[t])
            tightened += 1
    return {"stock_floors": tightened}
