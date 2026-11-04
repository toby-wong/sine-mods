# Sine Sync agent guide

## Current status

- Version 0.1.0 is an initial cross-computer sync implementation.
- Roles are Off, Send only and Receive only; new installations default to Off.
- Separate Work and Personal payloads use native Mozilla preferences sync.
- Public GitHub files are pinned and matched to the source bytes. Receiver
  downloads are validated and staged before a backed-up transaction.
- Twenty-two Node tests cover source integrity, receiver isolation, secret filtering,
  path validation, preference-only changes, rollback, concurrent edits, channel
  separation, role changes, source takeover, relay expiry and missing data.
- Twenty-one browser integration checks passed in two disposable Zen 1.24b
  profiles. All 15 source mods downloaded successfully; live document identity,
  unsaved input, destination credentials and local profile paths were preserved.
- A cold restart activated the received mods and cleared the restart notice.
  The settings dialog was checked with visible controls, Off/Receive transitions
  and live status updates. Local relay dispatch and lease cleanup also passed.
- Real Work and Personal profiles send separate channels. Work has browser Sync
  unconfigured; Personal uploads both through the optional local relay. A fresh
  authenticated read from Mozilla Sync returned both exact payloads, with 15
  mods and 76 portable setting entries in each channel.
- The live Work account-sync state and both profiles' other mod preferences
  remained unchanged. Follow-up Personal verification preserved all 93 tab and
  document identities. One earlier full-identity comparison changed during the
  operation, so do not use that earlier result as proof of preservation.
- The shared installer's nine checks passed.
- Native Windows execution has not been tested.

## Constraints

- One sender per channel. Do not claim two-way merging or pretend setup on one
  computer verifies delivery to another.
- Preserve tabs, live documents, tree/split/session data and unrelated mods.
  Do not restart the browser automatically or reload all mod scripts.
- Never modify the signed application or enable debugging on real profiles.
  Use disposable profiles for privileged automation.
- Sync only bounded, validated metadata and declared portable settings.
  Never include API keys, account records, local paths/endpoints or profile data.
- Every participating profile registers both payload control preferences;
  otherwise native settings sync can discard another channel's data.
- Do not sync the role/channel controls themselves.
- Local relay is opt-in. Never enable browser Sync on a previously unconfigured
  profile. Use expiring, owner-tagged manifests in the shared user-data folder.
  Disable/remove only the current profile's own lease. Native tests must override
  the relay directory to a disposable directory before enabling the relay.
- Verify source files against the pinned public repository; never silently
  substitute a newer version or upload private code to make syncing succeed.
- Keep downloads staged, back up selected state, preserve unrelated concurrent
  edits and abort on concurrent edits to a managed mod.
- Disabled/deleted source mods must not delete receiver-only mods or user data.
- Receiver code and enable-state updates take effect after a user restart.
- A native preferences pull may replace a just-published payload. Sync now
  reasserts the configured sender/relay values and sends once more if necessary.
- Keep temporary profiles, snapshots, settings and test results outside Git.

## Potential future direction

- Verify native Windows setup and sustained delivery across two actual machines.
- Add a dedicated encrypted sync collection if native preference-record size
  becomes restrictive, rather than increasing limits without understanding it.
- Add more logical channels with a plan for the aggregate settings-record size.
- Consider explicit two-way conflict resolution as a separate feature.
- Add selective mod exclusions and a backup restore UI.
