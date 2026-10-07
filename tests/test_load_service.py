from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from energymanager.diagnostics import (
    BACKGROUND_LOAD_BACKTEST_ENTITY,
    BACKGROUND_LOAD_FORECAST_NEXT_7_DAYS_ENTITY,
    BACKGROUND_LOAD_FORECAST_NEXT_24_HOURS_ENTITY,
    BACKGROUND_LOAD_FORECAST_NEXT_HOUR_ENTITY,
    BACKGROUND_LOAD_FORECAST_STATUS_ENTITY,
)
from energymanager.house_state import HouseState
from energymanager.load_service import (
    BackgroundLoadForecastArchive,
    BackgroundLoadHistory,
    BackgroundLoadService,
)


class FakeHomeAssistantClient:
    def __init__(self) -> None:
        self.states: dict[str, dict[str, Any]] = {}

    async def set_state(self, entity_id: str, state: str | int | float, attributes: dict[str, Any]) -> None:
        self.states[entity_id] = {"state": str(state), "attributes": attributes}


def _house_state(background_power_w: float) -> HouseState:
    state = HouseState()
    now = datetime(2026, 10, 4, 10, 0, tzinfo=UTC)
    values = {
        "grid.import_power": 1200.0,
        "grid.export_power": 0.0,
        "pv.solax_power": 600.0,
        "ess.power": -300.0,
        "ev.charging_power": 0.0,
    }
    # Desired background = grid + PV + ESS = 1500 W. Adjust grid to requested value.
    values["grid.import_power"] += background_power_w - 1500.0
    for key, value in values.items():
        reading = state.ensure_input(key, f"sensor.{key.replace('.', '_')}")
        reading.set_valid(value, unit="W", observed_at_utc=now, source_last_updated=None)
    return state


def test_history_persists_and_reloads(tmp_path: Path) -> None:
    path = tmp_path / "history.jsonl"
    history = BackgroundLoadHistory(path)
    sample = datetime(2026, 10, 4, 10, 0, tzinfo=UTC)
    from energymanager.load_forecast import LoadSample

    history.record(LoadSample(sample, 850.0))

    loaded = BackgroundLoadHistory(path)
    assert len(loaded.samples) == 1
    assert loaded.samples[0].power_w == 850.0


def test_service_samples_only_every_five_minutes_and_publishes_forecast(tmp_path: Path) -> None:
    client = FakeHomeAssistantClient()
    history = BackgroundLoadHistory(tmp_path / "history.jsonl")
    archive_path = tmp_path / "revisions.jsonl"
    service = BackgroundLoadService(
        client,  # type: ignore[arg-type]
        history=history,
        archive=BackgroundLoadForecastArchive(archive_path),
    )
    state = _house_state(900.0)
    start = datetime(2026, 10, 4, 10, 0, tzinfo=UTC)

    async def run() -> None:
        await service.update_from_house_state(state, now_utc=start)
        await service.update_from_house_state(state, now_utc=start + timedelta(minutes=2))
        await service.update_from_house_state(state, now_utc=start + timedelta(minutes=5))

    asyncio.run(run())
    assert len(history.samples) == 2
    assert client.states[BACKGROUND_LOAD_FORECAST_STATUS_ENTITY]["state"] == "learning"
    assert client.states[BACKGROUND_LOAD_BACKTEST_ENTITY]["state"] == "unavailable"
    assert float(client.states[BACKGROUND_LOAD_FORECAST_NEXT_HOUR_ENTITY]["state"]) == 900.0
    assert float(client.states[BACKGROUND_LOAD_FORECAST_NEXT_24_HOURS_ENTITY]["state"]) == 21.6
    week = client.states[BACKGROUND_LOAD_FORECAST_NEXT_7_DAYS_ENTITY]
    assert week["attributes"]["days_available"] == 7
    assert len(week["attributes"]["days"]) == 7
    records = [json.loads(line) for line in archive_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["model_version"] == "2026-10-04-baseline"
