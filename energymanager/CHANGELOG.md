## 4.5.1 — Planned power profiles in task details

- Added planned power profiles to EV and ESS session details and EV goal details.
- Showed planned pauses, power changes and exact time ranges.

## 4.5.0 — Appliance power-profile recording

- Added appliance cycle recording and profile management to both dashboards.
- Added configurable machine sensors, thresholds and idle timeouts.
- Added cycle review, trimming and representative profile selection, plus editable Mazak power estimates.

## 4.4.17 — Joint source allocation during charging refinement

- Let sources and ESS dispatch redistribute across the whole horizon while smoothing one EV window.
- Remove incidental ESS stock targets, frozen future source dispatch and per-window import caps that could exclude valid continuous charging over tiny conversion losses.
- Reserve useful global refinement time inside the existing planning budget, account for measured solver overrun and skip exhausted solver stages with checked fallbacks.

## 4.4.16 — Charging continuity across the full forecast

- Apply one bounded continuity procedure to every forecast day and availability window, across inherited charging limits, instead of repeatedly targeting the first work.
- Offer compact checked charging profiles, a one-session alternative and flexible transition minimization.
- Refine sources/ESS for the selected EV schedule before window preservation, preventing a weak dispatch candidate from locking in unnecessary household imports.

## 4.4.15 — Continuous charging across active limits

- Try a continuous candidate for selected optional and required charging, even when named targets are already satisfied or absent.
- Reserve part of each solar-refinement allowance for a bounded continuity candidate, preserving future ESS supply.

## 4.4.14 — Consistent energy direction arrows

- Use → for grid import and ESS charging, and ← for grid export and ESS discharging, consistently in native and standalone summaries.

## 4.4.13 — Reliable solar-allocation candidates

- Try bounded EV/solar/ESS allocation candidates before the full optional search, and reserve part of the existing budget for refinement before source certification.
- Route otherwise unused DC solar through spare inverter capacity.

## 4.4.12 — ESS display direction

- Show ESS AC charging above zero and discharge below zero in live cards and actual, planned and archived charts.

## 4.4.11 — Resume saved schedules after startup checks

- Restore compatible accepted instructions after fresh input/charger and current settings/goal/permission checks, without waiting for a new optimization.
- Older plans without recovery metadata require one fresh calculation; subsequently accepted plans can recover on later restarts.

## 4.4.10 — Faster EV failure alerts and vehicle charging status

- Shortened charging-wait alerts from 15 to 2 minutes.
- Added optional FordConnect charging-state monitoring and fault alerts.

## 4.4.9 — Earlier required charging when waiting has no benefit

- Restore the existing preference for early required charging after joint economic and continuity selection, before final grid certification.

## 4.4.8 — Compact EV session details

- Remove generic reasons, repeated target capacity and accounting explanations from normal EV details.

## 4.4.7 — Near-term goals on Overview

- Replace the Overview forecast-cost card with chronological goals due in the next 24 elapsed hours, including morning requirements and an explicit empty-window message.

## 4.4.6 — Meaningful EV session contributions

- Replace the all-future-goals count with named trips and planned driving kWh, accounting for initial battery charge, intervening travel and other charging sessions.
- Show retained energy and unknown future use explicitly.

## 4.4.5 — Focused, chronological goal details

- Remove goal cards from Overview; show all Planning goals in deadline order, with morning requirements interleaved with journeys.
- Show trip driving energy in kWh alongside distance and departure SoC, consistently in Planning, EV agenda and goal details.

## 4.4.4 — Snapshot schedules with adaptive live control

- Validate each schedule and its economic reference against the optimizer's original snapshot.
- Removed fresh-stock publication revalidation and the 4.4.1 session-extension repair.
- Queue forecast updates and measured bias corrections for the next periodic calculation.

## 4.4.3 — Stable traffic routing and useful failure reasons

- Added a 60-second margin when selecting traffic-aware departure times.
- Show safe failure reasons for access denial, rate/quota limits, provider/connection/ timeout/response problems, missing home/destination and past/invalid timing.
- Archive only journey ID, fixed error category, numeric HTTP status and time.

## 4.4.2 — Retire elapsed manual goals

- Remove elapsed manual SoC requirements and finished manual journeys from active goals.
- Hide elapsed source-managed journeys from active views without deleting source records.

## 4.4.1 — Reconcile unconfirmed charging during calculation

- Recover a required-goal shortfall caused by elapsed charging that the latest battery reading has not confirmed.
- Reconcile the economic reference on the same time boundaries and recheck all physical, source, grid-purchase, peak-permission and rolling-economic limits.
- Reuse cumulative arithmetic in the independent audit instead of repeatedly scanning seven-day inputs.

