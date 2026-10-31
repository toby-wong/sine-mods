# Little Zen

A compact temporary browser window for quick searches and links, built for Zen and Sine.

## Use

- Press **Command+Option+N** from any Mac app after installing the optional Hammerspoon integration.
- Or choose **File → New Little Zen** in Zen.
- Right-click a web link and choose **Open Link in Little Zen**.
- Search using your normal address bar and keywords: type the keyword, press Space, then enter the query.
- Click **Open in [Space]**, or press **Command+O** on Mac / **Ctrl+O** on Windows, to keep the current page in its originating Space.
- Use the arrow beside that button to choose a different Space.
- If a link opens another tab, use the tab-count menu to switch between temporary tabs.
- Use **Command+[ / Command+]** for back/forward and **Command+R** to reload. The compact toolbar retains the native address bar, Extensions and browser menu.
- Use the window's close control or the normal Command+W shortcut to close it.

The new window inherits its originating Space's container. Links opened through a context menu retain the source tab's container. Promotion moves the live tab, preserving the page, history, login context and unfinished forms. It also preserves that container when the destination Space has a different default.

Private windows remain private. Their keep control moves pages only into private windows.

Little Zen uses Zen's independent blank-window mechanism. Its temporary tabs are not restored at browser restart. Use the **Open in [Space]** button for pages you want to keep. Normal browsing history still applies.

## Settings

Open **Zen Settings → Sine**, find **Little Zen**, and choose **Configure**.

- Enable or disable the mod's behavior.
- Choose a new-window size: 720 × 560, 900 × 680 or 1100 × 800.
- Turn on **Open links from other apps in Little Zen** to route external HTTP/HTTPS links into temporary windows. This is off by default.

External routing applies when another app opens a link in Zen. It does not change your Mac's default browser. The temporary window uses the current Space's container; **Open in Space** chooses the permanent destination.

This is a local mod with automatic updates disabled. It uses Zen's internal browser APIs and should be checked when updating Zen. The existing Sine installation supplies the loader; installing Little Zen does not modify the Zen application bundle.

## Files

- `little-zen.uc.js`: window creation, commands, routing and promotion.
- `chrome.css`: styling scoped to Little Zen windows.
- `preferences.json` and `theme.json`: Sine settings and registration.
- `hammerspoon/little-zen.lua`: the Mac-wide shortcut.
- `PLAN.md`: implementation plan.
- `tests/runtime_test.py`: search, containers, promotion, external routing, privacy and unload checks in a disposable profile.
- `tests/lifecycle_test.py`: keeping a page after closing the main window.
- `tests/toolbar_test.py`: compact layout, direct keep button, Space menu and real keyboard shortcut.

## Install on macOS or Windows

Follow the collection's [installation guide](../README.md#install-the-sine-mods).
Use the Little Zen subfolder URL in Sine, or the shared local installer with
`--mods little-zen`. Restart Zen afterward.

The browser mod has platform-specific Command/Ctrl handling, but browser testing
has been on macOS only. The optional global shortcut is Mac-only; Windows users
can use the File menu (press Alt to reveal it) or the link context menu.

The [optional Mac shortcut instructions](../README.md#optional-mac-shortcuts)
install the Hammerspoon module without replacing existing configuration.
The older `scripts/install.py` and `scripts/uninstall.py` in this directory are
macOS-specific development utilities. Use the collection installer for new
installations on either platform.

## Disable or remove

Disabling Little Zen in Sine removes its added commands and restores its routing hooks. Open Little Zen windows become ordinary blank windows, retaining their tabs.

Remove the mod through Sine. To remove the optional Mac shortcut as well, remove
only the `BEGIN Little Zen` / `END Little Zen` block from `~/.hammerspoon/init.lua`
and its `little-zen.lua` module, then reload Hammerspoon's configuration.
Keep other Hammerspoon settings intact.
