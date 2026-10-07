"""Versioned tariff inputs, capacity-peak state and shadow-plan economics."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, tzinfo
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from .config import EconomicsSettings
from .ha_client import HomeAssistantClient

if TYPE_CHECKING:
    from .house_state import HouseState
    from .planner import ShadowPlan

COST_MODEL_VERSION = "2026-10-07-cost-v1"
CAPACITY_PEAK_VERSION = "2026-10-07-capacity-v1"
PLAN_COST_VERSION = "2026-10-07-plan-cost-v1"
ECONOMICS_STATUS_ENTITY = "sensor.energy_manager_economics_status"
CAPACITY_STATUS_ENTITY = "sensor.energy_manager_capacity_tariff_status"
PLAN_COST_STATUS_ENTITY = "sensor.energy_manager_plan_cost_status"
_LOCAL_HISTORY_PATH = Path("/data/tariff_profile_history.jsonl")
_CAPACITY_WINDOW = timedelta(minutes=15)
_MIN_LIVE_COVERAGE_SECONDS = 810.0
_MAX_LIVE_SAMPLE_GAP_SECONDS = 90.0
_INTERVAL_HOURS = 0.25
_LOGGER = logging.getLogger(__name__)


class _InfluxClient(Protocol):
    async def query_sql(self, query: str) -> list[dict[str, str]]: ...

    async def write_lines(self, lines: list[str]) -> None: ...


@dataclass(frozen=True, slots=True)
class TariffProfile:
    """Immutable planner-relevant tariff snapshot."""

    profile_id: str
    valid_from_utc: datetime
    import_energy_eur_per_kwh: float
    export_energy_eur_per_kwh: float
    capacity_tariff_eur_per_kw_month: float
    capacity_tariff_floor_kw: float

    def energy_cost_eur(self, import_kwh: float, export_kwh: float) -> float:
        """Return marginal energy cost excluding the capacity-tariff contribution."""
        return (
            max(0.0, import_kwh) * self.import_energy_eur_per_kwh
            - max(0.0, export_kwh) * self.export_energy_eur_per_kwh
        )


@dataclass(frozen=True, slots=True)
class CapacityPeakState:
    """Best available estimate of the current billing month's 15-minute import peak."""

    month_local: str
    observed_peak_kw: float | None
    billing_peak_kw: float
    peak_window_start_local: datetime | None
    peak_source: str | None
    history_complete: bool
    estimated_window_count: int
    live_window_count: int


@dataclass(frozen=True, slots=True)
class CapacityMonthCost:
    """Incremental capacity-tariff exposure for one local calendar month."""

    month_local: str
    observed_peak_kw: float | None
    baseline_billing_peak_kw: float | None
    projected_plan_peak_kw: float
    projected_billing_peak_kw: float | None
    incremental_peak_kw: float | None
    incremental_cost_eur: float | None


@dataclass(frozen=True, slots=True)
class PlanCostEvaluation:
    """Accounting view of one projected plan horizon; not yet the optimizer objective."""

    horizon_hours: int
    import_kwh: float
    export_kwh: float
    import_cost_eur: float
    export_revenue_eur: float
    net_energy_cost_eur: float
    incremental_capacity_cost_eur: float | None
    total_marginal_cost_eur: float | None
    months: tuple[CapacityMonthCost, ...]


