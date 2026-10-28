const escape = value => String(value ?? '').replace(/[&<>"']/g, character => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[character]));
const energy = value => value > 0 && value < 0.01 ? '&lt;0.01' : Number(value).toFixed(2);

export function sessionContributionMarkup(session, formatTime) {
  const allocation = session.energy_attribution;
  if (!allocation) return '<p>Contributions unavailable for this older plan.</p>';
  const contributions = new Map();
  for (const category of ['driving', 'targets']) {
    for (const row of allocation[category]) {
      const item = contributions.get(row.goal_id) || {...row};
      item[category] = row.energy_kwh;
      contributions.set(row.goal_id, item);
    }
  }
  const mixed = allocation.driving.length > 0 && allocation.targets.length > 0;
  const rows = [...contributions.values()].sort((a, b) => Date.parse(a.deadline) - Date.parse(b.deadline));
  const list = rows.length ? `<h3>Supports</h3><ul>${rows.map(row => {
    const amounts = [];
    if (row.driving !== undefined) amounts.push(`${energy(row.driving)} kWh driving`);
    if (row.targets !== undefined) amounts.push(`${energy(row.targets)} kWh${mixed ? ' target' : ''}`);
    return `<li><strong>${escape(row.title)}</strong> · ${escape(formatTime(row.deadline))} — ${amounts.join(' / ')}</li>`;
  }).join('')}</ul>` : '';
  const unknown = allocation.unresolved_kwh > 1e-8 ? '<p>Some contributions are unknown.</p>' : '';
  return list + unknown || '<p>Stored for later use.</p>';
}
