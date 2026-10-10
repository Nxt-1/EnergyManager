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
  getCardSize() { return 3; }
  render() {
    if (!this._hass || !this.config) return;
    const entity = this._hass.states[this.config.entity];
    const segments = Array.isArray(entity?.attributes?.segments) ? entity.attributes.segments : [];
    const hours = Math.max(1, Math.min(168, Number(this.config.hours || 24)));
    const now = Date.now(), end = now + hours * 3600000;
    const label = (ms) => new Date(ms).toLocaleString(undefined, {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
    });
    const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({
      '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'
    }[c]));
    const visible = segments.filter(s => new Date(s.end).getTime() > now && new Date(s.start).getTime() < end);
    const items = visible.map((s, i) => {
      const start = Math.max(now, new Date(s.start).getTime());
      const stop = Math.min(end, new Date(s.end).getTime());
      const left = 100 * (start-now)/(end-now), width = 100 * (stop-start)/(end-now);
      return `<button type="button" data-idx="${i}" aria-label="Details for ${esc(s.name)}" title="${esc(s.name)}: ${esc(label(new Date(s.start).getTime()))}" style="position:absolute;left:${left}%;width:${width}%;top:5px;height:30px;background:var(--primary-color);border:0;border-radius:4px;color:var(--text-primary-color,#fff);cursor:pointer;overflow:hidden;white-space:nowrap;font-weight:600;min-width:2px">${width>7?esc(s.name):''}</button>`;
    }).join('');
    this.innerHTML = `<ha-card header="${esc(this.config.title || 'Scheduled tasks')}"><div class="card-content">
      <div style="display:flex;justify-content:space-between;font-size:12px;opacity:.7;margin-bottom:6px"><span>${esc(label(now))}</span><span>${esc(label(end))}</span></div>
      <div style="position:relative;background:var(--secondary-background-color);height:40px;border-radius:6px;overflow:hidden">${items}</div>
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
  }
}
if (!customElements.get('energymanager-timeline-card')) {
  customElements.define('energymanager-timeline-card', EnergyManagerTimelineCard);
}
