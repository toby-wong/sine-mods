# Alt-click Split View agent guide

## Current status

- Source baseline: **1.4.4-local**, a fork of Kostiantyn Kugot's **1.4.2** mod.
  Preserve the upstream author and [MIT license](LICENSE).
- A capturing content actor handles routed links and frames before page handlers.
  Option/Alt-click opens a native split while preserving the original document.
- Links inside Glance use the promoted live preview. Pinned/Essential sources are
  reused, with temporary pin state restored when the managed split is separated.
- Hover-based pane focus is optional. A separate optional Hammerspoon guard
  preserves Option-click when focusing a background Zen/Arc window.
- Parent-hook tests cover Windows, macOS, and Linux tab accelerators and Glance
  conflicts. Live browser evidence is from macOS on Zen 1.24b; Windows desktop
  input has not been validated. See
  [PATCH-NOTES.md](PATCH-NOTES.md) and [VERIFICATION.md](VERIFICATION.md).
- Current validation: 8 Node tests, 15 live split cases, 25 Auto Glance checks,
  plus unload and restart restoration checks passed in a disposable profile.

## Implementation constraints

- This fork retains upstream's mod ID and replaces that mod in a profile. Keep
  its homepage/update source pointing to this fork; the shared local installer
  disables automatic updates so upstream cannot silently replace the fixes.
- Keep the actor (`AltClickSplitViewChild.sys.mjs`), parent click hook, and
  preferences (`settings.uc.js` / `preferences.json`) in agreement.
- An unset `zen.glance.activation-method` falls back to `ctrl` in native Zen and
  the actor. Use that same fallback in the parent hook and settings. Synthesize
  only the platform's tab accelerator: Meta on Darwin, Ctrl elsewhere.
- Continue through Firefox's native link validation and navigation parameters.
  Preserve modifier precedence and coexistence with Auto Glance's click hook.
- Native pinned/unpinned splitting can duplicate the source. Preserve the patch
  that reuses live pages; document identity and draft preservation are required.
- Preserve SessionStore return state for pins/Essentials and the distinction
  between hot reload (keep managed splits) and disable (separate/restore them).
- Do not silently install or broaden the Hammerspoon guard: it also affects
  background clicks in other applications. Keep it separate from browser files.
- If runtime resources change, update the collection's shared installer. Keep
  changes in the profile and never modify the signed Zen application.

## Validation for runtime changes

From the collection root:

```sh
node --test alt-click-split-view/tests/alt-click-split-view.test.cjs
```

For browser behavior, `alt-click-split-view/tests/regression.py` accepts
`--profile`, `--port` (default `2832`), `--report`, and repeatable `--case`.
It requires a separately launched disposable profile with localhost Marionette,
and validates the profile identity before running. On Zen 1.24b, launch the test
process with `--marionette` and `MOZ_REMOTE_ALLOW_SYSTEM_ACCESS=1` in its
environment; set `marionette.port` to the chosen port in that profile. The
`--allow-system-access` flag alone does not enable privileged access in this
version. Never enable automation in the everyday profile.

Exercise routed links, frames, Glance, pins/Essentials, the four-pane limit,
repeated operations, reload/unload, and restart restoration. Assert document and
browsing-context identity, drafts, and request counts; seeing two panes alone
does not prove the source avoided a reload. Run Auto Glance integration when
changing shared click handling, and test actual background-window clicks when
changing the Hammerspoon guard.

## Potential future direction

- Keep the local fixes as a small, reviewable patch against upstream; compare new
  upstream versions before adopting them rather than replacing the fork blindly.
- Validate Windows modifiers and expand compatibility checks for changed native
  splitting/adoption APIs.
- Improve multi-window, focus, and repeated reload coverage, including pin-state
  restoration when other mods also wrap the native handlers.

These are proposed directions. Update this guide with new baseline versions and
validation limits when work lands.
