"""Clear Home Assistant diagnostics for planner tasks."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .diagnostics import TASK_STATUS_ENTITY
from .tasks import TASK_VERSION, PlanningTask

TASK_DIAGNOSTIC_VERSION = "2026-10-10-task-diagnostics-v3"


async def publish_task_status(client, tasks: tuple[PlanningTask, ...]) -> None:
    """Publish task policy with hard and preferred EV targets labelled explicitly."""
    ready_count = sum(item.planning_available for item in tasks)
    attributes: dict[str, Any] = {
        "friendly_name": "Energy Manager Task Status",
        "task_version": TASK_VERSION,
        "task_diagnostic_version": TASK_DIAGNOSTIC_VERSION,
        "shadow_mode": True,
        "control_enabled": False,
        "task_count": len(tasks),
        "planning_available_count": ready_count,
        "tasks": [_task_attributes(item) for item in tasks],
        "last_update_utc": datetime.now(UTC).isoformat(),
    }
    await client.set_state(TASK_STATUS_ENTITY, _task_state(tasks), attributes)


def _task_state(tasks: tuple[PlanningTask, ...]) -> str:
    if not tasks:
        return "none"
    if any(item.status == "deadline_infeasible" for item in tasks):
        return "deadline_infeasible"
    if any(item.status == "configuration_required" for item in tasks):
        return "configuration_required"
    if any(item.status == "ready" for item in tasks):
        return "ready"
    if all(item.status == "satisfied" for item in tasks):
        return "satisfied"
    return tasks[0].status


def _task_attributes(item: PlanningTask) -> dict[str, Any]:
    return {
        "id": item.task_id,
        "kind": item.kind,
        "source": item.source,
        "actuator_id": item.actuator_id,
        "status": item.status,
        "planning_available": item.planning_available,
        "earliest_start": _iso(item.earliest_start_local),
        "latest_end": _iso(item.latest_end_local),
        "required_energy_kwh": _round_optional(item.required_energy_kwh, 3),
        "battery_energy_required_kwh": _round_optional(item.battery_energy_required_kwh, 3),
        "required_energy_role": "hard_by_deadline" if item.kind == "energy_by_deadline" else None,
        "preferred_energy_kwh": _round_optional(item.preferred_energy_kwh, 3),
        "preferred_battery_energy_kwh": _round_optional(item.preferred_battery_energy_kwh, 3),
        "preferred_energy_role": (
            "soft_terminal_soc_over_planning_horizon" if item.preferred_energy_kwh is not None else None
        ),
        "interruptible": item.interruptible,
        "current_soc_percent": _round_optional(item.current_soc_percent, 2),
        "minimum_soc_percent": _round_optional(item.minimum_soc_percent, 2),
        "preferred_soc_percent": _round_optional(item.target_soc_percent, 2),
        "target_soc_percent": _round_optional(item.target_soc_percent, 2),
        "target_soc_percent_role": "preferred",
        "feasible_at_max_power": item.feasible_at_max_power,
        "minimum_runtime_hours": _round_optional(item.minimum_runtime_hours, 3),
        "expected_return": _iso(item.expected_return_local),
        "expected_trip_energy_kwh": _round_optional(item.expected_trip_energy_kwh, 3),
        "unavailable_windows": [
            {"start": start.isoformat(), "end": end.isoformat()}
            for start, end in item.ev_unavailable_windows_local
        ],
    }


def _round_optional(value: float | None, digits: int) -> float | None:
    return round(value, digits) if value is not None else None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
