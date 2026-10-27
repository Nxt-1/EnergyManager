## 4.3.17 — Include incident onset in EV reports

- Export from five minutes before the incident began through ten minutes after fault
  detection (or now, if earlier), so long waits include their initial charging sequence.
  Existing incidents can be re-exported using retained archive data.
- Keep the bounded read and10,000-event limit; explicitly label omitted later events
  when the report is capped. Charging and recovery behavior is unchanged.

## 4.3.16 — Preserve EV starts across control revisions

- Keep confirming an unchanged start when the control revision changes; do not send
  an unnecessary stop or repeat the start. Preserve the original confirmation timeout
  and require a newer device readback for all unchanged pending settings.
- Discard unsent command acknowledgements after a generation guard revokes a write,
  restoring any previous pending command and restart deadline. Retain evidence after
  an unknown service response because the device may have accepted it.
- Keep protective stops, fault policy and charging delays unchanged. Includes the EV
  action strip and countdowns introduced in4.3.15.

## 4.3.15 — Visible EV controller actions

- Show what EnergyManager is doing separately from the car/charger's reported state.
  Highlight the active restart step and show a live countdown ring for the deliberate
  30-second hold, phase preparation and delivery check with distinct labels.
- Preserve fault details and measured readings. A timer ending never implies charging
  has started; expired updates become visibly unavailable. Charging behavior is unchanged.

## 4.3.14 — Immediate recalculation and visual activity

- Make Recalculate cancel the current solver process and start a fresh calculation
  with current inputs. Repeated requests replace each other instead of building a queue.
- Replace work on material input changes; ignore routine same-revision requests while
  busy. Preserve still-valid accepted charging instructions during manual recalculation.
- Show immediate button feedback, a restart action, an animated stage/elapsed-time bar
  and a brief success confirmation in native and standalone dashboards. Respect reduced
  motion; show failures without automatically repeating the request.

## 4.3.13 — EV restart settling

- Hold charging off for 30 seconds after a confirmed phase setting change in
  either direction, and after a confirmed stopped/low-power state before restarting.
  Time already spent stopped counts; repeated ticks and plan changes do not restart
  the hold. Keep ESS control responsive and retain immediate protective stops.
- Change current limits without stopping or adding a pause. Keep command readback,
  stale-input, charger-error and delivery supervision.
- Remove the configurable phase-switch cooldown from control, planning and validation.
  Retire its Settings field; existing configuration values remain readable and ignored.
- Preserve checked SoC ceilings through later optional refinements and the final
  grid certificate, including when the removed cooldown permits new schedules.

## 4.3.12 — Smoother EV plans and visible planning failures

- Reserve continuity work within each economic stage and try a constant-current
  session for the next grid-only requirement. Preserve goals, permissions and the
  existing two-cent economic/cash tolerance; retain flexibility when needed.
- Prevent the final minimum-grid calculation from worsening charger transitions.
- Show rejected plans under Decisions needing attention with a timestamp, the
  quarter-hour peak/allowance where relevant, and direct decision evidence.
- Recalculate automatically once, then send a deduplicated configured-phone notice
  if unresolved. Also notify for demonstrated EV/ESS peak permission requests.
  Distinguish HA handoff, retrying delivery and local-only notices.
- Include publication rejection reasons in history and preserve the failed
  reconciliation separately in diagnostic exports.

## 4.3.11 — Planner timeout recovery and accessible failure evidence

- Correct starting-schedule allowances across billing months: an incurred peak in
  the current month cannot authorize grid charging in the next month.
- Retry the required-schedule search once with the remaining global budget
  (reserving two seconds for validation) when its initial allowance expires without
  a candidate. Keep the same constraints,
  permissions, horizon and validation; optional refinements use only remaining time.
- Show rejected decision status, reason, timings and solver stages in the dashboard.
  Download the complete input/result JSON directly for checksum-preserving replay.

## 4.3.10 — Wheel zoom, Grid peak history and EV controls

- Correct mouse-wheel behavior to zoom the time axis around the pointer: up zooms
  in, down zooms out. Dragging pans; mobile pinch and two-finger gestures are retained.
- Draw the monthly peak with red long dashes.
- Add a peak-chart icon and recorded peak value to the Grid box. In native HA,
  clicking it opens the actual mapped sensor's more-info/history directly.
- Consolidate charger diagnostics beside the EV drawing and remove the details
  foldout and redundant footer note. Keep raw values and freshness visible.
- Add native HA 1 φ / 3 φ / Auto controls for one-time charger changes. Automatic
  control remains active and may overwrite a manual choice; no optimistic readback.

## 4.3.9 — Wheel, mobile time navigation and monthly peak

- Scroll either Overview graph through time with the mouse wheel. On mobile, pinch
  to zoom the time axis and swipe with two fingers to pan. Power, SoC and sessions
  stay aligned; Now restores six hours. One-finger vertical page scrolling remains.
- Bound time zoom to 15 minutes–7 days and move the current window width with arrows.
- Show the recorded monthly grid-import peak as a dotted line, labelled as a
  15-minute average. Keep it distinct from instantaneous power and planned limits;
  show unavailable rather than substituting a forecast or tariff floor.

## 4.3.8 — Drag Overview graphs through time

- Drag either Overview graph left/right with the primary mouse button to move the
  shared time window, with power, SoC and session bars staying aligned.
- Preserve click-to-pin values, keyboard inspection, selectable tooltip text and
  vertical touch scrolling. Now returns to the live six-hour window.
- Redraw once per animation frame and load newly requested history after release.

## 4.3.7 — Six-hour Overview graphs

- Show two hours of history and four hours ahead on Overview, sharing the same six-hour
  range across power, battery SoC and session bars for more horizontal detail.
- Move six hours with the navigation arrows; a history date opens its first six hours.
  Planning retains the full seven-day horizon.

## 4.3.6 — Annotated EV drawing and status colors

- Put measured power, battery level, current limit, phase setting and controller
  request around the charger/car drawing, with diagnostic states beside it.
- Show errors in red, confirmed OK states in green and neutral states in the normal
  theme text color (white in a dark dashboard). Waiting or forced stop is not an error.
- Keep current charger health separate from a latched incident. Stale device states
  remain explicitly unverified, with raw codes available in Charger details.

## 4.3.5 — EV charger visualization

- Add an EV-tab charger-to-car visualization with battery level, measured/requested
  power, current limit, phase selector mode, connection, waiting and fault/recovery state.
- Keep charger settings distinct from physical phase measurements; show unavailable
  readings explicitly, with expandable raw codes and HA/device frame times.
- Update native EV power/battery values as HA states arrive without rebuilding the
  calendar. Preserve diagnostic expansion, keyboard focus and text selection.

## 4.3.4 — Dashboard request recovery and copyable text

- Reduce polling payloads by sending display-only plan data once per accepted plan,
  then reusing it while polling live status and a bounded recent-sample window.
- Identify timed-out requests, retain useful data, back off failed state polls and
  clear connection warnings after recovery. Mutations are never automatically retried.
- Enable text selection inside HA, retain selections during automatic refreshes and
  keep source-history clicks from interrupting a selection gesture.
- Add timestamped, copyable connection warnings, including a manual-copy fallback
  when clipboard permission is unavailable. Existing installed HA loaders work unchanged.

