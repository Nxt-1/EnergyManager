from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from energymanager.actuators import EssActuatorSnapshot, EssCapabilities
from energymanager.load_forecast import BackgroundLoadForecast, BackgroundLoadForecastPoint
from energymanager.planner import ShadowPlanner
from energymanager.pv_forecast import PvForecast, PvForecastPoint

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


def _pv_forecast(start: datetime, hourly_powers: list[float], *, shed_w: float = 0.0) -> PvForecast:
    return PvForecast(
        generated_at_utc=start.astimezone(UTC),
        points=tuple(
            PvForecastPoint(
                period_end_local=start + timedelta(hours=index + 1),
                front_power_w=power,
                rear_power_w=0.0,
                shed_power_w=shed_w,
                total_power_w=power + shed_w,
                front_raw_power_w=power,
                rear_raw_power_w=0.0,
                shed_raw_power_w=shed_w,
                cloud_cover_pct=None,
                direct_radiation_wm2=None,
                diffuse_radiation_wm2=None,
            )
            for index, power in enumerate(hourly_powers)
        ),
    )


def _ess() -> EssActuatorSnapshot:
    return EssActuatorSnapshot(
        actuator_id="ess",
        kind="storage",
        configured=True,
        planning_available=True,
        status="ready",
        control_enabled=False,
        soc_percent=50.0,
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


def test_shadow_planner_builds_neutral_milp_input_frame() -> None:
    start = datetime(2026, 10, 8, 12, 0, tzinfo=_LOCAL)
    plan = ShadowPlanner().build(
        _load_forecast(start, [1000.0] * 4),
        _pv_forecast(start, [400.0], shed_w=100.0),
        now_utc=start.astimezone(UTC),
        actuators=(_ess(),),
    )

    assert len(plan.intervals) == 4
    assert plan.scheduling_strategy == "milp_input"
    assert plan.optimizer_status == "pending"
    assert plan.ess_projection_status == "not_solved"
    assert plan.ess_initial_soc_percent == pytest.approx(50.0)
    assert all(item.scheduled_load_w == 0.0 for item in plan.intervals)
    assert all(item.pv_ac_power_w == pytest.approx(400.0) for item in plan.intervals)
    assert all(item.pv_dc_power_w == pytest.approx(100.0) for item in plan.intervals)
    assert all(item.net_power_before_control_w == pytest.approx(500.0) for item in plan.intervals)


def test_shadow_plan_summary_keeps_ac_and_dc_pv_separate() -> None:
    start = datetime(2026, 10, 8, 12, 0, tzinfo=_LOCAL)
    plan = ShadowPlanner().build(
        _load_forecast(start, [1000.0] * 4),
        _pv_forecast(start, [400.0], shed_w=100.0),
        now_utc=start.astimezone(UTC),
    )
    summary = plan.summary(1)

    assert summary["background_load_kwh"] == pytest.approx(1.0)
    assert summary["pv_ac_potential_kwh"] == pytest.approx(0.4)
    assert summary["pv_dc_potential_kwh"] == pytest.approx(0.1)
    assert summary["pv_potential_kwh"] == pytest.approx(0.5)
    assert summary["net_deficit_kwh"] == pytest.approx(0.5)


def test_shadow_planner_accepts_full_seven_day_horizon() -> None:
    start = datetime(2026, 10, 8, 0, 0, tzinfo=_LOCAL)
    intervals = 7 * 24 * 4
    plan = ShadowPlanner().build(
        _load_forecast(start, [500.0] * intervals),
        _pv_forecast(start, [0.0] * (7 * 24)),
        now_utc=start.astimezone(UTC),
    )

    assert len(plan.intervals) == intervals
    assert plan.summary(168)["intervals"] == intervals


def test_shadow_planner_rejects_naive_now() -> None:
    start = datetime(2026, 10, 8, 12, 0, tzinfo=_LOCAL)
    with pytest.raises(ValueError):
        ShadowPlanner().build(
            _load_forecast(start, [500.0]),
            _pv_forecast(start, [0.0]),
            now_utc=datetime(2026, 10, 8, 10, 0),
        )
