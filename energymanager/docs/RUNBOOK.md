# Run, configure, review and roll back

## Shared EV-progress warnings and grid projection (4.6.8 / EV-A009)

Overview/Planning shows one current warning for a common progress-source fault.
Its action distinguishes an unmapped/unavailable eto sensor, a stalled counter and
post-trip vehicle reconciliation. Expand Affected goals to see current titles and
deadlines, including the dates of recurring daily goals, and the actual source evidence.
Native source actions open that mapped HA entity; standalone explains availability.

Restoring the source clears the operational warning without waiting for a replan.
Previously blocked goal results remain unavailable and show Awaiting recalculation;
recovery does not assert that a requirement is fulfilled. Other shortfalls, approvals,
planning failures and margin warnings remain separate. Notification policy is unchanged.

The Grid box retains its measured quarter value, including0W. The red quarter-end
marker and monthly forecast can remain available when EV progress/authority is lost
if the accepted full household/ESS instructions are independently usable. Revoked or
uncovered resource instructions withhold their whole interval; no EV/ESS flow is
silently removed from the joint balance. Handover follows prior complete instructions;
cautious execution uses its audited coverage. Uncertain controlled-appliance timing
also withholds affected predictions, while known idle remains household demand.
The existing availability hint explains missing predictions; measurement/history stay.
No live-load extrapolation fallback, control or peak policy is introduced.

Offline source-loss/recovery preview:
`python tools/offline_e2e.py --serve --routing-fixture --history-fixture --input-fault progress`.
Its local-only `/synthetic/progress` POST fixture toggles fake counter availability;
this endpoint exists only in that verification process, not the installed app.
Native preview uses `tools/native_dashboard_preview.py`. All data/actions are synthetic.

## Manual recorder readiness (4.6.7 / V45-A003)

Expand the washing machine (or an available manual recorder), select the program and
choose Record next cycle. Directly beneath it, Waiting for idle shows the armed program
and latest watts. Before the first successful read, power is explicitly unavailable.
Ready to record / Idle detected — start the machine confirms idle has actually been
observed. Starting the machine then changes the indicator to Recording with measured
power. Changing the selector does not change the already armed capture's identity.

Unavailable reads/status or evidence older than the existing15second gap withdraw
Ready; an unavailable value is never0W. After recorder restart, new idle evidence is
required. Available unchanged HA sensor states remain valid. Existing five-second
sampling, thresholds, idle completion and recording review rules remain unchanged.
The indicator appears only in the expanded recording form; Bosch automatic feedback
remains separate. Name, notes and open trim drafts survive live status updates.

Offline checks use deterministic local/fake endpoints and isolated synthetic stores;
no installation commissioning or remote machine start is implied by readiness.

## EV stock after driving (4.6.9 / EV-A008 follow-up)

If reported SoC is below retained estimated charge after driving, inspect Progress
sources. A charging counter proves added energy, not remaining stock after an absence.
Every observed return requires new vehicle stock evidence, whether or not a trip was
registered. An unchanged old reading and a moving charger counter cannot resolve it.
A changed lower valid SoC with a usable eto counter rebases stock once; timing stays
unknown when the source supplies no physical timestamp. Uncertain overlap is omitted,
and only subsequent delivery is credited to the corrected stock. The existing
uncertainty indicator remains visible. Without usable evidence, reconcile the source;
do not reset the ledger or mark the requirement fulfilled. EV authority is revoked
for recalculation when the stock baseline changes; ESS remains independent.

This changes stock accounting only. Existing charger faults and permissions still
apply; restarting/retrying hardware is not part of this recovery policy.

## EV progress and execution (4.6.6 / EV-A008)

Map the actual go-e Total energy (`eto`) sensor under Measurements, save and restart;
see SETTINGS.md for units, timestamp and reconciliation rules. Reload the dashboard.
The EV page separates reported vehicle SoC from estimated counter progress. Progress
sources shows the actual sample/read times and credited battery gain. An unavailable
progress warning pauses only EV; check the mapped counter's availability/units and
whether it advances while charging. Do not reset the retained reference to make a
warning disappear. An ordinary reconnect does not erase progress.

New calculations freeze the remaining accepted instructions and actual charger
transition state. Admission can hand over those instructions explicitly without
rewriting the calculation's frozen source or economics. Phase preparation may occur
with force-off and zero current; charge is requested only under the live guards.
A submitted phase write remains tracked until fresh acknowledgement or fault.
New phase changes reserve existing stop/acknowledgement/restart time in the model;
this bound is not a measurement of installation latency. Actual delivered energy
comes from the counter. No new phase lock/dwell or enlarged peak/solve allowance is used.