## 4.3.3 — Stable graphs and fixed daily energy estimates

- Retain overlapping archive data while rolling graph windows refresh, including
  temporary archive failures; preserve gaps and clear unrelated date ranges.
- Save one fixed midnight energy estimate per local day and operating mode, surviving
  restarts and replans. Show its capture time in the tooltip. A later startup uses an
  honestly labelled first available estimate when no midnight baseline exists.
- Load recorded daily totals independently of live updates; coalesce archive reads,
  bound queries and retain dated subtotals through temporary read failures.
- Allow derived negative household balances to settle for the input watchdog period
  without a global error or plan invalidation. Pause EV/ESS commands immediately,
  record raw diagnostic states and escalate persistent mismatches. Do not fabricate
  household samples or feed inconsistent readings into forecast learning.

## 4.3.2 — go-e charging supervision

- Interpret numeric car/status/error readings before timing non-delivery; require an
  advancing seconds heartbeat for EV authority while ESS remains available.
- Confirm current/force/phase readbacks without control-loop sleeps; bound failed
  commands and phase transitions. Escalate continuing power after stop and unconfirmed
  hardware-off stops without restoring hardware authority.
- Reboot only confirmed healthy non-delivery, never reported errors, waiting states,
  stale/unknown inputs or failed commands. Keep single-attempt/cooldown guards.
- Replan within the intersection of HA charger limits and configured limits. Existing
  installations must select numeric [CODE] sensors and last Status change age (seconds).

## 4.3.1 — EV fault evidence and one-attempt recovery

- Timestamp EV non-delivery incidents and retain them across restarts. Show recovery
  progress, incident history, diagnostic preview and a full JSON report on both UIs.
- Record EV/go-e states every five seconds, with optional status/error entity mappings.
  Reports include the five minutes before detection and up to ten minutes afterward.
- Add an optional charger reboot-button picker. Stop first, persist one attempt, wait
  for fresh inputs and verify actual charging. Keep EV stopped and notify the selected
  phone when recovery fails; prevent reboot loops and allow acknowledgement after diagnosis.
- Pause Google Maps work and preserve its code/tests locally outside the release package.

## 4.3.0 — Subscribed EV calendars

- Add multiple labelled iCalendar links in Settings; sync at startup, every four hours
  and from the EV page after saving/restarting in configured mode.
- Import timed events, recurring instances and changes/cancellations into the EV
  schedule and joint plan. Keep manual goals and deduplicate repeated feed occurrences.
- Clearly label provisional journeys:50km total, departure at event start and return
  four hours later. Display source/location and sync failures or skipped all-day items.
- Retain last-good data on a failed refresh; protect subscription links and keep feed
  downloads/parsing separate from control. Google Maps routing follows separately.

## 4.2.3 — Compact dashboard and graph cursors

- Pair compact daily energy values with expected totals at today's end: recorded
  energy so far plus the current plan until local midnight. Use directional grid,
  AC/DC solar and car-connection symbols with accessible explanations.
- Inspect power and battery SoC values with a shared pointer, touch or keyboard cursor.
  Preserve gaps and mark interpolated values.
- Enlarge the power graph, align both graphs with session bars, combine time/plan
  metadata and move normal provenance/history details into diagnostics.
- Remove the duplicate native battery-history chart; sensor history remains available
  through the live boxes. Planning and hardware-control policy are unchanged.

## 4.2.2 — Archived graph history

- Load older power and battery measurements for the visible graph range from SQLite.
  Add an installation-local History day selector; keep12-hour arrows and Now.
- Bound archive queries and plotted detail, retain extrema and leave missing/invalid
  measurements blank. Cache ranges and prevent old responses replacing newer views.
- Record capacities for future historical SoC; explicitly label the current-capacity
  assumption used for older records. Keep control and archival retention unchanged.

## 4.2.1 — Daily energy in the live boxes

- Remove the duplicate sensor strip from the native dashboard. Keep clickable live
  boxes and their underlying HA sensor/history chooser, including EV/ESS power.
- Show today's estimated grid import/export, AC/DC solar, household demand, EV charging
  and ESS charge/discharge energy in those boxes. Integrate recorded powers in the
  installation timezone; mark missing coverage as partial and never invent measurements.
- Query the existing indexed measurement archive through a read-only worker connection;
  update energy summaries every 30 seconds without changing controller behavior.

## 4.2.0 — Native, managed Home Assistant dashboard

- Replace the iframe wrapper with actual HA views, live sensor tiles, native history
  actions and custom planning/EV/settings cards. Keep the standalone sidebar interface.
- Install one small resource and dashboard strategy once; subsequent add-on updates
  deliver versioned layouts/cards/styles on HA page reload, without copying new YAML.
- Receive current live values from HA state changes. Keep planner/control permissions
  and backend input polling unchanged; HA Recorder owns native sensor history.
- Share scoped UI components between native cards and standalone mode, with lifecycle
  cleanup and release-mismatch handling. Add installation instructions/download in Settings.

## 4.1.0 — Visual EV schedule

- Dedicated EV page with a seven-day calendar, expected away periods, charging sessions
  and morning/manual/departure SoC requirements. Select a day for its detailed agenda.
- Add, inspect, edit and remove journeys and timed goals using the existing forms.
  Daily readiness links to Settings. Unknown returns remain explicit.
- Installation-local calendar boundaries handle clock changes and overnight events.
  Requirements remain visible before a plan exists; obsolete charging/outcome data is
  withheld until a current plan is accepted. Scheduling and hardware policy are unchanged.

## 4.0.10 — Journey pickers and watt display

- Choose journey/SoC dates with a calendar and 24-hour clock, or type them; use the installation timezone and handle clock changes explicitly.
- Display power in W across charts, live cards, peak permissions, settings and entity previews; retain kWh for energy and existing API/configuration units.
- Preserve existing requirements and architecture references in tracked documentation, with a current V4.1 handoff and deferred EV calendar/page idea.

## 4.0.9 — Trust HA availability and watch successful input reads

- Use Home Assistant's current available states without per-entity timestamp expiry or zero-value exceptions.
- Keep report timestamps as diagnostics; stop control if validated HA input reads cease or required states become unknown/unavailable.
- Preserve value/unit/physical validation and quarter-hour accounting; remove comparisons between report timestamps and billing quarters.
- Clarify the existing timeout setting as the HA input-read watchdog; no configuration migration required.

## 4.0.8 — Independent live values and per-input freshness

- Keep available Overview values visible when another input fails; mark stale values and unavailable components individually.
- Validate power, battery and status readings separately instead of giving every value the oldest sensor timestamp.
- Anchor quarter energy to its meter timestamp; require a current-quarter counter while allowing fresh power from just before a reset.
- Name the affected entity and report its age/limit or specific read/validation problem.

## 4.0.7 — Keep disabled control responsive during stop

- Return immediately from disabled actuator dispatch instead of waiting behind a slow stop request.
- Add a slow-stop responsiveness regression and separate baseline/switch timing evidence.
- Includes the automatic HA setup, phone picker, missing-setting highlights and single Overview switch introduced in4.0.6.

## 4.0.6 — Automatic HA connection and one hardware switch

