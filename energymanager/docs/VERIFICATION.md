# EnergyManager 4 verification

## 4.3.6 — Annotated EV drawing and independent status colors

Synthetic/local only.245 Python tests pass50.74s;36 frontend tests, Ruff/mypy35,
all JavaScript asset syntax and CLI4.3.6 pass. New cases distinguish a latched incident
from current None(0), reported error/car/overheat states, ordinary forced stop/waits,
permission versus actual delivery, unknown codes, stale readbacks and demo isolation.
No controller, recovery, API or entity-mapping contracts changed.

Full-horizon fake E2E passes35.446s/2,018intervals/max tick2.850ms/four fake-only calls.
Native browser checks the combined drawing/sidebar in light/dark themes: independently
green OK, red reported errors and neutral rgb(238,238,238) in dark mode. Historical
incident remains red with current charger None(0) green. Normal forced stop stays
neutral; stale fields are Unverified. Phase transition retains awaiting-readback text.
Expanded raw details and summary keyboard focus survive polling. At390px the native
card is355px/scroll353px; at320px the standalone card is281px/scroll279px. Browser
warning/error logs are empty. Screenshot: ignored artifacts/release-4.3.6-ev-desktop.jpg.
The fixture's theme/scenario controls change display data only. No live installation,
hardware, database, real notifications or deployment was accessed.

Wheel/sdist build passes. All55 packaged code/assets match source bytes in both
archives; an isolated extracted-wheel import reports4.3.6. Paused Maps code stays
outside the active package. Remote CI/image results are recorded after the release
commit only in the ignored local checkpoint and final response.

## 4.3.5 — EV charger visualization

Synthetic/local only.245 Python tests pass42.97s; final three versioned-bundle tests
pass0.29s.33 frontend tests, Ruff/mypy35, all asset JavaScript syntax and CLI4.3.5
pass. New frontend checks cover measured/requested power separation, go-e selector
code1/2 mapping, automatic/unverified mode, stale/missing inputs without fabricated
zero, command generation/age, charging/waiting/stopped/complete/disconnected states,
fault/recovery priority, escaped diagnostic content and demo/installation separation.
Native HA readings can update display while backend authority checks remain unchanged.

Full-horizon fake E2E passes32.818s/2,018intervals/max control tick4.138ms/four fake-only
service calls. Native browser verifies charging, phase transition with awaiting readback,
timestamped fault, stale values, expandable details, incoming sensor update and focus
preservation through repeated polls. Standalone EV tab also shows fresh charger settings.
The390px phone card is355px wide with353px scroll width and no card overflow; expanded
details also fit. Battery percentage is accessible text; motion respects reduced-motion
CSS. Final native and standalone warning/error logs are empty. Preview scenarios project
display data only and do not operate the backend controller. Screenshots remain in
ignored artifacts/release-4.3.5-ev-*.jpg; local preview tabs/servers are closed.

Wheel/sdist build and isolated4.3.5 import pass; all55 code/assets match source bytes
in both archives. Unrelated backlog edits and paused Maps code are excluded. No actual
HA/database/hardware, real notifications or installation deployment was used.

## 4.3.4 — Compact polling, request recovery and selectable text

Synthetic/local verification only. Full245 Python tests passed43.13s; final four
native-bundle/API checks after adding both imported modules to the asset allowlist
passed0.33s.28 frontend tests, Ruff/mypy35, all packaged JavaScript syntax and CLI4.3.4
pass. API checks preserve the full legacy endpoint, restrict compact data to display
fields/recent120 samples, handle unchanged/new/removed plans, avoid mutating stored
evidence and retain no-store headers. Frontend checks cover cache identity, bounded
retry/backoff recovery, contextual timeout/network errors, uncertain mutation outcomes,
validation field errors and text-selection detection across shadow-root boundaries.

Configured fake E2E passes32.403s/2,018intervals/max tick2.466ms/four fake-only calls,
with42,535labelled archived records. A synthetic full seven-day response measured
2,523,327bytes; compact initial784,842bytes and unchanged-plan poll50,534bytes:98.0%
less repeated transfer in that fixture, not an installation/network benchmark.

Native preview deliberately supplies an HA-like user-select:none parent. Actual text
and power-value selections remain highlighted through multiple refreshes; a drag does
not open source-history choices. Ordinary controls clear selection and resume rendering.
The installed loader's real15s AbortSignal deadline was triggered with a local delayed
state response: a timestamped GET state warning appeared, Copy error exactly matched
the clipboard, and recovery hid the warning without reload. A Permissions-Policy denial
exercised the selected read-only manual-copy field. Standalone selection, compact-data
Overview/Planning/EV navigation and native57% live update also pass. Initial browser
import failure exposed the missing asset allowlist entries, repaired before final checks;
expected clipboard-policy errors are distinct from final clean startup checks.
Native390px denied-clipboard warning fits355px with no horizontal overflow. Final
fresh native/standalone startup logs are clean. Verification fixtures are stopped.
Screenshots and payload report remain in ignored artifacts/release-4.3.4-*.
Wheel/sdist built; all54 code/assets match source and isolated4.3.4 import passes.
Paused Maps and unrelated backlog edits excluded. No live HA/database/hardware,
installation notifications or deployment was used.

## 4.3.3 — Stable graphs, frozen daily estimates and settling balances

Synthetic/local checks only. Final full suite244 passed44.33s; focused26 energy/input
checks passed0.61s after the archive-coalescing regression and clock guard.
24 frontend tests, Ruff/mypy35, all packaged JavaScript syntax and CLI4.3.3 pass.
Regression coverage includes overlap retained during pending/failed range replacement,
nonoverlap/mode/timezone isolation, obsolete responses, saved midnight baselines across
23/25-hour days, restart/replan immutability, honest late-start fallback, and coalesced
slow archive reads while the live state endpoint remains responsive. Real loopback HA
input-loop tests verify command pause/no revision change during a brief residual and
normal visible invalidation after30s of persistent mismatch. Invalid residuals do not
become measured household history or forecast-learning samples.

Configured fake E2E with42,480synthetic archived measurements passes32.344s across
2,018intervals, max control tick4.319ms, four fake-only service/notification calls.
Native and standalone browser previews verify capture/as-of tooltips and independently
loaded recorded totals. Native live EV update45→57% still works while estimates remain
fixed through the subsequent replan. Fifty sampled graph renders before/after a minute
rollover retained full archived paths (minimum6,840characters); no missing archive redraw
was observed. Native390px energy rows fit147px with no horizontal overflow. Screenshots
remain under ignored artifacts/release-4.3.3-*.jpg. No live HA/database/hardware use.

