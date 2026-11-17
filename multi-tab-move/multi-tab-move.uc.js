// ==UserScript==
// @name           Multi Tab Move
// @version        0.1.1
// @description    Shift-click individual tabs and move trees and split sessions together.
// @include        chrome://browser/content/browser.xhtml
// ==/UserScript==

(() => {
  "use strict";
  window.MultiTabMove?.destroy();

  const PREF = "uc.multi-tab-move.enabled";
  const explicit = new Set();
  const marked = new Set();
  const cleanups = [];
  const excluded = "[zen-essential], [zen-glance-tab], [zen-empty-tab], [zen-live-folder-item-id]";
  const controls = [
    ".tab-close-button", ".tab-reset-button", ".tab-reset-pin-button",
    ".tab-icon-overlay", ".tab-audio-button", ".uc-tree-twisty",
    ".tab-group-collapse-button", "input", "textbox", "menupopup",
  ].join(", ");
  let destroyed = false;
  let timer = 0;
  let drag = null;
  let pressed = null;
  let suppressClick = null;
  let pendingAction = false;
  let menu, indicator, ghost;

  const active = () => !destroyed && Services.prefs.getBoolPref(PREF, true);
  const alive = item => item?.isConnected && item.ownerDocument === document && !item.closing;
  const storedTabs = () => [...gZenWorkspaces.allStoredTabs].filter(alive);
  const isTab = item => gBrowser.isTab(item);
  const tabsOf = item => isTab(item) ? [item] : [...(item?.tabs || [])].filter(alive);
  const spaceOf = item => item?.getAttribute("zen-workspace-id") ||
    tabsOf(item)[0]?.getAttribute("zen-workspace-id") || "";
  const order = (a, b) => a === b ? 0 :
    a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
  const stop = event => { event.preventDefault(); event.stopImmediatePropagation(); };

  function unitOf(item) {
    if (!item) return null;
    if (isTab(item)) {
      return item.group?.hasAttribute("split-view-group") ? item.group : item.splitview || item;
    }
    return gBrowser.isTabGroup(item) || gBrowser.isSplitViewWrapper(item) ? item : null;
  }

  function eligible(item) {
    return alive(item) && !!unitOf(item) && !item.matches(excluded) &&
      tabsOf(item).some(tab => !tab.matches(excluded)) &&
      !tabsOf(item).some(tab => tab.hasAttribute("zen-essential") ||
        tab.hasAttribute("zen-live-folder-item-id"));
  }

  function eventUnit(event) {
    const target = event.target?.nodeType === Node.TEXT_NODE ?
      event.target.parentElement : event.target;
    if (target?.ownerDocument !== document || !target.closest ||
        !gBrowser.tabContainer.contains(target) || target.closest(controls)) return null;
    const tab = target.closest(".tabbrowser-tab");
    const item = unitOf(tab || target.closest("tab-group, zen-folder, tab-split-view-wrapper"));
    return eligible(item) ? item : null;
  }

  function plan() {
    const chosen = [...explicit].filter(eligible);
    const units = new Set(chosen);
    const tree = window.TreeTabs;
    // Follow only the live Tree Tabs API. Saved-but-disabled tree metadata
    // must not silently change what a flat sidebar selection moves.
    if (tree?.status === "ready" &&
        Services.prefs.getBoolPref("uc.tree-tabs.enabled", true)) {
      for (const tab of storedTabs()) {
        const seen = new Set();
        for (let parent = tree.parentOf(tab); parent && !seen.has(parent);
             parent = tree.parentOf(parent)) {
          seen.add(parent);
          if (units.has(parent)) {
            units.add(unitOf(tab));
            break;
          }
        }
      }
    }
    // A selected native folder/group already carries its descendants.
    const roots = [...units].filter(item => eligible(item) &&
      ![...units].some(other => other !== item && other.contains(item))).sort(order);
    const tabs = [...new Set(roots.flatMap(tabsOf))].sort(order);
    return { units: roots, tabs, chosen };
  }

  function render() {
    for (const item of marked) {
      item.removeAttribute("uc-multi-tab-selected");
      item.removeAttribute("uc-multi-tab-carried");
    }
    marked.clear();
    for (const item of explicit) if (!eligible(item)) explicit.delete(item);
    if (!active()) return;
    const selection = plan();
    for (const item of [...selection.units, ...selection.tabs]) {
      const selected = explicit.has(item) || explicit.has(unitOf(item));
      item.setAttribute(selected ? "uc-multi-tab-selected" : "uc-multi-tab-carried", "true");
      marked.add(item);
    }
  }

  function schedule() {
    if (timer || destroyed) return;
    timer = window.setTimeout(() => {
      timer = 0;
      render();
    }, 0);
  }

  function clear() {
    explicit.clear();
    pressed = null;
    render();
  }

  function toggle(item) {
    item = unitOf(item);
    if (!active() || !eligible(item)) return false;
    const first = [...explicit].find(eligible);
    if (first && spaceOf(first) !== spaceOf(item)) explicit.clear();
    if (explicit.has(item)) explicit.delete(item);
    else explicit.add(item);
    render();
    return true;
  }

  function selected(item) {
    return plan().units.some(unit => unit === item || unit.contains(item));
  }

  function requireTreeReady() {
    const tree = window.TreeTabs;
    if (tree && Services.prefs.getBoolPref("uc.tree-tabs.enabled", true)) {
      if (tree.status !== "ready")
        throw new Error("Tree Tabs must finish loading before acting on this selection.");
      if (!tree.moveBranches)
        throw new Error("Update Tree Tabs Prototype to 0.1.4 or later before acting on this selection.");
    }
  }

  function sameSelection(selection) {
    if (!active()) return false;
    const current = plan();
    return ["chosen", "units", "tabs"].every(key =>
      current[key].length === selection[key].length &&
      current[key].every((item, index) => item === selection[key][index])) &&
      current.units.every(item => spaceOf(item) === selection.space);
  }

  function onMouseDown(event) {
    if (!active() || !event.isTrusted || event.button !== 0 ||
        event.ctrlKey || event.metaKey || event.altKey) return;
    const item = eventUnit(event);
    if (!item) return;
    if (event.shiftKey) {
      toggle(item);
      pressed = { item, shift: true, x: event.clientX, y: event.clientY };
      // Leave the platform's drag gesture enabled, while preventing the
      // tab element's native Shift range-selection handler from running.
      event.stopImmediatePropagation();
    } else if (explicit.size && selected(item)) {
      pressed = { item, shift: false, x: event.clientX, y: event.clientY };
      event.stopImmediatePropagation();
    } else {
      clear();
    }
  }

  function onClick(event) {
    if (!active() || !event.isTrusted || event.button !== 0) return;
    if (suppressClick) {
      const last = suppressClick;
      suppressClick = null;
      if (event.timeStamp - last.time < 100 &&
          event.clientX === last.x && event.clientY === last.y) {
        stop(event);
        return;
      }
    }
    const item = eventUnit(event);
    if (!item) return;
    if (pressed?.item === item && !drag) {
      const wasShift = pressed.shift;
      pressed = null;
      stop(event);
      if (!wasShift && !event.shiftKey) {
        clear();
        const tab = isTab(item) ? item :
          tabsOf(item).find(tab => tab === gBrowser.selectedTab) ||
          tabsOf(item).find(tab => !tab.matches(excluded));
        if (tab) gBrowser.selectedTab = tab;
      }
    } else if (event.shiftKey && !event.altKey && !event.ctrlKey && !event.metaKey) {
      stop(event);
    }
  }

  function rootAnchor(item, before) {
    item = unitOf(item);
    while (item?.group) item = item.group;
    const tree = window.TreeTabs;
    if (isTab(item) && tree && Services.prefs.getBoolPref("uc.tree-tabs.enabled", true)) {
      const seen = new Set();
      while (tree.parentOf(item) && !seen.has(item)) {
        seen.add(item);
        item = tree.parentOf(item);
      }
      if (!before) {
        const root = item;
        for (const candidate of storedTabs()) {
          const parents = new Set();
          for (let parent = tree.parentOf(candidate); parent && !parents.has(parent);
               parent = tree.parentOf(parent)) {
            parents.add(parent);
            if (parent === root) { item = candidate; break; }
          }
        }
      }
    }
    return item;
  }

  function destination(event) {
    const target = event.target?.nodeType === Node.TEXT_NODE ?
      event.target.parentElement : event.target;
    if (target?.ownerDocument !== document || !target.closest) return null;
    const icon = target.closest("[zen-workspace-id]");
    if (icon && gZenWorkspaces.workspaceIcons?.contains(icon)) {
      return { workspace: icon.getAttribute("zen-workspace-id"), icon };
    }
    const item = eventUnit(event);
    if (item) {
      const row = isTab(item) ? item : item.labelContainerElement || item;
      const rect = row.getBoundingClientRect();
      const before = event.clientY < rect.y + rect.height / 2;
      const anchor = rootAnchor(item, before);
      return { workspace: spaceOf(anchor), anchor, before, row };
    }
    const section = target.closest(
      ".zen-workspace-normal-tabs-section, .zen-workspace-pinned-tabs-section");
    if (section) {
      return {
        workspace: section.closest("zen-workspace")?.id || gZenWorkspaces.activeWorkspace,
        pinned: section.classList.contains("zen-workspace-pinned-tabs-section"), section,
      };
    }
    return null;
  }

  function validDrop(selection, target) {
    if (!selection.units.length || !target?.workspace ||
        !gZenWorkspaces.workspaceElement(target.workspace)) return false;
    if (target.anchor && (!alive(target.anchor) ||
        selection.units.some(item => item === target.anchor || item.contains(target.anchor))))
      return false;
    if (!target.icon && (target.anchor || target.section)) {
      const pinned = target.anchor ? !!target.anchor.pinned : target.pinned;
      if (selection.units.some(item => !!item.pinned !== pinned)) return false;
    }
    return true;
  }

  function finishDrag() {
    drag = null;
    pressed = null;
    indicator?.setAttribute("hidden", "true");
    ghost?.setAttribute("hidden", "true");
    document.documentElement.removeAttribute("uc-multi-tab-dragging");
  }

  function onDragStart(event) {
    if (!active() || !event.isTrusted) return;
    const item = eventUnit(event);
    if (!item || !explicit.size || !selected(item)) return;
    // Keep native drag packing, split-on-hover and cross-window adoption
    // out of this gesture. Actual movement happens only on our mouseup.
    stop(event);
    startDrag();
  }

  function showIndicator(target) {
    if (target.icon) {
      const rect = target.icon.getBoundingClientRect();
      indicator.style.cssText = `left:${rect.left}px;top:${rect.bottom - 2}px;width:${rect.width}px`;
    } else {
      const row = target.row || target.section;
      const rect = row.getBoundingClientRect();
      indicator.style.cssText = `left:${rect.left + 4}px;top:${
        target.before ? rect.top : rect.bottom - 2}px;width:${Math.max(0, rect.width - 8)}px`;
    }
    indicator.removeAttribute("hidden");
  }

  function startDrag() {
    if (drag || !pressed || !selected(pressed.item)) return;
    const selection = plan();
    if (!selection.units.length) return;
    drag = { source: pressed.item };
    ghost.textContent = `${selection.tabs.filter(tab => !tab.matches(excluded)).length} tabs`;
    ghost.removeAttribute("hidden");
    document.documentElement.setAttribute("uc-multi-tab-dragging", "true");
  }

  function atPointer(event) {
    return destination({
      target: document.elementFromPoint(event.clientX, event.clientY),
      clientY: event.clientY,
    });
  }

  function onMouseMove(event) {
    if (!active() || !event.isTrusted || !pressed) return;
    if (!(event.buttons & 1)) { finishDrag(); return; }
    if (!drag && Math.hypot(event.clientX - pressed.x, event.clientY - pressed.y) < 6) return;
    startDrag();
    if (!drag) return;
    stop(event);
    ghost.style.left = `${event.clientX + 16}px`;
    ghost.style.top = `${event.clientY + 12}px`;
    const target = atPointer(event);
    if (validDrop(plan(), target)) showIndicator(target);
    else indicator.setAttribute("hidden", "true");
  }

  function move(target) {
    const selection = plan();
    if (!active() || !validDrop(selection, target)) return false;
    const { units, tabs } = selection;
    const tree = window.TreeTabs;
    requireTreeReady();
    const original = units.map(item => ({
      item, parent: item.parentNode, next: item.nextSibling,
    }));
    const spaceAttributes = new Map();
    for (const item of units) {
      for (const node of [item, ...tabsOf(item),
        ...item.querySelectorAll("tab-group, zen-folder")]) {
        spaceAttributes.set(node, node.getAttribute("zen-workspace-id"));
      }
    }
    const apply = () => {
      try {
        const workspace = gZenWorkspaces.workspaceElement(target.workspace);
        const changedSpace = units.some(item => spaceOf(item) !== target.workspace);
        if (changedSpace || !target.anchor) {
          for (const item of units) {
            const container = item.pinned ? workspace.pinnedTabsContainer : workspace.tabsContainer;
            gBrowser.zenHandleTabMove(item, () => {
              for (const node of [item, ...tabsOf(item),
                ...item.querySelectorAll("tab-group, zen-folder")]) {
                node.setAttribute("zen-workspace-id", target.workspace);
              }
              container.insertBefore(item, container.querySelector(
                ":scope > #tabbrowser-arrowscrollbox-periphery, :scope > .pinned-tabs-container-separator"));
            });
          }
        }
        if (target.anchor) {
          const method = target.before ? "moveTabsBefore" : "moveTabsAfter";
          gBrowser[method](units, target.anchor);
        }
        gZenWorkspaces.updateTabsContainers();
        return true;
      } catch (error) {
        // The wrappers and browsers themselves are the rollback data.
        // Never recreate a tab or rebuild a split from its URL.
        for (const { item, parent, next } of original.reverse()) {
          if (alive(item) && parent.isConnected) {
            gBrowser.zenHandleTabMove(item, () =>
              parent.insertBefore(item, next?.parentNode === parent ? next : null));
          }
        }
        for (const [node, value] of spaceAttributes) {
          if (value === null) node.removeAttribute("zen-workspace-id");
          else node.setAttribute("zen-workspace-id", value);
        }
        gZenWorkspaces.updateTabsContainers();
        throw error;
      }
    };
    const result = tree?.moveBranches ? tree.moveBranches(tabs, apply) : apply();
    for (const [space, tab] of Object.entries(gZenWorkspaces.lastSelectedWorkspaceTabs)) {
      if (tabs.includes(tab) && space !== target.workspace)
        delete gZenWorkspaces.lastSelectedWorkspaceTabs[space];
    }
    render();
    return result;
  }

  async function moveToSpace(workspace) {
    const selection = plan();
    const focused = gBrowser.selectedTab;
    if (!move({ workspace })) return false;
    gZenWorkspaces.lastSelectedWorkspaceTabs[workspace] =
      selection.tabs.includes(focused) ? focused :
        selection.tabs.find(tab => !tab.matches(excluded));
    await gZenWorkspaces.changeWorkspaceWithID(workspace);
    if (!destroyed) render();
    return true;
  }

  async function closeSelection() {
    if (!active() || pendingAction) return false;
    requireTreeReady();
    const selection = plan();
    const tabs = selection.tabs.filter(tab => !tab.matches(excluded));
    if (!tabs.length) return false;
    selection.space = spaceOf(selection.units[0]);
    pendingAction = true;
    finishDrag();
    try {
      // Preflight the entire set so cancellation cannot leave a partial
      // branch or split behind. Native removal still records Undo Close.
      if (await gBrowser.runBeforeUnloadForTabs(tabs) || !sameSelection(selection))
        return false;
      requireTreeReady();
      gBrowser.removeTabs(tabs, {
        animate: true,
        skipPermitUnload: true,
        closeWindowWithLastTab: false,
        metricsContext: gBrowser.TabMetrics.userTriggeredContext(
          gBrowser.TabMetrics.METRIC_SOURCE.TAB_MENU),
      });
      return tabs.every(tab => !alive(tab));
    } finally {
      pendingAction = false;
      if (!destroyed) render();
    }
  }

  async function createSpaceFromSelection() {
    if (!active() || pendingAction || !gZenWorkspaces.workspaceEnabled) return false;
    requireTreeReady();
    const selection = plan();
    if (!selection.tabs.length) return false;
    selection.space = spaceOf(selection.units[0]);
    pendingAction = true;
    finishDrag();
    let created, committed = false;
    try {
      const name = { value: "" };
      if (!Services.prompt.prompt(window, "New Space",
          "Name the new Space for the selected tabs:", name, null, {}) ||
          !name.value.trim() || !sameSelection(selection)) return false;
      const source = gZenWorkspaces.getWorkspaceFromId(selection.space);
      // Creating an inactive Space avoids switching focus or moving unrelated
      // tabs before the existing move transaction can run.
      created = await gZenWorkspaces.createAndSaveWorkspace(
        name.value.trim(), undefined, true, source?.containerTabId || 0,
        { insertAfterId: selection.space });
      if (!created || !sameSelection(selection)) return false;
      const focused = gBrowser.selectedTab;
      committed = move({ workspace: created.uuid });
      if (!committed) return false;
      gZenWorkspaces.lastSelectedWorkspaceTabs[created.uuid] =
        selection.tabs.includes(focused) ? focused :
          selection.tabs.find(tab => !tab.matches(excluded));
      await gZenWorkspaces.changeWorkspaceWithID(created.uuid);
      if (!destroyed) render();
      return true;
    } finally {
      try {
        // Remove only our unused Space after a failed/cancelled move. A Space
        // that acquired tabs or folders belongs to the user and must remain.
        const element = !destroyed && created &&
          gZenWorkspaces.workspaceElement(created.uuid);
        if (!destroyed && !committed && element &&
            !storedTabs().some(tab => spaceOf(tab) === created.uuid &&
              !tab.hasAttribute("zen-empty-tab")) &&
            !element.querySelector("tab-group, zen-folder, tab-split-view-wrapper")) {
          await gZenWorkspaces.removeWorkspace(created.uuid);
        }
      } finally {
        pendingAction = false;
      }
    }
  }

  function report(error) {
    api.lastError = String(error);
    console.error("[Multi Tab Move]", error);
  }

  function onMouseUp(event) {
    if (!drag || !event.isTrusted || event.button !== 0) return;
    stop(event);
    const target = atPointer(event);
    suppressClick = { time: event.timeStamp, x: event.clientX, y: event.clientY };
    finishDrag();
    try {
      if (target?.icon) moveToSpace(target.workspace).catch(report);
      else move(target);
    } catch (error) { report(error); }
  }

  function onContextMenu(event) {
    if (!active() || !event.isTrusted || !explicit.size) return;
    const item = eventUnit(event);
    if (!item || !selected(item)) return;
    stop(event);
    menu.replaceChildren();
    const heading = document.createXULElement("menuitem");
    heading.setAttribute("label", `Move ${plan().tabs.filter(tab => !tab.matches(excluded)).length} tabs to Space`);
    heading.setAttribute("disabled", "true");
    menu.append(heading, document.createXULElement("menuseparator"));
    const create = document.createXULElement("menuitem");
    create.id = "uc-multi-tab-new-space";
    create.setAttribute("label", "New Space with selected tabs…");
    create.disabled = pendingAction || !gZenWorkspaces.workspaceEnabled;
    create.addEventListener("command", () => createSpaceFromSelection().catch(report));
    menu.append(create, document.createXULElement("menuseparator"));
    for (const space of gZenWorkspaces.getWorkspaces()) {
      const entry = document.createXULElement("menuitem");
      entry.setAttribute("label", space.name);
      entry.setAttribute("data-workspace-id", space.uuid);
      entry.disabled = space.uuid === spaceOf(item);
      entry.addEventListener("command", () => moveToSpace(space.uuid).catch(report));
      menu.append(entry);
    }
    menu.append(document.createXULElement("menuseparator"));
    const close = document.createXULElement("menuitem");
    close.id = "uc-multi-tab-close";
    close.setAttribute("label",
      `Close selected tabs (${plan().tabs.filter(tab => !tab.matches(excluded)).length})`);
    close.disabled = pendingAction;
    close.addEventListener("command", () => closeSelection().catch(report));
    menu.append(close);
    const reset = document.createXULElement("menuitem");
    reset.setAttribute("label", "Clear tab selection");
    reset.addEventListener("command", clear);
    menu.append(reset);
    menu.openPopupAtScreen(event.screenX, event.screenY, true);
  }

  function listen(target, type, listener, options = false) {
    target.addEventListener(type, listener, options);
    cleanups.push(() => target.removeEventListener(type, listener, options));
  }

  async function install() {
    await gZenStartup.promiseInitialized;
    if (destroyed) return;
    if (PrivateBrowsingUtils.isWindowPrivate(window) || window._littleZenInfo) {
      api.status = "outside-prototype-scope";
      return;
    }
    const link = document.createElementNS("http://www.w3.org/1999/xhtml", "link");
    link.rel = "stylesheet";
    link.href = "chrome://sine/content/multi-tab-move/multi-tab-move.css?v=0.1.1";
    document.documentElement.append(link);
    cleanups.push(() => link.remove());
    for (const id of ["uc-multi-tab-indicator", "uc-multi-tab-ghost"]) {
      const element = document.createElementNS("http://www.w3.org/1999/xhtml", "div");
      element.id = id;
      element.setAttribute("hidden", "true");
      element.setAttribute("aria-hidden", "true");
      document.documentElement.append(element);
      cleanups.push(() => element.remove());
      if (id.endsWith("indicator")) indicator = element;
      else ghost = element;
    }
    menu = document.createXULElement("menupopup");
    menu.id = "uc-multi-tab-menu";
    document.getElementById("mainPopupSet").append(menu);
    cleanups.push(() => { menu.hidePopup(); menu.remove(); });
    for (const [type, callback] of Object.entries({
      mousedown: onMouseDown, click: onClick, dragstart: onDragStart,
      mousemove: onMouseMove, mouseup: onMouseUp, contextmenu: onContextMenu,
    })) listen(window, type, callback, true);
    listen(window, "mouseout", event => {
      if (drag && !event.relatedTarget) finishDrag();
    }, true);
    listen(window, "blur", event => {
      if (event.target?.document === document) finishDrag();
    });
    listen(window, "keydown", event => {
      if (event.isTrusted && event.key === "Escape" && (explicit.size || drag) &&
          !event.altKey && !event.ctrlKey && !event.metaKey && !event.shiftKey) {
        // Ordinary page Escape handling remains available.
        finishDrag();
        clear();
      }
    }, true);
    for (const type of ["TabClose", "TabMove", "TabPinned", "TabUnpinned", "TabGrouped",
      "TabUngrouped", "ZenSplitViewTabsSplit", "TabGroupRemoved", "SSWindowStateReady"]) {
      listen(window, type, () => { if (explicit.size || marked.size) schedule(); });
    }
    const observer = { observe: () => { finishDrag(); clear(); } };
    Services.prefs.addObserver(PREF, observer);
    cleanups.push(() => Services.prefs.removeObserver(PREF, observer));
    api.status = "ready";
  }

  function destroy() {
    if (destroyed) return;
    destroyed = true;
    window.clearTimeout(timer);
    finishDrag();
    clear();
    for (const undo of cleanups.splice(0).reverse()) {
      try { undo(); } catch (error) { report(error); }
    }
    if (window.MultiTabMove === api) delete window.MultiTabMove;
  }

  const api = window.MultiTabMove = {
    version: "0.1.1", status: "starting",
    toggle, clear, move, moveToSpace, closeSelection, createSpaceFromSelection, destroy,
    snapshot: () => {
      const selection = plan();
      return {
        explicit: selection.chosen.map(item => item.id),
        units: selection.units.map(item => item.id),
        tabs: selection.tabs.map(tab => tab.id),
        dragging: !!drag,
      };
    },
  };
  window.addUnloadListener?.(destroy);
  listen(window, "unload", destroy, { once: true });
  install().catch(error => { api.status = "error"; report(error); });
})();