## 4.4.0 — Google Maps journeys for EV charging

- Route selected calendars and destination-based manual journeys using predicted traffic and separate home-to-venue/return legs.
- Activate immediately when a Routes API key is saved in Settings.
- Refresh the next seven days daily, after event changes and on demand.

## 4.3.20 — Joint charging continuity and evidence-based recalculation

- Improved charging continuity within joint EV/ESS optimization.
- Accounted for phase changes and supported fixed-phase charging sessions.
- Replaced frequent mismatch replans with evidence-based forecast corrections.

## 4.3.19 — Overview EV power and native sensor history

- Show actual measured EV charging power in the Overview EV box, including zero and signed readings.
- Open mapped HA entity histories from the EV visualization's readings and diagnostics.

## 4.3.18 — Accept signed EV power and explain invalid inputs

- Accept finite negative EV power readings without rejecting inputs or invalidating control.
- Identify rejected sensors with their entity ID, original value/unit and read time.

## 4.3.17 — Include incident onset in EV reports

- Export from five minutes before the incident began through ten minutes after fault detection (or now, if earlier), so long waits include their initial charging sequence.

## 4.3.16 — Preserve EV starts across control revisions

- Preserved pending EV starts across control revisions.
- Discarded acknowledgements for revoked, unsent commands.

## 4.3.15 — Visible EV controller actions

- Show what EnergyManager is doing separately from the car/charger's reported state.

## 4.3.14 — Immediate recalculation and visual activity

- Make Recalculate cancel the current solver process and start a fresh calculation with current inputs.
- Replace work on material input changes; ignore routine same-revision requests while busy.
- Show immediate button feedback, a restart action, an animated stage/elapsed-time bar and a brief success confirmation in native and standalone dashboards.

## 4.3.13 — EV restart settling

- Hold charging off for 30 seconds after a confirmed phase setting change in either direction, and after a confirmed stopped/low-power state before restarting.
- Change current limits without stopping or adding a pause.
- Remove the configurable phase-switch cooldown from control, planning and validation.

## 4.3.12 — Smoother EV plans and visible planning failures

- Reserve continuity work within each economic stage and try a constant-current session for the next grid-only requirement.
- Prevent the final minimum-grid calculation from worsening charger transitions.
- Show rejected plans under Decisions needing attention with a timestamp, the quarter-hour peak/allowance where relevant, and direct decision evidence.

## 4.3.11 — Planner timeout recovery and accessible failure evidence

- Correct starting-schedule allowances across billing months: an incurred peak in the current month cannot authorize grid charging in the next month.
- Retry the required-schedule search once with the remaining global budget (reserving two seconds for validation) when its initial allowance expires without a candidate.
- Show rejected decision status, reason, timings and solver stages in the dashboard.

## 4.3.10 — Wheel zoom, Grid peak history and EV controls

- Correct mouse-wheel behavior to zoom the time axis around the pointer: up zooms in, down zooms out.
- Draw the monthly peak with red long dashes.
- Add a peak-chart icon and recorded peak value to the Grid box.

## 4.3.9 — Wheel, mobile time navigation and monthly peak

- Scroll either Overview graph through time with the mouse wheel.
- Bound time zoom to 15 minutes–7 days and move the current window width with arrows.
- Show the recorded monthly grid-import peak as a dotted line, labelled as a 15-minute average.

## 4.3.8 — Drag Overview graphs through time

- Drag either Overview graph left/right with the primary mouse button to move the shared time window, with power, SoC and session bars staying aligned.
- Redraw once per animation frame and load newly requested history after release.

## 4.3.7 — Six-hour Overview graphs

- Show two hours of history and four hours ahead on Overview, sharing the same six-hour range across power, battery SoC and session bars for more horizontal detail.
- Move six hours with the navigation arrows; a history date opens its first six hours.

## 4.3.6 — Annotated EV drawing and status colors

- Put measured power, battery level, current limit, phase setting and controller request around the charger/car drawing, with diagnostic states beside it.
- Show errors in red, confirmed OK states in green and neutral states in the normal theme text color (white in a dark dashboard).

## 4.3.5 — EV charger visualization

- Add an EV-tab charger-to-car visualization with battery level, measured/requested power, current limit, phase selector mode, connection, waiting and fault/recovery state.
- Update native EV power/battery values as HA states arrive without rebuilding the calendar.

## 4.3.4 — Dashboard request recovery and copyable text

