# Multi Tab Move agent guide

## Current status

- Version 0.2.0: Shift + left-click toggles individual sidebar
  rows, with owned selection styles and a pointer drag handler.
- Move entire selected Tree Tabs branches, native split sessions, and selected
  folder/group headers. Reuse browser, tab, group and split layout objects.
- Same-window ordering, folder transfers and Space moves. Space moves preserve
  pins; explicit folder/section drops can change the pin state of ordinary tabs
  and complete native split groups.
- Integrates with Tree Tabs 0.3.0's `moveBranches` transaction.
  Require its `supportsSplitTrees` capability before a selection action when
  Tree Tabs is present and enabled; older controllers cannot retain split branches.
  A pane's selected unit is the native split wrapper, which can own tree
  descendants. Resolve anchor ancestry and the last descendant through that
  same canonical unit; use the visible split row for pointer destinations.
- The middle of a native folder or ordinary group header is an inside-container
  destination, including empty or collapsed containers. Header edges reorder the
  container itself. Child row targets stay in that immediate folder/group but
  outside any unrelated tree branch. Read destination pin state instead of
  treating every group as a pinned folder. Split/Live Folder ancestors are
  never destinations.
- The selection menu can close the entire selection or create a named Space
  containing it. Close uses native beforeunload preflight and bulk removal;
  cancelling keeps all tabs. New Spaces are created inactive, then populated
  through the existing move transaction before being activated.
- macOS Zen 1.24.1b: 148 integration checks and 61 folder checks passed,
  including trusted WebDriver pointer dragging and native menu/dialog actions.
  Four sleeping-child checks, a real folder/tree/split restart comparison,
  the existing tree/Glance suites, 114 split-close checks and 11 installer tests
  also passed.
  See [VERIFICATION.md](VERIFICATION.md) for the split-shortcut test limitation.
- Version 0.1.3 also passed 26 ordinary-group checks both without companion
  mods and with Advanced Tab Groups 3.10.0. Header drops, child-row placement,
  pin state, sleeping children and complete split wrappers stay intact.
  ATG-backed restart and reload preservation were checked separately; do not
  make Tree Tabs responsible for ATG's group-wrapper persistence.
- Windows desktop input and physical mouse input remain unverified.
- Version 0.2.0 passed 118 split-tree checks, including selected split branches,
  nested split sessions, actual WebDriver pointer moves, sleeping children,
  folder/Space moves and reload. The 148 existing selection checks and all
  tree/Glance/keyword/split regressions passed. Split-tree restart passed with
  and without ATG. See [VERIFICATION.md](VERIFICATION.md) for exact coverage.

## Constraints

- Never use native `multiselected` as this mod's selection state. That would also
  change Close Tab semantics and let native drag packing reorder branches.
- Only the explicit Close selected tabs command closes this mod's selection.
  Use `runBeforeUnloadForTabs` before `removeTabs` with `skipPermitUnload`,
  native menu metrics and `closeWindowWithLastTab: false`. Never bypass the
  preflight or turn ordinary close controls into selection-wide close actions.
- After prompts or asynchronous preparation, recheck the owning instance,
  selection, source Space and Tree Tabs readiness. A disabled/unloaded instance
  or a changed selection must not complete a delayed close/move. Ignore duplicate
  close/create commands while an action is pending.
- Name cancellation/blank names must not create a Space. Keep the source
  container and existing tab/browser identities. A failed move may delete only
  its own unused, empty Space; never remove a Space that acquired tabs/folders.
- Cancel native `dragstart` only for this mod's selected rows. Track the trusted
  pointer gesture and apply moves on mouseup; Escape, leaving the window and
  window blur cancel it. Hit-test the destination instead of trusting a
  captured event's source target.
- Do not clone/reopen URLs, ungroup or rebuild split sessions. Split tree
  membership belongs to Tree Tabs; Multi Tab Move carries its existing wrapper
  and follows that controller's parent API. The earlier experiment hid split
  rows, so always verify rendered rows and panes alongside state assertions.
- Selection is explicit; the focused tab is not implicitly added. Tree
  descendants and all panes of a selected split must move with their owner.
- Native folder wrappers move intact when their header is selected. Ordinary
  child branches can move independently; never insert a selection into an unrelated
  tree branch as a side effect of dropping next to one of its children.
- Never allow a folder to move into itself/its descendants or a Live Folder,
  or bypass Zen's native folder-depth limit.
  Restore native pin state as well as DOM position and Space attributes during
  rollback. Do not convert a non-split group wrapper between pinned sections.
- Use native move APIs. Preserve live browser identities, collapsed state,
  order within the selection, native group identity, split layout and pane focus.
- Keep Space changes synchronous inside the tree transaction. A later Space
  activation may be asynchronous, but must not run late UI edits after unload.
- Exact trusted Shift-left-click only; page content, embedded controls,
  middle-click, accelerator-click and ordinary native drag remain native.
- Track all listeners, styles, timers and UI; clean up on disable/hot reload.
  No polling, actors, app-bundle edits or remote debugging in daily profiles.
- Install only this mod and its needed Tree Tabs update, with private backups
  and checks that unrelated profile state remains intact.

## Validation

- `node --check multi-tab-move/multi-tab-move.uc.js`
- `python3 multi-tab-move/tests/integration.py --profile ... --port ... --report ... --pointer-drag`
- Tree Tabs integration, branch moves, Glance promotion and keyboard suites.
- Split extension/closure regression suites if moving changes split behavior.
- Installer tests: `python3 -m unittest discover -s tests -v`
- Cover trusted Shift-click, deselection, source focus, inactive sleeping tabs,
  actual drag gestures, mixed tree/split ordering, collapsed descendants,
  multi-pane splits, Space moves, repeated moves, cancellation, hot reload,
  rollback, unchanged document IDs/drafts/request counts and visible split rows.
- Exercise real context-menu commands and native naming/beforeunload dialogs,
  cancellation/acceptance, unrelated tabs, failed Space creation cleanup,
  active split focus, and unload while awaiting close permission.
- Report separately whether a drop was synthesized or driven by real pointer
  input. Passing DOM tests alone does not prove drag interaction works.

## Potential future direction

- Optional contiguous range selection as an alternative gesture.
- Keyboard commands for moving the selected block.
- Cross-window transfers after verifying tree IDs, split ownership and native
  adoption without page reloads.
- Physical Windows input validation and accessibility announcements.
