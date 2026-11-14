# Current requirements and decisions

- 14 November 2026, task-specific implementation chats: retain ongoing architecture
  chats, but start a fresh implementation chat for each explicitly requested task.
  Automate creation, task-based naming, a short document-linked brief and registration.
  Keep related corrections/verification/releases in that chat. After verified completion,
  record the result, notify the registered architecture counterpart and archive the
  implementation chat; incomplete/blocked work stays open. Preserve archived evidence;
  do not delete chats. This replaces the original one-implementation-chat-per-release-
  stream lifetime. Fresh context is intended to reduce accumulated history and usage;
  handoffs reuse maintained documents, with no transcript copy or new handoff file.

- 13 November 2026, local development storage: the user approved moving private
  evidence, research, checkpoints, generated output, environments/caches and local
  history outside the Dropbox Git checkout, under the external Codex project-data
  workspace. New worktrees use Codex-managed locations; existing manual checkouts
  are preserved/retired through Git-aware operations. Cleanup depends on recorded
  verification/publication or extraction of failed-run diagnostic evidence, not
  arbitrary retention periods. Protect active/paused work, unresolved reproductions
  and original installation/user-supplied evidence; originals need explicit deletion
  permission. Preserve compact evidence and unmerged branches. See RUNBOOK.md and
  the 13 November WORK_STATE.md checkpoint for operational locations and migration.

- 11 November2026, EV-A012/EV-A013 scheduled implementation authorized: user requested
  "Schedule both of those for implementation in 3 hours" after finalizing both scopes.
  Schedule one start in the registered EV implementation chat, approximately17:24Brussels
  today: A012 first, then A013, with offline verification and ready-release publication
  under standing release permission. Automation implement-ev-a012-and-ev-a013 targets
  chat01a1b64b-a1fe-74d2-a393-afe7ed1aeb39. This supersedes the earlier no-authorization
  status for these scopes only; no live installation access or operation is authorized.

- 11 November2026, EV-A012 prepared scope: user brought the established baseline-
  reconciliation interruption from the EV charging errors chat here to finalize the
  work package and authorization. Preserve a still-valid task through usable stock
  corrections and normal recalculation, with updated remaining quantity and independent
  goal/source/peak checks. Preserve endpoint completion, real unknown/disconnect/fault/
  Off/revoked-permission stops, lower post-driving stock correction and no double credit.
  The software interruption trigger is established; later physical charging-failure
  causation is not. Separate from active EV-A011 and retry/reboot work. Architecture
  discussion continues: the user declined handoff pending understanding, then clarified
  that changed valid vehicle SoC must be trusted regardless of the estimate. No SoC
  agreement/magnitude gate or special blocking revalidation is intended; use normal
  task/source/peak guards and update remaining energy. The issue is revocation after
  accepting a new reference, not the discrepancy itself. Implementation/handoff authorization was supplied later by the scheduled request above.
  Further design direction: preserve the earlier accepted running profile and absorb
  routine corrections at the tail. User prefers shortening/extending the finish first;
  if constraints prevent that, adjust power/phases from the tail backward only as far
  as necessary. Deadline feasibility must be checked before deferring execution changes;
  normal live protection and endpoint completion remain immediate. User also permits
  earlier profile changes for clearly better solar/cost opportunities even when the
  tail-first plan can meet the deadline. Routine small corrections remain tail-first;
  the user subsequently confirmed current adjustment must always be preferred over
  phase switching for running-task corrections. Prefer an earlier feasible current-
  only adjustment over a later phase switch; unchanged-prefix length or a cheaper
  phase-changing candidate does not override that priority. Phase switching remains
  available when current-only adjustment cannot meet required service under hard
  constraints and permissions. Finish-time-only adjustment remains the first choice;
  the earlier solar/cost exception does not bypass the phase-preservation priority.
  Timeout fallback confirmed: if no checked replacement is available, keep existing
  instructions running only while independently valid, with normal expiry, updated
  remaining quantity, peak protection and completion stops. Timeout alone is neither
  a reason to stop valid charging nor evidence that phase switching is necessary.
  No authority extension or solve-budget increase is granted. Economic qualification
  confirmed: use the existing shared0.02EUR whole-plan comparison/cash envelope. Keep
  tail-first within that envelope relative to the feasible earlier same-phase option;
  permit earlier current adjustment when outside it, comparing matching required
  service/useful delivery and whole-system value. Do not accumulate another allowance
  per update or candidate. Implementation packages are separated: EV-A012 fixes the
  baseline-revocation defect; EV-A013 implements the running-task planning preference,
  with independent offline verification and bounded admission/handover. Architecture
  is ready for both; the subsequent scheduled request above supplies implementation/
  handoff authorization. Implemented together in4.6.12 with offline verification; no installation deployment.

- 11 November2026, EV-A011 EV-page cleanup: user selects the second preview,
  Beside sensors. Show its full diagnosis by default without an expander; the global
  banner stays brief. Stack Hardware control and Manual SoC with the same typography
  and colour. Manual mode reveals only the SoC field; entering a valid value counts
  as confirmation, superseding the separate A010 confirmation button. The field also
  displays updated system estimates; automatic updates must not act as human input
  or renew manual authority. Keep original car/sensor layout and existing bounded
  fallback/charger/source/peak/recovery rules. User approved the revised preview and
  explicitly authorized: "Good, hand it off for implementation". Authorization covers
  scoped EV-A011 implementation/verification and release under standing ready-release
  permission, with no live installation access, real notifications, hardware operation
  or deployment. Implemented in4.6.11; offline verified.