- Reduce polling payloads by sending display-only plan data once per accepted plan, then reusing it while polling live status and a bounded recent-sample window.
- Identify timed-out requests, retain useful data, back off failed state polls and clear connection warnings after recovery.
- Enable text selection inside HA, retain selections during automatic refreshes and keep source-history clicks from interrupting a selection gesture.

## 4.3.3 — Stable graphs and fixed daily energy estimates

- Save one fixed midnight energy estimate per local day and operating mode, surviving restarts and replans.
- Load recorded daily totals independently of live updates; coalesce archive reads, bound queries and retain dated subtotals through temporary read failures.
- Allow derived negative household balances to settle for the input watchdog period without a global error or plan invalidation.

## 4.3.2 — go-e charging supervision

- Interpret numeric car/status/error readings before timing non-delivery; require an advancing seconds heartbeat for EV authority while ESS remains available.
- Confirm current/force/phase readbacks without control-loop sleeps; bound failed commands and phase transitions.
- Reboot only confirmed healthy non-delivery, never reported errors, waiting states, stale/unknown inputs or failed commands.

## 4.3.1 — EV fault evidence and one-attempt recovery

- Timestamp EV non-delivery incidents and retain them across restarts.
- Record EV/go-e states every five seconds, with optional status/error entity mappings.
- Add an optional charger reboot-button picker.

## 4.3.0 — Subscribed EV calendars

- Add multiple labelled iCalendar links in Settings; sync at startup, every four hours and from the EV page after saving/restarting in configured mode.
- Import timed events, recurring instances and changes/cancellations into the EV schedule and joint plan.
- Clearly label provisional journeys:50km total, departure at event start and return four hours later.

## 4.2.3 — Compact dashboard and graph cursors

- Pair compact daily energy values with expected totals at today's end: recorded energy so far plus the current plan until local midnight.
- Inspect power and battery SoC values with a shared pointer, touch or keyboard cursor.
- Enlarge the power graph, align both graphs with session bars, combine time/plan metadata and move normal provenance/history details into diagnostics.

## 4.2.2 — Archived graph history

- Load older power and battery measurements for the visible graph range from SQLite.
- Bound archive queries and plotted detail, retain extrema and leave missing/invalid measurements blank.
- Record capacities for future historical SoC; explicitly label the current-capacity assumption used for older records.

## 4.2.1 — Daily energy in the live boxes

- Remove the duplicate sensor strip from the native dashboard.
- Show today's estimated grid import/export, AC/DC solar, household demand, EV charging and ESS charge/discharge energy in those boxes.
- Query the existing indexed measurement archive through a read-only worker connection; update energy summaries every 30 seconds without changing controller behavior.

## 4.2.0 — Native, managed Home Assistant dashboard

- Replace the iframe wrapper with actual HA views, live sensor tiles, native history actions and custom planning/EV/settings cards.
- Install one small resource and dashboard strategy once; subsequent add-on updates deliver versioned layouts/cards/styles on HA page reload, without copying new YAML.
- Receive current live values from HA state changes.

## 4.1.0 — Visual EV schedule

- Dedicated EV page with a seven-day calendar, expected away periods, charging sessions and morning/manual/departure SoC requirements.
- Add, inspect, edit and remove journeys and timed goals using the existing forms.
- Installation-local calendar boundaries handle clock changes and overnight events.

## 4.0.10 — Journey pickers and watt display

- Choose journey/SoC dates with a calendar and 24-hour clock, or type them; use the installation timezone and handle clock changes explicitly.
- Display power in W across charts, live cards, peak permissions, settings and entity previews; retain kWh for energy and existing API/configuration units.

## 4.0.9 — Trust HA availability and watch successful input reads

- Use Home Assistant's current available states without per-entity timestamp expiry or zero-value exceptions.
- Clarify the existing timeout setting as the HA input-read watchdog; no configuration migration required.

## 4.0.8 — Independent live values and per-input freshness

- Validate power, battery and status readings separately instead of giving every value the oldest sensor timestamp.
- Anchor quarter energy to its meter timestamp; require a current-quarter counter while allowing fresh power from just before a reset.
- Name the affected entity and report its age/limit or specific read/validation problem.

## 4.0.7 — Keep disabled control responsive during stop

- Return immediately from disabled actuator dispatch instead of waiting behind a slow stop request.
- Add a slow-stop responsiveness regression and separate baseline/switch timing evidence.

## 4.0.6 — Automatic HA connection and one hardware switch

- Remove connection and commissioning options; use the built-in HA Supervisor connection automatically.
- Replace notification webhooks with a phone destination picker supporting notify entities and phone notification actions.
- Add one immediate, persisted hardware-control switch to Overview, with input checks and stop/clear behavior on disable.

