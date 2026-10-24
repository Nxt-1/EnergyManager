import assert from 'node:assert/strict';
import test from 'node:test';
import {dailyEnergyRows, connectionIcon, displaySetting, entityState, powerText, settingLabel, storedSetting, watts}
  from '../src/energymanager/assets/display.js';
import {clockValue, localDateTime, localInstants, monthDays, validLocal}
  from '../src/energymanager/assets/date-time.js';
import {eventsOnDay, evSchedule, scheduleDays} from '../src/energymanager/assets/ev-schedule.js';
import {nativeLiveState} from '../src/energymanager/assets/native-live.js';

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

test('EV calendar keeps local days and elapsed time across both clock changes', () => {
  const autumn = scheduleDays(Date.parse('2026-10-24T10:00Z'), Date.parse('2026-10-31T10:00Z'), 'Europe/Brussels');
  assert.equal(autumn.length, 8); // Partial first and last days, seven elapsed days.
  assert.equal(autumn[1].date, '2026-10-25');
  assert.equal((autumn[1].end - autumn[1].start) / 3600000, 25);
  const spring = scheduleDays(Date.parse('2026-03-28T10:00Z'), Date.parse('2026-03-30T10:00Z'), 'Europe/Brussels');
  assert.equal((spring[1].end - spring[1].start) / 3600000, 23);
  const india = scheduleDays(Date.parse('2026-10-24T20:00Z'), Date.parse('2026-10-25T20:00Z'), 'Asia/Kolkata');
  assert.equal(india[0].date, '2026-10-25');
  const midnightShift = scheduleDays(Date.parse('2026-09-06T04:00Z'), Date.parse('2026-09-07T04:00Z'), 'America/Santiago');
  assert.ok(midnightShift.every(day => Number.isFinite(day.start) && day.end > day.start));
});

function syntheticSchedule() {
  return {now: '2026-10-24T10:00Z', revision: 2, ev_plan_valid: true, policy: {timezone: 'Europe/Brussels'},
    schedule_goals: [
      {id: 'overnight', revision: 1, kind: 'trip', title: 'SYNTHETIC overnight',
        deadline: '2026-10-24T20:00Z', return_at: '2026-10-25T08:00Z'},
      {id: 'unknown', revision: 1, kind: 'trip', title: 'SYNTHETIC unknown return',
        deadline: '2026-10-26T06:00Z', return_at: null},
      {id: 'morning', revision: 1, kind: 'daily', deadline: '2026-10-25T06:00Z'}
    ],
    accepted: {revision: 2, intervals: [{end: '2026-10-31T10:00Z'}],
      goals: [{id: 'morning', revision: 1, planned_kwh: 30, status: 'scheduled'}],
      sessions: [
        {id: 'ev-one', resource: 'ev', start: '2026-10-24T23:00Z', end: '2026-10-25T02:00Z'},
        {id: 'ess-one', resource: 'ess', start: '2026-10-24T12:00Z', end: '2026-10-24T13:00Z'}
      ]}};
}

test('EV calendar splits overnight events without duplicating energy or inventing a return', () => {
  const schedule = evSchedule(syntheticSchedule());
  const first = eventsOnDay(schedule.events, schedule.days[0], schedule.start, schedule.end);
  const second = eventsOnDay(schedule.events, schedule.days[1], schedule.start, schedule.end);
  assert.equal(first.find(event => event.type === 'away').right, schedule.days[0].end);
  assert.equal(second.find(event => event.type === 'away').left, schedule.days[1].start);
  assert.equal(second.filter(event => event.type === 'return').length, 1);
  assert.equal(schedule.events.filter(event => event.type === 'return').length, 1);
  assert.equal(schedule.events.find(event => event.type === 'away' && event.goal.id === 'unknown').end, schedule.end);
  assert.deepEqual(schedule.events.filter(event => event.type === 'charge').map(event => event.session.id), ['ev-one']);
  assert.equal(schedule.goals.find(goal => goal.kind === 'daily').planned_kwh, 30);
  assert.equal(schedule.events.filter(event => event.type === 'away').length, 2);
});

