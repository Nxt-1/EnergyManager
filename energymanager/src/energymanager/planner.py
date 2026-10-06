"""Read-only shadow planning primitives for forecasted household energy flow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .load_forecast import FORECAST_INTERVAL_MINUTES, BackgroundLoadForecast
from .pv_forecast import PvForecast

PLANNER_VERSION = "2026-10-06-shadow-v1"
PLANNER_HORIZON_HOURS = 48
_INTERVAL_HOURS = FORECAST_INTERVAL_MINUTES / 60.0


@dataclass(frozen=True, slots=True)
class ShadowPlanInterval:
    """One 15-minute planner interval before controllable resources are scheduled."""

    period_start_local: datetime
    background_load_w: float
    scheduled_load_w: float
    pv_power_w: float
    net_power_before_control_w: float

    @property
    def total_load_w(self) -> float:
        return self.background_load_w + self.scheduled_load_w


@dataclass(frozen=True, slots=True)
class ShadowPlan:
    """Planner-ready read-only energy balance used as the base for later scheduling."""

    generated_at_utc: datetime
    intervals: tuple[ShadowPlanInterval, ...]

    def summary(self, hours: int) -> dict[str, float | int]:
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
                "net_deficit_kwh": 0.0,
                "net_surplus_kwh": 0.0,
                "max_net_deficit_w": 0.0,
            }

        background = sum(item.background_load_w for item in intervals) * _INTERVAL_HOURS / 1000.0
        scheduled = sum(item.scheduled_load_w for item in intervals) * _INTERVAL_HOURS / 1000.0
        pv = sum(item.pv_power_w for item in intervals) * _INTERVAL_HOURS / 1000.0
        deficit = (
            sum(max(0.0, item.net_power_before_control_w) for item in intervals) * _INTERVAL_HOURS / 1000.0
        )
        surplus = (
            sum(max(0.0, -item.net_power_before_control_w) for item in intervals) * _INTERVAL_HOURS / 1000.0
        )
        return {
            "hours": hours,
            "intervals": len(intervals),
            "background_load_kwh": background,
            "scheduled_load_kwh": scheduled,
            "pv_potential_kwh": pv,
            "net_deficit_kwh": deficit,
            "net_surplus_kwh": surplus,
            "max_net_deficit_w": max(max(0.0, item.net_power_before_control_w) for item in intervals),
        }


class ShadowPlanner:
    """Merge independent forecasts onto the planner's 15-minute timeline."""

    def build(
        self,
        load_forecast: BackgroundLoadForecast,
        pv_forecast: PvForecast,
        *,
        now_utc: datetime,
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

        intervals = []
        for load_point in load_points:
            pv_w = _pv_power_for_interval(pv_forecast, load_point.period_start_local)
            background_w = max(0.0, load_point.power_w)
            scheduled_w = 0.0
            intervals.append(
                ShadowPlanInterval(
                    period_start_local=load_point.period_start_local,
                    background_load_w=background_w,
                    scheduled_load_w=scheduled_w,
                    pv_power_w=pv_w,
                    net_power_before_control_w=background_w + scheduled_w - pv_w,
                )
            )

        return ShadowPlan(
            generated_at_utc=now_utc.astimezone(UTC),
            intervals=tuple(intervals),
        )


def _pv_power_for_interval(forecast: PvForecast, interval_start_local: datetime) -> float:
    """Return the hourly PV-potential mean covering one 15-minute planner interval."""
    start_utc = interval_start_local.astimezone(UTC)
    for point in forecast.points:
        end_utc = point.period_end_local.astimezone(UTC)
        if end_utc - timedelta(hours=1) <= start_utc < end_utc:
            return max(0.0, point.total_power_w)
    return 0.0
