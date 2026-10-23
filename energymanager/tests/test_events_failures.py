import asyncio
from dataclasses import replace
from time import monotonic

import pytest

from energymanager.control import Command, FakeActuator
from energymanager.domain import Goal, Observation
from energymanager.forecasts import demo_snapshot
from energymanager.planner import Planner
from energymanager.service import Application
from energymanager.store import Store
from test_first_slice import tiny


class ProtectiveActuator(FakeActuator):
    """Signal delivery of the revocation command through the real control path."""

    def __init__(self) -> None:
        super().__init__()
        self.dispatched = asyncio.Event()

    async def apply(self, command: Command, generation: int, observation: Observation) -> None:
        await super().apply(command, generation, observation)
        if command.generation == generation and command.reason.startswith("Affected instruction revoked:"):
            self.dispatched.set()


def test_timeout_and_malformed_solution_are_not_infeasibility(monkeypatch):
    s = tiny()
    planner = Planner()
    monkeypatch.setattr(
        planner, "run_model", lambda *a, **k: {"status": "Time limit reached", "feasible": False}
    )
    result = planner.plan(s)
    assert not result["valid"]
    assert result["status"] == "Time limit reached"
    assert result.get("permission_proposals", []) == []
    monkeypatch.setattr(
        planner, "run_model", lambda *a, **k: {"status": "Optimal", "feasible": True, "flows": {}}
    )
    result = planner.plan(s)
    assert result["status"] == "invalid_solution"
    assert not result["valid"]


async def test_real_solve_does_not_block_control_and_disconnect_cannot_be_resurrected(tmp_path):
    short = tiny(hours=2, ev=24, house=0.4, planning_budget_seconds=3)
    short = replace(short, goals=(Goal("charge", "Charge", short.intervals[-1].end, 45),))
    accepted = Planner().plan(short)
    assert accepted["valid"]
    full = demo_snapshot(
        start=short.observation.at,
        policy=replace(short.policy, planning_budget_seconds=4, control_period_seconds=0.02),
        goals=(),
    )
    store = Store(tmp_path / "events.sqlite")
    app = Application(store, policy=full.policy, snapshot=full)
    actuator = ProtectiveActuator()
    app.actuator = actuator
    app.accepted = accepted
    app.ev_valid = app.ess_valid = True
    await app.start()
    try:
        end = monotonic() + 2
        while app.status != "planning" and monotonic() < end:
            await asyncio.sleep(0.01)
        assert app.status == "planning"
        await asyncio.sleep(0.05)
        app.observe(replace(app.observation, connected=False, at=app.now()))
        disconnect_revision = app.revision
        # Observe dispatch itself; an unrelated sleep also measures shared-runner scheduling delays.
        await asyncio.wait_for(actuator.dispatched.wait(), timeout=2)
        assert app.status == "planning"
        assert not store.decisions(), "Protective control must precede completion of the real solve"
        assert not app.ev_valid
        assert app.ess_valid
        assert app.last_command["ev_kw"] == 0
        assert app.last_command["generation"] == disconnect_revision
        assert app.response_seconds
        end = monotonic() + 8
        while monotonic() < end and not any(d["disposition"] == "rejected_stale" for d in store.decisions()):
            await asyncio.sleep(0.05)
        assert any(d["disposition"] == "rejected_stale" for d in store.decisions())
        assert not app.ev_valid
    finally:
        await app.close()
        store.close()


def test_oversized_trip_keeps_post_return_state_unknown():
    s = tiny(hours=4, ev=60, house=0, planning_budget_seconds=10)
    trip = Goal(
        "external",
        "Long trip",
        s.intervals[11].end,
        kind="trip",
        distance_km=450,
        return_at=s.intervals[23].end,
    )
    after = Goal("after", "Goal after external charging", s.intervals[-1].end, 70)
    from energymanager.forecasts import apply_requirements

    goals = (trip, after)
    s = replace(
        s,
        goals=goals,
        intervals=apply_requirements(s.intervals, goals, s.observation, s.capabilities, s.policy),
    )
    result = Planner().plan(s)
    assert result["valid"], result
    assert result["goals"][0]["external_charging_required"]
    assert result["goals"][1]["planned_kwh"] is None
    assert result["goals"][1]["status"] == "unknown_return_state"
    assert not result["summary"]["ev_terminal_state_known"]
    assert sum(result["flows"]["grid_ev"]) == pytest.approx(0)
    assert all(i["available"] is False for i in result["intervals"][12:])