class TariffProfileHistory:
    """Activate immutable tariff snapshots without rewriting prior history."""

    def __init__(
        self,
        settings: EconomicsSettings,
        *,
        influx_client: _InfluxClient | None = None,
        local_path: Path = _LOCAL_HISTORY_PATH,
    ) -> None:
        self._settings = settings
        self._influx_client = influx_client
        self._local_path = local_path
        self.backend = "influxdb" if influx_client is not None else "local_jsonl"

    async def activate(self, *, now_utc: datetime | None = None) -> TariffProfile | None:
        """Return the active profile and append a revision only when the configured tariff changed."""
        if not self._settings.configured:
            return None
        observed = (now_utc or datetime.now(UTC)).astimezone(UTC)
        valid_from = self._settings.valid_from_utc or observed
        profile_id = _profile_id(self._settings)
        if self._influx_client is not None:
            try:
                latest = await self._latest_influx_profile()
                if latest is not None and latest.profile_id == profile_id:
                    return latest
                profile = _profile_from_settings(self._settings, profile_id, valid_from)
                await self._write_influx_profile(profile)
                return profile
            except Exception as exc:  # noqa: BLE001 - economics history must not stop the controller.
                _LOGGER.warning("Tariff history InfluxDB persistence failed; using local fallback: %s", exc)
                self.backend = "local_jsonl"
        return self._activate_local(profile_id, valid_from)

    async def _latest_influx_profile(self) -> TariffProfile | None:
        assert self._influx_client is not None
        tables = await self._influx_client.query_sql(
            "SELECT table_name FROM information_schema.tables WHERE table_name = 'tariff_profile' LIMIT 1"
        )
        if not tables:
            return None
        rows = await self._influx_client.query_sql(
            'SELECT time, profile_id, import_energy_eur_per_kwh, export_energy_eur_per_kwh, '
            'capacity_tariff_eur_per_kw_month, capacity_tariff_floor_kw FROM "tariff_profile" '
            "ORDER BY time DESC LIMIT 1"
        )
        if not rows:
            return None
        return _profile_from_record(rows[0])

    async def _write_influx_profile(self, profile: TariffProfile) -> None:
        assert self._influx_client is not None
        fields = (
            f'import_energy_eur_per_kwh={profile.import_energy_eur_per_kwh:.9f},'
            f'export_energy_eur_per_kwh={profile.export_energy_eur_per_kwh:.9f},'
            f'capacity_tariff_eur_per_kw_month={profile.capacity_tariff_eur_per_kw_month:.9f},'
            f'capacity_tariff_floor_kw={profile.capacity_tariff_floor_kw:.6f},'
            f'cost_model_version="{COST_MODEL_VERSION}"'
        )
        line = f"tariff_profile,profile_id={profile.profile_id} {fields} {_timestamp_ns(profile.valid_from_utc)}"
        await self._influx_client.write_lines([line])

    def _activate_local(self, profile_id: str, observed: datetime) -> TariffProfile:
        records = _read_local_records(self._local_path)
        if records:
            try:
                latest = _profile_from_record(records[-1])
            except (KeyError, TypeError, ValueError):
                latest = None
            if latest is not None and latest.profile_id == profile_id:
                return latest
        profile = _profile_from_settings(self._settings, profile_id, observed)
        self._local_path.parent.mkdir(parents=True, exist_ok=True)
        with self._local_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(_profile_record(profile), sort_keys=True) + "\n")
        return profile