Wheel/sdist built; all52 code/assets match source and isolated4.3.3 import passes.
Paused Maps code and unrelated backlog edits are excluded from both distributions.
Remote results belong only in the ignored checkpoint/final reply after the release commit.

## 4.3.2 — Status-aware go-e charging supervision

Full suite236 passed42.91s; after the final evidence-storage stop safeguard,56 targeted
go-e/incident tests passed0.57s.22 frontend tests, Ruff/mypy34, all JS syntax and CLI4.3.2
pass. New deterministic fake cases cover normal120second pauses, waiting/car-complete/
OCPP states, unknown/nonnumeric inputs, all tested nonzero errors, no-reboot escalation,
one healthy confirmed non-delivery recovery, fresh post-reboot frames, current-before-
start, silent write failures, superseded start/stop races, cancelled current/phase
requests, phase dwell/readback/transition deadlines, stale heartbeat despite new HA
reads, malformed metadata, current-limit intersection/replan and ESS independence.
Fault stop is attempted even if incident persistence raises. Hardware-off verification
can notify but cannot re-enable or reboot. No installation entity ID is hardcoded.

Configured fake E2E accepted2,018 intervals in35.467s, max control tick4.937ms, four
fake-only service calls. It verifies advancing seconds heartbeat, numeric states,
readbacks and a confirmed zero-power hardware-off stop before preview fault injection.
Unchanged HA report timestamps are three hours old by design; they are not substituted
for the advancing device signal. The final phase and persistence paths were separately
verified by the targeted tests above. Report: offline-e2e.json.

Synthetic native and standalone browser checks passed: required-for-EV CODE/seconds
labels, clear/save/restore with backup/restart notice, unavailable-charger warning and
clean final warning/error logs. At390px requested viewport the heartbeat field is327px
wide at24px left, without overflow. Screenshots goe-v432-desktop/mobile/paused.png;
see goe-browser-verification.json. Fixtures/tabs closed and viewport restored.

Wheel/sdist built;51 code/assets match source and isolated4.3.2 import passes.
Both packages exclude parked Maps code/archive; the source distribution excludes the
separate uncommitted backlog edits. See goe-package-verification.json.

HA built-ins/Supervisor were simulated. No live HA/database/hardware, real reset,
phone notification or deployment. Maps remains parked and excluded. The pre-existing
uncommitted ARCH-011/012 backlog edits are preserved outside this release.

## 4.3.1 — EV fault evidence and bounded recovery

198 Python tests passed in51.29s, including16 new incident/recovery cases.22 frontend
tests, Ruff/mypy33, JavaScript syntax and CLI4.3.1 pass. Checks cover the90second
timestamp, one persisted reboot, stop/disable/generation guards, reboot failure and
unknown outcome, restart without replay, fresh-input grace period, ten seconds of
new measured charging evidence, cached-sample rejection, unresolved latching,
acknowledgement/new plan,30minute cooldown, notification retries/deduplication,
optional button unknown/unavailable states, raw diagnostics and archive/API boundaries.
A held report worker leaves /api/state responsive; report includes T−5minutes beyond
the recent100-event display limit. Persistence failure prevents button activation.

Configured fake E2E accepted2,018 intervals in30.300s, maximum control tick2.656ms,
five fake-only service calls. Native and standalone synthetic browser checks covered
timestamp/offset, report/download/history, acknowledgement, optional reset/phone mapping
save/backup/restart notice and clean final browser logs. At390px requested viewport,
dialog client/scroll widths both324px (341px outer). Screenshot raster dimensions
1265×889desktop and375×812phone; HA built-in cards/Supervisor are simulated.
See ev-fault-browser-verification.json and screenshots/ev-fault-v431-*.png.

Wheel/sdist built;50 packaged code/assets match and isolated4.3.1 import passes.
Both distributions exclude Maps code and its local archive; see
ev-fault-package-verification.json.

No actual HA/database/hardware, charger reboot, real phone notification or deployment
was used. The reported installation fault has not been diagnosed retrospectively.
Maps preparation is preserved in the ignored local archive and excluded from this
release; its earlier16 offline routing checks are not fault-release validation.

## 4.3.0 — Subscribed EV calendars

181 Python tests passed42.04s, followed by40 configuration/calendar checks (including
12 calendar cases) after the final invalid-config guard.21 frontend tests, Ruff/mypy32
and all JS syntax pass. Calendar checks cover multiple sources, save/backup/legacy settings,
recurrence/exceptions/cancellation, DST/TZID, folding/escaping, unsupported/invalid
feeds, source ownership, unchanged identity/no replan, reschedule/approval reset,
failure retention, restart and changed-URL removal, duplicate subscriptions, private
address rejection and a held sync request while /api/state remains responsive.
The supplied referee feed was read-only checked:five upcoming timed events with
locations. Its URL/content are not committed or used as synthetic fixtures.

Configured fake E2E with two synthetic subscriptions, a repeated occurrence and90%
initial EV SoC accepted2,022 intervals in65.617s. Two distinct50km/four-hour trips,
five fake-only service calls, max observed control tick2.761ms. Report offline-e2e.json.
The normal no-calendar CI fixture remains separate. Earlier two-trip45%SoC fixtures
hit the reference-solve time limit at15/60s; no incumbent was adopted and control
remained responsive. This is a known planner limitation, recorded under ARCH-003;
calendar import does not change solver policy or promise a plan for every scenario.

Native HA-contract and standalone browser checks passed: imported agenda/away/return,
provisional50km/four-hour labels, source/location, manual Sync and clean logs. Settings
add/label/remove/save with backup/restart message passed on local fixtures. At390px,
calendar fields fit327px rows without overflow. Screenshots calendar-v430-desktop/mobile.
Native HA built-ins/Supervisor were simulated; no actual HA/Companion installation,
database, hardware, real notification or deployment. Temporary tabs/servers closed.
Wheel/sdist built,49 source/assets match, isolated4.3.0 import passes; see
calendar-package-verification.json. Google Maps preparation follows after publication.

## 4.2.3 — Compact dashboard and numeric cursors

