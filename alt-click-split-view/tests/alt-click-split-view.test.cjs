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