- 10 November2026, EV-A010 unreliable SoC feedback: user accepts detection of
  unchanged SoC despite sufficient measured charging, materially contradictory new
  SoC and missing battery evidence after a return. Report suspected unreliable
  feedback through one mobile alert plus a persistent in-app warning. Pause automatic
  EV work when no trustworthy reference is available; retain task/evidence and keep
  ESS and other independent functions working. User selects manual current-SoC input
  in the EV tab through a slider-style switch, with counter-based best-effort charging.
  On an issue, activation may be offered automatically but requires confirmation.
  Unplugging invalidates the reference. A several-hour timeout is suggested, but the
  user raises sleeping/offline nonresponse: requesting another reading must not
  routinely leave an already confirmed charge incomplete. No12hour hard cutoff was
  accepted. The user subsequently accepted manual authorization for the next charging
  goal, with a separate age reminder unable to interrupt it. Unplug invalidation and
  normal guards remain; do not automatically renew to later goals/repeated top-ups.
  User selects automatic recovery when new valid vehicle readings appear, with a
  recovery notification. Do not require matching estimated/manual SoC; correct
  measurements can legitimately contradict the estimate and must not be blocked by
  it. Reconcile without double credit. A changed valid vehicle-reported SoC is
  sufficient practical new-report evidence, compared with the last vehicle report
  rather than the manual/counter estimate. No extra sample agreement is required.
  User accepted an initial stuck-reading threshold of3percentage points of estimated
  battery gain from measured delivery, followed by15minutes without a changed report.
  This remains installation-unverified. User accepted showing reference age in the
  EV tab and requesting a refresh only when another charge needs a new reference,
  without periodic age-only phone reminders. EV-A010 scope/completion criteria are
  implemented in4.6.10 as specified in ARCHITECTURE.md. The user subsequently authorized the implementation
  handoff: "You have permission to hand it off". This covers EV-A010 implementation,
  verification and release under standing ready-release permission, with no live
  installation access, real notifications, hardware operation or deployment.

- 10 November2026, EV-A008 stock follow-up: user authorized handing the confirmed
  17% versus retained50.1% discrepancy and export to the existing EV implementation
  chat for this scoped correction. Reconcile all observed returns, including
  unplanned driving, preserve delivered-energy continuity and correct genuinely
  changed lower SoC without double credit. Ford SoC has no guaranteed physical sample
  timestamp: distinguish changed-value evidence from precise measurement timing;
  anchor unknown overlap conservatively at a valid counter and retain uncertainty.
  Repeated old values must not reset stock, and insufficient evidence cannot satisfy
  the daily goal from retained high inventory. Existing charger protections remain;
  retry/reboot policy, live HA/database, hardware and deployment remain outside scope.

- 9 November2026, EV-A009: after mapping eto and restarting, the user confirms both
  the repeated EV-progress warnings and missing red quarter-end marker recovered.
  They requested one work package for grouping the common fault into one actionable
  warning and keeping grid projection independent of EV availability where the grid
  instructions remain usable. They authorized scheduling its implementation handoff
  in1hour10minutes. Scope and acceptance are in ARCHITECTURE.md; no new control,
  notification or peak policy is selected. Preserve unavailable forecasts when
  executable coverage cannot be established rather than plotting invalid instructions.
  Implemented in4.6.8 with a live presentation view, independently exposed resource
  authority and whole-interval executable coverage. Verified with fake/local sources.

- 9 November 2026, V45-A003 recorder readiness feedback. The user wants visible
  confirmation of idle detection and the latest power while manually arming a recording.
  They chose one clear location rather than repeating it on the collapsed card: place
  the live status beneath Record next cycle. Preserve current recorder detection rules.
  The user subsequently authorized implementation handoff only after the V4.6 EV
  implementation finishes. EV-A008 was the active task at authorization; no early
  dispatch or concurrent implementation of this feedback change is authorized.
  Its completion/release was confirmed on 9 November as4.6.6/068307c with CI and image
  publication passing, satisfying the condition for the recorder-feedback handoff.
  Implemented in4.6.7 using existing capture/read timestamps and the15second gap bound,
  with browser monotonic/request-age checks and no new detector/HA freshness policy.
  Both dashboards retain drafts and clear misleading Ready on missing/stale evidence.
  Verification uses local fake reads, status failures and recorder restart only.

- 9 November2026, EV-A008 charging-progress source: the user confirms both go-e
  energy sensors are available and selects cumulative Total energy (`eto`) as the
  primary measurement, since either counter requires a progress baseline. This
  supersedes the earlier preference for Energy since connected (`wh`).
  Retain the progress reference needed to avoid crediting energy already included
  in the SoC baseline and to preserve task progress across recalculations/restarts.
  The user accepted pausing EV after the existing measurement watchdog when neither
  usable meter progress nor fresh vehicle SoC is available; retain the task and
  progress, show a concise warning and keep ESS independent. Temporary counter gaps
  retain their reference; unexplained resets do not invent delivery or erase credited
  progress. New SoC reconciliation must avoid double credit. No additional phase-
  stability preference is approved: correct execution commitments and transition
  timing under the existing rules. After reviewing the four-part scope, the user
  authorized EV-A008 implementation and release on9November: “Ok, hand it off”.
  Implemented in4.6.6 with a persistent counter ledger, explicit accepted-trajectory
  handover and independently audited transition delivery. Verified offline only.

- 9 November 2026, V45-A001-P2 inline program actions. The user approved Add/Rename
  icons beside the washing-machine program selector, replacing it temporarily with
  a name field and Save/Cancel. Rename uses the currently selected program; Add selects
  the created program. Replace the separate management fold-outs. The user then
  explicitly authorized this separate implementation handoff: "yes, hand it over".
  Implemented in4.6.5 after incorporating main4.6.4. The shared row retains P1 metadata
  APIs/identities and original edit revision, disables recording while editing and
  preserves name/notes/trim drafts. Verified with local synthetic services only.

