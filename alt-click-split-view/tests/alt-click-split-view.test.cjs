const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');
const preferences = require('../preferences.json');
let policy;
try { policy = require('../alt-click-split-view.uc.js'); } catch (error) {
  if (error.code !== 'MODULE_NOT_FOUND') throw error;
}

test('only the selected modifier on a primary link opts into split view', () => {
  assert.ok(policy, 'Alt-click Split View policy is implemented');
  assert.equal(policy.shouldSplitLinkClick({
    button: 0,
    href: 'https://example.com',
    altKey: true,
    ctrlKey: false,
    metaKey: false,
    shiftKey: false,
  }), true);
  assert.equal(policy.shouldSplitLinkClick({
    button: 0,
    href: 'https://example.com',
    altKey: false,
    ctrlKey: true,
    metaKey: false,
    shiftKey: false,
  }, 'ctrl'), true);
  assert.equal(policy.shouldSplitLinkClick({
    button: 0,
    href: 'https://example.com',
    altKey: true,
    ctrlKey: false,
    metaKey: false,
    shiftKey: false,
  }, 'ctrl'), false);
  assert.equal(policy.shouldSplitLinkClick({
    button: 0,
    href: 'https://example.com',
    altKey: false,
    ctrlKey: false,
    metaKey: false,
    shiftKey: true,
  }, 'shift'), true);
  for (const data of [
    { button: 1, altKey: true },
    { button: 0, altKey: false },
    { button: 0, altKey: true, ctrlKey: true },
    { button: 0, altKey: true, metaKey: true },
    { button: 0, altKey: true, shiftKey: true },
    { button: 0, altKey: true, href: '' },
  ]) {
    assert.equal(policy.shouldSplitLinkClick({ href: 'https://example.com', ...data }), false);
  }
});

test('hover selection is delayed, guarded, and cancelled on unload', () => {
  const listeners = new Map(), timers = new Map();
  let enabled = false, nextId = 0;
  const targetBrowser = {}, tab = { linkedBrowser: targetBrowser };
  const panels = { getAttribute: () => 'true' };
  const pane = { parentNode: panels, isConnected: true, matches: () => true,
    getAttribute: () => 'true', querySelector: () => targetBrowser };
  const win = {
    document: { hasFocus: () => true, documentElement: { hasAttribute: () => false, getAttribute: () => null }, querySelector: () => null },
    gBrowser: { tabpanels: panels, selectedBrowser: {}, getTabForBrowser: () => tab },
    gURLBar: { focused: false, view: { isOpen: false } },
    addEventListener: (name, fn) => listeners.set(name, fn),
    removeEventListener: name => listeners.delete(name),
    setTimeout: (fn, ms) => { assert.equal(ms, 150); timers.set(++nextId, fn); return nextId; },
    clearTimeout: id => timers.delete(id),
  };
  const cleanup = policy.installHoverFocus(win, { getBoolPref: () => enabled });
  const move = { buttons: 0, target: { closest: () => pane } };
  listeners.get('mousemove')(move);
  assert.equal(timers.size, 0);
  enabled = true;
  listeners.get('mousemove')(move);
  assert.equal(win.gBrowser.selectedTab, undefined);
  [...timers.values()][0]();
  assert.equal(win.gBrowser.selectedTab, tab);
  win.gBrowser.selectedTab = undefined;
  win.gURLBar.focused = true;
  listeners.get('mousemove')(move);
  assert.equal(timers.size, 0);
  win.gURLBar.focused = false;
  listeners.get('mousemove')(move);
  listeners.get('mousedown')();
  assert.equal(timers.size, 0);
  listeners.get('mousemove')(move);
  cleanup();
  assert.equal(timers.size, 0);
  assert.equal(listeners.size, 0);
});

