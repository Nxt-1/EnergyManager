# EnergyManager Dashboard v1.7

Install the EnergyManager v0.31.8 add-on first. Replace the dashboard raw YAML with `energymanager-dashboard.yaml`. The timeline JavaScript is unchanged from v1.6.

Each Overview power tile now shows the live power and today's actual/estimated energy (kWh). The Peak tile shows the configured monthly highest 15-minute import average and current P1 quarter-hour average; no guessed peak is substituted when these inputs are absent.

In the add-on `monitoring` settings, configure any available `*_energy_entity` to a **daily-reset** energy counter (kWh/Wh). If an entity is a lifetime increasing counter, turn on the corresponding `*_counter_cumulative` option: the first observation becomes the reference for that day (so the first partial day is incomplete); a new baseline is established on the next day. With no valid energy counter, EnergyManager integrates the corresponding observed power from the point it starts observing and tags the result `estimated_from_power`. The fallback is an estimate, not a recovered historical meter value. Optional counters do not affect control health.

Configure `monthly_peak_entity` for the highest 15-minute grid-import average **this month**, and `quarter_hour_average_entity` for the P1 average **in the current quarter-hour**. Both must be power sensors in W or kW.

The custom monitor sensors are `sensor.energy_manager_<channel>_energy_today` for channels `grid_import`, `grid_export`, `pv_ac`, `pv_dc`, `house`, `ev`, `ess_charge`, `ess_discharge`, and `sensor.energy_manager_monthly_peak_kw` / `sensor.energy_manager_quarter_hour_average_kw`.

## Validation needed

- GitHub Actions Ruff and pytest pass.
- Inspect effective add-on monitoring options and confirm the selected HA IDs.
- Verify `sensor.energy_manager_grid_import_energy_today`, `sensor.energy_manager_pv_ac_energy_today`, and any other configured counters. Check `source` and `date` attributes.
- Check peak values against the P1 readings, especially W/kW conversion.
- Verify ESS, EV and MILP remain healthy after installation.
