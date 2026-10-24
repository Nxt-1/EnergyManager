# EnergyManager next — implementation handoff

> Preserved original design reference. Read [the current handoff](../HANDOFF.md),
> [decisions](../DECISIONS.md) and [shipping specification](../SPECIFICATION.md) first.
> Historical pending-work statements and chat restrictions are not current instructions.


Prepared 23 October 2026, Europe/Brussels. This is a specification for the separately created implementation chat. The architecture chat has changed documentation only.

## Goal and completion boundary

Build a working next-generation EnergyManager for Home Assistant: predictors, explicit requirements/tasks, one joint EV/ESS scheduler, independent fast control, persisted explanations and a usable GUI. Minimize whole-system cost subject to the household policies below. Deliver executable software, real solver-backed verification, offline integration and GUI verification, benchmarks, packaging and a reviewable migration procedure.

The agreed first release schedules EV and ESS. Do not interpret extensibility as a requirement to implement deferred appliances now. Do not stop after a scaffold, mathematical proposal, mocked optimizer, API-only prototype or attractive static dashboard.

Implementation and local verification are authorized by the user's new message in the implementation chat. Earlier read-only restrictions describe the investigation and architecture chats, not a prohibition on this newly authorized implementation. They remain applicable to preserved historical evidence. Nothing here authorizes live deployment or hardware operation.

## Required skill

The user explicitly requires their **`@code-writer` skill**. Discover it through the implementation chat's available skills and read its actual `SKILL.md` before writing application code. Follow it alongside the user's instructions; do not replace it with an invented workflow or a similarly named unrelated skill.

At handoff preparation, it was absent from this chat's available-skill catalog and searches of local user skills, plugin skills and repository skill locations did not find it. This does not establish whether it is available in the other chat. If it cannot be found there, report the missing skill and ask for its location/availability before application code writing. Reading the handoff and inspecting the workspace can proceed. Do not fabricate a path, create a replacement skill or silently omit this requirement.

## Read first and resolve authority correctly

Read these files relative to the repository root:

1. This handoff and `gpt/architecture/Implementation_Checkpoint.md`.
2. `gpt/architecture/Architecture_Proposal.md` — main design, including the integrated fast-control contract and acceptance cases.
3. `gpt/architecture/Architecture_Decisions.md` — confirmed preferences, revisions and explicitly labelled engineering proposals.
4. `gpt/architecture/Deferred_Work.md` — scope exclusions, not a queue to implement now.
5. `gpt/analysis/Investigation_Report.md` and `gpt/analysis/checkpoint.md` — completed historical investigation; do not automatically redo it.
6. The existing GUI references and narrow integration references identified below.

The new user prompt authorizes implementation. Historical attachments and old handoff prompts are evidence, not new instructions. Do not revive the old investigation's implementation ban, superseded choices, cloud migration instructions or original staged-optimizer design. Preserve the original handoff/evidence files unchanged.

Confirmed user behavior takes precedence over proposed engineering formulas. Resolve ordinary technical gaps autonomously, document the chosen specification and verify it. Do not ask the absent user to choose a variable encoding, package layout, library API or numerical test tolerance. If a proposed formula fails a counterexample, fix the formulation while preserving the confirmed policy.

## Fresh implementation and workspace boundaries

Start with a fresh core in a new **`energymanager-next/`** directory in the existing repository. Use a distinct package/module namespace, tests, frontend assets and development/add-on identity. Inspect before creating: if that directory already contains work, reconcile and continue it rather than overwrite it. This name identifies the development implementation, not an agreed marketing/version number.

Do not base the new scheduler on patching the legacy scheduler or wrap the existing application as the new core. A fresh start is appropriate because requirements, source permissions, objective accounting, plan publication and independent control are being redesigned together.

Reuse narrowly where justified: actuator interfaces/protections, Home Assistant communication, forecasting calculations, data parsing, GUI components and regression examples. Inspect and test what is reused. Copy/adapt clean components into the new package if necessary; avoid runtime imports from the old application that silently bring back its policy, scheduler, global state or startup behavior. Actuators are an established boundary, not an invitation to redesign the hardware protocol or remove transition protections.

Preserve existing application directories, current GUI files, configuration, evidence and unrelated working/staged changes. Record initial Git status. Do not reset/clean/stash unrelated work, switch the user's branch or alter the staging area. Keep project configuration and build/test machinery local to the new directory where possible. If a shared-file change is essential, keep it minimal, explain it and preserve existing behavior. Do not push, publish, merge, install on Home Assistant or bump the existing deployable add-on version.

