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

Solid outlines mark selected rows. Dashed outlines mark descendants that will
move with their parent. Selection itself does not switch tabs or load sleeping
pages, and it does not change the native set of tabs affected by Close Tab.

## What stays together

- **Tree Tabs branches:** a selected parent carries every descendant, including
  collapsed children. Selecting a parent and child does not move the child twice.
  Moving a child branch away from an unselected parent detaches that branch root;
  its own descendants remain attached.
- **Split sessions:** selecting any pane's sidebar row selects the whole session.
  Moving uses the existing group, panes and layout, without rebuilding the split.
- **Native folders/groups:** selecting the header moves its existing contents
  together. Selecting an individual ordinary tab inside a folder moves that tab.
- **Live pages:** tab and browser objects are reused; moves do not reopen URLs.

Sidebar drops go between existing branches/groups rather than reparenting them.
Pinned tabs keep their pinned state. A selection mixing pinned and ordinary tabs
can move to another Space; reorder one section at a time within a Space.

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

If you use Tree Tabs Prototype, update it to **0.1.4 or later** as well:

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

The initial version passed 99 browser checks on macOS Zen 1.24.1b, including
trusted WebDriver pointer dragging. See [VERIFICATION.md](VERIFICATION.md) for
coverage and limits. Windows desktop input has not been physically tested.
