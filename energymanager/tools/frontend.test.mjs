import {sessionContributionMarkup} from '../src/energymanager/assets/session-details.js';
import assert from 'node:assert/strict';
import test from 'node:test';
import {dailyEnergyRows, goalStatus, connectionIcon, displaySetting, entityState, evFaultText, evIncidentTime, monthlyPeakWatts, notificationStatus, powerText, settingLabel, storedSetting, watts}
  from '../src/energymanager/assets/display.js';
import {clockValue, localDateTime, localInstants, monthDays, validLocal}
  from '../src/energymanager/assets/date-time.js';
import {EVSchedulePage, eventsOnDay, evSchedule, scheduleDays} from '../src/energymanager/assets/ev-schedule.js';
import {nativeLiveState, phaseSelector, setChargerPhase} from '../src/energymanager/assets/native-live.js';
import {evControlActivityModel, evMeasuredPower, evStatusModel, evStatusMarkup} from '../src/energymanager/assets/ev-status.js';
import {PlanningActivity, planningActivityModel} from '../src/energymanager/assets/planning-activity.js';

test('planning activity reports real stages and elapsed time without a fabricated percentage', () => {
  assert.equal(planningActivityModel().visible, false);
  const model = planningActivityModel({state: 'calculating', stage: 'ev_continuity', elapsed_seconds: 74});
  assert.equal(model.busy, true);
  assert.equal(model.label, 'Smoothing charging');
  assert.equal(model.elapsed, '1:14');
  assert.equal(planningActivityModel({state: 'calculating', stage: 'normal_ceiling_joint'}).label, 'Optimizing energy');
  assert.equal(planningActivityModel({state: 'restarting'}).label, 'Restarting');
  assert.equal(planningActivityModel({state: 'waiting'}).label, 'Waiting for inputs');
  assert.equal(planningActivityModel({state: 'error'}).visible, true);
  const finished_at = '2026-10-27T12:00Z';
  assert.equal(planningActivityModel({state: 'ready', finished_at}, Date.parse(finished_at) + 2000).visible, true);
  assert.equal(planningActivityModel({state: 'ready', finished_at}, Date.parse(finished_at) + 7000).visible, false);
});

function activityElement() {
  const children = new Map(), attributes = new Map(), classes = new Set();
  return {hidden: false, dataset: {}, textContent: '',
    querySelector(selector) {
      if (!children.has(selector)) children.set(selector, activityElement());
      return children.get(selector);
    },
    setAttribute: (name, value) => attributes.set(name, value),
    getAttribute: name => attributes.get(name),
    classList: {toggle: (name, on) => on ? classes.add(name) : classes.delete(name),
      contains: name => classes.has(name)}};
}

test('manual recalculation gives immediate feedback, permits restart and ignores stale state', async () => {
  const root = activityElement(), button = activityElement(), evButton = activityElement();
  let resolve, requests = 0, locked = false;
  const view = new PlanningActivity(root, button, () => {
    requests++;
    return new Promise(done => { resolve = done; });
  }, () => locked, () => [evButton]);
  try {
    const request = view.recalculate();
    assert.equal(root.hidden, false);
    assert.equal(root.querySelector('[data-planning-label]').textContent, 'Starting');
    assert.equal(button.disabled, true);
    assert.equal(evButton.disabled, true);
    assert.equal(await view.recalculate(), null);
    assert.equal(requests, 1); // No duplicate POST while acknowledgement is pending.
    const activity = {request_id: 'newest', state: 'requested', requested_at: '2026-10-27T12:00Z'};
    resolve({requested: true, planning_activity: activity});
    await request;
    assert.equal(button.disabled, false);
    assert.equal(button.querySelector('[data-recalculate-label]').textContent, 'Restart calculation');
    assert.equal(evButton.querySelector('[data-recalculate-label]').textContent, 'Restart calculation');
    view.update({planning_activity: {...activity, state: 'calculating', started_at: activity.requested_at,
      elapsed_seconds: 12, stage: 'required_reference'}});
    assert.equal(root.querySelector('[data-planning-label]').textContent, 'Finding a plan');
    view.update({planning_activity: {state: 'ready', requested_at: '2026-10-27T11:59Z'}});
    view.update({});
    assert.equal(view.activity.request_id, 'newest');
    locked = true;
    view.update({planning_activity: {...activity, state: 'checking'}});
    assert.equal(root.querySelector('[data-planning-label]').textContent, 'Finding a plan');
    locked = false;
    view.render();
    assert.equal(root.querySelector('[data-planning-label]').textContent, 'Validating');
    const restart = view.recalculate();
    assert.equal(root.querySelector('[data-planning-label]').textContent, 'Restarting');
    resolve({requested: true, planning_activity: {...activity, request_id: 'replacement', state: 'restarting'}});
    await restart;
    assert.equal(requests, 2);
    assert.equal(root.querySelector('[role="progressbar"]').getAttribute('aria-valuenow'), undefined);
    const text = root.querySelector('[data-planning-label]').textContent;
    view.dispose();
    view.update({planning_activity: {...activity, state: 'error'}});
    assert.equal(root.querySelector('[data-planning-label]').textContent, text);
  } finally { view.dispose(); }
});

test('a failed recalculation request stays visible and never retries the mutation automatically', async () => {
  const root = activityElement(), button = activityElement();
  let requests = 0;
  const view = new PlanningActivity(root, button, async () => {
    requests++;
    throw new Error('SYNTHETIC request timeout');
  });
  try {
    await assert.rejects(view.recalculate(), /SYNTHETIC request timeout/);
    view.update({planning_activity: {state: 'idle'}});
    assert.equal(root.hidden, false);
    assert.equal(root.dataset.state, 'error');
    assert.equal(button.disabled, false);
    assert.equal(requests, 1);
    assert.match(root.title, /SYNTHETIC request timeout/);
  } finally { view.dispose(); }
});

function syntheticEVStatus() {
  const at = '2026-10-25T12:00:00Z';
  return {now: at, revision: 7, demo: false, control_enabled: true,
    policy: {measurement_max_age_seconds: 30, timezone: 'Europe/Brussels'},
    capabilities: {ev_capacity_kwh: 60}, observation: {at, quality: 'measured',
      ev_state_known: true, connected: true, ev_kwh: 27, ev_power_kw: 4.1},
    command: {at, generation: 7, current_a: 6, phases: 3, ev_kw: 4.14, reason: 'SYNTHETIC request'},
    charger: {at, device_at: at, issue: null, waiting: null, control: 'SYNTHETIC control',
      states: {phase: '2', current: '6', force: '2', ev_status: '2', charger_status: '3', charger_error: '0'}}};
}

