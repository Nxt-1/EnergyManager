import {localDateTime} from './date-time.js';
import {monthlyPeakWatts} from './display.js';

const quarterMs = 15 * 60000;

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
    if (interval.start > cursor || !Number.isFinite(interval.power)) return null;
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
  if (!plan?.intervals?.length || plan.valid === false || state.ev_plan_valid === false) {
    result.reason = 'No usable accepted plan'; return result;
  }
  const forecastAge = (now - Date.parse(plan.forecast_at)) / 1000;
  if (!Number.isFinite(forecastAge) || forecastAge < 0 || forecastAge > state.policy.forecast_max_age_seconds) {
    result.reason = 'Accepted forecast unavailable or stale'; return result;
  }
  const timeline = plan.intervals.map((interval, t) => {
    const powers = ['grid_ev', 'grid_house', 'grid_store'].map(name => plan.flows?.[name]?.[t]);
    const power = powers.every(value => Number.isFinite(value) && value >= -1e-6) ?
      Math.max(0, powers.reduce((a, b) => a + b, 0)) : NaN;
    return {start: Date.parse(interval.start), end: Date.parse(interval.end), power};
  });
  const remaining = plannedImport(timeline, readAt, end);
  if (remaining === null) { result.reason = 'Accepted plan does not cover the remaining quarter'; return result; }
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
    if (imported === null) { result.reason = 'Accepted plan has a gap in quarter coverage'; break; }
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

export function quarterReadout(quarter, formatTime) {
  const watts = value => value === null ? 'unavailable' : `${Math.round(value)} W`;
  const seconds = Math.ceil(quarter.secondsLeft);
  return `Quarter ${formatTime(quarter.start)} – ${formatTime(quarter.end)} · ` +
    `Meter contribution ${watts(quarter.measuredWatts)} (energy ÷ 0.25 h) · ` +
    `Planned remaining contribution ${watts(quarter.remainingWatts)} · ` +
    `Projected final average ${watts(quarter.projectedWatts)} · ${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, '0')}s remaining` +
    (Number.isFinite(quarter.readAt) ? ` · Meter read ${formatTime(quarter.readAt)}` : '');
}
