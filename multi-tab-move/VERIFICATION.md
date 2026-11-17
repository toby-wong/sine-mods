# Multi Tab Move validation

## Version 0.2.0 — split-session tree branches

Validated with Tree Tabs 0.3.0 on disposable macOS Zen 1.24.1b and Advanced
Tab Groups 3.10.0. The focused split-tree suite passed 118 checks, including
trusted Shift-click and pointer dragging of a split with tree descendants into
a collapsed group, moving the branch between Spaces, split-under-split trees
and unloaded children with zero page requests. The existing native wrappers,
pane order, layouts, documents and focus stayed intact. A real restart passed
13 checks for two-, three- and four-pane split trees and their folder placement.

The shared installer passed 11 tests, and the existing modifier/split hook Node
suite passed 14 tests. Browser reports remain outside Git. Physical mouse input
and Windows desktop input remain unverified.

| Regression suite | Result |
| --- | --- |
| Multi Tab Move with pointer dragging | 148 checks passed |
| Ordinary groups / native folders / sleeping children | 26 / 61 / 4 checks passed |
| Tree core / branch moves / Glance promotion / keyboard | 26 / 17 / 21 / 41 checks passed |
| Auto Glance / Keyword Tab Search | 31 / 36 checks passed |
| Split extension / adaptive layouts / closure / regression cases | 195 / 63 / 114 / 15 checks passed |
| Split-tree restart without ATG | 13 checks passed |
| Existing folder-tree restart without ATG | 11 tree nodes, folder hierarchy and native split preserved |

The rendered test sidebar showed two split rows in the same folder tree and
three visible active panes. A reload with a selected split branch retained all
explicit/carried selection, native objects, documents, tree/layout state,
preferences and other controllers.

Live Work activation preserved 140 tabs and five split sessions without a
browser restart. Personal received the update while closed, with byte-identical
preferences. Both profile copies matched source; unrelated registry entries and
enabled states were retained, and the temporary helpers were removed. Personal
runtime activation remains pending until its next launch.

## Version 0.1.3 — ordinary tab-group destinations

Validated on November 17, 2026 with macOS Zen 1.24.1b and Tree Tabs 0.1.6:

| Suite | Result |
| --- | --- |
| Ordinary groups, trusted menu/keyboard input and selection dragging | 26 checks passed |
| Same ordinary-group suite with Advanced Tab Groups 3.10.0 | 26 checks passed |
| Folder trees | 61 checks passed |
| Sleeping children through native and selection folder/pin moves | 4 checks passed |
| Multi Tab Move | 148 checks passed |
| Tree Tabs core / branch moves / Glance promotion / keyboard | 26 / 17 / 21 / 41 checks passed |
| Auto Glance | 31 checks passed |
| Split closure | 114 checks passed |
| Shared installer | 11 tests passed |
| Graceful quit/restart with Advanced Tab Groups | Group/folder hierarchy, collapse, 11 tree nodes, tab order and native split layout preserved |
| Reload with an existing group selection | Tab/group objects, documents, tree/split state, selection, preferences and companion settings preserved |

Existing ordinary groups now retain tree controls, branch relationships and
their original pin state. Header-center drops enter collapsed groups, child-row
drops remain in their immediate group, and folder/group round trips preserve
documents. Sleeping children remain unloaded with zero requests. Complete
split wrappers remain native and outside the tree, including when sleeping
panes lack individual split attributes. The compatibility guard rejects an
older Tree Tabs controller before moving a selection.

Tree Tabs saves per-tab trees; Advanced Tab Groups saves ordinary wrapper
nesting and header collapse. An initial restart without that companion retained
the trees but flattened/expanded ordinary wrappers. The test now explicitly
requires ATG for that additional wrapper assertion rather than assigning its
persistence responsibility to Tree Tabs.

An initial folder-suite setup exhausted Python's default five-connection
accept queue while loading concurrent fixture pages. Increasing only the
local test server's queue resolved setup; no browser network preference or
runtime mod change was needed. Physical mouse input and Windows desktop
input remain unverified.

The rendered ATG sidebar showed ordinary-group trees, native folder trees and
both native split panes. Live activation in the running profile preserved its
tabs, documents, focus, tree/group/split state, preferences and other mod
controllers. The second profile stayed closed and received the update for
its next launch, with its preferences unchanged. Both profiles' installed
files matched source, and the temporary helpers were removed.

## Version 0.1.2 — trees inside folders

Validated on November 17, 2026 with macOS Zen 1.24.1b and Tree Tabs 0.1.5:

| Suite | Result |
| --- | --- |
| Folder trees, including trusted pointer/keyboard input and selection actions | 61 checks passed |
| Sleeping children through native and selection folder/pin moves | 4 checks passed |
| Multi Tab Move, including pointer dragging and native menu/dialog actions | 148 checks passed |
| Tree Tabs core / branch moves / Glance promotion / keyboard | 25 / 17 / 21 / 41 checks passed |
| Auto Glance | 31 checks passed |
| Split closure | 114 checks passed |
| Shared installer | 11 tests passed |
| Real graceful quit/restart | Folder hierarchy, tree state/order/collapse and saved split layout preserved |

