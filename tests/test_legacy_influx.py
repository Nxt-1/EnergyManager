from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from energymanager.config import (
    EssSettings,
    EvSettings,
    GridSettings,
    LegacyInfluxSettings,
    PvSettings,
    Settings,
)
from energymanager.legacy_influx import (
    LegacyInfluxBackfill,
    LegacySeries,
    _legacy_entity_candidates,
    _missing_coverage_ranges,
    _normalize_source_values,
    _power_scale,
    _reconstruct_rows,
    _series_measurement,
)


def test_legacy_series_helpers_match_home_assistant_schema() -> None:
    assert _legacy_entity_candidates("sensor.grid_import") == ("grid_import", "sensor.grid_import")
    assert _series_measurement(r"W,domain=sensor,entity_id=grid_import") == "W"
    assert _series_measurement(r"power\,watts,entity_id=test") == "power,watts"
    assert _power_scale("W") == 1.0
    assert _power_scale("kW") == 1000.0
    assert _power_scale("kWh") is None


def test_reconstruct_rows_uses_canonical_power_balance_and_ev_subtraction() -> None:
    start = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
    values = {
        "grid_import": {start: 1500.0},
        "grid_export": {start: 0.0},
        "ess": {start: -500.0},
        "solax": {start: 2000.0},
        "ev": {start: 1400.0},
    }

    rows, house_rows, background_rows, skipped_rows = _reconstruct_rows(
        values,
        start_utc=start,
        end_utc=start + timedelta(minutes=5),
        ev_configured=True,
    )

    assert rows == [(start, 3000.0, 1400.0, 1600.0)]
    assert house_rows == 1
    assert background_rows == 1
    assert skipped_rows == 0


def test_reconstruct_rows_uses_already_normalized_ess_and_ev_sources() -> None:
    start = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
    values = {
        "grid_import": {start: 1000.0},
        "grid_export": {start: 0.0},
        "ess": {start: -500.0},
        "solax": {start: 500.0},
        "ev": {start: 0.0},
    }

    rows, _, background_rows, _ = _reconstruct_rows(
        values,
        start_utc=start,
        end_utc=start + timedelta(minutes=5),
        ev_configured=True,
    )

    assert rows == [(start, 1000.0, 0.0, 1000.0)]
    assert background_rows == 1


def test_reconstruct_rows_does_not_guess_missing_required_source() -> None:
    start = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
    values = {
        "grid_import": {start: 1000.0},
        "grid_export": {start: 0.0},
        "ess": {},
        "solax": {start: 500.0},
    }

    rows, house_rows, background_rows, skipped_rows = _reconstruct_rows(
        values,
        start_utc=start,
        end_utc=start + timedelta(minutes=5),
        ev_configured=False,
    )

    assert rows == []
    assert house_rows == 0
    assert background_rows == 0
    assert skipped_rows == 1


def test_source_normalization_canonicalizes_ess_and_ev_noise() -> None:
    start = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
    values = {start: 500.0, start + timedelta(minutes=5): -20.0}
    assert _normalize_source_values("ess", values, "charge") == [
        (start, -500.0),
        (start + timedelta(minutes=5), 20.0),
    ]
    assert _normalize_source_values("ev", values, "discharge") == [
        (start, 500.0),
        (start + timedelta(minutes=5), 0.0),
    ]


def test_missing_coverage_ranges_only_returns_new_prefix_or_tail() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 2, 1, tzinfo=UTC)
    state = {
        "source_start_utc": datetime(2026, 1, 5, tzinfo=UTC).isoformat(),
        "source_end_utc": datetime(2026, 1, 25, tzinfo=UTC).isoformat(),
    }
    assert _missing_coverage_ranges(state, start, end) == [
        (start, datetime(2026, 1, 5, tzinfo=UTC)),
        (datetime(2026, 1, 25, tzinfo=UTC), end),
    ]


def test_reconstruct_rows_carries_sparse_zero_states_across_long_gaps() -> None:
    start = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
    values = {
        "grid_import": {
            start: 1000.0,
            start + timedelta(minutes=5): 1000.0,
            start + timedelta(minutes=10): 1000.0,
            start + timedelta(minutes=15): 1000.0,
            start + timedelta(minutes=20): 1000.0,
        },
        "grid_export": {start: 0.0},
        "ess": {start: 0.0},
        "solax": {start: 0.0},
        "ev": {start: 0.0},
    }

    rows, house_rows, background_rows, skipped_rows = _reconstruct_rows(
        values,
        start_utc=start,
        end_utc=start + timedelta(minutes=25),
        ev_configured=True,
    )

    assert house_rows == 5
    assert background_rows == 5
    assert skipped_rows == 0
    assert all(row[1:] == (1000.0, 0.0, 1000.0) for row in rows)


