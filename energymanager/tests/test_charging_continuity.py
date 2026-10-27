"""Synthetic overnight charging regressions, without optional cleanup time."""

from dataclasses import replace
from datetime import timedelta
from time import monotonic

import pytest

from energymanager.domain import Goal
from energymanager.incumbent import seed
from energymanager.optimization import JointModel
from energymanager.planner import Planner
from energymanager.validation import validate
from test_first_slice import tiny


def test_main_search_prefers_a_continuous_overnight_session():
    s = tiny(hours=8, ev=15.444, house=0.6, planning_budget_seconds=6)
    s = replace(s, capabilities=replace(s.capabilities, ev_capacity_kwh=46.8),
                observation=replace(s.observation, monthly_peak_kw=5.49),
                goals=(Goal("morning", "Synthetic 50 percent", s.intervals[-1].end, 50),))
    planner = Planner()
    planner.deadline = monotonic() + 6
    model = JointModel(s)
    warm = planner.starting_point(model)
    result = planner.run_model("required_reference", model, 5, warm)
    assert result["feasible"], result
    assert not validate(s, result["flows"])
    f = result["flows"]
    active = [a + b > 0.5 for a, b in zip(f["one"], f["three"])]
    assert sum(on and (t == 0 or not active[t - 1]) for t, on in enumerate(active)) == 1
    assert sum(f["three"]) == pytest.approx(0)
    power = [0.23 * (a + 3 * b) for a, b in zip(f["amps_one"], f["amps_three"])]
    assert max(power) <= 3.68 + 1e-6
    assert f["ev_energy"][-1] >= 23.4 - 1e-6
    assert any(stage["name"] == "required_reference_joint_continuity" for stage in planner.stages)
    assert model.value(model.economic, result["values"]) <= result["economic_baseline"] + s.policy.polish_tolerance_eur + 1e-6


def test_source_certificate_cannot_increase_charger_transition_score(monkeypatch):
    s = tiny(hours=3, ev=24, planning_budget_seconds=10)
    s = replace(s, goals=(Goal("morning", "Synthetic morning", s.intervals[-1].end, 45),))
    original = Planner.run_model
    compared = []

    def record(self, name, model, allowance, warm=None, **kwargs):
        before = model.value(model.continuity_objective(), warm) if warm else None
        result = original(self, name, model, allowance, warm, **kwargs)
        if name == "minimum_necessary_grid_certificate" and result["feasible"]:
            compared.append((before, model.value(model.continuity_objective(), result["values"])))
        return result

    monkeypatch.setattr(Planner, "run_model", record)
    result = Planner().plan(s)
    assert result["valid"], result
    assert not validate(s, result["flows"], result.get("service"))
    assert compared
    assert all(after <= before + 2e-6 for before, after in compared)


def test_short_window_retains_necessary_three_phase_charging():
    s = tiny(hours=0.5, ev=24, house=0.4, planning_budget_seconds=4)
    s = replace(s, observation=replace(s.observation, monthly_peak_kw=12, ev_phases=3),
                goals=(Goal("urgent", "Synthetic short window", s.intervals[-1].end, 45),))
    result = Planner().plan(s)
    assert result["valid"], result
    assert not validate(s, result["flows"])
    assert sum(result["flows"]["three"]) > 0
    assert result["flows"]["ev_energy"][-1] >= 27 - 1e-6


def test_joint_search_can_move_ess_support_to_avoid_ev_restarts():
    s = tiny(hours=3, ev=24, ess=4.8, planning_budget_seconds=8)
    s = replace(s, intervals=tuple(replace(i, house_kw=3.8 if i.start.minute % 30 >= 15 else .4)
                                   for i in s.intervals),
                observation=replace(s.observation, monthly_peak_kw=4),
                goals=(Goal("morning", "SYNTHETIC alternating loads", s.intervals[-1].end, 45),))
    # Create a valid economic incumbent with EV gaps and ESS use in the wrong quarters.
    restricted = JointModel(s)
    for t, interval in enumerate(s.intervals):
        if interval.house_kw > 3:
            for name in ("one", "three", "solar_dis_house", "solar_dis_ev"):
                restricted.linear.upper[restricted.linear.variables[name][t]] = 0
    incumbent = restricted.run(2)
    assert incumbent["feasible"] and not validate(s, incumbent["flows"])
    model = JointModel(s)
    incumbent["values"] = model.warm_from(incumbent["flows"])
    before = model.value(model.continuity_objective(), incumbent["values"])
    planner = Planner()
    planner.deadline = monotonic() + 6
    result = planner.prefer_continuity("required_reference", model, incumbent, 5)
    assert result["feasible"] and not validate(s, result["flows"])
    assert model.value(model.continuity_objective(), result["values"]) < before
    f = result["flows"]
    active = [a + b > .5 for a, b in zip(f["one"], f["three"])]
    assert sum(on and (t == 0 or not active[t - 1]) for t, on in enumerate(active)) == 1
    assert any(f["solar_dis_house"][t] + f["solar_dis_ev"][t] > .01
               for t, i in enumerate(s.intervals) if i.house_kw > 3)
    for objective, key in ((model.economic, "economic_baseline"), (model.cash, "cash_baseline")):
        assert model.value(objective, result["values"]) <= result[key] + .02 + 1e-6


