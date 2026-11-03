// ==UserScript==
// @name           Alt-click Split View
// @author         Kostiantyn Kugot
// @version        1.4.5-local
// @description    Open Alt-clicked links in Zen Split View.
// @include        chrome://browser/content/browser.xhtml
// ==/UserScript==

(() => {
  const ENABLED_PREF = 'uc.alt-click-split-view.enabled';
  const TRIGGER_PREF = 'uc.alt-click-split-view.trigger';
  const HOVER_PREF = 'uc.alt-click-split-view.focus-on-hover';
  const ADAPTIVE_PREF = 'uc.alt-click-split-view.adaptive-direction';
  const MODIFIER_KEYS = Object.freeze({
    ctrl: 'ctrlKey',
    alt: 'altKey',
    shift: 'shiftKey',
    meta: 'metaKey',
  });

  function shouldSplitLinkClick(data, trigger = 'alt') {
    const modifier = MODIFIER_KEYS[trigger];
    return data?.button === 0 && Boolean(data.href) && modifier &&
      data[modifier] === true &&
      Object.values(MODIFIER_KEYS).every(key => key === modifier || !data[key]);
  }

  function installHoverFocus(win, prefs) {
    let timer = 0, pendingPane = null;
    const cancel = () => {
      if (timer) win.clearTimeout(timer);
      timer = 0;
      pendingPane = null;
    };
    const allowed = () => prefs.getBoolPref(HOVER_PREF, false) && win.document.hasFocus() &&
      win.gBrowser.tabpanels.getAttribute('zen-split-view') === 'true' &&
      !win.document.documentElement.hasAttribute('customizing') &&
      win.document.documentElement.getAttribute('inDOMFullscreen') !== 'true' &&
      !win.gURLBar.focused && !win.gURLBar.view.isOpen &&
      !win.document.querySelector('panel[panelopen="true"], menupopup[open="true"]') &&
      !win.gZenGlanceManager?.getFocusedTab?.();
    const move = event => {
      if (event.buttons || !allowed()) { cancel(); return; }
      const pane = event.target?.closest?.('.browserSidebarContainer[zen-split="true"]:not(.zen-glance-overlay)');
      const browser = pane?.querySelector(':scope > .browserContainer > .browserStack > browser');
      if (!browser || browser === win.gBrowser.selectedBrowser || pane.parentNode !== win.gBrowser.tabpanels) { cancel(); return; }
      if (pane === pendingPane) return;
      cancel();
      pendingPane = pane;
      timer = win.setTimeout(() => {
        cancel();
        if (!allowed() || !pane.isConnected || !pane.matches(':hover') || pane.getAttribute('zen-split') !== 'true') return;
        const tab = win.gBrowser.getTabForBrowser(browser);
        if (tab && !tab.closing) win.gBrowser.selectedTab = tab;
      }, 150);
    };
    const exit = event => { if (!event.relatedTarget) cancel(); };
    const events = [['mousemove', move], ['mouseout', exit], ['mousedown', cancel], ['keydown', cancel], ['dragstart', cancel], ['blur', cancel]];
    for (const [name, handler] of events) win.addEventListener(name, handler, true);
    return () => {
      cancel();
      for (const [name, handler] of events) win.removeEventListener(name, handler, true);
    };
  }

  function installAdaptiveSplits(win, prefs) {
    const splitter = win.gZenViewSplitter;
    const glance = win.gZenGlanceManager;
    const cleanup = [], glancePairs = new Set();
    let destroyed = false;
    const tallWindow = () => !destroyed &&
      prefs.getBoolPref(ENABLED_PREF, true) && prefs.getBoolPref(ADAPTIVE_PREF, true) &&
      win.outerWidth > 0 && win.outerHeight > win.outerWidth;
    const wrap = (owner, key, makeWrapper) => {
      if (typeof owner?.[key] !== 'function') return;
      const original = owner[key];
      const descriptor = Object.getOwnPropertyDescriptor(owner, key);
      const wrapped = makeWrapper(original);
      owner[key] = wrapped;
      cleanup.push(() => {
        if (owner[key] !== wrapped) return;
        if (descriptor) Object.defineProperty(owner, key, descriptor);
        else delete owner[key];
      });
    };
    wrap(splitter, 'splitTabs', original => function adaptiveSplitTabs(...args) {
      const [input, gridType] = args;
      if (tallWindow() && !this._sessionRestoring && Array.isArray(input) && input.length === 2) {
        const tabs = input.map(tab => glance?.getTabOrGlanceParent?.(tab) || tab);
        const newPair = tabs[0] !== tabs[1] && tabs.every(tab =>
          tab && !tab.hidden && !tab.splitView && !tab.hasAttribute('zen-empty-tab'));
        // Glance hard-codes vsep for its default Split button. Recognize only
        // the exact pair being promoted, without overriding explicit layouts
        // chosen elsewhere while that asynchronous promotion is in flight.
        const glanceDefault = gridType === 'vsep' &&
          [...glancePairs].some(pair => tabs.every(tab => pair.includes(tab)));
        if (newPair && (gridType == null || glanceDefault)) args[1] = 'hsep';
      }
      return original.apply(this, args);
    });
    wrap(splitter, 'createEmptySplit', original => function adaptiveEmptySplit(...args) {
      if (args[0] === undefined && tallWindow() && !this._sessionRestoring) args[0] = 'bottom';
      return original.apply(this, args);
    });
    wrap(glance, 'splitGlance', original => async function adaptiveGlanceSplit(...args) {
      const pair = [this.getFocusedTab(-1), this.getFocusedTab()];
      if (destroyed || pair.some(tab => !tab) || pair[0] === pair[1]) {
        return original.apply(this, args);
      }
      glancePairs.add(pair);
      try {
        return await original.apply(this, args);
      } finally {
        glancePairs.delete(pair);
      }
    });
    return () => {
      if (destroyed) return;
      destroyed = true;
      glancePairs.clear();
      for (const restore of cleanup.reverse()) restore();
    };
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { shouldSplitLinkClick, installHoverFocus, installAdaptiveSplits };
    return;
  }

  window.AltClickSplitView?.destroy({ reloading: true });
  const hookKey = '__altClickSplitViewHook';
  let cleanup, cleanupHover, cleanupSplits, cleanupAdaptive, cleanupStartup;
  let destroyed = false;
  const report = error => console.error('[Alt-click Split View]', error);
  const enabled = () => Services.prefs.getBoolPref(ENABLED_PREF, true);
  const trigger = () => Services.prefs.getStringPref(TRIGGER_PREF, 'alt');

  function preserveLivePages() {
    const splitter = window.gZenViewSplitter;
    const original = splitter.splitTabs;
    const marker = 'uc-split-return-state';
    let timer = 0;
    let splitting = false;
    const tabs = () => [...gZenWorkspaces.allStoredTabs];
    const savedState = tab => tab.getAttribute(marker) ||
      window.SessionStore.getCustomTabValue(tab, marker);
    const remember = tab => {
      if (savedState(tab)) return;
      const value = JSON.stringify({
        pinned: tab.pinned,
        essential: tab.hasAttribute('zen-essential'),
        next: tab.nextElementSibling?.id || null,
      });
      tab.setAttribute(marker, value);
      window.SessionStore.setCustomTabValue(tab, marker, value);
    };
    const restore = () => {
      timer = 0;
      if (splitting) return;
      for (const tab of tabs()) {
        if (tab.closing || tab.splitView ||
            tab.group?.hasAttribute('split-view-group')) continue;
        const value = savedState(tab);
        if (!value) continue;
        let state;
        try { state = JSON.parse(value); } catch { continue; }
        if (state.essential) {
          gZenPinnedTabManager.addToEssentials([tab], { replicating: true });
          const next = state.next && document.getElementById(state.next);
          if (next?.parentNode === tab.parentNode) {
            gBrowser.zenHandleTabMove(tab, () => next.before(tab));
          }
        } else if (!state.pinned && tab.pinned) {
          gBrowser.unpinTab(tab);
        } else if (state.pinned && !tab.pinned) {
          gBrowser.pinTab(tab);
        }
        tab.removeAttribute(marker);
        window.SessionStore.deleteCustomTabValue(tab, marker);
      }
    };
    const queueRestore = () => {
      if (!timer) timer = window.setTimeout(restore, 0);
    };
    const split = function (input, ...args) {
      if (!enabled() || splitting) return original.call(this, input, ...args);
      const candidates = [...new Set(input
        .filter(t => !t.hidden && !t.hasAttribute('zen-empty-tab'))
        .map(t => gZenGlanceManager.getTabOrGlanceParent(t)))];
      if (candidates.length < 2 || candidates.length > this.MAX_TABS ||
          !candidates.some(t => t.pinned)) {
        return original.call(this, input, ...args);
      }
      const existing = this._data.find(group => candidates.some(t => group.tabs.includes(t)));
      if (existing && existing.tabs.length >= this.MAX_TABS) {
        return original.call(this, input, ...args);
      }
      splitting = true;
      const duplicate = gBrowser.duplicateTab;
      const keepExisting = function (tab, ...options) {
        return candidates.includes(tab) ? tab : duplicate.call(this, tab, ...options);
      };
      try {
        const pinSplit = existing ? existing.tabs.some(t => t.pinned) : true;
        for (const tab of candidates) {
          remember(tab);
          // Zen cannot group Essentials. Borrow their existing tab for the
          // split and restore its Essential position when it leaves the split.
          if (tab.hasAttribute('zen-essential')) {
            gBrowser.unpinTab(tab);
          }
          if (pinSplit && !tab.pinned) gBrowser.pinTab(tab);
          if (!pinSplit && tab.pinned) gBrowser.unpinTab(tab);
        }
        // The native split method is synchronous. Suppress only its request
        // to duplicate the exact input tabs; all other duplicate calls retain
        // their usual behavior, and the original function is restored below.
        gBrowser.duplicateTab = keepExisting;
        return original.call(this, input, ...args);
      } finally {
        if (gBrowser.duplicateTab === keepExisting) gBrowser.duplicateTab = duplicate;
        splitting = false;
        queueRestore();
      }
    };
    splitter.splitTabs = split;
    const events = ['ZenTabRemovedFromSplit', 'TabClose', 'TabUngrouped'];
    for (const name of events) gBrowser.tabContainer.addEventListener(name, queueRestore);
    // Interrupted sessions may have saved the return marker after a split
    // was removed but before its Essential position could be restored.
    queueRestore();
    return ({ reloading = false } = {}) => {
      if (splitter.splitTabs === split) splitter.splitTabs = original;
      for (const name of events) gBrowser.tabContainer.removeEventListener(name, queueRestore);
      if (timer) window.clearTimeout(timer);
      timer = 0;
      if (!reloading) {
        for (const tab of tabs()) {
          if (savedState(tab) && tab.splitView && !tab.closing) {
            splitter.removeTabFromGroup(tab, undefined, { forUnsplit: true });
          }
        }
        restore();
      }
    };
  }

  function install() {
    let ClickHandlerParent;
    try {
      ({ ClickHandlerParent } = ChromeUtils.importESModule('resource:///actors/ClickHandlerParent.sys.mjs'));
    } catch (error) {
      report(error);
      return () => {};
    }
    const prototype = ClickHandlerParent?.prototype;
    if (!prototype || typeof prototype.contentAreaClick !== 'function') return () => {};

    let state = prototype[hookKey];
    if (!state) {
      state = { original: prototype.contentAreaClick, windows: new Map() };
      state.wrapped = function (data) {
        const browser = this.manager?.browsingContext?.top?.embedderElement;
        const win = browser?.documentGlobal;
        const handler = state.windows.get(win) ||
          [...state.windows].find(([owner]) => owner.gBrowser === win?.gBrowser)?.[1];
        if (handler?.(this, browser, data)) return;
        return state.original.call(this, data);
      };
      Object.defineProperty(prototype, hookKey, { value: state, configurable: true });
      prototype.contentAreaClick = state.wrapped;
    }
    if (!state.actorRegistered) {
      try {
        ChromeUtils.registerWindowActor('AltClickSplitView', {
          allFrames: true,
          matches: ['http://*/*', 'https://*/*'],
          safeForUntrustedWebProcess: true,
          child: {
            esModuleURI: 'chrome://sine/content/alt-click-split-view/AltClickSplitViewChild.sys.mjs',
            events: { click: { capture: true, mozSystemGroup: false } },
          },
        });
        state.actorRegistered = true;
      } catch (error) {
        report(error);
        api.error = String(error);
      }
    }

    const handle = (_actor, browser, data) => {
      if (!enabled() || !shouldSplitLinkClick(data, trigger())) return false;
      // Glance owns the gesture in the content process; never race its action.
      if (Services.prefs.getBoolPref('zen.glance.enabled', true) &&
          Services.prefs.getStringPref('zen.glance.activation-method', 'ctrl') === trigger()) return false;
      const win = browser?.documentGlobal;
      const sourceTab = win?.gBrowser.getTabForBrowser(browser);
      if (!win || !sourceTab || typeof win.openLinkIn !== 'function' ||
          typeof win.gZenViewSplitter?.splitTabs !== 'function') return false;

      const open = () => {
        if (!sourceTab.isConnected || sourceTab.closing) return;
        if (!win.gZenViewSplitter.canOpenLinkInSplitView()) {
          win.gZenUIManager.showToast('zen-split-view-limit-toast');
          return;
        }
        const nativeOpenLinkIn = win.openLinkIn;
        const hookedOpenLinkIn = function (url, where, params) {
          if (url !== data.href || where !== 'tab') {
            return nativeOpenLinkIn.call(this, url, where, params);
          }
          // Match Zen's own splitLinkInNewTab, retaining native click security metadata.
          const linkTab = win.gZenViewSplitter.openAndSwitchToTab(url, {
            ...params,
            skipRoute: true,
            inBackground: false,
          });
          if (linkTab) win.gZenViewSplitter.splitTabs([sourceTab, linkTab], undefined, 1);
          return linkTab;
        };
        win.openLinkIn = hookedOpenLinkIn;
        try {
          // Ask the native click handler for a tab using this platform's
          // accelerator, without also synthesizing an unrelated modifier.
          const isMac = Services.appinfo.OS === 'Darwin';
          state.original.call(_actor, {
            ...data,
            altKey: false,
            ctrlKey: !isMac,
            metaKey: isMac,
            shiftKey: false,
          });
        } finally {
          if (win.openLinkIn === hookedOpenLinkIn) win.openLinkIn = nativeOpenLinkIn;
        }
      };
      if (win.gZenGlanceManager.getFocusedTab()) {
        // Keep the clicked preview itself, then split beside that live page.
        // Native splitTabs otherwise substitutes the page behind the preview.
        Promise.resolve(win.gZenGlanceManager.fullyOpenGlance({ forSplit: true }))
          .then(open).catch(report);
      } else {
        open();
      }
      return true;
    };

    state.windows.set(window, handle);
    return () => {
      state.windows.delete(window);
      if (!state.windows.size && prototype.contentAreaClick === state.wrapped) {
        prototype.contentAreaClick = state.original;
        delete prototype[hookKey];
        if (state.actorRegistered) ChromeUtils.unregisterWindowActor('AltClickSplitView');
      }
    };
  }

  function destroy(options = {}) {
    if (destroyed) return;
    destroyed = true;
    cleanupStartup?.();
    cleanupStartup = null;
    cleanupAdaptive?.();
    cleanupAdaptive = null;
    cleanupSplits?.(options);
    cleanupSplits = null;
    cleanupHover?.();
    cleanupHover = null;
    cleanup?.();
    cleanup = null;
    window.removeEventListener('unload', unload);
    delete window.AltClickSplitView;
  }

  const unload = () => destroy({ reloading: true });
  const api = { version: '1.4.5-local', status: 'starting', destroy };
  window.AltClickSplitView = api;
  for (const pref of [ENABLED_PREF, TRIGGER_PREF, HOVER_PREF, ADAPTIVE_PREF]) {
    Services.prefs.setBoolPref(`services.sync.prefs.sync.${pref}`, false);
    Services.prefs.setBoolPref(`services.sync.prefs.sync-seen.${pref}`, false);
  }
  window.addUnloadListener?.(destroy);
  window.addEventListener('unload', unload, { once: true });
  cleanup = install();
  cleanupHover = installHoverFocus(window, Services.prefs);
  api.ready = (async () => {
    if (!window.gBrowserInit?.delayedStartupFinished) {
      await new Promise(resolve => {
        let observing = true;
        cleanupStartup = () => {
          if (!observing) return;
          observing = false;
          Services.obs.removeObserver(started, 'browser-delayed-startup-finished');
          resolve();
        };
        const started = subject => {
          if (subject === window) cleanupStartup();
        };
        Services.obs.addObserver(started, 'browser-delayed-startup-finished');
      });
    }
    await gZenStartup.promiseInitialized;
    if (destroyed) return;
    cleanupSplits = preserveLivePages();
    cleanupAdaptive = installAdaptiveSplits(window, Services.prefs);
    api.status = 'ready';
  })().catch(error => {
    api.status = 'error';
    api.error = String(error);
    report(error);
  });
})();
