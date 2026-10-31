# Little Zen agent guide

## Current status

- Source baseline: **0.1.0**, a working Sine prototype. Historical macOS browser
  validation is recorded in [VERIFICATION.md](VERIFICATION.md); Windows browser
  behavior has not been tested.
- Compact temporary windows, native search keywords, the Space picker, live-tab
  promotion, private-window handling, and opt-in external-link routing exist.
- `Command+Option+N` is an optional Hammerspoon integration. Windows has the
  browser menu/context-menu entry points and `Ctrl+O` promotion, but no supplied
  system-wide launcher.
- Temporary windows intentionally do not restore after a browser restart.
  [README.md](README.md) describes the user-facing behavior; [PLAN.md](PLAN.md)
  records the original implementation and completed scope.

## Implementation constraints

- Keep promotion as adoption of the existing tab. Preserve document identity,
  history, drafts, container identity, and private/public boundaries.
- Keep native address-bar/search behavior and independent blank-window handling;
  do not make temporary tabs participate in normal Space synchronization.
- Changes to external-link routing must remain opt-in and limited to HTTP/HTTPS.
- Exercise closing the original main window, moving into another Space, and
  disabling the mod. Unloading must retain open pages and restore patched hooks.
- Keep UI styling scoped to Little Zen windows. Compact mode can place the native
  address bar inside a different titlebar wrapper.
- Use the collection's [shared installer](../scripts/install.py). This directory's
  older install/uninstall scripts are macOS-specific. If runtime files change,
  update the shared installer's file list; never patch the signed Zen application.

## Validation for runtime changes

From the collection root, use `node --check little-zen/little-zen.uc.js` for syntax.
The Python suites require a separately launched disposable Zen profile with
privileged debugging available on localhost; their default port is `2832`.
They verify that the connected profile matches `--profile` and has `test-profile`
in its name. Each accepts `--profile`, `--port`, and `--report`:

- `little-zen/tests/runtime_test.py`: search, containers, promotion, routing,
  privacy, and unload.
- `little-zen/tests/lifecycle_test.py`: promotion after closing the main window.
- `little-zen/tests/toolbar_test.py`: compact layout, destination controls, and
  actual keyboard input.

Use an output directory outside the repository for reports. Validate the
Hammerspoon launcher with another application focused when changing that
integration; a browser API call alone does not establish global-shortcut behavior.

## Potential future direction

- Validate Windows layout, native menus, and promotion before claiming support;
  investigate a Windows launcher separately from the browser mod.
- Add compatibility checks for changed Zen window/adoption APIs, with a clear
  failure state rather than partially creating a temporary window.
- Expand accessibility and multi-window lifecycle coverage, including focus
  restoration when several temporary windows share a destination.

These are proposed next steps, not implemented features. Update this guide when
the source baseline or validation evidence changes.
