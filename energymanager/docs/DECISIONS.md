# Current requirements and decisions

Maintained 25 October 2026 for 4.2.3. This records confirmed product preferences and
implementation outcomes from the V4 implementation chat. It supplements the complete
original [architecture decisions](architecture/Architecture_Decisions.md); the
[maintained architecture](architecture/Architecture_Proposal.md) describes the resulting implementation.
New explicit user instructions take precedence. Deferred ideas are not authorization.

## Architecture and EV behavior retained

- One joint EV/ESS MILP, full seven elapsed days and intervals no longer than five
  minutes; an independent responsive control loop and persisted, validated decisions.
- Keep the original required/optional energy, source, cost, peak permission and
  continuity policies. Their complete original context is preserved in
  [the handoff](architecture/Implementation_Handoff.md) and
  [maintained architecture](architecture/Architecture_Proposal.md). Its current
  specification resolves the original mathematical proposals; historical pending-work
  statements are not a request to rebuild the application.
- The morning target is a timed minimum, initially 50% at 07:00 local. It is not a
  permanent floor and does not imply a daily journey or energy use. With these targets
  alone, predicted EV SoC can only stay level or rise. Entered total-distance journeys
  withdraw estimated travel energy; actual SoC reconciles the next planning snapshot.
  No automatic driving schedule or post-trip restore-to-50% rule is agreed.

## Project update and persistent configuration

- The user explicitly promoted the fresh `energymanager-next/` implementation into
  the main `energymanager/` project and named it version 4. Do not recreate the
  temporary tree or wrap the legacy scheduler. Keep the existing add-on/image identity.
- Create a missing selected configuration file from the bundled starter; preserve
  existing files. The configuration persists through image updates. Synthetic defaults
  are examples, not installation evidence. The editor writes the same file with a
  backup, atomic replacement and revision conflict checking.
- Provide HA-style searchable entity selectors and typed settings rather than require
  plain-text edits. Highlight missing mappings, placeholders, unavailable values,
  incompatible units and blank required fields immediately. Remove long explanatory
  entity subtitles. Installation settings take effect after restart.
- HA connection is automatic through Supervisor. Remove connection-address choices,
  the old notification webhook and the Commissioning tab. Standalone environment
  overrides remain tooling boundaries, outside the normal Settings page.
- Provide one hardware-control switch on Overview. The user explicitly chose immediate
  application. It persists independently of JSON settings, checks valid inputs/settings
  before enabling and revokes commands/stops EV/clears ESS on disable. First migration
  to the new switch starts off. Old commissioning/control flags cannot enable it.
- Optional phone destination is a searchable HA notify entity or mobile-app action.
  Keep existing deduplication and failure evidence. Development must not send real
  notifications. See SETTINGS.md for the complete control/configuration contract.

## Installation inputs and forecasting

- P1 import/export are separate sensors:
  `sensor.p1_dongle_momentary_active_import` and
  `sensor.p1_dongle_momentary_active_export`.
- `sensor.p1_dongle_current_quarter_average_demand` is kW with a fixed full-quarter
  denominator. The user confirmed it drops near zero at each quarter and builds up.
  Convert demand to quarter-import energy using 0.25 h. Do not ask for a measurement
  type or treat it as an elapsed-time average.
- There is no dedicated uncontrolled-house-demand sensor. Derive it from separate
  P1 import/export, AC solar, ESS AC output and EV charging, using the specified signs.
  Do not double-count DC solar or expose a nonexistent house sensor mapping.
- The user uses go-e APIv2 Connect. Use the existing phase selector readback for
  forced one/three-phase modes; no extra phase-count sensor or phase-source choice.
  Auto/unavailable readback is unknown; preserve stop/zero/dwell protections.
- Daily readiness settings belong with EV settings.
- Forecasting must use the original source, PV setups and applicable correction
  factors. These were recovered and restored: Open-Meteo KNMI seamless at HA home,
  four installed planes and original corrections. FORECASTING.md contains the exact
  recovered values and provenance. Never invent replacement installation parameters.

## Availability, watchdogs and display failures

- The user approved trusting HA's current available state rather than enforcing
  per-entity timestamp freshness or enumerating exceptions for zero/unchanged values.
  HA integrations own device availability. Retain numeric/unit/physical validation.
- Report timestamps are diagnostic. A successful validated HA read renews the input
  snapshot; the existing configurable watchdog (default 30 s) restricts control when
  successful reads cease. Forecast expiry remains separate. Device outage availability
  reporting is still an installation commissioning check.
- Do not infer a billing-quarter mismatch from an unchanged entity's report time.
  Preserve the actual quarter prefix/reset and fixed-denominator energy accounting.
