# Tree Tabs Prototype

A local Sine mod that adds parent and child relationships to ordinary tabs in
Zen's existing sidebar, including pinned tabs, native folders and ordinary
tab groups (including groups styled by Advanced Tab Groups).

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
- **Alt+Shift+Right:** nest the selected tab under the previous ordinary tab in
  its folder/group and Space. **Alt+Shift+Left:** move it out one level. A root
  stays inside its folder/group. On macOS use **Option**
  for Alt. Its children follow, and the selected page stays focused.
  These shortcuts work from the sidebar and web pages, including frames.
  Inputs, textareas, and editable content retain their text-selection shortcuts.
- **Close a parent:** its children remain open and move up a level.
- **Move a parent in the sidebar, into/out of a folder, or to another Space:**
  its whole branch follows, including collapsed children and grandchildren.
  Creating a folder from a parent also carries its branch. Pinning or unpinning
  a parent carries its descendants into the same section.
- **New tabs, bookmarks, and external links:** remain roots unless they have
  an actual in-page opener.

Existing tabs are not automatically rearranged when the mod is enabled. Tree
relationships and collapse state are saved in the browser session and survive
a restart.

## Prototype scope

Ordinary tabs, ordinary pinned tabs, and tabs inside native Zen folders or
ordinary tab groups participate. Each immediate folder/group has independent
trees; parent and child must share the same container, Space and pinned section.
Nested folders/groups can have their own trees, and moving a folder/group
preserves all trees inside it.

For tabs already in a folder or group, select the child tab and use
**Option/Alt+Shift+Right**, or right-click that tab's row and choose
**Tree tabs → Nest under previous tab**. Its intended parent must precede it
in the same folder/group. Group headers have their own native context menu.
Groups keep their existing type and pin state.

Folder collapse and individual branch collapse are independent. Expanding a
folder retains the branch collapse state. Native folder and tree state survive
a browser restart. Ordinary group-header collapse and nested group-container
restoration follow Zen and Advanced Tab Groups; Tree Tabs stores the tab tree.
Links opened from a tab in a folder and Glances expanded from it enter that
folder before attaching to their parent. Explicit destinations in another
folder are respected.

Essentials, split views, live folders and Glance previews
remain outside the tree. Private and Little Zen windows are also excluded.

The existing Auto Glance and Option-click split behavior remains available.
A Glance preview stays outside the tree while it is a preview. Expanding it
to a normal tab can attach it to its ordinary source tab. Using Glance's
**Split** button preserves native split membership and does not attach a tree
child. Split panes remain excluded, even when their split is inside a folder/group.

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
disable tree tabs, automatic nesting, or **Alt+Shift+Arrow shortcuts for nesting
tabs**. The shortcut toggle takes effect immediately. Alt+Tab is not used.

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

The separate [Multi Tab Move](../multi-tab-move/) mod adds Shift-click selection
and dragging of multiple branches and native split sessions. Update both mods
for folder/group support: Tree Tabs **0.1.6** and Multi Tab Move **0.1.3**.
The synchronous `moveBranches(tabs, callback)` integration retains internal tree
relationships while folders, branches and splits move. Splits remain native.

`tests/branch_moves.py` checks branch order, nested and collapsed branches,
multi-tab moves, Space menu moves, late workspace attribute changes, page and
selection preservation, and Zen's native drop handler and animation cleanup.

`tests/glance_promotion.py` exercises the native Expand command, nested and
collapsed origins, sibling order, draft/document preservation, native split
promotion, excluded origins, settings, saved relationships, and unloading
while a promotion is in flight.

`tests/keyboard.py` exercises trusted Alt+Shift+Arrow input from browser chrome,
pages, and frames. It checks branch order and collapse state, editor selection,
shortcut cancellation, modifier matching, rejected page-generated events,
settings changes, document/draft preservation, native splits, and reload/unload.
It accepts the same `--profile`, `--port`, and `--report` arguments.

`tests/integration.py` refuses to operate unless the browser's active profile
matches the supplied disposable `test-profile` path.

`tests/folders.py` covers native folder creation, nested folders, branch
transfers, independent collapse, trusted keyboard and pointer gestures,
pin/unpin transitions, split preservation, rollback, Cmd-click, Glance promotion,
selection actions and hot reload. It additionally requires a
`folder-tree-test-profile` marker in the disposable profile.

`tests/folder_restore.py --prepare` saves a fixture and expected state before
quitting the disposable browser. Run it without `--prepare` after restarting the
same profile to check native folder hierarchy, tree relationships, collapse,
order and split restoration. Both runs take `--profile`, `--port`, `--expected`
and `--report`. This changes startup restoration only in the guarded test profile.
With Advanced Tab Groups installed in that test profile, add
`--advanced-tab-groups` to both runs to verify its nested containers and
collapsed group headers alongside the tree.

`tests/folder_sleeping.py` checks that native and multi-selection folder/pin
moves keep a sleeping child unloaded, attached to its parent, and unfocused.
The local fixture server must receive no requests for that child.

`tests/group_containers.py` covers pre-existing ordinary tab groups: actual
context-menu commands and content shortcuts, independent collapse, nested groups,
folder/group/pin/Space moves, sleeping children, and atomic native split moves.
The restart fixture also includes ordinary groups and nested group trees.

Bonsai's native tree-tabs implementation informed the scope and edge cases.
This prototype is implemented for the installed Zen APIs and the local Sine
setup.
