"""SYNTHETIC go-e APIv2 readbacks; no installation or device access."""

import asyncio
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from energymanager.control import Command, GuardedActuator
from energymanager.domain import Capabilities, Observation
from energymanager.goe import GoEControl, GoEReadings


class ChargerFixture:
    def __init__(self):
        self.at = datetime(2026, 10, 25, 12, tzinfo=UTC)
        self.actuators = {key: f"select.synthetic_{key}" for key in ("force", "phase")}
        self.actuators.update(current="number.synthetic_current", ess_setpoint="number.synthetic_ess")
        self.diagnostics = {key: f"sensor.synthetic_{key}" for key in
                            ("ev_status", "charger_status", "charger_error", "heartbeat")}
        self.rows = {}
        for key, value in dict(force=1, phase=1, current=6, ev_status=2, charger_status=4,
                               charger_error=0, heartbeat=0).items():
            entity = (self.actuators | self.diagnostics)[key]
            self.rows[entity] = {"state": str(value), "attributes": {}}
        self.rows[self.actuators["current"]]["attributes"] = {"unit_of_measurement": "A", "min": 6, "max": 16}
        self.rows[self.diagnostics["heartbeat"]]["attributes"] = {"unit_of_measurement": "s"}
        self.calls = []
        self.ignore = set()
        self.auto_model = True
        self.readings = GoEReadings(self.actuators, self.diagnostics)
        self.readings.update(deepcopy(self.rows), self.at)
        self.actuator = GuardedActuator(self, self.actuators, Capabilities(), enabled=True, charger=self.readings)
        self.incidents = []
        self.actuator.on_delivery_fault = lambda *_: self.incidents.append(self.actuator.delivery_reason)
        self.refresh(5)

    def set(self, key, value):
        self.rows[(self.actuators | self.diagnostics)[key]]["state"] = str(value)

    def refresh(self, seconds=5, *, heartbeat=True):
        self.at += timedelta(seconds=seconds)
        if heartbeat:
            self.set("heartbeat", (self.at - datetime(2026, 10, 25, 12, tzinfo=UTC)).total_seconds())
        self.readings.update(deepcopy(self.rows), self.at)

    async def service(self, domain, service, data):
        self.calls.append((domain, service, data))
        entity = data.get("entity_id")
        if entity in self.rows and entity not in self.ignore:
            self.rows[entity]["state"] = str(data.get("value", data.get("option")))
            if entity == self.actuators["force"] and self.auto_model:
                self.set("charger_status", 4 if str(data["option"]) == "1" else 3)

    async def tick(self, *, amps=6, phases=1, power=0, connected=True, generation=1):
        observation = Observation(self.at, 30, 7, connected, .4, 1, 0, ev_power_kw=power,
                                  ev_phases=1 if self.readings.code("phase") == 1 else 3,
                                  ev_phase_source="goe_selector")
        command = Command(generation, "SYNTHETIC", self.at, amps * phases * .23, 0, phases, amps, 4, "SYNTHETIC")
        await self.actuator.apply(command, generation, observation)
        return command, observation

    async def start(self, *, amps=6):
        await self.tick(amps=amps)
        self.refresh(30)
        await self.tick(amps=amps)
        self.refresh()
        await self.tick(amps=amps)


async def test_controller_activity_distinguishes_restart_hold_start_ack_and_delivery_check():
    f = ChargerFixture()
    command, observation = await f.tick()
    control = f.actuator.goe_control
    deadline = f.actuator.resume_after
    calls = len(f.calls)
    view = control.view(f.at, observation, command)
    assert view["stage"] == "settling" and view["duration_seconds"] == 30
    assert view["until"] == deadline.isoformat() and view["timer"] == "Restart hold"
    # Reading the status must not change timing, write commands or confirm a pending operation.
    assert f.actuator.resume_after == deadline and len(f.calls) == calls
    f.refresh(30)
    command, observation = await f.tick()
    assert control.view(f.at, observation, command)["stage"] == "starting"
    f.refresh()
    command, observation = await f.tick()
    view = control.view(f.at, observation, command)
    assert view["stage"] == "power" and view["timer"] == "Delivery check"
    assert view["duration_seconds"] == 90
    command, observation = await f.tick(power=1.38)
    assert control.view(f.at, observation, command)["stage"] == "charging"
    command, observation = await f.tick(amps=0)
    assert control.view(f.at, observation, command)["stage"] == "stopping"
    f.refresh()
    command, observation = await f.tick(amps=0)
    assert control.view(f.at, observation, command)["stage"] == "idle"
    f.actuator.enabled = False
    assert control.view(f.at, observation, command)["stage"] == "disabled"


