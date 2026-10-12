// Keep a 24-hour visible window, backed by two full days of already-loaded data.
function energyManagerOverviewBase(now = new Date()) {
  const six = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 6);
  const start = now >= six ? six : new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1, 6);
  const end = new Date(start.getFullYear(), start.getMonth(), start.getDate() + 1, 6);
  return { start: start.getTime(), end: end.getTime() };
}

const energyManagerOverviewNavigation = (() => {
  let hours = 0;
  let notifyFrame = null;
  return {
    get hours() { return hours; },
    set(next) {
      const value = Math.max(0, Math.min(24, Math.round((Number(next) || 0) * 20) / 20));
      if (value === hours) return;
      hours = value;
      // Coalesce rapid pointer events; keep the slider and chart within one animation frame.
      if (notifyFrame === null) notifyFrame = requestAnimationFrame(() => {
        notifyFrame = null;
        window.dispatchEvent(new CustomEvent('energymanager-overview-window-change', { detail: { hours } }));
      });
    },
    reset() { this.set(0); }
  };
})();
window.energyManagerOverviewNavigation = energyManagerOverviewNavigation;

class EnergyManagerTimeNavigator extends HTMLElement {
  setConfig(config) { this._config = config || {}; if (this.isConnected) this.render(); }
  set hass(hass) { this._hass = hass; }
  connectedCallback() {
    this._listener = () => this._update();
    window.addEventListener('energymanager-overview-window-change', this._listener);
    this.render();
  }
  disconnectedCallback() {
    window.removeEventListener('energymanager-overview-window-change', this._listener);
  }
  getCardSize() { return 1; }
  _update() {
    if (!this.isConnected) return;
    const hours = energyManagerOverviewNavigation.hours;
    const base = energyManagerOverviewBase();
    const fmt = ms => new Date(ms).toLocaleString(undefined, {
      weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false
    });
    const slider = this.querySelector('input[type="range"]');
    if (!slider) return;
    slider.value = String(hours);
    this.querySelector('[data-back]').disabled = hours <= 0;
    this.querySelector('[data-forward]').disabled = hours >= 24;
    this.querySelector('[data-reset]').disabled = hours <= 0;
    this.querySelector('[data-time-label]').textContent =
      `${fmt(base.start + hours * 3600000)} — ${fmt(base.end + hours * 3600000)}`;
  }
  render() {
    if (!this.isConnected) return;
    // Do not reconstruct the input on navigation events: doing so cancels mouse dragging.
    this.innerHTML = `<ha-card><div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;` +
      `padding:10px 14px;box-sizing:border-box">` +
      `<strong style="font-size:13px;white-space:nowrap">24 h view</strong>` +
      `<button data-back title="Back 6 hours" aria-label="Back 6 hours">‹ 6h</button>` +
      `<input type="range" min="0" max="24" step="0.05" value="0" ` +
      `aria-label="Move 24-hour chart window towards tomorrow" style="flex:1;min-width:100px;accent-color:var(--primary-color)">` +
      `<button data-forward title="Forward 6 hours" aria-label="Forward 6 hours">6h ›</button>` +
      `<button data-reset title="Return to current day">Today</button>` +
      `<span data-time-label style="font-size:12px;color:var(--secondary-text-color);white-space:nowrap"></span>` +
      `</div></ha-card>`;
    for (const button of this.querySelectorAll('button')) {
      Object.assign(button.style, {
        background: 'var(--secondary-background-color)', color: 'var(--primary-text-color)',
        border: '1px solid var(--divider-color)', borderRadius: '6px', padding: '5px 9px', cursor: 'pointer'
      });
    }
    this.querySelector('[data-back]').addEventListener('click', () =>
      energyManagerOverviewNavigation.set(energyManagerOverviewNavigation.hours - 6));
    this.querySelector('[data-forward]').addEventListener('click', () =>
      energyManagerOverviewNavigation.set(energyManagerOverviewNavigation.hours + 6));
    this.querySelector('[data-reset]').addEventListener('click', () => energyManagerOverviewNavigation.reset());
    // 'input' fires continuously while dragging, not only when the handle is released.
    this.querySelector('input').addEventListener('input', event =>
      energyManagerOverviewNavigation.set(event.target.value));
    this._update();
  }
}
if (!customElements.get('energymanager-time-navigator')) {
  customElements.define('energymanager-time-navigator', EnergyManagerTimeNavigator);
}

class EnergyManagerTimelineCard extends HTMLElement {
  setConfig(config) {
    if (!config?.entity) throw new Error('EnergyManager timeline requires an entity');
    this.config = config;
  }
  set hass(hass) {
    this._hass = hass;
    // Do not overwrite an open dialog during HA state refresh.
    if (!this.querySelector('dialog[open]')) this.render();
  }
  connectedCallback() {
    this._onPlotBounds = () => this._scheduleAlignment();
    this._onNavigation = () => {
      if (this._navRenderTimer !== null && this._navRenderTimer !== undefined) return;
      this._navRenderTimer = setTimeout(() => {
        this._navRenderTimer = null;
        if (!this.querySelector('dialog[open]')) this.render();
      }, 90);
    };
    window.addEventListener('energymanager-power-plot-bounds', this._onPlotBounds);
    window.addEventListener('energymanager-overview-window-change', this._onNavigation);
    // A chart may publish its plot bounds while HA is still mounting the timeline.
    // Retry when the timeline becomes visible, including after card/view resizing.
    if (!this._alignTimer) this._alignTimer = setInterval(() => this._alignPlot(), 2000);
    this._scheduleAlignment();
  }
  disconnectedCallback() {
    window.removeEventListener('energymanager-power-plot-bounds', this._onPlotBounds);
    window.removeEventListener('energymanager-overview-window-change', this._onNavigation);
    clearInterval(this._alignTimer);
    this._alignTimer = null;
    clearTimeout(this._navRenderTimer);
    this._navRenderTimer = null;
    if (this._alignFrame !== undefined) cancelAnimationFrame(this._alignFrame);
    this._alignFrame = undefined;
  }
  getCardSize() { return 3; }
  _scheduleAlignment() {
    if (this._alignFrame !== undefined) return;
    this._alignFrame = requestAnimationFrame(() => {
      this._alignFrame = undefined;
      this._alignPlot();
    });
  }
  _alignPlot() {
    if (!this.config?.fixed_day_window || !this.isConnected) return;
    const area = this.querySelector('[data-em-plot-area]');
    const bounds = window.energyManagerPowerPlotBounds;
    if (!area || !bounds || Date.now() - bounds.at > 60000) return;

    const rect = area.getBoundingClientRect();
    // A 0x0 rectangle is common when HA sets `hass` before its card is laid out.
    // In that case, the plot's viewport coordinates cannot be compared yet.
    if (rect.width < 20 || !Number.isFinite(rect.left) || !Number.isFinite(rect.right)) {
      window.energyManagerPlotAlignmentStatus = {
        plotFound: true, aligned: false, reason: 'timeline-awaiting-layout',
        timelineWidthPx: rect.width, powerPlotLeftPx: bounds.left,
        powerPlotRightPx: bounds.right
      };
      return;
    }

    // The rectangle may already include our previous margins. Recover its
    // original boundaries without removing those margins (avoids reflow/flicker).
    const oldLeft = Number.parseFloat(area.style.marginLeft) || 0;
    const oldRight = Number.parseFloat(area.style.marginRight) || 0;
    const baseLeft = rect.left - oldLeft;
    const baseRight = rect.right + oldRight;
    const left = Math.max(0, bounds.left - baseLeft);
    const right = baseRight - bounds.right;
    const valid = left < 150 && right > -20 && right < 150 && bounds.right > bounds.left;
    if (valid) {
      if (Math.abs(left - oldLeft) > 0.5) area.style.marginLeft = `${left.toFixed(1)}px`;
      if (Math.abs(right - oldRight) > 0.5) area.style.marginRight = `${right.toFixed(1)}px`;
    }
    window.energyManagerPlotAlignmentStatus = {
      plotFound: true, aligned: valid, reason: valid ? 'ok' : 'plot-outside-timeline',
      leftOffsetPx: left, rightOffsetPx: right,
      powerPlotLeftPx: bounds.left, powerPlotRightPx: bounds.right,
      timelineBaseLeftPx: baseLeft, timelineBaseRightPx: baseRight,
      timelineWidthPx: rect.width
    };
  }

