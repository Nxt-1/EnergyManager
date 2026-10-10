"""Live-control health evaluation and Home Assistant diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from .house_state import HouseState, InputStatus

CONTROL_HEALTH_VERSION = "2026-10-10-control-health-v1"
CONTROL_HEALTH_STATUS_ENTITY = "sensor.energy_manager_control_health"
_INPUT_FRESHNESS = timedelta(seconds=45)


@dataclass(frozen=True, slots=True)
class ControlHealth:
    """Availability of the live ESS/EV control paths."""

    state: str
    ess_available: bool
    ev_available: bool
    stale_inputs: tuple[str, ...]
    unavailable_inputs: tuple[str, ...]
    reasons: tuple[str, ...]
    replan_required: bool


async def publish_control_health(
    client,
    health: ControlHealth,
    *,
    ess_control_enabled: bool,
    ev_control_enabled: bool,
    ess_write_failures: int = 0,
    ev_write_failures: int = 0,
    ess_last_error: str | None = None,
    ev_last_error: str | None = None,
) -> None:
    """Publish one consolidated live-control health entity."""
    attributes: dict[str, Any] = {
        "friendly_name": "Energy Manager Control Health",
        "control_health_version": CONTROL_HEALTH_VERSION,
        "ess_control_enabled": ess_control_enabled,
        "ev_control_enabled": ev_control_enabled,
        "ess_available": health.ess_available,
        "ev_available": health.ev_available,
        "input_freshness_seconds": int(_INPUT_FRESHNESS.total_seconds()),
        "stale_inputs": list(health.stale_inputs),
        "unavailable_inputs": list(health.unavailable_inputs),
        "reasons": list(health.reasons),
        "replan_required": health.replan_required,
        "ess_write_failures": ess_write_failures,
        "ev_write_failures": ev_write_failures,
        "ess_last_error": ess_last_error,
        "ev_last_error": ev_last_error,
        "last_update_utc": datetime.now(UTC).isoformat(),
    }
    await client.set_state(CONTROL_HEALTH_STATUS_ENTITY, health.state, attributes)


def evaluate_control_health(
    house_state: HouseState,
    *,
    now_utc: datetime,
    ess_control_enabled: bool,
    ev_control_enabled: bool,
    ess_fault: str | None = None,
    ev_fault: str | None = None,
) -> ControlHealth:
    """Evaluate whether live inputs are safe enough for hardware control."""
    stale: list[str] = []
    unavailable: list[str] = []
    reasons: list[str] = []

    ess_available = True
    ev_available = True

    if ess_control_enabled:
        for key in ("grid.import_power", "grid.export_power", "ess.soc", "ess.power"):
            quality = _input_quality(house_state, key, now_utc)
            if quality == "stale":
                stale.append(key)
                ess_available = False
            elif quality != "valid":
                unavailable.append(key)
                ess_available = False
        if ess_fault is not None:
            ess_available = False
            reasons.append(f"ess:{ess_fault}")

    if ev_control_enabled:
        for key in ("ev.connected", "ev.soc"):
            quality = _input_quality(house_state, key, now_utc)
            if quality == "stale":
                stale.append(key)
                ev_available = False
            elif quality != "valid":
                unavailable.append(key)
                ev_available = False
        connected = house_state.value("ev.connected")
        if connected is False:
            ev_available = False
            reasons.append("ev:disconnected")
        if ev_fault is not None:
            ev_available = False
            reasons.append(f"ev:{ev_fault}")

    if stale:
        reasons.append("stale_inputs")
    if unavailable:
        reasons.append("unavailable_inputs")

    if ess_control_enabled and not ess_available:
        state = "safe_fallback"
    elif ev_control_enabled and not ev_available:
        state = "degraded"
    elif ess_fault is not None or ev_fault is not None:
        state = "degraded"
    else:
        state = "healthy"

    return ControlHealth(
        state=state,
        ess_available=ess_available,
        ev_available=ev_available,
        stale_inputs=tuple(stale),
        unavailable_inputs=tuple(unavailable),
        reasons=tuple(reasons),
        replan_required=(
            (ess_control_enabled and not ess_available)
            or (ev_control_enabled and not ev_available)
        ),
    )


def _input_quality(house_state: HouseState, key: str, now_utc: datetime) -> str:
    reading = house_state.readings.get(key)
    if reading is None or reading.entity_id is None:
        return "unavailable"
    if reading.status is not InputStatus.VALID or reading.value is None:
        return "unavailable"
    if reading.observed_at_utc is None:
        return "unavailable"
    observed = reading.observed_at_utc.astimezone(UTC)
    if now_utc.astimezone(UTC) - observed > _INPUT_FRESHNESS:
        return "stale"
    return "valid"
