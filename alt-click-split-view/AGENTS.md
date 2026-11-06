# Alt-click Split View agent guide

## Current status

- Source baseline: **1.4.6-local**, a fork of Kostiantyn Kugot's **1.4.2** mod.
  Preserve the upstream author and [MIT license](LICENSE).
- A capturing content actor handles routed links and frames before page handlers.
  Option/Alt-click opens a native split while preserving the original document.
- Links inside Glance use the promoted live preview. Pinned/Essential sources are
  reused, with temporary pin state restored when the managed split is separated.
- Hover-based pane focus is optional. A separate optional Hammerspoon guard
  preserves Option-click when focusing a background Zen/Arc window.
- Automatic direction is enabled by default through
  `uc.alt-click-split-view.adaptive-direction`. New default two-pane splits use
  a horizontal divider when `outerHeight > outerWidth`; other window shapes
  retain the native default. Covers modifier-click, New Empty Split, and
  Glance's Split button. The Sine and Tab Management controls update live.
- New Empty Split extends an existing two- or three-pane group through its
  assigned native shortcut. It adds a temporary leaf to the existing layout,
  then uses native tab submission and `splitTabs` to commit the new page.
  URLs and Keyword Tab Search work; the native four-pane limit remains.
  Cancellation, losing focus, closing a member, separating the group, disabling
  the mod, or hot reload removes only the unfinished pane.
- Parent-hook tests cover Windows, macOS, and Linux tab accelerators and Glance
  conflicts. Live browser evidence is from macOS on Zen 1.24b; Windows desktop
  input has not been validated. See
  [PATCH-NOTES.md](PATCH-NOTES.md) and [VERIFICATION.md](VERIFICATION.md).
- Current validation: 14 Node tests, 195 existing-split checks, 63 adaptive
  checks, 15 split regressions, 36 Keyword Tab Search checks, and 31 Auto Glance
  checks passed. Eleven cold-restart checks restored three panes, their saved
  drafts and layout, excluded an unfinished fourth pane, and added a fourth
  afterward without reloading the restored documents. The shared installer's
  nine tests also passed. All browser checks used a disposable macOS profile
  on Zen 1.24b; normal and private windows are covered.

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
- Adapt only new default pairs. Preserve explicit `gridType`/side choices,
  existing split groups, and session restoration. Never reflow on resize or
  load pages to change direction.
- Native Zen 1.24b disables `cmd_zenNewEmptySplit` for any split; simply enabling
  that command creates an overlapping two-tab group. Keep the existing-group
  command wrapper and temporary leaf lifecycle together. Never replace the
  original live tabs to extend a group.
- Use the native URL-bar close token. Its close event is only emitted while
  focused, so the owned close callback also handles closure after a blur.
  Preserve native search-mode Escape behavior and later callback owners.
- Exclude the temporary empty leaf from serialized session data without mutating
  the live layout. Private windows can have an empty string for the empty tab's
  ID. Borrowed Essentials can lack a workspace attribute; capture the group's
  effective workspace when starting the pending pane.
- On cancellation/unload, cancel owned timers and animation frames and restore
  only owned method descriptors. An unloaded wrapper must remain inert if
  retained by another mod. Completed splits survive hot reload.
- Glance passes `vsep` explicitly for its default Split action. The adaptive
  wrapper tracks the exact parent/preview pair during that asynchronous
  promotion; never use a global flag that could affect an unrelated split.
- Remove adaptive wrappers, then existing-group command wrappers, then the
  page-preservation wrapper during unload.
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

Run `tests/adaptive.py --profile ... --port ... --report ...` for geometry,
real keyboard/Option-click input, Glance, and the settings toggle. Its profile
needs this collection's Keyword Tab Search and Auto Glance mods enabled.
Use a fresh disposable profile after a deliberately failing empty-split test:
an interrupted pending native split can leave its shared placeholder attached.
The old 1.4.4-local build fails the tall-window placeholder check.

Run `tests/extend.py --profile ... --port ... --report ...` for adding third and
fourth panes with real keyboard input, URLs, keyword searches, unequal pane
sizes, mixed layouts, pins/Essentials, private windows, cancellation, blur,
member closure, session serialization, and reload/unload. The 1.4.5-local
baseline leaves the assigned New Empty Split command disabled in a two-pane
group. Escape may first leave a retained search mode before cancelling.

## Potential future direction

- Keep the local fixes as a small, reviewable patch against upstream; compare new
  upstream versions before adopting them rather than replacing the fork blindly.
- Validate Windows modifiers and expand compatibility checks for changed native
  splitting/adoption APIs.
- Improve multi-window, focus, and repeated reload coverage, including pin-state
  restoration when other mods also wrap the native handlers.

These are proposed directions. Update this guide with new baseline versions and
validation limits when work lands.
