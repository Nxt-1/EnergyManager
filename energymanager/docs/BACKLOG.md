# Deferred work

Architecture discussion backlog. These entries record future work, not permission to implement or run experiments in this chat.

## ARCH-001 — Forecast accuracy by lead time and usefulness of the seven-day horizon

Recorded: 22 October 2026. Status: **deferred to a later release**, explicitly requested by the user.

Question: how does forecast accuracy change with days ahead, and does planning seven days ahead improve decisions enough to justify its computational and modelling cost?

Current decision: continue to use the full current seven-day horizon, including when evaluating whether opportunistic EV charging above the normal 80% ceiling is worthwhile. Do not shorten the horizon merely because this evaluation is pending.

Future assessment should:

- Compare predictions with actual outcomes by elapsed lead time, including day-ahead bins across the full horizon. Preserve forecast issuance time, target interval, timezone and revision identity; do not substitute later revisions or hindsight for what was known at the time.
- Evaluate AC PV, DC PV and uncontrolled consumption separately, where data permits. Assess energy error, bias, timing error and error ranges over decision-relevant windows. Do not treat curtailed PV output as uncurtailed production potential or double-count controlled task consumption as background demand.
- Determine whether distant forecasts add useful information for EV charging, ESS reserves and other decisions. Forecast accuracy alone is not the same as scheduling value: compare cost, completion reliability, changes between plan revisions and calculation time for candidate horizons under consistent assumptions.
- Use representative seasons and household conditions; identify limitations of available samples. Avoid inferring annual performance from a few sunny or cloudy days.
- Recommend whether to keep seven days, use a shorter horizon, or retain a longer view with less detail or confidence further ahead. None of these alternatives is adopted yet.

Evidence needed: archived forecasts as originally issued at sufficient temporal resolution; corresponding actual measurements with quality/curtailment information; relevant task, availability, tariff and resource-state records for scheduling comparisons. Existing daily forecast-summary tables alone do not establish quarter-hour timing accuracy. Data coverage and retention need checking before the future assessment can be considered feasible.

No evaluation or implementation has been performed for this backlog item.

## ARCH-002 — Revisit temporal resolution only if a demonstrated issue warrants it

Recorded: 22 October 2026. Status: **conditional future investigation**, not a planned change.

Current decision: use planning windows no longer than five minutes. The user prefers retaining that detail and considering coarser windows only if a real issue arises that reducing temporal resolution could resolve.

If triggered, compare the same requirements, forecasts and policies at candidate resolutions. Measure runtime and solver quality alongside energy cost, completion reliability, continuity and quarter-hour peak prediction. Include the effect on short charging opportunities and appliance profiles. Coarser windows or a coarser distant horizon are possibilities to discuss with the user, not automatically authorized fallbacks.

Keep this separate from ARCH-001: changing the number of days ahead and changing the size of time windows are different decisions.

## ARCH-003 — Automated trip-distance calculation and temperature compensation

Recorded: 22 October 2026. Updated25 October2026: **calendar import authorized for4.3.0;
Google Maps integration implemented for4.4.0**.

Initial agreed approach: the user enters expected trip kilometres; estimate battery energy using an assumed average consumption. No database of previous trips or learned driving schedule is required.

Future extensions, independently selectable:

- Calculate expected driving distance from the entered trip destination/location. Routing source, interpretation of outward/return journeys and supported input formats remain undecided.
- Adjust expected trip-energy consumption using predicted outside temperature, including relevant battery-conditioning and cabin-climate effects where evidence supports them. The compensation model, calibration evidence and treatment of uncertainty are not yet selected.

Retain explicit user requirements and distinguish distance-derived estimates from direct SoC targets. Do not silently alter a user-entered target or assume capabilities such as en-route charging. Any future calibration approach should respect the user's preference not to maintain trip-history records.

The user authorized multiple labelled iCalendar subscriptions in Settings, starting with
referee calendars. The first release imports active timed events into the EV schedule
as provisional50km total journeys, departing at event start and returning four elapsed
hours later (explicitly confirmed). Commit/push that release before starting Maps work.
Stable source/event identities, refresh/update/cancellation, timezone handling and
explicit last-good/stale/error status belong to this import scope. Actual subscription
links stay in installation configuration; do not commit the supplied private feed.

