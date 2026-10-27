"""SYNTHETIC EV/go-e faults and fake button/phone endpoints; no installation access."""

import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from energymanager.control import Command, GuardedActuator, StaleDispatch
from energymanager.domain import json_data
from energymanager.ev_faults import EVFaults, incident_report
from energymanager.notifications import Notifications, NotificationTarget
from energymanager.live_inputs import LiveInputs
from energymanager.measurements import MeasurementOptions
from energymanager.service import Application
from energymanager.store import Store
from test_first_slice import tiny


class SyntheticHA:
    def __init__(self, app):
        self.app = app
        self.calls = []
        self.entities = {key: f"sensor.{key}" for key in ("ev_soc", "connected", "ev_kw", "ev_phases")}
        self.inputs = LiveInputs(self.entities, MeasurementOptions.installation(), 30)
        self.fail_notify = False
        self.fail_reboot = False
        self.stop_entered = self.stop_release = None

    async def entity_state(self, entity):
        if entity == "sensor.bad":
            raise RuntimeError("SYNTHETIC unavailable input")
        return {"entity_id": entity, "state": "0", "last_updated": self.app.now().isoformat(),
                "attributes": {"unit_of_measurement": "W"}}

    async def service(self, domain, service, data):
        self.calls.append((domain, service, data))
        if domain == "select" and self.stop_entered:
            self.stop_entered.set()
            await self.stop_release.wait()
        if domain == "button":
            saved = self.app.store.get("ev_incident")
            assert saved["reboot_attempts"] == 1 and saved["status"] == "rebooting"
            if self.fail_reboot:
                raise RuntimeError("SYNTHETIC reboot response lost")
        if domain == "notify" and self.fail_notify:
            raise RuntimeError("SYNTHETIC phone unavailable")


def installation(tmp_path, reboot="button.synthetic_reboot"):
    snapshot = tiny()
    store = Store(tmp_path / "synthetic.sqlite")
    app = Application(store, snapshot=snapshot, policy=snapshot.policy, demo=False)
    clock = [datetime(2026, 10, 25, 12, tzinfo=UTC)]
    app.now = lambda: clock[0]
    app.observation = replace(snapshot.observation, at=clock[0], quality="measured", connected=True,
                              ev_phases=1, ev_power_kw=0)
    ha = SyntheticHA(app)
    app.ha = ha
    app.actuator = GuardedActuator(ha, {"force": "select.force", "phase": "select.phase",
        "current": "number.current", "ess_setpoint": "number.ess"}, snapshot.capabilities,
        enabled=True, generation=lambda: app.revision)
    app.notifications = Notifications(store, ha, NotificationTarget("notify.synthetic_phone", "action"))
    manager = EVFaults(app, reboot, {"charger_error": "sensor.bad"})
    app.ev_faults = manager
    return app, ha, manager, clock


def advance(app, clock, seconds, power=0):
    clock[0] += timedelta(seconds=seconds)
    app.observation = replace(app.observation, at=clock[0], ev_power_kw=power)
    app.current_command = Command(app.revision, "synthetic-plan", clock[0], 1.38, 0, 1, 6, 4, "SYNTHETIC charge")
    return app.current_command


async def detect(app, clock):
    await app.actuator.apply(advance(app, clock, 0), app.revision, app.observation)
    await app.actuator.apply(advance(app, clock, 30), app.revision, app.observation)
    await app.actuator.apply(advance(app, clock, 1), app.revision, app.observation)
    await app.actuator.apply(advance(app, clock, 90), app.revision, app.observation)
    assert app.actuator.delivery_fault


async def test_fault_timestamp_one_persisted_reboot_and_verified_charging(tmp_path):
    app, ha, manager, clock = installation(tmp_path)
    await detect(app, clock)
    fault = dict(manager.current)
    assert instant_seconds(fault["detected_at"], fault["started_at"]) == 90
    await manager.step()
    assert manager.current["status"] == "rebooting" and manager.current["reboot_attempts"] == 1
    assert [call for call in ha.calls if call[0] == "button"] == [
        ("button", "press", {"entity_id": "button.synthetic_reboot"})]
    await app.actuator.apply(advance(app, clock, 59), app.revision, app.observation)
    await manager.step()
    assert app.actuator.delivery_fault
    advance(app, clock, 1)
    await manager.step()
    assert manager.current["status"] == "verifying" and not app.actuator.delivery_fault
    await app.actuator.apply(advance(app, clock, 1), app.revision, app.observation)
    advance(app, clock, 1, power=1.2)
    await manager.step()
    clock[0] += timedelta(seconds=10)
    await manager.step()
    assert manager.current["status"] == "verifying"  # Repeated cached power is not recovery evidence.
    advance(app, clock, 0, power=1.2)
    await manager.step()
    assert manager.current["status"] == "recovered" and manager.current["resolved_at"]
    assert not any(call[0] == "notify" for call in ha.calls)
    assert app.store.ev_incident(fault["id"])["status"] == "recovered"
    app.store.close()