- Remove connection and commissioning options; use the built-in HA Supervisor connection automatically.
- Replace notification webhooks with a phone destination picker supporting notify entities and phone notification actions.
- Add one immediate, persisted hardware-control switch to Overview, with input checks and stop/clear behavior on disable.
- Highlight missing/placeholder/unavailable settings before Save and remove extra entity-help explanations.
- Keep the editor available for incomplete installations and hide unverified live-card values.
- Start the new switch off on first upgrade; retired commissioning and JSON control flags cannot enable it.

## 4.0.5 — Restore built-in installation forecasts

- Fetch the original Open-Meteo KNMI weather at the HA home location; no prepared forecast service is needed.
- Restore all four installed PV planes, original front/rear corrections and separate roof AC / shed DC forecasts.
- Restore household pattern learning from persisted measured background demand, with the original recent-history baseline.
- Preserve complete rolling seven-day coverage, both DST hours and forecast freshness through weather outages.
- Keep weather requests independent of measurement polling/control and prevent configured startup from inheriting demonstration journeys.
- Retain the connection settings for later review; mark the former forecast URL unused.

## 4.0.4 — Configure the confirmed installation directly

- Remove the house-demand source, quarter-hour type and charger-phase information dropdowns.
- Calculate house demand and P1 quarter-hour energy internally, and read phases from the existing charger selector.
- Remove house-demand and phase-count sensor fields, including when loading old configurations.
- Prefill known P1 mappings without overwriting custom settings; back up migration on explicit save.
- Move daily readiness, journey consumption and reserve settings into EV and charger.

## 4.0.3 — Existing P1 and go-e measurement support

- Accept P1 quarter-hour demand in W/kW with explicit conversion to imported energy.
- Calculate house demand from separate import/export, signed grid power or total consumption.
- Reuse the go-e phase selector without an extra phase-count sensor; wait for mode readback after switching.
- Keep ESS balancing responsive when phase information is unknown and preserve existing configuration interpretations until changed.
- Show only applicable measurement fields and describe source units, signs and conversions.

## 4.0.2 — Visual settings and Home Assistant entity pickers

- Add a Settings page with searchable entity selectors, friendly names, current states, units and compatible-domain filtering.
- Configure connections, measurements, actuators, physical limits, readiness and tariffs through forms backed by the existing JSON file.
- Discover HA entities through the server-side Supervisor proxy, including in demo mode; credentials stay on the server.
- Validate edits, preserve unknown fields, save a dated backup and replace the file atomically with protection against conflicting edits.
- Apply saved changes after an explicit restart; saving leaves the running controller unchanged.
- Show the running version in the GUI and retain the existing Overview and Planning pages.

## 4.0.1 — Automatic starter configuration

- Create the selected JSON configuration file on add-on startup if it is missing, including in demo mode.
- Bundle the complete example in the installed package and enable writes to the app configuration folder.
- Preserve existing files without modification; log new-file locations and report creation errors clearly.
- Keep generated settings explicitly synthetic, with remote access, commissioning confirmations and hardware control disabled.
- Support the same first-file creation for standalone `--config` use; document where to edit it on HA.

## 4.0.0 — Joint EV/ESS architecture

- Replace the V3 application with the fresh joint seven-day EV/ESS MILP and independent responsive control.
- Add causal source accounting, scoped peak approvals, conditional solar tasks and explicit best-effort outcomes.
- Persist immutable decisions and observations; validate current state before publication and reconcile after restart.
- Replace the dashboard entry point with the application's functional Overview and Planning pages.
- Use explicit reviewed V4 JSON configuration, a separate V4 SQLite database, and disabled control by default.
- Preserve the existing energy_manager add-on identity and GHCR image. V3 options/data require reviewed migration; they are not imported automatically.
- Local solver, integration, browser and package verification is documented in docs/VERIFICATION.md. Docker/Supervisor and hardware commissioning remain separate checks.

## 3.0.0b3 — Dashboard explanations and measured planning quality

- Integrate archived history, EV/ESS/requirement/job selection, stage schedules, input changes and
  energy/cost evidence into Overview and Planning through authenticated Home Assistant ingress.
- Add isolated, bounded GUI counterfactual jobs, including ESS charging/discharging restrictions;
  preserve per-device control permissions and prevent diagnostics from changing live plans.
- Record objective improvements, solver node counts, warm-start results and stage quality metrics.
- Benchmark identical inputs at 30/60/120 seconds and targeted formulation/budget variants.
  Keep production timing defaults unchanged: no demonstrated practical gain at the default budget.

## 3.0.0b2 — Focused V3 corrections

- Correct non-quarter-hour trip withdrawals; keep conservative departure constraints.
- Add explicit storage charging windows separate from state requirements.
- Report economic counterfactual bounds, gaps and incomplete-solve limitations.
- Compress archives with whole-decision checksums and default 30-day / 1 GiB retention.
- Use only per-device hardware permissions at the final service boundary. Reject obsolete preview
  configuration until device permissions are reviewed. Document direct replacement and rollback.

## 3.0.0b1 — Initial V3 preview

- Replace weighted scheduling refinement with bounded economic, robustness, operating-quality,
  stability and deterministic stages; retain the electrical model and fast safety controls.
- Add structured EV requirement provenance, generic jobs/storage, checksummed snapshots, decision
  diffs, offline replay/counterfactual CLI and focused dashboard evidence/session inspection.
- Initial preview hardware authorization was superseded by the per-device permissions in 3.0.0b2.
- Separate unspecified departure minimum from preferred terminal target. Configure an explicit
  minimum during migration; neither target is a physical maximum.
- Add bounded decision retention, configurable tolerances/grid limits and additive plan IDs in
  historic interval records. Existing telemetry remains intact.
- Add V3 regression tests and a real seven-day benchmark with saved quantitative counterfactuals.

# Changelog

## 0.31.16 — Optional one-shot go-e charger reset

- Optional EV charging-fault reset after a confirmed no-power episode; reset at most once before a supervised charging retry.
- Persistent charging failure prevents further automated retries; no recovery notification is emitted.
- All reset settings are in the existing EV configuration group.
- Removed the two obsolete MILP benchmark files so CI no longer runs their stale tests.

## 0.31.15
- Remove one-off MILP limit/thread benchmarks, their add-on options, background worker and diagnostic sensor publishing.
- Revert HiGHS to a fixed single-thread setting based on the 1/2/4-thread benchmark results.
- Retain configurable MILP tie-break time, seven-day accounting comparisons and the v0.31.14 EV safety protections.
- No EV or ESS control logic changes.

## 0.31.14
- Verify EV charging is stopped using go-e power measurements before sending a phase-mode change.
- Wait 10 seconds after a phase-mode change before resuming charging, and block another physical change for 10 minutes.
- Hold the current phase at a safe current where possible during the lockout; otherwise stop charging.
- Prevent a new planner output from reversing an in-progress phase transition.
- Remove user-facing recovery events and healthy-transition messages while retaining internal fault state tracking.
- No MILP objective, ESS controller, dashboard or data schema changes.

## 0.31.13
- Shift the secondary MILP preferences toward delaying discretionary grid imports, while retaining EV session consolidation.
- Set default secondary solve limit to 30 seconds, with configurable 5–120 seconds; keep 30-second economic solve.
- Compare seven-day monetary accounting for economic and selected solutions, including import/export and ESS terminal value.
- Offer an isolated 1/2/4-thread HiGHS benchmark with a fixed 30-second secondary solve; live default remains single-threaded.

