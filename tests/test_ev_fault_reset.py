"""Regression coverage for opt-in, one-shot go-e charging-fault reset."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from energymanager.config import ConfigurationError, EvSettings, Settings
from energymanager.ev_control import EV_CONTROL_STATUS_ENTITY, EvHardwareController
from energymanager.ha_client import HomeAssistantError

CURRENT = "number.charger_amp"
PHASE = "select.charger_psm"
FORCE = "select.charger_frc"
POWER = "sensor.charger_power"
RESET = "button.charger_rst"


class Client:
    def __init__(self, *, reset_fails: bool = False) -> None:
        self.states = {CURRENT: "6", PHASE: "1", FORCE: "2", POWER: "0"}
        self.calls: list[tuple[str, str, dict]] = []
        self.published: dict = {}
        self.reset_fails = reset_fails

    async def get_state(self, entity_id: str) -> dict:
        return {"state": self.states[entity_id]}

    async def call_service(self, domain: str, service: str, data: dict) -> None:
        self.calls.append((domain, service, data))
        if domain == "button":
            if self.reset_fails:
                raise HomeAssistantError("reset unavailable")
            return
        self.states[data["entity_id"]] = str(data.get("option", data.get("value", "")))

    async def set_state(self, entity_id: str, state: str, attributes: dict) -> None:
        self.published[entity_id] = {"state": state, "attributes": attributes}


class Snapshot:
    def __init__(self, power: float, connected: bool = True):
        self.power = power
        self.connected = connected

    def value(self, key: str) -> float | bool:
        return self.connected if key == "ev.connected" else self.power


def settings(*, enabled: bool = True, auto_reset: bool = True) -> EvSettings:
    return EvSettings(
        charging_power_entity=POWER, current_entity=CURRENT, phase_mode_entity=PHASE,
        force_state_entity=FORCE, reset_button_entity=RESET, control_enabled=enabled,
        automatic_fault_reset=auto_reset, fault_reset_delay_seconds=60, max_reset_attempts=1,
    )


def command() -> SimpleNamespace:
    return SimpleNamespace(command_results=(SimpleNamespace(
        actuator_id="ev", requested_power_w=1380, accepted_power_w=1380,
        phase_count=1, current_a=6, reason="planned",
    ),))


def fault(controller: EvHardwareController, *, now: datetime) -> None:
    controller._requested_charge_power_w = 1380
    controller._charge_enable_requested = True
    controller.observe_charging(Snapshot(0), now_utc=now - timedelta(seconds=100))
    controller.observe_charging(Snapshot(0), now_utc=now)


def reset_calls(client: Client) -> list[tuple[str, str, dict]]:
    return [call for call in client.calls if call[0] == "button"]


def test_single_reset_waits_for_delay_and_stop_confirmation() -> None:
    client = Client()
    controller = EvHardwareController(client, settings())
    now = datetime.now(UTC)
    fault(controller, now=now)
    assert controller.delivery_error == "connected_not_charging"

    async def scenario() -> None:
        await controller.apply_dispatch(command())
        assert not reset_calls(client)
        assert client.states[FORCE] == "1"
        controller._recovery_started_utc = datetime.now(UTC) - timedelta(seconds=61)
        client.states[POWER] = "500"  # Must not reset while power is measured.
        await controller.apply_dispatch(command())
        assert not reset_calls(client)
        client.states[POWER] = "0"
        await controller.apply_dispatch(command())
        await controller.apply_dispatch(command())

    asyncio.run(scenario())
    assert len(reset_calls(client)) == 1
    assert reset_calls(client)[0][2]["entity_id"] == RESET
    assert controller._reset_attempts == 1
    assert controller._reset_total_count == 1
    assert controller._last_reset_outcome == "requested"
    assert controller._recovery_state == "waiting_restart"
    assert client.published[EV_CONTROL_STATUS_ENTITY]["attributes"]["reset_attempts"] == 1


def test_verified_charging_is_required_to_clear_error() -> None:
    client = Client()
    controller = EvHardwareController(client, settings())
    fault(controller, now=datetime.now(UTC))
    controller._recovery_started_utc = datetime.now(UTC) - timedelta(seconds=61)

    async def scenario() -> None:
        await controller.apply_dispatch(command())
        controller._reset_issued_utc = datetime.now(UTC) - timedelta(seconds=35)
        await controller.apply_dispatch(command())
        assert controller._recovery_state == "test_charging"
        assert controller.delivery_error is not None
        started = datetime.now(UTC) - timedelta(seconds=21)
        controller.observe_charging(Snapshot(1380), now_utc=started)
        assert controller.delivery_error is not None
        controller.observe_charging(Snapshot(1380), now_utc=started + timedelta(seconds=21))

    asyncio.run(scenario())
    assert controller.delivery_error is None
    assert controller._recovery_state is None
    assert controller._last_reset_outcome == "verified_charging"
    assert len(reset_calls(client)) == 1


def test_failed_retry_latches_fault_with_no_second_reset() -> None:
    client = Client()
    controller = EvHardwareController(client, settings())
    fault(controller, now=datetime.now(UTC))
    controller._recovery_started_utc = datetime.now(UTC) - timedelta(seconds=61)

    async def scenario() -> None:
        await controller.apply_dispatch(command())
        controller._reset_issued_utc = datetime.now(UTC) - timedelta(seconds=35)
        await controller.apply_dispatch(command())
        controller._test_charging_since = datetime.now(UTC) - timedelta(seconds=91)
        controller.observe_charging(Snapshot(0))
        assert controller.delivery_error == "charging_fault_latched"
        for _ in range(5):
            await controller.apply_dispatch(command())

    asyncio.run(scenario())
    assert client.states[FORCE] == "1"
    assert controller._recovery_state == "manual_intervention"
    assert len(reset_calls(client)) == 1
    assert controller._last_reset_outcome == "charging_failed_after_reset"


def test_reset_failure_latches_without_retry() -> None:
    client = Client(reset_fails=True)
    controller = EvHardwareController(client, settings())
    fault(controller, now=datetime.now(UTC))
    controller._recovery_started_utc = datetime.now(UTC) - timedelta(seconds=61)

    async def scenario() -> None:
        await controller.apply_dispatch(command())
        await controller.apply_dispatch(command())

    asyncio.run(scenario())
    assert controller.delivery_error == "charging_fault_latched"
    assert len(reset_calls(client)) == 1


def test_reset_disabled_by_default_and_control_disabled_never_press() -> None:
    assert EvSettings().automatic_fault_reset is False
    client = Client()
    controller = EvHardwareController(client, settings(auto_reset=False))
    fault(controller, now=datetime.now(UTC))
    asyncio.run(controller.apply_dispatch(command()))
    assert controller.delivery_error == "charging_fault_latched"
    assert not reset_calls(client)
    disabled = EvHardwareController(client, replace(settings(), control_enabled=False))
    asyncio.run(disabled.apply_dispatch(command()))
    assert not reset_calls(client)


def test_reset_settings_roundtrip_in_existing_ev_group(tmp_path: Path) -> None:
    raw = Settings().as_options()
    raw["ev"].update({"charging_power_entity": POWER, "reset_button_entity": RESET, "automatic_fault_reset": True,
                      "fault_reset_delay_seconds": 75, "max_reset_attempts": 1})
    options_path = tmp_path / "options.json"
    options_path.write_text(json.dumps(raw))
    loaded = Settings.load(options_path)
    assert loaded.ev.reset_button_entity == RESET
    assert loaded.ev.fault_reset_delay_seconds == 75
    assert loaded.as_options()["ev"]["automatic_fault_reset"] is True
    assert "reset_button_entity" not in loaded.as_options()


@pytest.mark.parametrize("changes", [
    {"reset_button_entity": "select.charger_rst", "automatic_fault_reset": True},
    {"automatic_fault_reset": True},
    {"reset_button_entity": RESET, "automatic_fault_reset": True, "max_reset_attempts": 2},
])
def test_invalid_automatic_reset_config_rejected(changes: dict, tmp_path: Path) -> None:
    raw = Settings().as_options()
    raw["ev"].update(changes)
    options_path = tmp_path / "options.json"
    options_path.write_text(json.dumps(raw))
    with pytest.raises(ConfigurationError):
        Settings.load(options_path)


def test_phase_wait_without_charging_permission_cannot_trigger_false_retry_failure() -> None:
    client = Client()
    controller = EvHardwareController(client, settings())
    controller._recovery_state = "test_charging"
    controller._requested_charge_power_w = 6210
    controller._charge_enable_requested = False  # Still stopping for phase transition.
    controller._test_charging_since = datetime.now(UTC) - timedelta(seconds=180)
    controller.observe_charging(Snapshot(0))
    assert controller._recovery_state == "test_charging"
    assert not reset_calls(client)
