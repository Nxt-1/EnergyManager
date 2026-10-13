# V3 preview validation

Local branch: `development/energymanager-v3`, based on `c6ae5f1` (add-on 0.31.16).
Preview: 3.0.0b1. No branch push, PR, merge, image publication or deployment was performed.

## Automated verification

- Python 3.13.5; HiGHS/highspy 1.15.1; one solver thread, fixed seed.
- Full pytest run: **280 passed**, no skips (8.85 seconds on this cloud instance).
  This includes real HiGHS integration and 38 V3 acceptance cases.
- Ruff passed for `energymanager/src`, `tests` and `tools`.
- Python compilation, YAML parsing, default configuration loading and HA schema-field coverage passed.
- JavaScript syntax and the focused V3 dashboard DOM-contract checks passed. The latter checks
  unavailable data, requirement rendering without HTML injection, archived session selection and file-size rejection.
- Docker Alpine/Python 3.13 image built successfully as local `energymanager:v3-review`.
  The image's imports and replay CLI were exercised. A real frozen HiGHS replay inside the image
  with networking disabled returned `optimal`, validation `passed`, objective **−EUR 0.73025**.
  The temporary build CA was confirmed absent from the image.

The regression suite retains actuator current/phase limits, stop/zero verification, phase reversal,
settling/minimum interval, stale/held sensors, guarded charger reset, latched faults and notification
suppression. V3 tests add shadow startup/private-write/reset/shutdown blocking, latest-solve supersession,
failed storage, checksummed replay, mixed generic jobs and thermal storage, physical-resource occupancy,
DST, non-quarter deadlines, hard infeasibility, economic reconciliation, priority bounds, stability,
unknown peak rejection, counterfactuals, live grid-headroom limiting, and quarter-boundary dispatch
continuity without executing future intervals early. Existing HA outage and fast-loop
recovery tests continue to pass. No skipped solver suite was used as evidence.

## Seven-day benchmark and replay

`PYTHONPATH=energymanager/src .venv/bin/python tools/benchmark_v3.py` creates synthetic, non-personal
inputs with 672 intervals, five weekly EV departures/trips, diurnal PV, varying household load, ESS,
flat tariffs and a known monthly peak. The benchmark deliberately uses a 30-second total budget
(15 seconds maximum for economics), rather than the normal 60-second total default.

Measured run:

| Metric | Result |
|---|---:|
| Wall time, including model construction/validation | 30.33 s |
| Economic incumbent objective | EUR 14.920558 |
| Selected objective | EUR 14.930558 |
| Applied economic tolerance | EUR 0.01 |
| Selected EV sessions | 10 |
| Physical validation | passed |
| Overall status | feasible_time_limit |

Economics completed in 1.74 s, solver status `Optimal`, gap 0.0001298.
Robustness used 7.01 s (gap 0.00590); operating quality used 6.97 s (event objective 20, gap 0.70);
stability was constant because there was no previous accepted plan; deterministic selection used
13.84 s (gap 0.01724). The last three nonconstant stages timed out with feasible incumbents.
**Lower-priority optimality was not established.** The large operating-stage gap is visible evidence,
not hidden by a success label. Session consolidation can improve with a larger configured budget.

A separate CLI replay of the archived seven-day snapshot passed validation, returned the same
EUR 14.930558 objective and 10 sessions, and had zero EV-energy difference over the first four hours.
Small completed-solve replay tests also compare the entire EV schedule. Time-limited runs are not
promised to reproduce every slot across machines or loads; compare economic tolerance and physical
validation, then inspect recorded stage metrics.

The earlier validation bottleneck (repeated conversion of HiGHS sparse arrays) was removed. Sparse
arrays are cached once during independent primal validation. There is no GPU or multi-thread speedup claim.

## Quantitative counterfactual

A separate saved two-hour snapshot has PV in its first hour and an EV departure minimum at hour two.
The CLI intervention `forbid_ev 0 4` excludes charging in the first four frozen slots. Both baseline
and alternative are feasible and independently validated with identical observations, forecasts,
requirements, tariffs, peak baseline, policy and resource constraints.

| Metric | Baseline | Alternative |
|---|---:|---:|
| Grid import | 0.05012 kWh | 3.89750 kWh |
| Net energy cash cost | EUR 0.01428 | EUR 1.06952 |
| Incremental capacity cost | EUR 0 | EUR 0.28 |
| Terminal usable ESS value | EUR 0.74453 | EUR 1.06977 |
| Total objective | −EUR 0.73025 | EUR 0.27975 |
| EV sessions | 1 | 1 |

The objective increases **EUR 1.01**, import increases **3.84738 kWh**, and the first EV start shifts
**four slots (one hour)** later. First-window EV energy decreases **5.2325 kWh**. Session count is
unchanged. Cash cost and terminal stored-energy value are reported separately; the negative baseline
objective is not a claim of realized negative cash expenditure. This is comparative evidence under
a specific intervention, not proof that PV uniquely caused every original charging slot.

Ignored, local review artifacts are in `.v3-evidence/`: full snapshots under `archive/`,
`benchmark.json`, `seven-day-replay.json`, `counterfactual.json`, pytest and Docker logs. They contain
synthetic inputs only. Regenerate them with the benchmark and CLI commands in [V3.md](V3.md).

## Build networking

Initial Docker package downloads failed because the container could not resolve the platform proxy;
after resolving that hostname, TLS correctly rejected the untrusted proxy certificate. The final build
passes the existing platform CA as the optional `pip_ca` BuildKit secret. Verification remains enabled;
no CA or credentials are committed/baked into the image. `python tools/build_v3.py` reproduces this
local build using the current environment's supplied proxy/CA, if present. Ordinary CI does not require
those optional settings. The script never pushes an image.

## Scope limits and review

No live hardware, live HA API, production database or installed browser dashboard was accessed.
Generic appliances/thermal resources have planning models, not new actuator integrations. Robustness
is a documented timing heuristic, current tariffs remain flat-profile inputs, and no minimal conflicting
constraint set or EV-specific grid-source attribution is claimed. Quarter-hour planning does not simulate
every second of charger settling; existing actuator interlocks remain authoritative. Time-limited
lower-priority stages can remain far from proven optimal.

Review locally with:

```sh
git switch development/energymanager-v3
git log --oneline -3
git diff c6ae5f1..HEAD --stat
git diff c6ae5f1..HEAD
source .venv/bin/activate
ruff check energymanager/src tests tools
pytest
node tools/check_v3_dashboard.cjs
```

See [V3.md](V3.md#shadow-only-installation-then-deliberate-activation) for migration, archive handling,
precise shadow-only installation and later deliberate activation. Publishing or deploying requires
separate approval. The preview must first be evaluated with explicit EV minima, actual installation
limits and `planner.shadow_mode: true`.
