from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from energymanager.actuators import ActuatorRegistry
from energymanager.config import EssSettings, Settings
from energymanager.diagnostics import (
    ACTUATOR_COMMAND_STATUS_ENTITY,
    ACTUATOR_STATUS_ENTITY,
    SHADOW_PLAN_NET_DEFICIT_ENTITY,
    SHADOW_PLAN_STATUS_ENTITY,
    TASK_STATUS_ENTITY,
)
from energymanager.house_state import HouseState
from energymanager.load_forecast import BackgroundLoadForecast, BackgroundLoadForecastPoint
from energymanager.planner_service import ShadowPlannerService
from energymanager.pv_forecast import PvForecast, PvForecastPoint
from energymanager.tasks import TaskRegistry

_LOCAL = ZoneInfo("Europe/Brussels")


class FakeHomeAssistantClient:
    def __init__(self) -> None:
        self.states: dict[str, dict[str, Any]] = {}

    async def set_state(self, entity_id: str, state: str | int | float, attributes: dict[str, Any]) -> None:
        self.states[entity_id] = {"state": str(state), "attributes": attributes}


class FakeLoadService:
    def __init__(self, forecast: BackgroundLoadForecast | None) -> None:
        self.forecast = forecast


class FakePvService:
    def __init__(self, forecast: PvForecast | None) -> None:
        self.forecast = forecast


def _forecasts(start: datetime) -> tuple[BackgroundLoadForecast, PvForecast]:
    load = BackgroundLoadForecast(
        generated_at_utc=start.astimezone(UTC),
        points=tuple(
            BackgroundLoadForecastPoint(start + timedelta(minutes=15 * index), 1000.0, "test")
            for index in range(8)
        ),
        history_sample_count=100,
        history_days=30.0,
        model_stage="connected",
    )
    pv = PvForecast(
        generated_at_utc=start.astimezone(UTC),
        points=tuple(
            PvForecastPoint(
                period_end_local=start + timedelta(hours=index),
                front_power_w=400.0,
                rear_power_w=0.0,
                shed_power_w=0.0,
                total_power_w=400.0,
                front_raw_power_w=400.0,
                rear_raw_power_w=0.0,
                shed_raw_power_w=0.0,
                cloud_cover_pct=None,
                direct_radiation_wm2=None,
                diffuse_radiation_wm2=None,
            )
            for index in (1, 2)
        ),
    )
    return load, pv


def test_planner_service_waits_for_pv_forecast() -> None:
    start = datetime(2026, 10, 6, 12, 0, tzinfo=_LOCAL)
    load, _ = _forecasts(start)
    client = FakeHomeAssistantClient()
    service = ShadowPlannerService(
        client,
        FakeLoadService(load),  # type: ignore[arg-type]
        FakePvService(None),  # type: ignore[arg-type]
        actuator_registry=ActuatorRegistry(Settings()),
        task_registry=TaskRegistry(Settings().ev),
    )
    asyncio.run(service.update_from_house_state(HouseState(), now_utc=start.astimezone(UTC)))

    assert client.states[SHADOW_PLAN_STATUS_ENTITY]["state"] == "waiting_for_pv_forecast"


def test_planner_service_publishes_ready_plan() -> None:
    start = datetime(2026, 10, 6, 12, 0, tzinfo=_LOCAL)
    load, pv = _forecasts(start)
    client = FakeHomeAssistantClient()
    service = ShadowPlannerService(
        client,
        FakeLoadService(load),  # type: ignore[arg-type]
        FakePvService(pv),  # type: ignore[arg-type]
        actuator_registry=ActuatorRegistry(Settings()),
        task_registry=TaskRegistry(Settings().ev),
    )
    asyncio.run(service.update_from_house_state(HouseState(), now_utc=start.astimezone(UTC)))

    assert client.states[SHADOW_PLAN_STATUS_ENTITY]["state"] == "ready"
    assert client.states[SHADOW_PLAN_NET_DEFICIT_ENTITY]["state"] == "1.2"
    assert client.states[ACTUATOR_STATUS_ENTITY]["state"] == "not_configured"
    assert client.states[TASK_STATUS_ENTITY]["state"] == "not_configured"
    assert service.plan is not None
    assert [task.task_id for task in service.plan.tasks] == ["ev_charge"]


def test_planner_service_projects_ess_when_soc_is_valid() -> None:
    from energymanager.diagnostics import SHADOW_PLAN_GRID_IMPORT_ENTITY

    start = datetime(2026, 10, 6, 12, 0, tzinfo=_LOCAL)
    load, pv = _forecasts(start)
    client = FakeHomeAssistantClient()
    settings = EssSettings(
        soc_entity="sensor.ess_soc",
        capacity_kwh=10.0,
        min_soc_percent=10.0,
        max_soc_percent=100.0,
        max_charge_power_w=2000.0,
        max_discharge_power_w=2000.0,
        charge_efficiency=1.0,
        discharge_efficiency=1.0,
    )
    house_state = HouseState()
    reading = house_state.ensure_input("ess.soc", "sensor.ess_soc")
    reading.set_valid(
        50.0,
        unit="%",
        observed_at_utc=start.astimezone(UTC),
        source_last_updated=start.astimezone(UTC).isoformat(),
    )
    service = ShadowPlannerService(
        client,
        FakeLoadService(load),  # type: ignore[arg-type]
        FakePvService(pv),  # type: ignore[arg-type]
        actuator_registry=ActuatorRegistry(Settings(ess=settings)),
        task_registry=TaskRegistry(Settings().ev),
    )
    asyncio.run(service.update_from_house_state(house_state, now_utc=start.astimezone(UTC)))

    assert client.states[SHADOW_PLAN_STATUS_ENTITY]["attributes"]["ess_projection_status"] == "projected"
    assert client.states[SHADOW_PLAN_GRID_IMPORT_ENTITY]["state"] == "0.0"
    command = client.states[ACTUATOR_COMMAND_STATUS_ENTITY]
    assert command["state"] == "accepted"
    assert command["attributes"]["hardware_writes"] is False
    assert command["attributes"]["commands"][0]["id"] == "ess"
