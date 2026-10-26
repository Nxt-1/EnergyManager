"""Synthetic overnight charging regressions, without optional cleanup time."""

from dataclasses import replace
from time import monotonic

import pytest

from energymanager.domain import Goal
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
    assert any(stage["name"] == "required_reference_continuity" for stage in planner.stages)
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
