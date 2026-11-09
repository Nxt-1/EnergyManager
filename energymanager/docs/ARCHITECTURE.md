# EnergyManager architecture

This is the single maintained architecture and implementation specification. Update
this same file as requirements and implementation evolve across releases and chats;
do not create a new handoff document for each version. Renamed from
`architecture/Architecture_Proposal.md` on 1 November 2026 to reflect its maintained role.
The active application is `energymanager/`; its version is recorded in config.yaml and
the changelog. Technical content last reviewed: 2 November 2026.
Accepted changes awaiting implementation are explicitly labelled below; they must not
be mistaken for behavior already shipped in the application.

Repository-wide chat and coding rules live in the root [AGENTS.md](../../AGENTS.md).
It directs chats to this architecture, the ongoing backlog and the required coding
skill, and records the user's permission and conversational preferences.
From the remainder of V4.5, each release stream has paired architecture and
implementation chats, registered in [WORK_STATE.md](WORK_STATE.md). Architecture
discussion may continue while authorized implementation tasks proceed. Later decisions
are labelled pending and do not silently amend a task already in progress.

Confirmed user decisions take precedence over engineering proposals. This document
records the resulting behavior and technical contracts; [DECISIONS.md](DECISIONS.md)
retains the decision context. [BACKLOG.md](BACKLOG.md) records ideas
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

Release4.5.0 implements the first profile-management milestone of ARCH-005, integrated
with the current4.4.17 system. Scheduling suggestions are a subsequent milestone. These loads remain
in the existing household forecast until explicit scheduling/background separation is
implemented and verified. DHW, general appliance recognition (ARCH-006), learned driving,
advanced forecasting and a standing ESS reserve for unforeseen peaks remain deferred.
ARCH-009 is implemented as a dedicated visual EV schedule page.

### Appliance profiles (ARCH-005;4.5.0)

The standalone and managed native HA dashboards have an Appliances page. Supported
program identities are dishwasher Eco and optional Heavy, and washing-machine whites
60 C, darks 40 C, darks 30 C and coloured 40 C. Heavy remains optional; an empty profile
is not fabricated. Mazak has editable provisional flat averages: Program 2,500 W,
Light 3,500 W, Production 7,000 W. There is no learned Mazak cycle or assumed duration.

The user confirmed arming the next cycle, reviewing before saving, configurable idle
completion and profile management before scheduling suggestions. Each machine maps to
its own dedicated HA power sensor (W/kW) on the Appliances page. No entity is assumed.
HA power-entity discovery uses the existing authenticated, read-only settings discovery.
Sensor mapping, threshold, idle timeout and Mazak averages persist immediately in the
existing SQLite store, separately from restart-required installation JSON. Saving them
cannot operate a machine or change EV/ESS authority. Global profile-library revisions
reject stale edits/selections from another view. Demo/configured libraries are isolated;
demo cannot collect live profiles.

Record next cycle snapshots the selected machine, program, sensor, settings and optional
load/options notes. Only explicitly armed machines are polled. The backend records at
five-second polling cadence after each read, independently of browser lifetime and the
planner. It first observes idle at/below the threshold, then starts when power rises
above it. The provisional defaults are 10 W and 15 idle minutes, configurable per
machine (1–120 idle minutes); actual standby levels and quiet phases need installation
validation. Renewed activity resets the idle timer. Failed/invalid reads and polling
gaps over 15 seconds cannot count as idle or continuous coverage. HA's available
unchanged readings remain valid; report timestamps are not new device-freshness gates.
The sensor's own resolution/update cadence limits recorded detail; no sub-sample peaks
are claimed. Finish now is an explicit alternative; there is no automatic machine start.

Idle completion retains the full tail for review and suggests trimming at the beginning
of the final idle period. Review shows the original power graph with gaps and the
selected trim range, duration, measured energy, time-weighted mean and interval peak.
Statistics use left-held measured power only across valid adjacent samples no more than
15 seconds apart. Partial coverage is labelled and cannot be selected as a reusable
profile. User confirmation establishes that the chosen range is a complete cycle;
energy alone cannot establish completion. A 24-hour arm/capture cap bounds sessions.
Service interruption keeps raw evidence for inspection but disallows selecting the
interrupted run. An armed restart requires new idle evidence before detecting a start.

#### Recorder readiness feedback — V45-A003 (implemented in4.6.7; 9 November)

The user wants clearer positive feedback that a manually armed recorder has observed
idle and is ready to detect the machine starting. Use one clear status location directly
beneath Record next cycle in the expanded appliance card; do not duplicate this indicator
on the collapsed card. Identify the armed program and show its latest measured power.
Update automatically from the active capture: waiting for idle, confirmed ready to record
with an explicit cue that the user can start the machine, and recording once capture
starts. Before a valid reading or when measurements/status are unavailable, show that
explicitly and do not retain a misleading Ready indication or treat missing power as zero.

Use the existing backend status, idle_seen, last_power_w and observation evidence, with
the existing threshold, polling, gap/restart and freshness contracts. This is a feedback
change, not a new idle dwell time, arming/start policy or hardware command. Bosch's
automatic feedback-driven capture behavior remains separate. Keep the display concise
and combine text/icon cues with colour where helpful.

Completion criteria: both dashboards visibly progress from waiting through confirmed
idle to recording without opening program groups/Details; display the active capture's
power and program; handle read failures, missing/stale status, recovery and restart
without false readiness. Preserve input/trim drafts and existing recorder transitions.
Verify with deterministic local/fake readings. On 9 November the user explicitly
authorized this implementation handoff only once the V4.6 EV implementation finishes.
At authorization, the registered EV implementation chat was working on EV-A008;
regression/release checks were still in progress. Do not dispatch V45-A003 before
that task's confirmed completion. Reconcile its released main changes and version
order before implementing this follow-up. See WORK_STATE.md for the completion watch.
EV-A008 completion was confirmed on 9 November by its implementation chat's completed
release report:4.6.6/068307cbc1319aaff0fa80d4e24c68a342a084b5, with CI and image
publication successful. Release4.6.7 incorporates that complete release before this UI change.

Both dashboards render one text/icon status immediately after the manual arm button,
inside the expanded recording form. It identifies the capture's actual program from
the library, independently of the selector or an unsaved name draft. The arm response
shows Waiting for idle / Power unavailable until a valid read. Confirmed idle shows
Ready to record / Idle detected — start the machine and actual watts (including0W);
running captures show Recording. Finished/interrupted captures leave this live indicator;
their existing review evidence remains in the library. Bosch automatic capture is excluded.

Feedback uses status, idle_seen, last_power_w, error and last_at, with backend now and
the published maximum_gap_seconds (15s). Advance age by monotonic browser time, including
status-request latency. Failed/missing/old status, sampler failure, missing/failed power,
invalid times or observations older than that gap withdraw Ready and label unavailable;
missing power is never shown as0W. A local one-second display tick prevents a hung status
request from leaving Ready indefinitely; API polling remains five seconds. Current
available unchanged HA reads stay valid regardless of HA change/report timestamps.
Restart's existing cleared idle_seen/last_at requires fresh idle confirmation. No idle
dwell, threshold, recorder transition, persistence schema or hardware policy is added.

The feedback renderer updates only indicator text/state. Input/name/notes and the
active review/trim form remain intact while existing library polling continues. The static armed acknowledgement is removed; recovered
status/sampler errors clear their own acknowledgement without erasing unrelated errors.
Older same-revision profile responses cannot replace a newer post-arm snapshot. Verified
with local synthetic reads/status faults and recorder restart; installation unverified.

The existing database adds indexed appliance_recordings and appliance_samples tables.
UTC timestamps/raw W, source, program, settings, quality failures and load notes survive
restart. Review/save stores immutable selected bounds/statistics on that recording.
From4.5.3 each program has an explicit included set of complete reviewed recordings.
Saving a new cycle adds it to that set; add/remove actions retain all original evidence.
An old selected recording upgrades as the sole contributor; older unselected recordings
are not silently included. The legacy selected ID remains a compatibility marker;
members are the averaging contract. Selection and saving its recording are transactional.
Equal-weight means align each trimmed start to elapsed zero, retain real durations and
count zero only after a confirmed complete cycle ends. No phases are stretched or
averaged across missing data. Mean energy equals the arithmetic mean of measured
cycle energies. The graph extends to the longest cycle; show mean cycle duration
separately. Build sparse sample-held curves in a ten-second bounded read-only SQLite
worker, outside control, and reject a result if its library revision changed.
GET /api/profiles/{machine}/{program} returns the derived curve and statistics; library
polls return lightweight membership/energy/duration summaries without loading raw samples.
The library lists the latest 100 nondiscarded recordings and separately returns included
profiles even if older; their contributor controls remain available when inspecting the
average. From4.5.5 explicit confirmed deletion permanently removes a recording and its samples; otherwise raw evidence is retained. Discard hides unfinished/unselected
captures without deleting evidence. Saved cycles can be inspected and reselected.

The existing same-origin/ingress boundary protects GET /api/profiles,
POST /api/profiles/{configure,arm}, GET /api/profile-recordings/{id} and recording
POST actions finish/preview/accept/select/discard. New frontend assets use the existing
versioned bundle. Unexpected recorder termination is exposed in profile status.
Save/select responses return the resulting library revision. The initiating view advances
only forms matching the successful previous revision; it retains other drafts and never
uses an ordinary poll to bypass another view's revision conflict. Failed SQLite writes
cannot update in-memory settings or leave selection ahead of persisted recording evidence.

From4.5.3 power curves are thinner on Overview, Planning, task details and Appliances;
SoC widths are unchanged. Recording reviews reuse the shared timestamp/W cursor and
mouse drag, wheel zoom, two-finger pan and pinch navigation. Profile windows are bounded
to their capture, with a one-second minimum or the whole shorter capture. Start/end
handles shade their selected interior, synchronize with the numeric seconds on every
move, support keyboard arrows and cannot cross. Text entry must be valid before updating
the graph/preview; changing bounds clears the complete-cycle confirmation. Show selection
and Full recording restore useful windows. Preview responses cannot overwrite newer
bounds or another recording. From4.5.4 saved recordings also expose editable trim fields
and handles.44px labelled HTML Start/End grips sit above the inspection tooltip;
SVG boundary lines retain wide drag targets and inspection overlays cannot intercept them.
POST /api/profile-recordings/{id}/revise validates explicit review, complete coverage
and library revision, then creates a new saved recording with copied original samples,
revised bounds/statistics, capture_id and trimmed_from provenance. This is one SQLite
transaction with membership replacement; a failure cannot leave copied evidence or
selection ahead of committed data. Every previous recording/statistic remains immutable.
At most one trim revision per physical capture contributes to an average. Selecting an
older version restores it in place of the current one, rather than duplicating the
capture's weight. Success opens the new version at its returned library revision so a
second edit cannot reuse the previous form's revision. No new machine run is started.

#### Recording-list and trim cleanup (ARCH-018;4.5.8)

Implemented in4.5.8; verified offline, live unverified. The user selected foldable
program groups for a compact recording list that scales
to many runs. Program headers retain their summary while collapsed.
Show one entry per physical recording. Only one recording may be expanded at a time;
opening another collapses the previous entry. Expanding exposes its graph and trimming
controls in place. Deletion and technical details may remain directly visible;
moving them into a secondary menu is not required.

