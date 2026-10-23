# EnergyManager 4 dashboard entry point

Overview and Planning are served by the main V4 application and available through its
Home Assistant sidebar ingress. The old V3 timeline implementation is replaced.

An optional Lovelace wrapper is provided in `energymanager-dashboard.yaml`. Copy
`energymanager-card.js` into your Home Assistant `www/` folder, register
`/local/energymanager-card.js` as a JavaScript module resource, and replace the YAML's
placeholder with this installation's authenticated `/api/hassio_ingress/.../` URL.
The wrapper uses `custom:energymanager-card`. Its source matches the app's packaged
`src/energymanager/assets/ha-card.js` and embeds the actual V4 pages.

The two pages retain live summaries, observed/planned powers and SoC, time navigation,
EV/ESS sessions, seven-day planning, grouped goals and scoped approvals. Local verification
uses http://127.0.0.1:8100/ with explicitly synthetic inputs. Actual Supervisor ingress
and installation-specific resource setup remain commissioning checks.
