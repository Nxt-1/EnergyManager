"""Read-only shadow planning primitives for forecasted household energy flow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .actuators import ActuatorSnapshot, EssActuatorSnapshot, EssCapabilities, find_ess_actuator
from .load_forecast import FORECAST_INTERVAL_MINUTES, BackgroundLoadForecast
from .pv_forecast import PvForecast

PLANNER_VERSION = "2026-10-06-shadow-v3"
PLANNER_HORIZON_HOURS = 48
_INTERVAL_HOURS = FORECAST_INTERVAL_MINUTES / 60.0


@dataclass(frozen=True, slots=True)
class ShadowPlanInterval:
    """One 15-minute planner interval including an optional ESS feasibility projection."""

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
    """Planner-ready read-only energy balance used as the base for later scheduling."""

    generated_at_utc: datetime
    intervals: tuple[ShadowPlanInterval, ...]
    ess_projection_status: str = "not_configured"
    actuator_snapshots: tuple[ActuatorSnapshot, ...] = ()
    ess_resource: EssCapabilities | None = None
    ess_initial_soc_percent: float | None = None

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
    """Merge independent forecasts and project a conservative ESS self-consumption baseline."""

    def build(
        self,
        load_forecast: BackgroundLoadForecast,
        pv_forecast: PvForecast,
        *,
        now_utc: datetime,
        actuators: tuple[ActuatorSnapshot, ...] = (),
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

        base_intervals: list[ShadowPlanInterval] = []
        for load_point in load_points:
            pv_ac_w, pv_dc_w = _pv_powers_for_interval(pv_forecast, load_point.period_start_local)
            background_w = max(0.0, load_point.power_w)
            scheduled_w = 0.0
            pv_total_w = pv_ac_w + pv_dc_w
            base_intervals.append(
                ShadowPlanInterval(
                    period_start_local=load_point.period_start_local,
                    background_load_w=background_w,
                    scheduled_load_w=scheduled_w,
                    pv_ac_power_w=pv_ac_w,
                    pv_dc_power_w=pv_dc_w,
                    pv_power_w=pv_total_w,
                    net_power_before_control_w=background_w + scheduled_w - pv_total_w,
                )
            )

        ess_actuator = find_ess_actuator(actuators)
        if ess_actuator is None or not ess_actuator.configured:
            return ShadowPlan(
                generated_at_utc=now_utc.astimezone(UTC),
                intervals=tuple(base_intervals),
                ess_projection_status="not_configured",
                actuator_snapshots=actuators,
            )
        if not ess_actuator.planning_available or ess_actuator.soc_percent is None:
            return ShadowPlan(
                generated_at_utc=now_utc.astimezone(UTC),
                intervals=tuple(base_intervals),
                ess_projection_status=ess_actuator.status,
                actuator_snapshots=actuators,
                ess_resource=ess_actuator.capabilities,
            )

        projected_intervals = _project_ess(base_intervals, ess_actuator)
        return ShadowPlan(
            generated_at_utc=now_utc.astimezone(UTC),
            intervals=projected_intervals,
            ess_projection_status="projected",
            actuator_snapshots=actuators,
            ess_resource=ess_actuator.capabilities,
            ess_initial_soc_percent=max(0.0, min(100.0, ess_actuator.soc_percent)),
        )


def _project_ess(
    intervals: list[ShadowPlanInterval],
    actuator: EssActuatorSnapshot,
) -> tuple[ShadowPlanInterval, ...]:
    """Project greedy self-consumption through the ESS actuator capability envelope."""
    if actuator.soc_percent is None:
        raise ValueError("ESS actuator SoC is required for projection")
    resource = actuator.capabilities
    soc = max(0.0, min(100.0, actuator.soc_percent))
    stored_kwh = resource.capacity_kwh * soc / 100.0
    minimum_kwh = resource.capacity_kwh * resource.min_soc_percent / 100.0
    maximum_kwh = resource.capacity_kwh * resource.max_soc_percent / 100.0
    projected: list[ShadowPlanInterval] = []

    for item in intervals:
        ac_balance_w = item.total_load_w - item.pv_ac_power_w
        ess_ac_power_w = 0.0
        battery_delta_kwh = 0.0
        curtailed_dc_w = 0.0

        if ac_balance_w >= 0.0:
            dc_to_ac_w = min(
                ac_balance_w,
                resource.max_discharge_power_w,
                item.pv_dc_power_w * resource.discharge_efficiency,
            )
            dc_used_w = dc_to_ac_w / resource.discharge_efficiency
            ess_ac_power_w += dc_to_ac_w
            remaining_deficit_w = ac_balance_w - dc_to_ac_w
            inverter_headroom_w = max(0.0, resource.max_discharge_power_w - dc_to_ac_w)

            available_stored_kwh = max(0.0, stored_kwh - minimum_kwh)
            battery_ac_limit_w = (
                available_stored_kwh * resource.discharge_efficiency / _INTERVAL_HOURS * 1000.0
            )
            battery_to_ac_w = min(remaining_deficit_w, inverter_headroom_w, battery_ac_limit_w)
            battery_used_kwh = battery_to_ac_w / resource.discharge_efficiency * _INTERVAL_HOURS / 1000.0
            stored_kwh -= battery_used_kwh
            battery_delta_kwh -= battery_used_kwh
            ess_ac_power_w += battery_to_ac_w
            remaining_deficit_w -= battery_to_ac_w

            unused_dc_w = max(0.0, item.pv_dc_power_w - dc_used_w)
            room_kwh = max(0.0, maximum_kwh - stored_kwh)
            charge_by_room_w = room_kwh / resource.charge_efficiency / _INTERVAL_HOURS * 1000.0
            dc_charge_w = min(unused_dc_w, resource.max_charge_power_w, charge_by_room_w)
            stored_added_kwh = dc_charge_w * resource.charge_efficiency * _INTERVAL_HOURS / 1000.0
            stored_kwh += stored_added_kwh
            battery_delta_kwh += stored_added_kwh
            curtailed_dc_w = max(0.0, unused_dc_w - dc_charge_w)
            grid_after_ess_w = max(0.0, remaining_deficit_w)
        else:
            ac_surplus_w = -ac_balance_w
            room_kwh = max(0.0, maximum_kwh - stored_kwh)
            charge_by_room_w = room_kwh / resource.charge_efficiency / _INTERVAL_HOURS * 1000.0
            dc_charge_w = min(item.pv_dc_power_w, resource.max_charge_power_w, charge_by_room_w)
            stored_added_dc_kwh = dc_charge_w * resource.charge_efficiency * _INTERVAL_HOURS / 1000.0
            stored_kwh += stored_added_dc_kwh
            battery_delta_kwh += stored_added_dc_kwh
            curtailed_dc_w = max(0.0, item.pv_dc_power_w - dc_charge_w)

            charge_headroom_w = max(0.0, resource.max_charge_power_w - dc_charge_w)
            room_kwh = max(0.0, maximum_kwh - stored_kwh)
            charge_by_room_w = room_kwh / resource.charge_efficiency / _INTERVAL_HOURS * 1000.0
            ac_charge_w = min(ac_surplus_w, charge_headroom_w, charge_by_room_w)
            stored_added_ac_kwh = ac_charge_w * resource.charge_efficiency * _INTERVAL_HOURS / 1000.0
            stored_kwh += stored_added_ac_kwh
            battery_delta_kwh += stored_added_ac_kwh
            ess_ac_power_w -= ac_charge_w
            grid_after_ess_w = -(ac_surplus_w - ac_charge_w)

        stored_kwh = max(0.0, min(resource.capacity_kwh, stored_kwh))
        projected_soc = 100.0 * stored_kwh / resource.capacity_kwh
        projected.append(
            ShadowPlanInterval(
                period_start_local=item.period_start_local,
                background_load_w=item.background_load_w,
                scheduled_load_w=item.scheduled_load_w,
                pv_ac_power_w=item.pv_ac_power_w,
                pv_dc_power_w=item.pv_dc_power_w,
                pv_power_w=item.pv_power_w,
                net_power_before_control_w=item.net_power_before_control_w,
                ess_ac_power_w=ess_ac_power_w,
                battery_energy_delta_kwh=battery_delta_kwh,
                projected_soc_percent=projected_soc,
                grid_power_after_ess_w=grid_after_ess_w,
                curtailed_dc_pv_w=curtailed_dc_w,
            )
        )

    return tuple(projected)


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