class CapacityPeakTracker:
    """Track the current monthly quarter-hour import peak using history plus live samples."""

    def __init__(
        self,
        client: HomeAssistantClient,
        *,
        floor_kw: float,
        grid_import_entity_id: str | None,
        influx_client: _InfluxClient | None = None,
    ) -> None:
        self._client = client
        self._floor_kw = floor_kw
        self._grid_import_entity_id = grid_import_entity_id
        self._influx_client = influx_client
        self._month_local: str | None = None
        self._local_tz: tzinfo | None = None
        self._peak_w: float | None = None
        self._peak_window_start_utc: datetime | None = None
        self._peak_source: str | None = None
        self._history_complete = False
        self._estimated_window_count = 0
        self._live_window_count = 0
        self._window_start_utc: datetime | None = None
        self._window_energy_ws = 0.0
        self._window_coverage_seconds = 0.0
        self._last_observed_utc: datetime | None = None
        self._last_power_w: float | None = None

    @property
    def state(self) -> CapacityPeakState | None:
        """Return the current month state after the tracker has been initialized."""
        if self._month_local is None or self._local_tz is None:
            return None
        peak_local = (
            self._peak_window_start_utc.astimezone(self._local_tz)
            if self._peak_window_start_utc is not None
            else None
        )
        observed_kw = None if self._peak_w is None else self._peak_w / 1000.0
        return CapacityPeakState(
            month_local=self._month_local,
            observed_peak_kw=observed_kw,
            billing_peak_kw=max(self._floor_kw, observed_kw or 0.0),
            peak_window_start_local=peak_local,
            peak_source=self._peak_source,
            history_complete=self._history_complete,
            estimated_window_count=self._estimated_window_count,
            live_window_count=self._live_window_count,
        )

    async def observe(self, power_w: float, *, now_utc: datetime, local_tz: tzinfo) -> CapacityPeakState:
        """Add one live grid-import observation and finalize complete quarter-hour windows."""
        if now_utc.tzinfo is None:
            raise ValueError("now_utc must be timezone-aware")
        now = now_utc.astimezone(UTC)
        await self._ensure_month(now, local_tz)
        power = max(0.0, float(power_w))
        if self._last_observed_utc is None or self._window_start_utc is None:
            self._window_start_utc = _quarter_start_utc(now)
            self._last_observed_utc = now
            self._last_power_w = power
            await self._publish_status()
            assert self.state is not None
            return self.state

        if now <= self._last_observed_utc:
            self._last_observed_utc = now
            self._last_power_w = power
            assert self.state is not None
            return self.state

        gap_seconds = (now - self._last_observed_utc).total_seconds()
        if gap_seconds <= _MAX_LIVE_SAMPLE_GAP_SECONDS:
            await self._integrate_until(now)
        else:
            await self._advance_across_gap(now)
        self._last_observed_utc = now
        self._last_power_w = power
        assert self.state is not None
        return self.state

    async def _ensure_month(self, now_utc: datetime, local_tz: tzinfo) -> None:
        month_start_utc, next_month_utc, month_key = _month_bounds_utc(now_utc, local_tz)
        if self._month_local == month_key:
            return
        self._month_local = month_key
        self._local_tz = local_tz
        self._peak_w = None
        self._peak_window_start_utc = None
        self._peak_source = None
        self._history_complete = False
        self._estimated_window_count = 0
        self._live_window_count = 0
        self._window_start_utc = _quarter_start_utc(now_utc)
        self._window_energy_ws = 0.0
        self._window_coverage_seconds = 0.0
        self._last_observed_utc = None
        self._last_power_w = None
        if self._influx_client is not None and self._grid_import_entity_id is not None:
            try:
                await self._seed_from_influx(month_start_utc, min(now_utc, next_month_utc))
            except Exception as exc:  # noqa: BLE001 - peak accounting must not stop Energy Manager.
                _LOGGER.warning("Capacity-peak history seed failed; continuing with live-only tracking: %s", exc)
        await self._publish_status()

    async def _seed_from_influx(self, month_start_utc: datetime, now_utc: datetime) -> None:
        assert self._influx_client is not None
        cutoff = _quarter_start_utc(now_utc)
        if cutoff <= month_start_utc:
            return
        exact: dict[datetime, float] = {}
        if await _table_exists(self._influx_client, "capacity_peak_window"):
            query = (
                'SELECT time, average_import_w FROM "capacity_peak_window" '
                f"WHERE time >= '{month_start_utc.isoformat()}' AND time < '{cutoff.isoformat()}' ORDER BY time ASC"
            )
            for row in await self._influx_client.query_sql(query):
                try:
                    exact[_parse_timestamp(row["time"])] = max(0.0, float(row["average_import_w"]))
                except (KeyError, TypeError, ValueError):
                    _LOGGER.warning("Ignoring invalid persisted capacity-peak window")

        legacy_rows: list[tuple[datetime, float]] = []
        if await _table_exists(self._influx_client, "legacy_power_source"):
            entity = _escape_sql_string(self._grid_import_entity_id or "")
            query = (
                'SELECT time, power_w FROM "legacy_power_source" '
                f"WHERE signal = 'grid_import' AND entity_id = '{entity}' "
                f"AND time >= '{month_start_utc.isoformat()}' AND time < '{cutoff.isoformat()}' ORDER BY time ASC"
            )
            for row in await self._influx_client.query_sql(query):
                try:
                    legacy_rows.append((_parse_timestamp(row["time"]), max(0.0, float(row["power_w"]))))
                except (KeyError, TypeError, ValueError):
                    _LOGGER.warning("Ignoring invalid legacy grid-import row for capacity peak")

        legacy_buckets: dict[datetime, list[float]] = {}
        for observed, power in legacy_rows:
            legacy_buckets.setdefault(_quarter_start_utc(observed), []).append(power)
        estimated = {
            start: sum(values) / len(values)
            for start, values in legacy_buckets.items()
            if len(values) >= 2 and start not in exact
        }
        self._live_window_count = len(exact)
        self._estimated_window_count = len(estimated)
        for start, value in estimated.items():
            self._consider_peak(value, start, "legacy_5min_estimate")
        for start, value in exact.items():
            self._consider_peak(value, start, "live_high_resolution")

        expected_windows = max(0, int((cutoff - month_start_utc) / _CAPACITY_WINDOW))
        exact_complete = expected_windows > 0 and len(exact) >= expected_windows
        legacy_complete = False
        if legacy_rows:
            first = legacy_rows[0][0]
            last = legacy_rows[-1][0]
            legacy_complete = (
                first <= month_start_utc + timedelta(minutes=10)
                and last >= cutoff - timedelta(minutes=10)
            )
        self._history_complete = exact_complete or legacy_complete

    async def _integrate_until(self, now_utc: datetime) -> None:
        assert self._last_observed_utc is not None
        assert self._last_power_w is not None
        assert self._window_start_utc is not None
        cursor = self._last_observed_utc
        while cursor < now_utc:
            window_end = self._window_start_utc + _CAPACITY_WINDOW
            if cursor >= window_end:
                await self._finalize_window()
                self._window_start_utc = window_end
                continue
            segment_end = min(now_utc, window_end)
            seconds = max(0.0, (segment_end - cursor).total_seconds())
            self._window_energy_ws += self._last_power_w * seconds
            self._window_coverage_seconds += seconds
            cursor = segment_end
            if cursor >= window_end:
                await self._finalize_window()
                self._window_start_utc = window_end

    async def _advance_across_gap(self, now_utc: datetime) -> None:
        assert self._window_start_utc is not None
        while self._window_start_utc + _CAPACITY_WINDOW <= now_utc:
            await self._finalize_window()
            self._window_start_utc += _CAPACITY_WINDOW
        if _quarter_start_utc(now_utc) != self._window_start_utc:
            self._window_start_utc = _quarter_start_utc(now_utc)
            self._window_energy_ws = 0.0
            self._window_coverage_seconds = 0.0

    async def _finalize_window(self) -> None:
        assert self._window_start_utc is not None
        if self._window_coverage_seconds >= _MIN_LIVE_COVERAGE_SECONDS:
            average_w = self._window_energy_ws / self._window_coverage_seconds
            self._consider_peak(average_w, self._window_start_utc, "live_high_resolution")
            self._live_window_count += 1
            await self._persist_live_window(average_w, self._window_start_utc, self._window_coverage_seconds)
        self._window_energy_ws = 0.0
        self._window_coverage_seconds = 0.0
        await self._publish_status()

    async def _persist_live_window(self, average_w: float, start_utc: datetime, coverage_seconds: float) -> None:
        if self._influx_client is None:
            return
        fields = (
            f"average_import_w={average_w:.6f},coverage_seconds={coverage_seconds:.3f},"
            f'model_version="{CAPACITY_PEAK_VERSION}"'
        )
        line = f"capacity_peak_window,source=live_high_resolution {fields} {_timestamp_ns(start_utc)}"
        try:
            await self._influx_client.write_lines([line])
        except Exception as exc:  # noqa: BLE001 - persistence failure must not stop tracking.
            _LOGGER.warning("Could not persist capacity-peak window: %s", exc)

    def _consider_peak(self, power_w: float, start_utc: datetime, source: str) -> None:
        if self._peak_w is None or power_w > self._peak_w:
            self._peak_w = power_w
            self._peak_window_start_utc = start_utc
            self._peak_source = source

    async def _publish_status(self) -> None:
        state = self.state
        if state is None:
            return
        attributes: dict[str, object] = {
            "friendly_name": "Energy Manager Capacity Tariff Status",
            "capacity_peak_version": CAPACITY_PEAK_VERSION,
            "month_local": state.month_local,
            "observed_peak_kw": _round_optional(state.observed_peak_kw, 3),
            "billing_peak_kw": round(state.billing_peak_kw, 3),
            "floor_kw": round(self._floor_kw, 3),
            "peak_window_start_local": (
                state.peak_window_start_local.isoformat() if state.peak_window_start_local is not None else None
            ),
            "peak_source": state.peak_source,
            "history_complete": state.history_complete,
            "estimated_5min_windows": state.estimated_window_count,
            "live_high_resolution_windows": state.live_window_count,
            "unit_of_measurement": "kW",
            "last_update_utc": datetime.now(UTC).isoformat(),
        }
        entity_state: str | float = (
            "learning" if state.observed_peak_kw is None else round(state.observed_peak_kw, 3)
        )
        await self._client.set_state(CAPACITY_STATUS_ENTITY, entity_state, attributes)