async def test_controller_activity_prioritizes_faults_stale_inputs_and_phase_waits():
    f = ChargerFixture()
    command, observation = await f.tick(phases=3)
    control = f.actuator.goe_control
    assert control.view(f.at, observation, command)["stage"] == "stopping"
    f.refresh(10)
    command, observation = await f.tick(phases=3)
    assert control.view(f.at, observation, command)["stage"] == "settings"
    f.auto_model = False
    f.set("charger_status", 23)
    f.refresh()
    command, observation = await f.tick(phases=3)
    assert control.view(f.at, observation, command)["timer"] == "Restart hold"
    f.refresh(30)
    command, observation = await f.tick(phases=3)
    view = control.view(f.at, observation, command)
    assert view["until"] is None and "hold complete" in view["detail"]
    f.set("charger_error", 8)
    f.refresh()
    assert control.view(f.at, observation, command)["stage"] == "fault"
    await f.tick(phases=3)
    assert control.view(f.at, observation, command)["stage"] == "fault"
    f.actuator.delivery_fault = False
    f.refresh(31, heartbeat=False)
    assert control.view(f.at, observation, command)["stage"] == "blocked"


async def test_controller_activity_does_not_label_unfinished_stop_as_charging():
    f = ChargerFixture()
    command, observation = await f.tick(power=1.38)
    view = f.actuator.goe_control.view(f.at, observation, command)
    assert view["stage"] == "stopping" and view["until"] is None
    assert view["label"] == "Waiting for EV power to stop"


@pytest.mark.parametrize("early_power", [0, 1.38])
async def test_revisions_during_pending_start_neither_stop_nor_repeat_start(early_power):
    f = ChargerFixture()
    await f.tick()
    f.refresh(30)
    await f.tick()
    pending = f.actuator.goe_control.pending["force"]
    f.calls.clear()
    # Control ticks advance between the independent five-second readback samples.
    for generation in (2, 3, 4):
        f.at += timedelta(seconds=1)
        command, observation = await f.tick(generation=generation, power=early_power)
        assert f.actuator.goe_control.pending["force"] == pending
        assert f.actuator.goe_control.view(f.at, observation, command)["stage"] == "starting"
        assert not f.actuator.delivery_fault
    assert not [call for call in f.calls if call[2]["entity_id"] == f.actuators["force"]]
    f.refresh(2)
    await f.tick(generation=5, power=early_power)
    assert "force" not in f.actuator.goe_control.pending
    assert f.actuator.resume_after is None
    assert f.actuator.goe_control.status == "Charging command confirmed"


async def test_newer_revision_can_confirm_start_without_rewriting_an_already_matching_readback():
    f = ChargerFixture()
    await f.tick()
    f.refresh(30)
    await f.tick()
    f.refresh()
    f.calls.clear()
    await f.tick(generation=2, power=1.38)
    assert not [call for call in f.calls if call[2]["entity_id"] == f.actuators["force"]]
    assert f.actuator.resume_after is None and not f.actuator.delivery_fault


async def test_revisions_cannot_extend_an_unacknowledged_start_forever():
    f = ChargerFixture()
    f.ignore.add(f.actuators["force"])
    await f.tick()
    f.refresh(30)
    await f.tick()
    sent = f.at
    for generation in range(2, 8):
        f.refresh()
        await f.tick(generation=generation)
        assert f.actuator.delivery_fault == ((f.at - sent).total_seconds() >= 30)
    assert "force command was not confirmed within 30 seconds" in f.actuator.delivery_reason
    starts = [c for c in f.calls if c[2] == {"entity_id": f.actuators["force"], "option": "2"}]
    assert len(starts) == 1


