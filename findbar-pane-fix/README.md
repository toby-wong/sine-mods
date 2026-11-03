# Find Bar Pane Fix

Version **0.1.2** keeps the **Cmd+F / Ctrl+F** bar inside its own page pane.
It uses a 96% opaque background, 14px labels, and 15px search text. Controls wrap
in narrow panes, and closed find bars are fully hidden.

This is a CSS mod. Finding text, match counts, navigation, and keyboard shortcuts
continue to use Zen's native implementation. It can be used alongside Better
Find Bar; it corrects that mod's positioning while retaining the background
color and blur. Some transparency remains, but page text is less distracting.
The search field uses a solid background for readability.

Text and navigation icons automatically switch between black and white to
contrast with the bar's background, including when a Space or theme changes.
This takes precedence over Better Find Bar's custom text color. Current Zen
uses native CSS contrast selection; older engines without that feature use
matching system background and text colors.

## Install on macOS or Windows

Follow the collection's [installation guide](../README.md#install-the-sine-mods).
Use this subfolder URL in Sine:

```text
https://github.com/toby-wong/sine-mods/tree/main/findbar-pane-fix
```

For a local checkout, select `--mods findbar-pane-fix` with the shared installer
after closing Zen. Restart Zen after installation.

Disable this mod in Sine to restore the previous find-bar styling. The mod does
not alter Better Find Bar's source or preferences.

The stylesheet is shared by macOS and Windows. Live Windows validation remains
outstanding. See [AGENTS.md](AGENTS.md) for validation and future direction.