def instant_seconds(later, earlier):
    return (datetime.fromisoformat(later) - datetime.fromisoformat(earlier)).total_seconds()


async def test_failed_retry_stops_and_notifies_once_with_retryable_delivery(tmp_path):
    app, ha, manager, clock = installation(tmp_path)
    await detect(app, clock)
    await manager.step()
    advance(app, clock, 60)
    await manager.step()
    await app.actuator.apply(advance(app, clock, 0), app.revision, app.observation)
    await app.actuator.apply(advance(app, clock, 30), app.revision, app.observation)
    await app.actuator.apply(advance(app, clock, 1), app.revision, app.observation)
    await app.actuator.apply(advance(app, clock, 90), app.revision, app.observation)
    assert manager.current["status"] == "unresolved" and app.actuator.delivery_fault
    ha.fail_notify = True
    await manager.step()
    assert manager.current["notification"] == "retrying"
    await manager.step()
    assert len([call for call in ha.calls if call[0] == "notify"]) == 1
    ha.fail_notify = False
    advance(app, clock, 60)
    await manager.step()
    assert manager.current["notification"] == "delivered"
    advance(app, clock, 60)
    await manager.step()
    assert len([call for call in ha.calls if call[0] == "notify"]) == 2
    assert len([call for call in ha.calls if call[0] == "button"]) == 1
    message = [call[2]["message"] for call in ha.calls if call[0] == "notify"][-1]
    assert "13:02:01 CET" in message and manager.current["id"] in message
    app.store.close()


async def test_restart_and_unknown_reboot_outcome_never_replay_button(tmp_path):
    app, ha, manager, clock = installation(tmp_path)
    await detect(app, clock)
    ha.fail_reboot = True
    with pytest.raises(RuntimeError):
        await manager.step()
    assert app.store.get("ev_incident")["reboot_attempts"] == 1
    restored = EVFaults(app, "button.synthetic_reboot")
    assert app.actuator.delivery_fault
    await restored.step()
    assert len([call for call in ha.calls if call[0] == "button"]) == 1
    advance(app, clock, 60)
    await restored.step()
    assert restored.current["status"] == "verifying"
    restarted_again = EVFaults(app, "button.synthetic_reboot")
    assert restarted_again.current["status"] == "unresolved" and app.actuator.delivery_fault
    await restarted_again.step()
    assert len([call for call in ha.calls if call[0] == "button"]) == 1
    app.store.close()


@pytest.mark.parametrize("reason", ["missing_button", "disabled", "stale", "disconnected", "power"])
async def test_reboot_requires_mapping_authority_fresh_connection_and_zero_power(tmp_path, reason):
    app, ha, manager, clock = installation(tmp_path, "" if reason == "missing_button" else "button.synthetic_reboot")
    await detect(app, clock)
    if reason == "disabled":
        app.actuator.enabled = False
    elif reason == "stale":
        clock[0] += timedelta(seconds=120)
    elif reason == "disconnected":
        advance(app, clock, 120)
        app.observation = replace(app.observation, connected=False)
    elif reason == "power":
        advance(app, clock, 120, power=1)
    await manager.step()
    assert manager.current["status"] == "unresolved"
    assert not any(call[0] == "button" for call in ha.calls)
    assert app.actuator.delivery_fault
    app.store.close()


async def test_disable_during_recovery_stop_revokes_button_press(tmp_path):
    app, ha, manager, clock = installation(tmp_path)
    await detect(app, clock)
    ha.stop_entered, ha.stop_release = asyncio.Event(), asyncio.Event()
    task = asyncio.create_task(manager.step())
    await ha.stop_entered.wait()
    app.actuator.enabled = False
    app.revision += 1
    ha.stop_release.set()
    with pytest.raises(StaleDispatch):
        await task
    assert manager.current["reboot_attempts"] == 0 and not any(call[0] == "button" for call in ha.calls)
    app.store.close()