## 4.0.5 — Restore built-in installation forecasts

- Fetch the original Open-Meteo KNMI weather at the HA home location; no prepared forecast service is needed.
- Restore all four installed PV planes, original front/rear corrections and separate roof AC / shed DC forecasts.
- Restore household pattern learning from persisted measured background demand, with the original recent-history baseline.

## 4.0.4 — Configure the confirmed installation directly

- Remove the house-demand source, quarter-hour type and charger-phase information dropdowns.
- Calculate house demand and P1 quarter-hour energy internally, and read phases from the existing charger selector.
- Remove house-demand and phase-count sensor fields, including when loading old configurations.

## 4.0.3 — Existing P1 and go-e measurement support

- Accept P1 quarter-hour demand in W/kW with explicit conversion to imported energy.
- Calculate house demand from separate import/export, signed grid power or total consumption.
- Reuse the go-e phase selector without an extra phase-count sensor; wait for mode readback after switching.

## 4.0.2 — Visual settings and Home Assistant entity pickers

- Add a Settings page with searchable entity selectors, friendly names, current states, units and compatible-domain filtering.
- Configure connections, measurements, actuators, physical limits, readiness and tariffs through forms backed by the existing JSON file.
- Discover HA entities through the server-side Supervisor proxy, including in demo mode; credentials stay on the server.

## 4.0.1 — Automatic starter configuration

- Create the selected JSON configuration file on add-on startup if it is missing, including in demo mode.
- Bundle the complete example in the installed package and enable writes to the app configuration folder.
- Support the same first-file creation for standalone `--config` use; document where to edit it on HA.

## 4.0.0 — Joint EV/ESS architecture

- Replace the V3 application with the fresh joint seven-day EV/ESS MILP and independent responsive control.
- Add causal source accounting, scoped peak approvals, conditional solar tasks and explicit best-effort outcomes.
- Persist immutable decisions and observations; validate current state before publication and reconcile after restart.

## 3.0.0b3 — Dashboard explanations and measured planning quality

- Integrate archived history, EV/ESS/requirement/job selection, stage schedules, input changes and energy/cost evidence into Overview and Planning through authenticated Home Assistant ingress.
- Add isolated, bounded GUI counterfactual jobs, including ESS charging/discharging restrictions; preserve per-device control permissions and prevent diagnostics from changing live plans.
- Record objective improvements, solver node counts, warm-start results and stage quality metrics.

## 3.0.0b2 — Focused V3 corrections

- Correct non-quarter-hour trip withdrawals; keep conservative departure constraints.
- Add explicit storage charging windows separate from state requirements.
- Report economic counterfactual bounds, gaps and incomplete-solve limitations.

## 3.0.0b1 — Initial V3 preview

- Replace weighted scheduling refinement with bounded economic, robustness, operating-quality, stability and deterministic stages; retain the electrical model and fast safety controls.
- Add structured EV requirement provenance, generic jobs/storage, checksummed snapshots, decision diffs, offline replay/counterfactual CLI and focused dashboard evidence/session inspection.
- Initial preview hardware authorization was superseded by the per-device permissions in 3.0.0b2.

## 0.31.16 — Optional one-shot go-e charger reset

- Optional EV charging-fault reset after a confirmed no-power episode; reset at most once before a supervised charging retry.
- Persistent charging failure prevents further automated retries; no recovery notification is emitted.
- All reset settings are in the existing EV configuration group.

## 0.31.15

- Remove one-off MILP limit/thread benchmarks, their add-on options, background worker and diagnostic sensor publishing.
- Revert HiGHS to a fixed single-thread setting based on the 1/2/4-thread benchmark results.

## 0.31.14

- Verify EV charging is stopped using go-e power measurements before sending a phase-mode change.
- Wait 10 seconds after a phase-mode change before resuming charging, and block another physical change for 10 minutes.
- Hold the current phase at a safe current where possible during the lockout; otherwise stop charging.

## 0.31.13

- Shift the secondary MILP preferences toward delaying discretionary grid imports, while retaining EV session consolidation.
- Set default secondary solve limit to 30 seconds, with configurable 5–120 seconds; keep 30-second economic solve.
- Compare seven-day monetary accounting for economic and selected solutions, including import/export and ESS terminal value.

## 0.31.12

- Add an opt-in, one-shot benchmark of MILP tie-break limits at 10, 30, 60 and 120 seconds.
- Run the fixed planning snapshot in a separate, terminate-on-shutdown process and report the four outcomes.

## 0.31.11

