# Changelog

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
- No intended functional changes from 0.4.0.

## 0.4.0

- Added the first Python predictor: a four-plane Open-Meteo PV forecast.
- Migrated the existing three-plane physical PV calculation into the app and added the 6.18 kWp shed plane.
- Added separate front/rear group calibration seeded from August-October 2026 production history.
- Added time-of-day shading correction and conservative rear seasonal interpolation without extrapolating past observed data.
- Added direct/diffuse radiation and cloud-cover forecast inputs for later calibration work.
- Added persistent day-ahead PV snapshots after 20:15 local time.
- Added PV forecast status, daily-energy, day-ahead and next-hour diagnostic entities.
- Added an optional `pv.forecast_enabled` runtime setting; existing entity mappings remain unchanged.
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
