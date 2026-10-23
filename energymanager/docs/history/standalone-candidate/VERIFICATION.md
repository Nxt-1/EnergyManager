# Local release verification

Completed offline acceptance on 23 October 2026. All optimization and UI inputs here
are explicitly synthetic deterministic fixtures, not installation observations. The new
application runs end to end; live commissioning is a separate, unperformed step.

## Reproduction and environment

Use the commands and exact dependency setup in RUNBOOK.md. Verification used isolated
Python 3.13.17, Windows 10 10.0.19045, HiGHS 1.15.1, NumPy 2.4.2 and aiohttp 3.13.3.
The host exposes 24 logical processors, Intel64 Family 6 Model 183 Stepping 1. Docker
and Supervisor are unavailable. No system Python registration was changed.

## Automated and end-to-end checks

- `python -m pytest -q`: **43 passed in 32.70 s**.
- Ruff on `src tests tools`: passed. Mypy on `src/em_next`: passed, 19 modules.
- Node syntax checks on `app.js` and `ha-card.js`: passed.
- Wheel/sdist build: passed. Isolated installed-wheel real-solver CLI smoke: passed,
  Optimal, valid, 0.00924 s; all 23 source/asset files match the wheel byte for byte.
- Configured HTTP/fake-HA end to end: passed; full-horizon plan accepted in **24.061 s**
  from startup, 2,018 remaining intervals, maximum measured control tick **6.24 ms**,
  21 actuator service requests to the loopback fake only. See offline-e2e.json.

The configured test exercises real HTTP input/issued forecasts, a spawned full-horizon
MILP, publication against current measurements, independent guarded control, API state
and persisted input checksum/results. It does not enable a live controller. A separate
failure test requires disconnection handling within 200 ms and control computation below
100 ms while a real solve runs. These are offline event-loop targets, not hardware
response guarantees. Normal input/control cadence remains one second.

Tests cover AC/DC converter separation, losses, joint batteries, causal optional-source
restrictions, overlapping requirements, journey reserve/withdrawal, unknown returns,
local mornings across DST, billing-month reset and current-quarter prefix, specific peak
permissions, revocation between writes, fulfilled-grant isolation, 80/100% scarcity,
zero/partial optional quantities and inventory-value sensitivity, economical ESS peak
precharge/no arbitrage, source-specific reservations, protective fallback, delayed
publication, closed-loop delivered EV energy, timeout/error distinctions, local HA and
notification endpoints, immutable archive corruption and same-origin API rejection.

Final fixes have regression evidence: measured ESS balancing releases household discharge
at publication without inventing energy; best-effort source caps follow attained goals;
relaxed full-horizon warm starts remain authorized and can enter real HiGHS immediately.
Browser findings were repaired and rechecked: refreshing a plan cannot detach displayed
session controls from their records; chart axes adapt to available width.

## Full-horizon optimization

All three final reports have valid independent audits, a 168-hour horizon and maximum
300-second windows. Aligned fixtures have 2,017 intervals because an initial 15-second
phase-preparation boundary splits the usual 2,016 intervals. Unaligned running-service
snapshots add partial/hold boundaries; publication slices elapsed time without coarsening
any remaining window. Each complete benchmark had one 120-second wall budget.

| Synthetic case | Whole cycle | Peak kW | EV / ESS sessions | Optional EV kWh | Predicted bill EUR | Inventory-adjusted score EUR | Main economic gap |
|---|---:|---:|---:|---:|---:|---:|---:|
| Mixed solar + journey | 116.207 s | 2.50 | 14 / 18 | 17.976 | -1.424 | -7.951 | 0.424% |
| Winter + journey | 115.212 s | 3.21 | 2 / 14 | 0 | 25.875 | 25.462 | 12.334% |
| Urgent 56% in one hour | 116.488 s | 4.00 | 2 / 1 | 0 | 32.967 | 32.189 | 75.315% |

All have selected status `Time limit reached` with a validated feasible incumbent. None
is claimed globally optimal. The main economic stage's incumbent/bound pairs are
-6.835934/-6.864903, 26.577250/23.299096 and 90.058671/22.230806 respectively. These are
raw model objectives; constants, subsequent economic-bounded polish and grid cleanup
explain differences from the final displayed accounting score. The urgent case has a
large economic gap: service remains useful, but economic quality is not proven close
to optimum. Machine/timing and concurrent services can materially change incumbents.

The urgent original requirements were proven infeasible under current permissions.
Permitted best effort continues at 4 kW quarter-average ceiling with 2.619525 kWh urgent
shortfall. A separate feasible higher-permission diagnostic produces a goal/revision
request for 10.601033 kW. That is permission, not an execution target or a minimal-peak
proof. The urgent service objective itself ended with incumbent 2.619525 kWh versus
bound 2.585397 kWh, a 1.303% gap; later morning requirements were met. A timeout is
never substituted for proof of infeasibility.

