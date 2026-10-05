# InfluxDB 3 Enterprise

This Home Assistant app runs a single-node InfluxDB 3 Enterprise instance for
EnergyManager and future Home Assistant time-series storage.

## First start

1. Enter the email address to use for the free InfluxDB At-Home license.
2. Start the app.
3. Check the log for the license activation request.
4. Open the verification email from InfluxData and confirm the At-Home license.
5. Open the Web UI using the HA VM's direct LAN IP on port 8181 if the generated hostname does not route that port.
6. On the first-run Explorer setup page, create the administrator account.
7. Create a database named `energy_manager` without a retention period.
8. Create a database token with read/write access only to `energy_manager` and store it safely.

The app pins InfluxDB Enterprise 3.12.0 and limits InfluxDB to two CPU cores to match the At-Home license.
Version 0.1.1 also applies conservative memory budgets suitable for the low-volume EnergyManager workload on the same
HAOS VM as Home Assistant.

## Storage

All persistent data is stored below:

`/data/influxdb3`

This includes the InfluxDB object store, Explorer state, the license, and locally generated authentication keys.

## Network

InfluxDB and the integrated Explorer UI use TCP port `8181`.

The Explorer UI is served by InfluxDB itself. Username/password authentication is enabled. Do not expose port 8181
directly to the public internet.

## EnergyManager database

EnergyManager should use the `energy_manager` database with no retention period and a restricted read/write database
token. Do not use the administrator account or an all-database token for the EnergyManager app.
