# Energy Manager

This repo houses a project that serves as a predictive home energy manager that integrates with Home Assistant. It's
likely not useful to anyone else since it's taylor made to my setup, however if it can be of any use to someone, be my
guest.

The project is being developed as a Home Assistant app.

## V3 preview

Version **3.0.0b1** implements explainable hierarchical planning and defaults to **shadow mode**.
Observations and forecasts become immutable requirements and snapshots; HiGHS solves explicit
priority stages; validated schedules feed the existing independent safety/dispatch loop.
Every decision can be archived, replayed and compared with a read-only counterfactual.

See [V3 architecture, migration, replay and shadow installation](docs/V3.md) and
[validation results](docs/V3-validation.md). Existing installations must explicitly configure
an EV departure minimum; an omitted minimum no longer inherits the preferred terminal target.

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

## Development and installation

Use Python 3.13 and install `requirements-dev.txt` in a virtual environment. Run
`ruff check energymanager/src tests tools` and `pytest`. A reproducible synthetic benchmark is
available through `PYTHONPATH=energymanager/src python tools/benchmark_v3.py`.

The preview has not been published. Follow the shadow-only local installation procedure in
[the V3 guide](docs/V3.md#shadow-only-installation-then-deliberate-activation) after review and
explicit deployment approval. Do not enable device control merely to inspect planning diagnostics.
