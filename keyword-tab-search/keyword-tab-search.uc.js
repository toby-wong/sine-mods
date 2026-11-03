// ==UserScript==
// @name           Keyword Tab Search
// @version        0.1.1
// @description    Activate a saved search keyword with Tab.
// @include        chrome://browser/content/browser.xhtml
// ==/UserScript==

(() => {
  "use strict";
  const VERSION = "0.1.1";
  const PREF = "uc.keyword-tab-search.enabled";
  const TOPIC = "browser-search-engine-modified";
  const normalize = value => value.toLocaleLowerCase();

  function indexEngines(engines) {
    const exact = new Map(), bare = new Map();
    const add = (index, keyword, engine) => {
      if (!keyword || /\s/.test(keyword)) return;
      if (index.has(keyword) && index.get(keyword) !== engine) index.set(keyword, null);
      else index.set(keyword, engine);
    };
    for (const engine of engines) {
      if (engine.hidden) continue;
      for (const alias of engine.aliases || []) {
        const keyword = normalize(alias);
        add(exact, keyword, engine);
        if (keyword.startsWith("@")) add(bare, keyword.slice(1), engine);
      }
    }
    // Explicit keywords win over names derived from built-in @ aliases.
    for (const [keyword, engine] of bare) {
      if (!exact.has(keyword)) exact.set(keyword, engine);
    }
    return exact;
  }

  function keywordAtCaret(bar) {
    const input = bar.inputField;
    const value = input.value;
    let keyword = value;
    if (input.selectionStart !== input.selectionEnd) {
      // Native URL autofill selects the completed suffix. Match the text the
      // user actually typed, without treating arbitrary selections as keywords.
      const typed = bar.lastSearchString;
      if (!typed || bar._autofillPlaceholder?.value !== value ||
          input.selectionStart !== typed.length || input.selectionEnd !== value.length ||
          !normalize(value).startsWith(normalize(typed))) return null;
      keyword = typed;
    } else if (input.selectionEnd !== value.length) {
      return null;
    }
    return keyword && !/\s/.test(keyword) ? normalize(keyword) : null;
  }

  function createController(win, { getEngines, prefs, observers }) {
    let index = new Map(), generation = 0, destroyed = false, composing = false;
    let queued = false;
    const api = { version: VERSION, status: "starting", refresh, destroy };
    async function refresh() {
      const request = ++generation;
      index = new Map();
      try {
        const engines = await getEngines();
        if (destroyed || request !== generation) return;
        index = indexEngines(engines);
        api.status = "ready";
        delete api.error;
      } catch (error) {
        if (destroyed || request !== generation) return;
        api.status = "error";
        api.error = String(error);
        win.console.error("[Keyword Tab Search]", error);
      }
    }
    const observer = {
      observe() {
        index = new Map();
        generation++;
        if (queued || destroyed) return;
        queued = true;
        win.queueMicrotask(() => {
          queued = false;
          if (!destroyed) api.ready = refresh();
        });
      },
    };
    const inInput = event => {
      const input = win.gURLBar?.inputField;
      return input && (event.target === input || event.composedPath().includes(input));
    };
    const compositionStart = event => { if (inInput(event)) composing = true; };
    const compositionEnd = () => { composing = false; };
    const keydown = event => {
      if (destroyed || event.key !== "Tab" || event.defaultPrevented || event.repeat ||
          event.shiftKey || event.ctrlKey || event.altKey || event.metaKey ||
          event.isComposing || composing || !prefs.getBoolPref(PREF, true)) return;
      const bar = win.gURLBar;
      if (!bar?.focused || !inInput(event) || bar.searchMode ||
          typeof bar.search !== "function") return;
      const selected = bar.view?.selectedResult;
      if (selected && !selected.heuristic) return;
      const keyword = keywordAtCaret(bar);
      const engine = keyword && index.get(keyword);
      if (!engine) return;
      // Use native search mode: it owns query encoding, POST, containers,
      // privacy, suggestions, Enter, and Escape.
      bar.search("", { searchEngine: engine, searchModeEntry: "keywordoffer" });
      event.preventDefault();
      event.stopImmediatePropagation();
    };
    function destroy() {
      if (destroyed) return;
      destroyed = true;
      generation++;
      index.clear();
      observers.removeObserver(observer, TOPIC);
      for (const [type, handler, capture] of events) win.removeEventListener(type, handler, capture);
      api.status = "destroyed";
      if (win.KeywordTabSearch === api) delete win.KeywordTabSearch;
    }
    const windowUnload = event => {
      // Chrome can receive captured unloads from child documents, including
      // the about:blank document replaced when Settings opens.
      if (event.target === win || event.target === win.document) destroy();
    };
    const events = [
      ["keydown", keydown, true], ["compositionstart", compositionStart, true],
      ["compositionend", compositionEnd, true], ["blur", compositionEnd, true],
      ["unload", windowUnload, false],
    ];
    for (const [type, handler, capture] of events) win.addEventListener(type, handler, capture);
    observers.addObserver(observer, TOPIC);
    api.ready = refresh();
    return api;
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { indexEngines, keywordAtCaret, createController };
    return;
  }
  window.KeywordTabSearch?.destroy();
  const search = Services.search ||
    ChromeUtils.importESModule("moz-src:///toolkit/components/search/SearchService.sys.mjs").SearchService;
  window.KeywordTabSearch = createController(window, {
    getEngines: () => search.getVisibleEngines(),
    prefs: Services.prefs,
    observers: Services.obs,
  });
  window.addUnloadListener?.(window.KeywordTabSearch.destroy);
})();
