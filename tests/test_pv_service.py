from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from energymanager.diagnostics import (
    PV_FORECAST_NEXT_7_DAYS_ENTITY,
    PV_FORECAST_STATUS_ENTITY,
    PV_FORECAST_TOMORROW_ENTITY,
)
from energymanager.pv_forecast import PlaneWeatherHour, PlaneWeatherSeries
from energymanager.pv_service import PvForecastArchive, PvForecastService

LOCAL_TZ = ZoneInfo("Europe/Brussels")


class FakeHomeAssistantClient:
    def __init__(self) -> None:
        self.states: dict[str, dict[str, Any]] = {}

    async def get_state(self, entity_id: str) -> dict[str, Any]:
        assert entity_id == "zone.home"
        return {"state": "0", "attributes": {"latitude": 51.2, "longitude": 4.5}}

    async def set_state(self, entity_id: str, state: str | int | float, attributes: dict[str, Any]) -> None:
        self.states[entity_id] = {"state": str(state), "attributes": attributes}


class FakeOpenMeteoClient:
    async def fetch_planes(
        self,
        latitude: float,
        longitude: float,
        planes: tuple[Any, ...],
    ) -> dict[str, PlaneWeatherSeries]:
        assert latitude == 51.2
        assert longitude == 4.5
        start = datetime(2026, 10, 3, 1, 0, tzinfo=LOCAL_TZ)
        hours = []
        for index in range(8 * 24):
            timestamp = start + timedelta(hours=index)
            irradiance = 400.0 if 8 <= timestamp.hour <= 18 else 0.0
            hours.append(
                PlaneWeatherHour(
                    period_end_local=timestamp,
                    global_tilted_irradiance_wm2=irradiance,
                    temperature_c=15.0,
                    cloud_cover_pct=20.0,
                    direct_radiation_wm2=300.0,
                    diffuse_radiation_wm2=100.0,
                )
            )
        return {
            plane.key: PlaneWeatherSeries(plane.key, tuple(hours))
            for plane in planes
        }


def test_service_archives_each_rolling_revision(tmp_path: Path) -> None:
    client = FakeHomeAssistantClient()
    archive_path = tmp_path / "revisions.jsonl"
    service = PvForecastService(
        client,
        FakeOpenMeteoClient(),
        archive=PvForecastArchive(archive_path),
    )  # type: ignore[arg-type]
    now = datetime(2026, 10, 3, 17, 0, tzinfo=LOCAL_TZ)

    asyncio.run(service.update_once(now_local=now))
    asyncio.run(service.update_once(now_local=now + timedelta(minutes=30)))

    records = [json.loads(line) for line in archive_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 2
    assert records[0]["model"] == "knmi_seamless"
    assert records[0]["issued_at_local"].startswith("2026-10-03T17:00")
    assert len(records[0]["daily"]) == 8
    assert records[0]["daily"][1]["target_date"] == "2026-10-04"
    assert records[0]["daily"][1]["total_kwh"] > 0


def test_service_publishes_live_week_forecast_and_status(tmp_path: Path) -> None:
    client = FakeHomeAssistantClient()
    service = PvForecastService(
        client,
        FakeOpenMeteoClient(),
        archive=PvForecastArchive(tmp_path / "revisions.jsonl"),
    )  # type: ignore[arg-type]
    now = datetime(2026, 10, 3, 12, 0, tzinfo=LOCAL_TZ)

    forecast = asyncio.run(service.update_once(now_local=now))

    assert forecast.generated_at_utc.tzinfo == UTC
    assert float(client.states[PV_FORECAST_TOMORROW_ENTITY]["state"]) > 0
    assert client.states[PV_FORECAST_STATUS_ENTITY]["state"] == "connected"
    assert client.states[PV_FORECAST_STATUS_ENTITY]["attributes"]["model_id"] == "knmi_seamless"

    tomorrow = client.states[PV_FORECAST_TOMORROW_ENTITY]["attributes"]
    assert tomorrow["front_kwh"] > 0
    assert tomorrow["rear_kwh"] > 0
    assert tomorrow["shed_kwh"] > 0

    week = client.states[PV_FORECAST_NEXT_7_DAYS_ENTITY]
    assert float(week["state"]) > float(client.states[PV_FORECAST_TOMORROW_ENTITY]["state"])
    assert week["attributes"]["days_available"] == 7
    assert week["attributes"]["complete"] is True
    assert len(week["attributes"]["days"]) == 7
    assert week["attributes"]["days"][0]["date"] == "2026-10-04"
    assert week["attributes"]["days"][-1]["date"] == "2026-10-10"