- Limit the EV scheduling tie-break to 10 seconds within the existing 30-second overall solver budget.
- Add EV session-start variables only after the economic solution has been computed.
- Report separate economic and selected schedules (charging, starts, early-grid use and SoC ranges).

## 0.31.10

- Prefer fewer EV charging sessions within the existing €0.01 near-optimal economic band.
- Prefer earlier EV charging when equivalent; retain a weak tie-break for postponing grid imports.
- Use continuous EV session-start variables without additional binary variables.

## 0.31.9

- Treat configured EV charging-power loss as an EV availability fault after grace expires while connected.
- Isolate fast-dispatch and control-health diagnostic HTTP failures from hardware commands and retry failed dispatch cycles.
- Fix cooldown event spam; suppress repeat alerts once per episode and record recoveries without phone notifications.

## 0.31.8

- Add optional daily energy monitoring and two P1 capacity-peak inputs.
- Read configured daily or cumulative counters; use a persisted power-derived estimate when absent.
- Publish dashboard-only energy and peak sensors without modifying planner or control health.

## 0.31.7

- Export planned background and scheduled EV power separately for stacked-area dashboard charts.

## 0.31.6

- Publish the contiguous EV charging execution segments for the HA timeline, with energy and peak power.

## 0.31.5

- Renames internal planner types and methods to remove obsolete shadow terminology.
- Renames the plan status display name and corrects planner-only diagnostic metadata.
- Retains legacy Home Assistant entity IDs and stored InfluxDB schemas for compatibility.

## 0.31.4

- Fixes two Ruff E501 line-length violations in notification diagnostics; no runtime behavior changes.

## 0.31.3

- Stops treating delayed HA setpoint echoes as ESS write failures; retains service-call error and safety handling.
- Diagnoses an EV that remains plugged in, commanded to charge and below 100 W for 90 seconds.
- Suppresses phone alerts for brief health transients; exposes a bounded recent-event history for dashboard diagnostics.

## 0.31.2

- Adds pytest-asyncio to development dependencies so CI can execute the new async dashboard tests.

## 0.31.1

- Fixes Ruff UP037 in the MILP history writer annotation.

## 0.31.0

- Exports all 672 MILP intervals across seven Home Assistant daily plan entities for the full schedule view.
- Archives each adopted plan interval in InfluxDB 3 for historical plan-versus-actual comparisons.
- Historical writes run outside the MILP execution path, and database failures do not interrupt live control.

## 0.30.3

- Suppresses transient startup control notifications until the initial MILP attempt finishes.
- Evaluates current health at startup completion and reports persistent failures and later recovery.
- Exposes startup completion and startup-specific suppression count in notification diagnostics.

## 0.30.2

- Fixes the v0.30.1 CI Ruff failure by ordering the notification-test imports correctly.

## 0.30.1

- Adds optional Home Assistant notifications for live-control health transitions, including degraded operation, ESS safe fallback and recovery.
- Supports direct mobile-app notification services such as `notify.mobile_app_phone` through app configuration.
- Sends notifications only for alert-worthy health failures and recovery; a normal EV disconnect is not treated as a phone alert.

## 0.30.0

- Adds a 45-second live-input freshness watchdog for the grid, ESS and EV state used by hardware control.
- Drives the ESS to 0 W when critical ESS/grid inputs are stale or unavailable and stops the EV when its live state is unsafe.
- Adds bounded ESS setpoint acknowledgement retries and bounded go-e command retries, followed by a 10-second safe fallback.

## 0.29.0

- Adds guarded real EV charger control through configurable go-e current, phase-mode and force-state entities.
- Applies MILP EV commands as whole-ampere 1-phase/3-phase charging states and keeps EV control disabled unless explicitly enabled.
- Preserves the previous safe phase-switch sequence: stop charging, change phase mode, wait 3 seconds, set current, then resume.

## 0.28.1

- Changes whole-number Supervisor options to integer schema types to avoid silent numeric drift in the app UI.
- Adds `sensor.energy_manager_configuration_status` with the effective loaded ESS/EV whole-number options.
- Keeps runtime numeric handling and ESS/EV control behavior unchanged.

## 0.28.0

- Adds guarded real ESS hardware control through a configurable Home Assistant number setpoint entity.
- Converts the canonical ESS sign (positive discharge) to the Victron setpoint sign (negative discharge), clamps to the configured charge/discharge limits and rounds to the existing 10 W setpoint step.
- Uses the live P1 grid deviation for real ESS feedback, with a 100 W deadband, instead of the shadow-only EV-load substitution used before hardware control.

## 0.27.2

