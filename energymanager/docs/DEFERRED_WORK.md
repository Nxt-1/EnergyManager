# Deferred work

Architecture discussion backlog. These entries record future work, not permission to implement or run experiments in this chat.

## ARCH-001 — Forecast accuracy by lead time and usefulness of the seven-day horizon

Recorded: 22 October 2026. Status: **deferred to a later release**, explicitly requested by the user.

Question: how does forecast accuracy change with days ahead, and does planning seven days ahead improve decisions enough to justify its computational and modelling cost?

Current decision: continue to use the full current seven-day horizon, including when evaluating whether opportunistic EV charging above the normal 80% ceiling is worthwhile. Do not shorten the horizon merely because this evaluation is pending.

Future assessment should:

- Compare predictions with actual outcomes by elapsed lead time, including day-ahead bins across the full horizon. Preserve forecast issuance time, target interval, timezone and revision identity; do not substitute later revisions or hindsight for what was known at the time.
- Evaluate AC PV, DC PV and uncontrolled consumption separately, where data permits. Assess energy error, bias, timing error and error ranges over decision-relevant windows. Do not treat curtailed PV output as uncurtailed production potential or double-count controlled task consumption as background demand.
- Determine whether distant forecasts add useful information for EV charging, ESS reserves and other decisions. Forecast accuracy alone is not the same as scheduling value: compare cost, completion reliability, changes between plan revisions and calculation time for candidate horizons under consistent assumptions.
- Use representative seasons and household conditions; identify limitations of available samples. Avoid inferring annual performance from a few sunny or cloudy days.
- Recommend whether to keep seven days, use a shorter horizon, or retain a longer view with less detail or confidence further ahead. None of these alternatives is adopted yet.

Evidence needed: archived forecasts as originally issued at sufficient temporal resolution; corresponding actual measurements with quality/curtailment information; relevant task, availability, tariff and resource-state records for scheduling comparisons. Existing daily forecast-summary tables alone do not establish quarter-hour timing accuracy. Data coverage and retention need checking before the future assessment can be considered feasible.

No evaluation or implementation has been performed for this backlog item.

## ARCH-002 — Revisit temporal resolution only if a demonstrated issue warrants it

Recorded: 22 October 2026. Status: **conditional future investigation**, not a planned change.

Current decision: use planning windows no longer than five minutes. The user prefers retaining that detail and considering coarser windows only if a real issue arises that reducing temporal resolution could resolve.

If triggered, compare the same requirements, forecasts and policies at candidate resolutions. Measure runtime and solver quality alongside energy cost, completion reliability, continuity and quarter-hour peak prediction. Include the effect on short charging opportunities and appliance profiles. Coarser windows or a coarser distant horizon are possibilities to discuss with the user, not automatically authorized fallbacks.

Keep this separate from ARCH-001: changing the number of days ahead and changing the size of time windows are different decisions.

## ARCH-003 — Automated trip-distance calculation and temperature compensation

Recorded: 22 October 2026. Status: **deferred ideas for later releases**.

Initial agreed approach: the user enters expected trip kilometres; estimate battery energy using an assumed average consumption. No database of previous trips or learned driving schedule is required.

Future extensions, independently selectable:

- Calculate expected driving distance from the entered trip destination/location. Routing source, interpretation of outward/return journeys and supported input formats remain undecided.
- Adjust expected trip-energy consumption using predicted outside temperature, including relevant battery-conditioning and cabin-climate effects where evidence supports them. The compensation model, calibration evidence and treatment of uncertainty are not yet selected.

Retain explicit user requirements and distinguish distance-derived estimates from direct SoC targets. Do not silently alter a user-entered target or assume capabilities such as en-route charging. Any future calibration approach should respect the user's preference not to maintain trip-history records.

These extensions are not authorized implementation work in this architecture chat.

## ARCH-004 — DHW scheduling and heating-model calibration

Recorded: 22 October 2026. Status: **deferred beyond the initial release**, explicitly requested by the user.