@pytest.mark.parametrize("changed", ["stop", "phase", "fault", "stale", "disable"])
async def test_revision_continuation_does_not_bypass_real_stops_or_guards(changed):
    f = ChargerFixture()
    await f.tick()
    f.refresh(30)
    await f.tick()
    f.calls.clear()
    if changed == "disable":
        await f.actuator.stop(2, at=f.at)
    else:
        if changed == "fault":
            f.set("charger_error", 8)
            f.refresh(1)
        elif changed == "stale":
            f.refresh(31, heartbeat=False)
        await f.tick(generation=2, amps=0 if changed == "stop" else 6, phases=3 if changed == "phase" else 1)
    writes = [c[2] for c in f.calls if c[2]["entity_id"] == f.actuators["force"]]
    assert writes and writes[0]["option"] == "1"
    assert not any(c.get("option") == "2" for c in writes)


async def test_current_only_change_during_pending_start_does_not_send_stop_or_restart_hold():
    f = ChargerFixture()
    await f.tick()
    f.refresh(30)
    await f.tick()
    pending = f.actuator.goe_control.pending["force"]
    f.calls.clear()
    await f.tick(generation=2, amps=8)
    f.refresh()
    await f.tick(generation=3, amps=8, power=1.84)
    assert not [c for c in f.calls if c[2]["entity_id"] == f.actuators["force"]]
    assert pending[1] < f.at and f.actuator.resume_after is None


async def test_revoked_unsent_start_does_not_create_a_phantom_pending_acknowledgement():
    f = ChargerFixture()
    generation = [1]
    f.actuator.generation = lambda: generation[0]
    original = f.service

    async def revoke_after_ess(domain, service, data):
        await original(domain, service, data)
        if data["entity_id"] == f.actuators["ess_setpoint"]:
            generation[0] += 1

    await f.tick()
    f.refresh(30)
    f.service = revoke_after_ess
    await f.tick()
    assert "force" not in f.actuator.goe_control.pending
    assert f.rows[f.actuators["force"]]["state"] == "1"
    f.service = original
    await f.tick(generation=2)
    assert f.rows[f.actuators["force"]]["state"] == "2"
    assert f.actuator.goe_control.pending["force"][0] == 2


@pytest.mark.parametrize("key", ["current", "phase", "force"])
async def test_unchanged_pending_settings_and_stops_keep_original_timeout_across_revisions(key):
    f = ChargerFixture()
    f.ignore.add(f.actuators[key])
    amps, phases = (8, 1) if key == "current" else (6, 3) if key == "phase" else (0, 1)
    if key == "force":
        f.set("force", 2)
        f.refresh()
    await f.tick(amps=amps, phases=phases)
    if key == "phase":
        f.refresh(10)
        await f.tick(phases=phases)
    original = f.actuator.goe_control.pending[key]
    for generation in range(2, 8):
        f.refresh()
        await f.tick(generation=generation, amps=amps, phases=phases)
        if generation < 7:
            assert f.actuator.goe_control.pending[key] == original
            assert not f.actuator.delivery_fault
    assert f.actuator.delivery_fault and key in f.actuator.delivery_reason
    values = [c[2] for c in f.calls if c[2]["entity_id"] == f.actuators[key]]
    if key == "force":
        # Timeout may add a protective stop; the original pending stop was never repeated before it.
        assert len(values) == 2
    else:
        assert len(values) == 1


async def test_revoked_replacement_restores_the_previous_inflight_setting():
    f = ChargerFixture()
    f.ignore.add(f.actuators["current"])
    generation = [1]
    f.actuator.generation = lambda: generation[0]
    await f.tick(amps=8)
    pending = f.actuator.goe_control.pending["current"]
    original = f.service

    async def revoke_after_ess(domain, service, data):
        await original(domain, service, data)
        if data["entity_id"] == f.actuators["ess_setpoint"]:
            generation[0] += 1

    f.service = revoke_after_ess
    await f.tick(amps=6)
    assert f.actuator.goe_control.pending["current"] == pending
    f.service = original
    f.calls.clear()
    await f.tick(amps=6, generation=2)
    # The old 8 A command can still arrive, so 6 A must be sent even though the old frame says 6.
    assert any(c[2] == {"entity_id": f.actuators["current"], "value": 6} for c in f.calls)


