# EnergyManager 4 verification

## 4.7.1 — Diagnostics planning dataset (ARCH-030)

All history, databases, endpoints and downloads here are labelled synthetic/local. No live
HA/database, hardware, real notification or installation deployment was accessed.

- Eleven focused Python tests pass, covering exact legacy/zlib bytes and digests, independent
  ZIP member hashes, recording/observation-time selection and deduplication, all stored
  dispositions, full horizons, accepted/boundary/predecessor context, gaps, missing context,
  corrupt/sensitive records, unknown schema/kinds/fields, empty periods, source immutability,
  access/path rejection, duplicate jobs, cancellation, worker failure, runtime/disk limits,
  restart/retention and simultaneous download/expiry protection. A reserve failure during
  packaging removes the partial ZIP. No export-induced events/authority mutation occurs.
- 126 frontend cases pass; the native strategy includes Diagnostics and shared controls.
  DST repeated times require an occurrence and skipped times reject; exact captured bounds,
  discovered ingress paths, expired/failed/cancelled views and human actions during polling
  have regression coverage. Browser checks exercise standalone coverage/ZIP download,
  native Check history → All available → Prepare → Download, cancellation, reopening and
  restart restoration, plus desktop/mobile layout. The actual native browser-saved ZIP is
  30,158,031 bytes; every member hash verifies independently. Compact evidence is external
  `checkpoints/arch-030/native-browser-download.json`.
- Synthetic contention fixture: 2,000,000 events over seven days, 60 decision archives with
  425,095 decoded bytes per snapshot, a 510,914,560-byte source and concurrent commits.
  Export produced 30,142,895 bytes in 51.01 s; peak process memory was 130,723,840 bytes.
  API maximum was 38.0 ms during export (20.5 ms baseline). Actual fake-actuator control
  ran 51 ticks, maximum 1.043 s (1.026 s baseline), passing the 1.1 s gate at 1 s configured
  cadence. 1,017 concurrent commits completed; source revision stayed unchanged, no export-
  induced replan occurred, and 2,000,000 selected source events were counted independently.
  This establishes synthetic contention behavior, not installation performance.
- Configured and routed local fake-HA E2E runs pass, including real full-horizon planning,
  independent control, cancellation/adoption and persistence/recovery. Ruff and mypy pass;
  wheel/source package verification is recorded in the external checkpoint.
- **Known local limitation:** the final full Windows run passed 902 and failed the existing
  running-task allowance/handover assertion `second['valid']` under its 16 s solver budget.
  An explicit import of unchanged main source reproduces that assertion with previews
  stopped. The earlier full run passed 900; do not describe the final local suite as green.
  No scheduler behavior/tests were changed. Exact assertion, baseline/environment and
  solver evidence: external `checkpoints/arch-030/planner-baseline-limitation.md`.
  Normal full Linux CI on the actual integrated release revision remains the release gate;
  subsequent remote results belong in the external checkpoint and final delivery report.


## 4.7.0 — Local EV trip calendar (ARCH-022)

Based on released4.6.12/1befc16. All new stores, OAuth/Calendar/Places/Routes endpoints,
HA readings and notification destinations used for these checks are labelled synthetic
or local. No private calendar, paid request, actual HA/database, phone receipt, hardware,
reverse-proxy deployment or installation commissioning was accessed.

- Full888 Python cases pass247.51s. Current calendar/routing/settings/API focused cases
  pass164/6.75s; final58 calendar/route cases pass0.71s after readable Google-marker and
  token/empty-response checks.122frontend cases pass398.8ms; Ruff, mypy72 modules and
  CLI4.7.0 pass. New API tests verify ordinary appointments create no EV requirements,
  same-origin mutation boundaries and public push channel/resource/token validation.
- Durable tests cover escaped From lines and the readable v1 marker, direct distance-only
  creation, manual km/Use calculated distance, Google-time edits becoming fixed, manual
  conflict precedence, lost insert response/restart identity, stale acknowledgements,
  correction last-good state, invalid tokens/full-read deletion recovery and authorization
  episode deduplication. Real HTTP adapters run against disposable fake OAuth/Calendar
  endpoints, including native weekly masters and mapped instance edit/delete.
- Source/route tests cover two independent referee legs,1hour early arrival/2.5hour
  return departure, all-known distant finite events, bounded unending source rules,
  near-term traffic only, deletion suppression/source-change restoration, source removal
  confirmation and preserved unrelated/manual requirements. Withdrawal totals are checked
  through a planner snapshot; away-to-away absence and persisted actual-home-return
  override are exercised. Exactly10minutes does not warn; greater duration warns once
  per human edit, with fixed manual times and manual km retained on ordinary refresh.
- Standalone and native HA-contract browser previews were inspected on desktop and
  phone-sized views. Week/day defaults, switcher, read-only appointment click, drive
  movement and start/end resize, unsaved range selection/origin suggestion, Places search,
  distance-only/weekly save, shared24hour picker, draft retention and queued disconnect/
  reconnect edits passed. Fixed polling interference/scroll restoration and exposed resize
  handles. Browser warning/error logs were empty. Previews use fake providers and disposable
  stores; physical touch and the actual HA/proxy/account remain unverified.
- Configured4.7.0 fake E2E passes2019intervals in25.535s, maximum control3.275ms,
  four fake service calls, including solver cancellation/replacement, publication,
  meter progress, switch-off protection and archive recovery. The earlier routed run
  passed2023intervals/60.955s/max5.652ms/two imports/six route queries/four fake calls.
  A later routed fixture reached Required's time limit without a feasible candidate.
  Its frozen synthetic input reproduces that result on released4.6.12 in47.323s:
  an existing planner limitation, not evidence of a calendar/control regression or
  a reason to weaken validation. Original planner/charger recovery policy is unchanged.
- Bundled MIT assets: FullCalendar Standard6.1.20, matching Luxon3 plugin6.1.20 and
  Luxon3.7.2, served locally with licenses. Source/package parity and final packaging
  results: all106 runtime source/assets match the wheel, isolated4.7.0 imports/assets pass.
  The final rebuild includes the current documents/source; remote outcomes follow separately.

Runtime contracts/setup are maintained in ARCHITECTURE.md, SETTINGS.md and RUNBOOK.md.
Final confirmed-policy checks:25 calendar/source/API cases pass0.74s, including
routing-disabled and routing-enabled referee feeds replacing duplicate legacy goals.
Final122frontend cases pass403.9ms; rebuilt wheel/sdist both match106 runtime files.

The user confirmed13November that new-mode activation supersedes the legacy referee
routing checkbox; current all-feeds routing now matches the confirmed policy.
Exact-head remote CI/publication results belong in the ignored release checkpoint and
paired-chat/final report, without an optional verification-only commit.

## 4.6.12 — EV stock continuity and running corrections (EV-A012/A013)

Based on released4.6.11/5b06141. All fixtures, stores, HA/actuator endpoints and commands
below are local/synthetic. Preserved installation exports are read-only evidence.

- Full865Python cases pass243.61s; after final completion/profile-boundary guards,
  56focused controller/publication/execution/policy cases pass77.28s.122frontend
  cases pass410.4ms; Ruff, mypy64modules, CLI4.6.12 and every packaged JS syntax pass.
  No frontend assets changed; this release makes no new browser/physical commissioning claim.
- Original incident SHA25604d018b0c1259b5f3f216f92df11aea67417189491135557a6130212b0f07e02
  remains unchanged. Replay uses its before/after stock/timestamps/counter evidence with
  an explicitly reconstructed initial ledger and accepted16A/50% task. Observation→
  controller→fake go-e stays16A/one phase through9.5274→9.594kWh and baseline5→6,
  preserves2.6532kWh historical credit, and writes no force-off/start/phase command.
  The incident established the prior software stop trigger; it does not establish the
  cause of the later physical failure. See ignored a012-incident-replay.json/script.
- Up/down stock, repeated reports/no double credit, estimated50.1% versus actual17%
  after driving, manual bounds/recovery, completed-task tombstones, conditional advance,
  distinct future tasks and pending ACK/generation continuity pass. Fake actuator checks
  cover completion, unknown/disconnect, revoked authority, peak protection, expiry and
  checked replacement handover. Existing explicit fault/Off/stale/source guards pass.
- Six preserved controlled seven-day inputs (ESS disabled) yield audited integrated
  replacements in15.66–27.31s within120s. Ahead/behind change finish only; tight deadline
  changes current from90min; the phase-priority case changes current from10min and
  avoids the research prototype's later phase switch; household load brings current
  changes to2.25min; solar uses an earlier same-phase economic exception. All retain
  required service, zero phase changes and zero new starts. Exact currents, stock,
  costs, peak, audits and released-planner baseline comparisons are retained in ignored
  a012-a013-comparison.json, with original ev-tail-research bytes unchanged. Surplus
  rounding Wh are reported, not claimed as economic savings.
- Full joint ESS/EV fixtures check both sides of EUR0.02 at equal23.4kWh useful EV
  stock. Low-price tail regret is aboutEUR0.00822 and remains finish-only; the higher
  price opportunity is aboutEUR0.03289 and permits earlier current. A separate valued-ESS
  case rejects PV-to-EV transfer that displaces more useful stored supply. Task-keyed
  spent/remaining allowance survives repeated planning and thin handover; no new
  tolerance is added per candidate/update. Phase tests distinguish genuine infeasibility
  from required-reference and joint-support timeouts; cautious proof identity is audited.
- Archive-derived counterfactuals remain inconclusive: archived_bounce 72.82s/Time limit reached, archived_nov05 94.77s/unverified.
  Neither yields a checked replacement; no phase necessity is inferred from timeout.
  Prior authority is neither renewed nor extended. This is not an installation result
  or a claim that all full-horizon joint searches find a replacement inside the budget.
- Configured fake E2E25.731s/2019intervals/max control3.228ms; routed55.818s/2023intervals/
  max2.774ms pass with four fake service calls each, two calendar imports and six fake
  route queries in the routed run. Wheel/sdist4.6.12 build and all92runtime files match
  source bytes; isolated wheel imports/version pass. Local Docker is unavailable.

Exact-head CI/image publication outcomes follow in the ignored release checkpoint and
final paired-chat/user report, without an optional verification-only commit. No live
HA/database access, real notification, hardware operation or installation deployment.

## 4.6.11 — EV-page cleanup (EV-A011,11November2026)

Based on released4.6.10/6ab71f6. All endpoints, meters, faults, actuator calls and
notification destinations below are labelled synthetic/local. No live source was used.

- Final844Python cases pass174.56s;122frontend cases pass409.6ms.58focused feedback/
  fault/native cases pass4.73s. Ruff, mypy63modules, CLI4.6.11 and all asset JS syntax
  pass. Existing A010 endpoint/refinement/advisory, source/recovery/peak/charger and
  independent grid/ESS/appliance regressions remain unchanged and pass.
- Human edits commit once on Enter/blur; partial digits, opening a blank switch,
  untouched blur, programmatic estimates and completion submit none. Context tests
  reject changed goals, counter source/segment and changed-report recovery while
  accepting ordinary counter advances. Failure retains a draft without blur retry;
  switching off cannot first commit a dirty draft. Diagnostics preserve independent
  progress faults and real step/countdown data with one fault explanation.
- Native/standalone desktop1360px and mobile390px were inspected.320px standalone
  header has matching client/scroll width253px (no overflow); typography matches
  system font/12px/500/text colour for both header rows. Diagnosis is always visible
  above the sensor list, beside the unchanged drawing on desktop and below on mobile.
  Actual native reported-SoC history opens `sensor.ev_soc`; optional sources fit the
 390px screen (panel14.47–344.47px). No invented manual history entity or preview-only
  data/design controls are included in production assets.
- Browser blank switch and typing17% grant no authority until Enter/blur. One human
  entry establishes a scoped reference while a separate persisted synthetic delivery
  incident remains unresolved. An8second synthetic HTTP rejection preserves19% input,
  keyboard focus/read-only pending state and truthful accessible error; the backend
  remains at17%, and untouched blur does not retry. A new human18% edit succeeds.
  Counter completion updates the field to50%/30kWh without changing its reference ID,
  entered18% baseline or19.2kWh delivery ledger, and commands zero EV power.
- During a focused20% draft, changed vehicle57% recovery exits manual mode and
  corrects stock to34.2kWh. Late blur rejects the stale edit; reference ID, recovered
  status and delivery history stay intact, and the independent delivery fault stays
  active.101% validation and unplugging leave no inferred reference; invalid manual
  state displays a blank field. Healthy/fault/recovery/countdown and source
  states were exercised; a rendered13second countdown remains beside fault evidence.
  No console warnings/errors were observed in the final owned tabs. HA built-ins
  and preview display scenarios remain simulated. Owned tabs/servers were closed.
- Configured fake E2E25.724s/2019intervals/max control4.134ms passes; independent fault
  preview normal checks25.426s/max4.240ms also pass. Routed fake E2E55.836s/2023intervals/
  max4.094ms passes, two calendar imports/six local route queries. Each normal/routed
  check performs four fake service calls; cancellation, admission and genuine mapped
  usable-counter assertions remain enabled. Synthetic manual API delay/failure is
  available only with the local `--serve --feedback-fixture` test option.
- Wheel/sdist4.6.11 build; all91runtime files match source bytes in both. Isolated
  wheel import/version passes. Exact-head CI/container/publication outcomes are
  recorded subsequently only in ignored `artifacts/ev-a011-state.json` and final
  paired-chat/user reports. No local Docker or installation deployment is claimed.

## 4.6.10 — Unreliable feedback and bounded manual recovery (EV-A010,11November2026)

Based on released4.6.9/fd6d4a9. All measurements, counters, notification destinations,
endpoints and actuator operations below are explicitly synthetic/local. The supplied
frozen forecast is unchanged; no live installation/database/hardware was accessed.

- Final840Python cases pass171.75s;118frontend cases pass397.6ms. Ruff, mypy63modules,
  all asset JavaScript syntax and CLI4.6.10 pass. The final31focused feedback/manual
  cases pass4.65s. Existing A008/A009 stock/source/execution/grid/appliance cases pass.
- The feedback matrix covers fast/slow measured3point gain plus15minute grace,
  rounding/delayed changed readings, parked/small-top-up/near-full behavior, pauses,
  replans/restarts, missing/reset/changed/stalled counters, continuous gap recovery,
  absent/stale vehicle times and one persistent incident/notification identity.
  Manual confirmation/dismissal/update, overnight waiting beyond12hours, completed/
  changed/new goals, unplug/return, lower/higher changed recovery and unchanged
  cached values are checked. Historical energy credit stays separate from new stock.
- A real synthetic3600second control loop stops49→50% charging within one minimum
  control dose; a later80% goal cannot enlarge it. Partial15second prefixes, a130second
  phase wait spanning the completion interval and single/three-phase small quantities
  validate source/EV/ESS/quarter balance and normal admission. No flow is trimmed to
  create an accepted plan, and an uncapped seed is never execution authority.
- Full seven-day synthetic manual17% case on the supplied forecast completes in
  77.3149s within the original120s wall budget. Completion refinement2021→2022intervals
  freezes a new context; reference, full-joint independent validation and admission
  pass. Maximum stock is exactly23.4kWh for the confirmed50% goal. Captured digest
  `3ba50a392dbf1577120d490282ac7bb12a14eeca337381b78a26d8e3a645cf67`;
  effective digest`0a2a8003c6641432dcf15401d6af8e33a43c1eb3f01e65cc47d58af1930dac10`.
- Non-executable advisory tests independently audit complete joint flows/context,
  retain due instruction windows and gate refresh requests on current sources,
  revision and forecast. Timeout/missing/satisfied candidates invent no prompt time.
  The full2022interval completed-scope/later70% case takes22.3874s total: authoritative
  plan validates and remains capped, but the optional3second advisory solve times out
  without a checked candidate. It is explicitly unverified, with no instruction or
  phone timing guarantee. The small real-model checked path and due-window/dedup
  integration pass; no extra budget or deadline/max-rate reminder is introduced.
- Native/standalone desktop1360px and mobile390px browsers verify blank entry,
  dismissal without authority, confirmed17%/updated19% references, counter-loss pause,
  preserved reference on recovery, switch-off pending/error behavior, completion and
  changed vehicle57% recovery to34.2kWh. Historical18.6kWh credit remains separate;
  completed manual mode remained stopped for more than two elapsed hours before
  recovery. Native battery history opens the actual `sensor.ev_soc`, not a fabricated
  manual sensor. No console warnings/errors were observed. Screenshots are local
  synthetic evidence; HA built-in cards/Supervisor remain simulated.
- Configured fake E2E passes25.656s/2019intervals/max control2.744ms/four fake actuator
  calls. Routed fake E2E passes65.936s/2023intervals/max5.158ms/four calls, two calendar
  imports and six local route queries. Existing cancellation, current admission,
  persistence, authority and usable-progress assertions remain enabled.
- Wheel/sdist4.6.10 build; all91runtime files match source byte-for-byte in both
  artifacts. Isolated wheel import/version passes. No Docker daemon is used locally;
  exact-head CI/container/image publication must complete through existing workflows.

Evidence is indexed in ignored `artifacts/ev-a010-state.json`. Subsequent remote
outcomes belong there and in the paired chat/final reply, without a follow-up docs
commit. Detector calibration and physical meter/control response remain installation
unverified. No live installation deployment or real notification was performed.

## 4.6.9 — Vehicle stock after driving (EV-A008 follow-up, 10 November2026)

Based on released4.6.8/de726ed. All counters, ledgers, endpoints and actuator calls
below are labelled synthetic/local; the user-supplied frozen decision is unchanged.

- 809Python cases pass171.40s;25focused cases pass5.33s (final19restart cases0.47s);113frontend pass0.407s.
  Ruff, mypy61modules and CLI4.6.9 pass. Regressions cover planned/unplanned returns,
  missing physical timestamps, repeated unchanged values, genuinely fresh aligned/
  unaligned lower samples, stale explicit timestamps, counter gaps and restart credit.
  A real planner case confirms high retained stock cannot mark an unresolved return
  fulfilled and that corrected17% stock schedules energy for the50% daily target.
- Application regression proves a changed stock baseline revokes EV authority and
  requests exactly one recalculation while ESS authority and saved results remain.
  Existing execution/charger/fault/permission/peak and progress-warning cases pass.
  No retry/reboot or notification-policy changes are included.
- Frozen export2b8665d16f06478d89e164b531bdc91b/revision863 retains SHA256
  `826d923c31370055b5063eb442b78e4350c90c705d2d193f5685aa2a40dc4bac`
  and digest`8c5236354aa2f1208aa08a075e973f7091333dc610c088f51ee50aaff93d79ca`.
  An explicitly synthetic reconstructed persisted ledger reproduces23.4513kWh versus
  reported7.956kWh, with.7533kWh historical charging credit. Correction uses7.956kWh
  once, leaves vehicle sample time unknown and retains baseline/overlap uncertainty.
  All2021intervals/goals/execution context are preserved for the corrected replay;
  full solve103.749s validates and schedules17.16299kWh before11November07:00 Brussels,
  reaching23.40269kWh against23.4kWh target, versus zero charging in the supplied result.
  The complete installation ledger was not supplied. This reproduces the failure and
  correction, not the historical timing of any driving or missing charging segment.
- Configured fake E2E25.691s/2019intervals/max control3.140ms and routed60.864s/2023/
  max3.991ms pass. Actual mapped fake eto remains usable with old HA report metadata;
  EV goals are not bypassed as unknown. Both perform four fake actuator calls; routed
  imports two calendar trips with six local route queries. No installation benchmark.
- Wheel/sdist4.6.9 build,88runtime byte comparisons and isolated version/import pass.
  Existing113frontend cases cover both-dashboard progress-source/history rendering.
  This correction changes stock accounting and existing warning recovery prose;
  no layout or dashboard interaction changes require new visual acceptance.

Detailed frozen replay, package and local logs remain in ignored artifacts, indexed
by `artifacts/ev-progress-return-state.json`. Exact-head CI/container/publication results
belong only in that checkpoint and final reply. No live source or deployment used.

## 4.6.8 — EV-A009 shared warnings and independent grid display (9 November2026)

Based on released main4.6.7/4cecd64. EV-A008 and recorder readiness remain covered.
All sources, counters, notifications and actuator endpoints used below are synthetic/local.

- 800Python tests pass209.22s; final62source/journey/native cases pass1.07s after
  source-cause diagnostics.113frontend cases, Ruff/mypy61modules, all asset JavaScript
  syntax and CLI4.6.8 pass. The first broad run exposed a SyntheticHA fixture missing
  its entity-mapping contract; the corrected fixture and final full run pass.
