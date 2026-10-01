# Energy Manager

This repo houses a project that serves as a predictive home energy manager that integrates with Home Assistant. It's
likely not useful to anyone else since it's taylor made to my setup, however if it can be of any use to someone, be my
guest.

The project is being developed as a Home Assistant app.

## Architecture direction

The intended high-level architecture is:

```text
Independent predictors
        ↓
Load manager / task generator
        ↓
Planner
        ↕
Actuators
        ↕
Controllable devices
```

The planner owns both forward scheduling and management of unplanned conditions. Actuators own device-specific control
behaviour and report their actual state and dynamic capability back to the planner. Actuators do not coordinate directly
with one another.

## Repository layout

```text
energymanager/          Home Assistant app
.github/workflows/      CI and image publishing
tests/                  Unit tests
repository.yaml         Home Assistant custom repository metadata
```

## Versioning and updates

Home Assistant uses `energymanager/config.yaml` as the source of the available app version. A deployable change must
bump that version. Pushing the version bump to `main` triggers the publish workflow, which builds and publishes the
matching GHCR image. Home Assistant can then show the new version as an available update; installation remains manual.

Normal commits that do not change `energymanager/config.yaml` run CI but do not publish a deployable image.

## First installation

1. Push this repository to `https://github.com/Nxt-1/EnergyManager`.
2. Confirm the `Publish app image` GitHub Action completes successfully for version `0.1.0`.
3. Confirm the GHCR package can be pulled anonymously. If GitHub created it as private, change the package visibility to
   public once. Home Assistant must be able to pull the image without registry credentials.
4. In Home Assistant, add `https://github.com/Nxt-1/EnergyManager` as a custom app repository.
5. Install **Energy Manager**.
6. In the app configuration, set `grid_power_entity` to a numeric Home Assistant entity representing net grid power.
7. Start the app and inspect its logs.

The app creates temporary diagnostic states through the Home Assistant REST API:

- `sensor.energy_manager_status`
- `sensor.energy_manager_observed_grid_power`