async def test_unknown_service_response_keeps_pending_evidence_for_new_revision_readback():
    f = ChargerFixture()
    await f.tick()
    f.refresh(30)
    original = f.service

    async def accepted_but_response_lost(domain, service, data):
        await original(domain, service, data)
        if data == {"entity_id": f.actuators["force"], "option": "2"}:
            raise RuntimeError("SYNTHETIC response lost after device accepted start")

    f.service = accepted_but_response_lost
    with pytest.raises(RuntimeError, match="response lost"):
        await f.tick()
    assert f.actuator.goe_control.pending["force"][0] == 2
    f.service = original
    f.calls.clear()
    f.refresh()
    await f.tick(generation=2, power=1.38)
    assert not [c for c in f.calls if c[2]["entity_id"] == f.actuators["force"]]
    assert "force" not in f.actuator.goe_control.pending


async def test_revoked_unsent_stop_cannot_erase_an_active_restart_hold():
    f = ChargerFixture()
    await f.tick()
    deadline = f.actuator.resume_after
    f.set("force", 2)  # External change while the controller is still holding a restart.
    f.refresh()
    generation = [1]
    f.actuator.generation = lambda: generation[0]
    original = f.service

    async def revoke_after_ess(domain, service, data):
        await original(domain, service, data)
        if data["entity_id"] == f.actuators["ess_setpoint"]:
            generation[0] += 1

    f.service = revoke_after_ess
    await f.tick()
    assert f.actuator.resume_after == deadline
    assert "force" not in f.actuator.goe_control.pending


async def test_current_must_confirm_before_start_and_silent_failure_escalates():
    f = ChargerFixture()
    f.ignore.add(f.actuators["current"])
    await f.tick(amps=8)
    assert not any(call[2].get("option") == "2" for call in f.calls)
    f.refresh(15)
    await f.tick(amps=8)
    assert len([c for c in f.calls if c[2].get("entity_id") == f.actuators["current"]]) == 1
    f.refresh(15)
    await f.tick(amps=8)
    assert f.actuator.delivery_fault and "current" in f.incidents[0]
    assert not f.actuator.delivery_reboot_allowed
    assert f.rows[f.actuators["force"]]["state"] == "1"


async def test_start_confirmation_precedes_delivery_watchdog_and_current_changes_stay_live():
    f = ChargerFixture()
    await f.start(amps=8)
    await f.tick(amps=8, power=1.84)
    assert not f.actuator.delivery_fault
    f.calls.clear()
    await f.tick(amps=6, power=1.84)
    assert f.calls[-1][2] == {"entity_id": f.actuators["current"], "value": 6}
    assert not any(c[2].get("entity_id") == f.actuators["force"] for c in f.calls)


async def test_normal_two_minute_pause_and_wait_car_do_not_trigger_90_second_fault():
    f = ChargerFixture()
    f.auto_model = False
    f.set("charger_status", 24)
    f.set("ev_status", 3)
    f.refresh()
    await f.tick()
    for _ in range(25):
        f.refresh()
        await f.tick()
    assert not f.actuator.delivery_fault and f.actuator.charging_since is None
    assert f.actuator.goe_control.status == "Minimum charging pause"
    f.set("charger_status", 3)
    f.set("ev_status", 2)
    f.refresh()
    await f.tick(power=1.38)
    assert not f.actuator.delivery_fault


async def test_waiting_has_bounded_escalation_without_reboot():
    f = ChargerFixture()
    f.auto_model = False
    f.set("charger_status", 28)
    f.refresh()
    await f.start()
    f.refresh(900)
    await f.tick()
    assert f.actuator.delivery_fault and "OCPP" in f.incidents[0]
    assert not f.actuator.delivery_reboot_allowed


@pytest.mark.parametrize("code", [1, 2, 3, 4, 5, 8, 9, 10, 13, 14, 16, 255])
async def test_reported_errors_stop_and_can_never_be_rebooted(code):
    f = ChargerFixture()
    f.set("charger_error", code)
    f.refresh()
    await f.tick()
    assert f.actuator.delivery_fault and str(code) in f.incidents[0]
    assert not f.actuator.delivery_reboot_allowed
    assert f.readings.reboot_issue(f.at)