- Source-causal presentation groups missing/unmapped/unavailable and stalled-counter
  faults, distinguishes genuine post-trip reconciliation and updates current affected
  identities/revisions/deadlines. Recovery is independent of a planning result. Saved
  issue records, frozen results and unrelated approval/shortfall/planning/margin issues
  remain unchanged by the view; notification processing is not regrouped.
- Projection regressions cover a complete EV-disabled household/ESS plan, independently
  revoked EV/ESS/conditional authority, missing resource evidence, later invalid slots,
  full prior-plan handover with inherited authority, active cautious coverage/deadline,
  controlled-appliance execution evidence and known idle. No source flow is dropped.
  Existing gross-import, measured prefix, partial-slot, forecast-expiry, incomplete
  coverage, missing/true-zero meter, quarter/month reset and styling checks pass.
- Configured fake E2E passes25.590s/2019intervals/max control4.399ms/four fake calls.
  Routed fake E2E passes67.219s/2023intervals/max3.226ms/four fake calls, two calendar
  imports and six local route queries. Existing cancellation/admission/persistence and
  known usable progress assertions remain; explicit resource-authority fields are checked.
- The routed preview then loses the actual fake counter after normal acceptance.
  API state shows one counter-unavailable warning affecting nine identified daily/trip
  goals, EV unknown/invalid, ESS valid and a complete accepted plan with zero EV flows.
  Its existing measured quarter is0W and both dashboards retain one quarter-end marker.
  Independent execution of the display projection on this actual synthetic API snapshot
  preserves all flows, returns a0W marker and1345monthly points (26.4ms single local
  observation; not an installation/mobile benchmark).
- Restoring that fake source clears the warning in2.429s while planning is calculating.
  The accepted plan ID, every flow/goal result, saved issues and54.0kWh progress remain
  unchanged. Both dashboards show Awaiting recalculation for the pending goal results;
  neither fulfillment nor a recalculated result is invented. The marker remains visible.
- Native/standalone desktop and390px checks pass: one compact warning, expandable nine
  titles/deadlines, distinguishable recurring goals, retained expansion across updates,
  unavailable-result badges, and no repeated reconnection prose. Native Enter opens
  actual `sensor.ev_total_kwh` and `sensor.quarter_import_kwh`; standalone offers no
  fabricated HA action. Warning recovery and clean warning/error logs verified in both.
  Screenshots remain in the existing visualization directory. HA built-ins/touch are
  simulated; this is not physical installation evidence.
- Wheel/sdist4.6.8 build and88runtime source/asset/default byte comparisons plus
  isolated version/import/changed-asset checks pass. Planner, fast dispatch, source/
  quantity/peak/fault guards and notification decisions have no policy changes.

Exact-head CI/container/publication outcomes go only in the ignored EV-A009 checkpoint
and final reply. No live HA/database, real notification, hardware or deployment used.

## 4.6.7 — V45-A003 recorder readiness feedback (9 November2026)

Based on released main4.6.6/068307c, preserving complete EV-A008 execution/progress code.
Application changes are shared recorder feedback and scoped theme styling; no detector,
backend storage, HA timestamp gate, idle dwell, hardware or start-policy change.

- 113focused profile/Bosch/run/native Python cases pass2.33s. One new local fake HA
  case verifies exposed first-read/idle/failed-read/restart evidence with available
  unchanged historical HA report times, current read timestamps and the actual program.
- 106frontend cases pass. New feedback cases cover waiting/ready/recording, true zero,
  absent/invalid/failed/stale power/status, sampler errors, delayed responses, recovery,
  completed/Bosch exclusion and retained draft/review references. Existing graph grip,
  cursor/zoom/pan, groups and EV/source-history cases remain covered.
- Ruff/mypy61modules, all packaged JS syntax, wheel/sdist4.6.7 and isolated import pass;
  all88runtime files match source bytes. Final package evidence is in ignored
  artifacts/a003-package-verification.json.
- Both-dashboard synthetic browser flow shows initial unavailable, waiting at1500W,
  explicit idle readiness at0W and Recording at1800W, while a different selector never
  relabels the capture. Missing power, HTTP status failure and paused-read staleness
  withdraw Ready and recover. Recorder restart clears idle/observation evidence;1500W
  still waits, then fresh0→1800W starts. No collapsed-card indicator; native light/dark
  cues inspected. Name/notes and the open1second trim survive all updates; keyboard
  start→2seconds and end field→handle9seconds stay linked. Browser logs are empty.
  Native HA built-ins, readings and restart are simulated; no physical hardware claim.
- Configured local fake E2E passes25.993s/2019intervals/max control4.244ms/four fake
  service calls, including original worker cancellation/replacement and persisted plan
  recovery. Timings are synthetic integration evidence, not installation performance.

Browser harness and checkpoints are ignored artifacts; no synthetic control endpoint
is shipped. Screenshots recorder-ready-native.png and recorder-recording-native.png
remain in this chat's visualization directory. Full Python/routed/container release
checks run in CI. Exact-head remote outcomes go in the ignored release checkpoint and
final reply, without a follow-up documentation-only commit. No live access/deployment.

## 4.6.6 — EV-A008 execution and counter progress (9 November2026)

Based on released main4.6.5/0ea0dfb. All measurements, counters, endpoints and actuator
responses below are labelled synthetic; the supplied export remains unchanged evidence.

- 796Python tests pass164.27s,102frontend cases pass, Ruff/mypy61modules, shipped JS
  syntax and CLI4.6.6 pass. Ledger coverage includes unchanged49% SoC through ten
  actual replans, overlapping/revised goals, restart/reconnect, Wh/kWh, continuous
  gaps, counter/source resets, genuine SoC alignment/fallback, unknown timing,
  unknown-return guards, stationary/stalled counters, EV-only pause and guarded recovery.
- The supplied original plan with the existing real fake-go-e sequencer makes no
  phase writes, starts delivery after30s and delivers0.4743175kWh stored against its
  0.473187kWh task. Reconnect plus process/control restart delivers0.4739725kWh, with
  no incidents. Fifteen publication-ID changes retain its absolute endpoint.
- The final fresh calculation of the supplied snapshot with a clearly labelled
  synthetic preceding accepted trajectory passes physical/source/rolling audits in
  99.930s under120s. Its coherent candidate is checked, including five partial slots,
  rather than skipped for the old held phase. At the original adoption time, separate
  admission preserves every frozen flow. Actual fake-go-e delivery makes no phase
  writes, starts after30s and stops at the new0.468690kWh task within1.66Wh of
  meter/control quantization; restart/reconnect stays within0.80Wh. The missing prior
  installation history is not inferred from these synthetic trajectories.
- Required phase-switch cases cover immediate/delayed/missing acknowledgements,
  adoption during a submitted selector write, near deadlines, unexpected house load
  and constrained ESS. Solar-only phase preparation remains force-off through actual
  fake PV loss and cannot bypass unavailable progress or revoked authority. Snapshot
  commitments honor conditional/handover authority while retaining eligible required work.
- Serial fresh7day/≤5min/120s cases pass independent physical, source and rolling
  economic checks: mixed101.700s, winter103.038s, held/partial urgent permission94.021s.
  These are valid time-limited incumbents, not global optima. Mixed/winter minimum-grid
  checks certify; their cautious deadline refreshes remain unverified. Urgent permission
  reports nominal shortfall under existing authority. Raw attempts remain in artifacts;
  an unverified refresh is never represented as a cautious certificate.
- Released4.6.5 mixed baseline takes108.015s with63,894columns/55,843rows/17,489integers.
  New mixed model has69,989columns/94,266rows/21,535integers, build0.160s versus0.099s.
  Single timings do not establish a speedup. No expanded budget, reduced horizon,
  relaxed source constraint or skipped unknown EV requirement is used.
- Configured fake E2E passes25.542s/2019intervals/max control4.213ms/four fake calls.
  Routed E2E passes56.092s/2023intervals/max2.922ms/four fake calls, two calendar imports
  and six fake route queries. Both map a genuine fake total counter and assert usable,
  known EV progress, preserving route/source/authority coverage and worker cancellation.
- Native/standalone desktop and390px views show reported vehicle SoC separately from
  estimated progress, unknown genuine sample time, retained counter/read and credited
  gain. Expanded details and keyboard focus survive updates. Native Enter opens the
  actual `sensor.ev_total_kwh` history; standalone has no fabricated action. Settings
  shows its100000Wh input and compatible Wh/kWh choices; mapping save and cross-view
  stale-edit rejection pass. A labelled display-only source-loss projection shows the
  concise EV pause warning with retained progress; actual ESS independence/watchdog
  behavior is tested separately. Browser warnings/errors are empty. HA built-ins and
  touch are simulated; this is not physical-phone or installation evidence.
- Wheel/sdist4.6.6 build;88runtime source/assets/default files byte-match both archives.
  Isolated wheel imports/version/new modules and final progress asset pass. Screenshots
  and detailed reports remain in the existing ignored artifact/visualization directories.

Exact-head CI/container/image results belong only in the ignored release checkpoint
and final reply. No live HA/database, real notification, hardware or installation
deployment verification was performed.

## 4.6.5 — V45-A001-P2 inline program actions (9 November2026)

Reconciled released main4.6.4/fcb80b5 before the scoped UI follow-up. No backend,
planner/control/permission, catalogue schema or chart code changes.

- 112 focused Python tests pass1.97s: existing profile metadata validation/persistence,
 stable IDs/raw samples/average membership/mode isolation, Bosch/run and native assets.
- 101 frontend tests pass; new cases cover blank Add/selected Rename, Cancel without API
 calls, exact metadata-only request bodies, new ID selection and retained stale drafts.
 Existing source-history, groups, same-ID review, handles/cursor/zoom/pan cases pass.
 Ruff/mypy59modules and every packaged JavaScript syntax check pass.
- Browser checks on both dashboards: create selects the new program with no profile;
 rename prefills the selected legacy/new program, updates names without changing IDs;
 Save/check, Cancel/x and Enter/Escape work. Duplicate and cross-view stale edits keep
 the typed name. Unsaved notes, the existing inline review and a1second trim survive
 metadata saves; the original start handle then moves the linked field to2seconds.
 Bosch has no Add/Rename, browser warning/error logs are empty. Light native/dark
 standalone selector and editor inspected at320px with44px icon targets. The native
 harness simulates HA built-ins; this is not installation or physical-touch evidence.
- Configured local fake E2E passes25.519s/2019intervals/max control4.144ms/four fake
 service calls, including worker cancellation/replacement and recovered persistence.
 These timings are synthetic integration evidence. No live services were contacted.
- Wheel/sdist4.6.5 build;86runtime files byte-match source and isolated version checks are recorded
 in ignored artifacts/p2-package-verification.json. Screenshots retained in the existing
 chat visualization directory as inline-program-actions-narrow.png and native.png.

Full Python/configured+routed/container checks run in release CI. Exact-head remote
outcomes go in the ignored release checkpoint/final reply, without another commit.
No live HA/database/provider/hardware/phone or installation deployment verification.

## 4.6.4 — EV-A007 compact peak and genuine source actions (9 November2026)

Based on released main4.6.3/f1c3ce1. No planner/control/permission/notification-policy
changes. Existing EV safeguards and washing-machine/Bosch behavior remain covered.

- 143 focused Python tests pass5.66s: native mappings/assets, all four measurement
  topologies, polling/live input, measured peaks/history, appliance profiles and Bosch.
 98frontend tests pass; genuine direct/composite/quarter sources and honest standalone,
  demo and missing mappings covered. Ruff/mypy59modules and all JS syntax pass.
- Native contract preview verifies the quarter's Enter/Space action opens the actual
 `sensor.quarter_import_kwh`, the solar chooser opens its selected AC/DC sensor, daily
  import opens its cumulative meter, Bosch power opens its dedicated sensor and a
  profile average opens its captured contributor. No normalized-W sensor is invented.
- Desktop native light/standalone dark and390px native layout show red3px17/9 dashes,
  faded planned peak, unchanged monthly label, alternating/active quarter bands and
  end marker. Monthly and red-SVG quarter remain on the same bottom row. Cursor has
  only its timestamp and Actual/Planned table; Actual cells have genuine source
  actions, Planned cells have none. Native pointer replay changes zoom/pan ranges;
  physical touch/HA built-ins are simulated. Browser console is clean.
- Standalone has no native source buttons; quarter is a span with the native-history
  availability hint. Demo and unmapped behavior are verified deterministically.
- Configured local fake E2E passes25.516s/2019intervals/max control2.228ms/four fake
  calls, including worker cancellation/replacement, restored admission and persistence.
  Timing is synthetic integration evidence, not installation performance.
- Wheel/sdist4.6.4 build; all86runtime source/assets/default files match bytes and
  isolated wheel version/new history-helper asset import passes.

Existing release CI runs the full Python suite, frontend, configured/routed fake E2E,
package and container checks. Exact-head remote outcomes go to the ignored checkpoint
and final reply. No live HA/database, real notification, hardware or deployment test.

## 4.6.3 — EV-A006 peak forecast and quarter display (8 November2026)

Based on main4.6.2 (278cf48); no controller, planner, permission or notification-policy
code changes. Existing washing-machine/EV features are retained.

- 52 focused Python cases pass3.98s: independent current-quarter read/normalization,
 zero and failed other sensor, watchdog, mapped monthly history/alerts, compact
 plan timestamp and versioned native asset delivery.96frontend tests pass, including
 five source-arithmetic/absence/month-boundary/DST/step-clipping regressions.
- Ruff/mypy59modules, every packaged JavaScript syntax check and CLI4.6.3 pass.
- Browser standalone dark/native light on desktop and390px: monthly icon/value stays
 in the bottom row, new quarter immediately to its right, no row overflow. Same red,
2.5px dotted peak with faded future; normal1.2/.9px power, old label, alternating
 bands, active quarter and hollow end marker verified. Keyboard cursor exposes the
 measured/planned contributions and time;390px tooltip remains readable. Actual
 standalone drag/wheel and the labelled native pinch/two-finger replay change ranges
 without losing quarter alignment. The native harness mocks physical touch capture.
- Historical ranges show no future line or active marker. Native unavailable/zero
 monthly values remain distinct, with absent forecast on missing baseline; native
 monthly-peak action still opens the simulated HA history. Both consoles are clean.
- Final configured fake E2E:25.845s,2019intervals,max control2.821ms,four fake calls;
 worker cancellation, restored admission, frozen-source audit and API/persistence pass.
 Only local fake HA/weather endpoints and isolated synthetic archives were used.

Wheel/sdist4.6.3 build and all85runtime source/assets/default files match current
bytes. Isolated wheel version/new peak module asset import passes.

Full-suite, routed E2E and container checks also run in the existing release workflows.
Remote exact-commit outcomes belong in the ignored checkpoint/final reply. No live
HA/database, real phone delivery, hardware operation or installation deployment.

## 4.6.2 — V45-A001-P1 washing-machine programs (8 November2026)

Based on released main4.6.1/8cf94bf.767Python tests pass162.51s;106focused appliance
cases,91frontend cases, Ruff/mypy59modules and shared JS syntax pass. Tests cover stable
legacy/new IDs, additive catalogue persistence, normalized/duplicate/invalid names,
revision rejection, transactional failure, mode isolation, API origin guards and no
appliance commands. Rename preserves recording bodies/samples, selected contributors,
average curve/statistics and byte-identical archived decisions. New programs have no
invented profile and arm through the existing mapped-meter path.

Standalone and native fake dashboards create and rename programs, immediately update
record selectors/groups/review headings, and retain a legacy record/average and its
unsaved1second trim draft/handle. Reload shows both added and renamed names. Duplicate
and cross-dashboard stale edits reject while retaining the draft. Bosch exposes no manual
catalogue forms. Original handles, foldable groups and same-ID trim flow remain present.
All entities/traces are synthetic/local; no live HA/database/provider, real notifications,
hardware operation or installation deployment. Wheel/sdist84runtime files match source,
isolated4.6.2 import passes and an independent SQLite connection verifies persistence.
Final configured fake E2E25.464s/2019intervals/max control3.353ms/four fake calls passes;
subsequent remote outcomes belong in ignored artifacts/v462-release-state.json.


## 4.6.1 — EV-A003, EV-A004 and EV-A005 (8 November2026)

Based on released4.6.0/main6031411, incorporating4.5.8. No live HA/database,
installation hardware, real notifications or deployment was used.

- 755 Python tests pass159.71s, including real spawned-worker recalculation with an
 unchanged10A command, SoC lead/own-target/source/authority stops, useful PV interruption,
 held and fractional slots, exact quarter energy with fake EV/meter delays, future ESS
 reserve/DC release, next-quarter tails, permitted pulses and unavoidable household load.
 Existing measured-peak alerts, approvals and Bosch scheduling remain covered.
- Cautious tests cover spare/tight post-PV capacity, travel, no PV, held partial slots,
 initial known solar, future DC capture with the margin once, margin-only infeasibility,
 timeout versus proof, accepted appliance timing, tampered source/progress/scope evidence,
 fallback activation/target limits and persistent fake-phone retry/deduplication/clearing.
- Final concurrent-delivery regression:7focused deadline/planning-attention cases
  pass4.26s. A shared async lock prevents adoption and retry from sending one notice
  simultaneously. Ruff/mypy remain green after this focused correction.
- 89 frontend cases, Ruff/mypy59modules, all packaged JavaScript syntax and CLI4.6.1 pass.
 Standalone dark/native light browser checks show the same synthetic margin warning,
 retained limit and fake delivery state, with no approval buttons or console errors.
 Existing red measured-peak history remains present. Native HA built-ins are simulated.
- Configured fake E2E25.806s/2019intervals/max control4.269ms/four fake calls passes,
 including actual worker cancellation/replacement, persistence and restored admission.
- Routed-calendar fake E2E61.117s/2023intervals/max control4.068ms/four fake calls,
  two calendar imports and six local route requests passes.
- Physical infeasibility remains nominal best effort without a futile peak request,
  even when a diagnostic raises the ceiling. Both earlier retained equal-energy
  research results still pass current independent physical/rolling audits; the saved
  rejected rolling-cost trial remains explicitly rejected historical evidence.
- Wheel/sdist4.6.1 build;84runtime source/assets/default files match current bytes.
 Isolated wheel imports/version/new cautious module and warning asset pass.

All nine replays below ran serially from fresh snapshots under seven-day/five-minute/
120s limits. Final physical/rolling/certificate audits pass, including source/progress/
activation/reservation metadata. Every updated replay has a certified fallback.
Archives and raw attempts remain private under ignored `artifacts/ev-acceptance/`.
EV/grid quantities are battery kWh; costs are whole-horizon EUR. Starts count transitions
from the observed state, so a held already-running task can have zero starts.

| Replay | Seconds | Terminal EV | Direct-grid EV | Bill | Comparison | Peak kW | Starts |
|---|---:|---:|---:|---:|---:|---:|---:|
| Grid-only baseline |117.45|37.4078|9.0635|19.19449|10.88962|4.950|17|
| Grid-only updated |107.35|37.4250|8.3831|19.16363|10.90019|4.950|13|
| Mixed-PV baseline |118.30|29.1951|1.1720|2.79946|-2.58138|2.783|11|
| Mixed-PV updated |105.20|28.6268|1.2633|2.89152|-2.36311|2.783|6|
| PV/travel updated |93.51|37.4117|0.0000|3.57591|-1.09797|5.490|3|
| Synthetic mixed updated |78.16|28.0040|3.0360|26.23804|23.52060|3.500|1|
| Synthetic held/partial updated |13.48|21.1728|1.1728|26.06523|25.66704|3.500|0|
| Equal-energy baseline |118.07|29.1951|1.1720|2.79946|-2.58138|2.783|11|
| Equal-energy updated |106.76|29.1951|1.1720|2.79946|-2.58138|2.783|11|

Fresh runs have different optional EV quantities; reduced starts alone do not prove a
continuity improvement at equal benefit. The conditioned pair fixes final EV/direct-grid
energy, common required reference and shared cash/comparison envelope, and retains the
same11starts/cost. No equal-energy advantage is claimed. Earlier restricted research's
rolling-cost rejection remains historical evidence; the independent rolling checker
is unchanged and all retained results must still pass it. Time-limited searches retain
unresolved windows and raw statuses; none is labelled a global optimum or installation
performance guarantee. No unavailable-slot index rewrite was adopted after the research
found identical presolved counts. Physical stock bounds admit checked references and
are disabled for relaxed-service diagnostics.

Remote exact-head results are recorded only in the ignored checkpoint/final reply.