DHW scheduling is not essential for this release. Preserve the previously discussed requirements for later work: minimum usable hot-water reserve, scheduled comfort windows, optional surplus heating, task priorities and peak permissions, and separately validated disinfection completion. These remain design inputs, not implemented or validated capabilities.

Prerequisites and evidence:

- The user plans to install ESPAltherma; it is not installed yet. Verify the applicable device definition and actual availability of tank temperature, DHW/space-heating status and heater-stage flags.
- Collect synchronized whole-unit electrical power, tank temperature and operating-state observations over representative heating cycles. Use them to estimate heating time, energy use, standby cooling and uncertainty, and avoid double-counting DHW as both a task and background consumption.
- Account for observed backup-heater demand. Whether routine use can be suppressed remains unresolved; do not assume independently selectable heat-pump-only operation. Validate any inferred heater activity against available status readings.
- Establish the actual command interface and feasible heating behaviour before enabling scheduling. Disinfection integration and completion criteria remain separate unresolved work; this deferral does not authorize changing the unit's existing controls.

For the initial release, leave DHW under its existing control and account for its consumption as uncontrolled demand. Keep the general architecture able to add a thermal resource and its tasks later without requiring them for EV/ESS scheduling.

No installation, calibration or implementation is authorized by this backlog entry.

## ARCH-005 — Washing-machine and dishwasher scheduling suggestions

Recorded: 22 October 2026. Status: **deferred beyond the initial release**, explicitly requested by the user.

Preserve the earlier appliance-scheduling requirements for a later release:

- User-entered earliest start and latest completion, with reusable program durations and electrical power profiles.
- One recommended start time and a few alternatives, with meaningful cost differences where available. Current appliances are started or programmed by the user; do not assume remote-start capability.
- A user-confirmed start time becomes a fixed commitment. Subsequent improvements may be suggested but must not automatically move that commitment.
- Prefer measured time-varying profiles and retain variation between cycles. An average-power fallback can be used where detailed profiles are unavailable. Avoid double-counting these loads in background forecasts when explicit profiles are introduced.

### Planned Mazak operation

The user also defers explicitly planned Mazak operation and expects it can be added alongside washing-machine and dishwasher scheduling. Group the work here without assuming the machine shares their automatic-start, interruptibility, duration or power-profile behaviour. Establish its actual planning inputs and constraints when revisited.

For the initial release, its electricity use remains part of uncontrolled household demand. This deferral concerns planning its operation, not permission to control the machine.

This entry defers scheduling suggestions for these appliances and planned Mazak operation. Automatic recognition of already-running appliances was subsequently deferred separately as ARCH-006.

No implementation is authorized by this backlog entry.

## ARCH-006 — Automatic recognition of running appliances

Recorded: 22 October 2026. Status: **deferred beyond the initial release**, explicitly requested by the user.

Preserve the earlier direction: recognize starts of explicitly configured appliances from suitable circuit measurements, then represent their remaining demand as already-running, fixed, non-interruptible tasks. Do not attempt to identify every unexplained household fluctuation or stop/reschedule an uncontrollable appliance.

Future work needs representative circuit measurements, a validated recognition method, remaining-profile estimates and correct separation from the background forecast. Profile errors in an uncontrollable running load should not automatically trigger repeated full replanning without useful new information.

For the initial release, include these loads in the uncontrolled household-demand forecast. This does not remove fast peak protection by reducing eligible controllable loads.

No implementation or data-collection experiment is authorized by this backlog entry.

## ARCH-007 — Advanced forecasting ideas from the ML specialist

Recorded: 22 October 2026. Status: **deferred to a later release**, explicitly requested by the user.

The user has now consulted the ML specialist mentioned in the earlier discussion. The specialist proposed interesting forecasting ideas, but they require substantially more stored data than is currently available and are more advanced than the user wants to pursue for this release.

