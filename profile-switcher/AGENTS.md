# Profile Switcher agent guide

## Current status

- Version **0.2.2** identifies the current profile in the sidebar and window title.
- The control uses Zen's native dropdown SVG, button tokens, and focus outline.
  The popup lists registered profiles, external-link destinations, and `about:profiles`.
- The button uses the sidebar's `--border-radius-medium` and the address bar's
  two-pixel inset. The eight-pixel upper gap matches Essentials' six-pixel top
  padding plus two-pixel tab margin. Essentials supply their own lower gap, so
  the row adds no bottom padding.
- Version 0.2.1 styling was checked with native Essentials, a narrow control, and
  a changed theme radius in a disposable profile. Live Work and Personal checks
  confirmed matching 14px corners, aligned edges, 8–8.5px vertical gaps, and
  preserved tabs, splits, tree relationships, and controller instances.
- Optional macOS routing sends external HTTP/HTTPS links to a configured profile.
  The process handler survives closing the last window without retaining DOM
  windows. Internal navigation and explicit private-window commands stay native.
- Uses `SelectableProfileService.launchInstance({ path })` for native process
  activation/launch. This method uses only the path; enabling or migrating to
  Firefox's separate selectable-profile database is not required.
- Validation on Zen 1.24b/macOS: 18 Node tests, nine shared-installer tests,
  28 browser UI/lifecycle checks, and eight native routing checks passed. These cover profile path identity,
  keyboard/menu actions, colours, title changes, stale selections, child document
  unload, hot reload, preserved tabs/documents, later title wrappers, native
  cross-process URL delivery, fallback, and Sine's process/window unload paths.
- The 0.2.2 checkmark regression fails with the previous implementation and
  passes after the fix. UI checks cover the painted macOS checkmarks, selecting
  a destination, reopening the menu, and returning to normal routing. Live Work
  and Personal menus each showed one current profile and one destination,
  preserving the routing preference, saved tabs, and other mod controllers.
- Native launch of a closed disposable profile with a URL also passed. The
  control was visually checked with native light/dark colour tokens and narrow
  widths. Two OS-delivered links reached the configured destination with each
  of the two real profile applications active in turn; test tabs were removed.
- Two disposable processes exercised the native activation command in both
  directions, preserving each process's window count, tabs, and selection.
  Native launch of a closed disposable profile also passed with the complete
  installed mod set, including all seven custom JavaScript controllers.
- Startup checks in two existing macOS profiles also passed with all 14 installed
  mods, distinct profile colours, and preserved tab IDs, Spaces, folders, tree
  metadata, and split groups after restoring their saved sessions.
- Windows/Linux desktop activation has not been tested. External-link routing
  is currently macOS-only, and its submenu is disabled on those platforms.

## Constraints

- Read `profiles.ini`; never rewrite it, change default profiles, create profile
  groups, or call methods that migrate data just to show or launch a profile.
- Use the exact registered path. Names can collide or change, and profile
  service objects can become stale across processes. Refresh before switching.
- Profile switching never sends the current page, private content, or credentials.
  External routing forwards only the URLs explicitly received in macOS's
  `STATE_REMOTE_EXPLICIT` / `-url` request shape, after HTTP/HTTPS validation.
  Skip the current destination, permanent private browsing, and disabled Sine
  JavaScript/mods. Revalidate the destination path before launching it.
- `ExternalProfileRouting.sys.mjs` owns the process hook and native profile I/O.
  `CommandLineHandler.handle` is the entry point; `CommandLineHandler.openUrls`
  supplies the native fallback. `SelectableProfileService.launchInstance`
  activates/launches the destination. Do not migrate selectable-profile groups.
- Register the module's Sine unload callback with a null window. Window closure
  must not remove the process hook; disabling the mod must remove it. Keep
  callbacks free of DOM references, restore only owned wrappers, and replay
  pending requests once if unloaded or reconfigured during profile discovery.
- Keep UI outside the native tab strip's child list. The row belongs before
  `TabsToolbar`, not among tab, split, group, or Essential nodes.
- Set `checked="true"` only on selected menu items. Unselected items must omit
  `checked`: Zen's native menu CSS uses `[checked]`, so `"false"` still draws a
  tick. Verify exactly one selection in each menu, including after changing the
  external destination and returning to normal routing.
- Wrap native title generation without dropping page titles or private labels.
  Restore only a wrapper still owned by this instance and keep retained
  wrappers inert after unload.
- Window unload must ignore child-document unloads. Dispose of UI and observers,
  and discard pending async results after removal.
- Preserve existing profile colours, preferences, loaders, and unrelated mods
  during installation. Never modify the signed Zen application.
- A running macOS profile can have no windows. Temporary setup windows can
  restore or synchronize existing tabs; preserve those tabs and clean up only
  exact, known setup URLs. Keep session backups and reports outside Git.
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

Run `node --test profile-switcher/tests/*.test.*` from the collection root.
`tests/integration.py` accepts `--profile`, `--other-profile`,
`--port`, and `--report`. Its UI checks record launch requests instead of opening
real profiles. `tests/external_routing.py` additionally takes `--other-port` and
exercises native URL commands between two disposable processes. Its injected
catalogue and launch guard contain only those test paths.
Keep process-launch reports and screenshots outside the checkout.

## Potential future direction

- Validate Windows/Linux desktop profile activation and accessibility.
- Define and validate external URL command shapes before adding Windows/Linux
  routing. Keep explicit private/profile commands and browser navigation intact.
- Consider a keyboard shortcut if the user requests one.
- Adapt the catalogue when Zen adopts Firefox's selectable-profile groups.
