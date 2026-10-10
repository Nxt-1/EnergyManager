"""Planner-facing flexible task model and runtime task generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo

from .actuators import ActuatorSnapshot, EvActuatorSnapshot, find_ev_actuator
from .config import EvSettings, EvWeeklyScheduleEntry

TASK_VERSION = "2026-10-10-task-v3"
_EV_SCHEDULE_HORIZON = timedelta(days=7)
_INTERVAL = timedelta(minutes=15)


@dataclass(frozen=True, slots=True)
class PlanningTask:
    """A planner requirement independent of the device-specific command interface.

    ``required_energy_kwh`` remains a cumulative AC-energy diagnostic for hard departure milestones.
    The MILP also uses ``minimum_soc_percent`` directly when an EV battery model is available.
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
    expected_return_local: datetime | None = None
    expected_trip_energy_kwh: float | None = None
    ev_unavailable_windows_local: tuple[tuple[datetime, datetime], ...] = ()


@dataclass(frozen=True, slots=True)
class _EvTripOccurrence:
    departure_local: datetime
    return_local: datetime
    minimum_soc_percent: float
    expected_trip_energy_kwh: float


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
        if self._ev.weekly_schedule:
            return _ev_weekly_tasks(self._ev, actuators, now_utc=now_utc, local_tz=local_tz)
        return (_ev_charge_task(self._ev, actuators, now_utc=now_utc, local_tz=local_tz),)


def _ev_weekly_tasks(
    settings: EvSettings,
    actuators: tuple[ActuatorSnapshot, ...],
    *,
    now_utc: datetime,
    local_tz: tzinfo,
) -> tuple[PlanningTask, ...]:
    actuator = find_ev_actuator(actuators)
    now_local = now_utc.astimezone(local_tz)
    horizon_end = now_local + _EV_SCHEDULE_HORIZON
    occurrences = _schedule_occurrences(settings.weekly_schedule, now_local, horizon_end)
    unavailable = _unavailable_windows(occurrences, now_local, horizon_end, actuator)
    placeholder = _weekly_placeholder(settings, actuator, now_local, horizon_end, unavailable)
    if placeholder is not None:
        return (placeholder,)

    assert actuator is not None and actuator.soc_percent is not None
    assert actuator.capabilities.battery_capacity_kwh is not None
    capacity = actuator.capabilities.battery_capacity_kwh
    efficiency = actuator.capabilities.charge_efficiency
    current_soc = max(0.0, min(100.0, actuator.soc_percent))
    initial_energy = capacity * current_soc / 100.0
    maximum_power_w = _maximum_ev_power_w(actuator)
    future = [item for item in occurrences if now_local < item.departure_local <= horizon_end]

    tasks: list[PlanningTask] = []
    consumed_before_kwh = 0.0
    for occurrence in future:
        required_stored = capacity * occurrence.minimum_soc_percent / 100.0
        hard_battery_charge = max(0.0, required_stored + consumed_before_kwh - initial_energy)
        hard_ac_charge = hard_battery_charge / efficiency if hard_battery_charge > 0.0 else 0.0
        available_hours = _available_hours(now_local, occurrence.departure_local, unavailable)
        minimum_runtime = (
            hard_ac_charge * 1000.0 / maximum_power_w
            if hard_ac_charge > 0.0 and maximum_power_w > 0.0
            else 0.0
        )
        feasible = minimum_runtime <= available_hours + 1e-9
        tasks.append(
            PlanningTask(
                task_id=f"ev_departure_{occurrence.departure_local.strftime('%Y%m%dT%H%M')}",
                kind="energy_by_deadline",
                source="ev_weekly_departure_schedule",
                actuator_id="ev",
                status="ready" if feasible else "deadline_infeasible",
                planning_available=True,
                earliest_start_local=now_local,
                latest_end_local=occurrence.departure_local,
                required_energy_kwh=hard_ac_charge,
                battery_energy_required_kwh=hard_battery_charge,
                interruptible=True,
                current_soc_percent=current_soc,
                minimum_soc_percent=occurrence.minimum_soc_percent,
                target_soc_percent=settings.target_soc_percent,
                feasible_at_max_power=feasible,
                minimum_runtime_hours=minimum_runtime,
                expected_return_local=occurrence.return_local,
                expected_trip_energy_kwh=occurrence.expected_trip_energy_kwh,
            )
        )
        consumed_before_kwh += occurrence.expected_trip_energy_kwh

    preferred_stored = capacity * settings.target_soc_percent / 100.0
    preferred_battery_charge = max(0.0, preferred_stored + consumed_before_kwh - initial_energy)
    preferred_ac_charge = preferred_battery_charge / efficiency if preferred_battery_charge > 0.0 else 0.0
    tasks.append(
        PlanningTask(
            task_id="ev_preferred_horizon",
            kind="ev_terminal_soc_target",
            source="ev_weekly_departure_schedule",
            actuator_id="ev",
            status="ready" if preferred_battery_charge > 0.0 or future else "satisfied",
            planning_available=True,
            earliest_start_local=now_local,
            latest_end_local=horizon_end,
            required_energy_kwh=0.0,
            battery_energy_required_kwh=0.0,
            interruptible=True,
            current_soc_percent=current_soc,
            target_soc_percent=settings.target_soc_percent,
            preferred_energy_kwh=preferred_ac_charge,
            preferred_battery_energy_kwh=preferred_battery_charge,
            feasible_at_max_power=True,
            minimum_runtime_hours=0.0,
            ev_unavailable_windows_local=unavailable,
        )
    )
    return tuple(tasks)