## 4.6.0 — EV-A002 (8 November2026)

Integrated with main4.5.8 (`9daa786`) before release. Combined checks:726Python
tests151.64s,89frontend tests, Ruff/mypy53modules and all dashboard JS syntax pass.
The full suite includes Bosch managed execution, profile migration/same-ID trim saves,
background accounting, EV/ESS admission and new measured-peak/archive regressions.
Configured synthetic E2E:2019intervals,25.515s accepted solve,3.333ms maximum control
response, four fake service calls; real worker cancellation, restored-plan admission
and the measured household-background path pass. All inputs/endpoints are fake/local.
All78runtime files match the final wheel/sdist; isolated4.6.0 wheel import passes.
Remote exact-commit CI/publication results belong in ignored artifacts/v460-release-state.json.


Grouped measured-peak notifications and archived peak steps are implemented on
`codex/ev-a002`; V4.5.8 integration was authorized8 November2026.
The results below are the initial isolated implementation evidence. Combined
verification is recorded separately before release.

- Fake phone tests cover initialization, billing floor, sliding15-minute grouping,
  persistent deduplication/retry, offline rises, month reset and independent input failure.
- Archive/frontend regressions preserve exact step timestamps, zero/reset values,
  unavailable readings and bounded coarse buckets. New cases use synthetic data.
- Full Python suite686 passed in146.05s; focused Python30 passed; frontend87 passed.
  Ruff/mypy49 and changed JS syntax pass. Two old SyntheticHA fakes were updated
  to expose the adapter's input-reading interface before the final green suite.
- Configured fake E2E:2019 intervals,25.715s solve,5.592ms maximum control response,
  four fake service calls, including real worker cancellation and restored-plan admission.
- Browser inspected recorded Overview steps and final Current month peak label with
  a clean console. The archive fixture is explicitly synthetic; no installation evidence.
- Wheel and source distribution build; all73 runtime files match current source.
  Isolated wheel import reports4.6.0 and loads the measured-peak module.
  Windows reported temporary sdist-directory cleanup locks after creating the archive;
  both final artifacts were produced and their runtime bytes verified.

No live HA/database access, real mobile notification, hardware operation or deployment.


## 4.5.8 — ARCH-018 recording-list/trim cleanup (8 November2026)

721Python tests pass150.18s,88frontend cases and Ruff/mypy52modules. Synthetic migration
cases cover latest save-time ordering versus insertion/capture date, preserved inclusion/
exclusion, aliases, absent original, raw conflicts, transactional failure/restart/idempotence,
unrelated equal-date/notes runs,111-record access and unchanged frozen decisions. Repeated
same-ID trim saves preserve samples/counts and update averages atomically; stale and invalid
edits remain blocked. Queued M2 work detects updated selections despite unchanged IDs;
accepted/running curve evidence remains frozen. Existing scheduling/EV/ESS tests pass.

Both standalone and native browsers show foldable program summaries, compact rows and
one inline original editor. Verified44px handle drags→fields, fields→handles, keyboard,
shading, power/time cursor, zoom/pan and Full recording/Show selection. Two repeated saved
trims keep identity and total6 fixture entries; a native reload sees saved40/3900 bounds,
then native save keeps the same ID/count. Opening another entry leaves one form/editor.
Native420px layout has matching panel client/scroll width385px. All traces/endpoints are
labelled synthetic; no installation data or real hardware/phone/deployment was accessed.
Physical touch and live upgrade behavior remain unverified. Closed native rows are79px
with direct Details/Delete access after scoped spacing fixes. Wheel/sdist77runtime files
match source; isolated4.5.8 import passes. Final configured fake E2E25.727s/2019intervals,
max control3.811ms/four fake service calls passes. Remote results belong in ignored
artifacts/v458-release-state.json and the final reply.


## 4.5.7 — V45-A002-M2 (8 November2026)

708Python tests pass151.27s;87 frontend cases. Final lifecycle/estimate reset regression
passes15 cases; Ruff/mypy51modules pass. Synthetic source/physics tests conserve partial
interval and full-tail energy, fixed running phase and standalone standby, reject ESS
support from an unchosen start and unrelated-quarter peak permission, and keep elapsed
deadlines as explicit queued conflicts. Lifecycle cases cover persistent Ready without
writes, zero native delay/ASAP consent, door reopening, selected-program/profile loss,
request races/revisions, ambiguous transport/restart/no replay, first-seen-running unknown
phase, scoped approval, conflict notification and automatic original-feasibility recovery.
Legacy decision checksum/recovery remains compatible when no appliance is present.

Synthetic7day2017interval/2961point four-hour-profile joint solve is accepted and audited
in58.83s within60s. Full1.114kWh curve plus measured standby is counted once; mean239.1min
is distinct from the longer measured tail. Both standalone and native browsers verify
Ready/deadline/persistence and scheduled fake execution through Run→Finished, no automatic
hardware enablement and disabled in-run cancellation. Native inherited label margins were
corrected; selected/displayed wheel values agree. Browser warning/error logs are empty.
No live HA/database, hardware, real phone, provider or installation deployment was used.
Physical touch, representative-week accuracy and actual scheduling remain live-unverified.
Wheel/sdist76 runtime files match source; isolated4.5.7 import passes. Final configured
fake E2E25.501s/2019intervals, max control4.219ms/four fake service calls passes.
Remote results belong in ignored artifacts/v457-release-state.json and the final reply.


## 4.5.6 — V45-Q017 Bosch idle start repair (7 November2026)

Reproduced4.5.5 discarding valid active-program options when current state was unknown.
The corrected successful read retains validated capabilities with null current state.
A regression using the reported Eco option spelling and entirely fake entities/endpoints
submits exactly one explicit start and creates/confirms a recording only after actual
run/program feedback. Unknown selected program still blocks. Parameterized regressions
reject unavailable active entities, timed-out reads, malformed attributes/options, mixed
invalid options, missing options and a missing requested program, including after an
older valid read. Door/remote/operation/delay/meter/mode/hardware guards remain covered.

72focused appliance cases and690full Python tests pass149.33s;86frontend cases,
Ruff/mypy48modules pass. Configured local fake E2E25.534s/2019intervals, max control
4.148ms/four fake service calls. Wheel/sdist72runtime files byte-match source and isolated
wheel import reports4.5.6. No UI or managed scheduling change; no live HA/database access,
appliance operation, real notifications or deployment. Actual installation remains
unverified. Remote results go in ignored artifacts/v456-release-state.json and final reply.

## 4.5.5 — V45-A002-M1 (2 November2026)

681Python tests pass147.30s;86frontend cases, Ruff, mypy48modules and dashboard JS syntax
pass. New synthetic regressions cover panel/app runs, quiet phases, waiting/finish/error/
missing state, first-seen-running/restart evidence, program changes, meter gaps, reviewed
inclusion and raw HA identities. Manual actions distinguish selected from active program,
check door/permissions/native delay/meter/mode/hardware generation and never replay after
restart. Pending/failed/late feedback is explicit. Permanent deletion tests cover confirmation,
revision/origin guards, transactional rollback, sample/membership removal, independent trim
survival, restart and in-flight-read suppression. Existing washing-machine/Mazak and all
planner/control regressions pass.

Configured local fake E2E25.540s/2019intervals, max control4.287ms/four fake calls. Extended
--profiles-fixture adds explicit synthetic Bosch entities/programs, automatic capture
examples and a60second fake manual-start trace. Standalone browser verified only one card
expands; program selection leaves idle feedback and Start produces run feedback/capture.
Native preview saw finished feedback and review, linked trim keyboard/numeric fields,
preview energy/duration and explicit save into that HA program's average. Legacy profiles
remain distinct. Delete confirmation survives ordinary polls; API tests perform deletion.
Unapplied program choice survives page reload while Start stays disabled until device selection matches. Both browser logs are clean. Wheel/sdist72runtime files match; isolated4.5.5 imports pass.
All measurements/endpoints are synthetic/local. No live HA/database/hardware/phone/provider
or installation deployment; physical touch and actual appliance behavior remain unverified.
Remote CI/publication evidence belongs in ignored artifacts/v455-release-state.json and final reply.

## 4.5.4 — Saved trim correction (31 October2026)

652 Python tests pass148.33s;82frontend cases, Ruff/mypy47 and dashboard JS syntax pass.
New regressions cover immutable raw samples/old summaries, one weight per physical
capture through successive revisions/restoration, stale/unreviewed/invalid trim guards,
sample-copy rollback, endpoint origin/security and returned revision. The exact saved
UI state now has an editable revision form; labelled HTML sliders render above the SVG.

Configured fake E2E25.519s/2019intervals,
max control3.759ms/4fake calls.
Native browser measured both grips at44x44CSSpx and dragged both saved bounds; two
successive saves created revisions without increasing contributor count. Restoring the
original returned the original mean/count2. Standalone saved trimming/keyboard passed;
browser logs clean. Physical touch and the actual installation remain unverified.
Wheel/sdist71 runtime files match; isolated4.5.4 imports/new API/assets pass.
No live HA/database/hardware/provider/notification/deployment. Remote results only in
ignored artifacts/v454-release-state.json and final reply.

## 4.5.3 — Appliance chart controls and multi-recording means (31 October2026)

647 Python tests pass147.21s;80frontend cases, Ruff/mypy47 and every dashboard JS
syntax check pass. Regressions cover start-aligned equal-weight means, unequal duration/
zero completed tails, fractional trims/mean energy, membership deduplication/removal/
restore, legacy single selection without implicit inclusion, original sample retention,
revisions during worker reads, invalid evidence and endpoint/asset/security behavior.
Shared cursor tests retain existing Overview navigation and add a single appliance plot,
sample holds/gaps, one-second zoom, wheel/pinch, bounded windows and noncrossing handles.

Configured local fake E2E25.464s/2019intervals,
max control4.205ms/4fake calls.
Synthetic recording fixture:two accepted cycles, complete review and gapped review.
Native browser verifies thinner Overview/Planning curves; mouse/keyboard trim↔seconds,
timestamp/W cursor, wheel zoom, pan, selected window, save/add/remove2→3→2 average while
retaining raw evidence, and light/dark. Standalone zoom/gap reporting passes; logs clean.
Pinch/two-finger behavior has synthetic gesture coverage, not a physical touch-device test.
Wheel/sdist71 runtime files match source, isolated4.5.3 imports/new asset pass.
No live HA/database/hardware/provider/notification/deployment. Remote release results
belong only in ignored artifacts/v453-release-state.json and the final reply.

## 4.5.2 — P1 daily grid energy (31 October2026)

Full639 Python tests pass147.80s; final62 focused pass4.54s, including two subsequent
reset-metadata/mapping cases (641 cases exercised locally).77frontend cases, Ruff,
mypy46modules and every dashboard JS syntax check pass. Tests cover cumulative Wh/kWh,
no power/archive dependency, independent missing directions, invalid/nonfinite/negative
values and power units, unavailable/late midnight history, no first-read fallback,
recovery, counter decreases/reset metadata, durable reopened SQLite baselines, mapping/
demo isolation, local-midnight rollover and both DST transitions, coalesced reads and
HTTP failures, archive timeout, settings-save/restart/upgrade and missing forecast
subtotals. Existing history-power graphs and control inputs retain their behavior.

Configured fake HA E2E25.488s, 2019intervals,
max control2.926ms, 4fake calls,
saved-plan recovery79.693ms.
It explicitly supplies invented cumulative counters and local fake HA history.
Native Settings selectors and P1 source/coverage plus standalone Overview/history
were browser-verified with clean logs. Wheel/sdist69 runtime files byte-match;
isolated4.5.2 import/assets pass. No live HA/database/credential/hardware/provider/
notification or installation deployment. Remote CI/image results are recorded only
in ignored artifacts/v452-release-state.json and the final reply.

## 4.4.17 — Joint source allocation during charging refinement (30 October 2026)

598 Python cases exercised locally: full run: 596 passed in 187.36 s, followed by corrected
attempt-name assertions and all 17 horizon cases passing in 23.13 s. Final 67 continuity,
timing, recovery and source-hint cases pass in 79.12 s. Includes varied AC/DC efficiencies,
house loads, held prefixes, boundary stocks, quantity/readiness, shared cost bounds,
timeout history, stale proofs, exhausted-stage fallbacks, and invalid relaxed power
rejected before a checked integer fallback. 66 frontend cases, Ruff, mypy (44 modules), CLI and
4.4.17 wheel/sdist/import checks pass; all 66 source/assets/defaults match.

Frozen replays use the original 120 s budgets, checksum-verified inputs and original-model,
independent physical/source/permission and rolling audits. All listed audits pass.

| Frozen case | Seconds | EV sessions | Comparison EUR | Unresolved windows |
| --- | ---: | ---: | ---: | ---: |
| Supplied decision(4) | 108.75 | 4 | -3.451836 | 0 |
| Supplied decision(5) | 114.90 | 5 | -0.697407 | 0 |
| Earlier November | 117.70 | 5 | -4.754643 | 1 |
| Later solar | 102.69 | 5 | -2.514645 | 0 |

Both supplied daily splits become one session with unchanged battery energy:
30 October, 11:15–13:45 / 3.105 kWh and12:15:19–14:40 / 3.027966 kWh (Brussels). Later solar retains
one 13:10–16:00 session / 7.524094 kWh and reaches 79.989% SoC. November 1/2 remain one session
each. The older November case retains a 5 min gap on 30 October (16:00–16:05), 5 sessions
versus 4 in the previous release's bounded replay; comparison −€4.754643 versus −€4.733197.
Its incompatible relaxed source point is rejected and integer refinement times out.
This is unresolved, not proof of a necessary gap or a global optimum. Do not claim
fragmentation is eliminated throughout every forecast.

Final supplied/November replays include pruning and source warm hints. Solar predates
only those search-order/start changes. Original constraints, one shared €0.02 cash/
comparison allowance, live control and rescheduling remain. Restoring LP indicators
changes no physical power; full integer/model/independent checks gate adoption.
An invalid relaxed point is only a hint to a free integer solve. Failed shortcuts
cannot hide broader timeouts. Valid fallback plans remain executable.

Routed fake E2E: 71.05 s acceptance, 2,023 intervals, 2 journeys / 6 fake routes / 4 fake calls;
maximum control tick 7.73 ms, saved-plan recovery 97.57 ms. Includes infeasible-profile pruning and
predates only warm hints; exact-head CI repeats both local application fixtures.
Generated tracked report restored byte-for-byte. No live provider/HA/database/credential/
hardware/notification or installation deployment. Private evidence/original bytes:
artifacts/v4417-joint-continuity/ and prior ignored review folders. Remote results go
only in the ignored release checkpoint/final reply.

## 4.4.16 — Full-horizon charging continuity (29 October 2026)

590 Python tests pass131.33s;66 frontend tests, Ruff, mypy44 modules, CLI and4.4.16
sdist/wheel checks pass.66 source/assets/defaults match; isolated wheel import passes.
Deterministic fixtures move equivalent opportunities across all seven forecast days,
varied50/65/70/80/85/90/100% limits and grid/solar work. Cover complete interval accounting,
multiple-window preservation, no stacked allowance, overnight/availability, partial
trip tails, early solar bursts, saved-time reuse, required-versus-surplus readiness,
fixed-EV dispatch quality, timeout/zero-budget fallback and certification guards.

| Frozen case | Seconds | EV sessions | Comparison EUR | Independent/rolling audits |
| --- | ---: | ---: | ---: | --- |
| November, final goal guard | 111.03 | 4 (original21) | -4.733197 (original6.021312) | Pass |
| Earlier solar | 102.66 | 4; one today | -4.941330 | Pass |
| Later solar | 99.20 | 5; one today | -2.514645 | Pass |

November1/2 charging is one session each (nine each originally). Every2023interval
has a review outcome; final source certification preserves reviewed counts. Imports
fall40.112->3.037kWh in that frozen forecast. Earlier/later comparison improves on saved
4.4.15 benchmarks-3.925916/-0.448130EUR; the latter baseline was also reproduced from
exact4.4.15 Git sources. This is bounded planning evidence, not realized savings or
proof of global economic/operational optimality. Raw stage status remains separate.

Local routed fake E2E passes:71.49s acceptance,2023intervals,2journeys/6fake routes/
4fake calls, max control4.19ms and saved-instruction recovery56.64ms. The two earlier
solar replays and local E2E preceded the final surplus-bound relaxation; final590 tests
and November replay include it. Exact-head CI must repeat both application fixtures.
No live provider/HA/database/credential/hardware/phone or installation deployment used.
Private evidence: artifacts/v4416-horizon-continuity/. Remote results belong in the
ignored release checkpoint and final reply, without a success-only documentation commit.

## 4.4.15 — Continuity across active charging limits (29 October 2026)

573 Python tests pass in 115.19s; 66 frontend cases, Ruff, mypy (43 modules), asset syntax,
CLI and 4.4.15 sdist/wheel pass. New deterministic tests cover 50/65/80/90/authorised100%
model ceilings, required65/90/100% targets, already-satisfied/absent named targets, held
charging, time-varying ceilings, valid-candidate retention on timeout and repeated cost
references. Full-planner tests deliberately return fragmented economic candidates under
multiple configured limits and verify inherited normal/proven-exceptional authority.
An irregular first charging interval verifies exact selected quantity and safe smoothing.

Private supplied exports remain unmodified and uncommitted. Digests, original-model
rows/bounds/integers, independent physical/source/permission and rolling audits pass.
The supplied four-session decision replays as one 13:51–16:00 Brussels session with the
same 3.266051kWh at the original120s budget (99.57s elapsed). Both earlier solar decisions
also retain their first-day7.262/7.524kWh and reach about80%, now in one session each
(101.24/99.91s). No global optimality or realised-savings claim. A12s stress replay remains
valid within11.34s but can retain fragmentation when the bounded smoothing search times
out; constraints are never relaxed to force a continuous result.

Configured routed fake E2E passes 2023 intervals, two journeys, six fake route queries and
four local service calls. Acceptance 65.84s, max control tick 3.32ms,
cloned saved-plan recovery 58.23ms. All endpoints/notifications/actuators are fake;
no live HA/database/provider/Google/credential/hardware/phone or installation deployment.
Ignored evidence: artifacts/v4415-optional-continuity/release-final/ and release-state.txt.

## 4.4.14 — Consistent energy direction arrows (29 October 2026)

66 frontend tests and15 focused native-dashboard/release tests pass (10.31s). The existing
mixed actual/forecast energy regression verifies → for grid import/ESS charge and ← for
grid export/ESS discharge, with original values and missing/stale/partial handling intact.
The shared renderer serves native and standalone summaries; asset syntax passes. No
energy accounting, numeric sign, planning, sensor or actuator behavior changes. No live
services/database/provider/credential/hardware/notification or installation deployment.
Exact-commit CI/image results are kept in ignored artifacts/v4414-direction-arrows/.

## 4.4.13 — Reliable solar allocation (29 October 2026)

552 Python tests pass in102.39s;66frontend cases, Ruff, mypy43modules and asset syntax
pass. New deterministic cases cover DC export under converter limits and idle direction
flags, AC charging exclusion, later DC capture replacing early AC filling, unavailable
EV, normal health ceiling, future ESS/earlier EV preservation, a later capture window,
no useful EV-value assumption, invalid solver output and no-incumbent/global timeouts.
Legacy timeout cases explicitly remove warm candidates when testing recovery; a separate
case verifies that a valid starting schedule survives the deadline with no extra solve.
Raw solver failure/optimality evidence is not rewritten to claim a stronger result.

Configured routed fake E2E passes2023intervals/2journeys/6fake route queries/4local service
calls;66.44s acceptance/max control tick2.91ms;cloned archive recovery72.35ms. All services,
notifications and actuator endpoints are local fakes. No live HA/database/Google/provider,
credential, hardware, phone or installation deployment access.

Both private supplied exports have verified input/result digests and are replayed offline
at12s and120s budgets. Public automated tests use synthetic inputs; installation telemetry
is not committed. At12s the earlier case delivers7.262kWh to the EV on its first day and
reaches79.97% over the horizon; the later case retains7.524kWh/79.99%. Durations11.64/11.80s;
original model rows/integers, independent physical/source/permission and rolling checks
pass. The improved first-window allocation corrects an initial experiment that split the
small budget too thinly across days. At120s both pass in102.26/101.32s:7.262/7.524kWh EV
charging on the first day,79.98/79.99% maximum EV SoC, and essentially zero unused DC
across the seven days. Combined economic comparisons improve7.926→-3.946EUR and
6.546→1.050EUR against the supplied original schedules, under the existing assumed stored
energy values; these are forecast comparisons, not realized savings. All physical/source/
permission/rolling and original model checks pass. CLI/sdist/wheel4.4.13 pass;15 affected
solar/recovery cases pass again after final readability review. Private evidence and
exact-commit remote results:artifacts/v4413-solar-capture/.
The narrow solar/source stages' Optimal statuses do not prove global economic optimality.


