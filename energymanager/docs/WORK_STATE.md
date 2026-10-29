# EnergyManager work state

## Current checkpoint — continuity across charging limits (4.4.15, 29 October 2026)

AUTHORIZED: implement the optional continuous-session fallback across all active limits,
not just80%. Required skill/current docs checked. Base4.4.14 at
758b16c80ff516277a8cb8c65fc7ccee01f2d5ab; CI40877360277/image40877358386 succeeded.
Main's unrelated DEFERRED_WORK.md remains pending; preserve all its raw bytes. No live
service/database/provider/credential/hardware/notification or installation operation.

IMPLEMENTED: selected charging work activates the candidate, including already-satisfied
or absent targets. Inherit model interval ceilings, required-target/exceptional authority,
source/permission/availability/current/phase/hold constraints without a fixed percentage.
Preserve selected boundary quantity; unnamed work uses its local day; candidates are
bounded to24h. The unrestricted main search retains freedom. Bounded solar cleanup keeps
future ESS stocks/dispatch/import upper bounds, selected quantity exactly and partial-slot
amperes; optional incidental SoC prefixes may move, named deadlines/margins remain hard.
Try unchanged economic/cash comparison, then the same carried allowance, without stacking.
Up to11s initial/9s reserved final solar work includes up to3s/30% continuity inside the
unchanged global deadline, preserving the previous fast solar allocation opportunity.
Skip the narrow search for an already-continuous single-phase profile. All replacement
rows/bounds/integers and independent/rolling audits checked; live control unchanged.
Progress label/version15/architecture/decisions/runbook/verification/changelog synchronized.

VERIFIED: 573 Python cases115.19s, 66frontend, Ruff, mypy43modules, syntax, CLI and sdist/
wheel pass. 21 dedicated cases include three full-planner configured-limit regressions.
An initial synthetic fixture split the15s preparation interval incorrectly; corrected
actual-duration profiles. An initial complete replay still timed out despite helper
success; exact quantity/partial amperes and bounded optional-prefix handling resolve it.
Final complete latest replay at120s: one13:51–16:00Brussels session,3.266051kWh unchanged,
99.57s elapsed, all model/independent/rolling checks pass. Prior solar replays retain
7.262/7.524kWh first-day capture, about80% horizon charge and one first-day session each
(101.24/99.91s). At12s the latest result is valid but may retain fragmented fallback;
no guarantee of continuity after budget exhaustion or global optimum. Original evidence
stays private/unmodified; release-final reports under artifacts/v4415-optional-continuity/.
Configured routed fake E2E passes2023intervals/2journeys/6fake routes/4local calls;
65.84s acceptance,max control tick3.32ms;cloned recovery58.23ms.

NEXT: final diff/commit/main fast-forward and push, preserving unrelated backlog bytes.
Verify exact-commit CI and image; put remote results only in ignored release-state/final
reply. No optional success-only docs commit or installation deployment.

## Earlier checkpoint — consistent direction arrows (4.4.14, 29 October 2026)

AUTHORIZED: user requested → import/charge and ← export/discharge for grid/ESS summary
markers. Required skill and living docs checked; isolated worktree clean at4.4.13
035c990001b31d7fe62a3a85f1648bb23eb84cff. Exact-commit CI40875550803 and image40875550799
succeeded. Main has unrelated pending DEFERRED_WORK.md; original bytes saved privately.

IMPLEMENTED: change only the shared grid/ESS energy-row symbols; original values,
forecast comparison markers, numeric signs, source accounting and control unchanged.
Version4.4.14 and existing architecture/decisions/runbook/verification/changelog sync.
VERIFIED:66frontend and15 native-dashboard/release tests10.31s;asset syntax passes.
No live service/provider/database/credential/hardware/notification/install access.
NEXT: commit/main fast-forward/push preserving pending backlog; verify exact-commit
CI/image and record results in ignored artifacts/v4414-direction-arrows/release-state.txt.
No optional success-only docs commit or installation deployment.

## Earlier checkpoint — reliable solar capture (4.4.13, 29 October 2026)

AUTHORIZED: user said implement stronger starting candidates, reserved solar refinement,
checked timeout retention and regression checks on both supplied decisions. Keep existing
economics, health/source/permission/continuity rules, snapshot planning and live control.
No stored ESS export, arbitrary full-SoC penalty, live services/hardware or deployment.
Required skill/docs rechecked. Base4.4.12 cd459b7a9181a6eab6b0cbf0c486effa615fdeac;
CI40866509400/image40866509412 succeeded. Main has unrelated DEFERRED_WORK.md edits;
original bytes saved privately under artifacts/v4413-solar-capture/ for preservation.

IMPLEMENTED: SolarCapture makes an unused-DC export candidate, releasing only idle
converter/grid direction flags. Restricted24h EV/solar/ESS candidates cover the full
horizon, preserving earlier EV delivery/readiness, future ESS stocks/dispatch and each
interval's import upper bounds. Later grid EV may shrink when captured solar replaces
required imports. Original rows/bounds/integers and independent/rolling audits check each
replacement; existing economic/continuity selection stays. Normal joint search remains
unrestricted. Initial refinement prioritizes the immediate window; up to6s reserved from
the existing global budget for a final pass before required timing/source certification.
Valid warm candidates survive a no-incumbent timeout/worse result. Raw solver stages
retain status/bounds/gaps and flag retained_starting_candidate separately. Planning
activity recognizes the stage; version, architecture, decisions/runbook/verification sync.

VERIFIED:552Python tests102.39s;66frontend,Ruff,mypy43modules,asset syntax,CLI and4.4.13
sdist/wheel pass. Final15 affected cases pass1.58s. Initial full run547pass/2legacytimeout
failures corrected by explicitly excluding warm candidates in no-candidate recovery tests;
new deadline regression confirms safe candidate retention without an extra solve.
Configured routed fake E2E passes2023intervals/2journeys/6fake routes/4local calls;66.44s
acceptance,max control tick2.91ms;cloned saved-plan recovery72.35ms. All endpoints fake.
Both private frozen exports verify and pass original-model/independent/rolling checks.
12s runs finish11.64/11.80s: earlier first-day EV7.262kWh versus original0, reaching79.97%;
later retains7.524kWh/79.99%. At120s finish102.26/101.32s, reach79.98/79.99%, essentially
zero unusedDC across the horizon. Assumed combined comparisons improve7.926→-3.946EUR
and6.546→1.050EUR; no realized savings/global optimum claim. Final reports/results under
artifacts/v4413-solar-capture/final/; original exports remain unchanged/private.

NEXT: final diff/commit, main fast-forward/push preserving unrelated backlog raw bytes,
verify exact-commit CI and image publication. Record remote success only in ignored
release-state/final reply; no optional success-only commit or installation deployment.

## Earlier checkpoint — ESS display sign (4.4.12,29 October2026)

AUTHORIZED: user explicitly requested the visual ESS sign change while preparing separate
prompts for the remaining solar/full-battery issues. Required code-writer and current
project docs checked. Base4.4.11 at7aaf7c907c703343a4b15e1a6bc3cc6d1f189535. Main checkout
has unrelated pending DEFERRED_WORK.md entries; preserve its raw bytes. Earlier solar
review/evidence below remains private and is not authorization for an optimizer change.

IMPLEMENTED: frontend ESS AC power positive charging/negative discharge for live cards,
planned/recent/archived charts and cursors; charge/discharge arrows now up/down. Missing
values remain gaps/dashes. Input mapping explicitly says input positive-discharge. No
raw HA/backend/API/archive sign, house/grid balance, SoC, kWh totals, planner or actuator
behavior changes. AC converter exchange still excludes direct DC charging and can
include DC inversion; live/legend tooltips and docs identify that boundary. No net-battery
sensor or solar-routing change. Version4.4.12 and maintained docs synchronized.

VERIFIED:43 focused native/dashboard/history/settings/release cases13.38s;66frontend,
all asset JS syntax,Ruff,mypy42modules,CLI and4.4.12sdist/wheel pass. Configured routed
fake E2E passes2023intervals/2journeys/6fake routes/4local calls;66.03s acceptance/max tick
6.68ms;cloned saved-plan recovery56.97ms. Standalone cursor shows charging+437W; native
synthetic raw+1500W discharge shows-1500W, unchanged400W house and50percent SoC. Light
native and dark standalone layouts checked. All evidence synthetic/local; no live HA,
database/provider/credential/hardware/phone/install access. Private evidence:v4412-ess-sign/.
NEXT: final review/commit/main fast-forward preserving pending backlog, push and verify
exact-head CI/image. Remote results go ignored release-state, without success-only commit.

## Earlier checkpoint — solar graph/full-ESS review (29 October2026)

READ-ONLY user report: cursor powers do not add up; ESS stays full, suggesting earlier
export. Base4.4.11 at7aaf7c907c703343a4b15e1a6bc3cc6d1f189535;CI40781457613/image40781457818
success. Isolated worktree was clean;main pending unrelated backlog remains untouched.
No application implementation requested/authorized. No version, commit or release change.

Verified supplied export digest and original audits.12:15Brussels:Solar4.906kW is
AC2.130+DC2.775;house.526,ACbatterycharge1.604,DCbatterycharge2.775. NegativeESS means
charging. Chart mixes total rawPV andACconverter exchange, omitting directDCcharge from
ESS line;true storage gain4.244kW after losses. ESSfull12:45-17:00 with5.12kWhunusedDC.

Offline counterfactuals pass independent/rolling/full-model checks: direct unusedDCexport
adds4.830kWh/.1917EUR with stocks/otherdispatch unchanged. Freeing only pre17solar charge/
export routing adds5.143kWh/.2042EUR;ACcharge3.522->0kWh,DCcharge8.811->12.225kWh;fullat17:00
andall17:00/futurestocks/dispatch fixed. Restricted solveOptimal0.109s,not globaloptimum.
Seed convertsDC only for loads and fills storage greedily; all main economic stages
timeout at unchanged objective; narrow finalmingridcertificate freezes solar decisions.
NEXT: explain findings; proposed chart-accounting and robust solar-incumbent improvements
need explicit implementation request. Do not add arbitrary early-discharge/SoC penalties.
Evidence/reproduction/privatecopy:artifacts/solar-plateau-review-2026-10-29/,review-state.txt.
No liveHA/database/provider/credential/hardware/notification/deployment access.

## Earlier checkpoint — saved-plan startup recovery (4.4.11,28 October2026)

AUTHORIZED: user said implement that after agreeing to fast startup recovery first,
keeping shutdown stop until an independent offline bound is verified. Base4.4.10 at
7f995fdda0a712c68671760e7ca761b864e06f52;CI40775629393/image40775629097 success.
Required skill/project docs and clean isolated state checked. Main has unrelated pending
backlog ARCH-015..020; preserve its original raw bytes (saved v4411 artifacts). This
release appends ARCH-021 only; integrate without staging the unrelated main entries.

IMPLEMENTED: format1 execution context stamped with accepted archive transaction; masked
active-settings/requirements/permission identities and result/snapshot checksum checks.
One startup candidate restores authority only after fresh measurements/go-e and compatible
remaining inputs, without solver/economic recheck. Real invalidations/Off/faults/old history
fail closed; legacy plans need one fresh calculation. Original evidence remains untouched.
Restore runtime controller intent before hardware-enable protection/next snapshot so dry-
run zero does not insert a new off hold. Backend recovery authority keeps EV sessions
current in display without rewriting original revision. Shutdown stop unchanged. No live
HA/database/Google/Ford/credential/hardware/notification/install operations.

VERIFIED:540Python tests98.47s;65frontend,Ruff,mypy42modules,CLI4.4.11 pass.
Configured routed fake E2E2023intervals/2journeys/6fake routes/5local calls passes;
65.96s acceptance/max tick4.19ms. Cloned compatible archive reconciles57.45ms with no
solver/provider/actuator call and unchanged evidence. This excludes fresh-input/startup
and charger settling latency. Lifecycle regression executes6A while solver blocked;
actual next snapshot holds recovered request. All unsafe/legacy/corrupt cases fail closed.
Shutdown stop remains. Docs synchronized. Evidence:v4411-plan-recovery/.
NEXT: package/commit, main integration preserving unrelated backlog bytes via path-scoped
stash/composition (ours ARCH-021 only), push and verify exact-head CI/image. No live
installation operations. No optional success-only documentation commit.

## Earlier checkpoint — EV detection update (4.4.10,28 October2026)

AUTHORIZED: user said go after proposed120second blocked-wait fallback and configurable
FordConnect vehicle charging status. Required code-writer and maintained docs reviewed.
Base4.4.9 at1ebc40cd21fc44ff2fd5df2b1fcb1c8d3e379d95. Three pending review docs are ours;
main DEFERRED_WORK.md changes are unrelated and must remain byte-for-byte preserved.

IMPLEMENTED:120second persistent blocked non-delivery wait, existing90second ordinary
non-delivery watchdog unchanged. Optional ev_diagnostics.vehicle_charging sensor, blank
by default. A recently read explicitFAULT stops/latches without reboot, including during
pending recovery; persistent cloud HA state is reported evidence, not a proven new car
measurement. Unknown/unsupported/stale optional telemetry keeps normal power detection
but cannot authorize reboot. Waiting clears on actualpower. Incident snapshots/sampler
retain selected bounded attributes with HA read/report times and unknown vehicle source
time. Settings/native history/EV sidebar expose the optional source; reported faults must
clear before acknowledgement. No planner, first-stop hypothesis or live control-policy
change beyond authorized EV supervision. Version4.4.10 prepared.

VERIFIED: full519tests102.40s; final146affected cases6.19s;64frontend,Ruff/mypy41modules
and4.4.10sdist/wheel pass. Mixed status/current
updates cannot reset continuous acknowledged-request/non-delivery; normal continuous
healthy90second reboot eligibility remains. Actual power/intentional stop reset clocks.
Routed fake E2E passes2023intervals/2journeys/6fake routes/4local calls;65.66s acceptance,
max tick3.06ms. Final code/source review and docs synchronized; initial bootstrap-template
mismatch corrected and full suite passed. Private incident evidence remains ignored.
NEXT: package/commit/main fast-forward preserving unrelated backlog bytes, push and verify
exact-head CI/image. No installation deployment. Local evidence:v4410-vehicle-fault/.

## Earlier checkpoint — EV incident review (28 October2026)

READ-ONLY request: investigate supplied EV incident and discuss shorter waiting plus
configurable Ford charging status. Base4.4.9 at1ebc40cd21fc44ff2fd5df2b1fcb1c8d3e379d95;
exact-head CI40771893411 and image40771893306 succeeded. Isolated worktree was clean;
main pending DEFERRED_WORK.md is unrelated. No application code or version changes.

Export5776events,not truncated; original bytes and review preserved ignored under
artifacts/ev-incident-a895697f-review/.SHA2564acac01dcf6899cb6b813f35538e22e9c66ee5deddb0e500434e7e02775f6b9a.
Brussels21:38:39EM stop,21:40:19restart;power stays nearzero;21:41:01car-complete
waiting starts;21:56:01incident/alert,no reboot eligibility. go-e error0 throughout;
phase unchanged. First stop follows44->46.5percent SoC jump by about20s; live interval-
stock cap/smoothing is a plausible cause, but the referenced plan is absent. No proof
of hardware/Ford fault; the Ford charging-state sensor was not collected in this report.

