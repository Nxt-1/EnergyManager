"""Synthetic FordConnect2026.10.7 status and fake go-e/HA incident verification."""

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

import pytest

from energymanager.ev_faults import EVFaults, incident_report
from energymanager.vehicle_charging import VehicleCharging
from test_goe import ChargerFixture
from test_ev_faults import installation


def vehicle_fixture(state="IN_PROGRESS"):
    f = ChargerFixture()
    entity = "sensor.synthetic_ford_charging"
    f.diagnostics["vehicle_charging"] = entity
    f.readings.entities["vehicle_charging"] = entity
    f.readings.vehicle.entity = entity
    f.rows[entity] = {"state": state, "last_updated": (f.at - timedelta(hours=1)).isoformat(),
                      "attributes": {"chargingStatus": state, "chargingStationStatus": "OK",
                                     "stateOfCharge": 46.5, "private_unrelated": "exclude"}}
    f.refresh()
    return f


async def test_vehicle_fault_stops_immediately_persists_evidence_and_never_reboots(tmp_path):
    app, ha, _, _ = installation(tmp_path)
    f = vehicle_fixture("FAULT")
    app.now = lambda: f.at
    app.actuator = f.actuator
    manager = EVFaults(app, "button.synthetic_reboot", f.diagnostics)
    app.ev_faults = manager
    _, app.observation = await f.tick(power=1.38)
    assert f.actuator.delivery_fault and not f.actuator.delivery_reboot_allowed
    assert manager.current["started_at"] == manager.current["detected_at"]
    vehicle = manager.current["charger"]["vehicle_charging"]
    assert vehicle["state"] == "FAULT" and vehicle["attributes"]["stateOfCharge"] == 46.5
    assert vehicle["vehicle_observed_at"] is None and "private_unrelated" not in vehicle["attributes"]
    assert any(c[2].get("option") == "1" for c in f.calls)
    assert any(c[2].get("entity_id") == f.actuators["ess_setpoint"] for c in f.calls)
    await manager.step()
    await manager.step()
    assert manager.current["status"] == "unresolved" and manager.current["reboot_attempts"] == 0
    assert len([c for c in ha.calls if c[0] == "notify"]) == 1
    assert not any(c[0] == "button" for c in ha.calls)
    report = incident_report(app.store.path, manager.current, f.at)
    assert report["incident"]["charger"]["vehicle_charging"]["state"] == "FAULT"
    with pytest.raises(ValueError, match="vehicle charging fault must clear"):
        manager.acknowledge(manager.current["id"])
    f.set("vehicle_charging", "unavailable")
    f.refresh()
    app.observation = replace(app.observation, at=f.at)
    with pytest.raises(ValueError, match="Fresh vehicle charging status"):
        manager.acknowledge(manager.current["id"])
    f.set("vehicle_charging", "IN_PROGRESS")
    f.refresh()
    app.observation = replace(app.observation, at=f.at)
    manager.acknowledge(manager.current["id"])
    assert manager.current["status"] == "acknowledged"
    app.store.close()


@pytest.mark.parametrize("state", ["PAUSED", "SCHEDULED", "unavailable", "unknown", "FUTURE_STATE"])
async def test_optional_vehicle_wait_or_missing_data_keeps_power_watchdog_but_cannot_authorize_reboot(state):
    f = vehicle_fixture(state)
    await f.start()
    assert not f.actuator.delivery_fault
    f.refresh(89)
    await f.tick()
    assert not f.actuator.delivery_fault
    f.refresh(1)
    await f.tick()
    assert f.actuator.delivery_fault and "90 seconds" in f.incidents[0]
    assert not f.actuator.delivery_reboot_allowed


async def test_confirmed_in_progress_vehicle_keeps_existing_non_delivery_reboot_eligibility():
    f = vehicle_fixture()
    await f.start()
    f.refresh(90)
    await f.tick()
    assert f.actuator.delivery_fault and f.actuator.delivery_reboot_allowed
    f.set("vehicle_charging", "FAULT")
    f.refresh()
    assert "FAULT" in f.readings.reboot_issue(f.at)


