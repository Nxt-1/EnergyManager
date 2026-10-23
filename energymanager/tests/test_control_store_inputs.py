from dataclasses import replace
from datetime import timedelta

import pytest

from energymanager.adapters import JsonForecastAdapter, checked_url
from energymanager.control import Command, FastControl, GuardedActuator
from energymanager.domain import Capabilities, Goal, Policy, Snapshot, json_data
from energymanager.forecasts import background_sample, daily_goals, demo_snapshot
from energymanager.service import Application
from energymanager.store import Store


def test_snapshot_round_trip_and_goal_revision(tmp_path):
    s = demo_snapshot(hours=4, goals=())
    assert Snapshot.from_dict(json_data(s)).digest == s.digest
    store = Store(tmp_path / "test.sqlite")
    app = Application(store, snapshot=s)
    goal = app.upsert_goal(
        {
            "title": "Manual",
            "deadline": (s.observation.at + timedelta(hours=2)).isoformat(),
            "target_soc_percent": 70,
        }
    )
    approved = app.approve(goal.id, "granted", 7, goal.revision)
    assert approved.approved_peak_kw == 7
    app.requested.clear()
    app.changed("forecast")
    assert app.goals[0].approval_state == "granted"
    changed = (
        app.upsert_goal({**json_data(goal), "title": "Changed"})
        if False
        else app.upsert_goal(
            {
                "id": goal.id,
                "title": "Changed",
                "deadline": goal.deadline.isoformat(),
                "target_soc_percent": 80,
            }
        )
    )
    assert changed.revision == 2
    assert changed.approval_state == "none"
    with pytest.raises(ValueError):
        app.approve(goal.id, "granted", 7, 1)
    store.close()
    reopened = Store(tmp_path / "test.sqlite")
    assert reopened.get("goals")[0]["revision"] == 2
    reopened.close()


def test_quarter_prefix_protection_and_stale_data():
    s = demo_snapshot(hours=1, goals=())
    control = FastControl(s.capabilities, s.policy)
    at = s.observation.at.replace(minute=14, second=0)
    o = replace(
        s.observation, at=at, house_kw=5, pv_ac_kw=0, pv_dc_kw=0, ess_kwh=2.8, quarter_import_kwh=0.62
    )
    command = control.tick(o, at, None, 1)
    assert command.ev_kw == 0
    assert command.ess_kw == 0
    assert command.replan
    stale = control.tick(o, at + timedelta(seconds=31), None, 1)
    assert stale.ev_kw == stale.ess_kw == 0
    assert "stale" in stale.reason.lower()


class FakeClient:
    def __init__(self):
        self.calls = []

    async def service(self, domain, service, data):
        self.calls.append((domain, service, data))


async def test_goe_stop_confirm_phase_dwell_and_stale_generation():
    s = demo_snapshot(hours=1, goals=())
    o = replace(s.observation, ev_phases=1, ev_power_kw=0)
    client = FakeClient()
    actuator = GuardedActuator(
        client,
        {
            "force": "select.force",
            "phase": "select.phase",
            "current": "number.current",
            "ess_setpoint": "number.ess",
        },
        Capabilities(),
        enabled=True,
    )
    command = Command(1, "accepted", o.at, 4.14, -0.2, 3, 6, 4, "test")
    await actuator.apply(command, 2, o)
    assert client.calls == []
    await actuator.apply(command, 1, o)
    assert len(client.calls) == 2
    assert client.calls[0][2] == {"entity_id": "number.ess", "value": 200}
    assert client.calls[-1][2]["option"] == "1"
    await actuator.apply(replace(command, at=o.at + timedelta(seconds=9)), 1, o)
    assert not any(call[2].get("entity_id") == "select.phase" for call in client.calls)
    await actuator.apply(replace(command, at=o.at + timedelta(seconds=10)), 1, o)
    assert client.calls[-1][2] == {"entity_id": "select.phase", "option": "2"}
    await actuator.apply(replace(command, at=o.at + timedelta(seconds=11)), 1, replace(o, ev_phases=3))
    assert any(call[2].get("entity_id") == "number.ess" and call[2]["value"] == 200 for call in client.calls)
    previous = len([call for call in client.calls if call[2].get("entity_id") == "select.phase"])
    await actuator.apply(
        replace(command, at=o.at + timedelta(seconds=50), phases=1, current_a=6), 1, replace(o, ev_phases=3)
    )
    assert len([call for call in client.calls if call[2].get("entity_id") == "select.phase"]) == previous


def test_unknown_returns_and_manual_goals_do_not_withdraw():
    s = demo_snapshot(hours=48, goals=())
    trip = Goal("trip", "Unknown return", s.observation.at + timedelta(hours=4), kind="trip", distance_km=100)
    prepared = demo_snapshot(start=s.observation.at, hours=48, goals=(trip,))
    assert all(not i.available for i in prepared.intervals if i.start >= trip.deadline)
    assert sum(i.withdrawal_kwh for i in prepared.intervals) == 18
    manual = Goal("manual", "SoC", trip.deadline, 80)
    prepared = demo_snapshot(start=s.observation.at, hours=48, goals=(manual,))
    assert sum(i.withdrawal_kwh for i in prepared.intervals) == 0
    assert len(daily_goals(s.intervals[0].start, s.intervals[-1].end, Policy(), (trip,))) == 0


def test_configured_forecasts_have_full_horizon_and_energy_preserving_resampling():
    s = demo_snapshot(goals=())
    data = {
        "issued_at": s.observation.at.isoformat(),
        "revision": "local-1",
        "provenance": "SYNTHETIC adapter test",
        "intervals": [
            {
                "start": s.intervals[0].start.isoformat(),
                "end": s.intervals[-1].end.isoformat(),
                "house_kw": 0.5,
                "pv_ac_kw": 1,
                "pv_dc_kw": 2,
            }
        ],
    }
    result = JsonForecastAdapter.snapshot(
        data, s.observation, s.capabilities, s.policy, (), 1, s.observation.at
    )
    assert len(result.intervals) == 2017
    assert sum(i.pv_dc_kw * i.hours for i in result.intervals) == pytest.approx(336)
    data["intervals"][0]["end"] = s.intervals[-2].end.isoformat()
    with pytest.raises(ValueError, match="complete seven-day"):
        JsonForecastAdapter.snapshot(data, s.observation, s.capabilities, s.policy, (), 1, s.observation.at)
    with pytest.raises(ValueError, match="Remote"):
        checked_url("http://supervisor/core/api")
    assert background_sample(4.3, 3.3) == pytest.approx(1)