170 Python tests passed43.45s;20 frontend tests, Ruff/mypy31, all JavaScript syntax
and CLI4.2.3 passed. New checks cover recorded subtotal plus only remaining-day flows,
directional AC accounting, stale/unknown/unreconciled plans, insufficient coverage and
23/25-hour local days. Frontend checks cover symbols, partial/stale totals, prediction
identity, cursor interpolation, missing spans, exact step boundaries and window clipping.

Configured fake E2E seeded32,522 synthetic archive records and accepted2,018 intervals
in26.912s, max observed control tick2.866ms, five fake-only service calls. Wheel/sdist
built; all48 packaged source/assets match and isolated4.2.3 wheel import passed.
See compact-dashboard-package-verification.json and offline-e2e.json.

Labelled native HA-contract and standalone browser checks passed for compact energy
rows, day-end predictions across local midnight, connection symbols, source chooser/
more-info, pointer/keyboard W/% cursors, gaps and planned window edges. Both graph and
session-track endpoints align within0.02px on desktop and exactly at390px width;
power height360px, SoC255px. No browser warnings/errors. Screenshots and geometry are
in screenshots/compact-v423-desktop.png, compact-v423-mobile.png and
compact-dashboard-browser-verification.json. Temporary servers/tabs closed.

HA built-ins/Supervisor were simulated; actual HA/Companion installation remains
unverified. No live HA/database/hardware access, real notifications or deployment.

## 4.2.2 — Archived graph history

Final 4.2.2 release checks: 165 Python tests passed in 42.64s; 18 frontend tests,
Ruff/mypy31, all JavaScript syntax and CLI version passed. Configured fake E2E with
47,942 seeded synthetic archive records accepted 2,018 intervals in 27.108s, max
observed control tick 3.180ms, five fake-only service calls. No live installation access.
Final wheel/sdist built: all47 code/assets match source and isolated4.2.2 wheel import
passed (graph-history-package-verification.json).

Initial implementation/browser/load evidence (unchanged graph code):

165 Python tests passed43.50s; targeted12 tests passed again after adding503 coverage.
18 Node tests, Ruff/mypy31 and all JS syntax passed. Tests cover legacy events outside
the ring, index use, bounded responses, retained peaks, gaps/invalid/demo separation,
unknown EV SoC, recorded/legacy capacity handling, range/point/timezone validation,
read timeout, HTTP boundary and a held worker query while /api/state still responds.
Frontend checks cover23/25-hour dates, obsolete-response suppression, cache/error
backoff, merging recent samples and preserving valid archived readings after cached
watchdog failures. The user subsequently authorized the 4.2.2 release; final release
checks are recorded below before the single implementation commit.

The load check used245,924 explicitly synthetic archive records with two concurrent
24-hour queries. Each returned16,561 distinct samples as at most683 points per series
and125,847 response bytes, in1.294/1.282s.87 fake database writes continued; maximum
observed5ms heartbeat delay10.760ms. These are local read/write/event-loop measurements,
not installation control or hardware latency. See graph-history-load-verification.json.

Configured fake E2E with44,924 seeded old graph records:2,018 intervals accepted27.381s,
max initial control tick2.650ms, five local fake-only calls. After browser history reads,
max observed controller tick7.002ms and hardware control off. Browser native/standalone
checks show the previous day's full power and SoC history, deliberate noon outage,
EV-only unknown interval, correct date/12h/Now navigation and an absent day with zero
actual paths.390px controls fit; screenshots graph-history-v422-desktop/mobile.png.
The local ingress fixture now preserves query parameters. HA built-ins/Supervisor are
simulated; actual HA installation and existing installation archive remain unverified.
No browser warnings/errors after fixing the local proxy. Temporary8102/8103 servers
stopped, normal browser viewport restored.47 packaged code/assets match source and
isolated extracted-wheel import passed for the initial local implementation. The final
4.2.2 wheel/sdist is built separately under dist/ before publication. No live database/hardware/deployment.

## 4.2.1 — Daily energy in live boxes

161 Python tests passed40.58s,14 Node tests, Ruff/mypy30 and all packaged JS syntax.
Daily-energy fixtures cover old event backfill, repeated timestamps, watchdog failures,
gaps/unknown/demo separation, opposing flows, restart, local midnight and both DST
changes. API/ingress boundary and stale-day labels checked. Configured fake E2E accepted
2,018 intervals27.722s; max observed control tick3.285ms, five fake-only calls.
Wheel/sdist built;45 packaged source/assets match; isolated wheel import passed.
Labelled HA-contract browser preview confirms no sensor strip, today's energy in all
five boxes, grid source chooser and correct native more-info event. No warnings/errors.
Screenshot: screenshots/native-v421-desktop.png. Actual HA installation remains unverified;
no live database/hardware/deployment. Custom graph archive loading follows separately.

## 4.2.0 — Native managed HA dashboard

Native strategy, tiles/history actions and custom planning/EV/settings cards replace
the iframe wrapper. One-time loader/YAML setup; subsequent UI releases load versioned
assets from the installed add-on on HA page reload. No scheduler/controller policy or
backend five-second measurement cadence changed. No live HA deployment performed.

- 156 Python tests passed39.60s. Ruff/mypy29 and packaged JS syntax passed.13 Node tests
 cover managed layout/version updates without YAML changes, HA-native history bindings,
 direct current-state normalization/AC balance/partial unavailability, unchanged backend
 authority, discovery/session renewal/path validation/admin boundary, no POST replay and
 view-reuse cleanup. Versioned HTTP assets reject stale releases and disallowed paths;
 the manifest exposes active entities without credentials and excludes HA data in demo.
- Configured fake-HA/weather E2E:2,018 intervals accepted27.041s, max observed control
 tick2.616ms, five fake-only service calls. All measurements/weather explicitly synthetic.
- Browser harness: native views mount without iframe; an incoming45→57% HA state changes
 native live displays while backend remains45%. EV sensor click emits `hass-more-info`
 with the correct entity. Journey calendar/date picker/create/remove, Settings discovery/
 save/backup/restart message and native view navigation passed.390px layout and the
 standalone fallback/setup download were inspected. No browser warnings/errors.
- This is a labelled HA-contract harness with simulated HA built-in cards, more-info
 dialog and Supervisor WS responses. Versioned custom components, authenticated-style
 session transport, backend/settings API and configured real-solver fixture run locally.
 It is not evidence of installation on actual HA Core, Supervisor or Companion clients.

