# V3 explanations through Home Assistant

Version 3.0.0b3 keeps the existing planner and device controls. The **Understand this plan** card is
embedded in Overview and Planning alongside the existing charts. It needs the reviewed add-on with
ingress enabled and the updated dashboard JavaScript (`?v=300b3`). No file export or terminal is required.

## Workflow

1. **Browse decisions:** latest records load automatically. Use Newer/Older for pages of 20 or select
   a historical record. Its timestamp and accepted/rejected/superseded disposition remain visible;
   an archived accepted record is not necessarily the currently active plan.
2. **Select evidence:** choose an EV charging session, ESS charge/discharge action, requirement,
   generic job, or any quarter-hour. Inspect mandatory/preferred conditions, generation formula,
   parameters, assumptions, deadline, source timestamps and measurements. The available actions are
   derived from archived power, not an inferred explanation.
3. **Understand timing and power:** review load/PV, grid power, EV/ESS SoC, energy totals and cash
   accounting. Expand stage changes to see how the same slots evolved through optimization.
   Device limits, grid ceilings, policy tolerances and monthly peak baseline are recorded separately.
   Net energy cash for a selected window excludes global capacity cost and terminal storage value;
   full-plan accounting reports those terms separately. Do not interpret correlation as unique causation.
4. **Compare revisions:** inspect the prior accepted schedule beside current slot power and expand
   changed forecasts, actuators and requirements. Decisions without a previous plan show no overlap.
5. **Investigate an alternative:** select From/Until quarter-hour boundaries and choose EV prohibition
   (including postponement), continuous EV charging, no ESS charging, no ESS discharging, or no grid
   import. Departure requirements and all physical constraints remain in force. No-grid-import refers
   to the entire AC balance, not an invented EV-specific energy source.
6. **Assess results:** selected schedule deltas, feasible/infeasible status, both schedules/energy
   balances and all stage evidence are available in the card. Economic bounds determine whether an
   optimal cost direction is proven. An infeasible alternative does not identify a minimal conflict set.

The original reason for one particular time or power can remain indeterminate. The card states that
limitation and provides recorded stage differences and controlled model interventions. It never claims
"make room for PV" from the mere coincidence of discharge and a later PV forecast.

## Authentication and limits

The card uses Home Assistant's `supervisor/api` websocket calls for add-on discovery/info and
`/ingress/session`, and the standard `ingress_session` cookie under `/api/hassio_ingress/` with
SameSite=Strict (Secure on HTTPS). This follows Home Assistant frontend's `src/data/hassio/ingress.ts`.
The user must be authorized by Home Assistant/Supervisor to access these APIs. A denied session is
shown as an error; the card does not bypass permissions or request/store a long-lived token.

The add-on listens internally on port 8099 with **no published host port**. Only socket peers at
Supervisor ingress address `172.30.32.2` with a valid ingress-path header are accepted. Forwarded client
IP headers are never used as authentication. Custom proxying directly to this port is unsupported.
POSTs require JSON and a custom same-origin header; no CORS permission is offered. Authentication is
provided by Supervisor; these operations do not grant hardware authority.

Endpoints:

- `GET /api/decisions?offset=N`: bounded history, including corrupt/retained-away records as unavailable.
- `GET /api/decisions/ID`: validated archived evidence and stage comparisons.
- `POST /api/counterfactuals`: `{snapshot_id, kind, start_index, end_index}`; returns a job ID.
- `GET /api/counterfactuals/ID`: running/completed/failed/timeout result.

All routes require ingress. There are no configuration, plan-adoption, archive-mutation or hardware
endpoints. POST is read-only with respect to live state; transient result jobs exist only in memory.
At most two archive reads and one diagnostic worker run concurrently. A busy live solve rejects a new
worker. Repeated submissions have a 30-second cooldown, no queued solve backlog, 2 KiB request cap,
672-interval maximum, strict integer indices and a fixed intervention allowlist.

Each comparison uses the same frozen inputs in both arms, with at most 30 seconds per solve and at
most 15 seconds for economics. Other policy limits are unchanged; the reported diagnostic policy and
source snapshot ID make this budget change explicit. The worker has lower CPU priority, one HiGHS
thread, a 65-second wall/CPU ceiling and a 2 GiB address-space ceiling. Timeout/cancellation terminates
and reaps the process. Credentials are stripped from its environment; it imports no live HA client or
controller. Starting a later live solve does not adopt or await diagnostic output. CPU contention can
still affect solver progress, so seven-day results may be incomplete.

At most eight results are kept, expiring after 15 minutes. Counterfactual responses are capped at 4 MiB;
archive decompression remains bounded at 32 MiB. Restarting the add-on discards transient jobs. The
backend does not regenerate or alter an archived plan during ordinary evidence reads.

## Installation, failures and rollback

Deployment and hardware activation require explicit approval. Before deployment verify the exact
source/image version, entity mappings, electrical limits, `ess.control_enabled` and `ev.control_enabled`,
Supervisor ingress access and a saved prior image/configuration/data backup. Follow the existing
[direct replacement and rollback procedure](V3.md#direct-replacement-configuration-verification-and-rollback).
V3 replaces the installed planner; no parallel instance or alternate operating mode is required.

After an approved update, refresh the dashboard resource. The card discovers one installed slug ending
in `_energy_manager`; if discovery is ambiguous, set `addon: FULL_SUPERVISOR_SLUG` in the card config.
Do not expose port 8099 to the LAN or paste Supervisor tokens into dashboard YAML.

No records: check planner availability and archive persistence. Corrupt/rotated record: choose another
history entry. Busy/rate-limited: wait for the indicated solver or cooldown. Job timeout/failure: inspect
the recorded original decision, then retry a smaller window; the active plan remains unchanged. Expired
job: calculate again. Old archive fields may be unavailable; the GUI does not invent missing quality data.

Rollback stops the reviewed V3 process, restores the saved previous image/configuration/data and
restores the matching dashboard resource. Verify approved device ownership and permissions before
restarting. Disabling control does not itself stop a device previously commanded by another controller.

## Verification scope

Automated HTTP integration covers authorization rejection, same-origin header validation, historical
pagination, generic selections, actual subprocess HiGHS execution, concurrent requests, live-solve
priority, timeout, expiry, archive corruption and worker failure. A Node DOM test traverses the real
HTTP backend. Chromium additionally exercises the complete visible workflow against a local test
server, with only Supervisor session discovery mocked. This is not a claim that production HA ingress,
installation-specific permissions or physical hardware were exercised.