async def test_only_confirmed_healthy_non_delivery_is_reboot_eligible():
    f = ChargerFixture()
    await f.start()
    f.refresh(90)
    await f.tick()
    assert f.actuator.delivery_fault and f.actuator.delivery_reboot_allowed
    f.set("ev_status", 3)  # Normal car response after EnergyManager requests stop.
    f.refresh()
    assert f.readings.reboot_issue(f.at) is None
    f.set("charger_error", 13)
    f.refresh()
    assert "not permitted" in f.readings.reboot_issue(f.at)


async def test_phase_write_timeout_alerts_and_ess_keeps_receiving_commands():
    f = ChargerFixture()
    f.ignore.add(f.actuators["phase"])
    await f.tick(phases=3)
    f.refresh(10)
    await f.tick(phases=3)
    assert f.actuator.target_phase == 3
    f.refresh(30)
    await f.tick(phases=3)
    assert f.actuator.delivery_fault and "phase" in f.incidents[0]
    count = len([c for c in f.calls if c[2].get("entity_id") == f.actuators["ess_setpoint"]])
    f.refresh()
    await f.tick(phases=3)
    assert len([c for c in f.calls if c[2].get("entity_id") == f.actuators["ess_setpoint"]]) == count + 1


async def test_phase_readback_does_not_bypass_active_transition_and_it_eventually_times_out():
    f = ChargerFixture()
    f.auto_model = False
    f.set("charger_status", 23)
    f.refresh()
    await f.tick(phases=3)
    f.refresh(10)
    await f.tick(phases=3)
    f.refresh()
    await f.tick(phases=3)
    assert f.rows[f.actuators["force"]]["state"] == "1"
    f.refresh(780)
    await f.tick(phases=3)
    assert f.actuator.delivery_fault and "phase change timed out" in f.incidents[0]


async def test_unchanged_device_heartbeat_expires_even_with_successful_ha_reads():
    f = ChargerFixture()
    f.refresh(31, heartbeat=False)
    assert "cached" in f.readings.issue(f.at)
    await f.tick()
    assert f.rows[f.actuators["force"]]["state"] == "1"
    f.refresh(30, heartbeat=False)
    await f.tick()
    assert f.actuator.delivery_fault and not f.actuator.delivery_reboot_allowed


@pytest.mark.parametrize("key,value", [("ev_status", "Charging"), ("charger_status", "unavailable"),
                                       ("charger_error", "none"), ("heartbeat", "nan")])
async def test_missing_invalid_numeric_readings_pause_only_ev(key, value):
    f = ChargerFixture()
    f.set(key, value)
    f.refresh(heartbeat=key != "heartbeat")
    assert f.readings.issue(f.at)
    # Construct explicitly because invalid phase-independent diagnostics are the subject.
    await f.tick()
    assert f.calls[0][2]["entity_id"] == f.actuators["ess_setpoint"]
    assert not any(c[2].get("option") == "2" for c in f.calls)


async def test_charger_limits_do_not_silently_raise_or_exceed_installation_limits():
    f = ChargerFixture()
    f.rows[f.actuators["current"]]["attributes"].update(min=10, max=13)
    f.set("current", 10)
    f.refresh()
    await f.tick(amps=6)
    assert f.actuator.delivery_fault and "10–13" in f.incidents[0]
    assert not any(c[2].get("entity_id") == f.actuators["current"] for c in f.calls)


def test_coarse_uptime_is_rejected_and_new_samples_are_needed_after_missing_data():
    f = ChargerFixture()
    f.rows[f.diagnostics["heartbeat"]]["attributes"]["unit_of_measurement"] = "h"
    f.refresh()
    assert "whole hours" in f.readings.issue(f.at)
    f.rows[f.diagnostics["heartbeat"]]["attributes"]["unit_of_measurement"] = "s"
    f.refresh(0, heartbeat=False)
    assert "advancing" in f.readings.issue(f.at)
    f.refresh()
    assert f.readings.issue(f.at) is None


