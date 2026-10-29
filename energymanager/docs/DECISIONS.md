# Current requirements and decisions

Maintained 25 October 2026 for 4.3.2. This records confirmed product preferences and
implementation outcomes from the V4 implementation chat. It supplements the complete
original [architecture decisions](architecture/Architecture_Decisions.md); the
[maintained architecture](architecture/Architecture_Proposal.md) describes the resulting implementation.
New explicit user instructions take precedence. Deferred ideas are not authorization.

## Architecture and EV behavior retained

- For4.3.19 the user authorized actual EV power in the Overview EV box and standard
  HA sensor-history actions on the EV visualization. Use mapped entities for readings,
  keep phase controls separate and explain derived/unmapped sources. Planning rejection
  and repeated-calculation findings remain read-only while the user considers them.
- For4.3.18 the user authorized accepting negative measured EV power after observing
  brief negative readings as the car connects internally. Other validation stays;
  errors must identify the sensor, original value/unit and read time. Signed readings
  remain visible and usable without a sign-triggered control interruption. EV SoC
  range checks, planned charge-only behavior and existing supervision are retained.
- For4.3.17 the user authorized expanding incident reporting after a15minute wait's
  export missed its beginning. Anchor the pre-incident window to recorded onset,
  keep ten minutes after detection and existing read bounds, and clearly label a
  capped report. This does not change charging, fault or recovery policy.
- For4.3.11 the user authorized correcting the reproduced planner failure and making
  rejected decisions accessible. Match the existing billing-month permissions in seed
  construction, allow one no-candidate timeout recovery using remaining budget, and
  keep horizon, input requirements, permissions and validation intact. Full exported
  decision JSON must retain its checksum for offline replay; private replay inputs
  are not release fixtures or committed configuration.
- For4.3.10 the user clarified that mouse-wheel scrolling should zoom; mouse dragging
  already covers horizontal panning. Wheel zoom anchors time under the pointer and
  shares the15min–7day bounds. Preserve mobile pinch/two-finger gestures, which the
  user reports working. Show the monthly peak with red dashes and a clickable Grid
  peak icon/value, opening the actual HA sensor directly.
- The user also chose direct, one-time HA phase-selector changes and explicitly
  allows automatic control to overwrite them. Do not pause EV/ESS control or constrain
  the planner.1φ/3φ/Auto use the mapped select entity's real supported options; Auto
  remains subject to existing fixed-phase control validation. Consolidate charger
  details in the diagnostic sidebar and remove the crossed-out phase-current footer.
- For4.3.9 the user confirmed both mobile time gestures: pinch zoom and two-finger
  horizontal pan. Wheel navigation uses the same shared Overview range as mouse drag;
  Now restores six hours and arrows move the current width. Engineering zoom bounds
  are15minutes–7days, within the existing eight-day history-query limit. One-finger
  vertical page scrolling, numeric cursor and copyable tooltips are retained.
- ARCH-011 shows the current recorded monthly quarter-hour-average import peak with
  a neutral dotted line. It never substitutes a tariff floor, forecast or approval
  limit. Missing source means unavailable; valid zero is displayed. No policy changes.

- One joint EV/ESS MILP, full seven elapsed days and intervals no longer than five
  minutes; an independent responsive control loop and persisted, validated decisions.
- Keep the original required/optional energy, source, cost, peak permission and
  continuity policies. Their complete original context is preserved in
  [the handoff](architecture/Implementation_Handoff.md) and
  [maintained architecture](architecture/Architecture_Proposal.md). Its current
  specification resolves the original mathematical proposals; historical pending-work
  statements are not a request to rebuild the application.
- The morning target is a timed minimum, initially 50% at 07:00 local. It is not a
  permanent floor and does not imply a daily journey or energy use. With these targets
  alone, predicted EV SoC can only stay level or rise. Entered total-distance journeys
  withdraw estimated travel energy; actual SoC reconciles the next planning snapshot.
  No automatic driving schedule or post-trip restore-to-50% rule is agreed.

## Project update and persistent configuration

- The user explicitly promoted the fresh `energymanager-next/` implementation into
  the main `energymanager/` project and named it version 4. Do not recreate the
  temporary tree or wrap the legacy scheduler. Keep the existing add-on/image identity.
- Create a missing selected configuration file from the bundled starter; preserve
  existing files. The configuration persists through image updates. Synthetic defaults
  are examples, not installation evidence. The editor writes the same file with a
  backup, atomic replacement and revision conflict checking.
