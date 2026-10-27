# EnergyManager 4 verification

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
power height360px, SoC255px. No browser warnings/errors. Screenshots and geometry are
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
 standalone fallback/setup download were inspected. No browser warnings/errors.
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
live-unverified. Current architecture and specification: architecture/Architecture_Proposal.md;
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
