from dataclasses import replace
from datetime import timedelta

import pytest

from energymanager.control import FastControl
from energymanager.demo_plant import DemoPlant
from energymanager.domain import Goal
from energymanager.planner import Planner
from energymanager.publication import rebase
from energymanager.validation import validate
from test_first_slice import tiny


def test_elapsed_prefix_and_delivered_energy_are_not_repeated():
    s = tiny(hours=1, ev=24, house=0.4, planning_budget_seconds=5)
    hold = s.observation.at + timedelta(minutes=10)
    s = replace(s, hold_until=hold, goals=(Goal("manual", "Required goal", s.intervals[-1].end, 42),))
    result = Planner().plan(s)
    assert result["valid"], result
    assert sum(result["flows"]["grid_ev"][:2]) == pytest.approx(0)
    at = s.observation.at + timedelta(minutes=6)
    o = replace(s.observation, at=at, quarter_import_kwh=0.04)
    current, adopted, errors = rebase(s, result, o, at)
    assert not errors
    assert adopted["intervals"][0]["start"] == at.isoformat()
    assert adopted["flows"]["ev_energy"][0] == 24
    assert adopted["candidate_at_calculation"]["intervals"][0]["start"] == s.observation.at.isoformat()
    assert validate(current, adopted["flows"]) == []


def test_publication_reconciles_additional_measured_ess_headroom():
    s = tiny(hours=1, ev=50, ess=13, pv=4, dc=4, house=0, planning_budget_seconds=5)
    result = Planner().plan(s)
    at = s.observation.at + timedelta(minutes=1)
    o = replace(s.observation, at=at, ess_kwh=13.5)
    current, adopted, errors = rebase(s, result, o, at)
    assert not errors
    assert max(a + b for a, b in zip(adopted["flows"]["ess_solar"], adopted["flows"]["ess_grid"])) <= 11.20001
    assert validate(current, adopted["flows"]) == []


def test_real_plan_and_fast_control_complete_required_goal_in_closed_loop():
    s = tiny(hours=1, ev=24, house=0.4, planning_budget_seconds=6)
    s = replace(s, goals=(Goal("goal", "50 minute readiness", s.intervals[-1].end, 42),))
    result = Planner().plan(s)
    assert result["valid"]
    plant = DemoPlant(s)
    controller = FastControl(s.capabilities, s.policy)
    command = None
    for second in range(0, 3601, 5):
        at = s.observation.at + timedelta(seconds=second)
        o = plant.step(at, command)
        command = controller.tick(o, at, result, 1)
    assert plant.observation.ev_kwh >= 25.19
    assert plant.observation.monthly_peak_kw <= 4.0001
    assert plant.observation.quality == "SYNTHETIC"


def test_publication_releases_household_discharge_after_measured_balancing():
    s = tiny(hours=2, ev=50, ess=4, house=1, planning_budget_seconds=4)
    result = Planner().plan(s)
    assert result["valid"]
    at = s.observation.at + timedelta(minutes=2)
    o = replace(s.observation, at=at, ess_kwh=s.observation.ess_kwh - 0.04)
    current, adopted, errors = rebase(s, result, o, at)
    assert not errors, errors
    assert min(adopted["flows"]["ess_solar"]) >= -1e-8
    assert not validate(current, adopted["flows"])
    assert adopted["candidate_at_calculation"]["flows"] != adopted["flows"]