- Provide HA-style searchable entity selectors and typed settings rather than require
  plain-text edits. Highlight missing mappings, placeholders, unavailable values,
  incompatible units and blank required fields immediately. Remove long explanatory
  entity subtitles. Installation settings take effect after restart.
- HA connection is automatic through Supervisor. Remove connection-address choices,
  the old notification webhook and the Commissioning tab. Standalone environment
  overrides remain tooling boundaries, outside the normal Settings page.
- Provide one hardware-control switch on Overview. The user explicitly chose immediate
  application. It persists independently of JSON settings, checks valid inputs/settings
  before enabling and revokes commands/stops EV/clears ESS on disable. First migration
  to the new switch starts off. Old commissioning/control flags cannot enable it.
- Optional phone destination is a searchable HA notify entity or mobile-app action.
  Keep existing deduplication and failure evidence. Development must not send real
  notifications. See SETTINGS.md for the complete control/configuration contract.

## Installation inputs and forecasting

- P1 import/export are separate sensors:
  `sensor.p1_dongle_momentary_active_import` and
  `sensor.p1_dongle_momentary_active_export`.
- `sensor.p1_dongle_current_quarter_average_demand` is kW with a fixed full-quarter
  denominator. The user confirmed it drops near zero at each quarter and builds up.
  Convert demand to quarter-import energy using 0.25 h. Do not ask for a measurement
  type or treat it as an elapsed-time average.
- There is no dedicated uncontrolled-house-demand sensor. Derive it from separate
  P1 import/export, AC solar, ESS AC output and EV charging, using the specified signs.
  Do not double-count DC solar or expose a nonexistent house sensor mapping.
- The user uses go-e APIv2 Connect. Use the existing phase selector readback for
  forced one/three-phase modes; no extra phase-count sensor or phase-source choice.
  Auto/unavailable readback is unknown; preserve stop/zero protections and the
  30second restart settling hold adopted in4.3.13.
- Daily readiness settings belong with EV settings.
- Forecasting must use the original source, PV setups and applicable correction
  factors. These were recovered and restored: Open-Meteo KNMI seamless at HA home,
  four installed planes and original corrections. FORECASTING.md contains the exact
  recovered values and provenance. Never invent replacement installation parameters.

## Availability, watchdogs and display failures

- The user approved trusting HA's current available state rather than enforcing
  per-entity timestamp freshness or enumerating exceptions for zero/unchanged values.
  HA integrations own device availability. Retain numeric/unit/physical validation.
- Report timestamps are diagnostic. A successful validated HA read renews the input
  snapshot; the existing configurable watchdog (default 30 s) restricts control when
  successful reads cease. Forecast expiry remains separate. Device outage availability
  reporting is still an installation commissioning check.
- Do not infer a billing-quarter mismatch from an unchanged entity's report time.
  Preserve the actual quarter prefix/reset and fixed-denominator energy accounting.
- One failed input or forecast must not hide every available live summary. Show
  available readings independently and identify the failed entity/check. A validated
  control snapshot and command authority may still be withheld when required inputs
  fail. Actual charts use validated observations rather than invented measurements.

## GUI and future scope

- User authorized a full native HA dashboard with automatic future UI updates, retaining
  the current interface's useful presentation, immediate HA state updates and clickable
  sensor history. No iframe. Use HA's existing authenticated Supervisor bridge and a
  stable loader plus release-owned strategy/cards, avoiding a separate custom integration.
  Initial setup is once; subsequent add-on UI updates take effect on HA page reload.
  Personal dashboards are preserved. Backend polling/control policy and archived custom
  graph history are separate; ARCH-010 adds custom archive history in 4.2.2. See the maintained architecture.

- Keep Overview/Planning inspired by the original first two dashboard pages: live
  summaries, actual/planned power and SoC, time navigation, grouped sessions and the
  full seven-day view. Keep ESS blue and EV green; expose reasons/approvals without
  putting implementation detail into the normal household flow.
- Display power in W, including charts, card components, settings, peak/approval values
  and entity previews. Keep energy in kWh. Existing API/configuration/model units
  stay compatible. Capacity tariff display converts to EUR/W/month consistently.
- Journey and timed-SoC date/time fields use an Android-inspired calendar/24-hour clock
  with keyboard entry, the installation timezone, Cancel and optional-return Clear.
  Reject nonexistent clock-change times and expose both repeated-hour occurrences.
- On 24 October 2026 the user explicitly authorized ARCH-009 implementation. The EV
  page uses a seven-day calendar and selected-day agenda for journeys, away periods,
  morning/manual targets and accepted charging sessions. The existing scheduler and
  permissions remain authoritative; unknown returns and outdated plan results are explicit.
