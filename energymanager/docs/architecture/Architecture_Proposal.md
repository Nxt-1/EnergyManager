# EnergyManager architecture

This is the single maintained architecture and implementation specification. Update
this same file as requirements and implementation evolve across releases and chats;
do not create a new handoff document for each version. The filename is retained from
the original architecture proposal, but its content now describes the current system.
The active application is `energymanager/`; its version is recorded in config.yaml and
the changelog. Last reviewed: 28 October 2026.
Accepted changes awaiting implementation are explicitly labelled below; they must not
be mistaken for behavior already shipped in the application.

Repository-wide chat and coding rules live in the root [AGENTS.md](../../../AGENTS.md).
It directs chats to this architecture, the ongoing backlog and the required coding
skill, and records the user's permission and conversational preferences.

Confirmed user decisions take precedence over engineering proposals. This document
records the resulting behavior and technical contracts; [DECISIONS.md](../DECISIONS.md)
retains the decision context. [DEFERRED_WORK.md](../DEFERRED_WORK.md) records ideas
that require separate implementation authorization. Original draft wording remains
available in [Git history](https://github.com/Nxt-1/EnergyManager/blob/9d8a6944c20472df5b7b30b04cf14dcabea195c3/energymanager/docs/architecture/Architecture_Proposal.md)
and the preserved local architecture records.

Development capacities, tariffs and efficiencies are **synthetic provisional
parameters** unless explicitly verified for the installation. PV geometry and correction
tables were recovered from the original installation configuration. Verification weather
and measurements are labelled synthetic fixtures or public references. Do not substitute
these for installation evidence or fabricate the missing historical native archive.

## Scope and component boundaries

Schedule EV and ESS jointly over the full seven-day horizon with intervals no longer
than five minutes. Keep forecasting/input collection, explicit requirements, one bounded
MILP planning process, independent fast control, validated publication and persistence
as separate responsibilities. Full solves must not block live summaries or protective
control. One accepted shared plan supplies both resources' intended trajectories and
permission scope. Live ESS balancing and EV power modulation adapt execution to current
loads and production; the schedule is not a rigid instruction to reproduce forecast powers.
Ordinary execution differences do not make its original calculation invalid. See the
snapshot-planning contract below, implemented in4.4.4.

DHW, washing-machine/dishwasher scheduling, planned Mazak operation, appliance recognition,
learned driving, advanced forecasting and a standing ESS reserve for unforeseen peaks
remain deferred. Their uncontrolled consumption still belongs in the household forecast.
Resources and requirements should remain extensible without implementing those features
prematurely. ARCH-009 is implemented as a dedicated visual EV schedule page.

## Confirmed installation and GUI requirements

- Use separate P1 import/export sensors:
  `sensor.p1_dongle_momentary_active_import` and
  `sensor.p1_dongle_momentary_active_export`.
- `sensor.p1_dongle_current_quarter_average_demand` reports kW using a fixed full-quarter
  denominator. The user confirmed it resets near zero and builds up. Convert it using
  0.25 h; do not expose a quarter-measurement-type choice.
- There is no dedicated uncontrolled-house sensor. Derive household demand from the
  mapped powers. Use go-e APIv2 Connect's existing phase-selector readback without an
  additional phase-count sensor or phase-information choice.
- Preserve the original forecast source, installed PV planes and applicable correction
  factors. Use [FORECASTING.md](../FORECASTING.md) for their exact recovered values.
  Never invent replacement installation settings.
- Keep daily readiness with EV settings. Morning minima require charge by a deadline;
  they assume no driving. With these alone, the planned EV SoC stays level or rises.
  Explicit journeys withdraw estimated travel energy; fresh measurements inform live
  control and the next planning snapshot.
- Keep Overview and Planning inspired by the original first two dashboard pages:
  concise live summaries, actual/planned power and SoC, time navigation, grouped sessions,
  seven-day planning, goals/progress and inspectable reasons/approvals. ESS is blue;
  EV is green. Keep implementation details outside the main household flow.
- From4.4.7, Overview shows Goals · next24hours, including only deadlines strictly
  after now and at most24 elapsed hours ahead, in chronological order. An empty window
  states that no goals are due. The forecast cost/energy-assets card appears only on
  Planning. Planning retains all current goals together by deadline, including morning
  requirements interleaved with journeys. This supersedes4.4.5's removal of Overview goals.
  Trip summaries show driving energy (`distance_km * consumption_kwh_per_100km / 100`)
  in kWh separately from the departure target, which includes the arrival reserve.
  EV agenda/details use the same estimate. Only the earliest upcoming goal has a current
  charge/target bar, explicitly labelled with both kWh quantities and capped at100%.
  Hide that bar when EV energy/input health is unknown, stale or settling. Later/past
  goals retain forecast SoC/readiness without a current-charge bar. Display order and
  these estimates do not change scheduling priority, withdrawals or charging authority.
- Use typed settings and HA-style searchable entity/phone selectors. Highlight missing,
  placeholder, unavailable or incompatible required values immediately. Remove long
  explanatory entity subtitles and nonexistent house/phase sensor mappings.
- HA connects automatically through Supervisor. Keep connection-address options,
  notification webhooks and the Commissioning tab out of the normal GUI. Phone notices
  use the optional selected HA notify entity or mobile-app action.
- The single Overview hardware switch applies immediately and persists its requested
  state separately from installation JSON. Saving installation settings still requires
  restart. The control and migration boundaries below remain mandatory.

## Built-in installation forecasting

Configured mode uses the recovered Open-Meteo KNMI seamless source, HA zone.home location,
exact four-plane installation and original empirical front/rear corrections. The shed
retains its physical model without an empirical factor. AC/DC routing matches V3.
The original35-day median load predictor consumes persisted5min measured background
samples, with a recent3h median during learning. No prepared forecast endpoint is required.
See [FORECASTING.md](../FORECASTING.md) for numerical parameters, source provenance and failure behavior.
Weather HTTP runs independently from fresh measurements and fast control; no missing
weather is replaced by zero, extrapolation or a demonstration forecast. A configured
startup has no demonstration journeys. Existing user goals are preserved.

## Inputs and requirements

Each immutable snapshot contains observed EV/ESS energy and source ledger, connection,
AC powers, separate DC PV, current-quarter imported energy, actual monthly peak, issued
forecast revision, policy, capabilities, goal revisions and explicit permissions. SHA256
covers canonical serialized inputs. SQLite retains every decision and event without
automatic deletion. Exported decision JSON can be replayed with `--fixture ... --solve`.

The configured application uses the confirmed P1/go-e installation. House demand is
reconstructed as `grid_import - grid_export + PV_AC + ESS_AC_output - EV`. ESS means
its AC bus boundary; DC solar is not counted twice. The P1 demand sensor builds from
zero and is converted from W/kW to quarter import kWh using a fixed0.25h denominator.
The go-e phase selector supplies forced-mode readback; no additional phase sensor is
required. Auto/unavailable is unknown and pauses EV while fresh ESS balancing continues.
Stop/zero, post-switch readback and a30second restart settling hold are enforced
without claiming physical contactor telemetry. There is no minimum interval between
phase switches. Meter/controller clock alignment remains a commissioning check.

Settings exposes only these sensor mappings, with no source/type selectors or computed
house/phase-count inputs. Daily readiness is in the EV group. Older JSON is interpreted
with the same setup immediately; retired source choices are ignored. Missing/generated
P1 mappings receive the known defaults, while custom mappings and unrelated values are
preserved. The file is unchanged until explicit save creates a backup and removes the
retired choices. Starter templates omit the unused house and phase-count mappings.

The horizon is168 elapsed hours in UTC, with local recurring deadlines and billing
months. Five-minute boundaries are split at goals, departures, returns, publication hold
and an initial15-second phase-preparation window. Partial intervals never exceed300s.
Daily readiness is50% at07:00 local, configurable, suppressed during known away periods.
It is not a persistent floor. A trip targets `min(capacity,(km+reserve_km)*kWh_per_km)`
and withdraws only the journey energy at departure. The configurable arrival reserve
starts at 30 km; it is desired remaining energy, not an extra withdrawal. Manual SoC goals withdraw nothing.
Overlapping goals constrain the same battery trajectory. Unknown return remains away;
external or physically unachievable travel leaves dependent EV state unknown until a
measured reconnection. No external charging is fabricated. Priority then deadline order
locks best-effort outcomes only after proven hard infeasibility. Timeout is distinct.

## Frontend units and journey dates

### Subscribed EV calendars (ARCH-003,4.3.0)

Settings accepts up to20 uniquely identified, labelled public HTTPS/webcal iCalendar
links. Saving keeps the existing backup/conflict checks and requires configured-mode
restart to apply. Subscriptions fetch at startup, every four hours and on explicit EV
page Sync. Network reads and calendar parsing run separately from planning/control;
downloads are limited to2MB/20seconds, three redirects,5,000 source events and1,000
upcoming occurrences per feed. Redirect targets and resolved addresses must stay public
HTTPS; no HA credentials are sent. Subscription URLs are not exposed in state/events.

Expand timed events from four hours ago through90days ahead, including recurrence,
exceptions, cancellations, UTC/TZID and installation-local floating times. Skip all-day
items with a visible count because they have no departure time. Repetitions more frequent
than daily are unsupported and fail the refresh. Invalid feeds retain their last-good
snapshot and expose a warning; valid empty feeds remove their managed journeys.
The supplied referee feed was checked read-only; personal events/URL are not fixtures.

Every imported occurrence is a managed explicit trip with **provisional50km total**,
departure at calendar start and return four elapsed hours later, ignoring event duration
for this first release. The user confirmed these placeholders. Label/location and
placeholder provenance appear in EV agenda/details. Existing consumption/reserve,
availability, withdrawal, peak approval and joint-planning rules apply. Stable source+
UID/recurrence identity prevents duplication; changed journey data increments its goal
revision and clears permissions. Exact UID/start/location duplicates across feeds are
planned once. Manual goals remain separate. Edit/remove imported events at the source
or remove the subscription; normal goal APIs cannot overwrite managed journeys.

Persist successful snapshots for restart/outage continuity, retain failed sources'
last-good items and display last sync/error/staleness (after eight hours). Removed or
changed-URL sources cannot resurrect old cached journeys. Demo mode never fetches
configured calendars. The EV schedule still displays168hours; longer imported events
remain available for subsequent planning windows. No automatic driving history is learned.

### Google Maps routing (4.4.0)

Route selected subscribed calendars and manual journeys with a destination. Each calendar
subscription has a routing checkbox in Settings. Disabled subscriptions retain the labelled
legacy 50km/four-hour provisional trips. Manual journeys without a destination retain their
existing kilometre entry. Use predicted traffic within the next seven days, refreshing
daily, when events/locations change and on manual request.

Each routed trip independently uses HA zone.home → venue → HA zone.home, including
multiple events on one day. Do not chain venues. Referee calendars require arrival 60
minutes before event start and departure from the venue two elapsed hours after start;
ignore event end. Manual destination journeys accept desired venue arrival and departure.
Derive home departure, home return and total distance from separate outward/return legs,
using at most three outward traffic checks and one return request. From4.4.3 each
traffic-aware candidate departure includes60seconds of travel-time slack. The last
outward response must be requested at the exact published departure and predict arrival
by the required time. Small duration changes can fit inside this slack; a response
exceeding the final budget still rejects the route. This is a bounded routing allowance,
not a calibrated traffic guarantee or permission to relax the attendance deadline.
Static routing retains its existing two-leg behavior; no transport retries are added.

Saving a nonempty Google Routes API key in Settings activates routing immediately, without
a restart or another global enable switch. Google validates it on the first necessary route
request; saving does not make a separate paid validation probe or guarantee account/billing
readiness. Invalid/denied responses remain unresolved. Blank input preserves a saved key;
replacement applies immediately; explicit clear disables new requests. Other installation
settings, including calendar selection, retain their existing restart requirement. Demo
mode does not initialize a routing worker or use configured credentials.

The key is never returned in settings/state responses or transport errors. Private JSON
configuration and its dated backups contain it under the existing file mechanism. Legacy
maps.enabled values may remain in files but do not gate key-based activation. A credential
generation rejects in-flight results from replaced/cleared keys. Future automatic route
goals are reconciled; an already-underway checked trip retains its away period. Explicit
manual overrides remain usable without a key. The first checked response establishes a
route; a configured key alone is not labelled a validated route.

Requests and local overrides are stored separately from calendar snapshots. Per-event
local destination/distance/timing edits persist through refresh; Return to automatic clears
the overlay. Source cancellation removes its managed request. Routed request APIs reject
approval/authority injection. A lifecycle-managed asynchronous worker runs HTTP outside
planning/control, serializes refreshes and rejects stale request or credential responses.
It uses the fixed Google endpoint, bounded time/response sizes, no redirects or transport
retries. Distances and times retain Google Maps attribution. Existing goals/decision audit
storage is unchanged; no new archive expiry or deletion is introduced in this release.

Routing failures carry fixed categories and allowlisted public messages for missing
credentials/home/destination, invalid/past timing, unsettled traffic, HTTP access/quota/
provider rejection, timeouts, connection failure and malformed/no route responses.
Only a validated numeric HTTP status can accompany them. Never expose raw provider
bodies, addresses, keys or exception text through diagnostics. EV Journey routes shows
the safe reason. Archived journey_route_failed events hold only journey ID, category,
HTTP status and time; obsolete request/credential responses cannot record/adopt failures.
A later successful result clears the displayed failure. Retry/notification/retention
policy is unchanged.

Missing/failed routes contribute no guessed distance or timing. Show persistent EV warnings
and deduplicated alerts to the existing selected HA phone destination. Retry failed delivery
independently. Other valid EV goals continue under ordinary connection, measurement,
charger and permission guards; ESS authority is independent. A pending request without a
checked goal does not revoke unrelated authority or cancel a same-revision calculation.
Changing a previously checked trip invalidates affected work through Application.changed
and request_plan. Unchanged scoped approvals are retained only after checking current
requirements, revisions and permission scope.

Preserve4.3.20 charging continuity and the cancellable worker lifecycle. Its mismatch-
triggered replanning policy is superseded by the snapshot/live-execution decision below.
Route warnings coexist with planning/permission notices. The EV page retains native
history, phase actions and charger activity. No solver objective, evidence threshold or
charger timer changes belong to this release. Temperature compensation remains deferred.

### Native managed Home Assistant dashboard

Version4.2.0 replaces the optional iframe wrapper with a real HA dashboard strategy,
native sensor history actions and custom planning, EV and settings
cards. The add-on remains the planner, controller and persistent configuration owner.
The sidebar/standalone interface remains available using the same reusable components.

One-time setup installs the small `energymanager-card.js` resource and the strategy
configuration documented in [the dashboard guide](../../../energymanager-dashboard/README.md).
The loader discovers the installed add-on through HA's authenticated `supervisor/api`
WebSocket API, creates/renews the standard ingress session and obtains `/api/dashboard`.
That read-only manifest contains bootstrap protocol1, the installed release version,
demo mode and active HA entity mappings, never credentials or unsaved installation values.
No custom integration, additional listening port or weakened ingress boundary is needed;
HA OS/Supervisor and the existing administrator access are required.

The strategy and cards are served from `/frontend/{version}/{asset}`. Relative imports,
templates and styles stay within that release namespace. Stale versions return409;
an already-open card that detects a different backend release requests a reload and
withholds further actions. On HA page reload the installed version supplies the whole
layout and card implementation, so future dashboard changes require no YAML/file copying.
The bootstrap protocol stays stable for UI releases. Personal dashboards are not rewritten;
keep personal additions separate from the generated EnergyManager layout.

The duplicate top sensor strip is removed in4.2.1. Custom live summaries receive HA
state changes directly and use the normal more-info/history dialogs. They use a read-only frontend projection of current HA states,
with unit/numeric/availability checks and the same AC household-balance formula. Source
changes update only live summaries rather than repainting full trajectories. Combined
solar/net-grid/household summaries offer the contributing sensors' histories, without
inventing a measured household entity. HA tiles/dialogs retain their entity units;
EnergyManager's custom power summaries and planning charts retain W.

From4.3.5 the EV tab includes a read-only charger-to-car SVG visualization above the
existing calendar/agenda. It displays battery SoC, independently measured EV power in W,
current controller request in W, validated go-e current setting in A, phase selector
mode and connection/status. Selector code1 means one phase,2 means three phases and0
means automatic; no physical per-phase currents are available or fabricated. A differing
requested phase mode is labelled awaiting readback. Command intent requires a current
revision and recent timestamp and never implies device acknowledgement or delivery.
Hardware control on/off remains explicit. Actual measured power alone drives the cable
animation; reduced-motion preferences disable animation. Active incidents/recovery and
device faults take status priority. Missing/stale readings use unavailable values rather
than zero, and an expandable details section retains raw codes and HA/device frame times.
The browser display never grants control authority. Native HA battery/power/connection
updates replace only this status card, preserving calendar position. Demo uses only its
synthetic observation/command, never installation charger readings. Both native and
standalone layouts retain detail expansion and keyboard focus across refreshes.

From4.3.6 the approved combined layout annotates current limit, measured power,
battery SoC, phase selector and controller request around that drawing. The adjacent
diagnostic list shows connection, charge permission, force setting, car state, charger
status and error with their raw numeric codes. A reason above both explains the overall
state; raw readings and HA/device frame times remain in Charger details. Each status
is colored independently: red for reported errors, green for confirmed OK states,
and the normal theme text color (white in dark HA) for neutral settings/waits/stops.
Unknown and stale device states are explicitly unverified and cannot become green
from cached codes. A historical latched incident can be red while the current charger
error is green None(0). Normal forced stop and car waiting are neutral, not errors.
The data display changes neither control validation nor recovery behavior. The mapped
sensor-history portion of ARCH-014 is implemented in4.3.19 below.

From4.3.19 the Overview EV box includes actual EV charging power in W beside its SoC
and connection display. Overview and the EV visualization share the measured-power
projection: native HA states update immediately; backend-only readings honor input
quality/read freshness. Zero and finite signed power are valid; missing input shows a
dash rather than substituting controller intent or an old observation.

The native EV visualization opens standard HA more-info/history for mapped measured
power, battery SoC, connection, charge permission, car/status/error codes, force,
current setting, phase selector and device status age. Discovery includes only those
configured entity IDs, never credentials or an ESS actuator. Color coding and unverified
readings remain intact; a mapped unavailable entity can still open its history.
History buttons support keyboard/touch, retain focus through refreshes and do not send
charger commands. They are separate from the existing one-time phase controls. Demo,
standalone and unmapped readings explain why no HA history action is offered. Controller
request and internal HA/device-frame timestamps remain explicit EnergyManager data,
with no invented HA sensor. Command/composite history beyond these explanations remains
deferred. No scheduling, charging or recovery behavior changes in this release.

From4.3.4 native and standalone dashboards use optional compact state polling. The
first response projects accepted-plan display fields and at most120 recent samples;
immutable publication/calculation evidence remains in the decision archive. Subsequent
requests name the cached plan ID: the backend explicitly marks an unchanged plan and
the browser reuses that exact object. A new or removed plan is sent explicitly; a cache
identity mismatch is an error. Default /api/state remains complete for existing clients.
Older graph observations continue to come from /api/history, and no records are deleted.

Requests retain a15-second deadline. UI errors name method/endpoint without query
parameters, include detection time and offer Copy error. Denied/unavailable clipboard
access offers a selected read-only field for device copying. Failed state reads back
off2,4,8,16,then30s; explicit refreshes may bypass backoff. No mutation is automatically
replayed or reported as certainly unapplied after timeout. The installed loader retains
its authenticated ingress renewal; versioned card code supplies the new behavior without
reinstalling it. Successful state reads clear the connection warning (after an active
text selection ends); initial API failure does not destroy the dashboard or saved data.
Actual installation network/server causes cannot be inferred from a browser timeout.

The card explicitly enables text selection despite HA's parent user-select:none rule.
Active text selection, held pointers and the manual-copy field pause automatic DOM
replacement while state polling continues. Graph, live-value and resize callbacks honor
that pause; source-history actions ignore selection gestures. Once selection is cleared,
the normal polling cycle resumes rendering. Native release-mismatch detection also
checks compact query URLs and still requires an explicit dashboard reload.

The five live boxes also show today's estimated energy in kWh: separate grid import/
export, AC/DC solar, household demand, EV charging and ESS AC charge/discharge. These
are integrations of the existing validated recorded powers, not HA meter counters or
battery energy changes. Integration uses the installation-local midnight (including
23/25-hour days), holds each power only until the next read or its input-read watchdog,
deduplicates cached snapshots and excludes missing/invalid or other-mode data. Missing
coverage is labelled partial; no coverage is unavailable. Summaries refresh every30s.
An expression index on measurement timestamps covers legacy events too; range reads
use a separate read-only SQLite connection in a worker, outside the control event loop.
Creating this index can take time on the first startup with a large existing archive.

From4.2.3, compact rows use left/right arrows for grid import/export, alternating/direct
current symbols for AC/DC solar and downward/upward arrows for ESS AC charge/discharge.
From4.3.3 every recorded subtotal is followed by a fixed expected end-of-day total.
An independent task captures the accepted pre-midnight plan at the installation-local
midnight, integrating that entire23/25-hour day with continuous coverage and a fresh
forecast. Persist one immutable baseline per local date, timezone and demo/configured
mode; subsequent plans, input faults and restarts do not overwrite it. The tooltip
states the actual capture time and whether this is a midnight or first available
estimate. On later startup without an eligible midnight plan, the first reconciled
valid plan plus the recorded subtotal supplies the fallback at its actual capture time.
Missing actual coverage is never backfilled and its partial status remains explicit.
An unavailable plan/forecast/subtotal or uncovered remainder cannot create a fallback.
The fast state API supplies the saved baseline independently of archive integration.
Recorded subtotals refresh every30s and on local-day/mode changes, outside the browser's
live-state request. Coalesced backend reads cache30s and use a five-second scan budget;
read failures retain the last same-day subtotal with its as-of time in the tooltip.
ESS AC output includes DC passthrough after converter efficiency, matching observed
converter power rather than battery-inventory change. Connection status uses accessible
plug/slashed-plug/unknown symbols. The sensor/history chooser is retained.

Power and battery SoC graphs share a time cursor: hover inspects, click/touch pins,
arrows move, Shift+arrow moves one minute, Home/End select window edges and Escape clears.
Numeric W/% values follow displayed lines; interpolation is marked approximately and
missing values remain blank without extrapolation or bridging gaps. Cursor timestamps
include the UTC offset to distinguish repeated local hours. Both charts and session
tracks use58px left/16px right insets, redrawn on resize. The power plot is360px high.
The time bar includes the plan update moment; normal provenance/history-detail text is
in collapsed diagnostics while actual errors remain visible. The duplicate native
battery-history card is removed; the archived SoC plot remains.

From4.3.8 primary-mouse dragging on either Overview graph pans the shared time window
horizontally at its current duration; power, SoC, period and session bars move together.
A movement threshold distinguishes clicks (pin values) from horizontal drags; a vertical
gesture does not move time. The initial pointer/range anchors the displacement, with
one redraw per animation frame and one archive-range request after release/cancellation.
Pointer capture supports release outside the graph and lifecycle disposal cancels
pending frames. Tooltip text remains selectable; touch retains existing cursor and
vertical page-scroll behavior. Now restores the rolling live window. Planning retains
its full-horizon view and cursor behavior.

From4.3.10 Overview wheel input zooms only the time axis, anchored at the time beneath
the mouse: up/left zooms in, down/right zooms out. This corrects4.3.9 wheel panning
after user clarification; horizontal navigation remains click/drag. Wheel events are
coalesced per frame and archive loading
waits for180ms idle. Ctrl/Meta-wheel, selected text and tooltip interactions retain
browser behavior. Two touch pointers on one graph combine horizontal midpoint panning
with distance-based time zoom anchored under the initial midpoint. Zoom is bounded to
15 elapsed minutes–7 elapsed days. Vertical movement does not move the time window;
CSS `touch-action:pan-y` retains one-finger vertical page scrolling. Lifting/cancelling
a pointer commits once and suppresses the remaining finger until all are released.
Third pointers, navigation and disposal safely end pending work. Navigation arrows
move the selected window's width; Now restores two hours past/four ahead. Updates
cannot overwrite the range during a gesture. Both graphs/session tracks stay aligned.

ARCH-011 is implemented in4.3.9 on the Overview power graph; from4.3.10 a red long-dashed line and
Month peak label show the current recorded monthly `monthly_peak_kw` input in watts.
The graph's scale includes that value. HA source changes refresh it immediately;
unavailable/invalid readings omit the line and show unavailable, while zero is valid.
No forecast, permission limit, tariff floor or stale observation substitutes for this
reading. Demo uses only its own current synthetic observation. Accessible description
and legend identify the current-month15-minute-average grid-import billing peak,
distinct from instantaneous power. This release changes presentation only, not peak
permissions, optimizer policy or controller behavior.

From4.3.10 the Grid box also shows this recorded peak with a peak-chart icon. In native
HA its own keyboard-accessible button dispatches standard `hass-more-info` with the
actual mapped `monthly_peak_kw` entity, including while that entity is unavailable.
Grid power keeps its separate import/export source chooser; the two actions are
siblings, avoiding nested buttons. Missing mapping disables the peak-history action;
demo and standalone expose no installation history action. No synthetic HA entity or
Recorder history is created.

From4.3.10 EV diagnostics are consolidated in the sidebar: interpreted status plus
raw car/status/error/force/permission values, current and phase-selector readbacks,
device status age, HA read and device frame timestamps. Stale raw values stay visible
as unverified. The separate Charger details foldout and redundant phase-current footer
are removed. Red/neutral/green status meaning remains.

The phase-mode annotation has1φ/3φ/Auto buttons in native HA. The user explicitly chose
one-time direct charger changes that automatic control may overwrite, rather than a
planner constraint or EV-control pause. Dashboard discovery supplies only the mapped
actuator phase selector (no credentials, none in demo). Buttons use that actual HA
select entity, validate its offered0/1/2 options, and call HA `select.select_option`
once under the current user's permissions. Pending writes disable the buttons; errors
are visible and never retried automatically. Pressed state follows HA readback; focus
survives refreshes. Unknown/unavailable mappings, unsupported options, demo and standalone
have no enabled action. Automatic stop/settling/fault policies apply to controller
restarts; these direct HA buttons themselves do not run the automatic sequence.
Auto means the charger's own automatic phase mode, not EnergyManager scheduling; the
existing controller requires fixed1/3-phase readback and may hold EV control for Auto.

HA Recorder supplies the native historical view under its own coverage/retention settings.
It does not import EnergyManager's SQLite archive. Accepted plans/decisions/settings
still use the add-on API.

**From 4.2.2:** ARCH-010 loads archived power and battery
measurements for the custom graphs' visible range via `GET /api/history`. It streams the
indexed existing measurement events through a separate read-only worker connection,
with two concurrent archive reads and a five-second scan budget. Each query is limited
to eight elapsed days and100–2,000 points per series; the UI requests1,200 and can select
any retained local day. No retention/deletion or installation data migration is added.
First/min/max/last per time bucket retains extrema. A bucket containing invalid data or
a gap is suppressed rather than joining readings across the gap; empty spans remain
blank. Cached snapshots are deduplicated and read freshness bounds continuity. Current
measured and demo histories stay separate. Recent samples overlay the archive with the
same gap rules. The UI caches up to six ranges for30s, backs off failures and ignores
obsolete range responses or disposed views. Rolling windows retain the overlapping loaded archive until replacement succeeds;
failures label retained history or recent-only history truthfully. Nonoverlapping
navigation clears the old data, and stale responses cannot replace the selected range.
From4.3.7 Overview uses a shared six-hour range for power, SoC and session bars:
two hours before now and four after. Navigation shifts six elapsed hours; Now restores
that live window. History day starts at installation-local midnight (including DST
changes) and displays the next six elapsed hours, with arrows reaching later periods.
Planning retains its full accepted-plan/seven-day horizon. Future observations are not invented.
New measurement records also include EV/ESS capacities, without changing the Observation
used by planning/control. Historical percentages prefer those recorded capacities;
legacy records fall back to current runtime capacities with an explicit chart label.
Old capacity changes cannot be reconstructed from those legacy measurement events alone.
Frontend HA values never grant control authority or satisfy backend enablement checks.
Backend HA input polling remains five seconds; native display updates are independent.
Shared views mount inside the native card's shadow root, use HA theme variables and
dispose listeners/timers/dialogs on removal. Existing goal revision, approval, settings
conflict/backup/restart and hardware-switch validation remain authoritative. Mutating
requests are never automatically replayed after an ingress-session failure.

Offline verification uses a labelled HA-contract harness with simulated built-in cards
and Supervisor messages, real versioned components and a configured fake backend.
Actual HA frontend/Companion/Supervisor installation remains a separate target check.

The EV page combines a calendar for the next 168 elapsed hours with a selected-day
agenda. Installation-local days can be 23 or 25 hours and the horizon may span partial
first/last days. Separate lanes show entered away periods, accepted EV charging sessions
and morning/manual/departure requirements. Overnight events are clipped for display;
whole-session battery energy is never presented as a per-day allocation. Unknown returns
remain open-ended and do not imply external charging or a learned driving routine.

`/api/state.schedule_goals` projects current explicit goals and the existing daily-goal
rules independently of solver/forecast availability, including saved morning approvals.
It does not persist generated goals or change scheduling. Outcomes and EV sessions are
shown only when `ev_plan_valid` is true, the accepted plan revision matches the current
application revision and it still covers future time. During recalculation or startup
reconciliation, entered requirements remain visible;
outdated outcomes are withheld. Current EV readings retain the live-input quality rules.
Users can inspect items and add/edit/remove explicit goals through the existing API and
date/time controls; daily readiness links to Settings. No new control authority is added.

From4.4.2, the normal control tick durably retires manual SoC goals once their deadline
passes and manual trips once their known return elapses. Unknown-return or externally
charged trips remain until a fresh, known EV connection observed after departure;
normal underway trips can also retire on that measured home state. Unknown/stale/settling
input and unknown EV stock cannot establish return. Each retirement archives the full
goal with time/reason, clears its pending issues and removes only its active requirement;
existing decision/measurement history is retained. Grouped retirement requests one new
planning revision without revoking useful EV/ESS authority for other goals. A persisted
empty goal list remains empty on restart. Calendar/routed source records stay under their
owners; active goals/schedule projections omit their elapsed known returns, while unknown
external state remains visible. The frontend omits elapsed morning cards and labels
retained past-departure trips Underway or Awaiting return, rather than Waiting.

The frontend converts power to whole W for live summaries, AC/DC components, actual and
planned charts, peak/approval values, settings and entity previews. Energy remains kWh.
Settings converts limits back to the existing kW JSON/API values, preserving unchanged
numbers exactly; capacity tariff is displayed in EUR/W/month and stored in EUR/kW/month.
Raw technical evidence retains original named units for reproducible replay.

Journey and timed-SoC date/time fields use a Monday-first calendar, a 24-hour clock and
an optional keyboard mode. They use the configured installation timezone rather than
the viewing device's timezone. Nonexistent DST times are rejected; repeated times expose
both offsets and retain the selected occurrence on edit. Cancel leaves the saved field
unchanged; the optional return can be cleared. This does not add a travel forecast:
standing morning targets withdraw no energy, and no daily driving is inferred.

## Joint MILP and source accounting

Powers are kW, energies kWh, interval duration `dt` hours. Nonnegative AC allocations
explicitly distinguish PV→EV/house/ESS/export/curtail, grid→EV/house/ESS, solar-origin
ESS→EV/house and restricted ESS→house. DC PV splits between battery charging and
inverter routing. Restricted ESS inventory never supplies optional EV or export.

`EV[t+1] = EV[t] + dt*eta_ev*(PV_EV+grid_EV+solar_ESS_EV) - trip_withdrawal`.
`ESS_solar[t+1] = ESS_solar[t] + dt*(eta_ac*PV_store + eta_dc*DC_store
 - (solar_dis_EV+solar_dis_house)/eta_discharge)`.
`ESS_grid[t+1] = ESS_grid[t] + dt*(eta_ac*grid_store-grid_dis_house/eta_discharge)`.
The configured minimum is a physical boundary; usable inventory is above it. All losses
appear once in their actual conversion path. Unknown initial stored provenance is
restricted; fresh import-free charging can establish new eligible solar inventory.

AC converter input/output have separate2.5kW provisional caps and one direction at a
time. DC battery capture is independent; AC+DC may exceed2.5kW. Shared battery rates,
capacity, DC routing and charge/discharge exclusion remain hard. Stored energy cannot
be sold. House and PV conservation, grid direction and physical connection limits are
hard. Simultaneous nominal PV ESS charging and household grid purchase is prohibited
to avoid relabelling grid-supplied storage as solar. Genuine DC-bus routing is allowed.

EV uses integer6–16A and supported one/three-phase modes. Modes exclude each other.
From4.3.13 there is no minimum separation between opposite active phase modes in
planning, its incumbent or independent validation. The actuator still stops10s and
confirms zero3s before phase writes, then holds force off for30s after selector
acknowledgement in either direction. An ordinary restart requires30s from confirmed
force off and power below100W; an already long enough stop counts toward that hold.
Current-only adjustments stay live. It prepares a future phase during an off interval.
The five-minute plan uses nominal slot power; sub-minute control holds can postpone
actual delivery, which is reconciled from measurements rather than fabricated.
Planning holds the currently valid EV setting through the calculation budget plus15s,
as a forecast of command continuity during the solve. It is not proof that the expected
energy was measured as delivered, and does not require matching publication-time stock.

For each known requirement checkpoint `k`, `B[k]=target[k]+prior withdrawals-initialEV`.
Let `S[k]` be cumulative eligible non-grid EV battery energy and `G` total direct grid
EV battery energy. A binary witness enforces
`G <= max(0,max_k(B[k]-S[k])) + integer final-slot rounding`, with no rounding if there
is no positive causal deficit. Thus later PV cannot erase necessary pre-departure grid,
and already sufficient pre-deadline solar cannot leave a nominal required-grid purchase.
From4.3.20 the model’s positive-deficit witness exceeds the independent energy tolerance
by a numerical margin; a sub-tolerance solar deficit cannot unlock a whole grid rounding
increment. The independent audit itself is unchanged.
Required charging prefers earlier useful delivery when waiting has no actual benefit.
Useful later PV and genuine cost/peak/physical/source benefits still justify waiting.
This is the original early-winter requirement, retained through joint continuity selection.
A final certificate minimizes grid within the chosen modes, non-grid/storage allocations
and per-quarter import envelopes. Its Optimal status has this bounded scope, not a
global optimality claim. From4.3.12 it also bounds the EV start/phase/power-variation
score to the selected schedule's score, so certification cannot undo continuity.
All flows are independently audited outside the model builder against the same immutable
calculation inputs. New live readings are not substituted into that mathematical and
economic proof.

## Economics, opportunities and permission

The comparison is `imports*price - exports*price + incremental capacity cost
 + start stored EV/ESS value - end stored EV/ESS value`. Forecast bill and energy-asset
change are displayed separately. Unknown post-travel EV inventory receives no credit.
There is no monetary wear charge or cycle quota.

One finite planning process obtains required service, jointly optimizes zero-to-maximum
optional EV/ESS quantities, checks each extra charging origin over the following24h
(including both residual inventories), and uses a finite constraint repair if necessary.
Normal optional EV ceiling is80%; a100% probe executes only if matching the opportunity
later in the full horizon is proven infeasible with physical availability, losses,
inventories and no additional imports. Later diagnostic100% headroom grants no execution
authority. Timeout or an unvalidated comparison retains the80% result. Initial SoC above
80% never forces discharge. Named conditional solar-capture tasks carry source, amount,
forecast, target and deadline. A five-minute minimum is hard for entirely discretionary
plans; mixed required sessions retain necessary short service. Advancement requires an
existing task and at least a worthwhile five-minute opportunity before starting.

Capacity is a15-minute average including the measured consumed prefix. Cost baseline
is the actual incurred monthly peak or configured floor2.5kW, reset by local billing
month. A proposed future peak is never reused as incurred. Optional changes cannot
increase the required reference quarter envelope independently. Automatic4kW is a
provisional permission for required EV work or an economical specific ESS peak strategy.
Above it, EV grants are goal/revision scoped and bounded to that goal's remaining causal
energy. Fulfilled grants cannot fund another goal. ESS grants are separately scoped to
a forecast peak within24h; EV permission cannot lend ESS authority. A higher ceiling is
permission, not a target. Revised goals revoke approval; rejecting a proposed extension
preserves an existing lower EV grant. Physically useful feasible diagnostics produce
requests on creation/change or relevant changed circumstances, even days ahead; there
is no 12-hour waiting rule. Deduplicate requests and continue permitted best effort
while waiting. A timeout is not proof of infeasibility and must not itself trigger a
costly permission request. Do not request an extension that cannot solve a physical
charger or availability shortfall.

ESS grid charging must reduce a specific larger peak within24h and improve combined
economics including losses and inventory. It is disabled for ordinary arbitrage and
standing insurance. Required EV feasibility may be restored through ESS household
support only against a feasible higher-peak counterfactual. Adopted exceptions produce
deduplicated informational events; the default destination is local SQLite. An optional
configured HA phone notification destination receives deduplicated notices for an
adopted deliberate peak-increase strategy. Ordinary successful peak suppression stays
quiet. No external notice was sent in development.

## Continuity, control and publication

### Snapshot planning and live execution — accepted 28 October 2026

**Implemented in4.4.4.** This is the current contract. It supersedes the4.4.1
publication energy repair, fresh-stock revalidation and mismatch-only extra solves from
4.3.20–4.4.3. Historical decisions and release evidence remain labelled below.

The lifecycle is snapshot → calculate → validate against that snapshot → execute the
remaining schedule until a replacement is accepted. Validate required outcomes, source
accounting, grid-purchase causality, physical limits, permissions and economic comparisons
using the optimizer's frozen inputs and matching reference. Preserve those inputs,
results and validation evidence unchanged. A calculated schedule is a conditional forecast
for that moment, not a guarantee that subsequent readings will reproduce its trajectory.

Publication checks continued authority and usability: current requirement/configuration/
permission revisions, a usable time horizon, and the required input/connection/charger
health. Skip elapsed instructions and never repeat an elapsed withdrawal. Do not replace
the calculation's EV/ESS inventories with newer readings and rerun its energy-purchase,
required-outcome or economic proofs. A higher/lower battery reading or changed load/PV
alone must not reject publication or start a schedule-repair optimization. The4.4.1
energy-extension/reconciliation machinery is superseded; no new live remaining-grid-energy
budget is introduced as its replacement. Keep current admission observations separately
from the immutable calculation evidence. The accepted result retains its full original
interval grid and all original arrays/reservation indices. Fast control selects the
current interval by timestamp; it does not execute past intervals. Admission records
its time, snapshot/digest identity, actual observation, first usable interval and errors.
Current revision and physical balance/readback checks remain in the planning service.

Live control remains active throughout execution and replacement calculations. ESS
balances real demand/production within its physical and source limits. EV charging power
responds to fluctuating loads, PV, available quarter-hour headroom and existing charging
conditions. Current peak limits, battery bounds, source-specific reserves/permissions,
input freshness, connection, phase/readback and charger-fault protections remain binding.
A protective reduction or stop can suspend affected commands without declaring the
original mathematical schedule invalid. Basic ESS balancing remains independent of EV
instruction availability. No additional authority to buy optional grid energy is created.

Load/PV forecast mismatch, including large or sustained mismatch, and the resulting
deviation from predicted EV/ESS energy do not by themselves invalidate accepted work,
cancel an in-flight calculation or request an extra solve. Subsequent periodic calculations
use fresh measurements and any supported forecast corrections. Keep the existing periodic
cadence; this decision does not introduce a stricter start-to-start timing requirement.
Explicit goal/configuration/permission changes, connection and genuine safety/input-
availability events, manual recalculation and necessary failure recovery keep their
separate handling. Ordinary numerical mismatch must not be relabelled as such an event
to restore the superseded trigger indirectly.

Forecast/measurement drift is distinct from inconsistent measurements of the same physical
power balance. Missing, stale or mutually inconsistent critical inputs still invoke the
input-health safeguards described below. Forecast corrections may be prepared for the next
snapshot; preparing a correction alone does not revoke current authority or retarget the
accepted plan's forecast identity/permissions. Original forecast costs and readiness remain
labelled predictions; measured execution and later calculated schedules are separate evidence.

### Session energy explanations (4.4.6)

EV session details name the goals whose driving energy they supply and give the planned
kWh for each. Use a FIFO explanatory ledger on the frozen calculated trajectory:
consume initial battery energy first, then session deliveries in chronological order.
Energy enters a session's lot only as its intervals deliver it, including charging
losses; actual model withdrawals consume those lots. Attribute only matching in-horizon
trips. Simultaneous trips use stable ID order. This is a declared forecast accounting
convention, not measured electron tracing, a counterfactual optimization or a new control
reservation. Other charging sessions and pre-existing inventory are accounted for once.

Each session's driving allocations plus remaining known stored energy and unresolved
energy partition that session's delivered battery kWh. Retained stock can be an arrival
reserve, a SoC target or additional future energy; do not call all of it discretionary.
Unknown battery-state barriers end attribution of the surviving lots, marking that
quantity unresolved. Never infer the use or terminal value beyond unknown travel.

Track target support separately from energy consumption. At a checkpoint, the highest
simultaneous target explains the shared stock requirement; ties prefer explicit goals,
then priority and stable ID. Credit only the first target use of each surviving energy
portion. Equal later morning minima cannot each claim that same portion. A higher
threshold can claim an additional unclaimed portion, and later deliveries can help
subsequent targets without being credited backwards to an earlier deadline. Trip target
rows already fully explained by that trip's driving allocation are omitted. Any retained
reserve/extra target support remains explicit. Target rows overlap the driving/stored
partition; they are partial contributions, not a claim that an unmet requirement is
satisfied. Driving/target quantities must remain distinct and must never be added.

Session goal_ids now contain only these named contributions, ordered by deadline/ID.
From4.4.8, the normal EV dialog shows only title, time range, delivered battery kWh and
a compact Supports list (goal, date/time, contributed kWh). Target-only rows omit the
full target and repeated prose. When driving/target values coexist, use short labels;
combine same-goal values in one row without summing them. Do not show generic charging
reasons, accounting primers, no-driving paragraphs, retained-stock exposition or lengthy
caveats in the normal dialog. The full attribution metadata remains in the plan/export.
Unknown/legacy/no-named-goal cases use brief truthful fallbacks; never reconstruct the
old all-future-goals count.
The optimizer, frozen flows, live control, permissions and measured history are unchanged.

### Planning lifecycle and continuity

HiGHS runs in one spawned process; event-loop control normally ticks each second.
From4.3.14 each calculation owns a fresh terminable process. Manual Recalculate
replaces active work immediately: cancel the task, terminate/join the exact child
(kill if needed), then build a fresh snapshot and start the latest request. Process
launch and cleanup stay off the control event loop. Never overlap solvers or queue
full calculations. Bursts coalesce to the latest request. Material revision changes
also replace obsolete work; routine same-revision control requests while calculating
are ignored, so they cannot repeatedly restart a long solve. Five-minute idle refresh
remains. A manual request has its own identity and does not change the control revision
or revoke still-valid accepted instructions. Existing publication/permission checks
still apply. Canceled attempts record request/snapshot/replacement identities as
`planning_cancelled` events rather than publishing partial results or raising a
planning-failure notification. Shutdown reaps the active child; the parent watchdog
also remains.

`POST /api/replan` acknowledges with202 and the new request identity/activity. Compact
and full state expose requested/restarting/calculating/checking/waiting/ready/error,
request/start/finish timestamps, real solver stage and elapsed time. The shared native
and standalone UI immediately animates the button, then permits another restart once
the POST is acknowledged. A compact animated activity bar shows stage and elapsed time
across tabs, briefly confirms acceptance and exposes failed requests. It is indeterminate:
no completion percentage or ETA is inferred from the solver budget. Stage updates do
not redraw charts or replace selected text; reduced-motion preferences are respected.
An old state response cannot erase a newer manual request acknowledgement. Mutations
are never automatically retried by the browser.

One120s default wall budget
covers construction, reference/diagnostic/opportunity solves, polish and audits. Optional
refinements are skipped when unvalidated. Checked lower-peak warm starts are feasible
incumbents, not substitute published schedules. Raw status, bounds and gaps are retained.
From4.3.11 seed grid allowances reset by installation-local billing month, matching
the model: current-month incurred peak is never permission in a later month. Every
seed still passes row/bound checks before HiGHS and every published trajectory passes
the independent validator. If the initial required-reference stage reaches its time
limit without a feasible candidate, one recovery solve on the same model/objective
uses the remaining global wall budget less2s reserved for validation (only when more
than2s remain), retaining
the checked warm start if available. No infeasibility claim, new permission, reduced
horizon or relaxed constraint follows from timeout. Refinements use only leftover time.

Decision history lists status/reason/elapsed time for rejected attempts independently
of the last accepted plan's evidence. Its detail includes validity, all stages and
failure reason. A same-origin authenticated download of `GET /api/decisions/{id}?download=1`
returns full snapshot/result/digest/disposition with no-store attachment headers.
Download server JSON directly to preserve float representation/checksums; native HA
uses its discovered ingress base. Frozen CLI replay validates the exported top-level
digest as well as legacy result.input_digest. No full snapshot is added to state polls
or decision-list responses; opening/exporting a decision performs no hardware action.
From4.3.20 every economic stage is a two-objective joint search:80% of its allowance
establishes an economic reference, and20% chooses charger continuity in the same full
EV/ESS model. ESS dispatch and solar/source allocation remain decisions; an arbitrary
ESS incumbent cannot force EV gaps. Achieved required readiness and terminal EV quantity
are preserved. A fixed-phase, single-session candidate is tried for the next required
window, including solar allocation and already-held three-phase charging. The unrestricted
joint search can vary current or retain necessary pauses/phase changes. No new publication
repair is added. The older fixed-ESS EV-only refinement and leftover local-day polish are
replaced by this joint objective selection.

The operational search has one0.02EUR comparison and cash envelope against its economic
reference; the constant-session and unrestricted passes share it. Selection between later
economic stages also retains this reference and favors continuity within the allowance,
so a tiny saving cannot discard a known continuous session or stack tolerances. Starts, actual
selected phase-setting changes and absolute charging-power variation have weights10,5,0.1.
Changing phase between two charging intervals also counts a restart (weight10), because
the real controller must stop/resume. The single-session search varies current and favors
low variation; it does not require the held current to persist for the entire task. Phase
setting persists through off intervals; stopping three-phase charging is not itself a
selector change. The initial selector and power are included, so switching away from the
current setting is priced from the first interval. These are internal search priorities,
not monetary wear charges. Selector auxiliary rows are added to operational searches and
source certificates; the pure economic reference omits this unpriced bookkeeping.
From4.4.9 a bounded earlier-required-charging preference resolves timing indifference
before the final grid certificate fixes quarter envelopes. It minimizes the energy-weighted
time of required direct-grid EV delivery on the same immutable snapshot. The selected
non-grid EV/PV/ESS/house dispatch, total direct-grid EV energy, terminal inventories,
monthly peaks and achieved service are preserved. Required readiness may improve;
economic/cash and continuity objectives cannot worsen (numerical tolerance only, with
no additional0.02EUR allowance). Original holds, availability, integer current/phase,
health ceilings, source and permission rows remain hard constraints. Whole grid-only
session profiles are first tried earlier as fully row/bound/integer-checked incumbents;
the bounded model can refine them without discarding a useful checked start on timeout.
A candidate replaces the selected result only after independent physical/source/permission
and applicable rolling checks. Timing-stage status is separate from economic optimality.
This is planning on frozen inputs, not a publication repair or live schedule check.

Optional searches use the checked reference-ceiling seed selection, rather than only
trying an automatic-ceiling seed that may violate their tighter peak envelope. Joint
continuity candidates also retain rolling opportunity checks before replacing the economic
candidate. Economic status/objective/bound/gap and each operational stage
remain separate evidence. Measured independent-validation time is reserved inside the
wall budget so the final solver stage leaves time for its audit. All candidates retain
independent physical/source/permission checks, rolling opportunity comparisons and
seven-day coverage.

Rejected publication produces a persisted, timestamped planning attention item outside
the permission list. One immediate retry is automatic; another rejection escalates to
attention_required and a deduplicated configured-phone notice. Further failed solves
update evidence without spawning an immediate retry loop or repeating delivered alerts.
Acceptance clears the item and records recovery. Measurement/goal revisions do not
reset an unresolved incident's retry budget or delivered-notice deduplication. Rejection
never creates a peak grant/request: frozen-snapshot validation, current authority/input-
health checks and physically useful diagnostics remain mandatory. Numerical drift alone
is not a publication failure. Accepted pending EV/ESS
permission proposals also receive deduplicated notices. Missing destinations are shown
as local-only; failed HA handoffs remain retryable. Publication errors appear in history
metadata/detail. Preserve the original calculated flows and the actual admission reason;
legacy publication_candidate fields remain labelled evidence of historical reconciliation
attempts. Prior valid instructions retain only their existing control authority.

Continuity is selected inside each original joint scheduling stage within the single
comparison/cash allowance described above. It cannot trade required outcomes for inventory.
Desired15-minute completion margin is visible, uncalibrated, and does not increase required
energy. Certification cannot worsen the selected transition score.

Fast control uses fresh measured powers and quarter energy, protects only source-specific
EV/house-peak reservations, balances brief dips with ESS, reduces current for sustained
loss, and bypasses smoothing for peak danger. It reserves remaining planned quarter
imports, allowing legitimate short pulses rather than imposing a false instantaneous
limit. DC capture is reserved. Excess PV first charges ESS; only residual may advance
existing valid EV work. Without a usable plan, basic ESS balancing remains permitted;
forecast-driven grid precharging does not.
Missing EV SoC holds EV instructions while validated shared HA states still support ESS.
The HA input-read watchdog defaults to 30 s since the last validated snapshot. Individual
entity report timestamps do not expire available states. The read watchdog and forecast
2 h limit are provisional engineering parameters.
Measurement loss stops new commands. Source and permission guards remain independent
of economic score. Generation is checked between asynchronous actuator writes.

Forecast correction can retain the existing evidence mechanism: a covered15-minute
window integrates household, AC PV and DC PV residuals. A changed net-AC/DC bias of at
least500W and0.1kWh can inform the next snapshot, with full measured correction over its
first30minutes and a fade to zero by one hour. Forecast estimates stay nonnegative;
raw observations and long-term learner/weather inputs remain unchanged. Coverage,
deduplication, read-gap resets and rebasing against a new issued forecast still prevent
rediscovering the same bias. Corrections still require fresh covered observations;
recovered excursions and read gaps clear or suppress them under the existing evidence
rules. This decision does not change correction formulas or evidence thresholds. These
are forecast-input rules, not reasons to launch a calculation or revoke accepted instructions. A correction's identity belongs to the new
snapshot; it cannot widen or transfer an accepted forecast-specific permission.

**Historical implementation, superseded by the accepted contract:**4.3.20–4.4.3 request
an extra solve for a changed sustained bias and for additional plan-relative inventory
loss beyond max(0.5kWh,1% EV capacity) or max(0.5kWh,2% ESS capacity). Some corrections
also invalidate ESS/conditional authority. Those mismatch-only triggers/invalidation
paths are not the updated design. Physical protection and explicit structural-event
handling remain; ordinary mismatch is handled by live control and periodic replanning.

Goal/permission/connection changes invalidate affected EV or ESS authority, increment
the generation and coalesce a new solve. Household balancing remains useful when an EV
goal disappears. Publication follows the snapshot validation/admission separation above;
normal measurement drift leaves the original validated schedule intact. While a new
schedule is calculated, remaining accepted instructions retain their existing authority
and live modulation, subject to all current protective guards. If a real admission or
calculation failure occurs, retain still-usable prior work and record its specific reason.
From4.4.11 startup can restore a compatible saved accepted schedule independently of
optimization. The existing persisted hardware-On request, usable measured EV/ESS state,
known connection/phase, advancing go-e readbacks and no latched/reported fault are required.
An accepted result carries execution-context format1, active typed-settings and persisted
requirements/permission identities, and a result checksum. Credentials are masked before
settings identity is calculated. Recovery verifies the matching accepted archive and input
checksum, successful original admission, current capabilities/policy, remaining horizon and
forecast age. Travel/away boundaries since the saved calculation require a new plan. This
checks instruction applicability; it does not repeat economics against live measurements.

A successful recovery restores EV/ESS/conditional authority and runtime context while
preserving every archived input, flow, reservation, original revision and admission record.
The resumed controller request seeds the next calculation's hold; startup dry-run zero
cannot manufacture a new off window. A different observed phase retains normal preparation.
Hardware enable reconciles before its queued protective dispatch can stop a recovered task;
otherwise the control loop retries only while startup readiness is pending. A structural
invalidation/explicit Off cancels the startup candidate permanently. Failed/missing history,
legacy metadata or changed context waits for a fresh calculation with a specific recovery
reason. Older releases need one fresh4.4.11 calculation to obtain the metadata; no speculative
migration reconstructs missing settings identity. Recovery state/plan/revision is a backend
projection for current EV session display, never browser command authority.

The shutdown EV stop and ESS setpoint clear remain. Continuing charging through offline
updates is separately deferred (ARCH-021) until an independent device-side bound is verified.
A new accepted plan replaces recovery atomically through the existing adoption transaction.
Restart withholds recorded authority until these fresh startup checks complete. Actuator failures remain explicit events; repeated
failure backs off and non-delivery latches EV stopping. A solver-parent watchdog prevents
orphan workers after service loss. None of this authorizes executing elapsed commands,
ignoring a genuine safety stop or bypassing a goal/permission revision.

### EV charging supervision and incident recovery (4.3.2)

From4.4.10 persistent blocked charging requests escalate after120seconds. The existing
90second confirmed-non-delivery check and start/phase safeguards remain. Actual measured
power at/above100W ends the blocked non-delivery wait even if a status lags. A commanded
stop or lost connection resets that wait; it is not a fault merely to be intentionally off.
Changing ordinary/waiting status codes or current limits cannot restart the continuous
acknowledged-request/no-power window. A mixed-state120second failure cannot qualify
for reboot without the separate continuous90second healthy-delivery evidence.

Settings optionally maps ev_diagnostics.vehicle_charging to FordConnect Query's vehicle
charging-state sensor. Its2026.10.7 elvehcharging exposes raw Ford charge-display states,
including FAULT. It supplements go-e numeric diagnostics and measured power. A recently
successfully read HA value FAULT while connected immediately latches EV stopping without
charger reboot, including during recovery; it must clear before acknowledgement. The
current reported fault is conservatively honored even if unchanged. A configured source
that becomes unavailable cannot count as clearance of an incident carrying its fault.
The HA read/report
times do not prove a fresh physical vehicle observation: vehicle_observed_at remains
unknown. No Ford polling/refresh, remote vehicle command or automatic fault clearing is
added. Readings unavailable, unsupported or older than the sampler guard do not disable
ordinary EV/ESS control; the existing go-e/power safeguards remain. If the optional source
is configured, only a current recognized IN_PROGRESS read may supplement existing reboot
eligibility; unknown or blocked/reported-fault states cannot authorize a charger reboot.

Incident snapshots, sampled evidence and exports retain raw bounded vehicle state,
selected charging attributes and separate HA read/report times. The optional EV sidebar
row and native history link identify the actual mapped entity. No VIN/entity is hardcoded
or preselected. Configuration changes retain the usual save/restart requirement.

From4.3.15 the EV page shows a separate EnergyManager action strip, alongside the
charger's reported state and measured power. The read-only `charger.activity` API
projection exposes the active step, detail, server timestamp and actual timer deadline.
The strip highlights Stop → Settings → Wait → Start → Power, with a numeric countdown
and ring for the deliberate30second restart hold. It separately labels the10second
phase preparation and90second delivery check; command readback waits remain explicit.
Fault/blocked/disabled/idle states take priority where applicable. Normal action text
replaces the redundant generic verdict; fault/recovery/unavailable detail is retained.
The browser advances only the countdown each second, anchored to a new server activity
timestamp, without rebuilding the drawing or phase controls. Expiry waits for a new
controller update and never claims charging. Missing updates beyond the read watchdog
show controller status unavailable. Text selection and disposal stop local updates.
This display has no command authority and does not change charging checks or timing.

The configured actuator uses GoEReadings/GoEControl. The five-second sampler reads
mapped force/current/phase plus numeric `ev_status` (`car`), `charger_status`
(`modelStatus`), `charger_error` (`err`) and `heartbeat` (go-e `lmsc_delta`, seconds).
These four additional mappings gate EV only, as explicitly approved by the user;
missing mappings cannot disable otherwise valid ESS balancing. Settings stays editable
and shows numeric [CODE] labels. Translated text, invalid/unknown states and coarse
uptime are rejected. Integration2026.10.3 rounds `rbt` to whole hours; it is not a
heartbeat. Two distinct seconds-age samples establish device freshness; repeated HA
reads do not renew it. A30second sampler/device watchdog holds EV stopped. HA entity
change/report timestamps remain diagnostic and do not expire an otherwise steady state.

Current number min/max are intersected with configured capabilities. A changed usable
range updates runtime controller/snapshot capabilities, invalidates EV authority and
requests planning without rewriting JSON or raising the configured maximum. Disjoint
ranges fail the EV guard. Sampler frames retain actual limit evidence.

EV writes are staged across sampler frames, never sleeps under the control lock.
Current must match before forced start. Current-only increases and reductions do
not force a stop or start a settling interval. Pending writes require a later advancing device frame;
HA service acceptance alone is not a charger acknowledgement. A superseded pending
write is followed by the newly desired command even if an older frame already shows
that value. Missing confirmation after30seconds latches/escalates without reboot.
From4.3.16 a submitted command is identified by its target setting and original
submission time, independently of later control revisions. A still-authorized
identical request continues awaiting the same advancing device readback, without
rewriting the setting, sending stop or resetting its30second confirmation deadline.
In particular, an unchanged start remains in start confirmation across revisions
instead of returning to stop/restart preparation. Different targets, explicit stop,
phase changes and existing input/fault guards still supersede it. Every actual write
retains the enabled/current-generation guard. If that guard revokes a write before
the HA service is called, restore the prior pending operation and timing metadata;
never await an acknowledgement for the unsent command. An unknown service response
retains the pending evidence, since the device may already have accepted the write.
Stop/zero/10second phase preparation remains; selector echo alone does not complete
an active modelStatus22/23 transition. A30second nonblocking hold starts at phase
acknowledgement, or at confirmed force off plus power below100W for ordinary stops.
Repeated ticks, current changes and plan revisions preserve the deadline; another
observed phase change or lost stopped-power confirmation requires a new settling
interval. A stop supersedes an unconfirmed start. Fault/input/enabled/generation
guards remain effective during every wait; ESS keeps running. Delivery timing starts
after the start is acknowledged, not during settling. Initial/recovered control with
unknown stop duration waits conservatively. Phase sequencing times out after180s,
independently of non-delivery. The old `phase_dwell_seconds` field is optional,
hidden and ignored, retained only for old JSON/decision compatibility; the prior
default was600s, not900s. The separate persistent-wait escalation is120seconds from4.4.10.
Continuing power for30seconds after stop escalates. A disabled hardware stop is also
checked for30seconds in the incident worker; failure notifies without re-enabling or
issuing recovery writes. Every command still passes enabled/generation guards.

The delivery watchdog begins only after current/forced-start readback and an ordinary
charging state are confirmed. Car waiting/complete/idle and documented charger waits
pause it; persistent blockers escalate after120seconds without reboot. Unknown state
combinations also block recovery. All nonzero error codes and explicit error/overheat
states stop and escalate immediately, never reboot. The watchdog detects90seconds of
confirmed EV power request above100W while measured EV power stays below100W. This is
an EnergyManager delivery failure, not a confirmed go-e fault code. A persisted incident
records first suspected time, detection time, original command/observation, recovery
state, attempts and notification outcome. Incident history survives restart in SQLite.
The dashboard banner and report show local timestamps including seconds and UTC offset.

Settings optionally maps `actuators.ev_reboot` to a HA button; no installation ID is
hardcoded or preselected. Selecting it enables one automatic reboot only for healthy,
confirmed non-delivery. Failed commands, phase timeouts, reported errors, ordinary
blocking states and stale/unknown readings are ineligible. Eligibility is stored with
the incident and rechecked against current charger status before pressing; old pending
incidents without explicit eligibility cannot reboot after upgrade.
Without a mapping, keep EV stopped and escalate. Recovery requires enabled hardware
control, fresh validated connected EV/phase/SoC readings and power below100W. Under the
actuator generation guard, send stop, recheck permission, persist the attempt, then
press the button. A failed/unknown button response consumes the attempt. No network
retry or restart may replay it. A persisted30-minute cooldown also spans new incidents.

Wait60seconds after the attempt, then require an advancing device frame and input read at/after that
boundary before permitting a normal guarded charging trial. If inputs do not return
within180seconds, stop/escalate. Charging must be requested normally and fresh measured
power must exceed the threshold across at least10seconds of distinct readings to
confirm recovery. A repeated90-second non-delivery fault or five minutes without
verification leaves EV latched off. Disabling hardware revokes a pending reboot;
there are no long sleeps inside the actuator lock. ESS balancing remains available.
Restart during verification latches unresolved; restart during reboot wait retains the
single consumed attempt. Explicit acknowledgement requires fresh connected inputs,
and a cleared go-e error, records the user decision and invalidates EV authority for a new plan. It neither
reboots nor forces charging and does not reset the cooldown.

Unresolved incidents notify the existing selected phone target, deduplicated per
incident/destination. Failed notification delivery retries at60-second intervals,
independently of control. Without a target, evidence remains local and the UI says
phone not configured. A successful notify service means HA accepted the action, not
that physical phone receipt was confirmed. The agent uses fake endpoints only.

A separate five-second sampler records EV power/SoC/connection, forced phase selector,
charger force/current readbacks and optional `ev_diagnostics` status/error/allowed
entities. Store bounded state/unit/report metadata and explicit read errors, without
credentials or fabricated values. The four supervision mappings gate EV; other
diagnostic states do not grant authority. Status code meanings, entity units and write
semantics were checked against go-e APIv2 Connect2026.10.3 `select.py`, `number.py`,
`button.py`, coordinator/bridge, translations and manufacturer API key/HTTP documentation.
The integration catches some write errors and sends WebSocket commands asynchronously;
its `stop_charging` service can return to neutral after five minutes and is not used.
`GET /api/ev-incidents` lists the latest20 incidents. The incident endpoint reads
from five minutes before the recorded incident start through min(now,detection+10minutes),
so long waits include their initial command sequence. A missing start uses detection;
a start later than detection cannot discard the detection context. Reads use a separate
read-only worker connection, the event-time index, five-second scan budget and10,000-event
cap. A capped report flags truncation and states that only the first10,000 chronological
events are included; later events in the requested window are omitted.
The UI previews100 events and downloads the complete bounded JSON. Command intents,
successful service calls and observed states remain distinguishable. Added diagnostics
and exact incident timestamps cannot be reconstructed retroactively for older faults.
An initial event-time index may take time to create on a large archive; no deletion or
retention policy is introduced. No live HA/database/hardware/phone validation occurred.

Google Maps preparation was paused for the4.3.x fault-handling work. Its hash-verified
archive remains in the original checkout's ignored gpt/paused-maps-2026-10-25/ folder.
For V4.4, routing.py and test_routing.py were copied unchanged into the separate
codex/v4.4-google-maps worktree; archived documents were not restored. The implementation
is authorized for a scheduled start on25 October2026 at18:29 Europe/Brussels. See the
V4.4 scope above. The copied code has since been extended and connected to startup,
calendars and Settings. The later 4.4.0 release activates routing from a saved API key. No Maps activation was
included in4.3.x.

## Boundaries

The active EnergyManager application lives in the main project. Its fresh joint core replaces V3 under the
`energymanager` Python package and existing `energy_manager` add-on/image identity. V3
source/tests/dashboard were replaced; historical evidence remains in Git and labelled
reports. V3 installation options and database files are not automatically imported. V4
uses its own JSON configuration and SQLite file, with control disabled by default. Only
the selected configuration file is initialized when missing: add-on startup (including
demo mode) and standalone `--config` copy a bundled synthetic starter. The new single
hardware switch starts off and is the only control authority; legacy commissioning
flags and the old JSON control flag cannot enable it. Existing files, including
unfinished files, are preserved. Creation failures stop startup with the path and reason.
The Settings page edits that same JSON using typed controls and searchable entity
pickers. Discovery is read-only through the server-side Supervisor token, or the saved
standalone HA connection. Tokens and unknown configuration fields are not returned to
the editor. Validated edits preserve unknown fields, create a dated backup and replace
the file atomically; revision conflicts prevent overwriting concurrent edits. File I/O
runs outside the control event loop. Saving affects the next explicit restart, not the
active installation settings. The Overview hardware switch applies immediately and
persists in SQLite; turning it off revokes in-flight writes, stops EV charging and clears
the ESS setpoint. Enabling checks saved/runtime settings, entity availability and fresh
critical measurements. Restart waits for these checks before resuming a saved on state.
Incomplete saved settings keep the editor available without planning or command authority.
HA connections are automatic; phone notifications use selected HA notify entities/actions.
See [SETTINGS.md](../SETTINGS.md) for upgrade and control-state behavior. Local demo starts also initialize a missing file beside the database.
The add-on's app configuration mount is writable for initialization and editing. Only
amd64 packaging is declared. Deferred PV/storage expansion, market pricing, V2G, appliances, automatic
travel/external charging, learned policy, live deployment and historical retention
policy are outside this release. Live wiring, values and hardware timings remain
unverified and require the commissioning procedure in [RUNBOOK.md](../RUNBOOK.md).


## HA availability and input-read watchdog

HA owns device/integration availability. EnergyManager uses the current available state
and validates numbers, units, physical consistency and required entities. Unchanged values
are valid without zero-specific exceptions. Unknown/unavailable or failed critical reads
prevent a validated control snapshot; EV-only unknown inputs retain independent ESS behavior.

Observation.at is completion of the last validated HA input read. Existing control,
hardware-enable and household-forecast guards expire this snapshot if successful reads
cease. This is connection/snapshot health, not a claim that every device sampled at that
instant. Per-entity last_reported/last_updated timestamps are retained for diagnosis only;
old, absent or malformed report metadata cannot disable a valid available HA state.

Quarter demand is converted with the original meter semantics and accounted at read time.
The controller still handles quarter changes and measured counter resets. It does not
infer a wrong quarter from the timestamp of an unchanged counter. Available readings remain
visible independently of a failed snapshot. If reads stop, cached cards show a read-watchdog
warning; unavailable components remain explicit. Actual charts use validated HA snapshots.
Forecast issuance/expiry and permission/actuator guards remain unchanged. Installation
integrations must accurately signal device loss via availability; this remains a live check.

From4.3.18 finite EV power is a signed measurement: negative readings, including a
brief startup transient, do not reject the input snapshot, invalidate the plan or
request a stop merely because of their sign. Preserve the signed reading in actual
graphs and integrate signed net EV energy without dropping other powers' coverage.
This does not add planned EV discharge or change charger error/delivery supervision.
Other range, availability, unit and finite-number checks remain. Remaining negative
PV, separate grid import/export, quarter demand and monthly peak readings are rejected
at their mapped source. Input errors include the entity ID, bounded original HA state,
declared unit and UTC read time. Derived household errors list contributing readings
rather than assigning a multi-sensor balance failure to one sensor. Preserve their
HousePowerMismatch type and settling behavior. Domain-only invalid observations name
the failed field and value, including when no HA mapping exists.

From4.3.3 a derived household residual below−100W has a settling window equal to
measurement_max_age_seconds (normally30s), only after a validated observation existed.
The failed combination never refreshes Observation.at or invents nonnegative demand:
quality becomes settling, the controller requests zero EV/ESS commands, and no sample
is learned as measured household consumption. The accepted plan/permission revisions
remain intact during a brief mismatch; planning waits and in-flight publication is
rejected until a validated balance returns. Record first mismatch time, raw input states
and recovery. The UI retains independently available values with an explicit inconsistent
household value. At the deadline, on startup without a prior valid observation, or for
other critical-input failures, normal visible error/invalidation rules apply immediately.
Recovery from a brief mismatch resumes the existing plan subject to every normal guard.

## Maintaining the architecture and continuing work

Keep this document current when an agreed requirement, formula, component contract or
implemented behavior changes. Record decision context in [DECISIONS.md](../DECISIONS.md)
and deferred ideas in [DEFERRED_WORK.md](../DEFERRED_WORK.md). Update the existing
[runbook](../RUNBOOK.md), [settings contract](../SETTINGS.md) and
[forecasting reference](../FORECASTING.md) where their details change. Preserve original
verification evidence; keep new results in [VERIFICATION.md](../VERIFICATION.md) and
meaningful progress in [WORK_STATE.md](../WORK_STATE.md). Do not maintain a separate
version-specific handoff or another duplicate architecture specification.

A new chat starts by reading this document, the decision log and relevant supporting
references, then compares the latest checkpoint with actual files and Git state.
Project files carry the requirements; do not assume automatic access to another chat's
history. The ignored `gpt/architecture/Implementation_Checkpoint.md` may contain newer
local/remote evidence in this workspace, but a fresh clone must not depend on it.

Use the user's code-writer skill for application changes. Do not write code without
explicit user authorization; screenshots and questions alone are discussion. Once
scope is authorized, finish it and ask before unrelated changes. Preserve unrelated
working/staged changes and historical evidence. Use local fake endpoints for verification;
do not access live HA/databases, operate hardware, send real phone notices or deploy
without separate authorization. Offline verification is not physical commissioning.

The runbook contains environment setup, tests, builds, configured offline preview and
rollback procedures. The prepared interpreter in this workspace is
`energymanager/.venv313/Scripts/python.exe`; `python tools/offline_e2e.py --serve` from
`energymanager/` provides a synthetic preview on localhost:8102 with a real seven-day
solve. Check current tests/package/CI rather than assuming an earlier release's results.

Include relevant documentation with the authorized implementation commit. Do not create
optional follow-up commits solely to record a successful release; use the ignored local
checkpoint and final reply for subsequent remote results. Do not buy/reset usage credits,
switch to paid API usage, promise automatic resumption or create an automation as a
workaround. On resumption reconcile the checkpoint against the workspace and continue.
