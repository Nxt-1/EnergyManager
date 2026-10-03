# Changelog

## 0.2.0

- Replaced the single grid-power input with separate momentary import and export entities.
- Added canonical net grid power (`import - export`), with positive values meaning import and negative values meaning export.
- Added separate normalized import/export diagnostic sensors.
- Added degraded-state handling: invalid or unavailable input never silently falls back to zero.
- Generalized the Home Assistant WebSocket observer to subscribe to multiple entities on one connection.
- Rejects non-finite power values and negative values from the separate import/export inputs.
- Updated GitHub Actions to current Node 24/ESM action generations.
- Remains read-only; no device control is present.

## 0.1.0

- Initial Home Assistant app skeleton.
- Internal Home Assistant REST API access through the Supervisor proxy.
- Home Assistant WebSocket state subscription for one configured grid-power entity.
- Read-only shadow-mode diagnostics.
- Automatic reconnect with bounded exponential backoff.
- CI and GHCR publishing workflows.