Offline regression entry points are `tests/test_ev_progress.py`,
`tests/test_ev_progress_loop.py`, `tests/test_execution.py` and
`tests/test_execution_charger.py`. Use only their labelled synthetic counters and
fake endpoints. Archived exports remain unchanged evidence; replaying them does not
establish what hardware did throughout an earlier hour. Installation validation and
deployment require separate authorization.

## Monthly peak forecast and quarter meter (4.6.4 / EV-A006–EV-A007)

Reload the dashboard after updating. The Grid box keeps its monthly-peak icon/value
at the bottom and adds the current-quarter meter immediately to its right, marked
with a red clock icon. This is imported energy divided by the full0.25-hour quarter,
not instantaneous power, an elapsed-time average or the projected final average.
A stale, failed or previous-quarter read shows unavailable; a valid zero shows0W.
Native monthly-peak and quarter icon/value actions open their actual mapped HA
sensors. The quarter history uses the input entity and its native units, even when
the dashboard normalizes that value to watts. Enter/Space also open history.

Overview keeps recorded monthly-peak history and extends it with a faded forecast
after Now. Grid and peak share red; the peak uses heavier long dashes (3px,17/9px). The forecast
uses the accepted plan's imported energy by quarter, includes the current measured
prefix and remaining partial intervals, and resets at installation-local month start.
It is not an approval limit. Missing/expired/revoked plans or missing meter/peak inputs
are identified in the legend; no missing history is fabricated.

Subtle alternating backgrounds mark clock quarters; the active quarter is highlighted.
A hollow red mark at its end shows the projected final average. Point at the active
quarter or focus the graph and use arrow keys for a compact Actual/Planned table.
Measured cells open their genuine source history in native HA; planned cells remain
plain values. The verbose quarter contribution/time paragraph is removed. Drag,
wheel/pinch zoom and two-finger pan preserve those time alignments. Historical ranges
show only recorded peak values and do not acquire a current-quarter marker.

Across the native dashboard, individual live readings, actual daily totals and
Bosch feedback open their configured sensor. Composite household/grid/solar values
offer genuine contributing sources, matching the configured measurement mode.
Recording reviews and averages open captured source sensors. Forecasts and controller
requests are distinct. Standalone/demo/unmapped sources show an availability hint
instead of a history button.

Offline verification uses `python tools/offline_e2e.py --serve --history-fixture --profiles-fixture`
and `python tools/native_dashboard_preview.py`. Both are synthetic/local; actual
HA Recorder, meter timing, mobile hardware and installation performance remain
unverified. Control, permission and peak-notification policy is unchanged.

## Washing-machine program names (4.6.5 / V45-A001-P1/P2)

After updating, reload either dashboard and expand Washing machine. Beside the recording
program selector, + adds a program and the pencil renames the selected program. The name
field replaces that selector; check/Enter saves and x/Escape cancels without changing
metadata. Record next cycle is unavailable during name editing. Save errors keep the
typed name; Cancel restores the selector, and reopening starts from current metadata.

Creation selects the saved program immediately for Record next cycle and adds an empty
foldable group; recording still requires the mapped washer power sensor. Rename keeps
the ID, recordings, average contributors and raw measurements. Name actions preserve
unsaved recording notes and open review/trim drafts, updating the current review title.

Names must be1–80 printable characters. Whitespace is normalized and equivalent names
are rejected without changing the catalogue. Concurrent edited drafts are rejected with
a reload message; they are not silently overwritten. Names persist across reload/restart
and demo/configured catalogues remain separate. Bosch has no manual Add/Rename controls.
Metadata edits do not operate an appliance. Program removal, adding appliances and washer
scheduling/control are not part of this release. All verification used local fake data;
no live installation/database access, appliance operation or deployment was performed.

## EV continuity, peak protection and deadline margin (4.6.1)

Reload the dashboard after updating. A running EV task continues to its own energy
endpoint while source, peak and safety guards permit it; getting ahead of the
forecast does not pause charging. Recalculation continues using the accepted task.
A replacement may interrupt for a real benefit; near-term stop/restart alternatives
are checked within the frozen calculation. Delayed delivery retains the original
quantity, never a later goal's authority.

