"""Frozen accepted trajectories and physically interrupted phase delivery, offline only."""

from dataclasses import replace
from datetime import timedelta

import pytest

from energymanager.domain import Goal
from energymanager.execution import PHASE_SWITCH_SECONDS, freeze_execution
from energymanager.optimization import JointModel
from energymanager.validation import validate
from test_first_slice import tiny


def transition_model():
    s = tiny()
    s = replace(s, observation=replace(s.observation, ev_power_kw=1.38, monthly_peak_kw=8),
                goals=(Goal("g", "SYNTHETIC top-up", s.intervals[-1].end, target_soc_percent=44),))
    s = freeze_execution(s, None, {"phase": 1, "ready_at": s.intervals[0].start.isoformat()})
    m = JointModel(s)
    for t, phase in ((0, "one"), (1, "three")):
        for name in ("one", "three"):
            for key, value in ((name, float(name == phase)), ("amps_" + name, 6 if name == phase else 0)):
                index = m.linear.variables[key][t]
                m.linear.lower[index] = m.linear.upper[index] = value
    return s, m


def test_phase_change_has_real_energy_gap_and_independent_audit():
    s, m = transition_model()
    result = m.run(10)
    assert result["feasible"], result
    f = result["flows"]
    seconds = s.intervals[1].hours * 3600
    expected = 4.14 * (seconds - PHASE_SWITCH_SECONDS) / seconds
    assert f["grid_ev"][1] == pytest.approx(expected)
    assert f["ev_energy"][2] - f["ev_energy"][1] == pytest.approx(expected * s.intervals[1].hours * .9)
    assert validate(s, f) == []
    f["three"][1] = 0
    assert any("EV requested mode/current" in e for e in validate(s, f))
    f["three"][1] = 1
    f["grid_ev"][1] = 4.14
    assert any("EV mode power" in e for e in validate(s, f))


def test_new_snapshot_follows_old_schedule_not_a_constant_current_prefix():
    s = tiny(planning_budget_seconds=120)
    start = s.intervals[0].start
    split = start + timedelta(seconds=45)
    old = {"id": "old", "intervals": [{"start": start.isoformat(), "end": split.isoformat()},
            {"start": split.isoformat(), "end": s.intervals[-1].end.isoformat()}],
           "flows": {"one": [0, 1], "three": [1, 0], "amps_one": [0, 16], "amps_three": [6, 0]}}
    snapshot = freeze_execution(s, old, {"phase": 3, "ready_at": start.isoformat()})
    commitments = [snapshot.ev_commitment(t) for t in range(len(snapshot.intervals))]
    assert (4.14, 3) in commitments
    assert (3.68, 1) in commitments
    assert snapshot.ev_commitment(0) == (4.14, 3)
    after = next(t for t, i in enumerate(snapshot.intervals) if i.start == split)
    assert snapshot.ev_commitment(after) == (3.68, 1)
    assert snapshot.execution["commitment_until"] == (start + timedelta(seconds=135)).isoformat()


def test_initial_pending_phase_readiness_is_zero_delivery_commitment():
    s = tiny()
    ready = s.intervals[0].start + timedelta(seconds=47)
    snapshot = freeze_execution(s, None, {"phase": 3, "ready_at": ready.isoformat(),
                                         "pending": {"phase": "SYNTHETIC acknowledged request"}})
    assert all(snapshot.ev_commitment(t) == (0, 3) for t, i in enumerate(snapshot.intervals) if i.start < ready)
    assert next(i for i in snapshot.intervals if i.start == ready)


def test_frozen_trajectory_obeys_revoked_conditional_and_handover_authority():
    from test_publication_closed_loop import result_for, scheduled_flows
    s = tiny(planning_budget_seconds=120)
    old = result_for(s, scheduled_flows(s, [2.3] * len(s.intervals)))
    old["goals"] = []  # SYNTHETIC optional work, without an unmet required outcome.
    charger = {"phase": 1, "ready_at": s.intervals[0].start.isoformat()}
    frozen = freeze_execution(s, old, charger, conditional_valid=False)
    assert all((frozen.ev_commitment(t) or (0, 1))[0] == 0 for t in range(len(frozen.intervals)))
    old["goals"] = [{"deadline": s.intervals[-1].end.isoformat(), "target_kwh": s.observation.ev_kwh + 1}]
    required = freeze_execution(s, old, charger, conditional_valid=False)
    assert required.ev_commitment(0) == (2.3, 1)
    old["execution_handover"] = {"until": frozen.hold_until.isoformat(), "plan": dict(old),
                                "ev_valid": False, "conditional_valid": True, "ess_valid": True}
    frozen = freeze_execution(s, old, charger)
    assert all((frozen.ev_commitment(t) or (0, 1))[0] == 0 for t in range(len(frozen.intervals)))


def test_frozen_prefix_stops_at_remaining_task_quantity_not_its_old_timetable():
    from test_publication_closed_loop import result_for, scheduled_flows
    s = tiny(planning_budget_seconds=120)
    old = result_for(s, scheduled_flows(s, [2.3, 2.3] + [0.0] * (len(s.intervals) - 2)))
    target = old["flows"]["ev_energy"][2]
    s = replace(s, observation=replace(s.observation, ev_kwh=target - .01, ev_power_kw=2.3))
    frozen = freeze_execution(s, old, {"phase": 1, "ready_at": s.intervals[0].start.isoformat()})
    gain = sum((frozen.ev_commitment(t) or (0, 1))[0] * i.hours * s.capabilities.ev_efficiency
               for t, i in enumerate(frozen.intervals))
    assert gain == pytest.approx(.01, abs=1e-8)
    assert any(i.start < frozen.hold_until and frozen.ev_commitment(t) == (0.0, 1)
               for t, i in enumerate(frozen.intervals))


def test_instruction_identity_and_persisted_endpoint_survive_publication_ids():
    from copy import deepcopy
    from energymanager.control import FastControl
    from energymanager.domain import json_data
    from energymanager.execution import execution_identity
    from test_publication_closed_loop import result_for, scheduled_flows
    s = tiny()
    rates = [2.3, 2.3] + [0.0] * (len(s.intervals) - 2)
    target = 24 + sum(i.hours * power * .9 for i, power in zip(s.intervals, rates))
    s = replace(s, goals=(Goal("g", "SYNTHETIC late response", s.intervals[-1].end,
                               target_soc_percent=target / 60 * 100),))
    plan = result_for(s, scheduled_flows(s, rates))
    plan["execution_id"] = execution_identity(plan)
    control = FastControl(s.capabilities, s.policy)
    assert control.tick(s.observation, s.observation.at, plan, 1).current_a > 0
    restored = FastControl(s.capabilities, s.policy, json_data(control.ev_task))
    replacement = deepcopy(plan)
    replacement["id"] = "SYNTHETIC-new-publication-ID"
    assert execution_identity(replacement) == plan["execution_id"]
    at = s.observation.at + timedelta(minutes=10)
    behind = replace(s.observation, at=at, ev_kwh=target - .05)
    assert restored.tick(behind, at, replacement, 2).current_a > 0
    assert restored.ev_task["target"] == target
    assert restored.tick(behind, at, replacement, 2, ev_valid=False).current_a == 0
    assert restored.ev_task["target"] == target
    changed = deepcopy(replacement)
    changed["goals"][0]["revision"] += 1
    changed["execution_id"] = execution_identity(changed)
    assert changed["execution_id"] != replacement["execution_id"]
    assert restored.tick(behind, at, changed, 3).current_a == 0
