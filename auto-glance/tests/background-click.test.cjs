const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");

// Run both real click layers against Firefox's platform-specific tab-loader
// contract. These checks do not simulate physical Windows desktop input.
async function fixture(os, order = ["auto"]) {
  const prefs = new Map([["zen.glance.activation-method", "shift"]]);
  const loads = [], splits = [], messages = [], registrations = new Map();
  const nativeGlances = [];
  class ZenGlanceChild {
    on_click(event) {
      const trigger = prefs.get("zen.glance.activation-method") || "ctrl";
      if (!event.defaultPrevented && event[trigger + "Key"]) nativeGlances.push(event.href);
    }
  }
  const nativeGlanceClick = ZenGlanceChild.prototype.on_click;
  const document = {
    createElementNS: () => ({ remove() {} }),
    documentElement: { append() {} },
  };
  const source = {
    ownerDocument: document, userContextId: 7, isConnected: true,
    hasAttribute: () => false,
  };
  const tabs = new Map();
  const win = {
    document, gBrowserInit: { delayedStartupFinished: true },
    addEventListener() {}, removeEventListener() {},
    gBrowser: { selectedTab: source, getTabForBrowser: browser => tabs.get(browser) },
    gZenViewSplitter: {
      _data: [], updateSplitView() {},
      canOpenLinkInSplitView: () => true,
      openAndSwitchToTab(url, params) {
        // Native splits call addTab directly, without the link loader's
        // automatic Glance decision.
        const tab = nativeOpen(url, "tab", params, false);
        return tab;
      },
      splitTabs: pair => splits.push(pair),
    },
    gZenGlanceManager: {
      getFocusedTab: () => null,
      shouldOpenTabInGlance: () => false,
      openGlance(_params, tab) {
        tab.glance = true;
        win.gBrowser.selectedTab = tab;
      },
    },
  };
  source.linkedBrowser = { documentGlobal: win };
  tabs.set(source.linkedBrowser, source);
  function nativeOpen(url, where, params, checkGlance = true) {
    const tab = {
      ...source, owner: source, linkedBrowser: {}, glance: false,
      hasAttribute: () => false,
    };
    tabs.set(tab.linkedBrowser, tab);
    loads.push({ url, where, params, tab });
    params.resolveOnNewTabCreated?.(tab.linkedBrowser);
    if (!params.inBackground) win.gBrowser.selectedTab = tab;
    if (checkGlance && win.gZenGlanceManager.shouldOpenTabInGlance(tab, { spec: url })) {
      win.gZenGlanceManager.openGlance({}, tab);
    }
    return tab;
  }
  win.openLinkIn = nativeOpen;
  class ClickHandlerParent {
    constructor() {
      this.manager = { browsingContext: { top: { embedderElement: source.linkedBrowser } } };
    }
    contentAreaClick(data) {
      const accel = os === "Darwin" ? data.metaKey : data.ctrlKey;
      const where = accel || data.button === 1 ? "tab" : data.shiftKey ? "window" : "current";
      if (where === "current") return;
      return win.openLinkIn(data.href, where, {
        triggeringPrincipal: data.triggeringPrincipal,
        originPrincipal: data.triggeringPrincipal,
        referrerInfo: data.referrerInfo,
        policyContainer: data.policyContainer,
        userContextId: source.userContextId,
        openerBrowser: source.linkedBrowser,
      });
    }
  }
  const nativeClick = ClickHandlerParent.prototype.contentAreaClick;
  const parent = new ClickHandlerParent();
  const sandbox = vm.createContext({
    window: win, document, gBrowser: win.gBrowser,
    gZenStartup: { promiseInitialized: Promise.resolve() },
    console, queueMicrotask,
    Services: {
      appinfo: { OS: os },
      prefs: {
        getBoolPref: (key, fallback) => prefs.has(key) ? prefs.get(key) : fallback,
        getStringPref: (key, fallback) => prefs.has(key) ? prefs.get(key) : fallback,
        setBoolPref: (key, value) => prefs.set(key, value),
      },
      obs: { addObserver() {}, removeObserver() {} },
      scriptSecurityManager: {
        checkLoadURIStrWithPrincipal(principal) {
          if (principal.blocked) throw Error("Blocked navigation");
        },
      },
    },
    ChromeUtils: {
      importESModule: () => ({ ClickHandlerParent }),
      registerWindowActor: (name, options) => registrations.set(name, options),
      unregisterWindowActor: name => registrations.delete(name),
      getClassName: target => target.className || "HTMLAnchorElement",
    },
    BrowserUtils: {
      hrefAndLinkNodeForClickEvent: event => [event.href, event.node, event.principal],
    },
    E10SUtils: {
      serializePolicyContainer: value => value,
      serializeReferrerInfo: value => value,
    },
    Cc: {
      "@mozilla.org/referrer-info;1": {
        createInstance: () => ({ initWithElement(node) { this.node = node; } }),
      },
    },
    Ci: { nsIReferrerInfo: {} },
    JSWindowActorChild: class {},
    ZenGlanceChild,
  });
  const autoSource = fs.readFileSync(path.join(__dirname, "../auto-glance.uc.js"), "utf8");
  async function loadAuto() {
    vm.runInContext(autoSource, sandbox);
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(win.AutoGlance.status, "ready", win.AutoGlance.error);
  }
  for (const mod of order) {
    if (mod === "auto") await loadAuto();
    else {
      // Only install the real Alt-click parent hook, leaving unrelated sidebar
      // and split-layout startup waiting for a browser window.
      win.gBrowserInit.delayedStartupFinished = false;
      vm.runInContext(fs.readFileSync(path.join(
        __dirname, "../../alt-click-split-view/alt-click-split-view.uc.js",
      ), "utf8"), sandbox);
      win.gBrowserInit.delayedStartupFinished = true;
    }
  }
  const actorSource = fs.readFileSync(path.join(__dirname, "../AutoGlanceClickChild.sys.mjs"), "utf8")
    .replace(/^import .+;\n/gm, "").replace("export class ", "class ");
  vm.runInContext(actorSource + "\nglobalThis.Actor = AutoGlanceClickChild;", sandbox);
  const actor = new sandbox.Actor();
  actor.manager = {
    innerWindowId: 1,
    getActor: name => {
      assert.equal(name, "ClickHandler");
      return {
        sendAsyncMessage(name, data) {
          messages.push({ name, data });
          // The real parent fills these fields from the trusted frame actor.
          parent.contentAreaClick({ ...data, triggeringPrincipal: actor.principal });
        },
      };
    },
  };
  actor.actorCreated();
  const contentActors = [actor];
  const nativeActor = new ZenGlanceChild();
  nativeActor.manager = actor.manager;
  function event(overrides = {}) {
    const policyContainer = { sandboxFlags: 3 };
    const node = { hasAttribute: () => false, getAttribute: () => "A link" };
    return {
      type: "click", button: 0, isTrusted: true, altKey: false, shiftKey: false,
      ctrlKey: os !== "Darwin", metaKey: os === "Darwin",
      composedTarget: { ownerDocument: { policyContainer } },
      node, href: "https://example.test/target", principal: { isContentPrincipal: true },
      preventMultipleActions() { this.multipleActionsPrevented = true; },
      preventDefault() { this.defaultPrevented = true; },
      stopImmediatePropagation() { this.stopped = true; },
      ...overrides,
    };
  }
  return {
    win, source, prefs, loads, splits, messages, registrations, event, loadAuto, nativeGlances,
    capture(event) {
      actor.principal = event.principal;
      // Native actors are registered earlier. Their click listener can run
      // first even when the mod's listener also uses capture.
      nativeActor.on_click(event);
      actor.handleEvent(event);
    },
    contentActor(id) {
      const child = new sandbox.Actor();
      child.manager = { ...actor.manager, innerWindowId: id };
      child.actorCreated();
      contentActors.push(child);
      const native = new ZenGlanceChild();
      native.manager = child.manager;
      return { destroy: () => child.didDestroy(), nativeClick: event => native.on_click(event) };
    },
    click: data => parent.contentAreaClick({ ...data, triggeringPrincipal: data.principal }),
    destroy() {
      for (const child of contentActors) child.didDestroy();
      assert.equal(ZenGlanceChild.prototype.on_click, nativeGlanceClick);
      for (const mod of [...order].reverse()) {
        if (mod === "auto") win.AutoGlance?.destroy();
        else win.AltClickSplitView?.destroy({ reloading: true });
      }
      assert.equal(ClickHandlerParent.prototype.contentAreaClick, nativeClick);
      assert.equal(win.openLinkIn, nativeOpen);
      assert.equal(registrations.size, 0);
    },
  };
}