test('EV controller countdown uses the real deadline and never declares charging when it expires', () => {
  const state = syntheticEVStatus();
  state.observation.ev_power_kw = 0;
  state.charger.states.force = '1';
  state.charger.states.charger_status = '4';
  state.charger.activity = {as_of: state.now, stage: 'settling', label: 'Settling before restart',
    detail: 'SYNTHETIC deliberate pause', until: '2026-10-25T12:00:18Z', duration_seconds: 30, timer: 'Restart hold'};
  const model = evControlActivityModel(state, 5);
  assert.equal(model.seconds, 13);
  assert.equal(model.stage, 'settling');
  assert.equal(model.tone, 'active');
  assert.match(evStatusMarkup(state), /Stopped[\s\S]*Settling before restart[\s\S]*Restart hold/);
  assert.match(evStatusMarkup(state), /data-control-seconds>18/);
  const expired = evControlActivityModel(state, 19);
  assert.equal(expired.seconds, 0);
  assert.equal(expired.timerLabel, 'Awaiting control update');
  assert.equal(expired.stage, 'settling');
  assert.equal(evControlActivityModel(state, 31).label, 'Controller status unavailable');
  state.charger.activity = {...state.charger.activity, stage: 'fault', label: 'Stopped for attention',
    detail: '<script>SYNTHETIC</script>', until: null};
  assert.equal(evControlActivityModel(state).tone, 'error');
  const markup = evStatusMarkup(state);
  assert.match(markup, /&lt;script&gt;SYNTHETIC&lt;\/script&gt;/);
  assert.doesNotMatch(markup, /<script>/);
  assert.equal(evControlActivityModel({...state, demo:true}), null);
  delete state.charger.activity;
  assert.equal(evControlActivityModel(state), null);
});

test('EV visualization distinguishes measured power, command intent and selector settings', () => {
  const state = syntheticEVStatus();
  const model = evStatusModel(state);
  assert.equal(model.status, 'Charging');
  assert.equal(model.soc, 45);
  assert.equal(model.power, 4.1);
  assert.equal(model.requestedPower, 4.14);
  assert.equal(model.phase, 3); // go-e selector code2 means three phases.
  assert.equal(model.current, 6);
  assert.equal(model.flowing, true);
  state.charger.states.phase = '1';
  assert.equal(evStatusModel(state).phase, 1);
  assert.match(evStatusMarkup(state), /Requested phase mode: 3 φ · awaiting readback/);
  assert.match(evStatusMarkup(state), /Measured power[\s\S]*4100[\s\S]*Controller request[\s\S]*4140/);
  state.observation.ev_power_kw = 0;
  assert.equal(evStatusModel(state).status, 'Waiting to charge');
  assert.equal(evStatusModel(state).flowing, false);
  state.charger.states.force = '1';
  assert.equal(evStatusModel(state).status, 'Stopped');
  state.charger.states.ev_status = '4';
  assert.equal(evStatusModel(state).status, 'Charging complete');
  state.observation.connected = false;
  assert.equal(evStatusModel(state).status, 'Disconnected');
});

test('actual EV power is independent of request and SoC, preserves signed/zero readings and input availability', () => {
  const state = syntheticEVStatus();
  state.observation.ev_state_known = false;
  state.command.ev_kw = 11.04;
  assert.equal(evMeasuredPower(state), 4.1);
  for (const value of [0, -.035, 4.45]) {
    state.live_inputs = {readings:{ev_kw:{value, received_at:state.now}}, cards:{ev:{label:'Connected'}}};
    assert.equal(evMeasuredPower(state), value);
    assert.equal(evStatusModel(state).power, value);
  }
  state.live_inputs.readings.ev_kw.issue = 'unavailable';
  assert.equal(evMeasuredPower(state), null);
  state.live_inputs.readings.ev_kw = {value:4.45, received_at:'2026-10-25T11:00:00Z'};
  assert.equal(evMeasuredPower(state), null);
  state.live_inputs.readings.ev_kw.display_current = true;
  assert.equal(evMeasuredPower(state), 4.45); // HA's current state is independent of the backend input watchdog.
  state.demo = true;
  assert.equal(evMeasuredPower(state), 4.1);
});

test('native signed EV display uses the actual HA meter while remaining read-only', () => {
  const state = syntheticEVStatus();
  const manifest = {entities:{ev_kw:'sensor.synthetic_ev_power'}};
  const hass = {states:{'sensor.synthetic_ev_power':{state:'-35',attributes:{unit_of_measurement:'W'}}},
    callService:() => assert.fail('A display projection must never write to HA')};
  const projected = nativeLiveState(state,hass,manifest);
  assert.equal(evMeasuredPower(projected), -.035);
  assert.equal(evStatusModel(projected).power, -.035);
  assert.equal(projected.command, state.command);
  assert.equal(projected.charger, state.charger);
});

test('EV visualization does not fabricate zero or verified settings from stale/missing readings', () => {
  const state = syntheticEVStatus();
  state.now = '2026-10-25T12:01:00Z';
  let model = evStatusModel(state);
  assert.equal(model.status, 'Readings unavailable');
  for (const key of ['soc', 'power', 'current', 'phase', 'requestedPower']) assert.equal(model[key], null, key);
  state.now = state.observation.at;
  state.charger.states.phase = '0';
  state.charger.issue = 'Automatic phase selector blocks EV control';
  model = evStatusModel(state);
  assert.equal(model.phase, 'auto');
  assert.equal(model.current, null);
  assert.equal(model.status, 'Readings unavailable');
  state.command.generation = 6;
  assert.equal(evStatusModel(state).requestedPower, null);
  state.charger = null;
  state.observation.ev_state_known = false;
  assert.equal(evStatusModel(state).soc, null);
  assert.match(evStatusMarkup(state), /— <small>W/);
});

test('EV live display can advance independently of stale control inputs without changing authority', () => {
  const state = syntheticEVStatus();
  state.live_inputs = {readings: {ev_kw: {value: 8, issue: 'read watchdog expired', received_at: state.now},
    ev_soc: {value: 88, issue: 'read watchdog expired', received_at: state.now}}, cards: {ev: {label: 'Connected'}}};
  assert.equal(evStatusModel(state).power, null);
  assert.equal(evStatusModel(state).soc, null);
  const manifest = {entities: {ev_kw: 'sensor.power', ev_soc: 'sensor.soc', connected: 'binary_sensor.connected'}};
  const projected = nativeLiveState(state, {states: {
    'sensor.power': {state: '1380', attributes: {unit_of_measurement: 'W'}},
    'sensor.soc': {state: '57', attributes: {unit_of_measurement: '%'}},
    'binary_sensor.connected': {state: 'on'}}}, manifest);
  assert.equal(evStatusModel(projected).power, 1.38);
  assert.equal(evStatusModel(projected).soc, 57);
  assert.equal(projected.live_inputs.readings.ev_kw.issue, 'read watchdog expired');
  assert.equal(projected.command, state.command);
  assert.equal(projected.charger, state.charger);
});