Preserve the original Start/End slider functionality in the expanded recording:
draggable graph handles, linked numeric start/end fields in seconds, selected-range
shading, keyboard operation, bounds/non-crossing constraints and the existing chart
zoom/pan and selection/full-recording controls. The mockup's separate simplified range
inputs are illustrative, not a replacement for the working graph handles. Verify both
directions of synchronization between the graph handles and numeric fields after the
editor moves into the recording entry.

Saving a trim updates that recording's current selected bounds and statistics in place,
using the same recording identity. It must not create another recording or trim version.
This supersedes the historical4.5.4–4.5.7 version-creation behavior described above.
Library revisions still advance to protect stale edits; saves create no recording/version.
Revising a saved selection preserves its inclusion/exclusion; the explicit Add/Remove
actions manage participation. First review still saves and adds the cycle to its average.
Keep original captured samples available for adjusting the selection. Maintain atomic
average membership/statistics updates, stale-edit protection and accepted-plan evidence;
editing a library selection does not rewrite previously frozen planning evidence.

Consolidate existing trim duplicates into one recording per physical capture, retaining
the latest saved trim rather than preferring the currently included older trim. Latest
means trim-save time, not the shared capture timestamp. Preserve the original raw capture
and whether that physical capture contributes to the average; if included, use the retained
latest trim exactly once. Identify related entries by capture provenance, not matching
dates or notes. Previously frozen planning evidence remains unchanged.

The migration runs transactionally per mode before the recorder starts. Keep the original
capture ID where it survives, otherwise the first surviving copy; rank saved trims by
saved_at (insertion order only breaks ties/missing save times), never armed/started_at.
Retain one raw sample set/union, reject contradictory same-time raw readings and roll back
on failure. Historical IDs resolve through persisted aliases to the retained recording;
deleting that capture removes its samples, membership and aliases. Do not touch archived
planning decisions. Repeating startup is idempotent. There is no100-row truncation of the
recording library, so older records and included contributors stay accessible. Program
headers retain summaries while folded, and the single original graph/form is moved into
the chosen entry without recreating it during ordinary interacting polls. Existing handle
hit areas, shading, cursor, keyboard, bounds and zoom/pan remain in ProfileChart.

A contributor selection signature covers IDs, saved selection/statistics and save times.
Queued M2 runs detect in-place changes even when contributor IDs are unchanged and replan
with the updated profile. Already accepted plan evidence and an executing run's frozen
curve remain unchanged. No generic appliance/program CRUD or broader chart comparisons.

The user explicitly authorized this separate implementation handoff on 8 November 2026.
Completion criteria: compact
foldable program groups in both dashboard flows; exclusive in-place recording expansion;
unchanged graph-handle/numeric-field interaction; trim saves retain identity and do not
increase recording/version counts; existing duplicate captures consolidate to their latest
trim without lost raw measurements or duplicate average weight. Verify stale edits and
atomic persistence/membership changes, including after restart, using offline fixtures.
This follow-up is separate from the authorized M2 implementation and does not amend it.

The original ARCH-005 scheduling direction remains: earliest start/latest completion,
recommendation plus alternatives, manual appliance start/programming, and fixed
user-confirmed commitments. Before that milestone, resolve removal from background
learning, existing mixed history, unplanned runs, load variants/representative profiles,
peak permissions and Mazak timing/interruptibility/mode transitions. No such scheduling,
background subtraction, general appliance recognition or hardware control is added by
this milestone. Installation sensor identities, program status/energy entities and
appropriate threshold/timeout values are still unverified. No live HA/database access,
measurements, hardware operation, notifications or deployment occurred.

### Pending V4.5 direction — user-managed appliance library (V45-A001)

Agreed on 1 November 2026; not implemented or authorized for implementation. Replace
the fixed appliance/program catalogue with a user-managed library. Support additional
appliances and their programs without appliance-name-specific code. Operating behavior
determines planning support: the initial scheduling behavior is a manually started,
uninterrupted program cycle, using its reviewed power profile and an earliest-start /
latest-finish window. The user starts a manual appliance directly or sets its delayed
start; a confirmed manually arranged run becomes a fixed commitment, as in ARCH-005.
On 2 November the user selected a dedicated Bosch dishwasher integration through HA
as an additional pending direction. This supersedes the manual-only assumption for
that dishwasher; its agreed scheduling/commitment policy is recorded under V45-A002
below.

The agreed configuration model has three levels:
- Appliance: a user-defined name and an operating behavior chosen from predefined
  options. The specific behavior options and their required configuration are still
  to be agreed; manual delayed-start restrictions have not been selected.
- Program: a name and several recorded profiles, using the existing explicit
  membership/averaging contract. There is no separate variants model; materially
  different cycles can be separate programs.
- Planned run: the selected program plus inputs required by its operating behavior,
  such as readiness times. Directly controlled appliances may need fewer user inputs;
  their exact requirements and control support remain to be defined. This direction
  does not authorize implementing direct control.

Define these options and behavior-dependent requirements before designing the UI/UX.

Adding a library item does not establish remote control or scheduling support for every
kind of equipment. Recording profiles may serve other equipment before its operating
behavior is supported. Variable-duration/multi-mode Mazak work, thermal storage and
modulated/interruptible charging require their own explicit behavior; they must not be
treated as ordinary uninterrupted cycles merely because they appear in a library.

The existing appliances/programs and recordings must be preserved when introducing
the editable library. The user chose permanent recording deletion after confirmation,
including its stored samples; there is no recoverable archive. Deletion is separate
from removing a recording's contribution to an average, which retains the recording.
Deleting an included recording also removes its contribution from the program average.
Remaining editing fields, program/appliance removal and dependent-data handling remain to
be decided. The user identified missing saved-recording removal and program management
as current gaps.
This direction does not resolve the scheduling/background-accounting questions above.
See [DECISIONS.md](DECISIONS.md) and the V4.5 coordination record in
[WORK_STATE.md](WORK_STATE.md).

#### UI program creation and renaming — 8 November 2026 (V45-A001-P1; implemented4.6.2, offline verified)

The user wants to add programs from the UI for the washing machine and similar
appliances with manually maintained program lists. Bosch dishwasher programs remain
supplied by its known HA catalogue; do not expose manual program creation for Bosch.
Use the already agreed program model: a user-defined name with multiple reviewed
recordings, without a variants model or an invented power/duration estimate.

Authorized small delivery scope: an Add program action inside the expanded washing-
machine card, a name-only creation form, persistent program identity/name, immediate
availability in Record next cycle and the existing foldable program groups. New
programs initially have no recordings/profile. Preserve existing program identities,
recordings and averaging/trim behavior.

The user confirmed that this package includes renaming programs. Allow renaming both
existing and newly created washing-machine programs. Rename the display name while
retaining stable program identity, recording links, selected average members and raw
captures. The updated name appears consistently in selectors, program groups and
recording review; do not rewrite previously frozen planning evidence. Bosch's HA
catalogue remains outside these manual create/rename controls. Reject empty names and
ambiguous duplicate names within the same appliance; routine name-validation details
are implementation choices.

Completion criteria for V45-A001-P1: create and rename through both dashboard flows;
new programs are immediately available for recording; existing IDs/recordings/averages
survive migration and rename; names and new programs persist across reload/restart.
Verify stale-edit protection, invalid/duplicate names and that these metadata actions
do not send appliance commands. Preserve the original trim interaction and foldable
groups from4.5.8. This is separate from adding appliances, program removal/dependent-
data policy or washing-machine scheduling/control. On 8 November the user explicitly
authorized implementation and requested a start 1 hour and 11 minutes later. A one-time
task targeted the registered implementation chat at19:33:57 Europe/Brussels that day;
see WORK_STATE.md for its schedule identifier. Reconcile current main and release
ordering before selecting a release version; do not assume a4.5.x patch is appropriate
if a newer stream has already reached main.

P1 implementation contract: the effective washing-machine catalogue retains the four
legacy IDs and overlays a mode-isolated manual_programs.washing_machine map in the
existing profile settings. The first metadata edit persists the effective legacy names
alongside new opaque program_UUID identities. Existing recording/sample rows, average
membership, source signatures and archived planning evidence are not rewritten. There
is no provisional power/duration/profile for a new program. Bosch remains HA-supplied.

POST /api/profiles/program-create and program-rename require same-origin JSON and the
current library revision, and accept only washing_machine. Names use Unicode NFKC,
collapsed/trimmed whitespace,1–80 printable characters and case-folded duplicate checks
within this appliance (excluding the same ID when renaming). Persist settings atomically
before advancing in-memory state. Metadata actions do not send appliance commands.