- 8 November2026, dashboard presentation and EV-A007: the user prefers minimal
  visible text and visual cues where suitable. Across the dashboard, applicable
  measured values/states should open their actual HA sensor's standard more-info/
  history. Keep the current-quarter value's location, give it a red icon and the
  real mapped quarter-demand sensor action. Remove the verbose quarter paragraph
  from the cursor popup. Alternating quarter shading is approved. The user selected
  Long dashes from the visual alternatives and requested a slightly increased peak
  line weight compared with the current implementation. Keep normal power traces
  light, the same red grid/peak colour and existing label. The user subsequently
  authorized handoff for implementation and release: “Hand it over”.
  Implemented in4.6.4; verified offline with real source IDs in a synthetic HA harness.

- 8 November2026, EV-A006 peak display: retain the same red colour for grid power
  and peak, use a slightly heavier dotted peak line and lighter normal power lines,
  and retain the existing label. Keep the monthly-peak indication in its current
  Grid-box position and append the current-quarter meter value to its right on
  the same bottom row, as shown in the user's screenshot. No separate panel beside
  the graph. Shade clock-aligned quarter hours with subtly alternating tints,
  distinguish the current quarter and show its projected final average with a
  simple marker at quarter end. The user subsequently explicitly authorized
  implementation and release: “Push it for implementation and release”.
  Implemented in4.6.3 after integrating4.6.2; verified with local synthetic data.

- 8 November2026, V45-A001-P1 implementation in4.6.2. Reconciled released main4.6.1
  before implementation. Washing-machine creation/rename stores stable identities and
  display names only; existing captures/averages and frozen plans remain unchanged.
  Names normalize Unicode/whitespace and reject case-folded duplicates. Shared forms
  preserve trim drafts and revision guards; Bosch remains HA-managed. The one-time
  scheduled start was consumed and its automation removed. Verified offline only.

- 8 November 2026, V45-A001-P1 authorization and delayed start. The user explicitly
  authorized implementation of washing-machine program creation/renaming and requested
  it start in 1 hour and 11 minutes. A one-time task targets the existing registered
  implementation chat at 19:33:57 Europe/Brussels. Preserve the scoped requirements,
  existing recordings and Bosch catalogue; broader library work remains separate.

- 8 November 2026, requested user-created programs. The user wants to add programs
  from the UI for appliances such as the washing machine. Exclude the Bosch dishwasher,
  whose programs are already known through HA. This narrows the next V45-A001 discussion
  to program creation using the agreed name/recordings model. The user confirmed that
  renaming programs is included. Preserve program identity and existing recording/
  average links when renaming. V45-A001-P1 is the scoped creation/rename follow-up;
  broader appliance CRUD and program removal are not implicitly authorized.

- 8 November2026, EV-A003–EV-A005: the user authorized scheduled implementation
  and continuation through acceptance and release readiness. EV-Q020 confirms that
  protected allocations mean required service, hard reserves and binding commitments;
  optional nominal ESS dispatch is not immutable. Future AC/DC PV stored before EV
  use receives the20% margin once; initial known stock retains ordinary credit.
  Restricted witness failure cannot establish general cautious infeasibility.
  Preserve full joint alternatives and independent source/causal audits.
  No live installation action is authorized.

- 7 November 2026, EV deadline protection under PV uncertainty: the user chose
  a 20% margin. Credit 80% of remaining usable forecast PV before the deadline,
  with full credit for measured energy already delivered. The user accepted using
  the full forecast for economics and the cautious forecast to check how long
  grid charging can be deferred. Bring grid charging forward when further waiting
  would threaten the cautious deadline within the authorized limits.
  If only the cautious case needs a higher peak, keep the current limit and warn
  that the safety margin cannot be met. Send one mobile notice and show a persistent
  in-app warning for the affected deadline while unresolved. A nominal shortfall
  continues through the existing approval process.

- 6 November 2026, EV charging sources: the user accepts a split when it allows
  useful partial PV charging alongside the necessary grid portion. ARCH-026 will
  explore deterministic limits before the MILP.

- 6 November 2026, EV execution continuity: the user accepts interruption by a
  materially better plan and wants to limit stops followed by a near-term restart.
  The user confirmed that getting ahead of the forecast is irrelevant to whether
  an active session should continue while authorized charging work remains and live
  limits permit it. The user accepted a 15-minute review window for a replacement
  plan that proposes a stop and restart. Prefer a feasible continuation, including
  at a lower current, when it delivers the same required outcome within the limits.
  Live protective pauses can take effect immediately. Discuss how to retain the existing
  earlier required grid charging preference when considering the ARCH-026 rules.

- 6 November 2026, live peak protection: the user revised the priority for an
  unexpected threatened peak. Reduce or pause EV charging first. If that cannot
  protect the quarter, use available ESS discharge, including energy reserved
  for a later forecast peak as needed. The current quarter takes priority.

- 8 November 2026, EV-A002 / V4.6: the user authorized release after V4.5 was
  considered complete enough. V4.6 incorporates4.5.8. Measured monthly-peak alerts
  fire on the first billable rise above the2.5kW floor; further rises remain silent
  until15minutes without an increase. No final update is sent. State and failed
  delivery retries survive restart; advance approval remains separate. Recorded
  sensor history supplies the Overview peak steps, including zeros and month resets.
  This implements the6November design and7November implementation authorization.
  No live installation operation or deployment is authorized.

- 8 November 2026, ARCH-018 implementation (4.5.8; offline verified). Saved selections
  update one physical recording in place, preserving raw measurements and inclusion;
  first review still includes the new cycle. Consolidate historical copies by capture
  provenance using the latest saved trim and preserve included/excluded state. Historical
  IDs alias the surviving recording; accepted-plan evidence is immutable. Queued M2
  profiles detect selection changes even with unchanged recording IDs. Compact foldable
  program groups and one in-place original trim editor are shared by both dashboards.