def test_reconstruct_rows_rejects_stale_material_nonzero_state() -> None:
    start = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
    timeline = {
        start + timedelta(minutes=offset): 0.0
        for offset in range(0, 25, 5)
    }
    values = {
        "grid_import": {start: 1000.0},
        "grid_export": timeline,
        "ess": timeline,
        "solax": timeline,
    }

    rows, house_rows, background_rows, skipped_rows = _reconstruct_rows(
        values,
        start_utc=start,
        end_utc=start + timedelta(minutes=25),
        ev_configured=False,
    )

    assert house_rows == 4
    assert background_rows == 4
    assert skipped_rows == 1
    assert rows[-1][0] == start + timedelta(minutes=15)

def test_reconstruct_rows_treats_stale_ev_as_idle_after_freshness_window() -> None:
    start = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
    timeline = {
        start + timedelta(minutes=offset): 2000.0
        for offset in range(0, 30, 5)
    }
    zeros = {
        start + timedelta(minutes=offset): 0.0
        for offset in range(0, 30, 5)
    }
    values = {
        "grid_import": timeline,
        "grid_export": zeros,
        "ess": zeros,
        "solax": zeros,
        "ev": {start: 1400.0},
    }

    rows, house_rows, background_rows, skipped_rows = _reconstruct_rows(
        values,
        start_utc=start,
        end_utc=start + timedelta(minutes=30),
        ev_configured=True,
    )

    assert house_rows == 6
    assert background_rows == 6
    assert skipped_rows == 0
    assert rows[3][1:] == (2000.0, 1400.0, 600.0)
    assert rows[4][1:] == (2000.0, 0.0, 2000.0)
    assert rows[5][1:] == (2000.0, 0.0, 2000.0)

def test_reconstruct_rows_uses_seed_before_range_boundary() -> None:
    start = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
    seed = start - timedelta(minutes=30)
    values = {
        "grid_import": {start: 500.0},
        "grid_export": {seed: 0.0},
        "ess": {seed: 0.0},
        "solax": {seed: 0.0},
        "ev": {seed: 0.0},
    }

    rows, house_rows, background_rows, skipped_rows = _reconstruct_rows(
        values,
        start_utc=start,
        end_utc=start + timedelta(minutes=5),
        ev_configured=True,
    )

    assert rows == [(start, 500.0, 0.0, 500.0)]
    assert house_rows == 1
    assert background_rows == 1
    assert skipped_rows == 0


class FakeLegacySource:
    def __init__(self, start: datetime, end: datetime) -> None:
        self.start = start
        self.end = end
        self.pinged = False
        self.read_calls: list[str] = []

    async def ping(self) -> None:
        self.pinged = True

    async def discover_power_series(self, entity_id: str) -> LegacySeries:
        return LegacySeries(entity_id, entity_id.split(".", 1)[1], "W", 1.0, self.start, self.end)

    async def read_five_minute_power(
        self,
        series: LegacySeries,
        start_utc: datetime,
        end_utc: datetime,
    ) -> dict[datetime, float]:
        self.read_calls.append(series.entity_id)
        value = {
            "sensor.grid_import": 1000.0,
            "sensor.grid_export": 0.0,
            "sensor.ess": 0.0,
            "sensor.solax": 500.0,
            "sensor.ev": 200.0,
        }[series.entity_id]
        points: dict[datetime, float] = {}
        cursor = start_utc
        while cursor < end_utc:
            points[cursor] = value
            cursor += timedelta(minutes=5)
        return points


