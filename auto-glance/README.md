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

This includes real links inside editable documents. The explicit Command
gesture uses the normal browser link loader even when the document's editor
would otherwise open its own preview.

Glance previews are centered in the content area with a blurred backdrop.
Closing, expanding, and splitting previews retain Zen's native behavior.
The backdrop adds a light Space-coloured tint, making the area behind the
preview slightly less transparent than the sidebar. The sidebar and the preview
page itself are unchanged.

The mod also clears abandoned temporary splits whose placeholder tab was
closed. These can otherwise leave Glance stuck against the left edge before
its opening animation finishes. Working split groups and unloaded tabs are
preserved. Updating the mod can recover a preview already interrupted by this
specific failure without reloading it or its parent page.

Open **Zen Settings → Sine → Auto Glance → Configure** to disable the behavior or
configure the middle-click/context-menu behavior and Command-click override.
**Extra backdrop opacity** controls the tint from **0%** (the original backdrop)
to **100%** (opaque), with **20%** as the default. Changes apply immediately,
including to an open preview, and the tint follows your Space colour.

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

## Install on macOS or Windows

Follow the collection's [installation guide](../README.md#install-the-sine-mods).
Use the Auto Glance subfolder URL in Sine, or the shared local installer with
`--mods auto-glance`. Restart Zen afterward.

Browser testing has been on macOS. The background-tab override checks the
Command modifier (`metaKey`); it does not currently implement Windows Ctrl-click
as an override. On Windows, Ctrl-click can still be converted into Glance.

The installed mod lives under `chrome/sine-mods/auto-glance` in the Zen profile.
The shared local installer disables automatic updates for its installed copy.

Disable or remove **Auto Glance** in Sine to restore the earlier link behavior.
Existing previews and tabs are preserved when the mod unloads.

The Zen application bundle is unchanged. This uses internal Zen APIs, so the
included browser tests should be rerun after significant Zen updates.

## Verification

`tests/integration.py` exercises real automatic, Cmd, middle and Shift clicks;
context-menu links; script-created tabs; form POSTs; opener and container
preservation; expanding a preview; the existing Option-click split; disabling
the mod; and unloading it without losing tabs.

Regression checks include editable document links, links from an existing
preview and split view, centering, backdrop blur, and 80% page zoom.

`tests/contexts.py` checks private and Little Zen windows. Tests require a
separate disposable profile whose name includes `test-profile`.

`tests/stale_splits.py` reproduces the closed-placeholder failure, checks
recovery of both existing pages without a reload, verifies that working split
layouts survive, and checks that subsequent previews finish opening normally.
