// ==UserScript==
// @name           Tree Tabs Prototype
// @version        0.2.0
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
  const cleanups = [];
  let destroyed = false;
  let moving = 0;
  let timer = 0;
  let menu;

  const enabled = () => !destroyed &&
    Services.prefs.getBoolPref(PREFIX + "enabled", true);
  const allTabs = () => [...gZenWorkspaces.allStoredTabs].filter(t => t.isConnected && !t.closing);
  const isSplit = item => !!item?.hasAttribute("split-view-group");
  const itemOf = tab => isSplit(tab?.group) ? tab.group : tab;
  const members = item => isSplit(item) ? [...item.tabs].filter(t => t.isConnected && !t.closing) : [item];
  const allItems = () => [...new Set(allTabs().map(itemOf))];
  const selectedTab = item => members(item).find(t => t.selected) || members(item)[0];
  const workspace = item => members(item)[0]?.getAttribute("zen-workspace-id") || "";
  const usableTab = tab => !!tab?.isConnected && !tab.closing &&
    gBrowser.isTab(tab) && !tab.pinned && !tab.splitview &&
    !["zen-essential", "zen-glance-tab", "zen-empty-tab",
      "zen-live-folder-item-id"].some(attribute => tab.hasAttribute(attribute));
  const eligible = input => {
    const item = itemOf(input);
    if (isSplit(item)) {
      const tabs = members(item);
      return item.isConnected && !item.group && tabs.length >= 2 &&
        tabs.every(tab => usableTab(tab) && workspace(tab) === workspace(tabs[0]));
    }
    return usableTab(item) && !item.group && !item.hasAttribute("split-view");
  };
  const report = error => {
    api.lastError = String(error);
    console.error("[Tree Tabs]", error);
  };

  function read(item) {
    for (const tab of members(item)) {
      try {
        const value = JSON.parse(SessionStore.getCustomTabValue(tab, STORAGE) || "null");
        // A pane copied out of a split must not steal the split's identity.
        const matches = isSplit(item) ? value?.split === item.id : !value?.split;
        if (matches && value?.v === 1 && typeof value.id === "string" && value.id.length < 100) {
          return {
            id: value.id,
            parentId: typeof value.parent === "string" ? value.parent : "",
            collapsed: value.collapsed === true,
            persisted: true,
          };
        }
      } catch {}
    }
    return null;
  }

  function ensure(tab, restoring = false) {
    tab = itemOf(tab);
    let node = nodes.get(tab);
    const saved = !node || restoring ? read(tab) : null;
    if (!node) {
      node = {
        tab, id: Services.uuid.generateUUID().toString(),
        parentId: "", collapsed: false, parent: null, children: [],
        members: members(tab), persisted: false,
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
      ...(isSplit(node.tab) ? { split: node.tab.id } : {}),
    });
    // Save on every pane so closing one pane cannot discard the tree.
    for (const tab of members(node.tab)) {
      if (SessionStore.getCustomTabValue(tab, STORAGE) !== value) {
        SessionStore.setCustomTabValue(tab, STORAGE, value);
      }
    }
    node.persisted = true;
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

  // Native pinning, ordinary grouping and moving win. Split groups themselves
  // are tree items, so their panes are never moved separately by this mod.
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
        const content = isSplit(tab) ? tab : tab.querySelector(".tab-content");
        if (!content) continue;
        button = document.createElementNS("http://www.w3.org/1999/xhtml", "button");
        button.className = "uc-tree-twisty";
        if (isSplit(tab)) button.classList.add("uc-tree-split-twisty");
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
        // Zen overrides group.appendChild to insert into the pane container.
        if (isSplit(tab)) Node.prototype.appendChild.call(content, button);
        else content.prepend(button);
      }
      button.textContent = node.collapsed ? "▸" : "▾";
      button.setAttribute("aria-expanded", String(!node.collapsed));
      button.setAttribute("aria-label", `${node.collapsed ? "Expand" : "Collapse"} child tabs`);
      button.title = `${node.collapsed ? "Expand" : "Collapse"} ${descendants(node).length} child tabs`;
    }
  }

  function syncItems(items) {
    const live = new Set(items);
    const tabs = new Set(allTabs());
    const changed = new Set();

    // A dissolved split hands its role to its first surviving pane. Other
    // surviving panes become peers. No pane is closed, cloned or reloaded.
    for (const [item, node] of [...nodes]) {
      if (!isSplit(item) || live.has(item)) continue;
      const survivors = node.members.filter(tab => tabs.has(tab));
      const replacement = survivors.map(itemOf).find(eligible);
      clearUI(item);
      nodes.delete(item);
      if (!replacement) {
        release(node, true);
        continue;
      }
      const existing = nodes.get(replacement);
      if (existing) {
        for (const child of nodes.values()) {
          if (child.parentId === node.id) {
            child.parentId = existing.id;
            save(child);
          }
        }
      } else {
        node.tab = replacement;
        node.members = members(replacement);
        nodes.set(replacement, node);
        save(node);
      }
      changed.add(nodes.get(replacement));
      for (const tab of survivors) {
        if (itemOf(tab) !== tab || tab === replacement) continue;
        const peer = ensure(tab);
        peer.parentId = node.parentId;
        save(peer);
      }
    }

    // When tabs join a split, transfer their tree roles to the one group.
    // Prefer an existing ancestor's position if parent and child are split
    // together. This prevents a self-parent and keeps their children attached.
    for (const item of items) {
      if (!isSplit(item)) continue;
      const old = nodes.get(item);
      const candidates = members(item).map(tab => nodes.get(tab)).filter(Boolean);
      const node = ensure(item);
      if (candidates.length) {
        const ids = new Set(candidates.map(candidate => candidate.id));
        if (!old && !node.persisted) {
          const lead = candidates.find(candidate =>
            !ids.has(candidate.parentId) &&
            (candidate.parentId || candidate.children.length || candidate.collapsed)) ||
            candidates.find(candidate => !ids.has(candidate.parentId)) || candidates[0];
          node.id = lead.id;
          node.parentId = lead.parentId;
          node.collapsed = lead.collapsed;
        }
        const seen = new Set();
        while (ids.has(node.parentId) && !seen.has(node.parentId)) {
          seen.add(node.parentId);
          node.parentId = candidates.find(candidate => candidate.id === node.parentId)?.parentId || "";
        }
        if (seen.has(node.parentId)) node.parentId = "";
        for (const candidate of candidates) {
          clearUI(candidate.tab);
          nodes.delete(candidate.tab);
          for (const child of nodes.values()) {
            if (child !== node && child.parentId === candidate.id) {
              child.parentId = node.id;
              save(child);
            }
          }
        }
        save(node);
        changed.add(node);
      }
      const next = members(item);
      if (node.persisted && (next.length !== node.members.length ||
          next.some((tab, index) => tab !== node.members[index]))) save(node);
      node.members = next;
    }
    for (const [item] of nodes) {
      if (!live.has(item)) {
        clearUI(item);
        nodes.delete(item);
      }
    }
    return changed;
  }

  function keepBranchTogether(node) {
    if (!eligible(node.tab)) return;
    while (node.parent) node = node.parent;
    const branch = descendants(node);
    if (!branch.length) return;
    const items = allItems();
    const start = items.indexOf(node.tab) + 1;
    if (branch.every((child, index) => items[start + index] === child.tab)) return;
    moving++;
    try { gBrowser.moveTabsAfter(branch.map(child => child.tab), node.tab); }
    finally { moving--; }
  }

  function reconcile() {
    const started = performance.now();
    const tabs = allItems();
    const changed = syncItems(tabs);
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
    if (enabled()) for (const node of changed) keepBranchTogether(node);
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
    tab = itemOf(tab);
    parentTab = itemOf(parentTab);
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
    if (!enabled()) return false;
    tab = itemOf(tab);
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
    if (!enabled()) return;
    tab = itemOf(tab);
    const node = nodes.get(tab);
    if (!node?.children.length) return;
    const collapse = !node.collapsed;
    if (collapse && descendants(node).some(n => n.tab === itemOf(gBrowser.selectedTab))) {
      gBrowser.selectedTab = selectedTab(tab);
    }
    node.collapsed = collapse;
    save(node);
    render();
  }

  function revealSelected(update = true) {
    if (!enabled()) return;
    const node = nodes.get(itemOf(gBrowser.selectedTab));
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
    const context = () => itemOf(window.TabContextMenu?.contextTab);
    const previous = tab => {
      const tabs = allItems();
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
    style.href = "chrome://sine/content/tree-tabs-prototype/tree-tabs.css?v=0.2.0";
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
      const item = itemOf(event.target);
      // Split membership settles after TabClose; the remaining pane(s) must
      // retain the session's identity and children.
      if (!isSplit(item)) {
        const node = nodes.get(event.target);
        release(node, true);
        nodes.delete(event.target);
      }
      pendingParents.delete(event.target);
      schedule();
    });
    listen(window, "TabMove", event => {
      const detail = event.detail;
      const changingGroup = detail?.previousTabState?.tabGroupId !== detail?.currentTabState?.tabGroupId;
      const wasSplit = [...nodes.values()].some(node =>
        isSplit(node.tab) && node.members.includes(event.target));
      if (!moving && enabled() && !changingGroup && !wasSplit && !isSplit(itemOf(event.target))) {
        release(nodes.get(event.target));
      }
      if (!moving) schedule();
    });
    listen(window, "TabGroupMoved", event => {
      if (!moving && enabled() && isSplit(event.target)) release(nodes.get(event.target));
      if (!moving) schedule();
    });
    listen(window, "TabSelect", () => revealSelected());
    for (const type of ["TabPinned", "TabUnpinned", "TabGrouped", "TabUngrouped",
      "ZenSplitViewTabsSplit", "ZenTabRemovedFromSplit", "TabGroupRemoved",
      "FolderGrouped", "FolderUngrouped", "SSWindowStateReady"]) {
      listen(window, type, () => schedule());
    }
    listen(window, "SSTabRestored", event => {
      ensure(event.target, true);
      pendingParents.delete(event.target);
      schedule();
    });
    const observer = new MutationObserver(() => schedule());
    observer.observe(gBrowser.tabContainer, {
      subtree: true, attributes: true,
      attributeFilter: ["zen-workspace-id", "zen-glance-tab", "split-view",
        "split-view-group", "zen-essential", "pinned"],
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
    if (window.TreeTabs === api) delete window.TreeTabs;
  }

  const api = window.TreeTabs = {
    version: "0.2.0", status: "starting", reconciliations: 0, lastReconcileMs: 0,
    nest, outdent, toggleCollapse, expandAll, destroy,
    itemOf,
    parentOf: tab => nodes.get(itemOf(tab))?.parent?.tab || null,
    depthOf: tab => depth(nodes.get(itemOf(tab))),
    snapshot: () => [...nodes.values()].filter(n => eligible(n.tab)).map(n => ({
      tab: n.tab.id, id: n.id, parent: n.parent?.id || "", collapsed: n.collapsed,
      depth: depth(n), hidden: n.tab.hasAttribute("uc-tree-hidden"),
      children: n.children.length, workspace: workspace(n.tab),
      kind: isSplit(n.tab) ? "split" : "tab",
      members: members(n.tab).map(tab => tab.id),
    })),
  };
  window.addUnloadListener?.(destroy);
  listen(window, "unload", destroy, { once: true });
  install().catch(error => {
    api.status = "error";
    report(error);
  });
})();
