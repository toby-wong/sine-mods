// ==UserScript==
// @name           Profile Switcher
// @version        0.2.1
// @description    Identify the current Zen profile and switch profile windows.
// @include        chrome://browser/content/browser.xhtml
// ==/UserScript==

(() => {
  "use strict";
  const VERSION = "0.2.1";
  const PREFIX = "uc.profile-switcher.";
  const ROUTING_MODULE = `chrome://sine/content/profile-switcher/ExternalProfileRouting.sys.mjs?v=${VERSION}`;
  const COLOURS = Object.freeze({
    blue: "#377cde", purple: "#9765cf", green: "#26875f",
    orange: "#c97325", pink: "#c64e89", teal: "#168d96",
  });
  const cleanName = name => String(name || "").replace(/[\u0000-\u001f\u007f]/g, " ").trim() || "Unnamed profile";

  function profileColour(path, preference = "auto") {
    if (Object.hasOwn(COLOURS, preference)) return COLOURS[preference];
    let hash = 0;
    for (const char of path) hash = (Math.imul(hash, 31) + char.codePointAt(0)) >>> 0;
    return Object.values(COLOURS)[hash % Object.keys(COLOURS).length];
  }

  function catalogue(entries, currentPath, fallbackName) {
    const unique = new Map();
    for (const entry of entries) {
      if (typeof entry.path !== "string" || !entry.path || unique.has(entry.path)) continue;
      unique.set(entry.path, {
        path: entry.path, name: cleanName(entry.name), current: entry.path === currentPath,
      });
    }
    if (!unique.has(currentPath)) {
      unique.set(currentPath, { path: currentPath, name: cleanName(fallbackName), current: true });
    }
    return [...unique.values()].sort((a, b) =>
      Number(b.current) - Number(a.current) || a.name.localeCompare(b.name));
  }

  async function activateProfile(path, { readProfiles, currentPath, focus, launch }) {
    // Read again at the moment of selection: a menu can outlive a rename or
    // deletion in another profile. Paths, not display names, identify profiles.
    const profiles = await readProfiles();
    const profile = profiles.find(item => item.path === path);
    if (!profile) throw new Error("That profile is no longer registered. Reopen the menu to refresh.");
    if (path === currentPath) return focus();
    return launch(profile);
  }

  function createController(win, env) {
    const doc = win.document;
    let destroyed = false, generation = 0, profiles = [], current = null;
    let row, button, label, dot, popup, errorMessage = "", opening = false;
    const originalTitle = win.gBrowser.getWindowTitleForBrowser;
    const titleDescriptor = Object.getOwnPropertyDescriptor(win.gBrowser, "getWindowTitleForBrowser");
    const api = { version: VERSION, status: "starting", refresh, openMenu, switchTo, destroy };
    const xul = tag => doc.createXULElement(tag);
    const html = tag => doc.createElementNS("http://www.w3.org/1999/xhtml", tag);

    function windowTitle(...args) {
      const nativeTitle = originalTitle.apply(this, args);
      return !destroyed && current && env.prefs.getBoolPref(PREFIX + "show-in-title", true)
        ? `[${current.name}] ${nativeTitle}` : nativeTitle;
    }

    function mount() {
      const toolbar = doc.getElementById("TabsToolbar");
      if (toolbar?.parentNode && row.parentNode !== toolbar.parentNode) {
        toolbar.before(row);
      }
    }

    function render() {
      if (destroyed || !current) return;
      label.textContent = current.name + (env.isPrivate ? " · Private" : "");
      const colour = profileColour(current.path, env.prefs.getStringPref(PREFIX + "colour", "auto"));
      row.style.setProperty("--profile-switcher-colour", colour);
      button.setAttribute("title", `${label.textContent} — switch profile`);
      button.setAttribute("aria-label", `${label.textContent}. Switch profiles`);
      api.current = { ...current, colour };
      win.gBrowser.updateTitlebar();
    }

    async function refresh() {
      const request = ++generation;
      try {
        const entries = await env.readProfiles();
        if (destroyed || request !== generation) return;
        profiles = catalogue(entries, env.currentPath, env.fallbackName);
        current = profiles.find(profile => profile.current);
        api.status = "ready";
        delete api.error;
        render();
      } catch (error) {
        if (destroyed || request !== generation) return;
        api.status = "error";
        api.error = String(error);
        errorMessage = "Could not read the profile list. Try Manage profiles.";
        if (!current) {
          profiles = catalogue([], env.currentPath, env.fallbackName);
          current = profiles[0];
          render();
        }
        win.console.error("[Profile Switcher]", error);
      }
    }

    async function switchTo(path) {
      if (destroyed) return;
      try {
        await activateProfile(path, {
          readProfiles: env.readProfiles,
          currentPath: env.currentPath,
          focus: () => { if (!destroyed) win.focus(); },
          launch: profile => { if (!destroyed) return env.launch(profile); },
        });
        errorMessage = "";
      } catch (error) {
        if (destroyed) return;
        api.error = String(error);
        await openMenu(error.message || "Could not open that profile.");
      }
    }

    function fillMenu() {
      popup.replaceChildren();
      for (const profile of profiles) {
        const item = xul("menuitem");
        item.classList.add("profile-switcher-item");
        item.setAttribute("label", profile.name + (profile.current ? " (current)" : ""));
        item.setAttribute("type", "radio");
        item.setAttribute("name", "profile-switcher-profile");
        item.setAttribute("checked", String(profile.current));
        item.setAttribute("data-profile-path", profile.path);
        item.setAttribute("tooltiptext", profile.name);
        if (profile.current) item.setAttribute("disabled", "true");
        item.addEventListener("command", () => { void switchTo(profile.path); });
        popup.append(item);
      }
      popup.append(xul("menuseparator"));
      const routing = xul("menu");
      routing.id = "profile-switcher-external-links";
      routing.setAttribute("label", "Links from other apps");
      if (env.externalRoutingSupported === false) {
        routing.setAttribute("disabled", "true");
        routing.setAttribute("tooltiptext", "External-link routing is available on macOS.");
      }
      const destinations = xul("menupopup");
      const target = env.prefs.getStringPref(PREFIX + "external-profile", "");
      for (const profile of [{ name: "Use normal browser routing", path: "" }, ...profiles]) {
        const item = xul("menuitem");
        item.classList.add("profile-switcher-external-destination");
        item.setAttribute("label", profile.name);
        item.setAttribute("type", "radio");
        item.setAttribute("name", "profile-switcher-external-profile");
        item.setAttribute("checked", String(profile.path === target));
        item.setAttribute("data-profile-path", profile.path);
        item.addEventListener("command", () =>
          env.prefs.setStringPref(PREFIX + "external-profile", profile.path));
        destinations.append(item);
      }
      routing.append(destinations);
      popup.append(routing);
      const manage = xul("menuitem");
      manage.id = "profile-switcher-manage";
      manage.setAttribute("label", "Manage profiles…");
      manage.addEventListener("command", () => env.manage());
      popup.append(manage);
      if (errorMessage) {
        const error = xul("menuitem");
        error.setAttribute("label", errorMessage);
        error.setAttribute("disabled", "true");
        popup.append(error);
      }
    }

    async function openMenu(message = "") {
      if (destroyed || opening) return;
      if (popup.state === "open" || popup.state === "showing") {
        popup.hidePopup();
        return;
      }
      opening = true;
      errorMessage = message;
      try { await refresh(); }
      finally { opening = false; }
      if (destroyed) return;
      fillMenu();
      popup.openPopup(button, "after_start", 0, 3, false, false);
    }

    const onClick = event => { if (event.button === 0) void openMenu(); };
    const onKey = event => {
      if (event.key === "ArrowDown" && !event.altKey && !event.ctrlKey && !event.metaKey) {
        event.preventDefault();
        void openMenu();
      }
    };
    const popupShown = event => {
      if (event.target === popup) button.setAttribute("aria-expanded", "true");
    };
    const popupHidden = event => {
      if (event.target === popup) button.setAttribute("aria-expanded", "false");
    };
    const activated = () => { void refresh(); };
    const prefObserver = { observe: render };
    const onUnload = event => {
      if (event.target === win || event.target === doc) destroy();
    };

    function destroy() {
      if (destroyed) return;
      destroyed = true;
      generation++;
      env.prefs.removeObserver(PREFIX, prefObserver);
      win.removeEventListener("activate", activated);
      win.removeEventListener("aftercustomization", mount);
      win.removeEventListener("unload", onUnload);
      popup?.hidePopup();
      popup?.remove();
      row?.remove();
      if (win.gBrowser.getWindowTitleForBrowser === windowTitle) {
        if (titleDescriptor) Object.defineProperty(win.gBrowser, "getWindowTitleForBrowser", titleDescriptor);
        else delete win.gBrowser.getWindowTitleForBrowser;
      }
      win.gBrowser.updateTitlebar();
      api.status = "destroyed";
      if (win.ProfileSwitcher === api) delete win.ProfileSwitcher;
    }

    row = xul("hbox");
    row.id = "profile-switcher-row";
    button = html("button");
    button.id = "profile-switcher-button";
    button.type = "button";
    button.setAttribute("aria-haspopup", "menu");
    button.setAttribute("aria-expanded", "false");
    dot = html("span");
    dot.className = "profile-switcher-dot";
    dot.setAttribute("aria-hidden", "true");
    label = html("span");
    label.className = "profile-switcher-name";
    label.textContent = "Profile";
    const arrow = html("span");
    arrow.className = "profile-switcher-arrow";
    arrow.setAttribute("aria-hidden", "true");
    button.append(dot, label, arrow);
    row.append(button);
    popup = xul("menupopup");
    popup.id = "profile-switcher-menu";
    (doc.getElementById("mainPopupSet") || doc.documentElement).append(popup);
    button.addEventListener("click", onClick);
    button.addEventListener("keydown", onKey);
    popup.addEventListener("popupshown", popupShown);
    popup.addEventListener("popuphidden", popupHidden);
    env.prefs.addObserver(PREFIX, prefObserver);
    win.addEventListener("activate", activated);
    win.addEventListener("aftercustomization", mount);
    win.addEventListener("unload", onUnload);
    win.gBrowser.getWindowTitleForBrowser = windowTitle;
    mount();
    api.ready = refresh();
    return api;
  }

  async function readNativeProfiles() {
    return ChromeUtils.importESModule(ROUTING_MODULE).readNativeProfiles();
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { catalogue, profileColour, activateProfile, createController, readNativeProfiles };
    return;
  }

  window.ProfileSwitcher?.destroy();
  let cancelled = false, controller;
  const destroy = () => {
    cancelled = true;
    controller?.destroy();
    if (window.ProfileSwitcher === pending) delete window.ProfileSwitcher;
  };
  const pending = { version: VERSION, status: "starting", destroy };
  window.ProfileSwitcher = pending;
  window.addUnloadListener?.(destroy);
  pending.ready = (async () => {
    await gZenStartup.promiseInitialized;
    if (cancelled || window.closed) return;
    const profile = Services.dirsvc.get("ProfD", Ci.nsIFile);
    const routing = ChromeUtils.importESModule(ROUTING_MODULE);
    const routingStatus = routing.install();
    const { PrivateBrowsingUtils } =
      ChromeUtils.importESModule("resource://gre/modules/PrivateBrowsingUtils.sys.mjs");
    for (const key of ["colour", "show-in-title", "external-profile"]) {
      Services.prefs.setBoolPref("services.sync.prefs.sync." + PREFIX + key, false);
      Services.prefs.setBoolPref("services.sync.prefs.sync-seen." + PREFIX + key, false);
    }
    controller = createController(window, {
      prefs: Services.prefs,
      currentPath: profile.path,
      fallbackName: profile.leafName,
      isPrivate: PrivateBrowsingUtils.isWindowPrivate(window),
      externalRoutingSupported: routingStatus.status === "ready",
      readProfiles: readNativeProfiles,
      launch: entry => routing.launchProfile(entry),
      manage: () => window.openTrustedLinkIn("about:profiles", "tab"),
    });
    window.ProfileSwitcher = controller;
    await controller.ready;
  })().catch(error => {
    pending.status = "error";
    pending.error = String(error);
    console.error("[Profile Switcher]", error);
  });
})();
