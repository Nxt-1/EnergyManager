"""HA state validation, input-read watchdog and independent Overview values."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .domain import Capabilities, instant, json_data
from .measurements import MeasurementOptions


@dataclass(frozen=True)
class Reading:
    entity_id: str
    value: float | str | None
    unit: str | None
    reported_at: datetime | None
    received_at: datetime
    maximum_read_age: float
    timestamp_source: str | None
    error: str | None = None
    raw_state: str | None = None
    raw_unit: str | None = None

    @classmethod
    def parse(cls, entity: str, row: dict[str, Any] | BaseException, received_at: datetime,
              unit: str | None, maximum_read_age: float, *, nonnegative: bool = False) -> Reading:
        value: float | str | None = None
        reported_at = None
        source = None
        error = None
        raw_state = None
        raw_unit = None
        try:
            if isinstance(row, BaseException):
                raise ValueError(f"could not read entity ({type(row).__name__})")
            raw = str(row["state"])
            raw_state = raw[:256]
            actual_unit = row.get("attributes", {}).get("unit_of_measurement")
            raw_unit = str(actual_unit)[:64] if actual_unit is not None else None
            if raw.lower() in ("unknown", "unavailable", "none", ""):
                raise ValueError(f"state is {raw or 'empty'}")
            if unit is None:
                value = raw
            else:
                value = float(raw)
                if not math.isfinite(value):
                    value = None
                    raise ValueError("value is not finite")
                if unit == "%" and not 0 <= value <= 100:
                    value = None
                    raise ValueError("percentage must be between 0 and 100")
                if unit == "kW" and actual_unit == "W":
                    value /= 1000
                elif actual_unit != unit:
                    value = None
                    raise ValueError(f"requires declared {unit} units (received {actual_unit!r})")
                if nonnegative and value < 0:
                    value = None
                    raise ValueError("value must be nonnegative")
            source = "last_reported" if row.get("last_reported") else "last_updated"
            timestamp = row.get(source)
            if timestamp:
                try:
                    reported_at = instant(timestamp)
                except (ValueError, TypeError, AttributeError):
                    pass  # HA report metadata is diagnostic; availability/value checks grant authority.
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            error = str(exc)
        return cls(entity, value, unit, reported_at, received_at, maximum_read_age, source, error,
                   raw_state, raw_unit)

    def context(self) -> str:
        """Describe the original HA reading, even if numeric or unit validation failed."""
        return f"state={self.raw_state!r}, unit={self.raw_unit!r}, read_at={self.received_at.isoformat()}"

    def issue(self, at: datetime) -> str | None:
        reason = self.error
        if not reason:
            age = (at - self.received_at).total_seconds()
            if age < -5:
                reason = "HA input-read clock moved backwards"
            elif age > self.maximum_read_age:
                reason = f"last read from HA {age:.1f} s ago; watchdog limit {self.maximum_read_age:g} s"
        return f"{self.entity_id}: {reason} ({self.context()})" if reason else None

    def require(self, at: datetime) -> float | str:
        issue = self.issue(at)
        if issue or self.value is None:
            raise ValueError(issue or f"{self.entity_id}: value is missing")
        return self.value


class LiveInputs:
    """Retain successful reads even when another entity prevents a control snapshot."""

    def __init__(self, entities: dict[str, str], options: MeasurementOptions, maximum_read_age: float) -> None:
        self.entities, self.options = entities, options
        self.maximum_read_age = maximum_read_age
        self.readings: dict[str, Reading] = {}

    def update(self, values: dict[str, Any], received_at: datetime) -> None:
        units = {key: "kW" for key in (
            "house_kw", "pv_ac_kw", "pv_dc_kw", "ev_kw", "ess_kw", "grid_import_kw",
            "grid_export_kw", "monthly_peak_kw")}
        units.update(ev_soc="%", ess_soc="%",
                     quarter_import_kwh="kWh" if self.options.quarter_source == "energy" else "kW")
        self.readings = {}
        for key, row in values.items():
            self.readings[key] = Reading.parse(self.entities[key], row, received_at, units.get(key),
                self.maximum_read_age, nonnegative=key in ("pv_ac_kw", "pv_dc_kw", "grid_import_kw",
                    "grid_export_kw", "quarter_import_kwh", "monthly_peak_kw"))

    def number(self, key: str, at: datetime) -> float:
        return float(self.readings[key].require(at))

    def view(self, at: datetime, capabilities: Capabilities) -> dict[str, Any]:
        if not self.readings:
            return {"readings": {}, "cards": {}}
        readings = {
            key: {**json_data(reading), "issue": reading.issue(at),
                  "report_age_seconds": (at - reading.reported_at).total_seconds() if reading.reported_at else None,
                  "read_age_seconds": (at - reading.received_at).total_seconds()}
            for key, reading in self.readings.items()
        }

        def card(keys: tuple[str, ...], calculate: Callable[..., float]) -> dict[str, Any]:
            selected = [self.readings[key] for key in keys]
            issues = [issue for reading in selected if (issue := reading.issue(at))]
            value = None
            numbers = [reading.value for reading in selected if isinstance(reading.value, float)]
            if len(numbers) == len(selected):
                try:
                    value = calculate(*numbers)
                    if not math.isfinite(value):
                        value = None
                        raise ValueError("Calculated value is not finite")
                except ValueError as exc:
                    issues.append(str(exc))
            return {"value": value, "issues": issues}

        def display(key: str) -> str:
            value = self.readings[key].value
            return f"{value:.2f}" if isinstance(value, float) else "unavailable"

        power_keys = ("ev_kw", "pv_ac_kw", "ess_kw")
        house_keys: tuple[str, ...]
        if self.options.house_source == "separate_grid":
            house_keys = ("grid_import_kw", "grid_export_kw", *power_keys)
            house = card(house_keys, lambda imported, exported, ev, pv, ess:
                         self.options.house_power(imported - exported, ev, pv, ess))
            grid = card(("grid_import_kw", "grid_export_kw"), lambda imported, exported: imported - exported)
        else:
            house_keys = ("house_kw", *power_keys)
            house = card(house_keys, self.options.house_power)
            grid = card(house_keys, lambda measured, ev, pv, ess:
                        self.options.house_power(measured, ev, pv, ess) + ev - pv - ess)
        solar = card(("pv_ac_kw", "pv_dc_kw"), lambda ac, dc: ac + dc)
        ess = card(("ess_soc",), lambda soc: soc)
        ev = card(("ev_soc",), lambda soc: soc)
        quarter = self.readings["quarter_import_kwh"]
        quarter_kwh = None
        if isinstance(quarter.value, float):
            try:
                quarter_kwh = self.options.quarter_energy(quarter.value, quarter.received_at)
            except ValueError as exc:
                grid["issues"].append(f"{quarter.entity_id}: {exc}")
        if issue := quarter.issue(at):
            grid["issues"].append(issue)
        grid["label"] = (f"Quarter-hour import {quarter_kwh:.2f} kWh" if quarter_kwh is not None
                         else "Quarter-hour import unavailable")
        solar["label"] = f"AC {display('pv_ac_kw')} · DC {display('pv_dc_kw')} kW"
        house["label"] = "Uncontrolled demand"
        ess["label"] = f"Minimum {capabilities.ess_min_kwh / capabilities.ess_capacity_kwh * 100:.0f}% · {display('ess_kw')} kW"
        if issue := self.readings["ess_kw"].issue(at):
            ess["issues"].append(issue)
        connected = self.readings["connected"]
        ev["label"] = ("Connection unavailable" if connected.issue(at) else "Connected"
                       if str(connected.value).lower() in ("on", "true", "connected") else "Away / disconnected")
        if issue := connected.issue(at):
            ev["issues"].append(issue)
        return {"readings": readings, "cards": {"grid": grid, "solar": solar, "house": house, "ess": ess, "ev": ev}}
