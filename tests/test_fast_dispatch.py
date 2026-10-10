from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from energymanager.actuators import ActuatorRegistry
from energymanager.config import EssSettings, EvSettings, Settings
from energymanager.fast_dispatch import FAST_DISPATCH_STATUS_ENTITY, evaluate_fast_dispatch, publish_fast_dispatch
from energymanager.house_state import HouseState
from energymanager.planner import ShadowPlan, ShadowPlanInterval

_NOW = datetime(2026, 10, 10, 15, 30, tzinfo=UTC)


def _state(*, grid_w: float, ess_w: float, ev_w: float = 0.0) -> HouseState:
    state = HouseState()
    values = {
        "grid.import_power": max(0.0, grid_w),
        "grid.export_power": max(0.0, -grid_w),
        "ess.soc": 60.0,
        "ess.power": ess_w,
        "pv.solax_power": 0.0,
        "ev.connected": True,
        "ev.soc": 40.0,
        "ev.charging_power": ev_w,
    }
    for key, value in values.items():
        reading = state.ensure_input(key, f"sensor.{key.replace('.', '_')}")
        reading.set_valid(value, unit=None, observed_at_utc=_NOW, source_last_updated=None)
    return state


def _registry() -> ActuatorRegistry:
    settings = Settings(
        ess=EssSettings(
            soc_entity="sensor.ess_soc",
            power_entity="sensor.ess_power",
            max_charge_power_w=2000.0,
            max_discharge_power_w=2000.0,
        ),
        ev=EvSettings(
            soc_entity="sensor.ev_soc",
            connected_entity="sensor.ev_connected",
            charging_power_entity="sensor.ev_power",
            battery_capacity_kwh=52.0,
        ),
    )
    return ActuatorRegistry(settings)


def _plan(*, planned_grid_w: float, planned_ess_w: float, planned_ev_w: float = 0.0) -> ShadowPlan:
    interval = ShadowPlanInterval(
        period_start_local=_NOW,
        background_load_w=1000.0,
        scheduled_load_w=planned_ev_w,
        pv_ac_power_w=0.0,
        pv_dc_power_w=0.0,
        pv_power_w=0.0,
        net_power_before_control_w=1000.0 + planned_ev_w,
        ess_ac_power_w=planned_ess_w,
        projected_soc_percent=55.0,
        grid_power_after_ess_w=planned_grid_w,
        curtailed_dc_pv_w=0.0,
    )
    return ShadowPlan(generated_at_utc=_NOW, intervals=(interval,), ess_projection_status="projected")


def test_fast_dispatch_absorbs_unexpected_load_with_ess() -> None:
    plan = _plan(planned_grid_w=500.0, planned_ess_w=500.0)
    state = _state(grid_w=2000.0, ess_w=500.0)

    result = evaluate_fast_dispatch(plan, state, _registry(), now_utc=_NOW)

    assert result.status == "tracking"
    assert result.background_deviation_w == 1500.0
    assert result.requested_ess_power_w == 2000.0
    assert result.accepted_ess_power_w == 2000.0
    assert result.ess_correction_from_plan_w == 1500.0
    assert result.projected_grid_power_w == 500.0
    assert result.residual_to_plan_w == 0.0
    assert result.replan_required is False


def test_fast_dispatch_requests_replan_when_ess_cannot_absorb_deviation() -> None:
    plan = _plan(planned_grid_w=500.0, planned_ess_w=500.0)
    state = _state(grid_w=4000.0, ess_w=500.0)

    result = evaluate_fast_dispatch(plan, state, _registry(), now_utc=_NOW)

    assert result.status == "residual_requires_replan"
    assert result.requested_ess_power_w == 4000.0
    assert result.accepted_ess_power_w == 2000.0
    assert result.command_limited is True
    assert result.residual_to_plan_w == 2000.0
    assert result.replan_required is True
    assert result.replan_reason == "ess_correction_limit"


def test_fast_dispatch_substitutes_planned_ev_for_shadow_actual_ev() -> None:
    plan = _plan(planned_grid_w=2000.0, planned_ess_w=2000.0, planned_ev_w=3000.0)
    state = _state(grid_w=500.0, ess_w=500.0, ev_w=0.0)

    result = evaluate_fast_dispatch(plan, state, _registry(), now_utc=_NOW)

    assert result.estimated_grid_without_ess_with_planned_ev_w == 4000.0
    assert result.requested_ess_power_w == 2000.0
    assert result.projected_grid_power_w == 2000.0
    assert result.residual_to_plan_w == 0.0
    assert result.replan_required is False
    assert [item.actuator_id for item in result.command_results] == ["ess", "ev"]


class _FakeClient:
    def __init__(self) -> None:
        self.states: dict[str, dict[str, object]] = {}

    async def set_state(self, entity_id: str, state: str, attributes: dict[str, object]) -> None:
        self.states[entity_id] = {"state": state, "attributes": attributes}


def test_fast_dispatch_publishes_fixed_rate_runtime_metadata() -> None:
    client = _FakeClient()
    result = evaluate_fast_dispatch(
        _plan(planned_grid_w=500.0, planned_ess_w=500.0),
        _state(grid_w=500.0, ess_w=500.0),
        _registry(),
        now_utc=_NOW,
    )

    asyncio.run(
        publish_fast_dispatch(
            client,
            result,
            control_interval_seconds=1.0,
            dispatch_sequence=17,
            milp_solve_in_progress=True,
        )
    )

    attributes = client.states[FAST_DISPATCH_STATUS_ENTITY]["attributes"]
    assert isinstance(attributes, dict)
    assert attributes["control_interval_seconds"] == 1.0
    assert attributes["dispatch_sequence"] == 17
    assert attributes["milp_solve_in_progress"] is True


def test_fast_dispatch_live_control_uses_actual_grid_not_planned_ev_substitution() -> None:
    plan = _plan(planned_grid_w=0.0, planned_ess_w=500.0, planned_ev_w=3000.0)
    state = _state(grid_w=500.0, ess_w=500.0, ev_w=0.0)

    result = evaluate_fast_dispatch(plan, state, _registry(), now_utc=_NOW, live_control=True)

    assert result.requested_ess_power_w == 1000.0
    assert result.accepted_ess_power_w == 1000.0
    assert result.projected_grid_power_w == 0.0
    assert result.residual_to_plan_w == 0.0
    assert result.replan_required is False


def test_fast_dispatch_live_control_holds_current_ess_inside_deadband() -> None:
    plan = _plan(planned_grid_w=0.0, planned_ess_w=500.0)
    state = _state(grid_w=80.0, ess_w=500.0)

    result = evaluate_fast_dispatch(plan, state, _registry(), now_utc=_NOW, live_control=True)

    assert result.requested_ess_power_w == 500.0
    assert result.accepted_ess_power_w == 500.0
    assert result.projected_grid_power_w == 80.0
    assert result.replan_required is False
