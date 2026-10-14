# V3 focused correction validation

Correction branch: `development/energymanager-v3`, based on `e16db32`.
Version: **3.0.0b2**, corrected model `3.0-preview.2`.
This correction task does not push, merge, publish, deploy or activate hardware control.
The previously approved initial V3 commit remains on `main` until these corrections are separately approved.

## Corrections and relevant files

- `milp_planner.py`: trip withdrawals use UTC half-open intervals rather than exact-start equality.
  Departure constraints credit only complete prior slots. Earlier trips in the same slot reduce the
  energy available for a later departure, both in model constraints and independent validation.
- `requirements.py`, `jobs.py`: generic storage has explicit `charging_windows`. State requirement
  `earliest_start` does not prohibit precharging; deadlines, efficiency, withdrawals and reserves
  remain part of the same physical model.
- `counterfactual.py`, `decision_records.py`, dashboard: economic status, incumbent, bound and gap
  are exposed. Bounds, rather than status labels or selected-schedule deltas, determine whether a
  cost direction is proven. Both complete hierarchical stage records remain available.
- `decision_store.py`: gzip archives, whole-decision checksums, bounded decompression and legacy
  preview reads. Defaults are 30 days, 10,000 records, 1 GiB compressed. Retention and stale temporary
  cleanup run during background saves, never in store construction or read-only replay.
- `hardware_authority.py`, controllers, registry, startup and configuration: removed global mode;
  only each device's existing control flag authorizes service calls. Defaults remain false.
  Obsolete preview options are explicitly rejected pending permission review.
- Configuration/schema/translations, documentation, focused regression tests and dashboard contracts
  were updated. There is one planner and no parallel V2 path or replacement simulation mode.

## Automated verification

Python 3.13.5; real HiGHS/highspy 1.15.1; one solver thread and fixed seed.

- Full pytest: **304 passed** in 10.75 seconds, no failures or skips. See `.v3-evidence/corrections-tests.log`.
- Ruff, Python compilation, YAML parsing, default configuration/schema round-trip checks passed.
- Dashboard JavaScript syntax and DOM-contract checks passed, including confidence and baseline
  stage rendering. This is not a live browser/HA integration test.
- Local Docker image `energymanager:v3-review` built with verified TLS. Offline replay inside the
  image passed physical validation. No image was pushed or hardware client started.

Regression coverage includes 07:00, 07:05, 07:10 and 07:15 departures; successive trips and away
windows; two departures within one slot; DST folds; conservative minima and full SoC trajectories;
storage charging permissions and efficiency; counterfactual optimal/time-limit/infeasible/error
reports; archive rotation, age, bytes, corruption, legacy read/replay, interrupted-write cleanup and
bounded decompression; independent ESS/EV hardware permissions; startup/shutdown/private fallback
and reset blocking when disabled. Existing phase switching, fault recovery, health, HA outage,
latest-request supersession and failed-storage tests continue to pass.

Intermediate runs caught an archive test expecting an uncompressed filename and a diagnostic test
expecting the prior model-version string. Both expectations were updated to the corrected contracts;
the final complete suite has no failures.

## Seven-day archived scenario

`PYTHONPATH=energymanager/src .venv/bin/python tools/benchmark_v3.py` creates synthetic inputs:
672 intervals, five weekday departures, PV, load, ESS, flat tariffs and known monthly peak.
The benchmark uses a 30-second total budget, with at most 15 seconds for economics.

| Metric | Result |
|---|---:|
| Wall time | 30.35 s |
| Economic incumbent | EUR 14.920558 |
| Selected objective | EUR 14.930558 |
| Economic degradation allowance | EUR 0.01 |
| EV sessions | 10 |
| Physical validation | passed |
| Overall status | feasible_time_limit |

Economics completed in 1.71 s, status `Optimal`, gap 0.0001298. Robustness used 6.99 s with gap
0.00590; operating quality used 6.96 s with gap 0.70; stability was constant; deterministic selection
used 13.90 s with gap 0.01724. **Lower-priority optimality is unproven.** A separate archive CLI replay
passed validation and returned the same EUR 14.930558 objective and 10 sessions. Time-limited schedules
are not guaranteed to reproduce every slot across machines or CPU loads.

Snapshot: `2bc910e15f7ed5609b380821b48eb3a7`. Its decision compressed from 2,586,371 bytes to
150,906 bytes (about 17× smaller). At a ten-minute cadence, 4,320 such records occupy approximately
622 MiB for 30 days, within the default 1 GiB cap. Larger/event-driven records may shorten retention;
limits are configurable and pending atomic writes temporarily add one record. Compression preserves
self-contained snapshots and reduces repeated arrays without introducing cross-record dependencies.

## Counterfactual confidence

Snapshot `c5c3db64aa41a99a1bc0e3850696bfaf` uses an EV deadline at hour two and PV in hour one.
The intervention `forbid_ev 0 4` excludes charging during that first hour.

| Metric | Baseline | Alternative |
|---|---:|---:|
| Economic incumbent / lower bound | −EUR 0.74025 | EUR 0.26975 |
| Economic status / gap | Optimal / 0 | Optimal / 0 |
| Selected objective after hierarchy | −EUR 0.73025 | EUR 0.27975 |
| Grid import | 0.05012 kWh | 3.89750 kWh |
| Incremental capacity cost | EUR 0 | EUR 0.28 |
| EV sessions | 1 | 1 |

Both plans validate. The economic difference bounds coincide at **EUR 1.01** within numerical
precision, proving the alternative is more expensive under this frozen model. The selected schedule
also differs by EUR 1.01, with 3.84738 kWh more imports and the first EV start one hour later.
This does not establish real-world causation or uniquely attribute the original schedule to PV.
Tests with overlapping bounds explicitly report only feasible incumbent comparisons, including when
HiGHS labels economics `Optimal` within a nonzero MIP gap. Missing/invalid solves report incomplete.

## Review and readiness

The corrections are ready for source review and offline validation. Deployment and hardware activation
remain unapproved. Installation-specific entity mappings, actual electrical limits, hardware ownership,
control permissions and a documented rollback procedure must be verified before deployment approval.
Follow [direct replacement and rollback](V3.md#direct-replacement-configuration-verification-and-rollback).
There is no required parallel installation or preliminary operating mode.

No live Home Assistant, hardware, production database or installed dashboard was accessed. Generic
thermal/appliance models have no new hardware integration. Robustness remains a timing heuristic;
minimal infeasible subsets and EV-specific grid-source attribution remain unsupported. Physical
charger behavior still requires approved installation-specific validation.

```sh
git switch development/energymanager-v3
git diff e16db32..HEAD --stat
git diff e16db32..HEAD
source .venv/bin/activate
ruff check energymanager/src tests tools
pytest
node tools/check_v3_dashboard.cjs
python tools/build_v3.py
```

Local ignored evidence is in `.v3-evidence/`: `corrections-tests.log`, `corrections-build.log`,
`benchmark.json`, `corrections-seven-day-replay.json`, `corrections-counterfactual.json` and compressed
archives. Export a JSON document for the dashboard using the CLI `show` command in [V3.md](V3.md).