- Continue across chats and versions using the same maintained
  [architecture document](architecture/Architecture_Proposal.md). The user explicitly
  prefers updating it in place over creating version-specific handoffs. Backlog entries
  require separate authorization; a new chat does not authorize their implementation.

## Engineering/release rules from the user

- Do not write code without explicit permission. Questions, screenshots and error
  reports are discussion unless the user asks for implementation. Once authorized,
  finish that scope; ask before unrelated fixes/features and keep responses concise.
- Use the user's `code-writer` skill. Preserve unrelated working/staged changes and
  historical evidence. Do not access live HA/databases, operate hardware, send real
  notifications or deploy without separate authorization.
- Existing release authorization covers the agreed updates. Use one implementation
  commit with relevant docs; do not add optional "record successful release" commits.
  Record subsequent CI/publication results in the ignored checkpoint and final reply.
- On 24 October 2026 the user supplied standing authorization to commit and push
  versions when ready for release, including the existing image-publication workflow.
  Live installation deployment and hardware operation still need separate authorization.
- Maintain the same architecture document, decision log, deferred work, run
  instructions and meaningful verification alongside code. Preserve superseded design
  evidence in Git history and labelled historical records. On resumption compare
  checkpoint claims with the actual workspace.
- Do not buy/reset usage credits or switch to paid API usage. Do not promise automatic
  resumption or create an automation as a workaround. Resume from the checkpoint when
  the user returns after a normal reset.

## 24 October 2026 — 4.2.1 scope and graph-history follow-up

The user requests removing the duplicate native sensor strip, retaining the clickable
underlying-value chooser and adding daily energy to the live boxes. Release/push4.2.1
with that scope. Daily values integrate recorded power, show separate opposing flows
and explicitly mark partial coverage; no daily meter entities have been configured.
After that release, implement ARCH-010 graph archive loading, but do not commit or push
that work yet. This specific hold overrides standing ready-release permission for it.

## 24 October 2026 — Publish the graph-history fix

After reviewing the completed local implementation, the user explicitly authorized
committing and pushing it. This lifts the earlier hold for ARCH-010. Prepare release
4.2.2 with the completed code, tests, documentation and offline evidence. Existing
publication workflows are authorized; live HA deployment and hardware operation are
still separate actions. No additional dashboard or controller feature is added here.

## 25 October 2026 — Compact dashboard and graph inspection

The user requested compact symbolic energy/connection rows, numeric graph cursors,
more vertical power-graph space, aligned graph/session time axes and removal of the
duplicate battery-history chart. Keep the underlying-sensor chooser and archived SoC
graph. Move normal provenance/history details into diagnostics and combine plan-update
time with the selected time window. Existing error visibility remains.

The user explicitly chose expected total by the end of today after each energy value:
recorded energy so far plus the current plan for the rest of the installation-local
day. This is a projection, with partial actual coverage still marked, and does not
change scheduler or hardware authority. Prepare4.2.3 under standing release permission.

## 25 October2026 — ARCH-003 calendar import, then unreleased Maps preparation

The user authorized labelled links for multiple calendars in Settings, starting with
referee iCalendar subscriptions. First release: import agenda events into the EV
schedule using fake50km total and four hours, departing at event start and returning
four hours later. The user explicitly confirmed this interpretation. These journeys
use the existing energy/availability/planning rules and visibly retain placeholder
provenance. Subscription content owns imported journeys; manual requirements remain.
Release/commit/push4.3.0 when verified.

Only after that release, prepare Google Maps distance and travel-time calculation.
Code may be written if enough information is available, but the second version must
not be released yet. No paid API calls, assumed origin/margins or live installation
changes are authorized. Temperature compensation remains deferred within ARCH-003.

## 25 October2026 — Fault handling first; preserve and pause Maps

The user approved a separate EV fault-handling update: timestamps, five-minute prior
state/command evidence, one configurable go-e reboot attempt with verification, and
phone escalation if the system cannot resolve delivery. The supplied device action
reboots the charger; its entity must be configured, never hardcoded. Existing hardware,
fresh-input and planning guards remain authoritative. Verify only on synthetic/local
endpoints; no live reset, database access or phone notification is authorized.

Pause Maps without losing the work. Preserve the prepared code/tests/docs locally
outside the active package and keep it out of this release. The future referee policy
is confirmed: HA home for both legs, arrive60minutes early, leave the venue two elapsed
hours after event start. No Google credential input or live routing is activated.

