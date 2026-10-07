from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from energymanager.actuators import (
    EssActuatorSnapshot,
    EssCapabilities,
    EvActuatorSnapshot,
    EvCapabilities,
)
from energymanager.load_forecast import BackgroundLoadForecast, BackgroundLoadForecastPoint
from energymanager.planner import ShadowPlanner
from energymanager.pv_forecast import PvForecast, PvForecastPoint
from energymanager.tasks import PlanningTask

_LOCAL = ZoneInfo("Europe/Brussels")


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


def _pv_forecast(start: datetime, hourly_powers: list[float]) -> PvForecast:
    points = []
    for index, power in enumerate(hourly_powers, start=1):
        end = start + timedelta(hours=index)
        points.append(
            PvForecastPoint(
                period_end_local=end,
                front_power_w=power,
                rear_power_w=0.0,
                shed_power_w=0.0,
                total_power_w=power,
                front_raw_power_w=power,
                rear_raw_power_w=0.0,
                shed_raw_power_w=0.0,
                cloud_cover_pct=None,
                direct_radiation_wm2=None,
                diffuse_radiation_wm2=None,
            )
        )
    return PvForecast(generated_at_utc=start.astimezone(UTC), points=tuple(points))


def _ess_actuator(*, soc_percent: float = 50.0, **overrides: float) -> EssActuatorSnapshot:
    values = {
        "capacity_kwh": 10.0,
        "min_soc_percent": 10.0,
        "max_soc_percent": 100.0,
        "max_charge_power_w": 2000.0,
        "max_discharge_power_w": 2000.0,
        "charge_efficiency": 1.0,
        "discharge_efficiency": 1.0,
    }
    values.update(overrides)
    return EssActuatorSnapshot(
        actuator_id="ess",
        kind="storage",
        configured=True,
        planning_available=True,
        status="ready",
        control_enabled=False,
        soc_percent=soc_percent,
        current_power_w=0.0,
        capabilities=EssCapabilities(**values),
    )


def _ev_actuator() -> EvActuatorSnapshot:
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


def _ev_task(start: datetime, *, required_energy_kwh: float, end: datetime) -> PlanningTask:
    return PlanningTask(
        task_id="ev_charge",
        kind="energy_by_deadline",
        source="test",
        actuator_id="ev",
        status="ready",
        planning_available=True,
        earliest_start_local=start,
        latest_end_local=end,
        required_energy_kwh=required_energy_kwh,
        battery_energy_required_kwh=required_energy_kwh * 0.90,
        interruptible=True,
        current_soc_percent=50.0,
        target_soc_percent=80.0,
        feasible_at_max_power=True,
        minimum_runtime_hours=required_energy_kwh / 11.04,
    )


def test_shadow_plan_combines_load_and_pv_on_quarter_hour_timeline() -> None:
    start = datetime(2026, 10, 6, 12, 0, tzinfo=_LOCAL)
    plan = ShadowPlanner().build(
        _load_forecast(start, [1000.0] * 4),
        _pv_forecast(start, [400.0]),
        now_utc=start.astimezone(UTC),
    )
    assert len(plan.intervals) == 4
    assert all(point.pv_power_w == pytest.approx(400.0) for point in plan.intervals)
    assert all(point.net_power_before_control_w == pytest.approx(600.0) for point in plan.intervals)
    assert plan.summary(1)["net_deficit_kwh"] == pytest.approx(0.6)
    assert plan.summary(1)["net_surplus_kwh"] == pytest.approx(0.0)


def test_shadow_plan_reports_surplus_separately_from_deficit() -> None:
    start = datetime(2026, 10, 6, 12, 0, tzinfo=_LOCAL)
    plan = ShadowPlanner().build(
        _load_forecast(start, [250.0] * 4),
        _pv_forecast(start, [1000.0]),
        now_utc=start.astimezone(UTC),
    )
    summary = plan.summary(1)
    assert summary["background_load_kwh"] == pytest.approx(0.25)
    assert summary["pv_potential_kwh"] == pytest.approx(1.0)
    assert summary["net_deficit_kwh"] == pytest.approx(0.0)
    assert summary["net_surplus_kwh"] == pytest.approx(0.75)


def test_shadow_plan_uses_zero_for_missing_pv_interval() -> None:
    start = datetime(2026, 10, 6, 12, 0, tzinfo=_LOCAL)
    plan = ShadowPlanner().build(
        _load_forecast(start, [500.0] * 8),
        _pv_forecast(start, [100.0]),
        now_utc=start.astimezone(UTC),
    )

    assert all(point.pv_power_w == pytest.approx(100.0) for point in plan.intervals[:4])
    assert all(point.pv_power_w == pytest.approx(0.0) for point in plan.intervals[4:])


def test_shadow_plan_rejects_naive_now() -> None:
    start = datetime(2026, 10, 6, 12, 0, tzinfo=_LOCAL)

    with pytest.raises(ValueError):
        ShadowPlanner().build(
            _load_forecast(start, [1000.0]),
            _pv_forecast(start, [0.0]),
            now_utc=datetime(2026, 10, 6, 10, 0),
        )


