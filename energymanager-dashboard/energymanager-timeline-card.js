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
    window.addEventListener('energymanager-power-plot-bounds', this._onPlotBounds);
    // A chart may publish its plot bounds while HA is still mounting the timeline.
    // Retry when the timeline becomes visible, including after card/view resizing.
    if (!this._alignTimer) this._alignTimer = setInterval(() => this._alignPlot(), 2000);
    this._scheduleAlignment();
  }
  disconnectedCallback() {
    window.removeEventListener('energymanager-power-plot-bounds', this._onPlotBounds);
    clearInterval(this._alignTimer);
    this._alignTimer = null;
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
      const today = new Date(now);
      const todayAtSix = new Date(today.getFullYear(), today.getMonth(), today.getDate(), 6);
      const start = today >= todayAtSix ? todayAtSix :
        new Date(today.getFullYear(), today.getMonth(), today.getDate() - 1, 6);
      windowStart = start.getTime();
      // Local wall-clock dates handle 23/25-hour daylight-saving days correctly.
      windowEnd = new Date(start.getFullYear(), start.getMonth(), start.getDate() + 1, 6).getTime();
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
      const start = new Date(windowStart);
      const t = new Date(start.getFullYear(), start.getMonth(), start.getDate(), 6 + i * 6);
      const pos = 100 * (t.getTime() - windowStart) / (windowEnd - windowStart);
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
    if (this._chartReady) this._chart.hass = hass;
  }

  connectedCallback() {
    if (!this._timer) this._timer = setInterval(() => this._refresh(), 60_000);
    if (!this._plotTimer) this._plotTimer = setInterval(() => this._broadcastPlotBounds(), 2000);
    this._refresh();
  }

  disconnectedCallback() {
    clearInterval(this._timer);
    clearInterval(this._plotTimer);
    this._timer = null;
    this._plotTimer = null;
    // Discard card factory work that may finish after a view is removed.
    this._buildId = (this._buildId || 0) + 1;
    this._windowKey = null;
  }

  getCardSize() {
    return this._chart?.getCardSize?.() ?? 5;
  }

  // Calculate elapsed hours, not wall-clock arithmetic, to account for DST transitions.
  _window(now = new Date()) {
    const days = Number(this._config?.graph_span?.match(/^(\d+)d$/)?.[1] ?? 1);
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const todayAtSix = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 6);
    const start = now >= todayAtSix ? todayAtSix :
      new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1, 6);
    const end = new Date(start.getFullYear(), start.getMonth(), start.getDate() + days, 6);
    const offset = Math.round((start.getTime() - today.getTime()) / 3600000);
    const hours = Math.round((end.getTime() - start.getTime()) / 3600000);
    return {
      key: `${start.getTime()}/${end.getTime()}`,
      offset: `${offset >= 0 ? '+' : ''}${offset}h`,
      span: `${hours}h`,
    };
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

  _broadcastPlotBounds() {
    if (!this._config?.header?.title?.startsWith('Power ·')) return;
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
      window.energyManagerPlotAlignmentStatus = {
        plotFound: false, aligned: false,
        apexInstance: Boolean(instance), globalsAvailable: Boolean(globals),
        baseAvailable: Boolean(base), gridRectAvailable: Boolean(nativeGrid)
      };
      return;
    }
    const previous = window.energyManagerPowerPlotBounds;
    if (!previous || Math.abs(rect.left - previous.left) > 1 ||
      Math.abs(rect.right - previous.right) > 1 || Date.now() - previous.at > 30000) {
      window.energyManagerPowerPlotBounds = {
        left: rect.left, right: rect.right, at: Date.now(), method
      };
      window.dispatchEvent(new Event('energymanager-power-plot-bounds'));
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
        this._chartReady = true;
        if (this._hass) card.hass = this._hass;
        // The plot rectangle appears only after ApexCharts has rendered its SVG.
        requestAnimationFrame(() => this._broadcastPlotBounds());
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
