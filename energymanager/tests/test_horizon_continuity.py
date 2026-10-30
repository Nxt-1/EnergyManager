"""Synthetic coverage regressions: the same opportunity on every forecast day."""

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from time import monotonic

import pytest

from energymanager.charging_continuity import ChargingContinuity
from energymanager.domain import Goal, Interval, time_grid
from energymanager.optimization import JointModel
from energymanager.planner import Planner
from energymanager.validation import validate
from test_first_slice import tiny


def selected_week(day, *, grid=False, second_day=None):
    limit = (50, 65, 80, 90, 100, 70, 85)[day]
    count = 2 if second_day is not None else 1
    s = tiny(hours=168, ev=60 * limit / 100 - 1.242 * count, house=0, normal_soc_percent=limit)
    start = s.intervals[0].start
    days = (day,) if second_day is None else (day, second_day)
    def selected(interval):
        elapsed = (interval.start - start).total_seconds() / 3600
        return any(d * 24 + 10 <= elapsed < d * 24 + 12 for d in days)
    s = replace(s, intervals=tuple(replace(i, pv_ac_kw=3 if selected(i) and not grid else 0)
                                   for i in s.intervals),
                observation=replace(s.observation, monthly_peak_kw=4))
    if grid:
        deadline = start + timedelta(days=day, hours=12)
        s = replace(s, goals=(Goal("required", "SYNTHETIC week target", deadline, limit),))
    model = JointModel(s, optional=not grid, ceilings=None if grid else [60 * limit / 100] * len(s.intervals),
                       tight_ceilings=True)
    fixed = deepcopy(model)
    for t, interval in enumerate(s.intervals):
        minutes = (interval.start - start).total_seconds() / 60
        on = selected(interval) and int(minutes // 5) % 2 == 0
        for name, value in (("one", float(on)), ("three", 0), ("amps_one", 6 if on else 0), ("amps_three", 0)):
            index = fixed.linear.variables[name][t]
            fixed.linear.lower[index] = fixed.linear.upper[index] = value
    result = fixed.run(4)
    assert result["feasible"] and not validate(s, result["flows"])
    result["values"] = model.warm_from(result["flows"])
    return s, model, result


@pytest.mark.parametrize("day", range(7))
def test_every_forecast_day_gets_the_same_continuity_opportunity(day):
    s, model, original = selected_week(day, grid=day % 2 == 1)
    planner = Planner()
    planner.deadline = monotonic() + 5
    result = planner.review_continuity("synthetic_week", model, original, 4)
    assert not validate(s, result["flows"])
    assert model.linear.accepts(model.warm_from(result["flows"]))
    review = result["continuity_review"]
    assert [t for w in review["windows"] for t in range(w["first"], w["last"])] == list(range(len(s.intervals)))
    charged = [w for w in review["windows"] if w["sessions_before"]]
    assert len(charged) == 1
    assert charged[0]["sessions_before"] == 12
    assert charged[0]["sessions_after"] == 1, charged
    assert charged[0]["outcome"] == "improved"
    assert result["flows"]["ev_energy"][-1] == pytest.approx(original["flows"]["ev_energy"][-1], abs=1e-6)
    assert model.value(model.economic, result["values"]) <= result["economic_baseline"] + .02 + 1e-6
    assert model.value(model.cash, result["values"]) <= result["cash_baseline"] + .02 + 1e-6
    timing = ChargingContinuity.timing_terms(model)
    assert model.value(timing, result["values"]) <= model.value(timing, original["values"]) + 2e-6


def test_multiple_days_improve_without_undoing_the_first_or_stacking_allowances():
    s, model, original = selected_week(2, second_day=5)
    planner = Planner()
    planner.deadline = monotonic() + 15
    result = planner.review_continuity("synthetic_two_days", model, original, 14)
    assert not validate(s, result["flows"])
    charged = [w for w in result["continuity_review"]["windows"] if w["sessions_before"]]
    assert [w["sessions_after"] for w in charged] == [1, 1], charged
    assert model.value(model.economic, result["values"]) <= result["economic_baseline"] + .02 + 1e-6
    # A later certificate is not allowed to recreate either day's original gaps.
    certificate = deepcopy(model)
    certificate.add_continuity_limits()
    ChargingContinuity(model, result["flows"]).protect(certificate)
    assert certificate.linear.accepts(certificate.warm_from(result["flows"]))
    assert not certificate.linear.accepts(certificate.warm_from(original["flows"]))


def test_zero_budget_reports_unvisited_work_and_retains_valid_plan():
    s, model, original = selected_week(6)
    planner = Planner()
    planner.deadline = monotonic() + 1
    result = planner.review_continuity("synthetic_no_budget", model, original, 0)
    assert result["flows"] == original["flows"]
    assert not result["continuity_review"]["complete"]
    assert len(result["continuity_review"]["windows"]) >= 7
    assert any(w["outcome"] == "not_checked_budget" for w in result["continuity_review"]["windows"])
    assert not validate(s, result["flows"])


def test_partition_accounts_for_unavailability_and_preserves_overnight_sessions():
    s = tiny(hours=48)
    start = s.intervals[0].start
    # Brussels midnight is22:00UTC for this October fixture.
    s = replace(s, intervals=tuple(replace(i, available=not (start + timedelta(hours=30)
                                  <= i.start < start + timedelta(hours=32))) for i in s.intervals))
    flows = {name: [0.] * len(s.intervals) for name in ("one", "three")}
    for t, interval in enumerate(s.intervals):
        flows["one"][t] = float(start + timedelta(hours=21) <= interval.start < start + timedelta(hours=23))
    review = ChargingContinuity(JointModel(s), flows)
    assert [t for w in review.windows for t in range(w.first, w.last)] == list(range(len(s.intervals)))
    assert sum(review.sessions(w) for w in review.windows) == 1
    assert all(all(s.intervals[t].available == w.available for t in range(w.first, w.last)) for w in review.windows)
    assert any(not w.available for w in review.windows)


def test_solver_timeout_is_recorded_as_unfinished_not_a_necessary_pause(monkeypatch):
    s, model, original = selected_week(4)
    monkeypatch.setattr(JointModel, "run", lambda *a, **k:
                        {"feasible": False, "status": "Time limit reached", "seconds": 0})
    planner = Planner()
    planner.deadline = monotonic() + 3
    result = planner.review_continuity("synthetic_timeout", model, original, 2)
    assert result["flows"] == original["flows"]
    assert not result["continuity_review"]["complete"]
    charged = [w for w in result["continuity_review"]["windows"] if w["sessions_before"]]
    assert charged[0]["outcome"] == "unresolved_timeout"


def test_general_search_reduces_gaps_when_a_partial_departure_tail_prevents_one_session():
    s = tiny(hours=4, house=0, normal_soc_percent=80)
    start = s.intervals[0].start
    departure = start + timedelta(hours=3, minutes=54, seconds=22)
    grid = time_grid(start, 4, (departure,))
    intervals = tuple(Interval(a, b, 0, 3 if a < start + timedelta(hours=1)
                               or start + timedelta(hours=3, minutes=50) <= a < departure else 0,
                               pv_dc_kw=0, available=a < departure) for a, b in zip(grid, grid[1:]))
    profile = []
    for interval in intervals:
        minutes = (interval.start - start).total_seconds() / 60
        amps = 6 if minutes < 60 and int(minutes // 5) % 2 == 0 else 0
        profile.append(10 if start + timedelta(hours=3, minutes=50) <= interval.start < departure else amps)
    energy = sum(amps * .23 * .9 * interval.hours for amps, interval in zip(profile, intervals))
    s = replace(s, intervals=intervals, observation=replace(s.observation, ev_kwh=48 - energy),
                capabilities=replace(s.capabilities, ac_charge_kw=0, dc_charge_kw=0),
                goals=(Goal("departure", "SYNTHETIC partial departure", departure, 80),))
    model = JointModel(s, optional=True, ceilings=[48] * len(intervals), tight_ceilings=True)
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
    result = planner.review_continuity("synthetic_partial_tail", model, original, 3)
    assert not validate(s, result["flows"])
    window = result["continuity_review"]["windows"][0]
    assert window["sessions_before"] == 7
    assert window["sessions_after"] == 2
    assert window["improvement_retained"]
    assert window["outcome"] in ("improved", "unresolved_timeout", "no_improvement_found")
    assert window["attempts"][0]["kind"] in ("packed_relaxed", "packed")
    assert any(a["kind"] == "flexible" for a in window["attempts"])
    assert result["flows"]["ev_energy"][-1] == pytest.approx(original["flows"]["ev_energy"][-1], abs=1e-7)


def test_small_early_solar_burst_does_not_anchor_and_fragment_the_main_session():
    s = tiny(hours=3, ev=48 - 1.449, house=0, normal_soc_percent=80)
    start = s.intervals[0].start
    def useful(interval):
        minutes = (interval.start - start).total_seconds() / 60
        return 10 <= minutes < 20 or 60 <= minutes < 120
    s = replace(s, intervals=tuple(replace(i, pv_ac_kw=3 if useful(i) else 0) for i in s.intervals),
                capabilities=replace(s.capabilities, ac_charge_kw=0, dc_charge_kw=0))
    model = JointModel(s, optional=True, ceilings=[48] * len(s.intervals), tight_ceilings=True)
    fixed = deepcopy(model)
    for t, interval in enumerate(s.intervals):
        for name, value in (("one", float(useful(interval))), ("three", 0),
                            ("amps_one", 6 if useful(interval) else 0), ("amps_three", 0)):
            index = fixed.linear.variables[name][t]
            fixed.linear.lower[index] = fixed.linear.upper[index] = value
    original = fixed.run(2)
    assert original["feasible"] and not validate(s, original["flows"])
    original["values"] = model.warm_from(original["flows"])
    planner = Planner()
    planner.deadline = monotonic() + 4
    result = planner.review_continuity("synthetic_solar_bursts", model, original, 3)
    assert not validate(s, result["flows"])
    window = result["continuity_review"]["windows"][0]
    assert window["sessions_before"] == 2 and window["sessions_after"] == 1
    assert window["attempts"][0]["kind"] in ("packed_relaxed", "packed")
    assert window["attempts"][0]["status"] == "Infeasible"
    assert any(a["kind"] in ("consolidated_relaxed", "consolidated") and a.get("valid")
               for a in window["attempts"])
    assert result["flows"]["ev_energy"][-1] == pytest.approx(original["flows"]["ev_energy"][-1], abs=1e-7)


def test_saved_time_is_reused_for_an_earlier_unfinished_window(monkeypatch):
    s, model, original = selected_week(2, second_day=5)
    review = ChargingContinuity(model, original["flows"])
    windows = [w for w in review.windows if review.sessions(w)]
    first, later = windows[0].first, windows[1].first
    original_run = Planner.run_model
    later_visited = False
    def initial_timeout(self, name, *args, **kwargs):
        nonlocal later_visited
        if f"_window:{later}:" in name:
            later_visited = True
        if f"_window:{first}:" in name and not later_visited:
            return {"feasible": False, "status": "Time limit reached", "seconds": 0}
        return original_run(self, name, *args, **kwargs)
    monkeypatch.setattr(Planner, "run_model", initial_timeout)
    planner = Planner()
    planner.deadline = monotonic() + 10
    result = planner.review_continuity("synthetic_revisit", model, original, 9)
    assert later_visited and not validate(s, result["flows"])
    charged = [w for w in result["continuity_review"]["windows"] if w["sessions_before"]]
    assert [w["sessions_after"] for w in charged] == [1, 1]
    assert charged[0]["attempts"][0]["status"] == "Time limit reached"
    assert charged[0]["improvement_retained"]
    assert [t for w in result["continuity_review"]["windows"] for t in range(w["first"], w["last"])] == list(range(len(s.intervals)))


def weak_dispatch():
    s = tiny(hours=36, ev=48, house=1, normal_soc_percent=80)
    start = s.intervals[0].start
    s = replace(s, intervals=tuple(replace(i, pv_ac_kw=6 if i.start < start + timedelta(hours=4)
                                               or start + timedelta(hours=24) <= i.start < start + timedelta(hours=28)
                                               else 0)
                                   for i in s.intervals))
    model = JointModel(s, optional=True, ceilings=[48] * len(s.intervals), tight_ceilings=True)
    poor = deepcopy(model)
    for name in ("pv_store", "dc_store"):
        for index in poor.linear.variables[name]:
            poor.linear.upper[index] = 0
    original = poor.run(2)
    assert original["feasible"] and not validate(s, original["flows"])
    original["values"] = model.warm_from(original["flows"])
    return s, model, original


def test_dispatch_refinement_preserves_ev_schedule_and_recovers_household_solar_use():
    s, model, original = weak_dispatch()
    bounds = (list(model.linear.lower), list(model.linear.upper))
    planner = Planner()
    planner.deadline = monotonic() + 4
    planner.reference_flows = original["flows"]
    result = planner.prefer_dispatch(model, original, 3)
    assert not validate(s, result["flows"])
    assert model.linear.accepts(model.warm_from(result["flows"]))
    assert (model.linear.lower, model.linear.upper) == bounds
    for name in ("one", "three", "amps_one", "amps_three", "ev_energy"):
        assert result["flows"][name] == pytest.approx(original["flows"][name], abs=1e-6)
    assert sum(result["flows"]["grid_house"]) < sum(original["flows"]["grid_house"]) - 10
    assert model.value(model.economic, result["values"]) < model.value(model.economic, original["values"]) - 1


def test_dispatch_timeout_keeps_the_valid_selected_schedule(monkeypatch):
    s, model, original = weak_dispatch()
    evidence = deepcopy(original["flows"])
    monkeypatch.setattr(JointModel, "run", lambda *a, **k:
                        {"feasible": False, "status": "Time limit reached", "seconds": 0})
    planner = Planner()
    planner.deadline = monotonic() + 2
    result = planner.prefer_dispatch(model, original, 1)
    assert result["flows"] == evidence and not validate(s, result["flows"])


def test_surplus_above_a_goal_is_free_to_move_without_weakening_required_readiness():
    s = tiny(hours=4, house=0, normal_soc_percent=80)
    start = s.intervals[0].start
    departure = start + timedelta(hours=3, minutes=54, seconds=22)
    grid = time_grid(start, 4, (departure,))
    intervals = tuple(Interval(a, b, 0, 3, 0, available=a < departure) for a, b in zip(grid, grid[1:]))
    profile = []
    for i in intervals:
        minutes = (i.start - start).total_seconds() / 60
        amps = 6 if 10 <= minutes < 70 or 225 <= minutes < 230 else 0
        profile.append(10 if start + timedelta(minutes=230) <= i.start < departure else amps)
    energy = sum(amps * .23 * .9 * i.hours for amps, i in zip(profile, intervals))
    s = replace(s, intervals=intervals, observation=replace(s.observation, ev_kwh=48 - energy),
                capabilities=replace(s.capabilities, ac_charge_kw=0, dc_charge_kw=0),
                goals=(Goal("fulfilled", "SYNTHETIC already met target", departure, 50),))
    model = JointModel(s, optional=True, ceilings=[48] * len(intervals), tight_ceilings=True)
    fixed = deepcopy(model)
    for t, amps in enumerate(profile):
        for name, value in (("one", float(amps > 0)), ("three", 0), ("amps_one", amps), ("amps_three", 0)):
            index = fixed.linear.variables[name][t]
            fixed.linear.lower[index] = fixed.linear.upper[index] = value
    original = fixed.run(2)
    assert original["feasible"] and not validate(s, original["flows"])
    original["values"] = model.warm_from(original["flows"])
    planner = Planner()
    planner.deadline = monotonic() + 5
    result = planner.review_continuity("synthetic_surplus", model, original, 4)
    assert not validate(s, result["flows"])
    window = result["continuity_review"]["windows"][0]
    assert window["sessions_before"] == 2 and window["sessions_after"] == 1
    margin = s.checkpoint_index(departure - timedelta(minutes=s.policy.completion_margin_minutes))
    assert result["flows"]["ev_energy"][margin] >= 30
    assert result["flows"]["ev_energy"][-1] == pytest.approx(original["flows"]["ev_energy"][-1], abs=1e-7)
