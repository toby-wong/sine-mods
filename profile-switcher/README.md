# Profile Switcher

Version **0.2.1** adds a profile button above Zen's tabs. It shows the current
profile name and a colour marker. Window titles also include the name, making
profiles identifiable in the operating system's window list.

The button uses Zen's dropdown chevron, native button colours, typography, and
focus outline. Its corner radius follows the sidebar controls, and its inset
and vertical gaps align with the address bar and Essentials. The colour marker
identifies the profile while the rest of the control follows the browser theme.

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

## Links from other apps on macOS

Open the profile button → **Links from other apps** and choose the destination
profile. For example, choose **Work** in both Work and Personal to send external
web links to Work regardless of which profile macOS contacts.

This setting applies to the current profile, so configure it in every profile
you use. It takes effect immediately. The destination opens if it is closed,
and routing continues when the receiving profile has no open windows.

When Zen is not running, its native default profile determines startup. Choose
the same profile as the default in **Manage profiles…** for consistent behaviour.
The mod does not change that native default.

Only HTTP/HTTPS links received from other apps are redirected. Clicking links,
opening tabs, and browsing private pages inside Zen keep their normal behaviour.
If the destination is removed or cannot be launched, the link falls back to
normal routing in the receiving profile.

Choose **Use normal browser routing** to turn this off. This routing feature is
currently for macOS; the profile button and native profile switching remain
available on Windows and Linux.

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
- Sine removes the external-link handler when the mod is disabled or removed.
  The handler also respects Sine's JavaScript and disable-all switches.

Browser validation and platform limits are recorded in [AGENTS.md](AGENTS.md).
