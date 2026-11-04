// Native profile discovery and optional macOS external-link routing.
const VERSION = "0.2.0";
const TARGET_PREF = "uc.profile-switcher.external-profile";
const MODULE_URI = "chrome://sine/content/profile-switcher/ExternalProfileRouting.sys.mjs";
const HOOK = "__profileSwitcherExternalRouting";
let installed;

export async function readNativeProfiles() {
  const root = Services.dirsvc.get("UAppData", Ci.nsIFile);
  const data = await IOUtils.readUTF8(PathUtils.join(root.path, "profiles.ini"));
  const parser = Cc["@mozilla.org/xpcom/ini-parser-factory;1"]
    .getService(Ci.nsIINIParserFactory).createINIParser(null);
  parser.initFromString(data);
  const profiles = [];
  for (const section of parser.getSections()) {
    if (!/^Profile\d+$/.test(section)) continue;
    try {
      const file = Cc["@mozilla.org/file/local;1"].createInstance(Ci.nsIFile);
      const path = parser.getString(section, "Path");
      if (parser.getString(section, "IsRelative") === "1") file.setRelativeDescriptor(root, path);
      else file.initWithPath(path);
      profiles.push({ name: parser.getString(section, "Name"), path: file.path });
    } catch (error) {
      console.error("[Profile Switcher] Invalid profile entry", section, error);
    }
  }
  return profiles;
}

export function launchProfile(profile, urls) {
  const file = Cc["@mozilla.org/file/local;1"].createInstance(Ci.nsIFile);
  file.initWithPath(profile.path);
  if (!file.exists() || !file.isDirectory()) {
    throw new Error("That profile folder is unavailable. Check Manage profiles.");
  }
  const { SelectableProfileService } =
    ChromeUtils.importESModule("resource:///modules/profiles/SelectableProfileService.sys.mjs");
  SelectableProfileService.launchInstance({ path: file.path }, urls);
}

// Kept independent of browser globals so routing, fallbacks, and unload races
// can be checked without opening real profiles.
export function createCommandRouter(env) {
  let active = true;
  const tasks = new Set();
  const handle = function (command, ...rest) {
    const native = () => env.original.call(this, command, ...rest);
    const target = env.getTarget();
    if (!active || !target || target === env.currentPath ||
        command.state !== env.remoteExplicit || !command.length || command.length % 2) return native();

    const args = [], urls = [];
    for (let i = 0; i < command.length; i += 2) {
      const flag = command.getArgument(i), url = command.getArgument(i + 1);
      // This is the request shape macOS uses for links from another app.
      // Profile activation, private windows, new-window commands, and all
      // navigation inside a browser stay with their original native handlers.
      if (flag !== "-url" || !env.isWebURL(url)) return native();
      args.push(flag, url);
      urls.push(url);
    }
    command.removeArguments(0, command.length - 1);
    command.preventDefault = true;
    const task = (async () => {
      try {
        const profiles = await env.readProfiles();
        if (active && env.getTarget() === target) {
          const profile = profiles.find(item => item.path === target);
          if (!profile) throw new Error("The external-link profile is no longer registered.");
          await env.launch(profile, urls);
          return;
        }
      } catch (error) {
        env.report(error);
      }
      env.replay(args);
    })();
    tasks.add(task);
    // The native command-line interface is synchronous. A handled external URL
    // can be dispatched asynchronously once its original request is consumed.
    task.then(() => tasks.delete(task), error => {
      tasks.delete(task);
      env.report(error);
    });
    return undefined;
  };
  return {
    handle,
    destroy: () => { active = false; },
    idle: () => Promise.all([...tasks]),
  };
}

export function install() {
  if (Services.appinfo.OS !== "Darwin") return { status: "unsupported-platform" };
  if (installed) return { status: "ready", version: VERSION };
  const { CommandLineHandler } =
    ChromeUtils.importESModule("resource:///modules/profiles/SelectableProfileService.sys.mjs");
  const { PrivateBrowsingUtils } =
    ChromeUtils.importESModule("resource://gre/modules/PrivateBrowsingUtils.sys.mjs");
  const prototype = CommandLineHandler.prototype;
  prototype[HOOK]?.uninstall();
  const original = prototype.handle;
  const descriptor = Object.getOwnPropertyDescriptor(prototype, "handle");
  const native = new CommandLineHandler();
  const router = createCommandRouter({
    original,
    currentPath: Services.dirsvc.get("ProfD", Ci.nsIFile).path,
    remoteExplicit: Ci.nsICommandLine.STATE_REMOTE_EXPLICIT,
    getTarget: () => PrivateBrowsingUtils.permanentPrivateBrowsing ||
      !Services.prefs.getBoolPref("sine.allow-unsafe-js", false) ||
      Services.prefs.getBoolPref("sine.mods.disable-all", false) ? "" :
      Services.prefs.getStringPref(TARGET_PREF, ""),
    isWebURL: value => {
      try {
        const uri = Services.io.newURI(value);
        return uri.schemeIs("https") || uri.schemeIs("http");
      } catch { return false; }
    },
    readProfiles: readNativeProfiles,
    launch: launchProfile,
    // Native openUrls validates the argument pairs and delegates directly to
    // Firefox's final URL handler. It does not re-enter this profile hook.
    replay: args => {
      if (!native.openUrls(args)) throw new Error("Native external-link fallback was rejected.");
    },
    report: error => console.error("[Profile Switcher] External-link routing", error),
  });
  const uninstall = () => {
    router.destroy();
    if (prototype.handle === router.handle) {
      if (descriptor) Object.defineProperty(prototype, "handle", descriptor);
      else delete prototype.handle;
    }
    if (prototype[HOOK]?.uninstall === uninstall) delete prototype[HOOK];
    installed = null;
  };
  prototype.handle = router.handle;
  Object.defineProperty(prototype, HOOK, { value: { uninstall, version: VERSION }, configurable: true });
  installed = { uninstall, router };
  // A process-level listener survives closing the last window on macOS. It
  // retains no DOM windows and is removed when Sine disables/removes the mod.
  ChromeUtils.importESModule("chrome://userscripts/content/core/manager.sys.mjs").default
    .addUnloadListener(MODULE_URI, null, uninstall);
  return { status: "ready", version: VERSION };
}

export function uninstall() {
  installed?.uninstall();
}
