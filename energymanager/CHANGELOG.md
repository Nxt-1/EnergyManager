# Changelog
## 0.17.0
- Adds the first planner economics foundation without changing the v0.16.1 shadow scheduling behavior.
- Adds configurable marginal import energy cost, export revenue, capacity-tariff rate and capacity-tariff billing floor.
- Keeps economics disabled until all planner-relevant tariff values are configured; no placeholder prices affect planning.
- Versions each distinct tariff configuration as an immutable profile with a fingerprint and first-active UTC timestamp.
- Stores tariff revisions in InfluxDB when available and falls back to `/data/tariff_profile_history.jsonl` otherwise.
- Reusing the same tariff across restarts does not create a new revision; changing a tariff value creates a new revision.
- Adds `sensor.energy_manager_economics_status` exposing the active tariff profile and its historical revision ID.
- Does not yet use monetary cost to alter EV/ESS scheduling; this release establishes reproducible historical cost inputs first.
- Remains hard-coded shadow mode with no hardware writes.
## 0.16.1
- Fixes pre-control net-power diagnostics so scheduled task load is included in interval net power, deficit energy and peak deficit.
- Keeps the ESS/grid projection behavior unchanged; it already included scheduled load correctly.
- Adds regression coverage that a feasible EV task is never under-allocated after discrete charger-step quantization, including at 226 V.
- Renames the planner log wording from raw deficit to pre-control deficit to match the corrected metric.
- No configuration schema changes and no hardware writes. Shadow mode remains mandatory.
## 0.16.0
- Adds the first shadow task scheduler: planner tasks can now contribute scheduled load to the 15-minute planning horizon.
- Schedules the current EV energy-by-deadline task from its earliest start using physically feasible whole-ampere 1P/3P
  charging steps; this is a deadline-feasibility baseline, not an economic optimizer.
- Keeps the existing raw background/PV deficit metric unchanged while exposing task energy through `scheduled_load_kwh`.
- The ESS projection now reacts to scheduled EV load, so projected SoC and grid import include the task schedule.
- Does not yet issue EV dry-run commands from the schedule; the existing ESS dry-run plumbing remains unchanged.
- No configuration schema changes and no hardware writes. Shadow mode remains mandatory.
## 0.15.0
- Adds the first generic planner task model while keeping scheduling and hardware control disabled.
- Adds an EV target-by-departure task generated from live connection/SoC state and runtime policy settings.
- The EV task exposes earliest start, departure deadline, target SoC, required battery/AC energy, interruptibility and
  simple max-power feasibility.
- Adds `sensor.energy_manager_task_status` and includes task IDs/status in the shadow planner diagnostics/logs.
- Adds optional EV usable-battery-capacity and charging-efficiency settings; battery capacity must be configured before
  the task can derive an energy requirement.
