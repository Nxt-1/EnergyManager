from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from energymanager.task_diagnostics import publish_task_status
from energymanager.tasks import PlanningTask


class FakeHomeAssistantClient:
    def __init__(self) -> None:
        self.states: dict[str, dict[str, Any]] = {}

    async def set_state(self, entity_id: str, state: str | int | float, attributes: dict[str, Any]) -> None:
        self.states[entity_id] = {"state": str(state), "attributes": attributes}


def test_task_diagnostics_label_minimum_and_preferred_targets() -> None:
    now = datetime(2026, 10, 10, 12, 30, tzinfo=UTC)
    task = PlanningTask(
        task_id="ev_charge",
        kind="energy_by_deadline",
        source="ev_minimum_by_departure_with_preferred_soc",
        actuator_id="ev",
        status="ready",
        planning_available=True,
        earliest_start_local=now,
        latest_end_local=now,
        required_energy_kwh=8.84,
        battery_energy_required_kwh=7.956,
        interruptible=True,
        current_soc_percent=32.0,
        minimum_soc_percent=50.0,
        target_soc_percent=80.0,
        preferred_energy_kwh=24.96,
        preferred_battery_energy_kwh=22.464,
        feasible_at_max_power=True,
        minimum_runtime_hours=0.801,
    )
    client = FakeHomeAssistantClient()

    asyncio.run(publish_task_status(client, (task,)))

    state = client.states["sensor.energy_manager_task_status"]
    item = state["attributes"]["tasks"][0]
    assert state["state"] == "ready"
    assert item["minimum_soc_percent"] == 50.0
    assert item["preferred_soc_percent"] == 80.0
    assert item["target_soc_percent"] == 80.0
    assert item["target_soc_percent_role"] == "preferred"
    assert item["required_energy_kwh"] == 8.84
    assert item["preferred_energy_kwh"] == 24.96
    assert item["required_energy_role"] == "hard_by_deadline"
    assert item["preferred_energy_role"] == "soft_over_planning_horizon"
