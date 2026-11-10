# Sine mods

Toby Wong's custom mods for [Zen Browser](https://zen-browser.app/), loaded
through [Sine](https://github.com/CosmoCreeper/Sine).

## Included projects

| Project | Version | What it does |
| --- | --- | --- |
| [Little Zen](little-zen/) | 0.1.0 | Opens a compact temporary browsing window. **Open in Space** moves the live page into a normal window, preserving its state and container. |
| [Auto Glance](auto-glance/) | 0.2.3 | Opens website-created tabs as Glance previews, keeps Mac Command-click as a normal background tab, and adds configurable Space-coloured backdrop opacity. |
| [Tree Tabs Prototype](tree-tabs-prototype/) | 0.1.3 | Adds collapsible parent/child relationships to ordinary tabs. Alt+Shift+Right/Left nest and outdent whole branches; expanded Glances nest beneath their originating tree tab. |
| [Alt-click Split View — local fork](alt-click-split-view/) | 1.4.7-local | Preserves live pages when splitting, adds third/fourth panes, and supports whole-group middle-click closure with stable pane focus. Stacks new split pairs in tall windows. Based on Kostiantyn Kugot's mod. |
| [Keyword Tab Search](keyword-tab-search/) | 0.1.2 | Activates an existing search keyword with Tab, including `keyword` for a saved `@keyword` alias, and keeps searches in a pending split pane. |
| [Find Bar Pane Fix](findbar-pane-fix/) | 0.1.4 | Keeps Cmd/Ctrl+F inside its pane, with configurable styling and optional scaling with page zoom. |
| [Ctrl Tab Theme](ctrl-tab-theme/) | 0.1.0 | Matches the native Ctrl+Tab switcher to Space colours, with rounded previews, readable titles, and a clear selection outline. |
| [Profile Switcher](profile-switcher/) | 0.2.0 | Identifies and switches profiles with native controls. On macOS, optionally sends web links from other apps to a chosen profile. |
| [Window Sync Recovery](window-sync-recovery/) | 0.1.0 | Clears stale faded snapshots once a single browser window owns the live pages again, without reloading them. |
| [Sine Sync](sine-sync/) | 0.1.0 | Sends Sine mods and portable settings between computers, with configurable sender/receiver roles and separate Work/Personal channels. |

All included projects are Sine mods. Other third-party mods from the original
browser setup are not included.

### Behavior and platform support

These prototypes were developed and exercised on macOS. The browser scripts use
Zen/Firefox APIs, and the local installer supports macOS and Windows; Windows
browser behavior has **not** been tested.

- **Little Zen:** use **File → New Little Zen** or a link's **Open Link in Little
  Zen** context menu on either platform. Windows may need **Alt** to reveal the
  menu bar. Keep a page with **Command+O** on Mac or **Ctrl+O** on Windows.
  The optional system-wide **Command+Option+N** shortcut uses Hammerspoon and is
  Mac-only; a Windows global shortcut is not supplied. Temporary windows are not
  restored after a browser restart, so keep pages you need with **Open in Space**.
- **Auto Glance:** automatic website tabs, middle-click, and the page context
  menu's **Open Link in New Tab** can become previews. Its explicit background-tab
  override currently checks **Command**, not Windows **Ctrl**. Windows Ctrl-click
  may therefore become Glance; do not assume it has the Mac override.
  Adjust **Extra backdrop opacity** under its Sine Configure button to make the
  area behind a preview less transparent, without changing the sidebar.
- **Tree Tabs:** only ordinary, unpinned, ungrouped tabs participate. Splits,
  Essentials, native groups, Glance previews, private windows, and Little Zen windows are
  excluded. Expanding a Glance can nest it under its ordinary source tab.
  The experimental split-session tree support was reverted. Use
  **Alt+Shift+Right/Left** (Option on Mac), or **right-click a tab → Tree tabs**,
  to nest or outdent deliberately. The shortcuts preserve editor selection
  controls and can be disabled in the mod's settings.
- **Split View:** **Option-click** on Mac / **Alt-click** on Windows is the default.
  It uses each platform's native tab accelerator internally. Windows and Linux
  routing have automated coverage; live browser checks have run on macOS.
  Choose a different modifier in the mod's settings if it conflicts with Glance.
  The optional Hammerspoon background-window click guard is Mac-only.
- **Keyword Tab Search:** type an existing search keyword, press **Tab**, type
  your query, and press **Enter**. The same plain Tab gesture works on both
  platforms. Unrecognized text and normal Tab navigation are preserved.
- **Find Bar Pane Fix:** use **Command+F** on Mac or **Ctrl+F** on Windows.
  Works alongside Better Find Bar and keeps each find bar within its owning
  page, including split panes and Glance previews. Change its appearance in
  **Settings → Sine → Find Bar Pane Fix → Configure**; changes apply immediately.
- **Ctrl Tab Theme:** use **Control+Tab** on both Mac and Windows. Keeps native
  switching behaviour and works alongside Better CtrlTab Panel. Configure
  opacity and title size in **Settings → Sine Mods → Ctrl Tab Theme → Configure**.
- **Profile Switcher:** click the named button above your tabs to switch profile
  windows. The colour and window-title label are configurable. Install Sine and
  the mod separately in each profile. On macOS, use the menu's **Links from other
  apps** submenu to choose an external-link destination for each profile.
  Native process activation and launch have
  been tested on macOS; Windows/Linux desktop activation remains untested.
- **Window Sync Recovery:** automatically clears stale native snapshots when
  only one browser window remains in a profile. It preserves the live document
  and leaves genuine previews alone while multiple windows are open.

## Install the Sine mods

### Prerequisites on macOS and Windows

1. Install Zen, open it once, and identify the profile you actually use.
2. Install Sine for that profile using its
   [official installation instructions](https://github.com/sineorg/docs/blob/main/src/installation.md)
   and the appropriate [release installer](https://github.com/CosmoCreeper/Sine/releases/latest).
   If **Settings → Sine** already appears, keep your existing installation.
3. For mods that include custom JavaScript, set the `about:config` preference
   `sine.allow-unsafe-js` to `true` to allow Sine to load them. This preference
   applies to other custom Sine JavaScript mods too. Find Bar Pane Fix uses a
   small script for its optional page-zoom scaling. Its other styling and
   Ctrl Tab Theme work with CSS alone.
4. Keep Zen's native Glance and Split View features enabled for the corresponding
   mods. Their preferences are under **Settings → Sine → [mod] → Configure**.

### Install from GitHub with Sine

Paste **one full subfolder URL** at a time into Sine's custom repository
installation field:

| Mod | Repository URL to paste |
| --- | --- |
| Little Zen | `https://github.com/toby-wong/sine-mods/tree/main/little-zen` |
| Auto Glance | `https://github.com/toby-wong/sine-mods/tree/main/auto-glance` |
| Tree Tabs Prototype | `https://github.com/toby-wong/sine-mods/tree/main/tree-tabs-prototype` |
| Alt-click Split View — local fork | `https://github.com/toby-wong/sine-mods/tree/main/alt-click-split-view` |
| Keyword Tab Search | `https://github.com/toby-wong/sine-mods/tree/main/keyword-tab-search` |
| Find Bar Pane Fix | `https://github.com/toby-wong/sine-mods/tree/main/findbar-pane-fix` |
| Ctrl Tab Theme | `https://github.com/toby-wong/sine-mods/tree/main/ctrl-tab-theme` |
| Profile Switcher | `https://github.com/toby-wong/sine-mods/tree/main/profile-switcher` |
| Window Sync Recovery | `https://github.com/toby-wong/sine-mods/tree/main/window-sync-recovery` |
| Sine Sync | `https://github.com/toby-wong/sine-mods/tree/main/sine-sync` |

Use the same steps on macOS and Windows. Restart Zen after installation.
The repository root is a collection, not a single installable mod. Use the fork
URL above to get these split fixes; `kkugot/alt-click-split-view` installs upstream.
The fork retains upstream's mod ID, so it replaces an existing copy of that mod
in the selected profile.

### Install or update from a local checkout

This also works before the repository is published. It requires **Python 3.10
or newer** and an existing Sine installation.

Open `about:support` in Zen and use **Profile Folder → Show in Finder / Open
Folder** to obtain the exact profile path. Typical locations are:

| Platform | Profile directory |
| --- | --- |
| macOS | `~/Library/Application Support/Zen/Profiles/<your-profile>` |
| Windows | `%APPDATA%\zen\Profiles\<your-profile>` |

Fully quit Zen before installing: **Command+Q** on Mac; exit all Zen windows
and wait for its processes to finish on Windows. Run these commands from this
repository's root, substituting your actual profile path.

**macOS — Terminal**

```sh
python3 scripts/install.py \
  --profile "$HOME/Library/Application Support/Zen/Profiles/your-profile" \
  --backup "$HOME/Desktop/sine-mods-backup-$(date +%Y%m%d-%H%M%S)"
```

**Windows — PowerShell**

```powershell
py -3 scripts/install.py `
  --profile "$env:APPDATA\zen\Profiles\your-profile" `
  --backup "$env:USERPROFILE\Desktop\sine-mods-backup-$(Get-Date -Format yyyyMMdd-HHmmss)"
```

The default installs all included Sine mods. To choose a subset, append, for example:

```text
--mods auto-glance tree-tabs-prototype
```

Add `--dry-run` to inspect the plan without writing anything. The backup directory
must be new for each real installation. The installer:

- Backs up `mods.json` and the selected mods' existing directories.
- Installs the runtime files and merges only their Sine registrations.
- Preserves other mods, existing enable/disable choices, and browser preferences.
- Disables automatic updates for these local copies.
- Rolls back the selected files and registry if installation fails.

Restart Zen, check the mods are enabled in **Settings → Sine**, and configure
them there. This installer does not install Sine, change the Zen application
bundle or install Hammerspoon integrations.

For cross-computer synchronization, see [Sine Sync](sine-sync/). It defaults to
Off; choose matching Work/Personal channels and one sender before receiving on
another computer. Its own installation is required on each participating profile.

### Optional Mac shortcuts

For Little Zen's global shortcut, install
[Hammerspoon](https://www.hammerspoon.org/), grant the permissions it requests,
and copy `little-zen/hammerspoon/little-zen.lua` into `~/.hammerspoon/`.
Add this block **once** to your existing `~/.hammerspoon/init.lua`, then reload
Hammerspoon's configuration:

```lua
-- BEGIN Little Zen
if littleZen and littleZen.stop then littleZen.stop() end
littleZen = require("little-zen")
-- END Little Zen
```

Do not replace your whole `init.lua`. If Little Zen's shortcut is already
configured, keep that configuration.

`alt-click-split-view/option-click-guard.lua` is a separate optional integration:
it preserves Option-click when focusing a background Zen or Arc window and
removes Option from background clicks in other apps. See the
[fork README](alt-click-split-view/README.md) before enabling that behavior.
Neither integration is used on Windows.

## Disable, update, or restore

Disable/remove individual browser mods in **Settings → Sine**. Disabling Tree
Tabs restores a flat sidebar without closing tabs. Disabling Little Zen converts
open temporary windows into ordinary windows. Removing the split fork separates
its managed splits and restores their pin state without closing the pages.

For local updates, run the installer again with a new backup directory. To undo
one of its installations, quit Zen and use the backup's `receipt.json` to identify
the selected mods: replace only those mod directories with the copies in
`backup/mods/`, or remove them if they did not exist before. Restore that backup's
`mods.json` only if no later Sine changes need to be kept; otherwise merge just the
selected entries from it. Reopen Zen afterward.

## Development and history

Each mod directory contains its source, manifest, preferences, and individual
README. The installer and its tests live in `scripts/` and `tests/`.

Project agent guides record the current source status, implementation constraints,
validation requirements, and proposed future directions:

- [Little Zen](little-zen/AGENTS.md)
- [Auto Glance](auto-glance/AGENTS.md)
- [Tree Tabs Prototype](tree-tabs-prototype/AGENTS.md)
- [Alt-click Split View](alt-click-split-view/AGENTS.md)
- [Keyword Tab Search](keyword-tab-search/AGENTS.md)
- [Find Bar Pane Fix](findbar-pane-fix/AGENTS.md)
- [Profile Switcher](profile-switcher/AGENTS.md)
- [Window Sync Recovery](window-sync-recovery/AGENTS.md)

```sh
python3 -m unittest discover -s tests -v
node --test alt-click-split-view/tests/alt-click-split-view.test.cjs
node --test keyword-tab-search/tests/keyword-tab-search.test.cjs
node --test profile-switcher/tests/profile-switcher.test.cjs
```

The browser integration scripts inside the mod directories require a separately
launched disposable Zen profile. They are development tools, not part of
installation; do not point them at your everyday profile. Existing live-browser
validation was performed on macOS.

Auto Glance and Tree Tabs retain their original Git commits and authorship.
Their old branches live under `archive/auto-glance/` and
`archive/tree-tabs-prototype/`; their tags are prefixed with those project names.
Historical commits have that project's files at the repository root. Current
`main` has all projects in their respective subfolders.

```sh
git log --all --graph --oneline
git log --oneline archive/auto-glance/main
git show tree-tabs-prototype/prototype/v0.1.1:tree-tabs.uc.js
```

Local setup metadata, browser profiles, generated reports, and backups are
excluded from version control. Checking out a commit does not update the running
browser; install the chosen files separately.

## Credits

Little Zen, Auto Glance, Tree Tabs Prototype, Keyword Tab Search, Find Bar
Pane Fix, Profile Switcher, and Window Sync Recovery are local customizations
created for this collection. Tree Tabs' scope was informed by
[Zen Bonsai](https://github.com/joegoldin/zen-bonsai-browser).

Alt-click Split View is a modified version of
[Kostiantyn Kugot's upstream project](https://github.com/kkugot/alt-click-split-view).
Its [MIT license](alt-click-split-view/LICENSE) and attribution are retained.
See its [patch notes](alt-click-split-view/PATCH-NOTES.md) for the local changes.
