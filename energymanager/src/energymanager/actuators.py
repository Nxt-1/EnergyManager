"""Read-only actuator capability snapshots for planner use."""

from __future__ import annotations

from dataclasses import dataclass

from .config import EssSettings, EvSettings, Settings
from .house_state import HouseState

ACTUATOR_VERSION = "2026-10-06-actuator-v1"


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


class ActuatorRegistry:
    """Build read-only actuator snapshots from canonical Home Assistant state."""

    def __init__(self, settings: Settings) -> None:
        self._ess = settings.ess
        self._ev = settings.ev

    def snapshots(self, house_state: HouseState) -> tuple[ActuatorSnapshot, ...]:
        """Return all known actuator types, including unavailable/unconfigured devices."""
        return (
            _ess_snapshot(self._ess, house_state),
            _ev_snapshot(self._ev, house_state),
        )


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


def find_ess_actuator(actuators: tuple[ActuatorSnapshot, ...]) -> EssActuatorSnapshot | None:
    """Return the ESS actuator snapshot from a planner actuator collection."""
    return next((item for item in actuators if isinstance(item, EssActuatorSnapshot)), None)


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)