def _weekly_placeholder(
    settings: EvSettings,
    actuator: EvActuatorSnapshot | None,
    now_local: datetime,
    horizon_end: datetime,
    unavailable: tuple[tuple[datetime, datetime], ...],
) -> PlanningTask | None:
    status: str | None = None
    if actuator is None or not actuator.configured:
        status = "not_configured"
    elif actuator.connected is None:
        status = "connection_state_unavailable"
    elif actuator.soc_percent is None:
        status = "waiting_for_soc"
    elif actuator.capabilities.battery_capacity_kwh is None:
        status = "configuration_required"
    elif actuator.connected is False and not _window_contains(unavailable, now_local):
        status = "waiting_for_connection"
    if status is None:
        return None
    return PlanningTask(
        task_id="ev_weekly_schedule",
        kind="ev_terminal_soc_target",
        source="ev_weekly_departure_schedule",
        actuator_id="ev",
        status=status,
        planning_available=False,
        earliest_start_local=now_local,
        latest_end_local=horizon_end,
        required_energy_kwh=None,
        battery_energy_required_kwh=None,
        interruptible=True,
        current_soc_percent=None if actuator is None else actuator.soc_percent,
        minimum_soc_percent=settings.minimum_soc_percent,
        target_soc_percent=settings.target_soc_percent,
        ev_unavailable_windows_local=unavailable,
    )


def _schedule_occurrences(
    schedule: tuple[EvWeeklyScheduleEntry, ...],
    now_local: datetime,
    horizon_end: datetime,
) -> tuple[_EvTripOccurrence, ...]:
    occurrences: list[_EvTripOccurrence] = []
    current_date = now_local.date() - timedelta(days=1)
    last_date = horizon_end.date()
    while current_date <= last_date:
        for entry in schedule:
            if current_date.weekday() not in entry.weekdays:
                continue
            departure = _combine_local(current_date, entry.departure_time_local, now_local.tzinfo)
            return_time = _combine_local(current_date, entry.return_time_local, now_local.tzinfo)
            if return_time <= departure:
                return_time += timedelta(days=1)
            occurrences.append(
                _EvTripOccurrence(
                    departure_local=departure,
                    return_local=return_time,
                    minimum_soc_percent=entry.minimum_soc_percent,
                    expected_trip_energy_kwh=entry.expected_trip_energy_kwh,
                )
            )
        current_date += timedelta(days=1)
    return tuple(sorted(occurrences, key=lambda item: item.departure_local))


def _unavailable_windows(
    occurrences: tuple[_EvTripOccurrence, ...],
    now_local: datetime,
    horizon_end: datetime,
    actuator: EvActuatorSnapshot | None,
) -> tuple[tuple[datetime, datetime], ...]:
    windows: list[tuple[datetime, datetime]] = []
    for item in occurrences:
        if item.return_local <= now_local or item.departure_local >= horizon_end:
            continue
        active_window = item.departure_local <= now_local < item.return_local
        if active_window and actuator is not None and actuator.connected is True:
            continue
        start = max(now_local, item.departure_local)
        end = min(horizon_end, item.return_local)
        if start < end:
            windows.append((start, end))
    return tuple(windows)


def _available_hours(
    start: datetime,
    end: datetime,
    unavailable: tuple[tuple[datetime, datetime], ...],
) -> float:
    if end <= start:
        return 0.0
    total = (end - start).total_seconds() / 3600.0
    blocked = 0.0
    for window_start, window_end in unavailable:
        overlap_start = max(start, window_start)
        overlap_end = min(end, window_end)
        if overlap_start < overlap_end:
            blocked += (overlap_end - overlap_start).total_seconds() / 3600.0
    return max(0.0, total - blocked)


def _window_contains(windows: tuple[tuple[datetime, datetime], ...], moment: datetime) -> bool:
    return any(start <= moment < end for start, end in windows)


def _combine_local(value: date, configured_time: str, zone: tzinfo | None) -> datetime:
    hour, minute = (int(part) for part in configured_time.split(":", maxsplit=1))
    return datetime.combine(value, time(hour, minute), tzinfo=zone)


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
    minimum_runtime = (
        hard_ac_energy * 1000.0 / maximum_power_w
        if hard_ac_energy > 0.0 and maximum_power_w > 0.0
        else 0.0
    )
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
