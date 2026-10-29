# Auto Glance

A local Sine mod for Zen that opens link-created tabs as native Glance previews.

Enabled behavior:

- Website links that request a new tab, including `target="_blank"`.
- Script-created web tabs such as `window.open(url)`.
- Middle-click.
- **Open Link in New Tab** in a page's context menu.

Use Glance's **expand** button for a full tab, **split** button for a split view,
or **Escape** to dismiss it. The existing Shift-click Glance and Option-click
split gestures remain available.

**Command-click always opens a regular background tab**, even when the link
uses `target="_blank"` or a website script would normally open it in Glance.
The page you are reading remains selected. This also works from a Glance
preview and for links in frames.

Open **Zen Settings → Sine → Auto Glance → Configure** to disable the behavior or
configure the middle-click/context-menu behavior and Command-click override.

## Scope

The mod converts the tab that Zen created. It preserves the native navigation,
container, referrer, POST body, opener and security parameters. It works in
regular, private and Little Zen windows.

Ordinary same-tab navigation, the new-tab command, address-bar searches,
bookmarks and links from other applications retain their normal behavior.
Explicit splits, separate popup windows and requests to use a different
container also retain their native handling.

The mod applies to HTTP/HTTPS destinations. It keeps an existing Glance intact;
additional links opened from that preview can still use ordinary tabs.

## Local installation

The installed mod lives under `chrome/sine-mods/auto-glance` in the Zen profile.
Automatic updates are disabled for this local mod.

Disable or remove **Auto Glance** in Sine to restore the earlier link behavior.
Existing previews and tabs are preserved when the mod unloads.

The Zen application bundle is unchanged. This uses internal Zen APIs, so the
included browser tests should be rerun after significant Zen updates.

## Verification

`tests/integration.py` exercises real automatic, Cmd, middle and Shift clicks;
context-menu links; script-created tabs; form POSTs; opener and container
preservation; expanding a preview; the existing Option-click split; disabling
the mod; and unloading it without losing tabs.

`tests/contexts.py` checks private and Little Zen windows. Tests require a
separate disposable profile whose name includes `test-profile`.
