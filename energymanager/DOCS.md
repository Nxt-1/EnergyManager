# Energy Manager

Energy Manager is currently a read-only shadow-mode Home Assistant app. Version 0.5.0 extends the Python PV predictor to a
continuously refreshed week-ahead forecast and stores compact forecast revisions for later accuracy analysis.

## Configuration

Entity IDs remain runtime configuration and are not hardcoded. Existing Grid, ESS, PV and EV configuration is preserved.
There are no configuration-schema changes from v0.4.1.

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

## Input validity and freshness

Home Assistant measurement inputs are event-driven and also reconciled every 30 seconds. Invalid, unavailable or stale
configured measurement inputs degrade `sensor.energy_manager_input_health`. PV forecast health is deliberately separate in
`sensor.energy_manager_pv_forecast_status` because an external weather API failure must not invalidate local measurements.

## Safety

This release still contains no actuator and no command path. It cannot alter the ESS, EV charger, heat pump, ventilation,
or any other Home Assistant device.
