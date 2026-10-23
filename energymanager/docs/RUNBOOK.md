# Run, configure, review and roll back

## Local use

Use Python3.13 (also tested on3.12 during development). Run from `energymanager/`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m energymanager --port 8100 --budget 120
```

Open http://127.0.0.1:8100/ . Overview shows measured/synthetic and planned powers,
battery states and separate EV/ESS sessions. Planning shows the entire seven days.
Add/edit/remove timed SoC goals or total-distance journeys. Expand reasons, sessions
and history for explanations and immutable decision evidence. Approval buttons act on
the displayed revision. Hardware control is disabled by default. The demo advances an
explicitly synthetic device model and does not use installation inputs or databases.
Settings can separately read HA's entity list to prepare the configured installation.

This workspace's prepared environment is `.venv313/Scripts/python.exe`. Dependencies
are isolated, not registered system-wide. `requirements.lock` and `requirements-dev.lock`
contain the tested exact Windows3.13 resolution; Linux wheels/container must be checked
on the target host. The command above installs a source editable package; the built
wheel under `dist/` supports a separate installation without repository imports.

```powershell
.\.venv313\Scripts\python.exe -m pytest -q
.\.venv313\Scripts\python.exe -m ruff check src tests tools
.\.venv313\Scripts\python.exe -m mypy src/energymanager
node --check src/energymanager/assets/app.js
.\.venv313\Scripts\python.exe tools/offline_e2e.py
.\.venv313\Scripts\python.exe tools/benchmark.py --case mixed --budget 120
.\.venv313\Scripts\python.exe tools/benchmark.py --case winter --budget 120
.\.venv313\Scripts\python.exe tools/benchmark.py --case permission --budget 120
.\.venv313\Scripts\python.exe -m build --no-isolation
```

Run benchmarks sequentially, with the dev server stopped. Real HiGHS results depend on
machine and timing; inspect per-stage incumbents/bounds and validation, not only the
last solver status. Raw synthetic evidence is written under ignored `artifacts/` and
compact reports under `docs/`. No coarse distant horizon is used.

Frozen replay accepts a snapshot or exported `{snapshot,result}` decision, verifies an
available input checksum, and produces fresh evidence. `--budget` explicitly sets the
replay budget; matching the original value preserves that policy field. Solver time
limits can change incumbents; replay does not promise bit-identical optimization.

```powershell
.\.venv313\Scripts\python.exe -m energymanager --fixture artifacts/release-mixed.json --solve artifacts/replay.json --budget 120
```

## Main-project version 4 update

`config.yaml` now advertises **4.0.2** for the existing `energy_manager` Home Assistant
app and `ghcr.io/nxt-1/energymanager` image. It keeps ingress port8099 and manual startup.
The packaged Python distribution, CLI and module are all named `energymanager`. The
former standalone candidate has been moved into this main app; the old V3 modules,
tests and dashboard are replaced. The separate InfluxDB app is unchanged.

V4 starts in demo mode. On startup, including demo mode, the app creates a missing
`/config/energymanager.json` from its bundled synthetic example and logs the path.
The app configuration mount is writable for initialization. Existing files are never
replaced, including empty or unfinished files. Creation failures stop startup with a
clear error. Configured mode reads this file. It writes `/data/energymanager-v4.sqlite3`, separately
from V3 data. V3 options and database files are not automatically imported. Review the
mapping below; an old options object cannot enable V4 control. Existing JSON fixtures
and immutable candidate decisions remain usable for offline replay.

The app configuration mount follows the
[Home Assistant configuration contract](https://contributors.home-assistant.io/apps/reference/configuration/).
Ingress accepts Supervisor172.30.32.2 with its authenticated ingress path; direct dev
access remains localhost only, following the
[ingress boundary](https://developers.home-assistant.io/docs/apps/presentation/).
The dashboard wrapper uses `custom:energymanager-card` and embeds these pages. Its
setup is in ../../energymanager-dashboard/README.md. Existing installed dashboards
need the reviewed V4 resource/configuration update; no live dashboard was changed here.

Docker is unavailable locally. The V4.0.0 CI and image workflows verified the Linux
container build and publication; evidence is in VERIFICATION.md and ci-verification.json.
Supervisor installation and physical deployment remain separate checks. A target host
can run `docker build --build-arg BUILD_VERSION=4.0.2 -t energymanager:4.0.2 .` from this
directory. The repository publish workflow targets the existing GHCR image when
config.yaml is pushed to main; inspect the workflow for the version being installed.

The pre-promotion working files and staged patch were preserved locally under
`gpt/architecture/v4-promotion-2026-10-23/` (Git-ignored). Committed V3 history remains
available from Git; the original checkout HEAD was `7ea02e4`. Historical V3 evidence
stays under repository docs/, and original standalone-candidate reports/screenshots
are labelled under docs/history/standalone-candidate/. Do not use historical instructions
as V4 configuration defaults.

## Configuration mapping

Open **Settings** in EnergyManager for normal form controls and entity autocomplete.
Search by friendly name or entity ID; pickers show state and units and filter compatible
domains/units. In the HA app, entity discovery uses read-only `GET /core/api/states`
through the Supervisor, even when planning is in demo mode. The server reads the
Supervisor token from its environment; it never sends the token to the browser.
**Use Home Assistant connection** fills the API URL, token variable name and network
access flag. Save still requires an explicit click. Standalone discovery uses the
saved HA connection and named token variable instead.

**Save settings** validates the complete configuration, preserves unknown fields and
writes a dated `*.backup-*.json` beside the configuration before atomic replacement.
External or concurrent edits produce a conflict instead of being overwritten. Discovery
failure leaves current mappings and other settings editable. Credentials remain in
environment variables. Restart explicitly to apply saved changes. The HA Configuration
tab's `mode` dropdown selects demo/configured; saving JSON does not change that mode or
the currently running controller. Physical commissioning confirmations still apply.

For local demo use, a missing `energymanager.json` is created beside the state database
so Settings is available without supplying `--config`. Such a demo still uses synthetic
planning/control inputs. Its entity picker may read HA's entity list when requested.

Find the generated `energymanager.json` through Samba, SSH or an editor under
`app_configs/<repository-id>_energy_manager/` (some tools call the parent folder
`addon_configs`). Home Assistant maps that app-specific folder to `/config` inside
EnergyManager. For a custom `configuration_file` path, look at that location instead.
The [HA configuration guide](https://contributors.home-assistant.io/apps/guides/options/#configuration-files-for-users)
describes this folder mapping. The Settings page edits this same file; manual editing
remains available for backup/recovery and is not needed for routine configuration.

For standalone use, `--config path/to/new-file.json` also creates a missing file and
parent folders. Alternatively copy `configuration.example.json` yourself. The starter is
labelled synthetic and contains every required physical field. `allow_remote`,
`commissioning_reviewed`, `exclusive_controller_confirmed` and `policy.control_enabled`
are false. No old options file is imported. For local fake integration, keep remote
access false and use loopback URLs. Start with `--config path/to/new-file.json`.

| New field | Source to review in old configuration | Required interpretation |
|---|---|---|
| `measurements.ev_soc` | `ev.soc_entity` | `%`, current battery capacity mapping |
| `measurements.ess_soc` | `ess.soc_entity` | `%`, physical capacity/minimum verified |
| `measurements.connected` | `ev.connected_entity` | Explicit on/off binary; normalize device enums |
| `measurements.ev_kw` | `ev.charging_power_entity` | Nonnegative W or kW |
| `measurements.ess_kw` | `ess.power_entity` | W/kW, **positive discharge**; normalize opposite signs |
| `measurements.pv_ac_kw` | `pv.solax_power_entity` | AC generation, W/kW |
| `measurements.pv_dc_kw` | `pv.shed_power_entity` | DC generation, W/kW; confirm actual topology |
| `measurements.house_kw` | Uncontrolled house channel | Exclude controlled EV; no automatic double subtraction |
| `measurements.ev_phases` | New normalized phase sensor | Actual1 or3, not go-e selector enum |
| `measurements.quarter_import_kwh` | Meter/current-quarter helper | Imported kWh already consumed in this billing quarter |
| `measurements.monthly_peak_kw` | `monitoring.monthly_peak_entity` | Actual incurred billing quarter average, kW |
| `actuators.current` | `ev.current_entity` | `number.set_value`, integer amperes |
| `actuators.phase` | `ev.phase_mode_entity` | `select.select_option`:1 single,2 three phase |
| `actuators.force` | `ev.force_state_entity` | `select.select_option`:1 stop,2 charge; verify device meanings |
| `actuators.ess_setpoint` | `ess.setpoint_entity` | `number.set_value`, grid/converter AC W; negative supplies loads |

The quarter prefix is not a total lifetime counter or a full-quarter projected average.
If deriving it from a meter average, use the actual elapsed-quarter duration and verify
reset timing. Monthly allowance resets on the configured local month. Validate house
background against independent energy balances. All physical limits, phases, electrical
power boundaries, efficiencies, EV consumption and both residual-inventory values must
be reviewed; old ESS aggregate caps must not be copied onto independent DC charging.
The provisional2.5kW floor,4kW automatic ceiling,30km reserve and tariffs are not claimed
as installation settings.

HA REST base URL includes `/api`, e.g. `http://127.0.0.1:8129/api` for a fake. A later
authorized HA add-on setup may use `http://supervisor/core/api`, remote access explicitly
enabled, and `token_environment: SUPERVISOR_TOKEN`. Standalone HA tokens are read only
from the named environment variable; never put credentials in URLs, snapshots or commits.
Notification webhook is omitted by default; notices stay in local SQLite. A configured
webhook must be reviewed separately and was exercised only against a loopback fake.

