import { BrowserUtils } from "resource://gre/modules/BrowserUtils.sys.mjs";
import { E10SUtils } from "resource://gre/modules/E10SUtils.sys.mjs";

// Command-click is an explicit request for a background tab. Capture it before
// a site's router or target=_blank handler, then use Firefox's normal loader.
export class AutoGlanceClickChild extends JSWindowActorChild {
  handleEvent(event) {
    if (!event.isTrusted || event.button !== 0 ||
        !event.metaKey || event.altKey || event.ctrlKey || event.shiftKey ||
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
    // The native child's handleClickEvent deliberately ignores contenteditable
    // links. Send its normal message instead, preserving referrer and document
    // policy. The native parent supplies the frame's principals and container.
    const document = target.ownerDocument;
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
