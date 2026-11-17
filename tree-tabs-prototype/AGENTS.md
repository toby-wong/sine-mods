# Tree Tabs Prototype agent guide

## Current status

- Source baseline: **0.1.6**. Ordinary tabs support opener-based nesting,
  collapse/expand, menu-based nesting/outdenting, and session-persisted tree state.
- Native folders, ordinary tab groups and ordinary pinned tabs can contain trees.
  A parent and child share an immediate group/folder, Space and pinned section. The physical
  container determines ownership; `tab.group` can instead report the temporary
  collapsed-pins display group.
- Alt+Shift+Right nests the selected ordinary tab under its previous ordinary
  tab in the same folder/section and Space; Alt+Shift+Left outdents one level.
  Outdenting a root does not eject it from its folder. Descendants follow,
  preserving focus, live pages, and collapse state. A Sine checkbox controls
  `uc.tree-tabs.keyboard-shortcuts`, enabled by default.
- Moving a parent carries its entire branch in sidebar order and across folders,
  pinned sections and Spaces. Moving a native folder keeps its internal trees.
  Nested branch moves detach the moved root; parent/child multi-selection retains
  the relationship. Closing a parent promotes its children.
- `moveBranches(tabs, callback)` lets Multi Tab Move perform a synchronous
  native move while keeping internal parent links and collapse state. Only
  roots whose parent is outside the moving set detach. Splits remain excluded
  from the tree; the caller moves their native wrappers separately.
- Essentials, live folders, split views, Glance, private
  windows and Little Zen windows remain outside the tree. New ordinary opener
  tabs and promoted Glances enter their source's folder before attaching; an
  explicit different folder destination is respected.
- Existing Advanced Tab Groups containers are ordinary `tab-group` elements,
  not `zen-folder` elements. Preserve their group identity and pin state.
  Reject split groups and Live Folders anywhere in the ancestor chain; sleeping
  split panes may have no individual split attributes. Observe the group-level
  `split-view-group` attribute as well as pane-level split changes.
- ATG owns ordinary group-wrapper hierarchy/header-collapse persistence.
  Tree Tabs owns per-tab parent links and branch collapse. Do not duplicate
  ATG's `tabGroupParents` / `tabGroupCollapsedStates` window state. The restart
  suite's `--advanced-tab-groups` flag verifies both owners together; bare Zen
  restores the tab trees but does not retain nested ordinary-group wrappers
  or collapsed ordinary-group headers.
- Expose `supportsGroupTrees` for Multi Tab Move 0.1.3. Its header and child-row
  destinations must retain the immediate ordinary group rather than hoisting
  the row outside it or pinning it as if every group were a native folder.
- A Glance promoted with **Expand to new tab** becomes a child of its ordinary
  originating tab when automatic nesting is enabled. Capture the native parent
  before promotion clears its metadata, then nest after native completion.
  Existing siblings, nested ancestry, drafts, and live documents are preserved.
- The **0.2.0 split-session experiment was reverted after split rows disappeared**.
  Its tests had passed, so they were insufficient to establish correctness.
  Do not restore that implementation as if it were a working feature.
- Historical macOS validation and its limits are documented in
  [PROTOTYPES.md](PROTOTYPES.md). Windows browser behavior remains untested.
- Previous 0.1.3 validation on disposable macOS Zen 1.24b: 41 keyboard checks, 25 core
  checks, 17 branch-move checks, and 21 Glance-promotion checks passed, alongside
  the shared installer's nine checks.
- Version 0.1.4 passed those browser suites again on Zen 1.24.1b, plus 99 Multi
  Tab Move checks, 31 Auto Glance checks, 114 split-close checks and 11 installer
  tests. Multi Tab Move's own pointer gestures and visible native split panes
  were checked. See its [validation record](../multi-tab-move/VERIFICATION.md)
  for the independent split-shortcut timeout and physical-input limitations.
- Version 0.1.5 passed 61 folder checks, four sleeping-child checks and a real
  restart comparison of native folder hierarchy, tree state/order/collapse and
  saved split layout on disposable macOS Zen 1.24.1b. The existing 25 core,
  17 branch, 21 promotion, 41 keyboard, 31 Auto Glance, 148 Multi Tab Move and
  114 split-close checks passed, as did all 11 installer tests. A rendered
  browser screenshot confirmed nested rows and two visible split panes.
- Version 0.1.6 passed 26 ordinary-group checks both alone and with Advanced
  Tab Groups 3.10.0, including trusted context-menu, keyboard and pointer input.
  A real restart with ATG retained wrapper nesting/header collapse, 11 tree
  nodes, native folders and saved split layout. The existing suites passed:
  61 folder, four sleeping-child, 148 selection, 26 core, 17 branch,
  21 promotion, 41 keyboard, 31 Auto Glance, 114 split-close and 11 installer
  checks. Reloading with a nonempty selection preserved group objects and
  ATG window settings as well as existing tab/document/tree/split state.

## Implementation constraints

