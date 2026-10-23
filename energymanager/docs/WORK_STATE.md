# V4 promotion checkpoint — 23 October 2026

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
