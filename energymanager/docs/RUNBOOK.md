# Run, configure, review and roll back

## Session contributions (4.4.8)

Click a scheduled EV session for its time, battery kWh and a compact Supports list.
Each row names a goal, deadline and contributed kWh. Short driving/target labels keep
mixed allocations distinct; overlapping amounts are never summed. Full attribution
metadata remains in decision exports. Legacy/unknown cases have brief fallbacks.
The accounting rules and charging behavior are unchanged. Update/reload the add-on for
the display change; no settings or goal migration is required.

## Goal presentation (4.4.7)

Overview shows goals due within the next24 elapsed hours, with an explicit empty-window
message. Its forecast cost card has moved to Planning. Use Planning for the complete
chronological goal list and Forecast costs & energy assets breakdown. Trip driving kWh
uses configured consumption and excludes the arrival reserve; the departure SoC target
includes that reserve. Only the earliest future goal shows a current-charge/target
bar, with both kWh quantities labelled. Unknown/stale/settling EV readings hide it.
Later goals still show forecast departure SoC/readiness. EV agenda/details show the same
trip estimate. Update/reload the add-on to receive the display change; no settings,
sensor mapping, goal or schedule migration is required.

## Snapshot planning and live execution (4.4.4)

Update the add-on and reload HA to use the release; no new setting or sensor mapping
is required. Agent release publication does not perform that installation operation.
Each schedule and its economic reference are validated on the original calculation
snapshot. Accepted results retain their full calculation grid and evidence; live
control selects the current interval and ignores elapsed work. Admission health,
revision/connection and physical-bound checks still gate publication; its actual
readings are recorded separately in result.admission.