User confirmed no15minute wait and configurable Ford charging-state source. Proposed
120second blocked fallback plus existing90second confirmed non-delivery, immediate
fresh explicit vehicleFAULT, archive raw status/attributes; preserve charger/phase/ESS
and reboot guards. Reviewed exact FordConnect2026.10.7 tag:const_tags passes through
xevBatteryChargeDisplayStatus;const_shared includesFAULT;cloud polling/default60s.
Architecture marks accepted requirements pending;DECISIONS records scope. No code,
commit/release, live HA/provider/database/credential/hardware/notification operations.
NEXT: explain findings; await explicit implementation request before application changes.

## Earlier checkpoint — earlier required charging (4.4.9,28 October2026)

AUTHORIZED: user reaffirmed the original early-charging requirement and explicitly said
Fix that. Base4.4.8 at7806b51961a703d724729950a0205db29d613248. Required code-writer,
architecture/deferred/decisions and actual Git state reviewed. Main has unrelated pending
DEFERRED_WORK.md changes; preserve them byte-for-byte. Isolated V4.4 branch only.

IMPLEMENTED: separate bounded direct-grid delivery-time preference before final grid
certification, with checked whole-profile earlier incumbents that survive solver timeout.
Keep original model rows/bounds/integrality, chosen non-grid/ESS dispatch, grid quantity,
monthly peaks, service/terminal stocks, readiness and no-worse cost/cash/continuity.
Physical/permission/rolling checks still gate selection on the same frozen snapshot.
No live invalidation, extra mismatch solves, controller or UI changes. Docs/version4.4.9
prepared. No live installation/API/credential/database/hardware/notification access.

VERIFIED:502 Python tests99.06s; final27 timing/continuity/release-contract tests37.08s;
63 frontend cases, Ruff/mypy40modules and CLI4.4.9 pass. Full frozen seven-day replay
valid106.77s, independent/rolling errors empty; first session moves00:15–02:35 to
21:15–23:35 Brussels after21:13:59 hold, same2.898kWh/9.557428EUR bill/5.49kW peak.
Final bounded grid certificate succeeds; global economic optimality is not claimed.
Routed fake E2E2023intervals/2journeys/6fake routes/4local calls passes; acceptance65.89s,
max control tick4.19ms. Private evidence:ignored artifacts/charging-delay-review/;
local checks:artifacts/v449-timing/. NEXT: package/diff review, commit/integrate preserving
main backlog, publish and verify exact-head CI/image. No installation deployment.

## Earlier checkpoint — charging-delay review (28 October2026)

The sequential first task is complete. Current base:4.4.8 at
7806b51961a703d724729950a0205db29d613248. Prior cleanup verification/publication evidence
is in ignored artifacts/v448-compact-session/release-state.txt.

Read-only review of the supplied frozen decision is complete. Export digest/file hash
verify; original audits pass. Moving the identical6A/1.38kW/2.898kWh session from29Oct
00:15–02:35 to28Oct21:15–23:35 Brussels passes independent/rolling and all joint-model
row/bound/integrality checks. Hold ends21:13:59. Same bill9.557428EUR,peak5.49kW,ESS
flows/terminal stocks and continuity score51.978. Current objectives have no preference
between these timings once cost,continuity and15-minute readiness margin are satisfied.
Final grid certification retains chosen quarter envelopes; its Optimal is narrowly scoped.

At this historical investigation checkpoint the fix was proposed only. The subsequent
user correction and explicit Fix that authorize the implementation recorded above.
Reproduction and detailed evidence:ignored artifacts/charging-delay-review/review.py,
evidence.json,counterfactual-flows.json and review-state.txt. No live installation access.
This investigation checkpoint is intentionally uncommitted; no success-only release commit.

## Earlier release checkpoint — scheduled compact session details (28 October2026,21:41 Brussels)

AUTHORIZED: user scheduled implementation of a much shorter EV detail dialog, keeping
only title/time/battery kWh and short named contributions from the highlighted screenshot.
One-time automation simplify-ev-session-details paused immediately on invocation. Base
e9f3319 (published4.4.7; exact-head CI/image success in ignored prior checkpoint). Use
isolated V4.4 worktree; preserve unrelated main backlog bytes saved in ignored v448
artifacts. No live installation/HA/Google/database/credential/hardware/phone access.

IMPLEMENTED4.4.8: remove generic EV charging reason and explanatory sections; render one
compact Supports list. Same-goal driving/target amounts share one row, labelled separately
without addition. Target-only rows omit repeated target capacity and wording. Keep brief
legacy/unknown/no-named-goal fallbacks. Attribution data, optimizer/control/permissions,
4.4.7 Overview24h goals and full Planning/cost view remain unchanged.

VERIFIED:25 focused UI/API cases0.63s,63 frontend cases,Ruff pass. Routed fake E2E passes
2023 intervals/2journeys/6fake routes/4local calls; acceptance60.94s/max tick5.16ms.
Standalone/native dialogs contain only title,time,battery kWh and short Supports rows;
console warnings/errors empty. Screenshot:v448-compact-session.png. Temporary tabs/servers
closed. Maintained architecture/decisions/run instructions synchronized. Attribution
metadata and 4.4.7 Overview/Planning behavior remain unchanged.

NEXT: package/commit/push and exact-head CI/image verification. ONLY AFTER this cleanup/release
finishes, investigate the preserved charging-delay decision read-only and propose a fix.
No planner implementation is authorized by that second request. Frozen decision:
artifacts/charging-delay-review/decision-2026-10-28.json, SHA256
cb904e39ed6e99e85d90a8fb31c5893f344d158b5aa3b311bf1afcff3d21a496.

## Earlier release checkpoint — next-day Overview goals (28 October2026)

AUTHORIZED: user explicitly requested removal of Overview forecast costs and restoration
of goals for only the next24hours. Base85e2574 (published4.4.6; exact-head CI/image success
in ignored prior checkpoint). Isolated V4.4 branch. Main pending backlog bytes are saved
in ignored artifacts/v447-overview-goals/main-backlog-original.md. Prepared main-backlog-
after.md changes only the authorized ARCH-012 paragraph, preserving every other byte.

IMPLEMENTED4.4.7: Overview replaces the forecast-cost card with chronological deadlines
in(now,now+24 elapsed hours], with a clear empty state and window heading. Planning
retains the full goal list and forecast costs. Existing single earliest-goal meter,
trip kWh/session explanations and planner/control behavior remain unchanged.

VERIFIED:25 focused native/dashboard/schedule API cases0.72s,63 frontend cases, Ruff,
shipped-JS syntax and CLI4.4.7 pass. Configured routed fake E2E passes2023 intervals,
2journeys/6fake routes/4local calls; acceptance60.77s/max control tick5.20ms. Standalone
and native Overview show2 goals (next morning/first trip), excluding later trip/mornings;
Planning shows all9 and forecast costs. Back navigation restores the2-goal/no-cost view.
One earliest-goal meter remains. Warn/error console empty. Screenshot:v447-overview-24h.png.
Temporary tabs/servers closed. Low-impact presentation verified with existing suites and
actual rendered behavior; no implementation-mirroring tests added. No live installation/
HA/Google/database/credential/hardware/phone operations. Living docs synchronized.

Wheel/sdist/isolated install match all61 package files; source archive matches all14
maintained Markdown documents. Isolated4.4.7 import and updated view resources pass.
Source archive is refreshed after this final checkpoint. Main pending backlog bytes
still match the saved original; only the scoped ARCH-012 paragraph changes in release.

NEXT: scope-review/commit4.4.7, integrate main preserving all unrelated pending backlog
bytes, then check exact-head CI/image.
Record remote outcomes only in ignored release-state.txt/final; no success-only commit.

## Earlier release checkpoint — meaningful EV session contributions (28 October2026)

AUTHORIZED: user explicitly said Implement that after agreeing to named goals and
planned kWh contributions, accounting for existing battery energy, intervening trips
and other sessions. Repeated morning targets consume no energy; retain additional
stored energy explicitly. Base59400a6 (published4.4.5; exact-head CI/image success in
ignored prior checkpoint). Isolated codex/v4.4-google-maps worktree. Main's pending
backlog entries are unrelated; original bytes saved in ignored v446 task artifacts.

DESIGN: explanatory FIFO ledger (existing battery charge first, then chronological
session charge), driven by the frozen plan's actual per-slot energy/withdrawals.
Trip use partitions session energy across named trips and remaining/unresolved stock.
First-use target support is separate, non-additive evidence; the same cohort is not
credited to every later target. Unknown EV-state barriers stop future attribution.
No optimization, live control, source permission or measured-history behavior changes.

IMPLEMENTED4.4.6: session_attribution.py records disjoint named driving use, retained
known stock and unresolved energy. First target support is tracked separately without
repeated equal-target claims; redundant trip-target rows are omitted. Planner output
uses this metadata/goal_ids; shared session details render named kWh, reserve/stock and
unresolved/legacy cases. New asset has its versioned native route. Scheduling, frozen
flows, controller behavior and permissions remain unchanged.

VERIFIED:496 Python tests88.41s;19 focused attribution/native cases1.84s;63 frontend
cases, Ruff, shipped-JS syntax and mypy39 pass. Tests cover6/2 split, initial inventory,
other sessions, deadline/overlap/partial/target/reserve/unknown behavior and conservation;
real Planner output, HTML escaping and legacy result rendering pass. Configured routed
fake E2E passes2023 intervals/2journeys/6fake routes/4local calls; acceptance60.66s/max
tick4.14ms, real HiGHS cancellation/admission and session allocations checked. Standalone
and native dialogs show0.28kWh retained stock and only31October morning target support;
no blanket goal count. Warn/error console empty. Screenshot:v446-session-contribution.png.
Temporary tabs/servers closed. No live installation/HA/Google/database/credential/hardware/
real phone operations. Maintained architecture/decisions/run instructions synchronized.

Wheel/sdist/isolated install match all61 package files; source archive matches all14
maintained Markdown documents. Isolated4.4.6 attribution import and new packaged asset
pass. Source archive is refreshed after this final checkpoint. Main/origin remain
59400a6 at pre-release fetch; pending main backlog bytes match the original copy.

NEXT: scope-review/commit4.4.6, fast-forward/push main preserving pending backlog bytes,
then check exact-head CI/image.
Record remote outcomes only in ignored release-state.txt/final; no success-only commit.

## Earlier release checkpoint — focused goal-card cleanup (28 October2026)

AUTHORIZED: user requested removal of Overview goal cards, chronological Planning goals
and trip energy in kWh; explicitly chose a bar only for the earliest upcoming goal.
Base7a1c8c1 (published4.4.4; exact-head CI/image successful, see ignored prior checkpoint).
Use isolated V4.4 worktree. Preserve main's unrelated backlog additions; original bytes
are saved in ignored artifacts/v445-goal-cards/main-backlog-original.md.

IMPLEMENTED4.4.5: hide the whole goals card on Overview; display all Planning goals,
including morning minima, together by deadline. Show estimated driving kWh separately
from the reserve-inclusive departure target, consistently in cards/EV agenda/details.
Only the first future goal has a labelled current-charge/target meter, hidden when EV
energy is unknown. Later/past goals retain planned SoC/readiness without a progress bar.
Scheduling, charging and goal persistence are unchanged.

VERIFIED:25 focused native/dashboard/schedule API cases and61 frontend cases pass;
all shipped-JS syntax, Ruff and CLI4.4.5 pass. Configured routed fake E2E passes with
2023 intervals,2 journeys,6 fake routes,4 local HA calls; acceptance60.77s/max control
tick4.17ms. Standalone/native browsers show chronological mixed goals, only one labelled
upcoming meter, Overview card removal after navigation and consistent89km/16.02kWh
trip usage versus reserve-inclusive target. Warning/error console empty. Screenshot:
v445-planning-goals.png in the task visualization folder. Temporary tabs/servers closed.
No new low-impact UI implementation-mirroring tests; existing suites and actual rendered
behavior verify the scope. No live installation/HA/Google/credential/database/hardware/
real notification access. Scheduling/controller/persistence code unchanged.

Main's ARCH-012 entry was an uncommitted backlog addition. This release incorporates
only that authorized item's updated status; other pending entries remain uncommitted.
Ignored main-backlog-after.md contains the exact original main text with only ARCH-012
replaced; compare original bytes before integration and preserve all other entries.

Wheel/sdist/isolated install match all59 package files; source archive matches all14
maintained Markdown documents. Isolated4.4.5 module/assets import passes. Source archive
is refreshed after this final checkpoint. Final diff is limited to presentation,
release metadata and relevant docs; generated fake reports remain ignored.

NEXT: scope-review/commit4.4.5, fast-forward/push main with its other backlog entries
preserved, then check exact-head
CI/image publication. Record remote outcomes only in ignored release-state.txt/final;
no success-only documentation commit.

## Earlier release checkpoint — snapshot schedules with live control (28 October2026)

AUTHORIZED: user explicitly requested implementation of the agreed snapshot/live-
control architecture. Isolated branchcodex/v4.4-google-maps, base d5c4373 (4.4.3).
The five approved policy documents from main are included; original hashes are saved
in ignored artifacts/v444-snapshot-control/main-policy-docs.sha256. Main's unrelated
DEFERRED_WORK.md edit must remain byte-for-byte unchanged through integration.

IMPLEMENTED4.4.4: frozen candidate/reference validation plus narrow health/authority
admission. Keep original flows, forecast, goals, costs, reservations and interval grid;
record actual admission readings separately and select remaining commands by timestamp.
Remove fresh-stock revalidation/session repair and resource-deficit/monthly-peak extra
solves. Queue forecast issuances/corrections for the next periodic snapshot without
revoking accepted authority. Live ESS/EV modulation and existing structural, physical,
source/peak, input-health, phase/readback and charger protections remain active. No
new live grid-energy budget or stricter periodic cadence is introduced.

VERIFIED:482 Python cases pass86.69s;95 focused cases pass4.70s. All61 frontend cases,
shipped-JS syntax, Ruff and mypy38 pass; CLI reports4.4.4. Synthetic regressions cover
frozen mathematical/source/economic failures, actual admission health, coarse positive/
negative stock drift, in-flight continuity, adaptive live ESS/EV behavior and periodic
fresh inputs. Neither original private Downloads export remains available; no fresh
raw replay is claimed. A labelled synthetic case reproduces14.976→15.210kWh and
8.43525 planned versus8.190 required /0.14175 apparent excess.

Configured routed fake E2E passes:2023 intervals,2 imported journeys,6 fake Maps queries,
4 local HA calls, real spawned HiGHS/manual cancellation/reaping/latest-only adoption.
Routed acceptance60.78s/max tick4.22ms; standard acceptance25.36s/max tick3.30ms.
Both strengthened E2E variants explicitly assert
frozen validation, unchanged interval grid and separate persisted admission evidence.
No live HA/Google/database/credential/hardware/phone or installation operations.

Wheel/sdist/isolated offline install match all59 package files; source archive matches
all14 maintained Markdown documents. Isolated4.4.4 CLI/module import and packaged assets
pass. Source archive is refreshed after this final checkpoint. Final scope/whitespace
review passes; generated E2E reports stay in ignored task artifacts.

NEXT: commit4.4.4, fast-forward/push main preserving unrelated edits, then check
exact-head CI and image publication. Main/origin remain d5c4373 at final pre-release
fetch. Record remote outcomes only in the ignored checkpoint/final reply; no success-
only docs commit. Build the source archive after this maintained checkpoint is final.

## Earlier documentation checkpoint — snapshot planning with live control (28 October 2026)