  render() {
    if (!this._hass || !this.config) return;
    const entity = this._hass.states[this.config.entity];
    const segments = Array.isArray(entity?.attributes?.segments) ? entity.attributes.segments : [];
    const hours = Math.max(1, Math.min(168, Number(this.config.hours || 24)));
    const now = Date.now();
    let windowStart = now;
    let windowEnd = now + hours * 3600000;
    const fixedWindow = this.config.fixed_day_window === true;
    if (fixedWindow) {
      const base = energyManagerOverviewBase(new Date(now));
      const move = energyManagerOverviewNavigation.hours * 3600000;
      windowStart = base.start + move;
      windowEnd = base.end + move;
    }
    const label = (ms) => new Date(ms).toLocaleString(undefined, {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false
    });
    const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({
      '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'
    }[c]));
    // The timeline sensor contains future execution segments only; do not fabricate past tasks.
    const visible = segments.filter(s => new Date(s.end).getTime() > Math.max(now, windowStart) &&
      new Date(s.start).getTime() < windowEnd);
    const items = visible.map((s, i) => {
      const start = Math.max(now, windowStart, new Date(s.start).getTime());
      const stop = Math.min(windowEnd, new Date(s.end).getTime());
      const left = 100 * (start - windowStart) / (windowEnd - windowStart);
      const width = 100 * (stop - start) / (windowEnd - windowStart);
      return `<button type="button" data-idx="${i}" aria-label="Details for ${esc(s.name)}" title="${esc(s.name)}: ${esc(label(new Date(s.start).getTime()))}" style="position:absolute;left:${left}%;width:${width}%;top:5px;height:30px;background:var(--primary-color);border:0;border-radius:4px;color:var(--text-primary-color,#fff);cursor:pointer;overflow:hidden;white-space:nowrap;font-weight:600;min-width:2px">${width>7?esc(s.name):''}</button>`;
    }).join('');
    const nowPosition = 100 * (now - windowStart) / (windowEnd - windowStart);
    const nowMarker = fixedWindow && nowPosition >= 0 && nowPosition <= 100 ?
      `<div title="Now" style="position:absolute;z-index:2;left:${nowPosition}%;top:0;height:40px;border-left:2px dashed var(--primary-text-color);opacity:.8;pointer-events:none"></div>` : '';
    const axis = fixedWindow ? Array.from({ length: 5 }, (_, i) => {
      const t = new Date(windowStart + (windowEnd - windowStart) * i / 4);
      const pos = i * 25;
      const align = i === 0 ? '0%' : i === 4 ? '-100%' : '-50%';
      const hour = t.getHours().toString().padStart(2, '0');
      return `<span style="position:absolute;left:${pos}%;transform:translateX(${align});white-space:nowrap">${hour}:00</span>`;
    }).join('') : '';
    const heading = fixedWindow ? '' :
      `<div style="display:flex;justify-content:space-between;font-size:12px;opacity:.7;margin-bottom:6px"><span>${esc(label(windowStart))}</span><span>${esc(label(windowEnd))}</span></div>`;
    this.innerHTML = `<ha-card header="${esc(this.config.title || 'Scheduled tasks')}"><div class="card-content">
      ${heading}
      <div data-em-plot-area>
      <div style="position:relative;background:var(--secondary-background-color);height:40px;border-radius:6px;overflow:hidden">${items}${nowMarker}</div>
      ${fixedWindow ? `<div style="position:relative;height:18px;margin-top:6px;font-size:11px;opacity:.7">${axis}</div>` : ''}
      </div>
      ${visible.length ? '' : '<p style="opacity:.7">No planned execution in this period.</p>'}
      <small style="display:block;opacity:.65;margin-top:10px">${esc(entity?.attributes?.generated_at_utc ? 'Plan: '+label(new Date(entity.attributes.generated_at_utc).getTime()) : 'Waiting for plan')}</small>
      </div></ha-card><dialog aria-label="Scheduled task details" style="border:1px solid var(--divider-color);border-radius:12px;background:var(--card-background-color,var(--primary-background-color));color:var(--primary-text-color);padding:20px;width:min(420px,calc(100vw - 48px));box-shadow:0 12px 35px #0005"></dialog>`;
    const dialog = this.querySelector('dialog');
    this.querySelectorAll('button[data-idx]').forEach(btn => btn.addEventListener('click', () => {
      const item = visible[Number(btn.dataset.idx)];
      const kwh = Number(item.energy_kwh), watts = Number(item.peak_power_w);
      dialog.innerHTML = `<div style="display:flex;align-items:center;justify-content:space-between;gap:12px"><strong>${esc(item.name)} · Scheduled</strong><button type="button" data-close style="background:none;border:0;color:inherit;font-size:23px;cursor:pointer" aria-label="Close">×</button></div>
        <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-top:20px">
          <div>Start<br><b>${esc(label(new Date(item.start).getTime()))}</b></div>
          <div>End<br><b>${esc(label(new Date(item.end).getTime()))}</b></div>
          <div>Energy<br><b>${Number.isFinite(kwh) ? kwh.toFixed(2)+' kWh' : '—'}</b></div>
          <div>Peak power<br><b>${Number.isFinite(watts) ? Math.round(watts)+' W' : '—'}</b></div>
        </div><p style="opacity:.7;font-size:12px;margin-bottom:0">Scheduled execution period, not a uniquely assigned departure task.</p>`;
      dialog.querySelector('[data-close]').addEventListener('click', () => dialog.close());
      dialog.showModal();
    }));
    dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
    this._scheduleAlignment();
  }
}
if (!customElements.get('energymanager-timeline-card')) {
  customElements.define('energymanager-timeline-card', EnergyManagerTimelineCard);
}


