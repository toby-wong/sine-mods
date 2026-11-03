# Find Bar Pane Fix

Version **0.1.3** keeps the **Cmd+F / Ctrl+F** bar inside its own page pane.
It defaults to a 96% opaque background, 14px labels, and 15px search text.
Controls wrap in narrow panes, and closed find bars are fully hidden.

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

## Change the styling in Zen

Open **Settings → Sine → Find Bar Pane Fix → Configure**. These controls apply
immediately, on macOS and Windows, without restarting or reloading pages.

| Setting | Choices | Default |
| --- | --- | --- |
| Background opacity | 70–100%; higher values show less of the page underneath | 96% |
| Text size | 12, 14, 16, 18, or 20px; search text is always 1px larger | 14px |
| Background blur | Off, 4, 8, 12, or 16px | 8px |
| Text colour | Automatic contrast, always white, or always black | Automatic |
| Background colour | Space/theme colour or a custom CSS colour | Space/theme |

With **Custom colour** selected, enter a colour such as `#20242a` in the custom
background field and press Tab or click outside the field to apply it. Invalid
colours fall back to olive (`#525f2e`). Opacity is controlled separately, so any alpha in the colour
is ignored. Automatic contrast follows custom colours as well as theme changes.
For very transparent bars, readability also depends on the page underneath.

The choices are saved in your browser profile. To restore the original
appearance, select the choices labelled **default** in this panel. Other Better
Find Bar options remain in that mod's own configuration panel.

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