After4.3.0, prepare Google Maps routing for automated distance and travel timing. Code
may be written if enough information is available, but **do not release the second
version yet**. Origin, round-trip routing, arrival margin/event-duration policy, Google
project/key/billing and failure/override policy still need resolution before enabling
live route requests. No paid API calls or live installation operation are authorized.
Temperature compensation remains deferred; no calibration model has been selected.

25October2026 historical checkpoint: Maps preparation was **paused at the user's request** while EV fault
handling takes priority. Tested routing code and16 synthetic routing cases, plus the
previous doc changes, are preserved locally in `gpt/paused-maps-2026-10-25/` with a
SHA256-verified ZIP. They are outside the active package and are not released in4.3.1.
Subsequent V4.4 authorization: the prepared code/tests were copied unchanged into a
separate codex/v4.4-google-maps worktree for scheduled implementation. The original
archive remains intact. Confirmed policy: HA home to venue to home; arrive60minutes
before start and leave the venue two elapsed hours after start. Selected calendars
have routing toggles, and manual destination-based journeys are included. Use predicted
traffic for the next seven days; refresh daily, on event changes and manually. Failed
or missing routes remain unresolved and notify the user. Persistent per-event overrides
survive calendar sync and support an explicit return to automatic. See the maintained
architecture and decision log for the agreed scope and current4.4.0 implementation.
Follow-up answers confirm independent home to venue to home trips, including same-day
events. Manual destination journeys accept desired venue arrival/departure and derive
home departure/return plus distance. Unresolved trips show a persistent EV warning and
send one deduplicated notice to the existing selected phone destination. No venue
chaining is included in V4.4.
27 October2026: the user authorized key-based activation and publication to main.
4.4.0 activates routing immediately after saving a Routes API key; the first required
route request validates it with Google. This supersedes the draft activation/publication
hold. Unresolved trips warn without blocking other valid goals. Key replacement/clear
applies immediately; no live credentials or installation are used in development checks.
Temperature compensation remains deferred. Current behavior is in the maintained architecture.

Offline integration limitation observed25October2026: two synthetic50km journeys
requiring additional charging from45%initialSoC produced no reference incumbent at
15/60second planner budgets. No invalid plan was adopted; basic control stayed
responsive. The90%SoC version completed. Preserve this evidence for a separately
authorized planner/seed-budget investigation; calendar-import work does not authorize
changing solver policy or temporal resolution.

26October2026: the user authorized the planner/seed investigation after providing a
failed decision.4.3.11 corrects month-reset seed permissions and adds one bounded
required-reference timeout recovery within the existing global budget. The supplied
frozen failure reproduces before the fix and validates afterward; raw inputs/replays
remain ignored local evidence. This does not establish that all calendar scenarios
will solve within budget. Maps activation was separately authorized for4.4.0 afterward;
temperature compensation remains deferred.

27 October2026: V4.4 is reconciled with the committed4.3.20 baseline in its separate
worktree. This preserves the subsequently authorized planner fixes and current EV UI.
The former Maps pause is historical; key-based activation and release are now authorized. Temperature compensation
remains deferred. See WORK_STATE.md for compatibility verification and continuation.

## ARCH-004 — DHW scheduling and heating-model calibration

Recorded: 22 October 2026. Status: **deferred beyond the initial release**, explicitly requested by the user.

DHW scheduling is not essential for this release. Preserve the previously discussed requirements for later work: minimum usable hot-water reserve, scheduled comfort windows, optional surplus heating, task priorities and peak permissions, and separately validated disinfection completion. These remain design inputs, not implemented or validated capabilities.

Prerequisites and evidence:

- The user plans to install ESPAltherma; it is not installed yet. Verify the applicable device definition and actual availability of tank temperature, DHW/space-heating status and heater-stage flags.
- Collect synchronized whole-unit electrical power, tank temperature and operating-state observations over representative heating cycles. Use them to estimate heating time, energy use, standby cooling and uncertainty, and avoid double-counting DHW as both a task and background consumption.
- Account for observed backup-heater demand. Whether routine use can be suppressed remains unresolved; do not assume independently selectable heat-pump-only operation. Validate any inferred heater activity against available status readings.
- Establish the actual command interface and feasible heating behaviour before enabling scheduling. Disinfection integration and completion criteria remain separate unresolved work; this deferral does not authorize changing the unit's existing controls.

