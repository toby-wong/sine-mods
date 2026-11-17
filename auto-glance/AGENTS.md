# Auto Glance agent guide

## Current status

- Source baseline: **0.2.4**. Website-created tabs, configured middle-clicks, and
  page context-menu new-tab actions can open as native Glance previews.
- Mac Command-click and Windows/Linux Ctrl-click are explicit ordinary-background-tab
  overrides, including routed links, editable documents, frames, and links inside
  an existing preview. Both click layers select the modifier via `Services.appinfo.OS`.
- The content actor also guards native `ZenGlanceChild.on_click` for that exact
  eligible background gesture. Mousedown/keydown create the actor before native
  Glance handles a click; capture alone is insufficient when native Glance uses
  the same key. The native actor can otherwise open an extra foreground preview.
  Ownership is scoped to a WindowGlobal and removed in `didDestroy`.
- Centering/backdrop handling and recovery from abandoned temporary split records
  are implemented. This is targeted recovery, not a general split-state reset.
- Sine's **Extra backdrop opacity** control adds a Space-coloured layer only
  behind Glance. It defaults to 20%, ranges from 0% to 100%, and applies through
  a CSS variable without reloading pages. Sidebar and preview opacity are
  unchanged. All 34 integration checks passed on Zen 1.24.1b on macOS, including
  the actual Sine opacity control, dynamic light/dark colours, existing click
  gestures, frames, a conflicting native Glance shortcut, blur, centering, and
  document preservation. Six private/Little Zen checks, 15 split regressions,
  26 Tree Tabs checks, 32 combined platform/Alt-click Node checks, and 11 installer
  checks passed. The split-view Glance screenshot was visually inspected.
  Interrupted-split recovery has earlier 0.2.3 coverage; its code is unchanged.
- Normal, private, and Little Zen windows are supported by the implementation.
  Windows/macOS/Linux routing has automated handler coverage; live browser
  validation has been on macOS. Physical Windows/Linux input remains unverified.
- See [README.md](README.md) for eligibility rules and exclusions. Historical
  browser checks are represented by the suites below; reports are kept outside Git.

## Implementation constraints

- Keep parent-process routing in `auto-glance.uc.js` and trusted content clicks in
  `AutoGlanceClickChild.sys.mjs` consistent. They must agree on modifier semantics.
- Preserve Firefox's native navigation validation, principals, referrer,
  container, POST body, and opener handling. Do not replace navigation with a
  synthetic `window.open` or direct page reload.
- Command/Ctrl-click must preserve the selected source page. Automatic Glance must
  continue yielding to explicit splits, separate popup windows, and different
  destination containers.
- Retain `uc.auto-glance.cmd-click-background` as the preference key so existing
  settings and Sine Sync keep working. Reject extra modifiers, non-primary clicks,
  inputs, downloads, and non-HTTP(S) links in the trusted capture path.
- The native Glance wrapper must suppress only a matching live actor's eligible
  background gesture; keep its other gestures and mousedown positioning intact.
  On actor destruction, remove only that actor's ownership, and restore only an
  owned method. A later actor for the same WindowGlobal must survive old cleanup.
- Treat connected but unloaded tabs as live tabs. Repair only the abandoned
  temporary split condition; do not reset working native split groups.
- The CSS and actor module are loaded from within the controller, although they
  are not manifest entry points. Keep them in the shared installer's file list.
- Keep script metadata, runtime `VERSION`, manifest version, and cache-busting
  actor/style URLs consistent. Unload/reload must remove hooks, actors, listeners,
  and visual markers without losing pages.

## Validation for runtime changes

From the collection root, syntax-check both JavaScript files with `node --check`.
Run `node --test auto-glance/tests/background-click.test.cjs
alt-click-split-view/tests/alt-click-split-view.test.cjs` for platform semantics
and both parent-hook load orders. These execute the actual handlers against a
native-navigation contract; they are not Windows browser/OS input tests.
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

- Validate Ctrl-click with native desktop input on Windows and Linux, including
  Zen's default Ctrl Glance shortcut and the shared mod installation.
- Measure repeated open/close and hot-reload cycles for retained actors,
  listeners, or tabs before attempting performance optimizations.
- Strengthen compatibility checks around Zen's Glance/split internals and add
  targeted regressions when upstream behavior changes.

These are proposals. Do not present physical Windows validation or a diagnosed
memory leak as established; update this guide alongside implementation and evidence.