AUTHORIZED: documentation update requested after the user clarified the architecture.
Snapshot → calculate → validate on the same snapshot → execute remaining schedule with
adaptive live ESS/EV control until replacement. Ordinary and large/sustained load/PV
mismatch and resulting inventory drift do not invalidate a schedule, cancel work or
independently request an extra solve. Periodic calculations consume fresh inputs and
supported forecast corrections. Structural goal/config/permission and genuine safety/
availability events retain their handling. Physical/source/peak/input/charger guards
remain active. No new live grid-energy budget, fresh-stock economic revalidation or
publication energy-repair layer is part of the accepted design.

DOCUMENTED: updated the existing Architecture_Proposal.md in place, replaced conflicting
publication/mismatch-trigger requirements and labelled superseded implementation/history.
DECISIONS.md records the new choice and the superseded4.4.1 repair decision. Supporting
forecast/runbook notes distinguish accepted policy from the shipped implementation.

IMPLEMENTATION GAP: current published baseline4.4.3 atd5c4373 still performs fresh-stock
publication revalidation/repair and mismatch-triggered extra solves/invalidation. These
have not been changed or newly verified. Do not infer code authorization from this docs
request or previous routing-release mandates. A separately authorized migration should
preserve full frozen-input audits and adaptive live control, narrow admission checks,
remove mismatch-only triggers/repair and verify the supplied frozen rejection plus
normal/coarse measurement drift and genuine safety/authority failures offline.

This task changes documentation only: no application code/config/version change, commit,
push, publication, live HA/database/API, hardware or notification operation. Preserve the
pre-existing unrelated DEFERRED_WORK.md edits in the main checkout. Documentation diff
and consistency checks are sufficient; application tests are not required for this edit.
CHECKED: documentation-only diff, updated policy/implementation labels, new section links
and git diff --check pass. The unrelated backlog remains byte-for-byte unchanged.


## Earlier release checkpoint — stable route timing and safe diagnostics (28 October2026)

AUTHORIZED: user said Go ahead to fixing intermittent route resolution and exposing
safe failure reasons. Base5ea9dfe (published4.4.2); use isolated V4.4 branch. Preserve
main's unrelated DEFERRED_WORK.md edit. No live Google/HA/database/hardware/phone calls.

IMPLEMENTED:4.4.3 reserves60seconds when choosing each traffic-aware departure and
still requires an actual response at that exact departure to predict on-time arrival.
Max3 outward/1 return requests, no transport retries, no deadline waiver, no guessed/
last-good fallback. Genuinely unsettled or past timings remain unresolved. Fixed public
codes/text distinguish access/quota/provider/connection/timeout/response/timing and
missing home/destination/invalid journey. Raw provider bodies and exception text never
reach diagnostics. UI renders the escaped safe reason; archived failure events contain
only journey ID/code/numeric HTTP status/time. Credential/request-generation guards
and existing retention/notification policies remain.

VERIFIED:468 Python tests passed85.63s;78 focused routing/worker cases passed0.96s.
All61 frontend tests, Ruff, mypy38 modules, changed-JS syntax and whitespace checks pass.
Synthetic one-second/subsecond duration changes resolve with a checked on-time departure;
material nonconvergence rejects. HTTP/access/quota/timeout/connection/body/home/privacy
and failed-refresh/no-fallback/recovery cases pass. Browser4.4.3 shows the safe429 quota
message, clears it through the actual refresh worker and keeps both89km routes resolved
across three refresh clicks despite increasing fake durations. Warning/error console
is empty. Screenshots in this chat's visualization folder: v443-routing-error.png and
v443-routing-recovered.png. All services/data are fake; no real credential/API/HA used.
Temporary preview tab/server are closed.

Wheel/sdist match all59 package files and current maintained docs. Isolated4.4.3 wheel
imports, timing constant, updated UI resource and safe-error boundary pass. Source
archive is refreshed after this checkpoint. Main/origin remain5ea9dfe at final fetch.

NEXT: scope-review/commit4.4.3, fast-forward/push main while
preserving unrelated edits, then verify exact-head CI/image publication (including both
configured fake E2E runs). Record remote results only in ignored checkpoint/final reply;
no success-only docs commit. This fixes a reproduced code failure mode, not proof that
it caused every particular installation failure.

## Earlier release checkpoint — expired manual goals (28 October 2026)

AUTHORIZED: user requested a fix for a past manual trip still shown as Waiting.
Base a06b471 (published4.4.1); isolated V4.4 branch. Main backlog edits remain unrelated.

IMPLEMENTED:4.4.2 durably retires elapsed manual SoC goals and finished manual trips.
Keep ongoing trips until known return; unknown/external return needs a fresh known
home observation after departure. Unknown/stale/settling inputs cannot establish return.
Archive the full goal/time/reason, clear its issues and preserve prior decisions and
useful control authority for other goals. Retired records stay retired after restart
or later unplugging. Saved empty lists remain empty instead of injecting demo goals.
Source managers keep calendar/routed records; active projections omit elapsed known
returns. Omit past morning cards; display Underway/Awaiting return for retained trips.
No broad ARCH-012 redesign, route activation or charging timer/permission change.

VERIFIED:442 Python tests passed86.57s;38 focused lifecycle/replanning cases passed2.78s.
All60 frontend tests, Ruff, mypy38 modules and changed-JS syntax pass. Synthetic control
loop retires goals without a page request or solver; restart persistence/history and
fresh versus stale return boundaries pass. Browser4.4.2 confirms expired entry absent,
underway/unknown-return/future entries retained with correct labels. Screenshot:
C:/Users/Arne/.codex/visualizations/2026/10/25/01a1736b-2b27-7952-a275-df6d08645259/v442-goal-retirement.png
The lightweight in-memory fixture does not exercise graph history (unavailable there).
Its temporary tab/server are closed. No actual HA/Google/database/hardware/phone used.

Wheel/sdist match all59 package files and maintained docs; isolated4.4.2 wheel imports
and updated UI resources pass (explicit UTF-8 for text inspection). Final source archive
is refreshed after this checkpoint.

NEXT: scope review/commit, fast-forward/push main while
preserving its unrelated DEFERRED_WORK.md edit, then verify exact-head CI and image
publication (including both configured fake E2E runs). Record remote outcomes only in
ignored local evidence/final reply; no success-only documentation commit.

## Earlier release checkpoint — charging publication repair (28 October 2026)

AUTHORIZED: user requested completion of release leftovers and an independently
established fix for the attached charging decision. 4.4.0 CI and image publication
succeeded at06fcf78; remote results are in the ignored recovery checkpoint.

IMPLEMENTED:4.4.1 adds one bounded same-phase extension of existing future charging
when elapsed calculated delivery was not confirmed by current EV stock. It adds only
missing required energy, splits exact boundaries, reconciles the reference and keeps
all independent source/physical/permission/rolling checks. Measured stock is unchanged;
failed extensions remain rejected. Original evidence is preserved; adopted sessions,
goal completion, reservations and aligned rejection evidence remain consistent.
Cached cumulative audit arithmetic changes no equations/tolerances. No charger timers,
route activation settings or unrelated backlog items were changed.

VERIFIED:425 Python tests passed84.43s;16 publication cases cover the repair and safe
rejections. Ruff, mypy38 modules,59 frontend tests and all asset JavaScript syntax pass.
Original attached candidate, repaired candidate/reference and a forced peak violation
produce identical old/new independent-audit results. Frozen replay adds0.140042kWh
in135.306s; total local reconciliation fell from19.35s to0.894s (single measurements).
The private attachment is not tracked. All committed regression fixtures are synthetic.
Configured routed E2E passes60.800s with2,022 intervals, two imported journeys, six fake
Google queries/four fake HA calls and maximum local control tick5.587ms. Actual HiGHS
cancellation/reaping and latest-only adoption pass. All endpoints are fake/local.
Wheel/sdist contain all59 package files byte-for-byte and maintained docs; isolated
wheel import/resources/version4.4.1 pass. Source archive is refreshed after this checkpoint.

NEXT: scope-review and commit4.4.1; fast-forward main, preserving its unrelated
DEFERRED_WORK.md edit, then push and verify exact-head CI/image publication. Main and
origin/main were06fcf78 at the final fetch. No actual HA/Google/database/hardware or real
notification/installation operations occurred. Record subsequent remote outcomes only
in ignored local evidence and the final reply; do not add a success-only docs commit.

## Earlier release checkpoint — 4.4.0 activated-key release (27 October 2026)

AUTHORIZED: user explicitly requested activation on a valid Settings API key and
publication to the main release. This supersedes the earlier offline gate and Maps
publication hold. Prepare/test in codex/v4.4-google-maps (base d48969c), commit, fast-
forward main while preserving its unrelated DEFERRED_WORK.md edits, push main and
verify exact-head CI and ghcr.io/nxt-1/energymanager:4.4.0 publication. Do not access
actual keys, live Google/HA/databases/hardware, send real notices or install the release.

IMPLEMENTED: remove compile-time gate and extra global enable switch; save a key to
activate immediately, blank preserves, replacement/clear applies without restart.
The first required route request validates it with Google; no separate paid probe.
Reject invalid keys/routes with existing unresolved warning/notice. Credential generations
reject obsolete responses; old clients cannot request subsequent legs after revocation.
Explicit manual overrides and checked in-progress away periods remain. All 4.3.20
behavior is retained. Settings success copy correctly says no restart for key-only changes.
Release metadata is4.4.0; current architecture/settings/runbook/changelog/decisions updated.
CI now also runs the local fake routed end-to-end fixture. Existing archive behavior is
unchanged; no new expiry/deletion or provider-rights assertion is introduced.

FINAL LOCAL:414 root Python tests passed87.52s,74 focused cases1.00s, Ruff/mypy38,
59frontend, all JS syntax and CLI4.4.0 pass. Configured routed E2E passed79.554s,
2,022intervals, two89km trips, six fake Google queries/four fake HA calls, maximum
control4.702ms. Current Settings browser save/clear works immediately with the dummy
key; saved field is redacted and No restart is needed is shown. Route resolution and
clear-to-unresolved were observed with fake endpoints only; browser logs were clean.
Screenshot: C:/Users/Arne/.codex/visualizations/2026/10/25/01a1736b-2b27-7952-a275-df6d08645259/v440-key-activation.png
All preview tabs/servers are closed. Package build/content and isolated4.4.0 import
checks complete before commit. Remote CI/image results belong only in ignored local
checkpoint/final after publication; no extra documentation-only release commit.

Main is currentlyd48969c, remote matches, with an unrelated deferred backlog edit.
Do not accidentally include that edit in the release. Recovery stash from compatibility:
e23e5a11caca9a1c7af3c51f3eea535abd930048. Preserve it and the original Maps archive.
NEXT: complete verification, record local evidence, build4.4.0, scope-review and commit
only release files. Preserve/stash main's unrelated backlog while fast-forwarding;
restore it afterward, then push and verify CI/image at the resulting exact SHA.

## Earlier compatibility checkpoint — 27 October 2026

AUTHORIZED: compare V4.4 with subsequent V4.3.x changes and correct compatibility before
release. Code-writer and current project instructions read. The isolated branch
codex/v4.4-google-maps was fast-forwarded from 304e386 to d48969c (main 4.3.20), then
the saved draft was reapplied. Recovery stash e23e5a11caca9a1c7af3c51f3eea535abd930048
is retained; details are in ignored artifacts/v44-4320-compatibility/recovery.txt.
No feature commit, push, release, live calls or deployment occurred. Main checkout
has only its unrelated DEFERRED_WORK.md edit and was not modified.

RESOLVED: seven stash-apply conflicts. Preserve request_plan("startup") and the new
PlanningWorker lifecycle, evidence-based replanning and planning_issue state; add the
journey lifecycle alongside them. Preserve the EV widget's new interaction object,
history/phase controls and action countdown while adding the route panel. Retain real
solver cancellation/latest-request checks and planner-failure fixture in offline_e2e.py;
wait for routed inputs before cancellation. Merge maintained docs instead of restoring
old copies. The original paused Maps archive and the recovery stash remain intact.

FINAL VERIFICATION: 411 Python tests passed in 87.14s; 95 focused cases passed in
5.94s. Ruff, mypy (38 modules), 59 frontend tests and all JS syntax pass. Initial
combined run was 408 tests in 87.33s before the three added compatibility cases.
The routed configured E2E passed in 73.671s: 2,022 intervals, two 89km trips, six local
fake Google queries, four fake HA calls and maximum local control tick 5.020ms.
Real solver cancellation/reaping/latest-only adoption is verified. A bounded recent-
event assertion failed after the longer solve; its matching event was retained in
the synthetic archive (sequence34 versus newest171). The tool now queries that exact
request ID instead of the latest100-event display feed; the rerun passed.

BROWSER: latest native widget opened mapped sensor.ev_kw history, retained phase
controls and charger activity, saved a101km override, then returned to the automatic
89km route. Standalone EV rendering passed; native warn/error console was empty.
Evidence: C:/Users/Arne/.codex/visualizations/2026/10/25/01a1736b-2b27-7952-a275-df6d08645259/v44-4320-native-check.png
Tabs/servers closed; ports8102/8103 have no remaining listeners. All services/data are
synthetic; no actual HA histories, hardware, Google billing or real phone verified.

PACKAGING: combined draft wheel/source archives build with inherited4.3.20 metadata;
all59 package code/assets/default files match both archives. Final maintained docs
are included. Isolated offline installation verifies routing/replanning/worker imports,
current UI resources and the disabled live gate. Core optimizer/planner/publication,
replanning, worker and charger/control files are byte-identical to committed main.
No optimizer/charger policy or timers were altered by the compatibility work.

LIVE_ROUTING_AVAILABLE remains False. Retention compatibility is still unresolved;
no special Google agreement is asserted necessary. Before public release, resolve live
activation/retention and release scope, then apply 4.4.0 versioning and run publication
checks. Current work is compatibility preparation, not authorization for live services.
NEXT: compatibility review/fixes are complete on the isolated branch. Before publication,
resolve the existing activation/retention and release-scope question, apply4.4.0 metadata,
and run the normal release/CI/image workflow. Do not publish an enabled Maps release
from this checkpoint. Preserve main's unrelated backlog edit and the recovery stash.
4.3.20's separately documented publication-accounting limitation remains unchanged.
Commands: pytest -q -p no:cacheprovider --basetemp artifacts/v44-4320-final-suite;
ruff check --no-cache src tests tools; mypy --no-incremental src/energymanager;
node --test tools/frontend.test.mjs; all asset node --check; tools/offline_e2e.py
--routing-fixture --serve (closed); build --no-isolation. PYTHONPATH selects this
worktree's src when reusing the original checkout's interpreter. Changes are unstaged.

## Earlier commit-preparation checkpoint — 25 October 2026

The scheduled commit-preparation run began at 23:30 Brussels / 22:30 UTC; automation
start-v4-4-google-maps-implementation was immediately PAUSED. Only this worktree was
edited: C:/Users/Arne/.codex/worktrees/v4-4-google-maps/EnergyManager, branch
codex/v4.4-google-maps, based on 304e386. No staging, commit, push, merge, release,
deployment, live Google/HA/database access or real notifications occurred.

READY: the offline integration diff, including new routing.py, journeys.py and their
tests, is prepared for a source commit. The current request authorizes preparation;
leave the changes uncommitted. Release metadata remains 4.3.5, with an explicitly
unreleased V4.4 changelog. LIVE_ROUTING_AVAILABLE remains False. Retention compatibility
is unresolved; a special Google agreement has NOT been established as necessary.
Clarification under applicable standard terms or a compatible retention design may
resolve it. A seven-day routing horizon is not a storage-expiry policy.