class EconomicsService:
    """Own the active tariff, capacity state and read-only plan cost accounting."""

    def __init__(
        self,
        settings: EconomicsSettings,
        client: HomeAssistantClient,
        *,
        grid_import_entity_id: str | None = None,
        influx_client: _InfluxClient | None = None,
        local_path: Path = _LOCAL_HISTORY_PATH,
    ) -> None:
        self._settings = settings
        self._client = client
        self._grid_import_entity_id = grid_import_entity_id
        self._influx_client = influx_client
        self._history = TariffProfileHistory(settings, influx_client=influx_client, local_path=local_path)
        self.current_profile: TariffProfile | None = None
        self._capacity_tracker: CapacityPeakTracker | None = None

    @property
    def capacity_state(self) -> CapacityPeakState | None:
        """Expose current capacity state for diagnostics and plan evaluation."""
        return self._capacity_tracker.state if self._capacity_tracker is not None else None

    async def initialize(self) -> TariffProfile | None:
        """Activate the configured tariff revision and publish its diagnostic state."""
        self.current_profile = await self._history.activate()
        if not self._settings.enabled:
            await self._client.set_state(
                ECONOMICS_STATUS_ENTITY,
                "disabled",
                {
                    "friendly_name": "Energy Manager Economics Status",
                    "cost_model_version": COST_MODEL_VERSION,
                    "history_backend": self._history.backend,
                    "last_update_utc": datetime.now(UTC).isoformat(),
                },
            )
            return None
        if self.current_profile is None:
            await self._client.set_state(
                ECONOMICS_STATUS_ENTITY,
                "not_configured",
                {
                    "friendly_name": "Energy Manager Economics Status",
                    "cost_model_version": COST_MODEL_VERSION,
                    "history_backend": self._history.backend,
                    "last_update_utc": datetime.now(UTC).isoformat(),
                },
            )
            return None
        profile = self.current_profile
        self._capacity_tracker = CapacityPeakTracker(
            self._client,
            floor_kw=profile.capacity_tariff_floor_kw,
            grid_import_entity_id=self._grid_import_entity_id,
            influx_client=self._influx_client,
        )
        await self._client.set_state(
            ECONOMICS_STATUS_ENTITY,
            "ready",
            {
                "friendly_name": "Energy Manager Economics Status",
                "cost_model_version": COST_MODEL_VERSION,
                "profile_id": profile.profile_id,
                "valid_from_utc": profile.valid_from_utc.isoformat(),
                "history_backend": self._history.backend,
                "import_energy_eur_per_kwh": profile.import_energy_eur_per_kwh,
                "export_energy_eur_per_kwh": profile.export_energy_eur_per_kwh,
                "capacity_tariff_eur_per_kw_month": profile.capacity_tariff_eur_per_kw_month,
                "capacity_tariff_floor_kw": profile.capacity_tariff_floor_kw,
                "last_update_utc": datetime.now(UTC).isoformat(),
            },
        )
        _LOGGER.info(
            "Economic profile active: id=%s, import=%.5f EUR/kWh, export=%.5f EUR/kWh, "
            "capacity=%.5f EUR/kW/month, floor=%.2f kW, history=%s",
            profile.profile_id,
            profile.import_energy_eur_per_kwh,
            profile.export_energy_eur_per_kwh,
            profile.capacity_tariff_eur_per_kw_month,
            profile.capacity_tariff_floor_kw,
            self._history.backend,
        )
        return profile

    async def observe_house_state(self, house_state: HouseState, *, now_utc: datetime, local_tz: tzinfo) -> None:
        """Feed live grid import into quarter-hour capacity accounting."""
        if self._capacity_tracker is None:
            return
        value = house_state.value("grid.import_power")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return
        await self._capacity_tracker.observe(float(value), now_utc=now_utc, local_tz=local_tz)

    async def publish_plan_cost(self, plan: ShadowPlan, *, local_tz: tzinfo) -> PlanCostEvaluation | None:
        """Evaluate and publish the current plan without changing any planner decision."""
        profile = self.current_profile
        capacity_state = self.capacity_state
        if profile is None:
            return None
        evaluation_24 = evaluate_plan_cost(plan, profile, capacity_state, hours=24)
        evaluation_48 = evaluate_plan_cost(plan, profile, capacity_state, hours=48)
        if evaluation_24 is None:
            await self._client.set_state(
                PLAN_COST_STATUS_ENTITY,
                "unavailable",
                {
                    "friendly_name": "Energy Manager Plan Cost Status",
                    "plan_cost_version": PLAN_COST_VERSION,
                    "profile_id": profile.profile_id,
                    "reason": "grid_projection_unavailable",
                    "last_update_utc": datetime.now(UTC).isoformat(),
                },
            )
            return None
        attributes = {
            "friendly_name": "Energy Manager Plan Cost Status",
            "plan_cost_version": PLAN_COST_VERSION,
            "cost_model_version": COST_MODEL_VERSION,
            "profile_id": profile.profile_id,
            "tariff_valid_from_utc": profile.valid_from_utc.isoformat(),
            "accounting_only": True,
            "optimizer_objective_ready": False,
            "optimizer_blocker": "terminal_ess_value_not_modelled",
            "next_24_hours": _evaluation_attributes(evaluation_24),
            "next_48_hours": _evaluation_attributes(evaluation_48) if evaluation_48 is not None else None,
            "last_update_utc": datetime.now(UTC).isoformat(),
        }
        if capacity_state is not None:
            attributes["capacity_state"] = {
                "month_local": capacity_state.month_local,
                "observed_peak_kw": _round_optional(capacity_state.observed_peak_kw, 3),
                "billing_peak_kw": round(capacity_state.billing_peak_kw, 3),
                "history_complete": capacity_state.history_complete,
                "peak_source": capacity_state.peak_source,
            }
        state: str | float
        if evaluation_24.total_marginal_cost_eur is None:
            state = "partial"
        else:
            state = round(evaluation_24.total_marginal_cost_eur, 3)
            attributes["unit_of_measurement"] = "EUR"
        await self._client.set_state(PLAN_COST_STATUS_ENTITY, state, attributes)
        return evaluation_24