The user identifies the direction as **foundation models for forecasting**. Preserve this as a future investigation. No particular model, provider, training/fine-tuning approach or data requirement has been specified; do not infer one from that label. When revisited, establish the required signals, history length, data quality and retention before assessing feasibility.

Keep this separate from ARCH-001, which evaluates forecast accuracy by lead time and the usefulness of the seven-day horizon. That evaluation does not require committing to an advanced forecasting method.

This deferral does not authorize changes to predictors, new data-collection jobs or experiments.

## ARCH-008 — ESS reserve for unplanned load peaks

Recorded: 22 October 2026. Status: **deferred idea for a later release**, explicitly requested by the user.

Consider retaining some ESS energy to help cover unplanned load peaks. This is additional uncertainty protection, distinct from reserves for specific forecast peaks and from the actuator's physical minimum SoC. It is not a grid-outage/backup requirement.

When revisited:

- Use measured unexpected load events and forecast errors to assess a useful energy reserve and the discharge power needed. Stored energy alone cannot cover peaks above available converter output.
- Compare protection against its costs: reduced energy for ordinary use, possible extra grid imports, lost solar headroom and overlap with existing reservations.
- Decide whether sizing should be fixed or adaptive, when the reserve may be used/released and how replenishment fits source and peak permissions. Do not assume grid replenishment is automatically authorized.
- Keep the reserve and its reason visible. No reserve size or control policy is selected yet.

This does not add a standing reserve to the initial release or authorize experiments or implementation.


## ARCH-009 — Visual EV schedule and dedicated EV page

Recorded: 24 October 2026. Status: **implemented locally in 4.1.0**, after the user
explicitly authorized starting ARCH-009 and writing code on the same date. Retained
here to preserve the original deferred intent and its resolution.

Original intent: make the car schedule easier to understand visually, perhaps using a calendar on a
new page dedicated to the EV. Preserve journeys, expected away/return periods, morning
and manual SoC requirements, and planned charging sessions without implying measured
activity or inventing a learned driving routine. Layout and interactions were left
undecided for later feature work, including V4.1 discussion.

The dedicated EV page now combines a seven-day calendar with a selected-day agenda,
expected away/return periods, morning/manual/departure targets and accepted charging
sessions. Existing forms support explicit goal changes. Unknown returns remain explicit;
obsolete plan outcomes are withheld while current requirements remain visible. This
builds on the separate 4.0.10 date/time controls and W display. See the maintained
architecture for the implemented contract and VERIFICATION.md for local evidence.

## ARCH-010 — Longer graph history from archived measurements

Recorded: 24 October 2026. Status: **implemented in 4.2.2**. The user authorized
committing and pushing the completed history fix after reviewing the local result.

Original issue (through released4.2.1): graphs receive only the latest2,000 control-loop
samples, roughly33 minutes at a one-second loop. Overview shows six hours into the past
but backward navigation does not load older measurements. Measurement events remain in
SQLite; this is a display limit, not archival deletion.

The implemented fix loads the requested graph range from the indexed existing
measurement archive in a read-only worker. Overview keeps12-hour navigation/Now and
adds installation-local History day selection, including23/25-hour days. Any retained
day can be requested; the API bounds each query to eight elapsed days and100–2,000
points per series. The UI requests1,200. First/min/max/last reduction preserves peaks
within continuous buckets; buckets containing gaps are conservatively left blank.
Unknown/other-mode samples and expired reads break lines. Requests are cached and
obsolete navigation responses cannot repaint another range. Older graph data is merged
with recent samples rather than shipping the full archive to the browser.

New records retain battery capacities. Older archived kWh records use current runtime
capacities to estimate percentages, explicitly labelled in the graph. No missing data is
fabricated, no HA Recorder history is imported, and no retention/deletion policy is adopted.

Offline verification uses clearly labelled synthetic archives/local fake endpoints.
Actual installation history remains unverified; live database access was not authorized.
The earlier hold on committing/pushing was lifted by the user for the 4.2.2 release.