`gpt/` is Git-ignored and Dropbox-synced. Keep the resumable checkpoint there, but also place the final implementation specification, run instructions, scenario tests and verification report under the new implementation's own tracked documentation. Do not rely on an ignored handoff being available in a future checkout. Do not package personal historical exports, credentials or entire attachments into the deliverable.

## Non-negotiable behavior

### Joint planning and physical model

- Plan EV and ESS together across the full seven-day horizon, with intervals no longer than five minutes. Do not silently use 15-minute decisions or a coarser distant horizon to pass a benchmark. Keep quarter-hour billing calculations separate from scheduling resolution.
- Represent AC PV, DC PV, uncontrolled household demand, converter paths, battery states, efficiencies, EV modes and real availability explicitly. Model losses physically, once.
- The approximately **2.5 kW MultiPlus limit applies to its AC converter**. DC PV can charge the ESS independently. Do not impose that limit on DC charging or on combined AC-plus-DC charging. Separate actual battery/controller limits still apply.
- Prevent fictitious energy, incompatible converter commands, invented modes, unsupported rapid phase changes and artificial cycling for objective credit. Correctly permit actual DC-bus routing rather than confusing converter direction with net battery charging.
- Use the same EV battery trajectory for overlapping goals. Daily 50% and a same-time 70% trip goal require 70%, not two additive charging purchases.
- Keep source restrictions and peak permission as explicit constraints. A low comparison score does not grant authority.
- Use one planning process and one accepted plan, with immutable input snapshots, understandable decisions and explicit solver statuses. Do not recreate the old cascade of independent full-timeout refinement stages.

### EV goals, travel and availability

- Configurable daily minimum, initially **50% by 07:00 local time**, accounting for known away periods. It is not a continuously maintained 50% floor.
- Trips use manually entered total journey distance including the return, assumed energy per kilometre and an adjustable **30 km arrival reserve**. Reserve is desired remaining energy, not an additional trip withdrawal.
- Support manually entered timed SoC goals without inventing a trip or energy withdrawal. They are ordinary requirements, not immediate unscheduled actuator overrides.
- An oversized trip may target physical 100% and report that user-arranged external charging is necessary. Do not fabricate external charging or a precise return SoC.
- Unknown return time means unavailable until an actual reconnection or a user-provided return time. Never assume a midnight return.
- Reconnection reconciles measured state and triggers planning. The proposed daytime post-trip restore-to-50% rule was withdrawn; do not implement it.
- Start useful required charging early when waiting has no actual benefit. Wait for useful later PV or genuine cost benefits. Do not optimize into a needlessly last-minute winter charge.

### Optional energy, sources and battery-health preference

- Capture useful surplus even when no known trip consumes it inside the horizon. Selected opportunities become named conditional scheduled tasks; the fast controller cannot create and immediately execute new tasks.
- Select optional quantities jointly from zero to their feasible maxima. Do not turn a potential opportunity into a fixed demand or double-count a shared benefit.
- Normal discretionary EV ceiling is configurable, initially **80%**. Exceptional capture up to **100%** is allowed when that extra opportunity cannot adequately be replaced by later feasible solar within the full horizon. Required trip goals may independently require 100%.
- Avoid repeated unnecessary charging to 100% during plentiful sunny periods. Do not discard scarce winter surplus merely to stay at 80%. Do not invent a fixed 70% lower bound or force discharge when current SoC exceeds 80%.
- Replacement tests must consider actual EV availability, charging modes, household demands, ESS commitments, losses and headroom. Diagnostic permission to assess later headroom up to 100% is not permission to execute another 100% charge.
- Direct grid purchases solely for optional EV inventory are prohibited. Nominal labels such as "required grid" and "optional solar" must not launder extra grid purchases when solar already fulfills the actual requirement.
- PV allocated to optional EV energy may cause later household imports only if the joint comparison is better within **rolling 24 hours**. Useful EV and ESS energy remaining at that boundary is credited consistently; it need not be consumed within the window. This does not permit ordinary discretionary grid charging of the ESS.
- ESS grid precharging is allowed for economical avoidance of a specific forecast peak within **24 hours**. It is not general price arbitrage, grid insurance or a standing reserve for unforeseen demand. No intentional sale of stored ESS energy under the current fixed-tariff policy.

