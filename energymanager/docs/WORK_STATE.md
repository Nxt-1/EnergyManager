# V4 promotion checkpoint — 23 October 2026

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
