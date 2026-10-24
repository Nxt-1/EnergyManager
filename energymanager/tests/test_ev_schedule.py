"""Synthetic EV calendar API requirements, independent of solver availability."""

from datetime import UTC, datetime, timedelta
from dataclasses import replace

from energymanager.domain import Goal
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
