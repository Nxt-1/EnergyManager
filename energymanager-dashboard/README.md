# EnergyManager native Home Assistant dashboard — v1

## Install
1. Ensure **ApexCharts Card** is installed with HACS and its Lovelace resource is loaded.
2. Home Assistant → Settings → Dashboards → Add dashboard → New dashboard, and open its raw configuration editor (or use a YAML-mode dashboard).
3. Paste the contents of `energymanager-dashboard.yaml` into the dashboard raw configuration editor.
4. Save. The dashboard has Overview, Planning and Performance views.

If creating a dashboard with a built-in default card, remove the default view before pasting.

## Important limitations
- Day 1–7 fields are HA state *attributes* and will be available only while the add-on publishes them.
- ApexCharts plots the daily chunks as separate series to cover the entire 672-interval horizon.
- The display shows a **rolling** schedule from the latest solve; historical plans cannot yet be displayed here.
- Day series use `load_w`, `pv_ac_w`, `pv_dc_w`, `ess_w`, `grid_w`, `ess_soc`, `ev_soc`. There is no separate `ev_power_w` in the published plan slots.
- PV DC power is internal to battery charging and is not summed into the grid AC balance.
- Performance uses HA Recorder; ensure those sensors are retained in history.
- If custom cards show as unavailable, verify the ApexCharts frontend resource is correctly registered.

## Check after installation
- Overview: live power and controller status load.
- Planning: timeline spans seven days and both batteries' SoC tracks appear.
- Performance: real history appears for power and SoC.
- Check the plan-day timestamps update on subsequent MILP solves.

## Diagnostics tab (v1.1)

This version adds live control-health entities and the last 30 notification-manager events,
including pending, suppressed and delivered alerts. Event history is currently in-memory
and resets when the add-on restarts. Uses `recent_events` exposed from EnergyManager v0.31.3.
