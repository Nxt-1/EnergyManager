"""Immutable V3 requirement, provenance and extensible load/resource contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class Provenance:
    generator: str
    version: str
    generated_at_utc: datetime
    sources: tuple[str, ...]
    quality: str
    formula: str
    parameters: tuple[tuple[str, float | str | None], ...]
    assumptions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Requirement:
    requirement_id: str
    resource_id: str
    kind: str
    hard: bool
    amount: float | None
    unit: str
    earliest_start: datetime | None
    deadline: datetime | None
    feasible_at_max_power: bool | None
    provenance: Provenance
    penalty_eur_per_unit: float | None = None


@dataclass(frozen=True, slots=True)
class StorageResource:
    """State dynamics: next = state + input * efficiency - withdrawal (kWh)."""

    resource_id: str
    capacity_kwh: float
    initial_kwh: float
    reserve_kwh: float
    charge_efficiency: float
    max_input_kw: float = 2.0
    withdrawals_kwh: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if self.max_input_kw <= 0 or any(w < 0 for w in self.withdrawals_kwh):
            raise ValueError("invalid resource power/withdrawal")
        if not 0 <= self.reserve_kwh <= self.initial_kwh <= self.capacity_kwh or not 0 < self.charge_efficiency <= 1:
            raise ValueError("invalid storage resource")


@dataclass(frozen=True, slots=True)
class FlexibleJob:
    """Generic AC demand; cycle_kw denotes a non-interruptible 15-minute power sequence.

    No hardware integration is implied by this planning contract. Interruptible jobs
    deliver exactly energy_kwh; cycle jobs select one whole cycle within their window.
    """

    job_id: str
    resource_id: str
    earliest_start: datetime
    latest_finish: datetime
    energy_kwh: float
    max_power_kw: float
    provenance: Provenance
    cycle_kw: tuple[float, ...] = ()
    unavailable: tuple[tuple[datetime, datetime], ...] = ()

    def __post_init__(self) -> None:
        if self.earliest_start.tzinfo is None or self.latest_finish.tzinfo is None:
            raise ValueError("job times must be aware")
        if self.latest_finish <= self.earliest_start or self.energy_kwh <= 0 or self.max_power_kw <= 0:
            raise ValueError("invalid job window/energy/power")
        if self.cycle_kw and (
            any(p < 0 or p > self.max_power_kw for p in self.cycle_kw)
            or abs(sum(self.cycle_kw) * 0.25 - self.energy_kwh) > 1e-6
        ):
            raise ValueError("cycle must reconcile with energy and power")


def explain_ev_tasks(tasks, actuators, now: datetime) -> tuple[Requirement, ...]:
    """Expose the exact generator calculations, separately from scheduling evidence."""
    from .actuators import find_ev_actuator

    ev = find_ev_actuator(actuators)
    capacity = ev.capabilities.battery_capacity_kwh if ev else None
    efficiency = ev.capabilities.charge_efficiency if ev else None
    consumed = 0.0
    result = []
    for task in tasks:
        parameters = (
            ("capacity_kwh", capacity),
            ("measured_soc_percent", task.current_soc_percent),
            ("charge_efficiency", efficiency),
            ("minimum_soc_percent", task.minimum_soc_percent),
            ("preferred_soc_percent", task.target_soc_percent),
            ("trip_energy_before_kwh", consumed),
            ("mandatory_ac_kwh", task.required_energy_kwh),
            ("mandatory_stored_kwh", task.battery_energy_required_kwh),
            ("preferred_ac_kwh", task.preferred_energy_kwh),
            ("trip_withdrawal_kwh", task.expected_trip_energy_kwh),
            ("minimum_runtime_hours", task.minimum_runtime_hours),
        )
        provenance = Provenance(
            "ev_policy",
            "3.0",
            now.astimezone(UTC),
            ("observations:ev.soc", "observations:ev.connected", "configuration:ev", task.source),
            task.status,
            "mandatory_ac_kwh = max(0, capacity_kwh * minimum_soc_percent / 100 + "
            "trip_energy_before_kwh - capacity_kwh * measured_soc_percent / 100) / charge_efficiency",
            parameters,
            (
                "Trips withdraw energy at departure; no charging while away.",
                "Preferred SoC applies at horizon end, is soft, and is not a charge cap.",
                "An omitted minimum creates no hard departure-energy obligation (0 percent).",
                "Source timestamps and held/stale quality are archived in snapshot observations.",
                "Feasibility-at-max-power is necessary, not proof of electrical feasibility.",
            ),
        )
        if task.kind == "energy_by_deadline":
            result.append(
                Requirement(
                    task.task_id,
                    "ev",
                    "state_by_deadline" if task.minimum_soc_percent is not None else "energy_by_deadline",
                    True,
                    task.minimum_soc_percent if task.minimum_soc_percent is not None else task.required_energy_kwh,
                    "percent" if task.minimum_soc_percent is not None else "kWh",
                    task.earliest_start_local,
                    task.latest_end_local,
                    task.feasible_at_max_power,
                    provenance,
                )
            )
        if task.preferred_energy_kwh is not None:
            result.append(
                Requirement(
                    task.task_id + ":preferred",
                    "ev",
                    "preferred_terminal_state",
                    False,
                    task.target_soc_percent,
                    "percent",
                    task.earliest_start_local,
                    None,
                    None,
                    provenance,
                )
            )
        consumed += task.expected_trip_energy_kwh or 0.0
    return tuple(result)
