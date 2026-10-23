from dataclasses import replace
from datetime import timedelta

import pytest

from energymanager.control import Command, FastControl, GuardedActuator
from energymanager.domain import Goal, PeakPermission, json_data
from energymanager.optimization import JointModel
from energymanager.planner import Planner
from energymanager.service import Application
from energymanager.store import Store
from energymanager.validation import validate
from test_first_slice import tiny


def test_fulfilled_goal_cannot_lend_its_approved_peak_to_a_later_goal():
    s = tiny(hours=0.5, ev=24, house=0.4)
    fulfilled = Goal(
        "done",
        "Already ready",
        s.intervals[-1].end,
        40,
        approved_peak_kw=8,
        approval_state="granted",
        approval_revision=1,
    )
    later = Goal("later", "Other goal", s.intervals[-1].end, 47)
    s = replace(s, goals=(fulfilled, later))
    result = JointModel(s).run(5)
    assert result["status"] == "Infeasible"


def test_ess_can_restore_a_late_required_ev_goal_without_borrowing_a_peak_grant():
    s = tiny(hours=1, ev=24, house=1, planning_budget_seconds=14)
    s = replace(
        s,
        intervals=tuple(
            replace(i, available=i.start >= s.observation.at + timedelta(minutes=45)) for i in s.intervals
        ),
        goals=(Goal("late", "Late arrival readiness", s.intervals[-1].end, 41.4),),
    )
    result = Planner().plan(s)
    assert result["valid"], result
    assert result["goals"][0]["shortfall_kwh"] < 1e-5, result["stages"]
    assert sum(result["flows"]["grid_store"]) > 0
    assert result["summary"]["peak_kw"] <= 4.0001
    assert any("restores" in r["text"] for r in result["reasons"])
    assert not validate(s, result["flows"])


def ess_permission_case():
    s = tiny(hours=0.5, ev=50, house=3.8, planning_budget_seconds=15)
    # Only five minutes remain in the current quarter; its ten-minute prefix is real input.
    at = s.observation.at + timedelta(minutes=10)
    intervals = tuple(
        replace(i, house_kw=5 if i.start >= s.observation.at + timedelta(minutes=15) else 3.8)
        for i in s.intervals
        if i.end > at
    )
    return replace(
        s,
        observation=replace(s.observation, at=at, house_kw=3.8, quarter_import_kwh=3.8 / 6),
        intervals=intervals,
    )


def test_ess_higher_ceiling_is_a_scoped_request_and_automatic_work_continues(tmp_path):
    s = ess_permission_case()
    result = Planner().plan(s)
    assert result["valid"], result
    proposals = [p for p in result.get("permission_proposals", []) if p.get("kind") == "ess_peak"]
    assert proposals, result["stages"]
    proposal = proposals[0]
    assert 4 < proposal["proposed_peak_kw"] < 5
    assert sum(result["flows"]["grid_store"]) > 0
    store = Store(tmp_path / "permissions.sqlite")
    app = Application(store, snapshot=s, policy=s.policy)
    app.update_issues(result)
    grant = app.approve(proposal["goal_id"], "granted", proposal["proposed_peak_kw"], 1)
    assert isinstance(grant, PeakPermission)
    permitted = replace(s, peak_permissions=(grant,))
    approved = Planner().plan(permitted)
    assert approved["valid"]
    assert approved["summary"]["comparison_eur"] < result["summary"]["comparison_eur"] - 0.01
    assert approved["summary"]["peak_kw"] < result["summary"]["peak_kw"] - 0.01
    assert not validate(permitted, approved["flows"])
    assert validate(s, approved["flows"])
    assert app.build_snapshot().peak_permissions == (grant,)
    store.close()


def test_unallocated_ess_inventory_balances_and_ev_invalidation_releases_only_ev_reserve():
    s = tiny(hours=1, ess=7, house=1)
    solved = JointModel(s).run(5)
    plan = {
        "id": "reservation",
        "flows": solved["flows"],
        "intervals": json_data(s.intervals),
        "reasons": [],
        "goals": [],
        "reservations": [
            {"solar_ev_kwh": 4, "solar_house_kwh": 0.1, "grid_house_kwh": 0}
            for _ in range(len(s.intervals) + 1)
        ],
    }
    control = FastControl(s.capabilities, s.policy)
    held = control.tick(s.observation, s.observation.at, plan, 1)
    released = control.tick(s.observation, s.observation.at, plan, 2, ev_valid=False)
    assert held.ess_kw == pytest.approx(1)
    assert released.ess_kw == pytest.approx(1)
    # At only four usable kWh the EV reservation blocks household preferences.
    low = replace(s.observation, ess_kwh=6.8)
    assert FastControl(s.capabilities, s.policy).tick(low, low.at, plan, 1).ess_kw == 0
    assert FastControl(s.capabilities, s.policy).tick(
        low, low.at, plan, 2, ev_valid=False
    ).ess_kw == pytest.approx(1)


async def test_revocation_between_service_writes_blocks_force_start_and_phase_cancel_recovers():
    s = tiny()
    generation = 1

    class Client:
        def __init__(self):
            self.calls = []

        async def service(self, domain, service, data):
            nonlocal generation
            self.calls.append(data)
            if data["entity_id"] == "current":
                generation = 2

    client = Client()
    actuator = GuardedActuator(
        client,
        {k: k for k in ("force", "phase", "current", "ess_setpoint")},
        s.capabilities,
        True,
        generation=lambda: generation,
    )
    command = Command(1, "plan", s.observation.at, 1.38, 0, 1, 6, 4, "test")
    await actuator.apply(command, 1, s.observation)
    assert not any(c.get("option") == "2" for c in client.calls)
    generation = 3
    stopped = replace(command, generation=3, phases=3, current_a=0, ev_kw=0)
    await actuator.apply(stopped, 3, s.observation)
    assert actuator.target_phase == 3
    await actuator.apply(replace(command, generation=3), 3, s.observation)
    assert actuator.target_phase is None
    assert actuator.phase == 1


def test_rejecting_a_proposed_extension_preserves_an_existing_grant(tmp_path):
    s = tiny(hours=2)
    store = Store(tmp_path / "reject.sqlite")
    app = Application(store, snapshot=s)
    goal = app.upsert_goal(
        {"title": "Goal", "deadline": s.intervals[-1].end.isoformat(), "target_soc_percent": 70}
    )
    app.approve(goal.id, "granted", 5, 1)
    rejected = app.approve(goal.id, "rejected", 6, 1)
    assert rejected.approved_peak_kw == 5 and rejected.approval_state == "granted"
    assert rejected.rejected_peak_kw == 6
    store.close()