## 0.31.12
- Add an opt-in, one-shot benchmark of MILP tie-break limits at 10, 30, 60 and 120 seconds.
- Run the fixed planning snapshot in a separate, terminate-on-shutdown process and report the four outcomes.
- Keep the authoritative 10-second tie-break and all ESS/EV control behavior unchanged.

## 0.31.11
- Limit the EV scheduling tie-break to 10 seconds within the existing 30-second overall solver budget.
- Add EV session-start variables only after the economic solution has been computed.
- Report separate economic and selected schedules (charging, starts, early-grid use and SoC ranges).
- Preserve the €0.01 economic tolerance, hard constraints and existing hardware behavior.

## 0.31.10
- Prefer fewer EV charging sessions within the existing €0.01 near-optimal economic band.
- Prefer earlier EV charging when equivalent; retain a weak tie-break for postponing grid imports.
- Use continuous EV session-start variables without additional binary variables.
- Publish EV session count and charging-delay score for validation.
- No changes to hard deadlines, SoC or hardware limits, fast dispatch, notifications or dashboard.

## 0.31.9
- Retain the last valid EV SoC, connection and charging-power inputs for up to 10 minutes during brief outages.
  Explicit EV disconnection still takes effect immediately. Hold EV commands during the grace period; ESS remains active.
- Treat configured EV charging-power loss as an EV availability fault after grace expires while connected.
- Isolate fast-dispatch and control-health diagnostic HTTP failures from hardware commands and retry failed dispatch cycles.
- Fix cooldown event spam; suppress repeat alerts once per episode and record recoveries without phone notifications.
- No MILP objective, database schema, dashboard, tariffs or configured hardware-limit changes.


## 0.31.8
- Add optional daily energy monitoring and two P1 capacity-peak inputs.
- Read configured daily or cumulative counters; use a persisted power-derived estimate when absent.
- Publish dashboard-only energy and peak sensors without modifying planner or control health.

## 0.31.7
- Export planned background and scheduled EV power separately for stacked-area dashboard charts.
- Preserve total load and all other plan fields; no optimization, control, or schema changes.

## 0.31.6

- Publish the contiguous EV charging execution segments for the HA timeline, with energy and peak power.
- Preserve separate task constraints and existing MILP/control behavior.


## 0.31.5
- Renames internal planner types and methods to remove obsolete shadow terminology.
- Renames the plan status display name and corrects planner-only diagnostic metadata.
- Retains legacy Home Assistant entity IDs and stored InfluxDB schemas for compatibility.
- Does not change MILP policy, dispatch, hardware control or safety behavior.

## 0.31.4
- Fixes two Ruff E501 line-length violations in notification diagnostics; no runtime behavior changes.

## 0.31.3
- Stops treating delayed HA setpoint echoes as ESS write failures; retains service-call error and safety handling.
- Diagnoses an EV that remains plugged in, commanded to charge and below 100 W for 90 seconds.
- Suppresses phone alerts for brief health transients; exposes a bounded recent-event history for dashboard diagnostics.
- Keeps normal EV disconnection informational and does not stop EV charging for a delivery warning alone.
- Does not change MILP optimization or hardware limits.

## 0.31.2
- Adds pytest-asyncio to development dependencies so CI can execute the new async dashboard tests.
- No runtime behavior or configuration changes.

## 0.31.1
- Fixes Ruff UP037 in the MILP history writer annotation. No runtime behavior changes.

## 0.31.0
- Exports all 672 MILP intervals across seven Home Assistant daily plan entities for the full schedule view.
- Archives each adopted plan interval in InfluxDB 3 for historical plan-versus-actual comparisons.
- Historical writes run outside the MILP execution path, and database failures do not interrupt live control.
- Does not alter planning objectives, ESS/EV control decisions, or safety handling.
## 0.30.3
- Suppresses transient startup control notifications until the initial MILP attempt finishes.
- Evaluates current health at startup completion and reports persistent failures and later recovery.
- Exposes startup completion and startup-specific suppression count in notification diagnostics.
- Leaves live hardware control, safety fallback, and notification cooldown unchanged.

## 0.30.2
- Fixes the v0.30.1 CI Ruff failure by ordering the notification-test imports correctly.
- No notification, ESS/EV control, watchdog, MILP, or configuration behavior changes.

## 0.30.1
- Adds optional Home Assistant notifications for live-control health transitions, including degraded operation, ESS safe fallback and recovery.
- Supports direct mobile-app notification services such as `notify.mobile_app_phone` through app configuration.
- Sends notifications only for alert-worthy health failures and recovery; a normal EV disconnect is not treated as a phone alert.
- Applies a configurable cooldown to repeated identical failure alerts.
- Runs notification delivery outside the 1 Hz control path so a slow or failed notify service cannot block ESS/EV hardware control.
- Adds `sensor.energy_manager_notification_status` with delivery counts, suppression count and the last notification error.
- Keeps the v0.30 watchdog, fallback behavior, MILP, ESS control and EV control unchanged.

## 0.30.0
- Adds a 45-second live-input freshness watchdog for the grid, ESS and EV state used by hardware control.
- Drives the ESS to 0 W when critical ESS/grid inputs are stale or unavailable and stops the EV when its live state is unsafe.
- Adds bounded ESS setpoint acknowledgement retries and bounded go-e command retries, followed by a 10-second safe fallback.
- Treats controller faults and unavailable live inputs as actuator availability changes for replanning instead of retrying forever.
- Adds `sensor.energy_manager_control_health` with healthy/degraded/safe-fallback state, stale inputs, write failures and errors.
- Keeps the MILP objective, tariff model, task semantics, 1 Hz dispatch cadence and configured ESS/EV limits unchanged.

## 0.29.0
- Adds guarded real EV charger control through configurable go-e current, phase-mode and force-state entities.
- Applies MILP EV commands as whole-ampere 1-phase/3-phase charging states and keeps EV control disabled unless explicitly enabled.
- Preserves the previous safe phase-switch sequence: stop charging, change phase mode, wait 3 seconds, set current, then resume.
- Forces Don't charge before the first valid plan, when the EV command is unavailable/idle and on clean shutdown.
- Adds `sensor.energy_manager_ev_control_status` with desired/observed charger state, phase-transition state and write counters.
- Publishes ESS and EV hardware ownership together in actuator-command diagnostics; ESS fast control and MILP policy are unchanged.

## 0.28.1
- Changes whole-number Supervisor options to integer schema types to avoid silent numeric drift in the app UI.
- Adds `sensor.energy_manager_configuration_status` with the effective loaded ESS/EV whole-number options.
- Keeps runtime numeric handling and ESS/EV control behavior unchanged.

## 0.28.0
- Adds guarded real ESS hardware control through a configurable Home Assistant number setpoint entity.
- Converts the canonical ESS sign (positive discharge) to the Victron setpoint sign (negative discharge), clamps to the
  configured charge/discharge limits and rounds to the existing 10 W setpoint step.
- Uses the live P1 grid deviation for real ESS feedback, with a 100 W deadband, instead of the shadow-only EV-load
  substitution used before hardware control. This prevents an EV still controlled elsewhere from creating fictitious ESS
  corrections.