- Target SoC and local departure time default to 80% and 07:00 and remain runtime configuration rather than planner code.
- The planner receives the task catalog but does not schedule EV charging yet; actuator commands remain dry-run only.
## 0.14.0
- Adds the first generic actuator power-command contract while keeping all hardware writes disabled.
- Planner requests use actuator IDs plus requested power; actuator-specific code translates them into feasible dry-run commands.
- ESS dry-run commands enforce configured charge/discharge power limits and SoC boundaries.
- EV dry-run commands translate requested charging power into feasible whole-ampere 1-phase/3-phase charger states and never exceed the requested power.
- Adds `sensor.energy_manager_actuator_command_status` with requested versus accepted power, limiting reason and EV phase/current details.
- The first shadow-plan interval now passes its ESS request through the actuator command translator as an end-to-end dry-run plumbing check.
- `sensor.energy_manager_actuator_status` now documents the supported command interface for each actuator.
- No Home Assistant service calls or device writes are performed; `control_enabled` and `hardware_writes` remain false.
- No configuration schema changes.
## 0.13.0
- Adds the first generic read-only actuator registry for planner-facing device capabilities.
- Moves the ESS planning envelope behind an ESS actuator snapshot instead of passing ESS configuration directly into the planner.
- Adds an EV actuator snapshot with connection state, SoC, present charging power and configurable 1-phase/3-phase charge limits.
- Adds `sensor.energy_manager_actuator_status` with the actuator catalog, readiness and capability diagnostics.
- The shadow planner now receives a list of actuator snapshots; no EV task is scheduled yet and no actuator can write to hardware.
- Existing ESS projection behavior is retained, but its limits now come from the ESS actuator capability interface.
- New EV capability options are optional; defaults are 6-16 A, 230 V and both 1-phase and 3-phase support.
- Remains hard-coded shadow mode.
## 0.12.0
- Adds the first read-only ESS resource projection to the shadow planner.
- Uses current ESS SoC plus configurable capacity, SoC limits, charge/discharge power limits and efficiencies.
- Separates AC-coupled roof PV from DC-coupled shed PV so shed energy must pass through the ESS/inverter path before serving AC loads.
- Projects 15-minute ESS AC power, battery SoC, post-ESS grid power and DC-PV curtailment without sending any commands.
- Adds `sensor.energy_manager_shadow_plan_next_24_hours_grid_import_energy` and extends the shadow-plan status attributes.
- Keeps the existing raw pre-control deficit sensor for comparison.
- New ESS planning parameters are optional; existing saved configuration remains valid and runtime defaults are used when omitted.
- Remains hard-coded shadow mode; dynamic thermal/BMS capability feedback and cost optimization are not yet applied.
## 0.11.0
- Adds the first read-only shadow planner foundation.
- Aligns the rolling background-load forecast and PV-potential forecast onto one 15-minute timeline.
- Keeps a 48-hour internal horizon and publishes compact 24/48-hour summaries plus the next three hours of intervals.
- Reports background energy, PV potential, pre-control net deficit/surplus and peak net deficit.
- Adds `sensor.energy_manager_shadow_plan_status` and
  `sensor.energy_manager_shadow_plan_next_24_hours_net_deficit_energy`.
- Leaves `scheduled_load_w` at zero for now so EV/laundry/task scheduling can be added without changing the plan shape.
- Does not yet schedule the ESS or EV and does not claim grid export from DC-coupled shed surplus; surplus is reported as
  available energy before storage/control.
