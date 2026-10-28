"""Synthetic EV calendar API requirements, independent of solver availability."""

from datetime import UTC, datetime, timedelta
from dataclasses import replace

import pytest

from energymanager.domain import Goal, json_data
from energymanager.service import Application
from energymanager.store import Store
from test_first_slice import tiny


def test_schedule_requirements_exist_before_a_plan_and_follow_current_journeys(tmp_path):
    snapshot = tiny()
    application = Application(Store(tmp_path / "synthetic.sqlite"), snapshot=snapshot, policy=snapshot.policy)
    now = datetime(2026, 10, 24, 10, tzinfo=UTC)
    application.now = lambda: now
    trip = Goal("trip", "SYNTHETIC overnight", now + timedelta(hours=10), 0, "trip",
                distance_km=120, return_at=now + timedelta(hours=23))
    application.goals = (trip,)
    before = application.state()
    assert before["accepted"] is None
    assert before["ev_plan_valid"] is False
    assert before["goals"] == [before["schedule_goals"][0]]
    mornings = [goal for goal in before["schedule_goals"] if goal["kind"] == "daily"]
    assert len(mornings) == 6  # Sunday morning falls inside the expected away period.
    assert mornings[0]["deadline"] == "2026-10-26T06:00:00+00:00"
    assert all("planned_kwh" not in goal for goal in mornings)
    application.goals = (replace(trip, return_at=None),)
    assert all(goal["kind"] != "daily" for goal in application.state()["schedule_goals"])
    application.goals = ()
    assert len(application.state()["schedule_goals"]) == 7
    application.store.close()


def test_calendar_retains_morning_approval_and_does_not_persist_generated_goals(tmp_path):
    snapshot = tiny()
    application = Application(Store(tmp_path / "synthetic.sqlite"), snapshot=snapshot, policy=snapshot.policy)
    application.now = lambda: datetime(2026, 10, 24, 10, tzinfo=UTC)
    application.goals = ()
    morning = application.state()["schedule_goals"][0]
    approved = {**morning, "approval_state": "granted", "approved_peak_kw": 5, "approval_revision": 1}
    application.store.put("daily_approvals", {morning["id"]: approved})
    assert application.state()["schedule_goals"][0] == approved
    assert application.goals == ()
    assert application.store.get("goals") is None
    application.store.close()


def test_finished_manual_goals_leave_both_views_and_remain_in_history_after_restart(tmp_path):
    snapshot = tiny()
    now = snapshot.observation.at + timedelta(days=3)
    app = Application(Store(tmp_path / "synthetic-retirement.sqlite"), snapshot=snapshot)
    app.now = lambda: now
    finished = Goal("old-trip", "SYNTHETIC finished journey", now - timedelta(days=2), kind="trip",
                    distance_km=44, return_at=now - timedelta(days=2, hours=-3))
    expired = Goal("old-target", "SYNTHETIC elapsed target", now - timedelta(hours=1))
    future = Goal("future", "SYNTHETIC future target", now + timedelta(hours=1))
    app.goals = (finished, expired, future)
    app.store.put("goals", app.goals)
    app.ev_valid = app.ess_valid = True
    app.store.put("issues", {"old": {"goal_id": finished.id}, "future": {"goal_id": future.id}})
    app.archive_finished_goals(now)
    assert app.goals == (future,)
    assert app.ev_valid and app.ess_valid
    assert app.requested.is_set()
    assert {g["id"] for g in app.state()["goals"]} == {future.id}
    assert not {finished.id, expired.id} & {g["id"] for g in app.state()["schedule_goals"]}
    archived = [e["body"] for e in app.store.events() if e["kind"] == "goal_archived"]
    assert {e["goal"]["id"] for e in archived} == {finished.id, expired.id}
    assert next(e["goal"] for e in archived if e["goal"]["id"] == finished.id) == json_data(finished)
    assert list(app.store.get("issues")) == ["future"]
    revision = app.revision
    app.archive_finished_goals(now)
    assert app.revision == revision
    restarted = Application(app.store, snapshot=snapshot)
    assert restarted.goals == (future,)
    app.store.close()


def test_last_goal_retirement_stays_empty_on_restart_without_injecting_demo_goals(tmp_path):
    snapshot = tiny()
    app = Application(Store(tmp_path / "synthetic-empty.sqlite"), snapshot=snapshot)
    now = snapshot.observation.at
    app.goals = (Goal("past", "SYNTHETIC elapsed", now - timedelta(seconds=1)),)
    app.archive_finished_goals(now)
    assert app.store.get("goals") == []
    resurrecting_snapshot = replace(snapshot, goals=(Goal("sample", "SYNTHETIC sample", now + timedelta(hours=1)),))
    restarted = Application(app.store, snapshot=resurrecting_snapshot)
    assert restarted.goals == ()
    assert Application(app.store).goals == ()
    app.store.close()