The issued forecast endpoint returns JSON:

```json
{"issued_at":"2026-10-23T08:00:00+00:00","revision":"provider-1",
 "provenance":"declare actual provider or SYNTHETIC fixture",
 "intervals":[{"start":"2026-10-23T08:00:00+00:00",
 "end":"2026-10-30T09:00:00+00:00","house_kw":0.4,"pv_ac_kw":1,"pv_dc_kw":1}]}
```

That constant example is synthetic, not a forecast recommendation. Real issued intervals
must cover the complete rolling168h without overlap or holes, with separate background,
AC and DC channels. Resampling preserves interval energy. The independent median-load
and PV-plane utilities document the inspected forecasting mechanics; the configured
application consumes the declared issued feed, not the old scheduler's plan. Verify the
provider and calibration before commissioning; missing data is never treated as zero.
Over30s shared power data restricts new commands; EV SoC over900s disables EV while ESS
can balance fresh powers. Forecast over2h disables conditional work. These thresholds
and15-minute desired completion margin are provisional.

## Commissioning and rollback — later review, not performed here

1. Back up the current add-on/config/dashboard and independently export the new SQLite
   evidence. Keep a restorable V3 image and options/dashboard backup. Reproduce tests, wheel and target-host image.
2. Verify all mappings, signs, physical ratings, phase/stop timing, meter resets,
   forecast coverage, economics and UI permissions with control disabled. Confirm state
   and telemetry freshness and understand the conservative initial ESS provenance ledger.
