from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from energymanager.actuators import EssCapabilities
from energymanager.config import EconomicsSettings
from energymanager.economics import (
    CapacityPeakState,
    CapacityPeakTracker,
    EconomicsService,
    TariffProfile,
    TariffProfileHistory,
    evaluate_plan_cost,
    evaluate_plan_objective,
)
from energymanager.planner import ShadowPlan, ShadowPlanInterval


class FakeHomeAssistantClient:
    def __init__(self) -> None:
        self.states: dict[str, dict[str, Any]] = {}

    async def set_state(self, entity_id: str, state: str | int | float, attributes: dict[str, Any]) -> None:
        self.states[entity_id] = {"state": str(state), "attributes": attributes}


class FakeInfluxClient:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.profile_rows: list[dict[str, str | None]] = []

    async def query_sql(self, query: str) -> list[dict[str, str | None]]:
        if "information_schema.tables" in query:
            return [{"table_name": "tariff_profile"}] if self.profile_rows else []
        if 'FROM "tariff_profile"' not in query:
            return []
        rows = list(self.profile_rows)
        if "WHERE profile_id = '" in query:
            profile_id = query.split("WHERE profile_id = '", 1)[1].split("'", 1)[0]
            rows = [row for row in rows if row.get("profile_id") == profile_id]
        rows.sort(key=lambda row: str(row.get("time", "")))
        if "ORDER BY time DESC" in query:
            rows.reverse()
        if "LIMIT 1" in query:
            rows = rows[:1]
        return rows

    async def write_lines(self, lines: list[str]) -> None:
        self.lines.extend(lines)


def _settings(import_price: float = 0.25, valid_from_utc: datetime | None = None) -> EconomicsSettings:
    return EconomicsSettings(
        enabled=True,
        import_energy_eur_per_kwh=import_price,
        export_energy_eur_per_kwh=0.03,
        capacity_tariff_eur_per_kw_month=4.50,
        capacity_tariff_floor_kw=2.5,
        valid_from_utc=valid_from_utc,
    )


def test_local_history_does_not_duplicate_unchanged_tariff(tmp_path: Path) -> None:
    path = tmp_path / "tariffs.jsonl"
    first = datetime(2026, 10, 7, 18, 0, tzinfo=UTC)
    history = TariffProfileHistory(_settings(), local_path=path)

    profile_a = asyncio.run(history.activate(now_utc=first))
    profile_b = asyncio.run(history.activate(now_utc=first + timedelta(hours=1)))

    assert profile_a is not None
    assert profile_b == profile_a
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1


def test_local_history_appends_changed_tariff(tmp_path: Path) -> None:
    path = tmp_path / "tariffs.jsonl"
    first = datetime(2026, 10, 7, 18, 0, tzinfo=UTC)
    second = first + timedelta(days=90)

    profile_a = asyncio.run(TariffProfileHistory(_settings(0.25), local_path=path).activate(now_utc=first))
    profile_b = asyncio.run(TariffProfileHistory(_settings(0.31), local_path=path).activate(now_utc=second))

    assert profile_a is not None and profile_b is not None
    assert profile_a.profile_id != profile_b.profile_id
    assert profile_b.valid_from_utc == second
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 2
    assert records[0]["import_energy_eur_per_kwh"] == pytest.approx(0.25)
    assert records[1]["import_energy_eur_per_kwh"] == pytest.approx(0.31)


def test_influx_history_records_activation_time_separately_from_effective_date(tmp_path: Path) -> None:
    client = FakeInfluxClient()
    effective = datetime(2026, 9, 30, 22, 0, tzinfo=UTC)
    observed = datetime(2026, 10, 7, 19, 30, tzinfo=UTC)
    history = TariffProfileHistory(
        _settings(valid_from_utc=effective),
        influx_client=client,
        local_path=tmp_path / "fallback.jsonl",
    )

    profile = asyncio.run(history.activate(now_utc=observed))

    assert profile is not None
    assert profile.valid_from_utc == effective
    assert profile.recorded_at_utc == observed
    assert len(client.lines) == 1
    assert client.lines[0].startswith(f"tariff_profile,profile_id={profile.profile_id} ")
    assert f'valid_from_utc="{effective.isoformat()}"' in client.lines[0]
    assert client.lines[0].endswith(f" {int(observed.timestamp()) * 1_000_000_000}")


