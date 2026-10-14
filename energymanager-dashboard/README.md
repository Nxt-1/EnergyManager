# V3 dashboard explanations

Overview and Planning include **Understand this plan** cards for history, requirements, EV sessions,
ESS actions, generic jobs, stage comparisons and GUI counterfactuals. They use authenticated Home
Assistant ingress; exporting JSON or running a CLI is not required. Existing charts and notification
behavior are retained. Use resource `/local/energymanager-timeline-card.js?v=300b3`.

See [GUI setup and permissions](../docs/V3-GUI.md), [validation](../docs/V3-validation.md), and the
current V3 installation notes below. Production HA ingress still requires approved installation-specific verification.

## Retained dashboard history (historical release notes)

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

## Historical v2.37 installation (superseded by V3 below)
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

## V3 explanations in Overview and Planning

The `energymanager-decision-details` card is included in both existing views. Install the reviewed
3.0.0b3 add-on and update the JS resource to `?v=300b3`; refresh the browser. The card automatically
finds a single installed Energy Manager add-on. If more than one is registered, set `addon:` to the
approved installation's full Supervisor slug in each card. Do not run parallel controllers.

Use the decision selector and Newer/Older buttons for history; select a session, ESS action,
requirement, job or interval to inspect recorded evidence. Choose From/Until and Calculate alternative
for EV/ESS/grid counterfactuals. Results never change the active plan or hardware permissions.
A Supervisor-authorized Home Assistant account is required; no token, public port or JSON file is needed.
See [GUI and ingress](../docs/V3-GUI.md) and [validation](../docs/V3-validation.md).
