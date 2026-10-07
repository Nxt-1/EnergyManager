from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import energymanager.database as database_module
from energymanager.database import EnergyManagerStore


class FakeInfluxClient:
    def __init__(self) -> None:
        self.database = "energy_manager"
        self.lines: list[str] = []
        self.queries: list[str] = []
        self.query_rows: list[dict[str, str]] = []
        self.table_rows: dict[str, list[dict[str, str]]] = {}
        self.pinged = False

    async def ping(self) -> None:
        self.pinged = True

    async def write_lines(self, lines: list[str]) -> None:
        self.lines.extend(lines)

    async def query_sql(self, query: str) -> list[dict[str, str]]:
        self.queries.append(query)
        if "information_schema.tables" in query:
            for table in self.table_rows:
                if f"table_name = '{table}'" in query:
                    return [{"table_name": table}]
            return []
        for table, rows in self.table_rows.items():
            if f'FROM "{table}"' in query:
                return rows
        return self.query_rows


def test_house_load_is_written_as_line_protocol() -> None:
    client = FakeInfluxClient()
    store = EnergyManagerStore(client)  # type: ignore[arg-type]
    observed = datetime(2026, 10, 4, 10, 0, tzinfo=UTC)

    asyncio.run(
        store.record_house_load(
            observed_at_utc=observed,
            house_load_power_w=2200.0,
            known_controllable_load_power_w=1400.0,
            background_load_power_w=800.0,
        )
    )

    assert len(client.lines) == 1
    assert client.lines[0].startswith("house_load background_load_power_w=800.000000")
    assert "house_load_power_w=2200.000000" in client.lines[0]
    assert "known_controllable_load_power_w=1400.000000" in client.lines[0]


def test_legacy_house_load_is_written_to_separate_table() -> None:
    client = FakeInfluxClient()
    store = EnergyManagerStore(client)  # type: ignore[arg-type]
    observed = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)

    asyncio.run(store.record_legacy_house_load_batch([(observed, 1000.0, 0.0, 1000.0)]))

    assert len(client.lines) == 1
    assert client.lines[0].startswith("legacy_house_load_v2 background_load_power_w=1000.000000")


def test_background_training_window_combines_legacy_and_live_history() -> None:
    client = FakeInfluxClient()
    client.table_rows = {
        "legacy_house_load": [
            {"time": "2026-10-04T08:00:00Z", "background_load_power_w": "750.5"},
            {"time": "2026-10-04T08:05:00Z", "background_load_power_w": "800"},
        ],
        "house_load": [
            {"time": "2026-10-04T08:05:00Z", "background_load_power_w": "810"},
            {"time": "2026-10-04T08:10:00Z", "background_load_power_w": "900"},
        ],
    }
    store = EnergyManagerStore(client)  # type: ignore[arg-type]

    samples = asyncio.run(store.load_background_samples(days=35))

    assert [sample.power_w for sample in samples] == [750.5, 810.0, 900.0]
    assert any("INTERVAL '35 days'" in query for query in client.queries)


def test_legacy_background_history_migrates_once(tmp_path: Path, monkeypatch) -> None:
    history = tmp_path / "background_load_history.jsonl"
    history.write_text(
        json.dumps({"observed_at_utc": "2026-10-04T08:00:00+00:00", "power_w": 725.0}) + "\n",
        encoding="utf-8",
    )
    pv_archive = tmp_path / "pv_forecast_revisions.jsonl"
    load_archive = tmp_path / "background_load_forecast_revisions.jsonl"
    monkeypatch.setattr(database_module, "_LEGACY_LOAD_HISTORY", history)
    monkeypatch.setattr(database_module, "_LEGACY_PV_ARCHIVE", pv_archive)
    monkeypatch.setattr(database_module, "_LEGACY_LOAD_ARCHIVE", load_archive)

    client = FakeInfluxClient()
    store = EnergyManagerStore(client)  # type: ignore[arg-type]

    migrated = asyncio.run(store.initialize())

    assert client.pinged is True
    assert migrated == (0, 1, 0)
    assert not history.exists()
    assert (tmp_path / "background_load_history.jsonl.migrated").exists()
    assert any("background_load_power_w=725.000000" in line for line in client.lines)


def test_background_backtest_is_written_as_line_protocol() -> None:
    from energymanager.load_backtest import BackgroundLoadBacktest, BacktestMetric, ErrorBreakdown

    client = FakeInfluxClient()
    store = EnergyManagerStore(client)  # type: ignore[arg-type]
    generated = datetime(2026, 10, 5, 20, 0, tzinfo=UTC)
    metric = BacktestMetric(
        model="energy_manager",
        horizon_hours=24,
        total_energy_mae_kwh=1.25,
        energy_bias_kwh=-0.25,
        timing_mismatch_kwh=3.75,
        peak_underprediction_w=450.0,
        p90_peak_underprediction_w=900.0,
        mae_w=321.0,
        bias_w=-45.0,
        p90_abs_error_w=800.0,
        points=100,
        issue_count=10,
        coverage=0.9,
        issue_coverage=0.8,
    )
    result = BackgroundLoadBacktest(
        generated_at_utc=generated,
        evaluation_start_local=datetime(2026, 9, 10, 0, 0, tzinfo=UTC),
        evaluation_end_local=datetime(2026, 10, 1, 0, 0, tzinfo=UTC),
        issue_count=10,
        metrics=(metric,),
        best_by_horizon={24: "energy_manager"},
        best_power_by_horizon={24: "energy_manager"},
        daypart_breakdown={"night": ErrorBreakdown(100.0, 0.0, 200.0, 25)},
        daytype_breakdown={"weekday": ErrorBreakdown(100.0, 0.0, 200.0, 25)},
    )

    asyncio.run(store.record_background_backtest(result))

    assert len(client.lines) == 1
    assert client.lines[0].startswith("background_load_backtest,model=energy_manager,horizon_h=24")
    assert "mae_w=321.000000" in client.lines[0]
    assert "total_energy_mae_kwh=1.250000" in client.lines[0]
    assert "energy_bias_kwh=-0.250000" in client.lines[0]
    assert "timing_mismatch_kwh=3.750000" in client.lines[0]
    assert "peak_underprediction_w=450.000000" in client.lines[0]
    assert "p90_peak_underprediction_w=900.000000" in client.lines[0]
    assert "issue_coverage=0.800000" in client.lines[0]
