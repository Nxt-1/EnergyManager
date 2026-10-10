# EnergyManager dashboard v1.2

Native Home Assistant dashboard using the existing EnergyManager entities.

## Install

In Home Assistant: Settings → Dashboards → select the EnergyManager dashboard → Raw configuration editor. Replace the current YAML with `energymanager-dashboard.yaml`.

ApexCharts Card must be installed through HACS for the forecast plots. Native History Graph cards are used for recorded measurements. No EnergyManager add-on upgrade is needed.

## Changes since v1.1

- Removed the overview explanation and redundant controller-status card; diagnostics remain on the Diagnostics tab.
- Shortened the 24-hour forecast names and power/SoC legend labels.
- Simplified the Overview ApexCharts configuration and removed fixed hex colors throughout to allow theme-responsive colors.
- Removed redundant explanation cards in Planning, but retained seven-day planning, Performance, and Diagnostics views.
- Kept existing `shadow_plan` entity identifiers for compatibility; their on-screen naming no longer uses the legacy term.

## Notes

ApexCharts is still required to graph forward-looking plan data stored in sensor attributes; native HA history graphs cannot plot arbitrary future time series. Full backend terminology refactoring must be carried out in a separate EnergyManager release, with entity-ID migration and tests.
