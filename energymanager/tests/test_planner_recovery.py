"""Synthetic regressions for seed permissions and first-stage timeout recovery."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from energymanager.domain import Goal
from energymanager.incumbent import seed
from energymanager.optimization import JointModel
from energymanager.planner import Planner
from energymanager.validation import validate
from test_first_slice import tiny


def test_seed_respects_the_monthly_peak_reset_before_required_charging():
    snapshot = tiny(hours=8, ev=24, house=0.4)
    start = datetime(2026, 10, 31, 22, tzinfo=UTC)
    reset = datetime(2026, 10, 31, 23, tzinfo=UTC)  # Brussels local midnight.
    shift = start - snapshot.observation.at
    intervals = tuple(replace(i, start=i.start + shift, end=i.end + shift,
                              available=i.start + shift >= reset) for i in snapshot.intervals)
    snapshot = replace(snapshot, observation=replace(snapshot.observation, at=start, monthly_peak_kw=5.5),
                       intervals=intervals, goals=(Goal("morning", "Synthetic morning", intervals[-1].end, 50),))
    model = JointModel(snapshot)
    warm = seed(model)
    assert warm is not None, model.seed_issue
    flows = {name: [warm[index] for index in indexes] for name, indexes in model.linear.variables.items()}
    assert not validate(snapshot, flows)
    # October's already-incurred5.5kW must not authorize controlled purchases in November.
    for slots in model.quarters.values():
        if intervals[slots[0]].start >= reset:
            imports = sum((flows["grid_house"][t] + flows["grid_ev"][t]) * intervals[t].hours for t in slots)
            assert imports * 4 <= snapshot.policy.automatic_peak_kw + 1e-6
    assert flows["ev_energy"][-1] >= 30 - 1e-6


def test_reference_timeout_uses_remaining_budget_and_returns_a_valid_plan(monkeypatch):
    snapshot = tiny(hours=1, ev=24, house=0.4, planning_budget_seconds=5)
    snapshot = replace(snapshot, goals=(Goal("morning", "Synthetic morning", snapshot.intervals[-1].end, 42),))
    original = JointModel.run
    allowances = []

    def timed_out_once(self, seconds, **kwargs):
        allowances.append(seconds)
        if len(allowances) == 1:
            return {"status": "Time limit reached", "feasible": False, "seconds": 0}
        return original(self, seconds, **kwargs)

    monkeypatch.setattr(JointModel, "run", timed_out_once)
    result = Planner().plan(snapshot)
    assert result["valid"], result
    assert [stage["name"] for stage in result["stages"][:2]] == ["required_reference", "required_reference_recovery"]
    assert allowances[1] > allowances[0]
    assert allowances[1] <= snapshot.policy.planning_budget_seconds
    assert not validate(snapshot, result["flows"], result.get("service"))
    assert result["seconds"] <= snapshot.policy.planning_budget_seconds + 0.5


def test_no_reference_retry_after_the_global_deadline(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr("energymanager.planner.monotonic", lambda: clock[0])
    snapshot = tiny(planning_budget_seconds=5)

    def exhausted(self, seconds, **kwargs):
        clock[0] = 5.0
        return {"status": "Time limit reached", "feasible": False, "seconds": 5}

    monkeypatch.setattr(JointModel, "run", exhausted)
    result = Planner().plan(snapshot)
    assert not result["valid"]
    assert result["status"] == "Time limit reached"
    assert len(result["stages"]) == 1
    assert result.get("permission_proposals", []) == []
    assert result["seconds"] == pytest.approx(5)
