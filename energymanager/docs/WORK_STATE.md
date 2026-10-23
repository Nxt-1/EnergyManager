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
