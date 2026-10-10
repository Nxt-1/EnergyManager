"""Read-only planning primitives and forecast frame for the MILP planner."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .actuators import ActuatorSnapshot, EssCapabilities, find_ess_actuator
from .load_forecast import FORECAST_INTERVAL_MINUTES, BackgroundLoadForecast
from .pv_forecast import PvForecast
from .tasks import PlanningTask

PLANNER_VERSION = "2026-10-08-shadow-v10"
PLANNER_HORIZON_HOURS = 168
_INTERVAL_HOURS = FORECAST_INTERVAL_MINUTES / 60.0


@dataclass(frozen=True, slots=True)
class ShadowPlanInterval:
    """One 15-minute interval in the planner forecast or solved MILP plan."""

    period_start_local: datetime
    background_load_w: float
    scheduled_load_w: float
    pv_ac_power_w: float
    pv_dc_power_w: float
    pv_power_w: float
    net_power_before_control_w: float
    ess_ac_power_w: float | None = None
    battery_energy_delta_kwh: float | None = None
    projected_soc_percent: float | None = None
    grid_power_after_ess_w: float | None = None
    curtailed_dc_pv_w: float | None = None

    @property
    def total_load_w(self) -> float:
        return self.background_load_w + self.scheduled_load_w


@dataclass(frozen=True, slots=True)
class ShadowPlan:
    """Read-only seven-day forecast frame or solved MILP plan."""

    generated_at_utc: datetime
    intervals: tuple[ShadowPlanInterval, ...]
    ess_projection_status: str = "not_solved"
    actuator_snapshots: tuple[ActuatorSnapshot, ...] = ()
    tasks: tuple[PlanningTask, ...] = ()
    ess_resource: EssCapabilities | None = None
    ess_initial_soc_percent: float | None = None
    scheduling_strategy: str = "milp_input"
    optimizer_status: str = "pending"
    optimizer_objective: str | None = None
    optimizer_score_eur: float | None = None
    optimizer_baseline_score_eur: float | None = None
    optimizer_candidate_evaluations: int = 0
    preferred_ev_shortfall_kwh: float = 0.0
    preferred_ev_shortfall_penalty_eur: float = 0.0

    def summary(self, hours: int) -> dict[str, float | int | str | None]:
        """Return compact energy/peak statistics for the first requested hours."""
        count = min(len(self.intervals), max(0, hours * 60 // FORECAST_INTERVAL_MINUTES))
        intervals = self.intervals[:count]
        if not intervals:
            return {
                "hours": hours,
                "intervals": 0,
                "background_load_kwh": 0.0,
                "scheduled_load_kwh": 0.0,
                "pv_potential_kwh": 0.0,
                "pv_ac_potential_kwh": 0.0,
                "pv_dc_potential_kwh": 0.0,
                "net_deficit_kwh": 0.0,
                "net_surplus_kwh": 0.0,
                "max_net_deficit_w": 0.0,
                "ess_projection_status": self.ess_projection_status,
                "grid_import_after_ess_kwh": None,
                "grid_export_after_ess_kwh": None,
                "curtailed_dc_pv_kwh": None,
                "ess_ac_discharge_kwh": None,
                "ess_ac_charge_kwh": None,
                "battery_charge_stored_kwh": None,
                "battery_discharge_stored_kwh": None,
                "end_soc_percent": None,
                "min_soc_percent": None,
                "max_soc_percent": None,
                "max_grid_import_after_ess_w": None,
            }

        background = sum(item.background_load_w for item in intervals) * _INTERVAL_HOURS / 1000.0
        scheduled = sum(item.scheduled_load_w for item in intervals) * _INTERVAL_HOURS / 1000.0
        pv_ac = sum(item.pv_ac_power_w for item in intervals) * _INTERVAL_HOURS / 1000.0
        pv_dc = sum(item.pv_dc_power_w for item in intervals) * _INTERVAL_HOURS / 1000.0
        deficit = (
            sum(max(0.0, item.net_power_before_control_w) for item in intervals) * _INTERVAL_HOURS / 1000.0
        )
        surplus = (
            sum(max(0.0, -item.net_power_before_control_w) for item in intervals) * _INTERVAL_HOURS / 1000.0
        )
        result: dict[str, float | int | str | None] = {
            "hours": hours,
            "intervals": len(intervals),
            "background_load_kwh": background,
            "scheduled_load_kwh": scheduled,
            "pv_potential_kwh": pv_ac + pv_dc,
            "pv_ac_potential_kwh": pv_ac,
            "pv_dc_potential_kwh": pv_dc,
            "net_deficit_kwh": deficit,
            "net_surplus_kwh": surplus,
            "max_net_deficit_w": max(max(0.0, item.net_power_before_control_w) for item in intervals),
            "ess_projection_status": self.ess_projection_status,
            "grid_import_after_ess_kwh": None,
            "grid_export_after_ess_kwh": None,
            "curtailed_dc_pv_kwh": None,
            "ess_ac_discharge_kwh": None,
            "ess_ac_charge_kwh": None,
            "battery_charge_stored_kwh": None,
            "battery_discharge_stored_kwh": None,
            "end_soc_percent": None,
            "min_soc_percent": None,
            "max_soc_percent": None,
            "max_grid_import_after_ess_w": None,
        }
        if self.ess_projection_status != "projected":
            return result

        projected = [item for item in intervals if item.grid_power_after_ess_w is not None]
        if len(projected) != len(intervals):
            return result
        grid_values = [float(item.grid_power_after_ess_w) for item in projected]
        ess_ac_values = [float(item.ess_ac_power_w) for item in projected if item.ess_ac_power_w is not None]
        battery_deltas = [
            float(item.battery_energy_delta_kwh)
            for item in projected
            if item.battery_energy_delta_kwh is not None
        ]
        soc_values = [
            float(item.projected_soc_percent)
            for item in projected
            if item.projected_soc_percent is not None
        ]
        curtailed_values = [
            float(item.curtailed_dc_pv_w)
            for item in projected
            if item.curtailed_dc_pv_w is not None
        ]
        result.update(
            {
                "grid_import_after_ess_kwh": (
                    sum(max(0.0, power) for power in grid_values) * _INTERVAL_HOURS / 1000.0
                ),
                "grid_export_after_ess_kwh": (
                    sum(max(0.0, -power) for power in grid_values) * _INTERVAL_HOURS / 1000.0
                ),
                "curtailed_dc_pv_kwh": sum(curtailed_values) * _INTERVAL_HOURS / 1000.0,
                "ess_ac_discharge_kwh": (
                    sum(max(0.0, power) for power in ess_ac_values) * _INTERVAL_HOURS / 1000.0
                ),
                "ess_ac_charge_kwh": (
                    sum(max(0.0, -power) for power in ess_ac_values) * _INTERVAL_HOURS / 1000.0
                ),
                "battery_charge_stored_kwh": sum(max(0.0, delta) for delta in battery_deltas),
                "battery_discharge_stored_kwh": sum(max(0.0, -delta) for delta in battery_deltas),
                "end_soc_percent": soc_values[-1] if soc_values else None,
                "min_soc_percent": min(soc_values) if soc_values else None,
                "max_soc_percent": max(soc_values) if soc_values else None,
                "max_grid_import_after_ess_w": max(max(0.0, power) for power in grid_values),
            }
        )
        return result


class ShadowPlanner:
    """Merge load and PV forecasts into the neutral input frame consumed by MILP."""

    def build(
        self,
        load_forecast: BackgroundLoadForecast,
        pv_forecast: PvForecast,
        *,
        now_utc: datetime,
        actuators: tuple[ActuatorSnapshot, ...] = (),
        tasks: tuple[PlanningTask, ...] = (),
    ) -> ShadowPlan:
        if now_utc.tzinfo is None:
            raise ValueError("now_utc must be timezone-aware")
        horizon_end_utc = now_utc.astimezone(UTC) + timedelta(hours=PLANNER_HORIZON_HOURS)
        load_points = [
            point
            for point in load_forecast.points
            if now_utc.astimezone(UTC) <= point.period_start_local.astimezone(UTC) < horizon_end_utc
        ]
        if not load_points:
            raise ValueError("Background-load forecast has no future intervals in the planning horizon")

        intervals: list[ShadowPlanInterval] = []
        for load_point in load_points:
            pv_ac_w, pv_dc_w = _pv_powers_for_interval(pv_forecast, load_point.period_start_local)
            background_w = max(0.0, load_point.power_w)
            pv_total_w = pv_ac_w + pv_dc_w
            intervals.append(
                ShadowPlanInterval(
                    period_start_local=load_point.period_start_local,
                    background_load_w=background_w,
                    scheduled_load_w=0.0,
                    pv_ac_power_w=pv_ac_w,
                    pv_dc_power_w=pv_dc_w,
                    pv_power_w=pv_total_w,
                    net_power_before_control_w=background_w - pv_total_w,
                )
            )

        ess = find_ess_actuator(actuators)
        return ShadowPlan(
            generated_at_utc=now_utc.astimezone(UTC),
            intervals=tuple(intervals),
            actuator_snapshots=actuators,
            tasks=tasks,
            ess_resource=ess.capabilities if ess is not None and ess.configured else None,
            ess_initial_soc_percent=ess.soc_percent if ess is not None else None,
            scheduling_strategy="milp_input",
            optimizer_status="pending",
        )


def _pv_powers_for_interval(forecast: PvForecast, interval_start_local: datetime) -> tuple[float, float]:
    """Return AC-coupled roof and DC-coupled shed PV potential for one planner interval."""
    start_utc = interval_start_local.astimezone(UTC)
    for point in forecast.points:
        end_utc = point.period_end_local.astimezone(UTC)
        if end_utc - timedelta(hours=1) <= start_utc < end_utc:
            ac_power_w = max(0.0, point.front_power_w + point.rear_power_w)
            dc_power_w = max(0.0, point.shed_power_w)
            return ac_power_w, dc_power_w
    return 0.0, 0.0
