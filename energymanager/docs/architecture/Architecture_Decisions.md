# Architecture decisions

> Preserved original design reference. Read [the current handoff](../HANDOFF.md),
> [decisions](../DECISIONS.md) and [shipping specification](../SPECIFICATION.md) first.
> Historical pending-work statements and chat restrictions are not current instructions.


This folder records decisions from the architecture discussion. It is not authorization to implement changes. Application code, configuration, deployment and hardware control remain outside this chat's scope. Earlier context is in `../handoff/references/`; investigation findings are in `../analysis/Investigation_Report.md`.

## 22 October 2026 — Opportunistic EV charging ceilings

Confirmed by the user:

- Opportunistic charging has two levels: a configurable normal ceiling, initially 80%, and an exceptional ceiling of 100%. These are permissions for conditional charging, not perpetual charging obligations. Required trip targets can independently justify 100%.
- Avoid repeatedly charging to 100% when future surplus makes that unnecessary. The earlier 70% example was illustrative; no lower cycling threshold was specified.
- An exceptional surplus opportunity may justify capturing the additional energy up to 100% when equivalent future charging opportunities are lacking. The user's winter example means we **should not** forgo that energy solely to avoid reaching 100% on a rare occasion.
- Assess upcoming opportunities over the **full current scheduling horizon**, rather than only the next day. Count only opportunities compatible with the car's expected availability and the other constraints and commitments.
- Retain the current seven-day horizon for this design. Its forecast usefulness is an open empirical question, deferred to a later release; see `Deferred_Work.md`.

Still open: the precise economic/energy test for choosing the exceptional ceiling, treatment of uncertainty at different lead times, and conditional-task selection/lifecycle. Looking across the full horizon does not establish that distant forecasts are equally accurate or reliable.

Technical progress: the main architecture draft now proposes an opportunity/replacement comparison for this ceiling, with availability, conversion capacity, competing requirements and corresponding ESS state included. Its encoding, checkpoints, numerical tolerances and runtime remain to be validated; the existing behavioural preference is not reopened.

## 22 October 2026 — Indirect grid imports for optional EV charging

- The user provisionally allows optional direct-PV EV charging to leave less ESS energy for household loads and consequently cause household grid imports, **if the combined result is cheaper**. Source restrictions therefore cannot be interpreted as an unconditional ban on every indirect grid-import effect of optional charging.
- Cap the economic justification for this exception to a **rolling 24 hours**, explicitly confirmed by the user, because confidence in longer-range models is currently insufficient. This window crosses midnight where appropriate.
- Keep this short economic comparison distinct from the full-horizon lookahead for future charging opportunities used in the 80%/100% ceiling decision. It does not shorten the entire scheduling horizon.
- Existing required outcomes and peak permissions remain applicable. The exception does not authorize grid energy to be directly assigned to optional EV charging or override protected commitments.
- Explain this reason in the task/GUI **at the time the task is created or scheduled**. Preserve the originating rule, forecast/input context, relevant time window and expected combined cost benefit against the considered alternative. Revisions should make changed reasoning inspectable. Do not invent a reason afterward from coincident flows or present predicted savings as realized results.

Still open: the exact comparison/reference method and how its expected benefit is kept valid as the schedule changes. This decision does not by itself resolve conditional-task circularity.

## 22 October 2026 — Monthly peak target and approval boundary

Confirmed direction:

- Normal planning seeks to avoid increasing the already-incurred billable monthly peak, using the 2.5 kW billing floor when the observed peak is lower. These refer to quarter-hour average import, not instantaneous power spikes.
- A configurable absolute automatic ceiling (4 kW was the user's example) permits increases above the current baseline only when needed to meet important required goals. This is not a recurring allowance added on top of every new observed peak. The exact configured value has not been finalized.
- A planned increase above both the configured automatic ceiling and the actual recorded monthly peak requires user approval.
- If an actual event has already raised the monthly peak above the configured ceiling, the scheduler may use that new observed level without further approval. The user sees no reason to restrict use below a peak whose cost is already incurred. Thus the automatic authorization boundary is the greater of the configured ceiling and the actual monthly peak; it does not become that peak plus an allowance.
- Only an actually recorded peak changes this sunk-cost baseline automatically. A proposed or forecast peak is not equivalent to an incurred peak. Existing physical constraints remain applicable.
- Continue to minimize combined cost and use only a justified peak increase; permission to reach a ceiling is not a target to reach it.

Priority discussion is provisional: the user accepts protecting an EV departure requirement over DHW comfort during genuine infeasibility, while preserving the distinct minimum-reserve goal where feasible. General goal rankings, the definition of an important goal qualifying for automatic peak increases, approval details and notifications still need design. Do not silently soften ordinary deadlines for cost savings.

### Goals eligible for the automatic peak allowance

- Both the configurable daily EV minimum (initially 50% by 07:00) and explicit calendar trip requirements qualify when necessary to meet their deadlines. Opportunistic EV charging above those requirements does not qualify.
- Neither the DHW minimum usable reserve nor its comfort-window requirement qualifies for an automatic peak increase. They can use the already-incurred monthly baseline, with the billing floor, but cannot independently invoke the higher automatic allowance.
- The user subsequently also permits economical ESS precharging that deliberately incurs a smaller peak now to avoid a larger forecast household peak within 24 hours. It may use the configured automatic ceiling, or the actual monthly peak if higher. Above that boundary, approval is still required. See the dedicated decision below.
- Disinfection completion and margin policies remain deferred; the DHW question above covered only minimum reserve and comfort.

### General fallback for requirements that cannot be fully met

Confirmed by the user:

- Where feasible, continue best-effort execution within existing authorized limits instead of doing nothing because full completion is infeasible.
- Signal the issue and request approval of extended limits needed to achieve the requirement. DHW is explicitly covered by this rule, despite not qualifying for an automatic extension.
- Preserve the original requested outcome and deadline, and identify unmet or at-risk requirements. Best effort is a response to a conflict, not permission to quietly weaken targets during normal economic planning or learn that lateness is an acceptable intended outcome.
- Until approval is granted, the current authorization boundary remains in force. Physical device constraints remain binding regardless of approval.

Still open: approval scope, duration, cancellation/revision behaviour and how to compare and display proposed extensions. Actual observed peak increases continue to update the monthly baseline under the rule above.

### Approval scope clarified

- Approval applies to the requesting task and its approved peak limit; it does not change the configured automatic ceiling for all tasks.
- Ordinary forecast updates and rescheduling do not invalidate that approval while the task's goal and approved limit remain unchanged.
- Once the higher peak is actually recorded, other tasks can use the newly incurred monthly baseline as already agreed.
- A pending approval never blocks planning or best-effort execution within existing authorized limits. The request may take minutes, hours or receive no answer; only use of the proposed extended limits waits.

## 22 October 2026 — Schedule updates and continuity of execution

- Do not add a separate quick initial scheduling pass merely to start a new task while the full calculation runs. The user accepts a delay of a couple of minutes in most cases. Consistently excessive calculation time should be addressed directly; no exact runtime threshold is fixed yet.
- Continue executing still-valid parts of the accepted schedule during recalculation. Adopt a replacement when it materially improves the plan or restores feasibility.
- An event does not automatically void the entire plan. Immediately suspend, restrict or stop only affected execution instructions, extending the affected set when shared resource constraints require it. Keep the underlying task goals and progress unless the actual need is cancelled.
- EV disconnection invalidates its charging instructions, not unrelated tasks. Threatened peaks can require immediate reductions or pauses across multiple eligible loads. Reduce power before pausing where feasible, consistent with the earlier behaviour discussion.
- A forecast update alone triggers replanning without necessarily invalidating existing instructions. Fast coordinated control handles current deviations within authorized bounds while calculation proceeds.
- ESS operation continues during planning. With a usable plan, respect its still-valid explicit energy reservations and instructions. Without a usable plan, basic operation absorbs available PV and reduces grid import within physical limits. Deliberate forecast-driven interventions still require scheduling authority.
- Other tasks may continue only where their resource assumptions and constraints remain valid; local invalidation is not a guarantee that every other instruction remains valid automatically.

The precise scheduler/fast-control interfaces and validation mechanism remain to be designed. These are behavioural requirements, not an implemented controller.

## 22 October 2026 — Requirement generators and conditional opportunities

The user accepts the following separation:

- Calendar and policy generators define household requirements independently of the selected energy schedule, such as EV departure targets and DHW comfort requirements.
- Discovery and selection of conditional tasks belong inside the scheduler's planning process. A headroom/surplus rule needs a provisional plan and its predicted resource trajectories to assess whether an opportunity exists.
- A conditional rule may propose a purpose, conditions and maximum energy quantity. The scheduler determines the actual selected quantity, which may be smaller or zero, while evaluating complete alternatives and permitted changes to other tasks.
- Only selected conditional actions become executable scheduled tasks, with meaningful names and their reasons recorded before execution. This preserves the rule that actuators do not independently create and schedule new tasks.
- A successful intervention must not be cancelled solely because its own effect removed the surplus. Its contribution needs comparison with an alternative without that intervention, using consistent inputs and constraints. The exact comparison/reference method remains open.

This is an agreed responsibility boundary, not proof that iterative planning converges or that any particular search/optimization method will be fast or optimal. The scheduling engine, opportunity catalogue and joint selection/comparison mechanism remain undecided.

### Permitted origins and understandable reasons for every task

- The user accepts a defined catalogue of permitted conditional strategies for the first version, with later expansion when a useful missing strategy is identified.
- Extend this principle to all tasks: every task has an identifiable origin and understandable reason. A reason may be simple, such as a required outcome or a named EV trip and date; it need not be an elaborate solver explanation.
- Keep the reason a task exists distinct from why a particular timing or source was selected, where the latter matters to the user. Earlier decisions already require the one-day PV-to-EV/indirect-import trade-off to be explained when the task is scheduled.
- Exact catalogue entries, reason presentation and supporting data contracts are not finalized.

## 22 October 2026 — MILP as the current direction to explore

The user is willing to give MILP another attempt in light of the clearer requirements and constraints being developed here. Treat MILP as the current working direction for architecture design, not approval to implement or reuse the existing formulation without reassessment. The earlier option of a simpler scheduler is not evidence of a completed comparison, and this willingness is not proof of improved performance.

The new formulation, objective preferences, conditional-task benefit accounting, model size and validation scenarios remain to be designed. No application code changes, new solver experiments, deployment or hardware action are authorized by this architecture discussion.

## 22 October 2026 — Surplus capture without an existing trip need

- The user permits capturing surplus into the EV even if no currently known trip/energy goal will consume it within the seven-day horizon. A future-use justification is acceptable, subject to the 80%/100% ceilings and other source, cost, peak and commitment rules.
- This still requires a named conditional task selected by the scheduler; absence of a trip need does not authorize the fast controller to create an unscheduled charging task.
- The economic model therefore needs an explicit treatment of useful energy left beyond the horizon. No terminal valuation formula is selected yet. Do not silently reintroduce a standing preferred-SoC obligation or grid shortfall penalty.
- The rolling 24-hour justification limit for indirect household grid imports remains distinct. Its interpretation was subsequently clarified: count forecast-dependent effects inside the window and consistently value useful energy remaining at its end, including EV energy used later. This supersedes the earlier restriction against relying on such residual value.

## 22 October 2026 — Short optional charging sessions and smoother replans

- A one-minute opportunity is too short to justify starting optional EV charging. A standalone 15-minute session is clearly worthwhile to the user for real surplus capture; short sessions are not inherently undesirable when a meaningful supply opportunity explains them.
- The user proposes **five minutes as a justifiable minimum for starting charging** in this optional-capture discussion. Treat it as a provisional expected run-duration threshold to validate, not a finalized universal minimum for every task or a guarantee that solar availability can be predicted at that precision.
- Such a planned-start threshold must not prevent an earlier stop required by disconnection, physical constraints, source/authorization limits or peak protection.
- A revised plan with similar cost may replace a valid current plan specifically to make execution smoother. Continuity improvement can justify replanning even without an economic saving; stability does not require retaining an avoidably fragmented plan.
- The exact meaning of similar cost, treatment of intermediate session durations and detailed preference ordering remain open. A five-minute start threshold does not itself decide the MILP's time grid or require a five-minute grid over all seven days.

## 22 October 2026 — Planning resolution

- The user has now explicitly chosen planning windows of **five minutes at most** for the new architecture. Do not adopt the previously suggested fifteen-minute compromise or a coarser distant-horizon grid by default.
- With uniform five-minute windows, the current seven-day/168-elapsed-hour horizon contains 2,016 physical intervals, including across daylight-saving transitions.
- Keep the distinction between planning resolution and minimum useful charging-session duration: the resolution decision does not create a universal five-minute minimum run for every task or remove immediate protective responses.
- Revisit coarser temporal resolution only if actual issues arise and evidence indicates that fewer intervals could help. Measure the consequences before proposing a change; do not reduce resolution pre-emptively based solely on anticipated computational complexity.

## 22 October 2026 — Initial trip-energy estimation

- The user does not want to maintain a database of previous trips or provide estimated return SoC as the normal trip-energy input.
- In the initial version, use entered trip kilometres and an assumed average consumption. This supersedes the earlier direction of deferring all distance-based estimation: **manual-distance estimation is now in scope**.
- Basic battery-energy estimate: `trip_kWh = entered_km * average_kWh_per_100_km / 100`. Define the average on a battery-consumption basis; charging losses belong in the separate charging model rather than being silently counted twice.
- Calendar entries and recurring schedules remain the source of planned travel. No separate trip-history database or learned driving schedule is required.
- Preserve direct SoC targets as already required for explicit trips; the exact interaction between entered distance, explicit targets and an arrival reserve still needs clarification. The default daily 50% by 07:00 is not a continuously maintained reserve.
- Destination-based distance calculation and temperature compensation are future extensions, recorded in `Deferred_Work.md`. Neither is required to implement the initial distance estimate.

### Journey distance and remaining range reserve

- Use the total expected journey distance, normally including both outward and return travel. The user considers this the clearest representation; do not automatically double a distance already entered as the total.
- Include a configurable minimum remaining-range reserve, initially **30 km**, at the end of the journey.
- With an assumed consumption `c` in kWh/100 km, actual predicted trip withdrawal is `distance_km * c / 100`; the desired energy remaining after the journey is `reserve_km * c / 100`. Required departure energy for that journey is their sum. The reserve is not itself a trip withdrawal and must not be repeatedly subtracted as consumed energy.
- Keep the daily 50% by the configurable default time and explicit calendar requirements as previously agreed; the 30 km arrival reserve does not imply maintaining 50% continuously.

### Journeys requiring charging away from home

- If the journey plus arrival reserve exceeds usable battery capacity, prepare a 100% departure target and clearly flag that charging during the journey is needed. Execution remains subject to physical constraints and the previously agreed authorization and best-effort rules.
- The user arranges charging away from home. This version does not plan charging stops or assume that an external charging session will occur or deliver a particular quantity of energy.
- Do not derive a fictitious return SoC by subtracting the entire journey from one battery charge. Reconcile the vehicle's actual state when it becomes available again; subsequent-trip planning with unknown external charging remains to be specified.

### Explicit SoC requests are manual charging goals

- An explicitly requested SoC is a manual charging goal, without an entered journey distance or location. It need not represent a trip at all.
- Do not infer a departure, subsequent energy withdrawal, return SoC or external charging from that request. Reaching the requested SoC fulfils the charging goal; actual later energy use is observed rather than fabricated.
- This is a manual override of the normal charging goal. The user confirms that it follows the same energy-source and peak authorization rules as other required EV charging: grid use is allowed, the automatic peak allowance is available when needed, and exceeding the authorized limit requires task-specific approval. Physical constraints remain binding.
- A manual SoC request uses the same timing, deadline and scheduling behaviour as a regular task. It does not imply an immediate-start instruction or require a separate execution path.
- Distance-based journey requirements remain distinct from manual SoC charging requests. There is no need to invent precedence between two alternative input modes for the same request.

## 22 October 2026 — ESS wear and unnecessary cycling

- The user generally does not want a monetary battery-wear cost in the objective. Do not introduce a speculative degradation price by default.
- This does not mean arbitrary cycling is acceptable. The architecture must discourage pointless charging/discharging and oscillation while allowing useful ESS operation.
- Confirmed mechanism: model real conversion losses and physical operating modes; among schedules with similar total cost, prefer less ESS energy throughput and fewer unnecessary direction changes. Allow extra cycling when it meaningfully helps meet requirements, capture solar or protect the peak. Do not impose an arbitrary daily cycle quota. The exact preference ordering and cost tolerance remain open.

## 22 October 2026 — Lookahead for ESS grid charging to avoid a peak

- The user confirms that deliberate ESS grid charging for capacity-peak avoidance must be justified by a predicted peak within the next **24 hours**.
- This action must still be economical after import costs, conversion losses and avoided incremental capacity charges, and remain within authorized import limits. A peak below the already-incurred monthly baseline does not create an avoided incremental capacity charge.
- This decision limits the justification for purchasing energy for peak avoidance; it does not shorten the seven-day schedule or automatically impose the same restriction on every ESS reservation or ordinary use of stored solar energy.

## 22 October 2026 — Missing EV return time

- Most planned trips are expected to include a return time. When one is missing, treat the vehicle as unavailable after departure until it actually reconnects or the user supplies a return time.
- Do not assume a midnight return. A fictitious availability window could otherwise cause the scheduler to rely on charging opportunities while the vehicle remains away.
- Show that the return time is unknown and replan on reconnection or entry of a return time. This is an availability assumption, not an assumption about return SoC or energy received away from home.

## 22 October 2026 — ESPAltherma telemetry investigation

The user confirms that tank temperatures and the active hot-water/space-heating function are visible on the unit, but does not know which are exposed through ESPAltherma. Inspection of the upstream project establishes available definitions, not verified telemetry from this installation.

- The ERGA E / EHV-EHB-EHVZ E_EJ definition includes DHW tank temperature R5T, indoor operation mode, DHW setpoint, the DHW-versus-space three-way valve, BUH Step1/Step2 and BSH status. These entries are commented out in the inspected example and require selection in the applicable configuration. The exact definition matching the user's hardware is not established.
- Prefer actual heater-status readings if available and validated, retaining whole-unit power as the measured electrical total. Power-based heater inference remains a fallback.
- Do not equate an operation-mode label or valve position alone with active heat production. Validate using power and operating signals. The outdoor Operation Mode does not by itself distinguish DHW from space heating.
- The stable 1.x README documents selected values published as JSON over MQTT and Home Assistant discovery. It also explicitly states that serial monitoring cannot directly change heat-pump configuration. Telemetry support therefore does not resolve disabling routine backup-heater use.
- Next evidence: the installed ESPAltherma setup and an actual sensor/MQTT sample, followed by synchronized tank-temperature, operating-state and whole-unit power observations over ordinary heating cycles. No firmware, configuration or application code was changed.

Installation status clarified by the user: **ESPAltherma is not installed yet; installation is planned.** Treat those readings as planned inputs, not currently available sensors or historical evidence. Architecture design can proceed, while installation-specific telemetry validation and DHW heating-model calibration remain pending.

The user subsequently confirms that **DHW scheduling is not essential for this release** and explicitly requests recording it for the future. It is deferred as [ARCH-004](../DEFERRED_WORK.md#arch-004--dhw-scheduling-and-heating-model-calibration). Earlier DHW requirement discussions remain useful for that extension; they do not require thermal scheduling in the initial release. In the meantime, retain the unit's existing control and represent its consumption as uncontrolled demand in planning.

Sources checked:

- [ESPAltherma README](https://github.com/raomin/ESPAltherma#readme).
- [ERGA E / EHV-EHB-EHVZ E_EJ sensor definitions](https://github.com/raomin/ESPAltherma/blob/main/include/def/Altherma%28ERGA%20E%20EHV-EHB-EHVZ%20E_EJ%20series%2004-08kW%29.h).
- [Upstream value explanations](https://github.com/raomin/ESPAltherma/wiki/Information-about-Values).

## 22 October 2026 — Per-task priority overrides

- The user wants the option to change an individual task's priority when requirements genuinely conflict, rather than relying exclusively on fixed priorities by task type.
- Normal defaults can favour required EV charging, while an exceptional hot-water requirement can be given precedence over a routine EV charge.
- Priority does not redefine a normally required outcome as optional. Continue to seek satisfaction of all requirements; apply conflict handling when they cannot all be met within the applicable limits.
- The user confirms that priority and eligibility for the higher automatic peak allowance are separate settings. Raising a task's priority does not expand its import authorization or remove the need for approval above its authorized boundary.

## 22 October 2026 — Appliance scheduling deferred

- The user confirms that washing-machine and dishwasher scheduling suggestions are deferred beyond this release. Their previously discussed profiles, timing windows and fixed user-confirmed starts are retained in [ARCH-005](../DEFERRED_WORK.md#arch-005--washing-machine-and-dishwasher-scheduling-suggestions).
- Planned Mazak operation is also deferred, grouped with ARCH-005 for potential addition alongside the other appliances. Its particular constraints remain unspecified; do not assume it can be remotely started or interrupted. Its consumption remains part of uncontrolled demand in this release.
- Continue to account for their consumption in household demand. This scope decision does not remove general task/resource extensibility or authorize implementation.
- The user subsequently also defers automatic recognition of already-running appliances, recorded as [ARCH-006](../DEFERRED_WORK.md#arch-006--automatic-recognition-of-running-appliances). Include their consumption in the uncontrolled household-demand forecast for this release.
- The resulting scheduling scope is EV and ESS, with DHW and other appliances represented as uncontrolled demand. Keep the task/resource architecture extensible for the deferred features.

## 22 October 2026 — Advanced forecasting deferred

- The user has consulted the ML specialist. The resulting ideas need considerably more stored historical data and exceed the complexity desired for this release.
- Record them for later work as [ARCH-007](../DEFERRED_WORK.md#arch-007--advanced-forecasting-ideas-from-the-ml-specialist). The user identifies the direction as **foundation models for forecasting**; no specific model or exact data needs have been supplied here.
- Advanced ML forecasting is not a dependency for this release. This decision does not establish that existing forecasts are sufficiently accurate or remove the need for forecast-quality visibility and the previously discussed uncertainty treatment.

## 22 October 2026 — Timing of peak-limit approval requests

- **Superseded:** the initially proposed rule to wait until at most 12 hours ahead before requesting approval is replaced by the event-driven approach below. No deadline-versus-start anchor for that discarded rule needs selection.
- On task creation or modification, assess feasibility under existing permissions. If the plan indicates a likely need for a higher peak, signal it promptly and allow the user to approve the task-specific extension, reject it or change the task. Do not delay solely because the requirement is more than 12 or 24 hours away.
- Changed circumstances, including changed solar forecasts, can also justify a new approval request when they create a need for an extension. The user's examples of advance-known pressure are closely spaced EV trips and Mazak operation; the Mazak's input representation and release scope are not yet specified.
- Continue an executable best-effort schedule within existing permissions while approval is pending or declined. A proposed extension remains separate from executable instructions and does not count as an incurred monthly peak.
- Earlier approval remains permission, not an obligation to raise the peak. Ordinary forecast changes do not invalidate an existing task-specific approval while its goal and approved limit remain unchanged; use a higher peak only if still justified.
- Distinguish a forecast risk from a demonstrated shortfall under the model's current assumptions. Quantitative confidence thresholds and request deduplication/update behaviour remain to be designed; do not call an uncertain solar forecast proof of an unavoidable peak.
- This revision concerns approval timing only. It does not change the separate rolling 24-hour justification limit for ESS grid charging to avoid a peak.

## 22 October 2026 — Storage capacity assumption

- Plan deployment around having enough storage for the system's required data. The user does not want anticipated storage scarcity to constrain the architecture in advance.
- If storage capacity later becomes insufficient, address that operational issue then. Do not infer an agreed retention duration, automatic deletion policy or permission to silently drop diagnostic/learning records.
- Exact record contents, retention tiers and measured storage requirements remain design work. Advanced forecasting remains deferred; this decision does not authorize implementing data-collection jobs in this chat.

## 22 October 2026 — Unplanned-trip recovery rule withdrawn

- The user considered an automatic earlier reserve-restoration goal after an unplanned trip, then explicitly withdrew it. Do not implement or retain it as an unresolved requirement.
- The user does not see a defensible target or deadline for such a goal. Existing surplus-capture rules can use available solar; a substantial upcoming journey should be explicitly planned. Returning alone does not justify substantial or high-power charging.
- Retain the morning reserve, explicit trip/manual goals and permitted conditional surplus capture. The daily 50% rule is not a continuously maintained floor, and reconnection does not create a separate daytime restoration obligation. Reconnection still updates availability/state and triggers ordinary replanning as appropriate.
- The user wants the discussion to resolve remaining architecture/formulation and validation work before implementation handoff; the draft is not a finished design or authorization to implement.

## 22 October 2026 — Value of EV energy beyond the planning horizon

- The user says unused EV energy can be valued equally to other charged EV energy. Apply a consistent unit-valuation rule; energy must not become worthless merely because its use lies beyond the seven-day horizon.
- This establishes continuity of valuation across the horizon, not a separate standing charge target. The 80%/100% policy, source restrictions, peak permissions and rolling 24-hour rule for indirect imports continue to apply.
- The precise monetary accounting remains to be formulated. Do not infer that every stored kWh is independently proven to replace a future grid purchase; future solar is still uncertain. Avoid double-counting a benefit already represented through reduced purchases for requirements within the horizon.
- The user subsequently reviewed the planning/fast-control contract as fair and requested integrating it into the main architecture document. Its content now lives in components 3–5 of [Architecture_Proposal.md](Architecture_Proposal.md); the separate contract file was removed. Numerical details and experimental validation remain open.

## 22 October 2026 — Future ESS reserve for unplanned peaks

- The user requests considering an ESS reserve for unplanned load peaks as future work, recorded as [ARCH-008](../DEFERRED_WORK.md#arch-008--ess-reserve-for-unplanned-load-peaks).
- Keep this separate from current forecast-specific ESS reservations and the actuator's physical minimum SoC. No standing reserve amount, replenishment rule or implementation is agreed for this release.

## 22 October 2026 — Whole-system comparison accounting under specification

- The user agrees that counting conversion losses, capacity costs and actual energy makes sense across tasks.
- A common comparison formula and joint reference/candidate mechanism are now proposed in [Architecture_Proposal.md](Architecture_Proposal.md#whole-system-economic-comparison--proposed-calculation). They are technical proposals, not yet a validated solver formulation.
- Proposed accounting charges imports, subtracts export income, includes only incremental household capacity costs and values the change in useful stored energy once. Physical losses enter energy balances rather than a duplicated loss penalty.
- The user accepts the assistant's recommendation to include useful residual energy at the 24-hour boundary. Limit forecast-dependent operating effects and cash flows to the window, while applying the agreed stored-energy valuation at its end. Extra EV inventory can therefore justify some indirect household imports even if used later. This supersedes the earlier stricter interpretation; it does not permit direct optional EV grid charging or remove peak/commitment constraints.
- Show assumed residual-energy value separately from predicted cash bills and realized savings. The draft now proposes efficiency-adjusted replacement-value coefficients as an initial engineering model; reference efficiencies, calibration and sensitivity checks remain work before implementation.
- The main draft now specifies variable optional quantities, a proposed causal guard for required versus optional EV grid energy, and source/quantity acceptance cases. It includes an arithmetic example of zero, partial and maximum eligibility/capture; this is an idealized check, not an application solve or real-world performance evidence. These technical proposals still need formulation and validation.

## 22 October 2026 — Further technical specification and one open permission choice

- The main architecture draft now proposes priority/deadline best effort, one bounded operational polishing pass, a shared whole-cycle calculation budget, explicit solver-status handling, input-quality requirements and a concrete acceptance matrix. These are proposed implementation specifications; no solver or application test was run.
- Proposed engineering starting values are a conservative EUR 0.02 full-plan/cash tolerance for polishing and a visible uncalibrated 15-minute EV completion margin. They are not newly confirmed household preferences or guarantees of actual bills/reliability. They preserve the user's earlier limits on smoothing costs and prohibit extra grid insurance purchases solely for the margin.
- A permission case was identified and subsequently resolved by the user: intentionally raising today's peak through ESS grid charging to avoid a larger forecast uncontrolled peak is allowed within the automatic boundary, with a 24-hour lookahead. The main draft includes a physically consistent illustrative comparison (about 3.10 kW now/later versus about 3.65 kW later when charging stays at the existing 2.5 kW baseline).

## 22 October 2026 — Automatic ESS precharging for a smaller predicted peak

- The user allows this edge case automatically, with the same short rolling **24-hour** lookahead used earlier. This extends automatic eligibility to the named ESS peak-avoidance intervention, without changing the configured ceiling or requiring an EV goal.
- The intervention must actually reduce the predicted peak compared with feasible continued operation without the deliberate early increase, and remain economical after losses and other household effects. A forecast peak is not an incurred baseline.
- The deliberate increase must always be explicitly explained. The user suggests that a notification may also be appropriate. The architecture proposes one deduplicated informational notification on adoption, separate from approval requests and routine quiet peak suppression; that precise notification default has not been independently confirmed.
- This is forecast-driven precharging for a specific peak, not the standing reserve for unplanned peaks deferred as ARCH-008. No control, notification or implementation was performed in this chat.

## 22 October 2026 — DHW backup-heater modelling gap

- The user identifies the resistive backup heater as the only physically plausible source of the observed approximately 4 kW DHW peaks. This is installation information supplied by the user, not an independently verified mode trace.
- It remains unresolved whether the Daikin can be configured or controlled to avoid routine backup-heater use for DHW. Do not assume independently selectable heat-pump-only operation or guaranteed suppression of the backup heater.
- DHW scheduling must account for the observed electrical demand, including backup-heater operation where applicable. A later confirmed change in available operating modes can improve the model without changing the household requirement/task architecture.
- Only whole-unit electrical measurement is available. The user reports that normal heat-pump and backup-heater demand differ substantially, making backup activity distinguishable by power level. Separate electrical metering is not a prerequisite for the architecture.
- Treat backup activity derived from power as an inference, not a separately measured heater channel. Validate the distinction with recorded operating cycles; do not invent a precise switching threshold or assume whole-unit demand belongs exclusively to DHW.
- Needed evidence includes heating-state/temperature and electrical-demand observations sufficient to distinguish DHW heating from space heating and identify when backup demand occurs. Availability of tank-temperature and DHW-active telemetry remains to be established.
