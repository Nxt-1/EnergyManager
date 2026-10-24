# EnergyManager — first-release architecture draft

> Preserved original design reference. Read [the current handoff](../HANDOFF.md),
> [decisions](../DECISIONS.md) and [shipping specification](../SPECIFICATION.md) first.
> Historical pending-work statements and chat restrictions are not current instructions.


22 October 2026. Architecture discussion only: no implementation, application configuration changes or live operation are authorized here.

This draft consolidates the agreed behaviour and proposes component boundaries. It is not a finished MILP specification or a claim that runtime and economics have been validated. [Architecture_Decisions.md](Architecture_Decisions.md) records individual decisions; [Deferred_Work.md](../DEFERRED_WORK.md) retains later features.

23 October 2026 handoff note: the user now requests implementation in a separately created chat. [Implementation_Handoff.md](Implementation_Handoff.md) carries the scope, delegated technical work and verification criteria; [Implementation_Chat_Prompt.md](Implementation_Chat_Prompt.md) is the prompt to paste there. This chat remains documentation-only. The technical work listed below is explicitly delegated to that implementation chat rather than represented as already solved or verified.

## Scope

Schedule the EV and ESS together. Forecast AC PV, DC PV and uncontrolled household demand. DHW, washing-machine/dishwasher scheduling, planned Mazak operation and appliance recognition are deferred; include their consumption in uncontrolled demand for now. Keep resources and requirements extensible so adding them later does not require a new architecture.

