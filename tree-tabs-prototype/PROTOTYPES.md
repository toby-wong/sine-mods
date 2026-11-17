# Prototype history

The active version is **0.3.0**. A whole native split session can be a parent or
child in the tree, including inside folders. Its actual panes and layout remain
owned by Zen.

The repository was created after the first two prototypes were deployed.
Their commits were reconstructed from the saved source snapshots, followed
by an explicit revert. Commit dates therefore describe when this history was
recorded, not the original deployment times.

| Tag | Status |
| --- | --- |
| `tree-tabs-prototype/prototype/v0.1.0` | Original prototype: ordinary tabs form trees; splits are excluded. |
| `tree-tabs-prototype/prototype/v0.2.0` | Split-session experiment, rolled back after the user reported missing split tabs. |
| `tree-tabs-prototype/prototype/v0.1.0-restored` | Restored ordinary-tab prototype, with the split-session change reverted. |
| `tree-tabs-prototype/prototype/v0.1.1` | Whole branches follow sidebar moves and moves between Spaces. |
| `tree-tabs-prototype/prototype/v0.1.2` | Expanded Glances become children of their originating ordinary tabs. |
| `tree-tabs-prototype/prototype/v0.1.3` | Alt+Shift+Arrow shortcuts nest and outdent ordinary tab branches, preserving editor selection. |
| `tree-tabs-prototype/prototype/v0.1.4` | Branch-preserving synchronous move API for Multi Tab Move; split sessions remain native. |
| `tree-tabs-prototype/prototype/v0.1.5` | Independent trees inside native folders, preserving branches across folder, pin and Space moves. |
| `tree-tabs-prototype/prototype/v0.1.6` | Tree controls inside ordinary tab groups, including Advanced Tab Groups; preserve group type, pin state and native split ownership. |
| `tree-tabs-prototype/prototype/v0.3.0` | Whole split sessions as tree nodes inside folders/groups, with branch moves, lifecycle transfer and split-folder restoration. |

The v0.2.0 automated tests and installation checks passed, but did not catch
the subsequent user-visible problem. Its root cause has not been established.
The rollback restored the previous source and stylesheet, removed the
split-specific tree metadata, and preserved the current tabs and split
layouts. A live check confirmed the restored version and visible split rows.

## v0.3.0 validation

The user explicitly requested a split session as a parent/child node inside a
folder. This implementation builds on 0.1.6 and keeps a single node for the
actual native split wrapper. Tree descendants remain siblings of that wrapper,
and its twisty is outside the native pane container. The separate
`uc-tree-tabs-split-state` key stores the session's identity on its real panes.

Disposable macOS Zen 1.24.1b reproduced two native gaps: creating a split
hoisted it out of an ordinary group, and restart flattened split-folder
placement even with Advanced Tab Groups. Creation now returns the same wrapper
to the source slot. The `ucTreeContainer` property alongside a copied native
session entry restores that wrapper's folder/slot without rewriting its layout.
The hooks install before startup restoration; ATG still owns ordinary wrapper
hierarchy and header collapse.

The earlier 0.2.0 source was tested separately against a simple nested
split/collapse/reveal case. That case did not reproduce the historic missing
row on this Zen version; the historic root cause remains unestablished. Its
implementation was not restored as the new feature.

The focused suite passed 118 checks with ATG 3.10.0 and Multi Tab Move 0.2.0:
native folders and ordinary groups, trusted context-menu/keyboard nesting,
split-under-split trees, visible rows/panes, independent collapse, adding third
and fourth panes, the real New Split shortcut and cancellation, pane closure,
whole-row middle-click closure, separation, reversed ancestor/descendant
combination, pointer-drag folder moves, Space moves, unloaded children,
document/draft/request preservation, hot reload and settings changes.

A graceful quit/restart passed 13 verification checks for two-, three- and
four-pane split trees: parent roles, collapse, folder hierarchy, order, native
layouts, focused tab and visible restored panes. The fixture explicitly enables
Zen's “continue where left off” setting to test focus restoration; when disabled,
Zen correctly chooses its empty startup tab. These are test-profile settings.
The split restore suite also passed all 13 checks without ATG, and the existing
11-node folder-tree restart fixture retained its hierarchy and native split.

Existing suites passed: 26 ordinary-group, 61 folder, four sleeping-child,
148 Multi Tab Move, 26 core, 17 branch, 21 Glance-promotion, 41 keyboard,
31 Auto Glance, 36 Keyword Tab Search, 195 split-extension, 63 adaptive-layout,
114 split-close and 15 split-regression checks. The 14 modifier/hook Node tests
and 11 installer tests passed. Promotion coverage now expects an expanded
Glance from a split to become a tree child beside that split.

