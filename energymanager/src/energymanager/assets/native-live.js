// HA readings are a display projection only. They never grant controller authority.
export function nativeLiveState(state, hass, manifest) {
  if (manifest.demo || !hass?.states) return state;
  const readings = {};
  const read = (key, unit) => {
    const entity = hass.states[manifest.entities[key]];
    const raw = entity?.state;
    const declared = entity?.attributes?.unit_of_measurement;
    let value = typeof raw === 'string' && raw.trim() !== '' && Number.isFinite(Number(raw)) ? Number(raw) : null;
    if (unit === 'kW' && declared === 'W' && value !== null) value /= 1000;
    else if (declared !== unit) value = null;
    if (unit === '%' && (value < 0 || value > 100)) value = null;
    if (unit === 'kW' && key !== 'ess_kw' && value < 0) value = null;
    readings[key] = {
      ...state.live_inputs?.readings?.[key],
      value,
      display_current: value !== null
    };
    return value;
  };
  for (const key of ['grid_import_kw', 'grid_export_kw', 'pv_ac_kw', 'pv_dc_kw', 'ev_kw', 'ess_kw', 'monthly_peak_kw']) read(key, 'kW');
  read('ev_soc', '%');
  read('ess_soc', '%');
  const card = (keys, calculate, label) => {
    const missing = keys.filter(key => readings[key].value === null);
    const value = missing.length ? null : calculate(...keys.map(key => readings[key].value));
    return {
      value,
      label,
      issues: missing.map(key => `${manifest.entities[key] || key}: unavailable or incompatible HA state`)
    };
  };
  const connected = hass.states[manifest.entities.connected]?.state?.toLowerCase();
  const connection = ['on', 'true', 'connected'].includes(connected) ? 'Connected' : ['off', 'false', 'disconnected'].includes(connected) ? 'Away / disconnected' : 'Connection unknown';
  const cards = {
    grid: card(['grid_import_kw', 'grid_export_kw'], (a, b) => a - b, 'Home Assistant current states'),
    solar: card(['pv_ac_kw', 'pv_dc_kw'], (a, b) => a + b, 'AC and DC solar'),
    house: card(['grid_import_kw', 'grid_export_kw', 'pv_ac_kw', 'ess_kw', 'ev_kw'],
      (a, b, c, d, e) => a - b + c + d - e, 'Calculated household demand'),
    ess: card(['ess_soc'], value => value, 'Home Assistant current state'),
    ev: card(['ev_soc'], value => value, connection)
  };
  if (cards.house.value !== null) {
    if (cards.house.value < -0.1) {
      cards.house.value = null;
      cards.house.issues.push('Household power balance is inconsistent');
    } else cards.house.value = Math.max(0, cards.house.value);
  }
  return {
    ...state,
    live_inputs: {
      ...state.live_inputs,
      readings: {
        ...state.live_inputs?.readings,
        ...readings
      },
      cards
    }
  };
}