def evaluate_plan_cost(
    plan: ShadowPlan,
    profile: TariffProfile,
    capacity_state: CapacityPeakState | None,
    *,
    hours: int,
) -> PlanCostEvaluation | None:
    """Return marginal cash-flow accounting for the selected projected plan horizon."""
    count = min(len(plan.intervals), max(0, hours * 4))
    intervals = plan.intervals[:count]
    if not intervals or any(item.grid_power_after_ess_w is None for item in intervals):
        return None
    grid_values = [float(item.grid_power_after_ess_w) for item in intervals]
    import_kwh = sum(max(0.0, value) for value in grid_values) * _INTERVAL_HOURS / 1000.0
    export_kwh = sum(max(0.0, -value) for value in grid_values) * _INTERVAL_HOURS / 1000.0
    import_cost = import_kwh * profile.import_energy_eur_per_kwh
    export_revenue = export_kwh * profile.export_energy_eur_per_kwh
    energy_cost = import_cost - export_revenue

    month_peaks: dict[str, float] = {}
    for item, grid_w in zip(intervals, grid_values, strict=True):
        month = item.period_start_local.strftime("%Y-%m")
        month_peaks[month] = max(month_peaks.get(month, 0.0), max(0.0, grid_w) / 1000.0)
    month_costs: list[CapacityMonthCost] = []
    capacity_total = 0.0
    capacity_known = True
    for month in sorted(month_peaks):
        projected_peak = month_peaks[month]
        observed_peak: float | None
        if capacity_state is not None and month == capacity_state.month_local:
            observed_peak = capacity_state.observed_peak_kw
            known = capacity_state.history_complete and observed_peak is not None
        elif capacity_state is not None and month > capacity_state.month_local:
            observed_peak = 0.0
            known = True
        else:
            observed_peak = None
            known = False
        if known and observed_peak is not None:
            baseline = max(profile.capacity_tariff_floor_kw, observed_peak)
            projected_billing = max(baseline, projected_peak)
            incremental_kw = max(0.0, projected_billing - baseline)
            incremental_cost = incremental_kw * profile.capacity_tariff_eur_per_kw_month
            capacity_total += incremental_cost
        else:
            baseline = None
            projected_billing = None
            incremental_kw = None
            incremental_cost = None
            capacity_known = False
        month_costs.append(
            CapacityMonthCost(
                month_local=month,
                observed_peak_kw=observed_peak,
                baseline_billing_peak_kw=baseline,
                projected_plan_peak_kw=projected_peak,
                projected_billing_peak_kw=projected_billing,
                incremental_peak_kw=incremental_kw,
                incremental_cost_eur=incremental_cost,
            )
        )
    capacity_cost = capacity_total if capacity_known else None
    total = energy_cost + capacity_total if capacity_known else None
    return PlanCostEvaluation(
        horizon_hours=hours,
        import_kwh=import_kwh,
        export_kwh=export_kwh,
        import_cost_eur=import_cost,
        export_revenue_eur=export_revenue,
        net_energy_cost_eur=energy_cost,
        incremental_capacity_cost_eur=capacity_cost,
        total_marginal_cost_eur=total,
        months=tuple(month_costs),
    )


