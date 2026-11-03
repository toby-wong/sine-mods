# Ctrl Tab Theme agent guide

## Current status

- Version **0.1.0** is a CSS-only theme for Zen's native Ctrl+Tab switcher.
- Uses `--zen-colors-secondary` for a Space-derived surface and native
  `contrast-color()` for readable text. Older engines fall back to Canvas and
  CanvasText. Forced-colour mode uses system colours.
- Overrides Better CtrlTab Panel 1.0.1's zoom, spacing, and oversized outdented
  icons. The older mod uses obsolete popup variables such as
  `--panel-background`; current Zen uses `--panel-background-color` and
  `--panel-box-shadow`.
- Sine preferences control opacity and title size without runtime JavaScript.
- Eleven browser checks passed on Zen 1.24b on macOS: forward/reverse navigation,
  Escape, selection on Ctrl release, light/dark colours, ten previews over two
  rows, native method/document preservation, unload, actual Sine settings, and
  operation with Better CtrlTab Panel disabled. Computed styles and bounds
  confirm readable titles, contained icons, and a visible selection border.
  Native popup pixels are omitted by headless screenshots, so desktop visual
  verification remains outstanding. Native Windows UI remains untested.

## Constraints and validation

- Scope every style to `#ctrlTab-panel`; never change other browser popups.
- Preserve native ordering, preview count, quick switching, Ctrl release,
  Ctrl+Shift+Tab, Escape, and Show All Tabs. Do not patch JavaScript, move DOM,
  or enable the recently-used-order preference in the user's profile.
- Leave Better CtrlTab Panel's files and preferences intact.
- Preserve native columns and screen positioning; allow titles to truncate.
- Check actual keyboard selection and cancellation in a disposable profile.
  Inspect screenshots and bounds for light/dark Space colours, selected cards,
  long titles, and multi-row previews.
- Test with the existing Better CtrlTab Panel enabled and after unloading it.
- Keep screenshots and reports outside Git. Use loopback Marionette with
  `MOZ_REMOTE_ALLOW_SYSTEM_ACCESS=1`, never an everyday profile.
- Keep `../scripts/install.py` in sync if runtime resources change.

## Potential future direction

- Validate Windows, screen readers, and native forced-colour themes.
- Revisit popup variables and preview markup after major Firefox/Zen updates.
- Consider a compact layout option if requested, keeping native screen
  positioning and preview counts.
