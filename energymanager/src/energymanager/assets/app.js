import {SettingsPage} from './settings.js';
import {powerText, watts} from './display.js';
import {DateTimePicker} from './datetime-picker.js';

const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;'
} [char]));
let state, page = 'overview',
  offset = 0,
  loading = false,
  pointerUntil = 0,
  hardwareChanging = false,
  hardwareIntent = false,
  hardwareError = null;
const colors = {
  grid: '#dc2626',
  ess: '#007ac2',
  solar: '#e4ac19',
  house: '#8c65c8',
  ev: '#16a34a'
};
const num = (value, places = 2) => value !== null && value !== undefined && Number.isFinite(Number(value)) ?
  Number(value).toFixed(places) : '—';
const money = value => `€ ${num(value)}`;
const time = (value, date = true) => new Date(value).toLocaleString('en-GB', {
  timeZone: state?.policy.timezone || 'Europe/Brussels',
  ...(date ? {
    day: '2-digit',
    month: 'short'
  } : {}),
  hour: '2-digit',
  minute: '2-digit'
});
async function api(path, method = 'GET', body) {
  const response = await fetch(`./api/${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      'X-EnergyManager': '1'
    },
    ...(body === undefined ? {} : {
      body: JSON.stringify(body)
    })
  });
  const result = await response.json();
  if (!response.ok) {
    const error = new Error(result.error || `Request failed: ${response.status}`);
    error.fields = result.errors;
    throw error;
  }
  return result;
}
const settingsPage = new SettingsPage($('settings-panel'), api);
const dateTimePicker = new DateTimePicker(() => state.policy.timezone, () => state.now);
dateTimePicker.bind($('goal-form').elements.deadline, 'Deadline / departure', true);
dateTimePicker.bind($('goal-form').elements.return_at, 'Return time');

function range() {
  const now = Date.parse(state.now);
  if (page === 'planning') return [state.accepted ? Date.parse(state.accepted.intervals[0].start) : now, state
    .accepted ? Date.parse(state.accepted.intervals.at(-1).end) : now + 168 * 3600000
  ];
  return [now - 6 * 3600000 + offset * 3600000, now + 18 * 3600000 + offset * 3600000];
}

function points(series, soc = false) {
  const capabilities = state.capabilities;
  const plan = state.accepted;
  const planned = [];
  if (plan) {
    const flows = plan.flows;
    for (const [index, interval] of plan.intervals.entries()) {
      let value;
      if (soc) {
        const evKnown = interval.ev_state_known !== false;
        value = series === 'ev' ?
          (evKnown ? flows.ev_energy[index] / capabilities.ev_capacity_kwh * 100 : null) :
          (flows.ess_solar[index] + flows.ess_grid[index] + capabilities.ess_min_kwh) / capabilities
          .ess_capacity_kwh * 100;
      } else {
        const powers = {
          grid: flows.grid_ev[index] + flows.grid_house[index] + flows.grid_store[index] - flows.export[
            index],
          ess: flows.solar_dis_ev[index] + flows.solar_dis_house[index] + flows.grid_dis_house[index] -
            flows.pv_store[index] - flows.grid_store[index],
          solar: interval.pv_ac_kw + interval.pv_dc_kw,
          house: interval.house_kw,
          ev: flows.pv_ev[index] + flows.grid_ev[index] + flows.solar_dis_ev[index]
        };
        value = powers[series] * 1000;
      }
      planned.push([Date.parse(interval.start), value]);
      if (!soc) planned.push([Date.parse(interval.end), value]);
    }
    if (soc && plan.intervals.length) {
      const last = plan.intervals.at(-1);
      const value = series === 'ev' ?
        (last.ev_state_known !== false ? flows.ev_energy.at(-1) / capabilities.ev_capacity_kwh * 100 : null) :
        (flows.ess_solar.at(-1) + flows.ess_grid.at(-1) + capabilities.ess_min_kwh) / capabilities
        .ess_capacity_kwh * 100;
      planned.push([Date.parse(last.end), value]);
    }
  }
  const observed = state.observed.filter(observation =>
    observation.quality === (state.demo ? 'SYNTHETIC' : 'measured')).map(observation => {
    let value;
    if (soc) {
      value = series === 'ev' ?
        (observation.ev_state_known !== false ? observation.ev_kwh / capabilities.ev_capacity_kwh * 100 :
          null) :
        observation.ess_kwh / capabilities.ess_capacity_kwh * 100;
    } else {
      value = {
        grid: observation.house_kw + observation.ev_power_kw - observation.pv_ac_kw - observation
          .ess_power_kw,
        ess: observation.ess_power_kw,
        solar: observation.pv_ac_kw + observation.pv_dc_kw,
        house: observation.house_kw,
        ev: observation.ev_power_kw
      } [series] * 1000;
    }
    return [Date.parse(observation.at), value];
  });
  return {
    planned,
    observed
  };
}

function chart(soc = false) {
  const [start, end] = range(), names = soc ? ['ess', 'ev'] : ['grid', 'ess', 'solar', 'house', 'ev'];
  const series = names.map(name => ({
    name,
    ...points(name, soc)
  }));
  const visible = series.flatMap(s => [...s.planned, ...s.observed]).filter(p => p[0] >= start && p[0] <=
    end && p[1] !== null);
  let low = soc ? 0 : Math.min(0, ...visible.map(p => p[1])),
    high = soc ? 100 : Math.max(1000, ...visible.map(p => p[1]));
  if (!soc) {
    low = Math.floor(low);
    high = Math.ceil(high * 1.1 / 100) * 100;
  }
  const width = Math.max(280, $(soc ? 'soc' : 'power').clientWidth || 1000),
    height = 255,
    left = soc ? 48 : 58,
    right = 15,
    top = 12,
    bottom = 32;
  const x = value => left + (value - start) / (end - start) * (width - left - right);
  const y = value => height - bottom - (value - low) / (high - low) * (height - top - bottom);
  let svg =
    `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${soc?'Battery state of charge':'Power'} chart, ${esc(time(start))} to ${esc(time(end))}">`;
  for (let tick = 0; tick <= 4; tick++) {
    const value = low + (high - low) * tick / 4,
      pos = y(value);
    svg +=
      `<line class="grid" x1="${left}" x2="${width-right}" y1="${pos}" y2="${pos}"/><text class="axis" x="${left-9}" y="${pos+4}" text-anchor="end">${num(value, 0)}</text>`;
  }
  const timeTicks = width < 550 ? 2 : 4;
  for (let tick = 0; tick <= timeTicks; tick++) {
    const at = start + (end - start) * tick / timeTicks;
    svg +=
      `<text class="axis" x="${x(at)}" y="${height-8}" text-anchor="${tick===0?'start':tick===timeTicks?'end':'middle'}">${esc(time(at,page==='planning'))}</text>`;
  }
  for (const s of series)
    for (const kind of ['planned', 'observed']) {
      const data = s[kind].filter(p => p[0] >= start && p[0] <= end);
      if (!data.length) continue;
      let d = '',
        penLifted = true;
      for (const point of data) {
        if (point[1] === null) {
          penLifted = true;
          continue;
        }
        d += `${penLifted ? 'M' : 'L'}${num(x(point[0]),1)},${num(y(point[1]),1)} `;
        penLifted = false;
      }
      svg +=
        `<path d="${d}" fill="none" stroke="${colors[s.name]}" stroke-width="${kind==='observed'?2.8:1.8}" ${kind==='planned'?'stroke-dasharray="6 4" opacity=".85"':''}><title>${esc(s.name)} · ${kind}</title></path>`;
    }
  const now = Date.parse(state.now);
  if (now >= start && now <= end) svg +=
    `<line x1="${x(now)}" x2="${x(now)}" y1="${top}" y2="${height-bottom}" stroke="#718697" stroke-dasharray="3 3"/>`;
  return svg + '</svg>';
}

function viewLocked() {
  return $('goal-dialog').open || $('detail-dialog').open || Date.now() < pointerUntil;
}

function renderHardware() {
  $('hardware-controls').hidden = page !== 'overview';
  const hardware = state.hardware_control;
  $('hardware-toggle').checked = hardwareChanging ? hardwareIntent : !!hardware?.requested;
  $('hardware-toggle').disabled = hardwareChanging || (!hardware?.requested && !hardware?.can_enable);
  $('hardware-status').textContent = hardwareChanging ? 'Applying…' : hardwareError || hardware?.reason ||
    (hardware?.enabled ? 'On' : 'Off');
}

function render() {
  if (!state) return;
  renderHardware();
  if (viewLocked()) return;
  $('app-version').textContent = ` ${state.version}`;
  document.title = `EnergyManager · ${state.version}`;
  $('dashboard').hidden = page === 'settings';
  $('settings-panel').hidden = page !== 'settings';
  for (const name of ['overview', 'planning', 'settings']) {
    $(name).setAttribute('aria-selected', String(page === name));
  }
  $('connection').textContent = state.status === 'planning' ? '● Calculating · control responsive' : state
    .status === 'ready' ? '● Plan ready' : '● ' + state.status;
  document.querySelector('footer').textContent =
    `${state.control_enabled ? 'Hardware control enabled' : 'Hardware control disabled'} / Forecasts and planned costs are estimates.`;
  document.body.classList.toggle('planning', page === 'planning');
  if (page === 'settings') return;
  const o = state.observation,
    c = state.capabilities,
    plan = state.accepted;
  $('page-title').textContent = page === 'overview' ? 'Overview' : 'Planning';
  const [start, end] = range();
  $('period').textContent = `${time(start)} — ${time(end)} · ${state.policy.timezone}`;
  $('power-title').textContent = page === 'planning' ? '7 days · Power · actual / planned · W' :
    'Power · actual / planned · W';
  $('navigation').hidden = page === 'planning';
  $('provenance').textContent =
    `${state.provenance} · ${state.demo?'Deterministic local demonstration':'Configured inputs'} · ${state.control_enabled ? 'Hardware control enabled' : 'Hardware control disabled'}`;
  const live = [
    ['Grid', o.house_kw + o.ev_power_kw - o.pv_ac_kw - o.ess_power_kw, 'W', 'Quarter-hour import ' + num(o
      .quarter_import_kwh) + ' kWh', 'grid'],
    ['Solar', o.pv_ac_kw + o.pv_dc_kw, 'W', `AC ${watts(o.pv_ac_kw)} W · DC ${watts(o.pv_dc_kw)} W`, 'solar'],
    ['House', o.house_kw, 'W', 'Uncontrolled demand', 'house'],
    ['ESS', o.ess_kwh / c.ess_capacity_kwh * 100, '%',
      `Minimum ${num(c.ess_min_kwh/c.ess_capacity_kwh*100,0)}% · ${watts(o.ess_power_kw)} W`, 'ess'
    ],
    ['EV', o.ev_state_known === false ? null : o.ev_kwh / c.ev_capacity_kwh * 100, '%', o.ev_state_known ===
      false ? 'State unknown / charging held' : o.connected ? 'Connected' : 'Away / disconnected', 'ev'
    ]
  ];
  const measurementAge = (Date.parse(state.now) - Date.parse(o.at)) / 1000;
  const liveKnown = state.demo || o.quality === 'measured' && measurementAge >= -5 &&
    measurementAge <= state.policy.measurement_max_age_seconds;
  $('live').innerHTML = live.map(([name, value, unit, label, key]) => {
    let issues = [];
    if (!state.demo && state.live_inputs) {
      const reading = state.live_inputs.cards[key];
      value = reading?.value ?? null;
      label = reading?.label || 'Waiting for live input';
      issues = reading?.issues || [];
      const inputs = state.live_inputs.readings;
      if (key === 'solar' && inputs.pv_ac_kw && inputs.pv_dc_kw)
        label = `AC ${watts(inputs.pv_ac_kw.value)} W · DC ${watts(inputs.pv_dc_kw.value)} W`;
      if (key === 'ess' && inputs.ess_kw)
        label = `Minimum ${num(c.ess_min_kwh/c.ess_capacity_kwh*100,0)}% · ${watts(inputs.ess_kw.value)} W`;
    } else if (!liveKnown) { value = null; label = 'Waiting for live input'; }
    return     `<article class="live-item"><span class="muted">${name}</span><strong style="color:${colors[key]}">${unit==='W'?watts(value):num(value,0)} <small style="display:inline;font-size:13px">${unit}</small></strong><small>${esc(label)}</small>${issues.map(issue=>`<small class="error">${esc(powerText(issue))}</small>`).join('')}${unit==='%' && value !== null ?`<div class="meter"><i style="width:${Math.max(0,Math.min(100,value))}%;background:${colors[key]}"></i></div>`:''}</article>`;
  }).join('');
  $('status').innerHTML =
    `<p class="status-line">${plan?`Plan updated ${time(plan.intervals[0].start)} · ${plan.summary.intervals} intervals · ${num(plan.seconds,1)} s calculation`:'Waiting for the first validated joint plan. The independent control loop is running.'}${state.actuator_health?.delivery_fault ? '<span class="error"> / EV delivery fault: stopped; diagnose before restart</span>' : ''}${state.error?` · <span class="error">${esc(powerText(state.error))}</span>`:''}</p>`;
  $('power').innerHTML = chart();
  $('soc').innerHTML = chart(true);
  const sessions = plan?.sessions || [];
  $('timeline').innerHTML = ['ev', 'ess'].map(resource =>
      `<small>${resource.toUpperCase()}</small><div class="timeline-track">${sessions.filter(s=>s.resource===resource&&Date.parse(s.end)>start&&Date.parse(s.start)<end).map(s=>{const left=Math.max(start,Date.parse(s.start)),right=Math.min(end,Date.parse(s.end));return `<button class="timeline-run" data-session="${esc(s.id)}" style="background:${colors[resource]};left:${(left-start)/(end-start)*100}%;width:${(right-left)/(end-start)*100}%" title="${esc(s.title)} / ${esc(time(s.start))}" aria-label="${resource.toUpperCase()} session ${esc(time(s.start))}"></button>`}).join('')}</div>`
    ).join('') +
    `<div class="timeline-labels"><span>${time(start)}</span><span>${sessions.length} grouped sessions</span><span>${time(end)}</span></div>`;
  const goals = [...state.goals.map(g => ({
    ...((plan?.goals || []).find(p => p.id === g.id && p.revision === g.revision) || {}),
    ...g
  })), ...(plan?.goals || []).filter(g => g.kind === 'daily')];
  const goalCard = g =>
    `<section class="goal"><div class="goal-title"><strong>${esc(g.title)}</strong><span class="badge ${g.shortfall_kwh>0.001?'warning':''}">${g.shortfall_kwh>0.001?'Shortfall':g.status==='scheduled'?'Scheduled':g.status==='unknown_return_state'?'Unknown state':'Waiting'}</span></div><p>${time(g.deadline)} · ${g.kind==='trip'?num(g.distance_km,0)+' km total / '+num((g.target_kwh ?? Math.min(c.ev_capacity_kwh,(g.distance_km+state.policy.arrival_reserve_km)*state.policy.consumption_kwh_per_100km/100))/c.ev_capacity_kwh*100,0)+'% departure target':num(g.target_soc_percent,0)+'% SoC'}</p><p>${g.planned_kwh!==undefined&&g.planned_kwh!==null?num(g.planned_kwh/c.ev_capacity_kwh*100,1)+'% planned · ':''}${g.shortfall_kwh>.001?num(g.shortfall_kwh)+' kWh shortfall':'One shared battery trajectory'}</p>${g.completion_margin_minutes !== undefined && g.completion_margin_minutes !== null ? `<p>${g.desired_margin_met ? `Ready at least ${state.policy.completion_margin_minutes} min early` : `Limited completion margin / ${num(g.completion_margin_minutes,0)} min`}</p>` : ''}${g.external_charging_required?'<p class="error">Charging away must be arranged. Return SoC is unknown.</p>':''}<div class="meter"><i style="width:${Math.min(100,o.ev_kwh/(g.target_kwh||c.ev_capacity_kwh*g.target_soc_percent/100||1)*100)}%;background:#16a34a"></i></div><div class="actions"><button data-detail="${esc(g.id)}">Details</button>${g.kind!=='daily'?`<button data-edit="${esc(g.id)}">Edit</button><button data-delete="${esc(g.id)}">Remove</button>`:''}</div></section>`;
  const dailyGoals = goals.filter(goal => goal.kind === 'daily');
  const primaryGoals = goals.filter(goal => goal.kind !== 'daily' || goal.id === dailyGoals[0]?.id);
  const laterDaily = dailyGoals.slice(1);
  $('goals').innerHTML = primaryGoals.map(goalCard).join('') + (laterDaily.length ?
    `<details><summary>${laterDaily.length} later morning requirements</summary>${laterDaily.map(goalCard).join('')}</details>` :
    '');
  if (!goals.length) $('goals').innerHTML = '<p class="empty">Add a journey or timed SoC goal.</p>';
  $('approvals').innerHTML = state.issues.length ? state.issues.map(i =>
    `<section class="issue"><strong>${esc(i.title||goals.find(g=>g.id===i.goal_id)?.title||'EV goal')}</strong><p>${esc(powerText(i.text))}</p><p>${i.kind==='ess_peak'?'Specific forecast peak':i.shortfall_kwh===null?'Awaiting measured reconnection':num(i.shortfall_kwh)+' kWh short'} · ${esc(i.state)}</p>${i.proposed_peak_kw && i.state === 'pending'?`<p>Requested ceiling ${watts(i.proposed_peak_kw)} W</p><button data-approve="${esc(i.goal_id)}">Approve</button> <button data-reject="${esc(i.goal_id)}">Reject</button>`:''}</section>`
  ).join('') : '<p class="empty">No pending permission decisions.</p>';
  if (plan) {
    const v = plan.summary;
    $('costs').innerHTML = [
        ['Import electricity', money(v.import_cost_eur)],
        ['Export income', '− ' + money(v.export_income_eur)],
        ['Additional capacity cost', money(v.capacity_cost_eur)],
        ['Predicted bill', money(v.predicted_bill_eur), 'total'],
        ['Stored energy value change', money(v.inventory_change_eur), 'asset'],
        ['Comparison including energy assets', money(v.comparison_eur), 'total']
      ].map(([a, b, cls = '']) => `<div class="money ${cls}"><span>${a}</span><span>${b}</span></div>`).join(
        '') +
      `<p class="subtle">Seven-day forecast. Stored value is an assumption, not realized savings. Peak ${watts(v.peak_kw)} W.</p>`;
  } else $('costs').innerHTML = '<p class="empty">Costs appear after independent plan validation.</p>';
  $('reasons').innerHTML = (plan?.reasons || []).map(r => `<p>${esc(powerText(r.text))}</p>`).join('') ||
    '<p>Required goals establish the charging need. Source and peak permissions remain binding.</p>';
  $('sessions').innerHTML = sessions.map((s, t) =>
    `<div class="session"><button data-session="${esc(s.id)}"><strong>${esc(s.title)} · ${time(s.start)} — ${time(s.end)}</strong><br><small>${num(s.energy_kwh)} kWh battery energy · ${esc(powerText(s.reason))}</small></button>${(() => {const next=sessions.slice(t+1).find(other=>other.resource===s.resource);return next ? `<small>Resumes ${time(next.start)}<br>Pause ${num((Date.parse(next.start)-Date.parse(s.end))/3600000,1)} h</small>` : ''})()}</div>`
  ).join('') || '<p class="empty">No charging sessions selected.</p>';
  $('evidence').innerHTML =
    `<p>Control response observed locally: ${num(state.control_max_seconds*1000,2)} ms maximum. This is not hardware latency.</p>${plan?`<pre>${esc(JSON.stringify({status:plan.status,stages:plan.stages,input_digest:plan.input_digest},null,2))}</pre>`:''}`;
}

function openGoal(goal) {
  const form = $('goal-form');
  form.reset();
  form.elements.id.value = goal?.id || '';
  form.elements.title.value = goal?.title || '';
  form.elements.kind.value = goal?.kind || 'manual';
  form.elements.target_soc_percent.value = goal?.target_soc_percent ?? 70;
  form.elements.distance_km.value = goal?.distance_km || 120;
  dateTimePicker.setValue(form.elements.deadline, goal?.deadline || new Date(Date.parse(state.now) + 24 * 3600000).toISOString());
  dateTimePicker.setValue(form.elements.return_at, goal?.return_at || null);
  form.elements.priority.value = goal?.priority ?? 50;
  $('form-title').textContent = goal ? 'Edit EV goal' : 'Add an EV goal';
  $('form-error').textContent = '';
  toggleKind();
  $('goal-dialog').showModal();
}

function toggleKind() {
  const trip = $('goal-form').elements.kind.value === 'trip';
  $('soc-field').hidden = trip;
  $('distance-field').hidden = !trip;
  $('return-field').hidden = !trip
}

function detail(title, body) {
  $('detail-body').innerHTML = `<h2>${esc(title)}</h2>${body}`;
  $('detail-dialog').showModal()
}
async function refresh() {
  if (loading) return;
  loading = true;
  try {
    const nextState = await api('state');
    // Keep click targets and their backing records on the same displayed revision.
    if (!viewLocked()) {
      state = nextState;
      render()
    }
  } catch (error) {
    $('connection').textContent = 'Connection unavailable';
    $('status').textContent = error.message
  } finally {
    loading = false
  }
}
document.addEventListener('pointerdown', () => {
  pointerUntil = Date.now() + 350
});
function showPage(name) {
  pointerUntil = 0;
  page = name;
  history.replaceState(null, '', `#${name}`);
  render();
  if (name === 'settings') settingsPage.show();
}
for (const name of ['overview', 'planning', 'settings']) $(name).onclick = () => showPage(name);
$('back').onclick = () => {
  pointerUntil = 0;
  offset -= 12;
  render()
};
$('forward').onclick = () => {
  pointerUntil = 0;
  offset += 12;
  render()
};
$('now').onclick = () => {
  pointerUntil = 0;
  offset = 0;
  render()
};
$('new-goal').onclick = () => openGoal();
$('close-dialog').onclick = $('cancel-dialog').onclick = () => $('goal-dialog').close();
$('close-detail').onclick = () => $('detail-dialog').close();
$('goal-form').elements.kind.onchange = toggleKind;
$('goal-form').onsubmit = async event => {
  event.preventDefault();
  const f = event.target.elements;
  try {
    const body = {
      title: f.title.value,
      kind: f.kind.value,
      target_soc_percent: Number(f.target_soc_percent.value),
      deadline: dateTimePicker.instant(f.deadline),
      priority: Number(f.priority.value)
    };
    if (f.id.value) body.id = f.id.value;
    if (body.kind === 'trip') {
      body.distance_km = Number(f.distance_km.value);
      body.return_at = dateTimePicker.instant(f.return_at)
    }
    await api('goals', 'POST', body);
    $('goal-dialog').close();
    pointerUntil = 0;
    await refresh()
  } catch (error) {
    $('form-error').textContent = error.message
  }
};
$('hardware-toggle').onchange = async event => {
  hardwareIntent = event.target.checked;
  hardwareChanging = true;
  hardwareError = null;
  render();
  try {
    await api('control', 'POST', {enabled: hardwareIntent});
  } catch (error) {
    hardwareError = error.message;
  } finally {
    hardwareChanging = false;
    await refresh();
  }
};
$('refresh').onclick = async () => {
  try {
    await api('replan', 'POST', {});
    await refresh()
  } catch (error) {
    $('status').textContent = error.message
  }
};
document.addEventListener('click', async event => {
  const button = event.target.closest('button');
  if (!button || !state) return;
  try {
    if (button.dataset.edit) openGoal(state.goals.find(g => g.id === button.dataset.edit));
    if (button.dataset.delete) {
      await api(`goals/${encodeURIComponent(button.dataset.delete)}`, 'DELETE', {});
      pointerUntil = 0;
      await refresh()
    }
    if (button.dataset.detail) {
      const g = state.goals.find(g => g.id === button.dataset.detail) || (state.accepted?.goals || [])
        .find(g => g.id === button.dataset.detail);
      detail(g.title,
        `<p>Deadline ${time(g.deadline)}</p><p>${g.kind==='trip'?`Total journey ${num(g.distance_km,0)} km, arrival reserve ${state.policy.arrival_reserve_km} km. ${g.return_at?'Expected return '+time(g.return_at):'Return unknown; unavailable until reconnection.'}`:'Timed state-of-charge requirement. No journey or withdrawal is assumed.'}</p><p>Priority ${g.priority}. ${g.approval_state==='granted'?'Approved task ceiling '+watts(g.approved_peak_kw)+' W':'Normal automatic peak policy applies.'}</p><p>Power changes stay within grouped charging sessions.</p>`
      )
    }
    if (button.dataset.session) {
      const s = state.accepted.sessions.find(s => s.id === button.dataset.session);
      detail(s.title,
        `<p>${time(s.start)} — ${time(s.end)}</p><p>${num(s.energy_kwh)} kWh to the battery</p><p>${esc(powerText(s.reason))}</p><p>${s.resource === "ev" ? `Contributes to ${s.goal_ids.length} shared goals. Energy is counted once.` : "Source-specific reservations preserve required EV and household peak support."}</p>`
      )
    }
    if (button.dataset.approve || button.dataset.reject) {
      const id = button.dataset.approve || button.dataset.reject;
      const issue = state.issues.find(i => i.goal_id === id);
      await api(`goals/${encodeURIComponent(id)}/approval`, 'POST', {
        state: button.dataset.approve ? 'granted' : 'rejected',
        peak_kw: issue.proposed_peak_kw,
        revision: issue.revision
      });
      pointerUntil = 0;
      await refresh()
    }
  } catch (error) {
    $('status').textContent = error.message
  }
});
$('history').onclick = async () => {
  try {
    const rows = await api('decisions');
    $('history-list').innerHTML = rows.map(r =>
      `<p><button data-decision="${esc(r.id)}">${time(r.at)} · ${esc(r.disposition)}</button> ${money(r.summary.comparison_eur)} comparison</p>`
    ).join('')
  } catch (error) {
    $('status').textContent = error.message
  }
};
$('history-list').onclick = async event => {
  const b = event.target.closest('[data-decision]');
  if (b) {
    const d = await api(`decisions/${encodeURIComponent(b.dataset.decision)}`);
    detail('Persisted decision',
      `<p>${esc(d.disposition)} · ${esc(d.snapshot.provenance)}</p><pre>${esc(JSON.stringify({summary:d.result.summary,reasons:d.result.reasons,digest:d.digest},null,2))}</pre>`
    )
  }
};
page = ['#planning', '#settings'].includes(location.hash) ? location.hash.slice(1) : 'overview';
await refresh();
if (page === 'settings') await settingsPage.show();
setInterval(refresh, 2000);