Screenshots: screenshots/native-v420-desktop.png and native-v420-mobile.png. Wheel/sdist
built; all44 code/assets match source; isolated extracted-wheel manifest/import passed
with control disabled (native-dashboard-package-verification.json). Temporary8102/8103
fixtures and browser tabs closed, viewport reset; existing8100 preserved. No actual HA/database, hardware
or real notifications used. ARCH-010 remains deferred for the custom graphs' SQLite
archive; native Recorder history is a separate source under HA's retention configuration.

## 4.1.0 — ARCH-009 visual EV schedule

Local verification before the authorized release commit/push. Dedicated EV calendar and
daily agenda use existing goals, daily-readiness rules and accepted EV sessions. No
scheduling formulas, physical limits, source/peak permissions or hardware policy changed.

- 153 Python tests passed in39.36s. Ruff and mypy28 passed. Nine Node frontend tests
  and syntax checks for every packaged JS asset passed. New checks cover requirements
  without a plan, morning suppression while away, saved morning approvals, 23/25-hour
  days, a midnight clock change, overnight clipping, simultaneous targets, unknown
  returns, half-open day boundaries and withholding obsolete/unvalidated plan data.
- Configured full-horizon fake-HA/weather E2E: 2,018 intervals accepted in27.672s,
  max observed control tick2.791ms, five fake-only calls. These are synthetic local
  results, not installation or hardware latency measurements. See offline-e2e.json.
- Browser: direct EV navigation/reload, day selection, accepted charging details,
  journey creation/edit/overnight return, unknown return span, morning suppression,
  manual goal creation/removal and daily Settings navigation passed. Current requirements
  remained visible during recalculation. At390x844, the calendar scrolls within its card
  and selecting a day brings its single-column agenda into view. No console warnings/errors.
- Release metadata prepared as4.1.0; wheel/source builds succeeded. All38 packaged files
  match source. Isolated extracted-wheel import and synthetic state projection passed,
  with control disabled (ev-schedule-package-verification.json). Package assets include
  the EV module and retain same-origin/ingress boundaries. Temporary8102 preview/tab
  stopped and viewport reset; existing8100 preview preserved.

Screenshots: screenshots/ev-v410-desktop.png and screenshots/ev-v410-mobile.png.
All preview data and goal edits were explicitly SYNTHETIC and loopback-only. No live
HA/database, physical device, real notification, deployment or remote publication used.

## 4.0.10 — Journey date/time controls and watt display

Scope: Android-inspired date/time fields, W power presentation, and durable requirements/
decision/backlog handoff. The EV schedule/calendar page is deferred as ARCH-009. No
scheduler policy, physical limits, forecast source, device control or stored units changed.

- 151 Python tests passed in40.46s; final19 affected settings/asset tests passed in0.36s.
  Ruff, mypy28 and JavaScript syntax checks passed. Five Node frontend tests cover signed/
  missing W values, energy-unit preservation, reversible limits/rates, leap dates,
  installation timezone, skipped/repeated DST times and 24-hour clock selection.
- Real configured seven-day E2E: 2,018 intervals in26.594s, max control tick2.823ms,
  switch tick1.008ms (one sample), five fake-only service calls. All entity report
  metadata was three hours old; HA availability/read-watchdog behavior is unchanged.
- Browser: journey create/edit persistence, calendar/clock and exact-minute typing,
  Cancel, optional-return Clear, second DST occurrence retained on edit and missing
  spring hour rejected. Calendar arrow keys/focus and390x844 picker layout verified.
  Overview/Planning power, card components, peaks, entity previews and settings show W;
  energy remains kWh. No browser console warnings/errors.
- Wheel/sdist built; isolated installed wheel imports4.0.10 and all37 source/asset
  files match the final source byte-for-byte, including all three new JS modules.
- Saved2750W was independently read from JSON as2.75kW; a second save restored2.5kW.
  All unedited physical/policy numbers were exactly preserved. Capacity tariff save/
  reload used EUR/W/month display with existing EUR/kW/month storage. A binary floating
  display artifact found during verification was fixed before packaging.

Evidence: frontend-verification.json, offline-e2e.json and screenshots/journey-v4010-*.png,
screenshots/power-v4010-watts.png. These show **synthetic local fixtures**, not actual
installation readings. Physical devices, HA installation and phone delivery remain
live-unverified. Current architecture and specification: architecture/Architecture_Proposal.md;
historical design records retain explicit supersession notes.

## Version 4.0.9 — HA availability and successful-read watchdog

User-approved scope: use current available HA states, remove per-entity age gates and
retain a watchdog on validated input reads. Report timestamps are diagnostic, including
old/missing/malformed metadata. Numbers, units, physical consistency and required
unknown/unavailable states still validate. Quarter conversion/reset accounting remains;
report timestamps are no longer compared with the current quarter. Existing JSON timeout
key is retained with the clarified HA input-read watchdog label. Forecast expiry is unchanged.

Local: **151 tests passed in 39.54 s**; Ruff, mypy (28 modules) and JavaScript checks passed.
Coverage includes unchanged zero/nonzero states across quarters, diagnostic timestamps,
current-quarter counter reset, unavailable/unknown/read failures, value/unit rejection,
read-watchdog expiry/recovery and independent control while the input loop is stalled.
The full seven-day fake-Supervisor/HA/weather application accepted 2,018 intervals in
27.045 s, maximum tick 1.864 ms and five fake service calls. Every entity carried a
three-hour-old report timestamp throughout the successful run.

Browser: clean live values and immediate fake ON/OFF with old metadata; injected HA HTTP
failure blocks enablement and identifies failed reads. No console warnings/errors.
Screenshots availability-v409-healthy.png and availability-v409-read-failure.png are
synthetic local verification only. Wheel/source archives built (transient Windows metadata
rename denial resolved by retry); all 34 isolated installed files match source. Installed
old-state acceptance and read-watchdog expiry passed. Temporary fixtures/tabs closed and
the existing 8100 preview preserved. No live HA/database/hardware/real notification access.
Actual device outage detection is delegated to HA integrations as agreed and remains a
commissioning check. Remote results go in the chat/ignored checkpoint, without a separate
verification-record commit.

## Version 4.0.8 — independent live values and input freshness

Scope: the reported all-or-nothing Overview behavior and timestamp/freshness failures.
Local verification: **148 tests passed in 39.30 s**, plus the final 27 affected-input/integration checks
in 2.73 s; Ruff, mypy (28 modules) and JavaScript checks passed. Regressions cover
slow battery/static states, unchanged values with fresh reports, fallback timestamp age,
true quarter resets and recovery, stale/future/missing timestamps, invalid units/values,
failed HTTP reads, visible unaffected cards and restricted control on invalid snapshots.