REVIEW FIXES: reject malformed attendance and override date types before changing
requests; reject non-object zone.home replies; handle unrepresentable provider times
as an unresolved trip while continuing other requests; retain saved override distance
(including zero) and home times when reopening the editor. Eight regressions reproduced
the failures before the fixes. Existing confirmed routing/notification/EV policies remain.

FINAL VERIFICATION: 291 Python tests passed in 44.72s; 77 focused routing/calendar/
settings/journey cases passed in 0.95s. Ruff, mypy (37 modules), all JavaScript syntax
and 33 frontend tests passed. The seven-day configured --routing-fixture passed with
2,022 intervals in 71.467s, maximum control tick 3.248ms, two 89km journeys, six fake
Google queries and four local fake HA service calls. Initial EV SoC 90% is synthetic.
Draft wheel/source archives built with --no-isolation and no downloads; all 57 package
files matched source, and a separate offline installation passed isolated imports,
resource and live-gate checks. Final docs are included in the local draft packages.

BROWSER: synthetic standalone editor retained 0km and saved home times through reopen
and save. It displayed the confirmed continue-other-goals warning. Screenshot:
C:/Users/Arne/.codex/visualizations/2026/10/25/01a1736b-2b27-7952-a275-df6d08645259/v44-commit-override-check.png
Browser tab/server closed; ports 8144/8145 have no remaining preview listeners.
Earlier native/mobile evidence remains described below; physical commissioning is unverified.

INTEGRATION: main advanced to 4fe2291 (4.3.8), and its feature chat now has additional
uncommitted edits. Do not edit or stage that checkout. Read-only three-way comparisons
of file copies found application-view.js, style.css and view.html combine cleanly with
committed 4.3.8; DECISIONS.md, VERIFICATION.md, WORK_STATE.md and offline-e2e.json require
manual reconciliation when a merge is authorized. Recheck live Git state then: the
comparison does not cover main's ongoing uncommitted work. No branch merge was performed.
The original gpt/paused-maps-2026-10-25 archive remains intact.

NEXT: user can review/commit this isolated offline draft. Before any later merge or
release, reconcile latest main changes and docs, rerun affected checks, resolve the
publication hold and version appropriately. Live activation remains separate pending
retention compatibility; no paid API tests or installation operation are authorized.
Use the existing interpreter read-only, with PYTHONPATH selecting this worktree's src.
Commands: pytest -q -p no:cacheprovider --basetemp artifacts/<unique>; ruff check
--no-cache src tests tools; mypy --no-incremental src/energymanager; node --test
tools/frontend.test.mjs; node --check for each asset JS; tools/offline_e2e.py
--routing-fixture; python -m build --no-isolation --outdir artifacts/v44-commit-package.
Full suite temp dir: artifacts/v44-commit-final-suite. Preview/package/temp files are ignored.

## Earlier V4.4 implementation checkpoint — 25 October 2026

The scheduled start fired at17:29:24 UTC /18:29 Brussels. Its one-time automation
start-v4-4-google-maps-implementation is now PAUSED. Work remains exclusively in
C:/Users/Arne/.codex/worktrees/v4-4-google-maps/EnergyManager, branch
codex/v4.4-google-maps, based on304e386. No commits/push/merge/publication occurred.

IMPLEMENTED: per-calendar routing checkboxes; backwards-compatible legacy subscriptions;
manual destination journeys with venue arrival/departure; independent home/venue/home
traffic-aware routing (at most4 HTTP queries per journey); seven-day routing horizon;
daily/event-change/manual refresh; write-only masked Maps key entry/replace/explicit
clear with blank-preserve behavior; persistent per-event overrides and automatic reset;
async journey API; stale-response rejection; revisions/approval revocation on changed
requirements; unchanged scoped approvals retained only after fresh restart reconciliation;
persistent EV unresolved-route warnings and deduplicated existing-phone notices/retry.
Source parsing retains up to one day of past events so longer routed returns are not
silently dropped at the old four-hour placeholder boundary. No venue chaining.

LIVE ACTIVATION IS EXPLICITLY WITHHELD: journeys.LIVE_ROUTING_AVAILABLE=False. The
standard Routes policies only explicitly grant certain caching exceptions, while
current goals/decision archives retain route-derived inputs indefinitely. A question
about any additional storage rights was sent. Do not assume transient raw HTTP replies
solve derived-input retention, or flip the gate without a compatible design/terms.
Credential/API/billing readiness remains unverified. No real credential was accessed.

CONFIRMED AND IMPLEMENTED FOLLOW-UP: unresolved/pending routes do not block other valid
EV goals. The trip contributes no guessed distance/times; its warning and deduplicated
phone notice remain. A pending request with no published goal preserves unrelated EV
command authority. Changing/removing an existing checked trip still revokes the affected
plan normally, then valid remaining work can replan. Ordinary measurement, connection,
charger and permission guards remain; ESS is independent. The former global route
hold and its UI text were removed.80 focused tests pass1.16s, including a real locally
solved independent EV plan continuing through a route failure and fake actuator stop
on disconnect. Ruff, mypy37 and changed JS syntax pass.

The user questioned whether seven days is permitted caching. Clarification: seven days
is the planning horizon, not the current storage TTL. Route results are held for reuse
between refreshes, and route-derived goals/decision inputs enter the indefinite archive.
Current EEA3.3.2(b) prohibits caching except service-specific permissions; Routes20.2
explicitly permits latitude/longitude30days, not a general seven-day distance/time cache.
No documented allowance for seven-day distance/duration retention was identified. Do not
misstate this as a ruling about every operational derived value, or silently purge archives.
Sources: https://cloud.google.com/terms/maps-platform/eea
https://cloud.google.com/terms/maps-platform/eea/maps-service-terms

LATEST FOLLOW-UP: full Python suite283 passed44.80s after the confirmed continue-other-
goals policy;80 focused cases1.16s, Ruff/mypy37 and changed JS syntax also pass. Main
checkout remains untouched by this chat. No live calls, commit, publication or deployment.

Earlier verification: full Python suite281 passed44.29s, followed by68 focused routing/calendar/
settings/journey cases0.89s after the final restart-approval change.33 frontend cases,
changed JavaScript syntax, Ruff and mypy37 source modules pass. Real aiohttp transport
was exercised against a local fake Google server. Seven-day configured fake-HA/calendar
regression:68.891s,2021intervals,max control3.337ms,four fake service calls. Added
--routing-fixture: two routed89km journeys, six local fake Google HTTP requests,
71.483s,2021intervals,max control4.141ms,four fake HA service calls. Both accepted valid
plans from the real spawned solver. These are synthetic evidence, not installation data.

BROWSER: standalone synthetic fixture on8144 verified missing destination -> edit ->
resolved route, venue timing inputs, per-calendar checkbox and masked password input.
At390px viewport, route card351px and page scroll width equals client width375px.
Screenshot is a labelled synthetic preview with unchanged4.3.5 release metadata:
C:/Users/Arne/.codex/visualizations/2026/10/25/01a1736b-2b27-7952-a275-df6d08645259/v44-synthetic-mobile.jpg
The temporary standalone preview tab/server were closed; the normal viewport was restored.
Native HA-contract preview additionally verified editing a calendar trip, saving a101km
explicit override and Return to automatic restoring the92km synthetic route. Console
had no warnings/errors. Native proof is v44-synthetic-native.jpg beside the mobile proof.
Both preview tabs/servers were closed. Physical installation commissioning is unverified.
The preview used a fake router and a local fixture discovery URL; no live Google,
installation database, hardware or real phone delivery was used for verification.

NEXT: resolve route-data retention/activation, reconcile latest main/other-chat changes
without overwriting them, finish policy/API review, and only then prepare V4.4 release
metadata/package/release approval. Earlier Maps publication hold remains. Preserve
original ignored Maps archive. No new release automation or automatic continuation is
promised; resume from this checkpoint and actual files. Existing interpreter can be
used read-only with PYTHONPATH pointing to this worktree's energymanager/src and unique
pytest --basetemp under this worktree's ignored artifacts/.

## V4.4 preparation — 25 October 2026

AUTHORIZED in the V4.4 implementation chat: create a separate worktree/branch, restore
prepared Maps code there, and begin new implementation after 2 hours 50 minutes.
Worktree: C:/Users/Arne/.codex/worktrees/v4-4-google-maps/EnergyManager
Branch: codex/v4.4-google-maps, based on 304e386d7c2d363bc2fc93630df10ff50a53bb64.
The original checkout is used by another active chat; do not edit/stage/commit there.
A one-time chat automation is scheduled for 25 October 2026 at 18:29:09 Europe/Brussels
(17:29:09 UTC), id start-v4-4-google-maps-implementation. Disable/delete it after its
first invocation. Scheduling requires the computer on and desktop app running.

COPIED WITHOUT MODIFICATION: src/energymanager/routing.py and tests/test_routing.py
from the original checkout's gpt/paused-maps-2026-10-25 archive. SHA256 matches:
routing.py 3E6A381F1FAE82D9D918CEAFEB94EF3E5C12BDDD776E08708221E6AEE95C991F
 test_routing.py E4E26440247F9B9D50424726957B47AE0D05C7B29300D4FF759B729C6ADC0612
The original ignored archive remains intact. No archived documents were restored.
No startup/calendar/UI integration or new application behavior has been written yet.
The user has a Google credential, but its type, enabled API and billing are unverified.
No credential has been requested/read/stored and no live service has been contacted.

CONFIRMED referee policy: HA home to venue to HA home, arrive 60 minutes before event
start, leave venue two elapsed hours after start, ignore calendar event end. Existing
energy-consumption/reserve and permission rules remain; temperature compensation deferred.

CONFIRMED V4.4 choices from the user's answers:
- Route selected calendars and manual journeys that have a destination. Each calendar
  has an enable slider/checkbox alongside its subscription configuration.
- Use predicted traffic.
- Route the next seven days; refresh daily, on event changes and on manual request.
- Missing/failed estimates stay unresolved and create an intervention notification;
  do not substitute the old 50 km/four-hour placeholder for a failed enabled route.
- Preserve per-event local destination/distance/timing overrides across calendar refresh;
  include an explicit return-to-automatic action.
- The user believes the credential is a Maps API key with everything enabled/configured;
  treat service readiness as unverified, without requesting or exposing the secret.

FOLLOW-UP ANSWERS CONFIRMED:
- Every routed trip independently uses HA home to venue to HA home, including multiple
  events on one day. Do not chain venues in V4.4.
- Manual destination-based journeys accept desired venue arrival and venue departure;
  Maps calculates home departure, home return and total round-trip distance.
- Unresolved routes produce a persistent EV warning plus one deduplicated alert per
  unresolved trip to the existing selected HA phone destination. Development uses fakes.
The requested behavior choices are now resolved. Credential/API/billing readiness is
still unverified; no live requests are authorized. Recheck latest chat answers at start.

IMPLEMENTATION must reconcile the maintained architecture/decisions/settings/runbook and
this checkpoint. Read AGENTS.md and the code-writer skill. Keep source archive outside
releases. Prior Maps release hold remains pending explicit clarification; prepare and
verify implementation but do not commit/push/publish Maps merely from older release mandates.
Do not merge main or publish concurrently with another chat. Use fake/local HA, Routes
and actuator endpoints; no live Google/paid API calls, live HA/databases, hardware, real
notifications or deployment without separate explicit authorization.

Research before integrating persistence: Google Routes policies restrict content caching
and distinguish EEA billing terms. Existing app stores goals/decision history indefinitely;
check permitted retention and attribution before persisting route-derived content. Sources:
https://developers.google.com/maps/documentation/routes/policies
https://developers.google.com/maps/documentation/routes/usage-and-billing
Traffic-aware requests use the Pro category. No paid/request-volume promise is made.

VERIFIED now: 28 existing synthetic routing/calendar tests passed in 0.49 seconds.
Tests imported this worktree through PYTHONPATH using the existing interpreter. Initial
attempts failed only on temporary-directory setup; final run used a unique directory
under this worktree's ignored energymanager/artifacts/. No tests/source were altered.
Run: python -m pytest -q -p no:cacheprovider --basetemp <unique-worktree-artifacts-path>
     tests/test_routing.py tests/test_calendars.py

NEXT at scheduled start: reconcile latest chat answers and Git state; verify copied
routing/calendar baseline, then implement independent plumbing and resolved policy choices.
The original environment is energymanager/.venv313/Scripts/python.exe; it is ignored and
not copied. When using that interpreter, set PYTHONPATH to THIS worktree's energymanager/src
so tests import this branch rather than the original editable checkout. Keep preview ports,
fixture databases, dependency installation and release actions separate from other chats.


## Current work —4.3.19 Overview EV power and native sensor history

AUTHORIZED27Oct: show actual EV power in the Overview EV box; make the EV visualization's
sensor data open normal HA entity history. Implemented shared measured-power projection,
mapped history buttons for power/SoC/connection and charger readings/settings, explicit
derived/missing-source descriptions and focus preservation. Discovery exposes whitelisted
EV diagnostic/actuator IDs; phase controls remain separate. Signed EV display follows4.3.18.
LOCAL:334Python54.31s/59Node/Ruff/mypy35 pass. FakeE2E32.449s/2018intervals/max2.482ms/
four fake calls passes. Native/standalone, actual/signed power, mapped more-info events,
keyboard/focus and light/dark390px viewport checks pass.56 package files match wheel/
sdist; isolated4.3.19 import passes. NEXT: final scope review and authorized ready-release
commit/push with exact-head CI/image. Stage only the updated ARCH-014 entry
from the pre-existing deferred tail. Other backlog/paused Maps stay separate. Planning
reconciliation/restart investigation remains read-only; no live installation access.

## Current work —4.3.18 signed EV power and source-specific input errors

AUTHORIZED27Oct: accept negative EV measured power and identify rejected inputs with
their sensor, raw state/unit and read time. Other validation remains. Implemented
signed EV observation/history/net energy support, source-level rejection for other
negative inputs, retained bounded raw states/units and explicit error context.
Derived household errors list contributing readings and preserve settling behavior;
domain-only negative stock errors identify the field/value. No planned EV discharge,
charger fault/delivery-policy or timing changes.131 focused synthetic tests pass,
including unchanged control validity through a signed read, continued charger start,
stored/displayed error context, signed history/energy and a real validated joint solve.
LOCAL:330Python54.58s, then36 focused live-input tests0.70s after the final contributor
label refinement and three topology cases;55Node/Ruff/mypy35 pass. No frontend change.
FakeE2E33.639s/2018intervals/max2.684ms/four fake calls passes;56 package files match
wheel/sdist and isolated4.3.18 import passes. NEXT: final scope review and authorized
commit/push, then exact-head CI/image checks. Preserve unrelated deferred tail and paused
Maps. No live access.

## Current work —4.3.17 include EV incident onset in reports

AUTHORIZED27Oct: implement the reporting change after the provided15minute waiting
incident's export omitted its first ten minutes. Reports now begin five minutes
before recorded onset and end at min(now,detection+10minutes). Missing onset uses
detection and a later onset cannot discard detection context. Preserve read-only
off-loop SQLite access, five-second budget and10,000 chronological event cap; capped
reports explicitly identify the omitted tail. No charging/fault/recovery changes.
LOCAL:308Python53.65s/55Node/Ruff/mypy35 pass, including long waits, exact window
boundaries, legacy timestamps, capped exports and early-event inclusion via HTTP.
FakeE2E33.840s/2018intervals/max4.670ms/four fake calls passes.56 package files match
wheel/sdist; isolated4.3.17 import passes. The frontend is unchanged.
NEXT: final scope review and authorized ready-release commit/push; verify exact-head CI/image.
Preserve unrelated deferred tail and paused Maps; no live installation access.

