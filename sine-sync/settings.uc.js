// Sine Sync settings controls; use the browser's existing button/text styles.
(() => {
  const STATUS = "uc.sine-sync.status";
  const MODE = "uc.sine-sync.mode";
  const { controller } = ChromeUtils.importESModule("chrome://sine/content/sine-sync/SineSync.sys.mjs");
  window.SineSyncSettings?.destroy();
  let panel = null;
  const html = tag => document.createElementNS("http://www.w3.org/1999/xhtml", tag);
  function refresh() {
    if (!panel?.isConnected) return;
    panel.querySelector("p").textContent = Services.prefs.getStringPref(STATUS, "Choose a role to get started.");
    panel.querySelector("[data-claim]").hidden = Services.prefs.getStringPref(MODE, "off") !== "send";
  }
  function mount() {
    const anchor = document.getElementById("sine-sync-controls");
    if (!anchor || anchor.querySelector("[data-sync-controls]")) return;
    panel = html("div");
    panel.dataset.syncControls = "true";
    panel.style.cssText = "width:100%;margin-block:8px";
    const status = html("p");
    status.setAttribute("role", "status");
    status.style.cssText = "white-space:normal;overflow-wrap:anywhere;line-height:1.5";
    const button = html("button");
    button.textContent = "Sync now";
    const claim = html("button");
    claim.dataset.claim = "true";
    claim.textContent = "Use this computer as sender";
    const run = async claimSource => {
      button.disabled = claim.disabled = true;
      try { await controller.syncNow({ claim: claimSource }); }
      catch (error) { controller.setStatus(error.message); }
      finally { button.disabled = claim.disabled = false; }
    };
    button.addEventListener("click", () => run(false));
    claim.addEventListener("click", () => run(true));
    const note = html("p");
    note.textContent = "Use one sender per channel. Both computers need the same Mozilla account with Settings sync enabled. Restart the receiving browser after mod file changes.";
    note.style.cssText = "font-size:0.9em;opacity:0.8;white-space:normal;line-height:1.5";
    panel.append(status, button, claim, note);
    anchor.append(panel);
    refresh();
  }
  const observer = { observe: refresh };
  const dom = new MutationObserver(mount);
  dom.observe(document.documentElement, { childList: true, subtree: true });
  Services.prefs.addObserver(STATUS, observer);
  Services.prefs.addObserver(MODE, observer);
  function destroy() {
    dom.disconnect();
    Services.prefs.removeObserver(STATUS, observer);
    Services.prefs.removeObserver(MODE, observer);
    window.removeEventListener("unload", destroy);
    panel?.remove();
    if (window.SineSyncSettings?.destroy === destroy) delete window.SineSyncSettings;
  }
  window.SineSyncSettings = { destroy };
  window.addUnloadListener?.(destroy);
  window.addEventListener("unload", destroy, { once: true });
  mount();
})();
