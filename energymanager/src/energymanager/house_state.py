"""Normalized read-only house state used by later Energy Manager components."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum


class InputStatus(StrEnum):
    """Quality state for one configured Home Assistant input."""

    NOT_CONFIGURED = "not_configured"
    VALID = "valid"
    INVALID = "invalid"
    STALE = "stale"


@dataclass(slots=True)
class InputReading:
    """One normalized source value and its quality metadata."""

    key: str
    entity_id: str | None = None
    value: float | bool | None = None
    unit: str | None = None
    status: InputStatus = InputStatus.NOT_CONFIGURED
    observed_at_utc: datetime | None = None
    source_last_updated: str | None = None
    error: str | None = None

    @property
    def valid(self) -> bool:
        return self.status is InputStatus.VALID

    def configure(self, entity_id: str | None) -> None:
        self.entity_id = entity_id
        self.value = None
        self.observed_at_utc = None
        self.source_last_updated = None
        self.error = None
        self.status = InputStatus.INVALID if entity_id else InputStatus.NOT_CONFIGURED
        if entity_id:
            self.error = "Waiting for first valid observation"

    def set_valid(
        self,
        value: float | bool,
        *,
        unit: str | None,
        observed_at_utc: datetime,
        source_last_updated: str | None,
    ) -> None:
        self.value = value
        self.unit = unit
        self.status = InputStatus.VALID
        self.observed_at_utc = observed_at_utc
        self.source_last_updated = source_last_updated
        self.error = None

    def set_invalid(
        self,
        error: str,
        *,
        observed_at_utc: datetime,
        source_last_updated: str | None = None,
    ) -> None:
        self.value = None
        self.status = InputStatus.INVALID
        self.observed_at_utc = observed_at_utc
        self.source_last_updated = source_last_updated
        self.error = error

    def update_staleness(self, now_utc: datetime, stale_after: timedelta) -> None:
        if self.entity_id is None or self.observed_at_utc is None:
            return
        if self.status is InputStatus.INVALID:
            return
        age = now_utc - self.observed_at_utc
        if age > stale_after:
            self.status = InputStatus.STALE
            self.error = f"No successful observation for {int(age.total_seconds())} s"


@dataclass(slots=True)
class HouseState:
    """Canonical state snapshot assembled from configured Home Assistant inputs."""

    readings: dict[str, InputReading] = field(default_factory=dict)

    def ensure_input(self, key: str, entity_id: str | None) -> InputReading:
        reading = self.readings.setdefault(key, InputReading(key=key))
        if reading.entity_id != entity_id:
            reading.configure(entity_id)
        return reading

    def reading(self, key: str) -> InputReading:
        return self.readings[key]

    def value(self, key: str) -> float | bool | None:
        reading = self.readings.get(key)
        if reading is None or not reading.valid:
            return None
        return reading.value

    def update_staleness(self, stale_after: timedelta, *, now_utc: datetime | None = None) -> None:
        now = now_utc or datetime.now(UTC)
        for reading in self.readings.values():
            reading.update_staleness(now, stale_after)

    @property
    def grid_power_w(self) -> float | None:
        import_power = self._float_value("grid.import_power")
        export_power = self._float_value("grid.export_power")
        if import_power is None or export_power is None:
            return None
        return import_power - export_power

    @property
    def pv_total_power_w(self) -> float | None:
        configured = [
            reading
            for key in ("pv.solax_power", "pv.shed_power")
            if (reading := self.readings.get(key)) is not None and reading.entity_id is not None
        ]
        if not configured:
            return None
        if any(not reading.valid or not isinstance(reading.value, (int, float)) for reading in configured):
            return None
        return sum(float(reading.value) for reading in configured)

    @property
    def house_load_power_w(self) -> float | None:
        """Return instantaneous AC house load from the measured power balance.

        The shed MPPT is DC-coupled to the ESS and is therefore deliberately not
        added here. Its contribution to the AC bus is already represented by the
        normalized ESS AC power.
        """
        grid_power = self.grid_power_w
        if grid_power is None:
            return None

        solax_power = self._optional_configured_float("pv.solax_power")
        ess_power = self._optional_configured_float("ess.power")
        if solax_power is None or ess_power is None:
            return None

        return grid_power + solax_power + ess_power

    @property
    def known_controllable_load_power_w(self) -> float | None:
        """Return the measured power of controllable loads currently modeled.

        Version 0.6 starts with EV charging only. Unconfigured controllable loads
        contribute zero; configured-but-invalid inputs make the result unavailable.
        """
        ev_power = self._optional_configured_float("ev.charging_power")
        if ev_power is None:
            return None
        return ev_power

    @property
    def background_load_power_w(self) -> float | None:
        """Return house load after removing known controllable consumption."""
        house_load = self.house_load_power_w
        controllable_load = self.known_controllable_load_power_w
        if house_load is None or controllable_load is None:
            return None
        return house_load - controllable_load

    @property
    def configured_count(self) -> int:
        return sum(reading.entity_id is not None for reading in self.readings.values())

    @property
    def invalid_or_stale(self) -> tuple[InputReading, ...]:
        return tuple(
            reading
            for reading in self.readings.values()
            if reading.entity_id is not None and reading.status in {InputStatus.INVALID, InputStatus.STALE}
        )

    def _float_value(self, key: str) -> float | None:
        value = self.value(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return float(value)

    def _optional_configured_float(self, key: str) -> float | None:
        """Return zero when an optional source is unconfigured, else its valid value."""
        reading = self.readings.get(key)
        if reading is None or reading.entity_id is None:
            return 0.0
        if not reading.valid or isinstance(reading.value, bool) or not isinstance(reading.value, (int, float)):
            return None
        return float(reading.value)
