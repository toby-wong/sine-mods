# Local split fixes

## 1.4.5-local — 2026-11-03

- New default two-pane splits stack top-to-bottom when the Zen window is taller
  than it is wide. Wide and square windows keep the native side-by-side default.
- Covers Option/Alt-click, New Empty Split with keyword search, and Glance's
  Split button. Explicit directions/layouts, existing groups, and restored
  sessions keep their chosen layout.
- Adds **Stack new panes top-to-bottom in tall windows**, enabled by default,
  in both Sine configuration and the Tab Management card. Changes affect the
  next split without restarting.
- Uses native split creation and preserves live source pages. No resizing
  listener or page reload is needed. Hot reload removes the direction wrappers
  before the existing page-preservation wrapper.

## 1.4.4-local — 2026-10-31

- Use only the native tab accelerator when passing a split click through
  Firefox's click handler: Ctrl on Windows/Linux, Command on macOS. Previously,
  both flags were set. Navigation still uses the original principal and referrer.
- Use `ctrl` as the fallback for an unset `zen.glance.activation-method` in the
  parent hook and settings panel, matching the content actor and native Zen.
  Previously, the parent could treat Alt as a Glance conflict after the actor
  had already consumed the click, leaving no split.
- Label the Meta trigger for Windows/Super on non-Mac platforms and Command on
  macOS. Existing trigger preferences and the default Alt/Option gesture stay
  the same.

Automated parent-hook tests cover Windows, macOS, and Linux routing, an unset
Glance preference, conflicts, and the disabled mod. Live regression evidence is
from macOS with Zen 1.24b; native Windows input remains unverified.

## 1.4.3-local

The original local patch targeted Alt-click Split View 1.4.2 on Zen 1.23.4b.
The original mod's author and license remain unchanged.

The original parent-process click hook never saw clicks consumed by a website's
router. A trusted, capturing content actor now passes the Option-click to
Firefox's own ClickHandler before the website consumes it. Firefox still supplies
and checks the navigation principal, referrer, frame, and container information.
Ordinary clicks, Command-click, middle-click, and Shift-click retain their existing
behavior. HTTP and HTTPS links inside frames are covered.

Option-click inside Glance first promotes the existing preview without reloading,
then opens the link beside that page.

Zen's native split implementation duplicates a pinned source when combining it
with an unpinned tab. The patch instead uses the existing tabs. Tabs in a pinned
split share its pinned state; a newly pinned destination returns to its previous
state after leaving the split. An Essential temporarily appears in the pinned
split and returns to Essentials when the split is separated or the other panes
are closed. Closing the original page itself still closes that page.

Return information is saved as a custom SessionStore tab value. Hot reload keeps
existing splits. Unloading the mod separates its managed splits and restores their
pin state without closing or reloading pages.

The accompanying Hammerspoon patch preserves Option when clicking a background
Zen or Arc window. It focuses that browser before forwarding the click. The
existing guard for other background applications remains active.

The local registration disables upstream replacement of this patched mod.
Other mods and browser preferences are not changed.

Validation uses an isolated profile with the installed application. The
regressions check original document identity, browsing-context identity, drafts,
network request counts, pinned/Essential restoration, the four-pane limit,
Glance conversion, frames, and repeated operations. The existing Auto Glance
integration suite also passes.