For the initial release, leave DHW under its existing control and account for its consumption as uncontrolled demand. Keep the general architecture able to add a thermal resource and its tasks later without requiring them for EV/ESS scheduling.

No installation, calibration or implementation is authorized by this backlog entry.

## ARCH-005 — Washing-machine and dishwasher scheduling suggestions

Recorded: 22 October 2026. Updated: 30 October 2026. Status: **profile management in4.5.0; scheduling remains deferred**.
The user authorized implementation to start at 23:30 Europe/Brussels on 25 October,
with preparation/questions beforehand in a separate worktree/branch. First focus:
capture and durable storage of per-machine/per-program power profiles. No V4.5
application code was written before the requested time. The first profile-management
milestone is implemented for4.5.0, integrated with the4.4.17 baseline, with idle completion,
review/trim/select, persistent raw cycles and editable Mazak averages. The user confirmed
profile management first; scheduling suggestions remain the next milestone.

Confirmed modes: dishwasher Eco and possibly Heavy; washing machine whites 60 C,
darks 40 C, darks 30 C and coloured 40 C. Mazak uses provisional flat average loads:
Program 2,500 W, Light 3,500 W, Production 7,000 W, to be tuned later. Detailed Mazak
cycle learning is not requested. Capture uses an explicitly armed program and a
configurable idle timeout, followed by review. Installation sensor identities and
calibration and load variants remain unresolved. From4.5.3, explicitly included reviewed
cycles are averaged with starts aligned in real time and zero after each selected end.
Raw recordings are retained, and review graphs support linked trim handles and zoom/pan.
Appliance scheduling remains deferred.
The maintained architecture records these confirmed requirements and open decisions.

9 November recorder feedback follow-up (V45-A003): the user wants positive confirmation
that idle has been observed and visibility of latest power after arming. They selected
one clear location, directly beneath Record next cycle in the expanded card, without
duplicating it on the collapsed card. Show waiting/ready/recording and unavailable states
from existing recorder evidence, preserving its detection logic. Scope/completion criteria
are in ARCHITECTURE.md. The user authorized handoff on 9 November, conditional on
the current V4.6 EV implementation (EV-A008 at authorization) finishing first.
EV-A008 is now confirmed complete as4.6.6 with CI/publication successful. The authorized
recorder-feedback change is implemented in4.6.7 from that released base, verified with
local synthetic readings/faults/restart. Broader appliance changes remain separate;
see WORK_STATE.md.

On 1 November 2026 the user agreed to a user-managed appliance/program library,
with scheduling support determined by operating behavior. Initial support is for
manually started, uninterrupted program cycles; other equipment needs its own
supported behavior. This is pending V4.5 direction V45-A001, not implementation
authorization. Saved-recording removal and program management are identified gaps.
On 8 November the user requested UI creation of programs for the washing machine
and similar manually maintained catalogues, excluding the HA-known Bosch programs.
The small V45-A001-P1 scope uses name-only creation and the existing recording/average
workflow. The user also confirmed renaming existing and new washing-machine programs,
preserving their identities and recordings. Program removal/dependent-data policy and
adding appliances remain separate. See the pending UI program creation and renaming
section in ARCHITECTURE.md for scope/completion criteria. The user authorized this
subset on 8 November and requested starting in 1 hour and 11 minutes. Its one-time
implementation handoff fired on8November; P1 is implemented in4.6.2 and verified offline.
The automation was deleted after dispatch; see WORK_STATE.md.
The broader V45-A001 work remains outside this authorization.

9 November: the user wants the shipped Add/Rename UI integrated better and requested
a render of icons beside the existing program selector, with one inline name editor
and Save/Cancel. Rename uses the selected program; creation selects the new entry.
The user approved the preview and confirmed replacing the selector with the name field
while editing. V45-A001-P2 scope/completion criteria are recorded in ARCHITECTURE.md.
The user explicitly authorized this separate UI follow-up's implementation handoff on
9 November. Implemented in4.6.5 with offline both-dashboard/draft/conflict verification.
Keep broader V45-A001 work and program removal outside this package.

The user chose permanent recording deletion after confirmation; removal from an
average retains the recording. Program/appliance removal and dependent-data rules
remain open. See ARCHITECTURE.md and
the V4.5 coordination record in WORK_STATE.md.

