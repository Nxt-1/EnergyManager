"""Independent, best-effort dashboard energy and P1 peak observations."""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import MonitoringSettings
from .ha_client import HomeAssistantClient
from .house_state import HouseState

_LOGGER = logging.getLogger(__name__)
_STORAGE = Path('/data/dashboard_energy.json')
_CHANNELS = ('grid_import', 'grid_export', 'pv_ac', 'pv_dc', 'house', 'ev', 'ess_charge', 'ess_discharge')
_POWER_KEYS = {
    'grid_import': 'grid.import_power', 'grid_export': 'grid.export_power',
    'pv_ac': 'pv.solax_power', 'pv_dc': 'pv.shed_power', 'ev': 'ev.charging_power',
}


class EnergyMonitor:
    """Publish dashboard counters without affecting the controller or its health."""

    def __init__(self, client: HomeAssistantClient, settings: MonitoringSettings) -> None:
        self.client = client
        self.settings = settings
        try:
            self.cache = json.loads(_STORAGE.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            self.cache = {}

    async def update(self, house: HouseState) -> None:
        now = datetime.now(ZoneInfo('Europe/Brussels'))
        day = now.date().isoformat()
        changed = False
        for channel in _CHANNELS:
            entity = getattr(self.settings, f'{channel}_energy_entity')
            item = self.cache.setdefault(channel, {})
            if item.get('day') != day:
                item.clear()
                item.update(day=day, energy=0.0, last_time=now.isoformat())
                changed = True
            source = 'estimated_from_power'
            value = None
            if entity:
                try:
                    state = await self.client.get_state(entity)
                    raw = float(state['state'])
                    unit = state.get('attributes', {}).get('unit_of_measurement', 'kWh')
                    if math.isfinite(raw) and unit in ('kWh', 'Wh'):
                        reading = raw / (1000 if unit == 'Wh' else 1)
                        if getattr(self.settings, f'{channel}_counter_cumulative'):
                            # First-day baseline is established on the first reading; later baselines survive restarts.
                            if 'baseline' not in item or reading < item['baseline']:
                                item['baseline'] = reading
                                changed = True
                            value = max(0, reading - item['baseline'])
                            source = 'configured_cumulative_counter'
                        else:
                            value = reading
                            source = 'configured_daily_counter'
                except (ValueError, KeyError, OSError, RuntimeError) as exc:
                    _LOGGER.debug('Optional energy input %s unavailable: %s', entity, exc)
            if value is None:
                power = self._power(channel, house)
                before = datetime.fromisoformat(item['last_time'])
                elapsed = max(0, min((now - before).total_seconds(), 90))
                if power is not None and item.get('last_power') is not None:
                    item['energy'] = float(item['energy']) + max(0, float(item['last_power'])) * elapsed / 3_600_000
                    changed = True
                item['last_power'] = power
                value = float(item['energy']) if power is not None else None
            item['last_time'] = now.isoformat()
            attrs = {'friendly_name': f'Energy Manager {channel.replace("_", " ").title()} Today',
                     'unit_of_measurement': 'kWh', 'date': day, 'source': source,
                     'source_entity': entity, 'state_class': 'measurement'}
            await self.client.set_state(f'sensor.energy_manager_{channel}_energy_today',
                                        round(value, 3) if value is not None else 'unavailable', attrs)
        for name, key in (('monthly_peak', 'monthly_peak_entity'),
                          ('quarter_hour_average', 'quarter_hour_average_entity')):
            entity = getattr(self.settings, key)
            value = 'unavailable'
            if entity:
                try:
                    state = await self.client.get_state(entity)
                    numeric = float(state['state'])
                    unit = state.get('attributes', {}).get('unit_of_measurement', 'kW')
                    if math.isfinite(numeric) and unit in ('kW', 'W'):
                        value = round(numeric / (1000 if unit == 'W' else 1), 3)
                except (ValueError, KeyError, OSError, RuntimeError) as exc:
                    _LOGGER.debug('Optional peak input %s unavailable: %s', entity, exc)
            await self.client.set_state(f'sensor.energy_manager_{name}_kw', value,
                                        {'friendly_name': name.replace('_', ' ').title(),
                                         'unit_of_measurement': 'kW', 'source_entity': entity})
        if changed:
            try:
                _STORAGE.write_text(json.dumps(self.cache), encoding='utf-8')
            except OSError as exc:
                _LOGGER.warning('Unable to persist daily energy integration: %s', exc)

    @staticmethod
    def _power(channel: str, house: HouseState) -> float | None:
        if channel == 'house':
            return house.house_load_power_w
        if channel in ('ess_charge', 'ess_discharge'):
            power = house.value('ess.power')
            if not isinstance(power, (int, float)):
                return None
            return max(0.0, -power if channel == 'ess_charge' else power)
        key = _POWER_KEYS.get(channel)
        value = house.value(key) if key else None
        return max(0, float(value)) if isinstance(value, (float, int)) else None
