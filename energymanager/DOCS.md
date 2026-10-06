# Energy Manager

Energy Manager is currently a read-only shadow-mode Home Assistant app. It now combines the rolling PV and background-load forecasts in a first planner timeline while keeping all device control disabled.

## Configuration

Entity IDs remain runtime configuration and are not hardcoded. Existing Grid, ESS, PV and EV configuration is preserved.
Version 0.9 adds an optional legacy InfluxDB backfill group; existing entity mappings remain unchanged.

### Grid

Configure separate momentary import and export power entities. Both must report `W` or `kW` and must be non-negative.
Canonical grid power is `import - export`: positive means import, negative means export.

### ESS

ESS SoC is normalized to percent. ESS power is normalized so positive means discharge and negative means charge.

Version 0.12 adds an optional planning envelope under `ess`: nominal capacity, minimum/maximum planning SoC, maximum
charge/discharge power and charge/discharge efficiencies. Existing configurations remain valid when these fields are omitted.
The runtime defaults are 15 kWh, 10-100% SoC, 2 kW charge/discharge and 95% efficiency in each direction. These are
shadow-planning assumptions only and must be confirmed before any later control release. Dynamic BMS/thermal limits will
eventually be allowed to tighten the configured envelope at runtime.

### PV measurements

The Solax and shed/Victron PV power entities remain optional measurement inputs. Total measured PV is the sum of configured
valid PV inputs.

`forecast_enabled` controls the built-in PV predictor and defaults to enabled when omitted.

## PV predictor

The predictor refreshes every 30 minutes. It requests today plus seven full future calendar days from Open-Meteo using
`knmi_seamless`. Open-Meteo uses KNMI HARMONIE AROME for the short-range forecast and extends the horizon with ECMWF.
The full hourly forecast remains available inside Energy Manager for the future planner; Home Assistant receives compact
summary sensors.

The physical model uses four PV planes:

- Front roof: 3.28 kWp, tilt 38°, Open-Meteo azimuth +50°.
- Rear pitched roof: 1.64 kWp, tilt 46°, azimuth -130°.
- Rear flat-roof section: 0.82 kWp, tilt 13°, azimuth -130°.
- Shed: 6.18 kWp, tilt 9.5°, azimuth -40°.

Each plane uses global tilted irradiance and a cell-temperature estimate. The three original CECEP planes retain the
existing -0.34 %/°C Pmax coefficient. The DMEGC DM515G12RT-B54HBW shed plane uses -0.29 %/°C. The shed starts without an
empirical correction until enough operating history exists.

### Seed calibration

The physical model is corrected only at measurable group level:

- Front group: front roof.
- Rear group: rear pitched + rear flat.
- Shed group: shed plane.

The initial front/rear calibration was derived from recorded forecast and string-production history from 20 August through
3 October 2026. It models time-of-day shading and a conservative seasonal change on the rear group. Weak irradiance blends
the correction toward the unshaded physical model because the historical shade penalty was much smaller under weak/diffuse
conditions. Seasonal calibration is clamped outside the observed period instead of extrapolated into unobserved seasons.

Future shed calibration must exclude curtailed intervals. The shed MPPT can stop producing when the ESS is full and the
MultiPlus has no AC demand/export path, so measured shed production is not always equal to available PV potential.

The predictor also records direct radiation, diffuse radiation and cloud cover in its hourly forecast points so later
calibration can test weather-dependent effects without changing the planner interface.

### Rolling forecast history

There is no longer a special evening lock-in time. Every successful 30-minute refresh is the current operational forecast.
The planner will always use the newest available forecast.

For later accuracy analysis, each successful refresh appends a compact revision to
`/data/pv_forecast_revisions.jsonl`. Each revision stores its issue time, model/calibration version, and daily front/rear/
shed/total energy for the complete current horizon. The full hourly profile is not archived indefinitely.

## PV forecast diagnostics

Version 0.5.0 publishes:

