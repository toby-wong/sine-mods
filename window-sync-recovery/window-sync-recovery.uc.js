// ==UserScript==
// @name           Window Sync Recovery
// @version        0.1.0
// @description    Remove stale window-sync snapshots after the live page has returned.
// @include        chrome://browser/content/browser.xhtml
// ==/UserScript==

(() => {
  "use strict";

  const VERSION = "0.1.0";
  const IMAGE = ".zen-pseudo-browser-image";
  const HIDDEN = "zen-pseudo-hidden";
  const SETTLE_MS = 300;
  window.WindowSyncRecovery?.destroy();

  let destroyed = false;
  let timer = null;
  let observer = null;
  let initialized = false;
  const stats = { repairedTabs: 0, removedSnapshots: 0 };

  function onlyBrowserWindow() {
    const windows = [...Services.wm.getEnumerator("navigator:browser")]
      .filter(win => !win.closed);
    // Count opening/closing, private and unsynced windows too. A false
    // negative is safer than touching a snapshot during a docshell transfer.
    return windows.length === 1 && windows[0] === window;
  }

  function snapshot(browser) {
    if (!browser?.isConnected) return null;
    const tab = gBrowser.getTabForBrowser(browser);
    if (!tab?.isConnected || tab.closing || tab._zenContentsVisible !== true ||
        tab.hasAttribute("pending") || tab.hasAttribute("busy")) return null;
    const global = browser.browsingContext?.currentWindowGlobal;
    const documentURI = global?.documentURI?.spec;
    // A blank/unloaded stand-in is not proof that the live page came back.
    if (!documentURI || /^about:blank(?:[?#]|$)/.test(documentURI)) return null;
    const images = [...(browser.parentElement?.querySelectorAll(IMAGE) || [])];
    if (!browser.hasAttribute(HIDDEN) && !images.length) return null;
    return {
      browser, tab, tabId: tab.id, global,
      context: browser.browsingContext, uri: browser.currentURI.spec,
      documentURI, images,
    };
  }

  function candidates() {
    const browsers = new Set(document.querySelectorAll(`browser[${HIDDEN}]`));
    for (const image of document.querySelectorAll(IMAGE)) {
      const browser = image.parentElement?.querySelector(":scope > browser");
      if (browser) browsers.add(browser);
    }
    return [...browsers].map(snapshot).filter(Boolean);
  }

  function samePage(before, after) {
    return after && before.tab === after.tab && before.tabId === after.tabId &&
      before.global === after.global && before.context === after.context &&
      before.uri === after.uri && before.documentURI === after.documentURI;
  }

  function verify(pages) {
    timer = null;
    if (destroyed || !onlyBrowserWindow()) return;
    for (const before of pages) {
      const after = snapshot(before.browser);
      if (!samePage(before, after)) continue;
      // Match native cleanup without changing ownership, navigation, grouping
      // or the docshell. Revoke the native blob URL before removing its image.
      after.browser.removeAttribute(HIDDEN);
      for (const image of after.images) {
        if (image.src?.startsWith("blob:")) URL.revokeObjectURL(image.src);
        image.remove();
      }
      stats.repairedTabs++;
      stats.removedSnapshots += after.images.length;
    }
  }

  function check() {
    timer = null;
    if (destroyed || !onlyBrowserWindow()) return;
    const pages = candidates();
    if (pages.length) timer = setTimeout(() => verify(pages), SETTLE_MS);
  }

  function schedule() {
    if (destroyed || !initialized) return;
    if (timer !== null) clearTimeout(timer);
    timer = setTimeout(check, SETTLE_MS);
  }

  function onFocus(event) {
    if (event.target === window || event.target === document) schedule();
  }

  const windowsObserver = { observe: schedule };

  function destroy() {
    if (destroyed) return;
    destroyed = true;
    if (timer !== null) clearTimeout(timer);
    timer = null;
    observer?.disconnect();
    if (initialized) {
      gBrowser.tabContainer.removeEventListener("TabSelect", schedule);
      window.removeEventListener("activate", schedule);
      window.removeEventListener("focus", onFocus, true);
      Services.obs.removeObserver(windowsObserver, "domwindowclosed");
      Services.obs.removeObserver(windowsObserver, "domwindowopened");
    }
    window.removeEventListener("unload", destroy);
    if (window.WindowSyncRecovery === api) delete window.WindowSyncRecovery;
  }

  const api = {
    version: VERSION, refresh: schedule, destroy,
    get stats() { return { ...stats }; },
  };
  window.WindowSyncRecovery = api;
  window.addEventListener("unload", destroy, { once: true });
  window.addUnloadListener?.(destroy);

  async function init() {
    await gZenStartup.promiseInitialized;
    if (destroyed) return;
    initialized = true;
    gBrowser.tabContainer.addEventListener("TabSelect", schedule);
    window.addEventListener("activate", schedule);
    window.addEventListener("focus", onFocus, true);
    Services.obs.addObserver(windowsObserver, "domwindowclosed");
    Services.obs.addObserver(windowsObserver, "domwindowopened");
    observer = new MutationObserver(records => {
      if (records.some(record => record.type === "attributes" ||
          [...record.addedNodes].some(node => node.nodeType === 1 && node.matches(IMAGE)))) {
        schedule();
      }
    });
    observer.observe(gBrowser.tabpanels, {
      subtree: true, childList: true, attributes: true, attributeFilter: [HIDDEN],
    });
    schedule();
  }

  init().catch(error => {
    console.error("[Window Sync Recovery]", error);
    destroy();
  });
})();
