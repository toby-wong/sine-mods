# Keyword Tab Search agent guide

## Current status

- Version **0.1.1** activates exact saved search aliases with Tab.
- Uses native `gURLBar.search` and the search engine service. No search URL
  rewriting, engine migration, content injection, or periodic polling.
- Explicit aliases take precedence over stripped `@` aliases; ambiguous matches
  defer to normal browser behavior.
- Window unload cleanup runs without capture and checks the owning window or
  document. A captured child-document unload (such as `about:blank` replaced by
  Settings) must never destroy the controller. This caused the 0.1.0 shortcut to
  stop working even while the mod remained enabled.
- Validation: six Node tests and 21 browser checks passed on Zen 1.24b on
  macOS, covering regular and Little Zen windows, native query submission,
  engine edits, preserved Tab behavior, and unload/reload. The regression
  reproduces failure on 0.1.0 when Settings opens; 0.1.1 survives Settings open,
  reload, and close, and another window closing. Actual browser-window unload
  still cleans up the controller. Windows desktop input has not been tested.

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
