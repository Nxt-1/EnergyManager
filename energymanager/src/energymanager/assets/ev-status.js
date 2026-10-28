import {connectionIcon, evFaultText, evIncidentTime, powerText, watts} from './display.js';

const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[char]));
const numeric = value => value !== null && value !== undefined && value !== '' &&
  Number.isFinite(Number(value)) ? Number(value) : null;

export function evMeasuredPower(state) {
  const fresh = at => {
    const age = (Date.parse(state.now) - Date.parse(at)) / 1000;
    return age >= -5 && age <= (state.policy?.measurement_max_age_seconds ?? 30);
  };
  if (!state.demo && state.live_inputs) {
    const reading = state.live_inputs.readings?.ev_kw;
    return reading && (reading.display_current || !reading.issue && fresh(reading.received_at)) ?
      numeric(reading.value) : null;
  }
  const observation = state.observation || {};
  return (state.demo || observation.quality === 'measured') && fresh(observation.at) ?
    numeric(observation.ev_power_kw) : null;
}

export function evControlActivityModel(state, elapsed = 0) {
  const activity = !state.demo && state.charger?.activity;
  if (!activity) return null;
  const age = Math.max(0, (Date.parse(state.now) - Date.parse(activity.as_of)) / 1000) + elapsed;
  if (!Number.isFinite(age) || age > (state.policy?.measurement_max_age_seconds ?? 30))
    return {stage: 'blocked', label: 'Controller status unavailable', detail: 'Waiting for a new system update.',
      tone: 'neutral', seconds: null, offset: 0, step: -1, timerLabel: ''};
  const until = Date.parse(activity.until), total = Number(activity.duration_seconds);
  const remaining = (until - Date.parse(activity.as_of)) / 1000 - age;
  const timed = Number.isFinite(remaining) && total > 0;
  const stages = ['stopping', 'settings', 'settling', 'starting', 'power', 'charging'];
  return {...activity, tone: activity.stage === 'fault' ? 'error' : activity.stage === 'charging' ? 'good' :
    stages.includes(activity.stage) ? 'active' : 'neutral',
    seconds: timed ? Math.max(0, Math.ceil(remaining)) : null,
    offset: timed ? 113.1 * Math.max(0, Math.min(1, remaining / total)) : 0,
    timerLabel: timed && remaining <= 0 ? 'Awaiting control update' : timed ? `${activity.timer} · ${total} s` : '',
    step: stages.indexOf(activity.stage)};
}

function evControlActivityMarkup(state) {
  const model = evControlActivityModel(state);
  if (!model) return '';
  const steps = ['Stop', 'Settings', 'Wait', 'Start', 'Power'];
  const step = Math.min(4, model.step);
  return `<section class="ev-controller ev-controller-${model.tone}" data-ev-control aria-label="EnergyManager EV action">
    <div class="ev-controller-action"><small>EnergyManager</small><strong data-control-label>${esc(model.label)}</strong><p data-control-detail>${esc(model.detail)}</p>
    <ol class="ev-control-steps" aria-label="Restart sequence" ${model.step >= 0 ? '' : 'hidden'}>${steps.map((label, i) => `<li ${i === step ? 'aria-current="step"' : ''}>${label}</li>`).join('')}</ol></div>
    <div class="ev-control-timer" ${model.seconds === null ? 'hidden' : ''}>
      <div class="ev-countdown" role="timer" aria-label="${esc(model.timer)}" aria-live="off">
        <svg viewBox="0 0 44 44" aria-hidden="true"><circle class="ev-countdown-track" cx="22" cy="22" r="18"/><circle data-control-ring cx="22" cy="22" r="18" stroke-dasharray="113.1" stroke-dashoffset="${model.offset}"/></svg>
        <strong data-control-seconds>${model.seconds || '…'}<small>${model.seconds > 0 ? 's' : ''}</small></strong>
      </div><small data-control-timer-label>${esc(model.timerLabel)}</small>
    </div></section>`;
}

// Match the charging/waiting groups used by GoEReadings; permission is not power delivery.
const chargingStates = new Set([3, 7, 8, 9, 10, 11, 12, 13, 14, 15, 19, 20, 33]);
const waitingStates = {
  0: 'No controller data', 2: 'Waiting for authorization', 4: 'Forced stop',
  5: 'Charger schedule', 6: 'Energy limit', 16: 'Charger tariff', 17: 'Charger tariff',
  18: 'Automatic stop', 22: 'Simulated unplugging', 23: 'Phase switching',
  24: 'Minimum charging pause', 27: 'Load management', 28: 'OCPP control',
  29: 'Reconnect delay', 30: 'Adapter blocking', 31: 'Frequency protection',
  32: 'Unbalanced-load protection', 34: 'Grid monitoring', 35: 'OCPP fallback'
};

