# InfluxDB 3 Enterprise Home Assistant app

A small Home Assistant app wrapper around the official InfluxDB 3 Enterprise image.

It is intended to provide persistent time-series storage for EnergyManager on the same
Home Assistant OS VM while keeping the database in a separate container.

The app uses the free At-Home license, limits InfluxDB to two CPU cores, enables the
integrated Explorer UI, and stores all persistent database state under `/data`.
