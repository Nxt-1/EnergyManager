# V3 optimization quality: measured results

The hierarchy, hard constraints and priority tolerances remain unchanged. Production still uses
30 seconds for economics and up to 30 seconds for refinements. The experiments below do **not** justify
raising the default budget or adopting the experimental formulation switches.

## Reproducible inputs and method

Python 3.13.5, real HiGHS 1.15.1, one solver thread, fixed random seed. The same immutable snapshot
`2bc910e15f7ed5609b380821b48eb3a7` supplies 672 intervals, five weekly trips, PV, load, ESS, flat tariff
and known peak baseline. Only the reported time budget or research switch changes between runs.
Economics receives min(30, total/2) seconds; every subsequent priority retains its existing tolerance.
Physical validation passed in every run. Time limits are wall-clock limits and machine load can affect
which incumbent is found. These are measured comparisons on synthetic archived scenarios, not claims
of population-wide performance or guaranteed deterministic schedules.

Full stage records, objectives before/after, bounds, gaps, metrics and runtimes are committed in
[baseline and variants](quality-benchmarks.json), [allocation repeat](quality-candidate.json), and
[stability scenario](quality-stability.json). No forecasts or personal measurements are in these reports.

```sh
export PYTHONPATH="$PWD/energymanager/src"
.venv/bin/python tools/benchmark_v3.py
.venv/bin/python tools/benchmark_quality.py 2bc910e15f7ed5609b380821b48eb3a7
.venv/bin/python tools/benchmark_quality.py 2bc910e15f7ed5609b380821b48eb3a7 --candidate
.venv/bin/python tools/benchmark_quality.py c5c3db64aa41a99a1bc0e3850696bfaf --stability \
  --output .v3-evidence/quality-stability.json
```

The benchmark script never changes production configuration. The two internal `refine` switches are
research arguments, not new operating modes or add-on options. Existing archived snapshots are usable
by passing `--archive` and `--output`. The stability scenario freezes the small counterfactual snapshot
with +150 W background load in its first two intervals and the previous validated schedule as its
stability reference; this input is archived as `dbf61ccc85ff15545b955387f38f4f0a`.

## Budget comparison

| Total budget | Wall time | Selected EUR objective | EV sessions | Sessions under one hour | Three-phase activation transitions | Weighted import score | Operating objective / lower bound / gap |
|---|---:|---:|---:|---:|---:|---:|---|
| 30 s | 30.07 s | 14.930558 | 10 | 4 | 10 | 24.116697 | 20 / 6 / 70% |
| 60 s | 60.06 s | 14.930558 | 7 | 1 | 4 | 24.044966 | 11 / 6 / 45.45% |
| 120 s | 120.07 s | 14.930558 | 7 | 1 | 4 | 24.044966 | 11 / 6 / 45.45% |

The economic incumbent is EUR 14.920558 in all runs (status `Optimal`, gap 0.01298%); the selected plan
spends the allowed EUR 0.01 tolerance. More time from 30 to 60 seconds improves practical fragmentation
and phase activity. Doubling 60 to 120 seconds does not improve the selected schedule metrics here.
All three overall statuses remain `feasible_time_limit`. No later-stage global optimality is claimed.

Three-phase transitions count the model's activation/deactivation events, including stopping and
restarting three-phase charging. They are not necessarily physical phase-switch service calls: the
existing actuator interlocks and retained charger mode still determine those calls.

## What each stage actually achieved

At 30 seconds with the existing allocation:

- Economics finds EUR 14.920558 in 1.87 s, with its recorded nonzero relative gap.
- Robustness reduces its own objective from 25.963475 to 24.116697 weighted kWh in 6.95 s.
  This also increases three-phase transitions from 6 to 10; priorities are explicit, not blended.
- Operations starts at 20 events and ends at 20 after 6.96 s, bound 6. It proves no improvement in
  the incumbent during that stage. A 70% gap is not a 70% physical violation or cost penalty.
- Stability is constant zero because that snapshot has no previous accepted schedule.
- Deterministic selection starts and ends at 23,133.218302 slot-weighted kWh after 13.79 s. It does
  not improve the selected incumbent in this run.

At 60 and 120 seconds robustness reaches 24.044966, and the operating-stage incumbent is already
11 events when the stage starts. It stays 11. The practical improvement arose earlier in the hierarchy,
not from a proven improvement by the operating stage. The GUI now exposes this distinction directly.

In the separate two-hour changed-load stability scenario, all budgets complete optimally in well under
one second: robustness reduces 1.167911 to zero, operations reduces 3 to 2 events, and stability reduces
1.489056 kWh of deviation to approximately 0 (floating-point residual below 1e-12). The selected
objective is −EUR 0.70775 versus economic incumbent −EUR 0.71775, respecting the EUR 0.01 tolerance.
Negative objective includes terminal ESS value; it is not negative cash expenditure.

## Why the operating stage is difficult

The model contains repeated discrete choices for single/three-phase operation and integer charging
current at every eligible quarter-hour, continuous storage/grid flows, and start/transition variables.
Flat tariffs create many near-equivalent timing/current combinations. Earlier objectives then constrain
this large feasible region with tight economic and import-score bounds. The operating event objective
has a much coarser integer structure than the underlying flow model.

Recorded operating bounds support the weak-relaxation diagnosis: the solver has a lower bound of
6 events versus incumbent 20 or 11. In the baseline it processes zero search nodes at 30/60 seconds
and two at 120 seconds, consistent with substantial root processing rather than broad search. This
is model/solver evidence, not a CPU profile attributing exact time to a particular presolve routine.
The current start constraints already describe the standard local start-indicator convex hull; merely
marking them integer does not eliminate fractional schedules across the horizon.

## Targeted experiments

| Research change, 30 s | Selected sessions / short sessions | Final phase transitions | Operating-stage gap | Interpretation |
|---|---|---:|---:|---|
| Skip constant stages when sharing remaining time | 7 / 1 | 0 | 0% | Operating objective improves 16 → 7 and is proven optimal for that run's prior bounds |
| Explicitly integer start variables | 12 / 1 | 0 | 66.67% | Different practical trade-off; more sessions despite final deterministic gap falling to 0.45% |
| Omit explicit `setSolution` at refinements | 10 / 4 | 10 | unavailable | No better incumbent; some stages return no incumbent and preserve the validated prior one |
| Disable presolve after economics | 9 / 3 | 4 | 66.12% | Some schedule change, weaker operating lower bound 4.403805; no consistent proof benefit |

The omitted-start experiment is labelled `cold_refinement` in raw reports, but only the explicit
refinement warm-start call is disabled; HiGHS may retain internal state. Normal `setSolution` calls
return `HighsStatus.kOk`, which proves acceptance of the supplied start, not that the start is optimal.
Presolve remains enabled for economics in all comparisons. It is disabled only for subsequent stages
in the presolve experiment.

The current allocation assigns roughly 14.5 s each to robustness and operations at total 60 s, then
leaves about 29 s for deterministic selection because the intervening stability expression is constant.
Skipping constant expressions when dividing time gives roughly 19.3 s to each nonconstant stage.
The attractive 30-second result repeated (7 events, zero gap), but at both 60 and 120 seconds it gave
the same 7-session/4-transition outcome and 45.45% operating gap as baseline. Different time-limited
robustness incumbents establish different preceding bounds, so a 30-second operating optimum cannot
be compared as if all variants solved exactly the same final subproblem.

**Decision:** keep existing defaults and formulation. Retain the experiments as reproducible research
and expose actual improvement evidence. There is no justification here for arbitrary scheduling weights,
a longer default budget, removing presolve or adding integer start variables to production.
