# Native EnergyManager dashboard

EnergyManager 4.2.2 provides real HA dashboard views, live boxes, Recorder battery
history and custom planning/EV/settings cards. It uses no iframe. The same reusable
components remain available through the add-on sidebar for standalone/fallback use.

## One-time installation or migration from the old iframe card

1. Update/start the EnergyManager add-on. Use an HA administrator account; the existing
   admin-only Supervisor ingress boundary is retained. HA OS/Supervisor is required
   for the native dashboard. No separate custom integration or HA token is needed.
2. Open the add-on's Settings page and use **Download dashboard loader**. Save that
   file as `config/www/energymanager-card.js`. The identical loader is also available
   in this repository's `energymanager-card.js`.
3. In HA, register `/local/energymanager-card.js` as a **JavaScript module** dashboard
   resource. If this resource already exists, replace its old file and refresh HA.
4. Create a dedicated dashboard, open its raw configuration editor, and replace that
   new dashboard's configuration with the contents of `energymanager-dashboard.yaml`:

   ```yaml
   strategy:
     type: custom:energymanager
   ```

   The managed Overview, Planning, EV and Settings views appear on dashboard load.
   Existing personal dashboards are not modified. An old `custom:energymanager-card`
   iframe configuration must be replaced by this strategy during this one-time migration.

The loader discovers the single installed add-on whose slug ends in `_energy_manager`.
If more than one matches, specify the actual installed full slug under `strategy.addon`.
An optional `strategy.title` changes the dashboard title. Do not guess a repository prefix.

## Subsequent updates

Install the add-on update and reload the HA page. The strategy reads the installed
release manifest and loads that release's layout and card code from versioned ingress
URLs. New views, cards, forms and styles arrive together; the short dashboard YAML and
installed loader stay unchanged for dashboard updates using bootstrap protocol1.
Already-open views report an updated add-on and request a reload instead of mixing
release code. Session renewal uses HA's own authenticated Supervisor WebSocket API;
mutating requests are never replayed automatically.

Keep personal cards/views on a separate dashboard. The generated EnergyManager layout
is maintained by the installed release rather than copied into editable card YAML.

## Live values, history and controller boundaries

Live summaries use `hass.states` and update from HA changes
without waiting for the add-on's measurement polling or its two-second plan-state poll.
Custom summaries retain W/kWh display. HA's own tiles/dialogs use their entity's units.
Click live boxes to choose underlying sensors and open the standard HA more-info dialog. Combined solar, net grid
and calculated household-demand summaries offer the contributing entities' histories;
this release does not create a fictitious measured household sensor.

The boxes include today's estimated energy, integrated from EnergyManager's recorded
powers in the installation timezone. Grid import/export and ESS charge/discharge are
separate; solar includes AC/DC totals. These are not meter counters. Missing coverage
is labelled partial, absent coverage unavailable; gaps are not filled. Totals refresh
every30 seconds. The first startup creates an index over existing measurement events,
which can take longer with a large archive.

HA Recorder supplies native sensor history, subject to its configured coverage and
retention. It does not import EnergyManager's separate SQLite archive. From 4.2.2,
custom power/SoC graphs load the visible range from EnergyManager's archive.
Use History day to inspect any retained local day, the arrows to shift 12 hours, or Now
to return to the live window. Missing readings remain blank. Older battery percentages
use current capacities when the original record did not store capacities; the chart
labels this assumption. Planned curves, goals,
permissions and settings still come from EnergyManager. Frontend HA readings cannot
satisfy backend enablement checks or grant hardware authority. The controller's current
five-second HA input polling and all safety/permission rules remain unchanged.

## Verification

Offline browser checks use explicitly SYNTHETIC `offline_e2e.py --serve` plus
`native_dashboard_preview.py` on localhost8102/8103. HA's built-in cards and Supervisor
messages are simulated there; the versioned custom cards, API and planner are real.
Actual HA frontend/Companion/Supervisor installation remains a target-system check;
no live HA configuration, database or devices were accessed during development.
