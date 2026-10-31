// ==UserScript==
// @name           Tree Tabs Prototype
// @version        0.1.1
// @description    Parent and child tabs in Zen's existing sidebar.
// @include        chrome://browser/content/browser.xhtml
// ==/UserScript==

(() => {
  "use strict";
  window.TreeTabs?.destroy();

  const PREFIX = "uc.tree-tabs.";
  const STORAGE = "uc-tree-tabs-state";
  const nodes = new Map();
  const pendingParents = new Map();
  const pendingMoves = new Set();
  const cleanups = [];
  let destroyed = false;
  let moving = 0;
  let timer = 0;
  let menu;

  const enabled = () => !destroyed &&
    Services.prefs.getBoolPref(PREFIX + "enabled", true);
  const allTabs = () => [...gZenWorkspaces.allStoredTabs].filter(t => t.isConnected && !t.closing);
  const workspace = tab => tab.getAttribute("zen-workspace-id") || "";
  const eligible = tab => !!tab?.isConnected && !tab.closing &&
    gBrowser.isTab(tab) && !tab.pinned && !tab.group && !tab.splitview &&
    !["zen-essential", "zen-glance-tab", "zen-empty-tab", "split-view",
      "zen-live-folder-item-id"].some(attribute => tab.hasAttribute(attribute));
  const report = error => {
    api.lastError = String(error);
    console.error("[Tree Tabs]", error);
  };

  function read(tab) {
    try {
      const value = JSON.parse(SessionStore.getCustomTabValue(tab, STORAGE) || "null");
      if (value?.v === 1 && typeof value.id === "string" && value.id.length < 100) {
        return {
          id: value.id,
          parentId: typeof value.parent === "string" ? value.parent : "",
          collapsed: value.collapsed === true,
        };
      }
    } catch {}
    return null;
  }

  function ensure(tab, restoring = false) {
    let node = nodes.get(tab);
    const saved = !node || restoring ? read(tab) : null;
    if (!node) {
      node = {
        tab, id: Services.uuid.generateUUID().toString(),
        parentId: "", collapsed: false, parent: null, children: [], space: workspace(tab),
      };
      nodes.set(tab, node);
    }
    if (saved) Object.assign(node, saved);
    return node;
  }

  function save(node) {
    if (!node.tab.isConnected || node.tab.closing) return;
    const value = JSON.stringify({
      v: 1, id: node.id, parent: node.parentId, collapsed: node.collapsed,
    });
    if (SessionStore.getCustomTabValue(node.tab, STORAGE) !== value) {
      SessionStore.setCustomTabValue(node.tab, STORAGE, value);
    }
  }

  function descendants(node) {
    const result = [];
    const visit = parent => {
      for (const child of parent.children) {
        result.push(child);
        visit(child);
      }
    };
    visit(node);
    return result;
  }

  function depth(node) {
    let count = 0;
    for (let parent = node?.parent; parent; parent = parent.parent) count++;
    return count;
  }

  function clearUI(tab) {
    for (const attribute of ["uc-tree-node", "uc-tree-parent", "uc-tree-hidden", "uc-tree-collapsed"]) {
      tab.removeAttribute(attribute);
    }
    tab.style.removeProperty("--uc-tree-depth");
    tab.querySelector(".uc-tree-twisty")?.remove();
  }

  // Native pinning/grouping wins. Promote surviving children rather
  // than fighting the browser's move or pulling another tab out of a group.
  function release(node, closing = false) {
    if (!node) return;
    const parent = node.parent && eligible(node.parent.tab) ? node.parent : null;
    for (const child of nodes.values()) {
      if (child.parentId !== node.id || child.tab.closing) continue;
      child.parentId = parent && workspace(parent.tab) === workspace(child.tab) ? parent.id : "";
      child.parent = null;
      save(child);
    }
    if (!closing) {
      const changed = !!node.parentId || node.collapsed;
      node.parentId = "";
      node.parent = null;
      node.collapsed = false;
      if (changed) save(node);
    }
  }

  function followMovedBranches() {
    if (!enabled()) {
      pendingMoves.clear();
      return;
    }
    // A drag across Spaces sets the workspace attribute after TabMove, and
    // some native moves change only that attribute. Compare the final state
    // with the last reconciliation before rebuilding any parent links.
    for (const node of nodes.values()) {
      if (node.space && workspace(node.tab) && node.space !== workspace(node.tab)) {
        pendingMoves.add(node);
      }
    }
    const moved = new Set([...pendingMoves].filter(node =>
      nodes.get(node.tab) === node && eligible(node.tab) && node.tab.ownerDocument === document));
    pendingMoves.clear();
    // Native multi-tab moves emit one event per tab. A selected descendant
    // belongs to its moved ancestor's branch, not to a second independent move.
    const roots = [...moved].filter(node => {
      for (let parent = node.parent; parent; parent = parent.parent) {
        if (moved.has(parent) && workspace(parent.tab) === workspace(node.tab)) return false;
      }
      return true;
    });
    for (const node of roots) {
      const space = workspace(node.tab);
      const branch = [];
      const collect = child => {
        if (!eligible(child.tab) || child.tab.ownerDocument !== document) return;
        // Respect an independent move to a different Space in the same batch.
        if (child !== node && moved.has(child) && workspace(child.tab) !== space) return;
        branch.push(child);
        child.children.forEach(collect);
      };
      collect(node);
      moving++;
      try {
        if (node.space !== space && gZenWorkspaces.workspaceElement(space)) {
          // Use the native operation so Space membership and last-selected-tab
          // bookkeeping change without recreating browsers or reloading pages.
          gZenWorkspaces.moveTabsToWorkspace(branch.map(child => child.tab), space);
          gZenWorkspaces.updateTabsContainers();
        }
        const followers = branch.slice(1).filter(child => workspace(child.tab) === space);
        if (followers.length) gBrowser.moveTabsAfter(followers.map(child => child.tab), node.tab);
        // Reordering detaches only the branch root. Its descendants, saved
        // identities, and collapse flags all stay intact.
        if (node.parent) node.parent.children = node.parent.children.filter(child => child !== node);
        node.parent = null;
        if (node.parentId) {
          node.parentId = "";
          save(node);
        }
        for (const child of branch) child.space = workspace(child.tab);
      } finally {
        moving--;
      }
    }
  }

  function render() {
    const active = enabled();
    const indent = Math.max(8, Math.min(28,
      Services.prefs.getIntPref(PREFIX + "indent", 14)));
    document.documentElement.style.setProperty("--uc-tree-indent", `${indent}px`);
    for (const node of nodes.values()) {
      const tab = node.tab;
      if (!active || !eligible(tab) || (!node.parent && !node.children.length)) {
        clearUI(tab);
        continue;
      }
      let hidden = false;
      for (let ancestor = node.parent; ancestor; ancestor = ancestor.parent) {
        hidden ||= ancestor.collapsed;
      }
      tab.setAttribute("uc-tree-node", "true");
      tab.toggleAttribute("uc-tree-parent", node.children.length > 0);
      tab.toggleAttribute("uc-tree-hidden", hidden);
      tab.toggleAttribute("uc-tree-collapsed", node.collapsed);
      tab.style.setProperty("--uc-tree-depth", String(depth(node)));
      let button = tab.querySelector(".uc-tree-twisty");
      if (!node.children.length) {
        button?.remove();
        continue;
      }
      if (!button) {
        const content = tab.querySelector(".tab-content");
        if (!content) continue;
        button = document.createElementNS("http://www.w3.org/1999/xhtml", "button");
        button.className = "uc-tree-twisty";
        button.type = "button";
        button.addEventListener("mousedown", event => {
          if (event.button === 0) {
            event.preventDefault();
            event.stopPropagation();
          }
        });
        button.addEventListener("click", event => {
          event.preventDefault();
          event.stopPropagation();
          toggleCollapse(tab);
        });
        content.prepend(button);
      }
      button.textContent = node.collapsed ? "▸" : "▾";
      button.setAttribute("aria-expanded", String(!node.collapsed));
      button.setAttribute("aria-label", `${node.collapsed ? "Expand" : "Collapse"} child tabs`);
      button.title = `${node.collapsed ? "Expand" : "Collapse"} ${descendants(node).length} child tabs`;
    }
  }

  function reconcile() {
    const started = performance.now();
    followMovedBranches();
    const tabs = allTabs();
    const live = new Set(tabs);
    for (const [tab] of nodes) {
      if (!live.has(tab)) nodes.delete(tab);
    }
    const byId = new Map();
    for (const tab of tabs) ensure(tab);
    // Existing nodes win identity collisions even if a newly duplicated tab
    // was inserted before the original in the sidebar.
    for (const node of nodes.values()) {
      if (byId.has(node.id)) {
        // Duplicate-tab can copy session data; it must not steal an identity.
        node.id = Services.uuid.generateUUID().toString();
        node.parentId = "";
        node.collapsed = false;
        save(node);
      }
      byId.set(node.id, node);
    }
    for (const node of nodes.values()) {
      if (!eligible(node.tab)) release(node);
      node.children = [];
      node.parent = null;
      node.space = workspace(node.tab);
    }
    for (const tab of tabs) {
      const node = nodes.get(tab);
      if (!eligible(node.tab) || !node.parentId) continue;
      const parent = byId.get(node.parentId);
      // Missing parents may still be restoring. Keep the saved id but render
      // the child at root until that parent arrives.
      if (!parent) continue;
      let valid = eligible(parent.tab) && workspace(parent.tab) === workspace(node.tab);
      const seen = new Set([node.id]);
      for (let ancestor = parent; valid && ancestor; ancestor = byId.get(ancestor.parentId)) {
        if (seen.has(ancestor.id)) valid = false;
        seen.add(ancestor.id);
      }
      if (!valid) {
        node.parentId = "";
        save(node);
        continue;
      }
      node.parent = parent;
      parent.children.push(node);
    }
    for (const [tab, parentTab] of pendingParents) {
      pendingParents.delete(tab);
      if (enabled() && eligible(tab) && eligible(parentTab)) nest(tab, parentTab, false);
    }
    revealSelected(false);
    render();
    api.reconciliations++;
    api.lastReconcileMs = performance.now() - started;
  }

  function schedule(delay = 30) {
    if (destroyed || timer) return;
    timer = setTimeout(() => {
      timer = 0;
      try { reconcile(); } catch (error) { report(error); }
    }, delay);
  }

  function nest(tab, parentTab, update = true) {
    followMovedBranches();
    if (!enabled() || !eligible(tab) || !eligible(parentTab) ||
        tab === parentTab || workspace(tab) !== workspace(parentTab)) return false;
    const node = ensure(tab);
    const parent = ensure(parentTab);
    if (descendants(node).includes(parent) || depth(parent) + 1 > 8) return false;
    const branch = [node, ...descendants(node)];
    const targets = [parent, ...descendants(parent)].filter(n => !branch.includes(n));
    const anchor = targets.at(-1)?.tab || parentTab;
    moving++;
    try {
      gBrowser.moveTabsAfter(branch.map(n => n.tab), anchor);
    } finally {
      moving--;
    }
    if (node.parent) node.parent.children = node.parent.children.filter(n => n !== node);
    node.parentId = parent.id;
    node.parent = parent;
    parent.children.push(node);
    save(parent);
    save(node);
    if (update) {
      revealSelected(false);
      render();
    }
    return true;
  }

  function outdent(tab) {
    followMovedBranches();
    if (!enabled()) return false;
    const node = nodes.get(tab);
    const parent = node?.parent;
    if (!parent) return false;
    if (parent.parent) return nest(tab, parent.parent.tab);
    const branch = [node, ...descendants(node)];
    const anchor = [parent, ...descendants(parent)].filter(n => !branch.includes(n)).at(-1);
    moving++;
    try { gBrowser.moveTabsAfter(branch.map(n => n.tab), anchor.tab); }
    finally { moving--; }
    parent.children = parent.children.filter(n => n !== node);
    node.parentId = "";
    node.parent = null;
    save(node);
    render();
    return true;
  }

  function toggleCollapse(tab) {
    followMovedBranches();
    if (!enabled()) return;
    const node = nodes.get(tab);
    if (!node?.children.length) return;
    const collapse = !node.collapsed;
    if (collapse && descendants(node).some(n => n.tab === gBrowser.selectedTab)) {
      gBrowser.selectedTab = tab;
    }
    node.collapsed = collapse;
    save(node);
    render();
  }

  function revealSelected(update = true) {
    if (!enabled()) return;
    const node = nodes.get(gBrowser.selectedTab);
    let changed = false;
    for (let parent = node?.parent; parent; parent = parent.parent) {
      if (parent.collapsed) {
        parent.collapsed = false;
        save(parent);
        changed = true;
      }
    }
    if (changed && update) render();
  }

  function expandAll() {
    for (const node of nodes.values()) {
      if (node.collapsed && workspace(node.tab) === workspace(gBrowser.selectedTab)) {
        node.collapsed = false;
        save(node);
      }
    }
    render();
  }

  function listen(target, type, handler, options) {
    target.addEventListener(type, handler, options);
    cleanups.push(() => target.removeEventListener(type, handler, options));
  }

  function installMenu() {
    const parentMenu = document.getElementById("tabContextMenu");
    if (!parentMenu) return;
    menu = document.createXULElement("menu");
    menu.id = "uc-tree-tabs-menu";
    menu.setAttribute("label", "Tree tabs");
    const popup = document.createXULElement("menupopup");
    menu.append(popup);
    parentMenu.append(menu);
    const context = () => window.TabContextMenu?.contextTab;
    const previous = tab => {
      const tabs = allTabs();
      return tabs.slice(0, tabs.indexOf(tab)).reverse().find(t =>
        eligible(t) && workspace(t) === workspace(tab));
    };
    const item = (id, label, action) => {
      const element = document.createXULElement("menuitem");
      element.id = id;
      element.setAttribute("label", label);
      element.addEventListener("command", () => {
        try { action(context()); } catch (error) { report(error); }
      });
      popup.append(element);
      return element;
    };
    const nestItem = item("uc-tree-nest", "Nest under previous tab", tab => nest(tab, previous(tab)));
    const outdentItem = item("uc-tree-outdent", "Move out one level", outdent);
    const collapseItem = item("uc-tree-collapse", "Collapse child tabs", toggleCollapse);
    item("uc-tree-expand-all", "Expand all branches in this Space", expandAll);
    listen(parentMenu, "popupshowing", event => {
      if (event.target !== parentMenu) return;
      const tab = context();
      const node = nodes.get(tab);
      menu.hidden = !enabled() || !eligible(tab);
      nestItem.disabled = !previous(tab);
      outdentItem.disabled = !node?.parent;
      collapseItem.disabled = !node?.children.length;
      collapseItem.setAttribute("label", node?.collapsed ? "Expand child tabs" : "Collapse child tabs");
    });
    cleanups.push(() => menu.remove());
  }

  async function install() {
    if (!window.gBrowserInit?.delayedStartupFinished) {
      await new Promise(resolve => {
        let waiting = true;
        const stop = () => {
          if (!waiting) return;
          waiting = false;
          Services.obs.removeObserver(started, "browser-delayed-startup-finished");
          resolve();
        };
        const started = subject => {
          if (subject === window) stop();
        };
        Services.obs.addObserver(started, "browser-delayed-startup-finished");
        cleanups.push(stop);
      });
    }
    if (destroyed) return;
    await gZenStartup.promiseInitialized;
    if (destroyed) return;
    if (PrivateBrowsingUtils.isWindowPrivate(window) || window._littleZenInfo) {
      api.status = "outside-prototype-scope";
      return;
    }
    const style = document.createElementNS("http://www.w3.org/1999/xhtml", "link");
    style.rel = "stylesheet";
    style.href = "chrome://sine/content/tree-tabs-prototype/tree-tabs.css?v=0.1.1";
    document.documentElement.append(style);
    cleanups.push(() => style.remove());

    listen(window, "TabOpen", event => {
      const tab = event.target;
      if (enabled() && !event.detail?.fromExternal &&
          Services.prefs.getBoolPref(PREFIX + "auto-nest", true) && tab.openerTab) {
        pendingParents.set(tab, tab.openerTab);
      }
      schedule(80);
    });
    listen(window, "TabClose", event => {
      const node = nodes.get(event.target);
      release(node, true);
      pendingMoves.delete(node);
      nodes.delete(event.target);
      pendingParents.delete(event.target);
      schedule();
    });
    listen(window, "TabMove", event => {
      const node = nodes.get(event.target);
      if (!moving && enabled() && node) pendingMoves.add(node);
      if (!moving) schedule();
    });
    listen(window, "TabSelect", () => revealSelected());
    for (const type of ["TabPinned", "TabUnpinned", "TabGrouped", "TabUngrouped", "SSWindowStateReady"]) {
      listen(window, type, () => schedule());
    }
    listen(window, "SSTabRestored", event => {
      const node = ensure(event.target, true);
      node.space = workspace(event.target);
      pendingMoves.delete(node);
      pendingParents.delete(event.target);
      schedule();
    });
    const observer = new MutationObserver(() => schedule());
    observer.observe(gBrowser.tabContainer, {
      subtree: true, attributes: true,
      attributeFilter: ["zen-workspace-id", "zen-glance-tab", "split-view", "zen-essential", "pinned"],
    });
    cleanups.push(() => observer.disconnect());
    const prefObserver = { observe: () => schedule() };
    Services.prefs.addObserver(PREFIX, prefObserver);
    cleanups.push(() => Services.prefs.removeObserver(PREFIX, prefObserver));
    installMenu();
    reconcile();
    api.status = "ready";
  }

  function destroy() {
    if (destroyed) return;
    destroyed = true;
    clearTimeout(timer);
    for (const undo of cleanups.splice(0).reverse()) {
      try { undo(); } catch (error) { report(error); }
    }
    for (const tab of nodes.keys()) clearUI(tab);
    document.documentElement.style.removeProperty("--uc-tree-indent");
    nodes.clear();
    pendingParents.clear();
    pendingMoves.clear();
    if (window.TreeTabs === api) delete window.TreeTabs;
  }

  const api = window.TreeTabs = {
    version: "0.1.1", status: "starting", reconciliations: 0, lastReconcileMs: 0,
    nest, outdent, toggleCollapse, expandAll, destroy,
    parentOf: tab => nodes.get(tab)?.parent?.tab || null,
    depthOf: tab => depth(nodes.get(tab)),
    snapshot: () => [...nodes.values()].filter(n => eligible(n.tab)).map(n => ({
      tab: n.tab.id, id: n.id, parent: n.parent?.id || "", collapsed: n.collapsed,
      depth: depth(n), hidden: n.tab.hasAttribute("uc-tree-hidden"),
      children: n.children.length, workspace: workspace(n.tab),
    })),
  };
  window.addUnloadListener?.(destroy);
  listen(window, "unload", destroy, { once: true });
  install().catch(error => {
    api.status = "error";
    report(error);
  });
})();
