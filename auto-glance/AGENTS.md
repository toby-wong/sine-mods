# Auto Glance agent guide

## Current status

- Source baseline: **0.2.2**. Website-created tabs, configured middle-clicks, and
  page context-menu new-tab actions can open as native Glance previews.
- Mac Command-click is an explicit ordinary-background-tab override, including
  routed links, editable documents, frames, and links inside an existing preview.
- Centering/backdrop handling and recovery from abandoned temporary split records
  are implemented. This is targeted recovery, not a general split-state reset.
- Normal, private, and Little Zen windows are supported by the implementation.
  Browser validation has been on macOS; the override uses `metaKey`, so Windows
  Ctrl-click does **not** yet get equivalent treatment.
- See [README.md](README.md) for eligibility rules and exclusions. Historical
  browser checks are represented by the suites below; reports are kept outside Git.

## Implementation constraints

- Keep parent-process routing in `auto-glance.uc.js` and trusted content clicks in
  `AutoGlanceClickChild.sys.mjs` consistent. They must agree on modifier semantics.
- Preserve Firefox's native navigation validation, principals, referrer,
  container, POST body, and opener handling. Do not replace navigation with a
  synthetic `window.open` or direct page reload.
- Command-click must preserve the selected source page. Automatic Glance must
  continue yielding to explicit splits, separate popup windows, and different
  destination containers.
- Treat connected but unloaded tabs as live tabs. Repair only the abandoned
  temporary split condition; do not reset working native split groups.
- The CSS and actor module are loaded from within the controller, although they
  are not manifest entry points. Keep them in the shared installer's file list.
- Keep script metadata, runtime `VERSION`, manifest version, and cache-busting
  actor/style URLs consistent. Unload/reload must remove hooks, actors, listeners,
  and visual markers without losing pages.

## Validation for runtime changes

From the collection root, syntax-check both JavaScript files with `node --check`.
The following suites require an already running disposable Zen profile and a
privileged localhost debugger, default port `2832`. Each accepts `--profile`,
`--port`, and `--report`, and rejects a mismatched/non-test profile:

- `auto-glance/tests/integration.py`: real click gestures, POST/opener/container
  behavior, native split compatibility, layout, and unload.
- `auto-glance/tests/contexts.py`: private and Little Zen windows.
- `auto-glance/tests/stale_splits.py`: interrupted-preview recovery without
  reloading either page, plus preservation of working splits.

Keep reports outside Git. For click-hook changes, also exercise the split fork;
for opener changes, exercise Tree Tabs. Verify the centered preview and blurred
background visually as well as checking state/geometry.

## Potential future direction

- Implement Windows Ctrl-click parity using platform-aware checks in both click
  layers, preserving plain click, Shift-click, and Alt-click semantics.
- Measure repeated open/close and hot-reload cycles for retained actors,
  listeners, or tabs before attempting performance optimizations.
- Strengthen compatibility checks around Zen's Glance/split internals and add
  targeted regressions when upstream behavior changes.

These are proposals. Do not present Windows parity or a diagnosed memory leak as
existing behavior; update this guide alongside implementation and evidence.
