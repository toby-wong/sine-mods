# Little Zen

## Goal

Provide a Little Arc-style temporary browser window in the existing Zen and Sine installation.

## First version

- Open a compact, independent window from **File → New Little Zen**, **Command+Option+N**, or a link's context menu.
- Keep Zen's native address bar, search engines, keywords, navigation and extension access.
- Inherit the originating Space's container and login session.
- Offer **Open in Space** to move the current page into a regular Zen window.
- Match the supplied Little Arc reference with a single toolbar row, named destination, direct keep button, Space picker and **Command+O** keep shortcut.
- Use a small Hammerspoon module for the shortcut when another Mac app is active.
- Offer opt-in routing of external HTTP/HTTPS links through the mod's Sine settings.
- Keep temporary windows outside the main window's synchronized tab/workspace state.
- Support disabling and uninstalling the mod without restoring an old browser profile.

## Implementation

1. Verify the installed Zen window, workspace, tab adoption and external-link APIs.
2. Implement a Sine JavaScript mod with scoped CSS and Sine preferences.
3. Implement a Hammerspoon shortcut module without replacing existing configuration.
4. Exercise the mod in an isolated test profile using the installed Zen application.
5. Back up files affected by installation, merge the mod into the latest Sine registry, and verify the real profile.
6. Leave source, test evidence, usage instructions and rollback instructions locally.

## Validation

- A new mini-window does not copy, hide, navigate or close main-window tabs.
- A mini-window starts in the originating container; private windows stay private.
- The native address bar resolves custom search keywords.
- Promotion preserves the page and its container in the chosen Space.
- A main-window close or mod unload cannot silently discard a mini-window's page.
- External routing is opt-in and limited to HTTP/HTTPS; ordinary navigation is unchanged.
- Disabling the mod restores patched functions and removes added controls.
- The global shortcut works while a different application is active.
- Existing Sine mods, the Option-click split gesture and the user's settings remain present.

## Installation policy

Only edit the new mod files, the Sine registry and the additive Hammerspoon integration. Do not alter the Zen application bundle. Read the latest configuration immediately before merging so changes made during development are preserved.

## Completed — 26 October 2026

Implemented and installed locally with the supplied Little Arc toolbar reference.
Verified search keywords, container inheritance, private windows, external routing,
live tab promotion, the Space menu, Command+O, the global shortcut, and unload.
Checked both normal and compact layouts, including Zen's alternate placement of
the native address bar inside the titlebar wrapper.

The live update preserved each window's tabs and the main window's geometry.
All eight pre-existing Sine registrations and the search and shortcut files were
preserved. Source matches the installed files. Temporary automation was stopped,
and Arc was reopened. See `VERIFICATION.md` for the evidence locations.
