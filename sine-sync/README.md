# Sine Sync

Send installed Sine mods and their portable settings from one computer to another.
Each profile chooses **Off**, **Send only**, or **Receive only**. Work and Personal
use separate channels even when they share a Mozilla account.

This is a separate, experimental Sine mod. It does not merge the other mods.
It uses Mozilla's existing preferences sync for a small configuration manifest;
mod files are downloaded from their pinned public GitHub revisions and checked
against the sending computer's SHA-256 hashes.

## Install on Windows or macOS

1. Install Zen and Sine in each profile that should participate. Use Sine's
   [official installation instructions](https://github.com/sineorg/docs/blob/main/src/installation.md).
2. Sign in to the **same Mozilla account** on both computers. Enable **Settings**
   in the account's Sync choices.
3. Set `sine.allow-unsafe-js` to `true` in `about:config`, if it is not already
   enabled. This allows custom Sine JavaScript mods, including this one.
4. Paste this URL into Sine's custom repository installer:

   ```text
   https://github.com/toby-wong/sine-mods/tree/main/sine-sync
   ```

5. Restart Zen. Open **Settings → Sine Mods → Sine Sync → Configure**.
6. Choose the **profile channel first**: Work for Work, Personal for Personal.
7. On the source computer, choose **Send only**. On the other computer, choose
   **Receive only**. Click **Sync now** on the sender, then on the receiver.
8. After the receiver reports that mods were received, restart it to activate
   new files and on/off changes. Settings-only changes can apply without restart.

Installing Sine Sync is the only manual mod installation needed on a new
receiving profile. The other mods are downloaded by the receiver. Repeat for
Personal if you want both profiles on the second computer.

For a local checkout, the collection installer supports this mod:

```powershell
py -3 scripts/install.py --profile "$env:APPDATA\zen\Profiles\YOUR-PROFILE" `
  --backup "$env:USERPROFILE\Desktop\sine-sync-backup" --mods sine-sync
```

Quit Zen first when using the local installer. Use a new backup directory.

## Controls

- **This computer:** Off, Send only, Receive only. New installs default to Off.
- **Profile channel:** Work or Personal. Use the same channel on the two matching
  profiles. Channel names are logical labels, not filesystem paths.
- **Include portable mod settings:** synchronizes declared mod preferences such
  as find-bar text size, opacity and click behaviour.
- **Receive mod on/off choices:** follows the sender's enabled state. A mod
  removed by the sender is disabled on the receiver only if this channel
  previously managed it; its files are retained.
- **Check for changed files:** every 1, 5 or 15 minutes. Preference changes are
  noticed promptly; account synchronization follows Mozilla's normal schedule.
- **Sync now:** prepares/synchronizes the configuration immediately.
- **Local relay:** optionally lets another opted-in profile on this computer
  upload a sender's channel. This is useful when Work does not use browser Sync
  but Personal already does. Enable it in both local profiles; keep the
  signed-in relay profile running for new updates to upload. Leave it off on
  a normal Windows receiving profile.
- **Use this computer as sender:** explicitly takes over a channel. Stop the
  previous sender first to avoid competing sources.

To reverse direction, set the old sender to Off, choose Send only on the new
sender and use the takeover button, then make the old sender Receive only.
There is **one sender per channel**. Two-way conflict merging is not implemented.

The local relay checks for outgoing channels every 30 seconds. Its files are
private to the OS account under `<Zen user-data directory>/sine-sync-relay/`.
They contain the same bounded manifests, not credentials. Sender leases expire
if that sender stops running. Choosing Off or disabling the mod removes its
own local lease; previously uploaded configuration remains available to receivers.
An opted-in relay never enables browser Sync or signs in on another profile's
behalf. A Work source can therefore send through Personal while retaining its
existing browser-sync configuration.

For that setup, configure the Mac's Work profile as **Send only → Work** and
Personal as **Send only → Personal**, with **Local relay** on in both. On Windows,
use **Receive only → Work** or **Receive only → Personal** in each corresponding
profile, with Local relay off.

## What travels

- Mod files from public GitHub repositories, at the exact verified revision.
- The sender's enabled/disabled choices.
- Portable preferences declared in each mod's `preferences.json`.

Source-side code changes must be published to GitHub before they can travel.
Unpublished or unresolvable files stop publication and leave the previous
configuration intact. Preferences JSON may differ only in formatting; the
receiver uses the semantically identical public file. Old installed versions
are not silently upgraded.

API keys, credentials, local AI endpoints, profile paths, account state, browsing
history, tabs, tree relationships and ordinary Firefox extensions are excluded.
Sine's own loader, the signed Zen application and external helpers such as
Hammerspoon are not copied. The receiver installs Sine separately.

Receiver-managed mods have independent Sine auto-updates disabled so the sender
controls their versions. Unrelated receiver mods are preserved. The sync component
itself is updated separately through its Sine repository installation.

## Backup and failure behaviour

Downloads are staged before any installed files change. File hashes, relative
paths, entrypoints, setting declarations and payload size are validated.
Changed files, registrations and preferences are backed up under:

```text
<profile>/sine-sync/backups/<timestamp>-<id>/
```

Each backup includes a `receipt.json`, `registry-before.json`,
`preferences-before.json` and any replaced mod folders under `mods/`.
An application failure rolls back the files and selected preferences. A failed
download leaves the existing installation intact.

To stop synchronization, choose Off or disable Sine Sync. Installed mods remain.
To undo an applied update, quit Zen and restore only the mod IDs and preferences
listed in that backup's receipt. Preserve unrelated newer registrations.

## Limits and validation

- Both profiles must run Zen with Sine, use the same account and enable Settings sync.
- Only public GitHub mod sources are supported. Custom chrome manifests,
  symlinks and Windows-incompatible filenames stop publication.
- Payloads are capped at 64 KiB per channel; files are capped at 5 MiB each,
  40 MiB total and 300 files. These are checked before applying anything.
- Role, channel, device identity and status stay local to each profile.
- Local relay is off by default and does not synchronize its own toggle.
- Enabling normal Mozilla Settings sync also synchronizes the browser's usual
  supported settings; this mod does not replace that engine.
- The 22 Node checks, 21 disposable-browser checks, cold restart, settings
  controls and local relay were exercised on Zen 1.24b/macOS. Two real channels
  were uploaded and read back from Mozilla Sync with matching contents.
- Windows paths and download transactions have automated coverage. Native
  Windows execution and real cross-computer delivery require verification on
  the receiving computer.

Run the transaction tests with:

```sh
node --test sine-sync/tests/*.test.mjs
```
