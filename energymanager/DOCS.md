# Energy Manager

Version 0.2.0 remains a read-only shadow-mode release. It introduces the first canonical grid-state input used by later
planning code.

## Configuration

### `grid_import_power_entity`

Set this to the Home Assistant sensor that reports momentary grid import power. The entity must report `W` or `kW` and is
expected to be non-negative.

### `grid_export_power_entity`

Set this to the Home Assistant sensor that reports momentary grid export power. The entity must report `W` or `kW` and is
expected to be non-negative.

Both entities are required for the canonical grid state. If either input is missing, `unknown`, `unavailable`, non-numeric,
or otherwise invalid, Energy Manager marks the derived grid state as unavailable rather than assuming the missing side is
zero.

### `log_level`

Available values: `debug`, `info`, `warning`, `error`.

## Diagnostic states

The app publishes:

- `sensor.energy_manager_status`
- `sensor.energy_manager_grid_import_power`
- `sensor.energy_manager_grid_export_power`
- `sensor.energy_manager_grid_power`

All power states are normalized to watts. Canonical net grid power uses this sign convention:

- positive = importing from the grid;
- negative = exporting to the grid.

The net value is calculated as `import - export`.

## Expected status values

- `starting`: process is starting.
- `waiting_for_configuration`: one or both grid input entities are not configured.
- `connected`: Home Assistant communication works and both grid inputs are valid.
- `degraded`: Home Assistant communication works, but one or both grid inputs are currently invalid/unavailable.
- `reconnecting`: the Home Assistant connection failed and the app is retrying.
- `stopping`: the app is shutting down.

## Safety

This version contains no device actuator and no command path. It cannot alter the ESS, EV charger, heat pump, ventilation,
or any other Home Assistant device.
