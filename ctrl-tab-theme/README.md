# Ctrl Tab Theme

Version **0.1.0** gives Zen's native **Ctrl+Tab** switcher Space colours, rounded
preview cards, readable titles, and a clear outline around the selected tab.
Small icons sit beside the titles instead of overlapping the previews.
Text automatically switches between black and white with the background.

This is a CSS-only mod. Tab order, quick switching, Ctrl+Shift+Tab, selection on
releasing Ctrl, and Escape are still handled by Zen. It also works with Better
CtrlTab Panel 1.0.1 enabled, overriding that mod's appearance without changing its
files or preferences. Disable Ctrl Tab Theme to restore the previous styling.

## Install on macOS or Windows

Follow the collection's [installation guide](../README.md#install-the-sine-mods).
Use this subfolder URL in Sine:

```text
https://github.com/toby-wong/sine-mods/tree/main/ctrl-tab-theme
```

For a local checkout, select `--mods ctrl-tab-theme` with the shared installer
after closing Zen. Restart Zen after installation.

Enable **Ctrl+Tab cycles through tabs in recently used order** in Zen's tab
settings if the preview switcher is not already enabled. This mod does not change
that preference. Use **Control+Tab** on both macOS and Windows.

Open **Settings → Sine Mods → Ctrl Tab Theme → Configure** to change background
opacity (90%, 96%, or solid) and title size (12px, 14px, or 16px). Changes apply
immediately. The defaults are 96% opacity and 14px titles.

The stylesheet is shared by macOS and Windows. Native Windows validation is
still outstanding. See [AGENTS.md](AGENTS.md) for status and future direction.
