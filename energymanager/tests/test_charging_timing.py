"""Synthetic regressions for equal-benefit required charging start times."""

from dataclasses import replace
from time import monotonic

import pytest

from energymanager.charging_timing import ChargingTiming
from energymanager.domain import Goal
from energymanager.optimization import JointModel, LinearModel
from energymanager.planner import Planner
from energymanager.validation import accounting, validate
from test_first_slice import tiny


def delayed_session(*, blocked_until=0, health_until=0):
    s = tiny(hours=8, ev=20.592, house=.4, planning_budget_seconds=8)
    s = replace(s, capabilities=replace(s.capabilities, ev_capacity_kwh=46.8),
                observation=replace(s.observation, monthly_peak_kw=5.49),
                hold_until=s.intervals[2].end,
                intervals=tuple(replace(i, house_kw=5.0 if t < blocked_until else .4)
                                for t, i in enumerate(s.intervals)),
                goals=(Goal("morning", "SYNTHETIC morning target", s.intervals[-1].end, 50),))
    ceilings = [20.592 if t < health_until else 37.44 for t in range(len(s.intervals))]
    model = JointModel(s, optional=True, ceilings=ceilings, tight_ceilings=True)
    fixed = JointModel(s, optional=True, ceilings=ceilings, tight_ceilings=True)
    for t in range(len(s.intervals)):
        for name, value in (("one", float(39 <= t < 67)), ("three", 0.0),
                            ("amps_one", 6.0 if 39 <= t < 67 else 0.0), ("amps_three", 0.0)):
            index = fixed.linear.variables[name][t]
            fixed.linear.lower[index] = fixed.linear.upper[index] = value
    result = fixed.run(2)
    assert result["feasible"] and not validate(s, result["flows"])
    result["values"] = model.warm_from(result["flows"])
    return s, model, result


@pytest.mark.parametrize(("blocked_until", "health_until", "expected"), [(0, 0, 3), (18, 0, None), (0, 18, 18)])
def test_required_session_starts_at_first_equal_benefit_opportunity(blocked_until, health_until, expected):
    s, model, original = delayed_session(blocked_until=blocked_until, health_until=health_until)
    planner = Planner()
    planner.deadline = monotonic() + 5
    result = planner.prefer_earlier(model, original, 3)
    flows = result["flows"]
    assert not validate(s, flows)
    assert model.linear.accepts(model.warm_from(flows))
    first = next(t for t, power in enumerate(flows["grid_ev"]) if power > .1)
    if expected is None:
        # Quarter averaging and existing ESS dispatch can admit part of the high-load window.
        assert 3 <= first < 39
    else:
        assert first == expected
    for key in ("predicted_bill_eur", "imports_kwh", "peak_kw"):
        assert accounting(s, flows)[key] == pytest.approx(accounting(s, original["flows"])[key])
    for name in ("pv_ev", "solar_dis_ev", "ess_grid", "ess_solar", "grid_house", "grid_store"):
        assert flows[name] == pytest.approx(original["flows"][name])
    assert flows["ev_energy"][-1] == pytest.approx(original["flows"]["ev_energy"][-1])
    assert model.value(model.continuity_objective(), result["values"]) <= model.value(
        model.continuity_objective(), original["values"]) + 1e-6
    assert result["status"] == original["status"]  # Timing optimality is not economic optimality.


def test_earlier_checked_incumbent_survives_a_timing_solver_timeout(monkeypatch):
    s, model, original = delayed_session()
    monkeypatch.setattr(JointModel, "run", lambda *args, **kwargs: {
        "feasible": False, "status": "Time limit reached"})
    planner = Planner()
    planner.deadline = monotonic() + 3
    result = planner.prefer_earlier(model, original, 2)
    assert next(t for t, power in enumerate(result["flows"]["grid_ev"]) if power > .1) == 3
    assert not validate(s, result["flows"])


def test_timing_keeps_later_solar_allocation_and_does_not_add_grid_energy():
    s = tiny(hours=3, ev=24, pv=0, planning_budget_seconds=5)
    s = replace(s, goals=(Goal("morning", "SYNTHETIC PV waiting", s.intervals[-1].end, 46),),
                intervals=tuple(replace(i, pv_ac_kw=2 if t >= 18 else 0)
                                for t, i in enumerate(s.intervals)))
    model = JointModel(s)
    original = model.run(2)
    assert original["feasible"] and not validate(s, original["flows"])
    assert any(power > .1 for power in original["flows"]["pv_ev"])
    timing = ChargingTiming(model, original["flows"])
    planner = Planner()
    planner.deadline = monotonic() + 3
    result = planner.prefer_earlier(model, original, 2)
    assert not validate(s, result["flows"])
    for name in ("pv_ev", "solar_dis_ev", "pv_store", "pv_house", "export"):
        assert result["flows"][name] == pytest.approx(original["flows"][name])
    assert result["flows"]["grid_cumulative"][-1] == pytest.approx(original["flows"]["grid_cumulative"][-1])
    assert timing.model.linear.accepts(timing.model.warm_from(result["flows"]))


def test_full_candidate_check_handles_empty_rows_and_rejects_fractional_or_nonfinite_values():
    model = LinearModel()
    index = model.variable("synthetic_switch", 1, upper=1, integer=True)[0]
    model.row([])
    model.row([(index, 2)], upper=2)
    model.row([])
    assert model.accepts([1])
    assert not model.accepts([.5])
    assert not model.accepts([float("nan")])
    assert not model.accepts([float("inf")])
    model.row([], lower=1)
    assert not model.accepts([1])