On 2 November 2026 the user supplied an installed Bosch Home Connect capability
handoff and selected a dedicated dishwasher integration direction (V45-A002),
with reviewed program recordings as the next focus. This supersedes the manual-only
assumption for that dishwasher. Generic-library work has not been withdrawn;
Bosch scheduling/control requirements remain under discussion and implementation
is not yet authorized. See ARCHITECTURE.md for capability evidence and limits.

The user subsequently approved two delivery milestones: V45-A002-M1 for shared cards,
Bosch feedback and automatic profile collection/review/delete; V45-A002-M2 for managed
scheduling alongside EV/ESS, including background-demand separation. These are agreed
scope stages, not application implementation authorization. The user agreed to include
manual program/modifier controls and Start now and record in M1; M2's detailed
planner/accounting criteria remain pending. M1 scope/criteria are in ARCHITECTURE.md. M1 was
subsequently explicitly authorized and implemented in4.5.5 (cards, automatic Bosch capture,
review/delete and manual controls), with offline verification. M2 and full V45-A001
library management remain pending; see the current architecture/work-state records.

Preserve the earlier appliance-scheduling requirements for a later release:

- User-entered earliest start and latest completion, with reusable program durations and electrical power profiles.
- One recommended start time and a few alternatives, with meaningful cost differences where available. Current appliances are started or programmed by the user; do not assume remote-start capability.
- A user-confirmed start time becomes a fixed commitment. Subsequent improvements may be suggested but must not automatically move that commitment.
- Prefer measured time-varying profiles and retain variation between cycles. An average-power fallback can be used where detailed profiles are unavailable. Avoid double-counting these loads in background forecasts when explicit profiles are introduced.

### Planned Mazak operation

The user also defers explicitly planned Mazak operation and expects it can be added alongside washing-machine and dishwasher scheduling. Group the work here without assuming the machine shares their automatic-start, interruptibility, duration or power-profile behaviour. Establish its actual planning inputs and constraints when revisited.

For the initial release, its electricity use remains part of uncontrolled household demand. This deferral concerns planning its operation, not permission to control the machine.

The original deferral of scheduling suggestions and planned Mazak operation is now
superseded by the explicit V4.5 authorization above. Automatic recognition of
already-running appliances remains separately deferred as ARCH-006. This selection
does not authorize live access, operation or deployment.

## ARCH-006 — Automatic recognition of running appliances

Recorded: 22 October 2026. Status: **deferred beyond the initial release**, explicitly requested by the user.

Preserve the earlier direction: recognize starts of explicitly configured appliances from suitable circuit measurements, then represent their remaining demand as already-running, fixed, non-interruptible tasks. Do not attempt to identify every unexplained household fluctuation or stop/reschedule an uncontrollable appliance.

Future work needs representative circuit measurements, a validated recognition method, remaining-profile estimates and correct separation from the background forecast. Profile errors in an uncontrollable running load should not automatically trigger repeated full replanning without useful new information.

For the initial release, include these loads in the uncontrolled household-demand forecast. This does not remove fast peak protection by reducing eligible controllable loads.

No implementation or data-collection experiment is authorized by this backlog entry.

## ARCH-007 — Advanced forecasting ideas from the ML specialist

Recorded: 22 October 2026. Status: **deferred to a later release**, explicitly requested by the user.

The user has now consulted the ML specialist mentioned in the earlier discussion. The specialist proposed interesting forecasting ideas, but they require substantially more stored data than is currently available and are more advanced than the user wants to pursue for this release.

The user identifies the direction as **foundation models for forecasting**. Preserve this as a future investigation. No particular model, provider, training/fine-tuning approach or data requirement has been specified; do not infer one from that label. When revisited, establish the required signals, history length, data quality and retention before assessing feasibility.

Keep this separate from ARCH-001, which evaluates forecast accuracy by lead time and the usefulness of the seven-day horizon. That evaluation does not require committing to an advanced forecasting method.

This deferral does not authorize changes to predictors, new data-collection jobs or experiments.

## ARCH-008 — ESS reserve for unplanned load peaks

Recorded: 22 October 2026. Status: **deferred idea for a later release**, explicitly requested by the user.

Consider retaining some ESS energy to help cover unplanned load peaks. This is additional uncertainty protection, distinct from reserves for specific forecast peaks and from the actuator's physical minimum SoC. It is not a grid-outage/backup requirement.

