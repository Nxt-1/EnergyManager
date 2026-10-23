"""Immutable, unit-explicit contracts shared by planning, control and persistence."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any
from zoneinfo import ZoneInfo


def instant(value: str | datetime) -> datetime:
    result = datetime.fromisoformat(value) if isinstance(value, str) else value
    if result.tzinfo is None:
        raise ValueError("A timezone offset is required")
    return result.astimezone(UTC)


def json_data(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return json_data(asdict(value))
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): json_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_data(item) for item in value]
    return value


def encode(value: Any) -> str:
    return json.dumps(json_data(value), sort_keys=True, allow_nan=False, separators=(",", ":"))


@dataclass(frozen=True)
class Capabilities:
    # Defaults are declared synthetic development assumptions, never commissioning facts.
    ev_capacity_kwh: float = 60.0
    ess_capacity_kwh: float = 14.0
    ess_min_kwh: float = 2.8
    ac_charge_kw: float = 2.5
    ac_discharge_kw: float = 2.5
    dc_charge_kw: float = 6.0
    battery_charge_kw: float = 8.0
    battery_discharge_kw: float = 4.0
    ev_efficiency: float = 0.90
    ac_charge_efficiency: float = 0.95
    ac_discharge_efficiency: float = 0.95
    dc_efficiency: float = 0.98
    voltage: float = 230.0
    minimum_current_a: int = 6
    maximum_current_a: int = 16
    phases: tuple[int, ...] = (1, 3)
    phase_dwell_seconds: float = 600.0
    grid_connection_kw: float = 17.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "phases", tuple(self.phases))
        for name, value in asdict(self).items():
            if name != "phases" and (not math.isfinite(value) or value < 0):
                raise ValueError(f"Invalid capability {name}")
        for name in ("ev_efficiency", "ac_charge_efficiency", "ac_discharge_efficiency", "dc_efficiency"):
            if not 0 < getattr(self, name) <= 1:
                raise ValueError(f"Invalid efficiency {name}")
        if not 0 <= self.ess_min_kwh < self.ess_capacity_kwh or self.ev_capacity_kwh <= 0:
            raise ValueError("Invalid battery capacity")
        if not self.phases or any(p not in (1, 3) for p in self.phases):
            raise ValueError("Supported phase counts are 1 and 3")
        if not 0 < self.minimum_current_a <= self.maximum_current_a:
            raise ValueError("Invalid current range")


@dataclass(frozen=True)
class Policy:
    timezone: str = "Europe/Brussels"
    daily_soc_percent: float = 50.0
    daily_time: str = "07:00"
    consumption_kwh_per_100km: float = 18.0
    arrival_reserve_km: float = 30.0
    normal_soc_percent: float = 80.0
    import_eur_kwh: float = 0.30556
    export_eur_kwh: float = 0.03970
    capacity_eur_kw_month: float = 4.36417
    billing_floor_kw: float = 2.5
    automatic_peak_kw: float = 4.0
    ev_value_eur_kwh: float = 0.3395111111
    ess_value_eur_kwh: float = 0.290282
    planning_budget_seconds: float = 60.0
    polish_tolerance_eur: float = 0.02
    completion_margin_minutes: int = 15
    measurement_max_age_seconds: float = 30.0
    forecast_max_age_seconds: float = 7200.0
    control_period_seconds: float = 1.0
    sustained_deviation_seconds: float = 20.0
    control_enabled: bool = False

    def __post_init__(self) -> None:
        ZoneInfo(self.timezone)
        if not 0 <= self.normal_soc_percent <= 100 or not 0 <= self.daily_soc_percent <= 100:
            raise ValueError("Invalid SoC policy")
        for name, value in asdict(self).items():
            if isinstance(value, (float, int)) and (not math.isfinite(value) or value < 0):
                raise ValueError(f"Invalid policy {name}")
        if self.export_eur_kwh > self.import_eur_kwh:
            raise ValueError("This fixed-tariff policy requires export price <= import price")


@dataclass(frozen=True)
class Goal:
    id: str
    title: str
    deadline: datetime
    target_soc_percent: float = 50.0
    kind: str = "manual"
    revision: int = 1
    priority: int = 50
    distance_km: float = 0.0
    return_at: datetime | None = None
    earliest: datetime | None = None
    approved_peak_kw: float | None = None
    approval_revision: int = 0
    approval_state: str = "none"
    rejected_peak_kw: float | None = None

    def __post_init__(self) -> None:
        if self.kind not in ("manual", "trip", "daily"):
            raise ValueError("Unknown goal kind")
        if (
            not isinstance(self.priority, int)
            or not 0 <= self.priority <= 1000
            or not isinstance(self.revision, int)
            or self.revision < 1
        ):
            raise ValueError("Invalid goal priority/revision")
        if not self.id or not self.title.strip() or not 0 <= self.target_soc_percent <= 100:
            raise ValueError("Invalid goal identity or target")
        if not math.isfinite(self.distance_km) or self.distance_km < 0:
            raise ValueError("Invalid journey distance")
        if self.return_at is not None and instant(self.return_at) <= instant(self.deadline):
            raise ValueError("Return must follow departure")
        instant(self.deadline)

    def withdrawal(self, policy: Policy) -> float:
        return self.distance_km * policy.consumption_kwh_per_100km / 100 if self.kind == "trip" else 0.0

    def target(self, capabilities: Capabilities, policy: Policy) -> float:
        if self.kind == "trip":
            journey = self.withdrawal(policy)
            reserve = policy.arrival_reserve_km * policy.consumption_kwh_per_100km / 100
            return min(capabilities.ev_capacity_kwh, journey + reserve)
        return self.target_soc_percent / 100 * capabilities.ev_capacity_kwh

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Goal:
        data = dict(value)
        for name in ("deadline", "return_at", "earliest"):
            if data.get(name):
                data[name] = instant(data[name])
        return cls(**data)


@dataclass(frozen=True)
class Observation:
    at: datetime
    ev_kwh: float
    ess_kwh: float
    connected: bool
    house_kw: float
    pv_ac_kw: float
    pv_dc_kw: float
    ev_power_kw: float = 0.0
    ess_power_kw: float = 0.0  # Positive supplies the AC bus.
    quarter_import_kwh: float = 0.0
    monthly_peak_kw: float = 2.5
    ev_phases: int = 1
    quality: str = "measured"
    ess_grid_kwh: float = 0.0
    ev_state_known: bool = True
    ev_observed_at: datetime | None = None

    def __post_init__(self) -> None:
        instant(self.at)
        for name, value in asdict(self).items():
            if isinstance(value, (float, int)) and not math.isfinite(value):
                raise ValueError(f"Non-finite observation {name}")
        if (
            min(
                self.ev_kwh,
                self.ess_kwh,
                self.house_kw,
                self.pv_ac_kw,
                self.pv_dc_kw,
                self.ev_power_kw,
                self.quarter_import_kwh,
                self.monthly_peak_kw,
                self.ess_grid_kwh,
            )
            < 0
        ):
            raise ValueError("Invalid negative observation")
        if self.ev_phases not in (1, 3) or not isinstance(self.connected, bool):
            raise ValueError("Invalid EV mode/connection observation")


@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime
    house_kw: float
    pv_ac_kw: float
    pv_dc_kw: float
    available: bool = True
    withdrawal_kwh: float = 0.0
    ev_state_known: bool = True

    @property
    def hours(self) -> float:
        return (self.end - self.start).total_seconds() / 3600


@dataclass(frozen=True)
class PeakPermission:
    id: str
    forecast_id: str
    deadline: datetime
    peak_kw: float
    state: str = "pending"
    revision: int = 1

    def __post_init__(self) -> None:
        if (
            self.state not in ("pending", "granted", "rejected")
            or not math.isfinite(self.peak_kw)
            or self.peak_kw <= 0
        ):
            raise ValueError("Invalid peak permission")
        instant(self.deadline)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> PeakPermission:
        return cls(**{**value, "deadline": instant(value["deadline"])})


@dataclass(frozen=True)
class Snapshot:
    id: str
    revision: int
    observation: Observation
    forecast_at: datetime
    forecast_id: str
    intervals: tuple[Interval, ...]
    goals: tuple[Goal, ...]
    capabilities: Capabilities = field(default_factory=Capabilities)
    policy: Policy = field(default_factory=Policy)
    provenance: str = "SYNTHETIC deterministic fixture"
    hold_until: datetime | None = None
    hold_ev_kw: float = 0.0
    hold_phases: int = 1
    hold_plan_id: str | None = None
    peak_permissions: tuple[PeakPermission, ...] = ()

    def __post_init__(self) -> None:
        if not self.intervals:
            raise ValueError("Empty forecast")
        for index, interval in enumerate(self.intervals):
            if not 0 < interval.hours <= 5 / 60 + 1e-9:
                raise ValueError("Planning intervals must be at most five minutes")
            if index and interval.start != self.intervals[index - 1].end:
                raise ValueError("Forecast must be continuous")
            for value in (interval.house_kw, interval.pv_ac_kw, interval.pv_dc_kw, interval.withdrawal_kwh):
                if not math.isfinite(value) or value < 0:
                    raise ValueError("Invalid forecast value")
        c, o = self.capabilities, self.observation
        if not 0 <= o.ev_kwh <= c.ev_capacity_kwh or not c.ess_min_kwh <= o.ess_kwh <= c.ess_capacity_kwh:
            raise ValueError("Measured battery state outside physical bounds")
        if not 0 <= o.ess_grid_kwh <= o.ess_kwh - c.ess_min_kwh + 1e-8:
            raise ValueError("Invalid ESS provenance ledger")

    @property
    def digest(self) -> str:
        return sha256(encode(self).encode()).hexdigest()

    def checkpoint_index(self, deadline: datetime) -> int:
        return sum(interval.end <= instant(deadline) for interval in self.intervals)

    def ev_known_at(self, index: int) -> bool:
        return self.observation.ev_state_known and (index == 0 or self.intervals[index - 1].ev_state_known)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Snapshot:
        observation = dict(data["observation"])
        observation["at"] = instant(observation["at"])
        if observation.get("ev_observed_at"):
            observation["ev_observed_at"] = instant(observation["ev_observed_at"])
        intervals = tuple(
            Interval(**{**i, "start": instant(i["start"]), "end": instant(i["end"])})
            for i in data["intervals"]
        )
        return cls(
            id=data["id"],
            revision=data["revision"],
            observation=Observation(**observation),
            forecast_at=instant(data["forecast_at"]),
            forecast_id=data["forecast_id"],
            intervals=intervals,
            goals=tuple(Goal.from_dict(g) for g in data["goals"]),
            capabilities=Capabilities(**data["capabilities"]),
            policy=Policy(**data["policy"]),
            provenance=data["provenance"],
            hold_until=instant(data["hold_until"]) if data.get("hold_until") else None,
            hold_ev_kw=data.get("hold_ev_kw", 0.0),
            hold_phases=data.get("hold_phases", 1),
            hold_plan_id=data.get("hold_plan_id"),
            peak_permissions=tuple(PeakPermission.from_dict(p) for p in data.get("peak_permissions", [])),
        )


def time_grid(
    start: datetime, hours: float = 168, boundaries: tuple[datetime, ...] = ()
) -> tuple[datetime, ...]:
    """Use elapsed UTC time; split first/last intervals and exact goal/travel boundaries."""
    start = instant(start)
    end = start + timedelta(hours=hours)
    points = {start, end}
    # A short first window allows safe phase preparation before a newly accepted start.
    if start + timedelta(seconds=15) < end:
        points.add(start + timedelta(seconds=15))
    cursor = datetime.fromtimestamp((int(start.timestamp()) // 300 + 1) * 300, UTC)
    while cursor < end:
        points.add(cursor)
        cursor += timedelta(minutes=5)
    points.update(instant(value) for value in boundaries if start < instant(value) < end)
    return tuple(sorted(points))


def daily_goals(start: datetime, end: datetime, policy: Policy, trips: tuple[Goal, ...]) -> tuple[Goal, ...]:
    zone = ZoneInfo(policy.timezone)
    hour, minute = map(int, policy.daily_time.split(":"))
    day = instant(start).astimezone(zone).date()
    result: list[Goal] = []
    while day <= instant(end).astimezone(zone).date():
        deadline = datetime(day.year, day.month, day.day, hour, minute, tzinfo=zone).astimezone(UTC)
        away = any(
            g.kind == "trip" and g.deadline < deadline and (g.return_at is None or deadline < g.return_at)
            for g in trips
        )
        if start < deadline <= end and not away:
            result.append(
                Goal(
                    f"daily-{day}",
                    "Morning minimum",
                    deadline,
                    policy.daily_soc_percent,
                    "daily",
                    priority=40,
                )
            )
        day += timedelta(days=1)
    return tuple(result)
