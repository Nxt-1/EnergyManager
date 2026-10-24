import {
  SettingsPage
} from './settings.js';
import {
  powerText,
  watts,
  dailyEnergyRows,
  connectionIcon
} from './display.js';
import {
  DateTimePicker
} from './datetime-picker.js';
import {
  EVSchedulePage
} from './ev-schedule.js';
import {GraphHistory, historyDayRange, observedPoints} from './graph-history.js';
import {GraphCursor, plotInsets, clipSeries} from './graph-cursor.js';


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
    pointerUntil = 0,
    hardwareChanging = false,
    hardwareIntent = false,
    hardwareError = null;
  let dailyEnergy = null, energyRequestedAt = 0, energyPlanId = null, energyDay = null;
  const graphModels = {};
  let selectedRange = null;
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
    if (options.api) return options.api(path, method, body);
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
  const settingsPage = new SettingsPage($('settings-panel'), api, lifecycle.signal);
  const evPage = new EVSchedulePage($('ev-panel'), {
    add: kind => openGoal(null, kind),
    edit: id => openGoal(state.goals.find(goal => goal.id === id)),
    goal: id => showGoalDetail(id),
    session: id => showSessionDetail(id),
    remove: async id => {
      await api(`goals/${encodeURIComponent(id)}`, 'DELETE', {});
      pointerUntil = 0;
      await refresh();
    },
    settings: () => showPage('settings'),
    replan: async () => {
      await api('replan', 'POST', {});
      pointerUntil = 0;
      await refresh();
    }
  });
  const dateTimePicker = new DateTimePicker(() => state.policy.timezone, () => state.now, root);
  dateTimePicker.bind($('goal-form').elements.deadline, 'Deadline / departure', true);
  dateTimePicker.bind($('goal-form').elements.return_at, 'Return time');
  const graphCursor = new GraphCursor(root, at => new Date(at).toLocaleString('en-GB', {
    timeZone: state.policy.timezone, day: '2-digit', month: 'short',
    hour: '2-digit', minute: '2-digit', second: '2-digit', timeZoneName: 'shortOffset'
  }), colors, lifecycle.signal);
  const charts = root.querySelector('.charts');
  charts.style.setProperty('--plot-left', `${plotInsets.left}px`);
  charts.style.setProperty('--plot-right', `${plotInsets.right}px`);
  let chartWidth = 0;
  const resizeObserver = new ResizeObserver(entries => {
    const width = entries[0].contentRect.width;
    if (Math.abs(width - chartWidth) < 0.5) return;
    chartWidth = width;
    if (!lifecycle.signal.aborted && state && ['overview', 'planning'].includes(page)) renderCharts();
  });
  resizeObserver.observe(charts);
  lifecycle.signal.addEventListener('abort', () => resizeObserver.disconnect(), {once: true});

  function range() {
    const now = Date.parse(state.now);
    if (page === 'planning') return [state.accepted ? Date.parse(state.accepted.intervals[0].start) : now, state
      .accepted ? Date.parse(state.accepted.intervals.at(-1).end) : now + 168 * 3600000
    ];
    if (selectedRange) return selectedRange;
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
    let low = soc ? 0 : Math.min(0, ...visible.map(p => p[1])),
      high = soc ? 100 : Math.max(1000, ...visible.map(p => p[1]));
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
    return svg + '<g class="cursor-overlay" pointer-events="none"></g></svg><div class="cursor-values" role="status" hidden></div>';
  }

  function viewLocked() {
    return $('goal-dialog').open || $('detail-dialog').open || Date.now() < pointerUntil;
  }

  function renderCharts() {
    $('power').innerHTML = chart();
    $('soc').innerHTML = chart(true);
    graphCursor.update(graphModels);
    $('graph-history-status').hidden = !graphHistory.error;
    $('graph-history-status').textContent = graphHistory.error ? 'Archive history unavailable' : '';
    $('graph-history-status').title = graphHistory.error || '';
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
    const [start, end] = range();
    $('period').textContent = `${time(start)} — ${time(end)}${plan ? ` · Plan ${time(plan.intervals[0].start,false)}` : ''}`;
    $('period').title = `${state.policy.timezone}${plan ? ` · ${plan.summary.intervals} intervals · ${num(plan.seconds,1)} s calculation` : ''}`;
    $('power-title').textContent = page === 'planning' ? '7 days · Power · actual / planned · W' :
      'Power · actual / planned · W';
    $('navigation').hidden = page === 'planning';
    renderLive();
    $('status').innerHTML =
      `${!plan ? '<p class="status-line">Waiting for a validated plan.</p>' : ''}${state.actuator_health?.delivery_fault ? '<p class="error">EV delivery fault: stopped; diagnose before restart</p>' : ''}${state.error ? `<p class="error">${esc(powerText(state.error))}</p>` : ''}`;
    graphHistory.load(start, end, Date.parse(state.now));
    renderCharts();
    const sessions = plan?.sessions || [];
    $('timeline').innerHTML = ['ev', 'ess'].map(resource =>
        `<div class="timeline-lane"><small>${resource.toUpperCase()}</small><div class="timeline-track">${sessions.filter(s=>s.resource===resource&&Date.parse(s.end)>start&&Date.parse(s.start)<end).map(s=>{const left=Math.max(start,Date.parse(s.start)),right=Math.min(end,Date.parse(s.end));return `<button class="timeline-run" data-session="${esc(s.id)}" style="background:${colors[resource]};left:${(left-start)/(end-start)*100}%;width:${(right-left)/(end-start)*100}%" title="${esc(s.title)} / ${esc(time(s.start))}" aria-label="${resource.toUpperCase()} session ${esc(time(s.start))}"></button>`}).join('')}</div></div>`
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
        const coverage = row.partial ? ' Partial recorded coverage; the projection starts from that subtotal.' : '';
        return `<span class="energy-row" title="${esc(row.label)}: recorded today ⇢ expected at local midnight. Power integration estimates.${coverage}" aria-label="${esc(row.label)}: ${row.actual} kWh recorded, ${row.predicted} kWh expected at day end${row.partial ? ', partial coverage' : ''}"><span class="energy-symbol" aria-hidden="true">${row.symbol}</span><span>${row.actual}</span><span class="prediction-arrow" aria-hidden="true">⇢</span><span>${row.predicted}</span><span class="energy-unit">kWh${row.partial ? ' ◐' : ''}</span></span>`;
      }).join('');
      return `<article class="live-item" data-live="${key}" ${options.native ? 'role="button" tabindex="0"' : ''}><span class="live-label muted">${name}${key === 'ev' ? connectionIcon(connected) : ''}</span><strong style="color:${colors[key]}">${unit==='W'?watts(value):num(value,0)} <small style="display:inline;font-size:13px">${unit}</small></strong>${compact ? `<small class="live-components">${compact}</small>` : ''}<div class="daily-energy">${rows}</div>${issues.length ? `<span class="input-warning" title="${esc(issues.map(powerText).join('; '))}" aria-label="${esc(issues.map(powerText).join('; '))}">⚠</span>` : ''}${unit==='%' && value !== null ?`<div class="meter"><i style="width:${Math.max(0,Math.min(100,value))}%;background:${colors[key]}"></i></div>`:''}</article>`;
    }).join('');
  }

  function openGoal(goal, kind = 'manual') {
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
      `<p>Deadline ${time(goal.deadline)}</p><p>${goal.kind === 'trip' ? `Total journey ${num(goal.distance_km, 0)} km, arrival reserve ${state.policy.arrival_reserve_km} km. ${goal.return_at ? 'Expected return ' + time(goal.return_at) : 'Return unknown; unavailable until reconnection.'}` : 'Timed state-of-charge requirement. No journey or withdrawal is assumed.'}</p><p>Priority ${goal.priority}. ${goal.approval_state === 'granted' ? 'Approved task ceiling ' + watts(goal.approved_peak_kw) + ' W' : 'Normal automatic peak policy applies.'}</p><p>Power changes stay within grouped charging sessions.</p>`);
  }

  function showSessionDetail(id) {
    const session = state.accepted?.sessions.find(session => session.id === id);
    if (!session) return;
    detail(session.title,
      `<p>${time(session.start)} — ${time(session.end)}</p><p>${num(session.energy_kwh)} kWh to the battery</p><p>${esc(powerText(session.reason))}</p><p>${session.resource === 'ev' ? `Contributes to ${session.goal_ids.length} shared goals. Energy is counted once.` : 'Source-specific reservations preserve required EV and household peak support.'}</p>`);
  }
  async function refresh() {
    if (loading) return;
    loading = true;
    try {
      const nextState = await api('state');
      // Keep click targets and their backing records on the same displayed revision.
      if (!viewLocked()) {
        backendState = nextState;
        state = options.liveState ? options.liveState(backendState) : backendState;
        render();
        const energyDate = new Intl.DateTimeFormat('en-CA', {timeZone: state.policy.timezone,
          year: 'numeric', month: '2-digit', day: '2-digit'}).format(new Date(state.now));
        if (['overview', 'planning'].includes(page) && (Date.now() - energyRequestedAt > 30000 ||
            energyPlanId !== state.accepted?.id || energyDay !== energyDate)) {
          energyRequestedAt = Date.now();
          energyPlanId = state.accepted?.id;
          energyDay = energyDate;
          try {
            dailyEnergy = await api('daily-energy');
          } catch {
            dailyEnergy = null;
          }
          if (!lifecycle.signal.aborted && !viewLocked()) renderLive();
        }
      }
    } catch (error) {
      $('connection').textContent = 'Connection unavailable';
      $('status').textContent = error.message;
      if (options.native) root.querySelector('#native-error').textContent = error.message;
    } finally {
      loading = false
    }
  }
  root.addEventListener('pointerdown', () => {
    pointerUntil = Date.now() + 350
  }, {
    signal: lifecycle.signal
  });

  function showPage(name) {
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
    pointerUntil = 0;
    if (selectedRange) selectedRange = selectedRange.map(at => at - 12 * 3600000);
    else offset -= 12;
    $('history-date').value = '';
    render()
  };
  $('forward').onclick = () => {
    pointerUntil = 0;
    if (selectedRange) selectedRange = selectedRange.map(at => at + 12 * 3600000);
    else offset += 12;
    $('history-date').value = '';
    render()
  };
  $('now').onclick = () => {
    pointerUntil = 0;
    offset = 0;
    selectedRange = null;
    $('history-date').value = '';
    render()
  };
  $('history-date').onchange = () => {
    pointerUntil = 0;
    if (!$('history-date').value) return;
    try {
      selectedRange = historyDayRange($('history-date').value, state.policy.timezone);
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
      await api('control', 'POST', {
        enabled: hardwareIntent
      });
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
  root.addEventListener('click', async event => {
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
        await refresh()
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
  if (!options.native) page = ['#planning', '#ev', '#settings'].includes(location.hash) ? location.hash.slice(1) : 'overview';
  await refresh();
  if (page === 'settings') await settingsPage.show();
  const timer = setInterval(refresh, 2000);
  return {
    updateLive() {
      if (!backendState || viewLocked()) return;
      state = options.liveState ? options.liveState(backendState) : backendState;
      if (page === 'overview' || page === 'planning') renderLive();
      else if (page === 'ev') evPage.render(state);
    },
    dispose() {
      lifecycle.abort();
      graphHistory.dispose();
      clearInterval(timer);
      for (const dialog of root.querySelectorAll('dialog[open]')) dialog.close();
    }
  };

}
