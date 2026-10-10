EnergyManager Dashboard v1.6 (requires EnergyManager >=0.31.7)

Overview: planned total load (blue filled area), background (gray overlay), leaving EV charging visible as the upper band. Actual planned EV is load minus background. Supply is dashed: AC solar, grid, ESS with a five-color approximation. The ESS color estimates the MPPT share as min(1, DC PV / positive ESS AC output). It is not a measured attribution: conversion losses, simultaneous charging and dynamic battery power can change the real split. Negative ESS charge power has no source-colored trace in this chart; inspect Planning for signed ESS power. Capacity peak is an observed grid-import 15-minute reference, not a house-load limit.

ApexCharts mixed-series limitations: the areas deliberately use cumulative layers rather than chart.stacked=true, to keep independent supply lines from being stacked with consumption. This requires total load to be drawn before background.

1. Install EnergyManager v0.31.7 first.
2. Replace dashboard YAML in HA raw configuration editor.
3. Keep existing energymanager-timeline-card.js and its registered resource.
4. Hard refresh browser.

Validation: verify load top equals background + EV, ESS segment color changes with the forecast MPPT share, peak is in watts, and there are no missing-data/configuration errors.