## Current work —4.3.16 preserve starts across revisions

AUTHORIZED27Oct: user explicitly answered Yes to fixing the reproduced revision/
start-confirmation issue alongside the visual indicator, already released in4.3.15.
Implemented target-value/original-time pending identity, continuation of unchanged
starts across revisions without stop/rewrite/timeout reset, and rollback of pending/
hold metadata when an enabled/generation guard revokes a write before service entry.
Unknown service responses retain evidence for later readback. Actual writes still
check authority; explicit stops/phase changes/stale inputs/faults supersede. No change
to30s restart hold,90s delivery supervision or immediate reported-error policy.
Focused89 Python checks pass, covering the reproduced2s stop, repeated revision
changes, early flow, current-only changes, unconfirmed30s deadlines, real stops,
revoked unsent starts/settings/stops, and accepted-but-response-lost start confirmation.
LOCAL:300Python53.49s/55Node/Ruff/mypy35 pass. FakeE2E33.841s/2017intervals/max5.175ms/
four fake calls passes.56 package files match wheel/sdist; isolated4.3.16 import passes.
NEXT: final scope review and authorized release4.3.16
commit/push with exact-head CI/image evidence. Existing deferred tail and paused Maps
stay separate. No live HA/database/hardware/real notice/deployment access authorized.

## Current work —4.3.15 EV action visibility and rapid-stop investigation

AUTHORIZED27Oct: investigate rapid charging start/stop/error timing and implement
an EV-page visual action indicator, especially artificial30s holds. Reproduced a
specific unchanged-request stop: send force2 under generation1, then two seconds
later issue the same6A/one-phase positive request under generation2 before readback;
GoEControl sends force1. `starting` requires the pending generation to match, while
`resume_after` remains set until start confirmation. This establishes a code path,
not the cause of the user's unprovided incident. The90s low-power watchdog cannot
by itself explain a stop a few seconds after start. Fresh input loss, protective
zero commands and explicit charger errors remain other independent stop paths.
Also confirmed with a local fixture that `car=5`, even with `err=0`, two seconds
into the deliberate hold immediately latches a fault. This is the existing error
policy, not a demonstrated erroneous reading. It can prevent the self-recovery
observed in manual tests; actual incident codes/order are needed before proposing
which, if any, reported errors could be treated as transient.

Permission was initially pending for the charging-logic path; the user subsequently
authorized its fix in4.3.16 above. The4.3.15 visual scope is implemented:
read-only structured activity, action/step strip and real-deadline countdown ring;
separate restart/phase-preparation/delivery clocks, fault/blocked/off priorities,
stale/expired update handling and selection-safe1s updates without rebuilding SVG.
No control branch or duration changed. Native/standalone rendering, light/dark,
327px component at390px viewport and expired-wait behavior verified on local fixtures.
Version4.3.15 released the independently authorized visual scope; the charging fix
follows in4.3.16. Final verification/package evidence goes in VERIFICATION.md and the
existing ignored checkpoint. Preserve unrelated DEFERRED_WORK tail and paused Maps;
no installation access or hardware/real notification/deployment is authorized.

## Current work —4.3.14 immediate recalculation and visual activity

AUTHORIZED27Oct: manual Recalculate replaces a running solve, avoids queues and
provides visual feedback. Implemented own spawned process per solve, off-loop
spawn/terminate/kill/join, latest-request race/coalescing, material-revision replacement
and no routine same-revision busy queue. Manual request identity does not invalidate
accepted control. Retain process-crash recovery and independent validation/permissions.
API202 acknowledges identity/activity; compact native/standalone stage/elapsed bar,
Overview/EV button feedback, restart action, brief green confirmation, visible failures,
reduced motion and selection locks. No invented percentage/ETA.
LOCAL:280Python53.42s/54Node/Ruff/mypy35 pass. Actual HiGHS cancellation in fakeE2E
passes32.830s/2018intervals/max3.287ms/four fake calls. Browser native/standalone,
EV controls, restart/stage/elapsed, dark/light,355px component and read-timeout recovery
verified.56 source/assets/defaults match wheel/sdist; isolated4.3.14 import passes.
NEXT: scoped final review and ready-release commit/push; verify exact-head CI/image.
Preserve unrelated DEFERRED_WORK tail and paused Maps. No live installation operation.

## Current work —4.3.13 EV restart settling

AUTHORIZED27Oct: user confirmed standalone stop→phase→30s→charge worked; apply a30s
hold to automatic restarts after either phase direction and ordinary stop/start,
excluding current-only changes. Remove phase-switch cooldown. Verified previous
default600s (10min);900s persistent-wait escalation is separate and retained.
Implemented nonblocking deadline from confirmed force off/low power or latest phase
acknowledgement; existing elapsed stop time counts. Current reductions no longer stop
first. Protective/input/readback/fault guards and independent ESS dispatch remain.
Remove dwell from controller/model/incumbent/validator and Settings; retain optional
ignored legacy JSON field for compatibility. Preserve approved direct manual HA buttons.
Fix the exposed refinement path that could move unproven above80% charging into an
earlier solar window; retain checked ceilings through the final grid certificate.
LOCAL:272Python54.63s/51Node/Ruff/mypy35 pass; fakeE2E31.465s/2018intervals/max18.086ms/
four fake calls.55 package code/assets/defaults identical; isolated4.3.13 import passes.
Serial7day mixed115.705/winter115.143/permission120.074s pass validation and minimum-grid
certification; permission produces a demonstrated request. Last runtime includes74ms
overhead within the existing0.5s acceptance bound. NEXT: final package/docs/scope review,
ready release commit/push, then exact-head CI/image. Existing unrelated DEFERRED_WORK edits
and paused Maps preserved. No live HA/database/hardware/real notifications/deployment.

## Current work —4.3.11 planner recovery and rejected decision export

AUTHORIZED: fix the supplied frozen no-incumbent failure; inspect seed/budget and
expose failure evidence. Reproduced baseline12.733s failure under120s global budget.
Found seed incorrectly using current-month incurred peak in future-month allowance.
Fixed month boundary; one recovery solve after no-candidate timeout uses remaining budget less2s for validation
with same model/objective/permissions. First replay valid117.234s; final replay valid
117.242s and independent validation passes. Raw private snapshots/replays stay ignored.
Rejected history now lists reason/status/time, detail shows stages/validity, direct
serverJSON download preserves floats/checksum; CLI verifies exported top-level digest.
LOCAL:251 Python43.26s/50 Node/five new seed/recovery/export tests0.39s/Ruff/mypy35/JS
pass. Full replay timings are offline evidence, not installation timing guarantees.
NEXT: finish sequential synthetic benchmarks, fake E2E/browser download verification,
package/final docs and scoped ready-release commit/push. No live HA/db/hardware/phone/
deployment. Preserve unrelated backlog and separately paused Maps.
FINAL LOCAL: mixed115.867/winter115.260/permission115.366s benchmarks allvalid/certified;
fake E2E31.922s/max2.303ms/four fake calls. Native/standalone rejected detail/link and
339px dialog pass, logs clean. Browser download permission declined; no browser completion
claim/retry, prior server-side export/checksum tests pass. Remaining: package/scoped release.
PACKAGE:55 code/assets identical in wheel/sdist; isolated4.3.11 import passes. Temporary
browser tabs/servers closed and viewport reset. Remaining: scoped review/commit/push/CI.

## Current work —4.3.10 wheel correction, Grid peak and EV consolidation

AUTHORIZED: wheel zoom instead of pan; red dashed peak + Grid value/history; remove
EV footer/details, consolidate sidebar and make phase selectable. User explicitly
chose direct one-time charger changes that automatic control may overwrite, with no
EV-control pause or planner constraint. Implemented native HA action using actual
actuator mapping/options, busy/error handling, no auto retry or optimistic readback.
Demo/standalone/unavailable actions disabled. Existing control safeguards unchanged.
LOCAL:246 Python42.93s/50 Node/4native0.31s/Ruff/mypy35/JS pass. Final fake E2E32.451s/
2018intervals/max4.071ms/four fake calls. Browser wheel zoom/drag, synced ranges,
red8/5 line, direct peak entity click/keyboard and preserved Grid chooser pass.
Native synthetic phase2/Auto0, actual projected readback/focus, stale raw sidebar,
removed foldout/note and353px narrow fit pass; logs clean. No real hardware actions.
NEXT: final package comparison, scoped review/commit/push and exact-head CI/image.
PACKAGE:55 code/assets match wheel/sdist; isolated4.3.10 import passes. Browser closed,
viewport reset; release proof retained in ignored artifacts/release-4.3.10-*.jpg.
Preserve unrelated deferred work/paused Maps. No live HA/database/deployment access.

## Current work —4.3.9 wheel/mobile navigation and recorded peak

AUTHORIZED: scheduled one-time wheel navigation, mobile pinch time zoom + two-finger
pan, ARCH-011 monthly capacity peak. Implemented shared Overview range with15min–7day
zoom bounds, frame coalescing and one archive load at gesture end/wheel idle. Now,
cursor, selection and one-finger vertical scroll policy retained. Arrows use current
span. Live monthly input draws a dotted15min-average peak; missing never falls back
to forecast/floor, zero valid. Planning and controller policies unchanged.
LOCAL:245 Python42.95s/47 Node/Ruff/mypy35/JS pass. Synthetic E2E32.623s/2018intervals/
max3.751ms/four fake calls. Real browser wheel, live peak2500/7500/0/unavailable,
keyboard/Now/Planning checks pass. Labelled synthetic pointer replay verifies pinch,
pan and shared ranges in browser; physical phone touch negotiation remains unverified.
Narrow layout327px graph fits; no browser warnings/errors. Wheel/sdist55 code/assets
match; isolated4.3.9 import passes. NEXT: scoped review, commit/push ready release and
inspect exact-head CI/image; pause completed one-time automation. Preserve unrelated
backlog edits/paused Maps. No actual HA/database/hardware/notifications/deployment.

## Current work —4.3.8 horizontal mouse panning

AUTHORIZED: click/drag graphs left/right. Implemented Overview primary-mouse panning
with a horizontal threshold, pointer capture, initial range anchoring, animation-frame
redraw and archive load on release/cancel. Both graphs/period/session bars stay aligned;
six-hour duration persists until Now. Click pins, tooltip text remains selectable,
vertical gestures/touch and Planning keep prior behavior. Disposal cancels pending frames.
LOCAL:40 Node/3 native-asset tests0.27s/Ruff/JS pass; synthetic E2E32.030s/2018intervals/
max4.548ms/four fake calls. Real native power/SoC and standalone drags, vertical rejection,
outside release, text selection, cursor, Now and Planning checks pass; logs clean.
NEXT: package/final scoped review, one ready-release commit/push and exact-head CI/image.
Preserve unrelated backlog/paused Maps; no live HA/database/hardware/phone/deployment.

## Current work —4.3.7 six-hour Overview

User authorized narrowing Overview graphs to about six hours for more horizontal detail.
Implemented two hours past/four ahead, matching power/SoC/session ranges, six-hour arrows
and local-midnight six-hour History day. Planning remains seven days.36 Node/3 asset
tests/Ruff/JS pass; synthetic E2E32.319s/max3.134ms/2,018intervals/four fake calls passes.
Browser navigation/history/cursor/Now/DST and matching plot/session edges pass; logs clean.
NEXT: package/final scoped review, release commit/push and existing CI/image workflows.
Preserve unrelated backlog/paused Maps. No live HA/database/hardware/notifications/deploy.

## Current work —4.3.6 combined EV visualization

AUTHORIZED: implement the approved annotated drawing + diagnostic sidebar with red
errors, neutral white/theme text and green OK states. History clicks remain deferred.
IMPLEMENTED: data labels around the drawing, overall reason above, individually colored
connection/permission/car/charger/error readbacks beside it. Settings/waits/stops are
neutral; stale states unverified; current charger health stays separate from an old
incident. Raw details, phase transition, refresh/selection preservation and demo isolation
remain. No control behavior/mapping changes. Versioned assets require only an HA reload.
VERIFIED:245 Python50.74s;36 Node/Ruff/mypy35/JS/CLI; fake E2E35.446s/2018intervals,
max2.850ms/four fake-only calls. Native light/dark/colors/error/stop/stale/phase checks,
detail/focus preservation and390px fit pass; standalone320px fits. Browser logs clean.
PACKAGE: wheel/sdist55 code/assets match source; isolated extracted-wheel4.3.6 import passes.
NEXT: scoped review, one ready-release commit/push and existing
CI/image workflows. Preserve unrelated backlog edits/paused Maps. No live HA/database/
hardware/real notifications/deployment. Remote results go in ignored checkpoint/final.

## Current work —4.3.5 EV status visualization

AUTHORIZED: implement an EV-tab visualization of status, powers, phases and battery.
IMPLEMENTED: responsive charger/cable/car SVG, battery fill, actual W versus current
command intent W, validated current limit and phase-selector mode, transition request,
connection, waiting/fault/recovery priority and expandable raw readings/frame times.
Native EV source updates replace only status; selection guards remain in force and
detail expansion/focus survive refresh. Demo ignores installation device readings.
LOCAL:245 Python42.97s/33 frontend/Ruff/mypy35/all JS/CLI4.3.5 pass. Full fake E2E
32.818s/2,018intervals/max tick4.138ms/four fake-only calls passes. Native browser
charging, phase transition, timestamped fault and stale states pass; phone390px status
card355px fits without overflow. Native focus/expansion persist through repeated polls;
standalone EV and clean browser logs pass. Wheel/sdist55 code/assets match and isolated
4.3.5 import passes. Local fixtures/tabs closed; no live access or operation.
NEXT: final scoped review and one release commit/push;
check exact-head CI/image. Preserve unrelated backlog and paused Maps archive. No live access.

## Current work —4.3.4 request recovery and selectable dashboard text

AUTHORIZED: fix repeated generic browser timeouts and unselectable text. Native HA
root disables selection; our live DOM replacements also destroy it.15s native request
limit emitted raw exceptions and recovery never cleared the native error paragraph.
IMPLEMENTED: context-rich request errors, retry backoff/recovery banner and Copy error
with manual-selection fallback; compact polling projects display fields, reuses an
unchanged plan and limits recent samples to120 (older data stays in archive graphs).
Selection and held pointers pause automatic DOM replacement; source chooser ignores
selection gestures. Same versioned fix works with existing installed HA loader.
LOCAL VERIFIED:245 Python43.13s + final4 asset/API0.33s;28 Node/Ruff/mypy35/JS/CLI
pass. Fake E2E32.403s,2,018intervals,max tick2.466ms,four fake-only calls. Synthetic
repeated payload2,523,327→50,534B (-98.0%). Native HA-style parent selection/drag,
real15s timeout, exact clipboard copy, denied-clipboard fallback and recovery verified;
standalone selection and native Overview/Planning/EV/live57% update pass.
Native390px copy-warning355px fits without overflow; fresh startup logs clean.
Browser fixtures/tabs closed (initial failed temporary tab closes with the turn).
PACKAGED: wheel/sdist54 code/assets match; isolated4.3.4 import passes. Maps code and
unrelated backlog edits excluded. Final scoped diff review passes.
NEXT: single release commit/push and exact-head CI/image checks. Preserve unrelated backlog and Maps archive. No live access.

## Current work —4.3.3 stable graphs, fixed daily baseline and power-balance settling

