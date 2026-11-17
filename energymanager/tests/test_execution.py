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


def test_live_ramp_template_integrates_extra_energy_and_joint_reallocation_is_audited():
    from energymanager.execution import transition_power

    s = tiny(hours=1 / 6)
    s = replace(s, observation=replace(s.observation, ev_power_kw=3.68, monthly_peak_kw=8),
                goals=(Goal("g", "SYNTHETIC ramp", s.intervals[-1].end, target_soc_percent=40.6),))
    s = freeze_execution(s, None, {"phase": 1, "current_a": 16, "ready_at": s.intervals[0].start.isoformat()})
    model = JointModel(s)
    for t, amps in enumerate((16, 6)):
        for name, value in (("one", 1), ("three", 0), ("amps_one", amps), ("amps_three", 0)):
            index = model.linear.variables[name][t]
            model.linear.lower[index] = model.linear.upper[index] = value
    result = model.run(10)
    assert result["feasible"], result
    flows = result["flows"]
    expected = 1.38 + .23 * 5 * sum(range(1, 10)) / (s.intervals[1].hours * 3600)
    assert transition_power(s, [16, 6], [0, 0])[1] == pytest.approx((expected, 15 * .23))
    assert sum(flows[k][1] for k in ("grid_ev", "pv_ev", "solar_dis_ev")) == pytest.approx(expected)
    assert validate(s, flows) == [] and model.linear.accepts(result["values"])
    assert result["status"] == "Transition candidate checked" and result["gap"] is None
    assert result["transition_scope"].startswith("fixed integer profile")
    broken = {k: list(v) for k, v in flows.items()}
    broken["grid_ev"][1] -= expected - 1.38
    assert any("EV mode power 1" in e for e in validate(s, broken))


def test_ramp_events_coalesce_across_short_boundaries_and_off_is_immediate():
    from energymanager.domain import Interval
    from energymanager.execution import transition_power

    s = tiny()
    at = s.intervals[0].start
    ends = [at + timedelta(seconds=x) for x in (3, 7, 20)]
    s = replace(s, observation=replace(s.observation, ev_power_kw=3.68),
                intervals=tuple(Interval(a, b, .4, 0, 0) for a, b in zip([at] + ends, ends)),
                execution={"initial_phase": 1, "charger": {"current_a": 16}})
    trace = transition_power(s, [6, 8, 0], [0, 0, 0])
    assert trace[0][0] == pytest.approx(15 * .23)
    assert trace[1][0] == pytest.approx((15 * 2 + 14 * 2) * .23 / 4)
    assert trace[2] == (0, 0)


def test_guarded_manual_phase_target_preserves_existing_power():
    from types import SimpleNamespace
    from energymanager.control import Command
    from energymanager.service import Application

    s = tiny()
    owner = SimpleNamespace(snapshot=s)
    command = Command(1, "synthetic", s.observation.at, 3.68, 0, 1, 16, 4, "synthetic")
    target = Application.phase_target(owner, command, 3)
    assert target.ev_kw == 0 and target.current_a == 0 and target.prepare_phase
    target = Application.phase_target(owner, replace(command, ev_kw=4.14, phases=3, current_a=6), 1)
    assert target.current_a == 16 and target.ev_kw <= 4.14


