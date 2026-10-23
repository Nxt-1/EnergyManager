# Installation forecasting

The configured application builds its own forecasts using the original weather source
and recovered installation parameters below, restored in4.0.5. Since4.0.6 the HA
connection is automatic and the legacy forecast URL field is removed. See SETTINGS.md
for the current connection, notification and hardware-switch behavior.

## Recovered source and PV installation

The preserved implementation was found locally in
`gpt/architecture/v4-promotion-2026-10-23/legacy-application/src/energymanager/`:
`open_meteo.py`, `pv_forecast.py`, `pv_service.py`, `load_forecast.py`, `load_service.py`
and the AC/DC mapping in `planner.py`. The archived files remain untouched.
`forecast-restoration-verification.json` records source SHA256 checksums and comparisons.
No missing plane values, coordinates or calibration parameters were invented.

Weather comes from `https://api.open-meteo.com/v1/forecast`, model `knmi_seamless`.
Latitude and longitude come from Home Assistant's existing `zone.home` attributes.
Each plane requests tilted irradiance, temperature, cloud cover and direct/diffuse
radiation, using the original Europe/Brussels timezone and these exact parameters:

| Plane | Peak power | Tilt | Open-Meteo azimuth | Temperature coefficient | Planner channel |
|---|---:|---:|---:|---:|---|
| Front roof | 3,280 Wp | 38° | 50° | −0.0034 / °C | AC |
| Rear roof | 1,640 Wp | 46° | −130° | −0.0034 / °C | AC |
| Rear flat roof | 820 Wp | 13° | −130° | −0.0034 / °C | AC |
| Shed | 6,180 Wp | 9.5° | −40° | −0.0029 / °C | DC |

The original physical model remains:
`cell_temperature = ambient_temperature + 0.0275 × irradiance`;
`power = peak_Wp × max(0, irradiance)/1000 × max(0, 1 + coefficient × (cell_temperature − 25))`.
Ambient temperature is the mean of the previous/current front-roof hourly temperatures,
with the first available temperature used for the first record, as before.

Original empirical calibration version: **2026-10-03-seed**. The archived source describes
front/rear history from 20 August to 3 October 2026; that is preserved historical evidence,
not a newly validated installation measurement. The shed has no empirical adjustment.

| Local ending hour | Front factor | Rear day239 | Rear day254 | Rear day269 |
|---|---:|---:|---:|---:|
| 08–10 | 0.68 | 0.93 | 0.91 | 0.82 |
| 11–12 | 0.81 | 0.93 | 0.88 | 0.91 |
| 13–14 | 0.98 | 0.76 | 0.71 | 0.63 |
| 15–18 | 1.00 | 0.57 | 0.61 | 0.50 |
| 19–20 | 0.57 | 0.54 | 0.45 | 0.52 |

Other hours use factor1. Rear factors interpolate linearly by day of year and clamp
outside the anchor range, matching the original seasonal behavior. Rear irradiance is
weighted by its1,640/820Wp planes. Both corrections blend toward1 under weak irradiance:
`strength = clamp((irradiance − 75)/275, 0, 1)`;
`applied_factor = 1 − strength × (1 − base_factor)`.

## Time coverage, freshness and independence

Hourly solar values describe the preceding hour. New requests use Unix timestamps so
both occurrences of the autumn clock-change hour remain distinct. Calibration still
uses Brussels local time. Nine calendar weather days provide a buffer for the complete
rolling168-hour plan, including late-evening starts. This changes coverage handling,
not the selected source, installation parameters or model formulas.

[Open-Meteo's KNMI documentation](https://open-meteo.com/en/docs/knmi-api) describes
KNMI Seamless with ECMWF continuation up to15 days and preceding-hour solar averages.
The client rejects null/nonfinite required values, duplicate/gapped/misaligned hours,
missing home coordinates and incomplete coverage. Missing production is never filled
with zero or extrapolated. Hourly solar and quarter-hour household forecasts are
resampled onto the unchanged planning grid of at most5min, preserving energy.

Weather refresh runs in its own task every30min, with a60s retry after failure. HTTP
cannot hold up the5s measurement poll or independent control. Failed refreshes may use
cached weather only within the configured freshness/coverage limits; the old issuance
timestamp is preserved. Default forecast freshness remains2h. Fresh measured ESS
balancing stays available independently of forecast-dependent purchases.

## Household learning and persistence

The recovered **2026-10-04-baseline** model consumes actual reconstructed household
background demand, excluding controlled EV/ESS flows. One observation per5min is stored
in a new append-only `load_samples` table in the existing V4 SQLite database.
The active model uses35 days; historical evidence is not purged. Forecasts rebuild
every30min and include the current partial quarter-hour.

Per local quarter-hour slot, the predictor uses the median of at least two same-weekday
days, otherwise at least three weekday/weekend days, otherwise at least three available
days for that slot. While history is insufficient it uses the median of the latest3h
of measured samples. No synthetic household default is substituted. The dashboard
banner reports learning state and sample count; API `forecast_status` records methods,
history length, weather time and refresh errors. Samples survive restarts. V3 files and
databases are not silently imported or modified; a new V4 history starts learning from
current measurements immediately.

The store retains latest PV raw/corrected values, plane metadata and assembled inputs;
accepted decision archives retain the exact forecast inputs used for each plan.
Existing configuration files and user goals remain intact. New configured startup
does not inherit demonstration journeys. Rollback to4.0.4 leaves the additional SQLite
table unused; back up the JSON/database first, and remember4.0.4 required an external
prepared forecast service. Live installation location, telemetry topology and physical
control remain commissioning checks; offline/public-reference verification is not
live commissioning.
