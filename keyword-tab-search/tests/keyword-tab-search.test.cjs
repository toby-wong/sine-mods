const assert = require("node:assert/strict");
const { test } = require("node:test");
const { indexEngines, keywordAtCaret, createController } = require("../keyword-tab-search.uc.js");

const engine = (name, ...aliases) => ({ name, aliases });

test("explicit aliases win over stripped @ names; ambiguous aliases are ignored", () => {
  const builtin = engine("Built-in", "@google");
  const custom = engine("Custom", "Google");
  const one = engine("One", "@duplicate");
  const two = engine("Two", "@duplicate");
  const index = indexEngines([builtin, custom, one, two, { ...engine("Hidden", "hidden"), hidden: true }]);
  assert.equal(index.get("google"), custom);
  assert.equal(index.get("@google"), builtin);
  assert.equal(index.get("duplicate"), null);
  assert.equal(index.has("hidden"), false);
});

function bar(value, start = value.length, end = start) {
  return { inputField: { value, selectionStart: start, selectionEnd: end } };
}

test("only a whole keyword at the end or a genuine selected autofill suffix matches", () => {
  assert.equal(keywordAtCaret(bar("Cr")), "cr");
  for (const value of ["", "cr query", " cr", "cr "]) assert.equal(keywordAtCaret(bar(value)), null);
  assert.equal(keywordAtCaret(bar("cr", 0)), null);
  assert.equal(keywordAtCaret(bar("cr", 0, 2)), null);
  const autofill = { ...bar("crux.example/", 2, 13), lastSearchString: "cr",
    _autofillPlaceholder: { value: "crux.example/" } };
  assert.equal(keywordAtCaret(autofill), "cr");
  delete autofill._autofillPlaceholder;
  assert.equal(keywordAtCaret(autofill), null);
});

async function fixture() {
  const listeners = new Map();
  const captures = new Map();
  const searches = [];
  let engines = [engine("Crux", "cr")], enabled = true, observer;
  const inputBar = { ...bar("cr"), focused: true, view: {},
    search: (...args) => searches.push(args) };
  const win = {
    gURLBar: inputBar, console, queueMicrotask, document: {},
    addEventListener: (type, fn, capture) => {
      listeners.set(type, fn);
      captures.set(type, capture);
    },
    removeEventListener: (type, _fn, capture) => {
      assert.equal(capture, captures.get(type));
      listeners.delete(type);
      captures.delete(type);
    },
  };
  const api = createController(win, {
    getEngines: async () => engines,
    prefs: { getBoolPref: () => enabled },
    observers: {
      addObserver: value => { observer = value; },
      removeObserver: value => { assert.equal(value, observer); observer = null; },
    },
  });
  await api.ready;
  return {
    api, inputBar, listeners, searches, win, captures,
    setEnabled: value => { enabled = value; },
    async setEngines(value) {
      engines = value;
      observer.observe();
      await new Promise(resolve => setImmediate(resolve));
      await api.ready;
    },
    tab(overrides = {}) {
      const event = {
        key: "Tab", target: inputBar.inputField,
        composedPath: () => [inputBar.inputField],
        preventDefault() { this.defaultPrevented = true; },
        stopImmediatePropagation() { this.stopped = true; },
        ...overrides,
      };
      listeners.get("keydown")?.(event);
      return event;
    },
  };
}

test("Tab enters the engine's native search mode without submitting a query", async t => {
  const f = await fixture();
  t.after(f.api.destroy);
  assert.equal(f.tab().defaultPrevented, true);
  assert.equal(f.searches.length, 1);
  assert.equal(f.searches[0][0], "");
  assert.equal(f.searches[0][1].searchEngine.name, "Crux");
  assert.equal(f.searches[0][1].searchModeEntry, "keywordoffer");
});

test("modified Tab, page fields, IME, existing search mode, and selected results remain native", async t => {
  const f = await fixture();
  t.after(f.api.destroy);
  for (const property of ["shiftKey", "ctrlKey", "altKey", "metaKey", "isComposing", "repeat", "defaultPrevented"]) {
    assert.equal(f.tab({ [property]: true }).stopped, undefined);
  }
  assert.equal(f.tab({ target: {}, composedPath: () => [] }).stopped, undefined);
  f.listeners.get("compositionstart")({ target: f.inputBar.inputField });
  assert.equal(f.tab().stopped, undefined);
  f.listeners.get("compositionend")();
  f.inputBar.searchMode = { engineName: "Other" };
  assert.equal(f.tab().stopped, undefined);
  f.inputBar.searchMode = null;
  f.inputBar.view.selectedResult = { heuristic: false };
  assert.equal(f.tab().stopped, undefined);
  f.inputBar.view.selectedResult = null;
  f.setEnabled(false);
  assert.equal(f.tab().stopped, undefined);
  assert.equal(f.searches.length, 0);
});

test("engine edits invalidate stale aliases; unload removes listeners and observers", async () => {
  const f = await fixture();
  await f.setEngines([engine("Crux renamed", "review")]);
  assert.equal(f.tab().stopped, undefined);
  Object.assign(f.inputBar, bar("review"));
  assert.equal(f.tab().stopped, true);
  assert.equal(f.searches[0][1].searchEngine.name, "Crux renamed");
  f.api.destroy();
  f.api.destroy();
  assert.equal(f.listeners.size, 0);
  assert.equal(f.api.status, "destroyed");
});

test("child-page unloads preserve the shortcut; owning window unload cleans up", async t => {
  for (const target of ["document", "window"]) {
    const f = await fixture();
    t.after(f.api.destroy);
    assert.equal(f.captures.get("unload"), false);
    const unload = f.listeners.get("unload");
    unload({ target: { documentURI: "about:blank" } });
    assert.equal(f.api.status, "ready");
    assert.equal(f.tab().defaultPrevented, true);
    unload({ target: target === "document" ? f.win.document : f.win });
    assert.equal(f.api.status, "destroyed");
    assert.equal(f.listeners.size, 0);
  }
});
