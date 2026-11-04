// ==UserScript==
// @name Sine Sync
// @version 0.1.0
// @include chrome://browser/content/browser.xhtml
// ==/UserScript==
(() => {
  // One controller per profile process, not one per window.
  const { controller } = ChromeUtils.importESModule("chrome://sine/content/sine-sync/SineSync.sys.mjs");
  controller.start().catch(error => console.error("[Sine Sync]", error));
})();
