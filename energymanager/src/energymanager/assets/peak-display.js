import {localDateTime} from './date-time.js';
import {monthlyPeakWatts} from './display.js';

const quarterMs = 15 * 60000;
const evFlows = ['grid_ev','pv_ev','solar_dis_ev','one','three','amps_one','amps_three'];
const essFlows = ['grid_store','pv_store','dc_store','solar_dis_ev','solar_dis_house','grid_dis_house','dc_invert'];
const resourceFlows = [...new Set([...evFlows,...essFlows,'grid_house'])];

// An unusable resource invalidates the whole joint interval; no flow is removed/rebalanced.
function gridTimeline(state) {
  const timeline = [], now = Date.parse(state.now);
  const append = (plan, left, right, authority, followHandover = true) => {
    if (!(right > left)) return;
    if (!plan?.intervals?.length) {
      timeline.push({start:left,end:right,power:NaN,issue:'Accepted execution coverage unavailable'}); return;
    }
    const handover = followHandover && plan.execution_handover;
    const boundary = Date.parse(handover?.until);
    if (handover && boundary > left) {
      const inherited = {ev:authority?.ev === true && handover.ev_valid === true,
        ess:authority?.ess === true && handover.ess_valid === true,
        conditional:authority?.conditional === true && handover.conditional_valid === true};
      append(handover.plan, left, Math.min(right,boundary), inherited);
      if (right > boundary) append(plan,boundary,right,authority,false);
      return;
    }
    if (state.deadline_execution?.active && state.deadline_execution.plan_id === plan.id) {
      const guard = plan.deadline_guard;
      if (guard?.status !== 'certified' || !guard.context?.intervals?.length || !guard.flows
          || !Number.isFinite(Date.parse(guard.scope?.deadline))) {
        timeline.push({start:left,end:right,power:NaN,issue:'Deadline execution coverage unavailable'}); return;
      }
      const end = Date.parse(guard.scope.deadline);
      if (right > end) timeline.push({start:Math.max(left,end),end:right,power:NaN,issue:'Deadline execution coverage ends before this quarter'});
      right = Math.min(right,end);
      plan = {...plan, intervals:guard.context.intervals,flows:guard.flows,conditional_tasks:[]};
    }
    const age = (now - Date.parse(plan.forecast_at)) / 1000;
    const expired = !Number.isFinite(age) || age < 0 || age > state.policy.forecast_max_age_seconds;
    let previous = -Infinity;
    for (const [t, interval] of (plan.intervals || []).entries()) {
      const start = Date.parse(interval.start), end = Date.parse(interval.end);
      const malformed = !Number.isFinite(start) || !Number.isFinite(end) || end <= start || start < previous;
      previous = end;
      if (end <= left || start >= right) continue;
      const values = Object.fromEntries(resourceFlows.map(name => [name,plan.flows?.[name]?.[t]]));
      const missing = resourceFlows.some(name => !Number.isFinite(values[name]) || values[name] < -1e-6);
      const ev = evFlows.some(name => values[name] > 1e-6), ess = essFlows.some(name => values[name] > 1e-6);
      const conditional = ev && ((plan.conditional_tasks || []).some(task =>
        !Number.isFinite(Date.parse(task.scheduled_start)) || !Number.isFinite(Date.parse(task.deadline))
        || Date.parse(task.scheduled_start) < end && Date.parse(task.deadline) > start)
        || !Array.isArray(plan.conditional_tasks) && (plan.reasons || []).some(reason=>reason.kind==='joint_capture'));
      const run = state.appliance_run?.run, task = plan.appliance;
      const appliance = (!task || task.id !== null) &&
        (interval.dishwasher_kw > 1e-6 || plan.flows?.dishwasher_power?.[t] > 1e-6);
      const applianceUsable = !appliance || run && task && run.id === task.id && run.revision === task.revision
        && !run.blocked && (run.phase === 'queued' && plan.revision === state.revision && run.plan_id === plan.id
          && typeof task.planned_start === 'string' && task.planned_start === run.planned_start
          || run.phase === 'running' && run.timing_known !== false
          && typeof task.started_at === 'string' && task.started_at === run.started_at);
      const issue = plan.valid === false ? 'Accepted plan is invalid' : expired ? 'Accepted forecast unavailable or stale' :
        malformed || missing ? 'Accepted resource coverage unavailable' : !authority ? 'Resource authority unavailable' :
        ev && authority.ev !== true ? 'EV instructions are no longer authorized' :
        ess && authority.ess !== true ? 'ESS instructions are no longer authorized' :
        conditional && authority.conditional !== true ? 'Conditional instructions are no longer authorized' : '';
      const unavailable = issue || (!applianceUsable ? 'Appliance execution coverage unavailable' : '');
      const power = unavailable ? NaN : Math.max(0, values.grid_ev + values.grid_house + values.grid_store);
      timeline.push({start:Math.max(left,start),end:Math.min(right,end),power,issue:unavailable});
    }
  };
  const plan = state.accepted;
  append(plan,Date.parse(plan.intervals[0].start),Date.parse(plan.intervals.at(-1).end),
    state.plan_authority && {...state.plan_authority,ev:state.plan_authority.ev === true && state.ev_plan_valid !== false});
  return timeline.sort((a,b)=>a.start-b.start);
}