// One Recorder request for all five Overview power sources, shared by all five series.
// Custom ApexCharts data_generators bypass the card's normal Recorder cache.
const energyManagerPowerHistory = (() => {
  const SAMPLE_MS = 5 * 60 * 1000;
  const IDS = [
    'sensor.energy_manager_house_load_power',
    'sensor.energy_manager_background_load_power',
    'sensor.energy_manager_grid_power',
    'sensor.energy_manager_ess_power',
    'sensor.energy_manager_pv_solax_power'
  ];
  const indices = new Map(IDS.map((id, i) => [id, i]));
  const requests = new Map();
  const stats = { requests: 0, lastDurationMs: null, lastRawRows: 0, lastSamples: 0 };

  function readRows(history, id, i) {
    const rows = Array.isArray(history) ? (history[i] || []) : (history?.[id] || []);
    return rows.map(row => {
      const raw = row.s ?? row.state;
      const value = Number(raw);
      const timestamp = typeof row.lu === 'number' ? row.lu * 1000
        : Date.parse(row.last_updated || row.last_changed || '');
      return { value, timestamp, valid: raw != null &&
        !['unknown', 'unavailable', ''].includes(String(raw)) };
    }).filter(row => row.valid && Number.isFinite(row.value) && Number.isFinite(row.timestamp))
      .sort((a, b) => a.timestamp - b.timestamp);
  }

  async function load(hass, startMs, cutoff) {
    // A stable, 5-minute-aligned cutoff makes concurrent generators use the same key.
    const key = `${startMs}/${cutoff}`;
    if (requests.has(key)) return requests.get(key);
    const task = (async () => {
      const t0 = performance.now();
      stats.requests++;
      const history = await hass.callWS({
        type: 'history/history_during_period',
        entity_ids: IDS,
        start_time: new Date(startMs).toISOString(),
        end_time: new Date(cutoff).toISOString(),
        minimal_response: true,
        significant_changes_only: false,
        no_attributes: true
      });
      const records = IDS.map((id, i) => readRows(history, id, i));
      const cursors = IDS.map(() => 0);
      const latest = IDS.map(() => null);
      const samples = [];
      for (let t = Math.ceil(startMs / SAMPLE_MS) * SAMPLE_MS; t <= cutoff; t += SAMPLE_MS) {
        for (let i = 0; i < IDS.length; i++) {
          while (cursors[i] < records[i].length && records[i][cursors[i]].timestamp <= t) {
            latest[i] = records[i][cursors[i]].value;
            cursors[i]++;
          }
        }
        samples.push([t, ...latest]);
      }
      stats.lastDurationMs = Math.round(performance.now() - t0);
      stats.lastRawRows = records.reduce((sum, rows) => sum + rows.length, 0);
      stats.lastSamples = samples.length;
      return samples;
    })();
    // Keep only the current 5-minute window, releasing stale history and failed requests.
    requests.clear();
    requests.set(key, task);
    task.catch(() => { if (requests.get(key) === task) requests.delete(key); });
    return task;
  }

  return {
    stats,
    async getPoints(hass, start, end, sources) {
      const startMs = start.getTime();
      const finish = end.getTime();
      const cutoff = Math.floor(Math.min(Date.now(), finish) / SAMPLE_MS) * SAMPLE_MS;
      if (cutoff <= startMs) return [];
      const columns = sources.map(id => indices.get(id));
      if (columns.some(i => i === undefined)) throw new Error('Unrecognized power source');
      const data = await load(hass, startMs, cutoff);
      return data.filter(row => columns.every(i => row[i + 1] !== null))
        .map(row => [row[0], columns.reduce((sum, i) => sum + row[i + 1], 0)]);
    }
  };
})();
window.energyManagerPowerHistory = energyManagerPowerHistory;

// Keep ApexCharts anchored to 06:00 local time instead of following the current minute.
// A wrapper is needed because a static +6h offset would exclude 'Now' between 00:00 and 06:00.
class EnergyManagerDayChart extends HTMLElement {
  setConfig(config) {
    if (!config?.series || !config?.graph_span) {
      throw new Error('EnergyManager day chart requires an ApexCharts series and graph_span');
    }
    this._config = config;
    this._refresh();
  }

  set hass(hass) {
    this._hass = hass;
    this._refresh();
    if (this._chartReady) {
      this._chart.hass = hass;
      this._scheduleViewport();
    }
  }

  connectedCallback() {
    if (!this._timer) this._timer = setInterval(() => this._refresh(), 60_000);
    if (!this._plotTimer) this._plotTimer = setInterval(() => {
      this._broadcastPlotBounds();
      this._applyViewport(); // Reassert the viewport after ApexCharts' own data refresh.
    }, 2000);
    if (this._isOverview()) {
      this._navListener = () => this._scheduleViewport();
      window.addEventListener('energymanager-overview-window-change', this._navListener);
    }
    this._refresh();
  }

  disconnectedCallback() {
    clearInterval(this._timer);
    clearInterval(this._plotTimer);
    this._timer = null;
    this._plotTimer = null;
    if (this._navListener) window.removeEventListener('energymanager-overview-window-change', this._navListener);
    this._navListener = null;
    clearTimeout(this._viewportTimer);
    this._viewportTimer = null;
    // Discard card factory work that may finish after a view is removed.
    this._buildId = (this._buildId || 0) + 1;
    this._windowKey = null;
  }

  getCardSize() {
    return this._chart?.getCardSize?.() ?? 5;
  }

  _isOverview() {
    return this._config?.header?.title?.startsWith('Power ·') ||
      this._config?.header?.title?.startsWith('Battery SoC ·');
  }

  // Load two complete 06:00-to-06:00 days once. The visible 24h is clipped via ApexCharts xaxis.
  _window(now = new Date()) {
    const base = energyManagerOverviewBase(now);
    const first = new Date(base.start);
    const days = this._isOverview() ? 2 : Number(this._config?.graph_span?.match(/^(\d+)d$/)?.[1] ?? 1);
    const end = new Date(first.getFullYear(), first.getMonth(), first.getDate() + days, 6);
    const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const offset = Math.round((base.start - midnight.getTime()) / 3600000);
    const hours = Math.round((end.getTime() - base.start) / 3600000);
    return {
      key: `${base.start}/${end.getTime()}`,
      offset: `${offset >= 0 ? '+' : ''}${offset}h`,
      span: `${hours}h`
    };
  }

  _overviewViewport() {
    const base = energyManagerOverviewBase();
    const move = energyManagerOverviewNavigation.hours * 3600000;
    return { min: base.start + move, max: base.end + move };
  }

  _scheduleViewport() {
    if (!this._isOverview() || !this.isConnected || this._viewportTimer !== null && this._viewportTimer !== undefined) return;
    // Reuse the loaded 48h series; throttling prevents expensive redraws on every pointer pixel.
    this._viewportTimer = setTimeout(() => {
      this._viewportTimer = null;
      this._applyViewport();
    }, 100);
  }

  _applyViewport() {
    if (!this._isOverview() || !this.isConnected) return;
    const apex = this._chart?._apexChart;
    if (!apex?.w?.globals?.dom?.baseEl || typeof apex.updateOptions !== 'function') return;
    const { min, max } = this._overviewViewport();
    const actual = apex.w.config?.xaxis;
    if (Math.abs(Number(actual?.min) - min) < 1 && Math.abs(Number(actual?.max) - max) < 1) return;
    if (this._viewportBusy) { this._viewportDirty = true; return; }
    this._viewportBusy = true;
    this._viewportDirty = false;
    // Disable animation here: this is panning a viewport, not animating fresh data.
    Promise.resolve().then(() => apex.updateOptions({ xaxis: { min, max } }, false, false, false))
      .catch(error => console.warn('[EnergyManager Dashboard] Could not pan chart viewport:', error))
      .finally(() => {
        this._viewportBusy = false;
        if (!this.isConnected) return;
        this._broadcastPlotBounds();
        if (this._viewportDirty ||
            Math.abs(Number(apex.w.config?.xaxis?.min) - this._overviewViewport().min) > 1) {
          this._viewportDirty = false;
          this._scheduleViewport();
        }
      });
  }

  // ApexCharts' SVG may be inside multiple HA/custom-card shadow roots.
  // querySelector() does not cross shadow roots, so discover the visible plot recursively.
  _findPlotElement(root) {
    if (!root) return null;
    const pending = [root];
    if (root.shadowRoot) pending.push(root.shadowRoot);
    while (pending.length) {
      const current = pending.pop();
      const plot = current.querySelector?.('.apexcharts-gridRect');
      if (plot && plot.getBoundingClientRect().width > 20) return plot;
      for (const element of current.querySelectorAll?.('*') || []) {
        if (element.shadowRoot) pending.push(element.shadowRoot);
      }
    }
    return null;
  }

  _installDragToPan(card) {
    if (!this._isOverview()) return;
    let drag = null;
    card.addEventListener('pointerdown', event => {
      if (event.button !== 0 || event.ctrlKey || event.metaKey) return;
      const rect = this._findPlotElement(card)?.getBoundingClientRect();
      if (!rect?.width || event.clientX < rect.left || event.clientX > rect.right ||
          event.clientY < rect.top || event.clientY > rect.bottom) return;
      drag = { id: event.pointerId, x: event.clientX, y: event.clientY, width: rect.width };
    }, { capture: true });
    card.addEventListener('pointerup', event => {
      if (!drag || drag.id !== event.pointerId) return;
      const dx = event.clientX - drag.x;
      const dy = event.clientY - drag.y;
      if (Math.abs(dx) > 35 && Math.abs(dx) > Math.abs(dy) * 1.4) {
        const delta = Math.round(-dx / drag.width * 24);
        if (delta) energyManagerOverviewNavigation.set(energyManagerOverviewNavigation.hours + delta);
      }
      drag = null;
    }, { capture: true });
    card.addEventListener('pointercancel', () => { drag = null; });
  }

