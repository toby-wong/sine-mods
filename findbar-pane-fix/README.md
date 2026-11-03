# Find Bar Pane Fix

Version **0.1.1** keeps the **Cmd+F / Ctrl+F** bar inside its own page pane.
It preserves your theme's background and transparency settings, wraps controls
in narrow panes, and fully hides closed find bars.

This is a CSS mod. Finding text, match counts, navigation, and keyboard shortcuts
continue to use Zen's native implementation. It can be used alongside Better
Find Bar; it corrects that mod's positioning while retaining its transparent
background and blur when enabled.

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