## 25 October2026 — Implement the go-e source-review findings

The user approved status-aware charging, command confirmation, bounded phase waits,
restricted reboot eligibility and charger-limit/health validation. Explicitly confirmed:
numeric car/status/error and a device heartbeat may be required for EV control while
ESS stays available. Source inspection corrected the heartbeat choice: integration
2026.10.3 rounds uptime to whole hours; use its existing last Status change age in
seconds instead. No new physical phase sensor, direct charger connection, live access
or Maps activation. Keep HA as the control boundary and verify only fake endpoints.

## 25 October2026 — Fixed daily baseline and brief power-balance settling

The user requested investigation/fixes for graph flashes, slow/empty predicted energy
and transient negative derived household demand, and explicitly authorized code.
They selected a fixed estimate captured at midnight with capture time in the tooltip.
Save that baseline independently of open dashboards and retain it through replans and
restarts. If no eligible midnight plan exists, label a first available fallback honestly;
never reconstruct an apparent midnight forecast from information acquired afterward.

A brief inconsistent derived balance pauses commands without treating an impossible
negative demand as a valid measurement or triggering global errors/replans. Bound the
settling period by the existing input watchdog, retain diagnostic evidence, and keep
persistent/other input failures visible. Release4.3.3 uses standing ready-release
commit/push permission. Live HA, hardware and deployment remain separate authorization.

## 25 October2026 — Fix dashboard request recovery and selection

The user explicitly requested fixing repeated generic signal-timeout messages and
unselectable text after the read-only diagnosis. Preserve the15s deadline while
reporting the failing request, backing off state reads and clearing recovered errors.
Reduce repeated state transfers; keep full decision/replay evidence in the archive.
Enable selection and preserve it through automatic rendering, with a Copy error action
and manual fallback. Deliver through versioned card assets so the installed loader
continues to work. Ready-release commit/push authorization applies to4.3.4. No live
HA/database/hardware/deployment or real notifications are authorized.

## 25 October2026 — EV status visualization

The user requested an EV-tab visualization of status, powers and phases and explicitly
authorized implementation. Release4.3.5 uses existing measurements, command intent and
validated go-e readbacks; no new telemetry mappings or control behavior are introduced.
The phase selector is not evidence of physical per-phase amperage. Measured power and
requested power remain separately labelled, with unavailable/stale inputs visible and
fault/recovery reasons taking priority. Preserve the EV calendar and update only live
status on native HA source changes. Standing ready-release commit/push permission
applies; no live installation operation or deployment is authorized.

## 25 October2026 — Combined EV drawing and diagnostic status colors

The user selected the annotated drawing from the first design and diagnostic sidebar
from the third, approved the combined preview and explicitly requested implementation.
Release4.3.6 uses red for errors, white/normal theme text for neutral states and green
for OK. Color each current status independently rather than coloring all readings by
an older incident. Verified stop/wait settings are neutral; missing/stale states stay
unverified. Future HA history clicks remain deferred. Ready-release commit/push
permission applies; no installation access, hardware operation or deployment.

## 25 October2026 — Six-hour Overview graphs

The user requested a roughly six-hour Overview graph span for more horizontal detail.
Release4.3.7 uses two hours of history and four hours ahead, shared by power/SoC/session
bars. Arrows advance six elapsed hours; History day starts a six-hour view at local
midnight. Planning keeps its full horizon. These are display changes only.

## 25 October2026 — Drag Overview graphs horizontally

The user requested click-and-drag left/right graph scrolling. Release4.3.8 pans the
Overview time axis with the primary mouse button while synchronizing power/SoC/session
bars. Keep clicks for pinned values, tooltip text selection, keyboard inspection and
existing touch scrolling. A panned range stays fixed until Now. Do not change control
policy, zoom/vertical inputs, or the full Planning horizon. Standing release permission
applies; installation operation remains outside this scope.


## 26 October2026 — Charging continuity and rejected-plan attention

The user supplied a fragmented overnight EV candidate and explicitly authorized code
for continuity and the missing peak-rejection attention/notification path. Prefer fewer
starts, phase switches and power changes within the existing two-cent economic/cash
tolerance. Try a constant-current session where feasible, preserving required outcomes,
source accounting and permissions. Keep each economic search's real objective evidence
and use a focused refinement within its budget; a blended objective was rejected after
an offline replay showed much worse economic search quality. No billed wear fee is added.

