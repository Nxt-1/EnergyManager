"""Power-state conversion helpers."""

from __future__ import annotations

import math
from typing import Any


class PowerStateError(ValueError):
    """Raised when a Home Assistant state cannot be interpreted as electrical power."""


def power_w_from_state(state: dict[str, Any]) -> float:
    """Convert a Home Assistant power state to watts while preserving its sign."""
    raw_value = state.get("state")
    if raw_value is None:
        raise PowerStateError("State has no value")

    text_value = str(raw_value).strip().lower()
    if text_value in {"", "unknown", "unavailable", "none", "null"}:
        raise PowerStateError(f"Power state is not currently numeric: {raw_value!r}")

    try:
        value = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise PowerStateError(f"Power state is not numeric: {raw_value!r}") from exc

    if not math.isfinite(value):
        raise PowerStateError(f"Power state is not finite: {raw_value!r}")

    attributes = state.get("attributes") or {}
    unit = str(attributes.get("unit_of_measurement", "")).strip()

    if unit == "W":
        return value
    if unit == "kW":
        return value * 1000.0

    raise PowerStateError(f"Unsupported power unit {unit!r}; expected 'W' or 'kW'")


def grid_net_power_w(import_power_w: float, export_power_w: float) -> float:
    """Return canonical net grid power: positive import, negative export."""
    if import_power_w < 0:
        raise PowerStateError(f"Grid import power cannot be negative: {import_power_w} W")
    if export_power_w < 0:
        raise PowerStateError(f"Grid export power cannot be negative: {export_power_w} W")
    return import_power_w - export_power_w