### Cost, service and continuity

- Compare `import cost - export income + incremental household capacity cost + start stored value - end stored value`. Display forecast bill components separately from assumed energy-asset value and from realized results.
- Value remaining EV energy consistently across the horizon. Count useful residual EV and ESS inventory once; avoid end effects, double credits and cyclic money creation.
- Reference-efficiency valuation formulas in the main draft are engineering starting points, not validated household measurements. Use declared/configured parameters and sensitivity tests.
- Required outcomes normally remain hard. If proven incompatible, provide priority-preserving best effort and explicit shortfalls; do not trade a feasible required trip away for inventory credit.
- Distinguish physical impossibility, missing data, solver error, timeout with a feasible incumbent and timeout without one. A timeout is not proof of infeasibility and must not automatically trigger a costly permission request.
- Prefer continuous understandable operation, modest power changes and fewer phase transitions. Power changes belong within a task, not a new task per interval. Reduce power before a pause where feasible; show meaningful pauses and expected resumption. Roughly one hour is a presentation example, not an absolute permission to split.
- A provisional five-minute expected minimum makes optional starts worthwhile; 15 minutes is clearly worthwhile to the user. Emergency/protective stopping always remains possible.
- No monetary ESS wear cost or daily cycle quota. Among similarly priced plans, prefer less throughput and fewer unnecessary reversals.
- Proposed starting polish tolerance is **EUR 0.02 over the complete plan and predicted cash cost**, relative to the best economic comparison, not per task or solver stage. Document and test it; it is not a promise about realized daily bills.
- Proposed initial visible completion margin is **15 minutes**, uncalibrated. Seek earlier completion without increasing the requested energy or buying grid energy solely as uncertainty insurance. Preserve the true deadline and expose inadequate margin. Do not learn that lateness is an acceptable planned outcome.

### Capacity limits and approvals

- Peak is the actual **billing quarter-hour average import**, including energy already consumed in the current quarter, not an instantaneous watt ceiling. Handle month boundaries and local-time/DST conventions correctly.
- Use the actual incurred monthly peak and configured billing floor as the cost baseline. The discussed floor is 2.5 kW; verify settings rather than treat old exports as current configuration.
- A configurable automatic ceiling is available for required EV daily/trip/manual goals when needed. **4 kW is an illustrative starting example**, not a verified current installation setting.
- Economical ESS precharging may deliberately incur a smaller peak now to avoid a larger forecast household peak within 24 hours, even without an EV goal. Stay within `max(configured automatic ceiling, actual incurred monthly peak)` unless separately approved. Prove the forecast peak reduction against a fair feasible reference, and always explain this unusual deliberate increase.
- Proposed notification default for that ESS exception: one informational notice when adopted, with deduplicated updates on material changes. This is a reversible implementation default, not a separately confirmed user preference. Implement/test the event and notification adapter locally; send no real notices during development. Ordinary successful peak suppression should stay quiet.
- Optional EV capture cannot independently invoke the higher automatic allowance. Separate priorities from permission and prevent optional work from using a fictitious future peak as already free.
- Above the automatic boundary requires task-specific approval. Approval is permission, not an instruction to use the full peak. Preserve it during ordinary replanning while the approved goal and limit remain applicable.
- An actually measured higher peak becomes available to other tasks for the remainder of that month. A proposed/approved/forecast future peak does not.
- Signal likely permission trouble on task creation/change or relevant changed circumstances, even days ahead. The old 12-hour waiting rule was discarded. Deduplicate requests and continue permitted best effort while waiting. Do not request an extension that cannot help a physical charger/availability shortfall.

### Fast control, publication and persistence

