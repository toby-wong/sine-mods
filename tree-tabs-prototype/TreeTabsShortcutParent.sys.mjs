const owners = new Set();

export function registerShortcutActors(window) {
  if (!owners.size) {
    ChromeUtils.registerWindowActor("TreeTabsShortcut", {
      allFrames: true,
      safeForUntrustedWebProcess: true,
      parent: {
        esModuleURI: "chrome://sine/content/tree-tabs-prototype/TreeTabsShortcutParent.sys.mjs",
      },
      child: {
        esModuleURI: "chrome://sine/content/tree-tabs-prototype/TreeTabsShortcutChild.sys.mjs",
        events: {
          pageshow: {},
          keydown: {mozSystemGroup: true},
        },
      },
    });
  }
  owners.add(window);
  return () => {
    if (owners.delete(window) && !owners.size) {
      ChromeUtils.unregisterWindowActor("TreeTabsShortcut");
    }
  };
}

export class TreeTabsShortcutParent extends JSWindowActorParent {
  actorCreated() {
    this.updateContext();
  }

  context() {
    const browser = this.browsingContext.top.embedderElement;
    const window = [...owners].find(owner => owner.document === browser?.ownerDocument);
    return {browser, tree: window?.TreeTabs};
  }

  updateContext() {
    const {browser, tree} = this.context();
    this.sendAsyncMessage("TreeTabs:Context", {
      enabled: tree?.canHandleShortcut(browser) === true,
    });
  }

  receiveMessage(message) {
    if (this.manager !== this.browsingContext.currentWindowGlobal) return;
    if (message.name === "TreeTabs:GetContext") {
      this.updateContext();
    } else if (message.name === "TreeTabs:Key") {
      const {browser, tree} = this.context();
      tree?.handleShortcut(message.data.action, browser);
    }
  }
}