## 4.4.12 — ESS display direction (29 October2026)

43 focused native dashboard/polling/history/settings/release tests pass13.38s;66frontend
cases, asset JavaScript syntax,Ruff,mypy42modules,CLI andsdist/wheel pass. A deterministic
mixed archive/recent regression verifies both ESS signs, missing gaps and unchanged raw
samples, archive arrays, grid values and SoC. Daily charge/discharge kWh totals stay
unchanged while arrows match the new display convention.

Configured routed fake E2E passes2023intervals/2journeys/6fake route queries/4local service
calls;66.03s acceptance/max tick6.68ms;cloned compatible archive recovery56.97ms. Standalone
visual/cursor check shows planned AC charging+437W; native HA-contract preview with raw
+1500W discharge shows-1500W, unchanged400W house and50percent SoC. Light native/dark
standalone layouts remain intact. These are synthetic fixtures, not installation evidence.
AC converter exchange remains distinct from net battery power/direct DC charging. No
planner/control logic or raw evidence sign changes, live service/hardware/credentials or
installation deployment. Ignored local release evidence:artifacts/v4412-ess-sign/.

## 4.4.11 — Saved-plan startup recovery (28 October2026)

540 Python tests pass98.47s;65 frontend tests, Ruff, mypy42modules and CLI4.4.11 pass.
New synthetic lifecycle tests run real hardware-enable/control/planning loops while the
optimizer is deliberately blocked:6A charging continues without an unnecessary forced
stop, recovered instructions remain intact, and the next real snapshot builder holds
the recovered request rather than startup's dry-run zero. Closing still sends stop.
Readiness can recover later without solving; structural invalidations/Off cancel it.
Changed settings/capabilities/policy/goals/permissions, connection change, faults,
stale forecast, elapsed horizon, missed travel, legacy/malformed context, altered flows
and corrupt/compressed archive data never regain authority. Backend recovery identity
allows current session display only for the matching valid plan and current revision.
No historical economic comparison is rerun using live values.

Configured routed fake E2E passes2023intervals/2journeys/6fake route queries/5local
service calls; acceptance65.96s/max control tick4.19ms. A cloned synthetic accepted
archive regains authority in57.45ms, with no solver/provider/actuator call and unchanged
accepted evidence. This measures reconciliation after supplied fresh readings, not
installation startup/charger-settling time. Existing cancellation/latest-only adoption,
checksum, fault and guarded control checks pass. Initial fixture pending-settings
rejection was corrected by modelling changed active settings accurately.

No live HA/database/provider/credential/hardware/phone or deployment access. Older
plans lack the new configuration identity and require one fresh4.4.11 calculation;
shutdown stopping and normal live safeguards remain. Evidence stays ignored under
artifacts/v4411-plan-recovery/. Remote exact-head release results are recorded separately.

## 4.4.10 — Bounded EV waiting and optional Ford state (28 October2026)

519 Python tests pass102.40s; final146 affected control/incident/configuration/native
cases pass6.19s.64 frontend cases, Ruff, mypy41modules and the4.4.10 package build pass.
Cases cover exact119/120second blocked escalation (including the supplied incident's car-
complete state), unchanged90second confirmed non-delivery, mixed status/current changes
without timer resets, actual-power recovery and intentional stops. Configured FordFAULT
immediately stops/latches, persists selected attributes and prohibits reboot; pending/
rebooting/verifying recovery cannot falsely succeed. Acknowledgement requires fault clear.
Unavailable/unknown/future optional states preserve ordinary power supervision but cannot
qualify reboot. Source telemetry age remains unknown despite a current HA read. Blank
configuration compatibility, saved sensor wiring, native history and diagnostic red/
unverified states pass. One initial full-run failure exposed an unsynchronized second
example template; the templates were synchronized before the successful full run.

Configured routed fake E2E passes2023intervals/2journeys/6fake route queries/4local HA
calls; acceptance65.66s/max control tick3.06ms. It reads configured IN_PROGRESS/attributes
from fake HA, preserves unknown vehicle measurement age, and verifies independent control,
worker cancellation/latest-only adoption, immutable-snapshot admission and checksums.
The incident's5776-event export is private ignored evidence; no new diagnosis of the
initial stop is claimed. No live HA/provider/database/credentials/hardware/notifications
or installation deployment. Remote exact-head checks are recorded after publication.

## 4.4.9 — Earlier required grid charging (28 October2026)

502 Python tests pass99.06s; the final27 focused timing/continuity/release-contract tests
pass37.08s.63 frontend cases, Ruff, mypy40modules and CLI4.4.9 pass. New deterministic
cases cover a delayed overnight session moving to the first valid opportunity, a held
start, existing quarter-peak constraints and ESS dispatch, tighter health ceilings,
useful later PV allocation, fixed required-grid quantity and checked-incumbent retention
when the timing solver returns no feasible solution. Candidate checks include every
original and timing-model row/bound/integer, plus independent physical/source/permission
and applicable rolling checks. Empty sparse rows and invalid integer/non-finite values
are also covered. All inputs/services are synthetic/local or the supplied frozen export.

The supplied export's SHA-256 and snapshot/result digests verify. A complete seven-day
replay is valid in106.77s with no independent or rolling errors. Its first6A/1.38kW
session moves from29Oct00:15–02:35 to28Oct21:15–23:35 Brussels, after the21:13:59 hold,
with the same2.898kWh,9.557428EUR predicted bill and5.49kW peak. The timing solve reaches
its bound; a checked earlier incumbent is retained. Final minimum-grid certification
succeeds in its bounded scope; global economic optimality is not claimed. Private
reproduction and reports remain ignored under artifacts/charging-delay-review/.

Configured routed fake E2E passes2023intervals/2journeys/6fake route queries/4local HA
calls; acceptance65.89s and max control tick4.19ms. Worker cancellation/latest-only
adoption, checksum persistence and guarded fake operations pass. No UI/control-policy
change or live installation, provider, credential, database, hardware or notification
access. Remote CI/image results are recorded separately after release publication.

## 4.4.8 — Compact EV details (28 October2026)

25 focused native/dashboard/schedule API cases pass0.63s;63 frontend cases and Ruff pass.
Frontend regressions check escaped goal names, distinct driving/target values in one
row, short target-only rows, brief unknown/legacy fallbacks and unchanged input metadata.
Configured routed fake E2E passes2023 intervals/2journeys/6fake routes/4local
calls; acceptance60.94s/max tick5.16ms.
Standalone/native browsers show only title,time,battery kWh and Supports rows, with no
generic reason/accounting/stock/caveat blocks. Warning/error consoles are empty. Proof:
v448-compact-session.png in the task visualization folder. Temporary tabs/servers closed.
No attribution/optimizer/controller/permission changes or live installation access.

## 4.4.7 — Rolling Overview goals (28 October2026)

25 focused native/dashboard/schedule API cases and63 frontend cases pass. All shipped
JavaScript syntax, Ruff and CLI4.4.7 pass. The diff changes only card visibility and
displayed goal selection; no planner, controller, accounting or persistence changes.

Configured routed fake E2E passes2023 intervals/2journeys/6fake route queries/4local HA
calls; acceptance60.77s/max control tick5.20ms. Standalone and native HA-contract browsers
show only the next morning and first trip on Overview, excluding the later trip and
six later morning goals. Planning shows all9 goals and forecast costs. Switching back
restores the2-goal window and hides costs. The current-charge meter remains on the
earliest goal only. Warning/error consoles are empty. Screenshot:v447-overview-24h.png
in the task visualization folder. Temporary tabs/servers are closed. The window uses
strictly future deadlines through now+24 elapsed hours; an empty list has an explicit
message. All services/data are synthetic/local; no live installation/API/hardware used.

## 4.4.6 — Named EV session contributions (28 October2026)

496 Python tests pass88.41s;19 focused attribution/native cases pass1.84s. All63 frontend
cases, shipped-JS syntax, Ruff and mypy39 modules pass. Deterministic accounting cases
cover8kWh split6/2 across actual trips, initial-stock-first use, multiple sessions,
no backward deadline attribution, sessions crossing checkpoints, repeated/increasing/
simultaneous morning/manual targets, reserve retention, overlapping departures, unknown
battery barriers, remaining inventory, untouched ESS sessions and a real Planner output.
Driving/stored/unresolved energy conserves each session's delivery; first target support
is bounded separately. Frozen flows remain unchanged. Render tests cover named kWh,
non-additive target support, escaped goal text, unresolved/retained stock and old plans.
The versioned native asset endpoint serves the new session-details module.

Configured routed fake E2E passes2023 intervals,2 journeys,6 fake route requests and4
local HA calls; acceptance60.66s/max control tick4.14ms. Its real spawned HiGHS result
passes the new session-energy conservation/named-goal assertions plus existing frozen
admission, cancellation/reaping and latest-only adoption checks. Standalone and native
HA-contract browsers show a0.28kWh session attributed only to the31October morning
requirement, with retained stock and overlapping target support explicitly labelled;
the old all-future-goal count is absent. Warn/error consoles are empty. Screenshot:
v446-session-contribution.png in the task visualization folder. Temporary tabs/servers
are closed. All endpoints/data are fake/local; no live installation or provider access.

## 4.4.5 — Goal presentation (28 October2026)

25 focused native/dashboard/schedule API tests and61 frontend cases pass. All shipped
JavaScript syntax, Ruff and the4.4.5 CLI pass. This presentation-only change leaves
planner, controller, goal lifecycle and persistence source unchanged.

Configured synthetic routed E2E passes with2023 intervals, two journeys, six fake Maps
queries and four local HA calls; acceptance60.77s, max control tick4.17ms. Real spawned
HiGHS/manual cancellation/reaping/latest-only adoption remain exercised. Standalone and
native HA-contract previews show chronological morning/trip interleaving, exactly one
labelled current-charge bar and no Overview goal card, including after navigation back.
The89km fixture shows16.02kWh driving separately from its reserve-inclusive35.7% target;
the EV selected-day agenda uses the same energy estimate. Warning/error consoles are
empty. Screenshots live in the task visualization folder; v445-planning-goals.png shows
the chronological cards and single bar. Both temporary tabs/servers are closed.
All data/endpoints are synthetic/local; no live HA/Google/database/hardware/phone used.

## 4.4.4 — Frozen schedules and adaptive execution (28 October2026)

482 Python tests passed86.69s;61 frontend cases, all shipped JavaScript syntax, Ruff
and mypy38 modules pass. Synthetic regressions verify frozen candidate/reference
physical/source/grid/economic rejection, separate admission evidence, unchanged flows/
goals/reservations/costs, elapsed instruction/withdrawal handling, and both higher/lower
EV/ESS publication stocks. They reproduce the supplied0.234kWh inventory increase and
0.14175kWh apparent excess without substituting newer stock into the original proof.
The two private Downloads exports are no longer available; this is a labelled numerical
reproduction, not a new raw-log replay.

Live-control cases retain ESS demand balancing/PV absorption and EV power modulation
through heavy load and changing PV. Lost solar cannot become optional grid charging.
Quarter/source limits, stale/unknown/settling/future inputs, invalid battery/provenance,
connection/EV-state availability, elapsed horizon and stale forecasts retain guards.
In-flight numerical drift does not cancel work. Sustained forecast corrections, new
issuances, inventory deficits and higher measured peaks do not request extra solves or
revoke authority; periodic planning still consumes fresh measurements and forecasts.
Existing structural revisions, worker cancellation, planning failure/recovery and
notification deduplication regressions pass.

Configured offline verification uses fake local HA/Maps/weather/phone endpoints and
real seven-day HiGHS:2023 intervals, two imported/routed journeys, six fake route
queries, four local service calls, manual cancellation/reaping and latest-only adoption.
Routed acceptance60.78s/max control tick4.22ms; standard acceptance25.36s/3.30ms. Both
variants pass. The tool explicitly checks
frozen-snapshot validation, original interval boundaries and separate persisted admission
evidence. These timings are synthetic host-specific evidence, not live commissioning.
No live credentials, provider API, HA/database, hardware or real phone is accessed.

## 4.4.3 — Stable traffic routing and safe diagnostics (28 October2026)

Synthetic duration sequences reproduce the original false rejection. Regressions require
that the final checked departure equals the published departure, predicts on-time arrival
and supplies its own distance, including one-second/subsecond changes, a boundary at the
60second slack and a second adjustment. Genuine unsettled and past timings still reject.
Transport tests distinguish HTTP400/401/403/429/5xx/redirect, timeout, connection, malformed
JSON and no-route responses; non-200 bodies are never read. Worker tests ensure raw
exception details cannot enter public state/failure events and no old estimate is used
following a failed refresh. Home-read failures remain distinct. UI tests cover escaped
failure text and its removal on success.468 Python tests passed85.63s;78 focused
routing/worker cases passed0.96s;61 frontend cases, Ruff, mypy38 and changed-JS syntax
passed. Browser verification confirms safe429 text, actual worker refresh/recovery and
stable repeated resolution; warning/error console is empty. Evidence is in WORK_STATE.md.
No live Google/paid API, installation database, HA, hardware or phone is used.

## 4.4.2 — Expired manual goals (28 October2026)

Synthetic lifecycle tests cover elapsed trip/SoC retirement, complete archived records,
active API/schedule projections, pending-issue cleanup, idempotence, preservation of
other command authority, restart with future/empty saved goals, source ownership,
underway/unknown/external returns and fresh versus stale/unknown/settling home input.
A control-loop test checks retirement without a page request or solver. Frontend tests
cover Underway/Awaiting return labels. 442 Python tests passed86.57s;38 focused lifecycle/replanning cases passed2.78s.
All60 frontend cases, Ruff, mypy38 modules and changed-JS syntax passed. Browser
verification confirms expired goals are absent and retained-trip labels are correct;
the lightweight in-memory fixture intentionally does not provide graph history.
Screenshot and final release state are recorded in WORK_STATE.md.
All data/endpoints are synthetic/local; no actual HA or hardware verification is implied.

## 4.4.1 — Elapsed charging at publication (28 October2026)

The supplied frozen decision reproduces Required outcome rejection before the fix.
The calculated morning stock was23.4142kWh; publication from unchanged measured stock
left23.2600kWh against23.4kWh required. Offline repair adds0.140042kWh in a135.306s
same-phase extension, with all independent and rolling checks passing. No sensor
resolution/calibration or actual installation delivery is inferred. The private log
is not included in tracked tests or release artifacts.

Deterministic synthetic publication tests cover confirmed versus unconfirmed delivery,
separately repaired reference boundaries, one/three-phase continuity, exact energy,
metadata/evidence immutability, withdrawal splitting, failed references and rejection
for disconnected/unavailable charging, deadline, measured loss, peak limit and missing future session.
The unchanged audit now caches cumulative arithmetic: one attached-log reconciliation
fell from19.35s to0.894s locally (single observations, not an installation benchmark).
Final local suite:425 Python tests passed84.43s; Ruff, mypy38 modules,59 frontend
cases and all asset JavaScript syntax passed. Configured routed E2E passed60.800s,
2,022 intervals, two journeys, six fake route requests/four fake HA calls and maximum
local control tick5.587ms. Wheel/sdist match all59 package files and current docs;
isolated wheel imports/resources/version pass. Old/new audits agree on original and
repaired candidate/reference inputs and an intentionally unapproved peak. No live HA/Google/database/hardware/real-notification check is performed.

## 4.4.0 — Google Maps activation and release verification (27 October 2026)

The user authorized Settings-key activation and main release publication. The draft
compile-time gate and extra global enable switch are removed. A saved key applies
immediately; Google validates it on necessary route requests, without a separate paid
validation probe. Blank preserves, replacement/clear applies immediately, and retired
clients cannot issue later legs. Invalid keys/routes remain unresolved. Manual overrides,
in-progress checked away periods and other valid EV work retain their existing guards.

Final repository-root suite: **414 Python tests passed in 87.52s**.74 focused routing/
journey/settings cases pass1.00s, including Settings API activation/rejection/clear without
restart, secret redaction, stale credential results and retired-client request revocation.
Ruff, mypy38 modules,59frontend tests, all JS syntax and CLI4.4.0 pass. The core4.3.20
optimizer/planner/publication/replanning/worker/charger code remains unchanged.

Configured routed E2E passed79.554s:2,022intervals, two89km journeys, six local fake
Google queries, four fake HA service calls and maximum local control tick4.702ms.
Real worker cancellation/reaping and latest-only adoption remain verified. CI now runs
this routed fixture as well as the existing configured fixture. All data/services are
synthetic, including90% initial EV SoC; no real Google/HA, hardware or phone was used.

Browser Settings saved the dummy provider key, returned to a blank password field with
Saved key placeholder, reported No restart is needed, and immediately resolved journeys
through the fake provider. Explicit clear + Save immediately restored unresolved-key
warnings without restart. Console warn/error log was empty. A lightweight synthetic
release preview additionally checked current routed editing; screenshot:
v440-key-activation.png in this chat's visualization folder. All temporary tabs/servers
are closed. These are synthetic UI checks, not validation of the user's credential.

4.4.0 wheel/source archives and isolated imports/resources are checked before commit.
Exact-head CI and amd64 image publication results are recorded after push in the existing
ignored local checkpoint and final reply. No physical installation deployment is claimed.
The inherited publication-accounting limitation from4.3.20 is unchanged by this release.

## Earlier V4.4 compatibility check — 27 October 2026

The isolated Maps branch now uses committed main d48969c (4.3.20), preserving its
charging-continuity optimization, evidence-based replanning, cancellable process
worker, planning notices and current EV dashboard. Main's unrelated DEFERRED_WORK.md
edit remains untouched. A recoverable pre-integration draft stash is retained.

Seven conflicts were reconciled. Startup retains request_plan("startup"); routed goal
changes use the existing Application.changed/request_plan path. Unresolved requests
without a checked goal preserve active same-revision work. The planning_issue list
remains visible alongside route warnings. The EV widget receives its current interaction
object so native history, phase actions and charger activity remain available.
The synthetic E2E tool keeps current cancellation/replacement and planner-failure
fixtures while adding the routing fixture. The retired phase-dwell setting stays removed.

Final combined suite: **411 Python tests passed in 87.14s**; Ruff passed again.
Initial combined suite: 408 Python tests passed in 87.33s. A focused 95-case run in
5.94s includes three added compatibility cases for checked versus pending request
edits during active calculations and coexistence of planning/route warnings. Ruff,
mypy (38 modules), 59 frontend tests and all JavaScript syntax checks passed.

Configured local fake-route E2E passed in 73.671s: 2,022 intervals, two 89km journeys,
six fake Google queries, four fake HA service calls and maximum local control tick
5.020ms. It cancels/reaps a real HiGHS process and adopts only the latest replacement.
The first run exposed an assertion using only the latest 100 events; its matching
cancellation was sequence 34 while the newest event was 171. The tool now checks the
matching request ID directly in its own synthetic archive. No application event
retention or command behavior was changed. The rerun passed.

Native browser checks opened measured-power history for sensor.ev_kw, retained current
phase controls and charger-action display, saved a 101km route override and reset it
to the 89km automatic result. The standalone EV view also renders current controls and
routed journeys. Native warning/error console was empty. Preview evidence:
v44-4320-native-check.png in this chat's visualization folder. All inputs are synthetic;
HA built-in cards are simulated and no real notification/hardware/Google call occurred.

Combined draft wheel/source archives and final docs build locally; all59 package
code/assets/default files match both archives. A separate offline installation passes
routing/replanning/worker imports, current UI resource and disabled-live-gate checks.
Core planner/optimizer/publication, replanning, worker, control and charger files match
committed main exactly. Temporary tabs/servers are closed.

No 4.4.0 release has been published. Draft metadata follows the inherited 4.3.20
baseline; live routing remains disabled pending retention compatibility and release
scope. A special Google agreement has not been established as necessary. This check
does not repair or override 4.3.20's separately recorded publication-accounting limitation.

## V4.4 commit-ready offline draft — 25 October 2026

The isolated branch is prepared for a source commit with live routing disabled. This
is not release or commissioning approval. No commit, push, merge, version bump,
publication or deployment was performed. Special Google approval has not been
established as necessary; retention compatibility remains unresolved.

