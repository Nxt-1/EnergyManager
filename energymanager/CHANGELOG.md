# Changelog

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
