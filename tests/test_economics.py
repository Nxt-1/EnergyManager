from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from energymanager.config import EconomicsSettings
from energymanager.economics import EconomicsService, TariffProfileHistory


class FakeHomeAssistantClient:
    def __init__(self) -> None:
        self.states: dict[str, dict[str, Any]] = {}

    async def set_state(self, entity_id: str, state: str | int | float, attributes: dict[str, Any]) -> None:
        self.states[entity_id] = {"state": str(state), "attributes": attributes}


class FakeInfluxClient:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.profile_rows: list[dict[str, str]] = []

    async def query_sql(self, query: str) -> list[dict[str, str]]:
        if "information_schema.tables" in query:
            return [{"table_name": "tariff_profile"}] if self.profile_rows else []
        if 'FROM "tariff_profile"' in query:
            return self.profile_rows[-1:] if self.profile_rows else []
        return []

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


def test_influx_history_writes_profile_with_activation_timestamp(tmp_path: Path) -> None:
    client = FakeInfluxClient()
    observed = datetime(2026, 10, 7, 19, 30, tzinfo=UTC)
    history = TariffProfileHistory(_settings(), influx_client=client, local_path=tmp_path / "fallback.jsonl")

    profile = asyncio.run(history.activate(now_utc=observed))

    assert profile is not None
    assert len(client.lines) == 1
    assert client.lines[0].startswith(f"tariff_profile,profile_id={profile.profile_id} ")
    assert f" {int(observed.timestamp()) * 1_000_000_000}" in client.lines[0]
    assert "import_energy_eur_per_kwh=0.250000000" in client.lines[0]



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