def _evaluation_attributes(evaluation: PlanCostEvaluation) -> dict[str, object]:
    return {
        "hours": evaluation.horizon_hours,
        "import_kwh": round(evaluation.import_kwh, 3),
        "export_kwh": round(evaluation.export_kwh, 3),
        "import_cost_eur": round(evaluation.import_cost_eur, 3),
        "export_revenue_eur": round(evaluation.export_revenue_eur, 3),
        "net_energy_cost_eur": round(evaluation.net_energy_cost_eur, 3),
        "incremental_capacity_cost_eur": _round_optional(evaluation.incremental_capacity_cost_eur, 3),
        "total_marginal_cost_eur": _round_optional(evaluation.total_marginal_cost_eur, 3),
        "months": [
            {
                "month": item.month_local,
                "observed_peak_kw": _round_optional(item.observed_peak_kw, 3),
                "baseline_billing_peak_kw": _round_optional(item.baseline_billing_peak_kw, 3),
                "projected_plan_peak_kw": round(item.projected_plan_peak_kw, 3),
                "projected_billing_peak_kw": _round_optional(item.projected_billing_peak_kw, 3),
                "incremental_peak_kw": _round_optional(item.incremental_peak_kw, 3),
                "incremental_cost_eur": _round_optional(item.incremental_cost_eur, 3),
            }
            for item in evaluation.months
        ],
    }