Live ESS balancing and EV power modulation remain active under existing safeguards.
Load/PV mismatch, inventory drift and a higher measured peak alone do not request extra
solves or invalidate accepted work. Forecast updates and supported bias corrections
are queued for the next periodic snapshot. The five-minute idle refresh, manual
recalculation and structural/safety/input-recovery handling remain. forecast_updated
and forecast_bias events record queued inputs; they are not extra-solve requests.
The4.4.1 publication repair is removed. Original forecast readiness and costs remain
predictions; actual execution and later schedules are separate evidence. See the
[maintained architecture](architecture/Architecture_Proposal.md#snapshot-planning-and-live-execution--accepted-28-october-2026).

## Google Maps release and offline verification (4.4.0)

Save a Google Routes API key in Settings to activate routing immediately. Replacing or
clearing it applies without restart; calendar/other installation settings retain their
restart requirement. A first required route response validates the credential/service,
not the save itself. Rejected credentials and route failures remain unresolved and warn.
No separate paid validation probe or automatic retry loop is performed.

Run python tools/offline_e2e.py --routing-fixture from energymanager/ for two synthetic
calendar journeys through a local fake Google endpoint and a real seven-day joint solve.
It checks independent round-trip legs, traffic parameters, routed goals, API/checksum
persistence, real solver cancellation/reaping and latest-only adoption, fake hardware
guards and fake notifications. Existing --calendar-fixture covers legacy subscriptions.
All endpoints are fake/local; do not use a real key or installation for agent verification.
When reusing another checkout's editable interpreter, point PYTHONPATH to this worktree's
src and use a unique pytest --basetemp under ignored artifacts/. Keep preview ports and
databases separate. A public release is distinct from installing/operating the HA app.

## Local use

Release4.4.3 fixes false traffic-timing rejections from tiny duration changes and shows
safe failure reasons under EV → Journey routes. Update/reload HA, then Refresh routes
to retry previously unresolved trips. No configuration change or key re-entry is needed.
The minute of routing slack does not relax arrival deadlines or increase the request
limit. Real access/quota/connection/time problems still require the displayed action.
Archived journey_route_failed events provide code/status/time without raw provider data.

Release4.4.2 automatically retires elapsed manual goals and finished manual trips,
including older saved entries. No manual deletion or configuration migration is needed.
Unknown/external returns still require a fresh known home connection when applicable.
Archived events retain full retired goals; decision history is preserved. Existing
other charging authority remains usable during the refresh. A saved empty goal list
stays empty after restart. Update the add-on and reload HA to use the published version.

Historical4.4.1 extended existing future sessions for unconfirmed elapsed charging.
That publication repair and its fresh-stock audit are superseded by4.4.4. Old decision
exports may contain candidate_at_calculation/publication_repair evidence; new admissions
preserve the original schedule without an extension or a new remaining-energy budget.

Release4.3.20 introduced joint EV/ESS continuity selection within the existing0.02EUR
comparison/cash allowance. That objective remains, including actual phase transitions,
necessary availability/source/peak pauses and no invented wear charge. Its mismatch-
triggered solves/authority invalidation are superseded by4.4.4; the same supported
forecast-correction evidence now informs subsequent periodic calculations.

Release4.3.16 fixes an unnecessary EV stop if a control revision changes during
confirmation of an otherwise unchanged start. Identical pending commands keep their
original30second readback timeout and are not rewritten on each revision. Real stops,
changed phase targets, disabled control, stale inputs and charger faults still take
priority. The30second restart hold and90second delivery check are unchanged. Update
the add-on and reload HA; no new mappings/settings are needed. The4.3.15 EV action
strip/countdowns are included. The physical cause of any particular installation
incident still requires its recorded trace; offline reproduction is not live evidence.

The4.3.15 EV action strip reports the controller separately from charger state. During
the deliberate restart pause, Wait is highlighted with remaining seconds and a
30second total. Start means waiting for charger readback; Power means the acknowledged
request is awaiting measured delivery, with a separate90second check. Timer expiry
does not claim charging. A delayed API feed shows Awaiting control update and then
Controller status unavailable rather than inventing a transition. No new mapping or
setting is needed. This display does not change the charging sequence or its checks.

For display-only offline verification, run the synthetic E2E/native preview below,
select Restart hold ·30seconds in the native fixture and inspect the declining
countdown/ring on desktop and390px width. The fixture never changes backend commands.
Inspect fault scenarios and expired timers; restore Sampled fixture afterward.

Release4.3.13 adds a30second EV restart settling hold after phase acknowledgement
in either direction and after confirmed force off plus power below100W for ordinary
stops. Time already spent stopped counts. Current-only changes stay live; ESS and
protective stops remain responsive. Existing command/readback/error/watchdog guards
remain. The old phase-switch cooldown (600s by default) is removed from planning
and control, and its Settings field is retired. Existing JSON values are accepted
and ignored; no configuration edit is required. Update the add-on and reload HA.
Native manual phase buttons still send direct one-time HA changes and do not run
this automatic sequence. No installation/hardware checks were performed by the agent.

Release4.3.12 gives each economic planning stage a bounded continuity refinement and
tries a single constant-current one-phase session for the next grid-only requirement.
It retains the flexible candidate when availability, permissions, source allocations
or the two-cent comparison/cash tolerance prevent that alternative. No wear cost is
added to the displayed bill. The final grid certificate preserves the transition score.

A rejected candidate now appears immediately under Decisions needing attention, with
a timestamp, reason and Decision evidence button. One automatic recalculation runs;
if it also fails, the attention item remains and the configured phone destination gets
a deduplicated notice. A successful accepted plan clears the item. Existing instructions
continue only while valid. A rejected peak check is not itself a request to approve a
higher peak: a new validated diagnostic must demonstrate that request. Actual pending
EV/ESS permission requests also notify the configured phone destination. The page
shows HA handoff, delivery retry or local-only notice explicitly. No phone destination
means no phone alert. History list/details now include publication rejection reasons;
failed exports retain the attempted reconciliation under publication_candidate without
replacing the original solver evidence. Update the add-on and reload HA; no new sensor
mapping or configuration option is needed.

Release4.3.11 fixes a starting-schedule failure when the seven-day horizon crosses
a billing month and adds bounded first-stage timeout recovery within the existing
planning budget. Update the add-on and reload HA; no configuration change is needed.
For a planning error, expand Decision history & technical evidence, Load decisions,
then select the rejected attempt at the relevant time. The list shows status/reason/
elapsed time; the detail shows each solver stage. Download full decision JSON (inputs
and results) there for offline diagnosis; developer tools/database access are unnecessary.
The export includes schedule/forecast inputs, so share only the intended decision.

Release4.3.10 corrects mouse-wheel input to time zoom: up zooms in, down zooms out,
anchored under the mouse. Drag left/right to pan. The existing mobile pinch zoom and
two-finger pan are retained; the user reported these working on mobile. The recorded
monthly peak uses red long dashes and appears with a peak-chart icon in the Grid box.
Click the peak value to open its mapped HA sensor history directly; clicking Grid
power still opens import/export source histories. An unavailable reading shows — but
its mapped history remains accessible. An unmapped sensor has a disabled history button.
Demo and standalone show the value without an HA history action. Update and reload HA.

The EV diagram now offers direct1φ/3φ/Auto HA controls, using the configured phase
actuator and the options that HA actually offers. This is a one-time manual action;
EnergyManager continues running and may change it again. Auto is the charger's own
mode, not automatic scheduling; existing fixed-phase validation can hold EV control
until1φ/3φ is selected again. Busy buttons disable during the request; failures are
shown without automatic retries. Demo, standalone and unavailable mappings disable
these actions. Charger details are now in the sidebar, including raw codes, current,
status age and HA/device frame times. Stale raw values remain labelled unverified.

Release4.3.19 adds actual charging power to the Overview EV box. In the native HA EV
visualization, click or keyboard-activate a sensor/setting value to open its mapped HA
entity and available history. Phase-mode history and the1φ/3φ/Auto controls are separate
actions. Colors and unverified labels remain. Unmapped/standalone/demo values explain
why no HA history is offered; controller requests and internal timestamps are identified
as EnergyManager data. Signed EV power remains visible. Update and reload HA; no new
mapping or dashboard copying is needed. The planning issue is unchanged in this release.

Release4.3.9 adds wheel navigation over either Overview graph: wheel down/right moves
later, up/left earlier. Outside the graph, the wheel scrolls the page. Ctrl/Meta-wheel
is left to the browser. On mobile use two fingers to pan horizontally or pinch to
zoom time (15 minutes–7 days); one finger still scrolls the page vertically. Both
graphs and session bars share the range. Arrows move its current width; Now resets
to six hours. Click-to-pin, keyboard values and selectable tooltip text remain.
The dotted Month peak line is the current recorded monthly grid-import maximum,
measured as a15-minute average. It is not an instantaneous or forecast peak or an
approval limit. An unavailable source shows no line; a real zero remains valid.
Update the add-on and reload HA; no new configuration is required. Real phone gesture
negotiation remains unverified; local touch checks use labelled synthetic pointers.

Release4.3.8 lets you drag the power or SoC graph left/right with the primary mouse
button on Overview. Both graphs and session bars move together; release to load older
history. A click still pins values, and tooltip text can still be selected. Now restores
the live six-hour window. Touch vertical scrolling and Planning remain as before.
Update the add-on and reload HA; no new configuration is required.

Release4.3.7 narrows Overview power/SoC graphs and session bars to six hours: two hours
behind now and four ahead. Arrows move six hours. History day opens six elapsed hours
from that date's local midnight; Now returns to the live window. Planning remains
seven days. Update the add-on and reload HA; no configuration changes are needed.

Release4.3.6 combines the annotated EV drawing with a diagnostic sidebar. Red means
reported error, green means confirmed OK, and white/normal theme text means neutral.
Forced stop, waiting and selected settings are neutral; unverified device readings
are labelled. A red historical incident does not mean the current charger error is
nonzero. Raw codes/timestamps remain under Charger details. History clicks on these
EV fields remain deferred. Reload HA after updating; no new configuration is needed.

Release4.3.5 adds EV & charger above the EV calendar. Measured power is actual sensor
power; Controller request is intent and may differ while waiting or changing phases.
Current limit and Phase mode are charger settings, not individual phase measurements.
Charger details shows raw codes and HA/device frame timestamps; unavailable settings
remain unverified until fresh charger data arrives. No new configuration is required.
Reload the HA dashboard after updating to load the new versioned card automatically.
For local visual checks, the native preview's SYNTHETIC EV display selector projects
charging, phase-transition, historical fault, reported device error, normal stop,
stale and disconnected states without changing the
backend controller or issuing actuator calls. These are fixtures, not installation data.

Release4.3.4 makes dashboard text selectable and preserves selection while polling
continues in the background. Click outside the selection to resume rendering. Connection
warnings name the failing request and clear after successful recovery; Copy error
copies the timestamped report or selects a read-only field for manual device copying
if clipboard permission is unavailable. A timed-out action may already have applied:
check the current state before retrying it. Failed status polls back off automatically.
Reload HA after updating; the existing loader does not need reinstalling. Compact
polling reuses unchanged plans; complete state and decision evidence remain available.

Release4.3.3 freezes daily expected totals at local midnight and saves them across
restarts. Hover/tap the energy row for capture time and recorded subtotal as-of time.
After a midday upgrade/start without a saved baseline, the first eligible estimate is
labelled first available. Later replans do not change that day's comparison baseline.
Brief negative derived balances show an inconsistent household input and pause EV/ESS
commands while sensors settle; persistent mismatch after the read watchdog (normally
30s) still raises the normal input error. Events power_balance_settling and
power_balance_recovered retain raw states/timing for diagnosis. No measured negative
household value is clamped into fabricated history or forecast-learning samples.

Release4.3.2 requires numeric go-e car/status/error and last Status change age (seconds)
for EV control. Enable the raw [CODE] sensors in HA if necessary, select the four
entities in EV fault recovery, save and restart. Existing uptime is rounded to hours
and is not suitable. Missing mappings pause EV while ESS remains usable. See SETTINGS.md.
HA service acceptance is distinct from charger readback and physical stopped power.
Do not replace the force selector with the integration's `stop_charging` service:
that service can restore neutral mode automatically after five minutes.

Persisted EV delivery incidents and optional bounded reboot recovery remain available.
From4.3.18 a finite negative EV power reading is accepted, including during charging
startup. It remains signed in measured history and net EV energy totals. Other invalid
inputs name the mapped entity, original state/unit and UTC read time in the UI and
input_error event; derived household mismatches identify their contributing sensors.
Unavailable/non-finite EV readings, SoC validation and charger supervision still apply.
Configure the reboot button, diagnostic entities and phone destination as described in
SETTINGS.md; save/restart before relying on them. Do not acknowledge an unresolved
incident before checking its reason and recorded states. Report JSON distinguishes
requested commands from actual service calls. It contains only archived evidence.
The current pre-upgrade incident cannot acquire an exact timestamp or raw states that
were never recorded. The new event-time index may make first startup slower on a large
archive. Report reads use a separate worker, five-second budget and10,000event limit.
From4.3.17 the report starts five minutes before the incident began, rather than
five minutes before fault detection, and ends at the earlier of now or ten minutes
after detection. Re-exporting an existing incident after updating can include earlier
samples still in the archive. Missing onset timestamps fall back to detection; missing
samples remain missing. A capped report explicitly says its later events were omitted.

For a labelled local-only incident preview, run `python tools/offline_e2e.py --serve
--ev-fault-fixture` and, in another terminal, `python tools/native_dashboard_preview.py`.
This seeds synthetic T−5minute states and an unresolved fault only after the ordinary
fake E2E completes. All service calls/notifications stay on its fake HA endpoint.
Never point this verification fixture at an installation.
Use `--serve --input-fault charger` to verify the EV-only unavailable-status warning
after the baseline E2E; it changes only the local fake charger status.

Use Python3.13 (also tested on3.12 during development). Run from `energymanager/`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m energymanager --port 8100 --budget 120
```

Open http://127.0.0.1:8100/ . Overview shows measured/synthetic and planned powers,
battery states and separate EV/ESS sessions. Planning shows the entire seven days.
EV opens the dedicated calendar and daily agenda for the next 168 hours. Select a date
to inspect journeys, expected returns, minimum SoC and planned charging. Add a Journey
or SoC goal from that page; open an item for details, or use Edit/Remove in its agenda.
Daily readiness settings remain under Settings → EV and charger. During recalculation,
requirements stay visible while obsolete charging/outcome data is withheld.
Add/edit/remove timed SoC goals or total-distance journeys. Expand reasons, sessions
and history for explanations and immutable decision evidence. Approval buttons act on
the displayed revision. Hardware control is disabled by default. The demo advances an
explicitly synthetic device model and does not use installation inputs or databases.
Settings can separately read HA's entity list to prepare the configured installation.

Power is displayed in W, energy in kWh. Settings converts displayed watt limits to the
existing configuration units. Goal dates use the installation timezone: choose a day
on the calendar, an hour/minute on the clock, and OK; keyboard entry is also available.
Cancel keeps the previous value. Clear removes an optional return. During a repeated
DST hour select the first or second occurrence; nonexistent local times cannot be saved.
Morning SoC targets alone do not imply driving or a battery withdrawal.

This workspace's prepared environment is `.venv313/Scripts/python.exe`. Dependencies
are isolated, not registered system-wide. `requirements.lock` and `requirements-dev.lock`
contain the tested exact Windows3.13 resolution; Linux wheels/container must be checked
on the target host. The command above installs a source editable package; the built
wheel under `dist/` supports a separate installation without repository imports.

```powershell
.\.venv313\Scripts\python.exe -m pytest -q
.\.venv313\Scripts\python.exe -m ruff check src tests tools
.\.venv313\Scripts\python.exe -m mypy src/energymanager
node --check src/energymanager/assets/app.js
node --test tools/frontend.test.mjs
.\.venv313\Scripts\python.exe tools/offline_e2e.py
.\.venv313\Scripts\python.exe tools/benchmark.py --case mixed --budget 120
.\.venv313\Scripts\python.exe tools/benchmark.py --case winter --budget 120
.\.venv313\Scripts\python.exe tools/benchmark.py --case permission --budget 120
.\.venv313\Scripts\python.exe -m build --no-isolation
```

Run benchmarks sequentially, with the dev server stopped. Real HiGHS results depend on
machine and timing; inspect per-stage incumbents/bounds and validation, not only the
last solver status. Raw synthetic evidence is written under ignored `artifacts/` and
compact reports under `docs/`. No coarse distant horizon is used.

Frozen replay accepts a snapshot or exported `{snapshot,result}` decision, verifies an
available input checksum, and produces fresh evidence. `--budget` explicitly sets the
replay budget; matching the original value preserves that policy field. Solver time
limits can change incumbents; replay does not promise bit-identical optimization.

```powershell
.\.venv313\Scripts\python.exe -m energymanager --fixture artifacts/release-mixed.json --solve artifacts/replay.json --budget 120
```

## Main-project version 4 update

`config.yaml` now advertises **4.3.0** for the existing `energy_manager` Home Assistant
app and `ghcr.io/nxt-1/energymanager` image. It keeps ingress port8099 and manual startup.
The packaged Python distribution, CLI and module are all named `energymanager`. The
former standalone candidate has been moved into this main app; the old V3 modules,
tests and dashboard are replaced. The separate InfluxDB app is unchanged.

V4 starts in demo mode. On startup, including demo mode, the app creates a missing
`/config/energymanager.json` from its bundled synthetic example and logs the path.
The app configuration mount is writable for initialization. Existing files are never
replaced, including empty or unfinished files. Creation failures stop startup with a
clear error. Configured mode reads this file. It writes `/data/energymanager-v4.sqlite3`, separately
from V3 data. V3 options and database files are not automatically imported. Review the
mapping below; an old options object cannot enable V4 control. Existing JSON fixtures
and immutable candidate decisions remain usable for offline replay.

The app configuration mount follows the
[Home Assistant configuration contract](https://contributors.home-assistant.io/apps/reference/configuration/).
Ingress accepts Supervisor172.30.32.2 with its authenticated ingress path; direct dev
access remains localhost only, following the
[ingress boundary](https://developers.home-assistant.io/docs/apps/presentation/).
Version4.2.0 introduced the native HA dashboard strategy;4.2.2 adds archived graph history
and4.2.3 adds compact day-end energy projections and numeric graph cursors.
Follow the [one-time installation/migration guide](../../energymanager-dashboard/README.md):
download the loader from the add-on's Settings, register it as a module resource and
create a new dashboard with `strategy: {type: custom:energymanager}`. Later add-on UI
updates require an HA page reload, with no repeated YAML/file copying. Administrator
HA OS/Supervisor access is required; other installations keep the standalone UI.
No live dashboard was installed or modified during development.

Docker is unavailable locally. The V4.0.0 CI and image workflows verified the Linux
container build and publication; evidence is in VERIFICATION.md and ci-verification.json.
Supervisor installation and physical deployment remain separate checks. A target host
can run `docker build --build-arg BUILD_VERSION=4.3.0 -t energymanager:4.3.0 .` from this
directory. The repository publish workflow targets the existing GHCR image when
config.yaml is pushed to main; inspect the workflow for the version being installed.

The pre-promotion working files and staged patch were preserved locally under
`gpt/architecture/v4-promotion-2026-10-23/` (Git-ignored). Committed V3 history remains
available from Git; the original checkout HEAD was `7ea02e4`. Historical V3 evidence
stays under repository docs/, and original standalone-candidate reports/screenshots
are labelled under docs/history/standalone-candidate/. Do not use historical instructions
as V4 configuration defaults.

## Configuration mapping

Open **Settings** in EnergyManager for normal form controls and entity autocomplete.
Search by friendly name or entity ID; pickers show state and units and filter compatible
domains/units. In the HA app, entity discovery uses read-only `GET /core/api/states`
through the Supervisor, even when planning is in demo mode. The server reads the
Supervisor token from its environment; it never sends the token to the browser.
The installed HA app uses this same Supervisor connection automatically for live
measurements, actuators, forecasts and entity/notification discovery. No API URL,
token-variable name, network-access checkbox or forecast endpoint is configured in
the GUI. Standalone tools can supply ENERGY_MANAGER_HA_URL, ENERGY_MANAGER_HA_TOKEN
and ENERGY_MANAGER_ALLOW_REMOTE through their environment; old standalone connection
values remain readable for compatibility.

**Save settings** validates the complete configuration, preserves unknown fields and
writes a dated `*.backup-*.json` beside the configuration before atomic replacement.
External or concurrent edits produce a conflict instead of being overwritten. Discovery
failure leaves current mappings and other settings editable. Credentials remain in
environment variables. Restart explicitly to apply saved changes. The HA Configuration
tab's `mode` dropdown selects demo/configured; saving JSON does not change that mode or
the currently running controller. Hardware control is managed separately by the immediate Overview switch.

For local demo use, a missing `energymanager.json` is created beside the state database
so Settings is available without supplying `--config`. Such a demo still uses synthetic
planning/control inputs. Its entity picker may read HA's entity list when requested.

Find the generated `energymanager.json` through Samba, SSH or an editor under
`app_configs/<repository-id>_energy_manager/` (some tools call the parent folder
`addon_configs`). Home Assistant maps that app-specific folder to `/config` inside
EnergyManager. For a custom `configuration_file` path, look at that location instead.
The [HA configuration guide](https://contributors.home-assistant.io/apps/guides/options/#configuration-files-for-users)
describes this folder mapping. The Settings page edits this same file; manual editing
remains available for backup/recovery and is not needed for routine configuration.

For standalone use, `--config path/to/new-file.json` also creates a missing file and
parent folders. Alternatively copy `configuration.example.json` yourself. The starter is
labelled synthetic and contains every required physical field. Hardware control starts
off. No old options file is imported. For local fake integration, use loopback endpoints.
Start with `--config path/to/new-file.json`.

| New field | Source to review in old configuration | Required interpretation |
|---|---|---|
| `measurements.ev_soc` | `ev.soc_entity` | `%`, current battery capacity mapping |
| `measurements.ess_soc` | `ess.soc_entity` | `%`, physical capacity/minimum verified |
| `measurements.connected` | `ev.connected_entity` | Explicit on/off binary; normalize device enums |
| `measurements.ev_kw` | `ev.charging_power_entity` | Nonnegative W or kW |
| `measurements.ess_kw` | `ess.power_entity` | W/kW, **positive discharge**; normalize opposite signs |
| `measurements.pv_ac_kw` | `pv.solax_power_entity` | AC generation, W/kW |
| `measurements.pv_dc_kw` | `pv.shed_power_entity` | DC generation, W/kW; confirm actual topology |
| `measurements.grid_import_kw` / `grid_export_kw` | Separate P1 import/export sensors | Nonnegative W/kW; house demand is calculated automatically |
| `measurements.quarter_import_kwh` | Current Quarter Average Demand | P1 W/kW; fixed quarter-hour conversion applied internally |
| `measurements.monthly_peak_kw` | `monitoring.monthly_peak_entity` | Actual incurred billing quarter average, kW |
| `actuators.current` | `ev.current_entity` | `number.set_value`, integer amperes |
| `actuators.phase` | `ev.phase_mode_entity` | `select.select_option`:1 single,2 three phase |
| `actuators.force` | `ev.force_state_entity` | `select.select_option`:1 stop,2 charge; verify device meanings |
| `actuators.ess_setpoint` | `ess.setpoint_entity` | `number.set_value`, grid/converter AC W; negative supplies loads |

### P1 and go-e setup

Version4.0.4 uses the confirmed installation directly. **Settings → Measurements** asks
for the existing P1 import, export and demand entities. It has no house-demand sensor,
phase-count sensor or source/type dropdowns. Daily readiness, consumption and reserve
settings are grouped under **EV and charger**.

The known P1 mappings are filled when missing or still using the generated placeholder:

- Grid import: `sensor.p1_dongle_momentary_active_import`.
- Grid export: `sensor.p1_dongle_momentary_active_export`.
- Current Quarter Average Demand: `sensor.p1_dongle_current_quarter_average_demand`.

These are configuration defaults supplied by the user, not detected live measurements.
Keep existing non-placeholder mappings; the form still allows entity IDs to be edited.
Under Actuators select the existing go-e APIv2 Connect **Phase switch mode** entity once
as **Charger phase selector**. The same mapping supplies phase-mode readback. No
separate phase input is required. Raw options1/2 mean single/three phase. Auto or
unavailable means unknown: EV delivery pauses while fresh ESS balancing continues.
Phase changes retain stop/zero preparation, wait for readback and hold force off
for30seconds before charging resumes. There is no phase-switch cooldown.

House background is `import - export + AC_solar + ESS_AC_output - EV`. Both P1 grid
channels are nonnegative W/kW; ESS AC output is positive when supplying the AC bus and
negative when absorbing it. Use inverter AC power, not battery DC power. DC solar is
not added again to this AC balance. Negative derived demand beyond0.1kW is rejected;
small sampling differences are clamped to zero. Review AC topology and signs before control.

The confirmed demand sensor builds from zero during each quarter. Conversion is fixed:
`imported_kWh = demand_kW × 0.25 h`. W is converted to kW first. Instantaneous power and
lifetime energy counters are incompatible. Meter/controller clock alignment and reset
timing remain commissioning checks; samples spanning quarter boundaries are retried.

Existing JSON files are read without rewriting. Runtime and Settings resolve this setup
regardless of retired source choices. The next explicit save creates an original-byte
backup, persists missing P1 mappings and removes the three retired source-choice keys.
Unrelated values, custom mappings, unknown future fields and control flags are preserved.
Legacy house/phase-count mappings may remain in old files but are ignored and never
requested. New starter files omit them. Saving does not enable control or hot-apply changes.

Source inspection: the [P1 reader](https://github.com/Nxt-1/esphome-p1reader-BE/blob/0c0e9f07056e1907be9d92dcd06cbd4fa416f95d/components/p1reader/p1reader.cpp)
passes OBIS1-0:1.4.0 unchanged. The [go-e integration2026.10.3](https://github.com/marq24/ha-goecharger-api2/blob/2026.10.3/custom_components/goecharger_api2/const.py)
exposes the phase selector used here. Development used only synthetic local fixtures.

All physical limits, phases, electrical
power boundaries, efficiencies, EV consumption and both residual-inventory values must
be reviewed; old ESS aggregate caps must not be copied onto independent DC charging.
The provisional2.5kW floor,4kW automatic ceiling,30km reserve and tariffs are not claimed
as installation settings.

See [Settings and hardware control](SETTINGS.md) for the single Overview switch,
missing-field highlights and the optional phone notification picker. Notifications use
Home Assistant notify entities or phone-specific actions, with no webhook URL.

Configured mode now creates its forecasts internally. It reads latitude and longitude
from HA `zone.home`, then calls the original Open-Meteo `knmi_seamless` source for each
of the four recovered PV planes. No separate forecast service or forecast URL is needed.
The legacy forecast URL field is removed. Existing HA files do not need new connection
settings; the app connects automatically.

See [forecast sources and exact installation parameters](FORECASTING.md). Roof-front
and roof-rear production feed the AC channel; shed production feeds the DC channel.
The original correction tables are retained. Weather refreshes every30min independently
of measurement polling. A failed refresh keeps the old issuance timestamp, and stale or
incomplete data cannot authorize forecast-dependent purchases. Missing home coordinates,
HTTP failure and coverage problems appear in application status/evidence.

Household load is sampled from the measured background demand every5min and persisted
in the V4 SQLite file. The original35-day median predictor uses weekday/time-of-day
patterns when available and the recent3h measured median while learning. The banner
shows the learning state and sample count. V3 history/database files are not silently
imported or modified; a new V4 history learns from current measurements immediately.
There is no fabricated default household demand. Restart preserves V4 samples.

Planning still covers168 elapsed hours with windows no longer than5min. Weather requests
include9 calendar days to leave enough data for a late-evening start and refresh buffer.
UTC timestamps preserve DST; hourly solar means apply to the preceding hour. Interval
resampling preserves energy. Deterministic local HA/weather fixtures are explicitly
labelled SYNTHETIC and are only a verification source.

The HA input-read watchdog (default 30 s) restricts commands if validated input reads
cease. Available HA states do not expire merely because their report timestamps are old.
Unknown/unavailable critical inputs still block control; EV-only unknown state permits
independent ESS behavior. HA integrations own device availability. Verify that the P1,
ESS and charger integrations mark real device outages unavailable during commissioning.
Forecast over 2 h disables conditional work. The read/forecast thresholds and 15-minute
desired completion margin are provisional.

## Recalculate and planning activity (4.3.14)

Recalculate acknowledges immediately and replaces any running calculation with one
using current inputs. While busy it becomes Restart calculation; clicking again
cancels/replaces the current solve. Bursts produce only the latest calculation, never
a queue. The compact activity bar shows the actual stage and elapsed time; its moving
line has no percentage meaning. A green check briefly confirms a validated update;
failure stays visible. Valid prior instructions continue subject to normal control
guards. No extra hardware-control toggle or restart is needed for manual recalculation.

For offline checks use the fake E2E and native preview commands below. The E2E now
cancels a real HiGHS worker through `/api/replan`, confirms it was reaped and only the
newest replacement was adopted, while checking local control responsiveness. In each
dashboard click Recalculate, click Restart calculation during activity, verify the
elapsed/stage display and eventual confirmation, then inspect narrow layout and text
selection. `/api/state` includes `planning_activity`; the event log distinguishes
`planning_requested` and `planning_cancelled` from accepted/rejected decisions. No
partial result from canceled work is published. Use local synthetic endpoints only.

## Commissioning and rollback — later review, not performed here

1. Back up the current add-on/config/dashboard and independently export the new SQLite
   evidence. Keep a restorable V3 image and options/dashboard backup. Reproduce tests, wheel and target-host image.
2. Verify all mappings, signs, physical ratings, phase/stop timing, meter resets,
   forecast coverage, economics and UI permissions with control disabled. Confirm state
   and HA/device availability and the read watchdog, and understand the conservative initial ESS provenance ledger.
3. Review offline traces and compare shadow plans to real observations. Define usable
   emergency/manual operation and notification destination. Confirm actual host runtime
   and storage growth; no purge policy is enabled.
4. Only after separate authorization, establish one exclusive controller: stop old EV/
   ESS writers and verify stop/setpoint behavior. Then use the Overview hardware switch.
   Startup reconciliation initially revokes recorded commands. The removed commissioning
   flags have no authority. Never run competing enabled controllers.
5. To roll back, stop the new controller and verify EV stopped/ESS at the reviewed safe
   handover setting. Switch hardware control off in Overview. Restore/re-enable the previously reviewed
   V3 image/controller/configuration and dashboard, and verify sole authority. Preserve
   the V4 database and logs for diagnosis. Source promotion did not modify historical
   installation database files; never point V3 at the V4 SQLite database.

SQLite records are compressed and never automatically deleted. Events distinguish
observed, planned candidate, accepted, commanded dry-run/service-write and invalidated
states. The bounded GUI projection is not archival retention. Use SQLite's backup API
or stop the application before copying database+WAL; never copy a live main file alone.
Decision/input size and observed growth are reported in VERIFICATION.md; plan free disk
space and backups before unattended commissioning. No reset credits, paid API or recurring
automation are required. Resumption uses WORK_STATE.md; automatic resumption is not assumed.

## Archived graph-history verification

ARCH-010 is included in 4.2.2. The user authorized committing and pushing the
previously held implementation. Updating the add-on and reloading HA loads the new graphs.
Overview's History day selects six hours starting at local midnight; arrows shift six
elapsed hours, and Now restores the live six-hour window. Power/SoC graphs load the selected
archive range. Missing history remains blank; from4.2.3 normal detail/loading metadata
is in collapsed diagnostics and archive errors remain visible. Legacy battery percentages use current runtime
capacities where the archive did not record them; the chart explicitly labels this.

Offline browser verification only, from `energymanager/`:

```powershell
.\.venv313\Scripts\python.exe tools/offline_e2e.py --serve --history-fixture
# In a second terminal, after8102 is ready:
.\.venv313\Scripts\python.exe tools/native_dashboard_preview.py
```

Open localhost8102 for standalone, or localhost8103/native-preview for the labelled
HA-contract harness. `--history-fixture` seeds an isolated synthetic SQLite archive
with older5-second samples, daily power peaks, an explicit noon outage and EV-only
unknown SoC. It does not change current input readings, load-learning samples or control
authority. Choose the previous calendar day; navigate its six-hour power/SoC windows,
verify line breaks, six-hour navigation, Now and a day outside the fixture (blank). HA built-ins/Supervisor
remain simulated. Stop both test processes after inspection. Do not use an installation
database or substitute synthetic fixture values as evidence of live historical coverage.

For4.2.3 also inspect symbolic recorded ⇢ day-end energy rows, partial-coverage tooltips,
and unavailable forecasts when the accepted plan is obsolete or inputs unknown. Compare
both graph edges with session tracks on desktop and390px widths. Use pointer/touch and
keyboard cursor controls; check historical gaps, planned values at window edges and
offset-labelled repeated-hour times. Native sensor choosers must still open more-info.
Updating the add-on and reloading HA delivers these UI changes through the existing loader.

## Subscribed EV calendars (4.3.0)

Add labelled public HTTPS/iCalendar links in Settings, save and restart configured
mode. EV → Subscribed calendars shows last sync, failures and skipped all-day items;
Sync calendars refreshes all running subscriptions. Timed events create provisional
50km total trips with departure at event start and return four elapsed hours later.
Edit the source calendar; remove its link and restart to remove its managed journeys.
Keep subscription links/configuration/backups private. No Google routing is enabled.

For offline checks run `python tools/offline_e2e.py --serve --calendar-fixture` and the
native preview tool in another terminal. Two labelled synthetic feeds are served by
local fake endpoints; one event appears in both feeds and must be planned only once.
Verify the50km/four-hour labels, source/location, sync status, native/standalone agenda,
Settings add/label/remove/save/restart message and390px layout. The calendar fixture
uses the normal60-second planning budget and a180-second E2E acceptance timeout; the
older no-journey fixture retains its15-second budget. These are test-tool limits.
No live HA/database/hardware/notification/deployment checks are authorized here.
