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
