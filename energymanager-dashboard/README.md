# EnergyManager Dashboard v2.37 — SoC colors and notification diagnostics

Dashboard-only update based on v2.36. No EnergyManager add-on changes.

## Changes
- ESS SoC uses the same Victron-blue (`#007AC2`) as ESS power in both the Overview and Planning plots.
- EV SoC stays green (`#16a34a`) in both charts.
- Diagnostics notification events use a dedicated card with local timestamps, separate entries, event, health and reason.
- Consecutive identical suppressed events are grouped; expand a group to see individual times.
- **Clear displayed** hides existing events in this browser and persists across dashboard reloads. New events appear normally. **Show buffered** restores whatever is still present in the add-on's 30-event rolling history. This does **not** clear the backend; clearing across clients requires a future add-on command.
- Remove both standalone explanatory Markdown cards from Diagnostics.
- Preserve all Overview navigation, chart statistics, Planning and Performance behavior.

## Installation
1. Replace the dashboard YAML and `/config/www/energymanager-timeline-card.js`.
2. Set the dashboard resource URL to `/local/energymanager-timeline-card.js?v=237`.
3. Hard refresh Home Assistant (`Ctrl+F5`).

## Validation needed
1. Console shows `[EnergyManager Dashboard] JavaScript v2.37 loaded`; `window.energyManagerDashboardInfo.notificationEventsCardReady` is `true`.
2. ESS SoC is blue and EV SoC green on both Overview and Planning.
3. Diagnostics events are separated and timestamps shown in browser local time; consecutive identical suppressed events are grouped and expandable.
4. Click **Clear displayed**: list empties; reload dashboard: it stays hidden; a new event appears when generated. **Show buffered** restores the current rolling buffer.
5. Both explanatory Markdown cards are gone, while health/technical entities remain.

## Offline validation
YAML parsed and expected views / series / card verified; JavaScript syntax and event grouping/clear handling validated in a Node mock. Live Home Assistant verification remains necessary.
