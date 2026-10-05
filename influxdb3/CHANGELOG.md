# Changelog

## 0.1.1

- Added conservative memory limits for running InfluxDB on the same HAOS VM as Home Assistant.
- Limit the query execution pool and file cache to 512 MB each.
- Limit the replica buffer to 512 MB and compactor input budget to 1 GB.
- Reduce WAL and snapshot buffers for the low-volume EnergyManager workload.
- No database format, license, authentication or port changes.

## 0.1.0

- Initial Home Assistant app wrapper.
- Pin InfluxDB 3 Enterprise 3.12.0.
- Enable the integrated Explorer UI.
- Enable username/password authentication and first-run administrator setup.
- Persist database data, the At-Home license, and generated authentication keys.
- Limit InfluxDB to two CPU cores.