def test_explicit_valid_from_is_used_instead_of_activation_time(tmp_path: Path) -> None:
    effective = datetime(2026, 9, 30, 22, 0, tzinfo=UTC)
    observed = datetime(2026, 10, 7, 20, 0, tzinfo=UTC)
    history = TariffProfileHistory(_settings(valid_from_utc=effective), local_path=tmp_path / "tariffs.jsonl")

    profile = asyncio.run(history.activate(now_utc=observed))

    assert profile is not None
    assert profile.valid_from_utc == effective


def test_effective_timestamp_is_part_of_profile_identity(tmp_path: Path) -> None:
    path = tmp_path / "tariffs.jsonl"
    first = datetime(2026, 9, 30, 22, 0, tzinfo=UTC)
    second = datetime(2027, 1, 1, 0, 0, tzinfo=UTC)

    profile_a = asyncio.run(TariffProfileHistory(_settings(valid_from_utc=first), local_path=path).activate())
    profile_b = asyncio.run(TariffProfileHistory(_settings(valid_from_utc=second), local_path=path).activate())

    assert profile_a is not None and profile_b is not None
    assert profile_a.profile_id != profile_b.profile_id
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


class FakeLegacySchemaInfluxClient(FakeInfluxClient):
    async def query_sql(self, query: str) -> list[dict[str, str | None]]:
        if 'FROM "tariff_profile"' in query and ("valid_from_utc" in query or "supersedes_profile_id" in query):
            raise RuntimeError("column not found")
        return await super().query_sql(query)


def test_backdated_profile_migrates_from_legacy_influx_schema(tmp_path: Path) -> None:
    client = FakeLegacySchemaInfluxClient()
    old_observed = datetime(2026, 10, 7, 20, 36, 57, tzinfo=UTC)
    client.profile_rows.append(
        {
            "time": old_observed.isoformat(),
            "profile_id": "legacy",
            "import_energy_eur_per_kwh": "0.25",
            "export_energy_eur_per_kwh": "0.03",
            "capacity_tariff_eur_per_kw_month": "4.50",
            "capacity_tariff_floor_kw": "2.5",
        }
    )
    effective = datetime(2026, 9, 30, 22, 0, tzinfo=UTC)
    history = TariffProfileHistory(
        _settings(valid_from_utc=effective),
        influx_client=client,
        local_path=tmp_path / "fallback.jsonl",
    )

    profile = asyncio.run(history.activate(now_utc=datetime(2026, 10, 7, 21, 15, tzinfo=UTC)))

    assert profile is not None
    assert profile.valid_from_utc == effective
    assert profile.supersedes_profile_id == "legacy"
    assert history.backend == "influxdb"
    assert len(client.lines) == 1


def test_backdated_explicit_profile_supersedes_activation_fallback_in_influx(tmp_path: Path) -> None:
    client = FakeInfluxClient()
    old_observed = datetime(2026, 10, 7, 20, 36, 57, tzinfo=UTC)
    old_history = TariffProfileHistory(
        _settings(),
        influx_client=client,
        local_path=tmp_path / "fallback.jsonl",
    )
    old_profile = asyncio.run(old_history.activate(now_utc=old_observed))
    assert old_profile is not None
    client.profile_rows.append(
        {
            "time": old_observed.isoformat(),
            "profile_id": old_profile.profile_id,
            "valid_from_utc": None,
            "supersedes_profile_id": None,
            "import_energy_eur_per_kwh": "0.25",
            "export_energy_eur_per_kwh": "0.03",
            "capacity_tariff_eur_per_kw_month": "4.50",
            "capacity_tariff_floor_kw": "2.5",
        }
    )

    effective = datetime(2026, 9, 30, 22, 0, tzinfo=UTC)
    corrected_at = datetime(2026, 10, 7, 21, 15, tzinfo=UTC)
    corrected_history = TariffProfileHistory(
        _settings(valid_from_utc=effective),
        influx_client=client,
        local_path=tmp_path / "fallback.jsonl",
    )
    corrected = asyncio.run(corrected_history.activate(now_utc=corrected_at))

    assert corrected is not None
    assert corrected.valid_from_utc == effective
    assert corrected.supersedes_profile_id == old_profile.profile_id
    assert f'supersedes_profile_id="{old_profile.profile_id}"' in client.lines[-1]


