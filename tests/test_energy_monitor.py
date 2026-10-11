"""Optional dashboard counters must not affect energy-control decisions."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from energymanager.config import MonitoringSettings, Settings
from energymanager.energy_monitor import EnergyMonitor
from energymanager.house_state import HouseState


def test_monitoring_options_roundtrip(tmp_path):
    path = tmp_path / 'options.json'
    path.write_text(json.dumps({'monitoring': {
        'grid_import_energy_entity': 'sensor.grid_import_today',
        'pv_ac_counter_cumulative': True,
        'quarter_hour_average_entity': 'sensor.p1_average',
    }}), encoding='utf-8')
    settings = Settings.load(path)
    assert settings.monitoring.grid_import_energy_entity == 'sensor.grid_import_today'
    assert settings.monitoring.pv_ac_counter_cumulative is True
    assert settings.as_options()['monitoring']['quarter_hour_average_entity'] == 'sensor.p1_average'


@pytest.mark.asyncio
async def test_daily_energy_and_peak_conversion(monkeypatch, tmp_path):
    monkeypatch.setattr('energymanager.energy_monitor._STORAGE', tmp_path / 'cache.json')
    client = AsyncMock()
    client.get_state.side_effect = lambda entity: {
        'sensor.energy': {'state': '3500', 'attributes': {'unit_of_measurement': 'Wh'}},
        'sensor.peak': {'state': '2800', 'attributes': {'unit_of_measurement': 'W'}},
    }[entity]
    monitor = EnergyMonitor(client, MonitoringSettings(
        grid_import_energy_entity='sensor.energy', monthly_peak_entity='sensor.peak'))
    await monitor.update(HouseState())
    values = {call.args[0]: call.args[1] for call in client.set_state.await_args_list}
    assert values['sensor.energy_manager_grid_import_energy_today'] == 3.5
    assert values['sensor.energy_manager_monthly_peak_kw'] == 2.8
    assert values['sensor.energy_manager_quarter_hour_average_kw'] == 'unavailable'