def test_varying_available_power_changes_current_without_breaking_the_session():
    s = tiny(hours=3, ev=24, ess=2.8, planning_budget_seconds=7)
    s = replace(s, intervals=tuple(replace(i, house_kw=2 if i.start.minute % 30 >= 15 else .4)
                                   for i in s.intervals),
                observation=replace(s.observation, monthly_peak_kw=4),
                goals=(Goal("morning", "SYNTHETIC varying power", s.intervals[-1].end, 51),))
    planner = Planner()
    planner.deadline = monotonic() + 7
    model = JointModel(s)
    result = planner.run_model("required_reference", model, 6, planner.starting_point(model))
    assert result["feasible"] and not validate(s, result["flows"])
    f = result["flows"]
    active = [a + b > .5 for a, b in zip(f["one"], f["three"])]
    assert sum(on and (t == 0 or not active[t - 1]) for t, on in enumerate(active)) == 1
    amps = {round(a) for a, on in zip(f["amps_one"], active) if on}
    assert len(amps) > 1  # Constant power cannot supply this goal below the existing peak.
    assert sum(f["three"]) == pytest.approx(0)


def test_unavailable_window_keeps_a_genuinely_necessary_pause():
    s = tiny(hours=2, ev=24.2, planning_budget_seconds=5)
    start = s.intervals[0].start
    s = replace(s, observation=replace(s.observation, monthly_peak_kw=4),
                intervals=tuple(replace(i, available=not (start + timedelta(minutes=40)
                                                           <= i.start < start + timedelta(minutes=80)))
                                   for i in s.intervals),
                goals=(Goal("deadline", "SYNTHETIC availability", s.intervals[-1].end, 46),))
    result = Planner().plan(s)
    assert result["valid"] and not validate(s, result["flows"])
    f = result["flows"]
    assert all(f["one"][t] + f["three"][t] < 1e-6 for t, i in enumerate(s.intervals) if not i.available)
    active = [a + b > .5 for a, b in zip(f["one"], f["three"])]
    assert sum(on and (t == 0 or not active[t - 1]) for t, on in enumerate(active)) == 2


def test_held_three_phase_charging_remains_one_continued_session():
    s = tiny(hours=1, ev=24, house=.4, planning_budget_seconds=5)
    s = replace(s, observation=replace(s.observation, monthly_peak_kw=6, ev_phases=3, ev_power_kw=4.14),
                hold_until=s.intervals[2].start, hold_ev_kw=4.14, hold_phases=3,
                goals=(Goal("morning", "SYNTHETIC already charging", s.intervals[-1].end, 44),))
    planner = Planner()
    planner.deadline = monotonic() + 5
    model = JointModel(s)
    result = planner.run_model("required_reference", model, 4, planner.starting_point(model))
    assert result["feasible"] and not validate(s, result["flows"])
    f = result["flows"]
    assert f["three"][0] == pytest.approx(1) and sum(f["one"]) == pytest.approx(0)
    active = [a + b > .5 for a, b in zip(f["one"], f["three"])]
    assert not any(on and not active[t - 1] for t, on in enumerate(active) if t)


