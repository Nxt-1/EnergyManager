import {
  SettingsPage
} from './settings.js';
import {
  powerText,
  monthlyPeakWatts,
  watts,
  dailyEnergyRows,
  connectionIcon,
  evFaultText,
  evIncidentTime,
  notificationStatus
} from './display.js';
import {
  DateTimePicker
} from './datetime-picker.js';
import {
  EVSchedulePage
} from './ev-schedule.js';
import {GraphHistory, historyDayRange, observedPoints} from './graph-history.js';
import {GraphCursor, plotInsets, clipSeries} from './graph-cursor.js';
import {requestError, StatePoller} from './dashboard-client.js';
import {hasTextSelection, clearTextSelection} from './text-selection.js';


export async function mountApplication(root, options = {}) {
  const lifecycle = new AbortController();
  const $ = id => root.querySelector(`#${id}`);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  } [char]));
  let state, backendState, page = options.page || 'overview',
    offset = 0,
    loading = false,
    pointerHeld = false,
    pointerUntil = 0,
    hardwareChanging = false,
    hardwareIntent = false,
    hardwareError = null;
  let dailyEnergy = null, energyRequestedAt = 0, energyDay = null, energyLoading = false;
  const graphModels = {};
  let incidentReport = null;
  let selectedRange = null;
  let connectionError = null;
  const statePoller = new StatePoller(api);
  const graphHistory = new GraphHistory(api, () => {
    if (state && !viewLocked() && ['overview', 'planning'].includes(page)) renderCharts();
  });
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
  const notificationText = value => value === 'delivered' ? 'sent to Home Assistant' : value;
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
    try {
      if (options.api) return await options.api(path, method, body);
      const response = await fetch(`./api/${path}`, {
        method,
        signal: AbortSignal.timeout(15000),
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
    } catch (error) {
      throw requestError(error, path, method);
    }
  }
  const settingsPage = new SettingsPage($('settings-panel'), api, lifecycle.signal);
  const evPage = new EVSchedulePage($('ev-panel'), {
    add: kind => openGoal(null, kind),
    edit: id => openGoal(state.goals.find(goal => goal.id === id)),
    goal: id => showGoalDetail(id),
    session: id => showSessionDetail(id),
    remove: async id => {
      await api(`goals/${encodeURIComponent(id)}`, 'DELETE', {});
      pointerUntil = 0;
      await refresh(true);
    },
    settings: () => showPage('settings'),
    phase: options.setPhase,
    sync: async () => {
      await api('calendars/sync', 'POST', {});
      pointerUntil = 0;
      await refresh(true);
    },
    replan: async () => {
      await api('replan', 'POST', {});
      pointerUntil = 0;
      await refresh(true);
    }
  });
  const dateTimePicker = new DateTimePicker(() => state.policy.timezone, () => state.now, root);
  dateTimePicker.bind($('goal-form').elements.deadline, 'Deadline / departure', true);
  dateTimePicker.bind($('goal-form').elements.return_at, 'Return time');
  const graphCursor = new GraphCursor(root, at => new Date(at).toLocaleString('en-GB', {
    timeZone: state.policy.timezone, day: '2-digit', month: 'short',
    hour: '2-digit', minute: '2-digit', second: '2-digit', timeZoneName: 'shortOffset'
  }), colors, lifecycle.signal, {
    enabled: () => page === 'overview',
    changed: (nextRange, finished) => {
      selectedRange = nextRange;
      $('history-date').value = '';
      if (finished) { pointerHeld = false; pointerUntil = 0; }
      renderTimeRange(finished);
    }
  });
  const charts = root.querySelector('.charts');
  charts.style.setProperty('--plot-left', `${plotInsets.left}px`);
  charts.style.setProperty('--plot-right', `${plotInsets.right}px`);
  let chartWidth = 0;
  const resizeObserver = new ResizeObserver(entries => {
    const width = entries[0].contentRect.width;
    if (Math.abs(width - chartWidth) < 0.5) return;
    chartWidth = width;
    if (!lifecycle.signal.aborted && state && !viewLocked() && ['overview', 'planning'].includes(page)) renderCharts();
  });
  resizeObserver.observe(charts);
  lifecycle.signal.addEventListener('abort', () => resizeObserver.disconnect(), {once: true});

  function range() {
    const now = Date.parse(state.now);
    if (page === 'planning') return [state.accepted ? Date.parse(state.accepted.intervals[0].start) : now, state
      .accepted ? Date.parse(state.accepted.intervals.at(-1).end) : now + 168 * 3600000
    ];
    if (selectedRange) return selectedRange;
    return [now - 2 * 3600000 + offset * 3600000, now + 4 * 3600000 + offset * 3600000];
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
              flows.pv_store[index] - flows.grid_store[index] +
              (flows.dc_invert?.[index] || 0) * capabilities.ac_discharge_efficiency,
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
    const observed = observedPoints(state, graphHistory.data, series, soc);
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
    for (const item of series) for (const kind of ['observed', 'planned'])
      item[kind] = clipSeries(item[kind], start, end);
    const visible = series.flatMap(s => [...s.planned, ...s.observed]).filter(p => p[0] >= start && p[0] <=
      end && p[1] !== null);
    const peak = !soc && page === 'overview' ? monthlyPeakWatts(state) : null;
    let low = soc ? 0 : Math.min(0, ...visible.map(p => p[1])),
      high = soc ? 100 : Math.max(1000, peak ?? 0, ...visible.map(p => p[1]));
    if (!soc) {
      low = Math.floor(low);
      high = Math.ceil(high * 1.1 / 100) * 100;
    }
    const width = $(soc ? 'soc' : 'power').clientWidth || 1000,
      height = soc ? 255 : 360;
    const {left, right, top, bottom} = plotInsets;
    graphModels[soc ? 'soc' : 'power'] = {start, end, width, height, low, high, series, now: Date.parse(state.now)};
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
    if (!soc && page === 'overview') {
      const label = peak === null ? 'Monthly peak unavailable' : `Month peak · ${Math.round(peak)} W`;
      const month = new Intl.DateTimeFormat('en-GB', {timeZone: state.policy.timezone, month: 'short', year: 'numeric'}).format(new Date(state.now));
      const description = peak === null ? 'Current recorded monthly capacity peak unavailable.' :
        `${state.demo ? 'Synthetic demo: ' : ''}Current recorded ${month} grid-import peak: ${Math.round(peak)} W, a 15-minute average, not instantaneous power, forecast peak or permission limit.`;
      svg += `<desc>${esc(description)}</desc>`;
      if (peak !== null) svg += `<line class="monthly-peak-line" data-peak-watts="${peak}" x1="${left}" x2="${width-right}" y1="${y(peak)}" y2="${y(peak)}"><title>${esc(description)}</title></line>`;
      svg += `<text class="monthly-peak-label" x="${width-right-4}" y="${peak === null ? top+15 : Math.max(top+15,y(peak)-7)}" text-anchor="end"><title>${esc(description)}</title>${esc(label)}</text>`;
    }
    return svg + '<g class="cursor-overlay" pointer-events="none"></g></svg><div class="cursor-values" role="status" hidden></div>';
  }

  function viewLocked() {
    const copyField = $('connection-error-copy');
    return $('goal-dialog').open || $('detail-dialog').open || pointerHeld || graphCursor.interacting ||
      Date.now() < pointerUntil || hasTextSelection(root) ||
      (!copyField.hidden && (root.activeElement || document.activeElement) === copyField);
  }

  function renderConnectionError() {
    if (viewLocked()) return;
    const message = $('connection-error-message');
    const text = connectionError ? `${connectionError.at} · ${connectionError.message} Automatic retry will continue.` : '';
    if (message.textContent !== text) {
      message.textContent = text;
      $('copy-connection-error').textContent = 'Copy error';
      $('connection-error-copy').hidden = true;
    }
    $('connection-error').hidden = !connectionError;
    const legacyError = root.querySelector('#native-error');
    if (legacyError) legacyError.textContent = '';
  }

  $('copy-connection-error').onclick = async () => {
    const text = $('connection-error-message').textContent;
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard requires a secure connection');
      await navigator.clipboard.writeText(text);
      $('copy-connection-error').textContent = 'Copied';
    } catch {
      const field = $('connection-error-copy');
      field.value = text;
      field.hidden = false;
      field.focus();
      field.select();
      $('copy-connection-error').textContent = 'Selected — copy with your device';
    }
  };

  function renderCharts() {
    $('power').innerHTML = chart();
    $('soc').innerHTML = chart(true);
    graphCursor.update(graphModels);
    $('graph-history-status').hidden = !graphHistory.error;
    $('graph-history-status').textContent = graphHistory.error ? 'Archive history unavailable' : '';
    $('graph-history-status').title = graphHistory.error || '';
  }

  function renderTimeRange(loadHistory = true) {
    const [start, end] = range(), plan = state.accepted;
    const minutes = Math.round((end-start)/60000);
    const spanLabel = minutes % 60 ? `${minutes} minutes` : `${minutes/60} ${minutes === 60 ? 'hour' : 'hours'}`;
    $('back').setAttribute('aria-label', `Previous ${spanLabel}`);
    $('forward').setAttribute('aria-label', `Next ${spanLabel}`);
    $('period').textContent = `${time(start)} — ${time(end)}${plan ? ` · Plan ${time(plan.intervals[0].start,false)}` : ''}`;
    $('period').title = `${state.policy.timezone}${plan ? ` · ${plan.summary.intervals} intervals · ${num(plan.seconds,1)} s calculation` : ''}`;
    if (loadHistory) graphHistory.load(start, end, Date.parse(state.now), `${state.demo}/${state.policy.timezone}`);
    renderCharts();
    const sessions = plan?.sessions || [];
    $('timeline').innerHTML = ['ev', 'ess'].map(resource =>
        `<div class="timeline-lane"><small>${resource.toUpperCase()}</small><div class="timeline-track">${sessions.filter(s=>s.resource===resource&&Date.parse(s.end)>start&&Date.parse(s.start)<end).map(s=>{const left=Math.max(start,Date.parse(s.start)),right=Math.min(end,Date.parse(s.end));return `<button class="timeline-run" data-session="${esc(s.id)}" style="background:${colors[resource]};left:${(left-start)/(end-start)*100}%;width:${(right-left)/(end-start)*100}%" title="${esc(s.title)} / ${esc(time(s.start))}" aria-label="${resource.toUpperCase()} session ${esc(time(s.start))}"></button>`}).join('')}</div></div>`
      ).join('') +
      `<div class="timeline-labels"><span>${time(start)}</span><span>${sessions.length} grouped sessions</span><span>${time(end)}</span></div>`;
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
    const fault = state.ev_incident;
    const charger = state.charger;
    const chargerMessage = charger?.issue || (state.control_enabled &&
      !['EV stopped', 'Charging command confirmed'].includes(charger?.control) ? charger?.control : '');
    $('charger-status').hidden = !chargerMessage || Boolean(evFaultText(fault, state.policy.timezone));
    $('charger-status').textContent = chargerMessage ? `EV · ${chargerMessage}` : '';
    const faultText = evFaultText(fault, state.policy.timezone);
    $('ev-fault-banner').hidden = !faultText;
    $('ev-fault-banner').innerHTML = faultText ? `<strong>${esc(faultText)}</strong><p>Phone alert: ${esc(notificationText(fault.notification))} · Reboot attempts: ${fault.reboot_attempts}/1</p><button data-incident="${esc(fault.id)}">Incident details & logs</button>${fault.status === 'unresolved' ? ` <button data-ack-incident="${esc(fault.id)}">Acknowledge after diagnosis</button>` : ''}` : '';
    $('app-version').textContent = ` ${state.version}`;
    if (!options.native) document.title = `EnergyManager · ${state.version}`;
    $('dashboard').hidden = page === 'settings' || page === 'ev';
    $('ev-panel').hidden = page !== 'ev';
    $('settings-panel').hidden = page !== 'settings';
    $('native-setup').hidden = !!options.native || page !== 'settings';
    for (const name of ['overview', 'planning', 'ev', 'settings']) {
      $(name).setAttribute('aria-selected', String(page === name));
    }
    $('connection').textContent = (state.provenance.startsWith('SYNTHETIC') ? 'SYNTHETIC · ' : '') + (state.status === 'planning' ? '● Calculating · control responsive' : state
      .status === 'ready' ? '● Plan ready' : '● ' + state.status);
    root.querySelector('footer').textContent =
      `${state.control_enabled ? 'Hardware control enabled' : 'Hardware control disabled'} / Forecasts and planned costs are estimates.`;
    (options.native ? root.host : document.body).classList.toggle('planning', page === 'planning');
    $('live').hidden = !!options.hideLive;
    if (page === 'settings') return;
    if (page === 'ev') {
      evPage.render(state);
      return;
    }
    const o = state.observation,
      c = state.capabilities,
      plan = state.accepted;
    $('page-title').textContent = page === 'overview' ? 'Overview' : 'Planning';
    $('power-title').textContent = page === 'planning' ? '7 days · Power · actual / planned · W' :
      'Power · actual / planned · W';
    $('navigation').hidden = page === 'planning';
    $('monthly-peak-legend').hidden = page !== 'overview';
    renderLive();
    $('status').innerHTML =
      `${!plan ? '<p class="status-line">Waiting for a validated plan.</p>' : ''}${state.error ? `<p class="error">${esc(powerText(state.error))}</p>` : ''}`;
    renderTimeRange();
    const sessions = plan?.sessions || [];
    const goals = [...state.goals.map(g => ({
      ...((plan?.goals || []).find(p => p.id === g.id && p.revision === g.revision) || {}),
      ...g
    })), ...(plan?.goals || []).filter(g => g.kind === 'daily')];
    const goalCard = g =>
      `<section class="goal"><div class="goal-title"><strong>${esc(g.title)}</strong><span class="badge ${g.shortfall_kwh>0.001?'warning':''}">${g.shortfall_kwh>0.001?'Shortfall':g.status==='scheduled'?'Scheduled':g.status==='unknown_return_state'?'Unknown state':'Waiting'}</span></div><p>${time(g.deadline)} · ${g.kind==='trip'?num(g.distance_km,0)+' km total / '+num((g.target_kwh ?? Math.min(c.ev_capacity_kwh,(g.distance_km+state.policy.arrival_reserve_km)*state.policy.consumption_kwh_per_100km/100))/c.ev_capacity_kwh*100,0)+'% departure target':num(g.target_soc_percent,0)+'% SoC'}</p><p>${g.planned_kwh!==undefined&&g.planned_kwh!==null?num(g.planned_kwh/c.ev_capacity_kwh*100,1)+'% planned · ':''}${g.shortfall_kwh>.001?num(g.shortfall_kwh)+' kWh shortfall':'One shared battery trajectory'}</p>${g.completion_margin_minutes !== undefined && g.completion_margin_minutes !== null ? `<p>${g.desired_margin_met ? `Ready at least ${state.policy.completion_margin_minutes} min early` : `Limited completion margin / ${num(g.completion_margin_minutes,0)} min`}</p>` : ''}${g.external_charging_required?'<p class="error">Charging away must be arranged. Return SoC is unknown.</p>':''}<div class="meter"><i style="width:${Math.min(100,o.ev_kwh/(g.target_kwh||c.ev_capacity_kwh*g.target_soc_percent/100||1)*100)}%;background:#16a34a"></i></div><div class="actions"><button data-detail="${esc(g.id)}">Details</button>${g.kind!=='daily'&&!g.calendar?`<button data-edit="${esc(g.id)}">Edit</button><button data-delete="${esc(g.id)}">Remove</button>`:''}</div></section>`;
    const dailyGoals = goals.filter(goal => goal.kind === 'daily');
    const primaryGoals = goals.filter(goal => goal.kind !== 'daily' || goal.id === dailyGoals[0]?.id);
    const laterDaily = dailyGoals.slice(1);
    $('goals').innerHTML = primaryGoals.map(goalCard).join('') + (laterDaily.length ?
      `<details><summary>${laterDaily.length} later morning requirements</summary>${laterDaily.map(goalCard).join('')}</details>` :
      '');
    if (!goals.length) $('goals').innerHTML = '<p class="empty">Add a journey or timed SoC goal.</p>';
    $('approvals').innerHTML = state.issues.length ? state.issues.map(i => i.kind === 'planning' ?
      `<section class="issue"><strong>${esc(i.title)}</strong><p>${esc(powerText(i.text))}</p><p>${time(i.first_at)} · ${i.state === 'retrying' ? 'Recalculating' : 'Attention needed'}${i.notification ? ' · ' + esc(notificationStatus(i.notification)) : ''}</p><button data-decision="${esc(i.decision_id)}">Decision evidence</button></section>` :
      `<section class="issue"><strong>${esc(i.title||goals.find(g=>g.id===i.goal_id)?.title||'EV goal')}</strong><p>${esc(powerText(i.text))}</p><p>${i.kind==='ess_peak'?'Specific forecast peak':i.shortfall_kwh===null?'Awaiting measured reconnection':num(i.shortfall_kwh)+' kWh short'} · ${esc(i.state)}</p>${i.notification ? `<p>${esc(notificationStatus(i.notification))}</p>` : ''}${i.proposed_peak_kw && i.state === 'pending'?`<p>Requested ceiling ${watts(i.proposed_peak_kw)} W</p><button data-approve="${esc(i.goal_id)}">Approve</button> <button data-reject="${esc(i.goal_id)}">Reject</button>`:''}</section>`
    ).join('') : '<p class="empty">No pending decisions or planning problems.</p>';
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
      `<p>${esc(state.provenance)}</p><p>${esc(graphHistory.status)}</p><p>Control response observed locally: ${num(state.control_max_seconds*1000,2)} ms maximum. This is not hardware latency.</p>${plan?`<pre>${esc(JSON.stringify({status:plan.status,stages:plan.stages,input_digest:plan.input_digest},null,2))}</pre>`:''}`;
  }


  function renderLive() {
    const o = state.observation,
      c = state.capabilities;
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
      } else if (!liveKnown) {
        value = null;
        label = 'Waiting for live input';
      }
      let compact = '';
      const readings = state.live_inputs?.readings;
      if (key === 'solar') compact = `<span title="AC solar">∿ ${watts(readings ? readings.pv_ac_kw?.value : liveKnown ? o.pv_ac_kw : null)} W</span> · <span title="DC solar">⎓ ${watts(readings ? readings.pv_dc_kw?.value : liveKnown ? o.pv_dc_kw : null)} W</span>`;
      if (key === 'ess') compact = `<span title="Minimum battery state of charge">≥ ${num(c.ess_min_kwh/c.ess_capacity_kwh*100,0)}%</span> · ${watts(readings ? readings.ess_kw?.value : liveKnown ? o.ess_power_kw : null)} W`;
      let connected = liveKnown ? o.connected : null;
      if (!state.demo && state.live_inputs) {
        const connection = state.live_inputs.cards.ev?.label;
        connected = connection === 'Connected' ? true : connection === 'Away / disconnected' ? false : null;
      }
      const rows = dailyEnergyRows(dailyEnergy, key, state).map(row => {
        const coverage = row.partial ? ' Partial recorded coverage.' : '';
        const recorded = row.recordedAt ? ` Recorded through ${evIncidentTime(row.recordedAt, state.policy.timezone)}.` : '';
        return `<span class="energy-row" title="${esc(row.label)}: recorded today ⇢ fixed day-end estimate. ${esc(row.capture)}${recorded}${coverage}" aria-label="${esc(row.label)}: ${row.actual} kWh recorded, ${row.predicted} kWh fixed day-end estimate${row.partial ? ', partial coverage' : ''}"><span class="energy-symbol" aria-hidden="true">${row.symbol}</span><span>${row.actual}</span><span class="prediction-arrow" aria-hidden="true">⇢</span><span>${row.predicted}</span><span class="energy-unit">kWh${row.partial ? ' ◐' : ''}</span></span>`;
      }).join('');
      const content = `<span class="live-label muted">${name}${key === 'ev' ? connectionIcon(connected) : ''}</span><strong style="color:${colors[key]}">${unit==='W'?watts(value):num(value,0)} <small style="display:inline;font-size:13px">${unit}</small></strong>${compact ? `<small class="live-components">${compact}</small>` : ''}<div class="daily-energy">${rows}</div>${issues.length ? `<span class="input-warning" title="${esc(issues.map(powerText).join('; '))}" aria-label="${esc(issues.map(powerText).join('; '))}">⚠</span>` : ''}${unit==='%' && value !== null ?`<div class="meter"><i style="width:${Math.max(0,Math.min(100,value))}%;background:${colors[key]}"></i></div>`:''}`;
      const historyAction = options.native ? 'role="button" tabindex="0"' : '';
      if (key !== 'grid') return `<article class="live-item" data-live="${key}" ${historyAction}>${content}</article>`;
      const peak = monthlyPeakWatts(state), peakText = peak === null ? '—' : String(Math.round(peak));
      const canOpen = options.native && !state.demo && !!options.entities?.monthly_peak_kw;
      const description = `${state.demo ? 'Synthetic demo: ' : ''}Current recorded monthly grid-import peak: ${peak === null ? 'unavailable' : peakText + ' W'} · 15-minute average.${options.native && !state.demo ? canOpen ? ' Open HA sensor history.' : ' HA sensor is not mapped.' : ''}`;
      const peakContent = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M3 20h18M3 17l6-7 4 4 4-10 4 13M3 4h10"/></svg><span>${peakText} W</span>`;
      const peakRow = options.native && !state.demo ?
        `<button type="button" class="grid-peak" data-entity-key="monthly_peak_kw" ${canOpen ? '' : 'disabled'} title="${esc(description)}" aria-label="${esc(description)}">${peakContent}</button>` :
        `<span class="grid-peak" title="${esc(description)}" aria-label="${esc(description)}">${peakContent}</span>`;
      return `<article class="live-item"><div data-live="grid" ${historyAction}>${content}</div>${peakRow}</article>`;
    }).join('');
  }

  function openGoal(goal, kind = 'manual') {
    if (goal?.calendar) { showGoalDetail(goal.id); return; }
    if (!state) return;
    const form = $('goal-form');
    form.reset();
    form.elements.id.value = goal?.id || '';
    form.elements.title.value = goal?.title || '';
    form.elements.kind.value = goal?.kind || kind;
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

  function showGoalDetail(id) {
    const goal = state.goals.find(goal => goal.id === id) || state.schedule_goals.find(goal => goal.id === id);
    if (!goal) return;
    detail(goal.title,
      `<p>Deadline ${time(goal.deadline)}</p><p>${goal.kind === 'trip' ? `Total journey ${num(goal.distance_km, 0)} km, arrival reserve ${state.policy.arrival_reserve_km} km. ${goal.return_at ? 'Expected return ' + time(goal.return_at) : 'Return unknown; unavailable until reconnection.'}` : 'Timed state-of-charge requirement. No journey or withdrawal is assumed.'}</p>${goal.calendar ? `<p>Calendar: ${esc(goal.calendar.source)}. Provisional 50 km total / four hours from event start.<br>${esc(goal.calendar.location)}</p>` : ''}<p>Priority ${goal.priority}. ${goal.approval_state === 'granted' ? 'Approved task ceiling ' + watts(goal.approved_peak_kw) + ' W' : 'Normal automatic peak policy applies.'}</p><p>Power changes stay within grouped charging sessions.</p>`);
  }

  async function showFaultHistory() {
    const incidents = await api('ev-incidents');
    detail('EV fault history', incidents.map(item => `<p><button data-incident="${esc(item.id)}">${evIncidentTime(item.detected_at,state.policy.timezone)} · ${esc(item.status)}</button> ${esc(item.reason)}</p>`).join('') || '<p>No recorded EV incidents.</p>');
  }

  async function showIncident(id) {
    incidentReport = await api(`ev-incidents/${encodeURIComponent(id)}`);
    const item = incidentReport.incident;
    detail('EV delivery incident', `<p>Detected ${evIncidentTime(item.detected_at,state.policy.timezone)} · Began ${evIncidentTime(item.started_at,state.policy.timezone)}</p><p>${esc(item.status)} · ${esc(item.reason)}</p><p>Reboot attempts ${item.reboot_attempts}/1 · Phone alert: ${esc(notificationText(item.notification))}</p><p>${esc(incidentReport.note)}</p><button data-download-incident="true">Download full incident JSON</button><p>${incidentReport.events.length} recorded events${incidentReport.truncated ? ' (report limit reached)' : ''}; preview shows the latest 100.</p><pre class="incident-trace">${esc(JSON.stringify(incidentReport.events.slice(-100),null,2))}</pre>`);
  }

  function showSessionDetail(id) {
    const session = state.accepted?.sessions.find(session => session.id === id);
    if (!session) return;
    detail(session.title,
      `<p>${time(session.start)} — ${time(session.end)}</p><p>${num(session.energy_kwh)} kWh to the battery</p><p>${esc(powerText(session.reason))}</p><p>${session.resource === 'ev' ? `Contributes to ${session.goal_ids.length} shared goals. Energy is counted once.` : 'Source-specific reservations preserve required EV and household peak support.'}</p>`);
  }
  async function refresh(force = false) {
    if (loading) return;
    loading = true;
    try {
      const nextState = await statePoller.poll(force);
      if (!nextState || lifecycle.signal.aborted) return;
      connectionError = null;
      renderConnectionError();
      // Keep click targets and their backing records on the same displayed revision.
      if (!viewLocked()) {
        backendState = nextState;
        state = options.liveState ? options.liveState(backendState) : backendState;
        render();
        refreshEnergy();
      }
    } catch (error) {
      if (lifecycle.signal.aborted) return;
      if (connectionError?.message !== error.message)
        connectionError = {message: error.message, at: new Date().toISOString()};
      renderConnectionError();
      $('connection').textContent = 'Connection unavailable · retrying';
    } finally {
      loading = false
    }
  }

  async function refreshEnergy() {
    const energyDate = new Intl.DateTimeFormat('en-CA', {timeZone: state.policy.timezone,
      year: 'numeric', month: '2-digit', day: '2-digit'}).format(new Date(state.now));
    const key = `${state.demo}/${state.policy.timezone}/${energyDate}`;
    if (energyLoading || !['overview', 'planning'].includes(page) ||
        (Date.now() - energyRequestedAt <= 30000 && energyDay === key)) return;
    energyRequestedAt = Date.now();
    energyDay = key;
    energyLoading = true;
    try {
      const result = await api('daily-energy');
      if (!lifecycle.signal.aborted) dailyEnergy = result;
    } catch {
      // Retain the last dated subtotal; its tooltip states how far it was recorded.
    } finally {
      energyLoading = false;
      if (!lifecycle.signal.aborted && !viewLocked()) renderLive();
    }
  }
  root.addEventListener('pointerdown', () => {
    pointerHeld = true;
    pointerUntil = Date.now() + 350
  }, {
    signal: lifecycle.signal
  });
  const documentRoot = root.ownerDocument || root;
  root.addEventListener('click', event => {
    if (event.target.closest('button,input,select,a') && hasTextSelection(root)) clearTextSelection(root);
  }, {capture: true, signal: lifecycle.signal});
  documentRoot.addEventListener('pointerdown', event => {
    const target = event.composedPath()[0];
    if (hasTextSelection(root) && (!root.contains(target) || target.closest('button,input,select,a')))
      clearTextSelection(root);
  }, {signal: lifecycle.signal});
  for (const event of ['pointerup', 'pointercancel']) documentRoot.addEventListener(event, () => {
    pointerHeld = false;
    setTimeout(() => {
      if (!lifecycle.signal.aborted) renderConnectionError();
    }, 350);
  }, {signal: lifecycle.signal});

  function showPage(name) {
    graphCursor.cancelNavigation();
    pointerHeld = false;
    if (options.native && options.navigate) {
      options.navigate(name);
      return;
    }
    pointerUntil = 0;
    page = name;
    if (!options.native) history.replaceState(null, '', `#${name}`);
    render();
    if (name === 'settings') settingsPage.show();
  }
  for (const name of ['overview', 'planning', 'ev', 'settings']) $(name).onclick = () => showPage(name);
  $('back').onclick = () => {
    graphCursor.cancelNavigation();
    pointerHeld = false;
    pointerUntil = 0;
    if (selectedRange) { const span = selectedRange[1] - selectedRange[0]; selectedRange = selectedRange.map(at => at - span); }
    else offset -= 6;
    $('history-date').value = '';
    render()
  };
  $('forward').onclick = () => {
    graphCursor.cancelNavigation();
    pointerHeld = false;
    pointerUntil = 0;
    if (selectedRange) { const span = selectedRange[1] - selectedRange[0]; selectedRange = selectedRange.map(at => at + span); }
    else offset += 6;
    $('history-date').value = '';
    render()
  };
  $('now').onclick = () => {
    graphCursor.cancelNavigation();
    pointerHeld = false;
    pointerUntil = 0;
    offset = 0;
    selectedRange = null;
    $('history-date').value = '';
    render()
  };
  $('history-date').onchange = () => {
    graphCursor.cancelNavigation();
    pointerHeld = false;
    pointerUntil = 0;
    if (!$('history-date').value) return;
    try {
      const [start] = historyDayRange($('history-date').value, state.policy.timezone);
      selectedRange = [start, start + 6 * 3600000];
      render();
    } catch (error) {
      $('graph-history-status').textContent = error.message;
    }
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
      await refresh(true)
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
      await api('control', 'POST', {
        enabled: hardwareIntent
      });
    } catch (error) {
      hardwareError = error.message;
    } finally {
      hardwareChanging = false;
      await refresh(true);
    }
  };
  $('refresh').onclick = async () => {
    try {
      await api('replan', 'POST', {});
      await refresh(true)
    } catch (error) {
      $('status').textContent = error.message
    }
  };
  root.addEventListener('click', async event => {
    const button = event.target.closest('button');
    if (!button || !state) return;
    try {
      if (button.dataset.faultHistory) await showFaultHistory();
      if (button.dataset.incident) await showIncident(button.dataset.incident);
      if (button.dataset.ackIncident) {
        await api(`ev-incidents/${encodeURIComponent(button.dataset.ackIncident)}/acknowledge`, 'POST', {});
        pointerUntil = 0;
        await refresh(true);
      }
      if (button.dataset.downloadIncident && incidentReport) {
        const url = URL.createObjectURL(new Blob([JSON.stringify(incidentReport,null,2)], {type:'application/json'}));
        const link = document.createElement('a');
        link.href = url; link.download = `ev-incident-${incidentReport.incident.id}.json`; link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      }
      if (button.dataset.edit) openGoal(state.goals.find(g => g.id === button.dataset.edit));
      if (button.dataset.delete) {
        await api(`goals/${encodeURIComponent(button.dataset.delete)}`, 'DELETE', {});
        pointerUntil = 0;
        await refresh(true)
      }
      if (button.dataset.detail) {
        showGoalDetail(button.dataset.detail);
      }
      if (button.dataset.session) {
        showSessionDetail(button.dataset.session);
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
        await refresh(true)
      }
    } catch (error) {
      $('status').textContent = error.message
    }
  }, {
    signal: lifecycle.signal
  });
  $('history').onclick = async () => {
    try {
      const rows = await api('decisions');
      $('history-list').innerHTML = rows.map(r =>
        `<p><button data-decision="${esc(r.id)}">${time(r.at)} · ${esc(r.disposition)}${r.status ? ' · ' + esc(r.status) : ''}</button> ${r.reason ? esc(r.reason) : money(r.summary.comparison_eur) + ' comparison'}${r.seconds !== null && r.seconds !== undefined ? ' · ' + num(r.seconds,1) + ' s' : ''}</p>`
      ).join('')
    } catch (error) {
      $('status').textContent = error.message
    }
  };
  const openDecision = async event => {
    const b = event.target.closest('[data-decision]');
    if (b) {
      try {
        const id = encodeURIComponent(b.dataset.decision);
        const d = await api(`decisions/${id}`);
        detail(d.disposition.startsWith('rejected') ? 'Rejected planning attempt' : 'Persisted decision',
          `<p>${esc(d.disposition)} · ${esc(d.snapshot.provenance)}</p><pre>${esc(JSON.stringify({status:d.result.status,valid:d.result.valid,reason:d.result.reason,publication_errors:d.result.publication_errors,seconds:d.result.seconds,stages:d.result.stages,summary:d.result.summary,reasons:d.result.reasons,digest:d.digest},null,2))}</pre>`);
        const download = document.createElement('a');
        // Download server JSON directly so floating-point formatting and checksums survive.
        download.href = options.decisionDownloadUrl ? options.decisionDownloadUrl(id) : `./api/decisions/${id}?download=1`;
        download.download = 'energymanager-decision.json';
        download.textContent = 'Download full decision JSON (inputs and results)';
        $('detail-body').prepend(download);
      } catch (error) {
        detail('Decision unavailable', `<p class="error">${esc(error.message)}</p>`);
      }
    }
  };
  $('history-list').onclick = openDecision;
  $('approvals').addEventListener('click', openDecision, {signal: lifecycle.signal});
  if (!options.native) page = ['#planning', '#ev', '#settings'].includes(location.hash) ? location.hash.slice(1) : 'overview';
  await refresh(true);
  if (page === 'settings') await settingsPage.show();
  const timer = setInterval(refresh, 2000);
  return {
    updateLive() {
      if (!backendState || viewLocked()) return;
      const oldPeak = monthlyPeakWatts(state);
      state = options.liveState ? options.liveState(backendState) : backendState;
      if (page === 'overview' || page === 'planning') renderLive();
      else if (page === 'ev') evPage.updateStatus(state);
      if (page === 'overview' && monthlyPeakWatts(state) !== oldPeak) renderCharts();
    },
    dispose() {
      lifecycle.abort();
      graphHistory.dispose();
      clearInterval(timer);
      for (const dialog of root.querySelectorAll('dialog[open]')) dialog.close();
    }
  };

}
