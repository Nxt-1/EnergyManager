# Settings and hardware control

The HA app connects through the built-in Supervisor proxy automatically. Settings no
longer contains connection addresses, token-variable names, network permission choices,
a forecast URL or a notification webhook. The Commissioning group is removed.

## Configure the installation

Open EnergyManager Settings. Missing entity selections, generated placeholder IDs,
unavailable values, incompatible units and blank required numbers are highlighted
immediately. Zero remains a valid value where the field allows it. Entity subtitles
show the selected ID, state and unit; the explanatory paragraphs are removed.
You can clear an entity selection with its × button. A missing optional notification
destination is allowed. Other incomplete values cannot grant hardware authority.

Save keeps the same JSON configuration file, with an original-byte backup and conflict
checking. Installation changes apply after restart. Existing mappings, numbers and
unrelated/future fields are preserved. On an explicit save, retired commissioning,
webhook and forecast fields are removed; obsolete HA connection fields are removed
for the installed HA app. Reading or starting the app does not rewrite the file.

Incomplete physical settings keep the editor available. They do not produce a plan
or enable an actuator. Overview values are read independently: available values remain
visible when another input fails. Cached values carry a watchdog warning if HA reads stop;
unavailable values show dashes, and available solar components remain visible in the
subtitle. Actual charts use complete measured observations. Input errors name the entity
and failed check. The hardware switch still requires valid critical measurements.

The HA app's own Configuration tab still selects `demo` or `configured`. Demo mode
cannot operate hardware. Choose `configured` and restart to use installation inputs.

## EV charging supervision (4.3.2)

From4.3.13 the old Minimum phase dwell setting is removed. Its default was600seconds
(10minutes); existing JSON values are accepted but ignored. Automatic restarts instead
wait30seconds after a phase acknowledgement or confirmed stopped/low-power state.
Time already spent stopped counts. Current-only adjustments have no stop or hold.
No new setting or mapping is needed; the15minute persistent-wait alarm is separate.

After updating, select these go-e APIv2 Connect entities under EV fault recovery:

| Field | go-e entity | Typical suffix before HA renaming |
|---|---|---|
| Car state [CODE] | Numeric car state | `car` |
| Status [CODE] | Numeric charging-logic status | `modelstatus` |
| Error [CODE] | Numeric error;0 means none | `err` |
| Last Status change age | Age in **seconds** | `lmsc_delta` |

The three raw [CODE] sensors may need enabling in HA's device entity list; integration
2026.10.3 disables them by default. Do not select their translated text counterparts
(`*_value`). The age sensor is enabled by default. **Time since boot** is unsuitable:
the integration rounds it to whole hours. Suffixes are guidance, never a hardcoded
device identity. Select your actual entities, save and restart.

These mappings gate EV control only. They remain optional for the overall settings so
ESS can operate while EV is paused. A status line explains what EV is waiting for.
Two advancing age readings establish freshness; repeated HA reads or entity change
timestamps alone do not prove fresh device data. The device/read watchdog is30seconds.
Planning uses the intersection of the current number's min/max and configured limits;
it never raises the configured maximum. Disjoint limits pause EV.

## EV fault recovery

In Settings → EV fault recovery, select the optional charger reboot **button**. This
opts into one automatic reboot after an eligible delivery fault; leave it blank to keep the EV
stopped and escalate immediately. No installation entity ID is built in. Select the
numeric EV/charger status/error entities above and optional charging permission.
Existing EV measurements and actuator states are collected without extra mappings.
Choose the destination under Phone notifications, then save and restart.

The90second watchdog starts only after current/force readback confirms the request and
go-e reports a charging state. Normal car waits, minimum pauses and phase transitions
do not trigger it. Persistent blocking escalates after15minutes; command readbacks
have30second deadlines and phase sequencing has a bounded deadline. These blocked or
failed-command cases never permit reboot. All nonzero errors, unknown values and stale
data also prohibit it. This does not prove a charger defect. Recovery requires
hardware control enabled and fresh connected
EV inputs. It stops charging, records the attempt before pressing the button, waits
60seconds and verifies actual charging through normal control. An unsuccessful attempt
leaves EV stopped and sends a timestamped alert through HA. There is no repeat reboot
for that incident, including after restart; a30minute cross-incident cooldown also applies.

Open Incident details & logs or EV → EV fault history for timestamps and a JSON export
from five minutes before detection through up to ten minutes after it. Optional raw
states are sampled every five seconds after installation/configuration; older missing
states cannot be recovered. After diagnosis, Acknowledge clears the latch only with
fresh connected inputs and requests a new plan. It does not reboot or force charging.
“Sent to Home Assistant” confirms HA accepted the alert, not delivery to the phone.
A continuing power draw after a normal stop or an unconfirmed hardware-off stop is
also escalated. Switching off never re-enables hardware for verification or recovery.

## EV calendars (4.3.0)

In Settings → EV calendars, add a label and iCalendar subscription link for each feed.
HTTPS and webcal links are accepted (webcal uses HTTPS); use the link without sentence
punctuation. Save and restart in configured mode. Demo mode does not fetch calendars.
Links stay in your installation JSON/backups, so keep those files private. No calendar
login, Google account or HA calendar entity is needed for this first integration.

