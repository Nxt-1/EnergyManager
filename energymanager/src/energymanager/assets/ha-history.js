const escape = value => String(value ?? '').replace(/[&<>"']/g, char =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));

export function historySources(key, entities = {}, groups = {}) {
  const keys = {ev:['ev_soc','ev_kw','connected'], ess:['ess_soc','ess_kw'],
    solar:['pv_ac_kw','pv_dc_kw'], grid:['grid_import_kw','grid_export_kw'],
    house:['grid_import_kw','grid_export_kw','pv_ac_kw','ess_kw','ev_kw'],
    ev_progress:['ev_soc','ev_total_kwh']}[key] || [key];
  return genuineEntities(groups[key] ?? keys.map(name => entities[name]));
}

export function genuineEntities(ids) {
  return [...new Set(ids.filter(id => typeof id === 'string' && /^[a-z_]+\.[a-z0-9_]+$/.test(id)))];
}

// Content is already formatted markup. Entity IDs come only from configured sources.
export function historyReading(content, ids, {native = false, demo = false, label = '', className = 'history-reading', key = ''} = {}) {
  const sources = genuineEntities(ids);
  if (native && !demo && sources.length) {
    const action = sources.length === 1 ? sources[0] : 'source histories';
    return `<button type="button" class="${escape(className)}" data-ha-entities="${escape(sources.join(' '))}" ${key ? `data-entity-key="${escape(key)}"` : ''} title="${escape(action)}" aria-description="Open Home Assistant history"><span class="history-label">${escape(label)}: </span>${content}</button>`;
  }
  const reason = demo ? 'Demo: no HA history' : native ? 'HA source not mapped' : 'History available in native HA';
  return `<span class="${escape(className)}" data-history-unavailable title="${reason}" aria-label="${escape(label)}: ${reason}">${content}</span>`;
}