A general ESS reserve for unplanned load peaks is also deferred as [ARCH-008](../DEFERRED_WORK.md#arch-008--ess-reserve-for-unplanned-load-peaks). Forecast-specific peak reservations remain part of the current design; do not introduce a standing reserve for unforeseen loads in this release on the basis of that future idea.

Keep the seven-day horizon and planning windows no longer than five minutes. Forecast accuracy by lead time, foundation models and possible coarser resolution are separate future investigations. Actuator hardware and local protections are existing boundaries, not work to redesign in this chat.

## Proposed components

### 1. Measurements and predictions

Produce a time-stamped view of resource state, actual consumption, AC/DC solar forecasts, uncontrolled-demand forecasts and forecast uncertainty where supported by evidence. Preserve what was known at each planning decision; later forecast revisions must not overwrite that evidence.

Forecasts describe expected conditions. They do not create household requirements, reserve energy or command actuators. Distinguish systematic model bias from residual uncertainty. Initial margins must be visible and later calibrated, without treating missed deadlines as acceptable planned outcomes.

### 2. Requirements and policy

Calendar entries, recurring rules and manual requests define desired outcomes, timing, source permissions and priority. These exist independently of a particular schedule.

For the EV:

- Daily configurable minimum, initially 50% by 07:00, subject to known availability; this is not a continuously maintained 50% floor.
- Journey requirements use total journey kilometres, including return travel, assumed consumption and a configurable 30 km remaining-range reserve. The reserve is desired remaining energy, not an additional withdrawal on every trip.
- A manual SoC request is a regular timed task without an assumed journey or later energy withdrawal.
- Trips exceeding one battery charge target 100% and flag the need for user-arranged charging away. Do not fabricate external charging or return SoC.
- Missing return times mean unavailable after departure until reconnection or a supplied return time.

The considered daytime recovery rule after unplanned trips was withdrawn. Reconnection updates actual state and availability but creates no separate reserve-restoration obligation. Retain the morning goal, explicit trip/manual requirements and conditional surplus capture.

Keep task priority distinct from permission to increase the monthly peak. Preserve goals and progress across rescheduling. A task is not a separate object for every short execution session.

### 3. One coordinated planning process

Use MILP as the current candidate engine, with a newly specified physical model and policy constraints. Jointly choose EV timing/power and ESS trajectories; do not allocate each load independently and expect local adjustments to recover all interactions.

Model AC and DC paths explicitly. The approximately 2.5 kW MultiPlus limit applies to that converter. It must not cap DC charging into the ESS or the combined AC/DC charging total. Represent actual efficiencies, usable storage, EV charging modes, physical operating restrictions and quarter-hour import energy, including the already-elapsed part of the current quarter-hour.

Required outcomes normally remain requirements. If they cannot all be met within authorized limits, produce explicit best effort, identify the affected goals and consider an approval proposal separately. Do not hide infeasibility behind arbitrary economic penalties or silently weaken deadlines.

Conditional opportunities belong in this same planning process. A permitted strategy proposes a reason, conditions and an upper bound; the selected quantity can be zero or partial. Only selected actions become executable named tasks. Routine ESS balancing remains represented in the resource trajectory without manufacturing a task for every power adjustment.

Examples include useful EV surplus capture, preserving ESS energy for a predicted peak and creating ESS headroom for otherwise-curtailed DC solar. Their benefit must be assessed jointly so several sinks cannot claim the same available energy. The precise reference-plan and future-energy valuation methods are still open; the architecture does not assume that repeatedly regenerating fixed-energy tasks will converge.

#### Planning input snapshot

Each planning run reads an immutable input snapshot with a unique identity. Include:

- Current measurements and their timestamps/quality: ESS energy, EV SoC and connection state, actual import and consumption.
- Physical resource descriptions, converter paths, limits and efficiencies; refer to the existing actuator protections rather than redefining them here.
- Requirement identities and revisions, availability windows, remaining progress, priorities and source permissions.
- Tariff/profile identity, actual monthly peak, actual import energy already used in the current billing quarter-hour, configured allowance and task-specific approval/rejection state.
- Forecast issuance identities and their interval values, plus supported uncertainty information.
- The accepted plan and its current validity restrictions, for continuity and fair comparison.

An input changing during calculation creates a newer state; it does not mutate the snapshot used to explain that calculation. Record the change and request/coalesce further planning as needed.

#### Candidate plan output

A result contains planned resource trajectories and task execution instructions, goal outcomes/shortfalls, understandable reasons, proposed permission extensions, solver status, calculation timings and the input snapshot identity.

Keep permission proposals separate from executable instructions. A branch that requires approval cannot supply assumed energy to the executable branch. An actually incurred monthly peak is a measured input; an optimized or proposed peak is not.

Do not duplicate physical charging energy between overlapping EV goals. Use the same predicted battery trajectory to evaluate daily, trip and manual requirements. Distinct goal identities preserve provenance and progress without requiring disjoint charging sessions.

### 4. Fast coordinated control

React to actual conditions independently of the full planning calculation, within the accepted plan's valid permissions and reservations.

- Cover brief solar dips with the ESS where possible; brief grid imports are acceptable within permissions. Smooth EV adjustments rather than chasing every fluctuation.
- For sustained deviations, reduce flexible power before pausing where feasible. Peak protection can stop an eligible load immediately when necessary.
- Protect still-valid scheduled allocations. Unexpected surplus first increases feasible ESS charging; residual surplus may advance a suitable existing task within its constraints. Do not reduce scheduled ESS charging to create a competing optional opportunity or create and immediately execute a new unscheduled task.
- Trigger/coalesce replanning when a meaningful departure from the plan occurs.

#### Permissions for immediate adjustments

The accepted plan provides both intended operation and boundaries for permitted adjustments:

- Relevant task identities, valid availability/timing and allowed operating modes/power ranges.
- Remaining charging quantities/targets, applicable source permissions and peak authorization.
- Explicit ESS reservations needed for still-valid shared commitments, with their relevant times. These are constraints on permissible deviations, not a global permanent SoC reserve.
- Any explicitly permitted advancement of existing scheduled work. Advancing it cannot invalidate another task's protected allocation or exceed its own target/availability.

Fast control uses fresh measurements to remain within those boundaries and existing actuator protections. It does not create new goals or grant permissions. A protective reduction/stop can precede a full replan. Significant changes in progress or allocations trigger replanning; routine small balancing changes need not each start a new solve.

Guard quarter-hour import using measured energy already consumed plus remaining headroom and available controllable response. A five-minute planning interval is not a five-minute wait before acting. Exact sampling, smoothing and engineering allowances need evidence; they are not fixed by this architecture.

#### Invalidation while a solve is running

- On disconnection or a changed/cancelled goal, invalidate the affected execution instructions immediately. Retain goals/progress unless the need itself was cancelled.
- Extend restrictions to other tasks when a failed shared-energy or power assumption requires it. Do not assume every other instruction is unaffected simply because its task did not change.
- Continue still-valid instructions and ESS operation. Preserve explicit still-valid reservations; without a usable plan, basic ESS operation absorbs PV and reduces import within physical constraints. Do not invent forecast-driven grid charging or pre-discharge.
- Forecast revisions trigger replanning and measured deviations are handled by fast control. A revised forecast is not, by itself, an instruction to stop every task.

### 5. Plan validation, publication and decision records

Only one accepted plan controls execution. A calculated plan is a candidate until checked against current resource state, task versions, physical constraints and permissions. Proposed adoption sequence:

1. Reconcile elapsed execution and actual progress; a result cannot repeat energy already delivered or restart an elapsed session.
2. Verify current goal identities/revisions, availability, permissions and physical resource descriptions. Previously invalidated commands must not reappear from an older snapshot.
3. Recheck the candidate's remaining trajectories against current actual state and relevant updated inputs, including the current quarter-hour budget and shared reservations. An unchanged forecast version alone is not a feasibility guarantee.
4. Compare any claimed improvement with the current plan using consistent updated assumptions. A required feasibility repair can justify adoption independently of cost savings; similar cost may justify smoother execution.
5. Publish a coherent replacement only after these checks pass. If it fails, retain still-valid accepted instructions, apply necessary restrictions and replan. Never use an unapproved proposal as the fallback.

Validation may require recalculation of trajectories or a new solve; this architecture does not claim that every stale result can be repaired cheaply. Forecast updates need not force rejection when current checks still establish an acceptable candidate. The exact validation/versioning mechanism and numerical tolerances remain to be designed.

Store the input snapshot, forecast revisions, policies, relevant actual states, candidate, solver result/status and timings, validation outcome, accepted replacement or rejection reason, recorded reasons and subsequent invalidations. Distinguish planned, accepted, commanded and measured behaviour. Preserve permissions and goal revisions so replay can explain what execution was actually authorized to do, without reconstructing it from unrelated database tables.

Plan for sufficient storage. No retention duration or automatic deletion policy has been agreed. Future advanced forecasting may require additional signals/history; retaining decision records alone is not proof its training requirements are met.

## Whole-system economic comparison — proposed calculation

The user agrees that losses, capacity costs and actual energy belong in the comparison across tasks. Proposed common accounting for a plan over a window of length H:

`comparison_cost = import_cost - export_income + incremental_capacity_cost + stored_value_at_start - stored_value_at_end`

This is a decision score including energy assets, not solely the predicted invoice. Display the bill components and stored-energy valuation separately so assumed future value is not presented as cash already saved. With identical starting states, the starting-value term cancels when comparing plans.

### Energy and losses

Model physical energy balances across the AC/DC converter paths, ESS and EV. Apply charging, discharging and relevant standing efficiencies to the energy that actually reaches each destination. Imported energy is charged at the configured import tariff; exports earn the configured export tariff. Foregone export income is therefore counted without a separate invented solar price.

Do not add another monetary loss penalty after losses are already represented in the flows and stored-energy changes. There is no monetary ESS wear charge under the agreed policy. Standard storage balances express charge/discharge efficiencies in this way; see the [PyPSA storage modelling documentation](https://docs.pypsa.org/v1.4.0/user-guide/optimization/storage/). This is an engineering reference, not selection of a new application dependency.

### Capacity costs

For each affected billing month, calculate the configured capacity cost at the greater of the already-incurred baseline and the candidate's maximum quarter-hour import, then subtract the cost at the already-incurred baseline. Respect the billing floor and reset the baseline appropriately for a new month. Do not charge each overlapping task separately for the same household peak, or treat an approved/proposed peak as already incurred.

Permissions remain independent constraints. A saving in this score does not authorize exceeding a task's peak limit.

### Stored-energy accounting

Apply a consistent resource-specific valuation to useful energy remaining in the EV and ESS. EV energy retains the same unit-valuation rule across the seven-day boundary, as agreed. Account for the energy's physical location and conversion efficiencies rather than treating a battery-side kWh and a grid-side kWh as interchangeable.

Proposed first-release estimates under the current fixed import tariff:

- `EV_value_per_battery_kWh = import_price_per_kWh / reference_EV_charging_efficiency`.
- `ESS_value_per_battery_kWh = import_price_per_kWh * reference_ESS_discharge_efficiency`.
- `stored_value = EV_value_per_battery_kWh * useful_EV_energy + ESS_value_per_battery_kWh * useful_ESS_energy`.

Use the same reference coefficients for both alternatives and both ends of the comparison. Reference efficiencies must come from configuration or measured evidence; do not invent numerical values or increase the credit by choosing an inefficient charging mode. Actual mode-dependent losses still belong in the physical energy balances.

These are replacement-value estimates, not guaranteed future grid purchases avoided; actual future solar can change their realized benefit. The user has accepted counting useful residual energy in the comparison. These particular coefficient formulas are the proposed engineering starting point and still require calibration and sensitivity checks. No explicit monetary battery-wear charge is introduced.

Credit the change in useful stored energy once. Do not also award the same credit to every charging action or every intermediate SoC observation. Energy already used to meet requirements is reflected through the physical trajectory and purchases; required service must be held comparable between alternatives. For future appliance tasks, completing a cycle is a requirement, not permission to credit every consumed kWh as a stored asset. Thermal residual value will require its own model when DHW scheduling is added.

### Fair alternatives and joint opportunity selection

For an opportunity assessment, compare a reference without the optional intervention(s) and a candidate allowing them. Both use the same initial measurements, forecasts, required outcomes, commitments, constraints and permissions. In both, the scheduler may reposition flexible required work; do not freeze a poor reference and label avoiding its inefficiency an intrinsic optional-task benefit.

Disabling discretionary extra consumption must not remove an ESS control action needed to support a required outcome. The reference retains authorized required-goal support and normal ESS capabilities, with reasons recorded for forecast-driven interventions. It does not forbid a necessary action merely because that action also has a conditional strategy name.

The candidate selects optional quantities jointly, from zero up to their permitted bounds, while coordinating EV and ESS. Compare their combined whole-system result. Do not add independently calculated task savings that could each claim the same solar energy or avoided peak. The reference's exclusion of the intervention also prevents successful surplus absorption from cancelling its own reason merely because the candidate now has no surplus.

Proposed first-release mechanism: one reference calculation and a joint opportunity calculation for the same snapshot, retaining the reference as an available alternative. Record solver status and bounds: a comparison with a feasible reference is not proof that reference is globally optimal. Additional source/strategy eligibility checks may require more work; runtime and the exact formulation still need validation. This proposal does not establish convergence of an iterative task-generation loop.

Do not obtain a claimed saving by leaving a required goal unmet. Compare within equivalent fulfilled requirements or the applicable best-effort priority level; feasibility improvements can independently justify a plan change. Smoothing remains a subsequent preference within the agreed small cost tolerance.

### Agreed interpretation of the rolling 24-hour rule

The user accepts including useful energy remaining at the end of the 24-hour comparison, using the same valuation rules. The window limits forecast-dependent operating effects and cash flows used to justify the indirect-import exception; it does not make residual energy worthless or require predicting exactly when it will be used afterward.

Consequently, PV charging of the EV may be justified even if it causes some household grid imports within those 24 hours and the extra EV energy is used later, provided the combined score, including both EV and ESS residual values, improves. This explicitly supersedes the earlier interpretation excluding future residual value alone from that justification. The approval/source constraints, direct optional-grid-charging prohibition and protected commitments still apply.

Keep predicted cash expenditure and assumed residual-energy value separately visible. Do not claim the inventory credit is already realized bill savings. The distinct rule for ESS grid charging still requires a peak-avoidance justification tied to a predicted peak within 24 hours; residual value alone does not authorize ordinary grid charging of the ESS.

## Optional charging quantities and source permissions — technical proposal

### Quantity is a decision, not an obligation

For each permitted opportunity, introduce a non-negative quantity bounded by its actual eligibility, available source energy, resource capacity and allowed SoC ceiling. Zero is valid. The physical model allocates the shared PV and ESS energy once across all selected actions and required work.

Use one EV charging trajectory and one battery state, with requirement constraints at their relevant checkpoints. Daily, trip and manual goals do not each receive an independent copy of the delivered energy. A selected optional quantity becomes a named task/reason attached to the resulting trajectory; it does not become a fixed demand that a subsequent solve must satisfy regardless of its original benefit.

Keep supported current/phase choices in the EV resource model and transition constraints. Do not multiply those physical choices by every goal or conditional strategy. Strategy eligibility may need discrete decisions, but the amount captured remains variable. Model size and runtime must be measured before choosing the detailed discrete representation.

### Source accounting must describe feasible flows

Account for EV input from direct grid supply and eligible PV/ESS supply, consistently with the physical AC/DC balances, losses and converter modes. These are accounting allocations on a shared electrical system, not claims to identify individual electrons. Source labels cannot create more PV or bypass the MultiPlus limit.

Direct grid supply may cover required EV charging. Optional EV charging must be covered by eligible PV/ESS energy. Permitted indirect household imports remain subject to the combined 24-hour comparison. New grid charging of the ESS needs its own peak-avoidance justification and explicit reservation; optional actions cannot consume an active protected allocation or justify arbitrary ESS grid purchases through EV inventory credits.

### Guard against relabelling optional grid charging as required

A simple split into variables named required and optional is insufficient: the optimizer could keep buying grid energy for a nominal requirement, assign available solar to the optional variable and end with gratuitous extra EV energy.

Proposed guard: direct EV grid energy must be necessary for the required outcomes **given the eligible PV/ESS energy actually assigned to the EV and its timing**. Do not use a simple whole-week subtraction: solar arriving after an earlier departure cannot replace grid energy that was needed before that departure.

For the initial EV model with fixed known trip withdrawals and battery-side charging quantities, the causal energy audit can be expressed as:

- At each required checkpoint i, let `B_i = required_battery_energy_i + known_withdrawals_before_i - initial_battery_energy`.
- Let `S_i` be eligible non-grid energy actually delivered into the EV battery by that checkpoint.
- Then the minimum direct-grid battery energy needed across those checkpoints is `G_needed = max(0, max_i(B_i - S_i))`.
- Require the direct-grid contribution to cover only that causal deficit. The physical model still determines when it can be delivered and the associated AC energy/losses. Extra charging beyond the required trajectory must come from eligible sources.

Example consequences: if solar before a deadline already covers its energy requirement, grid charging cannot preserve an artificial separate mandatory allocation. If grid energy was needed for Monday's departure, Wednesday's solar does not retroactively invalidate that purchase and can still be captured afterward.

This is a proposed battery-energy guard, not a completed MILP encoding. Additional time-dependent battery losses would require extending the audit. Physical capacity/availability constraints remain binding. In infeasibility mode, establish the achievable priority-preserving service profile before the economic comparison; retain the original goals and shortfall status. Do not reduce service to make an optional action look cheaper.

### Sanity check of the accounting

Illustrative arithmetic only, using invented round numbers rather than this installation's calibrated efficiencies or tariff. Assume:

- 3 kWh of surplus AC PV during a one-hour capture window; later household demand is 2 kWh and stays below the already-incurred peak.
- Initially no usable ESS energy above its physical minimum; sufficient ESS capacity; maximum AC charging during the capture window is 2.5 kWh.
- Import price EUR 0.30/kWh, export price EUR 0.04/kWh, ESS charge/discharge efficiencies both 95%, and EV charging efficiency 90%.
- Required EV outcomes are already covered. Grid charging the ESS has no peak-avoidance reason in this example. Apply the proposed reference valuations consistently.

The following rows show the reference and the result under two optional-headroom limits. Existing EV energy is common to each comparison and cancels; the energy-value column counts additional EV energy and usable ESS energy remaining after the household demand.

| Case | PV AC energy to EV | Net bill contribution | Remaining energy value | Comparison score |
| --- | ---: | ---: | ---: | ---: |
| Reference: optional capture disabled | 0 kWh | EUR -0.0200 | EUR 0.0769 | EUR -0.0969 |
| EV headroom limited to 0.6 battery kWh | 0.667 kWh | EUR 0.0000 | EUR 0.2318 | EUR -0.2318 |
| Sufficient EV headroom for all 3 kWh | 3.000 kWh | EUR 0.6000 | EUR 0.9000 | EUR -0.3000 |

The limited case selects a partial quantity rather than inventing a 3 kWh obligation. With ample headroom, accepting household grid imports yields the lower combined score under the stated valuations. Its predicted bill is EUR 0.62 higher than the reference, while its adjusted score is about EUR 0.203 lower; these are different results and must not be reported interchangeably. Negative scores include stored-energy credits, not a cash profit.

The arithmetic was checked without running application code or a solver. This is not a demonstration of actual EV phase/current feasibility, scheduling runtime or realized savings. Actual implementation validation must use supported operating modes and measured parameters.

### Source and quantity acceptance cases for the handoff

- No PV or usable eligible ESS energy and no remaining required EV deficit: optional charging is zero even if inventory credits make grid purchases appear indifferent or attractive.
- Eligible solar can cover the required EV deadline: do not retain unnecessary EV grid charging by labelling that solar optional.
- Required grid charging occurs before an earlier deadline, with solar arriving afterward: permit later eligible capture without treating the earlier grid purchase as optional.
- A normal SoC ceiling or source budget leaves only a partial opportunity: select at most that quantity; zero is also permitted.
- Several strategies claim the same PV/ESS energy or peak saving: enforce shared physical constraints and report their joint benefit once.
- A candidate is economically attractive but needs an unapproved peak, an invalid source allocation or another task's protected ESS energy: it cannot become executable on the basis of that economic score.

The remaining implementation specification must encode this audit and the exact strategy eligibility rules, define rolling comparison windows for interacting interventions, and validate them against these cases. This section reduces the open formulation work; it does not claim a globally optimal, runtime-validated implementation.

## Exceptional EV ceiling — proposed opportunity test

The preference is already agreed: normally cap discretionary charging at 80%; permit up to 100% when today's extra opportunity cannot adequately be replaced later. The full seven-day horizon applies to this availability assessment. The following specifies a proposed test, not another request to choose the preference or a validated optimization implementation.

### Compare actual feasible opportunities

For the current solar-capture opportunity, estimate the extra battery energy that could usefully be accepted above the normal ceiling, up to 100%, while respecting physical limits, required outcomes, source rules and permissions. If no such extra energy is available, no exceptional-ceiling decision is needed. Keep this potential amount distinct from a required energy quantity or an instruction to fill the battery.

Assess whether a coherent alternative could replace that amount using later solar during the remaining horizon. Use the same forecasts, initial state, travel withdrawals, availability and requirement revisions. Allow flexible work to move jointly. A later forecast PV total alone is insufficient.

The comparison must account for:

- Whether the EV is actually expected to be available and whether its charging modes and physical battery headroom can accept that energy in the later windows.
- PV routing and conversion losses, including the independent DC charging path and MultiPlus AC limits.
- Competing household consumption and protected commitments. Do not count the same energy as both later EV replenishment and ESS support for another required outcome.
- Later solar already assigned to required EV replenishment: it may count as a replacement opportunity because extra energy captured now would reduce that later replenishment need.
- The corresponding ESS state, not merely the EV state. Restoring EV energy by leaving the ESS depleted is a transfer, not proof that later solar replaced the current opportunity. Compare corresponding resource states and costs at the assessment checkpoint.

A useful counterfactual is to constrain current discretionary capture to the normal ceiling, then test whether later eligible solar can match the EV energy of the exceptional-capture alternative without sacrificing other required outcomes, increasing grid reliance for the replacement or degrading protected ESS resources. Actual required trip charging remains permitted in both alternatives, including above 80% where needed.

For this diagnostic only, later battery headroom may be assessed up to the physical 100% limit. That asks whether energy could be supplied later if needed; it does not grant or schedule a future 100% charge. This avoids a circular test where the normal 80% policy itself is mistaken for absence of future solar opportunities.

### Result and relationship to the economic model

- If the useful extra opportunity can be replaced later, retain the normal discretionary ceiling for the current opportunity.
- If it cannot be fully replaced, permit the exceptional ceiling, subject to the economic comparison and all other constraints.
- Permission up to 100% remains an upper bound. The joint scheduler may select less or zero; no fixed 100% charging obligation is generated.
- The decision is based on the opportunity and a consistent reference snapshot. Do not revoke its rationale solely because successful capture removed the candidate's surplus. Reassess when actual state or relevant inputs change.

The seven-day replacement test does not authorize forecast-dependent indirect imports beyond the separate 24-hour comparison or ordinary ESS grid charging. The same visible forecast assumptions and supported uncertainty treatment must be used consistently; no new confidence percentage or arbitrary insurance purchase is introduced.

### Acceptance examples and open engineering details

1. Ample later solar, EV home and sufficient feasible charging capacity: stay at the normal ceiling.
2. Ample later solar but the car is away during every usable window: that solar cannot establish replaceability.
3. Later solar is fully committed to other protected requirements: do not count it again for the exceptional-ceiling decision.
4. Today's solar is the only adequate opportunity in the horizon: exceptional capture is permitted, with the selected quantity still chosen economically.
5. A trip requires 100% before later solar arrives: the required trip target governs independently of this discretionary test.
6. Current SoC already exceeds 80%: do not discharge merely to enforce the normal ceiling; this test governs additional discretionary charging.

Before implementation, encode the potential-opportunity and replacement comparisons precisely, define their checkpoints and numerical tolerances, and test interactions between several opportunity windows. Count the auxiliary calculations in the runtime budget and reuse results only while their input dependencies remain valid. This is a concrete proposed direction, not proof that the required calculations are cheap or that all temporal interactions are solved.

## Feasibility, objective order and bounded calculation — technical proposal

### Normal and infeasible operation

1. Physical constraints and execution permissions remain binding. Monetary benefits and task priority cannot override them.
2. Seek a plan satisfying all required outcomes within their actual deadlines. Normal economics operates inside that feasible set; it does not assign a price to missing an otherwise feasible trip.
3. If those requirements are demonstrably incompatible with the permitted resource model, select best effort by task priority, then deadline among equal-priority goals. For each such tier/checkpoint, minimize its battery-energy shortfall before trading off lower tiers or monetary cost. Retain original goals and explicitly report deficits.
4. Compare economics only after the achieved service level is established. Optional capture cannot buy priority by increasing its monetary inventory credit.

Canonicalize duplicate/overlapping constraints on the same resource and checkpoint. Daily 50% and a trip target of 70% at the same time require one battery trajectory reaching 70%, not 120% worth of separate charging. At different priorities, protect the higher-priority bound first and then improve the remaining outcome; do not count duplicate goals as extra votes.

Shortfall is an explicit fallback variable for desired outcomes, not permission to violate physical battery energy or invent a completed journey. If insufficient departure energy makes the expected travel withdrawal physically impossible, mark the post-trip energy forecast unknown/conditional. Do not subtract it into a negative battery or silently assume charging away. Require actual state reconciliation before dependent instructions can execute.

Distinguish an uncontrollable forecast overrun from a controllable authorized load. A load forecast may exceed a limit even with every eligible controllable load reduced. Report that issue and preserve useful permitted control; do not make its predicted peak available as a newly incurred allowance. Intentional ESS precharging that raises today's peak to reduce such an overrun is allowed under the specific exception below.

### Economics followed by one operational polishing pass

After service/permissions are fixed, minimize the common whole-system economic score. Retain the best validated feasible result. A further bounded pass may improve continuity, ESS throughput and stability within a small explicit tolerance.

Proposed conservative initial tolerance: at most **EUR 0.02 extra over the complete compared plan**, and at most EUR 0.02 extra in predicted cash charges, relative to that run's best economic reference. Do not multiply it by the number of tasks, optimization stages or repeated replacement attempts. This is an initial engineering setting derived from the user's acceptance of a couple of cents a day; its adequacy should be checked against actual scenarios. It is not a guaranteed bound on realized daily bills under changing forecasts.

Use one documented operational score covering unnecessary EV starts, phase changes, power variation, ESS throughput and deviation from still-valid instructions. Normalize its terms and record their contributions; choose/test numerical weights against the acceptance cases rather than hiding them in an arbitrary import-timing discount. Existing actuator transition protections remain hard regardless of score. A simpler plan may replace an equally cheap incumbent.

Include earlier useful completion for required charging when waiting has no source/cost benefit. Do not replace that explicit readiness preference with a generic discount on future imports. Waiting remains appropriate where useful PV or other real savings justify it. Exact normalized weights are engineering work to validate, not a new household preference question.

### One budget across the calculation

All required/reference, joint opportunity, ceiling-diagnostic, best-effort and polishing calculations share one wall-clock budget, including construction, validation and persistence. Do not grant every stage a fresh full timeout. Choose the initial total budget from representative benchmarks; no numerical runtime guarantee is established here.

Prioritize obtaining a valid useful plan. Reuse an accepted plan as a solver incumbent only after checking its relevance. Skip optional polishing or diagnostic refinements when the remaining budget cannot support them; leave unvalidated discretionary actions disabled. Continue the accepted valid instructions and fast control throughout.

Record time-limit status separately from mathematical infeasibility. A time-limited run with a feasible incumbent can produce a candidate for validation; a time-limited run with no feasible incumbent establishes neither impossibility nor permission for a higher peak. Do not convert solver difficulty into a request to spend more money. This distinction is explicit in [HiGHS model and solution statuses](https://ergo-code.github.io/HiGHS/dev/structures/enums/).

## Forecast quality and completion margins — technical proposal

Keep the real goal and deadline visible. Proposed initial EV completion margin: **15 minutes**, labelled an uncalibrated starting value and shown alongside how much usable margin the selected plan actually provides. It does not increase the requested SoC, replace the real deadline with an earlier hard deadline or require buying extra grid energy as insurance.

Seek earlier completion where energy sources and permissions allow it. If the margin cannot be achieved without the prohibited insurance purchase, retain the feasible original-deadline plan and show the reduced margin. Expected energy shortages in the ordinary forecast remain legitimate required charging needs; avoid conflating them with an extra uncertainty buffer.

Calibrate charging efficiency/duration models from observed progress, then estimate a conservative upper-tail completion-time error from comparable episodes. Exclude or separately classify user cancellations, disconnections, changed targets and known protective interruptions; do not learn that the original deadline no longer matters. Retain issuance-time predictions and actual progress rather than comparing actuals with revised hindsight forecasts. Publish sample support and uncertainty; exact sample sufficiency and the adaptation rule need evidence before implementation.

Each critical input carries its observation time, expected update cadence and quality status. Treat measured, estimated, stale and unknown states distinctly. Numerical freshness thresholds depend on the actual integrations' cadence. Do not replace missing solar with a confident zero forecast or missing EV SoC with an invented precise battery state.

Restrict only affected instructions when an input no longer supports their physical/source/peak assumptions. Preserve unaffected work and local actuator protection. Before new conditional instructions execute, require current evidence sufficient for their permissions and reservations. Data-quality problems are not proof of goal infeasibility.

## Authorized ESS precharging that intentionally raises a peak

The user explicitly allows ESS grid precharging to incur a smaller peak now to avoid a larger forecast household peak, even without an EV requirement needing the extension. This may happen automatically within the configured automatic ceiling, or the already-incurred monthly peak if higher. The avoided peak must be within the next **24 hours**.

Require a comparison against feasible continued operation without deliberately increasing the earlier peak. The proposed intervention must reduce the predicted maximum billable peak over that window and improve the combined economics after import/export costs, losses and residual-energy values. An EV inventory credit alone cannot establish this ESS exception: the predicted avoided capacity peak is an essential part of its purpose. Above the normal authorization boundary, task-specific approval is still required.

Illustrative physically consistent case, not measured installation data:

- Existing monthly peak/baseline: 2.5 kW; example configured automatic ceiling: 4 kW.
- Empty usable ESS, current uncontrolled demand 1 kW for a quarter-hour, followed immediately by a forecast 5 kW household quarter-hour.
- Assume 95% charge and discharge efficiencies and a 2.5 kW AC converter limit.
- Keeping current import at 2.5 kW permits 1.5 kW of ESS charging. Later import is about 3.65 kW despite discharging that energy.
- Allowing current total import about 3.10 kW permits about 2.10 kW of ESS charging, which reduces the later import to about 3.10 kW. Both converter directions stay below 2.5 kW.

The second plan deliberately incurs a smaller peak now to avoid a larger forecast peak later. The user permits this automatically under the conditions above. The later peak remains uncertain; no anticipated peak is treated as already incurred. This is distinct from the deferred standing reserve for unforeseen loads.

### Explanation and notification

Always expose the deliberate increase and its reason: for example, "ESS precharge: allow about 3.1 kW now to avoid a forecast 3.65 kW peak before [time]." Show the expected peak/cost comparison and the forecast context; do not describe predicted savings as realized savings.

The user suggests a notification may be appropriate. Proposed default: one informational notification when this intervention is adopted, with material revisions updating the same decision rather than creating repeated notices. It is not an approval request for an action already within the automatic boundary, and it does not block permitted execution. The exact notification default remains a proposal rather than an independently confirmed preference.

Ordinary successful peak suppression below the incurred baseline remains quiet. This additional explanation/notification concerns deliberately creating a new peak through a forecast-driven intervention. Record actual import/peak outcomes and forecast revisions for subsequent review.

## Behaviour and explanations

Default to continuous, understandable task execution. Power and phase changes can happen within a task, respecting existing actuator protections. Prefer less ESS throughput and fewer unnecessary reversals among similarly priced plans, without inventing a monetary wear cost or a daily cycle quota.

Start required charging early when waiting brings no useful benefit. Wait when later solar or other actual cost benefits justify it. Reduce power before pausing when the goal remains achievable. Explain meaningful pauses; roughly an hour was the user's example of a pause rather than a distinct session. A provisional five-minute expected minimum for optional EV starts is not a universal minimum for all operation or a barrier to protective stops.

For optional EV capture, retain the configurable normal 80% and exceptional 100% ceilings. Look over the full horizon for realistic replacement opportunities. Useful surplus may be captured without a known trip consuming it inside that horizon. This is not a standing instruction to buy enough energy to reach those ceilings.

The user confirms that EV energy remaining beyond the seven-day horizon should be valued equally to other charged EV energy. Use a consistent valuation across the boundary, while avoiding double-counting benefits already represented in horizon purchases. Exact monetary accounting remains to be specified; equal valuation does not expand source or peak permissions.

Optional direct grid charging remains prohibited. Preferential PV allocation that causes indirect household imports needs a cheaper combined outcome justified over rolling 24 hours. ESS grid charging for peak avoidance likewise needs a relevant predicted peak within 24 hours and an economic benefit after losses. The exact source-accounting/comparison formulation remains open.

Display household goal and progress separately from execution sessions, with the reason for a task and, where useful, why its timing/source was chosen. Keep predicted benefits distinct from measured results.

## Peak permissions and human decisions

Use the actual incurred monthly peak with the billing floor as the cost baseline. A configurable absolute automatic ceiling is available only to eligible required goals. An actually recorded higher peak becomes reusable; a proposed peak does not.

Immediately signal a likely permission problem when creating/changing a task or when circumstances materially change. Do not impose the discarded 12-hour waiting rule. Explain the assumptions, proposed limit and consequence; allow approval, rejection or task revision. Avoid duplicate requests for unchanged issues.

Continue permitted best effort while awaiting approval. Approval is task-specific permission, not an instruction to spend the full allowance. Ordinary rescheduling does not remove it while the approved goal and limit remain unchanged. Early forecast risk must not be described as a physically unavoidable peak.

## Concrete handoff acceptance cases

These are expected behaviours to test during separately authorized implementation. They are not claims of completed solver validation.

| Case | Setup | Required outcome |
| --- | --- | --- |
| Overnight continuity | Grid needed, no useful later solar, feasible peak-limited EV charging | Start early enough for useful readiness and use continuous operation where equally economic; avoid unexplained session gaps. |
| Useful solar wait | Solar before the real deadline can meet the goal | Allow waiting; do not buy extra grid energy solely to create the provisional margin. |
| Measured solar dip | EV running; ESS has permitted headroom | Cover brief dips, smooth ordinary EV changes, and reduce/stop immediately if quarter-hour protection requires it. |
| Independent DC charge | Empty ESS with adequate physical charge capacity; DC and AC PV both available | Allow combined charging above 2.5 kW while respecting the MultiPlus AC limit and every other device constraint. |
| Required-goal overlap | Daily 50% and trip 70% at the same checkpoint | Reach 70% on one shared trajectory; preserve both reasons without duplicating energy. |
| Optional sources | No eligible PV/ESS; required EV deficit zero | No discretionary grid charging, regardless of residual-energy credit. |
| Partial capture | A source/SoC bound permits only part of an opportunity | Select the feasible beneficial quantity, including zero; do not enforce the original maximum as demand. |
| Optional peak increase | Extra capture is profitable only by independently raising the protected peak | Reject the discretionary increase; automatic allowance is not available merely because the whole-system score improves. |
| No permission response | A task needs an extension; approval remains pending | Keep permissible best effort running and retain the request without blocking the scheduler. |
| Physical impossibility | Charger/availability cannot deliver the requested energy even with higher grid permission | Report the shortfall; do useful best effort and do not ask for a financially costly extension that cannot help. |
| Event during solve | EV disconnects or a goal/approval changes before a result returns | Restrict affected instructions immediately; stale results cannot restore them. |
| Unknown post-trip state | Travel needs external charging or exceeds feasible departure energy | Do not invent a return SoC; reconcile before executing instructions depending on it. |
| Solver time limit | Calculation ends with or without a feasible incumbent | Validate an available incumbent; otherwise retain valid instructions and report planning status, not proven infeasibility. |
| Cost versus assets | Optional EV capture raises cash imports but leaves more useful energy | Compare both residual inventories, count the joint benefit once and display bill/asset components separately. |
| Normal/exceptional ceiling | Later PV is abundant, absent, inaccessible or committed elsewhere | Apply the opportunity test with real availability/routing constraints; required trip targets remain independent. |
| ESS deliberate smaller peak | Precharging inside 24 hours raises today's peak but reduces a larger forecast peak within the configured boundary | Permit the economical intervention automatically; always explain the deliberate increase and keep notification deduplicated if enabled. |

## Input evidence required for implementation validation

- An authoritative resource/actuator capability snapshot: usable battery capacities, SOC conventions, allowed operating modes and transition limits, independent AC/DC constraints, phase limits and available efficiencies. Extract existing configuration/capability data where possible instead of asking the user to transcribe settings.
- Current tariff coefficients, actual incurred monthly peak and current quarter-hour energy, including their measurement/time conventions. Historic exports are evidence of past values, not proof of current configuration.
- Issued PV/load forecasts, matching measurements, connection/SoC observations and actual charging progress with timestamps and quality. Identify coverage and curtailment before treating forecast errors as model errors.
- Frozen requirement, approval and accepted-plan revisions for representative decisions. The existing exported plan alone lacks the native decision record needed to reconstruct every original input or diagnose the historical fragmentation fully.

Configuration values can establish an initial model; actual efficiency, freshness and completion-error data must then support calibration. No new live data access, installation or application experiment is authorized here. Architecture documentation can define the protocol and assumptions; actual solver benchmarks and hardware validation belong to the implementation work.

## Work still needed before implementation handoff

- Complete the technical proposals above: calibrate the reference valuation coefficients, encode the causal source audit, define precise conditional-strategy eligibility and rolling comparison windows for interacting actions, and validate joint comparison/runtime. The accounting arithmetic is checked; the solver formulation is not yet implemented or validated. Both the EV horizon-boundary valuation principle and inclusion of useful residual energy in the 24-hour comparison are settled.
- Encode and validate the proposed exceptional-ceiling opportunity test, including the distinction between diagnostic future capacity and executable charging permission. The user's 80%/100% preference and full-horizon lookahead are already settled.
- Validate the now-authorized ESS precharging exception and its counterfactual peak/cost comparison. The 24-hour limit, automatic permission within the configured boundary and mandatory explanation are settled; the proposed informational notification default remains to be finalized.
- Review and encode the proposed best-effort/operational ordering and conservative initial cost tolerance. Validate operational weights against the concrete cases without creating many full-budget refinement stages.
- Complete the integrated planning/control details in components 3–5: exact numerical adjustment envelopes, shared-resource validity checks, state/plan tolerances, latency limits and which validation paths require a full solve. The user has reviewed the overall contract as fair; numerical bounds and latency/quality checks still need validation.
- Obtain/declare the input capability and data-quality evidence above. Calibrate the proposed margin/efficiencies where evidence supports it; do not present the initial 15 minutes as a measured reliability guarantee.
- Validate feasibility, cost and runtime on frozen representative scenarios. Include overnight EV continuity, solar dips and peak protection, DC solar with a partly empty ESS, competing/partial optional opportunities, closely spaced trips, missing returns, approval decisions and events during a solve.
- Define observable pass criteria and required inputs for EV departure during a solve, approval granted/rejected during a solve, forecast revisions, actual ESS shortfall, a peak emergency affecting several instructions, reconnection with a different SoC, and optional advancement competing with a protected ESS allocation. Actual implementation tests and runtime measurements require separately authorized implementation/validation work.
- Use stage timings and solver quality to diagnose performance. Five-minute planning and new constraints are not proof of acceptable runtime. Existing exports do not establish the original fragmentation cause; its native decision record was missing.

This draft proposes an extensible architecture while making the initial operational scope smaller. Deferred features remain documented rather than silently removed from the design.