test('EV schedule shows requirements without presenting an obsolete plan as current', () => {
  const state = syntheticSchedule();
  state.revision++;
  const obsolete = evSchedule(state);
  assert.equal(obsolete.current, false);
  assert.equal(obsolete.events.some(event => event.type === 'charge'), false);
  assert.equal(obsolete.goals.find(goal => goal.kind === 'daily').planned_kwh, undefined);
  assert.equal(obsolete.events.some(event => event.type === 'daily'), true);
  state.accepted = null;
  assert.equal(evSchedule(state).events.filter(event => event.type === 'away').length, 2);
  const restarted = syntheticSchedule();
  restarted.ev_plan_valid = false;
  assert.equal(evSchedule(restarted).events.some(event => event.type === 'charge'), false);
});

test('EV agenda uses half-open day boundaries for returns and simultaneous targets', () => {
  const day = {start: 100, end: 200};
  const events = [
    {type: 'away', start: 50, end: 100},
    {type: 'return', start: 100, end: 100},
    {type: 'daily', start: 100, end: 100},
    {type: 'manual', start: 100, end: 100},
    {type: 'trip', start: 200, end: 200}
  ];
  assert.deepEqual(eventsOnDay(events, day, 0, 300).map(event => event.type), ['daily', 'manual', 'return']);
  assert.equal(eventsOnDay(events, day, 150, 180).length, 0);
});

test('native live values use HA states without mixing demo measurements', () => {
  const manifest = {demo: false, entities: {ev_soc: 'sensor.car', ess_soc: 'sensor.battery',
    connected: 'binary_sensor.car'}};
  const backend = {accepted: {id: 'unchanged'}, live_inputs: {cards: {ev: {value: 40}}}};
  const hass = {states: {'sensor.car': {state: '55', attributes: {unit_of_measurement: '%'}},
    'binary_sensor.car': {state: 'on'}}};
  const next = nativeLiveState(backend, hass, manifest);
  assert.equal(next.live_inputs.cards.ev.value, 55);
  assert.equal(next.live_inputs.cards.ev.label, 'Connected');
  assert.equal(backend.live_inputs.cards.ev.value, 40);
  assert.equal(next.accepted, backend.accepted);
  hass.states['sensor.car'].state = 'unavailable';
  assert.equal(nativeLiveState(backend, hass, manifest).live_inputs.cards.ev.value, null);
  assert.equal(nativeLiveState(backend, hass, {...manifest, demo: true}), backend);
});

test('native live power reconstructs the AC balance and isolates unavailable sources', () => {
  const values = {grid_import_kw: [0, 'W'], grid_export_kw: [600, 'W'], pv_ac_kw: [1000, 'W'],
    pv_dc_kw: [1, 'kW'], ess_kw: [0, 'W'], ev_kw: [0, 'W'], ev_soc: [57, '%'], ess_soc: [50, '%']};
  const manifest = {demo: false, entities: Object.fromEntries(Object.keys(values).map(key => [key, `sensor.${key}`]))};
  const hass = {states: Object.fromEntries(Object.entries(values).map(([key, [value, unit]]) =>
    [`sensor.${key}`, {state: String(value), attributes: {unit_of_measurement: unit}}]))};
  const backend = {observation: {ev_kwh: 20}, hardware_control: {can_enable: false}};
  const result = nativeLiveState(backend, hass, manifest);
  assert.equal(result.live_inputs.cards.grid.value, -0.6);
  assert.equal(result.live_inputs.cards.solar.value, 2);
  assert.equal(result.live_inputs.cards.house.value, 0.4);
  assert.equal(result.hardware_control.can_enable, false);
  assert.equal(result.observation, backend.observation);
  hass.states['sensor.pv_dc_kw'].state = 'unavailable';
  assert.equal(nativeLiveState(backend, hass, manifest).live_inputs.cards.solar.value, null);
  assert.equal(nativeLiveState(backend, hass, manifest).live_inputs.cards.house.value, 0.4);
  hass.states['sensor.ev_soc'].state = ' ';
  assert.equal(nativeLiveState(backend, hass, manifest).live_inputs.cards.ev.value, null);
});