A rejected peak check is a planning/reconciliation failure, not evidence that a higher
allowance is required. Show a persistent timestamped item, retry automatically once,
and notify the configured phone if unresolved. Genuine proven permission requests also
notify. Preserve prior instructions only while valid, and clear the attention item on
acceptance. Standing ready-release commit/push permission applies. No live installation,
hardware, actual phone alert or deployment is authorized in development.

## 27 October2026 — Fix revision changes interrupting EV start confirmation

The user explicitly approved fixing the reproduced revision/start issue alongside
the EV visual indicator. The indicator was already published in4.3.15;4.3.16 includes
it and fixes the charging path. Continue identical submitted commands across control
revisions, with the original confirmation deadline and advancing device readback;
never re-enter stop preparation solely because the revision changed. Preserve
enabled/generation guards on writes and all real stop/fault/input conditions. An
unsent revoked write must not leave a phantom pending acknowledgement or erase a
restart hold. Do not relax the separate immediate reported-error policy without
actual incident evidence and a confirmed policy choice. Standing ready-release
authorization applies; no live installation operation is authorized.

## 27 October2026 — Investigate rapid EV stops; show controller actions

The user reports charging starting then stopping/erroring after a few seconds and
requests investigation of timing/checks, plus a visual controller-action indicator
on the EV page, especially for the artificial30second restart holds. Implement the
read-only action/countdown display while preserving charger measurements and fault
details. Timer expiry is not evidence of charging or authority to start. Charging
behavior changes required separate authorization beyond this investigation; the
user subsequently approved the reproduced revision/start-readback fix for4.3.16.

## 27 October2026 — Recalculate replaces active work

The user explicitly requests that manual Recalculate start a fresh calculation,
canceling active work where possible, with no calculation queue and visual feedback.
Use one owned, terminable spawned process per solve; reap it before starting another.
Manual requests do not invalidate accepted control. Material revision changes replace
obsolete work, while routine same-revision control requests during a solve are ignored
to avoid starving it. Expose actual stages and elapsed time through a compact animated
indicator and button feedback; do not fabricate a completion percentage or ETA.
Standing ready-release commit/push permission applies. Development uses only synthetic
local endpoints; no installation operation or real phone notice is authorized.

## 27 October2026 — Thirty-second EV restart settling; retire phase cooldown

The user reported that the standalone stop→phase→30second pause→force-charge test
worked. Manual tests also showed car-app error/stopped cycles that self-recovered;
this does not identify a confirmed charger or car defect. Apply the30second hold
to automatic restarts after phase changes in either direction and ordinary stop/start
cycles. Current-only changes are excluded and must stay live. Count already elapsed
confirmed stopped time; keep control nonblocking and preserve protective/input/error
guards. Remove the phase-switch minimum from planning and control. The actual old
default was600seconds (10minutes), not15minutes; persistent-wait escalation is a
different900second timer and remains. Old configuration/decision fields stay readable
without retaining the cooldown. Existing direct manual HA phase controls retain their
previously approved semantics. Standing ready-release permission applies; no agent
operation of the installation is authorized.


27October2026 — User approved implementing EV continuity in original scheduling plus
recalculation changes. Preserve the existing0.02EUR economic allowance and all required
goals/permissions/physical constraints; prefer continuing sessions and current changes.
The implementation uses a full-joint economic reference and continuity objective with
ESS/source freedom, replacing fixed-ESS EV smoothing and leftover neighborhood polish.
Later stage selection preserves known continuity within the same shared allowance.
Short power mismatch is ordinary control work. Sustained energy evidence must change
near-term forecast assumptions before requesting another solve; deduplicate unchanged
bias and normal resource progress. New publication repair is explicitly excluded.


## 25 October 2026 — V4.4 routing scope and scheduled implementation

The user authorized a separate worktree/branch for V4.4 and restoration of the prepared
routing code there. New coding starts at18:29 Europe/Brussels, following the requested
2h50 delay. Scope includes per-calendar routing toggles beside subscription configuration
and manual destination-based journeys. Use predicted traffic, a seven-day routing
window, daily refresh, event-change refresh and a manual refresh action. Missing/failed
routes remain unresolved and notify the user to intervene; the old placeholder is not
an implicit substitute. Persistent per-event overrides survive calendar refreshes and
can be returned explicitly to automatic values.

