"""Full-horizon MILP plan exports for the Home Assistant dashboard."""

from datetime import UTC, datetime, timedelta

import pytest

from energymanager.database import EnergyManagerStore
from energymanager.diagnostics import DiagnosticsPublisher
from energymanager.planner import EnergyPlan, PlanInterval


class RecordingClient:
    def __init__(self):
        self.states = {}
        self.writes = []

    async def set_state(self, entity_id, value, attributes):
        self.states[entity_id] = (value, attributes)

    async def write_lines(self, lines):
        self.writes.extend(lines)


def make_plan():
    start = datetime(2026, 10, 10, 18, 0, tzinfo=UTC)
    intervals = tuple(
        PlanInterval(
            period_start_local=start + timedelta(minutes=15 * index),
            background_load_w=400,
            scheduled_load_w=100,
            pv_ac_power_w=200,
            pv_dc_power_w=50,
            pv_power_w=250,
            net_power_before_control_w=250,
            ess_ac_power_w=150,
            grid_power_after_ess_w=100,
            projected_soc_percent=60,
            projected_ev_soc_percent=80,
        )
        for index in range(672)
    )
    return EnergyPlan(generated_at_utc=start, intervals=intervals)


@pytest.mark.asyncio
async def test_full_plan_is_split_into_seven_daily_ha_entities():
    client = RecordingClient()
    await DiagnosticsPublisher(client).publish_plan(make_plan())
    all_starts = []
    for day in range(1, 8):
        count, attrs = client.states[f"sensor.energy_manager_plan_day_{day}"]
        assert count == 96
        assert attrs["interval_count"] == 96
        assert attrs["intervals"][0]["grid_w"] == 100
        assert attrs["intervals"][0]["background_w"] == 400
        assert attrs["intervals"][0]["ev_w"] == 100
        assert attrs["intervals"][0]["load_w"] == 500
        all_starts.extend(slot["start"] for slot in attrs["intervals"])
    assert len(all_starts) == len(set(all_starts)) == 672


@pytest.mark.asyncio
async def test_full_plan_is_archived_with_distinct_timestamps_and_revision_id():
    client = RecordingClient()
    store = EnergyManagerStore(client)
    plan = make_plan()
    await store.record_milp_plan(plan)
    assert len(client.writes) == 672
    assert all("issued_at_utc=" in line for line in client.writes)
    assert "ess_soc_percent=60.000" in client.writes[0]
    assert "grid_after_ess_w=100.000" in client.writes[-1]
    assert len({line.rsplit(" ", 1)[-1] for line in client.writes}) == 672


@pytest.mark.asyncio
async def test_plan_timeline_exports_contiguous_ev_charging_segments():
    client = RecordingClient()
    plan = make_plan()
    await DiagnosticsPublisher(client).publish_plan(plan)
    state, attributes = client.states["sensor.energy_manager_plan_timeline"]
    assert state == 1
    assert attributes["segments"][0]["name"] == "EV"
    assert attributes["segments"][0]["energy_kwh"] == 16.8
    assert attributes["segments"][0]["peak_power_w"] == 100
    assert attributes["segments"][0]["start"] == plan.intervals[0].period_start_local.isoformat()
