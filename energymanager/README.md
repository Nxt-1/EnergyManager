# EnergyManager 4

Version **4.0.0**, the main Energy Manager application. One joint seven-day EV/ESS MILP
feeds independent responsive control. The application includes configured input/actuator
boundaries, persisted goals/approvals/decisions and the functional Overview/Planning GUI.

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
and tariffs are synthetic assumptions. Demo never reads HA credentials or installation
DBs. Default local state is `runtime/energymanager-v4.sqlite3`.

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
V4 JSON input configuration. Remote addresses and hardware control are disabled by
default. Missing critical physical settings prevent enabling configured control.

- [Shipping specification](docs/SPECIFICATION.md)
- [Runbook, V3 mapping and rollback](docs/RUNBOOK.md)
- [Verification](docs/VERIFICATION.md)
- [Current checkpoint](docs/WORK_STATE.md)

The Home Assistant app retains slug `energy_manager`, image `ghcr.io/nxt-1/energymanager`
and ingress port 8099. Version 4 uses `/config/energymanager.json` and its own
`/data/energymanager-v4.sqlite3`. Review migration before installation; V3 configuration
and databases are not automatically imported. No live controller was enabled here.