The referee attendance/home policy is retained. Follow-up answers confirm that every
trip independently starts and ends at HA home, even for multiple same-day events;
venue chaining is outside V4.4. Manual destination journeys accept desired venue
arrival/departure, and Maps derives home departure/return plus total distance. An
unresolved trip shows a persistent EV warning and generates one deduplicated alert to
the existing selected HA phone destination; development uses fake notifications only.
The user believes their new credential is a configured Maps API
key; no secret/service/billing validation has occurred. There is no authorization for
live/paid API tests, installation operations or deployment. Earlier Maps publication
hold still requires clarification before commit/push/publication. Temperature adjustment
remains deferred. At the preparation checkpoint, 28 synthetic routing/calendar cases
passed; the subsequent offline integration is recorded in WORK_STATE.md.


## 25 October 2026 — Unresolved trips preserve other valid EV work

The user explicitly selected continuing other valid EV goals while an unresolved route
contributes no guessed distance/times. Persistent warnings and the deduplicated phone
notice remain. Remove the provisional blanket EV route hold. Pending requests without
a checked goal do not revoke unrelated work; changing/removing a previously checked
trip still invalidates its affected plan normally. Existing measurement, charger,
connection and permission guards remain unchanged. Verified against a real locally
solved EV plan plus fake actuator stop on disconnect; no installation operations.

The user questioned whether a seven-day lifetime should be ordinary use rather than
long-term caching. The current seven-day horizon does not expire stored goals/decision
inputs: the archive currently retains them indefinitely. Current EEA3.3.2(b) and Routes
service-specific20.2 were checked; an express general seven-day distance/time caching
allowance was not identified. This does not establish a definitive interpretation for
every transient operational calculation. Retention/activation remains unresolved; no
historical records are purged and no new API usage is authorized by the discussion.


## 25 October 2026 — Prepare the offline V4.4 diff for commit

The user requested commit preparation beginning at 23:30 Europe/Brussels. The one-time
schedule was paused on invocation. Review and offline fixes are authorized; this task
will not commit, push, merge, publish or deploy. The draft remains on its isolated
codex/v4.4-google-maps branch. Existing release metadata is unchanged.

A special Google agreement has not been established as necessary. Current retention
compatibility remains unresolved: clarification under the applicable standard terms or
an appropriate retention design may resolve it. Keep live routing disabled; this issue
does not prevent committing the offline implementation. Do not claim that a seven-day
planning horizon itself grants retention rights.


## 27 October 2026 — Reconcile V4.4 with the latest V4.3.x baseline

The user requested a compatibility check before a V4.4 release. Integrate the committed
4.3.20 baseline into the isolated Maps branch and fix interactions within V4.4 scope.
Retain newer charging continuity, evidence-based replanning, cancellable worker lifecycle,
planning failure notices, EV history/actions and charger timing. Preserve main's unrelated
working edits. This does not resolve the existing live-routing retention question or
authorize live API/installation operations; no release is published during the review.


## 27 October 2026 — Activate from a saved key and publish 4.4.0 to main

The user explicitly requested activation when a valid API token is entered in Settings
and publication to the main release. This supersedes the draft live-routing gate and
prior Maps publication hold. Saving a key activates immediately; Google's first required
route response validates it. Do not make a separate paid validation probe. Replacing or
clearing applies immediately; blank preserves. No extra global enable switch is needed.
Preserve calendar selection, all agreed routing/override/failure policies and existing
4.3.20 behavior. This release does not introduce archive deletion or claim new provider
retention rights. Development uses fake services; actual credentials, HA, hardware and
real notifications remain outside agent verification. Commit/push and the existing main
image-publication workflow are authorized; physical installation deployment is not.


## 28 October2026 — Recover elapsed delivery at publication (4.4.1)

Historical implementation decision. The later28October snapshot/live-control decision
below supersedes this publication repair requirement;4.4.4 removes that code.

The user authorized an independently established fix for an attached rejected charging
plan. Offline replay confirmed that the original candidate met the morning goal but
elapsed held charging was not confirmed by the publication-time battery reading.
This new authorization supersedes the4.3.20 exclusion of new publication repair for
this specific defect. Use one bounded same-phase extension of existing future work,
adding only the missing required energy. Keep measured inventory unchanged. Retain
all independent source/peak/physical/rolling checks and safe rejection when an extension
cannot fit. Reconcile and align the reference, preserve original evidence and update
adopted session/completion metadata. Cache only repeated audit arithmetic, changing no
policy or tolerances. Verification uses synthetic fixtures and the supplied frozen log;
no live installation/database/API or hardware operations are authorized by this fix.


## 28 October2026 — Retire expired manual goals (4.4.2)