def test_minimum_current_and_peak_permission_can_require_two_sessions():
    s = tiny(hours=2, ev=24, ess=2.8, planning_budget_seconds=6)
    start = s.intervals[0].start
    s = replace(s, observation=replace(s.observation, monthly_peak_kw=4),
                intervals=tuple(replace(i, house_kw=3.8 if start + timedelta(minutes=45)
                                        <= i.start < start + timedelta(minutes=75) else .4)
                                for i in s.intervals),
                goals=(Goal("morning", "SYNTHETIC minimum-current limit", s.intervals[-1].end, 46),))
    result = Planner().plan(s)
    assert result["valid"] and not validate(s, result["flows"])
    assert result["summary"]["peak_kw"] <= 4 + 1e-6
    f = result["flows"]
    active = [a + b > .5 for a, b in zip(f["one"], f["three"])]
    assert sum(on and (t == 0 or not active[t - 1]) for t, on in enumerate(active)) == 2


def test_selected_phase_persists_through_off_slots_and_initial_switch_has_a_cost():
    s = tiny(hours=1)
    s = replace(s, observation=replace(s.observation, ev_phases=3))
    model = JointModel(s)
    values = [0.] * len(model.linear.lower)
    v = model.linear.variables
    # A three-phase session followed by off leaves the physical selector on3p.
    values[v["three"][0]], values[v["amps_three"][0]] = 1, 6
    canonical = model.canonical_values(values)
    assert sum(canonical[index] for index in v["phase_change"]) == 0
    assert all(canonical[index] == 1 for index in v["phase_setting"])
    assert canonical[v["variation"][0]] == pytest.approx(4.14)
    # Switching to1p in the very first interval must no longer be free.
    values[v["three"][0]], values[v["amps_three"][0]] = 0, 0
    values[v["one"][0]], values[v["amps_one"][0]] = 1, 6
    canonical = model.canonical_values(values)
    assert canonical[v["phase_change"][0]] == 1
    assert canonical[v["phase_restart"][0]] == 0  # Starting from rest needs no extra interrupted session.
    charging = JointModel(replace(s, observation=replace(s.observation, ev_power_kw=4.14)))
    canonical = charging.canonical_values(values)
    assert canonical[v["phase_restart"][0]] == 1  # A live selector change requires the real stop/resume sequence.


def test_later_economic_stage_cannot_replace_continuity_for_tiny_savings_or_stack_tolerance():
    s = tiny(hours=2)
    model = JointModel(s)
    # Explicit synthetic model values isolate selection policy from solver timing.
    def result(cost, cash, starts, reference=None):
        values = [0.] * len(model.linear.lower)
        # Economic and cash coefficients share grid_ev; terminal inventory separates economics.
        t = 1
        index = model.linear.variables["grid_ev"][t]
        values[index] = cash / model.cash[index]
        ev = model.linear.variables["ev_energy"][-1]
        values[ev] = (cash - cost) / -model.economic[ev]
        for k in starts:
            values[model.linear.variables["one"][k]] = 1
            values[model.linear.variables["amps_one"][k]] = 6
        values = model.canonical_values(values)
        flows = {name: [values[i] for i in indexes] for name, indexes in model.linear.variables.items()}
        reply = {"flows": flows, "values": values}
        if reference is not None:
            reply.update(economic_baseline=reference, cash_baseline=cash)
        return reply

    continuous = result(1, 2, [2, 3, 4, 5], reference=.99)
    fragmented = result(.995, 2, [2, 4, 6, 8], reference=.99)
    assert not Planner.prefer_result(continuous, model, fragmented, model)
    expensive = result(1.025, 2, [2, 3, 4, 5], reference=1.015)
    assert not Planner.prefer_result(fragmented, model, expensive, model)
    assert fragmented["economic_baseline"] == .99


def test_optional_search_uses_a_seed_within_the_reference_peak_envelope():
    s = tiny(hours=3, ev=24, house=.8)
    s = replace(s, goals=(Goal("morning", "SYNTHETIC starting schedule", s.intervals[-1].end, 45),))
    reference_model = JointModel(s)
    reference = seed(reference_model, 2.5)
    assert reference is not None
    flows = {name: [reference[i] for i in indexes] for name, indexes in reference_model.linear.variables.items()}
    model = JointModel(s, optional=True)
    model.add_optional_peak_limits(flows)
    assert seed(model) is None  # The automatic4kW ceiling exceeds the existing optional envelope.
    planner = Planner()
    planner.deadline = monotonic() + 10
    values = planner.starting_point(model)
    assert values is not None
    flows = {name: [values[i] for i in indexes] for name, indexes in model.linear.variables.items()}
    assert not validate(s, flows)