def test_profile_at_ignores_superseded_activation_fallback(tmp_path: Path) -> None:
    client = FakeInfluxClient()
    old_id = "oldactivation"
    corrected_id = "corrected"
    client.profile_rows.extend(
        [
            {
                "time": "2026-10-07T20:36:57+00:00",
                "profile_id": old_id,
                "valid_from_utc": None,
                "supersedes_profile_id": None,
                "import_energy_eur_per_kwh": "0.25",
                "export_energy_eur_per_kwh": "0.03",
                "capacity_tariff_eur_per_kw_month": "4.50",
                "capacity_tariff_floor_kw": "2.5",
            },
            {
                "time": "2026-10-07T21:15:00+00:00",
                "profile_id": corrected_id,
                "valid_from_utc": "2026-09-30T22:00:00+00:00",
                "supersedes_profile_id": old_id,
                "import_energy_eur_per_kwh": "0.25",
                "export_energy_eur_per_kwh": "0.03",
                "capacity_tariff_eur_per_kw_month": "4.50",
                "capacity_tariff_floor_kw": "2.5",
            },
        ]
    )
    history = TariffProfileHistory(
        _settings(valid_from_utc=datetime(2026, 9, 30, 22, 0, tzinfo=UTC)),
        influx_client=client,
        local_path=tmp_path / "fallback.jsonl",
    )

    profile = asyncio.run(history.profile_at(datetime(2026, 10, 8, 12, 0, tzinfo=UTC)))

    assert profile is not None
    assert profile.profile_id == corrected_id
    assert profile.valid_from_utc == datetime(2026, 9, 30, 22, 0, tzinfo=UTC)


def test_profile_at_keeps_later_real_tariff_change_after_corrected_history(tmp_path: Path) -> None:
    path = tmp_path / "tariffs.jsonl"
    records = [
        {
            "profile_id": "corrected_october",
            "valid_from_utc": "2026-09-30T22:00:00+00:00",
            "recorded_at_utc": "2026-10-07T21:15:00+00:00",
            "supersedes_profile_id": "oldactivation",
            "import_energy_eur_per_kwh": 0.25,
            "export_energy_eur_per_kwh": 0.03,
            "capacity_tariff_eur_per_kw_month": 4.50,
            "capacity_tariff_floor_kw": 2.5,
        },
        {
            "profile_id": "january",
            "valid_from_utc": "2027-01-01T00:00:00+00:00",
            "recorded_at_utc": "2026-12-20T12:00:00+00:00",
            "supersedes_profile_id": None,
            "import_energy_eur_per_kwh": 0.31,
            "export_energy_eur_per_kwh": 0.04,
            "capacity_tariff_eur_per_kw_month": 4.70,
            "capacity_tariff_floor_kw": 2.5,
        },
    ]
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
    history = TariffProfileHistory(_settings(), local_path=path)

    october = asyncio.run(history.profile_at(datetime(2026, 10, 15, tzinfo=UTC)))
    january = asyncio.run(history.profile_at(datetime(2027, 1, 15, tzinfo=UTC)))

    assert october is not None and october.profile_id == "corrected_october"
    assert january is not None and january.profile_id == "january"


def test_energy_cost_treats_export_as_revenue(tmp_path: Path) -> None:
    profile = asyncio.run(
        TariffProfileHistory(_settings(), local_path=tmp_path / "tariffs.jsonl").activate(
            now_utc=datetime(2026, 10, 7, 18, 0, tzinfo=UTC)
        )
    )
    assert profile is not None
    assert profile.energy_cost_eur(10.0, 2.0) == pytest.approx(2.44)


def test_economics_service_publishes_versioned_profile(tmp_path: Path) -> None:
    client = FakeHomeAssistantClient()
    service = EconomicsService(_settings(), client, local_path=tmp_path / "tariffs.jsonl")  # type: ignore[arg-type]

    profile = asyncio.run(service.initialize())

    assert profile is not None
    state = client.states["sensor.energy_manager_economics_status"]
    assert state["state"] == "ready"
    assert state["attributes"]["profile_id"] == profile.profile_id
    assert state["attributes"]["history_backend"] == "local_jsonl"


