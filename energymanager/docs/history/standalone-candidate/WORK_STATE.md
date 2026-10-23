# Work checkpoint — 23 October 2026

Status: COMPLETE as an offline-verified first-release candidate. No usage-limit
interruption occurred. Live commissioning remains a separate authorized activity.
Governing handoff/architecture/decisions/deferred and investigation documents were read;
local @code-writer skill was applied. Historical evidence and legacy application remain.

## Implemented

Fresh energymanager-next package: full168h joint EV/ESS MILP at <=300s intervals; source,
peak, service, 80/100%, rolling-economics and scoped-approval rules; independent fast
control; revision-safe publication; immutable compressed SQLite evidence; configured
HA/issued forecast/notification boundaries; functional Overview and Planning; separate
CLI, wheel/sdist, add-on namespace, container recipe and exact dependency locks.
Shipping behavior is in SPECIFICATION.md; reproduction/configuration/rollback in RUNBOOK.md.

## Tested and benchmarked

43 tests passed32.70s. Ruff, mypy19 modules and both JS syntax checks passed. Configured
loopback-fake E2E passed: accepted full-horizon plan24.061s, max control tick6.24ms,
21 fake service requests, verified persistence/checksum/API. Real full-horizon mixed,
winter and urgent-permission cases validated in116.207/115.212/116.488s under one120s
budget;2017 intervals, no coarse horizon. Economic gaps0.424%/12.334%/75.315%; no global
optimality claim. Urgent permitted best effort and useful scoped request verified.
See VERIFICATION.md and benchmark-*.json for dimensions/status/bounds/costs/limitations.

Browser add/edit/reload/remove, grant/revise/revocation/fresh-request/reject/reload,
EV/ESS dialogs, immutable history, time navigation and seven-day view passed. Responsive
actual-app390px frame has no horizontal overflow; readable chart labels. Fixed displayed
session/backing-state refresh race and reverified. Screenshots in docs/screenshots.
Repeated fresh service adoptions and stale-solve rejection recorded in browser-service.json.
Wheel/sdist build and isolated installed-wheel real HiGHS CLI smoke passed;23 source/
asset files matched. Wheel identity and smoke evidence are in package-verification.json.

## Environment and running preview

Isolated .venv313/Scripts/python.exe Python3.13.17, HiGHS1.15.1, NumPy2.4.2/aiohttp3.13.3;
requirements*.lock. No system Python registration. Main synthetic dry-run service remains
http://127.0.0.1:8100/ (PID60772, exec71456), data runtime/release-overview-20261023.sqlite;
its tab is preserved. Temporary permission/mobile services and tabs were stopped.
Restart with `--port 8100 --data runtime/release-overview-20261023.sqlite --budget 120`.
A restart revokes stored command authority until fresh measurement/plan reconciliation.

## Boundaries and next concrete action

Docker/Supervisor, target-host wheels/ingress and all physical commissioning are LIVE-
UNVERIFIED. No live installation/DB, real actuator, external notification, deployment,
publish/push or legacy release/config/dashboard change occurred. Missing live critical
values/explicit commissioning flags prevent unsafe execution. No retention deletion,
credits, paid API or recurring automation was introduced. No automatic resumption assumed.

Next concrete action: reviewer reads VERIFICATION.md, SPECIFICATION.md and RUNBOOK.md,
reviews provisional parameters/config mappings and reproduces target-host checks with
control disabled before any separately authorized commissioning. No local acceptance
implementation step remains. If extending later, compare this checkpoint to actual files.

Git review: changes confined to energymanager-next (plus ignored architecture checkpoint).
The one generated nested build/config.yaml was unstaged only after explicit user approval;
ignore pattern prevents recurrence. All other staged content was preserved. Diagnostic
publication-replay.json remains labelled rejected evidence, not passing acceptance.
