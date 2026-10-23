"""Explicit interpretations of installation sensors, independent of their entity names."""

from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any


def installation_configuration(document: dict[str, Any]) -> dict[str, Any]:
    """Resolve the confirmed P1/go-e setup without replacing other saved settings."""
    prepared = deepcopy(document)
    measurements = prepared.setdefault("measurements", {})
    for key, entity in (
        ("grid_import_kw", "sensor.p1_dongle_momentary_active_import"),
        ("grid_export_kw", "sensor.p1_dongle_momentary_active_export"),
        ("quarter_import_kwh", "sensor.p1_dongle_current_quarter_average_demand"),
    ):
        if key not in measurements or measurements[key] == f"sensor.replace_{key}":
            measurements[key] = entity
    # These retired choices no longer control the application. Keep future extensions.
    options = prepared.get("measurement_options")
    if isinstance(options, dict):
        for key in ("house_source", "quarter_source", "phase_source"):
            options.pop(key, None)
        if not options:
            prepared.pop("measurement_options")
    return prepared


@dataclass(frozen=True)
class MeasurementOptions:
    house_source: str = "direct"
    quarter_source: str = "energy"
    phase_source: str = "count"

    @classmethod
    def installation(cls) -> MeasurementOptions:
        return cls(house_source="separate_grid", quarter_source="fixed_quarter_average",
                   phase_source="goe_selector")

    def __post_init__(self) -> None:
        for name, choices in (
            ("house_source", ("direct", "total_consumption", "signed_grid", "separate_grid")),
            ("quarter_source", ("energy", "elapsed_average", "fixed_quarter_average")),
            ("phase_source", ("count", "goe_selector")),
        ):
            if getattr(self, name) not in choices:
                raise ValueError(f"Invalid measurement option {name}")

    def house_power(self, measured_kw: float, ev_kw: float, pv_ac_kw: float, ess_kw: float) -> float:
        """Remove EV once; grid reconstruction uses ESS AC power, positive discharge."""
        if self.house_source == "total_consumption":
            result = measured_kw - ev_kw
        elif self.house_source in ("signed_grid", "separate_grid"):
            result = measured_kw + pv_ac_kw + ess_kw - ev_kw
        else:
            result = measured_kw
        if result < -0.1:
            raise ValueError("Derived house demand is negative; check power signs and meter topology")
        return max(0, result)  # Allow small differences between asynchronously sampled sensors.

    def quarter_energy(self, value: float, reported_at: datetime) -> float:
        if value < 0 or not math.isfinite(value):
            raise ValueError("Quarter-hour import must be finite and nonnegative")
        if self.quarter_source == "energy":
            return value
        if self.quarter_source == "fixed_quarter_average":
            return value * 0.25
        start = reported_at.replace(minute=reported_at.minute // 15 * 15, second=0, microsecond=0)
        return value * (reported_at - start).total_seconds() / 3600

    def phase_count(self, state: str) -> int | None:
        """A forced mode readback is operational state, not physical phase telemetry."""
        if self.phase_source == "goe_selector":
            return {"1": 1, "2": 3}.get(state)
        try:
            value = float(state)
        except ValueError:
            return None
        return int(value) if value in (1, 3) else None
