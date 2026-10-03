# Energy Manager

Energy Manager is currently a read-only shadow-mode Home Assistant app. Version 0.4.1 adds the first predictor: a
four-plane PV forecast running directly in Python.

## Configuration

Entity IDs remain runtime configuration and are not hardcoded. Existing Grid, ESS, PV and EV configuration is preserved.

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

The predictor requests three local calendar days from Open-Meteo using the KNMI HARMONIE AROME Netherlands model. It uses
four physical PV planes:

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

### Day-ahead snapshots

After 20:15 local time, the first successful forecast stores a snapshot for the following day under
`/data/pv_forecast_snapshots.json`. App data survives normal app updates. Snapshots are kept for approximately 90 days and
will later support forecast calibration.

## PV forecast diagnostics

Version 0.4.1 adds:

- `sensor.energy_manager_pv_forecast_status`
- `sensor.energy_manager_pv_forecast_today_energy`
- `sensor.energy_manager_pv_forecast_tomorrow_energy`
- `sensor.energy_manager_pv_forecast_next_hour_power`
- `sensor.energy_manager_pv_day_ahead_today_energy`
- `sensor.energy_manager_pv_day_ahead_tomorrow_energy`

Daily forecast sensors expose front, rear and shed energy as attributes. The next-hour sensor exposes calibrated and raw
power by group plus the available cloud/direct/diffuse forecast values.

## Input validity and freshness

Home Assistant measurement inputs are event-driven and also reconciled every 30 seconds. Invalid, unavailable or stale
configured measurement inputs degrade `sensor.energy_manager_input_health`. PV forecast health is deliberately separate in
`sensor.energy_manager_pv_forecast_status` because an external weather API failure must not invalidate local measurements.

## Safety

This release still contains no actuator and no command path. It cannot alter the ESS, EV charger, heat pump, ventilation,
or any other Home Assistant device.