async def test_acknowledge_requires_current_incident_and_cooldown_survives_it(tmp_path):
    app, ha, manager, clock = installation(tmp_path)
    await detect(app, clock)
    await manager.step()
    manager.unresolved("SYNTHETIC failure")
    with pytest.raises(ValueError):
        manager.acknowledge("obsolete")
    manager.acknowledge(manager.current["id"])
    assert manager.current["status"] == "acknowledged" and not app.actuator.delivery_fault
    await asyncio.gather(*app.protective_tasks)
    await detect(app, clock)
    await manager.step()
    assert manager.current["status"] == "unresolved" and "30 minutes" in manager.current["reason"]
    assert len([call for call in ha.calls if call[0] == "button"]) == 1
    app.store.close()


async def test_diagnostics_capture_actual_states_and_export_more_than_recent_event_limit(tmp_path):
    app, _, manager, clock = installation(tmp_path)
    await manager.sample()
    diagnostic = app.store.events()[0]["body"]["entities"]
    assert diagnostic["sensor.bad"]["error"] == "RuntimeError"
    assert "select.force" in diagnostic and "number.current" in diagnostic
    await detect(app, clock)
    incident = manager.current
    rows = [(clock[0] - timedelta(seconds=300-index), "measurement", json.dumps({"ev_power_kw": index / 100}))
            for index in range(300)]
    with app.store.connection:
        app.store.connection.executemany("INSERT INTO events(at,kind,body) VALUES (?,?,?)",
            [(at.isoformat(), kind, body) for at, kind, body in rows])
    report = incident_report(app.store.path, json_data(incident), clock[0])
    measurements = [event for event in report["events"] if event["kind"] == "measurement"]
    assert len(measurements) == 300 and not report["truncated"]
    assert instant_seconds(incident["started_at"], report["window_start"]) == 300
    assert measurements[0]["body"]["ev_power_kw"] == 0
    assert "Only actually recorded" in report["note"]
    app.store.close()


@pytest.mark.parametrize("wait_minutes", [0, 15, 120])
def test_incident_report_includes_onset_and_both_window_boundaries(tmp_path, wait_minutes):
    store = Store(tmp_path / "synthetic.sqlite")
    started = datetime(2026, 10, 27, 0, 29, tzinfo=UTC)
    detected = started + timedelta(minutes=wait_minutes)
    start, end = started - timedelta(minutes=5), detected + timedelta(minutes=10)
    incident = {"started_at": started.isoformat(), "detected_at": detected.isoformat()}
    rows = [(end + timedelta(seconds=1), "measurement", "after"),
            (detected, "ev_incident", "detection"), (started, "command_intent", "onset"),
            (start - timedelta(seconds=1), "measurement", "before"),
            (end, "actuator_service", "end"), (start, "ev_diagnostics", "start"),
            (started, "unrelated", "excluded")]
    with store.connection:
        store.connection.executemany("INSERT INTO events(at,kind,body) VALUES (?,?,?)",
            [(at.isoformat(), kind, json.dumps({"synthetic": label})) for at, kind, label in rows])
    report = incident_report(store.path, incident, end + timedelta(hours=1))
    assert report["window_start"] == start.isoformat() and report["window_end"] == end.isoformat()
    expected = ["start", "onset", "detection", "end"] if wait_minutes else ["start", "detection", "onset", "end"]
    assert [event["body"]["synthetic"] for event in report["events"]] == expected
    assert not report["truncated"]
    store.close()


@pytest.mark.parametrize("started_at", [None, "", "2026-10-27T13:00:00+00:00"])
def test_incident_report_legacy_or_late_onset_keeps_detection_context(tmp_path, started_at):
    store = Store(tmp_path / "synthetic.sqlite")
    detected = datetime(2026, 10, 27, 12, tzinfo=UTC)
    now = detected + timedelta(minutes=2)
    incident = {"detected_at": detected.isoformat()}
    if started_at is not None:
        incident["started_at"] = started_at
    report = incident_report(store.path, incident, now)
    assert report["window_start"] == (detected - timedelta(minutes=5)).isoformat()
    assert report["window_end"] == now.isoformat()
    assert report["events"] == [] and not report["truncated"]
    store.close()