- 8 November 2026, ARCH-018 implementation authorization. The user explicitly
  approved handing the completed recording-list/trim package to the registered
  V4.5 implementation chat as separate scope from M2. Includes foldable program groups,
  one expanded recording, existing Start/End controls, in-place trim saves and latest-
  saved-trim consolidation. General task-chart/comparison ideas remain outside scope.

- 7 November 2026, M2 implementation authorization. After reviewing the summarized
  work package, the user explicitly requested the implementation handoff. Scope is
  Ready/deadline controls, joint Bosch/EV/ESS planning and guarded execution, the
  seven-day measured constant background estimate with the proposed 30-minute refresh,
  per-run conflict choices/notifications/queued waiting, persistence and offline
  verification. Scope and criteria are recorded in ARCHITECTURE.md. The user selected
  energy-profile visualisations as the next architecture topic after the handoff.

- 7 November 2026, project-wide conversation flow. The user requires each response
  to include the next substantive item, question, suggestion or concrete next action
  while work remains. Acknowledgement-only prompts should not be needed to continue.
  State completion clearly when the current task is done. Recorded in root AGENTS.md.

- 7 November 2026, dishwasher deadline/peak conflicts (V45-Q018). The user wants
  to choose for each situation, using its timing and peak consequences. They declined
  selecting a permanent preference between a later finish and higher-peak approval.
  They accepted showing a later finish within the existing allowance and an on-time
  option requiring approval, with the required peak and estimated cost where available.
  Deadline changes and cancellation are also offered. The user accepted showing the
  alternatives on the appliance card, sending a notification through the configured
  phone channel and keeping the run queued while the conflict remains unresolved.

- 7 November 2026, V45-Q017 Bosch idle start fix. The user confirmed that the mapped
  active-program entity reports unknown while listing Eco 50 as available. They
  authorized the V4.5 implementation chat to fix the capability parsing and verify
  the reported case offline. Preserve valid options separately from the empty current
  active program and retain the existing command guards. This is a scoped M1 repair.
  Implemented in4.5.6;
  unknown current active state retains validated capabilities without inventing execution.

- 2 November 2026, V45-A002-M1 implementation: the user explicitly authorized cards,
  automatic recordings, review/permanent deletion and manual Bosch controls in the
  registered implementation chat, after reconciling primary-checkout requirements.
  Implemented as4.5.5 with fake/local verification. M2 scheduling and full V45-A001
  library management remain pending. Capture uses exact HA program identities; legacy
  Heavy is not treated as Intensive. Manual Start now does not alter native delay:
  require confirmed zero seconds and idle/door/remote/hardware guards; reconciliation
  of an existing appliance delay remains M2 work. No live installation operation or
  deployment is authorized by implementing these controls.

- 2 November 2026, Bosch delivery milestones: the user approved two stages for
  V45-A002. M1 provides the shared appliance cards, Bosch program/status feedback,
  automatic Refoss recordings and recording review/delete. M2 adds Ready/deadlines,
  joint optimization with EV/ESS and managed execution, including background-demand
  separation. Collect useful Eco/Intensive profiles through the first milestone while
  developing scheduling. Generic-library work is not withdrawn. The split is agreed;
  implementation has not been authorized. The user accepted including manual program/
  modifier controls and Start now and record in M1, completing the initial measured-
  profile workflow without scheduling. M1 scope/criteria are in ARCHITECTURE.md;
  application implementation starts only on the user's authorization.

- 2 November 2026, shared Appliances page: the user wants most, potentially all,
  appliances on the same page with two stages. The initial view consists of relatively
  large per-appliance cards with an icon and the most relevant information/controls.
  Clicking a card enlarges that original card in place to show the extra information;
  it does not navigate to another page or open a popup dialog. At most one card is
  expanded; opening another collapses the previous one. The Bosch card displays the
  program as a selector, defaulting to Eco for a new run while preserving an existing
  explicit choice/actual run. The user liked the initial interactive design preview.
  Bosch finish choices are Tomorrow 12:00 (noon), Tomorrow 18:00 and a custom date/time
  icon with a small popup. Presets use the next installation-local calendar date;
  they select latest finish and do not submit Ready. The custom popup uses a directly
  selectable calendar, limited to today through seven days ahead, with a time-picker
  wheel alongside it. The user clarified that only the rolling date window should
  be shown, not a full month with disabled dates; the limit exists to keep the picker
  simple. The user approved the corrected compact rolling-date picker with the
  current time wheel retained. No default deadline is chosen.
  Remaining card content and expanded layout remain to be agreed. This is design
  direction, not implementation
  authorization.

- 2 November 2026, Bosch dishwasher direction (pending V45-A002): following a
  user-supplied HA capability handoff, use a dedicated Bosch SMS6ZCW08E integration
  direction rather than assuming manual delayed start for this appliance. Official
  Home Connect is connected and power-on from off is user-confirmed. Program/delay
  controls are exposed and assumed usable; delayed execution and timing precision
  remain untested. The next stated focus is reviewed power recordings for the
  available programs. Eco is used roughly 90% of the time, otherwise most likely
  Intensive. Keep Extra dry/Half load/Vario speed+ controls available but do not
  adjust the planning profile for modifiers; the user may add combination-specific
  profiles later. A Refoss measures the dishwasher; its HA power entity is not yet
  identified here. The HA power switch is not a consumption sensor. The user chose
  automatic run capture using Bosch feedback and Refoss measurements, including
  panel/app-started runs, without per-cycle arming. Review before average inclusion
  and completeness/coverage requirements remain. Scheduling handoff: load, select
  the program and set a latest end date/time; from confirmation the manager may
  start immediately or later at its discretion. No additional earliest-start field
  is required. The user permits start-time changes while waiting without further
  confirmation, respecting the selected program/deadline. Once started, the cycle
  runs uninterrupted. For an impossible finish deadline, warn when the deadline is
  entered with earliest expected finish and start-as-soon-as-possible behavior.
  The user confirmed that proceeding with Ready and the unchanged deadline authorizes
  that fallback, without an extra countdown or confirmation. Opening the door while
  waiting keeps the queued run but blocks starting; closing it with remote-start
  permission available automatically resumes management without another Ready action.
  Explicit cancellation remains available. This does not select a policy for a
  running cycle interrupted by opening the door. The user selected EnergyManager-held
  timing and a Start command at the chosen moment, without programming a native delay.
  Waiting through a controller outage is acceptable; outage-independent starting is
  not required. Manual program changes while queued are adopted and replanned against
  the same deadline without another Ready confirmation; the user considers the case
  unlikely but accepts this default. Learn actual per-program cycle duration from
  recordings and use that estimate without extra scheduling margin; timing is
  generally not critical enough to justify padding. Continue planning estimated
  completion by the deadline. Until a program has a usable reviewed profile, offer
  Start now and record; enable optimized scheduling after review/inclusion of that
  first usable recording. No provisional manual estimates are required. Pre-existing
  device delays remain unresolved;
  generic library work has not been withdrawn. This is not code or live-operation
  authorization. Full capability evidence is in ARCHITECTURE.md.