- One failed input or forecast must not hide every available live summary. Show
  available readings independently and identify the failed entity/check. A validated
  control snapshot and command authority may still be withheld when required inputs
  fail. Actual charts use validated observations rather than invented measurements.

## GUI and future scope

- User authorized a full native HA dashboard with automatic future UI updates, retaining
  the current interface's useful presentation, immediate HA state updates and clickable
  sensor history. No iframe. Use HA's existing authenticated Supervisor bridge and a
  stable loader plus release-owned strategy/cards, avoiding a separate custom integration.
  Initial setup is once; subsequent add-on UI updates take effect on HA page reload.
  Personal dashboards are preserved. Backend polling/control policy and archived custom
  graph history are separate; ARCH-010 adds custom archive history in 4.2.2. See the maintained architecture.

- Keep Overview/Planning inspired by the original first two dashboard pages: live
  summaries, actual/planned power and SoC, time navigation, grouped sessions and the
  full seven-day view. Keep ESS blue and EV green; expose reasons/approvals without
  putting implementation detail into the normal household flow.
- Display power in W, including charts, card components, settings, peak/approval values
  and entity previews. Keep energy in kWh. Existing API/configuration/model units
  stay compatible. Capacity tariff display converts to EUR/W/month consistently.
- Journey and timed-SoC date/time fields use an Android-inspired calendar/24-hour clock
  with keyboard entry, the installation timezone, Cancel and optional-return Clear.
  Reject nonexistent clock-change times and expose both repeated-hour occurrences.
- On 24 October 2026 the user explicitly authorized ARCH-009 implementation. The EV
  page uses a seven-day calendar and selected-day agenda for journeys, away periods,
  morning/manual targets and accepted charging sessions. The existing scheduler and
  permissions remain authoritative; unknown returns and outdated plan results are explicit.
- Continue across chats and versions using the same maintained
  [architecture document](architecture/Architecture_Proposal.md). The user explicitly
  prefers updating it in place over creating version-specific handoffs. Backlog entries
  require separate authorization; a new chat does not authorize their implementation.

## Engineering/release rules from the user

- Do not write code without explicit permission. Questions, screenshots and error
  reports are discussion unless the user asks for implementation. Once authorized,
  finish that scope; ask before unrelated fixes/features and keep responses concise.
- Use the user's `code-writer` skill. Preserve unrelated working/staged changes and
  historical evidence. Do not access live HA/databases, operate hardware, send real
  notifications or deploy without separate authorization.
- Existing release authorization covers the agreed updates. Use one implementation
  commit with relevant docs; do not add optional "record successful release" commits.
  Record subsequent CI/publication results in the ignored checkpoint and final reply.
- On 24 October 2026 the user supplied standing authorization to commit and push
  versions when ready for release, including the existing image-publication workflow.
  Live installation deployment and hardware operation still need separate authorization.
- Maintain the same architecture document, decision log, deferred work, run
  instructions and meaningful verification alongside code. Preserve superseded design
  evidence in Git history and labelled historical records. On resumption compare
  checkpoint claims with the actual workspace.
- Do not buy/reset usage credits or switch to paid API usage. Do not promise automatic
  resumption or create an automation as a workaround. Resume from the checkpoint when
  the user returns after a normal reset.

## 24 October 2026 — 4.2.1 scope and graph-history follow-up

The user requests removing the duplicate native sensor strip, retaining the clickable
underlying-value chooser and adding daily energy to the live boxes. Release/push4.2.1
with that scope. Daily values integrate recorded power, show separate opposing flows
and explicitly mark partial coverage; no daily meter entities have been configured.
After that release, implement ARCH-010 graph archive loading, but do not commit or push
that work yet. This specific hold overrides standing ready-release permission for it.

## 24 October 2026 — Publish the graph-history fix

After reviewing the completed local implementation, the user explicitly authorized
committing and pushing it. This lifts the earlier hold for ARCH-010. Prepare release
4.2.2 with the completed code, tests, documentation and offline evidence. Existing
publication workflows are authorized; live HA deployment and hardware operation are
still separate actions. No additional dashboard or controller feature is added here.

## 25 October 2026 — Compact dashboard and graph inspection

The user requested compact symbolic energy/connection rows, numeric graph cursors,
more vertical power-graph space, aligned graph/session time axes and removal of the
duplicate battery-history chart. Keep the underlying-sensor chooser and archived SoC
graph. Move normal provenance/history details into diagnostics and combine plan-update
time with the selected time window. Existing error visibility remains.

The user explicitly chose expected total by the end of today after each energy value:
recorded energy so far plus the current plan for the rest of the installation-local
day. This is a projection, with partial actual coverage still marked, and does not
change scheduler or hardware authority. Prepare4.2.3 under standing release permission.
