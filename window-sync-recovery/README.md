# Window Sync Recovery

Repairs a Zen window-sync failure where a live page remains hidden behind a
faded snapshot after the other browser windows have closed.

Zen 1.24b can leave `zen-pseudo-hidden` and `.zen-pseudo-browser-image` on a
browser whose tab already has `_zenContentsVisible = true`. Selecting the tab
again does not necessarily clear them. This mod removes the stale presentation
state without reloading the page or changing its tab, container, split or tree.

## Scope

Cleanup runs only when exactly one browser window remains in the current
profile's process. Opening, closing, private and unsynced browser windows count.
The live tab must own its content, be loaded and idle, and retain the same
document across two checks 300 milliseconds apart. Blank stand-ins are ignored.

Real cross-window snapshots are left alone while multiple windows are open.
The mod does not repair a lost document or a failed docshell transfer. It also
does not change Glance blur, page transparency, window-sync settings or website
CSS.

Checks respond to native snapshot changes, tab selection, window focus and
window open/close events. There is no continuous polling.

## Install on macOS or Windows

Install Sine in the intended Zen profile, then install this subfolder:

```text
https://github.com/toby-wong/sine-mods/tree/main/window-sync-recovery
```

Enable `sine.allow-unsafe-js` in `about:config`, enable **Window Sync Recovery**
under **Settings → Sine Mods**, and restart Zen. Repeat for other profiles.
There are no additional settings.

For installation from a checkout, use the collection's
[local installer instructions](../README.md#install-or-update-from-a-local-checkout)
and append `--mods window-sync-recovery`.

Disable/remove the mod in Sine to stop future cleanup. Pages already repaired
remain intact. Native Windows browser behavior has not been tested.

## Validation

All 21 integration checks passed on Zen 1.24b on macOS, including preservation
of an unsaved draft and native split, multiple-window exclusion, and unload/reload.

Run the browser suite against a separately launched disposable Zen profile
with Sine and this mod installed. Never enable a privileged debugger on an
everyday profile.

```sh
node --check window-sync-recovery/window-sync-recovery.uc.js
python3 window-sync-recovery/tests/integration.py \
  --profile "/path/to/test-profile" --port 2842 \
  --report "/path/outside/checkout/window-sync-recovery.json"
```