At startup, every four hours or via EV → Subscribed calendars → Sync calendars, the app
imports the next90days of timed occurrences. The EV calendar shows its normal168-hour
window. Every imported event has provisional50km **total** distance and a four-hour
away period beginning at event start. These placeholders participate in the existing
shared charging plan; they are not measured distances or Google estimates. Location,
source and placeholder status appear in the agenda/details. Change imported items in
their original calendar; remove a link and restart to remove its managed journeys.

Changed events revise requirements and reset their old peak approval. Cancelled/deleted
events disappear after a successful refresh. Failed refreshes retain last-good items
with a warning and last-sync time; cached data is marked stale after eight hours.
All-day entries are skipped with a count because there is no departure time. Repeating
events, exceptions and timezones are supported; repetitions faster than daily are not.
Use at most20 distinct links. Google Maps distance/timing is a later, unreleased step.

## Power units

Power limits and entity-state previews are displayed in W. A 2.5 kW saved limit appears
as 2500 W; saving 3100 W writes 3.1 to the existing kW field. The capacity tariff is
displayed in EUR/W/month (a saved 4 EUR/kW/month appears as 0.004 EUR/W/month).
Energy, battery capacity and energy tariffs retain kWh units. These are display/input
conversions only: existing files need no migration, and unchanged numbers are preserved.

## One immediate hardware switch

Overview contains the only Hardware control switch. It applies immediately and saves
its requested state in the V4 SQLite database, without restarting or rewriting the
installation JSON. Planning and measurements continue while it is off.

On first upgrade to4.0.6 the new switch starts **off**. The old commissioning checkboxes
and JSON `policy.control_enabled` flag cannot enable it. Once explicitly enabled through
the new switch, later restarts wait for valid saved/runtime settings, mapped entities
and a recent validated HA input read before resuming. The switch can always revoke a pending
request. Settings that have been saved but not loaded still require their normal restart.

Enabling validates settings, checks entity availability/units and checks the last
validated input read against the HA read watchdog. A missing EV SoC or unknown phase reading can still pause EV independently
while fresh shared measurements permit ESS balancing. Existing planner permissions,
physical limits and conditional-purchase guards continue to apply.

Disabling revokes queued/in-flight ordinary writes, requests EV stop and clears the ESS
AC setpoint. The two stop operations are attempted independently; failure is reported
and never presented as a confirmed physical stop. If saving the off state fails, the
running controller still revokes authority and attempts the stop, and reports the
persistence failure. Restore storage/communication before relying on unattended restart.

## Phone notifications

The optional Phone notifications picker lists Home Assistant notify entities and
phone-specific notify actions, such as `notify.mobile_app_your_phone`. Select the device
by name or ID, save and restart. No webhook or manually copied credential is needed.

The stored `notification_target` is either null or an object with `id` and `kind`
(`entity` or `action`). Entity destinations use `notify.send_message` with an entity ID;
legacy phone actions use their own notify action. This supports both current
[HA notify entities](https://www.home-assistant.io/integrations/notify/) and
[Companion app phone actions](https://companion.home-assistant.io/docs/notifications/basic/).

From4.3.12, demonstrated EV/ESS peak permission requests and planning rejections that
persist after one automatic retry also use this destination. The attention item shows
whether HA accepted delivery, delivery is retrying, or only a local notice was recorded.
A rejection alone never creates an approval request or grants more peak allowance.

Existing informational peak-precharge notices use this destination. Material changes
are deduplicated, failed delivery remains retryable, and changing destinations does not
reuse an old destination's delivery record. Without a destination, notices remain in
local application evidence. Development delivery uses only local fake HA endpoints;
actual phone receipt and permissions remain unverified.

## Standalone tools and rollback

Outside the HA app, advanced tools can set `ENERGY_MANAGER_HA_URL`,
`ENERGY_MANAGER_HA_TOKEN` and `ENERGY_MANAGER_ALLOW_REMOTE` in their environment.
Legacy standalone connection settings remain readable for compatibility, outside the
GUI. Development fixtures use a local fake Supervisor resolver/token and fake services.

Before rollback, switch hardware control off and verify the physical stop/handover.
Keep the V4 database and configuration backups. Versions before4.0.6 do not use the new
SQLite switch key; they use the old JSON control/commissioning flags. Restore an
appropriately disabled earlier JSON backup and review those flags before starting an
earlier image. Automatic HA connection settings and phone notification destinations
also differ in earlier versions. No live deployment or rollback was performed here.


## HA availability and input-read watchdog (4.0.9)

Available HA states are accepted even when their values and report timestamps have not
changed for hours. There are no per-entity age limits or zero-value exceptions. HA is
responsible for marking devices/entities unavailable when device communication fails.
EnergyManager still rejects required unknown/unavailable states, failed reads, invalid
numbers/units and physically inconsistent values. A missing EV-only state can pause EV
independently while valid shared states continue to support ESS.

The Advanced setting HA input-read watchdog (seconds) defaults to 30 s. It retains the
existing JSON key policy.measurement_max_age_seconds, so no migration is needed. It now
limits time since a validated HA input read, rather than age of entity report timestamps.
If HA reads stop completing, the independent controller restricts commands, enablement
is blocked and cached Overview values show a read-watchdog warning. Report metadata is
kept in the API for diagnostics and never substituted with an invented report timestamp.

Quarter-hour accounting and meter conversion remain in place; available counters are
used at read time and reset with their reported values. An unchanged zero can span many
quarters without requiring a new entity timestamp. Weather forecast expiry is unchanged.
A working HA request proves HA is reachable; correct physical-device outage detection
still depends on the underlying integrations and must be checked during commissioning.