export function quarterStart(at, zone) {
  const minute = Number(localDateTime(new Date(at).toISOString(), zone).slice(-2));
  const date = new Date(at);
  return at - (minute % 15 * 60 + date.getUTCSeconds()) * 1000 - date.getUTCMilliseconds();
}

export function quarterBands(start, end, now, zone) {
  const bands = [];
  for (let at = quarterStart(start, zone); at < end; at += quarterMs) {
    const local = localDateTime(new Date(at).toISOString(), zone);
    bands.push({start: Math.max(start, at), end: Math.min(end, at + quarterMs),
      alternate: Number(local.slice(-2)) / 15 % 2 === 1, active: at <= now && now < at + quarterMs});
  }
  return bands;
}

// Meter import is gross imported energy. Export never subtracts from this counter.
function plannedImport(timeline, start, end) {
  let low = 0, high = timeline.length;
  while (low < high) {
    const middle = Math.floor((low + high) / 2);
    if (timeline[middle].end <= start) low = middle + 1;
    else high = middle;
  }
  let cursor = start, energy = 0;
  for (let t = low; t < timeline.length; t++) {
    const interval = timeline[t], right = Math.min(end, interval.end);
    if (interval.start > cursor || !Number.isFinite(interval.power) || interval.end <= interval.start) return null;
    energy += interval.power * (right - cursor) / 3600000;
    cursor = right;
    if (cursor >= end) return energy;
  }
  return null;
}

export function quarterMeasurement(state) {
  const now = Date.parse(state.now), zone = state.policy.timezone;
  const start = quarterStart(now, zone), end = start + quarterMs;
  const reading = state.demo ? {at: state.observation.at, energy_kwh: state.observation.quarter_import_kwh} :
    state.live_inputs?.quarter;
  const readAt = Date.parse(reading?.at), age = (now - readAt) / 1000;
  const energy = reading?.energy_kwh;
  const fresh = !reading?.issue && age >= 0 && age <= (state.policy.measurement_max_age_seconds ?? 30)
    && readAt >= start && readAt < end && Number.isFinite(energy) && energy >= 0;
  return {start, end, readAt, secondsLeft: Math.max(0, (end - now) / 1000),
    measuredWatts: fresh ? energy * 4000 : null, projectedWatts: null, remainingWatts: null};
}

export function peakDisplay(state) {
  const now = Date.parse(state.now), zone = state.policy.timezone, quarter = quarterMeasurement(state);
  const {start, end, readAt} = quarter, energy = quarter.measuredWatts / 4000;
  const result = {quarter, predicted: [], reason: ''};
  if (quarter.measuredWatts === null) { result.reason = 'Current-quarter meter unavailable or stale'; return result; }
  const plan = state.accepted;
  if (!plan?.intervals?.length || plan.valid === false) {
    result.reason = 'No usable accepted plan'; return result;
  }
  const forecastAge = (now - Date.parse(plan.forecast_at)) / 1000;
  if (!Number.isFinite(forecastAge) || forecastAge < 0 || forecastAge > state.policy.forecast_max_age_seconds) {
    result.reason = 'Accepted forecast unavailable or stale'; return result;
  }
  const timeline = gridTimeline(state);
  const unavailable = (left,right,fallback) => timeline.find(i=>i.end>left && i.start<right && i.issue)?.issue || fallback;
  const remaining = plannedImport(timeline, readAt, end);
  if (remaining === null) { result.reason = unavailable(readAt,end,'Accepted plan does not cover the remaining quarter'); return result; }
  quarter.remainingWatts = remaining * 4000;
  quarter.projectedWatts = quarter.measuredWatts + quarter.remainingWatts;
  let peak = monthlyPeakWatts(state);
  if (peak === null) { result.reason = 'Recorded monthly peak unavailable'; return result; }
  const month = at => localDateTime(new Date(at).toISOString(), zone).slice(0, 7);
  result.predicted.push([now, peak]);
  const horizon = Date.parse(plan.intervals.at(-1).end);
  for (let left = start; left + quarterMs <= horizon; left += quarterMs) {
    const right = left + quarterMs;
    const imported = left === start ? energy + remaining : plannedImport(timeline, left, right);
    if (imported === null) { result.reason = unavailable(left,right,'Accepted plan has a gap in quarter coverage'); break; }
    const previous = peak;
    peak = Math.max(peak, imported * 4000);
    // Preserve steps at the exact boundary; a following month starts a new forecast.
    const boundary = month(left) === month(right) ? right : right - 1;
    result.predicted.push([boundary, previous], [boundary, peak]);
    if (month(left) !== month(right)) {
      peak = 0;
      result.predicted.push([right, 0]);
    }
  }
  return result;
}
