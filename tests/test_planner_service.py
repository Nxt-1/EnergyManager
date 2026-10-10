from __future__ import annotations

import asyncio
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from energymanager.actuators import ActuatorRegistry
from energymanager.config import EssSettings, Settings
from energymanager.diagnostics import SHADOW_PLAN_STATUS_ENTITY
from energymanager.economics import CapacityPeakState, TariffProfile
from energymanager.house_state import HouseState
from energymanager.load_forecast import BackgroundLoadForecast, BackgroundLoadForecastPoint
from energymanager.milp_planner import MilpEvaluation
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


class FakeEconomicsService:
    def __init__(self, start: datetime) -> None:
        self.optimizer_ready = True
        self.current_profile = TariffProfile(
            profile_id="test",
            valid_from_utc=datetime(2026, 9, 30, 22, 0, tzinfo=UTC),
            import_energy_eur_per_kwh=0.30556,
            export_energy_eur_per_kwh=0.0397,
            capacity_tariff_eur_per_kw_month=4.36417,
            capacity_tariff_floor_kw=2.5,
        )
        self.capacity_state = CapacityPeakState(
            month_local="2026-10",
            observed_peak_kw=4.24,
            billing_peak_kw=4.24,
            peak_window_start_local=start - timedelta(days=1),
            peak_source="test",
            history_complete=True,
            estimated_window_count=1,
            live_window_count=0,
        )

    async def observe_house_state(self, *args, **kwargs) -> None:
        return None

    async def publish_plan_cost(self, *args, **kwargs):
        return None


def _forecasts(start: datetime) -> tuple[BackgroundLoadForecast, PvForecast]:
    load = BackgroundLoadForecast(
        generated_at_utc=start.astimezone(UTC),
        points=tuple(
            BackgroundLoadForecastPoint(start + timedelta(minutes=15 * index), 1000.0, "test")
            for index in range(16)
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
            for index in range(1, 5)
        ),
    )
    return load, pv


def _house_state(start: datetime) -> HouseState:
    state = HouseState()
    reading = state.ensure_input("ess.soc", "sensor.ess_soc")
    reading.set_valid(50.0, unit="%", observed_at_utc=start.astimezone(UTC), source_last_updated=None)
    return state


def _settings() -> Settings:
    return Settings(
        ess=EssSettings(
            soc_entity="sensor.ess_soc",
            capacity_kwh=10.0,
            min_soc_percent=10.0,
            max_soc_percent=100.0,
            max_charge_power_w=2000.0,
            max_discharge_power_w=2000.0,
            charge_efficiency=1.0,
            discharge_efficiency=1.0,
        )
    )


def _solved_evaluation(frame) -> MilpEvaluation:
    intervals = tuple(
        replace(
            item,
            ess_ac_power_w=0.0,
            battery_energy_delta_kwh=0.0,
            projected_soc_percent=50.0,
            grid_power_after_ess_w=item.background_load_w - item.pv_ac_power_w,
            curtailed_dc_pv_w=0.0,
        )
        for item in frame.intervals
    )
    plan = replace(
        frame,
        intervals=intervals,
        ess_projection_status="projected",
        scheduling_strategy="milp_joint_ev_ess",
        optimizer_status="optimized",
    )
    return MilpEvaluation(
        status="optimal",
        model_status="Optimal",
        solver_version="test",
        solve_time_seconds=0.1,
        mip_gap=0.0,
        mip_node_count=1,
        variable_count=100,
        integer_variable_count=10,
        constraint_count=80,
        horizon_intervals=len(plan.intervals),
        active_task_count=0,
        reference_strategy="milp_input",
        reference_objective_eur=None,
        milp_objective_eur=1.0,
        estimated_improvement_eur=None,
        validation_status="passed",
        adoption_ready=True,
        fallback_to_reference=False,
        plan=plan,
    )


