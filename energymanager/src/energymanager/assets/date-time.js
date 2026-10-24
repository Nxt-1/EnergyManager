const formatter = new Map();

export function localDateTime(instant, zone) {
  if (!formatter.has(zone)) formatter.set(zone, new Intl.DateTimeFormat('en-CA', {
    timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23'
  }));
  const parts = Object.fromEntries(formatter.get(zone).formatToParts(new Date(instant))
    .map(part => [part.type, part.value]));
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}

export function validLocal(value) {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) return false;
  const [year, month, day, hour, minute] = value.split(/[-T:]/).map(Number);
  const date = new Date(Date.UTC(year, month - 1, day, hour, minute));
  return year >= 1900 && year <= 9999 && date.toISOString().slice(0, 16) === value;
}

// A clock change can give a local time zero, one or two real instants.
export function localInstants(value, zone) {
  if (!validLocal(value)) return [];
  const nominal = Date.parse(value + 'Z');
  const offsets = new Set();
  for (const hours of [-36, -24, -12, 0, 12, 24, 36]) {
    const sample = nominal + hours * 3600000;
    offsets.add(Date.parse(localDateTime(sample, zone) + 'Z') - sample);
  }
  return [...offsets].map(offset => nominal - offset)
    .filter(instant => localDateTime(instant, zone) === value)
    .sort((a, b) => a - b).map(instant => new Date(instant).toISOString());
}

export function monthDays(year, month) {
  const first = new Date(Date.UTC(year, month - 1, 1));
  const padding = (first.getUTCDay() + 6) % 7;
  const count = new Date(Date.UTC(year, month, 0)).getUTCDate();
  return Array.from({length: Math.ceil((padding + count) / 7) * 7}, (_, index) =>
    index >= padding && index < padding + count ? index - padding + 1 : null);
}

export function clockValue(x, y, part) {
  const angle = (Math.atan2(x, -y) + Math.PI * 2) % (Math.PI * 2);
  if (part === 'minute') return Math.round(angle / (Math.PI * 2) * 60) % 60;
  const hour = Math.round(angle / (Math.PI * 2) * 12) % 12;
  return Math.hypot(x, y) < 80 ? (hour === 0 ? 0 : hour + 12) : (hour || 12);
}
