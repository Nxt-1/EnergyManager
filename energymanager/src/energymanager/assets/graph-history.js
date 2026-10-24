import {scheduleDays} from './ev-schedule.js';

export function historyDayRange(date, timezone) {
  const anchor = Date.parse(`${date}T00:00:00Z`);
  const day = scheduleDays(anchor - 36 * 3600000, anchor + 60 * 3600000, timezone)
    .find(value => value.date === date);
  if (!day) throw new Error('This calendar day does not exist in the installation timezone');
  return [day.start, day.end];
}

// Only the current visible range can repaint the charts. Older requests may finish later.
export class GraphHistory {
  constructor(api, changed) {
    this.api = api;
    this.changed = changed;
    this.cache = new Map();
    this.requests = new Map();
    this.key = null;
    this.data = null;
    this.error = null;
    this.loading = false;
    this.disposed = false;
  }

  load(start, end, now) {
    if (this.disposed) return;
    start = Math.floor(start / 60000) * 60000;
    end = Math.ceil(Math.min(end, now) / 60000) * 60000;
    const key = `${start}/${end}`;
    if (this.key !== key) {
      this.key = key;
      this.data = null;
      this.error = null;
    }
    if (end <= start) {
      this.data = {series: {}, sample_count: 0};
      this.loading = false;
      return;
    }
    const cached = this.cache.get(key);
    if (cached && Date.now() - cached.saved < 30000) {
      this.data = cached.data;
      this.error = cached.error || null;
      this.loading = false;
      return;
    }
    this.loading = true;
    if (this.requests.has(key)) return;
    const query = new URLSearchParams({start: new Date(start).toISOString(),
      end: new Date(end).toISOString(), points: '1200'});
    const request = this.api(`history?${query}`).then(data => {
      if (this.disposed) return;
      this.cache.delete(key);
      this.cache.set(key, {data, saved: Date.now()});
      if (this.cache.size > 6) this.cache.delete(this.cache.keys().next().value);
      if (!this.disposed && this.key === key) {
        this.data = data;
        this.error = null;
      }
    }).catch(error => {
      if (this.disposed) return;
      this.cache.delete(key);
      this.cache.set(key, {data: null, error: error.message, saved: Date.now()});
      if (this.cache.size > 6) this.cache.delete(this.cache.keys().next().value);
      if (this.key === key) {
        this.data = null;
        this.error = error.message;
      }
    }).finally(() => {
      this.requests.delete(key);
      if (!this.disposed && this.key === key) {
        this.loading = false;
        this.changed();
      }
    });
    this.requests.set(key, request);
  }

  get status() {
    if (this.error) return `Archive history unavailable · recent samples only · ${this.error}`;
    if (this.loading && !this.data) return 'Loading recorded graph history…';
    if (!this.data?.sample_count) return 'No archived measurements in this period. Missing history remains blank.';
    const detail = Math.ceil(this.data.bucket_seconds);
    return `Recorded history · up to ${detail}s detail · gaps indicate missing data${
      this.data.capacity_fallback ? ' · older battery percentages use current configured capacities' : ''}`;
  }

  dispose() {
    this.disposed = true;
    this.cache.clear();
  }
}

export function observedPoints(state, archive, name, soc = false) {
  const series = soc ? `${name}_soc` : name;
  const recent = new Map();
  for (const sample of state.observed) {
    const at = Date.parse(sample.at);
    if (!Number.isFinite(at)) continue;
    const valid = sample.quality === (state.demo ? 'SYNTHETIC' : 'measured');
    if (recent.get(at)?.valid) continue;
    let value = null;
    if (valid && soc) {
      const capacity = sample[`${name}_capacity_kwh`] ?? state.capabilities[`${name}_capacity_kwh`];
      const energy = sample[`${name}_kwh`];
      if ((name !== 'ev' || sample.ev_state_known !== false) && Number.isFinite(energy) &&
          energy >= 0 && capacity > 0 && energy <= capacity) value = energy / capacity * 100;
    } else if (valid) {
      value = {grid: sample.house_kw + sample.ev_power_kw - sample.pv_ac_kw - sample.ess_power_kw,
        ess: sample.ess_power_kw, solar: sample.pv_ac_kw + sample.pv_dc_kw,
        house: sample.house_kw, ev: sample.ev_power_kw}[name] * 1000;
      if (!Number.isFinite(value)) value = null;
    }
    recent.set(at, {valid, value});
  }
  const samples = [...recent].sort((a, b) => a[0] - b[0]);
  const cutoff = archive ? samples.find(([, reading]) => reading.value !== null)?.[0] ?? Infinity :
    samples[0]?.[0] ?? Infinity;
  const points = (archive?.series?.[series] || []).filter(point => point[0] < cutoff);
  const maxAge = state.policy.measurement_max_age_seconds * 1000;
  let previous = points.at(-1)?.[1] !== null ? points.at(-1)?.[0] ?? null : null;
  for (const [at, reading] of samples) {
    if (archive && at < cutoff) continue;
    if (previous !== null && at - previous > maxAge) points.push([previous + maxAge, null]);
    points.push([at, reading.value]);
    previous = at;
  }
  if (previous !== null && Date.parse(state.now) - previous > maxAge) points.push([previous + maxAge, null]);
  return points;
}