- 1 November 2026, V4.5 appliance library (V45-A001): the user agreed to a
  user-managed appliance/program library with planning support based on operating
  behavior. Initially support manually started, uninterrupted program cycles:
  reviewed power profiles, earliest start/latest finish, manual or user-set delayed
  start and fixed confirmed commitments. Appliance names do not determine support.
  Other equipment may have recorded profiles before its scheduling behavior is
  supported; Mazak, thermal loads and modulated charging need their own treatment.
  Preserve existing library data. Recording removal and program management are
  identified gaps. The user subsequently chose permanent recording deletion after
  confirmation, including stored samples, separate from removal from an average.
  Deleting an included recording removes its average contribution. Program/appliance
  removal and dependent-data handling remain open. This is design agreement, not
  implementation authorization.

- 1 November 2026, V45-A001 configuration before UI/UX: appliance name and a
  predefined operating behavior; program name and multiple recorded profiles.
  No program variants: materially different cycles can be separate programs.
  Each planned run selects a program and supplies behavior-dependent options such
  as readiness times. Directly controlled appliances may need fewer user inputs,
  but their requirements/support and the predefined behavior choices remain open.
  Define the needed options before UI/UX. No direct-control implementation is
  authorized by this design discussion.

- 1 November 2026, workflow adoption and document names: apply the paired-chat
  workflow to the remainder of V4.5 and subsequent release streams. Reuse the existing
  V4.5 implementation chat; architecture assignment is recorded in WORK_STATE.md.
  Rename architecture/Architecture_Proposal.md to ARCHITECTURE.md and DEFERRED_WORK.md
  to BACKLOG.md, retaining the maintained content and updating navigation. DECISIONS.md,
  WORK_STATE.md and the supporting document names remain unchanged. Historical paths
  in prior checkpoint evidence and pinned Git-history links retain their original names.

- 1 November 2026, initial development workflow (Setup V2; implementation-chat
  lifetime superseded on 14 November): one architecture chat and one
  implementation chat per release stream, retained through its patch releases;
  multiple release streams may develop concurrently. The user creates and starts
  implementation chats. Shared project documents carry requirements and results.
  Architecture continues during implementation, while each authorized task retains
  its scope until the user authorizes an amendment or follow-up. Design agreement
  alone is not implementation permission. Paired chats may directly message and
  trigger each other's questions/replies; architecture may clarify existing decisions,
  but new behavior, requirement changes and expanded scope return to the user.
  Application releases reach main in version order. The newer implementation chat
  incorporates earlier releases, resolves conflicts and verifies the combined result.
  Approved documentation may reach main before code, with pending behavior labelled.
  Use release sections in WORK_STATE.md for coordination rather than duplicate
  architecture specifications or per-release handoff documents. Operational rules
  live in the root AGENTS.md. This workflow does not authorize a new application task.

- 31October2026,4.5.4: user reported that the trim targets were tiny and would not
  slide, and confirmed this happened on saved recordings.4.5.3 rendered those bounds
  read-only despite their draggable appearance. Saved ranges now edit directly with
  large labelled grips; saving creates a retained trim revision, replacing the same
  physical cycle's contribution. Previous data remain inspectable/restorable, and
  different trims of one capture cannot acquire multiple weights in its average.


- 31October2026,4.5.3: user authorized thinner power plots and appliance review cursors,
  linked draggable trim bounds and seconds, and Overview-style zoom/pan. Confirmed
  multiple recordings should combine into an averaged program profile. Align trimmed
  starts in real elapsed time; completed cycles contribute zero after their selected
  end. Do not stretch heating phases. Inclusion is explicit and original cycles remain
  available; existing one-cycle selections upgrade without adding other saved runs.


- 31October2026,4.5.2: user authorized replacing the Overview grid import/export
  energy integrators with two P1 energy mappings and using the sensor-derived totals
  wherever those recorded subtotals are consumed. The supplied P1 screenshot shows
  matching Cumulative Active Import/Export registers and import-only Today; use the
  combined cumulative pair with local-midnight baselines. Retain non-grid integrators
  and instantaneous P1 power for planning/control. Sensor entity IDs remain user-selected.


- 30October2026,4.4.17: user approved correcting smoothing's feasible region after two
  supplied decisions demonstrated valid continuous schedules rejected by fixed ESS
  inventories/per-window import caps. Retain other EV work/quantity and all original
  requirements/authority; keep sources/ESS joint across the horizon within the shared
  original cash/comparison envelope and rolling checks. Preserve attempt history and
  unresolved timeouts independently from coverage. No live-control or replan change.