function browserContract() {
  const registry = new Map();
  globalThis.HTMLElement = class {};
  globalThis.customElements = {get: name => registry.get(name), define: (name, element) => registry.set(name, element)};
  globalThis.window = {customStrategies: []};
  globalThis.document = {};
  globalThis.location = {protocol: 'https:'};
}

test('managed strategy generates actual HA cards and adopts new release layout without changing YAML', async () => {
  browserContract();
  const {generateDashboard} = await import('../src/energymanager/assets/native-dashboard.js');
  const manifest = {version: '4.2.0', demo: false, entities: {ev_soc: 'sensor.car', ess_soc: 'sensor.battery'}};
  const config = {type: 'custom:energymanager'};
  const layout = generateDashboard(config, manifest, {addon: 'synthetic_energy_manager', manifest});
  assert.deepEqual(layout.views.map(view => view.path), ['overview', 'planning', 'ev', 'settings']);
  assert.ok(layout.views.every(view => view.sections.every(section => section.cards.every(card => card.type !== 'tile'))));
  assert.ok(layout.views.every(view => view.sections.every(section => section.cards.every(card => card.type !== 'history-graph'))));
  assert.ok(!JSON.stringify(layout).includes('iframe'));
  const future = {...manifest, version: '4.3.0'};
  const updated = generateDashboard(config, future, {addon: 'synthetic_energy_manager', manifest: future});
  assert.notEqual(layout.views[1].sections[0].cards[0].type, updated.views[1].sections[0].cards[0].type);
  assert.deepEqual(config, {type: 'custom:energymanager'});
  const Card = customElements.get(layout.views[1].sections[0].cards[0].type.slice(7));
  const instance = new Card();
  instance.setConfig({view: 'overview', addon: 'synthetic_energy_manager'});
  let disposed = 0;
  instance.controller = {dispose() { disposed++; }};
  instance.setConfig({view: 'ev', addon: 'synthetic_energy_manager'});
  assert.equal(disposed, 1); // HA may reuse a card while switching views.
  assert.equal(instance.controller, null);
});

test('stable loader uses authenticated HA discovery, versioned assets and safe session renewal', async () => {
  browserContract();
  const {connectDashboard, ingressBase} = await import('../src/energymanager/assets/ha-card.js');
  assert.throws(() => ingressBase('https://outside.test/'), /ingress/);
  assert.throws(() => ingressBase('/api/hassio_ingress/token/../../'), /ingress/);
  const calls = [];
  let sessionCount = 0, version = '4.2.0', expire = false;
  const hass = {connection: {}, user: {is_admin: true}, async callWS(message) {
    calls.push(message);
    if (message.endpoint === '/addons') return {addons: [{slug: 'synthetic_energy_manager'}]};
    if (message.endpoint === '/addons/synthetic_energy_manager/info')
      return {ingress_url: '/api/hassio_ingress/synthetic-token'};
    if (message.endpoint === '/ingress/session') return {session: `synthetic-session-${++sessionCount}`};
    throw new Error('Unexpected Supervisor endpoint');
  }};
  const originalFetch = globalThis.fetch;
  const requests = [];
  globalThis.fetch = async (url, options) => {
    requests.push({url, options});
    if (expire) { expire = false; return new Response('{}', {status: 401}); }
    return new Response(JSON.stringify({protocol: 1, version, entities: {}}));
  };
  try {
    const initial = await connectDashboard(hass);
    assert.equal(initial.assets, '/api/hassio_ingress/synthetic-token/frontend/4.2.0/');
    assert.match(document.cookie, /SameSite=Strict;Secure/);
    assert.equal(await connectDashboard(hass), initial);
    expire = true;
    await initial.request('state');
    assert.equal(sessionCount, 2);
    const before = requests.length;
    expire = true;
    await assert.rejects(initial.request('goals', 'POST', {title: 'SYNTHETIC'}));
    assert.equal(requests.length, before + 1); // Never replay a mutation automatically.
    assert.equal(requests.at(-1).options.headers['X-EnergyManager'], '1');
    version = '4.3.0';
    assert.match((await connectDashboard(hass, {}, true)).assets, /frontend\/4.3.0\/$/);
    assert.ok(calls.every(call => call.type === 'supervisor/api'));
    await assert.rejects(connectDashboard({...hass, user: {is_admin: false}}), /administrator/);
  } finally { globalThis.fetch = originalFetch; }
});

