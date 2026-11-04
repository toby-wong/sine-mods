# Profile Switcher agent guide

## Current status

- Version **0.1.0** identifies the current profile in the sidebar and window title.
- The native popup lists registered profiles and links to `about:profiles`.
- Uses `SelectableProfileService.launchInstance({ path })` for native process
  activation/launch. This method uses only the path; enabling or migrating to
  Firefox's separate selectable-profile database is not required.
- Validation on Zen 1.24b/macOS: eight Node tests, nine shared-installer tests,
  and 21 browser UI/lifecycle checks passed. These cover profile path identity,
  keyboard/menu actions, colours, title changes, stale selections, child document
  unload, hot reload, preserved tabs/documents, and later title wrappers.
- Two disposable processes exercised the native activation command in both
  directions, preserving each process's window count, tabs, and selection.
  Native launch of a closed disposable profile also passed with the complete
  installed mod set, including all seven custom JavaScript controllers.
- Startup checks in two existing macOS profiles also passed with all 14 installed
  mods, distinct profile colours, and preserved tab IDs, Spaces, folders, tree
  metadata, and split groups after restoring their saved sessions.
- Windows/Linux desktop activation has not been tested.

## Constraints

- Read `profiles.ini`; never rewrite it, change default profiles, create profile
  groups, or call methods that migrate data just to show or launch a profile.
- Use the exact registered path. Names can collide or change, and profile
  service objects can become stale across processes. Refresh before switching.
- Never send the current URL, private page content, or credentials to another
  profile. Leave the current window and session open.
- Keep UI outside the native tab strip's child list. The row belongs before
  `TabsToolbar`, not among tab, split, group, or Essential nodes.
- Wrap native title generation without dropping page titles or private labels.
  Restore only a wrapper still owned by this instance and keep retained
  wrappers inert after unload.
- Window unload must ignore child-document unloads. Dispose of UI and observers,
  and discard pending async results after removal.
- Preserve existing profile colours, preferences, loaders, and unrelated mods
  during installation. Never modify the signed Zen application.
- Zen 1.24b filters ordinary tabs at startup unless `browser.startup.page` is `3`;
  Firefox's `browser.sessionstore.resume_session_once` alone does not prevent that
  filter. The switcher respects startup settings. Before a user-authorized
  restart or recovery, back up both native and Zen session files and verify
  regular tabs and split groups, not just pinned tabs.
- Keep the runtime list in `../scripts/install.py` synchronized.
- Browser tests must use disposable profiles and inject a catalogue containing
  only test paths before exercising launch. Never automate real profile switches
  from a test catalogue sourced from the user's registry.
- The native launcher uses `nsIRemoteService` before starting a process. Use
  `--new-instance --profile <test-profile>` for the two-process activation check:
  `--no-remote` deliberately disables the remoting being tested. Validate `ProfD`
  before every automation session and keep automation out of real profiles.
- Marionette's system sandbox can retain bindings; use explicit `window.*`
  references for mutable fixture state and function-identity assertions.

Run `node --test profile-switcher/tests/profile-switcher.test.cjs` from the
collection root. `tests/integration.py` accepts `--profile`, `--other-profile`,
`--port`, and `--report`. Its UI checks record launch requests instead of opening
real profiles. Keep process-launch reports and screenshots outside the checkout.

## Potential future direction

- Validate Windows/Linux desktop profile activation and accessibility.
- Consider a keyboard shortcut if the user requests one.
- Adapt the catalogue when Zen adopts Firefox's selectable-profile groups.