def test_ev_task_is_scheduled_into_feasible_discrete_charge_steps() -> None:
    start = datetime(2026, 10, 6, 12, 0, tzinfo=_LOCAL)
    task = _ev_task(start, required_energy_kwh=3.0, end=start + timedelta(hours=2))
    plan = ShadowPlanner().build(
        _load_forecast(start, [500.0] * 8),
        _pv_forecast(start, [0.0, 0.0]),
        now_utc=start.astimezone(UTC),
        actuators=(_ev_actuator(),),
        tasks=(task,),
    )

    scheduled = [item.scheduled_load_w for item in plan.intervals if item.scheduled_load_w > 0.0]
    scheduled_energy = sum(scheduled) * 0.25 / 1000.0
    assert scheduled == pytest.approx([11040.0, 1380.0])
    assert scheduled_energy >= 3.0
    assert scheduled_energy - 3.0 < 1.38 * 0.25


def test_ev_task_does_not_change_raw_background_pv_deficit_metric() -> None:
    start = datetime(2026, 10, 6, 12, 0, tzinfo=_LOCAL)
    task = _ev_task(start, required_energy_kwh=3.0, end=start + timedelta(hours=2))
    plan = ShadowPlanner().build(
        _load_forecast(start, [1000.0] * 8),
        _pv_forecast(start, [0.0, 0.0]),
        now_utc=start.astimezone(UTC),
        actuators=(_ev_actuator(),),
        tasks=(task,),
    )
    summary = plan.summary(2)

    assert summary["net_deficit_kwh"] == pytest.approx(2.0)
    assert float(summary["scheduled_load_kwh"]) >= 3.0


def test_ev_scheduled_load_is_included_in_ess_projection() -> None:
    start = datetime(2026, 10, 6, 12, 0, tzinfo=_LOCAL)
    task = _ev_task(start, required_energy_kwh=3.0, end=start + timedelta(hours=2))
    plan = ShadowPlanner().build(
        _load_forecast(start, [0.0] * 8),
        _pv_forecast(start, [0.0, 0.0]),
        now_utc=start.astimezone(UTC),
        actuators=(_ess_actuator(soc_percent=50.0), _ev_actuator()),
        tasks=(task,),
    )
    summary = plan.summary(2)

    assert summary["scheduled_load_kwh"] == pytest.approx(3.105)
    assert summary["ess_ac_discharge_kwh"] == pytest.approx(0.845)
    assert summary["grid_import_after_ess_kwh"] == pytest.approx(2.26)


def test_ess_projection_discharge_reduces_grid_import_and_soc() -> None:
    start = datetime(2026, 10, 6, 12, 0, tzinfo=_LOCAL)
    plan = ShadowPlanner().build(
        _load_forecast(start, [1500.0] * 4),
        _pv_forecast(start, [0.0]),
        now_utc=start.astimezone(UTC),
        actuators=(_ess_actuator(soc_percent=50.0),),
    )
    summary = plan.summary(1)
    assert plan.ess_projection_status == "projected"
    assert summary["grid_import_after_ess_kwh"] == pytest.approx(0.0)
    assert summary["ess_ac_discharge_kwh"] == pytest.approx(1.5)
    assert summary["end_soc_percent"] == pytest.approx(35.0)


def test_ess_projection_respects_soc_floor() -> None:
    start = datetime(2026, 10, 6, 12, 0, tzinfo=_LOCAL)
    plan = ShadowPlanner().build(
        _load_forecast(start, [2000.0] * 4),
        _pv_forecast(start, [0.0]),
        now_utc=start.astimezone(UTC),
        actuators=(_ess_actuator(soc_percent=50.0, min_soc_percent=40.0),),
    )
    summary = plan.summary(1)
    assert summary["battery_discharge_stored_kwh"] == pytest.approx(1.0)
    assert summary["grid_import_after_ess_kwh"] == pytest.approx(1.0)
    assert summary["end_soc_percent"] == pytest.approx(40.0)


def test_dc_coupled_pv_must_pass_through_ess_power_path_to_serve_ac_load() -> None:
    start = datetime(2026, 10, 6, 12, 0, tzinfo=_LOCAL)
    pv = PvForecast(
        generated_at_utc=start.astimezone(UTC),
        points=(
            PvForecastPoint(
                period_end_local=start + timedelta(hours=1),
                front_power_w=0.0,
                rear_power_w=0.0,
                shed_power_w=4000.0,
                total_power_w=4000.0,
                front_raw_power_w=0.0,
                rear_raw_power_w=0.0,
                shed_raw_power_w=4000.0,
                cloud_cover_pct=None,
                direct_radiation_wm2=None,
                diffuse_radiation_wm2=None,
            ),
        ),
    )
    plan = ShadowPlanner().build(
        _load_forecast(start, [3000.0] * 4),
        pv,
        now_utc=start.astimezone(UTC),
        actuators=(
            _ess_actuator(
                soc_percent=100.0,
                max_discharge_power_w=2000.0,
                max_charge_power_w=1000.0,
            ),
        ),
    )
    summary = plan.summary(1)
    assert summary["net_deficit_kwh"] == pytest.approx(0.0)
    assert summary["grid_import_after_ess_kwh"] == pytest.approx(1.0)
    assert summary["curtailed_dc_pv_kwh"] == pytest.approx(2.0)


def test_ess_projection_charges_from_ac_surplus() -> None:
    start = datetime(2026, 10, 6, 12, 0, tzinfo=_LOCAL)
    plan = ShadowPlanner().build(
        _load_forecast(start, [500.0] * 4),
        _pv_forecast(start, [1500.0]),
        now_utc=start.astimezone(UTC),
        actuators=(_ess_actuator(soc_percent=50.0),),
    )
    summary = plan.summary(1)
    assert summary["grid_export_after_ess_kwh"] == pytest.approx(0.0)
    assert summary["ess_ac_charge_kwh"] == pytest.approx(1.0)
    assert summary["end_soc_percent"] == pytest.approx(60.0)