class FakeTargetStore:
    def __init__(self) -> None:
        self.source_state: dict[tuple[str, str, str], dict[str, str]] = {}
        self.source_rows: dict[tuple[str, str], dict[datetime, float]] = {}
        self.derivation_state: dict[tuple[str, str], dict[str, str]] = {}
        self.rows: list[tuple[datetime, float | None, float | None, float | None]] = []

    async def load_legacy_source_state(
        self,
        *,
        signal: str,
        entity_id: str,
        normalization_version: str,
    ) -> dict[str, str] | None:
        return self.source_state.get((signal, entity_id, normalization_version))

    async def record_legacy_source_state(self, **kwargs: object) -> None:
        key = (str(kwargs["signal"]), str(kwargs["entity_id"]), str(kwargs["normalization_version"]))
        self.source_state[key] = {
            "source_start_utc": str(kwargs["source_start_utc"]),
            "source_end_utc": str(kwargs["source_end_utc"]),
            "rows": str(kwargs["rows"]),
        }

    async def record_legacy_power_source_batch(
        self,
        *,
        signal: str,
        entity_id: str,
        rows: list[tuple[datetime, float]],
    ) -> None:
        values = self.source_rows.setdefault((signal, entity_id), {})
        values.update(rows)

    async def load_legacy_power_source(
        self,
        *,
        signal: str,
        entity_id: str,
        start_utc: datetime,
        end_utc: datetime,
    ) -> dict[datetime, float]:
        values = self.source_rows.get((signal, entity_id), {})
        return {time: value for time, value in values.items() if start_utc <= time < end_utc}

    async def load_legacy_power_source_seed(
        self,
        *,
        signal: str,
        entity_id: str,
        before_utc: datetime,
    ) -> tuple[datetime, float] | None:
        values = self.source_rows.get((signal, entity_id), {})
        candidates = [(time, value) for time, value in values.items() if time < before_utc]
        return max(candidates, default=None, key=lambda item: item[0])

    async def load_legacy_derivation_state(
        self,
        derivation_id: str,
        fingerprint: str,
    ) -> dict[str, str] | None:
        return self.derivation_state.get((derivation_id, fingerprint))

    async def record_legacy_derivation_state(self, **kwargs: object) -> None:
        key = (str(kwargs["derivation_id"]), str(kwargs["fingerprint"]))
        self.derivation_state[key] = {
            "source_start_utc": str(kwargs["source_start_utc"]),
            "source_end_utc": str(kwargs["source_end_utc"]),
            "house_rows": str(kwargs["house_rows"]),
            "background_rows": str(kwargs["background_rows"]),
            "skipped_rows": str(kwargs["skipped_rows"]),
        }

    async def record_legacy_house_load_batch(
        self,
        rows: list[tuple[datetime, float | None, float | None, float | None]],
    ) -> None:
        self.rows.extend(rows)


def _settings() -> Settings:
    return Settings(
        grid=GridSettings("sensor.grid_import", "sensor.grid_export"),
        ess=EssSettings(power_entity="sensor.ess", power_positive_means="discharge"),
        pv=PvSettings(solax_power_entity="sensor.solax"),
        ev=EvSettings(charging_power_entity="sensor.ev"),
        legacy_influx=LegacyInfluxSettings(backfill_enabled=True, url="http://legacy:8086"),
    )


def test_backfill_is_incremental_per_source_and_does_not_repeat_completed_coverage() -> None:
    start = datetime(2026, 9, 1, 10, 1, tzinfo=UTC)
    end = datetime(2026, 9, 1, 10, 31, tzinfo=UTC)
    source = FakeLegacySource(start, end)
    target = FakeTargetStore()
    backfill = LegacyInfluxBackfill(_settings(), source, target)  # type: ignore[arg-type]

    first = asyncio.run(backfill.run())
    calls_after_first = len(source.read_calls)
    second = asyncio.run(backfill.run())

    assert source.pinged is True
    assert first.status == "updated"
    assert first.sources_updated == 5
    assert first.source_rows == 25
    assert first.house_rows == 5
    assert first.background_rows == 5
    assert target.rows[0][1:] == (1500.0, 200.0, 1300.0)
    assert second.status == "up_to_date"
    assert len(source.read_calls) == calls_after_first
    assert len(target.rows) == 5


def test_backfill_imports_only_new_tail_when_legacy_history_grows() -> None:
    start = datetime(2026, 9, 1, 10, 1, tzinfo=UTC)
    source = FakeLegacySource(start, datetime(2026, 9, 1, 10, 31, tzinfo=UTC))
    target = FakeTargetStore()
    backfill = LegacyInfluxBackfill(_settings(), source, target)  # type: ignore[arg-type]
    asyncio.run(backfill.run())

    source.end = datetime(2026, 9, 1, 10, 46, tzinfo=UTC)
    result = asyncio.run(backfill.run())

    assert result.status == "updated"
    assert result.sources_updated == 5
    assert result.source_rows == 15
    assert result.house_rows == 3
    assert result.background_rows == 3
