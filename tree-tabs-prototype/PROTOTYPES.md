# Prototype history

The active version is **0.1.1**. Split sessions use Zen's normal sidebar
behavior and do not participate in the prototype's tree.

The repository was created after the first two prototypes were deployed.
Their commits were reconstructed from the saved source snapshots, followed
by an explicit revert. Commit dates therefore describe when this history was
recorded, not the original deployment times.

| Tag | Status |
| --- | --- |
| `prototype/v0.1.0` | Original prototype: ordinary tabs form trees; splits are excluded. |
| `prototype/v0.2.0` | Split-session experiment, rolled back after the user reported missing split tabs. |
| `prototype/v0.1.0-restored` | Restored ordinary-tab prototype, with the split-session change reverted. |
| `prototype/v0.1.1` | Whole branches follow sidebar moves and moves between Spaces. |

The v0.2.0 automated tests and installation checks passed, but did not catch
the subsequent user-visible problem. Its root cause has not been established.
The rollback restored the previous source and stylesheet, removed the
split-specific tree metadata, and preserved the current tabs and split
layouts. A live check confirmed the restored version and visible split rows.

## v0.1.1 validation

The ordinary-tab branch-move update passed 25 existing Tree Tabs checks,
17 branch-move checks, and 25 Auto Glance regression checks in an isolated
Zen profile. These cover upward/downward reordering, nested and collapsed
branches, multi-tab moves, Space menu moves, late workspace attribute changes,
native drop handling, animation cleanup, and preserved document identities.
The macOS pointer automation did not deliver a drop event reliably; the native
drop-handler check uses a synthesized drop event.

Live checks in the existing user window confirmed collapsed-branch reordering
and cross-Space moves, with all temporary tabs removed afterward. Existing
tabs, tree relationships, split layouts, focused pages, selected tab, active
Space, and Auto Glance state were preserved.

The source and session backup, together with test and live verification
reports, is:

`/Users/tobywo/Documents/Browser Migration Backups/2026-10-31_162055_Zen-Tree-Branch-Moves`

## Compare versions

```sh
git log --oneline --decorate
git diff prototype/v0.1.0 prototype/v0.2.0 -- tree-tabs.uc.js tree-tabs.css
git show prototype/v0.2.0:tree-tabs.uc.js
```

## Future prototypes

1. Check `git status` before changing files and preserve unrelated edits.
2. Start a branch for the change and commit each reviewable prototype.
3. Record validation results and tag versions that are installed.
4. Validate the live sidebar as well as isolated tests; preserve page state,
   selection, workspaces, and existing split layouts.
5. Use a revert commit to remove an installed change, retaining its history.

Git tracks source, tests, and documentation. Browser profiles, session data,
generated reports, and `.local-setup.json` stay outside version control.
The local setup file identifies the installation and backup locations.

Checking out or reverting a commit does not by itself change the running
browser. Install the chosen source into the profile's Sine mod directory and
reload the mod safely. Do not modify the signed Zen application or replace
the whole browser profile to roll back a code change.