test('compact daily energy separates flows, pairs day-end predictions and rejects stale totals/plans', () => {
  const summary = {date: '2026-10-25', timezone: 'Europe/Brussels', partial: true,
    prediction_revision: 2, prediction_plan_id: 'synthetic',
    kwh: {import: 4, export: 2, ess_charge: 1.5, ess_discharge: 1, solar_ac: 5, solar_dc: 1, house: 3, ev: 2},
    predicted_kwh: {import: 6, export: 3, ess_charge: 2, ess_discharge: 1.5, solar_ac: 7, solar_dc: 2, house: 5, ev: 4}};
  const state = {now: '2026-10-24T23:00:00Z', policy: {timezone: 'Europe/Brussels'}, revision: 2, accepted: {id: 'synthetic'}};
  assert.deepEqual(dailyEnergyRows(summary, 'grid', state).map(row => [row.symbol,row.actual,row.predicted]),
    [['←','4.00','6.00'],['→','2.00','3.00']]);
  assert.deepEqual(dailyEnergyRows(summary, 'solar', state).map(row => row.symbol), ['∿','⎓']);
  assert.ok(dailyEnergyRows(summary, 'ess', state).every(row => row.partial));
  assert.equal(dailyEnergyRows(summary, 'house', {...state, revision: 3})[0].predicted, '—');
  assert.equal(dailyEnergyRows(summary, 'house', {...state, now:'2026-10-25T23:00Z'})[0].actual, '—');
  assert.equal(dailyEnergyRows(null, 'ev', state)[0].actual, '—');
  assert.match(connectionIcon(true), /aria-label="Connected"/);
  assert.match(connectionIcon(false), /aria-label="Disconnected"/);
  assert.match(connectionIcon(null), /aria-label="Connection unknown"/);
});

const {valueAt, clipSeries} = await import('../src/energymanager/assets/graph-cursor.js');
test('graph cursor follows displayed lines and preserves gaps and planned step boundaries', () => {
  const readings = [[0,100],[10,200],[20,null],[30,300]];
  assert.deepEqual(valueAt(readings, 5), {value:150, approximate:true});
  assert.deepEqual(valueAt(readings, 10), {value:200, approximate:false});
  assert.equal(valueAt(readings, -1), null);
  assert.equal(valueAt(readings, 15), null);
  assert.equal(valueAt(readings, 25), null);
  assert.equal(valueAt(readings, 31), null);
  assert.deepEqual(valueAt([[0,100],[10,100],[10,200],[20,200]],10), {value:200,approximate:false});
});

// Synthetic archive transport and measurements; no HA access.
const {GraphHistory, historyDayRange, observedPoints} = await import('../src/energymanager/assets/graph-history.js');

test('graph history selects installation-local calendar days across clock changes', () => {
  const autumn = historyDayRange('2026-10-25', 'Europe/Brussels');
  const spring = historyDayRange('2026-03-29', 'Europe/Brussels');
  assert.equal((autumn[1] - autumn[0]) / 3600000, 25);
  assert.equal((spring[1] - spring[0]) / 3600000, 23);
  assert.equal(new Date(historyDayRange('2026-10-25', 'Asia/Kolkata')[0]).toISOString(), '2026-10-24T18:30:00.000Z');
});