@pytest.mark.parametrize("case", ["underway", "unknown_return", "external_return", "future", "calendar", "routed"])
def test_retirement_preserves_active_requirements_and_source_owned_records(tmp_path, case):
    snapshot = tiny()
    now = snapshot.observation.at
    goal = Goal("trip", "SYNTHETIC journey", now - timedelta(hours=1), kind="trip", distance_km=44,
                return_at=now + timedelta(hours=1))
    if case == "unknown_return":
        goal = replace(goal, return_at=None)
    elif case == "external_return":
        goal = replace(goal, distance_km=1000, return_at=now - timedelta(minutes=1))
    elif case == "future":
        goal = replace(goal, deadline=now + timedelta(minutes=1))
    elif case in ("calendar", "routed"):
        goal = replace(goal, id="calendar-fixture" if case == "calendar" else "journey-fixture",
                       return_at=now - timedelta(minutes=1))
    app = Application(Store(tmp_path / "synthetic-active.sqlite"), snapshot=snapshot)
    app.now = lambda: now
    app.goals = (goal,)
    app.archive_finished_goals(now)
    assert app.goals == (goal,)
    assert not app.requested.is_set()
    projected = {g["id"] for g in app.state()["goals"]}
    assert (goal.id in projected) == (case not in ("calendar", "routed"))
    app.store.close()


@pytest.mark.parametrize("blocked", [None, "stale", "settling", "unknown", "unknown_soc", "before_departure", "disconnected"])
def test_only_a_fresh_observed_home_state_can_retire_an_unknown_return(tmp_path, blocked):
    snapshot = tiny()
    now = snapshot.observation.at
    app = Application(Store(tmp_path / "synthetic-return.sqlite"), snapshot=snapshot)
    app.now = lambda: now
    goal = Goal("trip", "SYNTHETIC unknown return", now - timedelta(hours=1), kind="trip", distance_km=44)
    app.goals = (goal,)
    observed = replace(snapshot.observation, at=now)
    if blocked in ("settling", "unknown"):
        observed = replace(observed, quality=blocked)
    elif blocked == "stale":
        observed = replace(observed, at=now - timedelta(minutes=2))
    elif blocked == "unknown_soc":
        observed = replace(observed, ev_state_known=False)
    elif blocked == "before_departure":
        observed = replace(observed, at=goal.deadline)
    elif blocked == "disconnected":
        observed = replace(observed, connected=False)
    app.archive_finished_goals(now, observed)
    assert bool(app.goals) == (blocked is not None)
    if blocked is None:
        assert app.store.get("goals") == []
        # A later unplug or restart cannot reactivate this finished manual request.
        app.archive_finished_goals(now + timedelta(hours=1), replace(observed, connected=False))
        assert not app.goals
        assert not Application(app.store, snapshot=snapshot).goals
    app.store.close()


def test_observe_retires_a_returned_manual_trip_without_stopping_other_valid_goals(tmp_path):
    snapshot = tiny()
    app = Application(Store(tmp_path / "synthetic-observe.sqlite"), snapshot=snapshot)
    app.now = lambda: snapshot.observation.at
    app.goals = (Goal("trip", "SYNTHETIC returned", snapshot.observation.at - timedelta(hours=1), kind="trip"),)
    app.ev_valid = app.ess_valid = True
    app.observe(snapshot.observation)
    assert not app.goals
    assert app.ev_valid and app.ess_valid
    app.store.close()


@pytest.mark.asyncio
async def test_control_tick_retires_elapsed_goals_without_a_page_request_or_solver(tmp_path):
    import asyncio
    snapshot = tiny()
    app = Application(Store(tmp_path / "synthetic-tick.sqlite"), snapshot=snapshot)
    app.goals = (Goal("past", "SYNTHETIC elapsed", snapshot.observation.at - timedelta(hours=1)),)
    task = asyncio.create_task(app.control_loop())
    try:
        await asyncio.sleep(.05)
        assert not app.goals
        assert app.store.get("goals") == []
        assert app.last_command is not None
        assert any(e["kind"] == "goal_archived" for e in app.store.events())
    finally:
        app.shutdown = True
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        app.store.close()
