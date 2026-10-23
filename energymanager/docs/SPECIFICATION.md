# First release implementation specification

This is the shipping specification for the EnergyManager 4.0.5 application. The
authorized handoff and confirmed decisions govern behavior. All supplied development
capacities, tariffs and efficiencies are **synthetic provisional parameters**.
PV plane geometry and correction tables are recovered installation values; verification
weather and measurements are explicitly synthetic fixtures or labelled public references.
No installation measurements or missing historical native archive were substituted.

## Built-in installation forecasting

Configured mode uses the recovered Open-Meteo KNMI seamless source, HA zone.home location,
exact four-plane installation and original empirical front/rear corrections. The shed
retains its physical model without an empirical factor. AC/DC routing matches V3.
The original35-day median load predictor consumes persisted5min measured background
samples, with a recent3h median during learning. No prepared forecast endpoint is required.
See FORECASTING.md for numerical parameters, source provenance and failure behavior.
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
and withdraws only the journey energy at departure. Manual SoC goals withdraw nothing.
Overlapping goals constrain the same battery trajectory. Unknown return remains away;
external or physically unachievable travel leaves dependent EV state unknown until a
measured reconnection. No external charging is fabricated. Priority then deadline order
locks best-effort outcomes only after proven hard infeasibility. Timeout is distinct.

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
requests, while permitted best effort continues. No timeout is labelled infeasible.

ESS grid charging must reduce a specific larger peak within24h and improve combined
economics including losses and inventory. It is disabled for ordinary arbitrage and
standing insurance. Required EV feasibility may be restored through ESS household
support only against a feasible higher-peak counterfactual. Adopted exceptions produce
deduplicated informational events; the default destination is local SQLite. An optional
configured webhook is separately testable. No external notice was sent in development.

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
existing valid EV work. No plan permits basic ESS balancing, no forecast grid precharge.
Missing EV SoC holds EV instructions while fresh shared powers still support ESS. Power
freshness30s, EV SoC900s and forecast2h are declared provisional commissioning values.
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

The main project is now EnergyManager 4.0.5. Its fresh joint core replaces V3 under the
`energymanager` Python package and existing `energy_manager` add-on/image identity. V3
source/tests/dashboard were replaced; historical evidence remains in Git and labelled
reports. V3 installation options and database files are not automatically imported. V4
uses its own JSON configuration and SQLite file, with control disabled by default. Only
the selected configuration file is initialized when missing: add-on startup (including
demo mode) and standalone `--config` copy a bundled synthetic starter with remote access,
commissioning confirmations and hardware control disabled. Existing files, including
unfinished files, are preserved. Creation failures stop startup with the path and reason.
The Settings page edits that same JSON using typed controls and searchable entity
pickers. Discovery is read-only through the server-side Supervisor token, or the saved
standalone HA connection. Tokens and unknown configuration fields are not returned to
the editor. Validated edits preserve unknown fields, create a dated backup and replace
the file atomically; revision conflicts prevent overwriting concurrent edits. File I/O
runs outside the control event loop. Saving affects the next explicit restart, not the
active controller. Local demo starts also initialize a missing file beside the database.
The add-on's app configuration mount is writable for initialization and editing. Only
amd64 packaging is declared. Deferred PV/storage expansion, market pricing, V2G, appliances, automatic
travel/external charging, learned policy, live deployment and historical retention
policy are outside this release. Live wiring, values and hardware timings remain
unverified and require the commissioning procedure in RUNBOOK.md.