  _broadcastPlotBounds() {
    const overview = this._config?.header?.title?.startsWith('Power ·');
    const planning = this._config?.header?.title?.startsWith('7 days · AC power');
    if (!overview && !planning) return;
    const statusKey = planning ? 'energyManagerPlanningPlotStatus' : 'energyManagerPlotAlignmentStatus';
    const boundsKey = planning ? 'energyManagerPlanningPowerPlotBounds' : 'energyManagerPowerPlotBounds';
    const eventName = planning ? 'energymanager-planning-power-plot-bounds' : 'energymanager-power-plot-bounds';
    const card = this._chart;
    if (!card?.isConnected) return;

    const instance = card._apexChart;
    const globals = instance?.w?.globals;
    const base = globals?.dom?.baseEl;
    let rect = null;
    let method = null;

    // Access the rendered SVG through ApexCharts' own DOM reference first.
    // The surrounding Lovelace card may use nested shadow roots inaccessible
    // through queries starting at the outer custom-card element.
    const nativeGrid = base?.querySelector?.('.apexcharts-gridRect');
    if (nativeGrid) {
      const box = nativeGrid.getBoundingClientRect();
      if (box.width > 20 && Number.isFinite(box.left) && Number.isFinite(box.right)) {
        rect = box;
        method = 'apex-dom-grid';
      }
    }

    // If that grid rectangle is absent, ApexCharts already knows the plot's
    // x translation and width. Transform SVG units to screen CSS pixels.
    if (!rect && globals) {
      const svg = base?.querySelector?.('.apexcharts-svg') ||
        globals.dom?.Paper?.node || base?.querySelector?.('svg');
      const svgBox = svg?.getBoundingClientRect?.();
      const translateX = Number(globals.translateX);
      const gridWidth = Number(globals.gridWidth);
      const svgWidth = Number(globals.svgWidth);
      if (svgBox?.width > 20 && svgWidth > 20 && gridWidth > 20 &&
          Number.isFinite(translateX) && Number.isFinite(svgBox.left)) {
        const scale = svgBox.width / svgWidth;
        const left = svgBox.left + translateX * scale;
        const right = left + gridWidth * scale;
        if (left >= svgBox.left - 2 && right <= svgBox.right + 2 && right - left > 20) {
          rect = { left, right, width: right - left };
          method = 'apex-globals';
        }
      }
    }

    // Preserve the original recursive DOM search as a final fallback.
    if (!rect) {
      if (!this._plotElement?.isConnected) this._plotElement = this._findPlotElement(card);
      const fallback = this._plotElement?.getBoundingClientRect();
      if (fallback?.width > 20 && Number.isFinite(fallback.left) && Number.isFinite(fallback.right)) {
        rect = fallback;
        method = 'shadow-dom';
      }
    }
    if (!rect) {
      window[statusKey] = {
        plotFound: false, aligned: false,
        apexInstance: Boolean(instance), globalsAvailable: Boolean(globals),
        baseAvailable: Boolean(base), gridRectAvailable: Boolean(nativeGrid)
      };
      return;
    }
    const previous = window[boundsKey];
    if (!previous || Math.abs(rect.left - previous.left) > 1 ||
      Math.abs(rect.right - previous.right) > 1 || Date.now() - previous.at > 30000) {
      window[boundsKey] = {
        left: rect.left, right: rect.right, at: Date.now(), method
      };
      window.dispatchEvent(new Event(eventName));
    }
  }

  _refresh() {
    // HA may invoke setConfig before attaching the element or assigning the hass object.
    if (!this._config || !this._hass || !this.isConnected) return;
    const range = this._window();
    if (range.key === this._windowKey) return;
    this._windowKey = range.key;
    this._chartReady = false;
    this._plotElement = null;
    const buildId = (this._buildId || 0) + 1;
    this._buildId = buildId;

    const config = {
      ...this._config,
      type: 'custom:apexcharts-card',
      graph_span: range.span,
      span: { ...this._config.span, start: 'day', offset: range.offset },
      ...(this._isOverview() ? {
        apex_config: {
          ...this._config.apex_config,
          xaxis: { ...this._config.apex_config?.xaxis, ...this._overviewViewport() }
        }
      } : {})
    };

    // Use Home Assistant's card factory. A directly created ApexCharts element may
    // not be initialized/upgraded when setConfig is called, leaving all graphs blank.
    (async () => {
      try {
        if (typeof window.loadCardHelpers !== 'function') {
          throw new Error('Home Assistant card helpers are unavailable');
        }
        const helpers = await window.loadCardHelpers();
        const card = await helpers.createCardElement(config);
        if (buildId !== this._buildId) return;
        if (!card) throw new Error('Home Assistant could not create the ApexCharts card');

        this._chart = card;
        this.replaceChildren(card);
        this._installDragToPan(card);
        this._chartReady = true;
        if (this._hass) card.hass = this._hass;
        // The plot rectangle appears only after ApexCharts has rendered its SVG.
        requestAnimationFrame(() => {
          this._broadcastPlotBounds();
          this._scheduleViewport();
        });
      } catch (error) {
        if (buildId !== this._buildId) return;
        console.error('EnergyManager day chart initialization failed:', error);
        this._chart = null;
        this._chartReady = false;
        this._windowKey = null; // Permit a retry at the next minute tick.
        const fallback = document.createElement('ha-card');
        fallback.textContent = `Graph initialization failed: ${error.message}`;
        fallback.style.padding = '16px';
        this.replaceChildren(fallback);
      }
    })();
  }
}

if (!customElements.get('energymanager-day-chart')) {
  customElements.define('energymanager-day-chart', EnergyManagerDayChart);
}

