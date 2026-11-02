# Find Bar Pane Fix agent guide

## Current status

- Version **0.1.0** is a CSS-only correction for floating find-bar clipping and
  transparency in Zen, including with Better Find Bar 1.7.1 enabled.
- Anchors each bar to its own `.browserContainer`, bounds its width, wraps
  controls, uses opaque system colors, and removes hidden bars from layout.
- Validation: eight browser checks passed on Zen 1.24b on macOS, covering
  regular, split, narrow, and Glance layouts, match counts, Enter/Shift+Enter,
  Escape, and stylesheet removal. Screenshots were visually inspected.
  Native Windows UI remains untested.

## Constraints and validation

- Keep styling scoped to browser chrome find bars, never page inputs.
- Preserve native find logic, focus, counts, Enter/Shift+Enter, Escape, and
  selected-pane behavior. Do not move or duplicate find-bar DOM.
- Do not patch Better Find Bar or change its stored preferences.
- Span the browser container's full grid: the native `findbar` grid area has
  zero height when the bar is absolutely positioned. Percentage height limits
  against that area collapse the bar even when its controls remain visible.
- Check regular, split, narrow-pane, and Glance layouts with the existing mod
  enabled. Inspect screenshots as well as bounds, visible controls, and color.
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
