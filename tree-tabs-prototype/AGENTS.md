# Tree Tabs Prototype agent guide

## Current status

- Source baseline: **0.1.3**. Ordinary tabs support opener-based nesting,
  collapse/expand, menu-based nesting/outdenting, and session-persisted tree state.
- Alt+Shift+Right nests the selected ordinary tab under its previous ordinary
  tab in the same Space; Alt+Shift+Left outdents one level. Descendants follow,
  preserving focus, live pages, and collapse state. A Sine checkbox controls
  `uc.tree-tabs.keyboard-shortcuts`, enabled by default.
- Moving a parent carries its entire branch in sidebar order and across Spaces.
  Nested branch moves detach the moved root; parent/child multi-selection retains
  the relationship. Closing a parent promotes its children.
- Pinned tabs, Essentials, native groups, split views, Glance, private windows,
  and Little Zen windows are deliberately outside the current tree.
- A Glance promoted with **Expand to new tab** becomes a child of its ordinary
  originating tab when automatic nesting is enabled. Capture the native parent
  before promotion clears its metadata, then nest after native completion.
  Existing siblings, nested ancestry, drafts, and live documents are preserved.
- The **0.2.0 split-session experiment was reverted after split rows disappeared**.
  Its tests had passed, so they were insufficient to establish correctness.
  Do not restore that implementation as if it were a working feature.
- Historical macOS validation and its limits are documented in
  [PROTOTYPES.md](PROTOTYPES.md). Windows browser behavior remains untested.
- Current validation on disposable macOS Zen 1.24b: 41 keyboard checks, 25 core
  checks, 17 branch-move checks, and 21 Glance-promotion checks passed, alongside
  the shared installer's nine checks.

## Implementation constraints

- Keep tree state separate from native split/group membership. A tree operation
  must not hide or rearrange excluded native split members.
- Preserve live tabs, selected page, collapse state, and relative descendant order;
  move existing tabs with Zen's APIs rather than recreating or reloading them.
- `followMovedBranches()` handles batched `TabMove` events and delayed workspace
  attribute changes. Preserve that ordering and multi-selection handling.
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
```

All suites verify the connected profile. Also run Auto Glance integration after
opener/click changes, and check restart restoration after persistence changes.
The recorded branch-move suite exercises a synthesized native drop; macOS pointer
automation did not reliably deliver a physical drop. Confirm actual dragging and
visible split rows manually before claiming that interaction is validated.
The keyboard suite covers both content-targeted input and input routed through
browser chrome. Create untrusted test events in the served page's own realm:
events constructed by the privileged test sandbox can be trusted by Gecko.

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
