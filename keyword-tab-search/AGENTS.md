# Keyword Tab Search agent guide

## Current status

- Version **0.1.2** activates exact saved search aliases with Tab.
- Uses native `gURLBar.search` and the search engine service. No search URL
  rewriting, engine migration, content injection, or periodic polling.
- Explicit aliases take precedence over stripped `@` aliases; ambiguous matches
  defer to normal browser behavior.
- Window unload cleanup runs without capture and checks the owning window or
  document. A captured child-document unload (such as `about:blank` replaced by
  Settings) must never destroy the controller. This caused the 0.1.0 shortcut to
  stop working even while the mod remained enabled.
- A per-address-bar `parentController.openSERP` wrapper supplies Zen's native
  `_zenHandleUrlbarClose(true, true)` notification for foreground searches
  submitted from a pending empty split. Zen 1.24b's engine-mode Enter path
  bypasses `pickResult`, so without this notification it treats the tab switch
  as cancellation and removes the split placeholder.
- Validation: nine Node tests and 36 browser checks passed on Zen 1.24b on
  macOS, covering regular and Little Zen windows, native query submission,
  engine edits, preserved Tab behavior, and unload/reload. The regression
  reproduces failure on 0.1.0 when Settings opens; 0.1.1 survives Settings open,
  reload, and close, and another window closing. Actual browser-window unload
  still cleans up the controller. The split regression fails on 0.1.1 and passes
  on 0.1.2 with actual Ctrl+Cmd+Shift+T input, regular and pinned source pages,
  document identity, drafts, query encoding, Escape cancellation, existing
  split panes, and ordinary new-tab searches. Windows desktop input has not
  been tested.

## Constraints and checks

- Scope interception to plain Tab in the address input. Keep Shift+Tab, other
  modifiers, composition, page forms, selected results, and ordinary text intact.
- Respect caret position and native URL autofill. Do not activate a keyword
  from an arbitrary selection or from a prefix of a longer search.
- Keep the engine cache fresh through search-service notifications; invalidate
  stale results immediately and discard outdated asynchronous refreshes.
- Native search mode must continue to own navigation, query encoding, POST
  data, private windows, containers, suggestions, and exiting search mode.
- Unload/hot reload must remove all listeners and observers without changing
  tabs or engine definitions.
- Keep the unload listener out of the capture phase and reject events from
  other documents. Browser-chrome capture can see nested page unloads.
- Keep the split submission hook scoped to the selected reserved empty tab,
  an active pending split/new-tab session, and a foreground `tab` destination.
  Forward the original receiver, engine, query, browser ID, return value, and
  all navigation arguments. Never build a replacement search URL, create tabs,
  or split them manually. Native result picking already sends its own signal.
- Restore the original method descriptor on unload only while the mod still
  owns it; preserve later wrappers and leave disabled instances inert.
- Run `node --test keyword-tab-search/tests/keyword-tab-search.test.cjs`.
  Browser checks use a disposable profile with loopback Marionette and
  `MOZ_REMOTE_ALLOW_SYSTEM_ACCESS=1`, never the everyday profile.
- Record actual keyboard input, selected engine, submitted query, focus, and
  lifecycle evidence. Keep reports outside Git.
- Keep the runtime file list in `../scripts/install.py` synchronized.

## Potential future direction

- Validate native Windows input and international keyboard composition.
- Consider an optional shortcut hint when an exact keyword is typed.
- Track changes to native address-bar APIs and autofill behavior.
- Retire the split submission compatibility hook when Zen's native engine-mode
  Enter path supplies the result-picked close notification itself.