Shortcut fixtures now reinsert the keyset after assigning their test binding.
Without that step, Gecko retained the previous binding and trusted
Ctrl+Cmd+Shift+T input did not invoke the command. The native command itself
worked. This is a test setup correction, not a change to browser shortcuts.
Browser gestures were trusted WebDriver input on macOS; physical mouse input
and Windows desktop behavior remain unverified.

The rendered browser showed a three-pane split under a parent, ordinary child
tabs, and a second split as a child. Both split rows and all active panes were
visible. Reloading with a selected split branch preserved the same tab/group
objects, tree state, layouts, documents, selection, preferences and companion
controllers.

Work activated without restart: all 140 tabs and five split sessions at the
activation snapshot were preserved. Personal was updated while closed; its
preferences stayed byte-identical. Both installations matched source, retained
their enabled states and unrelated registry entries, and removed their temporary
activation helpers. Runtime activation in Personal awaits its next launch.

## v0.1.1 validation

The ordinary-tab branch-move update passed 25 existing Tree Tabs checks,
17 branch-move checks, and 25 Auto Glance regression checks in an isolated
Zen profile. These cover upward/downward reordering, nested and collapsed
branches, multi-tab moves, Space menu moves, late workspace attribute changes,
native drop handling, animation cleanup, and preserved document identities.
The macOS pointer automation did not deliver a drop event reliably; the native
drop-handler check uses a synthesized drop event.

Live checks in the existing user window confirmed collapsed-branch reordering
and cross-Space moves, with all temporary tabs removed afterward. Existing
tabs, tree relationships, split layouts, focused pages, selected tab, active
Space, and Auto Glance state were preserved.

The source/session backup and test reports are retained locally outside Git.
The ignored `.local-setup.json` records the original backup location.

## Compare versions

```sh
git log --oneline --decorate
git diff tree-tabs-prototype/prototype/v0.1.0 tree-tabs-prototype/prototype/v0.2.0 -- tree-tabs.uc.js tree-tabs.css
git show tree-tabs-prototype/prototype/v0.2.0:tree-tabs.uc.js
```

Run these commands from the collection root. The imported tags keep their
original single-project layout, with `tree-tabs.uc.js` at the root of those
historical commits. The current source is under `tree-tabs-prototype/`.

## Future prototypes

1. Check `git status` before changing files and preserve unrelated edits.
2. Start a branch for the change and commit each reviewable prototype.
3. Record validation results and tag versions that are installed.
4. Validate the live sidebar as well as isolated tests; preserve page state,
   selection, workspaces, and existing split layouts.
5. Use a revert commit to remove an installed change, retaining its history.

Git tracks source, tests, and documentation. Browser profiles, session data,
generated reports, and `.local-setup.json` stay outside version control.
The local setup file identifies the installation and backup locations.

Checking out or reverting a commit does not by itself change the running
browser. Install the chosen source into the profile's Sine mod directory and
reload the mod safely. Do not modify the signed Zen application or replace
the whole browser profile to roll back a code change.

## v0.1.2 validation

The Glance promotion update passed 21 focused promotion checks, 25 existing Tree
Tabs checks, 17 branch-move checks, and 31 Auto Glance checks in a disposable Zen
1.24b profile on macOS. These cover the native Expand command, existing sibling
order, nested/collapsed origins, unchanged drafts and document identities,
excluded origins, visible native split groups and panes, settings, saved
relationships, and unloading during promotion.

The update was installed in two existing profiles. Live checks preserved the
existing tabs, documents, tree relationships, Spaces, split layouts, and other
mod instances, with native split rows still visible. Backups and reports remain
outside Git. This update does not change the persistence schema or reintroduce
the reverted split-session tree experiment.

## v0.1.3 validation

The shortcut update passed 41 keyboard checks, 25 existing Tree Tabs checks,
17 branch-move checks, and 21 Glance-promotion checks in a disposable Zen 1.24b
profile on macOS. The shared installer's nine checks also passed.

Trusted browser input covers Alt+Shift+Right/Left from the sidebar, web pages,
and frames; browser-routed input also retains native word selection in inputs,
textareas, contenteditable elements, and the address bar. Checks preserve whole
branches, collapse state, selection, document identities, drafts, request counts,
and native split members. Modifier matching, page cancellation, untrusted events,
held keys, live settings changes, and repeated reload/unload are covered.