// Planning charts: seven daily MILP entities -> one future curve per quantity.
// Historical segments use a single five-minute Recorder statistics query for all
// seven actual sensors, shared by both Planning charts. This is independent of
// the Overview's existing power-history cache and does not modify that page.
const energyManagerPlanningV232 = (() => {
  const SAMPLE_MS = 5 * 60 * 1000;
  const SOURCES = {
    grid: ['sensor.energy_manager_grid_power', 'grid_w'],
    ess: ['sensor.energy_manager_ess_power', 'ess_w'],
    solar: ['sensor.energy_manager_pv_solax_power', 'pv_ac_w'],
    load: ['sensor.energy_manager_house_load_power', 'load_w'],
    background: ['sensor.energy_manager_background_load_power', 'background_w'],
    ess_soc: ['sensor.energy_manager_ess_soc', 'ess_soc'],
    ev_soc: ['sensor.energy_manager_ev_soc', 'ev_soc']
  };
  const IDS = Object.values(SOURCES).map(([id]) => id);
  const status = {
    mode: '5minute_mean', requests: 0, lastDurationMs: null,
    lastStatisticRows: 0, missingSensors: [], error: null, planPoints: {}
  };
  let cachedKey = null;
  let cachedTask = null;

  const numeric = value => value === null || value === undefined || value === '' ||
    ['unknown', 'unavailable'].includes(String(value).toLowerCase()) ? null :
    Number.isFinite(Number(value)) ? Number(value) : null;

  function timestamp(raw) {
    if (typeof raw === 'number') return raw < 1e11 ? raw * 1000 : raw;
    return Date.parse(raw);
  }

  function history(hass, begin, cutoff) {
    const key = `${begin}/${cutoff}`;
    if (key === cachedKey && cachedTask) return cachedTask;
    cachedKey = key;
    cachedTask = (async () => {
      const t0 = performance.now();
      status.requests++;
      status.error = null;
      const response = await hass.callWS({
        type: 'recorder/statistics_during_period', statistic_ids: IDS,
        start_time: new Date(begin).toISOString(),
        end_time: new Date(cutoff).toISOString(),
        period: '5minute', types: ['mean']
      });
      const data = {};
      let rows = 0;
      for (const id of IDS) {
        const points = new Map();
        for (const item of response?.[id] || []) {
          const time = timestamp(item.start);
          const value = numeric(item.mean);
          if (Number.isFinite(time) && value !== null && time >= begin && time < cutoff) {
            points.set(Math.floor(time / SAMPLE_MS) * SAMPLE_MS, value);
          }
        }
        data[id] = [...points.entries()].sort((a, b) => a[0] - b[0]);
        rows += points.size;
      }
      status.lastStatisticRows = rows;
      status.lastDurationMs = Math.round(performance.now() - t0);
      status.missingSensors = IDS.filter(id => !data[id].length);
      return data;
    })();
    cachedTask.catch(error => {
      status.error = String(error?.message || error);
      if (cachedKey === key) { cachedKey = null; cachedTask = null; }
      console.warn('EnergyManager Planning statistics unavailable:', error);
    });
    return cachedTask;
  }

  async function points(hass, start, end, quantity) {
    if (quantity === 'peak') {
      // Observed monthly 15-minute capacity peak, a reference threshold (not a predicted curve).
      const peakKw = numeric(hass.states['sensor.energy_manager_capacity_tariff_status']?.attributes?.observed_peak_kw);
      return peakKw === null ? [] : [[start.getTime(), peakKw * 1000], [end.getTime(), peakKw * 1000]];
    }
    const source = SOURCES[quantity];
    if (!source) throw new Error(`Unknown Planning quantity: ${quantity}`);
    const [actualId, forecastField] = source;
    const begin = start.getTime();
    const finish = end.getTime();
    const now = Date.now();
    const cutoff = Math.floor(Math.min(now, finish) / SAMPLE_MS) * SAMPLE_MS;
    const result = [];

    // Every actual power/SoC line reads from the same cached Recorder response.
    if (cutoff > begin) {
      try {
        const measured = await history(hass, begin, cutoff);
        result.push(...(measured[actualId] || []));
      } catch (_) {
        // Missing Recorder statistics must not hide valid MILP forecasts.
      }
    }
    const current = hass.states[actualId];
    const live = numeric(current?.state);
    const updated = Date.parse(current?.last_updated || '');
    if (begin <= now && now <= finish && live !== null && Number.isFinite(updated) &&
        now - updated >= 0 && now - updated < 120000) result.push([now, live]);

    let count = 0;
    for (let day = 1; day <= 7; day++) {
      const intervals = hass.states[`sensor.energy_manager_plan_day_${day}`]?.attributes?.intervals;
      if (!Array.isArray(intervals)) continue;
      for (const interval of intervals) {
        const time = timestamp(interval.start);
        const value = numeric(interval[forecastField]);
        if (Number.isFinite(time) && time > now && time >= begin && time <= finish && value !== null) {
          result.push([time, value]);
          count++;
        }
      }
    }
    status.planPoints[quantity] = count;
    return [...new Map(result.map(point => [point[0], point])).values()].sort((a, b) => a[0] - b[0]);
  }

  function tooltip({ seriesIndex, dataPointIndex, w }, unit) {
    const times = w.globals.seriesX || [];
    const values = w.globals.series || [];
    const time = Number(times[seriesIndex]?.[dataPointIndex]);
    if (!Number.isFinite(time)) return '';
    const hidden = new Set(w.globals.collapsedSeriesIndices || []);
    const escape = value => String(value).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
    const parts = [];
    for (let i = 0; i < times.length; i++) {
      if (hidden.has(i)) continue;
      let closest = null;
      let distance = 8 * 60 * 1000 + 1;
      for (let j = 0; j < (times[i] || []).length; j++) {
        const delta = Math.abs(Number(times[i][j]) - time);
        const value = numeric(values[i]?.[j]);
        if (value !== null && delta < distance) { closest = value; distance = delta; }
      }
      if (closest === null || distance > 8 * 60 * 1000) continue;
      const label = escape(w.config.series[i]?.name || `Series ${i + 1}`);
      const color = (w.globals.colors || [])[i] || '#888';
      const value = unit === '%' ? closest.toFixed(1) : Math.round(closest).toLocaleString();
      parts.push(`<div style="display:flex;gap:12px;justify-content:space-between;margin-top:5px">` +
        `<span><span style="display:inline-block;width:9px;height:9px;border-radius:50%;` +
        `background:${color};margin-right:6px"></span>${label}</span><strong>${value} ${unit}</strong></div>`);
    }
    if (!parts.length) return '';
    const when = new Date(time).toLocaleString(undefined, {
      day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false
    });
    return `<div style="padding:10px 12px;background:var(--card-background-color);` +
      `color:var(--primary-text-color);border:1px solid var(--divider-color);` +
      `border-radius:8px;min-width:185px"><strong>${escape(when)}</strong>${parts.join('')}</div>`;
  }

  return { points, tooltip, status };
})();
window.energyManagerPlanningV232 = energyManagerPlanningV232;

// Overview SoC history and MILP forecast in exactly two continuous series.
// Both series share one cached five-minute Recorder query. Never request raw states.
const energyManagerOverviewSocV236 = (() => {
  const SAMPLE_MS = 5 * 60 * 1000;
  const SOURCES = {
    ess_soc: 'sensor.energy_manager_ess_soc',
    ev_soc: 'sensor.energy_manager_ev_soc'
  };
  const ids = Object.values(SOURCES);
  const status = { requests: 0, durationMs: null, rows: 0, error: null };
  let cachedKey = null;
  let cachedTask = null;

  const numeric = value => value == null || value === '' ||
    ['unknown', 'unavailable'].includes(String(value).toLowerCase()) ? null :
    Number.isFinite(Number(value)) ? Number(value) : null;

  async function history(hass, begin, cutoff) {
    const key = `${begin}/${cutoff}`;
    if (cachedKey === key && cachedTask) return cachedTask;
    cachedKey = key;
    cachedTask = (async () => {
      const started = performance.now();
      status.requests++;
      const response = await hass.callWS({
        type: 'recorder/statistics_during_period', statistic_ids: ids,
        start_time: new Date(begin).toISOString(), end_time: new Date(cutoff).toISOString(),
        period: '5minute', types: ['mean']
      });
      const byEntity = {};
      let rows = 0;
      for (const id of ids) {
        const points = new Map();
        for (const item of response?.[id] || []) {
          const raw = item.start;
          const time = typeof raw === 'number' ? (raw < 1e11 ? raw * 1000 : raw) : Date.parse(raw);
          const value = numeric(item.mean);
          if (Number.isFinite(time) && value !== null && time >= begin && time < cutoff) {
            points.set(Math.floor(time / SAMPLE_MS) * SAMPLE_MS, value);
          }
        }
        byEntity[id] = [...points.entries()].sort((a, b) => a[0] - b[0]);
        rows += points.size;
      }
      status.rows = rows;
      status.durationMs = Math.round(performance.now() - started);
      status.error = null;
      return byEntity;
    })();
    cachedTask.catch(error => {
      status.error = String(error?.message || error);
      if (cachedKey === key) { cachedKey = null; cachedTask = null; }
      console.warn('[EnergyManager Dashboard] Overview SoC statistics unavailable:', error);
    });
    return cachedTask;
  }

  async function points(hass, start, end, quantity) {
    const id = SOURCES[quantity];
    if (!id) throw new Error(`Unknown Overview SoC series: ${quantity}`);
    const begin = start.getTime(), finish = end.getTime(), now = Date.now();
    const cutoff = Math.floor(Math.min(now, finish) / SAMPLE_MS) * SAMPLE_MS;
    const result = [];
    if (cutoff > begin) {
      try {
        const historical = await history(hass, begin, cutoff);
        result.push(...(historical[id] || []));
      } catch (_) { /* A statistics error must not hide valid future plan data. */ }
    }
    const current = hass.states[id];
    const value = numeric(current?.state);
    const updated = Date.parse(current?.last_updated || '');
    if (begin <= now && now <= finish && value !== null &&
        Number.isFinite(updated) && now - updated >= 0 && now - updated < 120000) {
      result.push([now, value]);
    }
    for (const day of [1, 2]) {
      const intervals = hass.states[`sensor.energy_manager_plan_day_${day}`]?.attributes?.intervals;
      if (!Array.isArray(intervals)) continue;
      for (const interval of intervals) {
        const time = Date.parse(interval.start);
        const forecast = numeric(interval[quantity]);
        if (Number.isFinite(time) && time > now && time >= begin && time <= finish && forecast !== null) {
          result.push([time, forecast]);
        }
      }
    }
    return [...new Map(result.map(point => [point[0], point])).values()]
      .sort((a, b) => a[0] - b[0]);
  }
  return { points, status };
})();
window.energyManagerOverviewSocV236 = energyManagerOverviewSocV236;