_LOCAL = ZoneInfo("Europe/Brussels")


class FakeCapacityInfluxClient:
    def __init__(self, legacy_rows: list[dict[str, str]] | None = None) -> None:
        self.legacy_rows = legacy_rows or []
        self.lines: list[str] = []

    async def query_sql(self, query: str) -> list[dict[str, str]]:
        if "information_schema.tables" in query:
            if "legacy_power_source" in query and self.legacy_rows:
                return [{"table_name": "legacy_power_source"}]
            if "capacity_peak_window" in query:
                return []
            return []
        if 'FROM "legacy_power_source"' in query:
            return self.legacy_rows
        return []

    async def write_lines(self, lines: list[str]) -> None:
        self.lines.extend(lines)


@dataclass(frozen=True)


class FakePlanInterval:
    period_start_local: datetime
    grid_power_after_ess_w: float | None


@dataclass(frozen=True)


class FakePlan:
    intervals: tuple[FakePlanInterval, ...]


def _profile() -> TariffProfile:
    return TariffProfile(
        profile_id="test",
        valid_from_utc=datetime(2026, 9, 30, 22, 0, tzinfo=UTC),
        import_energy_eur_per_kwh=0.30,
        export_energy_eur_per_kwh=0.04,
        capacity_tariff_eur_per_kw_month=4.50,
        capacity_tariff_floor_kw=2.5,
    )


def _capacity_state(*, peak_kw: float = 6.0, complete: bool = True) -> CapacityPeakState:
    return CapacityPeakState(
        month_local="2026-10",
        observed_peak_kw=peak_kw,
        billing_peak_kw=max(2.5, peak_kw),
        peak_window_start_local=datetime(2026, 10, 4, 18, 0, tzinfo=_LOCAL),
        peak_source="legacy_5min_estimate",
        history_complete=complete,
        estimated_window_count=100,
        live_window_count=0,
    )


def test_capacity_tracker_seeds_month_peak_from_legacy_history() -> None:
    client = FakeHomeAssistantClient()
    legacy_rows = [
        {"time": "2026-09-30T22:00:00+00:00", "power_w": "1000"},
        {"time": "2026-09-30T22:05:00+00:00", "power_w": "1200"},
        {"time": "2026-10-05T10:00:00+00:00", "power_w": "6000"},
        {"time": "2026-10-05T10:05:00+00:00", "power_w": "7000"},
        {"time": "2026-10-07T20:20:00+00:00", "power_w": "900"},
        {"time": "2026-10-07T20:25:00+00:00", "power_w": "1100"},
    ]
    influx = FakeCapacityInfluxClient(legacy_rows)
    tracker = CapacityPeakTracker(
        client,  # type: ignore[arg-type]
        floor_kw=2.5,
        grid_import_entity_id="sensor.grid_import",
        influx_client=influx,
    )

    state = asyncio.run(
        tracker.observe(
            500.0,
            now_utc=datetime(2026, 10, 7, 20, 30, tzinfo=UTC),
            local_tz=_LOCAL,
        )
    )

    assert state.month_local == "2026-10"
    assert state.observed_peak_kw == pytest.approx(6.5)
    assert state.history_complete is True
    assert state.peak_source == "legacy_5min_estimate"
    assert client.states["sensor.energy_manager_capacity_tariff_status"]["state"] == "6.5"


def test_capacity_tracker_builds_live_quarter_hour_average() -> None:
    client = FakeHomeAssistantClient()
    tracker = CapacityPeakTracker(
        client,  # type: ignore[arg-type]
        floor_kw=2.5,
        grid_import_entity_id="sensor.grid_import",
    )
    start = datetime(2026, 10, 7, 20, 0, tzinfo=UTC)

    async def run() -> CapacityPeakState:
        state = await tracker.observe(4000.0, now_utc=start, local_tz=UTC)
        for step in range(1, 31):
            state = await tracker.observe(
                4000.0,
                now_utc=start + timedelta(seconds=30 * step),
                local_tz=UTC,
            )
        return state

    state = asyncio.run(run())

    assert state.observed_peak_kw == pytest.approx(4.0)
    assert state.live_window_count == 1
    assert state.peak_source == "live_high_resolution"


