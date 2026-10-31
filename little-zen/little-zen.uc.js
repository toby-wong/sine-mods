// ==UserScript==
// @name           Little Zen
// @version        0.1.0
// @description    Compact temporary windows with native search and Space promotion.
// @include        chrome://browser/content/browser.xhtml
// ==/UserScript==

(() => {
  "use strict";

  const PREFIX = "uc.little-zen.";
  const MARKER = "little-zen";
  const SIZES = { small: [720, 560], medium: [900, 680], large: [1100, 800] };
  const isWebURL = url => /^https?:\/\//i.test(url || "");
  const report = error => console.error("[Little Zen]", error);
  const enabled = () => Services.prefs.getBoolPref(PREFIX + "enabled", true);

  window.LittleZen?.destroy();

  const { PrivateBrowsingUtils } = ChromeUtils.importESModule(
    "resource://gre/modules/PrivateBrowsingUtils.sys.mjs"
  );
  const { BrowserWindowTracker } = ChromeUtils.importESModule(
    "resource:///modules/BrowserWindowTracker.sys.mjs"
  );
  const root = document.documentElement;
  const cleanup = [];
  const nodes = [];
  let destroyed = false;
  let cleanupRouting;
  let resizeTimer;

  function listen(target, name, handler, options) {
    target.addEventListener(name, handler, options);
    cleanup.push(() => target.removeEventListener(name, handler, options));
  }

  function element(tag, attributes, parent) {
    const node = document.createXULElement(tag);
    for (const [name, value] of Object.entries(attributes || {})) {
      node.setAttribute(name, value);
    }
    parent?.appendChild(node);
    nodes.push(node);
    return node;
  }

  function ready(win) {
    if (win.gBrowserInit?.delayedStartupFinished) {
      return Promise.resolve(win.gZenStartup?.promiseInitialized).then(() => win);
    }
    return new Promise((resolve, reject) => {
      const finish = subject => {
        if (subject !== win) return;
        Services.obs.removeObserver(finish, "browser-delayed-startup-finished");
        win.removeEventListener("unload", closed);
        Promise.resolve(win.gZenStartup?.promiseInitialized).then(() => resolve(win), reject);
      };
      const closed = () => Services.tm.dispatchToMainThread(() => {
        // A newly opened window also unloads its initial about:blank document.
        // Only an actual closed window cancels browser startup.
        if (!win.closed) return;
        Services.obs.removeObserver(finish, "browser-delayed-startup-finished");
        win.removeEventListener("unload", closed);
        reject(new Error("The new window closed before startup completed."));
      });
      Services.obs.addObserver(finish, "browser-delayed-startup-finished");
      win.addEventListener("unload", closed);
    });
  }

  function realTabs(win = window) {
    // Zen's gBrowser.tabs can omit tabs inside collapsed folders/groups.
    return [...(win.gZenWorkspaces?.allStoredTabs || win.gBrowser.tabs)].filter(
      tab => !tab.closing && !tab.hasAttribute("zen-empty-tab")
    );
  }

  function isPrivate(win) {
    return PrivateBrowsingUtils.isWindowPrivate(win);
  }

  function regularWindows() {
    return [...BrowserWindowTracker.orderedWindows].filter(win =>
      !win.closed && win !== window && !win._littleZenInfo &&
      !win.document.documentElement.hasAttribute(MARKER) &&
      !win.document.documentElement.hasAttribute("mini-window") &&
      isPrivate(win) === isPrivate(window) &&
      (isPrivate(win) || win.gZenWorkspaces?.currentWindowIsSyncing)
    );
  }

  function preferredMainWindow() {
    const wins = regularWindows();
    return wins.find(win =>
      win.browsingContext.id === window._littleZenInfo?.originWindowId
    ) || wins[0] || null;
  }

  function destinationSpace(win, spaceId) {
    if (!win || isPrivate(win)) return null;
    const spaces = win.gZenWorkspaces.getWorkspaces();
    const desired = spaceId || window._littleZenInfo?.originSpaceId;
    return spaces.find(space => space.uuid === desired) ||
      spaces.find(space => space.uuid === win.gZenWorkspaces.activeWorkspace) || null;
  }

  function currentContext() {
    if (isPrivate(window)) return 0;
    if (window._littleZenInfo) return gBrowser.selectedTab?.userContextId || 0;
    return gZenWorkspaces.getCurrentSpaceContainerId();
  }

  function sizeFor(win = window) {
    const size = Services.prefs.getStringPref(PREFIX + "window-size", "medium");
    const [width, height] = SIZES[size] || SIZES.medium;
    return {
      width: Math.min(width, win.screen.availWidth),
      height: Math.min(height, win.screen.availHeight),
    };
  }

  function markWindow(win, options = {}) {
    const origin = window._littleZenInfo;
    win._littleZenInfo = {
      originWindowId: origin?.originWindowId || window.browsingContext.id,
      originSpaceId: origin?.originSpaceId || gZenWorkspaces.activeWorkspace,
      contextId: options.userContextId ?? currentContext(),
      ...options,
    };
    // Set before Zen's startup observers run, not after a synced window exists.
    win._zenStartupSyncFlag = "unsynced";
    win._zenStartupUnsyncedUserContextId = win._littleZenInfo.contextId;
    win.addEventListener("MozBeforeInitialXULLayout", () => {
      if (!win.closed) {
        win.document.documentElement.setAttribute(MARKER, "true");
        // Browser windows share a geometry entry in xulstore. A temporary
        // window must not replace the main window's saved size and position.
        win.document.documentElement.removeAttribute("persist");
      }
    }, { once: true });
    return win;
  }

  function open(options = {}) {
    if (!enabled() || destroyed) return null;
    if (options.url && options.url !== "about:blank" && !isWebURL(options.url)) {
      throw new Error("Little Zen's link command accepts only HTTP and HTTPS links.");
    }
    const args = Cc["@mozilla.org/supports-string;1"].createInstance(Ci.nsISupportsString);
    args.data = "about:blank";
    const size = sizeFor();
    const win = OpenBrowserWindow({
      args,
      private: isPrivate(window),
      zenSyncedWindow: Services.prefs.getBoolPref("zen.window-sync.prefer-unsynced-windows", false),
      features: `width=${size.width},height=${size.height}`,
    });
    markWindow(win, { ...options, fresh: true });
    return win;
  }

  async function promote(spaceId) {
    const info = window._littleZenInfo;
    if (!info || info.promoting || destroyed || !enabled()) return null;
    const tab = gBrowser.selectedTab;
    if (!tab || tab.hasAttribute("zen-empty-tab")) return null;
    info.promoting = true;
    try {
      let target = preferredMainWindow();
      if (!target) {
        const args = Cc["@mozilla.org/supports-string;1"].createInstance(Ci.nsISupportsString);
        args.data = "about:blank";
        target = OpenBrowserWindow({
          args,
          private: isPrivate(window),
          zenSyncedWindow: !Services.prefs.getBoolPref("zen.window-sync.prefer-unsynced-windows", false),
        });
        await ready(target);
      }
      // Opening the first regular window can make Sine reload all controllers.
      // The requested move may continue while its replacement remains enabled.
      if (!window.LittleZen || !enabled() || tab.closing || target.closed) return null;
      // Never let a private tab escape into a regular window.
      if (isPrivate(target) !== isPrivate(window)) {
        throw new Error("The destination window has a different privacy context.");
      }
      const destination = destinationSpace(target, spaceId)?.uuid;
      const newTab = target.gBrowser.adoptTab(tab, {
        tabIndex: Infinity,
        selectTab: true,
        spaceId: isPrivate(target) ? null : destination,
      });
      if (!newTab) throw new Error("Zen could not move this tab. It remains in Little Zen.");
      if (!isPrivate(target) && destination) {
        await target.gZenWorkspaces.changeWorkspaceWithID(destination);
      }
      target.gBrowser.selectedTab = newTab;
      target.focus();
      newTab.linkedBrowser.focus();
      if (!window.closed && realTabs().length === 0) window.close();
      return newTab;
    } finally {
      delete info.promoting;
    }
  }

  function fillSpaces(popup) {
    popup.replaceChildren();
    const target = preferredMainWindow();
    const spaces = isPrivate(window) ? [] : (target?.gZenWorkspaces.getWorkspaces() || []);
    if (!spaces.length) {
      const item = document.createXULElement("menuitem");
      item.setAttribute("label", isPrivate(window) ? "Keep in a Private Window" : "Open in Main Window");
      item.addEventListener("command", () => promote().catch(report), { once: true });
      popup.appendChild(item);
      return;
    }
    for (const space of spaces) {
      const item = document.createXULElement("menuitem");
      item.setAttribute("label", space.name || "Space");
      item.setAttribute("data-space-id", space.uuid);
      item.addEventListener("command", () => promote(space.uuid).catch(report), { once: true });
      popup.appendChild(item);
    }
  }

  function fillTabs(popup) {
    popup.replaceChildren();
    for (const tab of realTabs()) {
      const item = document.createXULElement("menuitem");
      item.setAttribute("label", tab.label || "New tab");
      item.setAttribute("type", "radio");
      item.setAttribute("checked", tab === gBrowser.selectedTab ? "true" : "false");
      item.addEventListener("command", () => {
        if (!tab.closing) gBrowser.selectedTab = tab;
      }, { once: true });
      popup.appendChild(item);
    }
  }

  function updateControls() {
    const tabButton = document.getElementById("little-zen-tabs");
    if (tabButton) {
      const count = realTabs().length;
      tabButton.setAttribute("label", `${count} ${count === 1 ? "tab" : "tabs"}`);
      tabButton.hidden = count < 2;
    }
    const keepButton = document.getElementById("little-zen-keep");
    if (keepButton) {
      const space = destinationSpace(preferredMainWindow());
      const label = isPrivate(window) ? "Keep Private" : `Open in ${space?.name || "Main Window"}`;
      keepButton.setAttribute("label", label);
      keepButton.setAttribute("tooltiptext",
        `${label} (${Services.appinfo.OS === "Darwin" ? "⌘O" : "Ctrl+O"})`);
    }
  }

  function installMiniUI() {
    if (!window._littleZenInfo || destroyed) return;
    root.toggleAttribute(MARKER, enabled());
    const toolbar = document.getElementById("navigator-toolbox");
    if (!toolbar || document.getElementById("little-zen-controls")) return;
    const controls = element("hbox", { id: "little-zen-controls", align: "center" }, toolbar);
    const tabButton = element("toolbarbutton", {
      id: "little-zen-tabs", type: "menu", class: "toolbarbutton-1",
      label: "Tabs", tooltiptext: "Switch temporary tabs",
    }, controls);
    const tabsPopup = element("menupopup", {}, tabButton);
    listen(tabsPopup, "popupshowing", () => fillTabs(tabsPopup));
    const keepGroup = element("hbox", { id: "little-zen-keep-group", align: "center" }, controls);
    const keepButton = element("toolbarbutton", {
      id: "little-zen-keep", class: "toolbarbutton-1",
      label: "Open in Space",
    }, keepGroup);
    element("label", {
      id: "little-zen-keep-shortcut",
      value: Services.appinfo.OS === "Darwin" ? "⌘O" : "Ctrl+O",
      "aria-hidden": "true",
    }, keepButton);
    listen(keepButton, "command", () => promote().catch(report));
    const chooseButton = element("toolbarbutton", {
      id: "little-zen-choose-space", type: "menu", class: "toolbarbutton-1",
      label: "⌄", tooltiptext: "Choose a Space", "aria-label": "Choose a Space",
    }, keepGroup);
    const spacesPopup = element("menupopup", { id: "little-zen-spaces" }, chooseButton);
    listen(spacesPopup, "popupshowing", () => {
      updateControls();
      fillSpaces(spacesPopup);
    });
    // Scope Arc's keep shortcut to temporary windows. Ordinary Zen windows
    // retain their configured Open File shortcut and menu command.
    listen(window, "keydown", event => {
      const accelerator = Services.appinfo.OS === "Darwin"
        ? event.metaKey && !event.ctrlKey : event.ctrlKey && !event.metaKey;
      if (!enabled() || !event.isTrusted || event.isComposing || !accelerator ||
          event.altKey || event.shiftKey || event.key.toLowerCase() !== "o") return;
      event.preventDefault();
      event.stopImmediatePropagation();
      if (!event.repeat) promote().catch(report);
    }, true);
    for (const event of ["TabOpen", "TabClose", "TabSelect", "TabAttrModified"]) {
      listen(gBrowser.tabContainer, event, updateControls);
    }
    listen(window, "focus", updateControls);
    updateControls();
  }

  async function setupMiniWindow() {
    const info = window._littleZenInfo;
    if (!info) return;
    root.removeAttribute("persist");
    installMiniUI();
    if (info.fresh) {
      // Zen's special empty-tab placeholder is not an ordinary navigable tab.
      const tab = gBrowser.addTab(info.url || "about:blank", {
        triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal(),
        ...info.loadOptions,
        userContextId: info.contextId,
        inBackground: false,
        skipRoute: true,
        skipAnimation: true,
      });
      gBrowser.selectedTab = tab;
      for (const other of [...gBrowser.tabs]) {
        if (other !== tab && !other.hasAttribute("zen-empty-tab") &&
            other.linkedBrowser?.currentURI.spec === "about:blank") {
          gBrowser.removeTab(other, { animate: false });
        }
      }
      info.focusAddressOnOpen = !info.url || info.url === "about:blank";
      delete info.fresh;
      delete info.loadOptions;
      delete info.url;
    }
    if (info.external && !info.externalInitialized) {
      const startupBlanks = realTabs().filter(
        tab => tab.linkedBrowser?.currentURI.spec === "about:blank"
      );
      const selectLoadedTab = () => {
        const tab = realTabs().find(
          item => item.linkedBrowser?.currentURI.spec !== "about:blank"
        );
        if (!tab) return false;
        gBrowser.selectedTab = tab;
        info.externalInitialized = true;
        for (const blank of startupBlanks) {
          if (blank !== tab && !blank.closing && blank.isConnected &&
              blank.linkedBrowser?.currentURI.spec === "about:blank") {
            gBrowser.removeTab(blank, { animate: false });
          }
        }
        return true;
      };
      if (!selectLoadedTab()) {
        const progress = {
          onLocationChange() {
            if (selectLoadedTab()) gBrowser.removeTabsProgressListener(progress);
          },
        };
        gBrowser.addTabsProgressListener(progress);
        cleanup.push(() => gBrowser.removeTabsProgressListener(progress));
      }
    }
    if (!info.initialized) {
      const size = sizeFor();
      window.resizeTo(size.width, size.height);
      const left = screen.availLeft + Math.max(0, (screen.availWidth - size.width) / 2);
      const top = screen.availTop + Math.max(0, (screen.availHeight - size.height) / 2);
      window.moveTo(Math.round(left), Math.round(top));
      window.focus();
      info.initialized = true;
    }
    // Native compact-mode observers can reposition the toolbox after startup.
    resizeTimer = window.setTimeout(() => {
      updateControls();
      if (info.focusAddressOnOpen) {
        delete info.focusAddressOnOpen;
        if (document.hasFocus() && gBrowser.selectedBrowser.currentURI.spec === "about:blank") {
          gURLBar.select();
        }
      }
    }, 100);
  }

  function installCommands() {
    const command = element("command", { id: "little-zen-new-command" },
      document.getElementById("mainCommandSet"));
    listen(command, "command", () => {
      try { open(); } catch (error) { report(error); }
    });
    const key = element("key", {
      id: "little-zen-new-key", key: "n", modifiers: "accel,alt",
      command: command.id,
    }, document.getElementById("mainKeyset"));
    const item = element("menuitem", {
      id: "little-zen-new-menu", label: "New Little Zen",
      command: command.id, key: key.id,
    });
    const newWindow = document.getElementById("menu_newNavigator");
    if (newWindow) newWindow.after(item);
    else document.getElementById("menu_FilePopup")?.prepend(item);

    const contextMenu = document.getElementById("contentAreaContextMenu");
    if (contextMenu) {
      const link = element("menuitem", {
        id: "little-zen-open-link", label: "Open Link in Little Zen", hidden: "true",
      });
      const newTabItem = document.getElementById("context-openlinkintab");
      if (newTabItem) newTabItem.after(link);
      else contextMenu.prepend(link);
      listen(contextMenu, "popupshowing", event => {
        if (event.target !== contextMenu) return;
        link.hidden = !enabled() || !window.gContextMenu?.onLink ||
          !isWebURL(window.gContextMenu.linkURL);
      });
      listen(link, "command", () => {
        const context = window.gContextMenu;
        if (!context || !isWebURL(context.linkURL)) return;
        const userContextId = isPrivate(window) ? 0 : context.contentData.userContextId;
        try {
          open({
            url: context.linkURL,
            userContextId,
            loadOptions: context._openLinkInParameters({ userContextId }),
          });
        } catch (error) { report(error); }
      });
    }
    const update = () => {
      const active = enabled();
      command.disabled = !active;
      item.hidden = !active;
      root.toggleAttribute(MARKER, active && !!window._littleZenInfo);
    };
    Services.prefs.addObserver(PREFIX + "enabled", update);
    cleanup.push(() => Services.prefs.removeObserver(PREFIX + "enabled", update));
    update();
  }

  function installExternalRouting() {
    const { BrowserDOMWindow } = ChromeUtils.importESModule(
      "resource:///modules/BrowserDOMWindow.sys.mjs"
    );
    // browserDOMWindow is an XPCOM interface with read-only methods. Patch the
    // shared JavaScript implementation once and dispatch to the owning window.
    const prototype = BrowserDOMWindow.prototype;
    const hook = "__littleZenExternalRouting";
    let state = prototype[hook];
    if (!state) {
      state = { original: prototype.openURI, windows: new Map() };
      state.wrapped = function (...args) {
        const handler = state.windows.get(this.win);
        return handler ? handler(this, ...args) : state.original.apply(this, args);
      };
      Object.defineProperty(prototype, hook, { value: state, configurable: true });
      prototype.openURI = state.wrapped;
    }
    const handle = function (receiver, uri, openWindowInfo, where, flags, ...rest) {
      if (!destroyed && enabled() &&
          Services.prefs.getBoolPref(PREFIX + "external-links", false) &&
          (flags & Ci.nsIBrowserDOMWindow.OPEN_EXTERNAL) &&
          !openWindowInfo && isWebURL(uri?.spec)) {
        // Delegate to Firefox's own external-window path with every principal,
        // policy container and flag unchanged. Decorate the resulting window.
        const nativeOpenDialog = window.openDialog;
        const decoratedOpenDialog = function (...args) {
          if (args[0] !== "chrome://browser/content/browser.xhtml") {
            return nativeOpenDialog.apply(this, args);
          }
          const size = sizeFor();
          args[2] += `,width=${size.width},height=${size.height}`;
          // browser-init consumes window.arguments[5] as the load's explicit
          // userContextId. Match the temporary window's initial container.
          args[8] = currentContext();
          const child = nativeOpenDialog.apply(this, args);
          markWindow(child, { external: true });
          return child;
        };
        window.openDialog = decoratedOpenDialog;
        try {
          return state.original.call(
            receiver, uri, openWindowInfo, Ci.nsIBrowserDOMWindow.OPEN_NEWWINDOW, flags, ...rest
          );
        } finally {
          if (window.openDialog === decoratedOpenDialog) window.openDialog = nativeOpenDialog;
        }
      }
      return state.original.call(receiver, uri, openWindowInfo, where, flags, ...rest);
    };
    state.windows.set(window, handle);
    cleanupRouting = () => {
      state.windows.delete(window);
      if (!state.windows.size && prototype.openURI === state.wrapped) {
        prototype.openURI = state.original;
        delete prototype[hook];
      }
    };
  }

  function destroy() {
    if (destroyed) return;
    destroyed = true;
    window.clearTimeout(resizeTimer);
    for (const undo of cleanup.splice(0).reverse()) {
      try { undo(); } catch (error) { report(error); }
    }
    cleanupRouting?.();
    for (const node of nodes.reverse()) node.remove();
    root.removeAttribute(MARKER);
    // Removing the mod reveals the underlying blank window; no tabs are closed.
    if (window.LittleZen === api) delete window.LittleZen;
  }

  const api = { version: "0.1.0", status: "waiting", open, promote, destroy, ready, realTabs };
  window.LittleZen = api;
  window.addUnloadListener?.(destroy);
  listen(window, "unload", destroy, { once: true });

  ready(window).then(async () => {
    if (destroyed) return;
    api.status = "commands";
    installCommands();
    api.status = "routing";
    installExternalRouting();
    api.status = "window";
    await setupMiniWindow();
    api.status = "ready";
  }).catch(error => {
    api.status = "error";
    api.error = String(error);
    report(error);
  });
})();