- 29October2026,4.4.16: user authorized a general full-horizon continuity procedure
  after repeated first-window fixes failed to cover1November. Account for every
  interval/window, test equivalent opportunities on all seven forecast days, preserve
  improvements through certification and archive unfinished bounded searches honestly.
  Keep original snapshot/constraints/global time budget and one shared0.02EUR envelope;
  no runtime economic recheck or reschedule change. A fixed-phase candidate can fail
  without proving pauses necessary. Preserve required readiness up to its target,
  allowing surplus to move; refine sources/ESS with the EV profile fixed before
  boundary preservation, inside the original model and authority.


Maintained 25 October 2026 for 4.3.2. This records confirmed product preferences and
implementation outcomes from the V4 implementation chat. It supplements the complete
original [architecture decisions](architecture/Architecture_Decisions.md); the
[maintained architecture](ARCHITECTURE.md) describes the resulting implementation.
New explicit user instructions take precedence. Deferred ideas are not authorization.

## 10 November 2026 — EV trip calendar direction (ARCH-022; pending)

Confirmed 12 November calendar creation gesture: dragging/selecting an empty time
range opens a new-drive detail editor with that range as fixed start/end times. The
user supplies locations or distance before saving; selection alone does not save a
trip. The combined calendar/detail-editor preview was accepted as a reasonable
starting point, not approval of every illustrative control or implementation.

Confirmed 12 November final view choice: build EnergyManager's own calendar view,
replacing the earlier preference for a Google iframe. Let the user select which Google
calendars appear; ordinary appointments are read-only context, while EV drives can be
dragged/resized and opened in EnergyManager's detail form. Keep direct bidirectional
Google synchronization and primary local trip storage. A cross-origin Google iframe
cannot be modified by HA to replace its internal dialogs; no supported Google embed
click/editor override was found. FullCalendar Standard is a candidate rendering and
interaction library selected by the user as the basis for the next mockup and planned
view. Standard features are sufficient in the current design; Premium is not agreed.
Exact version/packaging remain engineering details. This remains design authorization
only; no application implementation has been authorized.

12 November UI correction: show ordinary calendar appointments alongside drives, with
calendar-based dragging and start/end resizing as the primary placement workflow.
Keep the form for details. Prefer Google embedding, but the user accepts similar
functionality built in HA as fallback. This supersedes the form-first design and the
previous exclusion of a custom calendar fallback. It authorizes design, not coding.
Public documentation does not establish inline drag/resize in Google's embed; see the
research qualification and library fallback in ARCHITECTURE.md.

Confirmed 12 November event titles: default to Drive to [city], with destination
city filled automatically. For distance-only drives without a destination, use
Drive · [distance] km. An optional custom-title field was proposed but not confirmed.

Confirmed 12 November distance entry: the HA trip form supports an optional distance
in km, both to override automatic route distance and to describe a drive without a
location or a round trip whose origin/destination are identical. An entered nonzero
distance must not collapse to zero merely because endpoints coincide. Without locations,
assume departure from home and return home; entered start/end define the away period.
Distance-only drives require both start and end times; there is no route from which to
calculate the missing time.
This explicit distance-only mode is valid, unlike a malformed routed event with missing
endpoints. Do not invent a route duration or a calculated-duration warning where no
route is known. The Google Calendar representation of distance-only mode and overrides
must be defined alongside From: serialization. A manually entered distance stays
fixed during ordinary automatic route refreshes until the user explicitly chooses
Use calculated distance. This does not change the agreed source-match regeneration
exception for referee drives.

12 November storage clarification: the local EnergyManager database is the primary
trip store. Google Calendar supplies visualization and an editing frontend with changes
flowing both ways, not display-only publication. This supports independent local
management and leaves future statistics possible; statistics and historical retention
policy remain outside the agreed implementation scope. Local trips survive disconnect.
On disconnection, leave already published Google events untouched. The user expects
reliable operation and requests a visible alert for lost connection, without excessive
disconnect workflow design. Preserve the prior distinction between transient in-app
sync status and phone alerts requiring user action. Calendar switching remains open.

Confirmed transport: use Google Calendar push notifications as the primary change
signal, plus periodic synchronization to recover missed notifications. The user has
domains, DNS and a reverse proxy available for a dedicated public HTTPS webhook.
Endpoint configuration/verification remain future work; no live changes authorized.

11 November presentation clarification: pursue Google Calendar embedding in HA.
If editing in the embed is unavailable, the user will open Google Calendar themselves;
do not add an Open in Calendar button. Integration-source research and the direct API
findings are recorded in ARCHITECTURE.md. The user confirmed EnergyManager's own
direct Google Calendar API connection, authorized by the user during setup, with trip
controls remaining in HA. This is a design decision, not live-access or coding permission.

Confirmed 10 November 2026: improve creation, deletion and adjustment of EV trips
through a dedicated EV trips calendar. Allow edits in both Google Calendar and
EnergyManager with bidirectional synchronization. Explore only calendars visible in
Google Calendar; provider compatibility and write permissions remain unestablished.
Each event represents one actual drive, with outward and return as separate events.
Event start/end represent departure and expected arrival. EnergyManager automatically
creates outward and return drive events from referee appointments, calculating both
ends from routing. Keep the existing arrival target of 60 minutes before match start;
the pending return default is departure 2.5 elapsed hours after match start, superseding
the shipped two-hour default only when this scope is implemented. The user can move,
shorten or lengthen either generated drive event. If the source match changes time
or location, regenerate its drives even if manually adjusted and inform the user that
this happened. If the match disappears, ask whether to remove its drives; retain them
and their planning requirements unless the user confirms removal. Routine route-only
refreshes preserve manually overridden departure and arrival times. Notify the user
when calculated drive duration exceeds the manually allotted event duration by more
than 10 minutes; exactly 10 minutes does not trigger this warning. The warning does
not automatically change the event times. Deliver manual-duration warnings and
match-change notices through the existing EnergyManager phone notification destination
and an in-app notice. Send the duration warning once per trip and keep it visible
in-app while applicable; editing the trip again allows a new warning if the threshold
is exceeded. Routine refreshes do not repeatedly notify for that same edit. Repetition
of match-change notices and pending-confirmation presentation remain open.
Manually created drives support any user-selected origin and destination, including
drives between two places away from home; do not assume every leg starts or ends at
home. Suggest the previous drive's destination as origin, falling back to home;
the user can override this suggestion.

