"""Fresh synthetic references; no archived dispatch or installation access."""

from dataclasses import replace

from energymanager.charging_candidates import fixed_grid_reference, reachable_deadline_bounds
import pytest

from energymanager.domain import Goal, Interval, time_grid
from energymanager.optimization import JointModel
from energymanager.planner import Planner
from energymanager.validation import validate
from test_first_slice import tiny


@pytest.mark.parametrize("held", [False, True])
def test_reference_candidate_keeps_partial_and_held_energy_while_wider_model_stays_open(held):
    from time import monotonic

    s = tiny(hours=2, ev=24)
    s = replace(s, goals=(Goal("goal", "SYNTHETIC deadline", s.intervals[-1].end, 43),))
    if held:
        from datetime import timedelta
        until = s.observation.at + timedelta(seconds=90)
        grid = time_grid(s.observation.at, 2, (until,))
        s = replace(s, observation=replace(s.observation, ev_power_kw=2.3),
                    intervals=tuple(Interval(a, b, .4, 0, 0) for a, b in zip(grid, grid[1:])),
                    hold_until=until, hold_ev_kw=2.3, hold_phases=1)
    model = JointModel(s)
    planner = Planner()
    planner.deadline = monotonic() + 4
    values = planner.starting_point(model)
    assert values is not None
    flows = {name: [values[i] for i in indexes] for name, indexes in model.linear.variables.items()}
    assert not validate(s, flows)
    optional = JointModel(s, optional=True)
    before = list(optional.linear.upper)
    candidate, scope = fixed_grid_reference(optional, flows)
    assert candidate is not None and scope["applied"] and scope["partial_intervals"] >= 2
    assert optional.linear.upper == before
    for name in ("one", "three", "amps_one", "amps_three"):
        for t, index in enumerate(candidate.linear.variables[name]):
            assert candidate.linear.lower[index] == candidate.linear.upper[index] == flows[name][t]
    # Any new backward floor must admit this independent feasible reference.
    reachable_deadline_bounds(model)
    assert model.linear.accepts(model.warm_from(flows))


def test_reference_restriction_is_not_applied_to_usable_pv_windows():
    from time import monotonic

    s = tiny(hours=2, ev=24, pv=4)
    s = replace(s, goals=(Goal("goal", "SYNTHETIC PV deadline", s.intervals[-1].end, 43),))
    model = JointModel(s)
    planner = Planner()
    planner.deadline = monotonic() + 4
    values = planner.starting_point(model)
    assert values is not None
    flows = {name: [values[i] for i in indexes] for name, indexes in model.linear.variables.items()}
    candidate, scope = fixed_grid_reference(model, flows)
    assert candidate is None and scope["pv_windows"] and not scope["applied"]