test('Sine preferences expose the enable toggle and four trigger choices', () => {
  const enabled = preferences.find(pref => pref.property === 'uc.alt-click-split-view.enabled');
  const trigger = preferences.find(pref => pref.property === 'uc.alt-click-split-view.trigger');
  assert.equal(enabled.type, 'checkbox');
  assert.equal(enabled.defaultValue, true);
  const hover = preferences.find(pref => pref.property === 'uc.alt-click-split-view.focus-on-hover');
  assert.equal(hover.type, 'checkbox');
  assert.equal(hover.defaultValue, false);
  const adaptive = preferences.find(pref => pref.property === 'uc.alt-click-split-view.adaptive-direction');
  assert.equal(adaptive.type, 'checkbox');
  assert.equal(adaptive.defaultValue, true);
  assert.equal(trigger.type, 'dropdown');
  assert.deepEqual(trigger.options.map(option => option.value), ['ctrl', 'alt', 'shift', 'meta']);
  assert.equal(trigger.defaultValue, 'alt');
});

// Exercise the actual parent hook against the native new-tab contract on each
// platform. Browser UI and OS input still need separate live validation.
function browserFixture(os, glanceTrigger) {
  const sourceTab = { isConnected: true, closing: false };
  const destinationTab = {};
  const receivedClicks = [], nativeOpens = [], splitOpens = [], splits = [];
  const prefs = new Map();
  if (glanceTrigger !== undefined) prefs.set('zen.glance.activation-method', glanceTrigger);
  const win = {
    gBrowserInit: { delayedStartupFinished: false },
    addEventListener() {},
    removeEventListener() {},
    gBrowser: { getTabForBrowser: () => sourceTab },
    gZenGlanceManager: { getFocusedTab: () => null },
    gZenViewSplitter: {
      canOpenLinkInSplitView: () => true,
      openAndSwitchToTab(url, params) {
        splitOpens.push({ url, params });
        return destinationTab;
      },
      splitTabs(tabs) { splits.push([...tabs]); },
    },
    openLinkIn(url, where, params) { nativeOpens.push({ url, where, params }); },
  };
  const browser = { documentGlobal: win };
  class ClickHandlerParent {
    constructor() {
      this.manager = { browsingContext: { top: { embedderElement: browser } } };
    }
    contentAreaClick(data) {
      receivedClicks.push(data);
      // Firefox uses Command on macOS and Ctrl on Windows/Linux for a new tab.
      const accelerator = os === 'Darwin' ? data.metaKey : data.ctrlKey;
      const where = accelerator ? 'tab' : data.altKey ? 'save' : 'current';
      if (where === 'current') return;
      win.openLinkIn(data.href, where, {
        triggeringPrincipal: data.triggeringPrincipal,
        referrerInfo: data.referrerInfo,
        openerBrowser: browser,
      });
    }
  }
  vm.runInNewContext(
    fs.readFileSync(path.join(__dirname, '../alt-click-split-view.uc.js'), 'utf8'),
    {
      window: win,
      Services: {
        appinfo: { OS: os },
        prefs: {
          getBoolPref: (key, fallback) => prefs.has(key) ? prefs.get(key) : fallback,
          getStringPref: (key, fallback) => prefs.has(key) ? prefs.get(key) : fallback,
          setBoolPref: (key, value) => prefs.set(key, value),
        },
        obs: { addObserver() {}, removeObserver() {} },
      },
      ChromeUtils: {
        importESModule: () => ({ ClickHandlerParent }),
        registerWindowActor() {},
        unregisterWindowActor() {},
      },
      gZenStartup: { promiseInitialized: Promise.resolve() },
      console,
    },
  );
  return {
    click: data => new ClickHandlerParent().contentAreaClick(data),
    destroy: () => win.AltClickSplitView.destroy({ reloading: true }),
    sourceTab, destinationTab, browser, prefs, receivedClicks, nativeOpens, splitOpens, splits,
  };
}

function altClick() {
  return {
    button: 0,
    href: 'https://example.test/destination',
    altKey: true,
    ctrlKey: false,
    metaKey: false,
    shiftKey: false,
    triggeringPrincipal: { origin: 'https://example.test' },
    referrerInfo: { originalReferrer: 'https://example.test/source' },
  };
}

