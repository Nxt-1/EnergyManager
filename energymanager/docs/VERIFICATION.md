# EnergyManager 4 verification

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