test('EV faults and recovery stay visible above power flow; detail text is escaped', () => {
  const state = syntheticEVStatus();
  state.charger.states.charger_error = '1';
  assert.equal(evStatusModel(state).tone, 'fault');
  state.ev_incident = {status: 'rebooting', detected_at: state.now, reason: '<img src=x onerror=alert(1)>'};
  assert.equal(evStatusModel(state).status, 'Recovering');
  const markup = evStatusMarkup(state);
  assert.match(markup, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.doesNotMatch(markup, /<img/);
  assert.doesNotMatch(markup, /ev-device-details|<details|per-phase currents unavailable/);
  state.ev_incident.status = 'unresolved';
  assert.equal(evStatusModel(state).status, 'Fault · attention needed');
  state.ev_incident.status = 'acknowledged';
  state.charger.states.charger_error = '0';
  assert.equal(evStatusModel(state).status, 'Charging');
});

test('phase action targets the mapped actuator once and does not change the plan or invent readback', async () => {
  const manifest = {entities:{ev_phases:'sensor.measured_phases'},phase_selector:'select.synthetic_phase'};
  const calls = [], hass = {states:{'select.synthetic_phase':{state:'1',attributes:{options:['0','1','2']}}},
    callService:async(...args)=>calls.push(args)};
  const state = syntheticEVStatus(), command = state.command;
  assert.equal(phaseSelector(hass,manifest).value,'1');
  await setChargerPhase(hass,manifest,'2');
  assert.deepEqual(calls,[['select','select_option',{entity_id:'select.synthetic_phase',option:'2'}]]);
  assert.equal(hass.states['select.synthetic_phase'].state,'1');
  assert.equal(state.command,command);
  await setChargerPhase(hass,manifest,'0');
  assert.equal(calls[1][2].option,'0');
});

test('phase actions reject demo, missing, unavailable, unsupported and non-select mappings without writes', async () => {
  let calls=0;
  const hass={states:{'select.phase':{state:'1',attributes:{options:['1','2']}}},callService:async()=>calls++};
  for (const manifest of [{demo:true,phase_selector:'select.phase'},{phase_selector:'sensor.phases'},{}])
    await assert.rejects(setChargerPhase(hass,manifest,'1'),/unavailable/);
  const manifest={phase_selector:'select.phase'};
  await assert.rejects(setChargerPhase(hass,manifest,'0'),/does not support/);
  hass.states['select.phase'].state='unavailable';
  await assert.rejects(setChargerPhase(hass,manifest,'1'),/unavailable/);
  assert.equal(calls,0);
  hass.states['select.phase'].state='1';
  hass.callService=async()=>{throw new Error('SYNTHETIC HA denied');};
  await assert.rejects(setChargerPhase(hass,manifest,'2'),/HA denied/);
});

test('EV sidebar retains raw diagnostics without the removed details foldout and phase controls use HA readback', () => {
  const state=syntheticEVStatus();
  state.phase_selector={value:'2',options:['0','1','2']};
  state.charger.states.heartbeat='1234';
  state.charger.states.charge_allowed='on';
  let markup=evStatusMarkup(state);
  assert.match(markup,/data-ev-phase="2"[^>]*aria-pressed="true"/);
  assert.match(markup,/data-ev-phase="1"[^>]*aria-pressed="false"/);
  assert.match(markup,/Allowed \(on\)/);
  assert.match(markup,/Device status age \(s\)[\s\S]*1234/);
  assert.match(markup,/HA read[\s\S]*Device frame/);
  assert.doesNotMatch(markup,/<details|ev-device-details|per-phase currents unavailable/);
  state.now='2026-10-25T12:01:00Z';
  markup=evStatusMarkup(state,{phaseChanging:true,phaseError:'<SYNTHETIC error>'});
  assert.match(markup,/Unverified · 2/);
  assert.match(markup,/data-ev-phase="2"[^>]*disabled/);
  assert.match(markup,/&lt;SYNTHETIC error&gt;/);
});

test('EV sensor readings expose keyboard-native history buttons using only supplied entity mappings', () => {
  const state = syntheticEVStatus();
  const keys = ['ev_kw','ev_soc','connected','force','current','phase','charge_allowed','ev_status',
    'charger_status','charger_error','heartbeat'];
  const entities = Object.fromEntries(keys.map(key=>[key,'sensor.synthetic_'+key]));
  let markup = evStatusMarkup(state,{entities});
  for (const key of keys) {
    assert.match(markup,new RegExp(`<button type="button" class="entity-reading" data-entity-key="${key}"`));
    assert.ok(markup.includes(`Open ${entities[key]} in Home Assistant`));
  }
  assert.equal((markup.match(/data-ev-history="current-limit"/g)||[]).length,1);
  assert.equal((markup.match(/data-ev-history="current-setting"/g)||[]).length,1);
  assert.match(markup,/EnergyManager command intent; no HA sensor history/);
  assert.match(markup,/EnergyManager input read timestamp; no HA sensor history/);
  assert.match(markup,/EnergyManager validated device frame timestamp; no HA sensor history/);
  assert.doesNotMatch(markup,/data-entity-key="(?:command|request|device_at|at)"/);
  state.now='2026-10-25T12:01:00Z';
  markup=evStatusMarkup(state,{entities});
  assert.match(markup,/Unverified/);
  assert.match(markup,/data-entity-key="charger_error"/); // Unavailable mapped entities still have their own HA history.
});

test('EV history actions are absent in demo/standalone and unmapped readings explain their source', () => {
  const state=syntheticEVStatus();
  assert.doesNotMatch(evStatusMarkup(state),/data-entity-key=/);
  assert.match(evStatusMarkup(state),/Entity history is available in the native Home Assistant dashboard/);
  assert.doesNotMatch(evStatusMarkup(state,{entities:{}}),/data-entity-key=/);
  assert.match(evStatusMarkup(state,{entities:{}}),/No Home Assistant entity is mapped/);
  state.demo=true;
  const markup=evStatusMarkup(state,{entities:{ev_kw:'sensor.installation_power'}});
  assert.doesNotMatch(markup,/data-entity-key=|sensor.installation_power/);
  assert.match(markup,/Synthetic demo reading; no Home Assistant history/);
});

test('EV demo ignores installation charger faults and live readings', () => {
  const state = syntheticEVStatus();
  state.demo = true;
  state.observation.quality = 'SYNTHETIC';
  state.live_inputs = {readings: {ev_kw: {value: 99, display_current: true}}};
  state.charger.states.charger_error = '1';
  state.actuator_health = {delivery_fault: true};
  state.ev_incident = {status: 'unresolved', reason: 'Installation fault'};
  const model = evStatusModel(state);
  assert.equal(model.power, 4.1);
  assert.equal(model.status, 'Charging');
  assert.equal(model.phase, null);
  assert.equal(model.current, null);
  assert.match(evStatusMarkup(state), /Synthetic demo/);
  assert.doesNotMatch(evStatusMarkup(state), /Installation fault/);
});

test('EV diagnostic colors distinguish a historical incident from current charger health', () => {
  const state = syntheticEVStatus();
  state.ev_incident = {status: 'unresolved', detected_at: state.now, reason: 'Earlier recovery failed'};
  state.charger.states.charge_allowed = 'off';
  state.charger.states.force = '1';
  state.charger.states.ev_status = '3';
  state.charger.states.charger_status = '4';
  const model = evStatusModel(state);
  const fields = Object.fromEntries(model.diagnostics.map(field => [field.key, field]));
  assert.equal(model.tone, 'fault');
  assert.equal(fields.charger_error.tone, 'good');
  assert.equal(fields.charger_error.text, 'None (0)');
  for (const key of ['charge_allowed', 'force', 'ev_status', 'charger_status']) {
    assert.equal(fields[key].tone, 'neutral', key);
  }
  assert.equal(fields.connected.tone, 'good');
  assert.match(evStatusMarkup(state), /data-ev-field="charger_error" class="ev-reading-good"/);
});

test('EV diagnostics color actual errors red, and stale or unknown codes remain unverified', () => {
  const state = syntheticEVStatus();
  state.charger.states.charger_error = '8';
  state.charger.states.ev_status = '5';
  state.charger.states.charger_status = '26';
  let fields = evStatusModel(state).diagnostics;
  for (const key of ['charger_error', 'ev_status', 'charger_status']) {
    assert.equal(fields.find(field => field.key === key).tone, 'error', key);
  }
  state.now = '2026-10-25T12:01:00Z';
  fields = evStatusModel(state).diagnostics;
  for (const field of fields.filter(field => field.key !== 'connected')) {
    assert.equal(field.tone, 'neutral', field.key);
    assert.equal(field.text, 'Unverified', field.key);
  }
  state.now = state.observation.at;
  state.charger.states.charger_status = '255';
  const unknown = evStatusModel(state).diagnostics.find(field => field.key === 'charger_status');
  assert.equal(unknown.text, 'Unknown (255)');
  assert.equal(unknown.tone, 'neutral');
});

test('EV diagnostics separate charging permission, waiting states and selected settings', () => {
  const state = syntheticEVStatus();
  state.charger.states.charge_allowed = 'on';
  state.observation.ev_power_kw = 0;
  state.charger.states.ev_status = '3';
  state.charger.states.charger_status = '23';
  const fields = Object.fromEntries(evStatusModel(state).diagnostics.map(field => [field.key, field]));
  assert.equal(fields.charge_allowed.tone, 'good');
  assert.equal(fields.ev_status.tone, 'neutral');
  assert.equal(fields.charger_status.text, 'Phase switching (23)');
  assert.equal(fields.charger_status.tone, 'neutral');
  assert.equal(fields.force.tone, 'neutral');
  state.demo = true;
  state.observation.quality = 'SYNTHETIC';
  const demoFields = evStatusModel(state).diagnostics.filter(field => field.key !== 'connected');
  assert.ok(demoFields.every(field => field.tone === 'neutral' && field.text === 'Unverified'));
});

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

test('EV incident text includes second-level local timestamps, offsets and recovery phase', () => {
  const incident = {detected_at: '2026-10-25T12:01:30Z', status:'unresolved', reason:'No delivery'};
  assert.match(evFaultText(incident,'Europe/Brussels'), /stopped; attention needed.*13:01:30 GMT\+1.*No delivery/);
  assert.match(evFaultText({...incident,status:'verifying'},'Europe/Brussels'), /checking charging/);
  assert.equal(evFaultText(null,'Europe/Brussels'), '');
  assert.equal(evFaultText({...incident,status:'recovered'},'Europe/Brussels'), '');
  assert.notEqual(evIncidentTime('2026-10-25T00:30Z','Europe/Brussels'), evIncidentTime('2026-10-25T01:30Z','Europe/Brussels'));
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

test('subscribed journeys preserve source and placeholder metadata in departure, away and return items', () => {
  const state = syntheticSchedule();
  state.schedule_goals = [{id: 'calendar-synthetic', revision: 3, kind: 'trip', title: 'Referee · fixture',
    deadline: '2026-10-25T01:00Z', return_at: '2026-10-25T05:00Z', distance_km: 50,
    calendar: {source: 'Referee', location: 'Fixture hall', placeholder: true}}];
  state.accepted = null;
  const schedule = evSchedule(state);
  assert.deepEqual(schedule.events.map(event => event.type), ['trip', 'away', 'return']);
  assert.ok(schedule.events.every(event => event.goal.calendar.placeholder));
  assert.equal(schedule.goals[0].distance_km, 50);
  assert.equal(schedule.events[1].end - schedule.events[1].start, 4 * 3600000);
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

test('compact daily energy keeps the frozen baseline across plans and rejects other dates/modes', () => {
  const summary = {date: '2026-10-25', timezone: 'Europe/Brussels', partial: true,
    prediction_revision: 2, prediction_plan_id: 'synthetic',
    kwh: {import: 4, export: 2, ess_charge: 1.5, ess_discharge: 1, solar_ac: 5, solar_dc: 1, house: 3, ev: 2},
    predicted_kwh: {import: 6, export: 3, ess_charge: 2, ess_discharge: 1.5, solar_ac: 7, solar_dc: 2, house: 5, ev: 4}};
  const state = {now: '2026-10-24T23:00:00Z', policy: {timezone: 'Europe/Brussels'}, revision: 2, accepted: {id: 'synthetic'},
    daily_estimate: {date: summary.date, timezone: summary.timezone, kind: 'midnight',
      captured_at: '2026-10-24T22:00:01Z', kwh: summary.predicted_kwh}};
  assert.deepEqual(dailyEnergyRows(summary, 'grid', state).map(row => [row.symbol,row.actual,row.predicted]),
    [['←','4.00','6.00'],['→','2.00','3.00']]);
  assert.deepEqual(dailyEnergyRows(summary, 'solar', state).map(row => row.symbol), ['∿','⎓']);
  assert.ok(dailyEnergyRows(summary, 'ess', state).every(row => row.partial));
  assert.equal(dailyEnergyRows(summary, 'house', {...state, revision: 3, accepted: null})[0].predicted, '5.00');
  assert.equal(dailyEnergyRows(null, 'house', state)[0].predicted, '5.00');
  assert.match(dailyEnergyRows(null, 'house', state)[0].capture, /Fixed midnight estimate; captured.*00:00:01/);
  assert.equal(dailyEnergyRows(summary, 'house', {...state, demo: true})[0].predicted, '—');
  assert.equal(dailyEnergyRows(summary, 'house', {...state, now:'2026-10-25T23:00Z'})[0].predicted, '—');
  assert.equal(dailyEnergyRows(summary, 'house', {...state, now:'2026-10-25T23:00Z'})[0].actual, '—');
  assert.equal(dailyEnergyRows(null, 'ev', state)[0].actual, '—');
  assert.match(connectionIcon(true), /aria-label="Connected"/);
  assert.match(connectionIcon(false), /aria-label="Disconnected"/);
  assert.match(connectionIcon(null), /aria-label="Connection unknown"/);
});

const {GraphCursor, valueAt, clipSeries} = await import('../src/energymanager/assets/graph-cursor.js');
const {requestError, StatePoller} = await import('../src/energymanager/assets/dashboard-client.js');
const {hasTextSelection} = await import('../src/energymanager/assets/text-selection.js');

test('request failures name the endpoint and never imply a timed-out mutation was not applied', () => {
  const timeout = new DOMException('signal timed out', 'TimeoutError');
  assert.match(requestError(timeout, 'state?plan_id=private').message, /GET state: timed out after 15 seconds/);
  assert.doesNotMatch(requestError(timeout, 'state?plan_id=private').message, /private|may have been applied/);
  assert.match(requestError(timeout, 'goals', 'POST').message, /POST goals.*may have been applied/);
  assert.match(requestError(new TypeError('Failed to fetch'), 'state').message, /could not reach EnergyManager/);
  const invalid = Object.assign(new Error('Invalid settings'), {fields: {power: 'Invalid'}});
  assert.deepEqual(requestError(invalid, 'settings', 'POST').fields, invalid.fields);
  assert.doesNotMatch(requestError(invalid, 'settings', 'POST').message, /may have been applied/);
});

test('state polling reuses only the matching immutable plan and clears removed plans', async () => {
  const plan = {id: 'one', flows: {grid: [1]}};
  const states = [{accepted: plan}, {accepted_unchanged: true, accepted_plan_id: 'one'},
    {accepted: {id: 'two'}}, {accepted: null}, {accepted_unchanged: true, accepted_plan_id: 'unknown'}];
  const paths = [];
  const poller = new StatePoller(async path => {paths.push(path); return states.shift();});
  assert.equal((await poller.poll()).accepted, plan);
  assert.equal((await poller.poll()).accepted, plan);
  assert.match(paths[1], /compact=1&plan_id=one/);
  assert.equal((await poller.poll()).accepted.id, 'two');
  assert.equal((await poller.poll()).accepted, null);
  await assert.rejects(poller.poll(), /out of sync/);
});

test('failed state polls back off, permit explicit refresh and recover without retrying actions', async () => {
  const originalNow = Date.now;
  let now = 0, calls = 0, fail = true;
  Date.now = () => now;
  const poller = new StatePoller(async () => {calls++; if (fail) throw new Error('SYNTHETIC timeout'); return {accepted: null};});
  try {
    await assert.rejects(poller.poll());
    assert.equal(poller.retryAt, 2000);
    assert.equal(await poller.poll(), null);
    assert.equal(calls, 1);
    now = 2000;
    await assert.rejects(poller.poll());
    assert.equal(poller.retryAt, 6000);
    fail = false;
    assert.deepEqual(await poller.poll(true), {accepted: null});
    assert.equal(poller.failures, 0);
    assert.equal(poller.retryAt, 0);
  } finally { Date.now = originalNow; }
});

test('text selection covers shadow text and a document range crossing its host', () => {
  const text = {}, host = {};
  const selection = {isCollapsed: false, anchorNode: text, focusNode: text, rangeCount: 1,
    getRangeAt: () => ({intersectsNode: node => node === host})};
  const root = {host, contains: node => node === text, ownerDocument: {getSelection: () => selection}};
  assert.ok(hasTextSelection(root));
  selection.anchorNode = selection.focusNode = {};
  assert.ok(hasTextSelection(root));
  selection.isCollapsed = true;
  assert.equal(hasTextSelection(root), false);
});
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

function syntheticGraphPointer(t) {
  const frames = new Map(), changes = [], controller = new AbortController();
  const originalRequest = globalThis.requestAnimationFrame, originalCancel = globalThis.cancelAnimationFrame;
  let frameID = 0, enabled = true;
  globalThis.requestAnimationFrame = callback => {frames.set(++frameID, callback); return frameID;};
  globalThis.cancelAnimationFrame = id => frames.delete(id);
  t.after(() => {controller.abort(); globalThis.requestAnimationFrame = originalRequest;
    globalThis.cancelAnimationFrame = originalCancel;});
  class Plot extends EventTarget {
    constructor() {super(); this.classes = new Set(); this.capture = null; this.captures = new Set();
      this.classList = {add: value => this.classes.add(value), remove: value => this.classes.delete(value),
        toggle: (value, active) => active ? this.classes.add(value) : this.classes.delete(value)};}
    setAttribute() {}
    focus() {}
    closest() {return null;}
    querySelector(selector) {return selector === 'svg' ? {getBoundingClientRect: () => ({left:0,width:1000})} : null;}
    setPointerCapture(id) {this.captures.add(id); this.capture = id;}
    hasPointerCapture(id) {return this.captures.has(id);}
    releasePointerCapture(id) {this.captures.delete(id); this.capture = [...this.captures].at(-1) ?? null;}
  }
  const plots = {power: new Plot(), soc: new Plot()};
  const root = {ownerDocument: {getSelection: () => null}, querySelector: selector => {
    const plot = plots[selector.slice(1).split(' ')[0]];
    return selector.endsWith(' svg') ? plot.querySelector('svg') : plot;
  }};
  const cursor = new GraphCursor(root, String, {}, controller.signal,
    {enabled: () => enabled, changed: (range, finished) => changes.push({range,finished})});
  const model = {start:0,end:21600000,width:1000,now:7200000};
  cursor.update({power:model,soc:{...model}});
  const emit = (type, x, y = 50, extra = {}) => {
    const event = new Event(type, {cancelable:true});
    Object.assign(event, {pointerId:1,pointerType:'mouse',button:0,buttons:type === 'pointerup' ? 0 : 1,
      clientX:x,clientY:y,...extra});
    plots.power.dispatchEvent(event);
    return event;
  };
  return {cursor,changes,plots,controller,emit,disable: () => {enabled=false;},
    flush: () => {const pending=[...frames.values()]; frames.clear(); pending.forEach(callback=>callback());}};
}

test('horizontal graph dragging preserves duration, direction and the original pointer anchor', t => {
  const fixture = syntheticGraphPointer(t);
  fixture.emit('pointerdown', 200);
  fixture.emit('pointermove', 292.6, 54);
  fixture.emit('pointermove', 385.2, 52);
  assert.equal(fixture.changes.length, 0); // Multiple moves share one animation frame.
  fixture.flush();
  assert.ok(Math.abs(fixture.changes[0].range[0] + 4320000) < 0.001);
  assert.equal(fixture.changes[0].range[1]-fixture.changes[0].range[0], 21600000);
  assert.equal(fixture.changes[0].finished, false);
  fixture.emit('pointerup', 107.4, 58);
  const final = fixture.changes.at(-1);
  assert.ok(Math.abs(final.range[0] - 2160000) < 0.001);
  assert.equal(final.finished, true);
  assert.equal(fixture.plots.power.capture, null);
  assert.equal(fixture.cursor.pinned, false);
});

test('wheel zoom coalesces a burst, anchors time under the mouse and settles one archive update', async t => {
  const fixture = syntheticGraphPointer(t);
  const wheel = extra => {
    const event = new Event('wheel', {cancelable:true});
    Object.assign(event, {deltaX:0,deltaY:-100,deltaMode:0,clientX:289.5,ctrlKey:false,metaKey:false,...extra});
    fixture.plots.power.dispatchEvent(event);
    return event;
  };
  assert.equal(wheel({ctrlKey:true}).defaultPrevented, false);
  assert.equal(wheel({metaKey:true}).defaultPrevented, false);
  assert.equal(wheel({}).defaultPrevented, true);
  wheel({deltaX:-100,deltaY:0});
  assert.equal(fixture.changes.length, 0);
  fixture.flush();
  const [start,end] = fixture.changes[0].range, duration = end-start;
  assert.ok(Math.abs(duration - 21600000*Math.exp(-0.4)) < 0.001);
  assert.ok(Math.abs(start + 0.25*duration - 0.25*21600000) < 0.001);
  assert.equal(fixture.cursor.interacting, true);
  await new Promise(resolve => setTimeout(resolve, 220));
  assert.equal(fixture.changes.filter(change => change.finished).length, 1);
  assert.equal(fixture.cursor.interacting, false);
});

test('line/page wheel units, zoom bounds and cancellation preserve the final viewport', t => {
  const fixture = syntheticGraphPointer(t);
  const wheel = (deltaY, deltaMode, clientX=521) => {
    const event = new Event('wheel', {cancelable:true});
    Object.assign(event, {deltaX:0,deltaY,deltaMode,clientX}); fixture.plots.power.dispatchEvent(event);
  };
  wheel(1, 2);
  fixture.cursor.finishWheel();
  let [start,end] = fixture.changes.at(-1).range;
  assert.ok(Math.abs(end-start - 21600000*Math.E) < 0.001);
  assert.ok(Math.abs((start+end)/2 - 10800000) < 0.001);
  wheel(-1, 1);
  fixture.cursor.finishWheel();
  [start,end] = fixture.changes.at(-1).range;
  assert.ok(Math.abs(end-start - 21600000*Math.exp(-0.032)) < 0.001);
  for (let n=0;n<20;n++) wheel(-1000,0,58);
  fixture.flush(); [start,end] = fixture.changes.at(-1).range;
  assert.equal(end-start,15*60000);
  assert.ok(Math.abs(start) < 0.001);
  for (let n=0;n<20;n++) wheel(1000,0,58);
  fixture.flush(); [start,end] = fixture.changes.at(-1).range;
  assert.equal(end-start,7*24*3600000);
  const count = fixture.changes.length;
  wheel(120, 0);
  fixture.cursor.cancelNavigation();
  fixture.flush();
  assert.equal(fixture.changes.length, count);
  assert.equal(fixture.cursor.interacting, false);
});

test('two-finger panning preserves duration and ignores vertical centroid movement', t => {
  const fixture = syntheticGraphPointer(t);
  const touch = (type, id, x, y=50) => fixture.emit(type,x,y,{pointerId:id,pointerType:'touch'});
  assert.equal(touch('pointerdown',1,200).defaultPrevented, false);
  assert.equal(touch('pointerdown',2,400).defaultPrevented, true);
  touch('pointermove',1,250,100); touch('pointermove',2,450,100);
  fixture.flush();
  const range = fixture.changes.at(-1).range;
  assert.equal(range[1]-range[0], 21600000);
  assert.ok(Math.abs(range[0] + 50/926*21600000) < 0.001);
  touch('pointerup',1,250,100);
  const count = fixture.changes.length;
  touch('pointermove',2,500,100); touch('pointerup',2,500,100);
  fixture.flush();
  assert.equal(fixture.changes.length, count);
  assert.equal(fixture.cursor.pinned, false);
  assert.equal(fixture.cursor.interacting, false);
  assert.equal(fixture.plots.power.captures.size, 0);
});

test('pinch zoom preserves the midpoint time and has bounded duration', t => {
  const fixture = syntheticGraphPointer(t);
  const touch = (type, id, x) => fixture.emit(type,x,50,{pointerId:id,pointerType:'touch'});
  touch('pointerdown',1,100); touch('pointerdown',2,500);
  touch('pointermove',1,-100); touch('pointermove',2,700);
  fixture.flush();
  let range = fixture.changes.at(-1).range;
  assert.equal(range[1]-range[0], 10800000);
  const fraction = (300-58)/926;
  assert.ok(Math.abs(range[0] + fraction*10800000 - fraction*21600000) < 0.001);
  touch('pointermove',1,299); touch('pointermove',2,300);
  fixture.flush(); range=fixture.changes.at(-1).range;
  assert.equal(range[1]-range[0], 7*24*3600000);
  touch('pointermove',1,-1000000); touch('pointermove',2,1000000);
  fixture.flush(); range=fixture.changes.at(-1).range;
  assert.equal(range[1]-range[0], 15*60000);
});

test('third touch, pointer loss and disposal do not leave queued navigation or captures', t => {
  const fixture = syntheticGraphPointer(t);
  const touch = (type,id,x) => fixture.emit(type,x,50,{pointerId:id,pointerType:'touch'});
  touch('pointerdown',1,200); touch('pointerdown',2,400); touch('pointermove',2,500);
  touch('pointerdown',3,600);
  assert.equal(fixture.changes.filter(change=>change.finished).length, 1);
  const count=fixture.changes.length;
  touch('pointermove',3,700); touch('pointercancel',1,200); touch('pointerup',2,500); touch('pointerup',3,700);
  fixture.flush(); assert.equal(fixture.changes.length,count);
  touch('pointerdown',4,200); touch('pointerdown',5,400); touch('pointermove',5,500);
  fixture.controller.abort(); fixture.flush();
  assert.equal(fixture.changes.length,count);
  assert.equal(fixture.plots.power.captures.size,0);
  assert.equal(fixture.cursor.interacting,false);
});

test('monthly peak uses only a current recorded input, with explicit zero and demo isolation', () => {
  const state = syntheticEVStatus();
  state.observation.monthly_peak_kw = 2.5;
  state.policy.capacity_floor_kw = 2.5;
  state.accepted = {summary:{peak_kw:7}};
  assert.equal(monthlyPeakWatts(state),null);
  state.live_inputs = {readings:{monthly_peak_kw:{value:1.2,issue:null}}};
  assert.equal(monthlyPeakWatts(state),1200);
  const reading=state.live_inputs.readings.monthly_peak_kw;
  for (const value of [null,undefined,'', ' ',NaN,Infinity,-1]) {
    reading.value=value; assert.equal(monthlyPeakWatts(state),null);
  }
  reading.value=0; assert.equal(monthlyPeakWatts(state),0);
  reading.value=3; reading.issue='read watchdog expired'; assert.equal(monthlyPeakWatts(state),null);
  reading.display_current=true; assert.equal(monthlyPeakWatts(state),3000);
  state.demo=true; assert.equal(monthlyPeakWatts(state),2500);
  state.now='2026-10-25T12:01:00Z'; assert.equal(monthlyPeakWatts(state),null);
});

test('native monthly peak converts W and never replaces unavailable values with an old observation', () => {
  const state=syntheticEVStatus(), manifest={entities:{monthly_peak_kw:'sensor.peak'}};
  const hass={states:{'sensor.peak':{state:'3750',attributes:{unit_of_measurement:'W'}}}};
  assert.equal(monthlyPeakWatts(nativeLiveState(state,hass,manifest)),3750);
  hass.states['sensor.peak'].state='unavailable';
  assert.equal(monthlyPeakWatts(nativeLiveState(state,hass,manifest)),null);
});

test('graph clicks pin values and vertical gestures do not pan time', t => {
  const fixture = syntheticGraphPointer(t);
  fixture.emit('pointerdown', 200);
  fixture.emit('pointermove', 203);
  fixture.emit('pointerup', 203);
  assert.equal(fixture.cursor.pinned, true);
  assert.equal(fixture.changes.length, 0);
  fixture.emit('pointerdown', 200);
  fixture.emit('pointermove', 204, 80);
  fixture.emit('pointermove', 400, 85);
  fixture.emit('pointerup', 400, 85);
  fixture.flush();
  assert.equal(fixture.changes.length, 0);
});

test('graph cancellation finalizes once and disposal cancels pending rendering', t => {
  const fixture = syntheticGraphPointer(t);
  fixture.emit('pointerdown', 200);
  fixture.emit('pointermove', 100);
  fixture.emit('pointercancel', 100);
  fixture.emit('lostpointercapture', 100);
  fixture.flush();
  assert.equal(fixture.changes.length, 1);
  assert.equal(fixture.changes[0].finished, true);
  fixture.emit('pointerdown', 200);
  fixture.emit('pointermove', 100);
  fixture.controller.abort();
  fixture.flush();
  assert.equal(fixture.changes.length, 1);
  assert.equal(fixture.plots.power.capture, null);
  assert.equal(fixture.plots.power.classes.has('graph-panning'), false);
});

test('graph panning leaves secondary buttons, touch and disabled views alone', t => {
  const fixture = syntheticGraphPointer(t);
  for (const extra of [{button:2}, {pointerType:'touch'}]) {
    fixture.emit('pointerdown', 200, 50, extra);
    fixture.emit('pointermove', 100, 50, extra);
    fixture.emit('pointerup', 100, 50, extra);
  }
  fixture.disable();
  fixture.emit('pointerdown', 200);
  fixture.emit('pointermove', 100);
  fixture.emit('pointerup', 100);
  fixture.flush();
  assert.equal(fixture.changes.length, 0);
  assert.equal(fixture.plots.power.capture, null);
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

test('rolling graph history retains overlapping data through refresh and failure, clears unrelated ranges', async () => {
  const pending = [];
  const history = new GraphHistory(path => new Promise((resolve, reject) => pending.push({resolve, reject})), () => {});
  history.load(0, 3600000, 3600000);
  const data = {sample_count: 2, series: {house: [[0,100],[3500000,200]]}};
  pending[0].resolve(data);
  await [...history.requests.values()][0];
  history.load(60000, 3660000, 3660000);
  assert.equal(history.data, data);
  assert.ok(history.loading);
  pending[1].reject(new Error('SYNTHETIC timeout'));
  await [...history.requests.values()][0];
  assert.equal(history.data, data);
  assert.match(history.status, /retaining loaded history.*timeout/);
  history.load(60000, 3660000, 3660000);
  assert.equal(history.data, data); // Failed range backoff must retain it too.
  history.load(7200000, 10800000, 10800000);
  assert.equal(history.data, null);
  pending[2].resolve({sample_count: 0, series: {}});
  await [...history.requests.values()][0];
  history.dispose();
});

test('graph history never retains another operating mode or timezone', async () => {
  const pending = [];
  const history = new GraphHistory(() => new Promise(resolve => pending.push(resolve)), () => {});
  history.load(0, 3600000, 3600000, 'configured/Europe/Brussels');
  pending[0]({sample_count: 1, series: {house: [[0,400]]}});
  await [...history.requests.values()][0];
  history.load(0, 3600000, 3600000, 'demo/Europe/Brussels');
  assert.equal(history.data, null);
  const demoRequest = [...history.requests.values()][0];
  history.load(0, 3600000, 3600000, 'demo/UTC');
  pending[1]({sample_count: 9});
  await demoRequest;
  assert.equal(history.data, null);
  pending[2]({sample_count: 2, series: {}});
  await [...history.requests.values()][0];
  assert.equal(history.data.sample_count, 2);
  history.dispose();
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


test('planning notices distinguish HA handoff, local-only delivery and pending retry', () => {
  assert.equal(notificationStatus('delivered'), 'Phone alert sent to Home Assistant');
  assert.match(notificationStatus('local_only'), /no phone destination configured/);
  assert.match(notificationStatus('retrying'), /delivery retrying/);
  assert.match(notificationStatus('waiting_for_retry'), /if recalculation fails/);
  assert.equal(notificationStatus(null), '');
});


test('past trips show underway or awaiting return rather than waiting for a new plan', () => {
  const now = '2026-10-28T12:00Z';
  const goal = {kind: 'trip', deadline: '2026-10-28T10:00Z', return_at: '2026-10-28T14:00Z'};
  assert.equal(goalStatus(goal, now), 'Underway');
  assert.equal(goalStatus({...goal, return_at: null}, now), 'Awaiting return');
  assert.equal(goalStatus({...goal, return_at: '2026-10-28T11:00Z'}, now), 'Awaiting return');
  assert.equal(goalStatus({...goal, deadline: '2026-10-28T13:00Z'}, now), 'Waiting');
  assert.equal(goalStatus({...goal, deadline: '2026-10-28T13:00Z', status: 'scheduled'}, now), 'Scheduled');
});


test('journey route failures render an escaped reason and clear it after successful resolution', () => {
  const scroller = {scrollLeft: 0};
  const root = {hidden: true, innerHTML: '', addEventListener() {}, contains: () => false,
    getRootNode: () => ({activeElement: null}),
    querySelector: selector => selector === '.ev-calendar-scroll' ? scroller : null};
  const page = new EVSchedulePage(root, {entities: {}});
  const state = {...syntheticEVStatus(), ...syntheticSchedule(), accepted: null};
  Object.assign(state.policy, {arrival_reserve_km: 30, consumption_kwh_per_100km: 18});
  state.schedule_goals = state.schedule_goals.map(goal => ({distance_km: 44, target_soc_percent: 50, ...goal}));
  const error = 'Route timed out <img src=x onerror=alert(1)> & retry';
  state.routes = {items: [{id: 'journey-synthetic', title: 'SYNTHETIC route', state: 'unresolved',
    error, destination: 'SYNTHETIC venue', arrival: '2026-10-25T17:00Z', venue_departure: '2026-10-25T20:00Z'}]};
  try {
    page.render(state);
    assert.match(root.innerHTML, /Route timed out &lt;img src=x onerror=alert\(1\)&gt; &amp; retry/);
    assert.doesNotMatch(root.innerHTML, /<img src=x/);
    state.routes.items[0] = {...state.routes.items[0], state: 'resolved', provider: 'Google Maps',
      deadline: '2026-10-25T16:29Z', return_at: '2026-10-25T20:30Z', distance_km: 81};
    page.render(state);
    assert.doesNotMatch(root.innerHTML, /Route timed out/);
    assert.match(root.innerHTML, /81\.0 km total/);
  } finally { page.dispose(); }
});


test('session details name allocated trips, distinguish target support and escape goal text', () => {
  const row = {goal_id:'one', title:'Trip <img src=x> & test', deadline:'2026-10-29T07:00Z',
    kind:'trip', energy_kwh:6, target_kwh:8};
  const markup = sessionContributionMarkup({energy_attribution:{method:'existing_charge_first',
    driving:[row, {...row, title:'Second trip', goal_id:'two', energy_kwh:2}],
    targets:[{...row, energy_kwh:8}], stored_kwh:0, unresolved_kwh:0}}, value => value);
  assert.match(markup, /6.00 kWh driving \/ 8.00 kWh target/);
  assert.match(markup, /2.00 kWh driving/);
  assert.equal((markup.match(/<li>/g) || []).length, 2);
  assert.doesNotMatch(markup, /towards|Planned energy use|Existing battery|not additional energy/);
  assert.match(markup, /Trip &lt;img src=x&gt; &amp; test/);
  assert.doesNotMatch(markup, /<img|Contributes to|shared goals/);
});

test('session details keep only compact target rows and brief unknown or legacy fallbacks', () => {
  assert.match(sessionContributionMarkup({}, value => value), /older plan/);
  const markup = sessionContributionMarkup({energy_attribution:{driving:[], targets:[],
    stored_kwh:3, unresolved_kwh:5}}, value => value);
  assert.equal(markup, '<p>Some contributions are unknown.</p>');
  const row = {goal_id:'morning', title:'Morning minimum', deadline:'29 Oct, 07:00', energy_kwh:2.81, target_kwh:23.4};
  const session = {energy_attribution:{driving:[], targets:[row], stored_kwh:2.9, unresolved_kwh:0}};
  const before = JSON.stringify(session);
  const compact = sessionContributionMarkup(session, value => value);
  assert.match(compact, /Morning minimum<\/strong> · 29 Oct, 07:00 — 2.81 kWh<\/li>/);
  assert.doesNotMatch(compact, /23.40|towards|Stored|stored|No driving|Battery targets supported|Contributes to/);
  assert.equal(JSON.stringify(session), before);
});


test('vehicle fault has its own diagnostic/history source and stale reports remain unverified', () => {
  const state = syntheticEVStatus();
  state.charger.vehicle_charging = {configured: true, state: 'FAULT', read_at: state.now,
    issue: null, error: 'Vehicle reports charging FAULT'};
  let model = evStatusModel(state);
  assert.equal(model.tone, 'fault');
  assert.match(model.reason, /Vehicle reports/);
  assert.equal(model.diagnostics.find(f => f.key === 'vehicle_charging').tone, 'error');
  assert.match(evStatusMarkup(state), /data-ev-field="vehicle_charging"/);
  state.now = '2026-10-25T12:01:00Z';
  model = evStatusModel(state);
  assert.equal(model.diagnostics.find(f => f.key === 'vehicle_charging').text, 'Unverified');
  assert.equal(model.diagnostics.find(f => f.key === 'vehicle_charging').tone, 'neutral');
});


test('a restored schedule is current only with matching backend recovery authority', () => {
  const state = syntheticSchedule();
  state.accepted.id = 'saved-plan';
  state.revision++;
  state.plan_recovery = {state: 'restored', plan_id: 'saved-plan', revision: state.revision};
  assert.equal(evSchedule(state).current, true);
  state.plan_recovery.plan_id = 'other-plan';
  assert.equal(evSchedule(state).current, false);
  state.plan_recovery.plan_id = 'saved-plan';
  state.ev_plan_valid = false;
  assert.equal(evSchedule(state).current, false);
});