When revisited:

- Use measured unexpected load events and forecast errors to assess a useful energy reserve and the discharge power needed. Stored energy alone cannot cover peaks above available converter output.
- Compare protection against its costs: reduced energy for ordinary use, possible extra grid imports, lost solar headroom and overlap with existing reservations.
- Decide whether sizing should be fixed or adaptive, when the reserve may be used/released and how replenishment fits source and peak permissions. Do not assume grid replenishment is automatically authorized.
- Keep the reserve and its reason visible. No reserve size or control policy is selected yet.

This does not add a standing reserve to the initial release or authorize experiments or implementation.


## ARCH-009 — Visual EV schedule and dedicated EV page

Recorded: 24 October 2026. Status: **implemented locally in 4.1.0**, after the user
explicitly authorized starting ARCH-009 and writing code on the same date. Retained
here to preserve the original deferred intent and its resolution.

Original intent: make the car schedule easier to understand visually, perhaps using a calendar on a
new page dedicated to the EV. Preserve journeys, expected away/return periods, morning
and manual SoC requirements, and planned charging sessions without implying measured
activity or inventing a learned driving routine. Layout and interactions were left
undecided for later feature work, including V4.1 discussion.

The dedicated EV page now combines a seven-day calendar with a selected-day agenda,
expected away/return periods, morning/manual/departure targets and accepted charging
sessions. Existing forms support explicit goal changes. Unknown returns remain explicit;
obsolete plan outcomes are withheld while current requirements remain visible. This
builds on the separate 4.0.10 date/time controls and W display. See the maintained
architecture for the implemented contract and VERIFICATION.md for local evidence.

## ARCH-010 — Longer graph history from archived measurements

Recorded: 24 October 2026. Status: **implemented in 4.2.2**. The user authorized
committing and pushing the completed history fix after reviewing the local result.

Original issue (through released4.2.1): graphs receive only the latest2,000 control-loop
samples, roughly33 minutes at a one-second loop. Overview shows six hours into the past
but backward navigation does not load older measurements. Measurement events remain in
SQLite; this is a display limit, not archival deletion.

The implemented fix loads the requested graph range from the indexed existing
measurement archive in a read-only worker. Overview keeps12-hour navigation/Now and
adds installation-local History day selection, including23/25-hour days. Any retained
day can be requested; the API bounds each query to eight elapsed days and100–2,000
points per series. The UI requests1,200. First/min/max/last reduction preserves peaks
within continuous buckets; buckets containing gaps are conservatively left blank.
Unknown/other-mode samples and expired reads break lines. Requests are cached and
obsolete navigation responses cannot repaint another range. Older graph data is merged
with recent samples rather than shipping the full archive to the browser.

New records retain battery capacities. Older archived kWh records use current runtime
capacities to estimate percentages, explicitly labelled in the graph. No missing data is
fabricated, no HA Recorder history is imported, and no retention/deletion policy is adopted.

Offline verification uses clearly labelled synthetic archives/local fake endpoints.
Actual installation history remains unverified; live database access was not authorized.
The earlier hold on committing/pushing was lifted by the user for the 4.2.2 release.

## ARCH-011 — Current capacity peak on the power graph

Recorded: 25 October 2026. Status: **implemented in4.3.9**, explicitly authorized
alongside scheduled wheel/mobile graph navigation.

Overview shows the current recorded monthly capacity peak as a red long-dashed line
with a Month peak label and15-minute-average legend/description. Its live input is
distinct from instantaneous power, forecast peaks, tariff floors and approval limits.
Unavailable omits the line; real zero is valid. No scheduler/control-policy changes.
Presentation updated in4.3.10: the Grid box also shows a peak-chart icon/value opening
the actual mapped HA sensor history directly.

## ARCH-012 — Clean up goals and progress

Recorded: 25 October2026. Status: **specified cleanup implemented in4.4.5** after the
user's28October request. Broader unspecified redesign remains deferred.

From4.4.7, Overview shows goals due within the next24 elapsed hours and omits the
forecast cost card. Planning retains the full chronological goal list and cost breakdown.
Trips show driving kWh alongside total distance and departure target.
The user explicitly chose a current-charge bar only for the earliest upcoming goal;
later goals retain predicted SoC/readiness without implying today's energy is reserved
for each trip. Unknown/unusable current EV energy hides the bar. The EV agenda/details
share the same driving-energy estimate. Scheduling and goal semantics are unchanged.