AUTHORIZED: fix rolling graph flashes, slow/empty energy estimates and brief negative
household residual errors. User chose a fixed midnight estimate with capture tooltip.
IMPLEMENTED: overlap retention/error backoff; independently persisted midnight/labelled
first-available daily baseline; fast state projection, asynchronous/coalesced/bounded
archive totals and dated retention. Derived mismatch pauses commands immediately,
retains plan revisions for the input watchdog window, records raw states/recovery and
escalates persistent failure. No fabricated household samples or load-learning input.
FINAL LOCAL:244 Python44.33s/24 Node/Ruff/mypy35/all JS/CLI4.3.3 pass. Fake E2E
32.344s,2,018intervals,max tick4.319ms,four fake-only calls and42,480archived fixture
records. Native/standalone capture/as-of/HA update and390px fit checks pass; loaded
archive remains before/after minute rollover. Browser logs clean, fixtures closed.
PACKAGED: wheel/sdist built;52 code/assets match source, isolated4.3.3 import passes.
Paused Maps code and unrelated backlog edits excluded. Final focused diff review passes.
NEXT: single release commit/push and remote CI/image checks. Preserve unrelated ARCH-011/012 backlog edits and ignored
paused Maps archive. No live installation access.

## Current work - 4.3.2 go-e charging supervision

AUTHORIZED: implement the reviewed go-e fixes. User confirmed numeric car/status/error
and device heartbeat readings may gate EV while ESS continues. Actual integration
uptime rounds to hours; use its existing last Status change age in seconds instead.
Preserve the pre-existing ARCH-011/012 backlog edits and parked Maps archive.
LOCAL COMPLETE: numeric status and advancing seconds heartbeat, staged current/force/
phase confirmation, bounded phase and waiting states, error-aware reboot gate, actual
current-limit intersection/replan, stop verification after hardware-off and visible EV
status. Full suite236 passed42.91s; final56 go-e/incident checks after the storage-stop
safeguard passed0.57s.22 frontend/Ruff/mypy34/JS/CLI4.3.2 pass. Fake E2E35.467s,2,018
intervals,max tick4.937ms,four fake-only calls. Native/standalone/phone fields, save/
backup/restart and EV-only warning verified; clean final browser logs. Fixtures closed.
PACKAGED: wheel/sdist built,51 code/assets match and isolated4.3.2 import passes.
NEXT: one focused4.3.2 commit/push and CI/image checks.
Exclude pre-existing ARCH-011/012 backlog edits; preserve Maps ZIP/code/tests ignored.
Remote results only ignored checkpoint/final; no optional release-verification commit.

## Current work —4.3.1 EV delivery fault incidents and recovery

AUTHORIZED25October: implement timestamps, diagnostic history from T−5minutes, one
configured go-e reboot attempt with verification and phone escalation on failure.
User supplied a reboot button as installation context; no ID is hardcoded. No live
HA/database/hardware or real notifications. Use existing code-writer skill. Maps work
is explicitly on hold and preserved locally, outside the active package, in
`gpt/paused-maps-2026-10-25/maps-preparation.zip` (seven original files SHA256 verified),
plus unpacked routing.py/tests and tracked-doc patch. Restore only deliberately later.
LOCAL COMPLETE: persisted EVFaults state machine, optional reboot/diagnostic pickers,
separate five-second raw-state sampling, incident worker export and global incident
banner/history/download/acknowledgement. No routing code in active src/tests.
198 Python tests51.29s,22 frontend tests, Ruff/mypy33/all JS/CLI4.3.1 pass. Synthetic
native/standalone/phone browser report/history/download/ack/settings checks pass with
clean final logs; no horizontal dialog overflow. Configured fake E2E30.300s/2,018
intervals/max tick2.656ms/five fake-only service calls passes. Fixtures/tabs closed.
Wheel/sdist built;50 packaged code/assets match and isolated4.3.1 import passes.
Paused Maps code/archive excluded from both distributions. No live installation use.
NEXT: final focused review then single4.3.1 release commit/push and remote CI/image
checks. Remote outcomes only ignored checkpoint/final; no extra release docs commit.

## Current work —4.3.0 ARCH-003 subscribed EV calendars

AUTHORIZED: first implement/release multiple labelled iCalendar subscriptions, managed
50km-total journeys departing at event start/returning four hours later (confirmed).
Then prepare Google Maps distance/time calculation; second version MUST NOT RELEASE.
No live HA/database/hardware/deployment/paid routing calls. User example feed read-only
parser check passed:five upcoming timed events with locations; personal data not saved.
IMPLEMENTED: Settings links/save/restart, independent bounded/public-HTTPS fetch/parser,
recurrence/exceptions/cancellation,90day cache, deduplication, source-managed trip goals,
revision/approval invalidation and EV source/location/provisional/sync-status UI.
FINAL LOCAL:181 Python42.04s plus40 targeted configuration/calendar checks after the
invalid-config guard;21 frontend/Ruff/mypy32/all JS/CLI4.3.0 pass. Native/standalone/
390px browser and settings add/remove/label/save/backup/restart notice pass; clean final
browser logs.49 final packaged code/assets match and isolated4.3.0 wheel import passes.
Full-horizon fixture with45%SoC hit reference-solver time limit at15/60second budgets;
no invalid plan accepted and control remained responsive. Untouched90%SoC E2E passes:
65.617s/2,022 intervals, two unique imported journeys, five fake-only calls, max tick
2.761ms. Fixtures/tabs closed. No live deployment.
NEXT: single4.3.0 commit/push and remoteCI/image. Only then start unreleased Maps preparation.

## Current work — 4.2.3 compact dashboard and graph inspection

AUTHORIZED: simplify energy/connection labels with symbols; append expected end-of-today
energy after each recorded subtotal (explicit user answer); add numeric graph cursors;
remove provenance/history-detail clutter and duplicate native battery-history card;
combine plan-update/time bar, enlarge power plot and align power/SoC/session time axes.
Standing ready-release commit/push/publication permission applies. No live HA/hardware.
IMPLEMENTED: end-of-day projection clipped to local midnight with revision/forecast/
coverage guards; compact icon rows and partial-coverage tooltips; keyboard/pointer/touch
cursor follows displayed lines without bridging gaps; shared plot insets and360px power
height; simplified header and hidden normal history status, failures remain visible.
Native source/history choices remain available. Planner/controller authority unchanged.
LOCAL COMPLETE:170 Python43.45s/20 Node tests, Ruff/mypy31/JS syntax/CLI4.2.3 pass.
Native/standalone synthetic browser checks pass, including compact rows across midnight,
numeric cursors/gaps/window edges, source chooser and390px geometry. Graph/session
endpoints within0.02px desktop/exact phone;360px power plot. No browser warnings/errors.
Configured fake E2E26.912s/2,018 intervals/max tick2.866ms/five fake-only calls passes.
Wheel/sdist built;48 packaged code/assets match, isolated4.2.3 import passes. Relevant
architecture/decisions/runbook/guide/changelog/verification updated. No live deployment.
NEXT: final scoped diff review, one release commit/push and inspect CI/image publication.
Remote outcomes belong only in ignored checkpoint/final; no extra verification commit.

## Current work — 4.2.2 graph-history release

The user authorized committing and pushing the completed ARCH-010 implementation,
lifting the earlier hold. Release 4.2.2 includes the reviewed archive queries, bounded
plot data, gap preservation, History day/12-hour/Now navigation and recorded capacities.
No new feature or controller policy change is introduced during release preparation.
Prior local verification: 165 Python tests, 18 Node tests, Ruff/mypy31/JS syntax,
configured fake E2E, synthetic archive load check and native/standalone/390px browser
checks. Actual HA installation remains unverified. See VERIFICATION.md for evidence.
FINAL LOCAL CHECKS: 165 Python tests42.64s,18 frontend tests, Ruff/mypy31/all JS syntax
and CLI4.2.2 passed. Configured fake E2E27.108s/2,018 intervals/max tick3.180ms,
47,942 synthetic archived samples and five fake-only calls passed.
FINAL PACKAGE: wheel/sdist built; all47 packaged code/assets match source and isolated
4.2.2 wheel import passed. NEXT: commit/push the single release and inspect CI/image.
Record remote results only in the ignored checkpoint/final reply; no extra docs commit.

## Previous checkpoint — 4.2.1 live boxes and history follow-up

AUTHORIZED: remove the top sensor strip, add daily energy to live boxes, retain sensor
choosers, release/push4.2.1. Then implement ARCH-010 graph history without committing it.
IMPLEMENTED4.2.1: no duplicate sensor strip; existing boxes show installation-local daily
energy estimated from recorded power, separate opposing flows, partial/missing coverage.
Timestamp index includes legacy events; worker uses a read-only connection. Native
history choices include EV/ESS power. Controller and live installation remain untouched.
VERIFIED:161 Python tests40.58s;14 Node tests; Ruff/mypy30/all JS syntax passed. Configured
fake E2E27.722s/2,018 intervals/max tick3.285ms/five fake-only calls. Wheel/sdist and45
packaged source/assets checked; isolated wheel import passed. Browser preview confirms
strip removal, five energy boxes, underlying chooser and native more-info event; no
warnings/errors. HA built-ins/Supervisor are simulated; actual HA remains unverified.
COMPLETED: 4.2.1 was committed/pushed and its workflows passed. The later user
authorization to release the graph-history fix as 4.2.2 supersedes the original hold.

## Current work — native managed HA dashboard, 24 October 2026

AUTHORIZED: replace the iframe dashboard with real HA views/cards and automatic future
UI updates. Use code-writer skill. Existing ARCH-010 graph-history backlog edit must
remain. Plan/controller/installation permissions unchanged; no live HA/deployment.
Chosen design: one-time stable resource loader uses HA's existing supervisor/api WS
bridge to discover the add-on and create/renew ingress sessions. A dashboard strategy
loads versioned layout/card modules from the installed add-on. Native HA tiles receive
state changes and open more-info/history; custom planning/EV/settings components retain
existing features and scoped backend actions. No separate custom integration needed.
Version targeted4.2.0. Initial installation needs one loader resource and strategy config;
later add-on updates need only a dashboard/browser reload. Preserve admin ingress boundary.
IMPLEMENTED: versioned manifest/asset routes, stable Supervisor-authenticated loader,
generated native views/tiles/history and scoped shared planning/EV/settings components.
HA state changes update live summaries directly; more-info opens native sensor history,
with source selection for aggregate values. Lifecycle disposal and release mismatch
handling are explicit. Standalone UI and one-time setup/download remain available.

VERIFIED so far:156 Python tests39.60s,13 Node tests, Ruff/mypy29/all JS syntax passed.
Configured fake E2E27.041s/2,018 intervals/max tick2.616ms/five fake-only calls. Labelled
HA-contract browser harness verified native views,45→57% frontend updates independent
of backend45%, more-info event, journey picker/create/remove, Settings save/backup/
restart message, navigation and390px layout. Built-in HA cards/Supervisor are simulated;
no actual HA frontend/Companion installation claimed. Screenshots native-v420-*.png.
LOCAL COMPLETE: wheel/sdist built, all44 packaged code/assets match source and isolated
extracted-wheel import/manifest smoke passed with control disabled. Browser warnings/
errors absent, native and standalone navigation/forms verified. The8102/8103 fixtures
are stopped, temporary tabs are closed and viewport reset; existing8100 untouched.
Source/asset syntax and diff checks passed. No live HA/hardware/deployment.
NEXT: one4.2.0 release commit/push under standing authorization, then inspect CI/image;
record remote results only in ignored checkpoint/final reply. Target HA installation
needs the documented one-time loader/strategy setup and remains live-unverified.

## Current work — ARCH-009, 24 October 2026

User explicitly authorized implementing ARCH-009 and writing code. Implemented a
dedicated EV calendar/selected-day agenda, goal actions through existing forms, current
requirements before a plan, revision-safe charging/outcomes and installation-local DST
boundaries. Added read-only schedule_goals state projection; scheduling/control unchanged.
Version prepared as 4.1.0. Preserved pre-existing staged/unstaged documentation changes.
The user subsequently authorized committing/pushing release-ready versions and the
existing release workflow. Live installation deployment remains separately authorized.

LOCAL COMPLETE: 153 Python tests passed39.36s; nine frontend tests and all packaged JS
syntax checks passed; Ruff/mypy28 passed. Final configured synthetic E2E passed27.672s/
2,018 intervals/max tick2.791ms/five local fake-only service calls. Wheel/sdist built;
all38 packaged source/assets match, isolated extracted-wheel import/state projection
passed with control disabled. See ev-schedule-package-verification.json.

Browser confirmed direct EV reload/navigation, day agenda, accepted charging details,
morning targets, journey create/edit/overnight return, unknown-return span, manual goal
create/remove and daily Settings link. Requirements persist while outdated/unvalidated
outcomes are withheld. Desktop and390x844 screenshots saved; no console warnings/errors.
Mobile calendar scrolls within its card and selected-day agenda stays single-column.
The8102 synthetic preview and its test tab are stopped; viewport reset; existing8100
preview untouched. No live HA/database/hardware/real notification/deployment access.
Final diff whitespace check passed. Release-ready implementation and current architecture/
instructions reviewed. Next concrete action: one4.1.0 release commit/push, then check CI
and image publication. Record remote outcomes only in the ignored checkpoint/final reply.

COMPLETE: the user explicitly authorized replacing the old main project with the new
implementation and naming it version4. Main app now energymanager/, package/module/CLI
energymanager, version4.0.0. Candidate directory removed. Existing add-on slug/image
energy_manager / ghcr.io/nxt-1/energymanager and ingress8099 retained. V4 JSON and SQLite
are independent of old settings/data; manual/demo startup, hardware control disabled.

Updated main and root packaging/developer config, root dependencies, CI/publish checks,
translations, V4 dashboard wrapper, changelog, specification and migration/rollback docs.
Legacy application/tests/tools/dashboard, original working-file ZIP and staged patch
preserved under ignored gpt/architecture/v4-promotion-2026-10-23/. Historical V3 evidence,
InfluxDB app and its workflow unchanged. No live installation/database/hardware/
notification/controller action. The user explicitly authorized committing and pushing
this V4 update on 23 October 2026; the release proceeds through the existing main-branch
CI/image workflow. Git refs and workflow runs record the publication outcome. Earlier standalone reports
and screenshots are labelled in docs/history/standalone-candidate/.

TESTED after promotion:43 passed29.64s from root; Ruff/mypy19 modules/JS passed. CLI4.0.0.
Configured loopback fake E2E accepted full-horizon trajectory25.724s, max control5.70ms,
22 fake-only calls; API/archive verified. Wheel/sdist built; isolated installed V4 wheel
real solver smoke Optimal/valid0.00915s.23 source/assets matched. Twelve core modules
match prior candidate after namespace normalization; numerical/control behavior unchanged.
Prior full168h benchmarks retained and explicitly not rerun for the name/layout change.
Browser V4 Overview/Planning, branding, charts, synthetic goal create/reload/remove and
no console errors verified. Screenshots saved under docs/screenshots/.

RUNNING: synthetic dry-run preview http://127.0.0.1:8100/#planning, PID90904/exec22414,
data runtime/release-overview-20261023.sqlite. Local Python .venv313/Scripts/python.exe
3.13.17 moved/repaired and new main package editable installed; exact dependency locks.
Root commands use energymanager/.venv313/Scripts/python.exe or a new root .venv.