- Fixes the remaining v0.27 CI failure by aligning the planner cadence test with the asynchronous fast-dispatch architecture.
- Actuator-command publication remains covered by the dedicated fast-dispatch tests.

## 0.27.1

- Fixes the v0.27 CI Ruff failure by removing an unused `FastDispatchResult` import.

## 0.27.0

- Decouples MILP solving from live Home Assistant input processing so a 7-day replan no longer blocks fast dispatch updates.
- Runs fast shadow dispatch on an independent 1 Hz control loop using the latest coalesced Home Assistant state.
- Publishes the fast-dispatch sequence number, configured control interval and whether a MILP solve is in progress.

## 0.26.0

- Adds a fast shadow dispatch layer that tracks the current MILP grid-power target on every live Home Assistant state update.
- Replaces the measured EV load with the MILP-planned EV load when evaluating shadow dispatch, so a not-yet-controlled EV does not create a false ESS correction.
- Calculates the ESS power needed to absorb live grid/load/PV deviations and clamps it through the existing ESS actuator limits.

## 0.25.1

- Clarifies multi-trip EV validation diagnostics by replacing the misleading `outside_window_energy_kwh` field with `scheduled_after_deadline_kwh`.
- Adds `charging_during_away_windows_kwh` as a separate validation metric for actual charging while the EV is unavailable.

## 0.25.0

- Adds a recurring weekly EV trip schedule with configurable weekdays, departure/return times, hard departure SoC and expected trip energy.
- Generates every matching hard departure milestone inside the seven-day planning horizon plus one soft terminal preferred-SoC target.
- Models EV battery energy explicitly in MILP, including charge efficiency, battery-capacity bounds and expected trip-energy withdrawals at departure.

## 0.24.2

- Clarifies EV task diagnostics by publishing the hard minimum SoC and the soft preferred SoC separately.
- Publishes preferred AC/battery energy alongside the hard energy-by-deadline requirement.
- Keeps `target_soc_percent` as a compatibility alias and explicitly marks its role as `preferred`.

## 0.24.1

- Fixes the v0.24 CI Ruff failure by wrapping the EV minimum-runtime expression to the configured line-length limit.

## 0.24.0

- Splits the EV policy into a hard minimum SoC by departure and a soft preferred SoC target.
- Keeps the existing `target_soc_percent` as the preferred target and adds optional `minimum_soc_percent`; when omitted, the minimum defaults to the preferred target so existing installations preserve their current behavior.
- Lets MILP satisfy multiple cumulative EV energy-by-deadline milestones in one seven-day plan.

## 0.23.0

- Makes the HiGHS MILP the sole authoritative shadow planner and removes the portfolio/deadline scheduler from planning.
- Uses a 10-minute normal replan cadence with immediate replans for forecast/task/actuator changes, material ESS SoC deviation and significant unexpected background-load changes.
- Gives MILP a 30-second total solve budget: the economic stage has first claim on the full budget and the early-value tie-break receives whatever wall-clock budget remains.

## 0.22.1

- Warm-starts the second-stage early-value MILP from the complete feasible first-stage economic solution.
- Adds diagnostics showing whether the warm start was accepted and whether the published result came from the economic stage or the early-value tie-break stage.
- Keeps the economic objective, EUR 0.01 tolerance, three-day time-preference half-life, validation rules and planner authority unchanged.

## 0.22.0

- Adds independent post-solve validation for MILP interval timing, AC balance, ESS SoC/power limits, DC curtailment, discrete EV charging states and energy-by-deadline task fulfilment.
- Adds a second MILP pass that keeps the economic objective within EUR 0.01 of the first-stage economic result and then prefers earlier realized energy savings using an exponential three-day time-preference half-life.
- Publishes separate first-stage/tie-break solve times, validation results, task fulfilment checks and seven-day cost breakdowns for both the existing v0.20 reference plan and the MILP result.

## 0.21.0

- Adds a non-authoritative seven-day MILP evaluation using HiGHS/highspy alongside the existing v0.20 scheduler.
- Jointly models the current EV deadline task, ESS charge/discharge, grid import/export, AC/DC PV allocation, ESS SoC and monthly capacity-tariff peak while using the same economic objective as the active shadow planner.
- Keeps discrete EV whole-ampere 1-phase/3-phase operating states and configured ESS power/SoC limits as hard constraints.

## 0.20.0

- Extends the internal shadow planning horizon from 48 hours to 7 days while retaining the existing 24 h and 48 h views.
- Changes the economic objective and terminal ESS valuation to use the full 7-day horizon and adds 7-day plan-cost diagnostics.
- Replaces the v0.19 per-increment greedy EV search with a bounded portfolio search whose candidate count does not grow proportionally with every 15-minute slot in the horizon.