Final offline checks: **291 Python tests passed in 44.72s**, including eight new
regression cases for malformed attendance/override times, malformed HA home payloads,
and an unrepresentable provider duration. Invalid inputs are rejected before mutation;
a bad route stays unresolved while the worker continues with another valid journey.
The focused routing/calendar/settings/journey run passed 77 cases in 0.95s. Ruff,
mypy (37 source files), all JavaScript syntax checks and 33 frontend tests passed.
Earlier cases also verify route failures without placeholders, persistent overrides,
cancellation/edit during requests, revision/approval safeguards, notification dedup/retry,
credential redaction and same-origin API enforcement. Other valid EV goals continue
through unresolved routes; ordinary actuator connection guards still stop a disconnected car.

Final configured --routing-fixture end-to-end run passed: 2,022 intervals, 71.467s,
maximum control tick 3.248ms, two 89km journeys and six local fake Google queries.
Four fake HA service calls include local notification verification. A real spawned
HiGHS worker accepted the joint plan. All services/data are synthetic, including 90%
initial EV SoC. Machine-readable results are in docs/offline-e2e.json. Earlier legacy
calendar regression passed with 2,021 intervals in 68.891s, maximum control tick 3.337ms.
No installation measurement, hardware, Google billing or real phone delivery is verified.

Draft wheel/source archives built locally with existing 4.3.5 metadata; all 57 package
code/assets/default files matched source byte-for-byte in both archives. A separate
--no-index --no-deps installation passed isolated imports, the disabled routing gate
and packaged route UI resource checks. Artifacts/preview data and the original Maps
archive are excluded. These are draft package checks, not published release artifacts.

Browser verification confirmed that reopening and saving a zero-kilometre manual
route override retains zero and its home times. The unresolved warning says other
valid goals can continue. Evidence: v44-commit-override-check.png in this chat's
visualization folder. Earlier standalone/native checks covered destination correction,
per-calendar selection, masked credentials, phone-width layout and automatic reset.
Temporary browser tabs/servers are closed.

Read-only three-way comparisons against committed main 4fe2291 (4.3.8) found clean
combinations for the overlapping application-view.js, style.css and view.html edits.
DECISIONS.md, VERIFICATION.md, WORK_STATE.md and offline-e2e.json need reconciliation
when integration is authorized. Main also has ongoing uncommitted feature changes;
no merge or overwrite was attempted. See WORK_STATE.md for continuation boundaries.

## 4.3.20 — Joint EV continuity and evidence-based recalculation

362 Python tests pass102.73s;59 frontend tests, Ruff and mypy36 pass. No frontend
changes are included. New synthetic regressions cover one overnight
session, varying current under changing house load, moving ESS support to avoid EV
restarts, retained3p charging, necessary availability/minimum-current pauses, initial
selector/power costs, setting persistence across off intervals, live-switch restart
cost, shared two-cent selection, reference-envelope seeds and sub-tolerance source
rounding. Goals, physical/source/permission and independent audit checks remain.

Replanning checks cover sustained house/AC/DC PV energy evidence, transient/completed
appliance runs, gaps/invalid/repeated observations, correction taper/freshness, changed
issuances with unchanged baseline, expected ESS discharge, material inventory deficits
and unchanged expired-control deduplication. The actual input loop builds a corrected
snapshot once; correction identities prevent reuse of earlier forecast-specific ESS
peak grants. Required EV authority is retained while forecast-driven ESS/conditional
instructions are revoked. Manual cancellation/coalescing and charger timers still pass.

All three serial120s seven-day cases independently validate: mixed104.890s,
winter104.565s, permission118.767s. Mixed comparison is-7.9923EUR versus the historical
same-fixture-7.9707EUR; winter25.4417EUR and permission32.3713EUR. These are time-limited
incumbents with honest bounds/gaps, not global optimality. Mixed/winter grid certificates
complete; permission remains feasible/time-limited. Whole-week session counts16/15/2
include opportunities and necessary pauses; no universal one-session claim is made.

The supplied private decision replays offline in118.722s with independent validation,
one continued3p session up to the next morning requirement,23.4569kWh at that goal and
the unchanged5.49kW peak. Private inputs/results remain ignored. Applying the earlier
unchanged frozen adoption observation still reproduces Required outcome after elapsed
energy is removed. That separate publication-accounting issue remains; no new repair,
SoC credit or weakened goal validation is introduced.

Configured fake-HA E2E passes33.976s/2018intervals/maximum local control4.199ms
(not hardware latency), four fake service calls. It checks spawned cancellation,
latest-only publication, actual HTTP settings/state and independent control. Benchmarks
and E2E use labelled synthetic/local endpoints only. No live HA, installation database,
hardware, real notification or deployment was accessed.
All57 source/assets/defaults match wheel and sdist; isolated4.3.20 version/import and
the new replanning module are verified. A transient Windows metadata rename lock
required one build retry; the final archives are complete and byte-checked.

## 4.3.19 — Overview EV watts and native history actions

334 Python tests pass54.31s;59 frontend tests, Ruff and mypy35 pass. New discovery
coverage checks configured EV diagnostic/current/phase/force entity IDs, omitted empty
mappings and exclusion of credentials/ESS actuator/demo sources. Frontend regressions
separate actual power from command and SoC, preserve signed/zero values, reject missing/
stale display inputs, and verify every mapped sensor has a native button while derived,
unmapped, demo and standalone values do not invent an HA entity action.

Configured fake-HA E2E passes32.449s/2018intervals/maximum local control2.482ms (not
hardware latency), four fake calls; see offline-e2e.json. The synthetic HA-contract
browser preview verifies immediate4140W and−35W Overview updates; power, charger error,
battery and phase more-info events carry the actual mapped IDs. Enter/Space work and
history focus survives subsequent status refreshes. Phase history leaves the selected
mode unchanged. Status colors remain green/red as appropriate; text stays selectable.
Light/dark desktop and390px viewport checks pass:355px EV card within375px document,
no horizontal page overflow. Standalone has measured power and zero entity-history
buttons. Console errors/warnings are empty. The display fixture keeps P1/EV/PV balance
consistent when changing synthetic charging power and never changes backend control.

Proof is in ignored artifacts/release-4.3.19-overview-ev.png and
artifacts/release-4.3.19-ev-history.png. All56 source/assets/defaults match wheel and
sdist, with isolated4.3.19 import verified. Browser proof exercises the HA more-info
event contract; real HA Recorder history and physical touch remain live-unverified.
No live HA, installation database, hardware, real notice or deployment was accessed.
The separately diagnosed planner reconciliation/restart issue is unchanged.

## 4.3.18 — Signed EV readings and sensor-specific validation errors

330 Python tests pass54.58s, followed by36 focused live-input tests0.70s after
refining household contributor labels and adding three topology cases.55 frontend
tests, Ruff and mypy35 pass. Synthetic local HTTP tests accept−1,−35 and−2300W EV
readings, preserve signed graph values and reconstruct the P1 balance. The input-loop
regression retains EV/ESS validity, revision and observation freshness through a
negative EV reading, while real remaining input failures reach UI state and the
archived input_error reason with entity, original state/unit and read time.

The fake go-e startup test passes through negative power to positive delivery without
Stop or a fault. Domain stock validation names the field/value; negative PV, split
grid, quarter demand and monthly peak still fail at their mapped sensor. Non-finite,
unavailable and out-of-range SoC checks remain. All four household topologies identify
only contributing sensors, preserving HousePowerMismatch and settling behavior.
Signed net EV integration retains full sample coverage and other power totals. A
signed-observation snapshot round-trips and solves with independent validation and
positive charging flows. No planned EV discharge is introduced.

Configured fake-HA E2E passes33.639s/2018intervals/maximum local control2.684ms
(not hardware latency), four fake service calls; see offline-e2e.json. All56 source/
assets/defaults match wheel and sdist, with isolated4.3.18 import verified. The frontend
is unchanged; existing rendering and selection behavior still apply. No live HA,
installation database, hardware, real notification or deployment was accessed.

## 4.3.17 — Incident reports include the beginning of long waits

308 Python tests pass53.65s;55 frontend tests, Ruff and mypy35 pass. Eight new
synthetic cases cover immediate,15minute and two-hour detection delays, inclusive
window boundaries, excluded unrelated events, missing/empty/late onset timestamps
and exact10,000 versus10,001event limits. The HTTP export regression verifies that
commands before onset appear in the response. Existing nonblocking worker and
acknowledgement boundary tests pass. No private incident data is used as a fixture.

Reports use onset−5minutes through min(now,detection+10minutes), retaining the read-only
worker, five-second budget and chronological event cap. A capped report explicitly
identifies its omitted tail. The UI already displays this note and truncation flag;
no frontend code changed. The earlier4.3.15 browser evidence remains applicable.
Configured fake-HA E2E passes33.840s/2018intervals/maximum local control4.670ms
(not hardware latency), four fake calls; see offline-e2e.json. All56 source/assets/
defaults match wheel and sdist, with isolated4.3.17 import verified.
Charging, fault and recovery policy is unchanged. No live HA, installation database,
physical hardware, real notification or deployment was accessed.

## 4.3.16 — EV start confirmation across revisions

300 Python tests pass53.49s;55 frontend tests, Ruff and mypy35 pass. Seventeen new
synthetic regressions cover unchanged pending starts across multiple revisions with
zero or already flowing power, a newer revision receiving the matching readback,
current-only changes during startup, and the original30second timeout despite
repeated revisions. The original reproduction sent Stop at+2s; the corrected path
sends neither Stop nor duplicate Start and clears the hold only after new readback.

The guard tests exercise explicit zero requests, phase changes, real charger faults,
expired input frames and hardware disable. They still stop. Identical pending
current/phase/stop settings retain the original deadline; timeout cannot be postponed
by revision churn. An actual enabled/generation revocation after the fake ESS service
but before EV service entry leaves no phantom start acknowledgement, restores the
previous in-flight setting and preserves a restart hold. A fake accepted start with
a lost response retains evidence and later confirms without replaying Start.

Configured local fake-HA E2E passes33.841s/2017intervals/maximum local control5.175ms
(not hardware latency), four fake service calls. See offline-e2e.json. The existing
4.3.15 action strip/countdowns remain included and their model/markup tests pass;
the frontend is unchanged and its4.3.15 browser evidence still applies. All56 source/
assets/default files match wheel and sdist; isolated4.3.16 import passes.
The30s hold,90s delivery timer and
immediate reported-error policy are unchanged. Actual installation cause/recovery
remains unverified without its recent incident trace. No live HA, installation
database, hardware operation, real notification or deployment occurred.

## 4.3.15 — EV controller-action display

283 Python tests pass53.03s;55 frontend tests, Ruff and mypy35 pass. New read-only
activity regressions distinguish restart settling, start readback,90s delivery check,
actual charging, requested stops, disabled control, phase preparation/active transition,
reported errors and stale inputs. Repeated status reads do not write commands or
change the deadline. An unfinished stop with measured power still flowing is shown
as waiting for power to stop rather than controller intent to charge.

Node tests verify real-deadline countdown, elapsed-time extrapolation, expired timers
awaiting a control update, stale status becoming unavailable, demo/missing-source
isolation and escaped diagnostic text. Native preview uses a separately labelled,
display-only30s fixture with a fixed deadline, never repeated fake authority. Browser
checks cover native/standalone rendering, normal verdict consolidation with preserved
fault details, dark/light themes,327px strip at390px viewport and expired-wait behavior.
The active ring/step/remaining/total display is in ignored
artifacts/release-4.3.15-ev-hold.png. Countdown never declares a start by itself.
All56 source/assets/defaults match wheel and sdist; isolated packaged4.3.15 import passes.

Configured fake-HA E2E passes32.798s/2018intervals/maximum local control2.238ms (not
hardware latency), four fake service calls. See offline-e2e.json. This release scope
does not change command sequencing, watchdogs, error policy or any charging duration.
The separate start/revision and immediate-error-latch findings are synthetic code-path
evidence in WORK_STATE.md, not identification of the user's incident. The charging
fix was outside4.3.15 and subsequently authorized for4.3.16. No live HA, installation
database, physical hardware, real notice or deployment was accessed.

## 4.3.14 — Cancel/replace recalculation and visual activity

280 Python tests pass53.42s;54 frontend tests, Ruff and mypy35 pass. Regressions use
real spawned synthetic workers to cancel a running child, cancel during slow spawn,
reap on shutdown, recover after a child exception/crash and keep the event loop
responsive. The parent/public HTTP checks verify202 acknowledgement, rapid requests
coalescing to the newest identity, no same-revision busy queue, material-revision
cancellation, preservation of accepted control, no publication of superseded work
and the existing automatic recovery after process death. Both unversioned and
versioned progress-module assets are served. Existing rejected-plan retry/attention,
negative-power input guards and disconnect protection pass.

The configured local fake-HA E2E cancels an actual full-horizon HiGHS process via
the manual endpoint, verifies the old PID is reaped and only the newest replacement
is adopted. Final fixture result: accepted32.830s,2018intervals, maximum local control
3.287ms (not hardware latency), four calls to fake services only. Results are in
offline-e2e.json. No optimization objective/constraint changes are made in this release.

Browser checks cover immediate Starting/Restarting feedback, real stage/elapsed
updates, restart during a solve, native/standalone entry points, EV-tab activity and
its own button, light/dark themes and a355px component at390px viewport without
activity overflow. Synthetic read timeout recovery and green Plan updated feedback
were observed. The indeterminate bar never claims a percentage. Node checks cover
old GET suppression after POST acknowledgement, failed requests without automatic
mutation retries, selection locks, timer disposal and both button states. Existing
graph gesture/cursor/selection regressions pass. Screenshot evidence stays in ignored
artifacts/release-4.3.14-recalculation.png. All56 source/assets/defaults match wheel
and sdist; isolated packaged4.3.14 import passes. No live HA, installation database,
hardware, real notification or deployment access occurred. Paused Maps and unrelated
deferred-work edits remain separate.

## 4.3.13 — EV restart settling and phase cooldown removal

272 Python tests pass54.63s;51 frontend tests, Ruff and mypy35 pass. Focused
synthetic charger regressions check the exact30second boundary after phase
acknowledgement in both directions, short/long stopped periods, repeated ticks and
plan changes, canceled starts, current-only increases/reductions without stopping,
ESS dispatch during waits, unconfirmed commands, continuing power after stop and
delivery/reboot/notification timing after the hold. Existing charger errors and
stale-input cases remain protected. Old600/900second configuration values and a
missing retired field are readable; planner/independent validation accept phase
changes within the former cooldown. Settings omits the retired control.

Removing the cooldown exposed a later-refinement regression: an exceptional solar
candidate had not exceeded80% in an early window, so the window was left unprotected
and operational polishing moved extra charging into it without scarcity proof.
Unproven windows now retain the normal ceiling, and the final source certificate
inherits the selected ceiling rules. Existing scarce/plentiful-solar tests pass.

Final4.3.13 local fake-HA E2E passes: accepted31.465s,2018intervals, maximum local
control18.086ms (not hardware latency), four fake service calls. It exercises the
normal configured startup, settings, weather, planning and hardware-switch boundary
against isolated local endpoints. The full thirty-second charger sequence is
verified with simulated advancing time in the focused tests, not on physical hardware.
All55 code/assets/default files match wheel and sdist; isolated packaged4.3.13 import
passes. No agent access to live HA, installation databases, hardware, real phone
notifications or deployment occurred. The user separately reported that the standalone
thirty-second script worked; automatic installation behaviour remains unverified.

Sequential seven-day benchmarks pass independent validation and minimum-grid
certification: mixed115.705s, winter115.143s and permission120.074s. The last includes
74ms of final overhead within the existing120s+0.5s acceptance bound; it produces a
demonstrated pending EV peak request. All retain168h and≤300s intervals. These are
synthetic offline runtimes, not installation timing or delivery guarantees.

## 4.3.12 — EV continuity and planning attention

260 Python tests pass59.78s;51 frontend tests, Ruff/mypy35 and modified JS parsing
pass. Synthetic regressions cover continuous overnight charging inside an economic
stage, source-certificate transition preservation, necessary three-phase fallback,
measured ESS loss causing a new peak during publication, labelled failed-reconciliation
exports, persisted attention, one automatic retry, recovery without a phone alert,
revision-independent deduplication, input/worker retry failures, failed HA delivery,
local-only delivery, pending-proposal notices and history publication reasons.
The planning-loop regression exercises rejection followed by accepted recovery.

The supplied decision is rejected, not evidence of the displayed accepted plan. Its
checksum passes. It contains eight EV starts before the morning deadline and an11.04kW
maximum. Replaying publication reproduces a5.49→5.531619kW quarter after restricted
ESS inventory falls during the calculation. A rejected peak check alone does not
establish a physically necessary higher allowance. Private frozen files stay ignored.
An initial blended-objective experiment worsened economics and was discarded.

The final focused-refinement replay validates in118.284s under the120s policy. It
produces one constant3.45kW one-phase session for the morning goal, without pauses or
phase changes in that window. Its comparison is−2.873403EUR versus−2.842014EUR in the
supplied candidate. The independent validator returns no errors. Reconciliation with
the supplied later measured state also returns no errors and retains the5.49kW monthly
peak. These are offline frozen-data results, not installation behavior guarantees.

Serial120s synthetic benchmarks all validate and certify minimum necessary grid:
mixed115.952s, winter115.295s, permission115.433s. All retain168h and≤300s intervals;
permission produces a demonstrated pending EV ceiling request. The final certificate
cash/economic bounds were added after mixed; winter, permission, the final private
replay and source-certificate regressions include them.

Fake configured E2E passes35.295s/2,017intervals/max tick4.602ms/four fake-only service
calls, including HA phone handoff to the local fake endpoint. The display-only failure
fixture then seeds an unresolved rejection and freezes background planning. Native and
standalone browser views show the timestamped attention item and handoff status, with
no approval buttons for the rejection. Native Decision evidence opens the rejection,
publication errors, stages and authenticated export link; browser error/warning logs
are empty during that check. No browser download was attempted. Proof:
artifacts/release-4.3.12-attention.png. Temporary tabs/previews closed afterward.

Wheel/sdist build;55 application code/assets match source in both archives and isolated
extracted-wheel import reports4.3.12. Final release documents are packaged after these
checks. Unrelated backlog additions and the paused Maps archive remain untouched.
No live HA/database, hardware, real phone notice or installation deployment was used.

## 4.3.11 — Month-aware seeds, timeout recovery and failed-decision export

251 Python tests pass43.26s; final eight recovery/failure/export tests pass5.60s after
the recovery allocation was finalized.50 frontend tests, Ruff/mypy35 and JS parse pass.
New synthetic regressions cover a month-reset seed with required charging, one initial
timeout followed by a validated plan, no retry after deadline exhaustion, rejected-list
metadata, complete no-store attachment JSON with preserved float/checksum, missing ID
and CLI rejection of a corrupt top-level exported digest.

The user-supplied frozen failed decision passes its checksum. Baseline4.3.10 reproduces
required_reference timeout/no candidate at12.733s despite120s total budget. Its seed
uses the current month's incurred allowance in a later month and fails the model's
correct future-month quarter limit. Corrected replay validates at117.234s; a second
replay validates at117.242s with an empty independent validation-error list. Raw private
inputs and outputs remain ignored local evidence, not tracked fixtures or installation
configuration. These are frozen offline results, not live installation timing claims.

Sequential synthetic120s benchmarks preserve168h and≤300s intervals: mixed115.867s,
winter115.260s, permission115.366s; all valid, no validation errors and minimum necessary
grid certified. All three had a feasible initial reference and did not use recovery;
the recovery branch is covered by the final focused real-solver regression. Updated
benchmark-{mixed,winter,permission}.json reports retain full stage/gap evidence.

Fake E2E passes31.922s/2,018intervals/max control tick2.303ms/four fake-only service calls.
The explicitly labelled planner-failure fixture records display evidence after normal
acceptance checks. Native browser history lists rejected/status/reason/time; the modal
shows false validity, reason, timing/stages and the authenticated ingress export link.
Standalone renders the same details with its local export link. A339px dialog fits
without horizontal overflow; warning/error logs are empty. Synthetic proof is ignored
artifacts/release-4.3.11-diagnostics.jpg. Browser file-download permission was declined,
so actual browser download completion was not verified or retried through another route.
Earlier server-side export/checksum tests passed. No live HA/database/hardware/real
notifications or installation deployment was accessed.

Wheel/sdist build passes; all55 code/assets match source in both archives and isolated
extracted-wheel import reports4.3.11. Private replay inputs/artifacts and the paused
Maps archive are excluded from the package and commit.

## 4.3.10 — Wheel zoom, Grid peak history and EV controls