- Keep tree state separate from native folder/split/group membership. A tree
  operation must not hide or rearrange excluded native split members. Native
  folder collapse and branch collapse retain separate state.
- Preserve live tabs, selected page, collapse state, and relative descendant order;
  move existing tabs with Zen's APIs rather than recreating or reloading them.
- `followMovedBranches()` handles batched `TabMove` events and delayed workspace
  attribute changes. Preserve that ordering and multi-selection handling.
- `moveBranches` must suppress intermediate move events, update the moved
  nodes' folder, pin and Space baselines, then reconcile once. The callback must be synchronous;
  a throwing callback must restore native placement before propagating its
  error, so failed transactions preserve saved tree relationships.
- Native opener information drives automatic nesting. New-tab commands,
  bookmarks, and external links are roots unless a real page opener exists.
- The `fullyOpenGlance` wrapper must skip `{forSplit:true}`, preserve native
  arguments/results/errors, and restore only its own wrapper. Recheck eligibility
  and settings after awaiting native completion; an unloaded instance must not
  perform a late attachment.
- SessionStore relationships must survive restart. Disabling the mod restores a
  flat sidebar without closing pages; collapsing does not unload documents.
- Keep controller/manifest versions and the shared installer's CSS/controller
  file list aligned. Install into the profile, never into the signed application.
- Keyboard handling uses chrome keys and a content actor. On macOS, non-reserved
  native keys alone lose Option+Shift+Arrow to page selection even outside editors.
  The actor accepts only trusted, exact gestures outside editors, respects page
  cancellation, and ignores repeats. Chrome capture handles sidebar focus before
  native tab-strip arrow handling; it must skip browser/content targets.
- The parent rechecks the selected browser and ordinary-tab eligibility before
  acting. Match an owning window by its document: `browser.ownerGlobal` is not
  necessarily the same wrapper used by Sine's script. Register actors for
  untrusted web processes explicitly; unregister when the last owning window
  unloads. Context messages refresh on page load, selection, and settings changes.
- Preserve `TreeTabsShortcutChild.sys.mjs` and `TreeTabsShortcutParent.sys.mjs` in
  installations. Do not reserve editor selection shortcuts or bind Windows'
  Alt+Tab application switcher. Actor modules are cached for the process lifetime;
  restart only the disposable test process when developing module changes.

## Validation for runtime changes

From the collection root, use `node --check tree-tabs-prototype/tree-tabs.uc.js`.
With a disposable Zen profile already running and privileged debugging on
localhost (default port `2832`), run:

```sh
python3 tree-tabs-prototype/tests/integration.py --profile /path/to/test-profile --report /path/to/reports/tree.json
python3 tree-tabs-prototype/tests/branch_moves.py --profile /path/to/test-profile --report /path/to/reports/branches.json
python3 tree-tabs-prototype/tests/glance_promotion.py --profile /path/to/test-profile --report /path/to/reports/promotion.json
python3 tree-tabs-prototype/tests/keyboard.py --profile /path/to/test-profile --report /path/to/reports/keyboard.json
python3 tree-tabs-prototype/tests/folders.py --profile /path/to/test-profile --report /path/to/reports/folders.json
python3 tree-tabs-prototype/tests/folder_sleeping.py --profile /path/to/test-profile --report /path/to/reports/sleeping.json
python3 tree-tabs-prototype/tests/group_containers.py --profile /path/to/test-profile --report /path/to/reports/groups.json
```

All suites verify the connected profile. Also run Auto Glance integration after
opener/click changes, and check restart restoration after persistence changes.
The recorded branch-move suite exercises a synthesized native drop; macOS pointer
automation did not reliably deliver a physical drop. Confirm actual dragging and
visible split rows manually before claiming that interaction is validated.
The keyboard suite covers both content-targeted input and input routed through
browser chrome. Create untrusted test events in the served page's own realm:
events constructed by the privileged test sandbox can be trusted by Gecko.

Folder tests require the additional `folder-tree-test-profile` marker. The
two-phase `tests/folder_restore.py` verifies a real process restart: run with
`--prepare --expected /path/to/expected.json --report /path/to/prepare.json`,
quit/restart only that disposable browser, then run without `--prepare` and with
a fresh report path. It checks persisted native folders, tree order/collapse,
ordinary-group trees and native split restoration. Add `--advanced-tab-groups`
to both phases when ATG is installed to also verify ordinary wrapper nesting
and header collapse. The base fixture keeps ordinary wrappers top-level and
expanded because bare Zen does not persist those wrapper features.

## Potential future direction

- Explore a split session as a single tree node, preserving its native group and
  all visible panes. Reproduce the old missing-row regression first; isolate the
  prototype and validate move, collapse, close, restart, and actual drag behavior.
- Add deliberate drag-to-reparent only after defining drop targets and testing
  nested and multi-selected branches across Spaces.
- Define cross-window tree transfer semantics and validate Windows behavior.
  Neither cross-window synchronization nor drag-to-reparent exists today.

Treat these as separate proposals. Keep this file and the prototype history
current when behavior or evidence changes.
