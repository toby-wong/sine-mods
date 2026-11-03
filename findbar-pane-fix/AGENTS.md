# Find Bar Pane Fix agent guide

## Current status

- Version **0.1.4** corrects floating find-bar clipping in
  Zen, including with Better Find Bar 1.7.1 enabled.
- Anchors each bar to its own `.browserContainer`, bounds its width, wraps
  controls, defaults to the theme's background at 96% opacity, and removes hidden
  bars from layout. Labels default to 14px and the query is 1px larger.
- Sine's Configure panel controls opacity, text size, blur, automatic/white/black
  text, and theme/custom backgrounds. Dropdown values become CSS variables or
  attributes on `#theme-Find-Bar-Pane-Fix`.
- Text sizes go down to 8px. Optional **Scale with page zoom** defaults off and
  applies CSS `zoom` to each bar using its own browser's ZoomManager value.
  `findbar-zoom.uc.js` listens for native zoom/tab events and a preference
  observer. It uses weak bookkeeping, no polling, and restores inline state
  on disable or unload. It does not inspect page contents.
- `@property` validates the custom background as a color and falls back to
  `#525f2e` if invalid. Opacity is separate from the background color's alpha.
- Native `contrast-color()` selects black or white from the background color,
  updating automatically with Space/theme changes. Older engines use a matching
  system background/text pair. No JavaScript or page reload is needed.
- Validation: 26 browser checks passed on Zen 1.24b on macOS, covering
  regular, split, narrow, and Glance layouts, match counts, Enter/Shift+Enter,
  Escape, stylesheet removal, and live contrast changes across dark, light,
  and olive backgrounds. Opacity, font sizes, and visible control bounds are
  checked in each layout. The real Sine Configure panel was exercised for
  opacity, size, blur, manual text colors, custom colors, invalid-color fallback,
  and restoring defaults. Largest text fits a narrow split; preference changes
  preserve the original page document. Screenshots were visually inspected.
  Fresh checks cover 8px labels, 80% and 150% page zoom, independent pane zoom,
  turning scaling off and back on, and restoring fixed size on script unload.
  Same-host pane fixtures use native per-tab zoom to avoid site zoom inheritance.
  Native Windows UI remains untested.

## Constraints and validation

- Keep styling scoped to browser chrome find bars, never page inputs.
- Preserve native find logic, focus, counts, Enter/Shift+Enter, Escape, and
  selected-pane behavior. Do not move or duplicate find-bar DOM.
- Do not patch Better Find Bar or change its stored preferences.
- The user requested reduced transparency, larger text, and automatic white
  text on darker backgrounds. Keep some bar transparency and the existing blur;
  the query field is solid for readability. Automatic text color takes priority
  over a theme's fixed/custom text color unless the user selects a manual text
  color in this mod. Retain clear no-match feedback.
- Appearance must remain configurable inside Zen through Sine. Keep sensible
  CSS defaults for profiles whose settings have not yet been initialized.
- Span the browser container's full grid: the native `findbar` grid area has
  zero height when the bar is absolutely positioned. Percentage height limits
  against that area collapse the bar even when its controls remain visible.
- Check regular, split, narrow-pane, and Glance layouts with the existing mod
  enabled. Inspect screenshots as well as bounds, visible controls, and color.
  Check 96% opacity, 14px labels, 15px query text, and dynamic black/white
  contrast on dark, light, and olive backgrounds with default settings. Also
  check the largest text in a narrow pane, custom colors, invalid colors, and
  returning to defaults through the actual Sine settings controls.
- Exercise actual Cmd/Ctrl+F and Escape. Verify a hidden bar cannot overlay a
  neighboring pane, and that removing the stylesheet restores prior styling.
- Use a disposable profile with loopback Marionette and
  `MOZ_REMOTE_ALLOW_SYSTEM_ACCESS=1`; keep reports and screenshots outside Git.
  `--headless` avoids macOS pausing animation frames in occluded test windows.
- Update `../scripts/install.py` if runtime resources change.

## Potential future direction

- Validate Windows, high-contrast themes, and right-to-left chrome layouts.
- Revisit native Zen find-bar markup as Firefox versions change.
- Consider an optional top/bottom position preference if requested.
