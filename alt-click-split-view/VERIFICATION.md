# Zen split fix — installation record

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