The persistence format and native split/group exclusions are unchanged.
Windows desktop input has not been validated. Reports and profile backups
remain outside Git.

## v0.1.4 validation

The synchronous `moveBranches` API was exercised by Multi Tab Move's 99 checks
on disposable macOS Zen 1.24.1b, including trusted WebDriver pointer dragging.
It preserves selected branches through native moves and rollback, detaches only
moved roots whose parents were not included, and retains collapsed descendants.
Native three-/four-pane split sessions move as existing wrappers; they remain
outside the tree. A browser screenshot confirmed visible split panes and rows.

The 25 core, 17 branch-move, 21 Glance-promotion and 41 keyboard checks passed
again, alongside 31 Auto Glance checks, 114 split-close checks and 11 installer
tests. The existing split-extension shortcut suite timed out even with Multi Tab
Move unloaded; it is not counted as a pass. See
[the full validation record](../multi-tab-move/VERIFICATION.md).

Live activation preserved the running profile's tabs, documents, tree state,
native split layouts, preferences and other mod instances. A second profile was
updated on disk while closed; it will activate on its next launch. No persistence
schema, keyboard actor or split-as-tree-node behavior changed. Windows desktop
input and physical mouse input remain unverified.

## v0.1.5 validation

Validated on November 17, 2026 with disposable macOS Zen 1.24.1b and Multi Tab
Move 0.1.2. The folder suite passed 61 checks: native folder creation and nested
folders, independent branch collapse, folder/section/Space moves, root outdent
boundaries, trusted keyboard and pointer gestures, empty/collapsed folder drop
targets, native nesting limits, rollback, Cmd-click children, expanded Glances,
selection close/new-Space actions, and hot reload.

Four additional sleeping-child checks confirm that native and selection-based
folder/pin moves preserve the tree and focus without loading the child or
requesting its page. A real graceful quit/restart preserved native folders,
parent relationships, collapse flags, order, and the split layout returned by
Zen's session-store API. The rendered sidebar showed folder trees and both
native split panes.

The existing 25 core, 17 branch, 21 promotion, 41 keyboard, 31 Auto Glance,
148 Multi Tab Move and 114 split-close checks passed, along with 11 installer
tests. The session-value format and keyboard actors are unchanged. Splits remain
native groups, outside the tree. Pointer input was driven by WebDriver; physical
macOS mouse input and Windows desktop behavior remain unverified.

## v0.1.6 validation

The affected live container was an ordinary unpinned `tab-group`, styled by
Advanced Tab Groups, rather than a native `zen-folder`. Version 0.1.5 excluded
that container and hid both the menu and shortcut. A disposable reproduction
confirmed the failure before the change and exercised the restored context
menu with trusted browser input afterward.

On November 17, 2026, macOS Zen 1.24.1b passed 26 ordinary-group checks both
without a companion mod and with Advanced Tab Groups 3.10.0. These cover
existing groups, menu/keyboard nesting, scope boundaries, nested groups,
independent branch collapse, native group/folder/pin/Space moves, trusted
selection dragging, sleeping children and intact split groups. Split ownership
is checked on ancestors even when individual pane attributes are absent.

A real graceful quit/restart with Advanced Tab Groups preserved nested group
wrappers, header collapse, all 11 participating tree nodes, tab order, native
folders and saved split layout. Tree Tabs owns per-tab tree state; Advanced
Tab Groups owns ordinary wrapper nesting and header collapse. Bare Zen also
restored the tab trees but flattened/expanded the ordinary wrappers. The
restart test makes that companion requirement explicit.

The 61 folder, four sleeping-child, 148 Multi Tab Move, 26 core, 17 branch,
21 promotion, 41 keyboard, 31 Auto Glance, 114 split-close and 11 installer
checks passed. The local fixture server now has a larger accept queue so its
concurrent page setup does not exceed Python's five-connection default.
An activation check with a nonempty selection preserved native groups,
documents, tree/split state, Advanced Tab Groups settings, preferences and
other controllers. No persistence schema, keyboard actor or split-as-tree-node
behavior changed. Windows desktop and physical mouse input remain unverified.

The rendered ATG sidebar showed nested ordinary-group trees alongside native
folder trees and both visible split panes. Live activation in the running
profile preserved its tabs, documents, focus, group/tree/split state,
preferences and companion controllers. The originally affected tab remained
in its unpinned group and became eligible for tree controls. The second profile
was updated while closed for its next launch; its preferences were unchanged.
