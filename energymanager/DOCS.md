# EnergyManager 4 configuration

This app update replaces the V3 scheduler and dashboard API. Start in demo mode with
control disabled. Current detailed instructions are in [the runbook](docs/RUNBOOK.md).

Options select `mode` (`demo` or `configured`), `planning_budget_seconds` (one full-cycle
budget), and `configuration_file` (default `/config/energymanager.json`). At startup,
including demo mode, a missing file is created from the bundled example with remote
access and hardware control disabled. Its location is printed in the Log tab. Existing
files are never replaced. Find it using Samba, SSH or an editor in
`app_configs/<repository-id>_energy_manager/` (called `addon_configs` in some tools).
This folder appears as `/config` inside EnergyManager. Edit the generated file before
using configured inputs, then restart the app to load changes.

No V3 options/database are imported. Every physical capability, tariff, meter
prefix and entity/sign mapping must be reviewed. A complete issued seven-day forecast
is required; absent forecasts never become synthetic or zero inputs in configured mode.

Control defaults off. Explicit commissioning and exclusive-controller confirmations
are required before it can be enabled in the JSON file. Use the runbook's migration,
backup and rollback procedure. Version 4 writes `/data/energymanager-v4.sqlite3`; preserve
V3 data independently. The existing add-on slug/image is retained for normal updates.