async def test_fault_manager_checks_current_error_again_before_reboot(tmp_path):
    from test_ev_faults import installation, detect

    app, ha, manager, clock = installation(tmp_path)
    await detect(app, clock)
    f = ChargerFixture()
    f.at = clock[0]
    f.set("charger_error", 13)
    f.refresh(0)
    app.actuator.charger = f.readings
    app.actuator.goe_control = GoEControl(app.actuator, f.readings)
    await manager.step()
    assert manager.current["status"] == "unresolved"
    assert not any(c[0] == "button" for c in ha.calls)
    with pytest.raises(ValueError, match="fault must clear"):
        manager.acknowledge(manager.current["id"])
    app.store.close()


async def test_runtime_limits_replan_without_increasing_the_configured_maximum(tmp_path):
    from test_ev_faults import installation

    app, _, manager, clock = installation(tmp_path)
    f = ChargerFixture()
    app.actuator.charger = f.readings
    app.actuator.goe_control = GoEControl(app.actuator, f.readings)
    f.rows[f.actuators["current"]]["attributes"].update(min=10, max=32)
    f.set("current", 10)
    f.refresh()
    clock[0] = f.at
    old_revision = app.revision
    manager.update_limits()
    assert app.revision == old_revision + 1 and not app.ev_valid
    assert app.controller.c.minimum_current_a == 10
    assert app.controller.c.maximum_current_a == app.actuator.c.maximum_current_a == 16
    assert app.build_snapshot().capabilities.minimum_current_a == 10
    manager.update_limits()
    assert app.revision == old_revision + 1
    await asyncio.gather(*app.protective_tasks)
    app.store.close()


async def test_charging_can_resume_after_confirmed_phase_change():
    f = ChargerFixture()
    await f.tick(phases=3)
    f.refresh(10)
    await f.tick(phases=3)
    f.refresh()
    await f.tick(phases=3)
    f.refresh(30)
    await f.tick(phases=3)
    f.refresh()
    await f.tick(phases=3, power=4.14)
    assert f.rows[f.actuators["force"]]["state"] == "2"
    assert f.actuator.target_phase is None and not f.actuator.delivery_fault


async def test_power_continuing_after_stop_notifies_without_reboot():
    f = ChargerFixture()
    await f.tick(amps=0, power=1.38)
    f.refresh(30)
    await f.tick(amps=0, power=1.38)
    assert f.actuator.delivery_fault and "power did not stop" in f.incidents[0]
    assert not f.actuator.delivery_reboot_allowed


async def test_silently_failed_disabled_stop_is_escalated_without_reenabling_hardware(tmp_path):
    from test_ev_faults import installation

    app, _, manager, clock = installation(tmp_path)
    f = ChargerFixture()
    app.actuator.charger = f.readings
    app.actuator.goe_control = GoEControl(app.actuator, f.readings)
    app.actuator.enabled = False
    app.actuator.goe_control.disabled_stop_at = clock[0]
    clock[0] += timedelta(seconds=30)
    await manager.step()
    assert manager.current["status"] == "unresolved" and not manager.current["reboot_allowed"]
    assert not app.actuator.enabled
    assert "disabling hardware" in manager.current["reason"]
    app.store.close()


async def test_configured_recovery_verifies_new_frames_and_never_repeats_the_reboot(tmp_path):
    from test_ev_faults import installation
    from energymanager.ev_faults import EVFaults

    app, _, _, clock = installation(tmp_path)
    f = ChargerFixture()
    app.actuator = f.actuator
    manager = EVFaults(app, "button.synthetic_reboot")

    async def tick(seconds=5, power=0):
        f.refresh(seconds)
        command, observation = await f.tick(power=power)
        clock[0] = f.at
        app.observation, app.current_command = observation, command

    await tick()
    await tick(30)
    await tick()
    await tick(90)
    assert manager.current["reboot_allowed"]
    await tick()  # Stop readback and advancing device frame before recovery.
    await manager.step()
    assert manager.current["status"] == "rebooting"
    assert len([c for c in f.calls if c[0] == "button"]) == 1
    f.refresh(60)
    clock[0] = f.at
    app.observation = replace(app.observation, at=f.at)
    await manager.step()
    assert manager.current["status"] == "verifying"
    await tick()
    await tick(30)
    await manager.step()
    await tick(power=1.38)
    await manager.step()
    await tick(power=1.38)
    await manager.step()
    await tick(10, power=1.38)
    await manager.step()
    assert manager.current["status"] == "recovered"
    assert len([c for c in f.calls if c[0] == "button"]) == 1
    assert not f.actuator.delivery_fault
    app.store.close()