The real seven-day automatic-Supervisor/fake-HA E2E accepted 2,018 intervals in 27.573 s;
maximum control tick 2.178 ms, five fake service calls. Eight-minute battery states and
older unchanged-state timestamps exercise the original failure shape. Wheel/source
archives built; all 34 isolated installed package files match source, with live-input API
and disabled startup verified. The first local build hit a transient Windows metadata
rename denial; retry succeeded without changing packaging behavior.

Browser checks injected stale power, unavailable DC solar and an old quarter meter after
a successful real solve. Available values stayed visible, missing totals/components and
entity-specific warnings were clear, the hardware switch remained blocked, and console
warnings/errors were absent. Screenshots: live-v408-stale.png, live-v408-unavailable.png
and live-v408-quarter.png. All are synthetic local fixtures, not installation evidence.
Temporary fixtures/tabs were closed and the user's 8100 preview preserved. No live HA,
installation database, hardware or real notification access. Live installation reporting
rates and physical commissioning remain unverified. Release CI/publication results are
reported in the chat and ignored implementation checkpoint; no separate evidence commit.

## Version 4.0.7 — responsive disabled control during final stop

Includes the settings/control update below. A disabled actuator now returns before
acquiring the dispatch lock. The serial path retains its enabled/generation checks.
A regression holds the fake EV stop request open and verifies that a disabled control
tick completes independently. The regression failed before the fix.

Local verification: **136 tests passed in 39.25 s**; Ruff, mypy (27 modules) and
JavaScript checks passed. Wheel/source archives built; all 33 installed package files
match source. Isolated installed startup verified automatic Supervisor connection,
missing-field reporting, editor availability and hardware control off.

The synthetic configured seven-day E2E passed with 2,018 intervals in 27.346 s,
maximum control tick 2.811 ms and five fake service calls. The report now measures
all ticks and separates pre-switch and post-switch samples: baseline 2.811 ms,
post-switch 1.927 ms (one completed tick). No startup hardware writes occurred.
These are local observations, not a physical timing guarantee. The earlier 4.0.6
CI outlier was captured before switching and is retained without an inferred cause.

Final 4.0.7 browser checks verified immediate Overview ON/OFF, removed settings groups,
phone autocomplete and no console warnings/errors. Screenshots: settings-v407-*.png;
missing-field/save/reload checks from 4.0.6 remain applicable to unchanged GUI assets.
Temporary local fixtures/tabs were stopped; the user's existing 8100 preview was preserved.
No live HA, installation database, hardware or real notification was accessed.
Billing timestamp rejection remains guarded and needs actual telemetry diagnostics.

