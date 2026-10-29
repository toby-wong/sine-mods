# Tree Tabs Prototype

A local Sine mod that adds parent and child relationships to ordinary tabs and
split sessions in Zen's existing sidebar.

## Use

- **Command-click a link:** the new background tab becomes a child of the
  source tab, or of the whole split session when clicking inside a split.
- **Click the arrow beside a parent tab:** collapse or expand its descendants.
  Collapsing the branch containing the selected tab selects its parent.
- **Select a hidden child through a shortcut:** its ancestors expand.
- **Right-click a tab → Tree tabs:** nest it under the previous tab or split
  session, move it out one level, or expand the current Space's branches.
- **Right-click either pane of a split → Tree tabs:** the same actions apply
  to the entire split. A split can be a parent, a child, or both, including
  underneath another split. Its panes always move together.
- **Close a parent:** its children remain open and move up a level.
- **New tabs, bookmarks, and external links:** remain roots unless they have
  an actual in-page opener.

Existing tabs are not automatically rearranged when the mod is enabled. Tree
relationships and collapse state are saved in the browser session and survive
a restart.

## Split sessions

Splitting a tab that already has a parent or children transfers those
relationships to the split session. The arrow beside a split hides its tree
children; its own panes remain visible.

Adding or closing a pane preserves the session's tree position. When only one
pane survives, it inherits the split's parent and children. Explicitly
unsplitting transfers the tree role to the first surviving pane; other panes
become its peers. Closing the entire session promotes its surviving children.

Tree state is saved on every pane so it survives closing the first pane and
restarting Zen. Nesting uses Zen's native group movement and does not reload
the pages in the split.

## Prototype scope

Ordinary, ungrouped tabs and unpinned split sessions participate. Pinned tabs,
Essentials, ordinary native tab groups (including splits inside them), and
Glance previews remain outside the tree. Private and Little Zen windows are
also outside this prototype.

The existing Auto Glance and Option-click split behavior remains available.
In particular, an ordinary website-created Glance is not converted into a
child tab; Command-click's background-tab override is the usual way to create
children.

This version does not implement drag-to-reparent, dragging a whole branch, or
synchronizing trees between windows. Native dragging/reordering keeps the
browser's chosen placement, detaches the moved tab or split session, and
promotes its children.
Use the Tree tabs menu for deliberate nesting and outdenting.

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

The backup before adding split-session support is:

`/Users/tobywo/Documents/Browser Migration Backups/2026-10-29_112626_Zen-Tree-Tabs-Split-Sessions`

Its `before/installed-mod` directory contains version 0.1.0, and
`before/chrome/sine-mods/mods.json` contains the previous Sine registry.

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

Split checks cover whole-session nesting in both directions, split-under-split
trees, clicks from either pane, collapse and selection, pane addition and
removal, unsplitting, parent/child merging, and preserved browsing contexts and
documents.

`tests/integration.py` refuses to operate unless the browser's active profile
matches the supplied disposable `test-profile` path.

Bonsai's native tree-tabs implementation informed the scope and edge cases.
This prototype is implemented for the installed Zen APIs and the local Sine
setup.