The folder suite checks branches inside native and nested folders, folder and
branch collapse, scope-bound keyboard nesting, complete branch moves, pin/unpin
transitions, and moving whole folder wrappers between Spaces. Header-center
drops enter empty/collapsed folders; edge drops go before/after them. Row drops
inside a folder stay outside unrelated branches. Cycles, native folder-depth
violations and an older Tree Tabs controller are rejected before moving.

Mixed folder moves keep the existing split group, pane order, saved layout,
documents and visible panes. A failed move restores pin state and placement.
Cmd-click children and expanded Glances attach inside their source folder.
Selection-based new-Space and close actions preserve unrelated tabs and focus.
Sleeping children remain unloaded and make no page requests. A rendered
browser screenshot showed nested tree rows and both restored split panes.

Tests used a disposable profile with localhost automation. Pointer gestures
were trusted WebDriver input, not a physical mouse. Windows desktop input
remains unverified. Keep the fixture profile's Space list small when repeating
the suites: accumulated temporary Spaces can put an icon underneath Zen's
new-Space button and invalidate a pointer target.

## Version 0.1.1 — selection menu actions

Validated on November 17, 2026 with macOS Zen 1.24.1b:

| Suite | Result |
| --- | --- |
| Multi Tab Move, including pointer dragging and native menu/dialog actions | 148 checks passed |
| Split closure | 114 checks passed |
| Shared installer | 11 tests passed |

Close selected tabs was exercised through the context menu with selected trees
and a complete split. Unrelated tabs, surviving document identities and focus
were retained. Cancelling a real native beforeunload prompt kept the entire
selection open; accepting closed all selected branches/panes. Closing a child
branch preserved its parent and sibling. Duplicate commands and unloading while
waiting for permission did not close additional tabs.

New Space with selected tabs was exercised through the context menu and native
name prompt. Cancelling or supplying whitespace created no Space and moved
nothing. A named Space received the selected collapsed tree, split and pinned
tab with their original documents, layout, tree links, pin state, container and
active split pane. Unselected tabs stayed in their original Space. A simulated
move failure removed only its newly created, empty Space.

The existing move, rollback, sleeping-tab, cancellation and reload checks passed
again. Page request counts remained one per fixture page. Windows desktop and
physical mouse input remain unverified.

Only Multi Tab Move was updated in the two existing profiles. Live activation
preserved the running profile's tabs, documents, tree/split state, focus, move
selection, preferences and other controllers, including the existing Tree Tabs
instance. The closed profile was updated on disk for its next launch. A separate
activation check also retained a nonempty selection in the disposable profile.
Installed files matched source, and temporary activation helpers were removed.

## Version 0.1.0 — initial prototype

Validated on November 17, 2026 with Zen 1.24.1b on macOS, Tree Tabs 0.1.4,
Auto Glance 0.2.3 and Alt-click Split View 1.4.7-local. Browser tests used a
disposable profile; generated reports and profile backups remain outside Git.

| Suite | Result |
| --- | --- |
| Multi Tab Move, including WebDriver pointer dragging | 99 checks passed |
| Tree Tabs core | 25 checks passed |
| Tree Tabs branch moves | 17 checks passed |
| Glance promotion | 21 checks passed |
| Tree Tabs keyboard shortcuts | 41 checks passed |
| Auto Glance | 31 checks passed |
| Split closure | 114 checks passed |
| Shared installer | 11 tests passed |

The move suite covers individual Shift-click selection/deselection, no implicit
selection of the focused tab, whole branches, collapsed descendants, three- and
four-pane splits, native folders, pinned tabs, repeated moves in both directions,
Space-icon drops and context-menu Space moves. It checks cancellation, a failed
move's rollback, an incomplete Tree Tabs startup, settings changes and hot reload.
Sleeping tabs stay unloaded. Existing documents, drafts, tree links, split
wrappers, pane order and layouts are retained; fixture pages load only once.

Selection and dragging use trusted WebDriver mouse actions in browser chrome,
including mouse-down, movement and mouse-up. A screenshot of the disposable
browser was inspected for selection outlines and three visible, non-overlapping
split panes. This is not physical mouse or Windows desktop validation.

The selected mod files were installed with backups in two existing profiles.
Activation in the running profile preserved tab/document identities, tree state,
split layouts, selected tab, active Space, existing mod preferences and unrelated
controllers. The other profile remained closed; activation there awaits its next
launch. No daily browser process was restarted or given remote-debug access.

## Earlier shortcut-test limitation

The 0.1.x split-extension shortcut suite timed out before entering its initial
New Empty Split mode, including after unloading Multi Tab Move. The 0.2.0
investigation found that assigning key attributes in the fresh fixture did not
refresh Gecko's cached keyset. Reinserting that keyset registers the intended
binding; trusted keyboard input now invokes the command. Those historical
timeouts remain recorded rather than being retroactively counted as passes.

Cross-window/profile transfers are outside this prototype. Physical macOS mouse
input, Windows desktop input and activation in the closed profile remain
unverified.