Remote code `bd0af8fb4e7ca1804ed076ae5f2cf30299253a8a` passed
[CI 40010642618](https://github.com/Nxt-1/EnergyManager/actions/runs/40010642618)
(136 tests in 41.50 s, type/JS/CLI checks, configured E2E, package and Linux container
builds) and [publication 40010642108](https://github.com/Nxt-1/EnergyManager/actions/runs/40010642108)
(136 tests in 35.73 s). Remote E2E: 31.029 s, maximum tick 5.749 ms, baseline
3.630 ms and post-switch 5.749 ms (one sample), five fake-only service calls.
Published image: `ghcr.io/nxt-1/energymanager:4.0.7`, digest
`sha256:b909ccdf13b8a9e8a6b5285a9d9374a9a29bf57b3d84c633f3fc08fd42bfccc9`.
No live deployment was performed.

## Version 4.0.6 — automatic HA connection and one hardware switch

Removed the connection and commissioning options and explanatory entity subtitles.
Runtime and discovery use the automatic Supervisor URL/token. The webhook is replaced
by one optional phone picker, supporting notify entities and legacy phone actions.
Missing/placeholder/unavailable fields are highlighted before Save. Incomplete physical
settings keep the editor available with no plan/authority; unverified live cards show
dashes. The existing billing-boundary timestamp guard remains unchanged.

One Overview switch applies immediately and persists in SQLite. It starts off on first
upgrade, independently of retired checkbox/JSON flags. A saved on request waits for
settings/entity/input checks on restart. Off revokes queued/in-flight ordinary writes,
stops EV and clears ESS independently; stop/persistence failures are reported. Unknown
EV SoC/phase can still pause EV independently while fresh shared inputs permit ESS work.
See SETTINGS.md for exact state, migration and rollback behavior.

Local: **135 tests39.32s**, final27 focused tests0.98s, Ruff/mypy27 modules/JS passed.
Coverage includes concurrent enable/off, mid-dispatch revocation, failed persistence,
independent stop attempts, restart/input gates, local-only API boundary, legacy backups,
notify entity/action delivery and deduplication, and incomplete-file editor availability.

Configured new-pipeline seven-day E2E:2,018 intervals accepted26.521s, maximum control
2.718ms, five fake service calls. It used the automatic Supervisor connection through
local fake DNS/auth, made zero startup hardware calls, exercised the live switch and
sent a notification only to fake HA. Browser installation fixtures verified initial
missing-field highlights, missing-number/entity edits, one immediate switch, phone
picker/save/reload/backup, removed fields/help, pending-value dashes and zero console
errors. Screenshots use settings-v406-*.png. Both temporary previews/tabs were stopped;
the existing8100 preview was preserved.

Wheel/sdist built; all33 installed package code/assets match source. Isolated installed
startup verified automatic Supervisor access, removed groups, missing-field reports
and disabled control. No live HA, installation DB, hardware, real notifications or
deployment was accessed. Actual billing timestamps and hardware/phone commissioning
remain unverified. Evidence: settings-control-verification.json and offline-e2e.json.
Remote4.0.6 code d58b97d4c9ec4c3ed44bb751227459d075f7b790 passed
[CI40008621110](https://github.com/Nxt-1/EnergyManager/actions/runs/40008621110)
(135 tests37.78s, configured E2E32.219s and package/container checks) and
[publication40008621112](https://github.com/Nxt-1/EnergyManager/actions/runs/40008621112)
(135 tests42.43s). Image digest:
`sha256:16fb0bc43e69e8a2989285a4316dd78bd51525ce8f4a5070fe21a38f4a1c0208`.
The CI timing report recorded a 4.276 s control tick before switching; its cause is
not established. Follow-up investigation separately found that disabled dispatch could
wait behind a slow final stop. A regression reproduced that lock wait; 4.0.7 fixes it.

## Version 4.0.5 — original installation forecasting restored

Configured runtime now fetches Open-Meteo KNMI seamless weather at HA zone.home,
builds the exact four-plane PV model and original front/rear corrections, and learns
household demand from persisted background measurements. No prepared forecast service
is required. Connection-address redesign remains deferred. See FORECASTING.md for exact
installation values, retained formulas, time handling and outage policy.

Local: **112 tests passed in38.59s**; Ruff, mypy25 modules and dashboard JS syntax
passed. After a final malformed-response guard, all15 focused forecast tests passed
in5.40s and the rebuilt installed wheel guard was verified. New runtime tests cover
missing/null/nonfinite/gapped weather, stale-cache
issuance, remote-access gate, restart persistence, both DST changes and current partial
quarters. An application-level blocked-weather test confirms new HA polls and at least
five independent control ticks continue, and no placeholder forecast reaches planning.

Direct comparison against preserved source matched2,520 correction factors,648 PV
points and676 household points exactly. A35-day/10,080-sample load model built in41.3ms;
full-horizon resampling took9.25ms. Four actual Open-Meteo requests through the new
client returned216 aligned hours each and passed169h coverage. Those requests used
**public Brussels city-centre coordinates**, not installation coordinates. This is a
provider-contract check, not live installation evidence.

The configured fake-HA/fake-weather application accepted2,018 intervals in29.408s,
max control tick4.617ms and26 guarded calls to loopback fakes. Persistence, current
measurements, four plane queries, learning status, API and decision validation passed.
Overview/Planning browser checks showed forecasts and source/learning labels, retained
charts/time navigation and no demonstration journey; console errors absent. Screenshots:
forecast-overview.png and forecast-planning.png under screenshots/. The constant test
weather is explicitly SYNTHETIC. The temporary8102 preview was stopped;8100 preserved.

Wheel/sdist built;31 installed code/assets exactly match source. Isolated installed
configured startup selects the restored forecast pipeline, has no demonstration goals
and keeps hardware control disabled. No live HA, installation databases, notifications,
hardware, deployment or commissioning. Detailed evidence: forecast-restoration-verification.json
and offline-e2e.json.

Remote code commit32855877ea4177351d4c49dfce256baec01dc2d4 passed
[CI39997508230](https://github.com/Nxt-1/EnergyManager/actions/runs/39997508230):
**113 tests40.92s**, lint/types/CLI/JS, restored-source configured seven-day E2E,
package and Linux container build. Remote E2E accepted2,018 intervals31.174s,
max tick8.674ms and25 fake-only service calls.
[Image39997508225](https://github.com/Nxt-1/EnergyManager/actions/runs/39997508225)
passed113 tests37.69s and published `ghcr.io/nxt-1/energymanager:4.0.5`, digest
`sha256:95ee21fc26a7bf5793e7fdad51b681b38a24ce9abb0d8c8540dfe16748aad5cd`.
No installation deployment or hardware operation was performed.

## Version 4.0.4 — simplified installation settings

Removed all source/type selectors and the nonexistent house/phase sensor inputs.
The confirmed P1/go-e setup is applied in both runtime and Settings, including legacy
files that still contain direct/energy/count choices. Known P1 IDs replace only missing
or generated placeholders; custom mappings remain. Reads/startup do not rewrite files.
Explicit save backs up the original bytes, persists defaults and removes retired choice
keys while preserving future fields, unrelated values and control flags. Daily readiness,
journey consumption and reserve controls are in EV and charger.

Local checks: **85 tests passed in30.22s**, Ruff/mypy21 modules/JS passed. Browser checks
used a legacy config and synthetic loopback HA: all unwanted fields absent before and
after reload, P1 mappings prefilled, single go-e selector, daily target saved/reloaded
inside EV group, backup verified, zero desktop console errors. Screenshots are
simple-settings-measurements.png and simple-settings-ev.png under screenshots/.

The4.0.4 wheel/sdist built. All27 code/assets match source and isolated installed files;
installed legacy read/startup/save/backup/reload passed. Seven-day E2E without any source
choices accepted2,018 intervals21.799s; max control4.812ms;20 local fake calls. Known
EV SoC and selector state, archive and API checks passed. Details are in
simple-settings-verification.json and offline-e2e.json.

Remote: commitb6297bc29e60337e78ea4bdf00bc68d5dfd8f094 passed
[CI39979435914](https://github.com/Nxt-1/EnergyManager/actions/runs/39979435914):85 tests
35.31s, lint/types/CLI/JS, configured full-horizon application, package and container.
Remote synthetic E2E:2,018 intervals accepted28.934s, max tick11.632ms,22 fake calls.
[Image39979436032](https://github.com/Nxt-1/EnergyManager/actions/runs/39979436032)
succeeded and published4.0.4. Temporary browser/service fixtures were stopped.
No live HA/controller operation; wiring, clocks, ingress and commissioning remain unverified.

## Version 4.0.3 — installation measurement compatibility

P1 quarter demand accepts W/kW with a fixed0.25h energy conversion, based on the
user-confirmed reset-and-build behavior. Source inspection confirms the P1 reader
passes OBIS1-0:1.4.0 unchanged. Separate P1 import/export reconstruct house load; other
supported sources are direct house, total consumption and signed grid power. go-e
APIv2 Connect2026.10.3 can reuse its raw phase selector1/2 without an extra sensor.
Unknown phase information pauses EV while ESS remains responsive. Phase switching
waits for fresh mode readback after stop/zero/dwell. Slightly later SoC reads remain
valid within5s of the oldest shared input; far-future readings stay unknown.

Local verification: **84 tests passed in28.57s**; Ruff, mypy21 modules and JavaScript
syntax passed. The eight new test cases cover conversion denominators, import/export,
ESS directions, unknown modes, quarter boundaries, configuration reload and delayed
mode acknowledgment. Existing tests continue to cover the original normalized inputs.
The4.0.3 wheel and source distribution built. All27 package files match source and
an isolated installed wheel; actual settings save/backup/reload passed.

Browser verification used loopback synthetic HA states: all three source choices,
conditional fields, friendly-name/keyboard P1 selections, kW demand acceptance,
selector reuse, save/backup/reload and zero desktop console errors. Evidence is in
measurement-source-verification.json and screenshots/measurement-source-choices.png.
No live HA settings or controllers were accessed.

A real spawned HiGHS solve using the new P1/go-e input choices accepted the complete
seven-day2,018-interval schedule in21.556s. The check requires known measured EV SoC;
maximum control tick5.495ms;20 calls went only to local fake services. API and archive
checks passed. Details: offline-e2e.json.

Remote verification: implementation commit7d64dd39d9cff2d1507a1ecb0db96c0ce362520b
passed [CI39971619636](https://github.com/Nxt-1/EnergyManager/actions/runs/39971619636):
84 tests30.51s, Ruff/mypy/CLI/JS, configured new-source application, package and Linux
container builds. Remote synthetic seven-day solve:2,018 intervals accepted23.380s,
max control12.712ms,19 local fake calls. [Image workflow39971619511](https://github.com/Nxt-1/EnergyManager/actions/runs/39971619511)
succeeded and published4.0.3. The temporary8102 browser fixture was stopped; existing
8100 preview preserved. Meter clock alignment, inverter AC topology/signs, ingress and
hardware timing remain live-unverified commissioning checks.

## Version 4.0.2 — visual configuration

The Settings page edits the persistent JSON using grouped form controls and searchable
entity pickers. The server reads HA states through the Supervisor proxy or a saved
standalone connection, returns friendly names/state/units without credentials, and
does not call actuator services during discovery. Validated saves preserve unknown
fields, retain original bytes in a backup and replace the file atomically. Stale edits
are rejected. File work runs outside the control event loop. Changes apply after a
restart into configured mode; saving leaves the active controller unchanged.

Local checks: **76 tests passed in28.69s**, including24 settings tests for real loopback
HTTP discovery, Supervisor proxy/token boundaries, form API, backup/reload, concurrent
and external edits, physical/field validation, atomic replacement failure and discovery
outage. Ruff, mypy20 modules and JavaScript syntax passed. The4.0.2 wheel/source package
built; isolated installed-package save/backup/reload and26-file comparison passed.
Final package details are in settings-package-verification.json.

Browser checks used explicitly synthetic, loopback-only fixtures. Friendly-name search,
keyboard selection, actuator domain/unit filtering, field validation, save/reload and
Overview/Planning navigation passed. A390px mobile layout was inspected. Desktop browser
console errors were absent. Screenshots: settings-entities.png, settings-saved.png and
settings-mobile.png under screenshots/. Structured checks are in settings-ui-verification.json.

The configured seven-day fake integration passed with2,018 intervals accepted19.933s,
maximum measured control tick5.04ms and20 fake-only service calls (offline-e2e.json).
Scheduler mathematics and control policy are unchanged. Existing full-horizon benchmark
evidence remains applicable; no new benchmark claim is made for the settings editor.
Live Supervisor/ingress and physical commissioning remain unverified. Reports below
retain previous-release evidence; offline-e2e.json now describes4.0.2.

Remote verification on commit `bdacbee29b730aed86d939159817331fe525c005`:
[CI](https://github.com/Nxt-1/EnergyManager/actions/runs/39962540057) passed all 76 tests
in 35.68 s, lint/types/CLI/JavaScript, the configured fake integration, Python package
builds and the Linux container build. That synthetic integration accepted 2,018 intervals
in 27.227 s, with a maximum measured control tick of 8.85 ms and 21 fake-only calls.
The [image workflow](https://github.com/Nxt-1/EnergyManager/actions/runs/39962539923)
also passed and published version 4.0.2. No live installation was accessed or deployed.

## Version 4.0.1 — automatic starter configuration

Missing configuration files are created from the installed package on add-on startup,
including demo mode, and standalone `--config`. Existing bytes are preserved, including
empty/invalid files and user edits. New files retain disabled control/remote access and
explicit synthetic labels. Creation failures are reported before service startup. The
Home Assistant app configuration mount is writable for this initialization.

Local verification on23 October2026: **52 tests passed in28.29s**, including nine new
filesystem/startup/error tests and real localhost API checks in demo/configured modes.
Ruff and mypy passed.4.0.1 wheel and source archive built with the bundled template.
An isolated installed wheel created a file using its packaged resource, preserved an
edited file, reported4.0.1 and matched all24 package source/asset files. The wheel hash
and results are in configuration-bootstrap-verification.json.

The full-horizon configured fake integration also passed:2,018 intervals accepted in
20.096s, maximum measured control tick5.27ms and20 fake-only calls. See offline-e2e.json.
No scheduler mathematics or control policy changed. Live Supervisor startup and physical
commissioning remain unverified. The reports below retain4.0.0 promotion/CI history;
package-verification.json and ci-verification.json describe that prior release, while
offline-e2e.json now records the new4.0.1 run.

Remote verification on commit `32ea875364836b1512efb23fadadf84383dc19ca`:
[CI](https://github.com/Nxt-1/EnergyManager/actions/runs/39938880228) passed52 tests
in34.71s, lint/types/CLI/JS, configured fake integration, package builds and the Linux
container build. That synthetic integration accepted2,018 intervals in26.999s with
maximum measured control tick14.24ms and21 fake-only calls.
The [image workflow](https://github.com/Nxt-1/EnergyManager/actions/runs/39938880153)
also passed and published4.0.1. No live installation or controller action was performed.

## Version 4.0.0 promotion history

The fresh implementation has been promoted into the main `energymanager/` application,
replacing V3 as explicitly requested on 23 October 2026. The Python distribution,
module, CLI, source version, Home Assistant release and GUI now identify version4.0.0.
The former `energymanager-next/` directory has been removed.

## Promotion and compatibility

- Main Python package and command: `energymanager`.
- Home Assistant identity retained: slug `energy_manager`, image
  `ghcr.io/nxt-1/energymanager`, ingress8099. Local development remains port8100.
- V3 source/tests/tools/dashboard entry point replaced. Root development commands and
  CI/publish checks now target the V4 package and its tests/tools/assets.
- New V4 JSON configuration and `/data/energymanager-v4.sqlite3` are explicit. V3
  options, old controller permissions and installation databases are not automatically
  imported. Startup is manual/demo, and hardware control remains disabled by default.
- Existing changelog retained below the4.0.0 release notes. Historical V3 documents,
  the separate InfluxDB app and its publish workflow were verified unchanged.
- Original working files, prior implementation and staged patch were preserved locally
  under ignored `gpt/architecture/v4-promotion-2026-10-23/`. Local promotion verification preceded commit/publication; no live deployment was
  performed. The user subsequently authorized committing and pushing the V4 update.

RUNBOOK.md documents installation mapping, explicit commissioning and V3 rollback.
This is a major configuration update, not automatic conversion of V3 settings.

## Checks rerun after promotion

| Check | Result |
|---|---|
| Repository-root pytest | **43 passed in29.64s** |
| Ruff on app/src, app/tests, app/tools | Passed |
| Mypy on the renamed package | Passed,19 modules |
| JavaScript syntax, app/card/dashboard wrapper | Passed |
| Module/CLI release identity | `EnergyManager 4.0.0` |
| Configured localhost fake-HA end to end | Passed; accepted full-horizon plan in25.724s |
| Independent control during that solve | Max measured tick5.70ms;22 fake-only service requests |
| V4 wheel and source archive | Built |
| Isolated installed-wheel CLI, real HiGHS | Optimal, valid,0.00915s |
| Packaged source/assets vs current source | All23 files byte-identical |
| Browser main application | Overview/Planning,4.0.0 branding, charts and goal create/reload/remove passed; no console errors |

The configured E2E used actual loopback HTTP measurements/issued forecasts, a spawned
168-hour solver, current-state publication, independently guarded calls to a fake only,
API version4.0.0 and persisted checksum/results. The accepted remaining trajectory has
2,018 intervals, each no longer than300s. No installation input was substituted with a
fixture. All test/demo data are explicitly labelled synthetic. Full results are in
offline-e2e.json, package-verification.json and v4-promotion-browser.json.

The rebuilt wheel is `dist/energymanager-4.0.0-py3-none-any.whl`; its SHA256 is recorded
in package-verification.json. Installed verification used `python -I`, asserted the
import came from artifacts/v4-wheel-site, and executed the actual packaged optimizer.
Home Assistant release identity, package metadata and the removed candidate directory
were also checked. The optional dashboard wrapper matches the packaged card byte for byte.

## Preserved optimization and control evidence

Twelve core modules were compared to the pre-promotion candidate after namespace
normalization: domain, forecasts, optimization, incumbent, validation, planner,
reservations, publication, control, demo plant, worker and store. Their contents match;
promotion did not change scheduler mathematics or control behavior.

The original full-horizon benchmark reports are retained as evidence. They were not
rerun for the namespace/layout promotion; the full-horizon configured E2E was rerun.
All three original aligned168h cases used2,017 intervals and one120s cycle budget:

| Synthetic case | Cycle | Peak kW | EV/ESS sessions | Optional EV kWh | Main economic gap |
|---|---:|---:|---:|---:|---:|
| Mixed solar and journey |116.207s|2.50|14/18|17.976|0.424%|
| Winter and journey |115.212s|3.21|2/14|0|12.334%|
| Urgent one-hour56% goal |116.488s|4.00|2/1|0|75.315%|

All were independently valid feasible incumbents with time-limited economic stages,
not global-optimality claims. The urgent case had2.619525kWh permitted shortfall plus a
feasible goal-scoped10.601033kW permission diagnostic. Its economic gap remains large.
Minimum-grid certificates were Optimal only within the stated fixed-mode/non-grid/
quarter-envelope scope. Stage dimensions, bounds, times, costs and outcomes remain in
benchmark-*.json. SPECIFICATION.md defines the constraints and bounded comparisons.

Original pre-promotion verification, approval/revocation/history/session/mobile checks,
package identity/hashes, screenshots and work checkpoint are labelled under
history/standalone-candidate/. Statements there about a separate package or preserving
the old checkout describe that earlier stage. Current V4 screenshots are in screenshots/.
The inherited browser-service.json and publication-replay.json are earlier evidence;
the latter is a rejected diagnostic, never a passing acceptance result.

## Remaining external checks

Supervisor, authenticated ingress and physical commissioning remain unverified.
The authorized V4 push was commit `1d420848cdbb57e50169b552c178947343a5d494`.
The [image workflow](https://github.com/Nxt-1/EnergyManager/actions/runs/39935019989)
passed, including its tests, container build and publication of version4.0.0. Docker
was unavailable locally. No live installation/database, real hardware, external
notification or controller enablement was used. Review the runbook before
installing/configuring this major update; explicit complete physical/actuator mappings
and commissioning/exclusive-controller flags are still mandatory for control.

## CI timing regression follow-up — 23 October 2026

The [initial CI run](https://github.com/Nxt-1/EnergyManager/actions/runs/39935019991)
had42 passing tests and one failure in the real-solver disconnect test. Its elapsed
wall-clock assertion expected a requested80ms sleep plus observation processing to
finish within200ms; the observed time was423ms. The image workflow passed the same
test on the same commit. Those logs do not establish the actual protective-dispatch
latency on the failing runner.

Four diagnostic local runs restricted to two CPUs recorded protective dispatch in
1.13–2.39ms, while the old sleep-based measurement varied from83.38–166.31ms. These
are synthetic local measurements, not installation evidence or a CI latency guarantee.

The test now observes actual protective-actuator delivery, requires delivery while
the real full-horizon solve is pending, checks zero EV power and the current generation,
preserves unaffected ESS validity, and waits for stale-result rejection. The2s dispatch
timeout is a test deadlock guard; it is not a control-latency claim. Host-dependent
subsecond wall-clock assertions are removed. Runtime scheduling/control code is unchanged.
Existing numerical latency measurements above remain performance evidence.

Local verification with two-CPU affinity:43 tests passed in28.29s; Ruff and mypy passed.
Four additional focused runs passed in5.31–5.40s each, also restricted to two CPUs.
The [follow-up CI run](https://github.com/Nxt-1/EnergyManager/actions/runs/39936237809)
passed on commit `9fa914a97c2e7c34c877e636c3e50f85f0bc56e8`:43 tests in33.93s,
Ruff, mypy, CLI and JavaScript checks, configured localhost integration, wheel/source
archive builds and the Linux container build. Its synthetic seven-day integration
accepted2,018 intervals in25.806s, with maximum measured control tick6.85ms and21
fake-only service calls. Structured remote evidence is in ci-verification.json.

Storage policy is unchanged: no retention deletion is enabled. Prior compressed decisions
used about72–127kB per snapshot/result pair; one-second synthetic measurement+command
bodies averaged about742 bytes/cycle. A provisional200MB/day (about6GB/month) capacity
allowance includes overhead and replans; this is an estimate, not installation growth.
Use backups and review actual disk/event rates before unattended commissioning.

No usage-limit interruption, reset credit, paid API switch or recurring automation occurred.
