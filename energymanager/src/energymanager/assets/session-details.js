const escape = value => String(value ?? '').replace(/[&<>"']/g, character => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[character]));
const energy = value => value > 0 && value < 0.01 ? '&lt;0.01' : Number(value).toFixed(2);

export function sessionContributionMarkup(session, formatTime) {
  const allocation = session.energy_attribution;
  if (!allocation) return '<p>Detailed energy allocation is unavailable for this older plan. A new calculation will include it.</p>';
  const rows = (items, description) => `<ul>${items.map(row =>
    `<li><strong>${escape(row.title)}</strong> · ${escape(formatTime(row.deadline))}: ${energy(row.energy_kwh)} kWh ${description(row)}</li>`
  ).join('')}</ul>`;
  const driving = allocation.driving.length ? rows(allocation.driving, () => 'for driving') :
    '<p>No driving energy from this session is assigned to a trip in this forecast.</p>';
  const stored = allocation.stored_kwh > 1e-8 ?
    `<p><strong>${energy(allocation.stored_kwh)} kWh</strong> remains stored after the forecast trips, including any retained reserve or SoC target.</p>` : '';
  const unknown = allocation.unresolved_kwh > 1e-8 ?
    `<p><strong>${energy(allocation.unresolved_kwh)} kWh</strong> cannot be assigned to a trip or known remaining battery energy.</p>` : '';
  const targets = allocation.targets.length ?
    `<h3>Battery targets supported</h3>${rows(allocation.targets, row =>
      `towards the ${energy(row.target_kwh)} kWh ${row.kind === 'trip' ? 'departure' : 'SoC'} target`)}
    <p class="subtle">Target support uses the same driving or stored energy listed above; it is not additional energy. Repeated targets do not claim that energy again.</p>` : '';
  return `<h3>Planned energy use</h3><p class="subtle">Existing battery charge is used first, then charging sessions in time order. This is a forecast allocation.</p>${driving}${stored}${unknown}${targets}`;
}
