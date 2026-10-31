# Alt-click Split View — local fork

Option-click a web link on macOS, or Alt-click on Windows, to open it beside the
source page in Zen's native Split View.

This is version **1.4.4-local**, based on **1.4.2** of
[Kostiantyn Kugot's Alt-click Split View](https://github.com/kkugot/alt-click-split-view).
The upstream author and [MIT license](LICENSE) are retained.

## Local changes

- Captures Option/Alt-click before a website's router consumes it, including
  links inside frames, while retaining Firefox's normal link validation.
- Uses the platform's native tab accelerator internally: Ctrl on Windows/Linux
  and Command on macOS.
- Matches Zen's native Glance fallback when its shortcut preference is unset,
  so the default Alt-click is not consumed without opening a split.
- Promotes an existing Glance preview before splitting beside it.
- Reuses pinned and Essential source pages instead of loading duplicate pages.
- Restores temporary pin/Essential state after separating a managed split.
- Keeps existing splits during hot reload. Disabling the mod separates its
  managed splits without closing or reloading their pages.

See [PATCH-NOTES.md](PATCH-NOTES.md) for details and
[VERIFICATION.md](VERIFICATION.md) for validation records.
With the default Alt trigger, normal clicks, Ctrl/Command-click, middle-click,
and Shift-click retain their own handlers; Auto Glance may separately customize
some of those actions.

## Install on macOS or Windows

Follow the collection's [installation guide](../README.md#install-the-sine-mods).
Use this fork's subfolder URL:

```text
https://github.com/toby-wong/sine-mods/tree/main/alt-click-split-view
```

For installation from a local checkout, use the shared installer with
`--mods alt-click-split-view`. It backs up an existing copy before replacement.
The fork and upstream use the same mod ID, so install one or the other in a
profile. The shared installer disables automatic updates for this local copy.

Configure the modifier and optional pointer-hover pane switching under
**Settings → Sine → Alt-click Split View → Configure**. Avoid assigning the same
modifier to Glance; the mod yields when those shortcuts conflict.

The browser implementation supports selecting Alt/Option, Ctrl, Shift, or Meta
(Command on macOS, Windows/Super elsewhere). The operating system may reserve
the Meta key. Alt-click is the default Windows gesture and needs no extra helper.
Only the selected modifier is accepted; combinations such as Ctrl+Alt do not
trigger a split.

Automated tests exercise Windows, macOS, and Linux click routing, including
native navigation metadata and Glance conflicts. Live browser validation has
been on macOS; Windows desktop input has not yet been tested.

## Optional Mac background-window guard

`option-click-guard.lua` is an optional Hammerspoon integration. It preserves
Option when clicking a background Zen or Arc window, bringing that window to the
front. For other background apps, it removes Option from the click to suppress
macOS's hide-other-apps behavior. That is a system-wide behavior change.

If you want this behavior and do not already have the guard installed:

1. Install Hammerspoon and enable its requested permissions.
2. Copy `option-click-guard.lua` to `~/.hammerspoon/`.
3. Add this line once to your existing `~/.hammerspoon/init.lua`:

   ```lua
   dofile(hs.configdir .. "/option-click-guard.lua")
   ```

4. Reload Hammerspoon's configuration.

Keep existing configuration intact. If you already have an Option-click
eventtap, replace that specific guard instead of registering a second competing
one. Windows does not use this integration.

## Checks

From the collection root:

```sh
node --test alt-click-split-view/tests/alt-click-split-view.test.cjs
```

The Python browser regressions require a separately configured disposable Zen
profile. They check document identity, page state, frames, pinned/Essential
restoration, Glance promotion, and repeated split operations.