- Commands a safe zero setpoint before planning starts, when no safe live target exists and on clean shutdown.
- Adds `sensor.energy_manager_ess_control_status` with desired/observed setpoint, write/acknowledgement state and write count.
- Publishes actuator-command diagnostics with ESS hardware-write ownership while EV control remains shadow-only.
- Adds `ess.setpoint_entity` and `ess.control_enabled`; hardware control remains disabled unless explicitly enabled.
- Keeps the MILP, economics and EV scheduling policy unchanged.

## 0.27.2
- Fixes the remaining v0.27 CI failure by aligning the planner cadence test with the asynchronous fast-dispatch architecture.
- Actuator-command publication remains covered by the dedicated fast-dispatch tests.
- No runtime, MILP, scheduling, configuration, or hardware-control behavior changes.

## 0.27.1
- Fixes the v0.27 CI Ruff failure by removing an unused `FastDispatchResult` import.
- No fast-dispatch, MILP, configuration, scheduling, or hardware-control behavior changes.

## 0.27.0
- Decouples MILP solving from live Home Assistant input processing so a 7-day replan no longer blocks fast dispatch updates.
- Runs fast shadow dispatch on an independent 1 Hz control loop using the latest coalesced Home Assistant state.
- Publishes the fast-dispatch sequence number, configured control interval and whether a MILP solve is in progress.
- Atomically replaces the active shadow plan only after a newly solved MILP plan passes validation.
- Prevents overlapping MILP solves; live state processing and fast ESS correction continue while HiGHS runs in a worker thread.
- Keeps the 10-minute periodic MILP cadence and existing event-triggered replans.
- Remains hard-coded shadow mode with no hardware writes.

## 0.26.0
- Adds a fast shadow dispatch layer that tracks the current MILP grid-power target on every live Home Assistant state update.
- Replaces the measured EV load with the MILP-planned EV load when evaluating shadow dispatch, so a not-yet-controlled EV does
  not create a false ESS correction.
- Calculates the ESS power needed to absorb live grid/load/PV deviations and clamps it through the existing ESS actuator limits.
- Publishes `sensor.energy_manager_fast_dispatch_status` with planned/measured power, ESS correction, residual tracking error and
  replan status.
- Triggers an immediate MILP replan only when the remaining grid-target error after the feasible ESS correction is at least 500 W.
- Keeps the MILP on its normal 10-minute cadence when the fast ESS layer can absorb a disturbance.
- Remains hard-coded shadow mode with no hardware writes; the existing Home Assistant ESS automation remains the real writer.

## 0.25.1
- Clarifies multi-trip EV validation diagnostics by replacing the misleading `outside_window_energy_kwh` field with
  `scheduled_after_deadline_kwh`.
- Adds `charging_during_away_windows_kwh` as a separate validation metric for actual charging while the EV is unavailable.
- No MILP decisions, trip scheduling, task semantics, economic calculations, configuration or hardware-control behavior changes.

## 0.25.0
- Adds a recurring weekly EV trip schedule with configurable weekdays, departure/return times, hard departure SoC and expected
  trip energy.
- Generates every matching hard departure milestone inside the seven-day planning horizon plus one soft terminal preferred-SoC
  target.
- Models EV battery energy explicitly in MILP, including charge efficiency, battery-capacity bounds and expected trip-energy
  withdrawals at departure.
- Prevents EV charging during configured away windows and can keep planning while the car is currently away when the recurring
  schedule provides a matching future return.
- Keeps the legacy single `departure_time_local` policy unchanged when no weekly schedule is configured.
- Adds EV SoC and trip/availability information to task and MILP diagnostics.
- Remains hard-coded shadow mode with no hardware writes and adds no PV-specific charging rules.

## 0.24.2
- Clarifies EV task diagnostics by publishing the hard minimum SoC and the soft preferred SoC separately.
- Publishes preferred AC/battery energy alongside the hard energy-by-deadline requirement.
- Keeps `target_soc_percent` as a compatibility alias and explicitly marks its role as `preferred`.
- No task policy, MILP, configuration-schema or hardware-control behavior changes.

## 0.24.1
- Fixes the v0.24 CI Ruff failure by wrapping the EV minimum-runtime expression to the configured line-length limit.
- No EV policy, MILP, configuration-schema or hardware-control behavior changes.

## 0.24.0
- Splits the EV policy into a hard minimum SoC by departure and a soft preferred SoC target.
- Keeps the existing `target_soc_percent` as the preferred target and adds optional `minimum_soc_percent`; when omitted, the
  minimum defaults to the preferred target so existing installations preserve their current behavior.
- Lets MILP satisfy multiple cumulative EV energy-by-deadline milestones in one seven-day plan.
- Values unmet preferred EV energy at the configured import-energy price, so extra charging is selected only when the full
  economic plan makes it worthwhile rather than by a hard-coded PV or grid rule.
- Allows preferred charging anywhere in the seven-day horizon while hard minimum-energy milestones remain tied to their
  departure deadlines.
- Publishes preferred EV target, scheduled energy, shortfall and shortfall value in the MILP diagnostics.
- Remains hard-coded shadow mode with no hardware writes.

## 0.23.0
- Makes the HiGHS MILP the sole authoritative shadow planner and removes the portfolio/deadline scheduler from planning.
- Uses a 10-minute normal replan cadence with immediate replans for forecast/task/actuator changes, material ESS SoC
  deviation and significant unexpected background-load changes.
- Gives MILP a 30-second total solve budget: the economic stage has first claim on the full budget and the early-value
  tie-break receives whatever wall-clock budget remains.
- Keeps the previous valid MILP plan for at most 30 minutes only after a periodic or forecast-triggered replan failure;
  material task/actuator/state changes fail closed to planner-unavailable instead of invoking another scheduler.
- Generates both ESS and EV generic dry-run requests from the current MILP interval while all hardware writes remain disabled.
- Keeps the seven-day horizon, economic objective, EUR 0.01 tie-break tolerance and three-day early-value half-life.

## 0.22.1
- Warm-starts the second-stage early-value MILP from the complete feasible first-stage economic solution.
- Adds diagnostics showing whether the warm start was accepted and whether the published result came from the economic stage or
  the early-value tie-break stage.
- Keeps the economic objective, EUR 0.01 tolerance, three-day time-preference half-life, validation rules and planner authority
  unchanged.

## 0.22.0
- Adds independent post-solve validation for MILP interval timing, AC balance, ESS SoC/power limits, DC curtailment,
  discrete EV charging states and energy-by-deadline task fulfilment.
- Adds a second MILP pass that keeps the economic objective within EUR 0.01 of the first-stage economic result and then prefers
  earlier realized energy savings using an exponential three-day time-preference half-life.
- Publishes separate first-stage/tie-break solve times, validation results, task fulfilment checks and seven-day cost breakdowns
  for both the existing v0.20 reference plan and the MILP result.
- Marks whether a solved MILP plan is structurally ready for future adoption and whether the existing reference planner would
  need to remain the fallback. The MILP is still non-authoritative in this release.
- Keeps the seven-day horizon, existing tariff model, current task policy and all hardware writes unchanged.