for (const os of ["WINNT", "Darwin", "Linux"]) {
  test(`${os}: the tab accelerator opens one ordinary background tab through both layers`, async t => {
    const f = await fixture(os);
    t.after(f.destroy);
    const event = f.event();
    f.capture(event);
    assert.equal(f.messages.length, 1);
    assert.equal(f.messages[0].name, "Content:Click");
    assert.ok(event.defaultPrevented && event.stopped && event.multipleActionsPrevented);
    assert.equal(f.loads.length, 1);
    const load = f.loads[0];
    assert.equal(load.url, event.href);
    assert.equal(load.params.inBackground, true);
    assert.equal(f.win.gBrowser.selectedTab, f.source);
    assert.equal(load.tab.glance, false);
    assert.equal(load.params.triggeringPrincipal, event.principal);
    assert.equal(load.params.referrerInfo.node, event.node);
    assert.equal(load.params.policyContainer, event.composedTarget.ownerDocument.policyContainer);
    assert.equal(load.params.openerBrowser, f.source.linkedBrowser);
    assert.equal(load.params.userContextId, 7);
    assert.equal(f.win.gZenGlanceManager.shouldOpenTabInGlance(load.tab, { spec: event.href }), false,
      "the override must survive asynchronous Glance decisions after the click");
    // It is the override that keeps focus, not the normal new-tab preference.
    f.click(f.event({ button: 1, ctrlKey: false, metaKey: false }));
    assert.equal(f.loads.at(-1).tab.glance, true, "middle-click keeps its configured Glance behavior");
  });

  test(`${os}: capture preserves other gestures, downloads, inputs, and security checks`, async t => {
    const f = await fixture(os);
    t.after(f.destroy);
    for (const override of [
      { ctrlKey: false, metaKey: false },
      { ctrlKey: os === "Darwin", metaKey: os !== "Darwin" },
      { ctrlKey: true, metaKey: true },
      { altKey: true }, { shiftKey: true }, { button: 1 }, { button: 2 },
      { isTrusted: false }, { node: null }, { href: "javascript:void(0)" },
      { node: { hasAttribute: name => name === "download" } },
      { composedTarget: { ownerDocument: {}, className: "HTMLInputElement" } },
      { composedTarget: { ownerDocument: {}, className: "HTMLTextAreaElement" } },
      { principal: { blocked: true } },
    ]) {
      const event = f.event(override);
      f.capture(event);
      assert.equal(f.messages.length, 0, JSON.stringify(override));
      assert.equal(event.defaultPrevented, undefined);
    }
    f.prefs.set("uc.auto-glance.cmd-click-background", false);
    f.capture(f.event());
    assert.equal(f.messages.length, 0);
    f.click(f.event());
    assert.equal(f.loads[0].tab.glance, true, "disabling the override restores configured Glance");
  });

  test(`${os}: the background override wins a conflicting native Glance shortcut`, async t => {
    const f = await fixture(os);
    t.after(f.destroy);
    f.prefs.set("zen.glance.activation-method", os === "Darwin" ? "meta" : "ctrl");
    f.capture(f.event());
    assert.equal(f.nativeGlances.length, 0, "do not open a second preview before the normal tab");
    assert.equal(f.loads.length, 1);
    assert.equal(f.win.gBrowser.selectedTab, f.source);
    f.prefs.set("uc.auto-glance.cmd-click-background", false);
    f.capture(f.event());
    assert.equal(f.nativeGlances.length, 1, "disabling the override leaves native Glance available");
  });

  test(`${os}: actor cleanup preserves sibling frames and replacement actors`, async t => {
    const f = await fixture(os);
    t.after(f.destroy);
    f.prefs.set("zen.glance.activation-method", os === "Darwin" ? "meta" : "ctrl");
    const previous = f.contentActor(2);
    const replacement = f.contentActor(2);
    const sibling = f.contentActor(3);
    previous.destroy();
    replacement.nativeClick(f.event());
    sibling.nativeClick(f.event());
    assert.equal(f.nativeGlances.length, 0, "old cleanup must not remove another actor's guard");
    replacement.destroy();
    replacement.nativeClick(f.event());
    assert.equal(f.nativeGlances.length, 1, "a window without an owner returns to native Glance");
    sibling.nativeClick(f.event());
    assert.equal(f.nativeGlances.length, 1, "other frame ownership remains active");
  });

  for (const order of [["auto", "alt"], ["alt", "auto"]]) {
    test(`${os}: Alt-click remains a split with ${order.join(" then ")} hook order and reload`, async t => {
      const f = await fixture(os, order);
      t.after(f.destroy);
      for (let iteration = 0; iteration < 2; iteration++) {
        f.capture(f.event());
        assert.equal(f.win.gBrowser.selectedTab, f.source);
        assert.equal(f.loads.at(-1).params.inBackground, true);
        const alt = f.event({ ctrlKey: false, metaKey: false, altKey: true });
        f.capture(alt);
        assert.equal(alt.defaultPrevented, undefined);
        f.click(alt);
        assert.equal(f.splits.length, iteration + 1);
        assert.equal(f.splits.at(-1)[0], f.source);
        assert.equal(f.splits.at(-1)[1], f.loads.at(-1).tab);
        assert.equal(f.loads.at(-1).params.inBackground, false);
        assert.equal(f.loads.at(-1).tab.glance, false);
        f.win.gBrowser.selectedTab = f.source;
        await f.loadAuto();
      }
    });
  }
}