function diagnosticReadings(healthy, states, connected, vehicle, vehicleHealthy) {
  const field = (key, label, text, tone = 'neutral') => ({key, label, text, tone});
  const coded = (key, label, names, good = [], errors = []) => {
    const code = numeric(states[key]);
    if (!healthy || code === null) return field(key, label, 'Unverified');
    const text = `${names[code] || 'Unknown'} (${code})`;
    return field(key, label, text, errors.includes(code) ? 'error' : good.includes(code) ? 'good' : 'neutral');
  };
  const allowed = healthy ? String(states.charge_allowed ?? '').toLowerCase() : '';
  const chargerCode = numeric(states.charger_status);
  const chargerNames = {...waitingStates, 1: 'Error', 26: 'Overtemperature'};
  if (chargingStates.has(chargerCode)) chargerNames[chargerCode] = 'Charging permitted';
  const error = numeric(states.charger_error);
  return [
    field('connected', 'Cable', connected === null ? 'Unknown' : connected ? 'Connected' : 'Disconnected',
      connected === true ? 'good' : 'neutral'),
    field('charge_allowed', 'Charge allowed', allowed === 'on' ? 'Allowed' : allowed === 'off' ? 'Blocked' : 'Unverified',
      allowed === 'on' ? 'good' : 'neutral'),
    coded('force', 'Force setting', {0: 'Neutral', 1: 'Stop', 2: 'Start'}),
    coded('ev_status', 'Car state', {1: 'No car', 2: 'Charging', 3: 'Waiting', 4: 'Charging complete', 5: 'Error'}, [2, 4], [5]),
    coded('charger_status', 'Charger status', chargerNames, [...chargingStates], [1, 26]),
    field('charger_error', 'Charger error', !healthy || error === null ? 'Unverified' : error === 0 ? 'None (0)' : `Error (${error})`,
      healthy && error !== null ? error > 0 ? 'error' : error === 0 ? 'good' : 'neutral' : 'neutral'),
    ...(vehicle?.configured ? [field('vehicle_charging', 'Vehicle charging',
      !vehicleHealthy ? 'Unverified' : String(vehicle.state), vehicleHealthy && vehicle.error ? 'error' : 'neutral')] : [])
  ];
}

// This is a display projection. Requests and selector settings are not physical measurements.
export function evStatusModel(state) {
  const {observation = {}, policy = {}, capabilities = {}} = state;
  const maximumAge = policy.measurement_max_age_seconds ?? 30;
  const fresh = at => {
    const age = (Date.parse(state.now) - Date.parse(at)) / 1000;
    return age >= -5 && age <= maximumAge;
  };
  const observationKnown = observation.ev_state_known !== false && fresh(observation.at) &&
    (state.demo || observation.quality === 'measured');
  const inputs = state.demo ? null : state.live_inputs;
  const reading = key => {
    const row = inputs?.readings?.[key];
    return row && (row.display_current || !row.issue && fresh(row.received_at)) ? numeric(row.value) : null;
  };
  const power = evMeasuredPower(state);
  const capacity = numeric(capabilities.ev_capacity_kwh);
  const battery = numeric(observation.ev_kwh);
  let soc = inputs ? reading('ev_soc') : observationKnown && battery !== null && capacity > 0 ? battery / capacity * 100 : null;
  if (!(soc >= 0 && soc <= 100)) soc = null;
  const label = inputs?.cards?.ev?.label;
  const connected = inputs ? label === 'Connected' ? true : label === 'Away / disconnected' ? false : null :
    observationKnown && typeof observation.connected === 'boolean' ? observation.connected : null;
  const charger = state.demo ? null : state.charger;
  const states = charger?.states || {};
  const healthy = !!charger && !charger.issue && fresh(charger.at) && fresh(charger.device_at);
  const phaseCode = numeric(states.phase);
  const phase = healthy ? ({1: 1, 2: 3})[phaseCode] ?? null :
    charger && fresh(charger.at) && phaseCode === 0 ? 'auto' : null;
  const current = healthy ? numeric(states.current) : null;
  const command = state.command;
  const commandKnown = !!command && command.generation === state.revision && fresh(command.at);
  const requestedPower = commandKnown ? numeric(command.ev_kw) : null;
  const requestedPhases = commandKnown && command.current_a > 0 && [1, 3].includes(command.phases) ? command.phases : null;
  const incident = state.demo ? null : state.ev_incident;
  const activeIncident = incident && !['recovered', 'acknowledged'].includes(incident.status);
  const recovering = activeIncident && ['pending', 'rebooting', 'verifying'].includes(incident.status);
  const vehicle = charger?.vehicle_charging;
  const vehicleHealthy = vehicle?.configured && !vehicle.issue && fresh(vehicle.read_at);
  const vehicleFault = connected === true && vehicleHealthy && vehicle.error;
  const deviceFault = vehicleFault || healthy && (numeric(states.charger_error) > 0 || numeric(states.ev_status) === 5 ||
    [1, 26].includes(numeric(states.charger_status)));
  const deliveryFault = !state.demo && state.actuator_health?.delivery_fault;
  let status = 'Connected · idle', tone = 'idle';
  if (recovering) { status = 'Recovering'; tone = 'warning'; }
  else if (activeIncident || deviceFault || deliveryFault) { status = 'Fault · attention needed'; tone = 'fault'; }
  else if (connected === false) status = 'Disconnected';
  else if (connected === null || power === null || !state.demo && !healthy) { status = 'Readings unavailable'; tone = 'warning'; }
  else if (power > 0.1) { status = 'Charging'; tone = 'charging'; }
  else if (numeric(states.ev_status) === 4) status = 'Charging complete';
  else if (numeric(states.charger_status) === 4 || numeric(states.force) === 1) status = 'Stopped';
  else if (charger?.waiting || requestedPower > 0) status = 'Waiting to charge';
  const reason = activeIncident ? evFaultText(incident, policy.timezone || 'UTC') :
    vehicleFault || charger?.issue || (deviceFault ? `go-e fault ${states.charger_error} · car ${states.ev_status} · status ${states.charger_status}` :
      charger?.waiting || charger?.control || commandKnown && command.reason || '');
  const summary = recovering ? 'EnergyManager is checking recovery' :
    activeIncident || deviceFault || deliveryFault ? 'EV charging needs attention' :
    status === 'Charging' ? 'Power is reaching the car' :
    status === 'Charging complete' ? 'Car reports charging complete' :
    status === 'Stopped' ? 'Charger is set to stop' :
    status === 'Disconnected' ? 'Car is disconnected' :
    status === 'Readings unavailable' ? 'Charger state cannot currently be verified' :
    status === 'Waiting to charge' ? 'Waiting for charging to start' : 'Car is connected';
  return {soc, power, connected, phase, current, requestedPower, summary,
    diagnostics: diagnosticReadings(healthy, states, connected, vehicle, vehicleHealthy),
    requestedPhases, status, tone, reason, healthy, states, charger,
    flowing: power > 0.1, demo: !!state.demo, controlled: !!state.control_enabled};
}