- `sensor.energy_manager_pv_forecast_status`
- `sensor.energy_manager_pv_forecast_today_energy`
- `sensor.energy_manager_pv_forecast_tomorrow_energy`
- `sensor.energy_manager_pv_forecast_next_7_days_energy`
- `sensor.energy_manager_pv_forecast_next_hour_power`

The next-7-days sensor state is the total predicted energy for the seven full future calendar days, excluding today. Its
`days` attribute contains a daily total and front/rear/shed split for each date. The today and tomorrow sensors remain for
simple dashboards. The next-hour sensor exposes calibrated and raw power by group plus cloud/direct/diffuse forecast data.

The old fixed `pv_day_ahead_today` and `pv_day_ahead_tomorrow` diagnostics are removed in v0.5.0 and their stale Home
Assistant states are deleted at startup.

## Canonical load measurements

Version 0.6.0 adds three derived power signals for later demand forecasting:

- `sensor.energy_manager_house_load_power` is the instantaneous AC house consumption. It is calculated as
  `grid net + Solax AC PV + ESS AC power`, using the normalized ESS convention where positive means discharge.
- `sensor.energy_manager_known_controllable_load_power` is the measured consumption of loads Energy Manager already knows
  it can schedule or control. Version 0.6 starts with EV charging only.
- `sensor.energy_manager_background_load_power` is `house load - known controllable load`. This is the signal intended to
  become the first background-demand predictor input.

The shed MPPT is deliberately not added to the AC house-load equation. It is DC-coupled to the ESS, so any shed power that
reaches the AC bus is already represented by `ess.power`. Adding the MPPT power separately would double-count it. The total
PV diagnostic still includes both Solax and shed production because that sensor answers a different question: total PV being
generated, not AC house consumption.

Configured-but-invalid inputs propagate to the derived signal as unavailable rather than silently assuming zero. An
unconfigured EV charging-power input contributes zero to known controllable load.

## Background-load predictor

Version 0.7.0 introduced five-minute sampling of `sensor.energy_manager_background_load_power` and a 15-minute-resolution
rolling forecast recalculated every 30 minutes. Version 0.8.0 keeps that predictor but moves long-term persistence to
InfluxDB 3 when database persistence is enabled.

The initial model is deliberately simple and robust. It first learns time-of-day behavior, then distinguishes weekday from
weekend behavior, and uses the same weekday from previous weeks once enough history exists. During the first week the
status remains `learning`; this is expected and does not degrade the main Energy Manager input-health status.

The current baseline model still uses the most recent 35 days as its active in-memory training window. That is a model
choice, not a retention limit. InfluxDB retains the underlying history indefinitely so later models can use seasonal and
multi-year information without having to start collecting data again.

Home Assistant receives compact summaries:

- `sensor.energy_manager_background_load_forecast_status`
- `sensor.energy_manager_background_load_forecast_next_hour_power`
- `sensor.energy_manager_background_load_forecast_next_24_hours_energy`
- `sensor.energy_manager_background_load_forecast_next_7_days_energy`

The seven-day sensor contains seven complete future calendar days in its `days` attribute. Forecast revisions are persisted
in InfluxDB when enabled. If the database is disabled or unavailable, the existing JSONL files remain as a fallback.

This model intentionally predicts only the current generic background signal. As individually measured loads such as the
heat pump are promoted to separate models later, they can be removed from the generic background signal without changing
the planner-facing forecast concept.

## Shadow planner

Version 0.11.0 adds the first planner foundation without scheduling or controlling devices yet. It aligns the existing
15-minute background-load forecast with the hourly PV-potential forecast on one 15-minute timeline and retains 48 hours
internally. `scheduled_load_w` is present but remains zero until flexible tasks such as EV charging are introduced.

Version 0.12 adds a read-only ESS feasibility projection. Roof PV is treated as AC-coupled while shed PV is treated as
DC-coupled. Shed energy therefore has to pass through the configured ESS/inverter discharge envelope before serving AC
loads; unused DC energy can charge the battery and any remaining energy is reported as curtailed potential. The simulation
uses the current measured SoC and a conservative greedy self-consumption policy. It is not yet the cost optimizer.

