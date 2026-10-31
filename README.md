# Tree Tabs Prototype

A local Sine mod that adds parent and child relationships to ordinary tabs in
Zen's existing sidebar.

## Use

- **Command-click a link in an ordinary tab:** the new background tab becomes
  a child of the source tab.
- **Click the arrow beside a parent tab:** collapse or expand its descendants.
  Collapsing the branch containing the selected tab selects its parent.
- **Select a hidden child through a shortcut:** its ancestors expand.
- **Right-click a tab → Tree tabs:** nest it under the previous ordinary tab,
  move it out one level, or expand the current Space's branches.
- **Close a parent:** its children remain open and move up a level.
- **Move a parent in the sidebar or to another Space:** its whole branch follows,
  including collapsed children and grandchildren, in the same order.
- **New tabs, bookmarks, and external links:** remain roots unless they have
  an actual in-page opener.

Existing tabs are not automatically rearranged when the mod is enabled. Tree
relationships and collapse state are saved in the browser session and survive
a restart.

## Prototype scope

Only ordinary, ungrouped tabs participate. Pinned tabs, Essentials, native tab
groups, split views, and Glance previews remain outside the tree. Private and
Little Zen windows are also outside this prototype.

The existing Auto Glance and Option-click split behavior remains available.
In particular, an ordinary website-created Glance is not converted into a
child tab; Command-click's background-tab override is the usual way to create
children.

Dragging/reordering a nested parent detaches that branch from its former
parent and carries its descendants with it. Selecting both a parent and a child
for a move keeps their relationship intact. Moving a branch preserves its pages
and collapse state.

This version does not implement drag-to-reparent or synchronizing trees between
windows. Use the Tree tabs menu for deliberate nesting and outdenting.

Collapsing a branch hides sidebar rows; it does not unload web pages.

## Settings and undo

Open **Zen Settings → Sine → Tree Tabs Prototype → Configure** to enable or
disable tree tabs or automatic nesting.

Disabling or removing the mod restores a flat sidebar without closing or
reloading pages. Saved relationships remain inert in session data, so enabling
the mod again can restore them.

The installed files are under the active Zen profile's
`chrome/sine-mods/tree-tabs-prototype`. The signed Zen.app bundle is unchanged.
This uses internal Zen APIs and should be retested after significant updates.

The pre-installation backup is:

`/Users/tobywo/Documents/Browser Migration Backups/2026-10-29_110519_Zen-Tree-Tabs-Prototype`

It includes the previous chrome setup, preferences, and session files. The
`reports` directory contains browser tests, restart verification, and screenshots.

## Implementation and checks

The controller uses native tab-opener information, native tab-move APIs,
per-tab SessionStore values, and batched tab events. It does not poll or read
webpage content. Parent/child relationships are indexed in memory; existing
tabs acquire saved tree metadata only when they participate.

The integration checks exercise real Command-click, Glance, and Option-click
actions, page-state preservation, collapse and expansion, menu commands,
duplicates, ordering, workspace boundaries, pinning/grouping, a large set of
unloaded tabs, and disabling/reloading the mod. A separate browser restart
checks session restoration. The existing Auto Glance regression suite is also
run with Tree Tabs enabled.

`tests/branch_moves.py` checks branch order, nested and collapsed branches,
multi-tab moves, Space menu moves, late workspace attribute changes, page and
selection preservation, and Zen's native drop handler and animation cleanup.

`tests/integration.py` refuses to operate unless the browser's active profile
matches the supplied disposable `test-profile` path.

Bonsai's native tree-tabs implementation informed the scope and edge cases.
This prototype is implemented for the installed Zen APIs and the local Sine
setup.
