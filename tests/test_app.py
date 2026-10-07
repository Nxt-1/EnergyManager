from __future__ import annotations

import asyncio
from typing import Any

from energymanager.app import EnergyManagerApp
from energymanager.config import EssSettings, EvSettings, GridSettings, PvSettings, Settings
from energymanager.diagnostics import (
    BACKGROUND_LOAD_POWER_ENTITY,
    ESS_POWER_ENTITY,
    ESS_SOC_ENTITY,
    EV_CONNECTED_ENTITY,
    GRID_NET_POWER_ENTITY,
    HOUSE_LOAD_POWER_ENTITY,
    INPUT_HEALTH_ENTITY,
    KNOWN_CONTROLLABLE_LOAD_POWER_ENTITY,
    PV_TOTAL_POWER_ENTITY,
    STATUS_ENTITY,
)


class FakeHomeAssistantClient:
    def __init__(self) -> None:
        self.states: dict[str, dict[str, Any]] = {}
        self.deleted: list[str] = []
        self.replaced_options: dict[str, Any] | None = None

    async def set_state(self, entity_id: str, state: str | int | float, attributes: dict[str, Any]) -> None:
        self.states[entity_id] = {"state": str(state), "attributes": attributes}

    async def delete_state(self, entity_id: str) -> bool:
        self.deleted.append(entity_id)
        return True

    async def replace_own_options(self, options: dict[str, Any]) -> None:
        self.replaced_options = options


def _state(value: str, unit: str | None = "W") -> dict[str, Any]:
    attributes = {} if unit is None else {"unit_of_measurement": unit}
    return {
        "state": value,
        "attributes": attributes,
        "last_updated": "2026-10-03T10:00:00+00:00",
    }


def _configured_app() -> tuple[EnergyManagerApp, FakeHomeAssistantClient]:
    settings = Settings(
        grid=GridSettings("sensor.grid_import", "sensor.grid_export"),
        ess=EssSettings("sensor.ess_soc", "sensor.ess_power", "discharge"),
        pv=PvSettings("sensor.solax", "sensor.shed"),
        ev=EvSettings("sensor.ev_soc", "binary_sensor.ev_connected", "sensor.ev_power"),
    )
    client = FakeHomeAssistantClient()
    return EnergyManagerApp(settings, client), client  # type: ignore[arg-type]


def test_inputs_publish_normalized_house_state_diagnostics() -> None:
    app, client = _configured_app()

    async def run() -> None:
        app._process_entity_state("sensor.grid_import", _state("1800"))
        app._process_entity_state("sensor.grid_export", _state("250"))
        app._process_entity_state("sensor.ess_soc", _state("72", "%"))
        app._process_entity_state("sensor.ess_power", _state("-800"))
        app._process_entity_state("sensor.solax", _state("1200"))
        app._process_entity_state("sensor.shed", _state("1800"))
        app._process_entity_state("sensor.ev_soc", _state("58", "%"))
        app._process_entity_state("binary_sensor.ev_connected", _state("on", None))
        app._process_entity_state("sensor.ev_power", _state("0"))
        await app._publish_house_state()

    asyncio.run(run())

    assert client.states[GRID_NET_POWER_ENTITY]["state"] == "1550.0"
    assert client.states[ESS_SOC_ENTITY]["state"] == "72.0"
    assert client.states[ESS_POWER_ENTITY]["state"] == "-800.0"
    assert client.states[PV_TOTAL_POWER_ENTITY]["state"] == "3000.0"
    assert client.states[HOUSE_LOAD_POWER_ENTITY]["state"] == "1950.0"
    assert client.states[KNOWN_CONTROLLABLE_LOAD_POWER_ENTITY]["state"] == "0.0"
    assert client.states[BACKGROUND_LOAD_POWER_ENTITY]["state"] == "1950.0"
    assert client.states[EV_CONNECTED_ENTITY]["state"] == "on"
    assert client.states[INPUT_HEALTH_ENTITY]["state"] == "healthy"
    assert client.states[STATUS_ENTITY]["state"] == "connected"


def test_invalid_configured_input_marks_health_degraded() -> None:
    app, client = _configured_app()

    async def run() -> None:
        for entity_id, state in (
            ("sensor.grid_import", _state("1000")),
            ("sensor.grid_export", _state("0")),
            ("sensor.ess_soc", _state("unavailable", "%")),
        ):
            app._process_entity_state(entity_id, state)
        await app._publish_house_state()

    asyncio.run(run())

    assert client.states[INPUT_HEALTH_ENTITY]["state"] == "degraded"
    assert client.states[STATUS_ENTITY]["state"] == "degraded"


def test_legacy_config_is_written_back_in_grouped_format() -> None:
    settings = Settings(
        grid=GridSettings("sensor.grid_import", "sensor.grid_export"),
        legacy_options_detected=True,
    )
    client = FakeHomeAssistantClient()
    app = EnergyManagerApp(settings, client)  # type: ignore[arg-type]

    asyncio.run(app._migrate_legacy_configuration())

    assert client.replaced_options is not None
    assert client.replaced_options["grid"]["import_power_entity"] == "sensor.grid_import"
    assert "grid_import_power_entity" not in client.replaced_options


def test_legacy_diagnostic_cleanup_is_requested() -> None:
    app, client = _configured_app()

    asyncio.run(app._cleanup_legacy_diagnostics())

    assert "sensor.energy_manager_observed_grid_power" in client.deleted
    assert "sensor.energy_manager_pv_day_ahead_today_energy" in client.deleted
    assert "sensor.energy_manager_pv_day_ahead_tomorrow_energy" in client.deleted