LIVE-UNVERIFIED: Docker/Supervisor, target-host wheels/ingress and physical commissioning.
Current evidence/limits: VERIFICATION.md, package-verification.json, offline-e2e.json,
v4-promotion-browser.json. Next concrete action after the authorized push: inspect CI
and image-publishing results, then verify Supervisor startup/ingress with control disabled
and review the migration runbook before physical commissioning. No live deployment is
authorized by the commit/push request. Verify actual workspace/checkpoint if resumed later.

## CI follow-up — 23 October 2026

Initial V4 main commit1d420848cdbb57e50169b552c178947343a5d494 was pushed. Image
workflow39935019989 succeeded, including container publication. CI39935019991 failed
only the real-solver disconnect test's elapsed-sleep assertion (423ms vs200ms);
42 other tests passed. The same test passed in the image workflow on the same SHA.

IMPLEMENTED: test now signals actual protective-command delivery and requires it before
the real solve completes, then checks EV invalidation, unaffected ESS and stale-result
rejection. Removed host-dependent subsecond wall-clock assertions. No runtime code changed.
TESTED: full43 tests passed28.29s with two-CPU affinity; four additional focused runs
passed5.31–5.40s each on two CPUs; Ruff and mypy passed. Four local
diagnostic runs measured protective dispatch1.13–2.39ms vs old sleep measurement83–166ms.
These fixtures are synthetic; failing-runner dispatch latency is unknown.
REMOTE-VERIFIED: fix committed/pushed as9fa914a97c2e7c34c877e636c3e50f85f0bc56e8.
CI39936237809 passed all steps:43 tests33.93s, lint/types/CLI/JS, configured E2E,
Python package and Linux container builds. Synthetic E2E:2,018 intervals accepted25.806s,
max control6.85ms,21 fake-only calls. Evidence: ci-verification.json and VERIFICATION.md.
The published4.0.0 image contains the same runtime code; this fix changes tests/docs only.
Next concrete action: review RUNBOOK.md for Supervisor/ingress installation and physical
commissioning, which remain live-unverified and require separate user authorization.

## Automatic starter configuration — 23 October 2026

IMPLEMENTED for4.0.1: missing configuration initialized from a bundled package resource
on every add-on startup, including demo mode, and standalone --config. Existing files
are preserved, even empty/invalid user edits; exclusive creation handles competing
startups. New files retain synthetic labels and disabled remote/control/commissioning
flags. Startup logs the created path; write errors are explicit. App config mount is
writable. Updated release identity, user instructions and configuration-folder mapping.

TESTED:52 tests passed28.29s (nine new startup/filesystem/HTTP/error tests); Ruff and
mypy passed.4.0.1 wheel/sdist built; isolated installed-wheel creation/preservation
passed and all24 package source/assets match. Template included in wheel and sdist.
Evidence: configuration-bootstrap-verification.json. No scheduler/control policy changes.
Configured fake E2E also passed:2,018 intervals accepted20.096s, max control5.27ms,
20 fake-only calls. Current evidence: offline-e2e.json and VERIFICATION.md.
REMOTE-VERIFIED: implementation committed/pushed as32ea875364836b1512efb23fadadf84383dc19ca.
CI39938880228 passed52 tests34.71s, lint/types/CLI/JS, configured fake E2E, package and
Linux container builds. Synthetic E2E:2,018 intervals accepted26.999s, max control14.24ms,
21 fake-only calls. Image workflow39938880153 passed and published4.0.1.
Next concrete action for the user: update the HA app to4.0.1 and start it; inspect its
log for the created configuration path, edit the file and restart when ready. No live
deployment or controller action was performed; Supervisor/ingress/physical commissioning
remain unverified. Hardware control remains disabled in every generated starter.

## Visual configuration editor — complete, 23 October 2026

User request: edit the persistent JSON through HA-style forms and entity autocomplete.
Implementing a Settings page alongside Overview/Planning. Entity discovery uses read-only
HA states via the server-side Supervisor token in the app, or saved standalone connection.
No live installation is accessed during development. Entity IDs, friendly names, states,
units and compatible domains are provided; credentials are never sent to the browser.
Configuration edits are validated, backed up and atomically replaced with revision
conflict protection. Saving applies after explicit restart; no hot controller changes.

IMPLEMENTED for4.0.2: complete Settings form, entity combobox with keyboard selection,
friendly names/state/units and domain/unit filtering, Supervisor connection preset,
validated/atomic/revision-checked saves and backups, HTTP routes and startup wiring.
User-edited JSON remains the persisted source; unknown fields are preserved. Existing
Overview/Planning remain functional. Changes apply in configured mode after restart.

TESTED after normal allowance reset and checkpoint/workspace reconciliation:76 tests
passed28.69s (24 settings tests), Ruff/mypy20 modules/JS checks passed. Local configured
fake E2E accepted2,018 intervals19.933s, max control5.04ms,20 fake-only calls. Browser
verified entity search, keyboard choice, compatible actuator suggestion, invalid-value
feedback, save/backup/reload, navigation persistence and a390px mobile layout. Desktop
console errors absent. Entity traffic used only loopback Supervisor fixtures and GET.
Final4.0.2 package built and isolated editor save/backup/reload passed with26 matching
source/asset files, including the configured-mode guidance. Evidence is in
settings-package-verification.json and settings-ui-verification.json. Screenshots in
docs/screenshots/. No production installation or credentials were used.

REMOTE-VERIFIED: committed/pushed as bdacbee29b730aed86d939159817331fe525c005.
CI39962540057 passed all76 tests in35.68s, lint/types/CLI/JS, configured fake E2E,
package and Linux container builds. Remote synthetic E2E:2,018 intervals accepted27.227s,
max control8.85ms,21 fake-only calls. Image workflow39962539923 passed and published4.0.2.
Verification is recorded in VERIFICATION.md and settings-package-verification.json.
Browser verification tabs and the8102 synthetic fixture were stopped; the existing8100
preview was preserved. No live HA/database/hardware access or controller enablement.

No application work remains for this request. Next concrete action for the user: update
the HA app to4.0.2, reopen its interface and choose Settings. Select entities and save;
restart in configured mode when installation inputs are ready. Verify actual ingress,
entity mappings and physical commissioning separately before hardware control.

## Installation measurement compatibility — in progress, 23 October 2026
User reports P1 current-quarter demand in kW, no separate background-house sensor, no physical phase count sensor. User identified Nxt-1/esphome-p1reader-BE, separate sensor.p1_dongle_momentary_active_import/export, and go-e APIv2 Connect 2026.10.3. Reader source at 0c0e9f07056e1907be9d92dcd06cbd4fa416f95d passes OBIS 1-0:1.4.0 unchanged. go-e API docs expose pnp; integration disables that diagnostic by default and exposes psm selector (0/1/2). Implementing explicit source choices, separate-grid house reconstruction, quarter average normalization, and selector readback with guarded phase switching. Existing files retain legacy interpretation until user selects alternatives. Awaiting user confirmation of quarter demand reset/denominator; both supported, no live access. Next: finish settings and runtime regressions, browser verification, package/release checks. Initial focused legacy tests passed 35; type annotations need correction; changes are not yet complete or published.


LOCAL COMPLETE for4.0.3: explicit sensor interpretations, P1 separate-grid house reconstruction, fixed-quarter demand conversion, go-e selector readback and conditional Settings fields. User confirmed demand resets near zero then builds; fixed0.25h is correct for their signal. EV/ESS independent control preserved; unknown phase pauses EV; phase change waits for mode readback. Corrected SoC freshness for slight asynchronous read skew.84 tests passed28.57s; Ruff/mypy21 modules/JS passed. New-input seven-day E2E accepted2,018 intervals21.556s, max control5.495ms,20 fake calls, known EV SoC required. Wheel/sdist built and27 source/installed files matched, isolated config save/backup/reload passed. Browser choices, P1 autocomplete/kW demand, conditional fields and save/reload verified; desktop errors absent. Evidence: measurement-source-verification.json, offline-e2e.json, VERIFICATION.md and screenshot. No live access or commissioning. Next: final diff/release checks, commit/push and inspect CI/publication, then record outcome. Synthetic8102 preview will be stopped at completion.

REMOTE COMPLETE:4.0.3 committed/pushed as7d64dd39d9cff2d1507a1ecb0db96c0ce362520b.
CI39971619636 passed84 tests30.51s, lint/types/CLI/JS, configured new-source E2E,
Python packages and Linux container. Remote synthetic seven-day E2E accepted2,018
intervals23.380s, max control12.712ms,19 fake calls. Image workflow39971619511 passed
and published ghcr.io/nxt-1/energymanager:4.0.3. Updated VERIFICATION.md and
measurement-source-verification.json with run links/digest. Synthetic browser tab and
8102 service stopped; pre-existing8100 preview preserved. No live HA/hardware access.
No implementation work remains. Next concrete action: user updates HA app to4.0.3,
selects separate-grid source, P1 current-quarter demand and go-e selector source,
maps the three supplied P1 entity IDs plus existing phase selector, saves and restarts.
Physical commissioning remains separate: check AC signs/topology, meter clock/reset,
HA ingress and hardware timing before enabling control. On resumption reconcile the
actual workspace and current checkpoint before continuing new work.

## Settings simplification — local verification complete, 23 October 2026

User explicitly rejected source/type choices and nonexistent house/phase sensors.
IMPLEMENTED for4.0.4: configured runtime always uses separate P1 powers, fixed0.25h
demand conversion and existing go-e selector readback. Settings and new starters omit
all three source selectors and the two unused sensor mappings. Known P1 IDs fill only
missing/generated placeholders; custom mappings remain. Old source choices cannot
reappear or alter runtime. Reading/startup leave files unchanged; explicit save backs
up originals and removes retired choices, preserving unknown future fields and flags.
Daily readiness/consumption/reserve settings moved into EV and charger.
TESTED:85 tests30.22s, Ruff/mypy21 modules/JS passed. Seven-day new-input E2E accepted
2,018 intervals21.799s, max control4.812ms,20 fake calls. Browser used a legacy source
configuration: unwanted fields absent initially and after reload; P1 IDs filled; one
phase selector saved; daily target61 remained in EV group; backup/control-disabled
verified on disk; desktop console errors absent. Screenshots: simple-settings-*.png.
No live HA, controller or hardware access. Existing8100 preview preserved.
NEXT: build and isolated package check, final review, commit/push, CI/image verification.
Synthetic8102 preview must be stopped at completion. Shipping authority remains
SPECIFICATION.md/RUNBOOK.md and the original handoff/decisions/deferred work in gpt/.

Package verification passed:4.0.4 wheel/sdist,27 matching source/installed files, isolated legacy startup/read/save/backup checks. Existing8100 preview untouched; synthetic8102 service and verification tab stopped. Next: publish verified changes and inspect CI/image results.

REMOTE COMPLETE:4.0.4 pushed asb6297bc29e60337e78ea4bdf00bc68d5dfd8f094.
CI39979435914 passed85 tests35.31s, lint/types/JS/CLI, configured seven-day E2E,
Python packages and Linux container. Remote E2E accepted2,018 intervals28.934s,
max tick11.632ms,22 fake-only calls. Image39979436032 published4.0.4. Evidence in
simple-settings-verification.json and VERIFICATION.md. No live HA/hardware access.
No implementation work remains. User's next action: update HA app and refresh its
page; the known P1 mappings are prefilled, phase information uses the one existing
charger selector, and readiness appears in EV and charger. Save and restart when ready.
Commissioning of actual values, AC topology/signs, clocks and hardware remains separate.


## Forecast restoration — implementation milestone, 23 October 2026

User requests original weather source, installation PV planes and applicable correction
factors; connection-address redesign deferred. Found complete legacy modules/tests in
gpt/architecture/v4-promotion-2026-10-23/legacy-application and legacy-tests. Restored
Open-Meteo knmi_seamless, HA zone.home, all four exact PV planes, calibration
2026-10-03-seed and 35-day household median predictor. UTC weather timestamps preserve
DST hours; nine calendar weather days cover rolling168h with refresh buffer. Weather
fetch is an independent async task; measured background samples persist in V4 SQLite.
Configured runtime ignores obsolete forecast_url. Hardware authority unchanged.
TESTED so far:42 existing/recovered focused tests and13 new runtime/DST/failure tests
passed; Ruff passed and mypy25 modules passed. Full suite running.
NEXT: configured fake-weather seven-day E2E, browser, package, release review and CI.
No live weather coordinates, HA, hardware or installation databases accessed.


4.0.5 LOCAL COMPLETE: original Open-Meteo knmi_seamless + four exact PV planes and
2026-10-03-seed corrections restored; household median learning/persistent5min samples.
112 tests38.59s, Ruff/mypy25/JS passed. Exact legacy parity:2,520 correction factors,
648 PV points,676 load points. Public-reference four-plane weather HTTP check passed;
no installation coordinates used. New pipeline seven-day E2E29.408s/2,018 intervals/
max tick4.617ms/26 fake calls passed. Browser pages/source/learning labels/no fake
journey/console passed. Wheel/sdist and31 installed/source files match; isolated
configured startup passed. Synthetic8102 service/tab stopped;8100 untouched.
NEXT: final diff review, commit/push4.0.5 and inspect CI/image publication. Source/run
instructions and evidence ship in docs/FORECASTING.md, RUNBOOK.md, SPECIFICATION.md,
VERIFICATION.md and forecast-restoration-verification.json. Addresses deferred.
Live HA/topology/control commissioning remains unverified; no live operation occurred.

Resume audit: workspace matches checkpoint. Final malformed non-object weather guard added;15 focused forecast tests5.40s and Ruff/mypy25 passed. Rebuilt wheel31 source/assets match; installed guard verified. Full local suite previously112 tests; current collection113. Final review complete; next commit/push and CI/image verification. No new live access.


4.0.5 REMOTE COMPLETE: code32855877ea4177351d4c49dfce256baec01dc2d4 passed
CI39997508230 (113 tests40.92s; types/lint/CLI/JS, restored-source configured seven-day
E2E31.174s, max tick8.674ms/25 fake calls, package and Linux container).
Image39997508225 passed113 tests37.69s and published4.0.5; digest recorded in
forecast-restoration-verification.json and VERIFICATION.md. Original source/PV values
and corrections all found and preserved; addresses deferred. No live HA/DB/hardware
access or deployment. No application work remains for this forecasting request.
NEXT: commit/push the remote evidence and inspect that documentation commit's CI,
then finish. User's next action is update the HA app to4.0.5; forecast URL is unused,
location comes from HA zone.home. Existing connection/commissioning setup unchanged.


## 4.0.6 settings/control update — implementation in progress

User requests automatic HA connections, no connection/commissioning fields, a phone
notification destination picker, immediate Overview hardware switch (explicitly confirmed),
missing-setting highlights and shorter entity subtitles. Skill code-writer applies.
IMPLEMENTED so far: shared Supervisor connection resolution for runtime/discovery;
HA notify entity/action adapter replacing webhook; removed UI connection/commission
fields; required/placeholder field issues, phone destination discovery; live switch API
and stop/revoke sequencing with persisted SQLite switch authority. Legacy commission
flags cannot enable the new switch. New switch starts off until explicitly enabled,
then resumes after restart only once current settings/measurements are valid.
UI implementation underway: one Overview switch, missing-field styling, picker clear
actions and no extra entity-help text; unverified live cards display dashes.
NEXT: adapt/add meaningful tests and full fake-HA E2E, verify UI, fix integration
issues, bump4.0.6 and package/release. Existing billing-boundary timestamp problem
still needs live diagnostics; no stale-data guard has been bypassed.
No live HA/database/hardware/phone notifications accessed. Initial workspace clean.


