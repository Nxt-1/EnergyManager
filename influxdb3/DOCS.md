# InfluxDB 3 Enterprise

This Home Assistant app runs a single-node InfluxDB 3 Enterprise instance for
EnergyManager and future Home Assistant time-series storage.

## First start

1. Enter the email address to use for the free InfluxDB At-Home license.
2. Start the app.
3. Check the log for the license activation request.
4. Open the verification email from InfluxData and confirm the At-Home license.
5. Open **Web UI** from the app page.
6. On the first-run Explorer setup page, create the administrator account.
7. Store the operator token shown during setup somewhere safe. It is only shown once.

The app pins InfluxDB Enterprise 3.12.0, uses local persistent storage, and limits
InfluxDB to two CPU cores to match the At-Home license.

## Storage

All persistent data is stored below:

`/data/influxdb3`

This includes the InfluxDB object store, Explorer state, the license, and locally
generated authentication keys.

Removing and reinstalling the app may remove its `/data` directory. Treat the database
as persistent infrastructure and include it in the Home Assistant backup strategy.

## Network

InfluxDB and the integrated Explorer UI use TCP port `8181`.

The Explorer UI is served by InfluxDB itself. Username/password authentication is
enabled. Do not expose port 8181 directly to the public internet.

## EnergyManager database

After the server is running, create a database named:

`energy_manager`

Use infinite retention (the default).

Create a resource token for EnergyManager with read/write access only to that database.
EnergyManager should use that resource token rather than the operator/admin token.
