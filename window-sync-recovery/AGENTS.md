# Window Sync Recovery agent guide

## Current status

- Source version **0.1.0** repairs stale native window-sync presentation state.
- The observed Zen 1.24b failure left two loaded tabs marked as content owners
  while their browsers remained `zen-pseudo-hidden` behind 40%-opacity snapshots.
  Removing only the stale attributes/images preserved both live documents.
- Automatic cleanup requires exactly one browser window in the profile process,
  an idle, loaded content owner, and an unchanged document across two checks.
- All 21 browser integration checks passed on Zen 1.24b/macOS: stale recovery,
  live document and unsaved input preservation, mutation-triggered cleanup,
  owner/busy/pending/blank guards, revalidation during the delay, multiple-window
  exclusion, cleanup after closing a private window, split preservation, and
  unload/reload. The collection's 9 installer tests also passed.
- Native Windows behavior has not been tested.

## Constraints

- Do not reload pages, restore session state, force ownership flags or swap
  docshells. A live document must already exist before removing its snapshot.
- Do not hide all snapshots with CSS: that would conceal legitimate placeholders.
- Count private, unsynced, opening and closing windows conservatively. Multiple
  windows suspend cleanup.
- Preserve split membership, tree metadata, input values and navigation.
- Keep the observer scoped to browser chrome. Do not observe website DOM or add
  a polling interval.
- Unload must remove timers, event listeners and observers. It should not recreate
  stale presentation state on pages that have already been repaired.
- Keep script metadata, runtime version, manifest and collection documentation
  consistent. Register runtime files in `scripts/install.py`.

## Validation

Use `node --check` and `tests/integration.py` with a disposable profile and
privileged localhost debugger. Confirm stale cleanup, retained live content,
multiple-window exclusion, stability guards and unload/reload behavior.
Keep reports, screenshots, real URLs and profile backups outside Git.

## Potential future direction

- Reproduce the original native transfer race and upstream the cleanup fix.
- Reassess whether this workaround is needed after Zen updates its window sync.
- Consider multi-window recovery only with a reliable native transfer-completion
  signal and tests proving legitimate snapshots remain untouched.