The user explicitly requested a fix for a24October manual journey still shown as Waiting.
Retire elapsed manual requirements, preserving the full goal in archived events and all
existing decisions. Keep ongoing/unknown returns until their applicable return condition;
a fresh known home observation after departure can establish return. Persist retirement
so later unplugging/restart cannot resurrect a trip. Keep other valid command authority.
Calendar/routed managers retain ownership; active projections hide elapsed known returns.
This is a focused lifecycle correction, not authorization for the wider deferred
Goals & progress redesign (ARCH-012). No live installation operations are authorized.


## 28 October2026 — Stabilize routing and expose safe failures (4.4.3)

After reports of alternating resolution on refresh, a read-only synthetic reproduction
showed30:00→30:01→30:02 duration responses rejecting while30:00→30:01→30:00 succeeded.
The user authorized the proposed fix. Reserve60seconds when choosing a candidate
traffic-aware departure, still requiring a checked response at that exact departure
to predict on-time arrival. Keep3 outward/1 return request maximum, no transport retry
and no guessed/stale route fallback. Show fixed safe error reasons and archive only
ID/category/numeric HTTP status/time. Raw provider bodies and exception text remain
private. This reproduces a failure mode, not proof of a particular live Google failure.
No live Google/HA/credential/hardware or real notification access is authorized.


## 28 October 2026 — Snapshot schedules with adaptive live control

The user clarified that planning should use one snapshot, validate against that same
snapshot and execute the remaining schedule with live control until replacement.
Changing readings are expected in a dynamic system. ESS must remain active and EV power
must respond to fluctuating demand/production, with physical/source/peak permissions and
input/charger safeguards intact. These execution differences do not invalidate the
original schedule. Large/sustained load/PV mismatches and resulting inventory deviations
wait for periodic recalculation rather than independently requesting an extra solve or
revoking authority. Retain useful forecast corrections for the next planning snapshot.
Structural goal/configuration/permission changes and genuine safety/availability events
retain their separate handling; forecast mismatch is not inconsistent live measurements.

Keep full mathematical, source, required-grid and economic validation on the original
calculation inputs. Publication checks continued authority/usability and skips elapsed
instructions; do not substitute new EV/ESS stocks into that proof. Preserve original and
admission evidence separately. The proposed live remaining-grid-energy budget was not
adopted. Fresh-stock publication economic revalidation and4.4.1 energy repair are
superseded, as are the mismatch-only extra-solve/invalidation requirements from4.3.20.
See the maintained architecture for the complete current contract.

Initially documented without changing4.4.3. The user subsequently explicitly requested
implementation. Release4.4.4 validates frozen candidate/reference evidence, preserves the
original grid and records admission readings separately. It removes fresh-stock repair
and numerical mismatch/peak-only extra solves. Forecast issuances/corrections queue for
periodic work without revoking accepted authority. Current revision, connection,
input-health and physical/source/peak/charger protections remain; no live energy budget
is added. Verification uses deterministic fixtures and fake local services. Publication
through the existing release workflow is authorized; live installation operation is not.


## 28 October2026 — Focus goal cards on Planning (4.4.5)

The user requested space on Overview by removing duplicated goals, chronological goals
on Planning and trip consumption in kWh. They explicitly selected a bar only for the
earliest upcoming goal. Interleave all morning minima and explicit trips by deadline;
keep planned SoC/readiness for later goals. Label the first bar as current charge versus
its target, and hide it for unknown/unusable input. Show driving consumption separately
from reserve-inclusive departure SoC, using existing consumption/withdrawal arithmetic
in Planning cards, EV agenda and goal details. This is presentation only; it grants no
new control authority and changes no optimizer/persistence behavior.


## 28 October2026 — Explain actual planned session contributions (4.4.6)

After the user identified the meaningless Contributes to9shared goals count, read-only
inspection confirmed it included every later goal. The user explicitly authorized the
proposed replacement: named goals and planned kWh, accounting for existing battery
energy and other sessions; avoid repeated claims by non-consuming morning minima and
retain additional stored energy explicitly. Use chronological FIFO for explanatory
allocation, with initial inventory first. Driving/stored/unresolved energy is disjoint;
first target support is separately labelled, overlapping evidence. Keep unknown state
barriers and deadline causality. This does not alter the shared battery optimization,
charging behavior or permissions; physical future use cannot be measured in advance.
Per-task source labels and energy-profile visualization remain separate deferred work.


## 28 October2026 — Restore a near-term Overview goal list (4.4.7)