export function evStatusMarkup(state, interaction = {}) {
  const model = evStatusModel(state);
  const activity = evControlActivityMarkup(state);
  const number = value => value === null ? '—' : String(Math.round(value * 10) / 10);
  const time = value => value ? evIncidentTime(value, state.policy?.timezone || 'UTC') : '—';
  const historyValue = (key, content, label, identity = key) => {
    const entity = !model.demo && interaction.entities?.[key];
    if (entity) return `<button type="button" class="entity-reading" data-entity-key="${esc(key)}" data-ev-history="${esc(identity)}" title="Open ${esc(entity)} in Home Assistant" aria-label="${esc(label)}: open Home Assistant entity history">${content}</button>`;
    const explanation = model.demo ? 'Synthetic demo reading; no Home Assistant history.' :
      interaction.entities ? 'No Home Assistant entity is mapped for this reading.' :
      'Entity history is available in the native Home Assistant dashboard.';
    return `<span title="${explanation}">${content}</span>`;
  };
  const phaseText = model.phase === 'auto' ? 'Auto' : model.phase ? `${model.phase} φ` : '—';
  const selector = !model.demo && state.phase_selector;
  const selectedPhaseText = ({0:'Auto', 1:'1 φ', 2:'3 φ'})[selector?.value] || phaseText;
  const buttons = [['1', '1 φ'], ['2', '3 φ'], ['0', 'Auto']].map(([value, label]) =>
    `<button type="button" data-ev-phase="${value}" aria-label="Set charger phase mode to ${label}" aria-pressed="${selector?.value === value}" ${!selector?.options?.includes(value) || interaction.phaseChanging ? 'disabled' : ''}>${label}</button>`).join('');
  const extraFields = [
    ['Phase selector code', model.states.phase, 'phase'],
    ['Device status age (s)', model.states.heartbeat, 'heartbeat'],
    ['HA read', time(model.charger?.at), null], ['Device frame', time(model.charger?.device_at), null]
  ];
  const diagnostics = model.diagnostics.map(field => {
    const raw = field.key === 'connected' ? null : model.states[field.key];
    const text = field.text === 'Unverified' && raw !== null && raw !== undefined ?
      `Unverified · ${raw}` : field.key === 'charge_allowed' && raw ? `${field.text} (${raw})` : field.text;
    return `<div data-ev-field="${field.key}" class="ev-reading-${field.tone}"><dt>${field.key === 'connected' ? connectionIcon(model.connected) : '<i aria-hidden="true"></i>'}${field.label}</dt><dd>${historyValue(field.key, esc(text), field.label)}</dd></div>`;
  }).join('');
  return `<div class="ev-status-heading"><h2>EV &amp; charger</h2><span class="ev-control-badge">${model.demo ? 'Synthetic demo' : model.controlled ? 'Hardware control on' : 'Hardware control off'}</span></div>
    <div class="ev-status-body ev-tone-${model.tone}">
      <div class="ev-state-label"><i></i><strong>${esc(model.status)}</strong></div>
      ${!activity || ['fault', 'warning'].includes(model.tone) ? `<div class="ev-status-verdict"><strong>${esc(model.summary)}</strong>${model.reason ? `<p class="ev-status-reason">${esc(powerText(model.reason))}</p>` : ''}</div>` : ''}
      ${activity}
      <div class="ev-combined-layout">
      <div class="ev-flow ${model.flowing ? 'ev-flowing' : ''}">
        <svg aria-hidden="true" viewBox="0 0 500 150" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
          <rect class="ev-charger-shell" x="22" y="20" width="72" height="117" rx="12"/><path d="M14 138h89"/>
          <rect x="37" y="36" width="42" height="30" rx="5"/><path class="ev-bolt" d="m61 39-12 13h11l-6 11"/>
          <circle cx="58" cy="90" r="6"/><path d="M94 77h12v22h-12"/>
          <path class="ev-cable" d="M107 87h47c20 0 20 32 40 32h52c18 0 18-32 36-32h28"/>
          <path class="ev-current-flow" d="M107 87h47c20 0 20 32 40 32h52c18 0 18-32 36-32h28"/>
          <path class="ev-car-shell" d="m311 87 22-37q5-9 18-9h62q11 0 18 12l20 34 23 10v24h-23m-103 0h66m-103-21V87h140M349 50l-13 27h87l-15-27z"/>
          <circle cx="330" cy="119" r="17"/><circle cx="433" cy="119" r="17"/>
          <rect class="ev-battery-track" x="350" y="91" width="59" height="14" rx="3" stroke="none"/>
          <rect class="ev-battery-fill" x="350" y="91" width="${model.soc === null ? 0 : 59 * model.soc / 100}" height="14" rx="3" stroke="none"/>
        </svg>
        <div class="ev-annotation ev-on-current"><span>Current limit</span><strong>${historyValue('current', `${number(model.current)} <small>A</small>`, 'Current limit', 'current-limit')}</strong></div>
        <div class="ev-annotation ev-on-power"><span>Measured power</span><strong>${historyValue('ev_kw', `${watts(model.power)} <small>W</small>`, 'Measured power')}</strong></div>
        <div class="ev-annotation ev-on-battery"><span>Battery</span><strong>${historyValue('ev_soc', `${number(model.soc)} <small>%</small>`, 'Battery state of charge')}</strong></div>
        <div class="ev-annotation ev-on-phase"><span>Phase mode · ${historyValue('phase', selectedPhaseText, 'Phase mode', 'phase-mode')}</span><div class="ev-phase-options" role="group" aria-label="Charger phase mode" title="One-time charger change; EnergyManager may overwrite it. Auto is the charger's own phase mode and can leave EV control waiting for a fixed phase readback.">${buttons}</div>${interaction.phaseChanging ? '<small role="status">Sending…</small>' : ''}</div>
        <div class="ev-annotation ev-on-request" title="EnergyManager command intent; no HA sensor history. Not confirmed charger output. Hardware control must be on to apply requests."><span>Controller request</span><strong>${watts(model.requestedPower)} <small>W</small></strong></div>
      </div>
      <dl class="ev-diagnostic-readings">${diagnostics}<div><dt>Current setting</dt><dd>${historyValue('current', `${esc(model.states.current ?? '—')} A${!model.healthy ? ' · unverified' : ''}`, 'Current setting', 'current-setting')}</dd></div>${extraFields.map(([label, value, key]) => `<div><dt>${label}</dt><dd class="ev-reading-${label === 'Device frame' && model.healthy ? 'good' : 'neutral'}">${key ? historyValue(key, esc(value ?? '—'), label, 'detail-' + key) : `<span title="EnergyManager ${label === 'HA read' ? 'input read' : 'validated device frame'} timestamp; no HA sensor history.">${esc(value ?? '—')}</span>`}${!model.healthy ? ' · unverified' : ''}</dd></div>`).join('')}</dl>
      </div>
      ${interaction.phaseError ? `<p class="error" role="alert">${esc(interaction.phaseError)}</p>` : ''}
      ${model.requestedPhases && model.requestedPhases !== model.phase ? `<p class="subtle">Requested phase mode: ${model.requestedPhases} φ · awaiting readback</p>` : ''}
    </div>`;
}
