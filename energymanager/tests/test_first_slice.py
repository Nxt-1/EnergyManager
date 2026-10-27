from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from energymanager.domain import Capabilities, Goal, Interval, Observation, Policy, Snapshot, time_grid
from energymanager.optimization import JointModel
from energymanager.validation import accounting, validate


def tiny(*, hours=1, ev=24, ess=2.8, house=0.4, pv=0, dc=0, goals=(), **policy):
    start = datetime(2026, 10, 23, 0, tzinfo=UTC)
    grid = time_grid(start, hours)
    intervals = tuple(Interval(a, b, house, pv, dc) for a, b in zip(grid, grid[1:]))
    return Snapshot(
        "tiny",
        1,
        Observation(start, ev, ess, True, house, pv, dc),
        start,
        "synthetic",
        intervals,
        goals,
        Capabilities(),
        Policy(**policy),
    )


def solve(snapshot, **kwargs):
    model = JointModel(snapshot, **kwargs)
    result = model.run(10)
    assert result["feasible"], result
    assert validate(snapshot, result["flows"]) == []
    return result["flows"]


@pytest.mark.parametrize("field", ["ev_kwh", "ess_kwh", "ess_grid_kwh"])
def test_invalid_observation_stocks_name_the_field_and_value(field):
    with pytest.raises(ValueError, match=f"Invalid negative observation {field}=-0.1"):
        replace(tiny().observation, **{field: -.1})


def test_signed_ev_reading_round_trips_and_still_plans_only_positive_charging():
    from energymanager.domain import json_data

    s = tiny()
    s = replace(s, observation=replace(s.observation, ev_power_kw=-.035),
                goals=(Goal("manual", "SYNTHETIC charge", s.intervals[-1].end, 42),))
    restored = Snapshot.from_dict(json_data(s))
    assert restored.observation.ev_power_kw == -.035 and restored.digest == s.digest
    flows = solve(restored)
    assert flows["ev_energy"][-1] >= 25.2 - 1e-6
    assert min(flows["grid_ev"]) >= -1e-6


def test_real_required_ev_energy_and_grid_arithmetic():
    s = tiny()
    goal = Goal("manual", "Charge", s.intervals[-1].end, 42)
    s = replace(s, goals=(goal,))
    f = solve(s)
    assert 25.2 <= f["ev_energy"][-1] <= 25.2 + 0.1035 + 1e-6
    assert sum(power * i.hours for power, i in zip(f["grid_ev"], s.intervals)) == pytest.approx(
        (f["ev_energy"][-1] - 24) / 0.9
    )
    assert accounting(s, f)["imports_kwh"] == pytest.approx(0.4 + (f["ev_energy"][-1] - 24) / 0.9)


def test_ac_and_dc_charge_independently_above_converter_limit():
    s = tiny(pv=4, dc=4, house=0)
    f = solve(s)
    assert max(a + b for a, b in zip(f["pv_store"], f["dc_store"])) > 6
    assert max(f["pv_store"]) <= 2.5 + 1e-5
    assert f["ess_solar"][-1] > 6


def test_no_optional_grid_and_no_grid_laundering_with_solar():
    s = tiny(pv=0)
    f = solve(s, optional=True)
    assert sum(f["grid_ev"]) == pytest.approx(0)
    s = tiny(pv=4)
    s = replace(s, goals=(Goal("manual", "Charge", s.intervals[-1].end, 42),))
    f = solve(s, optional=True)
    assert sum(f["grid_ev"]) == pytest.approx(0)
    assert f["ev_energy"][-1] > 25.2


def test_sub_tolerance_solar_deficit_cannot_unlock_a_whole_grid_rounding_increment():
    s = tiny(hours=2, ev=24, pv=4, house=0)
    s = replace(s, goals=(Goal("goal", "SYNTHETIC source rounding", s.intervals[-1].end, 42),))
    model = JointModel(s)
    v = model.linear.variables
    deficit = s.goals[0].target(s.capabilities, s.policy) - s.observation.ev_kwh
    model.linear.equality([(v["non_grid_cumulative"][-1], 1)], deficit - 1e-6)
    model.linear.row([(v["grid_cumulative"][-1], 1)], lower=.05)
    result = model.run(3)
    assert result["status"] == "Infeasible" and not result["feasible"]


def test_duplicate_goals_share_one_battery():
    s = tiny(hours=2, ev=24, house=0)
    s = replace(
        s,
        goals=(
            Goal("a", "Daily", s.intervals[-1].end, 45),
            Goal("b", "Trip-like manual target", s.intervals[-1].end, 50),
        ),
    )
    f = solve(s)
    assert 30 <= f["ev_energy"][-1] <= 30.1035 + 1e-6


def test_time_grid_full_horizon_partial_and_dst():
    start = datetime(2026, 10, 23, 0, tzinfo=UTC)
    assert len(time_grid(start)) == 2018
    partial = time_grid(start + timedelta(seconds=31))
    assert len(partial) == 2019
    assert (partial[-1] - partial[0]).total_seconds() == 168 * 3600
    assert max((b - a).total_seconds() for a, b in zip(partial, partial[1:])) <= 300


def test_planner_and_independent_validation_ignore_retired_phase_cooldown():
    s = tiny(hours=.5, house=0, pv=12)
    s = replace(s, capabilities=replace(s.capabilities, phase_dwell_seconds=900))
    model = JointModel(s, optional=True)
    for t, phase in ((1, "one"), (2, "three"), (3, "one")):
        model.linear.equality([(model.linear.variables[phase][t], 1)], 1)
    result = model.run(10)
    assert result["feasible"]
    assert validate(s, result["flows"]) == []
