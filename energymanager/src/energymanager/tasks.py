"""Planner-facing flexible task model and runtime task generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, tzinfo

from .actuators import ActuatorSnapshot, EvActuatorSnapshot, find_ev_actuator
from .config import EvSettings

TASK_VERSION = "2026-10-08-task-v2"


@dataclass(frozen=True, slots=True)
class PlanningTask:
    """A planner requirement independent of the device-specific command interface.

    ``required_energy_kwh`` is a hard cumulative AC-energy milestone that must be met by
    ``latest_end_local``. ``preferred_energy_kwh`` is a soft cumulative target that may be met anywhere
    in the planning horizon when doing so is economically worthwhile.
    """

    task_id: str
    kind: str
    source: str
    actuator_id: str | None
    status: str
    planning_available: bool
    earliest_start_local: datetime | None
    latest_end_local: datetime | None
    required_energy_kwh: float | None
    battery_energy_required_kwh: float | None
    interruptible: bool
    current_soc_percent: float | None = None
    minimum_soc_percent: float | None = None
    target_soc_percent: float | None = None
    preferred_energy_kwh: float | None = None
    preferred_battery_energy_kwh: float | None = None
    feasible_at_max_power: bool | None = None
    minimum_runtime_hours: float | None = None


class TaskRegistry:
    """Generate current planner tasks from policy settings and actuator state."""

    def __init__(self, ev_settings: EvSettings) -> None:
        self._ev = ev_settings

    def snapshots(
        self,
        actuators: tuple[ActuatorSnapshot, ...],
        *,
        now_utc: datetime,
        local_tz: tzinfo,
    ) -> tuple[PlanningTask, ...]:
        """Return the task catalog for the current planning instant."""
        if now_utc.tzinfo is None:
            raise ValueError("now_utc must be timezone-aware")
        return (_ev_charge_task(self._ev, actuators, now_utc=now_utc, local_tz=local_tz),)


def _ev_charge_task(
    settings: EvSettings,
    actuators: tuple[ActuatorSnapshot, ...],
    *,
    now_utc: datetime,
    local_tz: tzinfo,
) -> PlanningTask:
    actuator = find_ev_actuator(actuators)
    now_local = now_utc.astimezone(local_tz)
    deadline = _next_local_deadline(now_local, settings.departure_time_local)
    minimum_soc = settings.minimum_soc_percent
    if minimum_soc is None:
        minimum_soc = settings.target_soc_percent
    preferred_soc = max(minimum_soc, settings.target_soc_percent)
    common = {
        "task_id": "ev_charge",
        "kind": "energy_by_deadline",
        "source": "ev_minimum_by_departure_with_preferred_soc",
        "actuator_id": "ev",
        "earliest_start_local": now_local,
        "latest_end_local": deadline,
        "interruptible": True,
        "minimum_soc_percent": minimum_soc,
        "target_soc_percent": preferred_soc,
    }
    if actuator is None or not actuator.configured:
        return PlanningTask(
            **common,
            status="not_configured",
            planning_available=False,
            required_energy_kwh=None,
            battery_energy_required_kwh=None,
        )
    if actuator.connected is False:
        return PlanningTask(
            **common,
            status="waiting_for_connection",
            planning_available=False,
            required_energy_kwh=None,
            battery_energy_required_kwh=None,
            current_soc_percent=actuator.soc_percent,
        )
    if actuator.soc_percent is None:
        return PlanningTask(
            **common,
            status="waiting_for_soc",
            planning_available=False,
            required_energy_kwh=None,
            battery_energy_required_kwh=None,
        )
    if actuator.capabilities.battery_capacity_kwh is None:
        return PlanningTask(
            **common,
            status="configuration_required",
            planning_available=False,
            required_energy_kwh=None,
            battery_energy_required_kwh=None,
            current_soc_percent=actuator.soc_percent,
        )

    current_soc = max(0.0, min(100.0, actuator.soc_percent))
    hard_delta_soc = max(0.0, minimum_soc - current_soc)
    preferred_delta_soc = max(0.0, preferred_soc - current_soc)
    battery_capacity = actuator.capabilities.battery_capacity_kwh
    hard_battery_energy = battery_capacity * hard_delta_soc / 100.0
    preferred_battery_energy = battery_capacity * preferred_delta_soc / 100.0
    efficiency = actuator.capabilities.charge_efficiency
    hard_ac_energy = hard_battery_energy / efficiency if hard_battery_energy > 0.0 else 0.0
    preferred_ac_energy = preferred_battery_energy / efficiency if preferred_battery_energy > 0.0 else 0.0

    maximum_power_w = _maximum_ev_power_w(actuator)
    minimum_runtime = hard_ac_energy * 1000.0 / maximum_power_w if hard_ac_energy > 0.0 and maximum_power_w > 0.0 else 0.0
    available_hours = max(0.0, (deadline - now_local).total_seconds() / 3600.0)
    feasible = minimum_runtime <= available_hours + 1e-9

    if hard_delta_soc <= 0.0 and preferred_delta_soc <= 0.0:
        status = "satisfied"
        planning_available = False
    elif not actuator.planning_available:
        status = actuator.status
        planning_available = False
    elif not feasible:
        status = "deadline_infeasible"
        planning_available = True
    else:
        status = "ready"
        planning_available = True

    return PlanningTask(
        **common,
        status=status,
        planning_available=planning_available,
        required_energy_kwh=hard_ac_energy,
        battery_energy_required_kwh=hard_battery_energy,
        current_soc_percent=current_soc,
        preferred_energy_kwh=preferred_ac_energy,
        preferred_battery_energy_kwh=preferred_battery_energy,
        feasible_at_max_power=feasible,
        minimum_runtime_hours=minimum_runtime,
    )


def _maximum_ev_power_w(actuator: EvActuatorSnapshot) -> float:
    candidates = (
        actuator.capabilities.maximum_single_phase_power_w,
        actuator.capabilities.maximum_three_phase_power_w,
    )
    return max((value for value in candidates if value is not None), default=0.0)


def _next_local_deadline(now_local: datetime, configured_time: str) -> datetime:
    hour, minute = (int(part) for part in configured_time.split(":", maxsplit=1))
    candidate = datetime.combine(now_local.date(), time(hour, minute), tzinfo=now_local.tzinfo)
    if candidate <= now_local:
        candidate += timedelta(days=1)
    return candidate
