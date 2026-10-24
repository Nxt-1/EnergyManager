import assert from 'node:assert/strict';
import test from 'node:test';
import {displaySetting, entityState, powerText, settingLabel, storedSetting, watts}
  from '../src/energymanager/assets/display.js';
import {clockValue, localDateTime, localInstants, monthDays, validLocal}
  from '../src/energymanager/assets/date-time.js';

test('power display preserves signs, missing values and energy units', () => {
  assert.equal(watts(1.68), '1680');
  assert.equal(watts(-1.345), '-1345');
  assert.equal(watts(-0.0001), '0');
  assert.equal(watts(0), '0');
  assert.equal(watts(null), '—');
  assert.equal(watts(undefined), '—');
  assert.equal(watts('unavailable'), '—');
  assert.equal(powerText('Peak 4.25 kW; discharge -2.5kW; energy 3.2 kWh'),
    'Peak 4250 W; discharge -2500 W; energy 3.2 kWh');
  assert.equal(entityState({state: '1.68', unit: 'kW'}), '1680 W');
  assert.equal(entityState({state: '1680', unit: 'W'}), '1680 W');
  assert.equal(entityState({state: 'unavailable', unit: 'kW'}), 'unavailable kW');
});

test('watt settings round-trip power limits and the capacity tariff without changing cost', () => {
  const limit = {kind: 'number', path: 'capabilities.ac_charge_kw', label: 'AC limit (kW)'};
  assert.equal(settingLabel(limit), 'AC limit (W)');
  assert.equal(displaySetting(limit, 2.5), 2500);
  assert.equal(storedSetting(limit, '3100'), 3.1);
  assert.equal(storedSetting(limit, ''), null);
  const tariff = {kind: 'number', path: 'policy.capacity_eur_kw_month', label: 'Capacity tariff (€/kW/month)'};
  assert.equal(settingLabel(tariff), 'Capacity tariff (€/W/month)');
  assert.equal(displaySetting(tariff, 4.254), 0.004254);
  assert.equal(String(displaySetting(tariff, 4.5)), '0.0045');
  assert.equal(storedSetting(tariff, '0.0045'), 4.5);
  assert.equal(storedSetting(limit, '0.1'), 0.0001);
  assert.ok(Math.abs(storedSetting(tariff, '0.004254') - 4.254) < 1e-12);
  assert.ok(Math.abs(displaySetting(tariff, 4.254) * 2500 - 4.254 * 2.5) < 1e-12);
  const energy = {kind: 'number', path: 'capabilities.ev_capacity_kwh', label: 'Capacity (kWh)'};
  assert.equal(displaySetting(energy, 60), 60);
  assert.equal(settingLabel(energy), 'Capacity (kWh)');
});

test('calendar alignment, leap years and invalid dates', () => {
  const february = monthDays(2028, 2);
  assert.equal(february[0], null); // Tuesday 1 February: Monday-first calendar.
  assert.equal(february[1], 1);
  assert.equal(february.filter(day => day !== null).length, 29);
  assert.equal(validLocal('2028-02-29T23:59'), true);
  for (const value of ['2027-02-29T07:00', '2026-10-24T24:00', '', '2026-13-01T12:00'])
    assert.equal(validLocal(value), false, value);
});

test('journey dates use configured timezone, including skipped and repeated DST times', () => {
  const zone = 'Europe/Brussels';
  assert.equal(localDateTime('2026-10-24T05:00:00Z', zone), '2026-10-24T07:00');
  assert.deepEqual(localInstants('2026-10-24T07:00', zone), ['2026-10-24T05:00:00.000Z']);
  assert.deepEqual(localInstants('2026-03-29T02:30', zone), []);
  assert.deepEqual(localInstants('2026-10-25T02:30', zone), [
    '2026-10-25T00:30:00.000Z', '2026-10-25T01:30:00.000Z'
  ]);
  assert.deepEqual(localInstants('2026-10-25T07:00', zone), ['2026-10-25T06:00:00.000Z']);
  assert.deepEqual(localInstants('2026-10-24T07:00', 'Asia/Kolkata'), ['2026-10-24T01:30:00.000Z']);
});

test('clock face selects all 24 hours and exact minutes', () => {
  assert.equal(clockValue(0, -105, 'hour'), 12);
  assert.equal(clockValue(0, -77, 'hour'), 0);
  assert.equal(clockValue(105, 0, 'hour'), 3);
  assert.equal(clockValue(77, 0, 'hour'), 15);
  assert.equal(clockValue(-105, 0, 'hour'), 9);
  const angle = 37 / 60 * Math.PI * 2;
  assert.equal(clockValue(Math.sin(angle) * 100, -Math.cos(angle) * 100, 'minute'), 37);
});