Live peak protection retains the measured quarter prefix, sustains measured load
and allows for unconfirmed actuator response. EV current is cut first; residual
risk may use ESS energy reserved for a later forecast peak. The existing read
watchdog supplies a conservative response allowance; actual device and meter
latencies still require installation verification. A household-only unavoidable
remainder is labelled in command evidence. EV-A002 measured-peak alerts remain active.

Economic planning uses the full PV forecast. The next known EV deadline also gets
an independently audited fallback using80% of future usable PV, initial eligible
stock at full credit, availability and existing peak authority. Its activation and
progress checks are precomputed; fast control does not optimize. A timeout is
unverified and preserves an eligible previously checked fallback. Decision evidence
contains `deadline_guard` with explicit contexts, source ledgers, attempts and scope;
`deadline_fallback_activated` and command `peak_protection` link actual activation,
plan identity, task target and quarter projection. No higher peak is purchased by
this safeguard.

When only the cautious case is proved infeasible, Overview retains a persistent
PV safety margin warning and the configured phone receives one notice per goal/
deadline. Failed delivery retries across restart; repeated forecasts do not repeat
a successful notice. Restored margin, fulfilment or removal clears the warning.
Nominal shortfalls continue through existing approval controls. Without a phone,
the warning and local notice remain available.

Offline only, from `energymanager/`:

```powershell
python tools/offline_e2e.py --serve --deadline-margin-fixture
python tools/native_dashboard_preview.py
# Separate terminal, private archived or labelled synthetic snapshot:
python tools/verify_ev_replay.py PATH_TO_SNAPSHOT --output artifacts/ev-replay.json --budget 120
```

The warning fixture is explicitly synthetic display evidence, not an infeasibility
proof. Verify the same warning and delivery state in standalone/native Overview,
with no Approve/Reject buttons on that warning. The replay tool performs a fresh
calculation and independent physical/rolling/certificate audits, retains raw stage
statuses and writes a compact `.report.json`. `--matched BASELINE_OUTPUT` conditions
both searches on common final EV/direct-grid quantities and a shared reference/
financial allowance. Run comparisons serially without other solver workers; report
energy, bill, comparison cost, peak and starts together. These are bounded incumbents,
not proofs of global optimality. Use fake endpoints and isolated databases only.

## Measured peak alerts and history (4.6.0 / EV-A002)

Use the existing mapped monthly-peak sensor and configured phone notification
destination. The first valid read initializes the baseline. Later billable rises
above the 2.5 kW floor alert immediately, including household-only peaks. Further
rises stay silent until there have been 15 minutes without an increase. Restart
retains the baseline, quiet-period state and pending delivery retries. No final
summary is sent. Advance peak approval remains a separate interaction. Without a
phone destination, the existing local-notice behavior applies.

Overview shows recorded monthly-peak steps with red long dashes. The cursor reports
Monthly peak (15 min); the Current month peak label identifies the current reading.
History uses the application's existing measurement archive, without importing HA
Recorder data. Missing data and overfull coarse buckets remain blank; zoom in for
more detail. Synthetic demo readings cannot send measured-peak alerts.

V4.6 incorporates4.5.8. Release publication does not deploy to the installation.

## Recording library and trims (4.5.8 / ARCH-018)

Expand an appliance, then a program. Folded program headers retain recording count,
included count and mean duration/energy. Select a dated recording row to open its original
graph and trim form in that same entry; opening another closes the previous editor.
Details and Delete recording remain directly accessible in the row. All stored records
remain browsable, including older contributors. Inspect average lists its contributors.

Drag the original Start/End grips or edit seconds; both stay linked. Arrow keys adjust
a focused grip. Cursor, zoom/pan, Full recording and Show selection are unchanged. Review
the complete selection and save. Saving retains the ID and original raw measurements;
repeated saves do not create entries or versions. A saved excluded recording remains
excluded until Add to average; initial review still adds the new cycle. Stale edits are
rejected rather than overwriting another view's selection. Reopen to load current bounds.

First startup consolidates historical trim copies by capture provenance, keeping the latest
saved trim even if an older copy was included. Each included capture contributes once;
excluded captures stay excluded. Original capture dates/notes do not identify duplicates.
Raw readings are retained and old IDs resolve to the surviving recording. The migration
is atomic/idempotent; contradictory evidence fails without partial consolidation. Follow
normal database backup/rollback practice before an installation upgrade. Frozen accepted
plans are not rewritten; queued M2 runs replan after contributor edits. No live installation
operation or deployment was performed for this release.

## Bosch managed runs (4.5.7 / V45-A002-M2)

