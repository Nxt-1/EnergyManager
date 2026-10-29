"""Synthetic selected-work continuity checks across active charging limits."""

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from time import monotonic

import pytest

from energymanager.domain import Goal, Interval, time_grid
from energymanager.optimization import JointModel
from energymanager.planner import Planner
from energymanager.validation import validate
from test_first_slice import tiny


def fragmented(*, limit=80, named=True, required=False, held=False, staged=False):
    capacity = 60
    energy = 1.242  # Twelve five-minute 6A intervals at90% efficiency.
    initial = capacity * limit / 100 - energy
    s = tiny(hours=2, ev=initial, ess=2.8, pv=3, house=.4, normal_soc_percent=70)
    if named:
        target = limit if required else 40
        s = replace(s, goals=(Goal("target", "SYNTHETIC selected work", s.intervals[-1].end, target),))
    if held:
        s = replace(s, observation=replace(s.observation, ev_power_kw=1.38),
                    hold_ev_kw=1.38, hold_phases=1, hold_until=s.intervals[1].start)
    ceilings = [capacity * limit / 100] * len(s.intervals)
    if staged:
        ceilings = [initial + energy / 2 if i.start < s.intervals[0].start + timedelta(hours=1)
                    else capacity * limit / 100 for i in s.intervals]
    model = JointModel(s, optional=not required, ceilings=None if required else ceilings, tight_ceilings=True)
    fixed = deepcopy(model)
    for t in range(len(s.intervals)):
        minutes = (s.intervals[t].start - s.intervals[0].start).total_seconds() / 60
        on = int(minutes // 5) % 2 == 0
        for name, value in (("one", float(on)), ("three", 0),
                            ("amps_one", 6 if on else 0), ("amps_three", 0)):
            index = fixed.linear.variables[name][t]
            fixed.linear.lower[index] = fixed.linear.upper[index] = value
    result = fixed.run(2)
    assert result["feasible"] and not validate(s, result["flows"])
    result["values"] = model.warm_from(result["flows"])
    return s, model, result


def starts(flows):
    active = [a + b > .5 for a, b in zip(flows["one"], flows["three"])]
    return sum(on and (t == 0 or not active[t - 1]) for t, on in enumerate(active))


@pytest.mark.parametrize("limit", [50, 65, 80, 90, 100])
@pytest.mark.parametrize("named", [True, False])
def test_optional_capture_smooths_with_the_actual_model_ceiling(limit, named):
    s, model, original = fragmented(limit=limit, named=named)
    planner = Planner()
    planner.deadline = monotonic() + 4
    result = planner.prefer_continuity("synthetic_optional", model, original, 3, single_only=True)
    assert starts(original["flows"]) == 12
    assert starts(result["flows"]) == 1
    assert model.linear.accepts(model.warm_from(result["flows"]))
    assert not validate(s, result["flows"])
    assert max(result["flows"]["ev_energy"]) <= 60 * limit / 100 + 1e-6
    assert result["flows"]["ev_energy"][-1] == pytest.approx(original["flows"]["ev_energy"][-1], abs=2e-6)
    assert max(result["flows"]["grid_ev"]) < 1e-6
    for objective, key in ((model.economic, "economic_baseline"), (model.cash, "cash_baseline")):
        assert model.value(objective, result["values"]) <= result[key] + s.policy.polish_tolerance_eur + 1e-6


@pytest.mark.parametrize("limit", [65, 90, 100])
def test_required_targets_keep_their_authority(limit):
    s, model, original = fragmented(limit=limit, required=True)
    planner = Planner()
    planner.deadline = monotonic() + 4
    result = planner.prefer_continuity("synthetic_required", model, original, 3, single_only=True)
    assert starts(result["flows"]) == 1
    assert not validate(s, result["flows"])
    assert result["flows"]["ev_energy"][-1] >= 60 * limit / 100 - 1e-6
    assert max(result["flows"]["ev_energy"]) <= s.capabilities.ev_capacity_kwh + 1e-6


def test_already_running_optional_charge_continues_without_an_inserted_restart():
    s, model, original = fragmented(limit=90, held=True)
    planner = Planner()
    planner.deadline = monotonic() + 4
    result = planner.prefer_continuity("synthetic_held", model, original, 3, single_only=True)
    assert not validate(s, result["flows"])
    assert result["flows"]["one"][0] == 1
    assert starts(result["flows"]) == 1
    assert sum(result["flows"]["three"]) == 0


def test_smoothing_does_not_remove_an_inherited_time_varying_ceiling():
    s, model, original = fragmented(staged=True)
    planner = Planner()
    planner.deadline = monotonic() + 3
    result = planner.prefer_continuity("synthetic_staged", model, original, 2, single_only=True)
    assert model.linear.accepts(model.warm_from(result["flows"]))
    assert not validate(s, result["flows"])
    assert max(result["flows"]["ev_energy"][:14]) <= s.observation.ev_kwh + .621 + 1e-6
    assert 1 <= starts(result["flows"]) < starts(original["flows"])


def test_continuity_timeout_retains_the_checked_original_candidate(monkeypatch):
    s, model, original = fragmented(limit=65)
    evidence = deepcopy(original["flows"])
    monkeypatch.setattr(JointModel, "run", lambda *a, **k:
                        {"feasible": False, "status": "Time limit reached", "seconds": 0})
    planner = Planner()
    planner.deadline = monotonic() + 3
    result = planner.prefer_continuity("synthetic_timeout", model, original, 2, single_only=True)
    assert result["flows"] == evidence
    assert not validate(s, result["flows"])
    assert result["status"] == original["status"]


def test_repeated_continuity_does_not_rebase_and_stack_the_cost_allowance():
    s, model, original = fragmented(limit=65)
    economic = model.value(model.economic, original["values"])
    cash = model.value(model.cash, original["values"])
    original.update(economic_baseline=economic - .015, cash_baseline=cash)
    planner = Planner()
    planner.deadline = monotonic() + 6
    first = planner.prefer_continuity("synthetic_first", model, original, 2, single_only=True)
    second = planner.prefer_continuity("synthetic_second", model, first, 2, single_only=True)
    assert not validate(s, second["flows"])
    assert second["economic_baseline"] <= economic - .015 + 1e-6
    assert model.value(model.economic, second["values"]) <= economic - .015 + .02 + 1e-6


def test_irregular_first_charging_interval_preserves_quantity_and_can_be_smoothed():
    s = tiny(hours=2, pv=3, dc=2, normal_soc_percent=65)
    start = s.intervals[0].start
    release = start + timedelta(seconds=100.063)
    grid = time_grid(start, 2, (release,))
    intervals = tuple(Interval(a, b, .4, 3, 2) for a, b in zip(grid, grid[1:]))
    profile = []
    for interval in intervals:
        minutes = (interval.start - start).total_seconds() / 60
        on = interval.start >= release and (minutes < 10 or int(minutes // 5) % 2 == 1)
        profile.append(16 if interval.start == release else 14 if on and minutes < 10 else 6 if on else 0)
    energy = sum(amps * .23 * .9 * interval.hours for amps, interval in zip(profile, intervals))
    s = replace(s, intervals=intervals, observation=replace(s.observation, ev_kwh=39 - energy),
                hold_until=release, hold_ev_kw=0)
    model = JointModel(s, optional=True, ceilings=[39] * len(intervals), tight_ceilings=True)
    fixed = deepcopy(model)
    for t, amps in enumerate(profile):
        for name, value in (("one", float(amps > 0)), ("three", 0), ("amps_one", amps), ("amps_three", 0)):
            index = fixed.linear.variables[name][t]
            fixed.linear.lower[index] = fixed.linear.upper[index] = value
    original = fixed.run(2)
    assert original["feasible"] and not validate(s, original["flows"])
    original["values"] = model.warm_from(original["flows"])
    planner = Planner()
    planner.deadline = monotonic() + 4
    result = planner.prefer_continuity("synthetic_partial", model, original, 3, single_only=True)
    assert starts(result["flows"]) == 1
    assert not validate(s, result["flows"])
    assert model.linear.accepts(model.warm_from(result["flows"]))
    assert result["flows"]["ev_energy"][-1] == pytest.approx(original["flows"]["ev_energy"][-1], abs=1e-7)


@pytest.mark.parametrize("limit", [50, 65, 95])
def test_full_planner_retains_continuity_when_economic_search_returns_fragmented_work(limit, monkeypatch):
    s, _, fragmented_result = fragmented(limit=limit)
    s = replace(s, policy=replace(s.policy, normal_soc_percent=limit, planning_budget_seconds=6))
    original_run = JointModel.run

    def fragmented_economic_search(self, seconds, **kwargs):
        objective = kwargs.get("objective")
        if self.optional and (objective is None or objective == self.economic):
            values = self.warm_from(fragmented_result["flows"])
            if self.linear.accepts(values):
                return {"feasible": True, "status": "Time limit reached", "seconds": 0,
                        "values": values, "flows": fragmented_result["flows"]}
        return original_run(self, seconds, **kwargs)

    monkeypatch.setattr(JointModel, "run", fragmented_economic_search)
    result = Planner().plan(s)
    assert result["valid"], result
    assert not validate(s, result["flows"])
    coverage = result["continuity_review"]["windows"]
    assert [t for w in coverage for t in range(w["first"], w["last"])] == list(range(len(s.intervals)))
    assert all(w["sessions_final"] <= w["sessions_after"] for w in coverage)
    assert starts(result["flows"]) == 1
    assert result["flows"]["ev_energy"][-1] >= 60 * limit / 100 - 1e-6
    # A proven scarce-solar window can legitimately authorise the higher ceiling.
    # Continuity must inherit that authority rather than hard-code the normal limit.
    for t in range(len(s.intervals)):
        exceptional = any(left <= t < right for left, right in result["exceptional_windows"])
        ceiling = 60 if exceptional else 60 * limit / 100
        assert result["flows"]["ev_energy"][t + 1] <= ceiling + 1e-6
    assert max(result["flows"]["grid_ev"]) < 1e-6
    assert result["seconds"] <= s.policy.planning_budget_seconds + .5
