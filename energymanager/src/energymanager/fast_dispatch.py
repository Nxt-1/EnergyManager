"""Fast shadow dispatch tracking between slower MILP replans."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from .actuators import ActuatorCommandResult, ActuatorPowerRequest, ActuatorRegistry
from .house_state import HouseState
from .planner import ShadowPlan, ShadowPlanInterval

FAST_DISPATCH_VERSION = "2026-10-10-fast-dispatch-v1"
FAST_DISPATCH_STATUS_ENTITY = "sensor.energy_manager_fast_dispatch_status"
_INTERVAL = timedelta(minutes=15)
_REPLAN_RESIDUAL_W = 500.0


@dataclass(frozen=True, slots=True)
class FastDispatchResult:
    """One live shadow correction around the current MILP interval."""

    status: str
    interval_start_local: datetime | None
    planned_grid_power_w: float | None
    planned_ess_power_w: float | None
    planned_ev_power_w: float | None
    measured_grid_power_w: float | None
    measured_ess_power_w: float | None
    measured_ev_power_w: float | None
    measured_background_power_w: float | None
    planned_background_power_w: float | None
    background_deviation_w: float | None
    estimated_grid_without_ess_with_planned_ev_w: float | None
    requested_ess_power_w: float | None
    accepted_ess_power_w: float | None
    ess_correction_from_plan_w: float | None
    projected_grid_power_w: float | None
    residual_to_plan_w: float | None
    command_limited: bool
    command_reason: str | None
    replan_required: bool
    replan_reason: str | None
    command_results: tuple[ActuatorCommandResult, ...] = ()


async def publish_fast_dispatch(client, result: FastDispatchResult) -> None:
    """Publish the live shadow dispatch correction into Home Assistant."""
    attributes: dict[str, Any] = {
        "friendly_name": "Energy Manager Fast Dispatch Status",
        "fast_dispatch_version": FAST_DISPATCH_VERSION,
        "shadow_mode": True,
        "control_enabled": False,
        "hardware_writes": False,
        "tracking_strategy": "milp_grid_target_with_live_ess_feedback",
        "interval_start_local": _iso(result.interval_start_local),
        "planned_grid_power_w": _round(result.planned_grid_power_w),
        "planned_ess_power_w": _round(result.planned_ess_power_w),
        "planned_ev_power_w": _round(result.planned_ev_power_w),
        "measured_grid_power_w": _round(result.measured_grid_power_w),
        "measured_ess_power_w": _round(result.measured_ess_power_w),
        "measured_ev_power_w": _round(result.measured_ev_power_w),
        "measured_background_power_w": _round(result.measured_background_power_w),
        "planned_background_power_w": _round(result.planned_background_power_w),
        "background_deviation_w": _round(result.background_deviation_w),
        "estimated_grid_without_ess_with_planned_ev_w": _round(
            result.estimated_grid_without_ess_with_planned_ev_w
        ),
        "requested_ess_power_w": _round(result.requested_ess_power_w),
        "accepted_ess_power_w": _round(result.accepted_ess_power_w),
        "ess_correction_from_plan_w": _round(result.ess_correction_from_plan_w),
        "projected_grid_power_w": _round(result.projected_grid_power_w),
        "residual_to_plan_w": _round(result.residual_to_plan_w),
        "command_limited": result.command_limited,
        "command_reason": result.command_reason,
        "replan_required": result.replan_required,
        "replan_reason": result.replan_reason,
        "last_update_utc": datetime.now(UTC).isoformat(),
    }
    await client.set_state(FAST_DISPATCH_STATUS_ENTITY, result.status, attributes)


def evaluate_fast_dispatch(
    plan: ShadowPlan,
    house_state: HouseState,
    actuator_registry: ActuatorRegistry,
    *,
    now_utc: datetime,
) -> FastDispatchResult:
    """Calculate the ESS correction needed to track the current MILP grid target.

    The measured EV load is removed from the live grid balance and replaced by the
    MILP-planned EV load. This keeps shadow evaluation meaningful before Energy
    Manager is the real EV writer.
    """
    interval = _current_interval(plan, now_utc)
    if interval is None:
        return _unavailable("no_current_plan_interval")

    planned_grid = interval.grid_power_after_ess_w
    planned_ess = interval.ess_ac_power_w
    planned_ev = interval.scheduled_load_w
    measured_grid = house_state.grid_power_w
    measured_ess = _number(house_state.value("ess.power"))
    measured_ev = _number(house_state.value("ev.charging_power"))
    measured_background = house_state.background_load_power_w

    missing: list[str] = []
    if planned_grid is None:
        missing.append("planned_grid")
    if planned_ess is None:
        missing.append("planned_ess")
    if measured_grid is None:
        missing.append("measured_grid")
    if measured_ess is None:
        missing.append("measured_ess")
    if measured_ev is None:
        missing.append("measured_ev")
    if missing:
        return FastDispatchResult(
            status="inputs_unavailable",
            interval_start_local=interval.period_start_local,
            planned_grid_power_w=planned_grid,
            planned_ess_power_w=planned_ess,
            planned_ev_power_w=planned_ev,
            measured_grid_power_w=measured_grid,
            measured_ess_power_w=measured_ess,
            measured_ev_power_w=measured_ev,
            measured_background_power_w=measured_background,
            planned_background_power_w=interval.background_load_w,
            background_deviation_w=_difference(measured_background, interval.background_load_w),
            estimated_grid_without_ess_with_planned_ev_w=None,
            requested_ess_power_w=None,
            accepted_ess_power_w=None,
            ess_correction_from_plan_w=None,
            projected_grid_power_w=None,
            residual_to_plan_w=None,
            command_limited=False,
            command_reason="missing:" + ",".join(missing),
            replan_required=False,
            replan_reason=None,
        )

    assert planned_grid is not None
    assert planned_ess is not None
    assert measured_grid is not None
    assert measured_ess is not None
    assert measured_ev is not None

    uncontrolled_with_planned_ev = measured_grid + measured_ess - measured_ev + planned_ev
    requested_ess = uncontrolled_with_planned_ev - planned_grid
    requests = [ActuatorPowerRequest(actuator_id="ess", requested_power_w=requested_ess)]
    if planned_ev > 0.0 or measured_ev > 0.0:
        requests.append(ActuatorPowerRequest(actuator_id="ev", requested_power_w=planned_ev))
    command_results = actuator_registry.evaluate_commands(tuple(requests), house_state)
    ess_result = next((item for item in command_results if item.actuator_id == "ess"), None)
    if ess_result is None:
        return FastDispatchResult(
            status="ess_unavailable",
            interval_start_local=interval.period_start_local,
            planned_grid_power_w=planned_grid,
            planned_ess_power_w=planned_ess,
            planned_ev_power_w=planned_ev,
            measured_grid_power_w=measured_grid,
            measured_ess_power_w=measured_ess,
            measured_ev_power_w=measured_ev,
            measured_background_power_w=measured_background,
            planned_background_power_w=interval.background_load_w,
            background_deviation_w=_difference(measured_background, interval.background_load_w),
            estimated_grid_without_ess_with_planned_ev_w=uncontrolled_with_planned_ev,
            requested_ess_power_w=requested_ess,
            accepted_ess_power_w=None,
            ess_correction_from_plan_w=requested_ess - planned_ess,
            projected_grid_power_w=None,
            residual_to_plan_w=None,
            command_limited=True,
            command_reason="missing_ess_command_result",
            replan_required=True,
            replan_reason="ess_dispatch_unavailable",
            command_results=command_results,
        )

    projected_grid = uncontrolled_with_planned_ev - ess_result.accepted_power_w
    residual = projected_grid - planned_grid
    replan_required = abs(residual) >= _REPLAN_RESIDUAL_W
    if replan_required:
        status = "residual_requires_replan"
        replan_reason = "ess_correction_limit"
    elif ess_result.limited:
        status = "tracking_limited"
        replan_reason = None
    else:
        status = "tracking"
        replan_reason = None

    return FastDispatchResult(
        status=status,
        interval_start_local=interval.period_start_local,
        planned_grid_power_w=planned_grid,
        planned_ess_power_w=planned_ess,
        planned_ev_power_w=planned_ev,
        measured_grid_power_w=measured_grid,
        measured_ess_power_w=measured_ess,
        measured_ev_power_w=measured_ev,
        measured_background_power_w=measured_background,
        planned_background_power_w=interval.background_load_w,
        background_deviation_w=_difference(measured_background, interval.background_load_w),
        estimated_grid_without_ess_with_planned_ev_w=uncontrolled_with_planned_ev,
        requested_ess_power_w=requested_ess,
        accepted_ess_power_w=ess_result.accepted_power_w,
        ess_correction_from_plan_w=ess_result.accepted_power_w - planned_ess,
        projected_grid_power_w=projected_grid,
        residual_to_plan_w=residual,
        command_limited=ess_result.limited,
        command_reason=ess_result.reason,
        replan_required=replan_required,
        replan_reason=replan_reason,
        command_results=command_results,
    )


def _current_interval(plan: ShadowPlan, now_utc: datetime) -> ShadowPlanInterval | None:
    for item in plan.intervals:
        start_utc = item.period_start_local.astimezone(UTC)
        if start_utc <= now_utc < start_utc + _INTERVAL:
            return item
    for item in plan.intervals:
        if item.period_start_local.astimezone(UTC) > now_utc:
            return item
    return None


def _unavailable(reason: str) -> FastDispatchResult:
    return FastDispatchResult(
        status="unavailable",
        interval_start_local=None,
        planned_grid_power_w=None,
        planned_ess_power_w=None,
        planned_ev_power_w=None,
        measured_grid_power_w=None,
        measured_ess_power_w=None,
        measured_ev_power_w=None,
        measured_background_power_w=None,
        planned_background_power_w=None,
        background_deviation_w=None,
        estimated_grid_without_ess_with_planned_ev_w=None,
        requested_ess_power_w=None,
        accepted_ess_power_w=None,
        ess_correction_from_plan_w=None,
        projected_grid_power_w=None,
        residual_to_plan_w=None,
        command_limited=False,
        command_reason=reason,
        replan_required=False,
        replan_reason=None,
    )


def _number(value: float | bool | None) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _difference(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return left - right


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 1)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