def test_phase_stop_straddles_five_minute_boundary_and_stop_from_sixteen_is_immediate():
    from energymanager.domain import Interval
    from energymanager.execution import transition_power

    s = tiny()
    at = s.intervals[0].start
    boundaries = [at, at + timedelta(seconds=290), at + timedelta(seconds=300), at + timedelta(seconds=600)]
    s = replace(s, intervals=tuple(Interval(a, b, .4, 0, 0) for a, b in zip(boundaries, boundaries[1:])),
                observation=replace(s.observation, ev_power_kw=1.38, monthly_peak_kw=8),
                goals=(Goal("g", "SYNTHETIC phase boundary", boundaries[-1], target_soc_percent=40.3),),
                execution={"initial_phase": 1, "charger": {"current_a": 6}, "commitments": []})
    trace = transition_power(s, [6, 0, 0], [0, 6, 6])
    assert trace[1] == (0, 0)
    assert trace[2][0] == pytest.approx(4.14 * 130 / 300)
    model = JointModel(s)
    for t, (one, three) in enumerate(((6, 0), (0, 6), (0, 6))):
        for name, value in (("amps_one", one), ("amps_three", three)):
            index = model.linear.variables[name][t]
            model.linear.lower[index] = model.linear.upper[index] = value
    result = model.run(10)
    assert result["feasible"], result
    assert validate(s, result["flows"]) == []
    assert sum(result["flows"][name][2] for name in ("grid_ev", "pv_ev", "solar_dis_ev")) == pytest.approx(trace[2][0])
    stopped = transition_power(replace(s, observation=replace(s.observation, ev_power_kw=3.68),
                                       execution={"initial_phase": 1, "charger": {"current_a": 16}}),
                               [16, 0, 0], [0, 0, 0])
    assert stopped[0][0] == pytest.approx(3.68) and stopped[1:] == [(0, 0), (0, 0)]


def test_historical_protocol_one_audits_recorded_math_without_new_live_admission():
    from energymanager.execution import transition_power
    from energymanager.publication import admit
    from test_publication_closed_loop import result_for

    current, _ = transition_model()
    assert current.execution["protocol"] == 2
    historical = replace(current, execution={**current.execution, "protocol": 1, "phase_switch_seconds": 130.})
    original_digest = historical.digest
    model = JointModel(historical)
    for t, phase in ((0, "one"), (1, "three")):
        for name in ("one", "three"):
            for key, value in ((name, float(name == phase)), ("amps_" + name, 6 if name == phase else 0)):
                index = model.linear.variables[key][t]
                model.linear.lower[index] = model.linear.upper[index] = value
    result = model.run(5)
    assert result["feasible"], result
    seconds = historical.intervals[1].hours * 3600
    power = sum(result["flows"][name][1] for name in ("grid_ev", "pv_ev", "solar_dis_ev"))
    assert power == pytest.approx(4.14 * (seconds - 130) / seconds)
    assert validate(historical, result["flows"]) == []
    accepted_before_upgrade = {**result_for(historical, result["flows"]), "execution": historical.execution}
    refused, errors = admit(historical, accepted_before_upgrade, historical.observation, historical.observation.at)
    assert any("protocol 1 is audit-only" in error for error in errors)
    assert not refused["admission"]["passed"]
    fresh = freeze_execution(replace(historical, execution=None), accepted_before_upgrade,
                             {"phase": 1, "ready_at": historical.observation.at.isoformat()})
    assert fresh.execution["protocol"] == 2 and fresh.execution["phase_switch_seconds"] == 180
    assert historical.digest == original_digest
    historical_live_shape = replace(historical, observation=replace(historical.observation, ev_power_kw=3.68))
    assert transition_power(historical_live_shape, [16, 6], [0, 0])[1][0] == pytest.approx(1.38)
    modern = replace(historical_live_shape, execution={**fresh.execution, "charger": {"current_a": 16}})
    assert transition_power(modern, [16, 6], [0, 0])[1][0] > 1.38


@pytest.mark.parametrize("protocol", [99, "2"])
def test_unknown_explicit_execution_protocol_is_not_silently_legacy(protocol):
    current, model = transition_model()
    result = model.run(5)
    assert result["feasible"]
    unknown = replace(current, execution={**current.execution, "protocol": protocol})
    assert any("Unsupported frozen EV execution protocol" in error for error in validate(unknown, result["flows"]))
    with pytest.raises(ValueError, match="Unsupported frozen EV execution protocol"):
        JointModel(unknown)
    with pytest.raises(ValueError, match="Unsupported frozen EV execution protocol"):
        freeze_execution(unknown, None, {"phase": 1})
