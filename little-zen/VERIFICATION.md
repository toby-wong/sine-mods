# Verification

Verified on macOS with the installed **Zen 1.23.4b**, 26 October 2026.

Evidence is retained outside the repository in the original installation
backup's `reports/` directory. The ignored `.local-setup.json` records that
machine-specific backup path.

| Evidence | Result |
| --- | --- |
| `runtime-verification-final.json` | Passed: independent windows, unchanged main tabs, inherited container cookies, native keyword search, promotion without reload, multiple tabs, link context menu, external routing, privacy, disable and unload. |
| `toolbar-verification-final.json` | Passed: one toolbar row, Extensions access, named Space destination, real Command+O input, direct keep button and Space menu. Each action preserved the draft and live document. |
| `compact-toolbar-verification.json` | Passed: address bar and controls stay visible with compact mode enabled. |
| `lifecycle-verification-toolbar.json` | Passed: alternate window defaults, closing the original main window, promotion into a new main window, and link-scheme validation. |
| `installer-verification.json` | Passed: install/remove preserves other mods and later Hammerspoon edits. |
| `live-global-shortcut-final.json` | Passed: global shortcut from another Mac app, address-field typing and preserved main-window geometry. |
| `live-toolbar-reload-final.json` | Passed: final toolbar loaded into running Zen windows; tabs and main-window size preserved. |
| `final-installation-verification.json` | Installed file hashes match source; original mod registrations, search, shortcuts and Hammerspoon configuration preserved. |
| `completion-status.json` | Zen and Arc running; temporary automation ports closed. |

Tests use a separate disposable profile with the installed application. Live
verification only exercises the added UI and checks preservation. The Zen app
bundle was not modified.

Existing container definitions are unchanged. One additional container appeared
during the session and was retained.

The backup contains private browser state. It has not been published or uploaded.