Any broader layout or interaction change still needs its own scope/authorization.

## ARCH-013 — Preserve unsaved settings in the native HA dashboard

Recorded: 25 October 2026. Target: **V4.3.x implementation**. Status: **deferred**,
explicitly requested by the user after entering the numeric go-e sensor mappings.

The user reports that the native HA dashboard's EnergyManager Settings tab sometimes
appears to refresh and clears unsaved edits. The current draft and dirty flag exist
only in the settings component. Card removal/recreation disposes that component and
loads saved configuration again; the browser-unload warning does not cover internal
HA card recreation. This is an identified loss path, but the exact event triggering
the user's observed refresh has not been reproduced. Ordinary state polling does not
directly rebuild the settings form. Entering/saving the mappings was subsequently
successful, but the underlying draft-loss problem remains unresolved.

Future implementation should preserve and restore unsaved field values, including
entity IDs still being typed, across native card recreation. Prevent delayed settings
loads or entity-list refreshes from overwriting newer edits. Clear drafts after a
successful save or an explicit discard; do not silently save/apply configuration.
Choose draft lifetime, isolation between installations/modes and revision-conflict
handling when implementing. Verify card detach/reattach, navigation, refresh/reconnect,
in-flight loads, failed saves and explicit save/discard, retaining useful focus/scroll
state where practical. Confirm the actual refresh trigger rather than assuming it.

This backlog entry records future work and does not authorize implementation.

## ARCH-014 — Clickable EV readings and states with history

Recorded: 25 October 2026. Status: **mapped sensor history implemented in4.3.19**,
explicitly authorized27October. Separate command/composite history remains deferred.

Make the EV visualization's numbers and states clickable in the normal HA manner so
the user can inspect their history. Include measured power, battery SoC, connection,
charger state/error, charging permission and current/phase setting readbacks. Use the
actual mapped HA entity and standard more-info/history when available. Distinguish
controller requests, composite status and derived values from measured HA sensors;
choose an appropriate command/event history or source-history explanation rather than
inventing an HA sensor or implying that its history already exists. Unknown or unmapped
sources must remain explicit. Keep keyboard/touch interaction usable.

The user likes the charger/car drawing with diagnostic readings integrated into it.
After the visual tryouts, the user approved the first design's annotated drawing with
the third design's diagnostic sidebar and authorized implementation with red/neutral/
green status colors in4.3.6. That layout is implemented. Release4.3.19 opens the actual
mapped entities from the visualization, preserving keyboard focus, selectable text and
phase controls. Missing mappings/demo/standalone explain the lack of an entity action.
Controller requests and internal timestamps explain their source without inventing an
HA sensor. A separate command/composite history UI remains deferred and is not authorized.

## ARCH-015 — Air compressor detection

Recorded: 25 October 2026. Status: **deferred**, requested by the user.

Detect when the air compressor is running. Available measurement sources, detection
criteria and how the detected activity should be used remain to be established.
Relates to ARCH-006 appliance recognition; do not assume remote control or scheduling
of the compressor is requested.

This backlog entry does not authorize implementation.

## ARCH-016 — Dynamic tariff comparison

Recorded: 25 October 2026. Status: **deferred**, requested by the user.

Compare dynamic electricity tariffs with the current tariff to assess potential
whole-system cost differences. Comparison period, tariff/data sources and whether
to compare the same consumption or separately optimized schedules remain to be
decided. Include applicable import/export charges and capacity costs consistently;
distinguish estimated savings from measured results.

This item does not authorize changing the active tariff or implementing dynamic-tariff
scheduling. Implementation requires separate authorization.

## ARCH-017 — Dynamic peak headroom by time and weekday

Recorded: 27 October 2026. Status: **deferred**, requested by the user.

Consider reserving grid-import headroom below the current monthly capacity peak,
varying with time of day and day of week, to leave room for uncertain household
loads. Decide whether this should constrain EV charging only or other controllable
loads as well; the user explicitly left the EV-only scope open.

When revisiting, establish how to size and release the headroom, and how it interacts
with required EV goals, charging continuity, ESS peak protection and existing peak
permissions. Keep the recorded 15-minute-average billing peak distinct from the
chosen planning headroom. No amounts, time bands or weekday rules are selected yet.