Confirmed 11 November: normal trip creation takes place in EnergyManager's HA
interface, with place search for both endpoints rather than requiring full typed
addresses. Google Calendar also supports adjustment and deletion. Direct creation
there remains an advanced option requiring the complete event syntax. Use the built-in
event Location as destination and a readable From: line in the event description for
the origin. HA writes that line automatically from the selected origin; direct creation
in Google Calendar requires the user to supply it. Exact parsing/serialization details
remain to be specified. Moving a drive manually changes only that drive. Leave other drives
untouched even if this creates overlaps or an inconsistent location sequence; the
user accepts responsibility for that manual adjustment. Changing a drive's destination
in Google Calendar also preserves its event times. Recalculate distance and required
energy for the new destination and apply the existing more-than-10-minute duration
warning rule; do not automatically resize or move the event.

Confirmed 12 November invalid endpoints: if a Google Calendar event has a missing or
unrecognizable origin/destination, mark it as needing correction without inventing a
route. For an existing trip, retain its last valid planning data until corrected.
A new event without valid endpoints has no invented planning route or energy estimate.
Send one notification to the existing phone destination per invalid edit, alongside
the in-app correction status; repeated synchronization of that edit must not resend it.

Deleting an automatically generated referee drive keeps it deleted while its match
remains in the source calendar; ordinary synchronization must not recreate it. Provide
an always-available Regenerate action per match, including when its drives have been
deleted. Explicit regeneration restores missing drives and regenerates/updates that
match's trips. A later source-match time or location change automatically regenerates
both drives, including deliberately deleted ones, and notifies the user under the
match-change policy. Deletion suppression applies only while that source match is
unchanged; it does not prevent this automatic regeneration.

Confirmed 11 November conflict policy: resolve competing HA/Google Calendar edits
automatically, without asking the user to select a version. Prefer a manual edit over
an automatic system adjustment when distinguishable; when both edits are manual,
the most recent wins. The explicit source-match time/location change policy remains
an exception: regenerate both drives and notify, even after manual edits or deletion.
Technical detection, ordering and fallback details remain to be specified.

Confirmed 11 November recurrence: support creating recurring drives in the HA
interface. For edits and deletion offer This drive and This and following drives;
leave past occurrences unchanged. This refines the earlier entire-series deletion
request: no separate action to delete past drives is needed. Initial recurrence
supports every N weeks on selected weekdays, with an optional end date.

Confirmed 11 November HA trip timing: offer Depart at (calculate arrival), Arrive by
(calculate departure), and fixed start and end times supplied by the user. Fixed times
remain user-controlled and use the agreed duration-warning policy. Manually moving
or resizing a drive in Google Calendar switches that occurrence to fixed times;
the user can restore Depart at or Arrive by in HA.

Confirmed 11 November referee endpoints: generated referee drives always default
to home -> match and match -> home. Do not infer chaining or merge trips based on
other scheduled destinations. This is separate from the origin suggestion for manually
created drives. The user combines trips manually by changing endpoints or deleting
and creating/replacing drives.

Confirmed 11 November synchronization outage behavior: if Google Calendar is
temporarily unavailable, continue planning from the last synchronized trips and allow
local HA edits. Show a visible synchronization status with pending changes, then
synchronize after connectivity returns under the agreed conflict policies. A failed
calendar read is not evidence that trips or source matches were deleted.

Confirmed 11 November calendar setup: the user creates the dedicated EV trips
calendar in Google Calendar and selects it in EnergyManager. EnergyManager does not
need to create that calendar during setup.

Confirmed 11 November reverse-drive action: offer Add reverse drive, creating a
separate event with origin and destination swapped. Initially place it immediately
after the original drive, with an option to place it immediately before instead.
Initially copy the original drive's event duration; a separate reverse-route duration
calculation is not required to place the event. The user can then move it or edit its
times; no ongoing timing link is specified. For a recurring drive, also offer creation
of a recurring reverse series using the same recurrence schedule, rather than only a
single reverse occurrence. After creation, outward and reverse drives/series are
independent: editing or deleting one does not change the other. The source-match
regeneration rules for automatically generated referee trips remain separate.

Confirmed 11 November home identity: use the existing HA Home location as the
home reference for trip endpoints, with a Home shortcut in the trip editor.

Confirmed 11 November planned availability: after a drive ends away from home,
assume the car remains away and unavailable for home charging until a later drive
returns it home. Actual observed plug-in at the configured home charger overrides
that inferred absence; a missing planned return must not prevent home charging when
the car is actually plugged in. Existing measurement, charger, permission and control
safety gates still apply; this does not authorize hardware actions during development.

Confirmed 11 November publication horizon: create calendar drives for all known
referee matches, independently of the seven-day charging-planning horizon. Do not
impose the proposed 90-day calendar publication cap. For distant matches, publish
provisional departure/arrival times using estimated travel duration. Restrict ongoing
traffic-based route refreshes to the next seven days; do not repeatedly update distant
events with traffic estimates. No provisional-travel-time note is needed in the
calendar event. Refine automatic times within that window while
preserving manual timing overrides under the agreed rules. The initial distant-trip
estimate method and bounded handling of unending source recurrence remain technical
questions; all known matches does not specify infinite recurrence expansion.

