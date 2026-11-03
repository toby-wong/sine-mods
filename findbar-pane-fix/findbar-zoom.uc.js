// ==UserScript==
// @name           Find Bar Page Zoom
// @version        0.1.4
// @description    Optionally match each find bar to its own page's zoom.
// @include        chrome://browser/content/browser.xhtml
// ==/UserScript==

(() => {
  "use strict";
  const PREF = "uc.findbar.scale-with-page-zoom";
  const PROPERTY = "--uc-findbar-page-zoom";
  const TOPIC = "browser-fullZoom:location-change";
  const SELECTOR = ".browserContainer > findbar";
  window.FindbarPageZoom?.destroy();

  const previous = new WeakMap();
  let destroyed = false;
  let queued = false;

  function restore(bar) {
    const saved = previous.get(bar);
    if (!saved) return;
    if (saved.value) bar.style.setProperty(PROPERTY, saved.value, saved.priority);
    else bar.style.removeProperty(PROPERTY);
    previous.delete(bar);
  }

  function refresh() {
    if (destroyed) return;
    const enabled = Services.prefs.getBoolPref(PREF, false);
    for (const bar of document.querySelectorAll(SELECTOR)) {
      if (!enabled) {
        restore(bar);
        continue;
      }
      const browser = bar.browser;
      if (!browser) continue;
      const zoom = ZoomManager.getZoomForBrowser(browser);
      if (!Number.isFinite(zoom) || zoom <= 0) continue;
      if (!previous.has(bar)) {
        previous.set(bar, {
          value: bar.style.getPropertyValue(PROPERTY),
          priority: bar.style.getPropertyPriority(PROPERTY),
        });
      }
      bar.style.setProperty(PROPERTY, String(zoom));
    }
  }

  function schedule() {
    if (destroyed || queued) return;
    queued = true;
    queueMicrotask(() => {
      queued = false;
      refresh();
    });
  }

  const observer = { observe: schedule };
  const events = ["FullZoomChange", "TextZoomChange", "FullZoomReset",
    "TabFindInitialized", "TabSelect"];
  function destroy() {
    if (destroyed) return;
    destroyed = true;
    for (const type of events) window.removeEventListener(type, schedule, true);
    window.removeEventListener("unload", destroy);
    Services.prefs.removeObserver(PREF, observer);
    Services.obs.removeObserver(observer, TOPIC);
    for (const bar of document.querySelectorAll(SELECTOR)) restore(bar);
    if (window.FindbarPageZoom === api) delete window.FindbarPageZoom;
  }

  const api = { version: "0.1.4", refresh, destroy };
  for (const type of events) window.addEventListener(type, schedule, true);
  window.addEventListener("unload", destroy);
  Services.prefs.addObserver(PREF, observer);
  Services.obs.addObserver(observer, TOPIC);
  window.FindbarPageZoom = api;
  window.addUnloadListener?.(destroy);
  refresh();
})();
