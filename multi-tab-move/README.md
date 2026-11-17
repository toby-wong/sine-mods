# Multi Tab Move

A Sine mod for selecting individual sidebar tabs with **Shift + left-click** and
moving them together. The gesture is the same on macOS and Windows.

## Use

1. Shift-click each row you want to move. Shift-click it again to deselect it.
   The focused tab is not implicitly added.
2. Drag any selected row above or below another sidebar row.
3. To change Spaces, drop onto a Space icon, or right-click a selected row and
   choose a destination Space.
4. Press Escape or click a tab normally to clear the selection.

To move into a folder or ordinary tab group, drop on the **middle of its header**;
a highlighted rectangle marks the destination. Empty folders and collapsed
folders/groups accept drops. Header edges place the selection before/after the folder/group.
Dropping beside a tab inside a folder/group reorders within that container.

The selection's right-click menu also offers:

- **New Space with selected tabs…** asks for a name, then creates the Space and
  moves the whole selection into it. Cancelling or submitting a blank name
  leaves the tabs and Spaces unchanged.
- **Close selected tabs (N)** closes the selection, including carried tree
  descendants and all panes of selected splits. The count includes those tabs.
  Native unsaved-page prompts run before any tab closes; cancelling keeps the
  selection intact. The browser window stays open.

Solid outlines mark selected rows. Dashed outlines mark descendants that will
move with their parent. Selection itself does not switch tabs or load sleeping
pages, and it does not change the native set of tabs affected by Close Tab.

## What stays together

- **Tree Tabs branches:** a selected parent carries every descendant, including
  collapsed children. Selecting a parent and child does not move the child twice.
  Moving a child branch away from an unselected parent detaches that branch root;
  its own descendants remain attached.
- **Split sessions:** selecting any pane's sidebar row selects the whole session.
  Its tree children follow too, including other splits. Moving uses the existing
  group, panes and layout, without rebuilding the split.
- **Native folders/groups:** selecting the header moves its existing contents
  together, including nested folders and internal trees. Selecting a parent tab
  inside a folder/group carries its branch; selecting a leaf moves only that tab.
- **Live pages:** tab and browser objects are reused; moves do not reopen URLs.

Sidebar row drops go between existing branches/groups without becoming a child
of the row under the pointer. Folder drops retain each moved branch and detach
its root from any parent left behind.

Space moves preserve pinned state. An explicit drop into a folder, ordinary
group or another tab section pins/unpins ordinary tabs and complete native split
groups to match the destination. Groups retain their existing type and pin state.
Folder wrappers cannot move into the unpinned section. Unsupported group
conversions are rejected before anything moves.

This prototype moves within one window and between its Spaces. Cross-window or
cross-profile transfers, Essentials, Glance preview rows, live-folder items,
private windows and Little Zen windows are excluded. Normal native dragging
remains available when there is no move selection.

## Install on macOS and Windows

Install [Sine](https://github.com/CosmoCreeper/Sine) in the desired Zen profile and
enable `sine.allow-unsafe-js`. In Sine's custom-repository field, use:

```text
https://github.com/toby-wong/sine-mods/tree/main/multi-tab-move
```

If you use Tree Tabs Prototype, update it to **0.3.0 or later** for split-session trees:

```text
https://github.com/toby-wong/sine-mods/tree/main/tree-tabs-prototype
```

Restart Zen after installing. Alternatively, use this collection's local
installer while Zen is closed. It also updates an already-installed Tree Tabs
copy and keeps that mod's enabled/disabled setting.

macOS:

```sh
python3 scripts/install.py \
  --profile "$HOME/Library/Application Support/zen/Profiles/your-profile" \
  --backup "$HOME/Desktop/multi-tab-move-backup" \
  --mods multi-tab-move
```

Windows PowerShell:

```powershell
py -3 scripts/install.py `
  --profile "$env:APPDATA\zen\Profiles\your-profile" `
  --backup "$env:USERPROFILE\Desktop\multi-tab-move-backup" `
  --mods multi-tab-move
```

Use a new backup directory each time. Install per profile. Disable the gesture
under **Settings → Sine Mods → Multi Tab Move → Configure**, or disable the mod.
Disabling removes selection, menus and drag handlers without moving any tabs.

## Development

Browser tests require a disposable profile with Sine, this mod, Tree Tabs,
Auto Glance and Alt-click Split View. Never enable automation in a daily profile.

```sh
node --check multi-tab-move/multi-tab-move.uc.js
python3 multi-tab-move/tests/integration.py \
  --profile /path/to/test-profile --port 2832 \
  --report /private/path/report.json --pointer-drag
```

See [VERIFICATION.md](VERIFICATION.md) for browser, restart and installation
coverage. Tests use disposable macOS Zen profiles and trusted WebDriver pointer
and keyboard input. Windows desktop input has not been physically tested.