## 0.21.0
- Adds a non-authoritative seven-day MILP evaluation using HiGHS/highspy alongside the existing v0.20 scheduler.
- Jointly models the current EV deadline task, ESS charge/discharge, grid import/export, AC/DC PV allocation, ESS SoC and
  monthly capacity-tariff peak while using the same economic objective as the active shadow planner.
- Keeps discrete EV whole-ampere 1-phase/3-phase operating states and configured ESS power/SoC limits as hard constraints.
- Limits the diagnostic solver to 5 seconds, a 1% relative MIP gap and one CPU thread; it runs at most once every 5 minutes.
- Adds `sensor.energy_manager_milp_status` with solver time, model size, MIP gap and objective comparison against v0.20.
- Keeps the v0.20 portfolio schedule authoritative; MILP results do not generate actuator requests or hardware writes.
- Pins `highspy==1.15.1`, which provides CPython 3.13 musllinux wheels for the Alpine app image.

## 0.20.0
- Extends the internal shadow planning horizon from 48 hours to 7 days while retaining the existing 24 h and 48 h views.
- Changes the economic objective and terminal ESS valuation to use the full 7-day horizon and adds 7-day plan-cost diagnostics.
- Replaces the v0.19 per-increment greedy EV search with a bounded portfolio search whose candidate count does not grow
  proportionally with every 15-minute slot in the horizon.
- Supports multiple additive EV energy-by-deadline tasks in one plan and keeps each requirement inside its own time window.
- Candidate generation uses generic physical schedule variants; the monetary objective still decides which feasible schedule wins.
- Keeps the existing default EV task policy unchanged for now; recurring departures, minimum SoC and preferred SoC are future
  task-generation work rather than hard-coded planner rules.
- Remains hard-coded shadow mode with no real EV or ESS hardware writes.

## 0.19.1
- Fixes the v0.19 CI lint failure by importing `Callable` from `collections.abc` on Python 3.13.
- No optimizer, economics, scheduling, configuration, or hardware-control behavior changes.

## 0.19.0
- Makes the configured economics influence the shadow EV schedule for the first time.
- Scores candidate EV charge allocations in EUR using projected import cost, export revenue and incremental capacity-tariff
  exposure while preserving the EV energy-by-deadline requirement as a hard constraint.
- Adds terminal ESS value to the optimizer objective so a candidate is not rewarded for ending the 48-hour horizon with an
  artificially depleted battery; usable terminal energy is valued at the import cost it can subsequently avoid.
- Uses the existing greedy ESS self-consumption projection when comparing candidate EV schedules; joint ESS optimization is
  intentionally deferred.
- Retains the v0.16 earliest-deadline schedule whenever the economic search cannot improve its objective.
- Extends plan-cost diagnostics with optimizer status, selected and baseline objective values, estimated improvement,
  terminal ESS value and candidate count.
- Remains hard-coded shadow mode: no real EV or ESS hardware writes are added.

## 0.18.2
- Separates tariff effective time from the time a tariff revision is recorded, so backdated tariff profiles can be stored safely.
- Reuses tariff revisions by profile ID instead of assuming the newest database timestamp is the configured profile.
- Adds historical tariff lookup by effective time and preserves later genuine tariff changes.
- Supersedes the earlier activation-time fallback when the same tariff values are corrected with an explicit effective date.
- No planner scheduling, cost-formula, configuration-schema, or hardware-control behavior changes.
## 0.18.1
- Fixes CI lint failures in the v0.18 economic-accounting test suite by keeping module imports at the top of the test module.
- No runtime, planning, configuration, or hardware-control behavior changes.

## 0.18.0
- Adds read-only economic accounting for the existing shadow plan without changing task or ESS scheduling behavior.
- Tracks the current billing month's 15-minute grid-import peak using legacy five-minute history as an estimate and
  higher-resolution live observations for newly completed quarter-hour windows.
- Persists completed live capacity windows in InfluxDB so later restarts can retain the higher-resolution result.
- Adds `sensor.energy_manager_capacity_tariff_status` with observed peak, billing floor, peak source and history quality.
- Adds `sensor.energy_manager_plan_cost_status` with projected import cost, export revenue and incremental capacity-tariff
  exposure for the next 24 and 48 hours.
- Capacity cost is evaluated as the incremental cost above the already-incurred monthly peak/floor, not as a forced peak
  minimization priority.
- Marks plan economics as accounting-only and not yet optimizer-ready because terminal ESS energy value is not modelled.
- No configuration schema changes and no hardware writes. Shadow mode remains mandatory.

## 0.17.1
- Adds an explicit `valid_from_utc` setting to tariff profiles so historical economics use the tariff's real effective date
  instead of merely the time Energy Manager first observed the configuration.
- Includes the effective timestamp in the tariff-profile fingerprint, so changing a tariff's effective date creates a distinct
  immutable historical revision.
- Keeps first activation as a fallback only when no explicit effective timestamp is configured.
- No scheduling or hardware-control behavior changes.

## 0.17.0
- Adds the first planner economics foundation without changing the v0.16.1 shadow scheduling behavior.
- Adds configurable marginal import energy cost, export revenue, capacity-tariff rate and capacity-tariff billing floor.
- Keeps economics disabled until all planner-relevant tariff values are configured; no placeholder prices affect planning.
- Versions each distinct tariff configuration as an immutable profile with a fingerprint and first-activation timestamp.
- Stores tariff revisions in InfluxDB when available and falls back to `/data/tariff_profile_history.jsonl` otherwise.
- Reusing the same tariff across restarts does not create a new revision; changing a tariff value creates a new revision.
- Adds `sensor.energy_manager_economics_status` exposing the active tariff profile and its historical revision ID.
- Does not yet use monetary cost to alter EV/ESS scheduling; this release establishes reproducible historical cost inputs first.
- Remains hard-coded shadow mode with no hardware writes.
## 0.16.1
- Fixes pre-control net-power diagnostics so scheduled task load is included in interval net power, deficit energy and peak deficit.
- Keeps the ESS/grid projection behavior unchanged; it already included scheduled load correctly.
- Adds regression coverage that a feasible EV task is never under-allocated after discrete charger-step quantization, including at 226 V.
- Renames the planner log wording from raw deficit to pre-control deficit to match the corrected metric.
- No configuration schema changes and no hardware writes. Shadow mode remains mandatory.
## 0.16.0
- Adds the first shadow task scheduler: planner tasks can now contribute scheduled load to the 15-minute planning horizon.
- Schedules the current EV energy-by-deadline task from its earliest start using physically feasible whole-ampere 1P/3P
  charging steps; this is a deadline-feasibility baseline, not an economic optimizer.
- Keeps the existing raw background/PV deficit metric unchanged while exposing task energy through `scheduled_load_kwh`.
- The ESS projection now reacts to scheduled EV load, so projected SoC and grid import include the task schedule.
- Does not yet issue EV dry-run commands from the schedule; the existing ESS dry-run plumbing remains unchanged.
- No configuration schema changes and no hardware writes. Shadow mode remains mandatory.
## 0.15.0
- Adds the first generic planner task model while keeping scheduling and hardware control disabled.
- Adds an EV target-by-departure task generated from live connection/SoC state and runtime policy settings.
- The EV task exposes earliest start, departure deadline, target SoC, required battery/AC energy, interruptibility and
  simple max-power feasibility.