3. Review offline traces and compare shadow plans to real observations. Define usable
   emergency/manual operation and notification destination. Confirm actual host runtime
   and storage growth; no purge policy is enabled.
4. Only after separate authorization, establish one exclusive controller: stop old EV/
   ESS writers, verify stop/setpoint behavior, then explicitly review both commissioning
   flags and the new control flag. Restart reconciliation initially revokes recorded
   commands. Never run competing enabled controllers.
5. To roll back, stop the new controller and verify EV stopped/ESS at the reviewed safe
   handover setting. Disable its control flag. Restore/re-enable the previously reviewed
   V3 image/controller/configuration and dashboard, and verify sole authority. Preserve
   the V4 database and logs for diagnosis. Source promotion did not modify historical
   installation database files; never point V3 at the V4 SQLite database.

SQLite records are compressed and never automatically deleted. Events distinguish
observed, planned candidate, accepted, commanded dry-run/service-write and invalidated
states. The bounded GUI projection is not archival retention. Use SQLite's backup API
or stop the application before copying database+WAL; never copy a live main file alone.
Decision/input size and observed growth are reported in VERIFICATION.md; plan free disk
space and backups before unattended commissioning. No reset credits, paid API or recurring
automation are required. Resumption uses WORK_STATE.md; automatic resumption is not assumed.