def test_vehicle_read_age_is_separate_from_unknown_cloud_measurement_age():
    f = vehicle_fixture("FAULT")
    vehicle = f.readings.vehicle
    assert vehicle.fault(f.at)
    view = vehicle.view(f.at)
    assert view["reported_at"] < view["read_at"] and view["vehicle_observed_at"] is None
    assert vehicle.fault(f.at + timedelta(seconds=31)) is None
    assert "stale" in vehicle.reboot_issue(f.at + timedelta(seconds=31))
    assert VehicleCharging().reboot_issue(f.at) is None


async def test_actual_power_resets_blocked_wait_and_commanded_stops_do_not_count():
    f = ChargerFixture()
    f.auto_model = False
    f.set("ev_status", 4)
    f.set("charger_status", 3)
    f.refresh()
    await f.start()
    f.refresh(119)
    await f.tick(power=1.38)
    assert not f.actuator.delivery_fault and f.actuator.goe_control.waiting_since is None
    f.refresh()
    await f.tick()
    f.refresh(119)
    await f.tick()
    assert not f.actuator.delivery_fault
    await f.tick(amps=0)
    f.refresh(120)
    await f.tick(amps=0)
    assert not f.actuator.delivery_fault


async def test_sampler_archives_bounded_vehicle_attributes_without_inventing_vehicle_timestamp(tmp_path):
    app, ha, _, _ = installation(tmp_path)
    f = vehicle_fixture("FAULT")
    app.now = lambda: f.at
    app.actuator = f.actuator
    manager = EVFaults(app, "", f.diagnostics)

    async def entity_state(entity):
        return deepcopy(f.rows.get(entity, {"state": "unknown"}))

    ha.entity_state = entity_state
    await manager.sample()
    sample = app.store.events()[0]["body"]["entities"][f.diagnostics["vehicle_charging"]]
    assert sample["state"] == "FAULT" and sample["attributes"]["chargingStatus"] == "FAULT"
    assert sample["vehicle_observed_at"] is None and "private_unrelated" not in sample["attributes"]
    app.store.close()


@pytest.mark.parametrize("status", ["pending", "rebooting", "verifying"])
async def test_vehicle_fault_prevents_a_pending_reboot_or_false_recovery(tmp_path, status):
    app, ha, _, _ = installation(tmp_path)
    f = vehicle_fixture()
    app.now = lambda: f.at
    app.actuator = f.actuator
    manager = EVFaults(app, "button.synthetic_reboot", f.diagnostics)
    command, app.observation = await f.tick(power=1.38)
    f.actuator.delivery_reason = "SYNTHETIC earlier delivery failure"
    f.actuator.delivery_reboot_allowed = True
    manager.capture(command, app.observation, f.at)
    manager.current["status"] = status
    f.set("vehicle_charging", "FAULT")
    f.refresh()
    app.observation = replace(app.observation, at=f.at)
    await manager.step()
    assert manager.current["status"] == "unresolved" and f.actuator.delivery_fault
    assert "Vehicle reports charging FAULT" in manager.current["reason"]
    assert manager.current["recovery_charger"]["vehicle_charging"]["state"] == "FAULT"
    assert not any(call[0] == "button" for call in ha.calls)
    app.store.close()


async def test_status_changes_and_current_updates_do_not_restart_two_minute_non_delivery_limit():
    f = ChargerFixture()
    f.auto_model = False
    f.set("ev_status", 4)
    f.set("charger_status", 3)
    f.refresh()
    await f.start()
    for car, seconds in ((2, 50), (4, 50), (2, 19)):
        f.set("ev_status", car)
        f.refresh(seconds)
        await f.tick(amps=8)
        assert not f.actuator.delivery_fault
    f.refresh(1)
    await f.tick(amps=8)
    assert f.actuator.delivery_fault and "2 minutes" in f.incidents[0]
    assert not f.actuator.delivery_reboot_allowed


async def test_pending_current_confirmation_cannot_extend_acknowledged_no_power_deadline():
    f = ChargerFixture()
    f.auto_model = False
    f.set("ev_status", 4)
    f.set("charger_status", 3)
    f.refresh()
    await f.start()
    f.ignore.add(f.actuators["current"])
    f.refresh(119)
    await f.tick(amps=8)
    assert not f.actuator.delivery_fault
    assert "current" in f.actuator.goe_control.pending
    f.refresh(1)
    await f.tick(amps=8)
    assert f.actuator.delivery_fault and "2 minutes" in f.incidents[0]
    assert not f.actuator.delivery_reboot_allowed