def _profile_id(settings: EconomicsSettings) -> str:
    payload = {
        "cost_model_version": COST_MODEL_VERSION,
        "capacity_tariff_eur_per_kw_month": settings.capacity_tariff_eur_per_kw_month,
        "capacity_tariff_floor_kw": settings.capacity_tariff_floor_kw,
        "export_energy_eur_per_kwh": settings.export_energy_eur_per_kwh,
        "import_energy_eur_per_kwh": settings.import_energy_eur_per_kwh,
        "valid_from_utc": settings.valid_from_utc.isoformat() if settings.valid_from_utc is not None else None,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _profile_from_settings(settings: EconomicsSettings, profile_id: str, valid_from: datetime) -> TariffProfile:
    assert settings.import_energy_eur_per_kwh is not None
    assert settings.export_energy_eur_per_kwh is not None
    assert settings.capacity_tariff_eur_per_kw_month is not None
    return TariffProfile(
        profile_id=profile_id,
        valid_from_utc=valid_from.astimezone(UTC),
        import_energy_eur_per_kwh=settings.import_energy_eur_per_kwh,
        export_energy_eur_per_kwh=settings.export_energy_eur_per_kwh,
        capacity_tariff_eur_per_kw_month=settings.capacity_tariff_eur_per_kw_month,
        capacity_tariff_floor_kw=settings.capacity_tariff_floor_kw,
    )


def _profile_record(profile: TariffProfile) -> dict[str, str | float]:
    return {
        "profile_id": profile.profile_id,
        "valid_from_utc": profile.valid_from_utc.isoformat(),
        "import_energy_eur_per_kwh": profile.import_energy_eur_per_kwh,
        "export_energy_eur_per_kwh": profile.export_energy_eur_per_kwh,
        "capacity_tariff_eur_per_kw_month": profile.capacity_tariff_eur_per_kw_month,
        "capacity_tariff_floor_kw": profile.capacity_tariff_floor_kw,
        "cost_model_version": COST_MODEL_VERSION,
    }


def _profile_from_record(record: dict[str, str | float]) -> TariffProfile:
    valid_from = record.get("valid_from_utc", record.get("time"))
    if valid_from is None:
        raise KeyError("valid_from_utc")
    return TariffProfile(
        profile_id=str(record["profile_id"]),
        valid_from_utc=_parse_timestamp(str(valid_from)),
        import_energy_eur_per_kwh=float(record["import_energy_eur_per_kwh"]),
        export_energy_eur_per_kwh=float(record["export_energy_eur_per_kwh"]),
        capacity_tariff_eur_per_kw_month=float(record["capacity_tariff_eur_per_kw_month"]),
        capacity_tariff_floor_kw=float(record["capacity_tariff_floor_kw"]),
    )


def _read_local_records(path: Path) -> list[dict[str, str | float]]:
    if not path.exists():
        return []
    records: list[dict[str, str | float]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        _LOGGER.warning("Could not read tariff profile history %s: %s", path, exc)
        return []
    for line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            _LOGGER.warning("Ignoring invalid tariff profile history row")
            continue
        if isinstance(value, dict):
            records.append(value)
    return records


async def _table_exists(client: _InfluxClient, table_name: str) -> bool:
    table = _escape_sql_string(table_name)
    rows = await client.query_sql(
        "SELECT table_name FROM information_schema.tables "
        f"WHERE table_name = '{table}' LIMIT 1"
    )
    return bool(rows)


def _month_bounds_utc(value_utc: datetime, local_tz: tzinfo) -> tuple[datetime, datetime, str]:
    local = value_utc.astimezone(local_tz)
    start_local = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start_local.month == 12:
        next_local = start_local.replace(year=start_local.year + 1, month=1)
    else:
        next_local = start_local.replace(month=start_local.month + 1)
    return start_local.astimezone(UTC), next_local.astimezone(UTC), f"{start_local.year:04d}-{start_local.month:02d}"


def _quarter_start_utc(value: datetime) -> datetime:
    utc = value.astimezone(UTC)
    minute = utc.minute - utc.minute % 15
    return utc.replace(minute=minute, second=0, microsecond=0)


def _parse_timestamp(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _timestamp_ns(value: datetime) -> int:
    utc = value.astimezone(UTC)
    return int(utc.timestamp()) * 1_000_000_000 + utc.microsecond * 1000


def _escape_sql_string(value: str) -> str:
    return value.replace("'", "''")


def _round_optional(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)