246 Python tests pass42.93s;50 frontend tests pass. Wheel cases verify pointer-anchored
zoom, both directions/units, coalescing,15min/7day bounds and cancellation. HA action
tests verify actual actuator mapping, exact one-time option dispatch, no fabricated
readback, rejection of demo/missing/unavailable/non-select/unsupported sources and
propagated action failure. Sidebar tests retain raw stale values and remove the old
details/note. Four native/versioned-asset tests pass0.31s; Ruff/mypy35/all JS parse pass.
Final synthetic E2E32.451s/2,018intervals/max control tick4.071ms/four fake-only calls.

Real browser wheel zoom narrows6h→290min; dragging then pans at290min. Power/SoC/session
labels stay aligned. Peak stroke is rgb(220,38,38), dash pattern8/5. Grid peak click and
Enter dispatch actual mapped sensor.monthly_peak_kw more-info; Grid power still opens
its import/export chooser. Missing peak has no line, but mapped history stays clickable.
Existing mobile gestures pass labelled synthetic replay and were reported working on
the installation by the user; no new physical phone test was performed here.

Native EV synthetic HA service actions record select.phase→2 and keyboardAuto→0;
pressed state follows HA readback and focus survives polls. No action is forwarded to
the application/controller or real HA. Consolidated sidebar retains neutral stop,
green OK, raw stale codes and timestamps with unverified labels. Narrow EV card353px
fits without horizontal overflow. Browser warning/error logs are empty. These checks
use local fake endpoints, not installation database/hardware/real notifications.

