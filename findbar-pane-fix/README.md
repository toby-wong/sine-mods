# Find Bar Pane Fix

Version **0.1.4** keeps the **Cmd+F / Ctrl+F** bar inside its own page pane.
It defaults to a 96% opaque background, 14px labels, and 15px search text.
Controls wrap in narrow panes, and closed find bars are fully hidden.

Finding text, match counts, navigation, and keyboard shortcuts
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
| Text size | 8, 9, 10, 11, 12, 14, 16, 18, or 20px; search text is 1px larger | 14px |
| Scale with page zoom | Scale the entire bar with its own page, or keep its size fixed | Off |
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

**Scale with page zoom** uses a small browser script. With it enabled, a 10px
label appears at 8px on a page zoomed to 80%, or 15px at 150%. Each split pane
follows its own page's zoom; switching the toggle off immediately restores the
chosen fixed size. The script listens for native zoom and tab events, without
polling or reading page content. Allow custom JavaScript in Sine
(`sine.allow-unsafe-js`) to use this option. Other styling works with CSS alone.

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
