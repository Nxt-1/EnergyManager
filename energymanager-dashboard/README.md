# EnergyManager Dashboard v2.30 — Timeline alignment lifecycle fix

Your diagnostics confirmed the plot coordinates were valid (`apex-globals` gave 526.6–1484.5 CSS px),
while the timeline's reference rectangle returned x=0, making the previous computed right margin negative.
This is a timeline layout timing problem, not a wrong ApexCharts x-axis or time scale.

Changes **only** to `energymanager-timeline-card.js`:
- Schedule alignment after the card is mounted instead of measuring during synchronous HTML construction.
- Reject zero-width timeline rectangles; retry every two seconds until HA has laid out the timeline.
- Recover unmodified timeline bounds using its current margins, without resetting styles and forcing reflow.
- Recheck alignment when the plot bounds change or the dashboard is resized.
- Report meaningful diagnostics (`reason`, `timelineWidthPx`, and base/plot bounds).

No changes to the power/SoC graphs, chart data, five-minute statistics cache, fixed 06:00 window,
24-hour timestamps, task scheduling, card colors, or dashboard YAML.

## Installation

1. Replace `/config/www/energymanager-timeline-card.js` with the included file.
2. Set Home Assistant's **JavaScript module** resource URL to `/local/energymanager-timeline-card.js?v=230`.
3. Hard-refresh the dashboard; if HA is still serving an older file, clear its frontend cache.
4. Keep the existing YAML (the archive includes a byte-identical copy of v2.29).

## Validation needed

After both graphs and timeline have rendered, run:

```js
window.energyManagerPlotAlignmentStatus
```

Expected: `plotFound: true`, `aligned: true`, `reason: 'ok'`, realistic `timelineBaseLeftPx` (not 0),
left and right timeline 06:00 markers lining up with the power plot's boundaries. Check once again
with the Chrome console closed / window resized. Click a task to verify its details still work.

If alignment remains false, send the **full diagnostic object**, especially `reason`,
`timelineWidthPx`, `timelineBaseLeftPx`, `timelineBaseRightPx`, `powerPlotLeftPx`,
`powerPlotRightPx`.

## Checks

- JavaScript syntax: check passed.
- Simulated zero-width initialization, deferred retry, and repeated alignment: check passed.
- YAML byte-identical to v2.29.
- Live browser geometry must be verified in Home Assistant.
