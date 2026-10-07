"""Planner-facing actuator state, capabilities and dry-run command translation."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .config import EssSettings, EvSettings, Settings
from .house_state import HouseState

ACTUATOR_VERSION = "2026-10-06-actuator-v2"
ACTUATOR_COMMAND_VERSION = "2026-10-06-command-v1"


@dataclass(frozen=True, slots=True)
class EssCapabilities:
    """Configured ESS planning envelope exposed by the ESS actuator."""

    capacity_kwh: float
    min_soc_percent: float
    max_soc_percent: float
    max_charge_power_w: float
    max_discharge_power_w: float
    charge_efficiency: float
    discharge_efficiency: float


@dataclass(frozen=True, slots=True)
class EssActuatorSnapshot:
    """Current ESS actuator state plus planning capabilities."""

    actuator_id: str
    kind: str
    configured: bool
    planning_available: bool
    status: str
    control_enabled: bool
    soc_percent: float | None
    current_power_w: float | None
    capabilities: EssCapabilities


@dataclass(frozen=True, slots=True)
class EvCapabilities:
    """Configured EV charging envelope exposed by the EV actuator."""

    min_charge_current_a: float
    max_charge_current_a: float
    nominal_voltage_v: float
    supports_single_phase: bool
    supports_three_phase: bool

    @property
    def minimum_single_phase_power_w(self) -> float | None:
        if not self.supports_single_phase:
            return None
        return self.nominal_voltage_v * self.min_charge_current_a

    @property
    def maximum_single_phase_power_w(self) -> float | None:
        if not self.supports_single_phase:
            return None
        return self.nominal_voltage_v * self.max_charge_current_a

    @property
    def minimum_three_phase_power_w(self) -> float | None:
        if not self.supports_three_phase:
            return None
        return 3.0 * self.nominal_voltage_v * self.min_charge_current_a

    @property
    def maximum_three_phase_power_w(self) -> float | None:
        if not self.supports_three_phase:
            return None
        return 3.0 * self.nominal_voltage_v * self.max_charge_current_a


@dataclass(frozen=True, slots=True)
class EvActuatorSnapshot:
    """Current EV/EVSE state plus charging capabilities."""

    actuator_id: str
    kind: str
    configured: bool
    planning_available: bool
    status: str
    control_enabled: bool
    connected: bool | None
    soc_percent: float | None
    current_power_w: float | None
    capabilities: EvCapabilities


ActuatorSnapshot = EssActuatorSnapshot | EvActuatorSnapshot


@dataclass(frozen=True, slots=True)
class ActuatorPowerRequest:
    """Generic planner request for an actuator power target.

    ESS convention: positive supplies the AC bus, negative absorbs from the AC bus.
    EV convention: positive consumes charging power; zero means idle.
    """

    actuator_id: str
    requested_power_w: float


@dataclass(frozen=True, slots=True)
class ActuatorCommandResult:
    """Dry-run actuator translation result; never writes to hardware."""

    actuator_id: str
    kind: str
    requested_power_w: float
    accepted_power_w: float
    status: str
    limited: bool
    reason: str | None = None
    phase_count: int | None = None
    current_a: float | None = None


class ActuatorRegistry:
    """Build actuator snapshots and translate planner requests without hardware writes."""

    def __init__(self, settings: Settings) -> None:
        self._ess = settings.ess
        self._ev = settings.ev

    def snapshots(self, house_state: HouseState) -> tuple[ActuatorSnapshot, ...]:
        """Return all known actuator types, including unavailable/unconfigured devices."""
        return (
            _ess_snapshot(self._ess, house_state),
            _ev_snapshot(self._ev, house_state),
        )

    def evaluate_commands(
        self,
        requests: tuple[ActuatorPowerRequest, ...],
        house_state: HouseState,
    ) -> tuple[ActuatorCommandResult, ...]:
        """Translate planner requests into device-feasible dry-run commands."""
        snapshots = {item.actuator_id: item for item in self.snapshots(house_state)}
        results: list[ActuatorCommandResult] = []
        for request in requests:
            snapshot = snapshots.get(request.actuator_id)
            if snapshot is None:
                results.append(
                    ActuatorCommandResult(
                        actuator_id=request.actuator_id,
                        kind="unknown",
                        requested_power_w=request.requested_power_w,
                        accepted_power_w=0.0,
                        status="rejected",
                        limited=True,
                        reason="unknown_actuator",
                    )
                )
            elif isinstance(snapshot, EssActuatorSnapshot):
                results.append(_evaluate_ess_command(snapshot, request))
            elif isinstance(snapshot, EvActuatorSnapshot):
                results.append(_evaluate_ev_command(snapshot, request))
        return tuple(results)


def _ess_snapshot(settings: EssSettings, house_state: HouseState) -> EssActuatorSnapshot:
    capabilities = EssCapabilities(
        capacity_kwh=settings.capacity_kwh,
        min_soc_percent=settings.min_soc_percent,
        max_soc_percent=settings.max_soc_percent,
        max_charge_power_w=settings.max_charge_power_w,
        max_discharge_power_w=settings.max_discharge_power_w,
        charge_efficiency=settings.charge_efficiency,
        discharge_efficiency=settings.discharge_efficiency,
    )
    configured = settings.soc_entity is not None
    soc = _number(house_state.value("ess.soc"))
    power = _number(house_state.value("ess.power"))
    if not configured:
        status = "not_configured"
        available = False
    elif soc is None:
        status = "soc_unavailable"
        available = False
    else:
        status = "ready"
        available = True

    return EssActuatorSnapshot(
        actuator_id="ess",
        kind="storage",
        configured=configured,
        planning_available=available,
        status=status,
        control_enabled=False,
        soc_percent=soc,
        current_power_w=power,
        capabilities=capabilities,
    )


def _ev_snapshot(settings: EvSettings, house_state: HouseState) -> EvActuatorSnapshot:
    capabilities = EvCapabilities(
        min_charge_current_a=settings.min_charge_current_a,
        max_charge_current_a=settings.max_charge_current_a,
        nominal_voltage_v=settings.nominal_voltage_v,
        supports_single_phase=settings.supports_single_phase,
        supports_three_phase=settings.supports_three_phase,
    )
    configured = settings.connected_entity is not None
    connected_value = house_state.value("ev.connected")
    connected = connected_value if isinstance(connected_value, bool) else None
    soc = _number(house_state.value("ev.soc"))
    power = _number(house_state.value("ev.charging_power"))

    if not configured:
        status = "not_configured"
        available = False
    elif connected is None:
        status = "connection_state_unavailable"
        available = False
    elif not connected:
        status = "disconnected"
        available = False
    elif soc is None:
        status = "soc_unavailable"
        available = False
    else:
        status = "ready"
        available = True

    return EvActuatorSnapshot(
        actuator_id="ev",
        kind="flexible_load",
        configured=configured,
        planning_available=available,
        status=status,
        control_enabled=False,
        connected=connected,
        soc_percent=soc,
        current_power_w=power,
        capabilities=capabilities,
    )


def _evaluate_ess_command(
    snapshot: EssActuatorSnapshot,
    request: ActuatorPowerRequest,
) -> ActuatorCommandResult:
    requested = float(request.requested_power_w)
    if not snapshot.planning_available or snapshot.soc_percent is None:
        return _rejected(snapshot, requested, snapshot.status)

    capabilities = snapshot.capabilities
    if requested > 0.0 and snapshot.soc_percent <= capabilities.min_soc_percent:
        return _rejected(snapshot, requested, "minimum_soc_reached")
    if requested < 0.0 and snapshot.soc_percent >= capabilities.max_soc_percent:
        return _rejected(snapshot, requested, "maximum_soc_reached")

    accepted = max(-capabilities.max_charge_power_w, min(capabilities.max_discharge_power_w, requested))
    limited = not math.isclose(accepted, requested, abs_tol=1e-6)
    return ActuatorCommandResult(
        actuator_id=snapshot.actuator_id,
        kind=snapshot.kind,
        requested_power_w=requested,
        accepted_power_w=accepted,
        status="limited" if limited else "accepted",
        limited=limited,
        reason="power_limit" if limited else None,
    )


def _evaluate_ev_command(
    snapshot: EvActuatorSnapshot,
    request: ActuatorPowerRequest,
) -> ActuatorCommandResult:
    raw_requested = float(request.requested_power_w)
    requested = max(0.0, raw_requested)
    if not snapshot.planning_available:
        return _rejected(snapshot, raw_requested, snapshot.status)
    if raw_requested < 0.0:
        return ActuatorCommandResult(
            actuator_id=snapshot.actuator_id,
            kind=snapshot.kind,
            requested_power_w=raw_requested,
            accepted_power_w=0.0,
            status="limited",
            limited=True,
            reason="negative_power_not_supported",
            phase_count=0,
            current_a=0.0,
        )
    if requested == 0.0:
        return ActuatorCommandResult(
            actuator_id=snapshot.actuator_id,
            kind=snapshot.kind,
            requested_power_w=raw_requested,
            accepted_power_w=0.0,
            status="accepted",
            limited=False,
            phase_count=0,
            current_a=0.0,
        )

    candidates = _ev_power_candidates(snapshot.capabilities)
    feasible = [candidate for candidate in candidates if candidate[0] <= requested + 1e-6]
    if not feasible:
        return ActuatorCommandResult(
            actuator_id=snapshot.actuator_id,
            kind=snapshot.kind,
            requested_power_w=float(request.requested_power_w),
            accepted_power_w=0.0,
            status="limited",
            limited=True,
            reason="below_minimum_charge_power",
            phase_count=0,
            current_a=0.0,
        )

    accepted_power, phase_count, current_a = max(feasible, key=lambda candidate: candidate[0])
    limited = not math.isclose(accepted_power, requested, abs_tol=1e-6)
    return ActuatorCommandResult(
        actuator_id=snapshot.actuator_id,
        kind=snapshot.kind,
        requested_power_w=float(request.requested_power_w),
        accepted_power_w=accepted_power,
        status="limited" if limited else "accepted",
        limited=limited,
        reason="discrete_charge_step" if limited else None,
        phase_count=phase_count,
        current_a=current_a,
    )


def _ev_power_candidates(capabilities: EvCapabilities) -> list[tuple[float, int, float]]:
    """Return feasible whole-ampere EV charging states ordered only by power at selection time."""
    minimum_current = math.ceil(capabilities.min_charge_current_a)
    maximum_current = math.floor(capabilities.max_charge_current_a)
    phase_counts: list[int] = []
    if capabilities.supports_single_phase:
        phase_counts.append(1)
    if capabilities.supports_three_phase:
        phase_counts.append(3)

    candidates: list[tuple[float, int, float]] = []
    for phase_count in phase_counts:
        for current_a in range(minimum_current, maximum_current + 1):
            power_w = phase_count * capabilities.nominal_voltage_v * float(current_a)
            candidates.append((power_w, phase_count, float(current_a)))
    return candidates


def _rejected(
    snapshot: ActuatorSnapshot,
    requested_power_w: float,
    reason: str,
) -> ActuatorCommandResult:
    return ActuatorCommandResult(
        actuator_id=snapshot.actuator_id,
        kind=snapshot.kind,
        requested_power_w=float(requested_power_w),
        accepted_power_w=0.0,
        status="rejected",
        limited=True,
        reason=reason,
    )


def find_ess_actuator(actuators: tuple[ActuatorSnapshot, ...]) -> EssActuatorSnapshot | None:
    """Return the ESS actuator snapshot from a planner actuator collection."""
    return next((item for item in actuators if isinstance(item, EssActuatorSnapshot)), None)


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)
