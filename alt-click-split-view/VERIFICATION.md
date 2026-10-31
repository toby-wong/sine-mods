# Alt-click Split View verification

## 1.4.4-local — platform compatibility

Eight Node tests passed, including execution of the parent hook against simulated
Windows, macOS, and Linux native tab-opening behavior. They verify that only the
platform's tab accelerator is synthesized, native navigation metadata is kept,
the source tab is reused, and an absent Glance shortcut preference does not
swallow Alt-click. Glance conflicts and a disabled mod still defer to native
handling. The accelerator and missing-preference cases failed against
1.4.3-local before the fix.

Live tests ran in a separate disposable profile on macOS with Zen 1.24b,
Alt-click Split View 1.4.4-local, and Auto Glance 0.2.2:

- All 15 split regressions passed, covering ordinary and website-controlled
  links, frames, Glance, pins/Essentials, repeated splits, the four-pane limit,
  and hot reload. Document identity, drafts, and request counts confirmed that
  splitting preserved the source page.
- All 25 Auto Glance integration checks passed, including Command-click
  background tabs, Glance alignment and blur, POST data, and modified clicks.
- Unloading preserved both live pages and restored the Essential source.
  A separate restart check restored a managed split; separating it restored the
  Essential and destination pin state while keeping the restored documents alive.

The disposable browser was closed, its automation port was closed, and hashes
confirmed that the everyday profile's installed mod files and registry were
unchanged. Machine-specific reports are outside Git; their location is recorded
in the ignored `.local-windows-validation.json`.

Windows and Linux routing were simulated. Native desktop input on those
platforms has not been tested.

## 1.4.3-local — original macOS installation record

At the original macOS validation, the local Alt-click Split View patch, version
1.4.3-local, was active in the running Zen profile. The original window's tab
identities, browsing contexts, pin state, and geometry were unchanged by
installation. The temporary setup window was closed and Zen remained open.

Option-click is captured before website router handlers and still goes through Firefox's native click validation. Links inside Glance use the preview itself as the source. Pinned splits reuse the existing page instead of loading a duplicate. Essentials temporarily enter the pinned split and return when separated or when the other panes close. Original pin state is stored in SessionStore and survives restart.

The Hammerspoon Option-click guard now preserves the modifier for background Zen and Arc windows. Its other shortcuts and startup code are unchanged. This was verified with five isolated policy checks; browser clicks were tested with real WebDriver input in a disposable profile.

Fifteen split regression cases passed, including ordinary and website-controlled links, iframes, Glance conversion, pinned and Essential pages, repeated openings, the four-pane limit, closing panes, and hot reload. Original document identity, drafts, and network request counts verified that splitting did not reload the source. The thirteen existing Auto Glance checks also passed. Restart and unload checks confirmed Essential restoration and page preservation. JavaScript syntax and three existing unit tests passed.

Search configuration, keyboard shortcuts, containers, Auto Glance source, and all other mod registrations are unchanged. Only the patched mod is protected from upstream replacement. No application-bundle files were edited. Temporary automation ports are closed and the separate test browser has stopped.

Source and notes now live in this directory. The ignored `.local-setup.json`
records the machine-specific original backup location, which is outside Git.
Machine-readable results: `reports/final-verification.json`, `reports/regression.json`, `reports/auto-glance-compatibility.json`, and `reports/restart-state.json`.

To disable this patch, disable Alt-click Split View in Sine. Its unload handler separates managed splits and restores their pin state without closing their pages. For a full rollback, first disable the mod (or separate its splits), restore the backed-up mod directory, and restore only that mod's registry entry from `before/mods-at-install.json`. Restore only the Option-click block from `before/init-at-install.lua` if rolling back the Hammerspoon change, so subsequent unrelated configuration edits are preserved.
