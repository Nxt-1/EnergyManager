// Conversion belongs at the UI boundary. API/configuration values retain their units.
export function watts(kilowatts) {
  return kilowatts === null || kilowatts === undefined || !Number.isFinite(Number(kilowatts)) ?
    '—' : String(Math.round(Number(kilowatts) * 1000) || 0);
}

export function powerText(text) {
  return String(text ?? '').replace(/(-?\d+(?:\.\d+)?)\s*kW\b/g,
    (_, value) => `${watts(value)} W`);
}

export function dailyEnergyRows(summary, key, state) {
  const {now, policy: {timezone}} = state;
  const date = new Intl.DateTimeFormat('en-CA', {timeZone: timezone,
    year: 'numeric', month: '2-digit', day: '2-digit'}).format(new Date(now));
  const current = summary?.date === date && summary.timezone === timezone;
  const prediction = current && summary.prediction_revision === state.revision &&
    summary.prediction_plan_id === state.accepted?.id ? summary.predicted_kwh : null;
  const definitions = {
    grid: [['←', 'import', 'Grid import'], ['→', 'export', 'Grid export']],
    solar: [['∿', 'solar_ac', 'AC solar'], ['⎓', 'solar_dc', 'DC solar']],
    ess: [['↓', 'ess_charge', 'ESS AC charge'], ['↑', 'ess_discharge', 'ESS AC discharge']],
    house: [['', 'house', 'Household energy']], ev: [['', 'ev', 'EV charging energy']]
  };
  const number = value => Number.isFinite(value) ? value.toFixed(2) : '—';
  return definitions[key].map(([symbol, name, label]) => ({symbol, label,
    actual: number(current ? summary.kwh?.[name] : null), predicted: number(prediction?.[name]),
    partial: current && !!summary.partial}));
}

export function connectionIcon(connected) {
  const label = connected === true ? 'Connected' : connected === false ? 'Disconnected' : 'Connection unknown';
  const mark = connected === false ? '<path d="M3 3L21 21"/>' : connected !== true ?
    '<text x="16" y="9" stroke="none" fill="currentColor" font-size="10">?</text>' : '';
  const status = connected === true ? 'connected' : connected === false ? 'disconnected' : 'unknown';
  return `<svg class="connection-icon ${status}" viewBox="0 0 24 24" role="img" aria-label="${label}"><title>${label}</title><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M8 3v5m8-5v5M6 8h12v3a6 6 0 0 1-12 0zm6 9v4"/>${mark}</g></svg>`;
}

export function entityState(entity) {
  if (entity.unit === 'kW' && entity.state !== '' && Number.isFinite(Number(entity.state)))
    return `${watts(entity.state)} W`;
  return `${entity.state || ''}${entity.unit ? ' ' + entity.unit : ''}`;
}

export function settingScale(field) {
  if (!['number', 'integer'].includes(field.kind)) return 1;
  if (field.path.endsWith('_kw')) return 1000;
  if (field.path === 'policy.capacity_eur_kw_month') return 0.001;
  return 1;
}

export function settingLabel(field) {
  return settingScale(field) === 1 ? field.label : field.label.replace(/kW\b/g, 'W');
}

export function displaySetting(field, value) {
  return value === null || value === undefined || value === '' ? '' : scaleDecimal(value, settingScale(field));
}

export function storedSetting(field, value) {
  return value.trim() === '' ? null : scaleDecimal(value, 1 / settingScale(field));
}

function scaleDecimal(value, scale) {
  // Shift the decimal exponent to avoid showing e.g. 0.0045000000000000005.
  const places = scale === 1000 ? 3 : scale === 0.001 ? -3 : 0;
  const [coefficient, exponent = '0'] = String(value).toLowerCase().split('e');
  return Number(`${coefficient}e${Number(exponent) + places}`);
}