The plan now reports both the raw pre-control balance and the projected post-ESS grid import/export, battery SoC trajectory,
ESS AC power and DC-PV curtailment. This prevents the planner from assuming that all DC-coupled shed PV can directly serve
AC load simply because total PV energy exceeds demand.

Home Assistant diagnostics:

- `sensor.energy_manager_shadow_plan_status`
- `sensor.energy_manager_shadow_plan_next_24_hours_net_deficit_energy`
- `sensor.energy_manager_shadow_plan_next_24_hours_grid_import_energy`

The status attributes include compact 24-hour and 48-hour summaries plus the next three hours of 15-minute intervals.
The planner remains hard-coded shadow mode and cannot write to the ESS, EVSE or any other device.

## Background-load backtesting

Version 0.10.0 adds a runtime evaluation layer around the existing background-load predictor. The production predictor itself
is unchanged. The purpose of the evaluator is to identify useful model structure and additional inputs without baking
household-specific correction constants into the application at compile time.

The evaluator performs rolling-origin backtests using only observations that existed before each simulated forecast issue
time. It evaluates two issue times per day over the most recent 21-day evaluation window, after a minimum seven-day warm-up.
The current EnergyManager model is compared with three intentionally simple baselines:

- persistence: the recent three-hour median held constant;
- yesterday: the observed load from the same 15-minute slot one day earlier;
- last week: the observed load from the same slot seven days earlier.

Metrics are calculated for 1 h, 3 h, 6 h, 12 h and 24 h horizons. The primary comparison is mean absolute total-energy
error in kWh: the absolute difference between predicted and observed energy over the horizon. The evaluator also reports
signed energy bias, integrated absolute timing mismatch in kWh, and 15-minute peak-load underprediction. The latter compares
the observed peak interval with the prediction for that same interval and is retained because peak timing can matter for the
capacity tariff and ESS reserve decisions.

Pointwise wattage MAE, signed bias and p90 absolute error remain available as secondary shape diagnostics. The evaluator
reports both the best energy model and the best power-shape model for each horizon. Available-point and valid-issue coverage
remain visible because incomplete historical data can otherwise make one baseline look artificially better than another.
The current EnergyManager model is also broken down by daypart and weekday/weekend to identify recurring failure modes.

`sensor.energy_manager_background_load_backtest` exposes the latest result. Its state is the current model's 24-hour mean
absolute total-energy error in kWh; detailed candidate-model and contextual metrics are available as attributes. When
InfluxDB persistence is enabled, each model/horizon summary is also written to `background_load_backtest`. The backtest
refreshes at most once every 24 hours and never changes the production forecast automatically. A true economic-regret metric
in euros is intentionally deferred until the planner can replay tariff, battery, PV and peak-management decisions.

The intended development loop is: inspect runtime backtest results, decide which general feature or separately-modelled load
is justified, implement that runtime model behavior, then compare the new model against the same baselines.

## InfluxDB 3 persistence

Version 0.8.0 adds an optional InfluxDB 3 backend for Energy Manager's own time-series history. Configure the database
section with the URL that is reachable from the Energy Manager app, the `energy_manager` database name, and the restricted
read/write database token created in InfluxDB Explorer. For the separate InfluxDB app on the same HAOS VM, the HA VM's
direct LAN address and exposed port 8181 can be used.

When enabled, Energy Manager stores:

- five-minute canonical house/background/known-controllable load samples;
- each rolling PV forecast revision as per-day front/rear/shed/total energy;
- each rolling background-load forecast revision as per-day energy plus model/history metadata.

The database itself has indefinite retention. Energy Manager does not delete old InfluxDB data. Existing JSONL files from
v0.5/v0.7 are imported once on the first successful database connection and then renamed with a `.migrated` suffix.

`sensor.energy_manager_database_status` reports `connected`, `disabled`, or `error`. A database outage does not stop the
controller: Energy Manager falls back to local JSONL persistence so measurement and forecasting can continue.