- Adds `sensor.energy_manager_task_status` and includes task IDs/status in the shadow planner diagnostics/logs.
- Adds optional EV usable-battery-capacity and charging-efficiency settings; battery capacity must be configured before
  the task can derive an energy requirement.
- Target SoC and local departure time default to 80% and 07:00 and remain runtime configuration rather than planner code.
- The planner receives the task catalog but does not schedule EV charging yet; actuator commands remain dry-run only.
## 0.14.0
- Adds the first generic actuator power-command contract while keeping all hardware writes disabled.
- Planner requests use actuator IDs plus requested power; actuator-specific code translates them into feasible dry-run commands.
- ESS dry-run commands enforce configured charge/discharge power limits and SoC boundaries.
- EV dry-run commands translate requested charging power into feasible whole-ampere 1-phase/3-phase charger states and never exceed the requested power.
- Adds `sensor.energy_manager_actuator_command_status` with requested versus accepted power, limiting reason and EV phase/current details.
- The first shadow-plan interval now passes its ESS request through the actuator command translator as an end-to-end dry-run plumbing check.
- `sensor.energy_manager_actuator_status` now documents the supported command interface for each actuator.
- No Home Assistant service calls or device writes are performed; `control_enabled` and `hardware_writes` remain false.
- No configuration schema changes.
## 0.13.0
- Adds the first generic read-only actuator registry for planner-facing device capabilities.
- Moves the ESS planning envelope behind an ESS actuator snapshot instead of passing ESS configuration directly into the planner.
- Adds an EV actuator snapshot with connection state, SoC, present charging power and configurable 1-phase/3-phase charge limits.
- Adds `sensor.energy_manager_actuator_status` with the actuator catalog, readiness and capability diagnostics.
- The shadow planner now receives a list of actuator snapshots; no EV task is scheduled yet and no actuator can write to hardware.
- Existing ESS projection behavior is retained, but its limits now come from the ESS actuator capability interface.
- New EV capability options are optional; defaults are 6-16 A, 230 V and both 1-phase and 3-phase support.
- Remains hard-coded shadow mode.
## 0.12.0
- Adds the first read-only ESS resource projection to the shadow planner.
- Uses current ESS SoC plus configurable capacity, SoC limits, charge/discharge power limits and efficiencies.
- Separates AC-coupled roof PV from DC-coupled shed PV so shed energy must pass through the ESS/inverter path before serving AC loads.
- Projects 15-minute ESS AC power, battery SoC, post-ESS grid power and DC-PV curtailment without sending any commands.
- Adds `sensor.energy_manager_shadow_plan_next_24_hours_grid_import_energy` and extends the shadow-plan status attributes.
- Keeps the existing raw pre-control deficit sensor for comparison.
- New ESS planning parameters are optional; existing saved configuration remains valid and runtime defaults are used when omitted.
- Remains hard-coded shadow mode; dynamic thermal/BMS capability feedback and cost optimization are not yet applied.
## 0.11.0
- Adds the first read-only shadow planner foundation.
- Aligns the rolling background-load forecast and PV-potential forecast onto one 15-minute timeline.
- Keeps a 48-hour internal horizon and publishes compact 24/48-hour summaries plus the next three hours of intervals.
- Reports background energy, PV potential, pre-control net deficit/surplus and peak net deficit.
- Adds `sensor.energy_manager_shadow_plan_status` and
  `sensor.energy_manager_shadow_plan_next_24_hours_net_deficit_energy`.
- Leaves `scheduled_load_w` at zero for now so EV/laundry/task scheduling can be added without changing the plan shape.
- Does not yet schedule the ESS or EV and does not claim grid export from DC-coupled shed surplus; surplus is reported as
  available energy before storage/control.
