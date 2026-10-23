# EnergyManager 4.0.0 verification

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

Docker/Supervisor, target-host dependency wheels, authenticated ingress and physical
commissioning remain unverified locally. CI has been updated, but remote execution was
not triggered. No live installation/database, real hardware, external notification,
controller enablement, image publishing or push was used. Review the runbook before
installing/configuring this major update; explicit complete physical/actuator mappings
and commissioning/exclusive-controller flags are still mandatory for control.

Storage policy is unchanged: no retention deletion is enabled. Prior compressed decisions
used about72–127kB per snapshot/result pair; one-second synthetic measurement+command
bodies averaged about742 bytes/cycle. A provisional200MB/day (about6GB/month) capacity
allowance includes overhead and replans; this is an estimate, not installation growth.
Use backups and review actual disk/event rates before unattended commissioning.

No usage-limit interruption, reset credit, paid API switch or recurring automation occurred.