def test_plan_cost_only_charges_capacity_above_existing_month_peak() -> None:
    start = datetime(2026, 10, 7, 22, 0, tzinfo=_LOCAL)
    plan = FakePlan(
        intervals=(
            FakePlanInterval(start, 8000.0),
            FakePlanInterval(start + timedelta(minutes=15), -2000.0),
            FakePlanInterval(start + timedelta(minutes=30), 0.0),
            FakePlanInterval(start + timedelta(minutes=45), 0.0),
        )
    )

    evaluation = evaluate_plan_cost(plan, _profile(), _capacity_state(peak_kw=6.0), hours=1)  # type: ignore[arg-type]

    assert evaluation is not None
    assert evaluation.import_kwh == pytest.approx(2.0)
    assert evaluation.export_kwh == pytest.approx(0.5)
    assert evaluation.net_energy_cost_eur == pytest.approx(0.58)
    assert evaluation.incremental_capacity_cost_eur == pytest.approx(9.0)
    assert evaluation.total_marginal_cost_eur == pytest.approx(9.58)


def test_plan_cost_does_not_reward_lower_peak_below_already_incurred_peak() -> None:
    start = datetime(2026, 10, 7, 22, 0, tzinfo=_LOCAL)
    plan = FakePlan(tuple(FakePlanInterval(start + timedelta(minutes=15 * index), 5000.0) for index in range(4)))

    evaluation = evaluate_plan_cost(plan, _profile(), _capacity_state(peak_kw=6.0), hours=1)  # type: ignore[arg-type]

    assert evaluation is not None
    assert evaluation.incremental_capacity_cost_eur == pytest.approx(0.0)
    assert evaluation.total_marginal_cost_eur == pytest.approx(evaluation.net_energy_cost_eur)


def test_plan_cost_is_partial_when_current_month_peak_history_is_incomplete() -> None:
    start = datetime(2026, 10, 7, 22, 0, tzinfo=_LOCAL)
    plan = FakePlan(tuple(FakePlanInterval(start + timedelta(minutes=15 * index), 3000.0) for index in range(4)))

    evaluation = evaluate_plan_cost(
        plan, _profile(), _capacity_state(complete=False), hours=1
    )  # type: ignore[arg-type]

    assert evaluation is not None
    assert evaluation.net_energy_cost_eur == pytest.approx(0.9)
    assert evaluation.incremental_capacity_cost_eur is None
    assert evaluation.total_marginal_cost_eur is None


def test_economic_objective_values_terminal_ess_energy_at_avoidable_import_cost() -> None:
    start = datetime(2026, 10, 8, 0, 0, tzinfo=_LOCAL)
    resource = EssCapabilities(
        capacity_kwh=10.0,
        min_soc_percent=10.0,
        max_soc_percent=100.0,
        max_charge_power_w=2000.0,
        max_discharge_power_w=2000.0,
        charge_efficiency=0.95,
        discharge_efficiency=0.90,
    )

    def plan(end_soc: float) -> ShadowPlan:
        intervals = tuple(
            ShadowPlanInterval(
                period_start_local=start + timedelta(minutes=15 * index),
                background_load_w=1000.0,
                scheduled_load_w=0.0,
                pv_ac_power_w=0.0,
                pv_dc_power_w=0.0,
                pv_power_w=0.0,
                net_power_before_control_w=1000.0,
                ess_ac_power_w=0.0,
                battery_energy_delta_kwh=0.0,
                projected_soc_percent=end_soc,
                grid_power_after_ess_w=1000.0,
                curtailed_dc_pv_w=0.0,
            )
            for index in range(4)
        )
        return ShadowPlan(
            generated_at_utc=start.astimezone(UTC),
            intervals=intervals,
            ess_projection_status="projected",
            ess_resource=resource,
            ess_initial_soc_percent=end_soc,
        )

    high = evaluate_plan_objective(plan(50.0), _profile(), _capacity_state(peak_kw=6.0), hours=1)
    low = evaluate_plan_objective(plan(20.0), _profile(), _capacity_state(peak_kw=6.0), hours=1)

    assert high is not None and low is not None
    assert high.terminal_usable_ac_kwh == pytest.approx(3.6)
    assert low.terminal_usable_ac_kwh == pytest.approx(0.9)
    assert high.objective_eur == pytest.approx(low.objective_eur - 0.81)

