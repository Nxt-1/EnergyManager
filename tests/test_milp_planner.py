from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from energymanager.actuators import EssActuatorSnapshot, EssCapabilities, EvActuatorSnapshot, EvCapabilities
from energymanager.economics import CapacityPeakState, TariffProfile
from energymanager.load_forecast import BackgroundLoadForecast, BackgroundLoadForecastPoint
from energymanager.milp_planner import MilpEvaluation, evaluate_shadow_plan_milp, publish_milp_evaluation
from energymanager.planner import ShadowPlanner
from energymanager.pv_forecast import PvForecast, PvForecastPoint
from energymanager.tasks import PlanningTask

_LOCAL = ZoneInfo("Europe/Brussels")


class FakeHomeAssistantClient:
    def __init__(self) -> None:
        self.states: dict[str, dict[str, Any]] = {}

    async def set_state(self, entity_id: str, state: str | int | float, attributes: dict[str, Any]) -> None:
        self.states[entity_id] = {"state": str(state), "attributes": attributes}


def _load_forecast(start: datetime, powers: list[float]) -> BackgroundLoadForecast:
    return BackgroundLoadForecast(
        generated_at_utc=start.astimezone(UTC),
        points=tuple(
            BackgroundLoadForecastPoint(
                period_start_local=start + timedelta(minutes=15 * index),
                power_w=power,
                method="test",
            )
            for index, power in enumerate(powers)
        ),
        history_sample_count=100,
        history_days=30.0,
        model_stage="connected",
    )


def _pv_forecast(start: datetime, hourly_ac_w: list[float], *, hourly_dc_w: list[float] | None = None) -> PvForecast:
    dc = hourly_dc_w or [0.0] * len(hourly_ac_w)
    return PvForecast(
        generated_at_utc=start.astimezone(UTC),
        points=tuple(
            PvForecastPoint(
                period_end_local=start + timedelta(hours=index + 1),
                front_power_w=ac_power,
                rear_power_w=0.0,
                shed_power_w=dc[index],
                total_power_w=ac_power + dc[index],
                front_raw_power_w=ac_power,
                rear_raw_power_w=0.0,
                shed_raw_power_w=dc[index],
                cloud_cover_pct=None,
                direct_radiation_wm2=None,
                diffuse_radiation_wm2=None,
            )
            for index, ac_power in enumerate(hourly_ac_w)
        ),
    )


def _ess(*, soc_percent: float = 50.0) -> EssActuatorSnapshot:
    return EssActuatorSnapshot(
        actuator_id="ess",
        kind="storage",
        configured=True,
        planning_available=True,
        status="ready",
        control_enabled=False,
        soc_percent=soc_percent,
        current_power_w=0.0,
        capabilities=EssCapabilities(
            capacity_kwh=10.0,
            min_soc_percent=10.0,
            max_soc_percent=100.0,
            max_charge_power_w=2000.0,
            max_discharge_power_w=2000.0,
            charge_efficiency=0.95,
            discharge_efficiency=0.95,
        ),
    )


def _ev() -> EvActuatorSnapshot:
    return EvActuatorSnapshot(
        actuator_id="ev",
        kind="flexible_load",
        configured=True,
        planning_available=True,
        status="ready",
        control_enabled=False,
        connected=True,
        soc_percent=50.0,
        current_power_w=0.0,
        capabilities=EvCapabilities(
            min_charge_current_a=6.0,
            max_charge_current_a=16.0,
            nominal_voltage_v=230.0,
            supports_single_phase=True,
            supports_three_phase=True,
            battery_capacity_kwh=46.8,
            charge_efficiency=0.90,
        ),
    )


def _task(start: datetime, *, task_id: str = "ev_charge", energy_kwh: float = 3.0) -> PlanningTask:
    return PlanningTask(
        task_id=task_id,
        kind="energy_by_deadline",
        source="test",
        actuator_id="ev",
        status="ready",
        planning_available=True,
        earliest_start_local=start,
        latest_end_local=start + timedelta(hours=2),
        required_energy_kwh=energy_kwh,
        battery_energy_required_kwh=energy_kwh * 0.90,
        interruptible=True,
        current_soc_percent=50.0,
        target_soc_percent=80.0,
        feasible_at_max_power=True,
        minimum_runtime_hours=energy_kwh / 11.04,
    )