Manual phase actions use the documented [HA frontend callService API](https://contributors.home-assistant.io/frontend/reference/hass-object/).
The current controller continues to require fixed-phase readback; selecting charger
Auto does not change that existing safeguard or add a planner preference.

Wheel/sdist build passes; all55 code/assets match source in both archives and an
isolated import reports4.3.10. Synthetic screenshots are under ignored artifacts/
release-4.3.10-ev.jpg and release-4.3.10-overview.jpg. No installation deployment.

## 4.3.9 — Wheel/mobile time navigation and monthly peak

245 Python tests pass42.95s;47 frontend tests pass, including wheel delta modes,
coalescing/settling, cancellation, two-finger pan direction, pinch anchor and15min/7day
bounds, third-pointer suppression, capture disposal and valid/zero/missing/stale peak
handling. Ruff/mypy35/all asset JavaScript parse pass. Synthetic full-horizon E2E
32.623s/2,018intervals/max control tick3.751ms/four fake-only calls passes.

Real browser wheel input pans time without moving the page over a plot. Both graph
ranges and session labels match. Native source updates2500→7500→unavailable→0 refresh
the line/scale correctly; unavailable has no line, zero remains zero. Keyboard values,
Now, zoom-aware arrow labels and Planning without a peak/panning remain functional.
Labelled fixture buttons replay touch PointerEvents against real view handlers, with
capture mocked: pinch6h→4h→8h and two-finger pan of both power/SoC synchronize all
ranges. These are synthetic integration checks, not a physical touch/browser gesture
negotiation test. Physical phone behavior remains unverified. A narrow-layout327px
graph fits; computed touch-action remains pan-y for one-finger vertical page scroll.
Browser warning/error logs are empty. Synthetic proof: artifacts/release-4.3.9-overview.jpg.

Pointer handling follows [Pointer Events pinch guidance](https://developer.mozilla.org/en-US/docs/Web/API/Pointer_events/Pinch_zoom_gestures)
and the browser's [touch-action contract](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/touch-action).
Wheel/sdist build passes;55 packaged code/assets match source in both archives and
isolated extracted-wheel import reports4.3.9. All endpoints/history are labelled
local fakes; no installation HA/database/hardware/notifications/deployment was accessed.

## 4.3.8 — Horizontal mouse panning

40 frontend tests pass, including drag geometry/duration/direction, frame coalescing,
click jitter, vertical intent, final release position, capture cancellation, disposal,
secondary buttons, touch and disabled views. Three native/versioned-asset tests pass
0.27s; Ruff and both changed JavaScript files parse. Full-horizon synthetic E2E passes
32.030s/2,018intervals/max control tick4.548ms/four fake-only calls. No backend changes.

Real browser mouse drags on native power and SoC move both charts and session labels
together. Drag right reveals older data, left reveals later data; duration stays six
hours. Release outside the plot ends capture without opening an unrelated goal/dialog.
Vertical drag leaves the range unchanged. Click pins numeric values, Escape clears;
actual tooltip-text selection stays blue and does not pan. Now restores the rolling
window. Planning has no panning class and retains its seven-day range. Standalone
drag also synchronizes all ranges. Native/standalone warning/error logs are empty.
Synthetic proof: ignored artifacts/release-4.3.8-drag.jpg. All endpoints/history are
local fakes; no actual HA, installation database, hardware or notification operation.

## 4.3.7 — Six-hour Overview window

36 frontend tests, three native/versioned-asset tests(0.27s), Ruff and changed JavaScript
syntax pass. Full-horizon synthetic E2E32.319s/2,018intervals/max control tick3.134ms/
four fake-only calls passes. No backend/controller changes. Browser verifies the live
two-hour-past/four-hour-future range, previous/next six hours, local history date,
historical navigation, numeric cursor and Now. On the25October DST day, local00:00→05:00
correctly spans six elapsed hours; next is05:00→11:00. Planning still spans seven days.
Power/SoC plot edges98→687px align with session98→687.44px (rounding under0.5px).
Browser warning/error logs are empty. Proof is ignored artifacts/release-4.3.7-overview.jpg.
Verification uses isolated synthetic history/local endpoints only; no installation access.

## 4.3.6 — Annotated EV drawing and independent status colors

Synthetic/local only.245 Python tests pass50.74s;36 frontend tests, Ruff/mypy35,
all JavaScript asset syntax and CLI4.3.6 pass. New cases distinguish a latched incident
from current None(0), reported error/car/overheat states, ordinary forced stop/waits,
permission versus actual delivery, unknown codes, stale readbacks and demo isolation.
No controller, recovery, API or entity-mapping contracts changed.

Full-horizon fake E2E passes35.446s/2,018intervals/max tick2.850ms/four fake-only calls.
Native browser checks the combined drawing/sidebar in light/dark themes: independently
green OK, red reported errors and neutral rgb(238,238,238) in dark mode. Historical
incident remains red with current charger None(0) green. Normal forced stop stays
neutral; stale fields are Unverified. Phase transition retains awaiting-readback text.
Expanded raw details and summary keyboard focus survive polling. At390px the native
card is355px/scroll353px; at320px the standalone card is281px/scroll279px. Browser
warning/error logs are empty. Screenshot: ignored artifacts/release-4.3.6-ev-desktop.jpg.
The fixture's theme/scenario controls change display data only. No live installation,
hardware, database, real notifications or deployment was accessed.

Wheel/sdist build passes. All55 packaged code/assets match source bytes in both
archives; an isolated extracted-wheel import reports4.3.6. Paused Maps code stays
outside the active package. Remote CI/image results are recorded after the release
commit only in the ignored local checkpoint and final response.

## 4.3.5 — EV charger visualization

Synthetic/local only.245 Python tests pass42.97s; final three versioned-bundle tests
pass0.29s.33 frontend tests, Ruff/mypy35, all asset JavaScript syntax and CLI4.3.5
pass. New frontend checks cover measured/requested power separation, go-e selector
code1/2 mapping, automatic/unverified mode, stale/missing inputs without fabricated
zero, command generation/age, charging/waiting/stopped/complete/disconnected states,
fault/recovery priority, escaped diagnostic content and demo/installation separation.
Native HA readings can update display while backend authority checks remain unchanged.

Full-horizon fake E2E passes32.818s/2,018intervals/max control tick4.138ms/four fake-only
service calls. Native browser verifies charging, phase transition with awaiting readback,
timestamped fault, stale values, expandable details, incoming sensor update and focus
preservation through repeated polls. Standalone EV tab also shows fresh charger settings.
The390px phone card is355px wide with353px scroll width and no card overflow; expanded
details also fit. Battery percentage is accessible text; motion respects reduced-motion
CSS. Final native and standalone warning/error logs are empty. Preview scenarios project
display data only and do not operate the backend controller. Screenshots remain in
ignored artifacts/release-4.3.5-ev-*.jpg; local preview tabs/servers are closed.

Wheel/sdist build and isolated4.3.5 import pass; all55 code/assets match source bytes
in both archives. Unrelated backlog edits and paused Maps code are excluded. No actual
HA/database/hardware, real notifications or installation deployment was used.

## 4.3.4 — Compact polling, request recovery and selectable text

Synthetic/local verification only. Full245 Python tests passed43.13s; final four
native-bundle/API checks after adding both imported modules to the asset allowlist
passed0.33s.28 frontend tests, Ruff/mypy35, all packaged JavaScript syntax and CLI4.3.4
pass. API checks preserve the full legacy endpoint, restrict compact data to display
fields/recent120 samples, handle unchanged/new/removed plans, avoid mutating stored
evidence and retain no-store headers. Frontend checks cover cache identity, bounded
retry/backoff recovery, contextual timeout/network errors, uncertain mutation outcomes,
validation field errors and text-selection detection across shadow-root boundaries.

Configured fake E2E passes32.403s/2,018intervals/max tick2.466ms/four fake-only calls,
with42,535labelled archived records. A synthetic full seven-day response measured
2,523,327bytes; compact initial784,842bytes and unchanged-plan poll50,534bytes:98.0%
less repeated transfer in that fixture, not an installation/network benchmark.

Native preview deliberately supplies an HA-like user-select:none parent. Actual text
and power-value selections remain highlighted through multiple refreshes; a drag does
not open source-history choices. Ordinary controls clear selection and resume rendering.
The installed loader's real15s AbortSignal deadline was triggered with a local delayed
state response: a timestamped GET state warning appeared, Copy error exactly matched
the clipboard, and recovery hid the warning without reload. A Permissions-Policy denial
exercised the selected read-only manual-copy field. Standalone selection, compact-data
Overview/Planning/EV navigation and native57% live update also pass. Initial browser
import failure exposed the missing asset allowlist entries, repaired before final checks;
expected clipboard-policy errors are distinct from final clean startup checks.
Native390px denied-clipboard warning fits355px with no horizontal overflow. Final
fresh native/standalone startup logs are clean. Verification fixtures are stopped.
Screenshots and payload report remain in ignored artifacts/release-4.3.4-*.
Wheel/sdist built; all54 code/assets match source and isolated4.3.4 import passes.
Paused Maps and unrelated backlog edits excluded. No live HA/database/hardware,
installation notifications or deployment was used.

## 4.3.3 — Stable graphs, frozen daily estimates and settling balances

Synthetic/local checks only. Final full suite244 passed44.33s; focused26 energy/input
checks passed0.61s after the archive-coalescing regression and clock guard.
24 frontend tests, Ruff/mypy35, all packaged JavaScript syntax and CLI4.3.3 pass.
Regression coverage includes overlap retained during pending/failed range replacement,
nonoverlap/mode/timezone isolation, obsolete responses, saved midnight baselines across
23/25-hour days, restart/replan immutability, honest late-start fallback, and coalesced
slow archive reads while the live state endpoint remains responsive. Real loopback HA
input-loop tests verify command pause/no revision change during a brief residual and
normal visible invalidation after30s of persistent mismatch. Invalid residuals do not
become measured household history or forecast-learning samples.

Configured fake E2E with42,480synthetic archived measurements passes32.344s across
2,018intervals, max control tick4.319ms, four fake-only service/notification calls.
Native and standalone browser previews verify capture/as-of tooltips and independently
loaded recorded totals. Native live EV update45→57% still works while estimates remain
fixed through the subsequent replan. Fifty sampled graph renders before/after a minute
rollover retained full archived paths (minimum6,840characters); no missing archive redraw
was observed. Native390px energy rows fit147px with no horizontal overflow. Screenshots
remain under ignored artifacts/release-4.3.3-*.jpg. No live HA/database/hardware use.

Wheel/sdist built; all52 code/assets match source and isolated4.3.3 import passes.
Paused Maps code and unrelated backlog edits are excluded from both distributions.
Remote results belong only in the ignored checkpoint/final reply after the release commit.

## 4.3.2 — Status-aware go-e charging supervision

Full suite236 passed42.91s; after the final evidence-storage stop safeguard,56 targeted
go-e/incident tests passed0.57s.22 frontend tests, Ruff/mypy34, all JS syntax and CLI4.3.2
pass. New deterministic fake cases cover normal120second pauses, waiting/car-complete/
OCPP states, unknown/nonnumeric inputs, all tested nonzero errors, no-reboot escalation,
one healthy confirmed non-delivery recovery, fresh post-reboot frames, current-before-
start, silent write failures, superseded start/stop races, cancelled current/phase
requests, phase dwell/readback/transition deadlines, stale heartbeat despite new HA
reads, malformed metadata, current-limit intersection/replan and ESS independence.
Fault stop is attempted even if incident persistence raises. Hardware-off verification
can notify but cannot re-enable or reboot. No installation entity ID is hardcoded.

Configured fake E2E accepted2,018 intervals in35.467s, max control tick4.937ms, four
fake-only service calls. It verifies advancing seconds heartbeat, numeric states,
readbacks and a confirmed zero-power hardware-off stop before preview fault injection.
Unchanged HA report timestamps are three hours old by design; they are not substituted
for the advancing device signal. The final phase and persistence paths were separately
verified by the targeted tests above. Report: offline-e2e.json.

Synthetic native and standalone browser checks passed: required-for-EV CODE/seconds
labels, clear/save/restore with backup/restart notice, unavailable-charger warning and
clean final warning/error logs. At390px requested viewport the heartbeat field is327px
wide at24px left, without overflow. Screenshots goe-v432-desktop/mobile/paused.png;
see goe-browser-verification.json. Fixtures/tabs closed and viewport restored.

Wheel/sdist built;51 code/assets match source and isolated4.3.2 import passes.
Both packages exclude parked Maps code/archive; the source distribution excludes the
separate uncommitted backlog edits. See goe-package-verification.json.

HA built-ins/Supervisor were simulated. No live HA/database/hardware, real reset,
phone notification or deployment. Maps remains parked and excluded. The pre-existing
uncommitted ARCH-011/012 backlog edits are preserved outside this release.

## 4.3.1 — EV fault evidence and bounded recovery

198 Python tests passed in51.29s, including16 new incident/recovery cases.22 frontend
tests, Ruff/mypy33, JavaScript syntax and CLI4.3.1 pass. Checks cover the90second
timestamp, one persisted reboot, stop/disable/generation guards, reboot failure and
unknown outcome, restart without replay, fresh-input grace period, ten seconds of
new measured charging evidence, cached-sample rejection, unresolved latching,
acknowledgement/new plan,30minute cooldown, notification retries/deduplication,
optional button unknown/unavailable states, raw diagnostics and archive/API boundaries.
A held report worker leaves /api/state responsive; report includes T−5minutes beyond
the recent100-event display limit. Persistence failure prevents button activation.

Configured fake E2E accepted2,018 intervals in30.300s, maximum control tick2.656ms,
five fake-only service calls. Native and standalone synthetic browser checks covered
timestamp/offset, report/download/history, acknowledgement, optional reset/phone mapping
save/backup/restart notice and clean final browser logs. At390px requested viewport,
dialog client/scroll widths both324px (341px outer). Screenshot raster dimensions
1265×889desktop and375×812phone; HA built-in cards/Supervisor are simulated.
See ev-fault-browser-verification.json and screenshots/ev-fault-v431-*.png.

Wheel/sdist built;50 packaged code/assets match and isolated4.3.1 import passes.
Both distributions exclude Maps code and its local archive; see
ev-fault-package-verification.json.

No actual HA/database/hardware, charger reboot, real phone notification or deployment
was used. The reported installation fault has not been diagnosed retrospectively.
Maps preparation is preserved in the ignored local archive and excluded from this
release; its earlier16 offline routing checks are not fault-release validation.

## 4.3.0 — Subscribed EV calendars

181 Python tests passed42.04s, followed by40 configuration/calendar checks (including
12 calendar cases) after the final invalid-config guard.21 frontend tests, Ruff/mypy32
and all JS syntax pass. Calendar checks cover multiple sources, save/backup/legacy settings,
recurrence/exceptions/cancellation, DST/TZID, folding/escaping, unsupported/invalid
feeds, source ownership, unchanged identity/no replan, reschedule/approval reset,
failure retention, restart and changed-URL removal, duplicate subscriptions, private
address rejection and a held sync request while /api/state remains responsive.
The supplied referee feed was read-only checked:five upcoming timed events with
locations. Its URL/content are not committed or used as synthetic fixtures.

Configured fake E2E with two synthetic subscriptions, a repeated occurrence and90%
initial EV SoC accepted2,022 intervals in65.617s. Two distinct50km/four-hour trips,
five fake-only service calls, max observed control tick2.761ms. Report offline-e2e.json.
The normal no-calendar CI fixture remains separate. Earlier two-trip45%SoC fixtures
hit the reference-solve time limit at15/60s; no incumbent was adopted and control
remained responsive. This is a known planner limitation, recorded under ARCH-003;
calendar import does not change solver policy or promise a plan for every scenario.

Native HA-contract and standalone browser checks passed: imported agenda/away/return,
provisional50km/four-hour labels, source/location, manual Sync and clean logs. Settings
add/label/remove/save with backup/restart message passed on local fixtures. At390px,
calendar fields fit327px rows without overflow. Screenshots calendar-v430-desktop/mobile.
Native HA built-ins/Supervisor were simulated; no actual HA/Companion installation,
database, hardware, real notification or deployment. Temporary tabs/servers closed.
Wheel/sdist built,49 source/assets match, isolated4.3.0 import passes; see
calendar-package-verification.json. Google Maps preparation follows after publication.

## 4.2.3 — Compact dashboard and numeric cursors

170 Python tests passed43.45s;20 frontend tests, Ruff/mypy31, all JavaScript syntax
and CLI4.2.3 passed. New checks cover recorded subtotal plus only remaining-day flows,
directional AC accounting, stale/unknown/unreconciled plans, insufficient coverage and
23/25-hour local days. Frontend checks cover symbols, partial/stale totals, prediction
identity, cursor interpolation, missing spans, exact step boundaries and window clipping.

Configured fake E2E seeded32,522 synthetic archive records and accepted2,018 intervals
in26.912s, max observed control tick2.866ms, five fake-only service calls. Wheel/sdist
built; all48 packaged source/assets match and isolated4.2.3 wheel import passed.
See compact-dashboard-package-verification.json and offline-e2e.json.

Labelled native HA-contract and standalone browser checks passed for compact energy
rows, day-end predictions across local midnight, connection symbols, source chooser/
more-info, pointer/keyboard W/% cursors, gaps and planned window edges. Both graph and
session-track endpoints align within0.02px on desktop and exactly at390px width;
power height360px, SoC255px. Unapplied program choice survives page reload without sending a command. No browser warnings/errors. Screenshots and geometry are
in screenshots/compact-v423-desktop.png, compact-v423-mobile.png and
compact-dashboard-browser-verification.json. Temporary servers/tabs closed.

HA built-ins/Supervisor were simulated; actual HA/Companion installation remains
unverified. No live HA/database/hardware access, real notifications or deployment.

## 4.2.2 — Archived graph history

Final 4.2.2 release checks: 165 Python tests passed in 42.64s; 18 frontend tests,
Ruff/mypy31, all JavaScript syntax and CLI version passed. Configured fake E2E with
47,942 seeded synthetic archive records accepted 2,018 intervals in 27.108s, max
observed control tick 3.180ms, five fake-only service calls. No live installation access.
Final wheel/sdist built: all47 code/assets match source and isolated4.2.2 wheel import
passed (graph-history-package-verification.json).

Initial implementation/browser/load evidence (unchanged graph code):

165 Python tests passed43.50s; targeted12 tests passed again after adding503 coverage.
18 Node tests, Ruff/mypy31 and all JS syntax passed. Tests cover legacy events outside
the ring, index use, bounded responses, retained peaks, gaps/invalid/demo separation,
unknown EV SoC, recorded/legacy capacity handling, range/point/timezone validation,
read timeout, HTTP boundary and a held worker query while /api/state still responds.
Frontend checks cover23/25-hour dates, obsolete-response suppression, cache/error
backoff, merging recent samples and preserving valid archived readings after cached
watchdog failures. The user subsequently authorized the 4.2.2 release; final release
checks are recorded below before the single implementation commit.

The load check used245,924 explicitly synthetic archive records with two concurrent
24-hour queries. Each returned16,561 distinct samples as at most683 points per series
and125,847 response bytes, in1.294/1.282s.87 fake database writes continued; maximum
observed5ms heartbeat delay10.760ms. These are local read/write/event-loop measurements,
not installation control or hardware latency. See graph-history-load-verification.json.

Configured fake E2E with44,924 seeded old graph records:2,018 intervals accepted27.381s,
max initial control tick2.650ms, five local fake-only calls. After browser history reads,
max observed controller tick7.002ms and hardware control off. Browser native/standalone
checks show the previous day's full power and SoC history, deliberate noon outage,
EV-only unknown interval, correct date/12h/Now navigation and an absent day with zero
actual paths.390px controls fit; screenshots graph-history-v422-desktop/mobile.png.
The local ingress fixture now preserves query parameters. HA built-ins/Supervisor are
simulated; actual HA installation and existing installation archive remain unverified.
No browser warnings/errors after fixing the local proxy. Temporary8102/8103 servers
stopped, normal browser viewport restored.47 packaged code/assets match source and
isolated extracted-wheel import passed for the initial local implementation. The final
4.2.2 wheel/sdist is built separately under dist/ before publication. No live database/hardware/deployment.

## 4.2.1 — Daily energy in live boxes

161 Python tests passed40.58s,14 Node tests, Ruff/mypy30 and all packaged JS syntax.
Daily-energy fixtures cover old event backfill, repeated timestamps, watchdog failures,
gaps/unknown/demo separation, opposing flows, restart, local midnight and both DST
changes. API/ingress boundary and stale-day labels checked. Configured fake E2E accepted
2,018 intervals27.722s; max observed control tick3.285ms, five fake-only calls.
Wheel/sdist built;45 packaged source/assets match; isolated wheel import passed.
Labelled HA-contract browser preview confirms no sensor strip, today's energy in all
five boxes, grid source chooser and correct native more-info event. No warnings/errors.
Screenshot: screenshots/native-v421-desktop.png. Actual HA installation remains unverified;
no live database/hardware/deployment. Custom graph archive loading follows separately.

## 4.2.0 — Native managed HA dashboard

Native strategy, tiles/history actions and custom planning/EV/settings cards replace
the iframe wrapper. One-time loader/YAML setup; subsequent UI releases load versioned
assets from the installed add-on on HA page reload. No scheduler/controller policy or
backend five-second measurement cadence changed. No live HA deployment performed.

- 156 Python tests passed39.60s. Ruff/mypy29 and packaged JS syntax passed.13 Node tests
 cover managed layout/version updates without YAML changes, HA-native history bindings,
 direct current-state normalization/AC balance/partial unavailability, unchanged backend
 authority, discovery/session renewal/path validation/admin boundary, no POST replay and
 view-reuse cleanup. Versioned HTTP assets reject stale releases and disallowed paths;
 the manifest exposes active entities without credentials and excludes HA data in demo.
- Configured fake-HA/weather E2E:2,018 intervals accepted27.041s, max observed control
 tick2.616ms, five fake-only service calls. All measurements/weather explicitly synthetic.
- Browser harness: native views mount without iframe; an incoming45→57% HA state changes
 native live displays while backend remains45%. EV sensor click emits `hass-more-info`
 with the correct entity. Journey calendar/date picker/create/remove, Settings discovery/
 save/backup/restart message and native view navigation passed.390px layout and the
 standalone fallback/setup download were inspected. Unapplied program choice survives page reload without sending a command. No browser warnings/errors.
- This is a labelled HA-contract harness with simulated HA built-in cards, more-info
 dialog and Supervisor WS responses. Versioned custom components, authenticated-style
 session transport, backend/settings API and configured real-solver fixture run locally.
 It is not evidence of installation on actual HA Core, Supervisor or Companion clients.

Screenshots: screenshots/native-v420-desktop.png and native-v420-mobile.png. Wheel/sdist
built; all44 code/assets match source; isolated extracted-wheel manifest/import passed
with control disabled (native-dashboard-package-verification.json). Temporary8102/8103
fixtures and browser tabs closed, viewport reset; existing8100 preserved. No actual HA/database, hardware
or real notifications used. ARCH-010 remains deferred for the custom graphs' SQLite
archive; native Recorder history is a separate source under HA's retention configuration.

## 4.1.0 — ARCH-009 visual EV schedule

Local verification before the authorized release commit/push. Dedicated EV calendar and
daily agenda use existing goals, daily-readiness rules and accepted EV sessions. No
scheduling formulas, physical limits, source/peak permissions or hardware policy changed.

- 153 Python tests passed in39.36s. Ruff and mypy28 passed. Nine Node frontend tests
  and syntax checks for every packaged JS asset passed. New checks cover requirements
  without a plan, morning suppression while away, saved morning approvals, 23/25-hour
  days, a midnight clock change, overnight clipping, simultaneous targets, unknown
  returns, half-open day boundaries and withholding obsolete/unvalidated plan data.
- Configured full-horizon fake-HA/weather E2E: 2,018 intervals accepted in27.672s,
  max observed control tick2.791ms, five fake-only calls. These are synthetic local
  results, not installation or hardware latency measurements. See offline-e2e.json.
- Browser: direct EV navigation/reload, day selection, accepted charging details,
  journey creation/edit/overnight return, unknown return span, morning suppression,
  manual goal creation/removal and daily Settings navigation passed. Current requirements
  remained visible during recalculation. At390x844, the calendar scrolls within its card
  and selecting a day brings its single-column agenda into view. No console warnings/errors.
- Release metadata prepared as4.1.0; wheel/source builds succeeded. All38 packaged files
  match source. Isolated extracted-wheel import and synthetic state projection passed,
  with control disabled (ev-schedule-package-verification.json). Package assets include
  the EV module and retain same-origin/ingress boundaries. Temporary8102 preview/tab
  stopped and viewport reset; existing8100 preview preserved.

Screenshots: screenshots/ev-v410-desktop.png and screenshots/ev-v410-mobile.png.
All preview data and goal edits were explicitly SYNTHETIC and loopback-only. No live
HA/database, physical device, real notification, deployment or remote publication used.

## 4.0.10 — Journey date/time controls and watt display

Scope: Android-inspired date/time fields, W power presentation, and durable requirements/
decision/backlog handoff. The EV schedule/calendar page is deferred as ARCH-009. No
scheduler policy, physical limits, forecast source, device control or stored units changed.

- 151 Python tests passed in40.46s; final19 affected settings/asset tests passed in0.36s.
  Ruff, mypy28 and JavaScript syntax checks passed. Five Node frontend tests cover signed/
  missing W values, energy-unit preservation, reversible limits/rates, leap dates,
  installation timezone, skipped/repeated DST times and 24-hour clock selection.
- Real configured seven-day E2E: 2,018 intervals in26.594s, max control tick2.823ms,
  switch tick1.008ms (one sample), five fake-only service calls. All entity report
  metadata was three hours old; HA availability/read-watchdog behavior is unchanged.
- Browser: journey create/edit persistence, calendar/clock and exact-minute typing,
  Cancel, optional-return Clear, second DST occurrence retained on edit and missing
  spring hour rejected. Calendar arrow keys/focus and390x844 picker layout verified.
  Overview/Planning power, card components, peaks, entity previews and settings show W;
  energy remains kWh. No browser console warnings/errors.
- Wheel/sdist built; isolated installed wheel imports4.0.10 and all37 source/asset
  files match the final source byte-for-byte, including all three new JS modules.
- Saved2750W was independently read from JSON as2.75kW; a second save restored2.5kW.
  All unedited physical/policy numbers were exactly preserved. Capacity tariff save/
  reload used EUR/W/month display with existing EUR/kW/month storage. A binary floating
  display artifact found during verification was fixed before packaging.

Evidence: frontend-verification.json, offline-e2e.json and screenshots/journey-v4010-*.png,
screenshots/power-v4010-watts.png. These show **synthetic local fixtures**, not actual
installation readings. Physical devices, HA installation and phone delivery remain
live-unverified. Current architecture and specification: ARCHITECTURE.md;
historical design records retain explicit supersession notes.

## Version 4.0.9 — HA availability and successful-read watchdog

User-approved scope: use current available HA states, remove per-entity age gates and
retain a watchdog on validated input reads. Report timestamps are diagnostic, including
old/missing/malformed metadata. Numbers, units, physical consistency and required
unknown/unavailable states still validate. Quarter conversion/reset accounting remains;
report timestamps are no longer compared with the current quarter. Existing JSON timeout
key is retained with the clarified HA input-read watchdog label. Forecast expiry is unchanged.

Local: **151 tests passed in 39.54 s**; Ruff, mypy (28 modules) and JavaScript checks passed.
Coverage includes unchanged zero/nonzero states across quarters, diagnostic timestamps,
current-quarter counter reset, unavailable/unknown/read failures, value/unit rejection,
read-watchdog expiry/recovery and independent control while the input loop is stalled.
The full seven-day fake-Supervisor/HA/weather application accepted 2,018 intervals in
27.045 s, maximum tick 1.864 ms and five fake service calls. Every entity carried a
three-hour-old report timestamp throughout the successful run.

Browser: clean live values and immediate fake ON/OFF with old metadata; injected HA HTTP
failure blocks enablement and identifies failed reads. No console warnings/errors.
Screenshots availability-v409-healthy.png and availability-v409-read-failure.png are
synthetic local verification only. Wheel/source archives built (transient Windows metadata
rename denial resolved by retry); all 34 isolated installed files match source. Installed
old-state acceptance and read-watchdog expiry passed. Temporary fixtures/tabs closed and
the existing 8100 preview preserved. No live HA/database/hardware/real notification access.
Actual device outage detection is delegated to HA integrations as agreed and remains a
commissioning check. Remote results go in the chat/ignored checkpoint, without a separate
verification-record commit.

## Version 4.0.8 — independent live values and input freshness

Scope: the reported all-or-nothing Overview behavior and timestamp/freshness failures.
Local verification: **148 tests passed in 39.30 s**, plus the final 27 affected-input/integration checks
in 2.73 s; Ruff, mypy (28 modules) and JavaScript checks passed. Regressions cover
slow battery/static states, unchanged values with fresh reports, fallback timestamp age,
true quarter resets and recovery, stale/future/missing timestamps, invalid units/values,
failed HTTP reads, visible unaffected cards and restricted control on invalid snapshots.

The real seven-day automatic-Supervisor/fake-HA E2E accepted 2,018 intervals in 27.573 s;
maximum control tick 2.178 ms, five fake service calls. Eight-minute battery states and
older unchanged-state timestamps exercise the original failure shape. Wheel/source
archives built; all 34 isolated installed package files match source, with live-input API
and disabled startup verified. The first local build hit a transient Windows metadata
rename denial; retry succeeded without changing packaging behavior.

Browser checks injected stale power, unavailable DC solar and an old quarter meter after
a successful real solve. Available values stayed visible, missing totals/components and
entity-specific warnings were clear, the hardware switch remained blocked, and console
warnings/errors were absent. Screenshots: live-v408-stale.png, live-v408-unavailable.png
and live-v408-quarter.png. All are synthetic local fixtures, not installation evidence.
Temporary fixtures/tabs were closed and the user's 8100 preview preserved. No live HA,
installation database, hardware or real notification access. Live installation reporting
rates and physical commissioning remain unverified. Release CI/publication results are
reported in the chat and ignored implementation checkpoint; no separate evidence commit.

## Version 4.0.7 — responsive disabled control during final stop

Includes the settings/control update below. A disabled actuator now returns before
acquiring the dispatch lock. The serial path retains its enabled/generation checks.
A regression holds the fake EV stop request open and verifies that a disabled control
tick completes independently. The regression failed before the fix.

Local verification: **136 tests passed in 39.25 s**; Ruff, mypy (27 modules) and
JavaScript checks passed. Wheel/source archives built; all 33 installed package files
match source. Isolated installed startup verified automatic Supervisor connection,
missing-field reporting, editor availability and hardware control off.

The synthetic configured seven-day E2E passed with 2,018 intervals in 27.346 s,
maximum control tick 2.811 ms and five fake service calls. The report now measures
all ticks and separates pre-switch and post-switch samples: baseline 2.811 ms,
post-switch 1.927 ms (one completed tick). No startup hardware writes occurred.
These are local observations, not a physical timing guarantee. The earlier 4.0.6
CI outlier was captured before switching and is retained without an inferred cause.

Final 4.0.7 browser checks verified immediate Overview ON/OFF, removed settings groups,
phone autocomplete and no console warnings/errors. Screenshots: settings-v407-*.png;
missing-field/save/reload checks from 4.0.6 remain applicable to unchanged GUI assets.
Temporary local fixtures/tabs were stopped; the user's existing 8100 preview was preserved.
No live HA, installation database, hardware or real notification was accessed.
Billing timestamp rejection remains guarded and needs actual telemetry diagnostics.

Remote code `bd0af8fb4e7ca1804ed076ae5f2cf30299253a8a` passed
[CI 40010642618](https://github.com/Nxt-1/EnergyManager/actions/runs/40010642618)
(136 tests in 41.50 s, type/JS/CLI checks, configured E2E, package and Linux container
builds) and [publication 40010642108](https://github.com/Nxt-1/EnergyManager/actions/runs/40010642108)
(136 tests in 35.73 s). Remote E2E: 31.029 s, maximum tick 5.749 ms, baseline
3.630 ms and post-switch 5.749 ms (one sample), five fake-only service calls.
Published image: `ghcr.io/nxt-1/energymanager:4.0.7`, digest
`sha256:b909ccdf13b8a9e8a6b5285a9d9374a9a29bf57b3d84c633f3fc08fd42bfccc9`.
No live deployment was performed.

## Version 4.0.6 — automatic HA connection and one hardware switch

Removed the connection and commissioning options and explanatory entity subtitles.
Runtime and discovery use the automatic Supervisor URL/token. The webhook is replaced
by one optional phone picker, supporting notify entities and legacy phone actions.
Missing/placeholder/unavailable fields are highlighted before Save. Incomplete physical
settings keep the editor available with no plan/authority; unverified live cards show
dashes. The existing billing-boundary timestamp guard remains unchanged.

One Overview switch applies immediately and persists in SQLite. It starts off on first
upgrade, independently of retired checkbox/JSON flags. A saved on request waits for
settings/entity/input checks on restart. Off revokes queued/in-flight ordinary writes,
stops EV and clears ESS independently; stop/persistence failures are reported. Unknown
EV SoC/phase can still pause EV independently while fresh shared inputs permit ESS work.
See SETTINGS.md for exact state, migration and rollback behavior.

Local: **135 tests39.32s**, final27 focused tests0.98s, Ruff/mypy27 modules/JS passed.
Coverage includes concurrent enable/off, mid-dispatch revocation, failed persistence,
independent stop attempts, restart/input gates, local-only API boundary, legacy backups,
notify entity/action delivery and deduplication, and incomplete-file editor availability.

Configured new-pipeline seven-day E2E:2,018 intervals accepted26.521s, maximum control
2.718ms, five fake service calls. It used the automatic Supervisor connection through
local fake DNS/auth, made zero startup hardware calls, exercised the live switch and
sent a notification only to fake HA. Browser installation fixtures verified initial
missing-field highlights, missing-number/entity edits, one immediate switch, phone
picker/save/reload/backup, removed fields/help, pending-value dashes and zero console
errors. Screenshots use settings-v406-*.png. Both temporary previews/tabs were stopped;
the existing8100 preview was preserved.

Wheel/sdist built; all33 installed package code/assets match source. Isolated installed
startup verified automatic Supervisor access, removed groups, missing-field reports
and disabled control. No live HA, installation DB, hardware, real notifications or
deployment was accessed. Actual billing timestamps and hardware/phone commissioning
remain unverified. Evidence: settings-control-verification.json and offline-e2e.json.
Remote4.0.6 code d58b97d4c9ec4c3ed44bb751227459d075f7b790 passed
[CI40008621110](https://github.com/Nxt-1/EnergyManager/actions/runs/40008621110)
(135 tests37.78s, configured E2E32.219s and package/container checks) and
[publication40008621112](https://github.com/Nxt-1/EnergyManager/actions/runs/40008621112)
(135 tests42.43s). Image digest:
`sha256:16fb0bc43e69e8a2989285a4316dd78bd51525ce8f4a5070fe21a38f4a1c0208`.
The CI timing report recorded a 4.276 s control tick before switching; its cause is
not established. Follow-up investigation separately found that disabled dispatch could
wait behind a slow final stop. A regression reproduced that lock wait; 4.0.7 fixes it.

## Version 4.0.5 — original installation forecasting restored

Configured runtime now fetches Open-Meteo KNMI seamless weather at HA zone.home,
builds the exact four-plane PV model and original front/rear corrections, and learns
household demand from persisted background measurements. No prepared forecast service
is required. Connection-address redesign remains deferred. See FORECASTING.md for exact
installation values, retained formulas, time handling and outage policy.

Local: **112 tests passed in38.59s**; Ruff, mypy25 modules and dashboard JS syntax
passed. After a final malformed-response guard, all15 focused forecast tests passed
in5.40s and the rebuilt installed wheel guard was verified. New runtime tests cover
missing/null/nonfinite/gapped weather, stale-cache
issuance, remote-access gate, restart persistence, both DST changes and current partial
quarters. An application-level blocked-weather test confirms new HA polls and at least
five independent control ticks continue, and no placeholder forecast reaches planning.

Direct comparison against preserved source matched2,520 correction factors,648 PV
points and676 household points exactly. A35-day/10,080-sample load model built in41.3ms;
full-horizon resampling took9.25ms. Four actual Open-Meteo requests through the new
client returned216 aligned hours each and passed169h coverage. Those requests used
**public Brussels city-centre coordinates**, not installation coordinates. This is a
provider-contract check, not live installation evidence.

The configured fake-HA/fake-weather application accepted2,018 intervals in29.408s,
max control tick4.617ms and26 guarded calls to loopback fakes. Persistence, current
measurements, four plane queries, learning status, API and decision validation passed.
Overview/Planning browser checks showed forecasts and source/learning labels, retained
charts/time navigation and no demonstration journey; console errors absent. Screenshots:
forecast-overview.png and forecast-planning.png under screenshots/. The constant test
weather is explicitly SYNTHETIC. The temporary8102 preview was stopped;8100 preserved.

Wheel/sdist built;31 installed code/assets exactly match source. Isolated installed
configured startup selects the restored forecast pipeline, has no demonstration goals
and keeps hardware control disabled. No live HA, installation databases, notifications,
hardware, deployment or commissioning. Detailed evidence: forecast-restoration-verification.json
and offline-e2e.json.

Remote code commit32855877ea4177351d4c49dfce256baec01dc2d4 passed
[CI39997508230](https://github.com/Nxt-1/EnergyManager/actions/runs/39997508230):
**113 tests40.92s**, lint/types/CLI/JS, restored-source configured seven-day E2E,
package and Linux container build. Remote E2E accepted2,018 intervals31.174s,
max tick8.674ms and25 fake-only service calls.
[Image39997508225](https://github.com/Nxt-1/EnergyManager/actions/runs/39997508225)
passed113 tests37.69s and published `ghcr.io/nxt-1/energymanager:4.0.5`, digest
`sha256:95ee21fc26a7bf5793e7fdad51b681b38a24ce9abb0d8c8540dfe16748aad5cd`.
No installation deployment or hardware operation was performed.

## Version 4.0.4 — simplified installation settings

Removed all source/type selectors and the nonexistent house/phase sensor inputs.
The confirmed P1/go-e setup is applied in both runtime and Settings, including legacy
files that still contain direct/energy/count choices. Known P1 IDs replace only missing
or generated placeholders; custom mappings remain. Reads/startup do not rewrite files.
Explicit save backs up the original bytes, persists defaults and removes retired choice
keys while preserving future fields, unrelated values and control flags. Daily readiness,
journey consumption and reserve controls are in EV and charger.

Local checks: **85 tests passed in30.22s**, Ruff/mypy21 modules/JS passed. Browser checks
used a legacy config and synthetic loopback HA: all unwanted fields absent before and
after reload, P1 mappings prefilled, single go-e selector, daily target saved/reloaded
inside EV group, backup verified, zero desktop console errors. Screenshots are
simple-settings-measurements.png and simple-settings-ev.png under screenshots/.

The4.0.4 wheel/sdist built. All27 code/assets match source and isolated installed files;
installed legacy read/startup/save/backup/reload passed. Seven-day E2E without any source
choices accepted2,018 intervals21.799s; max control4.812ms;20 local fake calls. Known
EV SoC and selector state, archive and API checks passed. Details are in
simple-settings-verification.json and offline-e2e.json.

Remote: commitb6297bc29e60337e78ea4bdf00bc68d5dfd8f094 passed
[CI39979435914](https://github.com/Nxt-1/EnergyManager/actions/runs/39979435914):85 tests
35.31s, lint/types/CLI/JS, configured full-horizon application, package and container.
Remote synthetic E2E:2,018 intervals accepted28.934s, max tick11.632ms,22 fake calls.
[Image39979436032](https://github.com/Nxt-1/EnergyManager/actions/runs/39979436032)
succeeded and published4.0.4. Temporary browser/service fixtures were stopped.
No live HA/controller operation; wiring, clocks, ingress and commissioning remain unverified.

## Version 4.0.3 — installation measurement compatibility

P1 quarter demand accepts W/kW with a fixed0.25h energy conversion, based on the
user-confirmed reset-and-build behavior. Source inspection confirms the P1 reader
passes OBIS1-0:1.4.0 unchanged. Separate P1 import/export reconstruct house load; other
supported sources are direct house, total consumption and signed grid power. go-e
APIv2 Connect2026.10.3 can reuse its raw phase selector1/2 without an extra sensor.
Unknown phase information pauses EV while ESS remains responsive. Phase switching
waits for fresh mode readback after stop/zero/dwell. Slightly later SoC reads remain
valid within5s of the oldest shared input; far-future readings stay unknown.

Local verification: **84 tests passed in28.57s**; Ruff, mypy21 modules and JavaScript
syntax passed. The eight new test cases cover conversion denominators, import/export,
ESS directions, unknown modes, quarter boundaries, configuration reload and delayed
mode acknowledgment. Existing tests continue to cover the original normalized inputs.
The4.0.3 wheel and source distribution built. All27 package files match source and
an isolated installed wheel; actual settings save/backup/reload passed.

Browser verification used loopback synthetic HA states: all three source choices,
conditional fields, friendly-name/keyboard P1 selections, kW demand acceptance,
selector reuse, save/backup/reload and zero desktop console errors. Evidence is in
measurement-source-verification.json and screenshots/measurement-source-choices.png.
No live HA settings or controllers were accessed.

A real spawned HiGHS solve using the new P1/go-e input choices accepted the complete
seven-day2,018-interval schedule in21.556s. The check requires known measured EV SoC;
maximum control tick5.495ms;20 calls went only to local fake services. API and archive
checks passed. Details: offline-e2e.json.

Remote verification: implementation commit7d64dd39d9cff2d1507a1ecb0db96c0ce362520b
passed [CI39971619636](https://github.com/Nxt-1/EnergyManager/actions/runs/39971619636):
84 tests30.51s, Ruff/mypy/CLI/JS, configured new-source application, package and Linux
container builds. Remote synthetic seven-day solve:2,018 intervals accepted23.380s,
max control12.712ms,19 local fake calls. [Image workflow39971619511](https://github.com/Nxt-1/EnergyManager/actions/runs/39971619511)
succeeded and published4.0.3. The temporary8102 browser fixture was stopped; existing
8100 preview preserved. Meter clock alignment, inverter AC topology/signs, ingress and
hardware timing remain live-unverified commissioning checks.

## Version 4.0.2 — visual configuration

The Settings page edits the persistent JSON using grouped form controls and searchable
entity pickers. The server reads HA states through the Supervisor proxy or a saved
standalone connection, returns friendly names/state/units without credentials, and
does not call actuator services during discovery. Validated saves preserve unknown
fields, retain original bytes in a backup and replace the file atomically. Stale edits
are rejected. File work runs outside the control event loop. Changes apply after a
restart into configured mode; saving leaves the active controller unchanged.

Local checks: **76 tests passed in28.69s**, including24 settings tests for real loopback
HTTP discovery, Supervisor proxy/token boundaries, form API, backup/reload, concurrent
and external edits, physical/field validation, atomic replacement failure and discovery
outage. Ruff, mypy20 modules and JavaScript syntax passed. The4.0.2 wheel/source package
built; isolated installed-package save/backup/reload and26-file comparison passed.
Final package details are in settings-package-verification.json.

Browser checks used explicitly synthetic, loopback-only fixtures. Friendly-name search,
keyboard selection, actuator domain/unit filtering, field validation, save/reload and
Overview/Planning navigation passed. A390px mobile layout was inspected. Desktop browser
console errors were absent. Screenshots: settings-entities.png, settings-saved.png and
settings-mobile.png under screenshots/. Structured checks are in settings-ui-verification.json.

The configured seven-day fake integration passed with2,018 intervals accepted19.933s,
maximum measured control tick5.04ms and20 fake-only service calls (offline-e2e.json).
Scheduler mathematics and control policy are unchanged. Existing full-horizon benchmark
evidence remains applicable; no new benchmark claim is made for the settings editor.
Live Supervisor/ingress and physical commissioning remain unverified. Reports below
retain previous-release evidence; offline-e2e.json now describes4.0.2.

Remote verification on commit `bdacbee29b730aed86d939159817331fe525c005`:
[CI](https://github.com/Nxt-1/EnergyManager/actions/runs/39962540057) passed all 76 tests
in 35.68 s, lint/types/CLI/JavaScript, the configured fake integration, Python package
builds and the Linux container build. That synthetic integration accepted 2,018 intervals
in 27.227 s, with a maximum measured control tick of 8.85 ms and 21 fake-only calls.
The [image workflow](https://github.com/Nxt-1/EnergyManager/actions/runs/39962539923)
also passed and published version 4.0.2. No live installation was accessed or deployed.

## Version 4.0.1 — automatic starter configuration

Missing configuration files are created from the installed package on add-on startup,
including demo mode, and standalone `--config`. Existing bytes are preserved, including
empty/invalid files and user edits. New files retain disabled control/remote access and
explicit synthetic labels. Creation failures are reported before service startup. The
Home Assistant app configuration mount is writable for this initialization.

Local verification on23 October2026: **52 tests passed in28.29s**, including nine new
filesystem/startup/error tests and real localhost API checks in demo/configured modes.
Ruff and mypy passed.4.0.1 wheel and source archive built with the bundled template.
An isolated installed wheel created a file using its packaged resource, preserved an
edited file, reported4.0.1 and matched all24 package source/asset files. The wheel hash
and results are in configuration-bootstrap-verification.json.

The full-horizon configured fake integration also passed:2,018 intervals accepted in
20.096s, maximum measured control tick5.27ms and20 fake-only calls. See offline-e2e.json.
No scheduler mathematics or control policy changed. Live Supervisor startup and physical
commissioning remain unverified. The reports below retain4.0.0 promotion/CI history;
package-verification.json and ci-verification.json describe that prior release, while
offline-e2e.json now records the new4.0.1 run.

Remote verification on commit `32ea875364836b1512efb23fadadf84383dc19ca`:
[CI](https://github.com/Nxt-1/EnergyManager/actions/runs/39938880228) passed52 tests
in34.71s, lint/types/CLI/JS, configured fake integration, package builds and the Linux
container build. That synthetic integration accepted2,018 intervals in26.999s with
maximum measured control tick14.24ms and21 fake-only calls.
The [image workflow](https://github.com/Nxt-1/EnergyManager/actions/runs/39938880153)
also passed and published4.0.1. No live installation or controller action was performed.

## Version 4.0.0 promotion history

The fresh implementation has been promoted into the main `energymanager/` application,
replacing V3 as explicitly requested on 23 October 2026. The Python distribution,
module, CLI, source version, Home Assistant release and GUI now identify version4.0.0.
The former `energymanager-next/` directory has been removed.

## Promotion and compatibility

- Main Python package and command: `energymanager`.
- Home Assistant identity retained: slug `energy_manager`, image
  `ghcr.io/nxt-1/energymanager`, ingress8099. Local development remains port8100.
- V3 source/tests/tools/dashboard entry point replaced. Root development commands and
  CI/publish checks now target the V4 package and its tests/tools/assets.
- New V4 JSON configuration and `/data/energymanager-v4.sqlite3` are explicit. V3
  options, old controller permissions and installation databases are not automatically
  imported. Startup is manual/demo, and hardware control remains disabled by default.
- Existing changelog retained below the4.0.0 release notes. Historical V3 documents,
  the separate InfluxDB app and its publish workflow were verified unchanged.
- Original working files, prior implementation and staged patch were preserved locally
  under ignored `gpt/architecture/v4-promotion-2026-10-23/`. Local promotion verification preceded commit/publication; no live deployment was
  performed. The user subsequently authorized committing and pushing the V4 update.

RUNBOOK.md documents installation mapping, explicit commissioning and V3 rollback.
This is a major configuration update, not automatic conversion of V3 settings.

## Checks rerun after promotion

| Check | Result |
|---|---|
| Repository-root pytest | **43 passed in29.64s** |
| Ruff on app/src, app/tests, app/tools | Passed |
| Mypy on the renamed package | Passed,19 modules |
| JavaScript syntax, app/card/dashboard wrapper | Passed |
| Module/CLI release identity | `EnergyManager 4.0.0` |
| Configured localhost fake-HA end to end | Passed; accepted full-horizon plan in25.724s |
| Independent control during that solve | Max measured tick5.70ms;22 fake-only service requests |
| V4 wheel and source archive | Built |
| Isolated installed-wheel CLI, real HiGHS | Optimal, valid,0.00915s |
| Packaged source/assets vs current source | All23 files byte-identical |
| Browser main application | Overview/Planning,4.0.0 branding, charts and goal create/reload/remove passed; no console errors |

The configured E2E used actual loopback HTTP measurements/issued forecasts, a spawned
168-hour solver, current-state publication, independently guarded calls to a fake only,
API version4.0.0 and persisted checksum/results. The accepted remaining trajectory has
2,018 intervals, each no longer than300s. No installation input was substituted with a
fixture. All test/demo data are explicitly labelled synthetic. Full results are in
offline-e2e.json, package-verification.json and v4-promotion-browser.json.

The rebuilt wheel is `dist/energymanager-4.0.0-py3-none-any.whl`; its SHA256 is recorded
in package-verification.json. Installed verification used `python -I`, asserted the
import came from artifacts/v4-wheel-site, and executed the actual packaged optimizer.
Home Assistant release identity, package metadata and the removed candidate directory
were also checked. The optional dashboard wrapper matches the packaged card byte for byte.

## Preserved optimization and control evidence

Twelve core modules were compared to the pre-promotion candidate after namespace
normalization: domain, forecasts, optimization, incumbent, validation, planner,
reservations, publication, control, demo plant, worker and store. Their contents match;
promotion did not change scheduler mathematics or control behavior.

The original full-horizon benchmark reports are retained as evidence. They were not
rerun for the namespace/layout promotion; the full-horizon configured E2E was rerun.
All three original aligned168h cases used2,017 intervals and one120s cycle budget:

| Synthetic case | Cycle | Peak kW | EV/ESS sessions | Optional EV kWh | Main economic gap |
|---|---:|---:|---:|---:|---:|
| Mixed solar and journey |116.207s|2.50|14/18|17.976|0.424%|
| Winter and journey |115.212s|3.21|2/14|0|12.334%|
| Urgent one-hour56% goal |116.488s|4.00|2/1|0|75.315%|

All were independently valid feasible incumbents with time-limited economic stages,
not global-optimality claims. The urgent case had2.619525kWh permitted shortfall plus a
feasible goal-scoped10.601033kW permission diagnostic. Its economic gap remains large.
Minimum-grid certificates were Optimal only within the stated fixed-mode/non-grid/
quarter-envelope scope. Stage dimensions, bounds, times, costs and outcomes remain in
benchmark-*.json. SPECIFICATION.md defines the constraints and bounded comparisons.

Original pre-promotion verification, approval/revocation/history/session/mobile checks,
package identity/hashes, screenshots and work checkpoint are labelled under
history/standalone-candidate/. Statements there about a separate package or preserving
the old checkout describe that earlier stage. Current V4 screenshots are in screenshots/.
The inherited browser-service.json and publication-replay.json are earlier evidence;
the latter is a rejected diagnostic, never a passing acceptance result.

## Remaining external checks

Supervisor, authenticated ingress and physical commissioning remain unverified.
The authorized V4 push was commit `1d420848cdbb57e50169b552c178947343a5d494`.
The [image workflow](https://github.com/Nxt-1/EnergyManager/actions/runs/39935019989)
passed, including its tests, container build and publication of version4.0.0. Docker
was unavailable locally. No live installation/database, real hardware, external
notification or controller enablement was used. Review the runbook before
installing/configuring this major update; explicit complete physical/actuator mappings
and commissioning/exclusive-controller flags are still mandatory for control.

## CI timing regression follow-up — 23 October 2026

The [initial CI run](https://github.com/Nxt-1/EnergyManager/actions/runs/39935019991)
had42 passing tests and one failure in the real-solver disconnect test. Its elapsed
wall-clock assertion expected a requested80ms sleep plus observation processing to
finish within200ms; the observed time was423ms. The image workflow passed the same
test on the same commit. Those logs do not establish the actual protective-dispatch
latency on the failing runner.

Four diagnostic local runs restricted to two CPUs recorded protective dispatch in
1.13–2.39ms, while the old sleep-based measurement varied from83.38–166.31ms. These
are synthetic local measurements, not installation evidence or a CI latency guarantee.

The test now observes actual protective-actuator delivery, requires delivery while
the real full-horizon solve is pending, checks zero EV power and the current generation,
preserves unaffected ESS validity, and waits for stale-result rejection. The2s dispatch
timeout is a test deadlock guard; it is not a control-latency claim. Host-dependent
subsecond wall-clock assertions are removed. Runtime scheduling/control code is unchanged.
Existing numerical latency measurements above remain performance evidence.

Local verification with two-CPU affinity:43 tests passed in28.29s; Ruff and mypy passed.
Four additional focused runs passed in5.31–5.40s each, also restricted to two CPUs.
The [follow-up CI run](https://github.com/Nxt-1/EnergyManager/actions/runs/39936237809)
passed on commit `9fa914a97c2e7c34c877e636c3e50f85f0bc56e8`:43 tests in33.93s,
Ruff, mypy, CLI and JavaScript checks, configured localhost integration, wheel/source
archive builds and the Linux container build. Its synthetic seven-day integration
accepted2,018 intervals in25.806s, with maximum measured control tick6.85ms and21
fake-only service calls. Structured remote evidence is in ci-verification.json.

Storage policy is unchanged: no retention deletion is enabled. Prior compressed decisions
used about72–127kB per snapshot/result pair; one-second synthetic measurement+command
bodies averaged about742 bytes/cycle. A provisional200MB/day (about6GB/month) capacity
allowance includes overhead and replans; this is an estimate, not installation growth.
Use backups and review actual disk/event rates before unattended commissioning.

No usage-limit interruption, reset credit, paid API switch or recurring automation occurred.


## V4.5 / ARCH-005 first milestone — local, 25 October 2026

Implemented on codex/v4.5-implementation, based on released 4.3.8; not published or
installed. The scheduled start ran at 23:30 Europe/Brussels, and its one-time automation
was paused. No actual installation measurements, databases, hardware or phone access.

- Final full Python suite: 266 passed in 42.98 s. Twenty-one new deterministic profile
  cases cover explicit arming, quiet-phase activity resetting idle completion, invalid
  reads/gaps, integration and trim boundaries, review/revision guards, original-sample
  retention/reselection, restart while recording or armed, capture limit, source mapping,
  demo isolation, API origin headers and a real HTTP read from a local fake HA endpoint.
- Frontend: 42 Node tests pass, including new profile-graph gap/peak/trim-selection
  checks and the native Appliances tab. Ruff, mypy (36 modules) and JavaScript syntax
  checks pass. No change to optimization policy or temporal resolution.
- Existing full-horizon configured synthetic E2E: accepted 2,018 intervals in 32.070 s,
  maximum measured control tick 3.930 ms, four fake-only service calls. See offline-e2e.json.
  This is synthetic integration evidence, not a measurement of active appliance capture
  overhead or installation performance.
- Actual browser checks on standalone and native HA-contract preview: sensor discovery;
  drafts retained across polling; editable Mazak save; graph/trim preview; rejection of
  missing-data selection; explicit save and previous-cycle retention; native arm,
  backend idle observation, discard/reload; light/dark contrast and clean browser logs.
  The native harness simulates HA built-in cards/Supervisor messages. No live HA frontend
  or mobile viewport was commissioned. The shown recordings are explicitly SYNTHETIC.
- Local wheel and sdist build successfully; all 57 runtime source/assets match current
  worktree bytes. These retain the base 4.3.8 metadata for local verification and must
  not be distributed as a release; V4.5 identity/publication is not prepared yet.

Run profile tests with an explicit ignored writable --basetemp under artifacts/ when
reusing the original checkout's interpreter. The initial test attempts failed before
fixtures ran because of temporary-directory access/missing-parent setup; reruns passed.
Separate preview ports 8105/8106 avoid another chat's existing 8102 process. Screenshot:
`C:/Users/Arne/.codex/visualizations/2026/10/25/01a174ba-43a6-7680-9dff-a5828471be00/v45-native-profile.png`.

Remaining: installation power-sensor IDs/update cadence and threshold/timeout calibration;
representative load variants and any aggregation policy; later scheduling, background
separation and Mazak timing/permissions. No live collection or deployment was performed.


## 4.5.0 appliance profiles integrated with4.4.17 — 30 October2026

The confirmed profile-management milestone is reconciled onto b2aee28(4.4.17),
preserving current routing, source/continuity planning, restart recovery, dashboard
controls and all existing tests. The original25Oct work is retained in a local Git
stash. No actual HA/database/provider/credential/hardware/phone access or deployment.

- Full merged Python suite:621 passed187.85s. Profile cases:23, including additive
  database upgrade preserving household state, restart/gap/trim/idle behavior and
  transactional rollback of failed save/selection, with matching in-memory state.
- Frontend:69 tests pass, retaining all current graph/EV/routing/recovery cases and
  adding profile graph/selection and draft-revision coverage. Ruff/mypy45 modules,
  every packaged JavaScript syntax check and CLI4.5.0 pass.
- Configured local fake E2E:25.589s,2019 intervals, max control2.913ms, four fake calls.
  Includes the current manual-cancellation/process replacement and recovery checks.
- Routed local fake E2E:70.858s,2023 intervals, max control5.212ms, four fake calls,
  two calendar imports and six fake Google route requests. Both reports passed;
  docs/offline-e2e.json contains the current routed run, the configured run is retained
  privately as artifacts/v450-configured-e2e.json. Timing is synthetic integration
  evidence, not an installation or active-recorder performance benchmark.
- Browser standalone and native contract harness: Appliances tab/source discovery,
  graph/gap rejection, reviewed trim/save, earlier-cycle retention, sequential profile
  and Mazak saves without false conflicts or lost drafts; current Overview/monthly
  peak/graph controls and EV status/calendar load. No browser errors/warnings.
  Native preview simulates HA built-ins; actual installation/mobile remains unverified.
- Wheel/sdist4.5.0 build;68 runtime source/assets/defaults match current source bytes.
  Isolated wheel imports/version/appliance asset pass. Database upgrade adds tables
  and mode-specific keys without changing existing household state/configuration.

No planner/solver policy, live-control behavior or forecast background subtraction is
changed. Sensor identities/update cadence and machine thresholds/timeouts need actual
installation configuration. Scheduling suggestions remain a subsequent milestone.
Release publication is authorized; exact-commit CI/image results are recorded in the
ignored local release state and final reply, without an extra verification-only commit.


## 4.5.1 task-detail power charts — 30 October2026

Display-only change to shared session/goal detail components; no Python planner/control
behavior changed.76 frontend tests pass, covering clipped interval powers, real zeros,
missing-data gaps, signed ESS AC/separate DC, shared goal deadline bounds, current and
restored-plan guards, DST offsets, second-level partial intervals and escaping.
Five native asset/API tests pass; Ruff/mypy45 modules/all JS syntax checks pass.
Configured fake E2E:25.470s,2019 intervals,max control3.162ms,five fake-only calls.
Native browser EV/ESS session charts and shared requirement chart/table, standalone
requirement details and native light/dark rendering pass with clean browser logs.
The shown frozen profiles come from synthetic fake-HA data, not installation evidence.
Wheel/sdist4.5.1 build;all68 runtime source/assets/defaults match current bytes and
isolated wheel version/session-details asset import passes. Local verification is
focused on the changed UI and existing fake integration; full Python/routed/container
release checks run in CI. Screenshot retained privately as v451-ev-power-profile.png.
No live HA/database/hardware/notification/deployment operation. Subsequent exact-commit
CI/image results belong in the ignored release state/final reply, without another commit.
