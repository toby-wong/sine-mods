# Tree Tabs Prototype

A local Sine mod that adds parent and child relationships to ordinary tabs in
Zen's existing sidebar.

## Use

- **Command-click a link in an ordinary tab:** the new background tab becomes
  a child of the source tab.
- **Expand a Glance to a new tab:** with automatic nesting enabled, the promoted
  tab becomes a child of its originating ordinary tab, after existing children.
  Both pages retain their live state. A collapsed parent expands to reveal it.
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
A Glance preview stays outside the tree while it is a preview. Expanding it
to a normal tab can attach it to its ordinary source tab. Using Glance's
**Split** button preserves native split membership and does not attach a tree
child. Pinned, grouped, and split source tabs remain excluded.

Dragging/reordering a nested parent detaches that branch from its former
parent and carries its descendants with it. Selecting both a parent and a child
for a move keeps their relationship intact. Moving a branch preserves its pages
and collapse state.

This version does not implement drag-to-reparent or synchronizing trees between
windows. Use the Tree tabs menu for deliberate nesting and outdenting.

Collapsing a branch hides sidebar rows; it does not unload web pages.

## Install on macOS or Windows

Follow the collection's [installation guide](../README.md#install-the-sine-mods).
Use the Tree Tabs subfolder URL in Sine, or the shared local installer with
`--mods tree-tabs-prototype`. Restart Zen afterward.

Browser testing has been on macOS. Tree creation follows native opener
relationships, not a specific keyboard modifier. If Auto Glance converts a link
into a preview, that preview is excluded from the tree. Auto Glance's explicit
background-tab override is currently Mac Command-click only; Windows Ctrl-click
does not have that override.

## Settings and undo

Open **Zen Settings → Sine → Tree Tabs Prototype → Configure** to enable or
disable tree tabs or automatic nesting.

Disabling or removing the mod restores a flat sidebar without closing or
reloading pages. Saved relationships remain inert in session data, so enabling
the mod again can restore them.

The installed files are under the active Zen profile's
`chrome/sine-mods/tree-tabs-prototype`. The signed Zen.app bundle is unchanged.
This uses internal Zen APIs and should be retested after significant updates.

Original installation backups and browser reports are retained outside this
repository. The ignored `.local-setup.json`, when present, records their local
locations. Each run of the shared installer makes a separate backup.

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

`tests/glance_promotion.py` exercises the native Expand command, nested and
collapsed origins, sibling order, draft/document preservation, native split
promotion, excluded origins, settings, saved relationships, and unloading
while a promotion is in flight.

`tests/integration.py` refuses to operate unless the browser's active profile
matches the supplied disposable `test-profile` path.

Bonsai's native tree-tabs implementation informed the scope and edge cases.
This prototype is implemented for the installed Zen APIs and the local Sine
setup.
