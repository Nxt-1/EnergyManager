# EnergyManager 4 configuration

This app update replaces the V3 scheduler and dashboard API. Start in demo mode with
control disabled. Current detailed instructions are in [the runbook](docs/RUNBOOK.md).

Options select `mode` (`demo` or `configured`), `planning_budget_seconds` (one full-cycle
budget), and `configuration_file` (default `/config/energymanager.json`). Put a reviewed
copy of `configuration.example.json` in the app configuration folder before configured
mode. No V3 options/database are imported. Every physical capability, tariff, meter
prefix and entity/sign mapping must be reviewed. A complete issued seven-day forecast
is required; absent forecasts never become synthetic or zero inputs in configured mode.

Control defaults off. Explicit commissioning and exclusive-controller confirmations
are required before it can be enabled in the JSON file. Use the runbook's migration,
backup and rollback procedure. Version 4 writes `/data/energymanager-v4.sqlite3`; preserve
V3 data independently. The existing add-on slug/image is retained for normal updates.