@pytest.mark.parametrize("count", [10000, 10001])
def test_incident_report_retains_chronological_cap_and_labels_omitted_tail(tmp_path, count):
    store = Store(tmp_path / "synthetic.sqlite")
    started = datetime(2026, 10, 27, 12, tzinfo=UTC)
    detected = started + timedelta(minutes=15)
    incident = {"started_at": started.isoformat(), "detected_at": detected.isoformat()}
    with store.connection:
        store.connection.executemany("INSERT INTO events(at,kind,body) VALUES (?,?,?)",
            [((started + timedelta(milliseconds=index)).isoformat(), "measurement", json.dumps({"synthetic": index}))
             for index in range(count)])
    report = incident_report(store.path, incident, detected)
    assert len(report["events"]) == 10000
    assert report["events"][0]["body"]["synthetic"] == 0
    assert report["events"][-1]["body"]["synthetic"] == 9999
    assert report["truncated"] == (count > 10000)
    assert ("later events in the requested window are omitted" in report["note"]) == report["truncated"]
    store.close()


async def test_incident_http_history_report_and_acknowledgement_boundary(tmp_path):
    from aiohttp.test_utils import TestClient, TestServer
    from energymanager.web import create_web

    app, _, manager, clock = installation(tmp_path, "")
    await detect(app, clock)
    await manager.step()
    identity = manager.current["id"]
    started = datetime.fromisoformat(manager.current["started_at"])
    early = started - timedelta(minutes=4)
    with app.store.connection:
        app.store.connection.execute("INSERT INTO events(at,kind,body) VALUES (?,?,?)",
            (early.isoformat(), "command_intent", json.dumps({"synthetic": "before onset"})))

    async def no_lifecycle():
        pass

    app.start = app.close = no_lifecycle
    async with TestClient(TestServer(create_web(app))) as client:
        items = await (await client.get("/api/ev-incidents")).json()
        assert items[0]["id"] == identity
        report = await (await client.get(f"/api/ev-incidents/{identity}")).json()
        assert report["incident"]["status"] == "unresolved" and report["window_start"]
        assert report["window_start"] == (started - timedelta(minutes=5)).isoformat()
        assert any(event["body"].get("synthetic") == "before onset" for event in report["events"])
        assert (await client.get("/api/ev-incidents/missing")).status == 404
        assert (await client.post(f"/api/ev-incidents/{identity}/acknowledge", json={})).status == 403
        response = await client.post(f"/api/ev-incidents/{identity}/acknowledge", json={}, headers={"X-EnergyManager": "1"})
        assert response.status == 200 and not app.actuator.delivery_fault
        await asyncio.gather(*app.protective_tasks)


async def test_incident_report_worker_does_not_block_state_api(tmp_path, monkeypatch):
    import threading
    from aiohttp.test_utils import TestClient, TestServer
    from energymanager import web as web_module

    app, _, manager, clock = installation(tmp_path)
    await detect(app, clock)
    entered, released = threading.Event(), threading.Event()

    def held_read(path, incident, now):
        entered.set()
        assert released.wait(3)
        return {"incident": incident, "events": []}

    async def no_lifecycle():
        pass

    app.start = app.close = no_lifecycle
    monkeypatch.setattr(web_module, "incident_report", held_read)
    async with TestClient(TestServer(web_module.create_web(app))) as client:
        pending = asyncio.create_task(client.get(f"/api/ev-incidents/{manager.current['id']}"))
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            async with asyncio.timeout(1):
                assert (await client.get("/api/state")).status == 200
        finally:
            released.set()
            response = await pending
        assert response.status == 200


async def test_reboot_is_not_sent_when_attempt_cannot_be_persisted(tmp_path, monkeypatch):
    import sqlite3

    app, ha, manager, clock = installation(tmp_path)
    await detect(app, clock)

    def no_storage(incident):
        raise sqlite3.OperationalError("SYNTHETIC full disk")

    monkeypatch.setattr(app.store, "save_ev_incident", no_storage)
    with pytest.raises(sqlite3.OperationalError):
        await manager.step()
    assert not any(call[0] == "button" for call in ha.calls)
    app.store.close()


@pytest.mark.parametrize("state,allowed", [("unknown", True), ("unavailable", False)])
async def test_button_without_press_history_is_valid_but_unavailable_button_is_not(tmp_path, state, allowed):
    app, ha, manager, clock = installation(tmp_path)
    await detect(app, clock)

    async def button_state(entity):
        return {"entity_id": entity, "state": state}

    ha.entity_state = button_state
    await manager.step()
    assert any(call[0] == "button" for call in ha.calls) == allowed
    assert manager.current["status"] == ("rebooting" if allowed else "unresolved")
    app.store.close()