for (const os of ['WINNT', 'Darwin', 'Linux']) {
  test(`${os}: Alt-click splits using only the native tab accelerator`, t => {
    const fixture = browserFixture(os, 'shift');
    t.after(fixture.destroy);
    const click = altClick();
    fixture.click(click);
    assert.equal(fixture.nativeOpens.length, 0, 'do not open a second normal tab or save the link');
    assert.equal(fixture.splitOpens.length, 1);
    assert.equal(fixture.splits.length, 1);
    assert.equal(fixture.splits[0][0], fixture.sourceTab, 'reuse the original source tab');
    assert.equal(fixture.splits[0][1], fixture.destinationTab);
    assert.equal(fixture.splitOpens[0].url, click.href);
    assert.equal(fixture.splitOpens[0].params.triggeringPrincipal, click.triggeringPrincipal);
    assert.equal(fixture.splitOpens[0].params.referrerInfo, click.referrerInfo);
    assert.equal(fixture.splitOpens[0].params.openerBrowser, fixture.browser);
    assert.equal(fixture.splitOpens[0].params.inBackground, false);
    const nativeClick = fixture.receivedClicks[0];
    assert.equal(nativeClick.ctrlKey, os !== 'Darwin');
    assert.equal(nativeClick.metaKey, os === 'Darwin');
    assert.equal(nativeClick.altKey, false);
    assert.equal(nativeClick.shiftKey, false);
    assert.equal(click.altKey, true, 'do not mutate the original click message');
    assert.equal(click.ctrlKey, false);
    assert.equal(click.metaKey, false);
  });
}

test('an unset Glance preference uses native Ctrl fallback and does not swallow Alt-click', t => {
  const fixture = browserFixture('WINNT');
  t.after(fixture.destroy);
  fixture.click(altClick());
  assert.equal(fixture.splitOpens.length, 1);
  assert.equal(fixture.nativeOpens.length, 0);
});

test('a conflicting Glance gesture and a disabled mod remain native', t => {
  const fixture = browserFixture('WINNT', 'alt');
  t.after(fixture.destroy);
  const click = altClick();
  fixture.click(click);
  assert.equal(fixture.splitOpens.length, 0);
  assert.equal(fixture.receivedClicks[0], click);
  fixture.prefs.set('zen.glance.activation-method', 'shift');
  fixture.prefs.set('uc.alt-click-split-view.enabled', false);
  fixture.click(click);
  assert.equal(fixture.splitOpens.length, 0);
  assert.equal(fixture.receivedClicks[1], click);
});

function adaptiveFixture() {
  const calls = [], prefs = new Map(), result = {};
  const tab = () => ({ splitView: false, hidden: false, hasAttribute: () => false });
  const tabs = [tab(), tab()];
  const splitter = {
    splitTabs(...args) { calls.push({ method: 'tabs', receiver: this, args }); return result; },
    createEmptySplit(...args) { calls.push({ method: 'empty', receiver: this, args }); return result; },
  };
  let finishPromotion;
  const promoted = new Promise(resolve => { finishPromotion = resolve; });
  const glance = {
    getFocusedTab: direction => tabs[direction < 0 ? 0 : 1],
    getTabOrGlanceParent: t => t,
    async splitGlance() {
      await promoted;
      return splitter.splitTabs(tabs, 'vsep', 1);
    },
  };
  const win = { outerWidth: 800, outerHeight: 1200, gZenViewSplitter: splitter, gZenGlanceManager: glance };
  const originals = { splitTabs: splitter.splitTabs, createEmptySplit: splitter.createEmptySplit, splitGlance: glance.splitGlance };
  const cleanup = policy.installAdaptiveSplits(win, {
    getBoolPref: (key, fallback) => prefs.has(key) ? prefs.get(key) : fallback,
  });
  return { win, splitter, glance, tabs, tab, calls, prefs, result, originals, cleanup, finishPromotion };
}

test('new default splits use current window shape and preserve native arguments', t => {
  const f = adaptiveFixture();
  t.after(f.cleanup);
  const options = { activate: false };
  assert.equal(f.splitter.splitTabs(f.tabs, undefined, 1, options), f.result);
  assert.deepEqual(f.calls.pop(), { method: 'tabs', receiver: f.splitter, args: [f.tabs, 'hsep', 1, options] });
  assert.equal(f.splitter.createEmptySplit(), f.result);
  assert.deepEqual(f.calls.pop().args, ['bottom']);
  for (const [width, height] of [[1200, 800], [900, 900], [0, 1200]]) {
    Object.assign(f.win, { outerWidth: width, outerHeight: height });
    f.splitter.splitTabs(f.tabs);
    assert.deepEqual(f.calls.pop().args, [f.tabs]);
    f.splitter.createEmptySplit();
    assert.deepEqual(f.calls.pop().args, []);
  }
  Object.assign(f.win, { outerWidth: 800, outerHeight: 1200 });
  f.splitter.createEmptySplit();
  assert.deepEqual(f.calls.pop().args, ['bottom'], 'read the current dimensions for every new split');
});

