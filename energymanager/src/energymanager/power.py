"""Power-state conversion helpers."""

from __future__ import annotations

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

    attributes = state.get("attributes") or {}
    unit = str(attributes.get("unit_of_measurement", "")).strip()

    if unit == "W":
        return value
    if unit == "kW":
        return value * 1000.0

    raise PowerStateError(f"Unsupported power unit {unit!r}; expected 'W' or 'kW'")