Confirmed 11 November normal-operation notifications: ordinary automatic traffic
time updates and successful routine synchronization are silent. Do not notify merely
because normal system operation occurred. Retain the explicitly agreed source-match
change notices and duration warnings. Temporary calendar connection outages appear
in sync status without a phone notification. Send a phone notification when user action
is needed, such as reauthorizing calendar access.

Confirmed 12 November migration scope: do not implement copying existing manual
trips into the dedicated Google calendar for this initial integration. The user reports
no manual trips at present, not a guarantee that none will exist at connection time.
This does not authorize deleting or overwriting any existing manual trips.

Confirmed 12 November referee planning ownership: when the new generated calendar
drives are enabled, they replace the current referee-import trip entries in charging
planning. The referee calendar remains the source for generation, not an additional
set of energy withdrawals/away periods. Count each journey once; do not plan both
the legacy imported round trip and the new drive events for the same match.

13 November implementation clarification: FullCalendar Standard is the selected
own-view implementation, with primary local storage and direct Google editing.
V4.7 offline implementation was authorized on 12 November; final release verification
is in progress. Older embed/unassigned wording above is historical and superseded.
Engineering contracts and evidence remain in ARCHITECTURE.md and WORK_STATE.md.


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
  [maintained architecture](ARCHITECTURE.md). Its current
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
  [architecture document](ARCHITECTURE.md). The user explicitly
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


## 29 October 2026 — Reliable optional solar capture (4.4.13)

After comparing two supplied decisions, the user authorized stronger starting candidates,
reserved solar refinement time and retaining the best checked candidate through solver
timeouts. Use bounded neighborhoods across the unchanged full horizon and the same frozen
snapshot; preserve future supply, existing economics, 80%/exceptional health checks and
source/permission/continuity rules. Prioritize the immediate opportunity under short
budgets before exceptional100% investigations. Existing required-grid timing remains.
Do not add a runtime economic recheck, arbitrary maximum time at full ESS or stored
ESS-to-grid export. Both private supplied exports are offline regression evidence;
public automated tests use synthetic scenarios, without publishing installation telemetry.


## 29 October 2026 — Consistent grid/ESS direction arrows (4.4.14)

The user explicitly requested right arrows for import/charge and left arrows for export/
discharge. Apply that convention to grid and ESS summary markers in the shared renderer,
superseding the earlier opposite grid and vertical ESS arrows. Keep numeric signs, daily
energy totals, forecast comparison arrows and all planner/control behavior unchanged.


## 29 October 2026 — Continuous fallback for every active charging limit (4.4.15)

The user authorized extending the missing optional-capture continuity fallback and
explicitly required coverage beyond80%. Selected charging work activates the candidate;
inherit the model's actual ceilings and required-target authority, including authorised
higher ceilings, without granting new charging permission. Reserve bounded continuity
time inside solar refinement so its economic candidate is not left fragmented merely
because the full search timed out. Preserve selected quantity/future supply, one carried
economic/cash allowance and existing necessary pauses/live control. The supplied frozen
decision is private offline evidence; public tests use deterministic synthetic cases.

## 25 October 2026 — V4.5 / ARCH-005 profile preparation

The user selected ARCH-005 for V4.5, requested a separate worktree/branch and authorized
code writing from 23:30 Europe/Brussels tonight, after discussion of required decisions.
Initial focus: capture and store per-machine/per-program power profiles. Dishwasher:
Eco and possibly Heavy. Washing machine: whites 60 C, darks 40 C, darks 30 C, coloured
40 C. Mazak is intentionally modelled with provisional flat averages: Program 2,500 W,
Light 3,500 W, Production 7,000 W, with later fine-tuning. Detailed Mazak cycle learning
is not requested. Recording workflow, available entities, profile variants/aggregation,
Mazak timing and the first scheduling milestone remain unresolved. No installation
facts or live access/operation permission is inferred. No application code before 23:30.

The user subsequently confirmed: arm the next cycle and review before saving; implement
profile management before scheduling suggestions; use a configurable idle timeout for
automatic completion. The first local implementation retains separate recordings and
explicitly selects a reviewed representative cycle per program, with configurable
power sources/thresholds/timeouts and editable Mazak averages. Default thresholds/timeouts
are provisional UI defaults, not installation facts. No live collection is authorized.


## 30 October2026 — Integrate and publish appliance-profile management

The user explicitly requested making the V4.5 build compatible with the current system,
merging it and pushing main. Release4.5.0 integrates the confirmed profile-management
milestone onto4.4.17, preserving routing, current planner/source/continuity policies,
recovery and dashboard controls. Appliance scheduling remains a subsequent milestone;
this authorization does not expand into ARCH-006 or live installation operation.
Preserve the main checkout's uncommitted deferred-work notes. Run existing release
checks and publish via the existing workflow; do not deploy to the live installation.


## 30 October2026 — Visual planned power in task details

The user requested visual planned power profiles in task details, including other tasks
such as EV charging. Implement the accepted EV/ESS interval curves in shared task details
and the shared EV plan through a saved requirement's deadline. Keep goal sharing explicit
and distinguish ESS AC/DC boundaries and battery versus AC energy. This authorizes the
display feature, not new scheduling or live operation. Ready-release permission applies.


## 13 November2026 — V4.7 supersedes the legacy referee routing checkbox

The user explicitly confirmed that enabling the new trip system replaces the old
per-feed routing checkbox behavior. All configured referee feeds generate calculated
outward/return drives even if their legacy routing flag is false. Label the checkbox
as legacy-only; preserve it for installations using the old system. Ordinary selected
Google context calendars remain read-only and generate no EV requirements.


## 14 November2026 — EV-specific hands-off authority

User authorized V4.7 implementation of the EV charging-errors architecture package:
a separate persisted EV write veto, no stop/reset on takeover, ESS under the existing
master. Observe actual charging and faults; cancel automatic queued work without
deleting evidence. Native phase actions share the backend gate. No ordinary retry,
MILP replacement or live installation operation is included.