4.0.6 milestone: implementation integrated;131 tests45.45s/Ruff/mypy27/JS passed
before three additional switch-failure regressions. Local fake Supervisor E2E passed
2,018 intervals30.006s/max tick2.571ms; automatic URL/token, zero startup writes,
immediate switch ON/OFF stop/clear and fake phone delivery verified. Browser first
pass: switch acts immediately; missing entity and empty numeric field highlighted
before Save; phone autocomplete/save/backup succeeded; connection/commissioning
controls and entity explanations absent. Service still8102 for verification;8100
untouched. Metadata bumped4.0.6 after that first run; final4.0.6 E2E/browser still
needed. NEXT: final UI pass/source review, remaining tests, docs, packaging/release.
No live HA/DB/hardware or real notification access. Existing timestamp guard intact.


4.0.6 LOCAL COMPLETE: automatic Supervisor runtime/discovery; phone notify entity/action
picker replaces webhook; Connections/Commissioning removed; one immediate Overview
switch with persisted SQLite state, required-input checks and OFF stop/clear/revocation.
Missing fields highlighted on opening/edit; entity explanations removed; incomplete
files retain editor and no plan/authority, unverified live values show dashes. Old
commission flags cannot enable new switch; first upgrade off, later resumes gated.
TESTED:135 tests39.32s +final27 focused0.98s; Ruff/mypy27/JS passed. New automatic-
Supervisor seven-day E2E26.521s/2,018 intervals/max tick2.718ms/5 fake service calls.
Browser switch, highlights, phone save/reload/backup, removed fields, pending values
and console checks passed. Wheel/sdist33 source/installed files match; isolated
startup verified. Local8102/8103 fixtures and tabs closed;8100 preserved.
NEXT: final diff review, commit/push4.0.6 and inspect CI/image. Shipping authority
SPECIFICATION.md/RUNBOOK.md/SETTINGS.md; evidence settings-control-verification.json
and VERIFICATION.md. Persistent real billing timestamp issue not bypassed; live
telemetry/phone/physical commissioning remains unverified. No live access occurred.


4.0.6 remote CI/publication passed135 tests, but CI timing exposed4.276s during control
switching. Investigated instead of closing task: disabled GuardedActuator.apply waited
for the stop lock. Added slow-stop regression; reproduced failure on4.0.6, then fixed
with a disabled fast path before lock acquisition (serial guard still rechecks).
Version4.0.7 prepared to preserve the already-published4.0.6 image history. E2E now
reports baseline versus switch timing. NEXT:136-test verification, full-horizon E2E,
package and CI/publication for4.0.7, then final evidence. No live operation.


4.0.7 LOCAL COMPLETE: disabled actuator dispatch bypasses the stop lock; regression
failed before the fix and passes after it. All 136 tests passed in 39.25 s; Ruff,
mypy (27 modules), JS and isolated wheel/startup checks passed. 33 installed files
match source. Seven-day fake-Supervisor E2E: 2,018 intervals, 27.346 s, max tick
2.811 ms, post-switch 1.927 ms (one sample), five fake-only service calls.
Final browser ON/OFF, phone autocomplete and no console warnings/errors verified;
local fixture/tab closed, existing 8100 preview preserved. No live operation.
Clarification of preceding entry: the 4.0.6 CI 4.276 s tick was measured BEFORE
switching, so its cause is unestablished. The disabled-stop lock wait is a separate
reproduced bug, now fixed. Timing reports now separate baseline/post-switch samples.
NEXT: commit/push 4.0.7, inspect CI and container publication, record final evidence.


4.0.7 IMPLEMENTED / TESTED / PUBLISHED: code bd0af8fb4e7ca1804ed076ae5f2cf30299253a8a.
CI 40010642618 passed (136 tests, 41.50 s; types/JS/CLI, full-horizon E2E, package
and Linux container). Publication 40010642108 passed (136 tests, 35.73 s), image
4.0.7 digest sha256:b909ccdf13b8a9e8a6b5285a9d9374a9a29bf57b3d84c633f3fc08fd42bfccc9.
Remote E2E 31.029 s, max tick 5.749 ms, baseline 3.630 ms, post-switch 5.749 ms
(one sample), five fake-only calls. Shipping behavior/run instructions: SETTINGS.md,
SPECIFICATION.md and RUNBOOK.md. Evidence: VERIFICATION.md and
settings-control-verification.json; screenshots settings-v407-*.png (synthetic).
Local fixtures stopped and existing 8100 preview preserved. First upgrade switch off;
subsequent saved on requests resume only after input/configuration checks.
LIVE-UNVERIFIED: actual Supervisor/ingress, billing telemetry timestamps, physical stop/
phase/setpoint behavior and phone receipt. No live HA/database/hardware/phone access
or deployment occurred. No implementation work remains for this settings update.
NEXT: commit/push verification evidence; user installs/configures and reviews actual
telemetry before enabling hardware. Earlier billing timestamp rejection is not bypassed.


4.0.8 IN PROGRESS (authorized next release): scope limited to independent live cards,
per-input freshness and actionable input errors. No unrelated features/fixes; user
requires permission before any later code work and no optional verification-only commit.
Implemented: per-entity reads survive another failure; individual Overview values with
source/age/error metadata; meter's own timestamp anchors quarter energy. Power/quarter
retain configured age (default 30 s), battery percentages have separate 900 s bound,
static connection/phase-selector/monthly-peak states use availability. Expired/unknown
critical inputs still prevent control. Current-quarter counter required, while fresh
power from just before reset is allowed. No poll-time substitution for report timestamps.
64 focused regressions passed in 6.41 s; mypy 28 / Ruff / JS passed. Full suite running.
NEXT: full-suite results; full-horizon fake E2E including slow battery states; browser
verification with stale/unavailable/quarter inputs, packaging, one release commit/push
and inspect existing CI/publication. Record remote results in ignored checkpoint/final
response, without a separate verification-record commit. No live installation access.


4.0.8 LOCAL COMPLETE: limited input freshness/independent Overview update. Full suite
148 passed in 39.30 s; final 12 input regressions 0.33 s; Ruff/mypy 28/JS passed.
Seven-day fake-Supervisor E2E: 2,018 intervals, 27.573 s, max tick 2.178 ms, five
fake-only calls, including eight-minute battery and old static-state reports. Browser
stale/unavailable/old-quarter cases passed; unaffected cards remain, failed components
and ages identified, switch blocked; no console warnings/errors. Wheel/sdist built;
34 installed files match source and isolated startup/API passed. Transient Windows
build metadata rename error resolved on retry, no packaging behavior change.
Local fixtures/tabs closed; existing 8100 preview preserved. No live installation,
database, hardware or real notification access. State age budgets remain provisional.
NEXT: final diff review, ONE release commit/push, inspect CI and image publication.
Then append remote evidence only to ignored checkpoint/final reply; user forbids optional
verification-record commits. Future unrelated code work requires explicit permission.


4.0.9 IN PROGRESS: user explicitly authorized replacing per-entity age gates with HA
availability/current states and a successful-input-read watchdog. Scope only this design
change; no unrelated fixes, one release commit, no optional verification-only commit.
Implemented: HA report timestamps diagnostic only (including old/missing/future metadata);
Observation.at is completion of a validated HA input read. Unknown/unavailable, failed
reads and value/unit/physical checks still apply. Existing control/hardware/forecast
watchdogs now age the successful-read snapshot; quarter accounting uses current HA value
at read time, with no report-timestamp quarter comparison. Original P1 conversion and
quarter reset/accounting retained. Existing JSON watchdog key retained; UI label clarified.
67 affected tests passed in 6.58 s; Ruff/mypy 28 passed. Includes stalled input-loop
independent-control watchdog and old unchanged values across quarters. Metadata bumped
4.0.9; full E2E now uses three-hour-old report timestamps on every entity.
NEXT: full suite, full-horizon E2E, browser healthy-old-metadata and HA failure cases,
package/install checks, focused docs, one commit/push and inspect CI/publication.
No live HA/database/hardware/real notification access. Integration device availability
is trusted as agreed; actual installation outage reporting remains live-unverified.


4.0.9 LOCAL COMPLETE: 151 tests passed in 39.54 s; Ruff/mypy 28/JS passed. Seven-day
fake-Supervisor/HA/weather E2E: 2,018 intervals, 27.045 s, max tick 1.864 ms, five
fake-only calls; ALL entity report timestamps three hours old. Read-time watchdog,
HA availability and value validation gate control; no per-entity expiry or report-quarter
comparison. Original quarter conversion/reset and forecast expiry remain. Watchdog
expiry/recovery and stalled input-loop independent control tested. Browser healthy-old
metadata ON/OFF, genuine HA HTTP failure/blocking and no console errors passed.
Wheel/sdist built (metadata rename retry); 34 isolated installed files match source;
old available states accepted and read watchdog expiry verified. Local fixtures/tabs
closed, existing 8100 preview preserved. No live access or operation. Actual integration
outage reporting remains live-unverified. NEXT: final scoped diff review, ONE release
commit/push, inspect CI/image. Record remote results only in ignored checkpoint/final.


4.0.10 IN PROGRESS (24 October 2026): user authorized Android-style journey date/time
pickers, all frontend power values in W, EV schedule/calendar deferral and a durable
V4.1 handoff with current requirements/decisions. No scheduler behavior change authorized.
Confirmed prior question: daily SoC goals have zero withdrawal; only explicit journeys
consume predicted EV energy. No learned daily driving or automatic trip assumed.
Implemented: calendar/24-hour clock and keyboard option, installation-timezone conversion,
DST skipped/repeated-time handling; W display and reversible settings conversion with
API/JSON retaining existing units. Added five frontend tests, all pass; Ruff/mypy28/JS
pass. Full Python suite running. Initial tracked Git tree clean, baseline17279c2.
NEXT: reconcile/copy architecture references into tracked docs, browser journeys/settings
and watts verification with local fake HA, package and complete focused4.0.10 release.
No actual HA/database/hardware/phone access; EV calendar/new page remains deferred.


4.0.10 LOCAL VERIFICATION: 151 Python tests passed40.46s; final19 settings/asset checks
passed0.36s; five frontend tests cover W/rate conversions, calendar/clock, timezone/DST.
Ruff/mypy28/JS passed. Full-horizon fake-Supervisor E2E26.594s/2,018 intervals,
max tick2.823ms; five fake-only calls. Browser create/edit/Cancel/Clear, exact-minute
entry, repeated-hour persistence, skipped-time rejection, keyboard navigation and
390x844 layout passed. W cards/chart/peak/entity previews/settings verified; on-disk
2750W ->2.75kW and second-save reversal plus exact unedited numeric preservation checked.
Fixed a tariff floating-display artifact; no scheduler policy change. Current decisions,
V4.1 handoff and all original architecture references/backlog are now tracked with app;
ARCH-009 EV calendar/page remains deferred. Wheel/sdist built; final source install check
and release review remain. NEXT: package final assets, stop local preview, commit/push
one4.0.10 update and inspect CI/image; no separate verification-only commit. No live access.


4.0.10 LOCAL COMPLETE: final wheel/sdist built; isolated4.0.10 import and all37 code/
asset byte comparisons passed. Final frontend tests/syntax and19 settings/asset tests
passed after fixes. Historical architecture references preserved in tracked docs with
supersession notes; current HANDOFF/DECISIONS/SPECIFICATION/DEFERRED_WORK ready for a
new V4.1 chat. No new chat or V4.1 feature created. Local8102 preview/tab closed;
pre-existing tabs/8100 untouched. No actual HA/hardware/database/phone/deployment.
NEXT: final diff review, one4.0.10 release commit/push, inspect CI/image; append remote
completion only to ignored checkpoint/final reply. Future code needs explicit permission.


24 October 2026 DOCUMENTATION CORRECTION: user prefers one maintained architecture
across versions/chats, with no per-version handoff documents. Updated the existing
tracked docs/architecture/Architecture_Proposal.md with current requirements and resolved
implementation contracts; SPECIFICATION.md is now a compatibility link. Removed the
new HANDOFF.md, updated active links/pointers and recorded the preference in DECISIONS.md.
Original draft/history remains in Git and local historical records. Documentation only;
no application code, version bump or release. NEXT: keep this same architecture current
with future authorized changes; deferred ideas remain deferred.


4.3.12 LOCAL COMPLETE26October2026: user authorized continuity and rejected-peak
attention/notification fixes. Each economic stage reserves focused continuity work;
steady-grid alternatives retain all requirements and one2c comparison/cash envelope.
Final certificate preserves transition score/economics. Persisted rejection item retries
once then escalates via configured phone; successful acceptance clears it. Normal
revisions do not reset retry/dedup. Genuine pending permissions notify separately.
Publication reasons and labelled reconciliation evidence are available in history.
260Python59.78s/51Node/Ruff/mypy35 pass. Final private replay118.284s validates one
constant3.45kW morning session; supplied later measurement also reconciles with no
errors and unchanged5.49kW monthly peak. Three serial120s synthetic benchmarks valid/
certified; configured fake E2E35.295s/max4.602ms/four fake calls. Native/standalone
attention and native evidence verified.55 wheel/sdist code/assets identical; isolated
4.3.12 import. No live installation/database/hardware/phone/deployment. NEXT scoped
release commit/push and exact-head CI/image; remote results only in ignored checkpoint.
Preserve unrelated deferred backlog and paused Maps.


4.3.20 IMPLEMENTED27October2026: user authorized original EV scheduling continuity
and evidence-based recalculation. Full joint EV/ESS continuity retains source/ESS
freedom, prices actual phase changes and live-switch restarts, and preserves a shared
2cent cash/comparison reference. One fixed-phase session per connected window is an
alternative inside the original joint search; current can vary. No publication repair
or charger timer/fault change is included. Operational auxiliaries are appended after
physical variables and their rows added only when priced/certified, preserving economic
search quality. Optional/health searches keep valid reference/best-selected seeds;
model source-rounding threshold agrees with independent validation.

Replanning integrates15minutes of fresh household/PV residuals, changes the near-term
forecast before requesting work, rebases the correction across new issuances, and
ignores completed excursions and repeated unchanged bias. Expected resource progress
and immediate protective power changes do not launch full solves. Material inventory
loss, manual restart, periodic refresh and material events remain. Corrected forecasts
have their own permission identity and cannot consume prior forecast-specific ESS grants.
Required EV authority remains usable; forecast-driven ESS/conditional work is revoked.

Latest serial seven-day benchmarks validate within120s: mixed104.89s comparison-7.9923EUR
(previous same fixture-7.9707), winter104.56s25.4417EUR, permission118.77s32.3713EUR.
These are time-limited synthetic incumbents, not global optimality; mixed/winter source
certificates complete, permission certificate is feasible/time-limited. Final private
replay validates in118.72s with one continued3p session for the next morning,23.4569kWh
at its goal and peak5.49kW. This is offline evidence, not installation delivery.
Applying the earlier frozen unchanged adoption observation still rejects Required outcome:
the separate elapsed-energy publication issue remains; validation is not weakened and
no repair added. Final362Python102.73s/59Node/Ruff/mypy36 pass. FakeE2E33.976s,
2018intervals/max local control4.199ms/four fake calls passes;57 packaged source/assets/
defaults match wheel/sdist and isolated4.3.20 import passes. NEXT scoped release commit,
push and exact-head CI/image; remote results only in ignored checkpoint/final reply.
Detailed experiments/checkpoints remain ignored. Preserve unrelated DEFERRED additions
and paused Maps; no live installation/database/hardware/phone access or deployment.
