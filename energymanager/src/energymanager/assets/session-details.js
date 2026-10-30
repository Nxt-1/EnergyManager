const escape = value => String(value ?? '').replace(/[&<>"']/g, character => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[character]));
const energy = value => value > 0 && value < 0.01 ? '&lt;0.01' : Number(value).toFixed(2);

export function sessionContributionMarkup(session, formatTime) {
  const allocation = session.energy_attribution;
  if (!allocation) return '<p>Contributions unavailable for this older plan.</p>';
  const contributions = new Map();
  for (const category of ['driving', 'targets']) {
    for (const row of allocation[category]) {
      const item = contributions.get(row.goal_id) || {...row};
      item[category] = row.energy_kwh;
      contributions.set(row.goal_id, item);
    }
  }
  const mixed = allocation.driving.length > 0 && allocation.targets.length > 0;
  const rows = [...contributions.values()].sort((a, b) => Date.parse(a.deadline) - Date.parse(b.deadline));
  const list = rows.length ? `<h3>Supports</h3><ul>${rows.map(row => {
    const amounts = [];
    if (row.driving !== undefined) amounts.push(`${energy(row.driving)} kWh driving`);
    if (row.targets !== undefined) amounts.push(`${energy(row.targets)} kWh${mixed ? ' target' : ''}`);
    return `<li><strong>${escape(row.title)}</strong> · ${escape(formatTime(row.deadline))} — ${amounts.join(' / ')}</li>`;
  }).join('')}</ul>` : '';
  const unknown = allocation.unresolved_kwh > 1e-8 ? '<p>Some contributions are unknown.</p>' : '';
  return list + unknown || '<p>Stored for later use.</p>';
}


const powerSeries = {
  ev: [{key: 'ac_w', label: 'EV AC input', color: '#16a34a'}],
  ess: [{key: 'ac_w', label: 'ESS AC · + charge / − supply', color: '#007ac2'},
        {key: 'dc_w', label: 'Direct DC solar charge', color: '#e4ac19'}]
};

function flowSum(flows, names, index) {
  const values = names.map(name => flows?.[name]?.[index]);
  return values.every(value => typeof value === 'number' && Number.isFinite(value)) ?
    values.reduce((total, value) => total + value, 0) : null;
}

export function sessionPowerProfile(plan, task, capabilities = {}) {
  const start = Date.parse(task.start), end = Date.parse(task.end);
  if (!powerSeries[task.resource] || !Number.isFinite(start) || !Number.isFinite(end) || end <= start) return [];
  const rows = [];
  for (const [index, interval] of (plan?.intervals || []).entries()) {
    const left = Math.max(start, Date.parse(interval.start));
    const right = Math.min(end, Date.parse(interval.end));
    if (!Number.isFinite(left) || !Number.isFinite(right) || right <= left) continue;
    let ac = null, dc = null;
    if (task.resource === 'ev') ac = flowSum(plan.flows, ['pv_ev', 'grid_ev', 'solar_dis_ev'], index);
    else {
      const charge = flowSum(plan.flows, ['pv_store', 'grid_store'], index);
      const supply = flowSum(plan.flows, ['solar_dis_ev', 'solar_dis_house', 'grid_dis_house'], index);
      const invert = flowSum(plan.flows, ['dc_invert'], index);
      const efficiency = capabilities.ac_discharge_efficiency;
      const inverterOutput = invert === 0 ? 0 : invert !== null && Number.isFinite(efficiency) ? invert * efficiency : null;
      if (charge !== null && supply !== null && inverterOutput !== null) ac = charge - supply - inverterOutput;
      dc = flowSum(plan.flows, ['dc_store'], index);
    }
    const row = {start: left, end: right, ac_w: ac === null ? null : ac * 1000, dc_w: dc === null ? null : dc * 1000};
    const previous = rows.at(-1);
    if (previous && previous.end === left && previous.ac_w === row.ac_w && previous.dc_w === row.dc_w)
      previous.end = right;
    else rows.push(row);
  }
  return rows;
}

function currentPowerPlan(state, resource) {
  const plan = state.accepted;
  const restored = state.plan_recovery?.state === 'restored' && state.plan_recovery.plan_id === plan?.id &&
    state.plan_recovery.revision === state.revision;
  return plan?.valid === true && (plan.revision === state.revision || restored) &&
    (resource !== 'ev' || state.ev_plan_valid === true) && Date.parse(plan.intervals?.at(-1)?.end) > Date.parse(state.now);
}

export function plannedPowerProfileMarkup(state, task, options = {}) {
  const unavailable = '<p class="muted">Planned power profile unavailable for the current calculation.</p>';
  if (!currentPowerPlan(state, task.resource)) return unavailable;
  const rows = sessionPowerProfile(state.accepted, task, state.capabilities);
  const series = powerSeries[task.resource];
  const values = rows.flatMap(row => series.map(item => row[item.key])).filter(value => value !== null);
  if (!values.length) return unavailable;
  const start = rows[0].start, end = rows.at(-1).end;
  const low = Math.min(0, ...values), high = Math.max(1, ...values);
  const left = 70, right = 780, top = 18, bottom = 190;
  const x = at => left + (at - start) / (end - start) * (right - left);
  const y = value => bottom - (value - low) / (high - low) * (bottom - top);
  const zone = state.policy?.timezone || 'Europe/Brussels';
  const clock = (at, precise = false) => new Date(at).toLocaleTimeString('en-GB', {timeZone: zone,
    hour: '2-digit', minute: '2-digit', ...(precise ? {second: '2-digit'} : {}), timeZoneName: 'shortOffset'});
  const date = at => new Date(at).toLocaleDateString('en-GB', {timeZone: zone, day: '2-digit', month: 'short'});
  const number = value => value === null ? 'Unknown' : `${Math.round(value)} W`;
  const paths = series.map(item => {
    let path = '', previous = null;
    for (const row of rows) {
      const value = row[item.key];
      if (value === null) { previous = null; continue; }
      const contiguous = previous && previous.end === row.start;
      path += `${contiguous ? 'L' : 'M'}${x(row.start).toFixed(2)},${y(value).toFixed(2)}H${x(row.end).toFixed(2)}`;
      previous = row;
    }
    return `<path d="${path}" fill="none" stroke="${item.color}" stroke-width="2.5"/>`;
  }).join('');
  const ticks = [0, .25, .5, .75, 1].map(fraction => {
    const at = start + fraction * (end - start);
    const anchor = fraction === 0 ? 'start' : fraction === 1 ? 'end' : 'middle';
    return `<text x="${x(at)}" y="212" text-anchor="${anchor}">${escape(clock(at, end - start < 15 * 60000))}</text><text x="${x(at)}" y="230" text-anchor="${anchor}">${escape(date(at))}</text>`;
  }).join('');
  const levels = [...new Set([low, (low + high) / 2, high])].map(value =>
    `<text x="60" y="${y(value) + 4}" text-anchor="end">${Math.round(value)}</text>`).join('');
  const title = options.title || 'Planned power profile';
  const note = options.note || (task.resource === 'ev' ? 'AC charging input; energy above is delivered to the battery.' : 'AC power is positive for charging and negative for supply. Direct DC charging is separate.');
  return `<section class="task-power-profile"><h3>${escape(title)} · W</h3>
    <svg viewBox="0 0 800 240" role="img" aria-label="${escape(title)} in watts, with step changes and pauses">
    <title>${escape(title)} · ${escape(date(start))} ${escape(clock(start))} — ${escape(date(end))} ${escape(clock(end))}</title>
    <path d="M${left},${top}V${bottom}H${right} M${left},${y(0)}H${right}" class="task-power-axis"/>
    ${levels}${ticks}${paths}</svg>
    <div class="legend">${series.map(item => `<span style="--series:${item.color}">${escape(item.label)}</span>`).join('')}</div>
    <p class="muted">${escape(note)}</p><details><summary>Power levels</summary><div class="task-power-levels"><table>
    <thead><tr><th>From</th><th>Until</th>${series.map(item => `<th>${escape(item.label)}</th>`).join('')}</tr></thead>
    <tbody>${rows.map(row => `<tr><td>${escape(date(row.start))} ${escape(clock(row.start, true))}</td><td>${escape(date(row.end))} ${escape(clock(row.end, true))}</td>${series.map(item => `<td>${number(row[item.key])}</td>`).join('')}</tr>`).join('')}</tbody></table></div></details></section>`;
}

export function goalPowerProfileMarkup(state, goal) {
  const plannedGoal = state.accepted?.goals?.find(item => item.id === goal.id && item.revision === goal.revision);
  if (!plannedGoal) return '<p class="muted">No power profile for this requirement in the current plan.</p>';
  return plannedPowerProfileMarkup(state, {resource: 'ev', start: state.accepted.intervals[0]?.start, end: goal.deadline},
    {title: 'EV power before this deadline', note: 'Shared EV charging plan; sessions can support several requirements.'});
}