Both dashboards share Add/Rename controls in the expanded washer card (inline from
4.6.5/P2 below, superseding P1's separate fold-outs). Creation selects the new identity
for Record next cycle; selectors, foldable groups and an open review heading update
without replacing its chart/trim draft. Opening a name editor snapshots the current
revision; edited drafts retain that conflict guard across ordinary catalogue polling.
Older in-flight profile polls cannot replace a newer metadata catalogue. Existing graph
handles, linked fields, exclusive inline review and same-ID trim saves are retained.
Program removal, appliance CRUD and washing-machine control/scheduling remain outside P1.
The one-time start fired8November and its automation was deleted after dispatch. Release
4.6.2 incorporates main4.6.1; the task's V4.5 label does not roll back newer releases.

#### Inline program actions — V45-A001-P2 (implemented in4.6.5; 9 November)

The user approved the selector-adjacent Add/Rename preview and confirmed that the
name field replaces the selector while editing. Place Add and Rename icons beside
the washing-machine recording program selector. Rename targets that selection and
prefills its current name. Add opens an empty name field. Only one inline editor
appears, with Save/Cancel icons; creation selects the new program automatically.
Cancel retains the original program/name and makes no metadata change. Replace the
two separate management fold-outs and their duplicate program selector with these
controls. Keep concise labels, accessible action names and usable touch targets.

Preserve P1's existing metadata APIs, validation, stable identities, recording/average
links and stale-edit handling. Retain name drafts on validation/conflict errors and
do not reset recording notes or an existing recording trim draft when saving names.
Bosch remains outside manual Add/Rename. The approved preview is
`program-selector-actions.html` in this chat's visualization directory.

Completion criteria: both dashboards support Add/selected-program Rename, Save and
Cancel in the approved location; the newly created program becomes selected; name
editing never arms a recording or sends an appliance command. Verify keyboard
Save/Cancel, narrow layouts, validation/conflict handling and preservation of current
recording/review state. This is a separate UI follow-up to implemented P1. On 9 November
the user explicitly authorized the implementation handoff: "yes, hand it over".
Release4.6.5 incorporates main4.6.4 before this UI follow-up. Both dashboards use the
shared selector/name row with44px labelled Add/Rename/Save/Cancel icon targets. Only
the active control is enabled: editing disables the hidden selector and Record next
cycle, and routes submission exclusively to P1's metadata endpoint. Enter saves and
Escape cancels; focus returns to the selector after success/cancel. Save errors keep
the typed name, original identity/revision, recording notes and open review/trim state.
Same-view successful profile edits advance compatible revision guards as in P1;
another view's edits remain conflicts. No preview example data enters the application.
Verified with deterministic local fixtures; installation behavior remains unverified.

#### Pending Appliances UI direction — agreed 2 November 2026

Keep most, potentially all, appliances on one shared Appliances page. Use two stages:
- On opening the page, show relatively large cards, one per appliance, with an icon
  and the most relevant information and controls for that appliance. Keep this view
  concise and avoid exposing all settings/history on the overview.
- Clicking an appliance card enlarges that original card in place to reveal its full
  information and controls on the same Appliances page. The user explicitly chose
  this instead of navigation to a new page or a popup dialog. Embedded controls must
  remain usable without unintentionally expanding/collapsing the card. At most one
  card may be expanded: expanding another collapses the previously expanded card.
  Exact expanded layout and collapse interaction remain open.

The user selected an on-card program selector for the Bosch dishwasher, using the
space that would otherwise display the program name. Default to Eco for a new run;
preserve an explicit program choice and reflect the actual queued/running program.
An ordinary refresh or reopening the page must not reset that choice to Eco. Other
card fields/actions and the detailed expanded layout remain under discussion.

The user approved the initial card/expansion design preview and selected three Bosch
finish-deadline choices on the card: Tomorrow 12:00 (noon), Tomorrow 18:00 and a custom
time icon opening a small date/time popup. These set the latest finish, not the start.
Tomorrow means the next installation-local calendar date at the selected wall time,
not a fixed elapsed-hours offset. Custom values remain visible after choosing them.
Selecting a deadline does not itself mark the dishwasher Ready. The small date/time
popup is distinct from appliance details, which still expand in the original card.
For custom selection, show a directly clickable calendar with dates selectable from
today through seven days ahead, beside a time-picker wheel. Use installation-local
calendar dates. Show only those dates in a compact rolling selection; do not display
a full month with other dates disabled, blank padding cells or month navigation.
The user clarified that the seven-day limit is intended to simplify the visible
calendar. The current time-wheel design may remain, although it differs from the
user's original mental image. Replace the separate date/time entry fields and nested
native picker flow shown in the earlier preview. Preserve the selected deadline on
the card. The user approved the corrected compact rolling-date picker preview on
2 November 2026, with the existing time wheel retained.
No default finish-deadline preset has been selected by the user.

The shared page/card layout accommodates the appliance's supported behavior,
including the dedicated Bosch integration. This is agreed UI direction, not an
implemented redesign or application-code authorization.

#### Appliance connectivity investigation — 1 November 2026 (V45-Q006)

User-reported equipment: Miele WSD 663 WCS TwinDos, whose app connectivity has not
worked for years; Bosch SMS6ZCW08E Serie 6, connected to its app/internet with fine
delayed-start options. Neither appliance's HA integration or commands were tested.
Research establishes potential integration paths, not installation control capability:

- Bosch's [model support page](https://www.bosch-home.co.uk/customer-service/SMS6ZCW08E/36)
  lists Home Connect remote monitoring/control and Remote Start. HA's official
  [Home Connect integration](https://www.home-assistant.io/integrations/home_connect/)
  uses the cloud API and supports program selection/start, relative start-delay options
  for dishwashers and remote-control/start availability sensors. Actual exposed options,
  authorization/door behavior and appliance revision remain to be checked.
- HA's official [Miele integration](https://www.home-assistant.io/integrations/miele/)
  uses the manufacturer API and requires the appliance connected to the Miele account/
  CloudService. Start, program and status support depends on model/API capabilities.
  The [WSD663 Belgian manual](https://media.miele.com/downloads/46/46/01_96106053F20B1EEDBCF8D9EBCEA74646.pdf)
  documents MobileStart/remote control, app or WPS pairing, network reset, and delayed
  start from 30 minutes to 24 hours: half-hour steps below 10 hours, hourly above.
  Its remote/SmartGrid windows can auto-start at the latest start time without an
  external signal; this needs explicit accounting if that mode is used.
- Miele's [network requirements](https://www.miele.com/de/com/systemvoraussetzungen-6743.htm)
  specify 2.4 GHz; its [WPA2 support guidance](https://www.miele.nl/support/customer-assistance/app-848/alle/apparaat_niet_verbonden-93659538699)
  identifies WPA3/mixed WPA2+WPA3 as a possible connection failure. No cause has been
  established for this installation. Determine the failure stage/error before changes.
- The unofficial [MieleRESTServer](https://github.com/akappner/MieleRESTServer)
  offers local provisioning/control and reports WSD663 basic information and remote
  start compatibility. It requires working local networking and preparation of the
  program on the machine; it does not remotely configure programs. This is a possible
  workaround, community-reported and unverified here, not an adopted dependency.

Potential EnergyManager use through HA still requires agreed requirements and an
authorized implementation. Public documentation research does not authorize live
HA access, pairing, appliance/network changes or hardware operation.

#### Bosch HA capability handoff — 2 November 2026 (pending V45-A002)

The user supplied the Bosch support chat's findings and selected a dedicated
dishwasher implementation direction. This is design discussion, not authorization
to write application code or operate the dishwasher. The generic library direction
has not been explicitly withdrawn. Recording reviewed program power profiles is
the next stated focus; exact recording/control scope remains to be agreed.

- Built-in Home Connect is connected through Bosch's cloud API. The user confirmed
  HA can turn on the dishwasher from off. Other controls/delayed start are assumed
  usable for design; actual program start, delayed execution and precision were
  not verified in the supplied handoff.
- Selected/active program controls expose Intensive 70 C, Auto 2, Eco 50 C,
  Pre-rinse, Night wash, Speed 60 C and Machine care. Eco 50 C was selected.
- `number.kitchen_dishwasher_start_in_relative` exposes 0–86,400 seconds, step 1.
  This is an entity setting range, not evidence of one-second execution precision.
- Exposed readings include remote-control/start permissions, door, operation state,
  finish time and progress. Reported operation options include ready, delayedstart,
  run, finished and error. At inspection permissions were on, door open, state ready;
  finish/progress were unavailable. Permissions alone do not establish loaded/ready
  status or the ability to start with an open door.
- Extra dry, Half load and Vario speed+ switches are exposed. The user uses Eco
  roughly 90% of the time, otherwise most likely Intensive, and almost never these
  modifiers. Keep modifiers available to enable, but do not adjust the planning
  profile or introduce modifier-dependent profiles for them in this scope. If desired
  later, the user will add profiles for specific program/modifier combinations.
  The agreed absence of a separate variants model still applies. Recording inclusion
  for unusual modified cycles and future combination mapping remain to be defined.
- HA's appliance power switch is not a consumption measurement. Planning will use
  reviewed measured power profiles; a dedicated power-measurement source is still
  required for recordings. The user confirms a Refoss measures the dishwasher among
  several kitchen appliances. Its dedicated dishwasher HA power entity still needs
  mapping; no entity ID or measurement cadence/quality has been supplied.

Agreed recording behavior for V45-A002: automatically capture dishwasher runs using
Bosch program/operation feedback and Refoss power measurements, including runs
started at the panel or through the Bosch app. Explicit per-cycle arming is not
required for this integration. Track actual program execution rather than treating
power-on or delayed-start waiting as the cycle. Retain review before contribution
to a program average and the existing coverage/completeness requirements; automatic
capture does not establish that an interrupted or partly observed cycle is usable.
Exact state-transition/restart handling remains an implementation detail to specify
within the agreed contract. This uses dedicated appliance feedback and does not
authorize the separately deferred general load-recognition work in ARCH-006.

Agreed scheduling handoff for V45-A002: the user loads the dishwasher, selects the
program and sets a latest end date/time, then confirms it ready for management.
From that handoff the manager may start immediately or choose a later start at its
discretion to meet the deadline. There is no additional user-entered earliest-start
restriction for this workflow; the handoff time is the earliest authorized start.
This specifies future application permission, not agent permission to operate the
installation. While waiting, the manager may revise the planned start without
further user confirmation, keeping the selected program and latest finish constraint.
Once started, the dishwasher runs uninterrupted; scheduling does not pause or move
the running cycle. This supersedes fixed-start commitments for this automatically
managed Bosch workflow only.

Opening the door while a managed run is waiting retains the queued run and blocks
starting. The user confirmed automatic resumption of planned operation when the door
closes and remote-start permission is available again, without another Ready action.
The selected program/deadline remain attached to the queued run and the user can
explicitly cancel it. This concerns a run waiting to start, not automatic resumption
of a physically interrupted running cycle.

For the unlikely case of a manual program change at the panel or in the Bosch app
while queued, the user accepted adopting the newly selected program and recalculating
the start against the existing finish deadline, without another Ready confirmation.
Do not restore the old program over the user's choice. Modifier controls retain the
agreed base-profile estimation policy.

For a program without a usable reviewed recording, the user selected Start now and
record as the initial workflow. Optimized scheduling becomes available once at least
one complete usable recording has been reviewed and included in that program's
profile. Do not require provisional manually entered duration/consumption estimates.
This also applies if a program loses its last usable profile or a manually selected
program has no usable profile; do not invent a curve or reuse a different program's
measurements. Automatic capture remains available for normal panel/app-started runs.

The user considers exact dishwasher timing generally noncritical, but wants actual
per-program duration learned from the recordings. Use a learned duration estimate
without an added scheduling safety margin; do not add a buffer or choose a longer
duration solely as uncertainty protection. Keep actual cycle timings as evidence and
improve estimates as usable recordings accumulate. The entered latest finish still
constrains planned estimated completion; this is not permission to knowingly plan late
for a cheaper start when an on-time plan is feasible. Actual completion remains an
estimate and may vary. The impossible-deadline fallback below remains applicable.

The user selected EnergyManager-held timing: retain the planned start in EnergyManager
and issue Start through HA at the chosen time. Do not program the dishwasher's native
delay as the managed-run timer. The user accepts waiting if the controller is unavailable
at the planned time; starting through a controller outage is not a requirement. On
recovery, retained work must be reconciled with actual appliance state before any start
command, under the same readiness and control permissions. Existing user/app-set delays
still need an explicit reconciliation policy.

For a deadline that cannot be met even with immediate start, show a UI warning when
the deadline is entered, giving the earliest expected finish and explaining that the
dishwasher will start as soon as possible. The user confirmed that leaving the deadline
unchanged and confirming Ready authorizes this fallback; there is no extra countdown
or confirmation. Do not silently treat the deadline as achievable. This fallback does
not establish permission to bypass unavailable
remote start, an open door, appliance faults or existing control/peak permissions.

#### Agreed Bosch delivery milestones — 2 November 2026

The user approved this split for V45-A002. M1 was explicitly authorized in the registered implementation chat on 2 November and is implemented in4.5.5, verified offline only. M2 was separately authorized on7 November2026; its implementation contract is below.

**V45-A002-M1 — appliance cards and profile collection.** Deliver the shared appliance
card overview/one-card expansion and Bosch program/status feedback, automatic Refoss
run recordings and review/permanent-deletion controls. The user also agreed to include
manually initiated program/modifier controls and Start now and record in M1. Preserve
existing washing-machine
recording, Mazak settings and stored profiles. The generic appliance/program management
direction V45-A001 is not withdrawn or automatically added in full to this milestone.

Completion criteria for M1:
- Both supported dashboards show the shared cards and in-place expansion. Existing
  programs, notes, sensor settings, recordings and average membership survive migration.
- Configure/map the Bosch program/status sources and dedicated Refoss power entity;
  represent absent or unavailable inputs explicitly. Preserve the reported HA program
  identities instead of assuming legacy Heavy and Intensive are interchangeable.
- Provide explicit manual program/modifier controls and Start now and record. Program
  selection uses HA's selected-program control and must not implicitly start a cycle;
  the active-program control must not be mistaken for a harmless selection. Eco is a
  new-run UI default, not an instruction to overwrite a device/user choice on load.
  Rendering, polling and recording alone must not send appliance commands. Explicit
  command handling respects application mode/authority, appliance state, closed-door
  and available remote-control/start permissions as relevant. A command response is
  not proof of a running cycle; use feedback and expose command failures accurately.
- Capture actual program runs automatically, including panel/app starts; distinguish
  waiting/off/finished/error and retain incomplete/interrupted evidence without treating
  it as a complete usable profile. Browser closure does not stop capture.
- Reviewed complete recordings retain working graph inspection/trim, duration/energy
  statistics and explicit average membership. Deletion after confirmation removes the
  selected recording's stored data and contribution without stale average references.
- Verify with deterministic fake/local HA state and power traces, persistence/restart
  cases and compact/expanded card interactions. No live installation verification is
  implied by offline results; follow the existing release/runbook checks when authorized.

M1 does not add a managed start timer, automatic program/modifier commands or joint
planning/background-forecast changes. Scheduling handoff/deadline controls belong to
M2; the complete approved UI preview is the target across both milestones, not evidence
that M1 includes working optimized scheduling. Actual entity IDs must be mapped during
configuration; do not invent them from the capability labels. The user starts the
registered implementation chat to authorize the task. Agent live HA access, appliance
operation and deployment still require their own authorization.

**M1 implementation contract (4.5.5; offline verified, live unverified).** The existing
Appliances component supplies both dashboards with three cards (Bosch dishwasher,
washing machine and Mazak). One original card expands in place; embedded controls do
not toggle it. No Ready/deadline/scheduled-start actions are provided in M1.

The Bosch mapping form stores explicit entity IDs immediately in the mode-isolated
profile SQLite settings, under the existing library revision guard. No installation
IDs are supplied by defaults. Map selected-program and active-program selects separately,
operation sensor and the dedicated dishwasher W/kW meter. Additional mappings cover
appliance power switch, remote-control/start binary sensors, door binary/sensor,
read-only native-delay number in seconds, finish/progress sensors and the three modifier
switches. Optional absent/unavailable feedback remains explicit. Available HA selected
program options and actual active program identities are persisted as distinct program
keys alongside the legacy catalogue. Heavy is not remapped to Intensive, and old curves,
notes, settings and average membership are unchanged. Eco is only an initial UI fallback
when an actual/explicit choice is absent. An unapplied UI choice is stored locally per mode/mapped selected-program entity and restored only while actual selection is unchanged; running feedback takes priority. Rendering and polling send no appliance writes.

A backend worker reads Bosch feedback and its dedicated meter together at the existing
nominal five-second cadence. Idle/delayed-start waiting does not start a capture. A
transition from ready/inactive/finished/delayedstart to run, observed within15seconds,
starts a candidate complete capture using the reported active program. A run first seen
already underway, a changed program during execution or a restart creates/retains
interrupted evidence. Missing operation feedback interrupts usability; missing/invalid
power is stored as a gap. Quiet measured phases do not trigger idle completion for Bosch.
Only finished feedback completes its automatic capture; error, pause, inactive or other
non-run transitions retain interrupted review evidence. The existing24hour cap still
applies. Restart finalizes an open recording as interrupted and never reconstructs the
missing cycle. Stopping a Bosch recording manually ends collection, not the appliance,
and marks it incomplete. Finishing/discarding/deleting collection cannot recapture that
same continuously observed run. Automatic captures retain modifier feedback at start;
the user reviews whether a run represents its base program. No modifier energy correction
or automatic average inclusion is added.

Manual actions perform fresh mapped reads, require configured mode and enabled application
hardware authority, and recheck its generation/mappings immediately before a single HA
write. Selection uses select.select_option on selected-program only. Start now and record
uses that service on active-program only after actual selected-program feedback matches,
power-on/idle state, a closed door, remote-control/start permissions, an available dedicated
meter, and confirmed zero native delay in seconds. Running, delayed, unavailable or unknown
operation states cannot start. M1 never clears/programs the native delay or powers on implicitly.
Power on is its own explicit switch.turn_on action from confirmed off with remote-control
permission. Modifier on/off actions are explicit and require powered-on idle state and
remote-control permission. Accepted HA requests remain pending until matching feedback;
a30second lack of confirmation and failed/unknown requests remain visible. There are no
automatic retries/replays, start timers or automatic program/modifier/power commands.

POST /api/profiles/bosch-configure and /api/profiles/bosch-command use the existing
same-origin JSON/ingress boundary. POST /api/profile-recordings/{id}/delete requires
confirmed=true and the current library revision. One SQLite transaction removes exactly
that row, its samples and its average membership/selected reference; failure leaves both
persisted and in-memory state unchanged. Other trim revisions have independent copied
samples and survive deletion, retaining their opaque capture provenance. Removing from
an average still retains evidence. In-flight reads cannot resurrect deleted samples;
concurrent average derivations are rejected if the library revision changes. Washing
machine/manual capture and Mazak settings retain their existing behavior. No planner,
background-demand accounting or physical installation validation is included.

V45-Q017 — fixed in4.5.6 (7 November2026; offline verification). A successful HA
read of active-program state unknown retains a valid bounded list of startable program
options, independently of the absent current program. State remains null: it is never
copied from selected-program or treated as execution feedback. Genuinely unavailable
entities, failed reads and malformed active-program capabilities have no usable options;
a missing requested option still blocks Start. Selected-program must be known and match
as before, with the same operation/power, door, remote permissions, zero native delay,
meter, configured-mode and hardware-generation guards. No automatic retry or live
installation operation is added. The reported4.5.5 failure was reproduced locally before
the fix; the user authorized this scoped M1 repair in V4.5 architecture. Source contract:
[HA Home Connect program select](https://github.com/home-assistant/core/blob/dev/homeassistant/components/home_connect/select.py)
maintains its options independently of current program value.

**V45-A002-M2 — managed scheduling.** Add the agreed Ready/finish-time workflow,
joint start optimization alongside EV/ESS and execution through HA at the selected
time. Include correct separation of dishwasher demand from background forecasts and
existing mixed history, representation of already-running/manual cycles, and the
agreed timing/replanning/intervention rules. Its authorized scope and completion criteria are recorded below. M2 depends on M1's capture/
profile contract and requires a usable reviewed profile per scheduled program.

For a dishwasher deadline that conflicts with the permitted quarter-hour peak, the
user wants to decide for the particular situation. Present a later finish within the
current allowance and an on-time option with its required peak increase, plus estimated
cost consequences where available. Allow changing the deadline or cancelling the run.
A standing preference for lateness or a higher peak has not been selected. Higher
proposed peaks continue through explicit approval. The user accepted showing the
alternatives on the appliance card, sending a notice through the configured phone
channel and keeping the run queued while the conflict remains unresolved. Resume
after the user chooses an alternative, or if the original request becomes feasible
within its deadline and existing permissions. Notification delivery itself does not
authorize a higher peak or a later finish.

For M2, use a measured constant for the default household background forecast.
Calculate it from representative household observations after subtracting matched
Refoss dishwasher draw. Refresh the estimate periodically and use one level across
each issued planning horizon. Add dishwasher program demand separately for scheduled
and observed runs. The existing time-of-day learner is a comparison candidate if
evaluation on separate measured data shows an improvement. The user accepted a rolling
seven-day averaging window. Refresh cadence, coverage requirements and transition from
mixed history still need final specification.
The forecasting change is pending. See [FORECASTING.md](FORECASTING.md) for the
current learner.

Use valid measured background readings in the agreed rolling seven-day window.
Refresh on the existing 30-minute forecast cycle is proposed. Older readings are
eligible where retained evidence establishes the dishwasher
contribution or an idle period. A full new week of collection is not required. Data
coverage and initial-estimate eligibility still need definition.

#### M2 implementation scope — authorized 7 November 2026

The user reviewed the work-package summary and explicitly authorized its handoff to
the registered V4.5 implementation chat on 7 November 2026. The following scope is
the authorized M2 contract. Subsequent energy-profile visualization discussion is a
separate follow-up and requires an explicit amendment to enter this implementation.

- Calculate and persist the measured constant background estimate over the agreed
  rolling seven days. Use the existing 30-minute forecast refresh as the initial
  engineering default. Reuse retained observations with adequate evidence of the
  dishwasher contribution, account for gaps and report insufficient coverage. Define
  and document coverage checks using the actual sampling contracts. A fresh week of
  measurements is unnecessary when usable historical evidence exists.
- Keep household/background and explicit dishwasher accounting consistent across
  historical estimation, forecast corrections, planning and actual execution. Preserve
  raw evidence and recorded forecast provenance. Missing dishwasher measurements or
  running-profile estimates must remain explicit rather than becoming zero demand.
- Add the reviewed program curve to joint EV/ESS planning with a movable start before
  execution and an uninterrupted cycle afterward. Preserve the curve's energy when
  mapping it to planning intervals. Use measured duration without added padding and
  the existing source, quarter-hour peak and approval contracts. Freeze profile and
  forecast evidence with each accepted plan and reconcile actual/manual runs.
- Deliver the approved Ready/deadline card controls, two tomorrow presets and compact
  rolling-date/time-wheel picker. Keep the selected program, account for manual
  changes and door reopening, and implement the agreed impossible-deadline warning
  and per-conflict approval/notification/queued-wait behavior.
- Persist readiness and queued work. Execute through fresh HA feedback and existing
  command guards at the planned start, with EnergyManager holding the timer. Reconcile
  actual operation on recovery before sending commands. Respect the existing native-
  delay guard when accepting management of a run with an appliance-set timer.
- Verify normal scheduled starts, replanning, manual starts, missing profiles/data,
  restart/ambiguous command outcomes, pending approvals and complete energy accounting
  with deterministic local/fake endpoints. Verify both dashboard flows and the existing
  release checks. Record live installation validation separately when authorized.

Completion requires an accepted joint plan and guarded execution for a reviewed Eco
profile, with that run counted once in load/energy projections, all agreed user choices
persisted and the critical offline regressions passing. Implementation must reconcile
the concurrently maintained EV requirements and release order before integration.

**M2 implementation contract (4.5.7; offline verified, live unverified).** The shared
Bosch card supplies persistent Ready/deadline/edit/cancel controls and per-run audited
conflict choices. No deadline is committed by default. The eight rolling local dates
and hour/minute wheels respect the installation timezone; nonexistent local times block
saving and repeated times require an occurrence. Door reopening retains readiness;
selected-program changes use the new reviewed profile against the same deadline.
Alternatives are counterfactuals, never authority. Unresolved requests remain queued
with retry/deduplicated notices through the configured phone path. An independently
valid standby-only EV/ESS plan may remain active while a queued request awaits a choice.

Joint binary start choices integrate the complete measured step curve over partial
planning intervals, with mean duration used only for estimated finish. Frozen plans
retain contributor/curve evidence. Selected-run quarter limits and24hour ESS support
cannot use another possible start as evidence. Source, loss and economic comparisons
remain independently audited. Outside the complete curve add retained measured standby
once; the curve replaces standby during its support. Observed running timing is fixed.
A first-seen-running cycle without a known start, missing profile or already overlong
run leaves remaining demand explicitly unknown and blocks new planning.

Execution requires the exact current admitted queued plan, fresh validated measurements/
forecast/appliance feedback, enabled authority and all existing idle/on, door, remote,
meter and zero-native-delay guards. Recheck generation/mappings immediately before the
single HA write. Persist starting intent before submission; ambiguous outcomes never
replay. Actual run/finished feedback is authoritative. Startup shared-plan recovery waits
for fresh appliance reconciliation and rejects incompatible run/profile contexts. There
are no automatic program/modifier/power-on commands or native timer programming.

The default measured-constant-7d-v1 background refreshes every30minutes. Store raw house
and separately matched house-minus-dishwasher evidence, including standby subtraction;
actual house/grid control retains total physical power. Older mixed samples qualify only
with retained same-entity dedicated readings bracketing them within15seconds. Deduplicate
equal retained traces; exclude ambiguous evidence. Join eligible five-minute samples at
most315seconds apart (300second persistence cadence plus15second read/scheduling tolerance).
Report supported duration, gaps, source and seven-day coverage; the one-hour/13-bin
bootstrap is not proof of representativeness. Meter changes invalidate mixed forecasts.
Bias corrections use matched background; missing readings are gaps rather than zero.
Unmapped installations use an explicitly unseparated household constant. The earlier
time-of-day learner remains comparison code, not the issued default.

V45-Q019 — M2 contract clarification (7 November 2026): use measured mean cycle
duration for the estimated finish/deadline check, without padding. The equal-weight
real-elapsed average curve still extends to the longest included recording; map its
complete tail for energy, source and peak accounting. Do not truncate at the mean
duration or stretch the curve to it. Estimated completion is not a guaranteed end or
an instruction to mark the appliance finished: observed Bosch state remains authoritative.

The implementation's initial coverage rule is an engineering eligibility threshold:
at least one covered hour and 13 distinct five-minute household observations within
the rolling seven days, using matched dedicated-meter observations or explicit retained
idle evidence. Count only actually supported intervals, never bridge gaps beyond the
five-minute sampling contract. Meter matching uses observations within 15 seconds;
available unchanged HA values remain valid under the existing reader contract. Missing
meter data alone is not idle/zero evidence. Document idle/standby accounting, covered
duration and gaps; meeting this minimum does not establish that a full week was observed
or that the estimate has been validated as representative of the installation.

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
  factors. Use [FORECASTING.md](FORECASTING.md) for their exact recovered values.
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
See [FORECASTING.md](FORECASTING.md) for numerical parameters, source provenance and failure behavior.
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

Dashboard presentation preference confirmed 8 November2026: keep visible text
minimal and prefer clear visual cues over explanatory paragraphs. Preserve concise
values, units and accessible names; put supplementary detail in appropriate native
sensor history or optional detail rather than the normal dashboard/cursor view.
Where a displayed measured value or state has an applicable real HA entity, make
it a keyboard/touch-accessible standard HA more-info/history action for that entity.
Apply this across the dashboard, not only EV readings. Derived/composite values use
their genuine contributing-source history where available; forecasts and controller
requests must not masquerade as measured HA sensors. This is a presentation/source
contract, not authorization to create synthetic HA entities.

Version4.2.0 replaces the optional iframe wrapper with a real HA dashboard strategy,
native sensor history actions and custom planning, EV and settings
cards. The add-on remains the planner, controller and persistent configuration owner.
The sidebar/standalone interface remains available using the same reusable components.

One-time setup installs the small `energymanager-card.js` resource and the strategy
configuration documented in [the dashboard guide](../../energymanager-dashboard/README.md).
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

The five live boxes also show today's energy in kWh: separate grid import/export,
AC/DC solar, household demand, EV charging and ESS AC charge/discharge. From4.5.2,
grid import/export use the selected P1 cumulative energy counters, not power integration.
Two Settings mappings, measurements.grid_import_kwh/grid_export_kwh, accept Wh/kWh
and start empty on upgrade. They are required only for the corresponding daily total,
not for planning/control. Use the combined Cumulative Active Import/Export counters,
not individual tariff registers or a daily-reset utility meter. Read them independently
every30s; unchanged available states remain valid. HA recorder's initial state at local
midnight supplies each baseline through its authenticated read-only history API.
Persist that baseline and last counter per timezone/date/entity across app restarts.
Missing midnight history/current readings, invalid units/values, or detected counter
decreases/reset metadata changes withhold only the affected total, with an explicit
reason and no power/first-read fallback. Other-direction and power-archive outages do
not erase a valid counter difference. A detected reset stays unavailable for that day;
a new local day/mapping has its own baseline. Demo does not read configured counters.
The meter/HA update resolution bounds midnight accuracy; an unreported reset entirely
between reads cannot be established from two cumulative values alone.
First-available day-end estimates use these meter subtotals; unknown channels remain
unknown independently. Older integrated fallback grid estimates are withheld without
rewriting their evidence; fixed midnight forecasts remain planned power calculations.

Other boxes remain integrations of existing validated recorded powers, not battery
energy changes. Integration uses the installation-local midnight (including
23/25-hour days), holds each power only until the next read or its input-read watchdog,
deduplicates cached snapshots and excludes missing/invalid or other-mode data. Missing
coverage is labelled partial; no coverage is unavailable. Summaries refresh every30s.
An expression index on measurement timestamps covers legacy events too; range reads
use a separate read-only SQLite connection in a worker, outside the control event loop.
Creating this index can take time on the first startup with a large existing archive.

Compact rows use alternating/direct current symbols for AC/DC solar. From4.4.14 grid
import and ESS AC charge use a right arrow (→); grid export and ESS AC discharge use a
left arrow (←), consistently in shared native and standalone live summaries.
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

ARCH-011 was introduced in4.3.9. From4.6.0, EV-A002 replaces the
horizontal line with red long-dashed recorded monthly-peak history. The Current
month peak label still identifies today's mapped input, independently of the viewed
historical range. The scale includes the visible history and current value. Zero
is valid; missing history stays blank. No forecast, permission limit or billing
floor substitutes for recorded history. The legend and cursor identify the
15-minute-average grid-import billing peak separately from instantaneous power.

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
From4.4.12 displayed ESS AC power is positive for charging and negative for discharge:
apply the sign conversion only when rendering live cards, planned charts and recent/
archived chart measurements. Raw HA/configuration inputs, backend/API/archive values,
house/grid balance and optimizer/control signs remain positive for AC discharge. SoC
percentages and unsigned daily charge/discharge kWh totals are unchanged. From4.4.14 their
arrows point right for charging and left for discharge, matching grid import/export.
The ESS line remains AC converter exchange,
including DC inversion, not net battery-port power; direct DC solar charging is separate.
The legend/live-power tooltip identifies that boundary. Solar accounting/routing changes
are outside this presentation-only release.

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
From4.4.13 normal optional planning first compares checked solar-allocation candidates.
A deterministic candidate routes otherwise unused DC via spare AC inverter capacity,
without altering batteries or other delivery. Idle converter/grid direction flags may be
released when no actual charge/import commits them. Bounded 24h neighborhoods cover the
full horizon, prioritizing the immediate window when time is short. They free solar/ESS
routing and normal EV capture within the window while preserving earlier EV delivery,
achieved readiness, future ESS stocks/dispatch and each interval's import upper bounds.
Later required grid EV delivery may shrink when captured solar makes it unnecessary.
These restrictions define additional candidates only; the normal joint search stays free.
Every replacement must pass original model rows/bounds/integers and independent physical,
source, permission and rolling checks, then the existing economic/continuity selector.
There is no hard EV-first override, full-ESS duration penalty or stored-energy export.

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

### Measured peak alerts and graph history (EV-A002, 4.6.0)

Send a mobile alert as soon as the meter reports a new billable monthly peak,
including when household demand alone caused it. Compare the recorded 15-minute
monthly peak with the prior billable baseline for the same month, including the
2.5 kW billing floor. Send one immediate alert for the first increase in an
episode, including after a billing-month reset. Each further billable increase
within 15 minutes of the preceding one belongs to the same episode and stays
silent. After 15 minutes without another increase, the next increase starts a
new episode. Closing an episode sends no final-value update. Advance approval
for a planned peak increase remains a separate interaction.

On the Overview power graph, show the history of the mapped monthly peak sensor
as a step series. Each recorded value applies at its timestamp and until the next
recorded change. Show rises and billing-month resets in their historical positions.
Use the recorded sensor value for the series, independently of the 2.5 kW alert
floor. Leave unavailable history as a gap. Keep the quarter-hour peak labelled
separately from instantaneous grid power and planned limits.

EV-A002 completion requires fake mobile delivery and archive-backed graph tests.
Detect the measured increase without waiting for an optimization result. Persist
the last observed month, peak and episode state so repeated reads and restarts
retain notification deduplication. Keep failed delivery retryable through the
existing notification mechanism. Start a new billing month against its own floor.
Verify increases below the floor, the first billable rise, rapid successive rises,
a rise after 15 quiet minutes, a month reset and missing historical values. The
graph uses recorded monthly-peak values from the existing measurement history.
The first valid observation initializes a new installation's baseline. A restored
baseline can detect a rise that occurred while the application was offline.

Implemented in4.6.0 after integration with4.5.8 on 8 November2026. The input poll records a sensor-specific partial measurement
in the existing archive even when another input prevents a complete observation.
An independent notification task retries persisted pending notices through the
existing destination/deduplication mechanism. No planner result is required. A
same-month transient sensor decrease does not lower the billable alert baseline.
Demo mode cannot generate measured-peak alerts or installation history.
The bounded graph projection preserves exact peak-change timestamps instead of
power extrema. If a bucket has too many transitions for its point budget, it is
blank rather than moving or inventing steps; zooming in recovers finer detail.


## Continuity, control and publication

### Peak graph forecast and current-quarter display (EV-A006, 4.6.3)

The user requests a future predicted peak on the Overview power graph as well as
recorded history, clearer separation from grid power, and a visualization of the
current quarter-hour demand. This is a follow-up to EV-A002; the user authorized
implementation and release on 8 November2026. Before4.6.3, the monthly-peak series had recorded points only.
The planned grid-power series can fall and resembles the red dashed peak series;
the reported screenshot does not by itself establish a falling measured peak.

Show the monthly peak expected under the accepted plan,
starting from the actual recorded monthly peak and rising only when a forecast
quarter-average import exceeds it. Use the measured imported-energy prefix plus
planned remaining imports for the active quarter, not instantaneous grid power.
Keep recorded history and prediction distinct. Grid power and the peak retain the
same red colour. Use a dotted, slightly heavier peak line and lighter normal power
lines. Retain the existing monthly-peak label rather than moving it onto the line.
Use the now boundary and observed/forecast styling and readout to distinguish the
recorded and predicted sections while retaining the dotted peak treatment. A
permission limit remains a different quantity. Billing-month boundaries,
missing inputs and absent plans must be explicit rather than inventing history.

Show the current quarter's mapped meter value in the existing Grid number box,
immediately after the monthly peak on the same bottom row. Preserve the current
monthly-peak icon/value position; place the new indication to its right, as marked
in the user's screenshot. Identify it separately from instantaneous grid power and
the monthly maximum. The user rejected a separate panel beside the graph. The mapped
meter builds up from zero using the fixed 0.25-hour denominator; it is not an
elapsed-time average. Shade consecutive quarter-hour intervals in subtly alternating
background tints, aligned to installation-local clock quarters. Visually distinguish
the current quarter from those bands. Keep power traces, cursor and labels readable.
Show a simple marker at the current quarter's end for its projected final average,
with measured contribution, projection and time remaining available in the graph
readout. Keep that projection distinct from the measured value in the Grid box.
These display changes do not change control policy.

EV-A006 is authorized for implementation and release. Completion requires desktop/mobile
and native/standalone verification of the preserved monthly-peak position, new
quarter value, line styles, existing label, alternating quarter bands and current-
quarter marker. Cover valid zero and missing/stale inputs, quarter transitions,
historical ranges, zoom/pan, month reset, no usable plan and quarter-energy prefix
plus partial planned intervals. A predicted monthly peak must not follow declining
instantaneous grid power; measured history remains recorded data. Verify that the
forecast does not imply approval and that the changes leave execution and peak
notification policy unchanged.

Implemented4.6.3: `LiveInputs.view` exposes the independently read normalized
quarter energy and its read time/issue as display metadata. The Grid value is
`energy_kwh / 0.25 * 1000` watts; a valid zero remains zero. Old-quarter, failed or
watchdog-expired reads are unavailable, even if an older control observation remains.
The compact accepted-plan response includes its forecast timestamp for display expiry.

`peak-display.js` integrates gross planned imports (`grid_house + grid_ev + grid_store`)
from the meter read time to the active quarter end, clipping every partial interval.
Exports do not subtract from imported energy. It divides the measured-plus-remaining
energy by0.25h. Full later quarters use their planned import totals. The forecast starts
at the current recorded monthly value, takes a running maximum within each installation-
local month and resets its predicted baseline to zero at the next local month boundary.
Only covered full quarters are predicted; missing inputs, revoked/expired plans or
coverage gaps do not acquire invented values. The independent historical series stays
unchanged. This model supplies display only and does not alter fast-control projection,
permission, notification or optimizer policy.

Recorded and predicted peaks use the same red dotted2.5px line, with faded prediction
after Now; ordinary power traces are1.2px observed/0.9px planned. The existing label
and monthly-peak history action stay in place. A clock symbol identifies the adjacent
quarter meter. Clock-aligned quarter bands and a highlighted active band follow the
visible range, with a hollow red quarter-end projection marker. The4.6.3 cursor
exposed quarter contribution/time prose; EV-A007 below replaces that presentation while preserving the forecast calculation.

### Peak display refinement (EV-A007, 4.6.4)

The user selected Long dashes after reviewing alternatives to the4.6.3 dotted
peak. Implemented in4.6.4 as17px/9px long dashes at3px. Peak and grid power retain
the same red colour, existing monthly label and forecast semantics. Normal power
remains1.2/.9px and the planned peak remains faded. Alternating quarter shading,
current-quarter emphasis and the quarter-end projection marker are preserved.

Keep the quarter value in its approved Grid-box position. Replace its plain clock
character with a red icon consistent with the other Grid readings. In native HA,
make the icon/value a standard more-info/history action on the configured
`quarter_import_kwh` input entity (the actual quarter-demand sensor, in its native
units), not the converted display value or a fabricated sensor. Retain a meaningful
accessible name and missing-mapping handling, and do not imply a native HA history
action in standalone/demo where it cannot be opened.

Remove the verbose quarter explanation appended to the cursor popup: interval
dates, conversion formula, contribution prose, meter-read timestamp and countdown.
Retain the compact actual/planned values and visual quarter marker. The requested
dashboard-wide minimal-text and genuine HA-source actions are specified above.
The user authorized EV-A007 implementation and release on 8 November2026 by
instructing the architecture chat to hand the settled package over.

Implemented and verified offline in4.6.4. Acceptance checks cover the
selected long dashes and increased weight, preserved shading/label/value placement,
compact cursor without the quarter prose, and red quarter icon plus actual mapped
HA sensor action. Review applicable measured dashboard values/states for genuine
entity or contributing-source history actions under the dashboard-wide contract.
Verify keyboard/touch, native/standalone, missing mappings and desktop/mobile
layouts without inventing HA entities or changing control/notification policy.

The read-only dashboard manifest provides genuine household/grid contributor
groups for the configured measurement mode. Individual live/daily readings,
actual graph-cursor cells, Bosch feedback and captured recording/profile sources
use their configured entity IDs. Composite readings retain a source chooser.
Standalone, demo and missing mappings remain noninteractive with a concise
availability hint. Predicted cells and configured controller values are not
measured-entity actions. The quarter action opens the actual input entity in
HA native units, independent of its normalized dashboard display.

### Charging bounce and progress source (EV-A008, 4.6.6)

For the4.6.3 charging-bounce follow-up, use the actual configured go-e cumulative
Total energy (`eto`) sensor as the primary delivered-energy measurement. The user
confirms both sensors are available and selected total energy after clarifying
that either counter needs a progress baseline. This supersedes the earlier session-
counter preference. Ordinary disconnection/reconnection must not reset the baseline
or re-credit delivered energy. Use counter differences rather than integrating power.
Normalize declared Wh/kWh units. Retain a reference identifying the energy already
included in the SoC/progress baseline, so later readings credit only additional
delivery. Recalculation must preserve that progress. A counter reset starts a new
measurement segment; it does not itself fulfill or cancel an EV requirement.
Battery gain remains an estimate using the configured efficiency. Persist the
baseline and credited task progress across application restarts as well as replans.
Reconcile genuinely new vehicle SoC information against the appropriate counter
reference, crediting subsequent delivery once. Re-reading an unchanged old SoC from
HA must not reset progress. Preserve the distinction between HA read/report time
and the vehicle measurement time; never invent precise timing that is unavailable.

On a temporary missing counter reading, preserve the last valid reference. A later
continuous cumulative reading can recover delivery during the gap. On a counter
reset or source change, preserve credited progress and begin a new measurement
segment; energy spanning an unexplained discontinuity remains uncertain. Do not
turn a negative counter difference into negative charging or credit a reset as
delivery. A steady counter while charging is stopped is valid.

The user confirmed the missing-progress fallback on9November2026: use a genuinely
fresh vehicle SoC if available. If neither usable charger-energy progress nor fresh
vehicle SoC is available, pause EV charging after the existing measurement watchdog
expires, retain the task/progress and show a concise warning. ESS remains independent.
Resume eligible task execution under existing source, peak, authority and charger
guards once progress is usable again. These rules do not override charger incidents.

The user requested root-cause analysis before choosing a phase-stability preference.
The captured replacement demonstrates an incorrect execution-commitment assumption:
snapshot construction fixes the current command/observed phase for135seconds, while
the previous accepted plan continues executing. By new-plan admission the charger
has changed from3to1phase, but34.55seconds of the new plan's fixed3-phase prefix
remain. Adoption requests3phase and its following instruction requests1phase again.
The model's phase-change terms score transitions without representing the actual
stop/acknowledgement/restart energy gap. Its on/off continuity check sees nonzero
charging on both sides, so active continuation review is not applicable; the coherent
single-phase alternative is skipped because of the held3-phase prefix. This is
confirmed for the supplied replacement, not every preceding screenshot gap.

EV-A008 corrects those mechanisms:

- Execution commitments used by a new snapshot must reflect the remaining accepted
  instructions, actual acknowledged state and pending charger transitions. Do not
  assume that the command seen at calculation start remains constant for the entire
  calculation allowance while the old schedule continues executing. Preserve ordinary
  execution and independent live protection during recalculation.
- A replacement must not force a return to an obsolete phase solely to satisfy its
  calculation-time prefix. Handle departures from a predicted execution commitment
  through explicit live/admission sequencing within current authority. Preserve
  immutable calculation inputs/results and independent validation; do not introduce
  publication-time economic repair or reject a valid plan merely for a changed SoC.
- Represent phase transition stop, acknowledgement and restart waits in executable
  charging time, delivered energy and deadline comparisons. Existing go-e guards
  remain in force. Continuity assessment must count the physical interruption of a
  phase change even when both adjacent planned power values are nonzero. Cover the
  held/partial interval and coherent-candidate paths, not just a final score penalty.
- Use persistent go-e total-energy progress in subsequent planning inputs and fast
  task execution. A new plan ID must not restart the same unmet requirement's energy
  allowance. Carry relevant progress when a requirement changes without inventing
  new authority. Keep reported vehicle SoC, counter-derived estimated gain and their
  source/timing evidence distinguishable; original archived snapshots remain intact.
- Provide a selectable actual HA total-energy sensor accepting declared Wh/kWh.
  Preserve ESS operation when that mapping/progress is unavailable. Unknown vehicle
  measurement timing cannot be replaced by an assumed HA polling timestamp. Where
  a new SoC cannot be aligned reliably, retain credited progress and explicit
  uncertainty; use the agreed watchdog fallback if neither progress source is usable.
  Preserve existing away/unknown-return, source, quantity, peak and fault guards.

No new minimum phase dwell, arbitrary phase lock, enlarged peak authority or increased
production solve budget is part of this package. A general preference for the current
phase remains unconfirmed and is not required to correct a hard obsolete commitment.
Routine representation, state-storage and solver choices belong to implementation
within these contracts; report a genuine uncovered policy conflict to the user.

EV-A008 was authorized for implementation and release on9November2026 after the
user reviewed the four-part scope and instructed “Ok, hand it off”. Acceptance coverage:

1. Replay the supplied replacement state and fake go-e sequencer. Remove the
   ineffective1→3→1 detour and its76s interruption while retaining permitted energy,
   deadlines and live peak protection. The prior export remains unchanged evidence.
2. Run a closed loop with repeated replans, counter increments and unchanged49% SoC.
   Verify that credited energy persists, the same top-up is not repeatedly purchased,
   and the active task finishes its authorized quantity. Include restarts, overlapping
   goals, revisions, rounding, ordinary reconnects and existing unknown-return guards.
3. Exercise real required phase changes as well as avoidable ones, including a
   transition spanning plan adoption, delayed/missing acknowledgements, fractional
   slots, a near deadline, unexpected house load and a constrained ESS. Requested
   transitions must have feasible post-wait delivery; retain all existing stop waits.
4. Verify Wh/kWh, genuine new SoC reconciliation, repeated old SoC reads, unavailable
   timing, temporary counter gaps, counter/source resets, valid stationary readings,
   fresh-SoC fallback, watchdog pause and guarded recovery. Credit each measured
   increment once; do not invent energy across an unexplained discontinuity.
5. Retain independent physical/source/economic audits and test varied grid/PV/travel
   and held/partial scenarios under the existing seven-day/five-minute/120s limits.
   Measure model/runtime changes rather than assuming new transition detail is free.
   Verify native/standalone sensor mapping and concise progress/availability display.
   Existing release checks remain required. The separately reported routed-fixture
   timeout is not permission to relax acceptance or expand planner behavior.

Implementation contracts in4.6.6:

- Optional `Observation.ev_progress` retains reported stock, actual vehicle sample
  time, counter read/source, estimated stock, credited gain, uncertainty and validity.
  The persistent ledger is independent of plan/goal IDs. A stationary stopped counter
  is usable; measured charging without advancement expires the existing watchdog and
  remains blocked until real progress or a genuinely fresh vehicle sample recovers it.
  Unknown-return protection remains in force. The optional SoC sensor attribute
  `vehicle_observed_at` must be an actual vehicle sample time; absent timing is unknown.
- A frozen `Snapshot.execution` records actual/pending charger state and segmented
  accepted instructions, capped to their remaining task quantity. Legacy snapshots
  omit this field and retain their original digest and arithmetic. A separate admitted
  `execution_handover` continues the valid prior source through the frozen boundary,
  intersecting current EV/ESS/conditional authority. It never repairs frozen flows.
  Instruction hashes distinguish changed work from a publication-ID-only change;
  the active absolute energy endpoint persists through restart and source pauses.
- Requested integer current is distinct from average delivered power during waits.
  A future phase switch reserves130s: stop acknowledgement30s, preparation10s,
  selector acknowledgement30s, restart hold30s and start acknowledgement30s; current
  confirmation overlaps the hold. These are conservative existing protocol allowances,
  not measured installation latency. Same-phase restarts retain the remaining30s
  restart hold. Waits cross partial intervals; joint source/converter/battery limits
  constrain instantaneous delivery as well as average energy. An independent audit
  reconstructs the timeline. Continuity counts physical phase interruptions.
- Admission suppresses only an ineffective immediate-return phase prefix shorter
  than the mandatory40s physical preparation/restart. It adds no phase preference or
  dwell. Zero-energy phase preparation keeps force-off; a submitted selector write
  remains pending until fresh acknowledgement or fault. Live peak/source/permission
  and charger guards still determine actual charging. The counter determines actual
  progress even when real acknowledgements complete earlier than the model reserve.

The original hour's complete incident attribution remains limited by missing prior
decisions/command history; synthetic regressions do not become installation evidence.
Implemented in4.6.6 and verified offline; see VERIFICATION.md for results and limits.
No live installation action is included.

### Live peak protection priority (EV-A004, 4.6.1)

When an unexpected load change threatens the authorized quarter-hour peak, first
reduce EV charging by the amount needed and pause it if reduction is insufficient.
If the projected peak still exceeds the limit with EV charging paused, use
available ESS discharge within physical and safety limits. The current quarter
takes priority over a later forecast peak, so use energy reserved for that later
peak as needed. Base these decisions on the projected quarter average, including
metered energy already imported. Issue the protective actions promptly if both
are needed.

Project remaining quarter consumption using fresh measured load and actual EV/ESS
response, the measured P1 prefix and the time left. Account for sustained demand
above forecast, battery discharge availability and actuator response delay. A
forecast load decrease or an unconfirmed reduction command cannot by itself fund
extra charging headroom. These protections apply during recalculation as well.
Reduce current without a stop when the supported range permits. Pause when the
necessary reduction is below minimum charging power. Ordinary source, permission,
freshness, fault and generation guards remain authoritative.

EV-A004 completion requires deterministic offline cases with exact quarter energy
and fake actuator feedback. Cover sustained unexpected load with empty ESS, usable
ESS with a future-peak reserve, a spike near quarter end, delayed EV reduction,
meter-read delays, quarter reset and a legitimate permitted short pulse. Check
that controlled charging adds no avoidable excess when physical curtailment is
still possible. Attribute an unavoidable remainder explicitly when the household
alone exceeds the available grid and battery capacity. Verify 3,500 W automatic
permission, reuse of an incurred higher peak and approval for a higher proposed
limit. Link actual measured increases to EV-A002 notifications.

### Running EV sessions and replacement plans (EV-A003, 4.6.1)

Continue an active EV session while authorized charging work remains and live
source, peak and safety limits permit it. A measured state of charge ahead of
the forecast trajectory is irrelevant to the decision to interrupt charging.
Use the active task's authorized target or quantity, source scope and live guards
to decide when to stop. A later unrelated requirement does not extend that task's
authority.

A materially better plan may interrupt an active EV session. If a replacement
would stop an active session and restart it within 15 minutes, check whether
continued charging, including at a lower permitted current, can achieve the same
required outcome within the applicable limits. Prefer that continuation when it
can. Live protection may still pause immediately. Preserve the established
preference to deliver required grid charging earlier when waiting offers no
real benefit. Revisit how to express that preference under ARCH-026.

Evaluate continuation alternatives inside the frozen-snapshot planning process.
Keep the original admission checks and independent live control. The replacement
comparison uses the same required outcomes, optional benefit, shared financial
allowance and source/peak constraints. A valid checked continuation remains a
candidate on timeout. Report an unfinished comparison accurately.

EV-A003 completion requires the reproduced SoC-step case to continue charging
below its task target, plus stops at the task target, source loss, a genuine peak
threat and revoked authority. Verify an unchanged command throughout a full
recalculation, continuation through an equivalent replacement, the 15-minute
stop/restart alternative and a justified PV-related interruption. Exercise active
holds and partial slots with fake charger acknowledgements and existing restart
timers. Archive the stop reason and plan identity so execution gaps can be traced.

### EV planning candidates and deadline safeguard (EV-A005 / ARCH-026, 4.6.1)

For the next required EV deadline, the initial search should consider all usable
forecast PV windows before that deadline while the EV is expected to be connected.
Exclude known away or unplugged periods from the EV charging choices. Current
models already forbid charging in unavailable intervals. Evaluate omitting the
fixed EV charging choices from model construction while retaining battery energy
accounting, trip withdrawals and household and ESS decisions for those intervals.
Useful partial PV charging can justify a split between solar and necessary grid
charging. Use the full PV forecast for economic planning. Check deadline feasibility
with a 20% margin on the remaining usable PV. Waiting for solar is permitted while
enough charging capacity remains under the authorized peak and availability limits
to meet that cautious requirement. Bring required grid charging forward before
further waiting would make the cautious requirement infeasible. Use a continuous
session where feasible. When useful PV is absent, retain early required charging.

For deadline protection, apply the user's chosen 20% margin to the remaining
usable PV forecast. Credit 80% of the PV opportunity before the deadline while
the EV is available. Measured energy already delivered receives full credit.
Identify earlier grid charging justified by this safeguard against the cautious
feasibility calculation. Forecast economics continue to use the full PV forecast.
The physical and source audits must retain the distinction between the forecast
trajectory and the deadline safeguard when checking minimum necessary grid energy.

Produce a feasible fallback certificate for the next known requirement using the
cautious PV opportunity, supported currents/phases, home availability, held
commands, quarter import already consumed and authorized peak limits. Retain
intermediate deadlines and trip withdrawals. Known stored energy receives its
ordinary source-specific credit. Future PV is credited only when physically usable
before the deadline, after conversion losses and competing protected allocations.
Apply the 20% margin to that future usable opportunity. A total daily generation
estimate alone cannot establish feasibility. Store the fallback's activation and
required-progress conditions with the accepted task so live control can use them
within that task's authority. No optimizer is run in the fast loop.

Each nominal and cautious candidate must pass physical and source checks using its
own forecast context. Extra grid remains bounded by actual required charging in
that candidate's source ledger. Preserve the existing causal-deficit check against
the allocated sources. Nominal economics use the full forecast, including the
allocation of any PV beyond the fallback's needs. Keep the two forecast contexts
and their evidence inspectable.

If the normal forecast can meet a deadline within the permitted peak but the
20% cautious case cannot, retain that peak limit and warn that the margin cannot
be met. Send one mobile notice and show a persistent in-app warning for the
affected goal/deadline while unresolved. Forecast refreshes and solver IDs do not
repeat the notice. Clear the warning when the margin is restored or the goal is
fulfilled or removed. A nominal shortfall retains the existing best-effort and
peak-approval process. A timeout is an unverified assessment, not an infeasibility
proof. Preserve any valid fallback already obtained.

Offer coherent charging candidates before the main optional search using the
planner's newly generated reference. For a grid-only next requirement, first
offer a feasible early continuous single-phase session where supported. Handle
held commands, fractional boundary intervals and exact delivered energy. A short
optional pass may keep that checked session fixed while all source and ESS
dispatch remains joint. Then allow the wider search and compare all retained
valid candidates using one shared economic/cash reference. Avoid rebasing the
allowance between attempts. A restriction that cannot supply a checked candidate
must release its options within the same global budget. Preserve useful PV splits.

Explore deriving EV energy bounds backward from deadlines, using the maximum
charge that can still be delivered while available. Also explore tighter current
and source bounds from physical capabilities, authorized quarter-hour import and
measured import already used in the first quarter. Bounds used to rule out a
choice must preserve every feasible outcome under the existing rules. Forecast
preferences can narrow an initial search and need an explicit widening path.

EV-A005 completion requires fresh snapshot replays covering grid-only
and mixed PV/grid requirements, trips, an active hold and partial slots. Verify
that waiting respects the cautious deadline, earlier grid charging has a recorded
justification, and a wider search retains a checked usable plan on timeout. Compare
continuity at equal delivered EV energy as well as the value of extra optional PV.
Use the existing seven-day, five-minute and 120-second limits and the shared cost
allowance. The implementation selects stage time shares from measured results.
Retain raw statuses, scope and unresolved search diagnostics. Use paired baselines
and report energy, cost, peak and starts together. The earlier matched-energy
comparison and its rejected rolling-cost candidate remain regressions. The
synthetic deadline-certificate study covers spare and tight post-PV capacity,
travel, no PV, held partial slots, known stored solar, physical infeasibility and
a margin-only shortfall. Complete this contract before replacing production stages.

Implementation contracts (4.6.1):

- `LivePeak` retains the greater of the valid P1 prefix and conservative measured
  integration, sustains measured household demand and credits confirmed ESS response.
  Unconfirmed EV reductions reserve the measurement-watchdog plus control-period
  allowance through the next-quarter tail. This is an engineering projection, not
  measured installation latency. EV cuts precede physical ESS support, including
  future-peak reserves. Command evidence identifies the task, plan and unavoidable remainder.
- `FastControl` retains the contiguous task endpoint, source and own deadline when
  physical response leaves energy undelivered. Later goals cannot extend its quantity.
  Forecast progress cannot pause it. Frozen replacement review tests a continued
  supported phase at equal boundary energy within the carried cash/economic allowance.
- `charging_candidates` offers a bounded phase-one grid reference before unrestricted
  optional search. Source/ESS choices stay joint; useful PV and travel retain wider
  choices. Backward stock floors use physical available capacity and withdrawals;
  relaxed-service diagnostics are excluded. Dense unavailable-slot indexing remains:
  explicit fixing produced identical presolved counts and no demonstrated gain.
- `deadline_guard` adds an explicit cautious source context. Separately conserved
  protected future household stock starts at zero, serves required household service
  and binding reserves, and cannot supply EV. Remaining future AC/DC PV receives80%
  credit once before conversion/storage. Initial known stock retains ordinary credit.
  Independent physical/source/causal audits check each candidate in its own context.
  Restricted prefix witnesses preserve later required stock and accepted appliance
  timing; only full joint infeasibility establishes a margin-only shortfall. A feasible
  alternative needing different accepted appliance timing remains unverified for execution.
  No-PV cases retain the checked nominal schedule.
- Bounded latest-start searches retain audited incumbents on timeout. Certificates
  store activation, progress, scope and reservations. `DeadlineExecution` uses measured
  progress without optimization or added authority; first activation requests one
  ordinary replan. Prior certified fallback survives an unverified refresh only with
  matching goal/capabilities/policy/appliance, fresh forecast and repeated audit.
- `DeadlineWarnings` persists proved margin failures and deduplicates delivery per
  goal/deadline/destination across refreshes/restarts, retries failures and clears
  restored, fulfilled or removed requirements. The shared warning shows the retained
  limit and notification state without an approval button. Nominal shortfalls retain
  existing approvals. Active-continuation and cautious-certificate time are reserved
  within the global120s budget; raw attempts and unresolved scope stay inspectable.

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

### Planned power in task details (4.5.1)

EV and ESS session dialogs show the frozen accepted interval powers as step curves,
clipped to the session bounds, including variable levels, valid zero-power pauses and
partial boundary intervals. EV uses AC input (PV + grid + solar ESS), distinct from
battery energy after losses. ESS uses the same AC display boundary as Overview:
AC charging minus AC discharge/inverter supply, positive charge and negative supply.
Direct DC solar charging is a separate series; it is never silently added to AC power.
The existing ESS energy label distinguishes energy to/from its battery.

Requirement details and the saved-goal editor show the shared EV power plan from the
calculation start through that saved deadline (bounded to the available horizon). They
do not derive a fictitious per-goal power allocation from session energy contributions.
The editor explicitly labels the saved requirement; unsaved edits have no new plan yet.
Require matching plan/goal revisions and current EV validity, or the existing matching
restored-plan identity/revision. Expired/outdated/missing profiles show an unavailable
message. Missing interval powers remain gaps, never interpolated or replaced with zero
or session-average power. Real zero-power plan intervals remain visible.

Charts use W and the installation timezone, with UTC offsets for repeated local hours.
A compact expandable Power levels table exposes exact interval boundaries and W values;
only equal adjacent complete levels merge. The shared native/standalone module is part
of the existing versioned session-details asset. No scheduling, control, source accounting
or appliance-task implementation is introduced by this display feature.

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
candidate schedules. From4.4.13 a warm candidate that passes all current model rows,
bounds and integrality is retained if a timed solve returns none or a worse objective;
normal final independent audits still gate publication. Raw solver status/bounds/gaps
remain in stages, with retained_starting_candidate identifying this fallback separately.
Its feasibility does not establish global optimality.
From4.3.11 seed grid allowances reset by installation-local billing month, matching
the model: current-month incurred peak is never permission in a later month. Every
seed still passes row/bound checks before HiGHS and every published trajectory passes
the independent validator. If the initial required-reference stage reaches its time
limit without a feasible candidate, one recovery solve on the same model/objective
uses the remaining global wall budget less2s reserved for validation (only when more
than2s remain), retaining
the checked warm start if available. No infeasibility claim, new permission, reduced
horizon or relaxed constraint follows from timeout. From4.4.13 solar refinement runs
before the normal optional search. In4.4.17 the initial allocation pass uses up to8s,
with up to6s (10% of remaining time) reserved for final solar allocation. After a feasible
required reference exists, reserve up to6s (6% of remaining time) for final continuity;
use up to24s/85% of what remains at that stage, after solar allocation/required timing
and before source certification. The economic stages retain their80% economic/20%
joint-continuity split. Within that operational share, use35% for the same window
procedure before an unrestricted joint search. The fast dispatch candidate avoids
repeated costly integer presolve; no extra upfront reserve starves economic/solar search.
Share time across pending fragmented windows, then revisit unfinished work once with
time saved by easier windows. Keep the original partition and accepted bounds across
both sweeps. Construction/audits count against
the existing global deadline. Reserve measured solver overrun as well as audit time;
an exhausted stage does not launch a nominally tiny solve, because presolve can cost
seconds. Requested bounds still apply before retaining a checked warm fallback. Raw
status stays time-limited and records skipped_budget. No reserve takes priority over finding the first feasible
required schedule. Exceptional100% probes use the unreserved remainder. A short budget
retains valid work and records unfinished review, without claiming unavoidable gaps.

Decision history lists status/reason/elapsed time for rejected attempts independently
of the last accepted plan's evidence. Its detail includes validity, all stages and
failure reason. A same-origin authenticated download of `GET /api/decisions/{id}?download=1`
returns full snapshot/result/digest/disposition with no-store attachment headers.
Download server JSON directly to preserve float representation/checksums; native HA
uses its discovered ingress base. Frozen CLI replay validates the exported top-level
digest as well as legacy result.input_digest. No full snapshot is added to state polls
or decision-list responses; opening/exporting a decision performs no hardware action.
Main economic stages use80% of their allowance to establish an economic reference
and20% for unrestricted joint continuity. ESS dispatch and source allocation remain
decisions; an arbitrary ESS incumbent cannot force EV gaps. Achieved required readiness
and selected EV quantity are preserved. From4.4.16 one general window procedure replaces
the next-work-only
single-session fallback. Partition every interval of the full horizon at local midnight
and availability changes, including empty/unavailable windows; merge midnight boundaries
crossed by an existing active session. Apply the same procedure on every forecast day
and at every inherited limit, including fulfilled/absent named goals. Each fragmented
window first offers compact integer-current alternatives:
keep irregular slots and group regular-slot ampere-hours from the first charging work.
Also try consolidation into the existing longest run, so a small earlier solar burst
need not anchor the whole session. From4.4.17 a fixed EV profile also fixes derived
start/phase/variation markers, removing redundant integer choices. First try a bounded
linear relaxation (up to2s/80% of the window share) with every source/ESS allocation
free. Restore only unpriced source-direction indicators from the actual powers and
canonical witness/permission bookkeeping. Change no physical flow or energy stock.
Accept only if the complete original integer candidate, original selected model,
cost/cash bounds and independent/rolling audits all pass. Fractional or incompatible
physical dispatch is rejected, never repaired. The relaxation's Optimal status alone
proves no executable result or global EV optimality. An Infeasible relaxation rules
out only that identical fixed profile, so skip its redundant integer solve and try the
next profile. A rejected relaxed point can seed the matching full integer solve;
this fixes no source choice and grants no authority. Only a newly model/audit-checked
integer result can replace the plan. Otherwise, if needed, retain the full integer compact search (up to6s/80% remaining window share), then wider alternatives. It is only a
checked candidate, never a forced schedule. Then try a fixed-phase one-session alternative
using65% of the remaining share.
If that fails, spend the remaining share minimizing transitions with flexible phase and
session count. Preserve exact selected energy even when an irregular departure interval
forces a separate tail; failure to reach one session must not prevent reducing many
avoidable gaps to a few sessions. Original phase/current/hold,
availability, health ceilings, required/exceptional authority, sources and permissions
remain hard. The unrestricted joint search remains available for pauses/phase changes.

Before final solar/continuity review, a bounded economic candidate (up to8s/half the
unreserved remainder) fixes the selected EV modes/current across the full horizon and
refines sources/ESS in the original joint model. This supplies an economical incumbent;
its temporary EV fixes stay in its copied model. Its Optimal status describes that
fixed-EV subproblem. Independent/model/rolling checks still gate adoption.

From4.4.17 the continuity candidate fixes only EV modes/current outside its target
window and the window's EV energy boundaries. The original ledger determines the
surrounding EV stocks; other EV sessions and selected quantity stay intact. Source
routing and ESS dispatch/inventories remain free across the entire horizon under the
original model. Measured initial stocks, source provenance, household balance, converter/
battery limits, availability, holds, phases, health ceilings, goals, peak permissions
and all original model rows remain hard. Preserve achieved required deadline/margin
readiness up to its target, including achieved parts of a shortfall; surplus can move.

Do not impose incumbent ESS stock values at midnight, freeze later source dispatch,
cap each window's imports to its incumbent, or add incumbent-monthly-peak ceilings.
Those choices are not requirements and can exclude continuous charging over tiny AC/DC
conversion-loss differences. Household imports may change when original source, peak,
economic/cash and independent rolling checks permit it. The shared0.02EUR envelope
covers the whole review and all retries, not individual windows. Preserve the established
required-grid timing preference and accepted per-window count/score improvements.
Compact fixed-current candidates minimize source economics because their physical EV
continuity score is already determined; broader candidates minimize operational score.
All work uses the same frozen snapshot and existing global budget; unfinished refinement
retains the valid selected plan. No runtime economic recheck or reschedule change.

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
not monetary wear charges. Each full-horizon sweep uses one carried0.02EUR comparison/
cash envelope shared across all windows, not per day. Repeated calls cannot rebase the
reference upward. Replacements pass narrow/original model rows/bounds/integers and
independent physical/source/permission/rolling audits. Later window work cannot worsen
previous window session counts or transition scores. Final source certification preserves
those per-window bounds and required-grid timing, plus overall score/economics; full
certificate-model checks precede adoption, so it cannot undo checked improvements.

Archive `continuity_review`: interval count, full ordered window coverage, before/after/
final session counts and every attempt's kind/phase/raw status/time. `coverage_complete`
means all intervals were accounted for; `unresolved_windows` counts unfinished windows.
`complete` is true only when that count is zero. A single valid fixed-phase session
resolves its window even if found in a timed solve. Otherwise a valid broad flexible
Optimal attempt on the current surrounding-plan revision establishes only bounded
completion (`no_improvement_found`), never global inevitability of gaps. Attempts carry
basis/result revisions so later EV changes cannot make an old proof appear current.

A failed packed/consolidated/single shortcut must not erase a broad timeout. Residual
timeouts/rejections, untried broader work and stale results remain unresolved. Preserve
raw timeout history in `had_timeouts`, and `improvement_retained` when a useful partial
improvement survives unfinished work. `candidate_infeasible` describes bounded failed
candidates, not a required pause; it alone does not complete the review. Rejections retain
bounded model/audit reasons. These diagnostics do not invalidate an executable plan or
create user warnings/notifications. Economic/operational optimality remains separately
scoped; live control is independent.

Selector auxiliary rows are added to operational searches and
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
See [SETTINGS.md](SETTINGS.md) for upgrade and control-state behavior. Local demo starts also initialize a missing file beside the database.
The add-on's app configuration mount is writable for initialization and editing. Only
amd64 packaging is declared. Deferred PV/storage expansion, market pricing, V2G, appliances, automatic
travel/external charging, learned policy, live deployment and historical retention
policy are outside this release. Live wiring, values and hardware timings remain
unverified and require the commissioning procedure in [RUNBOOK.md](RUNBOOK.md).


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
implemented behavior changes. Record decision context in [DECISIONS.md](DECISIONS.md)
and deferred ideas in [BACKLOG.md](BACKLOG.md). Update the existing
[runbook](RUNBOOK.md), [settings contract](SETTINGS.md) and
[forecasting reference](FORECASTING.md) where their details change. Preserve original
verification evidence; keep new results in [VERIFICATION.md](VERIFICATION.md) and
meaningful progress in [WORK_STATE.md](WORK_STATE.md). Do not maintain a separate
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
