# Energy Manager

Energy Manager is currently a read-only shadow-mode Home Assistant app. Version 0.7.0 adds the first rolling background-demand predictor on top of the canonical load signals.

## Configuration

Entity IDs remain runtime configuration and are not hardcoded. Existing Grid, ESS, PV and EV configuration is preserved.
There are no configuration-schema changes from v0.5.1.

### Grid

Configure separate momentary import and export power entities. Both must report `W` or `kW` and must be non-negative.
Canonical grid power is `import - export`: positive means import, negative means export.

### ESS

ESS SoC is normalized to percent. ESS power is normalized so positive means discharge and negative means charge.

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

Version 0.7.0 samples `sensor.energy_manager_background_load_power` internally every five minutes and keeps a local
35-day history in `/data/background_load_history.jsonl`. Forecasts are recalculated every 30 minutes at 15-minute
resolution and retained in Python for the future planner.

The initial model is deliberately simple and robust. It first learns time-of-day behavior, then distinguishes weekday from
weekend behavior, and uses the same weekday from previous weeks once enough history exists. During the first week the
status remains `learning`; this is expected and does not degrade the main Energy Manager input-health status.

Home Assistant receives compact summaries:

- `sensor.energy_manager_background_load_forecast_status`
- `sensor.energy_manager_background_load_forecast_next_hour_power`
- `sensor.energy_manager_background_load_forecast_next_24_hours_energy`
- `sensor.energy_manager_background_load_forecast_next_7_days_energy`

The seven-day sensor contains seven complete future calendar days in its `days` attribute. Each 30-minute forecast revision
is also appended to `/data/background_load_forecast_revisions.jsonl` so prediction accuracy can be evaluated later without
freezing the live operational forecast.

This model intentionally predicts only the current generic background signal. As individually measured loads such as the
heat pump are promoted to separate models later, they can be removed from the generic background signal without changing
the planner-facing forecast concept.

## Input validity and freshness

The EV charging-power input treats values from -100 W up to 0 W as measurement noise and normalizes them to 0 W. More
negative values remain invalid so a real sensor-sign or configuration problem is not hidden.

Home Assistant measurement inputs are event-driven and also reconciled every 30 seconds. Invalid, unavailable or stale
configured measurement inputs degrade `sensor.energy_manager_input_health`. PV forecast health is deliberately separate in
`sensor.energy_manager_pv_forecast_status` because an external weather API failure must not invalidate local measurements.

## Safety

This release still contains no actuator and no command path. It cannot alter the ESS, EV charger, heat pump, ventilation,
or any other Home Assistant device.
