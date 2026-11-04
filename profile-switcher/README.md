# Profile Switcher

Version **0.1.0** adds a profile button above Zen's tabs. It shows the current
profile name and a colour marker. Window titles also include the name, making
profiles identifiable in the operating system's window list.

Click the button and choose a profile to activate its existing window or launch
it if closed. Your current profile stays open. **Manage profiles…** opens Zen's
native `about:profiles` page for creating and renaming profiles.

When launching a closed profile, its startup setting controls which tabs return.
Enable **Open previous windows and tabs** in each profile to restore ordinary
tabs as well as pinned tabs.

## Install on macOS or Windows

Install Sine in each profile where you want the button, then enable
`sine.allow-unsafe-js` in `about:config`.

In Sine's custom repository field, install:

```text
https://github.com/toby-wong/sine-mods/tree/main/profile-switcher
```

For a local checkout, use the collection's [installer](../README.md#install-or-update-from-a-local-checkout)
with `--mods profile-switcher`. Fully quit Zen before using that installer, then
restart it. Install the mod separately in each profile.

Configure **Profile colour** and **Include the profile name in window titles**
under **Settings → Sine Mods → Profile Switcher → Configure**. These settings
apply immediately and stay local to the profile. They do not alter Space themes.

## Behaviour

- Uses existing registered profiles, including legacy Zen profiles.
- Reads `profiles.ini` when the menu opens or the window activates. Profile names
  can change without changing their identity: switching uses the profile path.
- Uses Zen/Firefox's native profile launcher and activation command.
- Switches windows without moving the current page, cookies, containers, or tabs.
- Preserves native window titles, including their private-browsing indication.
- Supports mouse, Enter/Space, and Down Arrow on the button, with native menu
  keyboard navigation. Private windows are labelled explicitly.
- Disabling or reloading removes the UI and restores native title handling.

Browser validation and platform limits are recorded in [AGENTS.md](AGENTS.md).
