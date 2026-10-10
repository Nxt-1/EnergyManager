# EnergyManager dashboard v1.3

Requires EnergyManager v0.31.6, ApexCharts Card and this bundled timeline card.

1. Copy `energymanager-timeline-card.js` to `/config/www/energymanager-timeline-card.js` in Home Assistant.
2. Settings → Dashboards → Resources → Add resource: `/local/energymanager-timeline-card.js`, type **JavaScript module**.
3. Reload the browser (hard refresh if necessary).
4. Replace the EnergyManager dashboard raw YAML with `energymanager-dashboard.yaml`.

The clickable timeline currently shows EV charging runs only, because no Daikin task is controlled by the MILP yet.
The power chart includes expected AC+DC solar and the current observed monthly 15-minute grid import peak.
The energy chart shows *cumulative planned* grid import, export and expected PV energy over the 24-hour window.
These are not actual metered daily totals; adding actual daily energy requires separate verified energy sources.
