// Conversion belongs at the UI boundary. API/configuration values retain their units.
export function watts(kilowatts) {
  return kilowatts === null || kilowatts === undefined || !Number.isFinite(Number(kilowatts)) ?
    '—' : String(Math.round(Number(kilowatts) * 1000) || 0);
}

export function powerText(text) {
  return String(text ?? '').replace(/(-?\d+(?:\.\d+)?)\s*kW\b/g,
    (_, value) => `${watts(value)} W`);
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
