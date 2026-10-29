import { BrowserUtils } from "resource://gre/modules/BrowserUtils.sys.mjs";

// Command-click is an explicit request for a background tab. Capture it before
// a site's router or target=_blank handler, then use Firefox's normal loader.
export class AutoGlanceClickChild extends JSWindowActorChild {
  handleEvent(event) {
    if (!event.isTrusted || event.defaultPrevented || event.button !== 0 ||
        !event.metaKey || event.altKey || event.ctrlKey || event.shiftKey ||
        !Services.prefs.getBoolPref("uc.auto-glance.cmd-click-background", true)) {
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
    this.manager.getActor("ClickHandler").handleClickEvent(event);
    event.preventDefault();
    event.stopImmediatePropagation();
  }
}