// Planning-only, seven-day grouped execution timeline and task list.
// Future-only segments are read from EnergyManager; historical execution is not reconstructed.
class EnergyManagerPlanningTasksCard extends HTMLElement {
  setConfig(config) {
    if (!['timeline', 'list'].includes(config?.mode)) throw new Error('Planning tasks require mode: timeline or list');
    this._config = config;
  }
  set hass(hass) {
    this._hass = hass;
    const timeline = hass.states['sensor.energy_manager_plan_timeline'];
    const requirements = hass.states['sensor.energy_manager_task_status'];
    const key = `${timeline?.last_updated || ''}/${requirements?.last_updated || ''}/${Math.floor(Date.now() / 60000)}`;
    if (key === this._renderKey || this.querySelector('dialog[open]')) return;
    this._renderKey = key;
    this.render();
  }
  connectedCallback() {
    if (this._config?.mode === 'timeline') {
      this._onBounds = () => this._align();
      window.addEventListener('energymanager-planning-power-plot-bounds', this._onBounds);
      if (!this._alignTimer) this._alignTimer = setInterval(() => this._align(), 2000);
    }
    this.render();
  }
  disconnectedCallback() {
    if (this._onBounds) window.removeEventListener('energymanager-planning-power-plot-bounds', this._onBounds);
    clearInterval(this._alignTimer);
    this._alignTimer = null;
  }
  getCardSize() { return this._config?.mode === 'list' ? 6 : 3; }
  _esc(value) {
    return String(value ?? '').replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
  }
  _time(ms) {
    return new Date(ms).toLocaleString(undefined, {
      day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false
    });
  }
  _window() {
    const now = Date.now();
    const date = new Date(now);
    const six = new Date(date.getFullYear(), date.getMonth(), date.getDate(), 6);
    const start = date >= six ? six : new Date(date.getFullYear(), date.getMonth(), date.getDate() - 1, 6);
    return { now, start: start.getTime(), end: new Date(start.getFullYear(), start.getMonth(), start.getDate() + 7, 6).getTime() };
  }
  _category(value) {
    if (value === 'ev') return 'EV';
    if (value === 'dhw') return 'DHW';
    if (value === 'washing' || value === 'laundry') return 'Laundry';
    return String(value || 'Other').replace(/[_-]/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  }
  _color(value) {
    return { ev: '#16a34a', dhw: '#eab308', washing: '#007AC2', laundry: '#007AC2' }[value] || '#a855f7';
  }
  _model() {
    const win = this._window();
    const source = this._hass?.states['sensor.energy_manager_plan_timeline'];
    const sourceTasks = this._hass?.states['sensor.energy_manager_task_status'];
    const segments = (Array.isArray(source?.attributes?.segments) ? source.attributes.segments : [])
      .map((s, i) => {
        const start = Date.parse(s.start), end = Date.parse(s.end);
        if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) return null;
        const clipStart = Math.max(start, win.now, win.start), clipEnd = Math.min(end, win.end);
        if (clipEnd <= clipStart) return null;
        const energy = Number(s.energy_kwh);
        return { ...s, index: i, startMs: start, endMs: end, clipStart, clipEnd,
          category: s.actuator_id || s.kind || 'other',
          displayedEnergy: Number.isFinite(energy) ? energy * (clipEnd - clipStart) / (end - start) : null };
      }).filter(Boolean).sort((a, b) => a.startMs - b.startMs);
    const tasks = (Array.isArray(sourceTasks?.attributes?.tasks) ? sourceTasks.attributes.tasks : [])
      .filter(t => t && t.actuator_id && (!t.latest_end || Date.parse(t.latest_end) >= win.now))
      .sort((a, b) => (Date.parse(a.latest_end) || 0) - (Date.parse(b.latest_end) || 0));
    const groups = new Map();
    for (const s of segments) {
      if (!groups.has(s.category)) groups.set(s.category, { key: s.category, segments: [], tasks: [] });
      groups.get(s.category).segments.push(s);
    }
    for (const t of tasks) {
      if (!groups.has(t.actuator_id)) groups.set(t.actuator_id, { key: t.actuator_id, segments: [], tasks: [] });
      groups.get(t.actuator_id).tasks.push(t);
    }
    return { win, groups: [...groups.values()].sort((a,b) => (a.key === 'ev' ? -1 : b.key === 'ev' ? 1 : a.key.localeCompare(b.key))),
      generated: source?.attributes?.generated_at_utc, timelineAvailable: Boolean(source), taskAvailable: Boolean(sourceTasks) };
  }
  _align() {
    if (!this.isConnected || this._config?.mode !== 'timeline') return;
    const plot = this.querySelector('[data-em-planning-plot]');
    const bounds = window.energyManagerPlanningPowerPlotBounds;
    if (!plot || !bounds || Date.now() - bounds.at > 60000) return;
    const rect = plot.getBoundingClientRect();
    if (rect.width < 20) return;
    const oldLeft = Number.parseFloat(plot.style.marginLeft) || 0;
    const oldRight = Number.parseFloat(plot.style.marginRight) || 0;
    const baseLeft = rect.left - oldLeft, baseRight = rect.right + oldRight;
    const left = Math.max(0, bounds.left - baseLeft);
    const right = baseRight - bounds.right;
    const aligned = left < 160 && right > -20 && right < 160 && bounds.right > bounds.left;
    if (aligned) {
      if (Math.abs(left - oldLeft) > 0.5) plot.style.marginLeft = `${left.toFixed(1)}px`;
      if (Math.abs(right - oldRight) > 0.5) plot.style.marginRight = `${right.toFixed(1)}px`;
    }
    window.energyManagerPlanningAlignmentStatus = { aligned, leftOffsetPx: left, rightOffsetPx: right,
      graphLeftPx: bounds.left, graphRightPx: bounds.right };
  }
  _timeline(model) {
    const { win, groups } = model;
    const duration = win.end - win.start;
    const pct = ms => (100 * (ms - win.start) / duration);
    const rows = groups.map(g => {
      const blocks = g.segments.map(s => {
        const width = pct(s.clipEnd) - pct(s.clipStart);
        return `<button type="button" data-index="${s.index}" title="${this._esc(this._category(g.key))}: ${this._esc(this._time(s.startMs))} – ${this._esc(this._time(s.endMs))}" ` +
          `style="position:absolute;left:${pct(s.clipStart).toFixed(5)}%;width:${width.toFixed(5)}%;top:3px;height:24px;min-width:2px;` +
          `border:0;border-radius:4px;background:${this._color(g.key)};color:#fff;cursor:pointer;overflow:hidden;white-space:nowrap;` +
          `font-size:11px;font-weight:600;opacity:.95">${width > 5 ? this._esc(this._category(g.key)) : ''}</button>`;
      }).join('');
      return `<div style="position:relative;height:30px;margin-bottom:5px;background:var(--secondary-background-color);border-radius:5px">` +
        `<span style="position:absolute;right:calc(100% + 9px);width:62px;text-align:right;top:8px;font-size:12px;color:var(--secondary-text-color)">${this._esc(this._category(g.key))}</span>` +
        `${blocks}</div>`;
    }).join('');
    const ticks = Array.from({ length: 8 }, (_, d) => {
      const start = new Date(win.start);
      const day = new Date(start.getFullYear(), start.getMonth(), start.getDate() + d, 6);
      const x = pct(day.getTime());
      const text = day.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
      return `<span style="position:absolute;left:${x.toFixed(4)}%;transform:translateX(${d === 0 ? '0%' : d === 7 ? '-100%' : '-50%'});white-space:nowrap">${this._esc(text)}</span>`;
    }).join('');
    const marker = pct(win.now);
    const nowLine = marker >= 0 && marker <= 100 ? `<span title="Now" style="position:absolute;top:0;bottom:18px;left:${marker.toFixed(4)}%;border-left:2px dashed var(--primary-color);z-index:3;pointer-events:none"></span>` : '';
    return `<ha-card header="Scheduled tasks · 7 days"><div class="card-content">` +
      `<div data-em-planning-plot style="position:relative">${rows || '<p style="opacity:.7">No scheduled execution in this period.</p>'}${nowLine}` +
      `<div style="position:relative;height:20px;margin-top:8px;font-size:11px;color:var(--secondary-text-color)">${ticks}</div></div>` +
      `<small style="display:block;margin-top:8px;color:var(--secondary-text-color)">Future scheduled runs only · ${this._esc(model.generated ? 'Plan updated '+this._time(Date.parse(model.generated)) : 'Waiting for plan')}</small>` +
      `</div></ha-card><dialog aria-label="Planned run details" style="border:1px solid var(--divider-color);border-radius:12px;background:var(--card-background-color);color:var(--primary-text-color);padding:20px;width:min(420px,calc(100vw - 48px))"></dialog>`;
  }
  _taskDetail(task) {
    const deadline = task.latest_end ? this._time(Date.parse(task.latest_end)) : '—';
    const required = task.required_energy_kwh === null || task.required_energy_kwh === undefined ?
      NaN : Number(task.required_energy_kwh);
    const minSoc = task.minimum_soc_percent;
    const preferred = task.preferred_energy_kwh !== null && task.preferred_energy_kwh !== undefined;
    const label = task.kind === 'energy_by_deadline' ? 'Departure deadline' : preferred ? 'Preferred horizon target' : (task.kind || 'Task');
    const energy = preferred ? Number(task.preferred_energy_kwh) : required;
    const soc = task.kind === 'energy_by_deadline' ? minSoc : task.target_soc_percent;
    const feasible = task.status === 'deadline_infeasible' || task.feasible_at_max_power === false ? ' · Cannot meet deadline' :
      task.status === 'satisfied' ? ' · Already met' : task.planning_available === false ? ` · ${task.status}` : '';
    return `<div style="display:flex;gap:12px;justify-content:space-between;align-items:baseline;flex-wrap:wrap;padding:7px 0;border-bottom:1px solid var(--divider-color)">` +
      `<span><b>${this._esc(label)}</b> · ${this._esc(deadline)}<span style="font-size:12px;color:var(--secondary-text-color)">${this._esc(feasible)}</span></span>` +
      `<span style="font-variant-numeric:tabular-nums">${soc === null || soc === undefined ? '' : this._esc(soc)+'% SoC · '}${Number.isFinite(energy) ? energy.toFixed(2)+' kWh' : '—'}</span></div>`;
  }
  _list(model) {
    const body = model.groups.map(group => {
      const energy = group.segments.reduce((sum, s) => sum + (s.displayedEnergy || 0), 0);
      const heading = `${this._category(group.key)} · ${group.segments.length} scheduled run${group.segments.length === 1 ? '' : 's'} · ${energy.toFixed(2)} kWh`;
      const runs = group.segments.length ? `<div style="display:grid;grid-template-columns:1.7fr 1.4fr .7fr .8fr;gap:6px;font-size:12px;color:var(--secondary-text-color);padding:8px 0 4px">` +
        `<span>Start</span><span>End</span><span style="text-align:right">Energy</span><span style="text-align:right">Max power</span></div>` +
        group.segments.map(s => `<div style="display:grid;grid-template-columns:1.7fr 1.4fr .7fr .8fr;gap:6px;padding:7px 0;border-bottom:1px solid var(--divider-color);font-size:13px;font-variant-numeric:tabular-nums">` +
          `<span>${this._esc(this._time(s.clipStart))}</span><span>${this._esc(this._time(s.clipEnd))}</span>` +
          `<span style="text-align:right">${s.displayedEnergy === null ? '—' : s.displayedEnergy.toFixed(2)+' kWh'}</span>` +
          `<span style="text-align:right">${Number.isFinite(Number(s.peak_power_w)) ? Math.round(Number(s.peak_power_w))+' W' : '—'}</span></div>`).join('') :
        '<p style="color:var(--secondary-text-color)">No planned execution in this window.</p>';
      const constraints = group.tasks.length ? `<div style="margin-top:14px;font-size:13px;font-weight:600">Task requirements and deadlines</div>` +
        group.tasks.map(t => this._taskDetail(t)).join('') : '';
      return `<section style="margin-bottom:18px"><h3 style="font-size:16px;margin:4px 0 6px;color:${this._color(group.key)}">${this._esc(heading)}</h3>` +
        `${runs}${constraints}</section>`;
    }).join('');
    return `<ha-card header="Tasks by category"><div class="card-content">` +
      (body || '<p>No scheduled tasks or task requirements are published.</p>') +
      `<small style="color:var(--secondary-text-color)">Charging sessions are not assigned to individual departures. ` +
      `Requirements are planner constraints, not additional scheduled runs. Other device categories appear when their scheduling is implemented.</small>` +
      `</div></ha-card>`;
  }
  render() {
    if (!this._hass || !this._config || !this.isConnected) return;
    const model = this._model();
    this.innerHTML = this._config.mode === 'timeline' ? this._timeline(model) : this._list(model);
    if (this._config.mode !== 'timeline') return;
    const dlg = this.querySelector('dialog');
    this.querySelectorAll('button[data-index]').forEach(btn => btn.addEventListener('click', () => {
      const item = model.groups.flatMap(g => g.segments).find(s => s.index === Number(btn.dataset.index));
      if (!item) return;
      dlg.innerHTML = `<div style="display:flex;justify-content:space-between;gap:15px"><b>${this._esc(this._category(item.category))} · Scheduled run</b>` +
        `<button data-close style="background:none;border:0;color:inherit;font-size:22px;cursor:pointer">×</button></div>` +
        `<p>Start: <b>${this._esc(this._time(item.startMs))}</b></p><p>End: <b>${this._esc(this._time(item.endMs))}</b></p>` +
        `<p>Energy: <b>${item.displayedEnergy === null ? '—' : item.displayedEnergy.toFixed(2)+' kWh (visible portion)'}</b></p>` +
        `<p>Maximum planned power: <b>${this._esc(item.peak_power_w ?? '—')} W</b></p>` +
        `<small>These planned runs are not attributed to particular departure requirements.</small>`;
      dlg.querySelector('[data-close]').addEventListener('click', () => dlg.close());
      dlg.showModal();
    }));
    dlg.addEventListener('click', event => { if (event.target === dlg) dlg.close(); });
    requestAnimationFrame(() => this._align());
  }
}
if (!customElements.get('energymanager-planning-tasks-card')) {
  customElements.define('energymanager-planning-tasks-card', EnergyManagerPlanningTasksCard);
}