async def test_stop_supersedes_an_unconfirmed_start_even_if_old_frame_shows_stopped():
    f = ChargerFixture()
    await f.tick()
    f.refresh(30)
    await f.tick()
    assert f.actuator.goe_control.pending["force"][0] == 2
    f.calls.clear()
    await f.tick(amps=0)
    assert any(c[2] == {"entity_id": f.actuators["force"], "option": "1"} for c in f.calls)


async def test_cancelled_phase_request_can_restart_without_a_cooldown_or_stale_timeout():
    f = ChargerFixture()
    await f.tick(phases=3)
    f.refresh(10)
    await f.tick(phases=3)
    assert "phase" in f.actuator.goe_control.pending
    f.refresh()
    await f.tick(amps=0)
    assert f.actuator.goe_control.phase_started is None
    f.refresh(60)
    await f.tick(phases=3)
    f.refresh()
    await f.tick(phases=3, power=4.14)
    assert not f.actuator.delivery_fault


async def test_finished_charger_transition_resumes_without_waiting_another_dwell():
    f = ChargerFixture()
    f.auto_model = False
    f.set("charger_status", 23)
    f.refresh()
    await f.tick(phases=3)
    f.refresh(10)
    await f.tick(phases=3)
    f.refresh()
    await f.tick(phases=3)
    assert f.actuator.target_phase == 3
    f.set("charger_status", 4)
    f.refresh()
    await f.tick(phases=3)
    assert f.actuator.target_phase is None
    assert f.rows[f.actuators["force"]]["state"] == "1"
    f.refresh(25)
    await f.tick(phases=3)
    assert f.rows[f.actuators["force"]]["state"] == "2"


def test_malformed_current_attributes_pause_ev_without_breaking_the_status_api():
    f = ChargerFixture()
    f.rows[f.actuators["current"]]["attributes"] = None
    f.refresh()
    assert f.readings.issue(f.at)
    assert f.readings.view(f.at)["current_limits"] == {"min": None, "max": None}


async def test_delivery_timer_restarts_after_a_new_current_is_confirmed():
    f = ChargerFixture()
    await f.start()
    f.refresh(60)
    await f.tick(amps=8)
    assert f.actuator.charging_since is None
    f.refresh()
    await f.tick(amps=8)
    f.refresh(30)
    await f.tick(amps=8)
    assert not f.actuator.delivery_fault
    f.refresh(60)
    await f.tick(amps=8)
    assert f.actuator.delivery_fault


async def test_stopped_plan_cancels_a_pending_current_write_without_a_future_stale_timeout():
    f = ChargerFixture()
    f.ignore.add(f.actuators["current"])
    await f.tick(amps=8)
    await f.tick(amps=0)
    f.refresh(300)
    f.ignore.clear()
    await f.tick(amps=8)
    f.refresh()
    await f.tick(amps=8)
    assert not f.actuator.delivery_fault


async def test_incident_storage_failure_cannot_prevent_fault_stop():
    f = ChargerFixture()
    f.set("charger_error", 13)
    f.refresh()

    def full_disk(*_):
        raise RuntimeError("SYNTHETIC evidence storage failure")

    f.actuator.on_delivery_fault = full_disk
    with pytest.raises(RuntimeError, match="storage failure"):
        await f.tick()
    assert f.actuator.delivery_fault
    assert f.calls[-1][2] == {"entity_id": f.actuators["force"], "option": "1"}


async def test_error_during_pending_start_sends_a_new_stop_immediately():
    f = ChargerFixture()
    await f.tick()
    f.refresh(30)
    f.actuator.goe_control.stop_sent = f.at
    await f.tick()
    f.set("charger_error", 13)
    f.refresh(1)
    await f.tick()
    assert f.calls[-1][2] == {"entity_id": f.actuators["force"], "option": "1"}


