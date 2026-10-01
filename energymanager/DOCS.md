# Energy Manager

Version 0.1.0 is a connectivity/shadow-mode milestone only.

## Configuration

### `grid_power_entity`

Optional during first startup. Set this to a numeric Home Assistant power entity, for example a net P1/grid-power sensor.
The entity must report power in `W` or `kW`.

The value is only observed. Energy Manager does not write to the configured entity or command any device.

### `log_level`

Available values: `debug`, `info`, `warning`, `error`.

## Diagnostic states

The app publishes:

- `sensor.energy_manager_status`
- `sensor.energy_manager_observed_grid_power`

The second sensor is normalized to watts. Its sign is preserved exactly as reported by the configured source entity; no
import/export sign convention is assumed in this release.

## Expected status values

- `starting`: process is starting.
- `waiting_for_configuration`: no `grid_power_entity` has been configured.
- `connected`: REST and WebSocket communication with Home Assistant are working.
- `reconnecting`: the Home Assistant connection failed and the app is retrying.
- `stopping`: the app is shutting down.

## Safety

This version contains no device actuator and no command path. It cannot alter the ESS, EV charger, heat pump, ventilation,
or any other Home Assistant device.