// Read-only view of the last 30 notification-manager events exposed by Home Assistant.
// Clear displayed events is browser-local; the add-on buffer is intentionally not modified.
class EnergyManagerNotificationEventsCard extends HTMLElement {
  static STORAGE_KEY = 'energyManager.notificationEvents.hiddenBefore.v1';

  setConfig(config) { this._config = config || {}; this._render(); }
  set hass(hass) {
    this._hass = hass;
    const events = this._events();
    const key = JSON.stringify(events);
    if (key !== this._eventsKey) {
      this._eventsKey = key;
      this._render();
    }
  }
  connectedCallback() { this._render(); }
  getCardSize() { return 5; }

  _events() {
    const events = this._hass?.states?.['sensor.energy_manager_notification_status']?.attributes?.recent_events;
    return Array.isArray(events) ? events : [];
  }
  _cutoff() {
    try { return Number(window.localStorage.getItem(EnergyManagerNotificationEventsCard.STORAGE_KEY)) || 0; }
    catch (_) { return this._temporaryCutoff || 0; }
  }
  _saveCutoff(value) {
    this._temporaryCutoff = value;
    try {
      if (value) window.localStorage.setItem(EnergyManagerNotificationEventsCard.STORAGE_KEY, String(value));
      else window.localStorage.removeItem(EnergyManagerNotificationEventsCard.STORAGE_KEY);
    } catch (_) { /* Browser storage may be unavailable. */ }
  }
  _esc(value) {
    return String(value ?? '').replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
  }
  _time(value) {
    const ms = Date.parse(value);
    return Number.isFinite(ms) ? new Date(ms).toLocaleString(undefined, {
      day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
    }) : 'Time unavailable';
  }
  _label(value) {
    return String(value || 'unknown').replace(/_/g, ' ').replace(/\b\w/g, s => s.toUpperCase());
  }
  _groups(events) {
    const groups = [];
    for (const entry of events) {
      const key = [entry?.event, entry?.health, entry?.reason, entry?.notification_requested].join('\u0000');
      const prior = groups[groups.length - 1];
      // Repeated suppression events are individually available via the expandable details.
      if (entry?.event === 'suppressed' && prior?.key === key) {
        prior.entries.push(entry);
      } else {
        groups.push({key, entries:[entry]});
      }
    }
    return groups.reverse();
  }
  _row(group) {
    const entries = group.entries;
    const item = entries[entries.length - 1] || {};
    const count = entries.length;
    const event = String(item.event || 'unknown');
    const health = String(item.health || 'unknown');
    const tint = health === 'healthy' ? '#16a34a' :
      health === 'degraded' ? '#f59e0b' :
      health === 'safe_fallback' ? '#dc2626' : 'var(--secondary-text-color)';
    const times = count > 1 ?
      `${this._time(entries[0].time)} – ${this._time(item.time)}` : this._time(item.time);
    const reason = String(item.reason || '').trim();
    const expanded = count > 1 ?
      `<details data-group="${this._esc(entries[0].time || '')}" style="margin-top:6px">` +
      `<summary style="cursor:pointer;font-size:12px;color:var(--secondary-text-color)">` +
      `Show all ${count} timestamps</summary>` +
      `<div style="padding:6px 0 0 12px;font-size:12px;color:var(--secondary-text-color);` +
      `line-height:1.8;font-variant-numeric:tabular-nums">` +
      entries.map(e => `<div>${this._esc(this._time(e.time))}</div>`).join('') + `</div></details>` : '';
    return `<div class="em-notification-row" style="border-top:1px solid var(--divider-color);padding:12px 0;` +
      `display:grid;grid-template-columns:minmax(135px,190px) minmax(0,1fr);gap:12px;align-items:start">` +
      `<time style="font-size:12px;color:var(--secondary-text-color);font-variant-numeric:tabular-nums;` +
      `white-space:normal">${this._esc(times)}</time>` +
      `<div style="min-width:0">` +
      `<div style="display:flex;flex-wrap:wrap;align-items:center;gap:8px">` +
      `<strong style="font-size:13px">${this._esc(this._label(event))}${count > 1 ? ' ×'+count : ''}</strong>` +
      `<span style="font-size:12px;color:${tint}">${this._esc(this._label(health))}</span>` +
      `${item.notification_requested ? '<span style="font-size:12px">Alert requested</span>' : ''}` +
      `</div>` +
      `${reason ? `<div style="margin-top:4px;font-size:12px;color:var(--secondary-text-color);` +
        `overflow-wrap:anywhere">${this._esc(reason)}</div>` : ''}` + expanded + `</div></div>`;
  }
  _render() {
    if (!this.isConnected || !this._hass) return;
    const events = this._events();
    const cutoff = this._cutoff();
    const visible = events.filter(entry => {
      const stamp = Date.parse(entry?.time);
      return !cutoff || (Number.isFinite(stamp) && stamp > cutoff);
    });
    const expanded = new Set(Array.from(this.querySelectorAll('details[open]')).map(el => el.dataset.group));
    const groups = this._groups(visible);
    const rowHTML = groups.map(g => this._row(g)).join('');
    this.innerHTML = `<ha-card><div style="padding:16px;box-sizing:border-box">` +
      `<div style="display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;` +
      `margin-bottom:12px"><div><div style="font-size:19px;font-weight:500">Recent notification events</div>` +
      `<span style="font-size:12px;color:var(--secondary-text-color)">${visible.length} visible of ${events.length} buffered</span></div>` +
      `<div style="display:flex;gap:8px;flex-wrap:wrap">` +
      (cutoff ? `<button type="button" data-restore>Show buffered</button>` : '') +
      `<button type="button" data-clear ${visible.length ? '' : 'disabled'}>Clear displayed</button></div></div>` +
      (rowHTML || `<div style="padding:14px 0;color:var(--secondary-text-color);font-size:13px">` +
        (cutoff ? 'No new events since the list was cleared.' : 'No notification events recorded.') + '</div>') +
      `</div></ha-card>`;
    for (const el of this.querySelectorAll('button')) Object.assign(el.style, {
      border: '1px solid var(--divider-color)', borderRadius: '6px', padding: '6px 10px',
      background: 'var(--secondary-background-color)', color: 'var(--primary-text-color)',
      cursor: el.disabled ? 'default' : 'pointer', fontSize: '12px'
    });
    this.querySelector('[data-clear]')?.addEventListener('click', () => {
      const latest = Math.max(0, ...this._events().map(e => Date.parse(e?.time)).filter(Number.isFinite));
      this._saveCutoff(latest || Date.now());
      this._render();
    });
    this.querySelector('[data-restore]')?.addEventListener('click', () => {
      this._saveCutoff(0);
      this._render();
    });
    for (const el of this.querySelectorAll('details')) if (expanded.has(el.dataset.group)) el.open = true;
  }
}
if (!customElements.get('energymanager-notification-events-card')) {
  customElements.define('energymanager-notification-events-card', EnergyManagerNotificationEventsCard);
}

// Module resource/version verification (logged once per script evaluation).
// The Planning helper retains its v2.32 name to keep the existing chart API stable.
window.energyManagerDashboardVersion = '2.37';
window.energyManagerDashboardInfo = {
  version: '2.37',
  loadedAt: new Date().toISOString(),
  planningHelperReady: typeof window.energyManagerPlanningV232?.points === 'function',
  taskCardReady: Boolean(customElements.get('energymanager-planning-tasks-card')),
  overviewNavigationReady: Boolean(customElements.get('energymanager-time-navigator')),
  overviewSocReady: typeof window.energyManagerOverviewSocV236?.points === 'function',
  notificationEventsCardReady: Boolean(customElements.get('energymanager-notification-events-card'))
};
console.info('[EnergyManager Dashboard] JavaScript v2.37 loaded', window.energyManagerDashboardInfo);