test('graph history ignores obsolete responses, caches ranges and exposes archive failure', async () => {
  const pending = [];
  let renders = 0;
  const history = new GraphHistory(path => new Promise((resolve, reject) => pending.push({path, resolve, reject})), () => renders++);
  history.load(0, 3600000, 7200000);
  history.load(0, 3600000, 7200000);
  assert.equal(pending.length, 1);
  history.load(3600000, 7200000, 7200000);
  const old = [...history.requests.values()][0];
  const next = [...history.requests.values()][1];
  pending[1].resolve({sample_count: 2, bucket_seconds: 12, series: {house: [[3600000, 400]]}});
  await next;
  pending[0].resolve({sample_count: 1, series: {house: [[0, 100]]}});
  await old;
  assert.equal(history.data.sample_count, 2);
  assert.equal(renders, 1);
  history.load(0, 3600000, 7200000);
  assert.equal(history.data.sample_count, 1);
  assert.equal(pending.length, 2);
  history.load(7200000, 10800000, 10800000);
  const failure = [...history.requests.values()][0];
  pending[2].reject(new Error('SYNTHETIC archive timeout'));
  await failure;
  assert.match(history.status, /unavailable.*recent samples only.*timeout/);
  history.load(7200000, 10800000, 10800000);
  assert.equal(pending.length, 3); // Back off a failed archive rather than hammering it every state poll.
  history.dispose();
  history.load(0, 3600000, 7200000);
  assert.equal(pending.length, 3);
});

test('observed graphs merge older archive with recent snapshots while preserving missing readings', () => {
  const start = Date.parse('2026-10-24T00:00Z');
  const sample = {at: new Date(start).toISOString(), quality: 'measured', house_kw: 0.4,
    pv_ac_kw: 1, pv_dc_kw: 0, ev_power_kw: 0, ess_power_kw: 0, ev_kwh: 24, ess_kwh: 7};
  const state = {demo: false, now: new Date(start + 150000).toISOString(), policy: {measurement_max_age_seconds: 30},
    capabilities: {ev_capacity_kwh: 60, ess_capacity_kwh: 14}, observed: [
      sample, {...sample, quality: 'unknown'}, {...sample, at: new Date(start + 5000).toISOString()},
      {...sample, at: new Date(start + 90000).toISOString(), ev_state_known: false}
    ]};
  const archive = {series: {house: [[start - 3600000, 200], [start, 399]], ev_soc: [[start - 3600000, 40]]}};
  const house = observedPoints(state, archive, 'house');
  assert.deepEqual(house, [[start - 3600000, 200], [start - 3570000, null], [start, 400], [start + 5000, 400],
    [start + 35000, null], [start + 90000, 400], [start + 120000, null]]);
  const ev = observedPoints(state, archive, 'ev', true);
  assert.equal(ev.find(point => point[0] === start)[1], 40);
  assert.equal(ev.find(point => point[0] === start + 90000)[1], null);
  assert.equal(state.observed[0], sample); // Projection does not change backend evidence.
});

test('a ring of repeated expired snapshots cannot erase the valid archived reading', () => {
  const start = Date.parse('2026-10-24T00:00Z');
  const state = {demo: false, now: new Date(start + 120000).toISOString(),
    capabilities: {ev_capacity_kwh: 60, ess_capacity_kwh: 14}, policy: {measurement_max_age_seconds: 30},
    observed: [{at: new Date(start).toISOString(), quality: 'unknown'}]};
  const archive = {series: {house: [[start, 400], [start + 30000, null]]}};
  assert.deepEqual(observedPoints(state, archive, 'house'), archive.series.house);
});


test('graph window boundaries keep bracketing line values without extrapolating across missing data', () => {
  const clipped = clipSeries([[0,100],[10,100],[10,200],[20,200]], 5, 15);
  assert.deepEqual(valueAt(clipped, 5), {value:100,approximate:true});
  assert.deepEqual(valueAt(clipped, 15), {value:200,approximate:true});
  assert.deepEqual(valueAt(clipped, 10), {value:200,approximate:false});
  assert.deepEqual(clipSeries([[0,100],[10,null],[20,200]], 5, 15), [[10,null]]);
});
