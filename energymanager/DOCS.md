# Energy Manager

Version 0.3.0 remains a fully read-only shadow-mode release. It introduces the first normalized internal house state and
expands the Home Assistant inputs beyond the grid.

## Configuration

Inputs are grouped by function on the app Configuration page. Entity IDs remain runtime configuration; none are hardcoded
in Energy Manager.

### Grid

Configure separate momentary import and export power entities. Both must report `W` or `kW` and must be non-negative.
Energy Manager derives canonical grid power as:

`grid power = import power - export power`

Positive canonical grid power means import; negative means export.

### ESS

- **SoC entity**: percentage from 0 to 100.
- **Power entity**: power in W or kW.
- **Positive ESS power means**: tells Energy Manager how the source sensor signs its value.

Internally, ESS power is normalized so **positive means discharge** and **negative means charge**.

### PV

Configure the Solax and/or shed/Victron PV power entities. Each configured input must report non-negative power in W or kW.
Total PV power is the sum of all configured valid PV inputs.

### EV

- **SoC entity**: percentage from 0 to 100.
- **Connected entity**: common binary/connection states such as on/off, true/false or connected/disconnected.
- **Charging power entity**: non-negative charging power in W or kW.

### Log level

Available values: `debug`, `info`, `warning`, `error`.

## Input validity and freshness

Energy Manager subscribes to Home Assistant state changes for fast updates and also refreshes all configured inputs every
30 seconds. This periodic refresh prevents a sensor that simply remains at the same value from being mistaken for stale
data. The internal input model records the normalized value, source entity, source timestamp, observation time and any
validation error.

An invalid/unavailable configured input makes the aggregate input health `degraded`. Grid import/export remain the minimum
configuration needed for overall status `connected`.

## Diagnostic states

Depending on what is configured, v0.3.0 publishes:

- `sensor.energy_manager_status`
- `sensor.energy_manager_input_health`
- `sensor.energy_manager_grid_import_power`
- `sensor.energy_manager_grid_export_power`
- `sensor.energy_manager_grid_power`
- `sensor.energy_manager_ess_soc`
- `sensor.energy_manager_ess_power`
- `sensor.energy_manager_pv_solax_power`
- `sensor.energy_manager_pv_shed_power`
- `sensor.energy_manager_pv_total_power`
- `sensor.energy_manager_ev_soc`
- `binary_sensor.energy_manager_ev_connected`
- `sensor.energy_manager_ev_charging_power`

The obsolete v0.1.0 `sensor.energy_manager_observed_grid_power` state is removed automatically on startup.

## Configuration migration

When upgrading from v0.2.0, Energy Manager understands the previous flat grid options and attempts to migrate them to the
new grouped Grid configuration automatically.

## Safety

This release contains no actuator and no command path. It cannot alter the ESS, EV charger, heat pump, ventilation, or any
other Home Assistant device.
