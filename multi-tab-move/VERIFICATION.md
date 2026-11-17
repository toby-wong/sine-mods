# Multi Tab Move 0.1.0 validation

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