## 0.19.1

- Fixes the v0.19 CI lint failure by importing `Callable` from `collections.abc` on Python 3.13.

## 0.19.0

- Makes the configured economics influence the shadow EV schedule for the first time.
- Scores candidate EV charge allocations in EUR using projected import cost, export revenue and incremental capacity-tariff exposure while preserving the EV energy-by-deadline requirement as a hard constraint.
- Adds terminal ESS value to the optimizer objective so a candidate is not rewarded for ending the 48-hour horizon with an artificially depleted battery; usable terminal energy is valued at the import cost it can subsequently avoid.

## 0.18.2

- Separates tariff effective time from the time a tariff revision is recorded, so backdated tariff profiles can be stored safely.
- Reuses tariff revisions by profile ID instead of assuming the newest database timestamp is the configured profile.
- Adds historical tariff lookup by effective time and preserves later genuine tariff changes.

## 0.18.1

- Fixes CI lint failures in the v0.18 economic-accounting test suite by keeping module imports at the top of the test module.

## 0.18.0

- Adds read-only economic accounting for the existing shadow plan without changing task or ESS scheduling behavior.
- Tracks the current billing month's 15-minute grid-import peak using legacy five-minute history as an estimate and higher-resolution live observations for newly completed quarter-hour windows.
- Persists completed live capacity windows in InfluxDB so later restarts can retain the higher-resolution result.

## 0.17.1

- Adds an explicit `valid_from_utc` setting to tariff profiles so historical economics use the tariff's real effective date instead of merely the time Energy Manager first observed the configuration.
- Keeps first activation as a fallback only when no explicit effective timestamp is configured.

## 0.17.0

- Adds the first planner economics foundation without changing the v0.16.1 shadow scheduling behavior.
- Adds configurable marginal import energy cost, export revenue, capacity-tariff rate and capacity-tariff billing floor.
- Keeps economics disabled until all planner-relevant tariff values are configured; no placeholder prices affect planning.

## 0.16.1

- Fixes pre-control net-power diagnostics so scheduled task load is included in interval net power, deficit energy and peak deficit.
- Keeps the ESS/grid projection behavior unchanged; it already included scheduled load correctly.
- Adds regression coverage that a feasible EV task is never under-allocated after discrete charger-step quantization, including at 226 V.

## 0.16.0

- Adds the first shadow task scheduler: planner tasks can now contribute scheduled load to the 15-minute planning horizon.
- Schedules the current EV energy-by-deadline task from its earliest start using physically feasible whole-ampere 1P/3P charging steps; this is a deadline-feasibility baseline, not an economic optimizer.
- Keeps the existing raw background/PV deficit metric unchanged while exposing task energy through `scheduled_load_kwh`.

## 0.15.0

- Adds the first generic planner task model while keeping scheduling and hardware control disabled.
- Adds an EV target-by-departure task generated from live connection/SoC state and runtime policy settings.
- The EV task exposes earliest start, departure deadline, target SoC, required battery/AC energy, interruptibility and simple max-power feasibility.

## 0.14.0

- Adds the first generic actuator power-command contract while keeping all hardware writes disabled.
- Planner requests use actuator IDs plus requested power; actuator-specific code translates them into feasible dry-run commands.
- ESS dry-run commands enforce configured charge/discharge power limits and SoC boundaries.

## 0.13.0

- Adds the first generic read-only actuator registry for planner-facing device capabilities.
- Moves the ESS planning envelope behind an ESS actuator snapshot instead of passing ESS configuration directly into the planner.
- Adds an EV actuator snapshot with connection state, SoC, present charging power and configurable 1-phase/3-phase charge limits.

## 0.12.0

- Adds the first read-only ESS resource projection to the shadow planner.
- Uses current ESS SoC plus configurable capacity, SoC limits, charge/discharge power limits and efficiencies.
- Separates AC-coupled roof PV from DC-coupled shed PV so shed energy must pass through the ESS/inverter path before serving AC loads.

## 0.11.0

- Adds the first read-only shadow planner foundation.
- Aligns the rolling background-load forecast and PV-potential forecast onto one 15-minute timeline.
- Keeps a 48-hour internal horizon and publishes compact 24/48-hour summaries plus the next three hours of intervals.

## 0.10.2

- Scores all candidate load models on the same common set of valid forecast intervals for each horizon.
- Keeps one accuracy score set; no duplicate native/common model scores are exposed.
- Keeps `coverage` and `issue_coverage` as separate availability diagnostics for each model.