- Full planning may take seconds or minutes. Run it away from the event/control loop; a solver must not block protective response.
- Keep valid accepted instructions running until a validated replacement is adopted. Immediately invalidate affected instructions on departure, cancellation, changed permission or a peak emergency; expand the affected set when shared assumptions fail, rather than discard every task blindly.
- ESS handles brief solar dips within permissions/reservations. Smooth routine EV changes; sustained deviations first reduce feasible power. Peak danger can demand an immediate reduction/stop.
- Unexpected surplus first goes to feasible extra ESS charging. Residual may advance suitable existing tasks only within their constraints and without reducing protected scheduled ESS charging or another task's allocation. Trigger/coalesce replanning for meaningful deviations.
- Without a usable plan, permit basic ESS PV absorption/import reduction within established protections. Do not invent forecast-driven grid charging or new goals in fallback.
- Validate remaining candidate trajectories against current state, progress, goal/approval versions, availability, shared resources and current quarter energy before atomic publication. An old solve must never resurrect a disconnected task or obsolete approval.
- Persist input/forecast/policy revisions, goal progress, candidate and accepted plans, reasons, permissions, invalidations, solver timings/bounds and outcomes. Distinguish planned, accepted, commanded and measured behavior. Support restart/reconciliation and frozen offline replay.
- Plan adequate storage. No data-retention duration or automatic deletion policy has been agreed. Do not import an old archive-purge default as a new product decision.

## GUI references and deliverable

The first two current GUI pages are **Overview** and **Planning**. They are the user's preferred information/layout reference, not a request for a completely different visual product.

Inspect:

- `energymanager-dashboard/energymanager-dashboard.yaml`: Overview begins at line 4; Planning at line 993 in the inspected file. Find headings again if the file changed.
- `energymanager-dashboard/energymanager-timeline-card.js`: current charts, navigation, timeline and task-card implementation.
- `energymanager-dashboard/README.md` and `docs/V3-GUI.md`: current use and Home Assistant ingress context. Their old optimization stages/counterfactual features are historical context, not mandatory new architecture.

Preserve the useful layout: concise live energy summaries; 24-hour actual/planned power, task timeline and battery SoC with time navigation on Overview; seven-day power/SoC and planning task information on Planning. Keep readable units, series colors and the distinction between actual and predicted data. Existing ESS blue and EV green are useful references.

Integrate clear goals/progress, grouped execution sessions, reasons, pauses, shortfalls and pending approvals without turning the main pages into a solver-debug dump. Include task creation/editing for the in-scope goals, and approve/reject controls for the new permission workflow. Show invoice versus inventory estimates honestly. Make meaningful decision detail inspectable, with technical diagnostics outside the central household flow.

Build functional pages backed by the new API and actual planner/control records. A local deterministic demo mode is required for offline visual/integration verification. Screenshots/static fixtures alone are insufficient. Reuse the existing Home Assistant dashboard approach or adapt its components cleanly; maintain a Home Assistant-compatible integration and avoid unnecessary framework replacement. Namespace new assets and entities to avoid colliding with the current installation. Do not edit the existing dashboard or install the new one live.

## Integrations and missing installation data

Maintain the surrounding application role: Home Assistant measurements/configuration, forecasts, persistence, notifications and established actuator interfaces. Inspect the existing `ha_client.py`, forecast/services, actuator/control modules, configuration and add-on packaging for contracts. The current project uses Python 3.13, aiohttp and HiGHS; a compatible Python/HiGHS implementation is the practical starting point. Resolve and pin tested dependencies in an isolated environment; do not assume the shell's Python has the solver installed.

Implement usable configured forecasting/input adapters, including separate AC/DC PV and background load, plus deterministic offline providers. Reuse suitable existing forecasting logic after inspection. Do not make the user wait for deferred foundation models or new months of history. Keep controlled EV/ESS power out of background consumption where measurements allow; surface insufficient telemetry honestly.

Existing exports and the investigation's synthetic results are incomplete historical evidence. In particular, the native frozen decision record for the investigated plan was missing, and exported interval plans do not contain all settings. Do not fabricate historical replay inputs or call a synthetic benchmark a reconstruction of that event.

Do not block all development on absent live configuration. Create explicitly labelled fixtures/config examples with declared units and assumed capacities, efficiencies, device modes and tariffs; extract only non-secret contracts from available files. Missing live values must prevent inappropriate live command authority, not prevent offline software and tests. Document the minimum installation snapshot needed for eventual commissioning and prefer a read-only export over asking the user to transcribe settings.

Live Home Assistant/database access, hardware commands and external notifications are outside this task. Exercise integration boundaries with local test servers/simulated devices. Implement/configure control disabled by default. Local development servers, dependency setup, solver runs and builds are in scope subject to the environment's permissions; no paid API or deployment service is required.

## Technical decisions delegated to the implementation chat

The main draft contains proposals rather than a complete proven MILP. Finish the mathematical specification as part of implementation, and keep it next to the code. In particular:

1. Define variables, physical balances, discrete EV modes, battery paths, goal/availability constraints, actual quarter energy and permission attribution. Use consistent sign/unit conventions and independent physical validation of the resulting plan.
2. Make the causal required-versus-optional grid rule exact. The checkpoint audit in the draft is a proposed invariant, not a validated complete encoding. Test temporal causality, initial inventory, trips and later PV; prevent label laundering and ESS-grid laundering.
3. Define a finite reference/candidate procedure for joint optional selection, preserving equal achieved service and legitimate ESS support for requirements. Do not rely on open-ended task-regeneration convergence or independently sum claimed savings.
4. Specify rolling 24-hour comparisons for interacting actions. Compare both resource inventories and all relevant cash/peak effects under identical inputs; avoid letting several tasks independently spend the same benefit or exploit inconsistent boundaries. Full seven-day information still governs required planning and solar replaceability. Future conditional actions must be reassessed under the permitted short justification window before execution.
5. Specify the 80%/100% opportunity/replacement test and multiple-window interactions. Do not let terminal-value credit override the health preference. Avoid repeatedly charging to 100% merely because a distant requirement appears somewhere in the week.
6. Define solver/validation tolerances, source/provenance checks, fast-adjustment envelopes, forecast freshness, operational-score terms and event coalescing. Use measured/configurable capability facts where available; label engineering starting values and test their sensitivity.
7. Give all model construction, reference/opportunity diagnostics, best-effort work, polishing, validation and persistence **one total planning budget**. Benchmark before fixing the default. Skip unvalidated discretionary refinements if necessary; do not silently drop required policies or change temporal resolution. Separate feasibility status from bound/optimality claims.

Do not pause merely because these engineering decisions need work. Derive, implement and test them. If a genuine confirmed-policy conflict survives reasonable technical attempts, isolate it, show the smallest concrete counterexample and ask only the necessary preference question. Preserve valid useful work and continue independent parts while waiting.

## Verification and acceptance

Create meaningful tests of physical/policy outcomes, with real solver integration. A mocked solver is appropriate for event/failure tests but not proof that optimization works. Check tiny cases against independent arithmetic or exhaustive feasible alternatives; do not have the same formulation generate its own expected answers.

Required coverage includes the main draft's acceptance matrix and these interactions:

- Winter required charging starts early and remains continuous when no useful waiting benefit exists; useful later solar can instead justify waiting.
- Simultaneous DC/AC capture exceeds 2.5 kW in total when physically feasible, while the AC converter respects its own cap. Check both charge/discharge directions and accounting.
- Overlapping daily/trip/manual goals, close trips, recurring local-time schedules, missing returns, oversized travel and reconnection with different SoC. Test five-minute windows, partial first intervals, midnight, DST and billing-month changes.
- Zero/partial/full optional quantities; available solar fulfilling a requirement must not leave unnecessary nominally required grid purchases; later solar must not retroactively disallow necessary pre-departure grid energy.
- Independent/mutually competing opportunities, source restrictions, 24-hour boundary effects and no double-counting. Include present capture benefiting a later day without using impermissible distant cash/peak justification.
- Sunny-series 80%, scarce opportunity 100%, car away during later PV, later energy committed elsewhere and a genuine trip requiring 100%. Verify no forced discharge solely because current SoC is above 80%.
- Quarter-hour guard with an already-consumed prefix, sustained dips, ESS depletion, peak emergencies and uncontrollable demand already over a limit. Do useful permitted control without treating forecast excess as an incurred allowance.
- ESS deliberately raising a smaller peak now to avoid a larger forecast peak within 24 hours; reject an uneconomical/out-of-window/unapproved case. Verify explanation and deduplication through a fake notifier.
- Task-specific approval pending/granted/rejected/revised/expired-by-goal-change; other work continues. Actually measured higher monthly peak is reusable; a planned one is not. Optional capture cannot independently acquire required-goal authority.
- Long solve with responsive control; disconnect/goal/approval/forecast change during solve; affected-only invalidation with shared-resource propagation; reject stale commands; restart and recovery.
- A timeout with a feasible incumbent, timeout without one, proven infeasibility and malformed/failed solver output have distinct validated outcomes. No fictitious external charging or negative battery states in best effort.
- GUI goals remain readable across power changes/replans; task edits and approval actions round-trip through persistence; actual/predicted data and cash/asset values remain distinct. Verify browser interactions and visual layout locally.