Configure the existing Bosch mappings and collect/review at least one complete program
recording first. Load the dishwasher, select the program and wait for feedback, clear
any native appliance delay, then choose a latest finish and Ready. Tomorrow12:00/18:00
are shortcuts; Custom offers today through seven days ahead and hour/minute wheels.
No deadline is preselected. An impossible deadline displays the earliest estimated
finish; Ready with that unchanged warning authorizes ASAP. Ready alone does not enable
hardware authority. Start now and record remains the immediate manual alternative.

The queue survives restarts. Opening the door blocks starting; closing with remote
permissions restores eligibility without Ready again. A changed selected program keeps
the deadline and uses its reviewed profile, or waits explicitly if none exists. Before
execution you may edit/cancel. Pending peak conflicts offer a later allowed finish or
an explicitly approved on-time peak when the solver establishes those alternatives;
the request remains queued and the configured phone is notified. No option is invented
when a bounded search cannot establish it. Original feasibility can resume automatically.
Once Start is submitted cancellation cannot stop the appliance. Check ambiguous outcomes
at the appliance before cancelling and creating a replacement request; no automatic replay.

Forecasting now needs matched dishwasher/household evidence, initially at least one
supported hour and13 five-minute observations within the last seven days. Existing
retained measured traces can qualify; a new week is unnecessary. Coverage/gaps and
insufficient data remain visible in forecast status. Standby is subtracted from the
background estimate and included once outside the scheduled curve. First-seen-running
or beyond-profile demand remains unknown. Hardware, real phone delivery and installation
performance are live-unverified; all release evidence uses local fake endpoints.

## Bosch idle start correction (4.5.6 / V45-Q017)

Update to4.5.6 and reload the dashboard. A successful HA read can report unknown current
active program while exposing valid startable program options; this now permits the
explicit Start now and record action when the selected program matches and the normal
idle/power, door, remote, delay, meter and hardware-authority guards pass. No mapping
change is required for an already correct setup. Unavailable entities, failed reads,
malformed capabilities or missing requested programs remain blocked. Current active
program stays unknown until actual feedback arrives; submission alone does not start
a recording or confirm execution. This repair was verified only with local fake HA.

## Bosch cards and profile collection (4.5.5 / V45-A002-M1)

Reload the dashboard after updating. Appliances shows Bosch dishwasher, washing machine
and Mazak cards; Expand opens that card in place and collapses the previous one. The
expanded card contains settings, profiles and recordings. Existing stored data is retained.

In the dishwasher card load HA entities, map its dedicated Refoss W/kW sensor under
Recording settings, then map Bosch HA entities. Selected program and Active program
must be different select entities: selection alone does not start; active-program
selection does. Supply operation feedback for automatic capture. Remote permissions,
door, appliance power and native-delay mappings are needed for the corresponding manual
actions. No installation entity IDs are prefilled. These settings persist immediately.

Automatic recording works with hardware control off and the browser closed, including
panel/app starts. It starts from actual run feedback and finishes from finished feedback,
not low power. First-seen-running, missing operation, restarted or interrupted captures
are labelled incomplete. Review/trim and confirm a complete measured cycle before adding
it to that exact HA program's average. Check modifier information during review. Legacy
Eco/Heavy evidence remains separate; do not assume Heavy is Intensive.

Manual Bosch commands require enabled hardware control and fresh appliance guards.
Use Power on if needed, choose Select program and await feedback, then Start now and
record. Start requires idle/on, a closed door, both remote permissions, usable meter and
zero native delay in seconds. Clear an existing native delay yourself; M1 does not manage
it. Submitted is not Running: the card reports pending, confirmed or unconfirmed/failed
feedback. There is no automatic command retry or scheduled start. Modifiers are explicit
idle-state actions and do not adjust a planning curve. Ending collection does not stop
the physical dishwasher. Ready/deadlines and managed optimization belong to M2.

Delete recording… opens the irreversible deletion warning; Confirm permanent deletion
removes exactly that recording, all its samples and its contribution. Remove from average
retains data. Other trim revisions keep their independent samples. Back up the database
before an installation upgrade or intentional deletion as appropriate. No live installation
access, hardware operation or deployment was performed for this release.

The local --profiles-fixture preview includes labelled legacy recordings, two synthetic
HA program identities, automatic Bosch examples and fake manual actions. A fake Start
runs a60second synthetic trace and finishes through feedback; no real hardware is involved.
Use the existing offline/native preview commands with an unused localhost port.

