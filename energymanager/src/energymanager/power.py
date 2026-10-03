"""Normalization helpers for Home Assistant sensor states."""

from __future__ import annotations

import math
from typing import Any


class PowerStateError(ValueError):
    """Raised when a Home Assistant state cannot be normalized."""


def power_w_from_state(state: dict[str, Any]) -> float:
    """Convert a Home Assistant power state to watts while preserving its sign."""
    value = _finite_number(state)
    unit = str((state.get("attributes") or {}).get("unit_of_measurement", "")).strip()

    if unit == "W":
        return value
    if unit == "kW":
        return value * 1000.0

    raise PowerStateError(f"Unsupported power unit {unit!r}; expected 'W' or 'kW'")


def percentage_from_state(state: dict[str, Any]) -> float:
    """Normalize a percentage state and enforce the physical 0..100 range."""
    value = _finite_number(state)
    unit = str((state.get("attributes") or {}).get("unit_of_measurement", "")).strip()
    if unit not in {"", "%"}:
        raise PowerStateError(f"Unsupported percentage unit {unit!r}; expected '%' or no unit")
    if not 0.0 <= value <= 100.0:
        raise PowerStateError(f"Percentage is outside 0..100: {value}")
    return value


def state_bool(state: dict[str, Any]) -> bool:
    """Normalize common Home Assistant connection/binary state representations."""
    raw_value = state.get("state")
    if raw_value is None:
        raise PowerStateError("State has no value")

    value = str(raw_value).strip().lower()
    true_values = {"1", "true", "on", "yes", "connected", "plugged", "plugged_in"}
    false_values = {"0", "false", "off", "no", "disconnected", "unplugged"}
    if value in true_values:
        return True
    if value in false_values:
        return False
    if value in {"", "unknown", "unavailable", "none", "null"}:
        raise PowerStateError(f"Binary state is not currently usable: {raw_value!r}")
    raise PowerStateError(f"Unsupported binary state: {raw_value!r}")


def grid_net_power_w(import_power_w: float, export_power_w: float) -> float:
    """Return canonical net grid power: positive import, negative export."""
    if import_power_w < 0:
        raise PowerStateError(f"Grid import power cannot be negative: {import_power_w} W")
    if export_power_w < 0:
        raise PowerStateError(f"Grid export power cannot be negative: {export_power_w} W")
    return import_power_w - export_power_w


def _finite_number(state: dict[str, Any]) -> float:
    raw_value = state.get("state")
    if raw_value is None:
        raise PowerStateError("State has no value")

    text_value = str(raw_value).strip().lower()
    if text_value in {"", "unknown", "unavailable", "none", "null"}:
        raise PowerStateError(f"State is not currently numeric: {raw_value!r}")

    try:
        value = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise PowerStateError(f"State is not numeric: {raw_value!r}") from exc

    if not math.isfinite(value):
        raise PowerStateError(f"State is not finite: {raw_value!r}")
    return value
