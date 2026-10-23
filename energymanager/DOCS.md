# EnergyManager 4 configuration

This app update replaces the V3 scheduler and dashboard API. Start in demo mode with
control disabled. Current detailed instructions are in [the runbook](docs/RUNBOOK.md).

Choose **Settings** in the app to configure it without editing JSON. Search entity
pickers by friendly name or entity ID; results show current states and units and are
filtered to compatible domains. In the HA app, **Use Home Assistant connection** fills
the Supervisor API connection. Its token stays on the server. Entity discovery is
read-only and also works while planning runs in demo mode.

Edit the grouped capacities, tariffs, readiness and connection fields, then choose
**Save settings**. Edits are validated and saved to the existing configuration file.
The previous bytes are preserved in a dated backup alongside it. If another editor
changed the file, reload before saving. Restart EnergyManager explicitly to apply
changes; saving does not change the running controller. Choose `configured` in the
HA app's Configuration tab when your inputs are ready. Initial settings are examples
and hardware control stays disabled unless explicitly commissioned.

Options select `mode` (`demo` or `configured`), `planning_budget_seconds` (one full-cycle
budget), and `configuration_file` (default `/config/energymanager.json`). At startup,
including demo mode, a missing file is created from the bundled example with remote
access and hardware control disabled. Its location is printed in the Log tab. Existing
files are never replaced. Find it using Samba, SSH or an editor in
`app_configs/<repository-id>_energy_manager/` (called `addon_configs` in some tools).
This folder appears as `/config` inside EnergyManager. Settings edits this same file,
so it remains transferable and survives app upgrades.

No V3 options/database are imported. Every physical capability, tariff, meter
prefix and entity/sign mapping must be reviewed. A complete issued seven-day forecast
is required; absent forecasts never become synthetic or zero inputs in configured mode.

Control defaults off. Explicit commissioning and exclusive-controller confirmations
are required before it can be enabled in the JSON file. Use the runbook's migration,
backup and rollback procedure. Version 4 writes `/data/energymanager-v4.sqlite3`; preserve
V3 data independently. The existing add-on slug/image is retained for normal updates.