test('explicit layouts, directions, restored sessions, and existing groups retain their layout', t => {
  const f = adaptiveFixture();
  t.after(f.cleanup);
  for (const grid of ['vsep', 'hsep', 'grid']) {
    f.splitter.splitTabs(f.tabs, grid, 0);
    assert.deepEqual(f.calls.pop().args, [f.tabs, grid, 0]);
  }
  for (const side of ['left', 'right', 'top', 'bottom']) {
    f.splitter.createEmptySplit(side);
    assert.deepEqual(f.calls.pop().args, [side]);
  }
  f.splitter._sessionRestoring = true;
  f.splitter.splitTabs(f.tabs);
  assert.deepEqual(f.calls.pop().args, [f.tabs]);
  f.splitter.createEmptySplit();
  assert.deepEqual(f.calls.pop().args, []);
  f.splitter._sessionRestoring = false;
  for (const property of ['splitView', 'hidden']) {
    f.tabs[0][property] = true;
    f.splitter.splitTabs(f.tabs);
    assert.deepEqual(f.calls.pop().args, [f.tabs]);
    f.tabs[0][property] = false;
  }
  for (const tabs of [[...f.tabs, f.tab()], [f.tabs[0], f.tabs[0]]]) {
    f.splitter.splitTabs(tabs);
    assert.deepEqual(f.calls.pop().args, [tabs]);
  }
});

test('the direction toggle and master toggle disable adaptation immediately', t => {
  const f = adaptiveFixture();
  t.after(f.cleanup);
  for (const pref of ['uc.alt-click-split-view.adaptive-direction', 'uc.alt-click-split-view.enabled']) {
    f.prefs.set(pref, false);
    f.splitter.splitTabs(f.tabs);
    assert.deepEqual(f.calls.pop().args, [f.tabs]);
    f.splitter.createEmptySplit();
    assert.deepEqual(f.calls.pop().args, []);
    f.prefs.set(pref, true);
  }
  f.splitter.splitTabs(f.tabs);
  assert.equal(f.calls.pop().args[1], 'hsep');
});

test('Glance adaptation follows its exact promoted pair and ends when promotion finishes', async t => {
  const f = adaptiveFixture();
  t.after(f.cleanup);
  const pending = f.glance.splitGlance();
  const unrelated = [f.tab(), f.tab()];
  f.splitter.splitTabs(unrelated, 'vsep');
  assert.deepEqual(f.calls.pop().args, [unrelated, 'vsep']);
  f.finishPromotion();
  assert.equal(await pending, f.result);
  assert.deepEqual(f.calls.pop().args, [f.tabs, 'hsep', 1]);
  f.splitter.splitTabs(f.tabs, 'vsep');
  assert.deepEqual(f.calls.pop().args, [f.tabs, 'vsep']);
});

test('unloading during Glance promotion restores methods and leaves its completion native', async () => {
  const f = adaptiveFixture();
  const pending = f.glance.splitGlance();
  f.cleanup();
  f.cleanup();
  assert.equal(f.splitter.splitTabs, f.originals.splitTabs);
  assert.equal(f.splitter.createEmptySplit, f.originals.createEmptySplit);
  assert.equal(f.glance.splitGlance, f.originals.splitGlance);
  f.finishPromotion();
  assert.equal(await pending, f.result);
  assert.deepEqual(f.calls.pop().args, [f.tabs, 'vsep', 1]);
});

test('unloading preserves a later wrapper and leaves the old adaptation inert', () => {
  const f = adaptiveFixture();
  const installed = f.splitter.splitTabs;
  const later = function (...args) { return installed.apply(this, args); };
  f.splitter.splitTabs = later;
  f.cleanup();
  assert.equal(f.splitter.splitTabs, later);
  assert.equal(f.splitter.splitTabs(f.tabs), f.result);
  assert.deepEqual(f.calls.pop().args, [f.tabs]);
});
