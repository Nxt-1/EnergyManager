# Settings and hardware control in 4.0.6

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
or enable an actuator. Unverified live-card values display dashes; unknown or demo
observations are excluded from configured-mode actual charts. The original billing
timestamp checks remain in force. Persistent input errors need actual telemetry
diagnosis; the hardware switch does not bypass them.

The HA app's own Configuration tab still selects `demo` or `configured`. Demo mode
cannot operate hardware. Choose `configured` and restart to use installation inputs.

## One immediate hardware switch

Overview contains the only Hardware control switch. It applies immediately and saves
its requested state in the V4 SQLite database, without restarting or rewriting the
installation JSON. Planning and measurements continue while it is off.

On first upgrade to4.0.6 the new switch starts **off**. The old commissioning checkboxes
and JSON `policy.control_enabled` flag cannot enable it. Once explicitly enabled through
the new switch, later restarts wait for valid saved/runtime settings, mapped entities
and fresh critical measurements before resuming. The switch can always revoke a pending
request. Settings that have been saved but not loaded still require their normal restart.

Enabling validates settings, checks entity availability/units and checks measurement
freshness. A missing EV SoC or unknown phase reading can still pause EV independently
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
