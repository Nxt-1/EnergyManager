# Continue EnergyManager after V4.0

Prepared 24 October 2026. The active implementation is `energymanager/`, version
**4.0.10**, in `Nxt-1/EnergyManager`. A new chat may use this file as its starting
point for V4.1. Chat history is not required to recover the documented requirements.
Do not assume a new chat can read another chat's entire history automatically.

Read in order:

1. [Current decisions and working rules](DECISIONS.md).
2. [Shipping implementation specification](SPECIFICATION.md).
3. [Original forecasting source, PV setups and corrections](FORECASTING.md).
4. [Settings and hardware-control contract](SETTINGS.md).
5. [Run, install, commission and roll back](RUNBOOK.md).
6. [Deferred work](DEFERRED_WORK.md); none is automatically approved.
7. [Verification evidence](VERIFICATION.md) and the latest entry in
   [WORK_STATE.md](WORK_STATE.md). Check the actual Git state and relevant CI runs.

The complete original architecture [handoff](architecture/Implementation_Handoff.md),
[proposal](architecture/Architecture_Proposal.md) and
[decisions](architecture/Architecture_Decisions.md) are retained as references.
Their "not implemented", fresh-directory and no-release instructions describe the
earlier chats. They do not undo the user's subsequent main-project promotion and
release decisions. Current explicit user instructions and DECISIONS.md take precedence;
SPECIFICATION.md resolves the original mathematical proposals as implemented.

## Baseline and verification boundary

4.0.9 was published from `17279c21cfa977c4a72b52b5d7eda73ced08fb04` after CI run
40024429281 and publication run 40024429516 passed (151 Python tests, full-horizon
offline integration, package and Linux container verification). 4.0.10 adds the
authorized pickers/watt presentation and documentation consolidation; see the latest
verification entry for its actual results. No scheduling policy is changed by it.

No agent has verified actual installation device availability, physical stop/current/
phase/setpoint behavior, phone receipt or HA ingress cutover. Offline fake endpoints
and synthetic measurements are labelled accordingly. The original PV geometry and
corrections are recovered configuration, not synthetic installation guesses.

Configuration JSON and SQLite survive image updates; UI units do not change stored
units. Hardware control is requested through the immediate Overview switch. Do not
use old commissioning flags or enable a second controller. A user saying the system
is enabled is not authorization for this agent to access or operate live devices.

## Resume locally

- Inspect `git status`, the latest commit, and WORK_STATE.md before editing. Preserve
  unrelated or staged work. The ignored `gpt/architecture/Implementation_Checkpoint.md`
  may contain newer local/remote completion evidence in this workspace; it is optional
  context, not a dependency of a fresh clone.
- Load `C:/Users/Arne/.codex/skills/code-writer/SKILL.md` (or discover the matching
  skill locally) for code changes. Do not write application code without the skill.
- Prepared interpreter: `energymanager/.venv313/Scripts/python.exe`. Use the runbook
  to recreate an environment. Run Python tests, Ruff, mypy, frontend tests and relevant
  browser workflows; packaging/CI as appropriate to the change.
- A full configured offline preview is `python tools/offline_e2e.py --serve` from
  `energymanager/`, on localhost:8102. It uses only fake Supervisor/HA/weather services
  and a real seven-day HiGHS solve. Do not substitute the user's live HA endpoint.
- For new features, get explicit scope/behavior decisions first. V4.1 is not yet
  started; this update does not create a new chat, branch, controller or automation.

Update DECISIONS.md and SPECIFICATION.md when an agreed behavior changes, the backlog
when an idea is deferred, and WORK_STATE.md at meaningful milestones. Keep shipping
documents tracked; `gpt/` is ignored. Preserve historical verification rather than
rewriting old evidence to describe a newer release. Do not push an optional extra
verification-only commit after a successful release.