## 0.10.1

- Makes horizon energy accuracy the primary background-load backtest criterion instead of pointwise wattage MAE.
- Adds mean absolute total-energy error, signed energy bias and integrated absolute timing mismatch in kWh.
- Adds mean and p90 15-minute peak-load underprediction diagnostics for capacity-tariff risk.

## 0.10.0

- Added a runtime rolling-origin backtest for the background-load predictor; no household-specific correction constants are compiled into the application.
- Evaluates the current EnergyManager model against three simple baselines: persistence, same time yesterday and same time last week.
- Measures 1 h, 3 h, 6 h, 12 h and 24 h forecast MAE, bias, p90 absolute error, energy MAE and coverage.

## 0.9.3

- Treats stale EV charging-power history as 0 W after the existing 15-minute freshness window, instead of dropping the entire background-load sample.
- Keeps the stricter stale-value rules for grid, ESS and PV sources so sensor outages are not silently stretched into fake historical power.
- Uses a new derived-history recipe ID so the full archived source range is rebuilt automatically without re-importing the legacy source rows.

## 0.9.2

- Rebuilds legacy house/background history on a complete five-minute timeline instead of requiring every source to have written in the same bucket.
- Carries recent historical source values forward for up to 15 minutes to bridge normal sparse Home Assistant state updates.
- Treats stale values within ±50 W as inactive and resolves them to 0 W, allowing long zero periods such as PV at night, no export, idle ESS and an unplugged/idle EV to remain reconstructable.

## 0.9.1

- Added optional username/password authentication for the legacy InfluxDB 1.x backfill source.
- Uses HTTP Basic authentication when legacy credentials are configured.
- Keeps unauthenticated legacy sources supported by leaving both credential fields empty.

## 0.9.0

- Added incremental historical backfill from the legacy Home Assistant InfluxDB 1.x database into EnergyManager's InfluxDB 3 database.
- Reuses configured Grid, ESS, Solax PV and EV charging entity mappings; source entity IDs are never hardcoded.
- Archives only signals EnergyManager currently uses, as normalized five-minute source history in `legacy_power_source`.

## 0.8.0

- Added optional InfluxDB 3 persistence using a restricted database read/write token.
- Added `sensor.energy_manager_database_status` for connection and migration health.
- Background-load samples now persist indefinitely in InfluxDB while the current baseline model keeps a 35-day active training window.

## 0.7.0

- Added persistent sampling of canonical background-load power every five minutes.
- Added a 15-minute rolling background-load forecast for the future planner.
- The baseline model learns robust time-of-day patterns, then weekday/weekend and same-weekday behavior as history grows.

## 0.6.0

- Added canonical instantaneous AC house-load power derived from grid net power, Solax AC PV and normalized ESS AC power.
- Explicitly excludes the DC-coupled shed MPPT from the house-load balance so shed PV is not double-counted.
- Added known controllable-load power; v0.6 starts with measured EV charging power.

## 0.5.1

- Clamp small negative EV charging-power readings between -100 W and 0 W to zero.

## 0.5.0

- Replaced the fixed 20:15 day-ahead snapshot workflow with a continuously refreshed rolling forecast.
- Extended the PV horizon to today plus seven full future calendar days.
- Switched Open-Meteo to `knmi_seamless`, using KNMI HARMONIE AROME in the near term and ECMWF beyond it.

## 0.4.1

- Fixed Python 3.13/Ruff import placement for `Mapping`.
- Re-published the v0.4 predictor release under 0.4.1 after the 0.4.0 CI failure.

## 0.4.0

- Added the first Python predictor: a four-plane Open-Meteo PV forecast.
- Migrated the existing three-plane physical PV calculation into the app and added the 6.18 kWp shed plane.
- Added separate front/rear group calibration seeded from August-October 2026 production history.

## 0.3.1

- Re-published the v0.3 house-state release after missing source files were added to the repository.

## 0.3.0

- Added grouped runtime configuration for Grid, ESS, PV and EV inputs.
- Added a normalized internal House State with per-input validity, observation time and source metadata.
- Added ESS SoC/power, separate PV powers, EV SoC/connection/charging-power inputs.

## 0.2.0

- Replaced the single grid-power input with separate momentary import and export entities.
- Added canonical net grid power (`import - export`), with positive values meaning import and negative values meaning export.
- Added separate normalized import/export diagnostic sensors.

## 0.1.0

- Initial Home Assistant app skeleton.
- Internal Home Assistant REST API access through the Supervisor proxy.
- Home Assistant WebSocket state subscription for one configured grid-power entity.
