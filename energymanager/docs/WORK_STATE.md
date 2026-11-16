# EnergyManager work state

This file is the current coordination view, not a journal. Update entries in place;
keep a fact only while it affects current work. Requirements and acceptance criteria
live in ARCHITECTURE.md, rationale in DECISIONS.md, and verification in VERIFICATION.md
or the referenced external checkpoint. Historical wording is not new authorization.

## Current workspace

- Main contains application **4.7.3** (`3e95b4d`) plus workflow baseline `bb782b3`; the prior release was published. No installation deployment was performed.
- The repository stays at `C:/Users/Arne/Dropbox/Documents/Github/EnergyManager`.
  External evidence, research, environments and checkpoints use
  `C:/Users/Arne/.codex/project-data/EnergyManager`; see the
  [runbook](RUNBOOK.md#local-development-workspace-and-completion-based-cleanup).
- Retained manual checkouts are external `checkouts/ev-a002` (`codex/ev-a002`, two
  commits absent from main) and `checkouts/v4-7` (`codex/v4.7-ev-calendar`). They kept
  their Git state during migration. Retention does not imply unfinished code work
  or authorization to resume an old release. Completed worktrees are retired.
- Other chats' pending edits to ARCHITECTURE.md, BACKLOG.md and DECISIONS.md remain
  uncommitted in the primary checkout. Consult them and preserve them when integrating;
  a branch copy may not contain the latest decisions.

## EV-A015 implementation

- Authorized guarded setpoint actuator; no live operation or replacement-model work.
- Chat: Implementation — EV-A015 guarded EV setpoints, `01a1e662-443c-74d3-a39c-c8d5e1c17736` (local); architecture: Planning review `01a1cc3a-ed08-7f50-9aba-20552446bce1`.
- Branch `codex/ev-a015`, managed checkout `C:/Users/Arne/.codex/worktrees/ev-a015/EnergyManager`, based on main `bb782b3` (4.7.3). Intended next release 4.7.4, subject to integration order.
- State:4.7.4 implementation and offline acceptance complete; preparing branch CI, ordered main integration and image publication. Full Windows suite924 pass/1 known main failure (same case reproduced unchanged on main); final fresh-guard cases134 pass, frontend125 pass, Ruff/mypy and both fake-endpoint E2E variants pass. Wheel/sdist build passes. No live operation.
- Compatibility: candidate-local 5s ramp and existing quantity-completion events plus conservative phase/start allowances; bounded joint source/stock/peak reallocation and independent event audit. Repair scope/status never establishes global infeasibility/optimality or extra permission.
- Evidence/checkpoint: `C:/Users/Arne/.codex/project-data/EnergyManager/checkpoints/ev-a015/implementation.md`; synthetic logs under external `runs/ev-a015-*`.
- Architecture clarification: manual fixed-phase requests retain existing permitted
  power/quantity/source/peak bounds; no legal current in the requested phase means OFF/
  prepare-only until fresh authority, not rounding up. Protective OFF is allowed when
  a ramp cannot meet a binding limit. A proposed1A-per-planning-interval restriction
  was rejected: the accepted rule is1A per5s actuation event, not per5minute slot.
  Use bounded shared transition accounting without a new unrestricted solver design;
  escalate concrete compatibility choices if needed. Documentation cleanup/recovery
  policy review remains proposal-only awaiting the user, outside this implementation.
- Documentation audit awaiting approval: EV-A015 must update legacy phase timing,
  status/phase-control instructions and shared accounting references. Additional
  proposal is to consolidate current protocol guidance, put the unimplemented ordinary-
  retry-then-reboot extension on hold, retain the implemented opt-in bounded reboot
  and essential supervision, and preserve versioned verification/incident evidence as
  historical rather than rewrite it. No recovery-policy retirement or cleanup approval
  has been inferred from accepting the actuator constraints.

## Registered chats

Ongoing architecture chats coordinate fresh implementation chats per authorized task;
use the [task-chat procedure](RUNBOOK.md#task-specific-implementation-chats) for creation,
naming, concise briefs, registration and completion/archiving. Existing release-chat
identities remain references, not permission to launch or resume another task. Keep
only currently useful task/owner/state/evidence entries; archive completed task chats.

All registered IDs below use host `local`. Verify an identity before messaging it.
The user decides when implementation starts; registration alone is not authorization.

| Topic | Architecture/discussion chat | Implementation chat |
| --- | --- | --- |
| Development workflow | Setup V2: `01a1968e-1b06-7db1-98d8-a0c3e26d071a` | None |
| Planning review | Planning review: `01a1cc3a-ed08-7f50-9aba-20552446bce1` | ARCH-030 Diagnostics export implementation: `01a1d4da-e63d-7a20-8165-7a5f3bcf8b0e` |
| EV-A015 guarded EV setpoints | Planning review: `01a1cc3a-ed08-7f50-9aba-20552446bce1` | Implementation — EV-A015 guarded EV setpoints: `01a1e662-443c-74d3-a39c-c8d5e1c17736` (GPT-6.1 Sol / medium) |
| EV optimization / V4.6 | V4.6 EV Task optimization architecture: `01a18e54-5380-7703-b13d-8044baa8a7ac` | V4.6 EV task optimization implementation: `01a1b64b-a1fe-74d2-a393-afe7ed1aeb39` |
| EV calendar / V4.7 | EV calendar architecture: `01a1c271-d7eb-7e03-b136-30173682df74` | V4.7 EV calendar implementation: `01a1d19b-6409-7b52-a868-df87257111af` |
| EV charging errors | EV charging errors architecture: `01a1b5ee-a26d-7481-8cfe-f160c58f7efc` | EV hands-off only: V4.7 EV calendar implementation `01a1d19b-6409-7b52-a868-df87257111af`; recovery unassigned |
| Dynamic contract / V4.8 | V4.8 architecture: `01a17cd0-618b-77f2-be82-7809155f6722` | Unassigned |
| Heat pump / ESPAltherma | V4.? ESPAltherma architecture: `01a16511-37fd-7e83-93bd-ebb0e536d514` | Unassigned |

## Planning review and ARCH-030 Diagnostics export

- **Active requirements discussion (14November):** user wants a guided, concrete set
  of questions to define a proposed replacement EV optimization model. Confirmed:
  no inherent penalty for same-phase current changes; uninterrupted variable-current
  sessions are acceptable; phase preference remains distinct from actuator feasibility.
  Accepted16November Ford/go-e constraints replace the previously missing model input.
  The replacement-model section now defines hard ramp/stop/phase transitions, delivered-
  energy integration and joint source/peak accounting. User corrected phase changes to
  stop first: no pre-stop ramp; current may change directly while confirmed stopped;
  any requested stop can be immediate. For a current-only reduction retain live1A/5s
  ramping; no actuator-created stop/restart shortcut. Exact encoding, phase/economic
  preference, ordinary session-interruption penalty and accepted-profile/finish-first
  implications remain open. New solver/model implementation or experiments are not
  authorized. Continue concrete preference elicitation after work-package review.
- **EV-A015 authorized (16November):** user requested a setpoint-driven EV actuator work
  package; maintained scope and completion criteria are in ARCHITECTURE.md under
  Ford/go-e operating constraints, then explicitly requested handoff to a separate
  GPT-6.1 Sol / medium implementation chat. Created/started
  **Implementation — EV-A015 guarded EV setpoints**, thread
  `01a1e662-443c-74d3-a39c-c8d5e1c17736`, host `local`, paired with this Planning review;
  scoped code/offline verification/delivery are authorized, live operation is not.
  All EnergyManager EV requests converge through one
  guarded target, including manual fixed-phase paths; no persistent manual mode is
  added, and Auto cannot bypass the fixed-phase contract. New targets coalesce, OFF
  pre-empts, live current reductions ramp, stopped settings may change directly, phase
  changes use confirmed60s stop and6A restart. Preserve EV hands-off/4.7.3 switch-state
  retention, independent ESS, acknowledgements, actual delivery and bounded supervision.
  Include existing planning/execution/audit timing compatibility without redesigning
  the optimization pipeline. Source inspection on current main found raw phase API/UI
  bypasses and legacy timing helpers; offline completion criteria cover both. Parallel
  architecture documentation audit is proposal-only pending user approval: do not
  silently retire recovery policies or extend this implementation scope from it.
- **Deferred presentation follow-up:** user requested ARCH-031 on13November2026:
  project-wide DD/MM/YYYY, 24-hour times and timezone mentions only when relevant.
  Contract/backlog updated; retrofit is unassigned and no code work is authorized.
- **Delivered:** ARCH-030 in **4.7.1**, main `76c4017`; retained branch
  `codex/arch-030-diagnostics`. User-authorized 13 November 2026; implementation
  chat `01a1d4da-e63d-7a20-8165-7a5f3bcf8b0e`, paired with Planning review
  `01a1cc3a-ed08-7f50-9aba-20552446bce1` on local.
- **Verification:** eleven scoped backend cases, 126 frontend cases, two-million-event
  synthetic contention and actual standalone/native browser downloads pass. Full
  [main CI](https://github.com/Nxt-1/EnergyManager/actions/runs/43450807702) and
  [image publication](https://github.com/Nxt-1/EnergyManager/actions/runs/43450807752)
  passed on the exact integrated revision. This is not live installation validation.
- **Boundary:** the pre-existing local Windows running-task assertion also reproduces
  on main; evidence is retained. No scheduler behavior/tests, live access, hardware,
  real notifications or installation deployment were changed/performed.
- **Installation export limitation:** user-reported4.7.1 dataset preparation stalled
  after about12.26million scan operations and timed out at30minutes twice. Read-only
  source inspection confirms two full event passes and no progress updates while
  processing decision archives/coverage; the actual bottleneck has not been profiled.
  No corrective implementation is authorized. A Windows SSH CLI export succeeded.
- **Dataset received/verified:** user supplied223.3MiB compressed SQLite for
  06/11/2026 00:00–13/11/2026 00:00, plus preceding context. Original and1.73GB
  decompressed copy preserved in external `evidence/planner-datasets/cli-2026-11-06_to_13`.
  Archive SHA25654c32d99dcfd71b3312c8f2e514a531a0409f38936eb4d6f04232020f24673f9;
  gzip CRC and SQLite quick_check pass. initial-audit.json / fitness-audit.json retain
  coverage and field inventory. All1,654 original input snapshot digests verify:
  1,375accepted (including pre-period baseline),279rejected; all have seven-day horizons.
  Contains672,691measurement events,119,241observations,1,991load samples and
  1,287background samples. Four observation gaps exceed60s, maximum301.09s.
- **Retained dataset pair:** user supplied a second CLI export for24/10/2026
  00:00–31/10/2026 00:00 (earliest complete week) and explicitly requested keeping
  both original compressed files for later use. Independent copies are preserved
  under external `evidence/planner-datasets/cli-2026-10-24_to_31` and
  `cli-2026-11-06_to_13`; `evidence/planner-datasets/DATASETS.json` is their catalogue
  with exact paths, periods, sizes, provenance, SHA256 and verification scope.
  October archive286,211,716bytes, SHA256
  bbd8d8ed09b2602b87a0ee4b42e9dcf46ca175b70d0daaf6de20653ee467f1e5;
  gzip CRC and SQLite quick_check pass. initial-audit.json verifies all2,167input
  digests:1,495accepted/530rejected/142rejected_stale, all168-hour horizons with goals
  and EV/ESS stocks; none has newer execution context. One earlier hold reference
  is missing. This supports frozen planning comparisons, not complete execution replay.
  Copies match Downloads byte-for-byte; original Downloads files remain intact.
  These are retained installation evidence, excluded from disposable-output cleanup;
  deletion requires explicit user approval. Future chats should consult the catalogue.
- **Fitness/next:** enough evidence to select initial offline cases; no further export
  currently needed. The week contains PV/ESS operation, EV charging/connection changes
  and unknown-progress periods. Execution context appears from09/11;67snapshots have
  running profiles, first11/11. The preceding baseline references one older omitted
  hold plan; do not claim complete boundary execution state. Selection uses recording
  time, so late measurements outside the range may be absent; no current state/config
  was substituted. Fixed comparison cases were subsequently selected below. Historical resource
  stocks/grid/monthly peaks remain endogenous in alternative-schedule simulations.
  ARCH-029, EV-A014 and production scheduler integration remain outside this mandate;
  isolated comparison research was subsequently authorized below.
- **Comparison plan restored after user steering:** the agreed direction before data
  collection was to compare A: rules throughout, B: accepted-profile-first joint
  optimization, C: direct rules with joint conflict-search escalation, against the
  released planner baseline. No candidate was adopted. Original proposal is in the
  preserved instruction-review WORK_STATE, Step3/Step4. Dataset collection paused
  preparation of that comparison; it did not replace it with a narrow EV patch or
  provisional-approval design. Next prepare a bounded offline comparison using both
  retained weeks and fixed difficult cases, comparing total runtime, feasibility/
  authority, stability, matching-service whole-system value and explanations. Executable
  research/prototypes were subsequently authorized for the bounded scope below.
- **Prototype readiness/proposed first scope:** both archives verified,3,821input
  snapshot digests valid. No further export is needed to begin bounded research.
  Propose one isolated offline harness, shared full-horizon evaluator and A/B/C plus
  released-planner baseline; no production integration, live inputs or deployment.
  Initial fixed corpus:12historical cases (six per week, October for general scheduling,
  November including running-context adjustments) and six explicitly synthetic edge
  cases covering joint resource conflicts, deadlines, PV loss, stock corrections and
  economic replacement. Select identities by fixed coverage criteria before tuning;
  hold separate cases out of tuning. Compare first-plan construction and existing-plan
  correction, retaining original full seven-day inputs and<=5minute intervals, with
  total120s cap including construction/audits per attempt. A does not silently fall
  back to MILP; C records every escalation. Unverified remains distinct from infeasible.
  Start with frozen-snapshot comparisons; do not claim complete counterfactual week
  replay by imposing recorded stocks/grid peaks after different decisions. One initial
  run/case/variant is exploratory; repeat representative cases before latency claims.
  Report correctness/service/authority, whole-system value at matched delivery, profile
  stability, explanations, end-to-end time and maintenance complexity. Missing execution
  context is a declared case limitation, not filled with fabricated installation state.
  **Authorized:** user answered "yes" to building/running this concrete scope.
  **First comparison complete:** external `research/planning-strategies-2026-11-13`;
  source frozen from main5dba273, no application edits. Corpus.json fixes18case identities,
  hashes and six held-out cases before tuning. Rules constructor extends the frozen
  constructive incumbent with accepted-profile input, backward household reserves and
  joint ESS/EV source dispatch; it calls no solver. Shared rows plus independent
  arithmetic audits gate candidates. Seven focused research checks pass. All72 main
  attempts and eight separate synthetic policy-probe attempts completed, with120s
  caps. Saved checked flows/cautious witnesses and frozen source/corpus/run hashes
  independently verify. Detailed findings: external
  `research/planning-strategies-2026-11-13/results/verified/REPORT.md`; raw results,
  `summary.json`, DC-export opportunity analysis and separate `results/policy-probes`
  retain evidence. A/B/C checked17/18nominal and cautious candidates; baseline14/18
  nominal and12/18cautious. Two cases have unknown EV progress: blocked-EV schedules
  do not establish goal completion. Successful-candidate median times A2.15s,
  B95.21s, C2.16s, baseline101.58s are exploratory single-run measurements, not
  installation guarantees; six unchanged baseline measurements were reused with hashes.
  Recorded finish-only corrections take about2.2s using direct rules. C only escalates
  unresolved feasibility/caution, so economic improvements are not explored when A
  succeeds. A separate simple DC-export rule closes part of a raw matched-delivery
  value gap; the joint alternative also fails a rolling economic check against A,
  so that gap is not an admitted saving. All four variants preserve phase when current
  adjustment suffices. In the forced-phase probe B/C prove same-phase infeasibility
  and find nominal schedules, but cautious qualification remains unresolved; no variant
  fully qualifies that probe. Pure rules remain open; no architecture winner selected.
  Proposed next scope: identical complete policy admission, simple source-rule
  refinement and conflict/economic-triggered search comparison. This is a proposal,
  not authorization for more research or production work. No live access, production
  integration, release or deployment was performed/authorized.
- **Authorized horizon follow-up:** user requested the proposed bounded48h versus168h
  released-planner experiment. External research subfolder
  `research/planning-strategies-2026-11-13/horizon-48h`; six frozen cases, six new48h
  runs and two repeated168h timing controls,120s hard cap per process. Four earlier
  long-horizon measurements are retained references. Same forecasts, initial stocks,
  policies and<=5minute resolution; first48h cash/value and boundary stocks are
  compared. Later-goal optimistic bounds and fixed-original-tail diagnostics are
  deliberately weaker than a rolling simulation or verified joint continuation.
  **Complete:** all eight attempts, source/case/hash checks and independent output
  audits finished; preflight stock propagation/regridding and event-withdrawal checks
  pass on four complete references. Report and raw evidence remain in that subfolder.
  Both horizons return4/6nominal checked schedules; the same two cases stay unresolved.
  In the four checked pairs, median total time48h92.38s versus168h106.12s (about13%
  reduction); two cases improve18-27s, two less than1s. A representative economic
  stage is much faster with the smaller model, but later refinements use the budget.
  Common-first48h bill differences are mixed (+0.315,-0.079,-0.231,+1.154EUR);
  inventory-adjusted results favor48h by0.135-1.474EUR, with different battery stocks
  and no matched full-week service claim. Optimistic future-goal bounds prove no
  inevitable shortage in this sample; all four original later command schedules
  need repair after the changed prefix. That is not proof a rolling controller fails.
  No recurring weekly cost estimate or production horizon decision follows. Proposed
  optional-refinement budget/rolling-economic experiments remain unapproved. No
  production horizon change, live access or general follow-up research is authorized
  by this experiment.
- **Candidate sequence inventory (read-only):** inspected all67November decisions with running profiles:
  35accepted/32rejected, not a classification of rejection causes. First comparison
  sequence11/11:15020e7d (18:45:59,87.41s/rejected),0ce618b9 and6973c80b rejected,
  then3dc0db68 (18:58:38,100.78s/accepted). Initial stored finish correction is about
  5min18s, phase1; this repeats the known incident in its surrounding history, not
  new proof of feasibility. Second sequence12/11:b2b819b3 through250513bc includes
  72–73s rejected required searches despite near-unchanged recorded finish estimates.
  Use these to assess validation/direct-repair/joint-search boundaries; numerical
  finish corrections alone do not establish joint feasibility or authority to extend.
- **Implementation evidence:** external `checkpoints/arch-030/implementation.md`,
  stress/package/native-download reports and `planner-baseline-limitation.md` remain.
- **Earlier seasonal request (now superseded by earliest-week acquisition):** user
  initially wanted a PV-surplus summer/September
  week. Current SQLite starts23/10, so it cannot supply September. Selected a
  measurement-only candidate21/09/2026–28/09/2026 from previously supplied Influx CSVs;
  external `evidence/planner-datasets/september-2026-09-21_to_28/manifest.json` records
  source hashes/limitations. Contains600household and6,660source readings (PV/grid/
  ESS/EV). Recorded export peaks near4.68kW; gaps prevent a complete weekly energy
  total or claim that this was the highest-surplus week. No September forecast input
  snapshots/goals/permissions/stocks were supplied; this is not equivalent to the
  November evidence. Need establish older history/backup availability before promising
  a complete historical September planning replay. Missing data must not be fabricated.

## EV optimization / V4.6

- **Delivered baseline:** EV-A002 through EV-A013 and their authorized follow-ups are
  in main through 4.6.12 and carried into 4.7.0. Their old local-complete/release-pending
  checkpoints are superseded; do not restart them from historical NEXT entries.
- **Open:** a supplied 4.6.12 rejected plan exposed a bounded finish-preference search
  discarding an already checked same-phase candidate. The proposed fallback correction
  was not accepted for handoff; planner-generation/ownership design is now part of the
  separate Planning review. Installation effects remain limited by the supplied evidence.
- **EV-A014:** independent timer/stage/completion/error display is retained, but the user
  explicitly withheld handoff while planner discussion continues. [Scope and criteria](ARCHITECTURE.md#pending-independent-progress-indicator-ev-a014)
  remain authoritative; no new implementation/release is authorized for this item.
- **Evidence:** original planner datasets are under external `evidence/planner-datasets/`;
  the rejected export is `evidence/ev-a013-rejection-2026-11-11/incident.json`.
  **Next:** continue the architecture discussion; obtain explicit authorization before
  starting a new implementation task.

## EV calendar / V4.7

- **State:** ARCH-022 shipped in 4.7.0; the earlier foundation-only, policy-hold and
  release-pending notes are superseded. New-mode referee generation replaces the old
  per-feed routing-checkbox behavior; ordinary Google context remains read-only.
- **Current boundary:** code/package/offline checks do not establish live OAuth,
  callback-proxy, external calendar-write or installation behavior. No new live access,
  hardware/deployment operation or follow-up code task is authorized by this record.
- **Next when work resumes:** use current main/shared requirements and the external
  V4.7 checkout location above; agree the requested follow-up or live validation scope
  with the user. Existing behavior/verification are in ARCHITECTURE.md/VERIFICATION.md.

## EV charging errors

- **Testing closed16November2026:** user accepts the
  [Ford/go-e operating constraints](ARCHITECTURE.md#ford-puma-go-e-operating-constraints)
  as working assumptions until contrary real-use evidence. The maintained architecture
  now contains the constraints, accepted3p extrapolation and condensed test/recovery
  evidence; no further exploratory runs are planned. Original supplied traces remain
  in Downloads; authored test YAML is external under
  `research/ev-error-investigation/ev-mixed-test.yaml`.
  **Next:** use the constraints in architecture/planning discussion. Application changes
  or implementation handoff require a separate user request; none is authorized here.
- **Authorized:** user requested an [EV-specific hands-off control package](ARCHITECTURE.md#pending-ev-specific-hands-off-control)
  on14November2026: replace the EV tab's Hardware control indicator with a switch;
  off observes but sends no EV writes and makes no stop/reset at takeover. ESS remains
  independent. Package covers persistence, queued/in-flight dispatch, recovery and
  master/shutdown paths. User explicitly assigned implementation to V4.7 EV calendar
  implementation (`01a1d19b-6409-7b52-a868-df87257111af`, host `local`).
  **Implementation:**4.7.2 on main77ec5ae. Native timeout validation found a successful
  switch save could be hidden by a failed follow-up status refresh.4.7.3 immediately
  renders the save response and protects it from older read revisions. Hardware
  dispatch is unchanged.34 affected/126frontend, Ruff/mypy73 and native synthetic
  timeout/keyboard/off-state reload checks pass. External evidence/checkpoint under
  ev-hands-off-* and ev-switch-ack-*. **State:** scoped code is integrated as4.7.3;
  no implementation work remains. Delivery/retirement evidence is in the external
  `checkpoints/ev-hands-off-release.md`. Any new implementation or live installation
  operation requires its own authorized scope.
  physical-error investigation and ordinary retry/reboot changes remain separate.
- **State:** agreed [supervised ordinary retry](ARCHITECTURE.md#pending-supervised-ordinary-retry)
  remains pending and unverified, with no release/implementation partner or code
  authorization. Notifications follow exhaustion of the agreed bounded recovery path;
  the design does not bypass explicit vehicle/charger faults.
- **Dependency:** the stock-reconciliation interruption diagnosed from incident57adac04
  was taken into EV-A012 and shipped in 4.6.12. That delivery does not implement the
  separate retry/reboot package or establish the physical cause of later non-delivery.
- **Open:** physical fault/non-delivery causes and vehicle-telemetry/rate-limit behavior
  remain limited by the supplied offline evidence. Originals are under external
  `evidence/ev-error-investigation/`; detailed prior findings remain in the pre-cleanup
  record. **Next:** finalize/assign the recovery package only when requested; new live
  inspection or implementation needs the user's authorization.

## V4.8 — dynamic electricity contract

- **State:** discussion of [ARCH-016](BACKLOG.md#arch-016--dynamic-tariff-comparison),
  with no implementation owner, branch or authorized code task.
- **Next:** establish the current-contract baseline, confirm meter SMR3 status and
  available quarter-hour history. Comparison method, price source, unpublished-price
  treatment and charging-policy changes remain undecided. The October 2026 Energie.be
  card is dated reference material, not a selected contract or current-price claim.

## Altherma / ESPAltherma

- **15 November:** user is still waiting for hardware. Outdoor-temperature-dependent
  heating/cooling efficiency retained as a deferred scheduling consideration in
  ARCHITECTURE.md and ARCH-004; no model/control policy or implementation selected.
- **State:** architecture discussion only; implementation/release unassigned. Device,
  purchased-board and selected-relay details are in the [pending integration contract](ARCHITECTURE.md#pending-altherma-integration-arch-004).
  No installation, physical validation or hardware-operation authority is inferred.
- **Next:** verify ESP32-C6 firmware support and UART/relay GPIO assignments, then actual
  Daikin wiring/level shifting/supply capacity and startup/stale-command behavior before
  commissioning. DHW scheduling remains deferred in [ARCH-004](BACKLOG.md#arch-004--dhw-scheduling-and-heating-model-calibration).

## Preserved reference records

The full pre-cleanup work state, including unique uncommitted notes, is preserved at
`C:/Users/Arne/.codex/project-data/EnergyManager/history/instruction-review-2026-11-13/WORK_STATE.md`,
with its hash in the adjacent manifest. Committed history remains in Git. Read specific
historical sections only when needed for evidence or an unresolved investigation;
never treat archived proposals, permissions or next steps as current instructions.

The architecture before topic reorganization is preserved at
`C:/Users/Arne/.codex/project-data/EnergyManager/history/architecture-topic-review-2026-11-13/ARCHITECTURE.md`,
with hashes for the reviewed documents in the adjacent manifest. It is historical
evidence, not another maintained specification.
