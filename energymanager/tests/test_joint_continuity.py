"""Joint source freedom and truthful bounded-search diagnostics on synthetic inputs."""

from copy import deepcopy
from dataclasses import replace
from time import monotonic

import pytest

from energymanager.charging_continuity import ChargingContinuity
from energymanager.optimization import JointModel
from energymanager.planner import Planner
from energymanager.validation import validate
from test_first_slice import tiny
from test_optional_continuity import fragmented


@pytest.mark.parametrize("ac_eff,dc_eff,held", [(.95, .98, False), (.90, .99, False), (.95, .98, True)])
def test_original_model_continuous_points_remain_eligible_with_source_redistribution(ac_eff, dc_eff, held):
    s = tiny(hours=30, ev=48 - 1.242, pv=1.1, dc=2, house=.5, normal_soc_percent=80)
    start = s.intervals[0].start
    s = replace(s, capabilities=replace(s.capabilities, ac_charge_efficiency=ac_eff, dc_efficiency=dc_eff),
                intervals=tuple(replace(i, house_kw=.50 if i.start.minute < 30 else .52) for i in s.intervals))
    if held:
        s = replace(s, observation=replace(s.observation, ev_power_kw=1.38),
                    hold_ev_kw=1.38, hold_phases=1, hold_until=s.intervals[1].start)
    model = JointModel(s, optional=True, ceilings=[48] * len(s.intervals), tight_ceilings=True)
    def fixed_profile(continuous, boundary=None, solar=None):
        point = deepcopy(model)
        for t, interval in enumerate(s.intervals):
            minutes = (interval.start - start).total_seconds() / 60
            on = minutes < 60 if continuous else minutes < 120 and int(minutes // 5) % 2 == 0
            for name, value in (("one", float(on)), ("three", 0), ("amps_one", 6 if on else 0), ("amps_three", 0)):
                index = point.linear.variables[name][t]
                point.linear.lower[index] = point.linear.upper[index] = value
        if boundary is not None:
            index = point.linear.variables["ess_solar"][boundary]
            shift = .01 if solar < .1 else -.01
            point.linear.lower[index] = point.linear.upper[index] = solar + shift
            index = point.linear.variables["grid_house"][2]
            point.linear.lower[index] = .0006
        result = point.run(4)
        assert result["feasible"] and not validate(s, result["flows"])
        assert model.linear.accepts(model.warm_from(result["flows"]))
        return result
    original = fixed_profile(False)
    review = ChargingContinuity(model, original["flows"])
    window = review.windows[0]
    point = fixed_profile(True, window.last, original["flows"]["ess_solar"][window.last])
    local = review.candidate(window, None)
    values = local.warm_from(point["flows"])
    assert local.linear.accepts(values)
    assert point["flows"]["ev_energy"][-1] == pytest.approx(original["flows"]["ev_energy"][-1])
    assert abs(point["flows"]["ess_solar"][window.last] - original["flows"]["ess_solar"][window.last]) == pytest.approx(.01)
    for objective in (model.economic, model.cash):
        assert model.value(objective, model.warm_from(point["flows"])) <= model.value(objective, model.warm_from(original["flows"])) + .02
    old_imports = sum(sum(original["flows"][name][t] for name in ("grid_ev", "grid_house", "grid_store"))
                      * i.hours for t, i in enumerate(s.intervals[:window.last]))
    new_imports = sum(sum(point["flows"][name][t] for name in ("grid_ev", "grid_house", "grid_store"))
                      * i.hours for t, i in enumerate(s.intervals[:window.last]))
    assert new_imports > old_imports + 1e-6


def test_failed_shortcut_cannot_erase_an_unfinished_broad_search(monkeypatch):
    s, model, original = fragmented()
    planner = Planner()
    planner.deadline = monotonic() + 5
    packed_calls = 0
    def simulate(self, name, *args, **kwargs):
        nonlocal packed_calls
        if name.endswith(":packed_relaxed"):
            packed_calls += 1
            if packed_calls == 2:
                self.deadline = monotonic()
        status = "Time limit reached" if name.endswith((":single", ":flexible")) else "Infeasible"
        return {"feasible": False, "status": status, "seconds": 0}
    monkeypatch.setattr(Planner, "run_model", simulate)
    result = planner.review_continuity("synthetic_timeout_history", model, original, 4)
    review = result["continuity_review"]
    window = review["windows"][0]
    assert window["attempts"][-1]["kind"] == "packed_relaxed"
    assert window["attempts"][-1]["status"] == "Infeasible"
    assert window["outcome"] == "unresolved_timeout" and window["had_timeouts"]
    assert review["coverage_complete"] and not review["complete"]
    assert review["unresolved_windows"] == 1
    assert result["flows"] == original["flows"] and not validate(s, result["flows"])


def test_only_a_valid_current_broad_result_resolves_residual_search():
    _, model, original = fragmented()
    current = ChargingContinuity(model, original["flows"])
    record = {"sessions_before": 12, "attempts": [
        {"kind": "single", "status": "Time limit reached"},
        {"kind": "flexible", "status": "Optimal", "valid": True, "result_revision": 3},
        {"kind": "packed", "status": "Infeasible"}]}
    current.summarize(current.windows[0], record, 3)
    assert not record["unresolved"] and record["outcome"] == "no_improvement_found"
    assert record["had_timeouts"]  # Raw history is still available.
    current.summarize(current.windows[0], record, 4)
    assert record["unresolved"] and record["outcome"] == "unresolved_timeout"


@pytest.mark.parametrize("bound_allows_warm", [False, True])
def test_exhausted_stage_skips_solver_and_checks_bounds_before_using_warm(monkeypatch, bound_allows_warm):
    s, model, original = fragmented()
    def unexpected(*args, **kwargs):
        raise AssertionError("Exhausted stages must not start another solver")
    monkeypatch.setattr(JointModel, "run", unexpected)
    planner = Planner()
    planner.deadline = monotonic() + 10
    values = model.warm_from(original["flows"])
    cost = model.value(model.economic, values)
    result = planner.run_model("synthetic_exhausted", model, 0, values, objective=model.economic,
                               bounds=[(model.economic, cost + 1 if bound_allows_warm else cost - 1)])
    assert result["status"] == "Time limit reached"
    assert result["skipped_budget"]
    assert result["feasible"] == bound_allows_warm
    if result["feasible"]:
        assert not validate(s, result["flows"])


def test_incompatible_relaxed_dispatch_is_rejected_before_integer_fallback(monkeypatch):
    s, model, original = fragmented()
    planner = Planner()
    planner.deadline = monotonic() + 6
    run_model = Planner.run_model
    def incompatible(self, name, *args, **kwargs):
        result = run_model(self, name, *args, **kwargs)
        if name.endswith(":packed_relaxed") and result["feasible"]:
            result = deepcopy(result)
            # An invalid relaxed dispatch must not be repaired into publishable power.
            result["flows"]["solar_dis_house"][0] += .1
        return result
    monkeypatch.setattr(Planner, "run_model", incompatible)
    result = planner.review_continuity("synthetic_relaxation_rejection", model, original, 5)
    window = result["continuity_review"]["windows"][0]
    assert window["attempts"][0]["kind"] == "packed_relaxed"
    assert window["attempts"][0]["rejected"]
    assert "integer_dispatch" in window["attempts"][0]["rejection_errors"]
    assert any(a["kind"] == "packed" and a.get("valid") and a.get("warm_from_relaxation")
               for a in window["attempts"])
    assert window["sessions_after"] == 1
    assert model.linear.accepts(model.warm_from(result["flows"]))
    assert not validate(s, result["flows"])
