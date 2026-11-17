# Multi Tab Move validation

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

## Unresolved validation

The existing split-extension shortcut suite timed out before entering its
initial New Empty Split mode. The same timeout occurred after unloading Multi
Tab Move. Its cause remains uninvestigated in this change; this suite is not
counted as a pass. Moving existing three-/four-pane splits and split closure
passed separately.

Cross-window/profile transfers are outside this prototype. Physical macOS mouse
input, Windows desktop input and activation in the closed profile remain
unverified.