The user explicitly requested implementation of a revised Overview: remove Forecast
costs & energy assets and restore goal cards for only the next24hours. This supersedes
4.4.5's removal of Overview goals. Use the rolling interval(now,now+24 elapsed hours],
not the next calendar date; keep chronological ordering, trip kWh and the existing
single earliest-goal progress bar. Planning retains the full goals and cost breakdown.
No scheduling, goal persistence, control or cost arithmetic changes are authorized.


## 28 October2026 — Compact EV session details (4.4.8)

The user highlighted only the session title/time/battery kWh and named target rows as
useful, requested fewer words and scheduled implementation for21:41 Brussels. Keep one
compact Supports list; omit repeated target capacity, generic reasons and accounting/
retained-stock/caveat paragraphs. Distinguish driving from target support with short
labels when needed and combine same-goal rows without adding overlapping quantities.
Keep brief truthful legacy/unknown/no-named-goal fallbacks. The existing attribution
math/data and planner/control/permission semantics remain unchanged. The separately
queued charging-delay review is read-only and follows this cleanup's completed release.


## 28 October2026 — Restore early required charging (4.4.9)

The user reaffirmed the existing requirement to start useful required charging early
when waiting has no PV or genuine economic benefit, then explicitly requested the fix.
This is an implementation correction, not a new policy. A supplied frozen decision
allowed an identical6A session three hours earlier without a cost, peak, source or
continuity penalty. Joint continuity had omitted the former timing coefficients; its
score alone did not distinguish the schedules. Add a separate bounded timing preference
before grid certification, preserve the chosen sources/energy/cost/peak/service and
continuity, and retain a checked earlier incumbent when the timing solve times out.
Useful later PV still justifies waiting. Keep all holds, physical/permission/health
constraints and snapshot/live-control separation; no new live invalidation or extra
load-mismatch rescheduling. Release publication is distinct from installation deployment.


## 28 October2026 — Shorter EV waiting escalation and vehicle status

The user supplied incident a895697fea0047579922e7b33c8103dd for investigation and
confirmed that15minutes of waiting is no longer needed: at most a couple of minutes.
They identified a configurable FordConnect Query2026.10.7 vehicle charging-state
sensor as an additional direct fault signal. Source review confirms elvehcharging
passes through xevBatteryChargeDisplayStatus, including FAULT; it is cloud-polled.
The current log lacks that sensor, so it proves failed resumption after a commanded
stop but no specific Ford fault.120seconds is the proposed concrete waiting limit.
This discussion records requirements and evidence; application implementation/release
has not been authorized by the investigation question. Existing charger guards and
reported-fault reboot exclusions remain the starting contract.


28October2026 — The user subsequently said go, authorizing implementation of the proposed
120second persistent-wait limit and configurable Ford charging-state source in4.4.10.
Preserve90second confirmed-non-delivery, ordinary phase/start guards and ESS response.
ReportedFAULT latches without reboot; actual delivery resets waiting. Optional unknown
telemetry retains ordinary control and cannot qualify a reboot. HA read/report times
remain separate from unverified vehicle telemetry age. Keep the suspected initial-stop
cause out of this release; the supplied export does not prove its controlling branch.


## 28 October2026 — Fast startup recovery, retaining shutdown stop (4.4.11)

After discussing interruption risk, the user explicitly authorized the two-step approach:
first restore compatible saved schedules after fresh checks without waiting for optimization;
keep shutdown stopping until a charger-enforced offline bound is verified. Persist format1
execution identity alongside accepted evidence; check current configuration, requirements,
permissions, device/measurement health and coverage, independently of fresh optimization.
Do not re-evaluate historical economics on live inputs or replay elapsed work. Preserve
original plan evidence and existing live modulation/guards. A startup dry-run zero must not
become a new optimizer off hold. Legacy plans without settings identity need one new
calculation; do not invent the missing identity. A real fault, explicit Off or incompatible
context still blocks execution. Uninterrupted offline charging remains ARCH-021, not part
of this release. No installation operation or live provider/hardware access is authorized.


## 29 October2026 — ESS display direction (4.4.12)

The user explicitly authorized the visual ESS sign fix while preparing separate solar/
full-battery follow-up prompts. Positive displayed AC power means charging; negative means
discharge. Apply consistently to live cards and actual/planned/archived power charts, at
the frontend boundary only. Input mappings, source math, raw evidence and live controls
retain positive AC discharge. Do not invert SoC or energy totals. AC converter exchange
still excludes direct DC solar charging and may include DC passthrough; do not imply a
net battery measurement or implement the separate solar optimizer/accounting changes.
