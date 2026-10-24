# EnergyManager 4

Version **4.1.0** replaces the previous Energy Manager application with a joint EV/ESS
MILP scheduler, independent responsive control and Overview/Planning/EV pages.
The complete seven-day horizon uses planning intervals no longer than five minutes.
Goals, scoped peak permissions, reasons, measured progress and immutable decisions are
persisted. Demo mode uses explicitly synthetic inputs and disables hardware control.

The main app lives in `energymanager/`. The standalone `energymanager-next/` tree has
been promoted into it; there is one active application. Home Assistant retains the
`energy_manager` slug and `ghcr.io/nxt-1/energymanager` image identity. The separate
`influxdb3/` app is unchanged.

## Run locally

From the repository root, use Python 3.13:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m energymanager --version
.\.venv\Scripts\python.exe -m energymanager --port 8100
```

Open [Overview and Planning](http://127.0.0.1:8100/). In this prepared workspace the
existing interpreter is `energymanager/.venv313/Scripts/python.exe`.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check energymanager/src energymanager/tests energymanager/tools
.\.venv\Scripts\python.exe -m mypy energymanager/src/energymanager
node --test energymanager/tools/frontend.test.mjs
.\.venv\Scripts\python.exe -m build --no-isolation energymanager
```

- [Architecture](energymanager/docs/architecture/Architecture_Proposal.md)
- [Project instructions for chats](AGENTS.md)
- [Current decisions](energymanager/docs/DECISIONS.md)
- [Deferred work](energymanager/docs/DEFERRED_WORK.md)
- [Run, configure, migrate and roll back](energymanager/docs/RUNBOOK.md)
- [Verification and remaining commissioning checks](energymanager/docs/VERIFICATION.md)
- [Release notes](energymanager/CHANGELOG.md)
- [Optional Home Assistant dashboard card](energymanager-dashboard/README.md)

## Updating from V3

This is a major application/configuration update. V3 options and databases are not
loaded by V4. Review the explicit JSON mapping in the runbook, keep a V3 backup, and
start with control disabled. The add-on defaults to manual start and synthetic demo
mode. Configured operation builds Open-Meteo PV and measured household forecasts; control additionally
requires complete physical/actuator mappings, valid live readings and the single
Overview hardware switch. The HA connection is automatic. The V4 SQLite file is separate from historical V3 data.

Home Assistant reads the available version from `energymanager/config.yaml`. The existing
publish workflow targets the same GHCR image when a version change is pushed to main.
No image has been built or published locally and no live installation has been changed.
Docker/Supervisor, physical mapping and hardware cutover require the runbook's later checks.
Historical V3 investigation/verification documents remain under `docs/`; current V4
shipping documentation lives with the application in `energymanager/docs/`.