def _profile() -> TariffProfile:
    return TariffProfile(
        profile_id="test",
        valid_from_utc=datetime(2026, 9, 30, 22, 0, tzinfo=UTC),
        import_energy_eur_per_kwh=0.30556,
        export_energy_eur_per_kwh=0.0397,
        capacity_tariff_eur_per_kw_month=4.36417,
        capacity_tariff_floor_kw=2.5,
    )


def _capacity(start: datetime) -> CapacityPeakState:
    return CapacityPeakState(
        month_local="2026-10",
        observed_peak_kw=4.24,
        billing_peak_kw=4.24,
        peak_window_start_local=start - timedelta(days=1),
        peak_source="test",
        history_complete=True,
        estimated_window_count=1,
        live_window_count=0,
    )


def _reference_plan(start: datetime, *, tasks: tuple[PlanningTask, ...]) -> Any:
    return ShadowPlanner().build(
        _load_forecast(start, [500.0] * 8),
        _pv_forecast(start, [0.0, 0.0]),
        now_utc=start.astimezone(UTC),
        actuators=(_ess(), _ev()),
        tasks=tasks,
    )


def test_milp_rejects_multiple_active_tasks_without_affecting_reference_plan() -> None:
    start = datetime(2026, 10, 8, 12, 0, tzinfo=_LOCAL)
    tasks = (_task(start, task_id="ev_one"), _task(start, task_id="ev_two"))
    reference = _reference_plan(start, tasks=tasks)

    result = evaluate_shadow_plan_milp(reference, _profile(), _capacity(start))

    assert result.status == "unsupported"
    assert result.reason == "multiple_active_tasks_not_yet_supported"
    assert result.plan is None
    assert result.reference_strategy == reference.scheduling_strategy
    assert result.active_task_count == 2


def test_milp_status_publisher_marks_result_non_authoritative() -> None:
    client = FakeHomeAssistantClient()
    result = MilpEvaluation(
        status="optimal",
        model_status="Optimal",
        solver_version="test",
        solve_time_seconds=0.123,
        mip_gap=0.0,
        mip_node_count=12,
        variable_count=100,
        integer_variable_count=20,
        constraint_count=80,
        horizon_intervals=672,
        active_task_count=1,
        reference_strategy="economic_ev_portfolio:test",
        reference_objective_eur=12.0,
        milp_objective_eur=10.0,
        estimated_improvement_eur=2.0,
    )

    asyncio.run(publish_milp_evaluation(client, result))

    entity = client.states["sensor.energy_manager_milp_status"]
    assert entity["state"] == "optimal"
    assert entity["attributes"]["authoritative"] is False
    assert entity["attributes"]["hardware_writes"] is False
    assert entity["attributes"]["milp_objective_eur"] == 10.0
    assert entity["attributes"]["estimated_improvement_eur"] == 2.0


def test_highs_milp_solves_discrete_ev_and_ess_model_when_dependency_is_available() -> None:
    pytest.importorskip("highspy")
    start = datetime(2026, 10, 8, 12, 0, tzinfo=_LOCAL)
    task = _task(start, energy_kwh=3.0)
    reference = _reference_plan(start, tasks=(task,))

    result = evaluate_shadow_plan_milp(reference, _profile(), _capacity(start))

    assert result.status in {"optimal", "feasible", "feasible_time_limit"}
    assert result.plan is not None
    assert result.solve_time_seconds is not None
    assert result.variable_count > 0
    assert result.integer_variable_count > 0
    assert result.constraint_count > 0
    assert result.milp_objective_eur is not None
    scheduled_kwh = float(result.plan.summary(2)["scheduled_load_kwh"])
    assert scheduled_kwh >= 3.0
    assert scheduled_kwh - 3.0 < 6.0 * 230.0 * 0.25 / 1000.0
    summary = result.plan.summary(2)
    assert float(summary["min_soc_percent"]) >= 10.0 - 1e-6
    assert float(summary["max_soc_percent"]) <= 100.0 + 1e-6
