export class TreeTabsShortcutChild extends JSWindowActorChild {
  enabled = false;

  receiveMessage(message) {
    if (message.name === "TreeTabs:Context") {
      this.enabled = message.data.enabled === true;
    }
  }

  handleEvent(event) {
    if (event.type === "pageshow") {
      this.sendAsyncMessage("TreeTabs:GetContext");
      return;
    }
    if (!this.enabled || !event.isTrusted || event.defaultPrevented ||
        event.isComposing || !event.altKey || !event.shiftKey ||
        event.ctrlKey || event.metaKey ||
        !["ArrowRight", "ArrowLeft"].includes(event.key)) return;

    const target = event.composedTarget;
    if (target?.ownerDocument?.designMode === "on" ||
        event.composedPath().some(element => element.isContentEditable ||
          element.matches?.("input, textarea, select, [role=textbox], [role=combobox]"))) return;

    // On macOS the page consumes Option+Shift+Arrow for selection even outside
    // editors. Handle the tree gesture before that default action runs.
    event.preventDefault();
    if (!event.repeat) {
      this.sendAsyncMessage("TreeTabs:Key", {
        action: event.key === "ArrowRight" ? "nest" : "outdent",
      });
    }
  }
}