Benchmark at least representative full seven-day, at-most-five-minute EV/ESS cases, including a difficult source/ceiling/approval combination. Normally five-minute resolution means roughly 2,016 intervals, with explicit handling of horizon/partial boundary conventions. Record machine/runtime/library versions, model dimensions, stage and whole-cycle timings, incumbent/bound/status, service shortfalls, peak, cost components, starts/phase changes and validation outcome. Synthetic assumptions must be clearly labelled. Do not recycle old 15-minute benchmarks as proof of this design's performance.

Measure control response while a real solve runs; specify and test an explicit latency target appropriate to the established input/actuator cadence. Test with an injected clock where useful, and distinguish deterministic control tests from observed runtime measurements. No claim of production hardware latency follows from offline tests alone.

Run relevant lint/type/static checks, new unit/integration/solver/frontend tests, package/startup smoke checks and a local end-to-end demo. Run existing checks where shared/reused contracts could regress. Document every unavailable check precisely, including the external requirement; do not count skipped core solver or GUI verification as completed functionality.

## Work sequence and definition of done

Proceed in useful vertical slices, not months of speculative framework design:

1. Read skill/specification, inspect workspace/GUI/contracts, preserve initial state, establish the checkpoint and a finite implementation plan.
2. Implement the domain/input/configuration/persistence contracts and a real required-goal EV/ESS planning slice with independent validation.
3. Complete optional sources, economic accounting, normal/exceptional ceilings, peak permissions, best effort and bounded refinement. Resolve the delegated mathematics and test it.
4. Wire event handling, nonblocking planning, fast control, versioned publication, restart/reconciliation, explanations and notification/approval adapters with simulated hardware.
5. Finish Home Assistant-facing packaging/adapters and the two functional GUI pages; exercise the local complete workflow and benchmark realistic full-horizon cases.
6. Repair discovered issues, review the change as a whole, rerun affected checks and produce the verification/migration report. Keep advancing until the defined goal is achieved or a specific unavoidable blocker requires user input.

Done means the in-scope implementation runs end to end offline, required acceptance cases pass with real optimization, GUI workflows work, measured performance/status is reported honestly, and a reviewer has reproducible commands, fixtures, documented assumptions and a commissioning/rollback procedure. The replacement must be reviewable as a coherent application, not disconnected modules.

Do not declare success while mandatory behavior is replaced with TODOs/stubs or core checks remain unavailable. You may finish an offline-verified release candidate while clearly listing separately pending installation-specific/live commissioning; that boundary is intentional and does not authorize deployment. If representative computation remains impractical, report the evidence and exact unresolved issue rather than claim a successful scheduler or quietly reduce resolution.

Leave the legacy installation untouched. Provide a configuration mapping/export procedure, prerequisites, exclusive-controller/cutover steps and rollback instructions for later approval; do not execute them. Do not enable both controllers or transmit a hardware command to prove readiness.

## Persistence, usage limits and user absence

The user will be away for several hours. Routine implementation decisions are delegated. Keep updates concise and do not stop at every milestone waiting for approval. Ask only when information or a confirmed-policy decision is truly necessary and cannot be safely isolated; continue unaffected work where possible.

Continue until the agreed implementation and verification are complete.

Maintain a concise progress checkpoint at meaningful milestones, recording completed work, remaining steps, relevant decisions, and verification results. Use `gpt/architecture/Implementation_Checkpoint.md`; include exact commands/results, current source paths, dependency environment, unresolved failures and the next concrete step. Clearly distinguish implemented, tested, benchmarked and live-unverified work. Update before compaction or a foreseeable interruption when possible.

If a usage limit blocks execution, preserve progress and wait for the normal allowance to reset. Do not consume rate-limit reset credits, purchase credits, or switch to paid API usage.

If the environment supports automatic resumption after the normal reset, resume the same task from its checkpoint. Otherwise, clearly report that manual resumption is required. Do not promise native automatic resumption if it is unavailable, and do not create a new recurring automation to imitate it without authorization.

On resumption, verify the checkpoint against the actual workspace and continue unfinished work. Check actual files, Git state, environment and relevant verification outputs; a checkpoint alone is not proof a step completed. Preserve progress rather than restart or repeat the old investigation.

At completion report what was delivered, how to run/view it, meaningful verification/performance results, remaining installation assumptions and the exact live steps awaiting separate approval. No actual external notifications or messages are authorized by the architectural notification feature.
