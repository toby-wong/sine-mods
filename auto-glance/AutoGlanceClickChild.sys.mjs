import { BrowserUtils } from "resource://gre/modules/BrowserUtils.sys.mjs";
import { E10SUtils } from "resource://gre/modules/E10SUtils.sys.mjs";
import { ZenGlanceChild } from "resource:///actors/ZenGlanceChild.sys.mjs";

const isMac = Services.appinfo.OS === "Darwin";

// Command-click on macOS and Ctrl-click elsewhere request a background tab.
// Capture before a site's router or target=_blank handler, then use Firefox's
// normal loader.
export class AutoGlanceClickChild extends JSWindowActorChild {
  actorCreated() {
    const prototype = ZenGlanceChild.prototype;
    if (typeof prototype.on_click !== "function") return;
    const key = "__autoGlanceBackgroundClickHook";
    let state = prototype[key];
    if (!state) {
      state = { original: prototype.on_click, actors: new Map() };
      state.wrapped = function (event) {
        const owner = state.actors.get(this.manager.innerWindowId);
        if (owner?.backgroundLink(event)) return;
        return state.original.call(this, event);
      };
      Object.defineProperty(prototype, key, { value: state, configurable: true });
      prototype.on_click = state.wrapped;
    }
    this.glanceHook = state;
    this.windowId = this.manager.innerWindowId;
    state.actors.set(this.windowId, this);
  }

  didDestroy() {
    const state = this.glanceHook;
    if (!state) return;
    if (state.actors.get(this.windowId) === this) state.actors.delete(this.windowId);
    const prototype = ZenGlanceChild.prototype;
    if (!state.actors.size && prototype.on_click === state.wrapped) {
      prototype.on_click = state.original;
      delete prototype.__autoGlanceBackgroundClickHook;
    }
    this.glanceHook = null;
  }

  backgroundLink(event) {
    if (!event.isTrusted || event.button !== 0 ||
        event.altKey || event.shiftKey ||
        !(isMac ? event.metaKey : event.ctrlKey) ||
        (isMac ? event.ctrlKey : event.metaKey) ||
        !Services.prefs.getBoolPref("uc.auto-glance.cmd-click-background", true)) {
      return;
    }
    const target = event.composedTarget;
    if (!target?.ownerDocument ||
        ["HTMLInputElement", "HTMLTextAreaElement"].includes(ChromeUtils.getClassName(target))) {
      return;
    }
    const [href, node, principal] = BrowserUtils.hrefAndLinkNodeForClickEvent(event);
    if (!node || !/^https?:\/\//i.test(href || "") || node.hasAttribute("download")) {
      return;
    }
    try {
      Services.scriptSecurityManager.checkLoadURIStrWithPrincipal(principal, href);
    } catch {
      return;
    }
    return { href, node, document: target.ownerDocument };
  }

  handleEvent(event) {
    // Mousedown/keydown create this actor before native Glance's click handler.
    // Native Glance can otherwise win listener order when its shortcut is Ctrl
    // on Windows. Its other gestures and click-position recording stay native.
    if (event.type !== "click") return;
    const link = this.backgroundLink(event);
    if (!link) return;
    const { href, node, document } = link;
    // The native child's handleClickEvent deliberately ignores contenteditable
    // links. Send its normal message instead, preserving referrer and document
    // policy. The native parent supplies the frame's principals and container.
    const referrer = Cc["@mozilla.org/referrer-info;1"].createInstance(Ci.nsIReferrerInfo);
    referrer.initWithElement(node);
    this.manager.getActor("ClickHandler").sendAsyncMessage("Content:Click", {
      button: event.button,
      shiftKey: event.shiftKey,
      ctrlKey: event.ctrlKey,
      metaKey: event.metaKey,
      altKey: event.altKey,
      href,
      title: node.getAttribute("title"),
      policyContainer: document.policyContainer
        ? E10SUtils.serializePolicyContainer(document.policyContainer) : null,
      referrerInfo: E10SUtils.serializeReferrerInfo(referrer),
    });
    event.preventMultipleActions();
    event.preventDefault();
    event.stopImmediatePropagation();
  }
}