- No configuration schema changes and no device control.
## 0.10.2
- Scores all candidate load models on the same common set of valid forecast intervals for each horizon.
- Keeps one accuracy score set; no duplicate native/common model scores are exposed.
- Keeps `coverage` and `issue_coverage` as separate availability diagnostics for each model.
- Leaves the production background-load predictor unchanged.
- No configuration schema changes and no actuator/control changes.
## 0.10.1
- Makes horizon energy accuracy the primary background-load backtest criterion instead of pointwise wattage MAE.
- Adds mean absolute total-energy error, signed energy bias and integrated absolute timing mismatch in kWh.
- Adds mean and p90 15-minute peak-load underprediction diagnostics for capacity-tariff risk.
- Keeps wattage MAE, bias and p90 error as secondary shape diagnostics and reports the best power model separately.
- Changes `sensor.energy_manager_background_load_backtest` to expose the current model's 24-hour total-energy MAE in kWh.
- Stores the new runtime evaluation metrics in InfluxDB under the existing `background_load_backtest` measurement.
- Leaves the production background-load predictor unchanged and does not add any compile-time household-specific corrections.
- No configuration schema changes and no actuator/control changes.
## 0.10.0
- Added a runtime rolling-origin backtest for the background-load predictor; no household-specific correction constants are compiled into the application.
- Evaluates the current EnergyManager model against three simple baselines: persistence, same time yesterday and same time last week.
- Measures 1 h, 3 h, 6 h, 12 h and 24 h forecast MAE, bias, p90 absolute error, energy MAE and coverage.
- Adds current-model error breakdowns for night/morning/afternoon/evening and weekday/weekend to identify where separate models or inputs may be useful.
- Uses only data that would have been available at each historical forecast issue time, avoiding look-ahead leakage.
- Runs the evaluation at runtime from the current InfluxDB-backed history and refreshes at most once per 24 hours.
- Stores backtest summaries in InfluxDB and exposes `sensor.energy_manager_background_load_backtest` for inspection.
- Leaves the production background-load predictor unchanged; v0.10 is an evaluation release intended to guide later runtime-learning model improvements.
- No configuration schema changes and no actuator/control changes.
## 0.9.3
- Treats stale EV charging-power history as 0 W after the existing 15-minute freshness window, instead of dropping the entire background-load sample.
- Keeps the stricter stale-value rules for grid, ESS and PV sources so sensor outages are not silently stretched into fake historical power.
- Uses a new derived-history recipe ID so the full archived source range is rebuilt automatically without re-importing the legacy source rows.
- Writes the corrected reconstruction to `legacy_house_load_v2`; the predictor prefers v2 over the v0.9.2 legacy table and still prefers live `house_load` data over both.
- No configuration schema changes and no actuator/control changes.
## 0.9.2
- Rebuilds legacy house/background history on a complete five-minute timeline instead of requiring every source to have written in the same bucket.
- Carries recent historical source values forward for up to 15 minutes to bridge normal sparse Home Assistant state updates.
- Treats stale values within ±50 W as inactive and resolves them to 0 W, allowing long zero periods such as PV at night, no export, idle ESS and an unplugged/idle EV to remain reconstructable.
- Refuses to carry stale material non-zero values beyond 15 minutes so historical sensor outages are not silently converted into fake load.
- Seeds each 14-day reconstruction chunk with the latest prior archived source state, so chunk boundaries do not create artificial gaps.
- Uses a new derived-history recipe ID and writes the rebuilt history to `legacy_house_load`, leaving live `house_load` data append-only and avoiding duplicate-point overwrites.
- The predictor merges reconstructed legacy and live background history by timestamp, preferring live samples when both exist.
- No configuration schema changes and no actuator/control changes.
## 0.9.1
- Added optional username/password authentication for the legacy InfluxDB 1.x backfill source.
- Uses HTTP Basic authentication when legacy credentials are configured.
- Keeps unauthenticated legacy sources supported by leaving both credential fields empty.
- No changes to EnergyManager InfluxDB 3 persistence or backfill data semantics.
## 0.9.0
- Added incremental historical backfill from the legacy Home Assistant InfluxDB 1.x database into EnergyManager's InfluxDB 3 database.
- Reuses configured Grid, ESS, Solax PV and EV charging entity mappings; source entity IDs are never hardcoded.
- Archives only signals EnergyManager currently uses, as normalized five-minute source history in `legacy_power_source`.
- Tracks imported coverage per logical signal + entity mapping instead of using one global migration-complete flag.
- New configured/modelled signals can therefore be backfilled later without re-importing the whole Home Assistant database.
- If the old source database gains newer data, only the missing tail is imported on the next synchronization.
- Derived house/background history has its own recipe/source fingerprint and coverage state, so future model changes can rebuild only the relevant derived history.
- Reports source and derived backfill progress through `sensor.energy_manager_database_status`.
- Corrected the baseline predictor's active history window to the documented 35 days; database retention remains indefinite.
- Backfill failure is non-fatal; normal InfluxDB 3 persistence and EnergyManager operation continue with existing history.
- Remains shadow mode; no device control is present.
## 0.8.0
- Added optional InfluxDB 3 persistence using a restricted database read/write token.
- Added `sensor.energy_manager_database_status` for connection and migration health.
- Background-load samples now persist indefinitely in InfluxDB while the current baseline model keeps a 35-day active training window.
- PV rolling forecast revisions and background-load forecast revisions are stored in InfluxDB instead of JSONL when enabled.
- Existing v0.5/v0.7 JSONL persistence files are imported once and renamed with a `.migrated` suffix after successful migration.
- Database failure is non-fatal: Energy Manager reports the database error and falls back to the existing local JSONL persistence.
- Includes the complete v0.7 background-load predictor for users upgrading directly from v0.6.
- Remains shadow mode; no device control is present.
## 0.7.0
- Added persistent sampling of canonical background-load power every five minutes.
- Added a 15-minute rolling background-load forecast for the future planner.
- The baseline model learns robust time-of-day patterns, then weekday/weekend and same-weekday behavior as history grows.
- Added next-hour power, next-24-hours energy and next-seven-days energy diagnostics.
- Added independent predictor status with learning progress and retained-history metadata.
- Added `/data/background_load_history.jsonl` with 35-day retention and compact forecast revision history.
- No configuration schema changes; the predictor uses the v0.6 canonical background-load signal.
- Remains shadow mode; no device control is present.
## 0.6.0
- Added canonical instantaneous AC house-load power derived from grid net power, Solax AC PV and normalized ESS AC power.
- Explicitly excludes the DC-coupled shed MPPT from the house-load balance so shed PV is not double-counted.
- Added known controllable-load power; v0.6 starts with measured EV charging power.
- Added background-load power as house load minus known controllable loads.
- Added Home Assistant diagnostics for house load, controllable load and background load.
- No configuration schema changes; existing v0.5.1 entity mappings are reused.
- Remains shadow mode; no device control is present.
## 0.5.1
- Clamp small negative EV charging-power readings between -100 W and 0 W to zero.
- Keep larger negative EV charging-power readings invalid so a real sign/configuration problem is still visible.
- No configuration schema changes.
- Remains shadow mode; no device control is present.
## 0.5.0
- Replaced the fixed 20:15 day-ahead snapshot workflow with a continuously refreshed rolling forecast.
- Extended the PV horizon to today plus seven full future calendar days.
- Switched Open-Meteo to `knmi_seamless`, using KNMI HARMONIE AROME in the near term and ECMWF beyond it.
- Added `sensor.energy_manager_pv_forecast_next_7_days_energy` with per-day front/rear/shed breakdowns.
- Added append-only `/data/pv_forecast_revisions.jsonl` history with each 30-minute forecast revision and daily totals.
- Removed the two fixed day-ahead diagnostic entities; v0.5 cleans their stale Home Assistant states on startup.
- Kept the existing today, tomorrow and next-hour live forecast diagnostics.
- No configuration schema changes; existing v0.4.1 options remain valid.
- Remains shadow mode; no device control is present.
## 0.4.1
- Fixed Python 3.13/Ruff import placement for `Mapping`.
- Re-published the v0.4 predictor release under 0.4.1 after the 0.4.0 CI failure.
- No intended functional changes from v0.4.0.
## 0.4.0
- Added the first Python predictor: a four-plane Open-Meteo PV forecast.
- Migrated the existing three-plane physical PV calculation into the app and added the 6.18 kWp shed plane.
- Added separate front/rear group calibration seeded from August-October 2026 production history.
- Added time-of-day shading correction and conservative rear seasonal interpolation without extrapolating past observed data.
- Added direct/diffuse radiation and cloud-cover forecast inputs for later calibration work.
- Added persistent day-ahead PV snapshots after 20:15 local time.
- Added PV forecast status, daily-energy, day-ahead and next-hour diagnostic entities.
- Added an optional `pv.forecast_enabled` runtime setting; existing entity mappings remain valid.
- Added Docker build-time imports for core/predictor modules to catch missing source files before publication.
- Remains shadow mode; no device control is present.
## 0.3.1
- Re-published the v0.3 house-state release after missing source files were added to the repository.
- No intended functional changes from v0.3.0.
## 0.3.0
- Added grouped runtime configuration for Grid, ESS, PV and EV inputs.
- Added a normalized internal House State with per-input validity, observation time and source metadata.
- Added ESS SoC/power, separate PV powers, EV SoC/connection/charging-power inputs.
- Added canonical ESS sign handling: positive discharge, negative charge.
- Added total-PV and aggregate input-health diagnostics.
- Added periodic 30-second input reconciliation alongside event-driven WebSocket updates.
- Added automatic migration of the v0.2 flat grid configuration to the grouped v0.3 format.
- Removes the obsolete v0.1 `sensor.energy_manager_observed_grid_power` state on startup.
- Remains read-only; no device control is present.
## 0.2.0
- Replaced the single grid-power input with separate momentary import and export entities.
- Added canonical net grid power (`import - export`), with positive values meaning import and negative values meaning export.
- Added separate normalized import/export diagnostic sensors.
- Added degraded-state handling: invalid or unavailable input never silently falls back to zero.
- Generalized the Home Assistant WebSocket observer to subscribe to multiple entities on one connection.
- Rejects non-finite power values and negative values from the separate import/export inputs.
- Updated GitHub Actions to current Node 24/ESM action generations.
- Remains read-only; no device control is present.
## 0.1.0
- Initial Home Assistant app skeleton.
- Internal Home Assistant REST API access through the Supervisor proxy.
- Home Assistant WebSocket state subscription for one configured grid-power entity.
- Read-only shadow-mode diagnostics.
- Automatic reconnect with bounded exponential backoff.
- CI and GHCR publishing workflows.