def test_planner_service_waits_for_pv_forecast() -> None:
    start = datetime(2026, 10, 8, 12, 0, tzinfo=_LOCAL)
    load, _ = _forecasts(start)
    client = FakeHomeAssistantClient()
    service = ShadowPlannerService(
        client,
        FakeLoadService(load),  # type: ignore[arg-type]
        FakePvService(None),  # type: ignore[arg-type]
        actuator_registry=ActuatorRegistry(_settings()),
        task_registry=TaskRegistry(Settings().ev),
        economics_service=FakeEconomicsService(start),  # type: ignore[arg-type]
    )
    asyncio.run(service.update_from_house_state(_house_state(start), now_utc=start.astimezone(UTC)))
    assert client.states[SHADOW_PLAN_STATUS_ENTITY]["state"] == "waiting_for_pv_forecast"


def test_planner_service_requires_economics_for_milp() -> None:
    start = datetime(2026, 10, 8, 12, 0, tzinfo=_LOCAL)
    load, pv = _forecasts(start)
    client = FakeHomeAssistantClient()
    service = ShadowPlannerService(
        client,
        FakeLoadService(load),  # type: ignore[arg-type]
        FakePvService(pv),  # type: ignore[arg-type]
        actuator_registry=ActuatorRegistry(_settings()),
        task_registry=TaskRegistry(Settings().ev),
    )
    asyncio.run(service.update_from_house_state(_house_state(start), now_utc=start.astimezone(UTC)))
    assert client.states[SHADOW_PLAN_STATUS_ENTITY]["state"] == "waiting_for_economics"


def test_planner_service_uses_ten_minute_periodic_cadence(monkeypatch) -> None:
    start = datetime(2026, 10, 8, 12, 0, tzinfo=_LOCAL)
    load, pv = _forecasts(start)
    client = FakeHomeAssistantClient()
    calls = 0

    def fake_solver(frame, profile, capacity_state):
        nonlocal calls
        calls += 1
        return _solved_evaluation(frame)

    monkeypatch.setattr("energymanager.planner_service.evaluate_shadow_plan_milp", fake_solver)
    service = ShadowPlannerService(
        client,
        FakeLoadService(load),  # type: ignore[arg-type]
        FakePvService(pv),  # type: ignore[arg-type]
        actuator_registry=ActuatorRegistry(_settings()),
        task_registry=TaskRegistry(Settings().ev),
        economics_service=FakeEconomicsService(start),  # type: ignore[arg-type]
    )
    state = _house_state(start)

    async def scenario() -> None:
        await service.update_from_house_state(state, now_utc=start.astimezone(UTC))
        assert service.solve_in_progress is True
        assert service._solve_task is not None
        await service._solve_task
        assert calls == 1

        await service.update_from_house_state(state, now_utc=(start + timedelta(minutes=5)).astimezone(UTC))
        assert calls == 1
        await service.update_from_house_state(state, now_utc=(start + timedelta(minutes=10)).astimezone(UTC))
        assert service._solve_task is not None
        await service._solve_task
        assert calls == 2

    asyncio.run(scenario())
    assert service.plan is not None
    assert service.plan.scheduling_strategy == "milp_joint_ev_ess"


def test_planner_service_returns_while_milp_worker_is_still_solving(monkeypatch) -> None:
    start = datetime(2026, 10, 8, 12, 0, tzinfo=_LOCAL)
    load, pv = _forecasts(start)
    client = FakeHomeAssistantClient()

    def slow_solver(frame, profile, capacity_state):
        time.sleep(0.15)
        return _solved_evaluation(frame)

    monkeypatch.setattr("energymanager.planner_service.evaluate_shadow_plan_milp", slow_solver)
    service = ShadowPlannerService(
        client,
        FakeLoadService(load),  # type: ignore[arg-type]
        FakePvService(pv),  # type: ignore[arg-type]
        actuator_registry=ActuatorRegistry(_settings()),
        task_registry=TaskRegistry(Settings().ev),
        economics_service=FakeEconomicsService(start),  # type: ignore[arg-type]
    )

    async def scenario() -> None:
        before = asyncio.get_running_loop().time()
        await service.update_from_house_state(_house_state(start), now_utc=start.astimezone(UTC))
        elapsed = asyncio.get_running_loop().time() - before
        assert elapsed < 0.10
        assert service.solve_in_progress is True
        assert service._solve_task is not None
        await service._solve_task
        assert service.plan is not None

    asyncio.run(scenario())