This backlog entry does not authorize implementation.

## ARCH-018 — Task energy profile visualization

Recorded: 27 October 2026. Updated: 8 November 2026. Status: **recording-list/trim
package implemented in4.5.8 and verified offline**; original task-chart ideas remain deferred.

Include a visualization of each task's energy profile. Establish the presentation,
time resolution and whether it shows planned, measured or both profiles when
revisiting; keep predictions and observations distinguishable.

On 7 November the user asked to put energy-profile visualisations on the immediate
todo list once the M2 scheduling package was handed to implementation. Clarify whether
this follow-up covers appliance/program profiles, task/run views or comparisons.
Existing planned task charts and appliance recording/average graphs are the starting
point. Preserve the original task-profile intent while the follow-up scope is discussed.
This discussion does not silently amend the authorized M2 implementation.

8 November clarification: the immediate problem is the presentation and organisation
of recording entries, not the plotted power values. The user finds the current large
entries excessive and unsuitable for many recordings, and reports that saving new
selections appears to create duplicate recordings. Read-only source inspection confirms
that saving revised trims creates separate immutable saved versions, all listed as
peers; average membership changes alone do not create recordings. One physical capture
still contributes at most once to a program average. Prioritise compact, scalable
recording browsing. The user agreed to grouping per program and expanding trimming
controls within the same recording entry. Saved trims must update that recording in
place, without a new entry or version. Deletion and technical details need not move into
a secondary menu. The proposed version-history approach was rejected. See the pending
ARCH-018 requirements in ARCHITECTURE.md. One recording expanded at a time is confirmed;
opening another collapses the previous entry. After reviewing examples, the user chose
foldable program groups and explicitly required retaining the original Start/End slider
functionality. Keep draggable graph handles and linked numeric fields; the simplified
mockup controls do not replace them. The user chose the latest saved trim when
consolidating existing duplicates, including when an older trim was previously included.
Retain raw capture data and the capture's inclusion/exclusion; apply the latest trim once.
The user explicitly authorized the separate recording-list/trim implementation handoff
on 8 November. Scope and completion criteria are in ARCHITECTURE.md. Preserve the original task-profile
visualization idea separately within this entry; chart comparisons are not the user's
current focus and are not part of this authorization.

Authorization covers only the recording-list/trim package, separately from M2.

## ARCH-019 — Task main energy source

Recorded: 27 October 2026. Status: **deferred**, requested by the user.

Show the main energy source for each task. Define the source categories and how the
main source is determined for tasks supplied by multiple sources. Keep planned
source allocation distinct from measured attribution; do not assume this display
request changes scheduling or source permissions.

This backlog entry does not authorize implementation.

## ARCH-020 — Adaptive plan-update frequency

Recorded: 28 October 2026. Status: **deferred**, requested by the user.

Adjust plan-update frequency based on generation and load stability: replan less
often during stable conditions and more often when meaningful changes warrant it.
Define stability measures, thresholds and minimum/maximum update intervals when
revisiting. Keep fast control and urgent event handling independent; a longer
planning interval must not delay peak protection or invalidate required deadlines.

This backlog entry does not authorize implementation.


## ARCH-021 — Uninterrupted charging during application restarts

Recorded:28 October2026. Status:**deferred pending a verified independent limit**.

The user authorized fast saved-schedule startup recovery first (4.4.11). The explicit
shutdown stop remains. Before allowing an update/restart to leave charging running,
verify an independent charger-enforced time/energy bound and its interaction with
forced start, plus loss of live load/ESS balancing. A Python timeout cannot enforce a
stop while the application is offline. Do not assume a generic HTTP watchdog exists
or that the documented energy limit overrides forced charging on installed firmware.
A full HA/host outage and an explicit control-Off/fault must retain defined behavior.
No live hardware testing or implementation of offline continuation is authorized here.

## ARCH-022 — Revisit EV trip calendar integration and bidirectional sync

Recorded: 2 November 2026. Status: **deferred**, requested by the user.

Revisit the EV trip calendar integration to address its issues and limitations, and
consider bidirectional synchronization with the source calendar. The specific issues,
supported calendar services, synchronization behavior and conflict handling remain to
be established with the user. This entry does not authorize implementation.

