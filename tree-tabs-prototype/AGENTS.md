# Tree Tabs Prototype agent guide

## Current status

- Source baseline: **0.1.1**. Ordinary tabs support opener-based nesting,
  collapse/expand, menu-based nesting/outdenting, and session-persisted tree state.
- Moving a parent carries its entire branch in sidebar order and across Spaces.
  Nested branch moves detach the moved root; parent/child multi-selection retains
  the relationship. Closing a parent promotes its children.
- Pinned tabs, Essentials, native groups, split views, Glance, private windows,
  and Little Zen windows are deliberately outside the current tree.
- The **0.2.0 split-session experiment was reverted after split rows disappeared**.
  Its tests had passed, so they were insufficient to establish correctness.
  Do not restore that implementation as if it were a working feature.
- Historical macOS validation and its limits are documented in
  [PROTOTYPES.md](PROTOTYPES.md). Windows browser behavior remains untested.

## Implementation constraints

- Keep tree state separate from native split/group membership. A tree operation
  must not hide or rearrange excluded native split members.
- Preserve live tabs, selected page, collapse state, and relative descendant order;
  move existing tabs with Zen's APIs rather than recreating or reloading them.
- `followMovedBranches()` handles batched `TabMove` events and delayed workspace
  attribute changes. Preserve that ordering and multi-selection handling.
- Native opener information drives automatic nesting. New-tab commands,
  bookmarks, and external links are roots unless a real page opener exists.
- SessionStore relationships must survive restart. Disabling the mod restores a
  flat sidebar without closing pages; collapsing does not unload documents.
- Keep controller/manifest versions and the shared installer's CSS/controller
  file list aligned. Install into the profile, never into the signed application.

## Validation for runtime changes

From the collection root, use `node --check tree-tabs-prototype/tree-tabs.uc.js`.
With a disposable Zen profile already running and privileged debugging on
localhost (default port `2832`), run:

```sh
python3 tree-tabs-prototype/tests/integration.py --profile /path/to/test-profile --report /path/to/reports/tree.json
python3 tree-tabs-prototype/tests/branch_moves.py --profile /path/to/test-profile --report /path/to/reports/branches.json
```

Both suites verify the connected profile. Also run Auto Glance integration after
opener/click changes, and check restart restoration after persistence changes.
The recorded branch-move suite exercises a synthesized native drop; macOS pointer
automation did not reliably deliver a physical drop. Confirm actual dragging and
visible split rows manually before claiming that interaction is validated.

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