async def test_restart_waits_thirty_seconds_without_resetting_for_ticks_current_or_plan_updates():
    f = ChargerFixture()
    await f.tick()
    ready = f.actuator.resume_after
    f.refresh(10)
    await f.tick(amps=8, generation=2)
    f.refresh(5)
    await f.tick(amps=8, generation=2)
    f.refresh(14)
    await f.tick(amps=8, generation=2)
    assert f.actuator.resume_after == ready
    assert f.rows[f.actuators["force"]]["state"] == "1"
    assert f.actuator.charging_since is None and not f.incidents
    assert len([c for c in f.calls if c[2]["entity_id"] == f.actuators["ess_setpoint"]]) == 4
    f.refresh(1)
    await f.tick(amps=8, generation=2)
    assert f.rows[f.actuators["force"]]["state"] == "2"


async def test_short_stop_waits_remaining_time_but_a_long_stop_does_not_add_another_pause():
    f = ChargerFixture()
    await f.start()
    await f.tick(amps=0, power=1.38)
    f.refresh()
    await f.tick(amps=0)
    f.refresh(29)
    await f.tick()
    assert f.rows[f.actuators["force"]]["state"] == "1"
    f.refresh(1)
    await f.tick()
    assert f.rows[f.actuators["force"]]["state"] == "2"
    f.refresh()
    await f.tick(power=1.38)
    await f.tick(amps=0, power=1.38)
    f.refresh()
    await f.tick(amps=0)
    f.refresh(60)
    await f.tick()
    assert f.rows[f.actuators["force"]]["state"] == "2"
    assert not f.incidents


@pytest.mark.parametrize("initial,target", [(1, 3), (3, 1)])
async def test_each_phase_direction_holds_thirty_seconds_after_acknowledgement(initial, target):
    f = ChargerFixture()
    f.actuator.c = replace(f.actuator.c, phase_dwell_seconds=900)
    f.actuator.switched_at = f.at  # Even a legacy configured cooldown must be ignored.
    f.set("phase", 2 if initial == 3 else 1)
    f.set("force", 2)
    f.refresh()
    await f.tick(phases=target, power=2)
    f.refresh()
    await f.tick(phases=target)
    f.refresh(10)
    await f.tick(phases=target)
    assert "phase" in f.actuator.goe_control.pending
    f.refresh()
    await f.tick(phases=target)
    acknowledged = f.at
    assert f.actuator.resume_after == acknowledged + timedelta(seconds=30)
    f.refresh(29)
    await f.tick(phases=target)
    assert f.rows[f.actuators["force"]]["state"] == "1"
    f.refresh(1)
    await f.tick(phases=target)
    assert f.rows[f.actuators["force"]]["state"] == "2"
    assert not f.incidents


@pytest.mark.parametrize("amps", [6, 12])
async def test_current_only_adjustments_never_stop_or_start_a_settling_period(amps):
    f = ChargerFixture()
    await f.start(amps=8)
    f.calls.clear()
    await f.tick(amps=amps, power=1.84)
    f.refresh()
    await f.tick(amps=amps, power=amps * .23)
    assert [c[2] for c in f.calls if c[2]["entity_id"] == f.actuators["force"]] == []
    assert f.actuator.resume_after is None
    assert f.rows[f.actuators["current"]]["state"] == str(amps)


async def test_new_stop_cancels_settling_start_and_later_restart_still_waits():
    f = ChargerFixture()
    await f.tick()
    f.refresh(10)
    await f.tick(amps=0)
    assert not any(c[2].get("option") == "2" for c in f.calls)
    f.refresh(19)
    await f.tick(generation=2)
    assert f.rows[f.actuators["force"]]["state"] == "1"
    f.refresh(1)
    await f.tick(generation=2)
    assert f.rows[f.actuators["force"]]["state"] == "2"


async def test_restart_never_treats_continuing_power_as_a_settled_stop():
    f = ChargerFixture()
    await f.tick(power=1.38)
    f.refresh(30)
    await f.tick(power=1.38)
    assert f.actuator.delivery_fault
    assert "power did not stop" in f.incidents[0]
    assert not any(c[2].get("option") == "2" for c in f.calls)