## ARCH-023 — Complete energy and power breakdown

Recorded: 2 November 2026. Status: **deferred**, requested by the user.

Add a complete energy and power breakdown. The scope, categories, presentation and
distinction between measured and planned values remain to be discussed. This entry
does not authorize implementation.

## ARCH-024 — ESS minimum SoC line

Recorded: 2 November 2026. Status: **deferred**, requested by the user.

Add an ESS minimum state-of-charge line. Its presentation and placement remain to be
discussed. This entry does not authorize implementation.

## ARCH-025 — Peak-power line from the actual sensor

Recorded: 2 November 2026. Status: **implemented in4.6.0 (EV-A002)** on 8 November2026.

Show the mapped monthly-peak sensor's recorded history as Overview graph steps,
including billable rises, zeros, month resets and missing-history gaps. This shares
EV-A002 with grouped measured-peak mobile alerts. The2.5kW alert billing floor
never substitutes for actual plotted sensor values.
See [ARCHITECTURE.md](ARCHITECTURE.md#measured-peak-alerts-and-graph-history-ev-a002-460).


Peak-graph follow-up to ARCH-025 is scoped as EV-A006 in
[ARCHITECTURE.md](ARCHITECTURE.md#peak-graph-forecast-and-current-quarter-display-ev-a006-463):
predicted peak, visual separation from grid power while keeping the same colour,
and current-quarter visualization. The quarter value belongs in the existing Grid
box to the right of the monthly peak in its existing bottom-row position; no
separate panel beside the graph. Dotted/heavier peak, lighter power traces,
alternating quarter-hour backgrounds, current-quarter emphasis and a simple
projected-end marker are agreed. Implemented in4.6.3 after the8November authorization;
verification and release coordination remain in WORK_STATE.md.

Further peak-display refinement is scoped as EV-A007 in
[ARCHITECTURE.md](ARCHITECTURE.md#peak-display-refinement-ev-a007-464):
use Long dashes slightly heavier than the current peak line, give the quarter value a red icon/native mapped
sensor action and remove cursor prose. Retain quarter shading and value placement.
The minimal-text and applicable HA-sensor-action preferences apply dashboard-wide.
Authorized on8November2026; implemented in4.6.4. Offline verification and
release coordination are recorded in WORK_STATE.md.

## ARCH-026 — Deterministic planning inputs and limits before MILP

Recorded6November2026; scoped into EV-A005 and authorized8November.
Status: **implemented in4.6.1**. Reference candidates, safe
backward physical bounds, bounded wider search, cautious80% future-PV certificates,
execution fallback and margin warnings. Dense unavailable-slot bookkeeping is
retained after explicit fixing showed no presolve gain. See the maintained
[architecture](ARCHITECTURE.md#ev-planning-candidates-and-deadline-safeguard-ev-a005--arch-026-461).

## ARCH-028 — Unreliable EV feedback and manual charging recovery

Recorded:10November2026. Status: **Implemented in4.6.10 (EV-A010); offline verified, installation unverified**.

Detect insufficient SoC response to measured charging, contradictory new battery
readings and insufficient return evidence. The user accepts a mobile alert and a
persistent in-app warning; keep ESS and other independent functions working. They
propose manual actual-SoC input to anchor best-effort counter-measured charging during
upstream feedback failure. An EV-tab manual-SoC switch, confirmed activation when
offered after an issue and invalidation on unplugging are agreed. User also accepted
manual authority for the next charging goal, with age reminders unable to interrupt
it and no automatic renewal to later goals. Automatic recovery with a notification
on new valid vehicle readings is agreed; matching the estimate is not a gate. A
changed valid SoC compared with the previous vehicle report is sufficient evidence.
Initial3percentage-point delivery plus15minute update grace is accepted, subject to
verification. Reference age is displayed in the EV tab; request refresh only when
another charge needs a new reference, with no periodic age-only phone reminders.
Scope/UI and completion criteria are in the maintained architecture. The user
explicitly authorized implementation handoff on10November: "You have permission to
hand it off". Do not treat a charger counter as indefinite actual battery feedback or
remove progress tracking without a decision. Confirmed and proposed details are
separated in ARCHITECTURE.md under EV-A010. Standing ready-release permission applies;
live installation access/operation remains unauthorized.