## Saved recording trims (4.5.4)

Update the add-on and reload HA. Inspect / review works on saved recordings too.
Drag the labelled Start/End grips, edit the seconds, or use a focused grip's arrow keys.
The grips are44CSSpx square and remain above the power-inspection tooltip.
Reconfirm the complete range and choose Save revised trim. The earlier recording and
its samples remain available; the new version replaces its contribution to the average.
Use Add to average on an earlier trim to restore it; only one trim per captured cycle
can contribute. Saving/revising does not run the appliance again.


## Appliance graph review and averages (4.5.3)

Update the add-on and reload HA. Inspect a recording: hover/tap or use arrow keys on the
graph for timestamp, elapsed seconds and W. Drag the coloured start/end handles to trim;
their fields update continuously. Editing valid seconds moves the handles. Reconfirm
the complete cycle after changing bounds, then Save and add to average. Unknown gaps
remain visible and still prevent accepting incomplete coverage.

Drag the graph to pan, wheel/pinch to zoom, or use two fingers to pan. The recording
window stays within the captured data. Full recording and Show selection restore useful
views. Keyboard arrows move a focused handle (Shift:10seconds). Averaged profiles →
Inspect average shows the equal-weight curve and included recordings. Add/remove saved
recordings without deleting their raw samples. Mean duration and longest graph duration
are distinct; completed cycles contribute zero to the shared tail.

The labelled --profiles-fixture preview now includes two accepted cycles, one complete
review and one gapped review. No installation data or appliance operation is involved.


## P1 daily grid totals (4.5.2)

After updating, open Settings → Measurements, select P1 cumulative import energy and
P1 cumulative export energy, Save and restart. Use the two combined Cumulative Active
Import/Export sensors. Reload HA. Confirm the Overview grid totals and their source
tooltips. The selected sensors must have HA recorder history at local midnight.
Missing history is explicit; it is never replaced by a first post-start reading or a
power integral. A saved baseline survives app restart; a new day gets its own baseline.
No sensor IDs are assumed and no live installation verification has been performed.


## Planned task power (4.5.1)

Update the add-on and reload HA; no configuration is needed. Open a scheduled EV/ESS
session for its calculated power graph. Requirement details show shared EV power before
the saved deadline. Expand Power levels for exact times/W; offsets distinguish repeated
local hours. Missing/outdated plans are labelled, and ESS direct DC charging is separate
from signed AC flow. The graph is planned power, not a measured trace or a new command.

## Appliance profiles (4.5.0)

Open Appliances, load HA power sensors and map a dedicated W/kW sensor per machine.
Set the idle/start threshold above that machine's standby demand, and choose an idle
timeout longer than its quiet wash/drying phases. Defaults 10 W / 15 min are provisional.
Select a program, optionally describe load/options and choose Record next cycle. Wait
until the recorder reports waiting for start, then run the machine normally. Recording
continues with the dashboard closed. The timer finishes after continuous idle; renewed
activity and missing reads reset it. Finish now is available for explicit completion.
Review the graph, trim start/end in seconds, preview the statistics and confirm that
the selected range is a complete cycle before Save and add to average. Missing coverage
or interrupted recordings cannot be selected. Keep several runs to compare variability;
add or remove reviewed cycles from the average without deleting the originals.
Mazak averages are editable on the same page. This milestone does not schedule/start
machines or subtract them from household forecasts. No installation collection was run.

Use clearly labelled synthetic data for offline UI verification. From energymanager/,
set PYTHONPATH to this worktree's src when reusing another checkout's interpreter:
`python tools/offline_e2e.py --serve --profiles-fixture --port 8105`, then
`python tools/native_dashboard_preview.py --backend http://127.0.0.1:8105/ --port 8106`.
The fixtures expose only fake HA and local endpoints, with two saved cycles,
one complete review and one gapped review. Keep this separate from installation configuration/data.


Update the add-on and reload Home Assistant. The existing native dashboard loader adds
the Appliances tab; no dashboard YAML copying or sensor assumptions are required.
The database migration is additive. Existing settings/goals/accepted-plan/control state
are retained, and the new optional sensor mappings start empty. Configure them when
ready to collect a real cycle. Back up configuration/database before updating as usual;
an older4.4.x version leaves the additional tables/profile-state keys unused.


## Charging continuity (4.4.17)

