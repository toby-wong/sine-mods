// ==UserScript==
// @name           Auto Glance
// @version        0.2.3
// @description    Open link-created tabs as native Zen Glance previews.
// @include        chrome://browser/content/browser.xhtml
// ==/UserScript==

(() => {
  "use strict";

  window.AutoGlance?.destroy();
  const VERSION = "0.2.3";
  const PREFIX = "uc.auto-glance.";
  const cleanups = [];
  let destroyed = false;
  let commandClickDepth = 0;
  const backgroundTabs = new WeakSet();
  const webURL = url => /^https?:\/\//i.test(url || "");
  const enabled = () => !destroyed &&
    Services.prefs.getBoolPref(PREFIX + "enabled", true) &&
    Services.prefs.getBoolPref("zen.glance.enabled", true);
  const report = error => console.error("[Auto Glance]", error);

  function installCommandClickHook() {
    const { ClickHandlerParent } = ChromeUtils.importESModule(
      "resource:///actors/ClickHandlerParent.sys.mjs"
    );
    const prototype = ClickHandlerParent.prototype;
    const key = "__autoGlanceClickHook";
    let state = prototype[key];
    if (!state) {
      state = { original: prototype.contentAreaClick, windows: new Map() };
      state.wrapped = function (data) {
        const browser = this.manager?.browsingContext?.top?.embedderElement;
        const win = browser?.documentGlobal;
        const handler = state.windows.get(win) ||
          [...state.windows].find(([owner]) => owner.gBrowser === win?.gBrowser)?.[1];
        const run = () => state.original.call(this, data);
        return handler ? handler(data, run) : run();
      };
      Object.defineProperty(prototype, key, { value: state, configurable: true });
      prototype.contentAreaClick = state.wrapped;
    }
    state.windows.set(window, (data, run) => {
      if (destroyed || !Services.prefs.getBoolPref(PREFIX + "cmd-click-background", true) ||
          data.button !== 0 || !data.metaKey || data.altKey || data.ctrlKey || data.shiftKey) {
        return run();
      }
      commandClickDepth++;
      try { return run(); } finally { commandClickDepth--; }
    });
    cleanups.push(() => {
      state.windows.delete(window);
      if (state.windows.size) return;
      if (state.actorRegistered) {
        ChromeUtils.unregisterWindowActor("AutoGlanceClick");
        state.actorRegistered = false;
      }
      if (prototype.contentAreaClick === state.wrapped) {
        prototype.contentAreaClick = state.original;
        delete prototype[key];
      }
    });
    if (state.actorRegistered && state.actorVersion !== VERSION) {
      ChromeUtils.unregisterWindowActor("AutoGlanceClick");
      state.actorRegistered = false;
    }
    if (!state.actorRegistered) {
      ChromeUtils.registerWindowActor("AutoGlanceClick", {
        allFrames: true,
        matches: ["http://*/*", "https://*/*"],
        safeForUntrustedWebProcess: true,
        child: {
          esModuleURI: `chrome://sine/content/auto-glance/AutoGlanceClickChild.sys.mjs?v=${VERSION}`,
          events: { click: { capture: true, mozSystemGroup: false } },
        },
      });
      state.actorRegistered = true;
      state.actorVersion = VERSION;
    }
  }

  function eligible(tab, owner, url) {
    return enabled() && webURL(url) &&
      tab && owner && tab !== owner && !tab.closing && !owner.closing &&
      tab.isConnected && owner.isConnected &&
      tab.ownerDocument === document && owner.ownerDocument === document &&
      tab.userContextId === owner.userContextId &&
      !owner.hasAttribute("zen-empty-tab") &&
      !owner.hasAttribute("glance-id") &&
      !tab.hasAttribute("glance-id") &&
      !tab.hasAttribute("split-view");
  }

  function installVisuals(manager) {
    const backgrounds = new Set();
    let pending = false;
    const clear = () => {
      for (const element of backgrounds) element.removeAttribute("uc-auto-glance-background");
      backgrounds.clear();
    };
    const refresh = () => {
      pending = false;
      clear();
      const tab = gBrowser.selectedTab;
      if (destroyed || !tab?.hasAttribute("zen-glance-tab")) return;
      const parent = manager.getTabOrGlanceParent(tab);
      if (!parent || parent === tab) return;
      const tabs = parent.group?.hasAttribute("split-view-group") ? parent.group.tabs : [parent];
      for (const source of tabs) {
        const element = source.linkedBrowser?.closest(".browserSidebarContainer");
        if (!element) continue;
        element.setAttribute("uc-auto-glance-background", "true");
        backgrounds.add(element);
      }
    };
    const schedule = () => {
      if (pending || destroyed) return;
      pending = true;
      // Native Glance sets its tab flags during the same event turn.
      queueMicrotask(refresh);
    };
    for (const type of ["TabSelect", "GlanceOpen", "GlanceClose", "ZenSplitViewTabsSplit"]) {
      window.addEventListener(type, schedule);
      cleanups.push(() => window.removeEventListener(type, schedule));
    }
    cleanups.push(clear);
    refresh();
  }

  function installSplitRecovery(manager) {
    const splitter = window.gZenViewSplitter;
    if (!Array.isArray(splitter?._data) || typeof splitter.updateSplitView !== "function") return;
    let repairing = false;
    const repair = () => {
      if (repairing) return 0;
      repairing = true;
      let count = 0;
      try {
        for (let index = splitter._data.length - 1; index >= 0; index--) {
          const group = splitter._data[index];
          // An unfinished "new split" has no groupId. A closed placeholder can
          // leave this record active, making native Glance throw before its
          // animation starts. Connected, unloaded tabs are not closed tabs.
          if (group.groupId || !group.tabs.some(tab => !tab.isConnected || tab.closing)) continue;
          const remaining = group.tabs.filter(tab => tab.isConnected && !tab.closing);
          if (remaining.length > 1) continue;
          if (splitter.currentView === index) {
            const originalTabs = group.tabs;
            group.tabs = remaining.filter(tab => tab.linkedBrowser);
            try { splitter.deactivateCurrentSplitView(); }
            finally { group.tabs = originalTabs; }
          }
          splitter._data.splice(index, 1);
          if (splitter.currentView > index) splitter.currentView--;
          for (const tab of remaining) {
            // The survivor may already be part of a different, working split.
            if (splitter._data.some(other => other.tabs.includes(tab))) continue;
            if (tab.linkedBrowser) splitter.resetTabState(tab, true);
            else {
              tab.splitView = false;
              tab.removeAttribute("split-view");
            }
          }
          count++;
        }
        api.repairedTransientSplits += count;
        return count;
      } finally { repairing = false; }
    };
    const original = splitter.updateSplitView;
    const update = function (...args) {
      repair();
      return original.apply(this, args);
    };
    splitter.updateSplitView = update;
    cleanups.push(() => {
      if (splitter.updateSplitView === update) splitter.updateSplitView = original;
    });

    if (repair()) recoverInterruptedGlance(manager);
  }

  function recoverInterruptedGlance(manager) {
    const tab = gBrowser.selectedTab;
    const wrapper = manager.browserWrapper;
    const content = manager.contentWrapper;
    // Only finish the precise pre-animation failure recovered above. Never
    // interrupt a running animation or a pending element snapshot.
    if (!tab?.hasAttribute("zen-glance-tab") || !manager.animatingOpen ||
        !manager._animating || manager.animatingFullOpen || manager.closingGlance ||
        !wrapper?.isConnected || !content || !manager.overlay?.isConnected ||
        wrapper.getAttribute("animate") !== "true" ||
        wrapper.hasAttribute("has-finished-animation") ||
        wrapper.getAnimations().length || content.style.opacity === "0" ||
        wrapper.querySelector(".zen-glance-element-preview")) return;

    const parent = manager.getTabOrGlanceParent(tab);
    const background = parent?.linkedBrowser?.closest(".browserSidebarContainer");
    if (!background || parent === tab) return;
    gZenViewSplitter.onLocationChange(tab.linkedBrowser);
    manager.quickOpenGlance();
    background.style.opacity = "0.3";
    background.style.transform = "scale(0.97)";
    wrapper.style.height = "100%";
    wrapper.style.width = "80%";
    wrapper.removeAttribute("animate");
    wrapper.setAttribute("has-finished-animation", "true");
    manager.overlay.style.removeProperty("overflow");
    manager._animating = false;
    manager.animatingOpen = false;
    gBrowser.tabContainer._invalidateCachedTabs();
    tab.dispatchEvent(new Event("GlanceOpen", { bubbles: true }));
    api.recoveredPreview = true;
  }

  function destroy() {
    if (destroyed) return;
    destroyed = true;
    for (const undo of cleanups.splice(0).reverse()) {
      try { undo(); } catch (error) { report(error); }
    }
    if (window.AutoGlance === api) delete window.AutoGlance;
  }

  async function install() {
    if (!window.gBrowserInit?.delayedStartupFinished) {
      await new Promise(resolve => {
        let observing = true;
        const stop = () => {
          if (!observing) return;
          observing = false;
          Services.obs.removeObserver(started, "browser-delayed-startup-finished");
          resolve();
        };
        const started = subject => {
          if (subject !== window) return;
          stop();
        };
        Services.obs.addObserver(started, "browser-delayed-startup-finished");
        cleanups.push(stop);
      });
    }
    await gZenStartup.promiseInitialized;
    if (destroyed) return;
    const manager = window.gZenGlanceManager;
    if (typeof manager?.shouldOpenTabInGlance !== "function" ||
        typeof manager.openGlance !== "function" || typeof window.openLinkIn !== "function") {
      throw new Error("This Zen version does not expose the expected Glance APIs.");
    }
    const style = document.createElementNS("http://www.w3.org/1999/xhtml", "link");
    style.rel = "stylesheet";
    style.href = `chrome://sine/content/auto-glance/auto-glance.css?v=${VERSION}`;
    document.documentElement.append(style);
    cleanups.push(() => style.remove());
    installVisuals(manager);
    installSplitRecovery(manager);

    // This is Zen's own path for target=_blank and window.open links. Reuse
    // the browser-created tab, retaining opener, principals and load options.
    const originalDecision = manager.shouldOpenTabInGlance;
    const decide = function (tab, uri) {
      if (commandClickDepth || backgroundTabs.has(tab)) return false;
      return eligible(tab, tab?.owner, uri?.spec) ||
        originalDecision.call(this, tab, uri);
    };
    manager.shouldOpenTabInGlance = decide;
    cleanups.push(() => {
      if (manager.shouldOpenTabInGlance === decide) {
        manager.shouldOpenTabInGlance = originalDecision;
      }
    });

    installCommandClickHook();

    // Modified clicks and "Open Link in New Tab" use the normal link loader.
    // Capture its resulting browser; do not replace its navigation or security
    // parameters with a fresh Glance load.
    const originalOpen = window.openLinkIn;
    const open = function (url, where, params, ...rest) {
      if (commandClickDepth && ["tab", "tabshifted"].includes(where) && webURL(url)) {
        return originalOpen.call(this, url, where, {
          ...params,
          inBackground: true,
          resolveOnNewTabCreated: browser => {
            const tab = gBrowser.getTabForBrowser(browser);
            if (tab) backgroundTabs.add(tab);
            params?.resolveOnNewTabCreated?.(browser);
          },
        }, ...rest);
      }
      if (!enabled() || !Services.prefs.getBoolPref(PREFIX + "modified-clicks", true) ||
          !["tab", "tabshifted"].includes(where) || !webURL(url) ||
          !params?.triggeringPrincipal?.isContentPrincipal ||
          params.fromExternal || params.initiatedByURLBar ||
          // Native split view supplies its own creation callback.
          params.resolveOnNewTabCreated || params.resolveOnContentBrowserCreated) {
        return originalOpen.call(this, url, where, params, ...rest);
      }
      const context = window.gContextMenu;
      const sourceBrowser = params.openerBrowser ||
        (context?.onLink && context.linkURL === url ? context.browser : null);
      const owner = sourceBrowser && gBrowser.getTabForBrowser(sourceBrowser);
      if (!owner || owner.hasAttribute("glance-id")) {
        return originalOpen.call(this, url, where, params, ...rest);
      }
      let browser;
      const result = originalOpen.call(this, url, where, {
        ...params,
        resolveOnNewTabCreated: created => { browser = created; },
      }, ...rest);
      const tab = browser && gBrowser.getTabForBrowser(browser);
      if (eligible(tab, owner, url)) {
        try {
          Promise.resolve(manager.openGlance({}, tab, owner)).catch(report);
        } catch (error) {
          // The native tab remains available if Glance cannot open.
          report(error);
        }
      }
      return result;
    };
    window.openLinkIn = open;
    cleanups.push(() => {
      if (window.openLinkIn === open) window.openLinkIn = originalOpen;
    });
    api.status = "ready";
  }

  const api = {
    version: VERSION, status: "starting",
    repairedTransientSplits: 0, recoveredPreview: false, destroy,
  };
  window.AutoGlance = api;
  window.addUnloadListener?.(destroy);
  window.addEventListener("unload", destroy, { once: true });
  cleanups.push(() => window.removeEventListener("unload", destroy));
  install().catch(error => {
    api.status = "error";
    api.error = String(error);
    report(error);
  });
})();