- No configuration schema changes and no device control.
## 0.10.2
- Scores all candidate load models on the same common set of valid forecast intervals for each horizon.
- Keeps one accuracy score set; no duplicate native/common model scores are exposed.
- Keeps `coverage` and `issue_coverage` as separate availability diagnostics for each model.
- Leaves the production background-load predictor unchanged.
- No configuration schema changes and no actuator/control changes.
## 0.10.1
- Makes horizon energy accuracy the primary background-load backtest criterion instead of pointwise wattage MAE.
- Adds mean absolute total-energy error, signed energy bias and integrated absolute timing mismatch in kWh.
- Adds mean and p90 15-minute peak-load underprediction diagnostics for capacity-tariff risk.
- Keeps wattage MAE, bias and p90 error as secondary shape diagnostics and reports the best power model separately.
- Changes `sensor.energy_manager_background_load_backtest` to expose the current model's 24-hour total-energy MAE in kWh.
- Stores the new runtime evaluation metrics in InfluxDB under the existing `background_load_backtest` measurement.
- Leaves the production background-load predictor unchanged and does not add any compile-time household-specific corrections.
- No configuration schema changes and no actuator/control changes.
## 0.10.0
- Added a runtime rolling-origin backtest for the background-load predictor; no household-specific correction constants are compiled into the application.
- Evaluates the current EnergyManager model against three simple baselines: persistence, same time yesterday and same time last week.
- Measures 1 h, 3 h, 6 h, 12 h and 24 h forecast MAE, bias, p90 absolute error, energy MAE and coverage.
- Adds current-model error breakdowns for night/morning/afternoon/evening and weekday/weekend to identify where separate models or inputs may be useful.
- Uses only data that would have been available at each historical forecast issue time, avoiding look-ahead leakage.
- Runs the evaluation at runtime from the current InfluxDB-backed history and refreshes at most once per 24 hours.
- Stores backtest summaries in InfluxDB and exposes `sensor.energy_manager_background_load_backtest` for inspection.
- Leaves the production background-load predictor unchanged; v0.10 is an evaluation release intended to guide later runtime-learning model improvements.
- No configuration schema changes and no actuator/control changes.
## 0.9.3
- Treats stale EV charging-power history as 0 W after the existing 15-minute freshness window, instead of dropping the entire background-load sample.
- Keeps the stricter stale-value rules for grid, ESS and PV sources so sensor outages are not silently stretched into fake historical power.
- Uses a new derived-history recipe ID so the full archived source range is rebuilt automatically without re-importing the legacy source rows.
- Writes the corrected reconstruction to `legacy_house_load_v2`; the predictor prefers v2 over the v0.9.2 legacy table and still prefers live `house_load` data over both.
- No configuration schema changes and no actuator/control changes.
## 0.9.2
- Rebuilds legacy house/background history on a complete five-minute timeline instead of requiring every source to have written in the same bucket.
- Carries recent historical source values forward for up to 15 minutes to bridge normal sparse Home Assistant state updates.
- Treats stale values within ±50 W as inactive and resolves them to 0 W, allowing long zero periods such as PV at night, no export, idle ESS and an unplugged/idle EV to remain reconstructable.
- Refuses to carry stale material non-zero values beyond 15 minutes so historical sensor outages are not silently converted into fake load.
- Seeds each 14-day reconstruction chunk with the latest prior archived source state, so chunk boundaries do not create artificial gaps.
- Uses a new derived-history recipe ID and writes the rebuilt history to `legacy_house_load`, leaving live `house_load` data append-only and avoiding duplicate-point overwrites.
- The predictor merges reconstructed legacy and live background history by timestamp, preferring live samples when both exist.
- No configuration schema changes and no actuator/control changes.
## 0.9.1
- Added optional username/password authentication for the legacy InfluxDB 1.x backfill source.
- Uses HTTP Basic authentication when legacy credentials are configured.
- Keeps unauthenticated legacy sources supported by leaving both credential fields empty.
- No changes to EnergyManager InfluxDB 3 persistence or backfill data semantics.
## 0.9.0
- Added incremental historical backfill from the legacy Home Assistant InfluxDB 1.x database into EnergyManager's InfluxDB 3 database.
- Reuses configured Grid, ESS, Solax PV and EV charging entity mappings; source entity IDs are never hardcoded.
- Archives only signals EnergyManager currently uses, as normalized five-minute source history in `legacy_power_source`.
- Tracks imported coverage per logical signal + entity mapping instead of using one global migration-complete flag.
- New configured/modelled signals can therefore be backfilled later without re-importing the whole Home Assistant database.
- If the old source database gains newer data, only the missing tail is imported on the next synchronization.
- Derived house/background history has its own recipe/source fingerprint and coverage state, so future model changes can rebuild only the relevant derived history.
- Reports source and derived backfill progress through `sensor.energy_manager_database_status`.
- Corrected the baseline predictor's active history window to the documented 35 days; database retention remains indefinite.
- Backfill failure is non-fatal; normal InfluxDB 3 persistence and EnergyManager operation continue with existing history.
- Remains shadow mode; no device control is present.
## 0.8.0
- Added optional InfluxDB 3 persistence using a restricted database read/write token.
- Added `sensor.energy_manager_database_status` for connection and migration health.
- Background-load samples now persist indefinitely in InfluxDB while the current baseline model keeps a 35-day active training window.
- PV rolling forecast revisions and background-load forecast revisions are stored in InfluxDB instead of JSONL when enabled.
- Existing v0.5/v0.7 JSONL persistence files are imported once and renamed with a `.migrated` suffix after successful migration.
- Database failure is non-fatal: Energy Manager reports the database error and falls back to the existing local JSONL persistence.
- Includes the complete v0.7 background-load predictor for users upgrading directly from v0.6.
- Remains shadow mode; no device control is present.
## 0.7.0
- Added persistent sampling of canonical background-load power every five minutes.
- Added a 15-minute rolling background-load forecast for the future planner.
- The baseline model learns robust time-of-day patterns, then weekday/weekend and same-weekday behavior as history grows.
- Added next-hour power, next-24-hours energy and next-seven-days energy diagnostics.
- Added independent predictor status with learning progress and retained-history metadata.
- Added `/data/background_load_history.jsonl` with 35-day retention and compact forecast revision history.
- No configuration schema changes; the predictor uses the v0.6 canonical background-load signal.
- Remains shadow mode; no device control is present.
## 0.6.0
- Added canonical instantaneous AC house-load power derived from grid net power, Solax AC PV and normalized ESS AC power.
- Explicitly excludes the DC-coupled shed MPPT from the house-load balance so shed PV is not double-counted.
- Added known controllable-load power; v0.6 starts with measured EV charging power.
- Added background-load power as house load minus known controllable loads.
- Added Home Assistant diagnostics for house load, controllable load and background load.
- No configuration schema changes; existing v0.5.1 entity mappings are reused.
- Remains shadow mode; no device control is present.
## 0.5.1
- Clamp small negative EV charging-power readings between -100 W and 0 W to zero.
- Keep larger negative EV charging-power readings invalid so a real sign/configuration problem is still visible.
- No configuration schema changes.
- Remains shadow mode; no device control is present.
## 0.5.0
- Replaced the fixed 20:15 day-ahead snapshot workflow with a continuously refreshed rolling forecast.
- Extended the PV horizon to today plus seven full future calendar days.
- Switched Open-Meteo to `knmi_seamless`, using KNMI HARMONIE AROME in the near term and ECMWF beyond it.
- Added `sensor.energy_manager_pv_forecast_next_7_days_energy` with per-day front/rear/shed breakdowns.
- Added append-only `/data/pv_forecast_revisions.jsonl` history with each 30-minute forecast revision and daily totals.
- Removed the two fixed day-ahead diagnostic entities; v0.5 cleans their stale Home Assistant states on startup.
- Kept the existing today, tomorrow and next-hour live forecast diagnostics.
- No configuration schema changes; existing v0.4.1 options remain valid.
- Remains shadow mode; no device control is present.
## 0.4.1
- Fixed Python 3.13/Ruff import placement for `Mapping`.
- Re-published the v0.4 predictor release under 0.4.1 after the 0.4.0 CI failure.
- No intended functional changes from v0.4.0.
## 0.4.0
- Added the first Python predictor: a four-plane Open-Meteo PV forecast.
- Migrated the existing three-plane physical PV calculation into the app and added the 6.18 kWp shed plane.
- Added separate front/rear group calibration seeded from August-October 2026 production history.
- Added time-of-day shading correction and conservative rear seasonal interpolation without extrapolating past observed data.
- Added direct/diffuse radiation and cloud-cover forecast inputs for later calibration work.
- Added persistent day-ahead PV snapshots after 20:15 local time.
- Added PV forecast status, daily-energy, day-ahead and next-hour diagnostic entities.
- Added an optional `pv.forecast_enabled` runtime setting; existing entity mappings remain valid.
- Added Docker build-time imports for core/predictor modules to catch missing source files before publication.
- Remains shadow mode; no device control is present.
## 0.3.1
- Re-published the v0.3 house-state release after missing source files were added to the repository.
- No intended functional changes from v0.3.0.
## 0.3.0
- Added grouped runtime configuration for Grid, ESS, PV and EV inputs.
- Added a normalized internal House State with per-input validity, observation time and source metadata.
- Added ESS SoC/power, separate PV powers, EV SoC/connection/charging-power inputs.
- Added canonical ESS sign handling: positive discharge, negative charge.
- Added total-PV and aggregate input-health diagnostics.
- Added periodic 30-second input reconciliation alongside event-driven WebSocket updates.
- Added automatic migration of the v0.2 flat grid configuration to the grouped v0.3 format.
- Removes the obsolete v0.1 `sensor.energy_manager_observed_grid_power` state on startup.
- Remains read-only; no device control is present.
## 0.2.0
- Replaced the single grid-power input with separate momentary import and export entities.
- Added canonical net grid power (`import - export`), with positive values meaning import and negative values meaning export.
- Added separate normalized import/export diagnostic sensors.
- Added degraded-state handling: invalid or unavailable input never silently falls back to zero.
- Generalized the Home Assistant WebSocket observer to subscribe to multiple entities on one connection.
- Rejects non-finite power values and negative values from the separate import/export inputs.
- Updated GitHub Actions to current Node 24/ESM action generations.
- Remains read-only; no device control is present.
## 0.1.0
- Initial Home Assistant app skeleton.
- Internal Home Assistant REST API access through the Supervisor proxy.
- Home Assistant WebSocket state subscription for one configured grid-power entity.
- Read-only shadow-mode diagnostics.
- Automatic reconnect with bounded exponential backoff.
- CI and GHCR publishing workflows.
