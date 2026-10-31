// Capture the user's split gesture before a site's click/router handlers.
// Firefox's existing ClickHandler still constructs and validates the message.
import { BrowserUtils } from "resource://gre/modules/BrowserUtils.sys.mjs";

export class AltClickSplitViewChild extends JSWindowActorChild {
  handleEvent(event) {
    if (!event.isTrusted || event.button !== 0 ||
        !Services.prefs.getBoolPref("uc.alt-click-split-view.enabled", true)) {
      return;
    }
    const trigger = Services.prefs.getStringPref("uc.alt-click-split-view.trigger", "alt");
    const keys = { alt: "altKey", ctrl: "ctrlKey", shift: "shiftKey", meta: "metaKey" };
    if (!keys[trigger] || !event[keys[trigger]] ||
        Object.values(keys).some(key => key !== keys[trigger] && event[key])) {
      return;
    }
    if (Services.prefs.getBoolPref("zen.glance.enabled", true) &&
        Services.prefs.getStringPref("zen.glance.activation-method", "ctrl") === trigger) {
      return;
    }
    const target = event.composedTarget;
    if (target?.isContentEditable || target?.ownerDocument?.designMode === "on" ||
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
    if (event.defaultPrevented) {
      return;
    }
    this.manager.getActor("ClickHandler").handleClickEvent(event);
    event.preventDefault();
    event.stopImmediatePropagation();
  }
}