Reports benchmark-mixed.json, benchmark-winter.json and benchmark-permission.json retain
every stage's dimensions, integer count, time, status, incumbent, bound and gap, as well
as cost components, shortfalls/request, starts, phase changes and validation. Typical
joint economic model: 59,860 columns, 67,269 rows, 17,489 integer columns. Mixed operational
polish: 61,877 columns and 71,303 rows. Actual active phase switches were 2 in each case;
three-phase activation changes were 6/2/2. ESS groups can contain declared brief pauses;
interval power and all physical checks retain those pauses.

Operational gaps refer to a different objective, not economic optimality. A single
EUR 0.02 bound protects both complete-plan comparison and predicted cash during polish.
The final minimum-grid certificate reached Optimal in all cases, within selected modes,
non-grid/storage allocations and quarter import envelopes. Its limited scope is explicit
in SPECIFICATION.md. Frozen snapshots/results are generated under ignored artifacts/ by
tools/benchmark.py; compact reports ship here. Re-running time-limited solves need not
return identical incumbents. Mixed/winter model runs preceded only the later conservative
warm-start repair; model constraints and their independent audits are the same.

## Browser and running service

Manual browser acceptance used the actual new HTTP application and real solver results:

- Overview live summaries, actual/planned powers, EV/ESS SoC, session timeline and time
  navigation: passed. Next/previous moves 12 hours; Now restores the current window.
- Planning spans all seven days, including the DST change: passed. Goals share one
  trajectory; later daily goals are grouped, and technical diagnostics are collapsed.
- Add a timed goal at 55%, edit to 57%, reload, remove: passed with persisted state.
- Grant a real diagnostic request, inspect the scoped grant, revise its goal, inspect
  revocation, receive a fresh request, reject and reload: passed. No hardware authority
  exists in these dry-run fixtures.
- EV and ESS session dialogs, reasons, stored decision list and immutable decision
  details: passed. Post-fix browser console error check returned no errors.
- Responsive Overview/Planning: passed in a 390px-wide same-origin test frame showing
  the actual application. Document width equals scroll width (390px; also 375px with a
  scrollbar in the shorter-frame check). This is width/layout verification, not a real
  phone or touch-device certification. Narrow axes use fewer, readable time labels.

Screenshots are in screenshots/. The main dry-run demo remains at http://127.0.0.1:8100/
using runtime/release-overview-20261023.sqlite. Temporary permission/mobile services and
tabs were stopped/closed. browser-service.json records fresh service adoption beyond the
initial seeded evidence: accepted decisions plus stale candidates rejected after goal
changes; maximum control computations in that sample were 8.86/21.10 ms for the two
services. Synthetic measured progress changes independently of the planned trajectory.

## Package and change review

Separate version 0.1.0.dev0, wheel/source distribution, CLI, assets, exact dependency
locks, new add-on namespace and container recipe are provided. Installed-wheel verification
uses `python -I`, asserts imports came from artifacts/wheel-final, and runs a real solver.
package-verification.json records wheel SHA256
`5b75ee4c816de8ab6831194c9f390fc4ce96f82a551e19ec7f1b97bf1e3f234c`.
No old scheduler is imported. Legacy source/dashboard/configuration/version diff is empty.
The sole Git-index exception was the generated nested build config: the user explicitly
authorized unstaging that file, and it was unstaged. Other staged content was preserved.

## Storage and remaining commissioning

Measured compressed snapshot/result sizes are 29,598/97,742 bytes (mixed), 28,437/52,185
(winter), and 28,358/44,087 (permission). At 288 decisions/day, that is about 21–37 MB/day
before SQLite/index overhead, extra replans and events. One-second synthetic measurement
and dry-run command bodies averaged about 488+254 bytes per cycle: another 64 MB/day of
JSON bodies alone. A provisional capacity allowance of **200 MB/day, about 6 GB/month**
includes overhead/headroom; it is an engineering estimate, not measured installation
storage growth. Monitor actual event rates/size, plan backups, and review free space.
No retention duration, automatic purge or data deletion policy has been introduced.

No Docker image build, Supervisor install, target-host dependency-wheel verification,
authenticated live ingress check, physical telemetry mapping, hardware timing or controller
cutover was performed. Those installation-specific checks remain in RUNBOOK.md together
with configuration mapping, exclusive-controller commissioning and rollback. Missing live
critical values prevent unsafe execution; they did not block offline implementation.
No installation database, real actuator, external notification, deployment or publishing
was used. Declared fixture economics and residual values are provisional, not calibrated.

publication-replay.json preserves an expected rejected diagnostic against a much later EV
observation; it is not a passing acceptance result. The current publication regressions,
fresh configured E2E and repeated service adoptions verify the repaired path.

No usage-limit interruption, reset-credit use, paid API switch or recurring automation
occurred. Automatic resumption was not assumed. The work checkpoint now records the
completed local release candidate; commissioning needs a separate authorized task.