No settings migration is needed. Fixed-profile `packed_relaxed`/`consolidated_relaxed`
attempts are fast source candidates; restoring indicators changes no physical powers.
Only original integer/model and independent audit checks permit adoption.
`warm_from_relaxation` marks a solver hint, never unchecked adoption. A relaxation
status alone proves no executable/global optimum; full integer alternatives remain.
 Smoothing preserves other EV work/selected energy and
required readiness while allowing source/ESS dispatch to redistribute across all seven
days. Original limits, source provenance, peak permissions and rolling checks remain;
one shared0.02EUR cash/comparison allowance spans all windows/retries. Small household
import differences can be legal. Existing ESS stock values and exact window imports are
not extra requirements. Live control and rescheduling behavior are unchanged.

Decision downloads include `continuity_review`. `coverage_complete` accounts for every
interval; `unresolved_windows` and `complete` describe remaining work. A failed shortcut
cannot overwrite a broader timeout. `had_timeouts`, raw attempt statuses/revisions and
`improvement_retained` remain available. A valid current broad Optimal result provides
only bounded completion; a stale result requires rechecking. `candidate_infeasible`
alone is not proof that gaps are necessary or that review finished. Unfinished smoothing
keeps the valid schedule usable and sends no new warning or notification.

## Energy direction arrows (4.4.14)

Update/reload the add-on for consistent summary markers: → means grid import/ESS charge;
← means grid export/ESS discharge. No settings migration is needed. Numbers, signs,
energy accounting, planning and control are unchanged.

## Reliable solar capture (4.4.13)

Update/reload the add-on; no setting or sensor migration is required. The planner now
tries checked solar allocation candidates before its full optional search and reserves
refinement time before certification. Export means incoming solar, not stored ESS energy.
The existing forecast horizon, normal80% ceiling, exceptional health proof, periodic
recalculation and live control remain. Time limit reached can accompany a valid checked
candidate; retained_starting_candidate in the raw stage diagnostics explains fallback.
Optimal on a restricted solar/source stage does not prove global economic optimality.
All final publication checks remain on the original snapshot.

## ESS display direction (4.4.12)

Update/reload the add-on for positive charging and negative discharge on dashboard ESS
AC readings and charts, including recorded history. No sensor remapping or settings
migration is required. The ESS input remains positive for discharge. Its display is AC
converter exchange; direct DC solar charging is separate, so AC sign alone cannot always
predict net battery SoC direction. Planner, live control and original evidence are unchanged.

## Saved-schedule startup recovery (4.4.11)

Update/reload the add-on; no new setting is required. Shutdown still stops EV charging
and clears the ESS setpoint. Startup automatically resumes a compatible saved schedule
after fresh measurements/charger readbacks and the persisted hardware-On request are
verified; it can run while the new optimizer is still calculating. Normal guards and
phase/restart holds remain. Existing plans from earlier releases require one fresh
4.4.11 calculation before subsequent restarts can recover quickly. Changed settings,
goals, permissions, faults, stale/expired/corrupt history or missed travel require a new
plan. plan_recovery in API state and archived events records the result/reason. A rejected
startup candidate cannot reactivate after a structural invalidation or explicit Off.
The archived calculation and economics remain unchanged. See ARCH-021 for the separately
deferred uninterrupted-update behavior; this release does not remove the shutdown stop.

## EV waiting and vehicle status (4.4.10)

Persistent blocked charging requests now escalate after2minutes instead of15; confirmed
non-delivery still uses90seconds. Actual delivery clears the blocked timer. To add Ford
vehicle faults, select the optional Vehicle charging state sensor under EV fault recovery,
save and restart. A reported FAULT stops/latches without charger reboot and must clear
before acknowledgement. Missing optional telemetry does not replace the measured-power
watchdog or go-e guards. Reported state/selected attributes are preserved in incident
evidence with HA timestamps; physical cloud-telemetry age remains unknown. No vehicle
entity is selected automatically. Update/reload the add-on to receive4.4.10.

## Required charging timing (4.4.9)

Required grid charging now prefers earlier delivery after cost/continuity selection when
waiting offers no benefit. Useful PV waiting and existing cost, peak, health, availability,
hold, source and permission constraints remain. A solver timeout retains a checked earlier
incumbent; its timing status is not a global economic optimality claim. No settings or
sensor migration is required. Update/reload the add-on to receive the planner change.
Snapshot planning, periodic recalculation and live EV/ESS control remain unchanged.

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
[maintained architecture](ARCHITECTURE.md#snapshot-planning-and-live-execution--accepted-28-october-2026).

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
