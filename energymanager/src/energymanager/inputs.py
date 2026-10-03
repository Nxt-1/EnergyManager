"""Home Assistant input definitions and normalization for the canonical house state."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .config import Settings
from .power import PowerStateError, percentage_from_state, power_w_from_state, state_bool

Parser = Callable[[dict[str, Any]], float | bool]


@dataclass(frozen=True, slots=True)
class InputSpec:
    """Describe one semantic Energy Manager input and how to normalize it."""

    key: str
    entity_id: str | None
    unit: str | None
    parser: Parser


def build_input_specs(settings: Settings) -> tuple[InputSpec, ...]:
    """Build the v0.3 semantic input map from runtime configuration."""
    ess_sign = -1.0 if settings.ess.power_positive_means == "charge" else 1.0

    return (
        InputSpec(
            "grid.import_power",
            settings.grid.import_power_entity,
            "W",
            _non_negative_power,
        ),
        InputSpec(
            "grid.export_power",
            settings.grid.export_power_entity,
            "W",
            _non_negative_power,
        ),
        InputSpec("ess.soc", settings.ess.soc_entity, "%", percentage_from_state),
        InputSpec(
            "ess.power",
            settings.ess.power_entity,
            "W",
            lambda state: power_w_from_state(state) * ess_sign,
        ),
        InputSpec(
            "pv.solax_power",
            settings.pv.solax_power_entity,
            "W",
            _non_negative_power,
        ),
        InputSpec(
            "pv.shed_power",
            settings.pv.shed_power_entity,
            "W",
            _non_negative_power,
        ),
        InputSpec("ev.soc", settings.ev.soc_entity, "%", percentage_from_state),
        InputSpec("ev.connected", settings.ev.connected_entity, None, state_bool),
        InputSpec(
            "ev.charging_power",
            settings.ev.charging_power_entity,
            "W",
            _non_negative_power,
        ),
    )


def _non_negative_power(state: dict[str, Any]) -> float:
    value = power_w_from_state(state)
    if value < 0:
        raise PowerStateError(f"Directional power cannot be negative: {value} W")
    return value
