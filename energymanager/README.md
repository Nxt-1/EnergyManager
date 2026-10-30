# EnergyManager 4

Version **4.5.1**, the main Energy Manager application. One joint seven-day EV/ESS MILP
feeds independent responsive control. The application includes configured input/actuator
boundaries, persisted goals/approvals/decisions and Overview/Planning/EV/Appliances pages.

## Planned power in task details

Open an EV/ESS charging session to see its planned power over time. Requirement details
show the shared EV charging plan before their deadline. Expand Power levels for the
exact intervals and W values. These are calculated profiles; live power can differ.

## Appliance profiles

Appliances records the next explicitly selected washing-machine/dishwasher program
from a dedicated HA W/kW power sensor. Configure the idle threshold and finish timeout,
arm the cycle, then review/trim and explicitly save the measured profile. Original
recordings survive restart; incomplete/interrupted runs cannot become selected profiles.
Mazak has editable provisional Program/Light/Production averages of 2500/3500/7000 W.
Profiles are preparation for later scheduling; this release does not start or schedule
machines or change their accounting in the household forecast. Existing installation
settings, EV/ESS planning, routing and live-control behavior remain in place.

## Charging continuity

Required and optional charging share the continuous-session fallback, using their active
goals and charging ceilings. Solar refinement reserves time for smoothing even when named
targets are already satisfied. Necessary pauses and existing limits remain; no new setting.

## Solar capture

The planner keeps checked solar-allocation alternatives when a timed search cannot improve
its starting schedule. Bounded 24h candidates across the full forecast consider EV capture
within the existing health ceiling, direct solar export and later ESS filling. Future
supply and normal source/permission guards remain. No new setting is required.

## ESS display sign

ESS AC power is positive when charging and negative when discharging, in live cards and
actual/planned/history charts. Input sensors and control retain their existing convention;
no remapping is needed. Direct DC solar charging remains separate from this AC reading.

## Startup recovery

After fresh checks, compatible saved schedules can resume while a new plan calculates.
Shutdown still stops charging. Older schedules need one fresh4.4.11 calculation before
later restarts can use this recovery. Existing faults, permissions and live guards remain.

## EV failure detection

Blocked charging now raises attention after two minutes; confirmed non-delivery retains
its90second watchdog. Optionally select the FordConnect vehicle charging-state sensor in
Settings → EV fault recovery, then save and restart. A reported FAULT stops EV charging
without automatic charger reboot. Vehicle/cloud state supplements measured power.

## Google Maps journeys

Save a Google Routes API key under Settings → Google Maps to activate routing immediately.
The first required route request validates the key with Google; rejected requests stay
unresolved and warn you. Clear the saved key to stop new requests. The key is write-only.
Enable routing beside each selected calendar subscription, or add a manual journey with
a destination and desired venue arrival/departure. Calendar configuration changes still
require restart; key changes apply immediately. Each trip independently returns home.

## Local deterministic demo

From this directory, use Python 3.13:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m energymanager --version
.\.venv\Scripts\python.exe -m energymanager --port 8100 --budget 120
```

Open [Overview and Planning](http://127.0.0.1:8100/). Solver work runs in a separate
process while dry-run control continues. All demo measurements, forecasts, capacities
and tariffs are synthetic assumptions. Demo planning/control never uses installation
inputs or databases. Settings can read HA's entity list to prepare the real configuration.
Default local state is `runtime/energymanager-v4.sqlite3`.

The **EV** tab shows a seven-day calendar and daily agenda for entered journeys,
expected away periods, morning/manual SoC targets and accepted charging sessions.
Use its Journey and SoC goal buttons to add requirements and its agenda to edit them.

For native HA views, immediate sensor-state updates and clickable sensor history, follow
the [native dashboard guide](../energymanager-dashboard/README.md). Install its loader and
strategy once; later add-on updates deliver the dashboard layout/cards on HA page reload.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests tools
.\.venv\Scripts\python.exe -m mypy src/energymanager
node --check src/energymanager/assets/app.js
.\.venv\Scripts\python.exe tools/offline_e2e.py
.\.venv\Scripts\python.exe -m energymanager --solve artifacts/decision.json --budget 120
.\.venv\Scripts\python.exe -m build --no-isolation
```

`--fixture` accepts an immutable snapshot for `--solve`. `--config` selects explicit
V4 JSON input configuration and creates a disabled starter file if it is missing.
Remote addresses and hardware control are disabled by
default. Missing critical physical settings prevent enabling configured control.

- [Architecture](docs/architecture/Architecture_Proposal.md)
- [Runbook, V3 mapping and rollback](docs/RUNBOOK.md)
- [Verification](docs/VERIFICATION.md)
- [Current checkpoint](docs/WORK_STATE.md)

Open **Settings** for searchable entity pickers and normal controls for capacities,
tariffs and policy. The HA app can discover entities through its Supervisor proxy;
the connection is automatic; no address or token setting is needed. Save writes the same
JSON file, preserves unknown fields and creates a dated backup. Conflicting edits are
rejected. Restart explicitly to apply changes; the running controller stays unchanged.
Local demo starts also create `energymanager.json` alongside the selected state database.

The Home Assistant app retains slug `energy_manager`, image `ghcr.io/nxt-1/energymanager`
and ingress port 8099. Version 4 uses `/config/energymanager.json` and its own
`/data/energymanager-v4.sqlite3`. On startup, including demo mode, the add-on creates
the configuration file if missing and logs its location. Existing files are preserved.
Find it through Samba, SSH or an editor in `app_configs/<repository-id>_energy_manager/`
(some tools expose `addon_configs`). Replace the labelled example settings before
using configured inputs. Review migration before installation; V3 configuration
and databases are not automatically imported. No live controller was enabled here.

Hardware control uses one immediate switch on Overview. Connections and Commissioning
settings have been removed. Settings highlights missing values and offers a phone
notification picker. See [settings and control](docs/SETTINGS.md).
