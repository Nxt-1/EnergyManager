class EnergyManagerTimelineCard extends HTMLElement {
  setConfig(config) { this.config = config; this.selected = null; }
  set hass(hass) { this._hass = hass; this.render(); }
  getCardSize() { return 4; }
  render() {
    if (!this._hass || !this.config) return;
    const entity = this._hass.states[this.config.entity];
    const segments = entity?.attributes?.segments || [];
    const hours = Math.max(1, Math.min(168, Number(this.config.hours || 24)));
    const now = Date.now(), end = now + hours * 3600000;
    const label = (ms) => new Date(ms).toLocaleString(undefined, {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'});
    const esc = (s) => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const visible = segments.filter(s => new Date(s.end).getTime() > now && new Date(s.start).getTime() < end);
    const items = visible.map((s, i) => {
      const start = Math.max(now, new Date(s.start).getTime());
      const stop = Math.min(end, new Date(s.end).getTime());
      const left = 100 * (start-now)/(end-now), width = 100 * (stop-start)/(end-now);
      return `<button data-idx="${i}" title="${esc(s.name)}: ${esc(label(new Date(s.start).getTime()))}" style="position:absolute;left:${left}%;width:${width}%;top:5px;height:30px;background:var(--primary-color);border:0;border-radius:4px;color:var(--text-primary-color,#fff);cursor:pointer;overflow:hidden;white-space:nowrap;font-weight:600;min-width:2px">${width>7?esc(s.name):''}</button>`;
    }).join('');
    const item = visible[this.selected];
    const detail = item ? `<section style="border-top:1px solid var(--divider-color);padding:12px 0 0;margin-top:14px">
      <b>${esc(item.name)} · planned charging</b><div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:10px">
      <div>Start<br><b>${esc(label(new Date(item.start).getTime()))}</b></div><div>End<br><b>${esc(label(new Date(item.end).getTime()))}</b></div>
      <div>Energy<br><b>${Number(item.energy_kwh).toFixed(2)} kWh</b></div><div>Peak power<br><b>${Math.round(item.peak_power_w)} W</b></div></div>
      <small style="display:block;margin-top:8px;opacity:.7">Scheduled execution segment, not an individual departure task.</small></section>` : '';
    this.innerHTML = `<ha-card header="${esc(this.config.title || 'Scheduled tasks')}"><div class="card-content">
      <div style="display:flex;justify-content:space-between;font-size:12px;opacity:.7;margin-bottom:6px"><span>${esc(label(now))}</span><span>${esc(label(end))}</span></div>
      <div style="position:relative;background:var(--secondary-background-color);height:40px;border-radius:6px;overflow:hidden">${items}</div>
      ${visible.length ? '' : '<p style="opacity:.7">No planned execution in this period.</p>'}${detail}
      <small style="display:block;opacity:.65;margin-top:10px">${esc(entity?.attributes?.generated_at_utc ? 'Plan: '+label(new Date(entity.attributes.generated_at_utc).getTime()) : 'Waiting for plan')}</small>
      </div></ha-card>`;
    this.querySelectorAll('button[data-idx]').forEach(btn => btn.addEventListener('click', () => {
      const idx = Number(btn.dataset.idx); this.selected = this.selected === idx ? null : idx; this.render();
    }));
  }
}
if (!customElements.get('energymanager-timeline-card')) customElements.define('energymanager-timeline-card', EnergyManagerTimelineCard);