## Input validity and freshness

The EV charging-power input treats values from -100 W up to 0 W as measurement noise and normalizes them to 0 W. More
negative values remain invalid so a real sensor-sign or configuration problem is not hidden.

Home Assistant measurement inputs are event-driven and also reconciled every 30 seconds. Invalid, unavailable or stale
configured measurement inputs degrade `sensor.energy_manager_input_health`. PV forecast health is deliberately separate in
`sensor.energy_manager_pv_forecast_status` because an external weather API failure must not invalidate local measurements.

## Safety

This release still contains no actuator and no command path. It cannot alter the ESS, EV charger, heat pump, ventilation,
or any other Home Assistant device.

## Legacy Home Assistant InfluxDB backfill

Version 0.9.2 can seed EnergyManager with selected historical Home Assistant data from the old InfluxDB 1.x instance.
The source URL, database, retention policy and optional read-only username/password are runtime configuration; configured
Home Assistant entity IDs are reused and never hardcoded.

Backfill is deliberately **selective and incremental**. The old Home Assistant database remains the broad historical archive;
the `energy_manager` database receives only signals that EnergyManager actually uses. Each imported source is tracked by its
logical role, configured entity ID, normalization version and covered time range. There is no global "migration completed"
flag. If a later EnergyManager version adds a separately modelled signal such as heat-pump power or outside temperature, that
new source can be imported then without copying unrelated Home Assistant sensors or re-importing sources already covered.

For the current load model, v0.9 selects grid import/export, ESS AC power, Solax AC PV and EV charging power. Five-minute
normalized source history is archived in `legacy_power_source`. ESS power is stored using EnergyManager's canonical sign
(positive discharge, negative charge), and small negative EV zero-offset readings are normalized the same way as live data.

Current canonical load history is reconstructed from those selected source records on a regular five-minute timeline:

- `house_load = grid_import - grid_export + solax_ac_pv + normalized_ess_ac_power`
- `background_load = house_load - ev_charging_power`

The legacy Home Assistant database behaves like sparse state history: an entity may not have a new row in every five-minute
bucket when its state has not changed. Version 0.9.3 therefore carries recent source values forward for up to 15 minutes.
After that window, stale EV charging power resolves to 0 W because an idle/disconnected charger commonly stops reporting;
grid, ESS and PV retain the stricter stale-value policy so material non-zero sensor outages are not silently extended.
If a carried value is within ±50 W, it is treated as inactive and resolves to zero after that freshness period; this permits
long legitimate zero periods such as no PV at night, no grid export, idle ESS or an idle EV. A material non-zero value older
than 15 minutes is not trusted, so a sensor outage is not silently stretched across hours or days. Each reconstruction chunk
is seeded from the latest archived source value before the chunk boundary. Reconstructed historical load is written to the
separate `legacy_house_load_v2` table. Live samples remain in `house_load`; the predictor merges both by timestamp and lets a
live sample win when both exist. This avoids relying on nondeterministic duplicate-point overwrites in InfluxDB 3.

Derived-history coverage is tracked separately using a derivation recipe and a fingerprint of the participating source
mappings. If source coverage extends, only the missing prefix/tail is derived. A future model that changes which separately
modelled loads are subtracted can use a new derivation recipe and rebuild the relevant historical background signal from the
selected archived sources.

This design intentionally does not migrate the complete Home Assistant database. Before the deprecated InfluxDB 1.x app is
eventually removed, keep a complete archival backup of that database so a currently-unused HA signal can still be recovered
if a future EnergyManager model needs it.

`sensor.energy_manager_database_status` reports backfill status plus source rows, sources updated, derived house/background
rows, skipped rows and the current overlapping source range. Backfill errors are non-fatal. If the legacy InfluxDB has
authentication enabled, configure a dedicated read-only user for `home_assistant`; EnergyManager sends those credentials with
HTTP Basic authentication.



### Backtest comparison fairness

Load-model accuracy is scored only on forecast intervals shared by all candidate models. Coverage remains a separate availability diagnostic.
