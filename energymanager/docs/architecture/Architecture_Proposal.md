# EnergyManager architecture

This is the single maintained architecture and implementation specification. Update
this same file as requirements and implementation evolve across releases and chats;
do not create a new handoff document for each version. The filename is retained from
the original architecture proposal, but its content now describes the current system.
The active application is `energymanager/`; its version is recorded in config.yaml and
the changelog. Last reviewed: 24 October 2026.

Repository-wide chat and coding rules live in the root [AGENTS.md](../../../AGENTS.md).
It directs chats to this architecture, the ongoing backlog and the required coding
skill, and records the user's permission and conversational preferences.

Confirmed user decisions take precedence over engineering proposals. This document
records the resulting behavior and technical contracts; [DECISIONS.md](../DECISIONS.md)
retains the decision context. [DEFERRED_WORK.md](../DEFERRED_WORK.md) records ideas
that require separate implementation authorization. Original draft wording remains
available in [Git history](https://github.com/Nxt-1/EnergyManager/blob/9d8a6944c20472df5b7b30b04cf14dcabea195c3/energymanager/docs/architecture/Architecture_Proposal.md)
and the preserved local architecture records.

Development capacities, tariffs and efficiencies are **synthetic provisional
parameters** unless explicitly verified for the installation. PV geometry and correction
tables were recovered from the original installation configuration. Verification weather
and measurements are labelled synthetic fixtures or public references. Do not substitute
these for installation evidence or fabricate the missing historical native archive.

## Scope and component boundaries

Schedule EV and ESS jointly over the full seven-day horizon with intervals no longer
than five minutes. Keep forecasting/input collection, explicit requirements, one bounded
MILP planning process, independent fast control, validated publication and persistence
as separate responsibilities. Full solves must not block live summaries or protective
control. One accepted shared plan owns both resource trajectories and permissions.

DHW, washing-machine/dishwasher scheduling, planned Mazak operation, appliance recognition,
learned driving, advanced forecasting and a standing ESS reserve for unforeseen peaks
remain deferred. Their uncontrolled consumption still belongs in the household forecast.
Resources and requirements should remain extensible without implementing those features
prematurely. ARCH-009 is implemented as a dedicated visual EV schedule page.

## Confirmed installation and GUI requirements

- Use separate P1 import/export sensors:
  `sensor.p1_dongle_momentary_active_import` and
  `sensor.p1_dongle_momentary_active_export`.
- `sensor.p1_dongle_current_quarter_average_demand` reports kW using a fixed full-quarter
  denominator. The user confirmed it resets near zero and builds up. Convert it using
  0.25 h; do not expose a quarter-measurement-type choice.
- There is no dedicated uncontrolled-house sensor. Derive household demand from the
  mapped powers. Use go-e APIv2 Connect's existing phase-selector readback without an
  additional phase-count sensor or phase-information choice.
- Preserve the original forecast source, installed PV planes and applicable correction
  factors. Use [FORECASTING.md](../FORECASTING.md) for their exact recovered values.
  Never invent replacement installation settings.
- Keep daily readiness with EV settings. Morning minima require charge by a deadline;
  they assume no driving. With these alone, the planned EV SoC stays level or rises.
  Explicit journeys withdraw estimated travel energy, and measurements reconcile state.
- Keep Overview and Planning inspired by the original first two dashboard pages:
  concise live summaries, actual/planned power and SoC, time navigation, grouped sessions,
  seven-day planning, goals/progress and inspectable reasons/approvals. ESS is blue;
  EV is green. Keep implementation details outside the main household flow.
- Use typed settings and HA-style searchable entity/phone selectors. Highlight missing,
  placeholder, unavailable or incompatible required values immediately. Remove long
  explanatory entity subtitles and nonexistent house/phase sensor mappings.
- HA connects automatically through Supervisor. Keep connection-address options,
  notification webhooks and the Commissioning tab out of the normal GUI. Phone notices
  use the optional selected HA notify entity or mobile-app action.
- The single Overview hardware switch applies immediately and persists its requested
  state separately from installation JSON. Saving installation settings still requires
  restart. The control and migration boundaries below remain mandatory.

## Built-in installation forecasting

Configured mode uses the recovered Open-Meteo KNMI seamless source, HA zone.home location,
exact four-plane installation and original empirical front/rear corrections. The shed
retains its physical model without an empirical factor. AC/DC routing matches V3.
The original35-day median load predictor consumes persisted5min measured background
samples, with a recent3h median during learning. No prepared forecast endpoint is required.
See [FORECASTING.md](../FORECASTING.md) for numerical parameters, source provenance and failure behavior.
Weather HTTP runs independently from fresh measurements and fast control; no missing
weather is replaced by zero, extrapolation or a demonstration forecast. A configured
startup has no demonstration journeys. Existing user goals are preserved.

## Inputs and requirements

Each immutable snapshot contains observed EV/ESS energy and source ledger, connection,
AC powers, separate DC PV, current-quarter imported energy, actual monthly peak, issued
forecast revision, policy, capabilities, goal revisions and explicit permissions. SHA256
covers canonical serialized inputs. SQLite retains every decision and event without
automatic deletion. Exported decision JSON can be replayed with `--fixture ... --solve`.

The configured application uses the confirmed P1/go-e installation. House demand is
reconstructed as `grid_import - grid_export + PV_AC + ESS_AC_output - EV`. ESS means
its AC bus boundary; DC solar is not counted twice. The P1 demand sensor builds from
zero and is converted from W/kW to quarter import kWh using a fixed0.25h denominator.
The go-e phase selector supplies forced-mode readback; no additional phase sensor is
required. Auto/unavailable is unknown and pauses EV while fresh ESS balancing continues.
Stop/zero/dwell and post-switch readback remain enforced without claiming physical
contactor telemetry. Meter/controller clock alignment remains a commissioning check.

Settings exposes only these sensor mappings, with no source/type selectors or computed
house/phase-count inputs. Daily readiness is in the EV group. Older JSON is interpreted
with the same setup immediately; retired source choices are ignored. Missing/generated
P1 mappings receive the known defaults, while custom mappings and unrelated values are
preserved. The file is unchanged until explicit save creates a backup and removes the
retired choices. Starter templates omit the unused house and phase-count mappings.

The horizon is168 elapsed hours in UTC, with local recurring deadlines and billing
months. Five-minute boundaries are split at goals, departures, returns, publication hold
and an initial15-second phase-preparation window. Partial intervals never exceed300s.
Daily readiness is50% at07:00 local, configurable, suppressed during known away periods.
It is not a persistent floor. A trip targets `min(capacity,(km+reserve_km)*kWh_per_km)`
and withdraws only the journey energy at departure. The configurable arrival reserve
starts at 30 km; it is desired remaining energy, not an extra withdrawal. Manual SoC goals withdraw nothing.
Overlapping goals constrain the same battery trajectory. Unknown return remains away;
external or physically unachievable travel leaves dependent EV state unknown until a
measured reconnection. No external charging is fabricated. Priority then deadline order
locks best-effort outcomes only after proven hard infeasibility. Timeout is distinct.

## Frontend units and journey dates

The EV page combines a calendar for the next 168 elapsed hours with a selected-day
agenda. Installation-local days can be 23 or 25 hours and the horizon may span partial
first/last days. Separate lanes show entered away periods, accepted EV charging sessions
and morning/manual/departure requirements. Overnight events are clipped for display;
whole-session battery energy is never presented as a per-day allocation. Unknown returns
remain open-ended and do not imply external charging or a learned driving routine.

`/api/state.schedule_goals` projects current explicit goals and the existing daily-goal
rules independently of solver/forecast availability, including saved morning approvals.
It does not persist generated goals or change scheduling. Outcomes and EV sessions are
shown only when `ev_plan_valid` is true, the accepted plan revision matches the current
application revision and it still covers future time. During recalculation or startup
reconciliation, entered requirements remain visible;
outdated outcomes are withheld. Current EV readings retain the live-input quality rules.
Users can inspect items and add/edit/remove explicit goals through the existing API and
date/time controls; daily readiness links to Settings. No new control authority is added.

The frontend converts power to whole W for live summaries, AC/DC components, actual and
planned charts, peak/approval values, settings and entity previews. Energy remains kWh.
Settings converts limits back to the existing kW JSON/API values, preserving unchanged
numbers exactly; capacity tariff is displayed in EUR/W/month and stored in EUR/kW/month.
Raw technical evidence retains original named units for reproducible replay.

Journey and timed-SoC date/time fields use a Monday-first calendar, a 24-hour clock and
an optional keyboard mode. They use the configured installation timezone rather than
the viewing device's timezone. Nonexistent DST times are rejected; repeated times expose
both offsets and retain the selected occurrence on edit. Cancel leaves the saved field
unchanged; the optional return can be cleared. This does not add a travel forecast:
standing morning targets withdraw no energy, and no daily driving is inferred.

## Joint MILP and source accounting

Powers are kW, energies kWh, interval duration `dt` hours. Nonnegative AC allocations
explicitly distinguish PV→EV/house/ESS/export/curtail, grid→EV/house/ESS, solar-origin
ESS→EV/house and restricted ESS→house. DC PV splits between battery charging and
inverter routing. Restricted ESS inventory never supplies optional EV or export.

`EV[t+1] = EV[t] + dt*eta_ev*(PV_EV+grid_EV+solar_ESS_EV) - trip_withdrawal`.
`ESS_solar[t+1] = ESS_solar[t] + dt*(eta_ac*PV_store + eta_dc*DC_store
 - (solar_dis_EV+solar_dis_house)/eta_discharge)`.
`ESS_grid[t+1] = ESS_grid[t] + dt*(eta_ac*grid_store-grid_dis_house/eta_discharge)`.
The configured minimum is a physical boundary; usable inventory is above it. All losses
appear once in their actual conversion path. Unknown initial stored provenance is
restricted; fresh import-free charging can establish new eligible solar inventory.

AC converter input/output have separate2.5kW provisional caps and one direction at a
time. DC battery capture is independent; AC+DC may exceed2.5kW. Shared battery rates,
capacity, DC routing and charge/discharge exclusion remain hard. Stored energy cannot
be sold. House and PV conservation, grid direction and physical connection limits are
hard. Simultaneous nominal PV ESS charging and household grid purchase is prohibited
to avoid relabelling grid-supplied storage as solar. Genuine DC-bus routing is allowed.

EV uses integer6–16A and supported one/three-phase modes. Modes exclude each other;
opposite active phases require600s separation. The actuator independently stops10s,
confirms zero3s and enforces dwell. It prepares a future phase during an off interval.
Planning holds the currently valid EV setting through the calculation budget plus15s,
so a candidate never assumes energy that could not have been delivered while solving.

For each known requirement checkpoint `k`, `B[k]=target[k]+prior withdrawals-initialEV`.
Let `S[k]` be cumulative eligible non-grid EV battery energy and `G` total direct grid
EV battery energy. A binary witness enforces
`G <= max(0,max_k(B[k]-S[k])) + integer final-slot rounding`, with no rounding if there
is no positive causal deficit. Thus later PV cannot erase necessary pre-departure grid,
and already sufficient pre-deadline solar cannot leave a nominal required-grid purchase.
A final certificate minimizes grid within the chosen modes, non-grid/storage allocations
and per-quarter import envelopes. Its Optimal status has this bounded scope, not a
global optimality claim. All flows are independently audited outside the model builder.

## Economics, opportunities and permission

The comparison is `imports*price - exports*price + incremental capacity cost
 + start stored EV/ESS value - end stored EV/ESS value`. Forecast bill and energy-asset
change are displayed separately. Unknown post-travel EV inventory receives no credit.
There is no monetary wear charge or cycle quota.

One finite planning process obtains required service, jointly optimizes zero-to-maximum
optional EV/ESS quantities, checks each extra charging origin over the following24h
(including both residual inventories), and uses a finite constraint repair if necessary.
Normal optional EV ceiling is80%; a100% probe executes only if matching the opportunity
later in the full horizon is proven infeasible with physical availability, losses,
inventories and no additional imports. Later diagnostic100% headroom grants no execution
authority. Timeout or an unvalidated comparison retains the80% result. Initial SoC above
80% never forces discharge. Named conditional solar-capture tasks carry source, amount,
forecast, target and deadline. A five-minute minimum is hard for entirely discretionary
plans; mixed required sessions retain necessary short service. Advancement requires an
existing task and at least a worthwhile five-minute opportunity before starting.

Capacity is a15-minute average including the measured consumed prefix. Cost baseline
is the actual incurred monthly peak or configured floor2.5kW, reset by local billing
month. A proposed future peak is never reused as incurred. Optional changes cannot
increase the required reference quarter envelope independently. Automatic4kW is a
provisional permission for required EV work or an economical specific ESS peak strategy.
Above it, EV grants are goal/revision scoped and bounded to that goal's remaining causal
energy. Fulfilled grants cannot fund another goal. ESS grants are separately scoped to
a forecast peak within24h; EV permission cannot lend ESS authority. A higher ceiling is
permission, not a target. Revised goals revoke approval; rejecting a proposed extension
preserves an existing lower EV grant. Physically useful feasible diagnostics produce
requests on creation/change or relevant changed circumstances, even days ahead; there
is no 12-hour waiting rule. Deduplicate requests and continue permitted best effort
while waiting. A timeout is not proof of infeasibility and must not itself trigger a
costly permission request. Do not request an extension that cannot solve a physical
charger or availability shortfall.

ESS grid charging must reduce a specific larger peak within24h and improve combined
economics including losses and inventory. It is disabled for ordinary arbitrage and
standing insurance. Required EV feasibility may be restored through ESS household
support only against a feasible higher-peak counterfactual. Adopted exceptions produce
deduplicated informational events; the default destination is local SQLite. An optional
configured HA phone notification destination receives deduplicated notices for an
adopted deliberate peak-increase strategy. Ordinary successful peak suppression stays
quiet. No external notice was sent in development.

## Continuity, control and publication

HiGHS runs in one spawned process; event-loop control normally ticks each second. A
coalesced event or five-minute refresh requests planning. One120s default wall budget
covers construction, reference/diagnostic/opportunity solves, polish and audits. Optional
refinements are skipped when unvalidated. Checked lower-peak warm starts are feasible
incumbents, not substitute published schedules. Raw status, bounds and gaps are retained.
One sweep of local-day operational neighborhoods keeps the entire horizon and fixed
outside decisions, with a **single**0.02EUR bound on comparison and cash against the
best economic result. It favors fewer starts/phase changes, lower throughput and early
required readiness; it cannot trade required outcomes for inventory. Desired15-minute
completion margin is visible, uncalibrated, and does not increase required energy.

Fast control uses fresh measured powers and quarter energy, protects only source-specific
EV/house-peak reservations, balances brief dips with ESS, reduces current for sustained
loss, and bypasses smoothing for peak danger. It reserves remaining planned quarter
imports, allowing legitimate short pulses rather than imposing a false instantaneous
limit. DC capture is reserved. Excess PV first charges ESS; only residual may advance
existing valid EV work. Without a usable plan, basic ESS balancing remains permitted;
forecast-driven grid precharging does not.
Missing EV SoC holds EV instructions while validated shared HA states still support ESS.
The HA input-read watchdog defaults to 30 s since the last validated snapshot. Individual
entity report timestamps do not expire available states. The read watchdog and forecast
2 h limit are provisional engineering parameters.
Measurement loss stops new commands. Source and permission guards remain independent
of economic score. Generation is checked between asynchronous actuator writes.

Goal/permission/connection changes invalidate affected EV or ESS authority, increment
the generation and coalesce a new solve. Household balancing remains useful when an EV
goal disappears. Before atomic adoption the application checks revision, slices elapsed
power, rebuilds both battery trajectories from measured state, clamps excess future
storage charging to headroom, and independently rechecks physical/source/permission and
rolling economics against a reconciled reference. Failure retains still-valid accepted
work. Restart initially revokes all recorded command authority until fresh reconciliation.
Actuator failures are explicit events; repeated failure backs off, and non-delivery
latches EV stopping. A solver-parent watchdog prevents orphan workers after service loss.

## Boundaries

The active EnergyManager application lives in the main project. Its fresh joint core replaces V3 under the
`energymanager` Python package and existing `energy_manager` add-on/image identity. V3
source/tests/dashboard were replaced; historical evidence remains in Git and labelled
reports. V3 installation options and database files are not automatically imported. V4
uses its own JSON configuration and SQLite file, with control disabled by default. Only
the selected configuration file is initialized when missing: add-on startup (including
demo mode) and standalone `--config` copy a bundled synthetic starter. The new single
hardware switch starts off and is the only control authority; legacy commissioning
flags and the old JSON control flag cannot enable it. Existing files, including
unfinished files, are preserved. Creation failures stop startup with the path and reason.
The Settings page edits that same JSON using typed controls and searchable entity
pickers. Discovery is read-only through the server-side Supervisor token, or the saved
standalone HA connection. Tokens and unknown configuration fields are not returned to
the editor. Validated edits preserve unknown fields, create a dated backup and replace
the file atomically; revision conflicts prevent overwriting concurrent edits. File I/O
runs outside the control event loop. Saving affects the next explicit restart, not the
active installation settings. The Overview hardware switch applies immediately and
persists in SQLite; turning it off revokes in-flight writes, stops EV charging and clears
the ESS setpoint. Enabling checks saved/runtime settings, entity availability and fresh
critical measurements. Restart waits for these checks before resuming a saved on state.
Incomplete saved settings keep the editor available without planning or command authority.
HA connections are automatic; phone notifications use selected HA notify entities/actions.
See [SETTINGS.md](../SETTINGS.md) for upgrade and control-state behavior. Local demo starts also initialize a missing file beside the database.
The add-on's app configuration mount is writable for initialization and editing. Only
amd64 packaging is declared. Deferred PV/storage expansion, market pricing, V2G, appliances, automatic
travel/external charging, learned policy, live deployment and historical retention
policy are outside this release. Live wiring, values and hardware timings remain
unverified and require the commissioning procedure in [RUNBOOK.md](../RUNBOOK.md).


## HA availability and input-read watchdog

HA owns device/integration availability. EnergyManager uses the current available state
and validates numbers, units, physical consistency and required entities. Unchanged values
are valid without zero-specific exceptions. Unknown/unavailable or failed critical reads
prevent a validated control snapshot; EV-only unknown inputs retain independent ESS behavior.

Observation.at is completion of the last validated HA input read. Existing control,
hardware-enable and household-forecast guards expire this snapshot if successful reads
cease. This is connection/snapshot health, not a claim that every device sampled at that
instant. Per-entity last_reported/last_updated timestamps are retained for diagnosis only;
old, absent or malformed report metadata cannot disable a valid available HA state.

Quarter demand is converted with the original meter semantics and accounted at read time.
The controller still handles quarter changes and measured counter resets. It does not
infer a wrong quarter from the timestamp of an unchanged counter. Available readings remain
visible independently of a failed snapshot. If reads stop, cached cards show a read-watchdog
warning; unavailable components remain explicit. Actual charts use validated HA snapshots.
Forecast issuance/expiry and permission/actuator guards remain unchanged. Installation
integrations must accurately signal device loss via availability; this remains a live check.

## Maintaining the architecture and continuing work

Keep this document current when an agreed requirement, formula, component contract or
implemented behavior changes. Record decision context in [DECISIONS.md](../DECISIONS.md)
and deferred ideas in [DEFERRED_WORK.md](../DEFERRED_WORK.md). Update the existing
[runbook](../RUNBOOK.md), [settings contract](../SETTINGS.md) and
[forecasting reference](../FORECASTING.md) where their details change. Preserve original
verification evidence; keep new results in [VERIFICATION.md](../VERIFICATION.md) and
meaningful progress in [WORK_STATE.md](../WORK_STATE.md). Do not maintain a separate
version-specific handoff or another duplicate architecture specification.

A new chat starts by reading this document, the decision log and relevant supporting
references, then compares the latest checkpoint with actual files and Git state.
Project files carry the requirements; do not assume automatic access to another chat's
history. The ignored `gpt/architecture/Implementation_Checkpoint.md` may contain newer
local/remote evidence in this workspace, but a fresh clone must not depend on it.

Use the user's code-writer skill for application changes. Do not write code without
explicit user authorization; screenshots and questions alone are discussion. Once
scope is authorized, finish it and ask before unrelated changes. Preserve unrelated
working/staged changes and historical evidence. Use local fake endpoints for verification;
do not access live HA/databases, operate hardware, send real phone notices or deploy
without separate authorization. Offline verification is not physical commissioning.

The runbook contains environment setup, tests, builds, configured offline preview and
rollback procedures. The prepared interpreter in this workspace is
`energymanager/.venv313/Scripts/python.exe`; `python tools/offline_e2e.py --serve` from
`energymanager/` provides a synthetic preview on localhost:8102 with a real seven-day
solve. Check current tests/package/CI rather than assuming an earlier release's results.

Include relevant documentation with the authorized implementation commit. Do not create
optional follow-up commits solely to record a successful release; use the ignored local
checkpoint and final reply for subsequent remote results. Do not buy/reset usage credits,
switch to paid API usage, promise automatic resumption or create an automation as a
workaround. On resumption reconcile the checkpoint against the workspace and continue.
