"""Exercise stale snapshot recovery in a disposable Zen profile."""

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "little-zen/scripts"))
from runtime import Marionette


def run(args):
    m = Marionette(args.port)
    result = {"checks": [], "passed": False}
    fixture_created = False

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        result["checks"].append(name)
        print("PASS", name, flush=True)

    def state():
        return m.js("""
          const f=window.snapshotRecoveryTest,b=f.source.linkedBrowser;
          return {
            hidden:b.hasAttribute("zen-pseudo-hidden"),
            images:b.parentElement.querySelectorAll(".zen-pseudo-browser-image").length,
            context:b.browsingContext.id,
            document:b.browsingContext.currentWindowGlobal.innerWindowId,
            uri:b.currentURI.spec,
            tabIds:[...gZenWorkspaces.allStoredTabs].map(t=>t.id),
            splits:gZenViewSplitter.storeDataForSessionStore(),
            stats:window.WindowSyncRecovery?.stats
          };
        """)

    def settle():
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            current = state()
            if not current["hidden"] and current["images"] == 0:
                return current
            time.sleep(.1)
        raise AssertionError(f"Snapshot not cleared: {state()}")

    def poison(hidden=True, image=True):
        m.js("""
          const b=window.snapshotRecoveryTest.source.linkedBrowser;
          if(arguments[0])b.setAttribute("zen-pseudo-hidden","true");
          if(arguments[1]){
            const img=document.createElement("img");
            img.className="zen-pseudo-browser-image";
            img.src=URL.createObjectURL(new Blob(
              ['<svg xmlns="http://www.w3.org/2000/svg" width="2" height="2"/>'],
              {type:"image/svg+xml"}));
            b.after(img);
          }
        """, [hidden, image])

    def load():
        m.js("""
          Services.scriptloader.loadSubScriptWithOptions(
            "chrome://sine/content/window-sync-recovery/window-sync-recovery.uc.js",
            {target:window,ignoreCache:true});
        """)

    def unchanged(before, after):
        return all(before[key] == after[key] for key in
                   ("context", "document", "uri", "tabIds", "splits"))

    def content(script):
        m.command("Marionette:SetContext", {"value": "chrome"})
        m.command("WebDriver:SwitchToWindow", {"handle": m.command("WebDriver:GetWindowHandle")})
        m.command("Marionette:SetContext", {"value": "content"})
        try:
            return m.js(script)
        finally:
            m.command("Marionette:SetContext", {"value": "chrome"})

    try:
        actual = Path(m.js('return Services.dirsvc.get("ProfD",Ci.nsIFile).path'))
        if actual.resolve() != args.profile.resolve() or "test-profile" not in actual.name:
            raise RuntimeError("Use the explicitly selected disposable test-profile")
        m.async_js("""
          await gZenStartup.promiseInitialized;
          window.WindowSyncRecovery?.destroy();
          const original=gBrowser.selectedTab;
          const source=gBrowser.addTrustedTab(
            "data:text/html,<title>Snapshot recovery fixture</title><textarea id=draft>Initial</textarea>",
            {skipRoute:true});
          const sibling=gBrowser.addTrustedTab(
            "data:text/html,<title>Split sibling</title><p>Keep this page</p>",{skipRoute:true});
          const blank=gBrowser.addTrustedTab("about:blank",{skipRoute:true});
          window.snapshotRecoveryTest={original,source,sibling,blank};
          gBrowser.selectedTab=source;
          for(let i=0;i<100;i++){
            if(source.linkedBrowser.browsingContext.currentWindowGlobal?.documentURI?.spec.startsWith("data:")
               && !source.hasAttribute("busy"))break;
            await new Promise(r=>setTimeout(r,50));
          }
          source._zenContentsVisible=true;
          return true;
        """)
        fixture_created = True
        content("""
          document.querySelector("#draft").value="Keep this unsaved draft";
          window.wrappedJSObject.recoveryMarker="same live document";
          return true;
        """)
        before = state()
        poison()
        time.sleep(.9)
        check("stale native snapshot reproduced without the mod",
              state()["hidden"] and state()["images"] == 1)
        load()
        after = settle()
        check("startup clears the stale layer", not after["hidden"] and not after["images"])
        check("recovery preserves document, navigation, tabs and splits", unchanged(before, after))
        check("unsaved input and page globals survive", content("""
          return document.querySelector("#draft").value==="Keep this unsaved draft" &&
            window.wrappedJSObject.recoveryMarker==="same live document";
        """))

        poison(hidden=False)
        settle()
        check("new image-only residue is recovered automatically", True)
        poison(image=False)
        settle()
        check("new hidden-only residue is recovered automatically", True)

        m.js("delete window.snapshotRecoveryTest.source._zenContentsVisible;")
        poison()
        time.sleep(.9)
        check("a tab that does not own its live content is untouched", state()["hidden"])
        m.js("""
          const f=window.snapshotRecoveryTest;
          f.source._zenContentsVisible=true;
          gBrowser.selectedTab=f.sibling;gBrowser.selectedTab=f.source;
        """)
        settle()
        check("tab selection retries recovery after ownership returns", True)

        m.js('window.snapshotRecoveryTest.source.setAttribute("busy","true");')
        poison()
        time.sleep(.9)
        check("busy navigation is untouched", state()["hidden"])
        m.js('window.snapshotRecoveryTest.source.removeAttribute("busy");WindowSyncRecovery.refresh();')
        settle()

        m.js('window.snapshotRecoveryTest.source.setAttribute("pending","true");')
        poison()
        time.sleep(.9)
        check("a pending tab is untouched", state()["hidden"])
        m.js('window.snapshotRecoveryTest.source.removeAttribute("pending");WindowSyncRecovery.refresh();')
        settle()

        poison()
        m.js("""
          setTimeout(()=>{delete window.snapshotRecoveryTest.source._zenContentsVisible;},400);
        """)
        time.sleep(1)
        check("ownership is checked again before cleanup", state()["hidden"])
        m.js('window.snapshotRecoveryTest.source._zenContentsVisible=true;WindowSyncRecovery.refresh();')
        settle()

        m.js("""
          const t=window.snapshotRecoveryTest.blank,b=t.linkedBrowser;
          t._zenContentsVisible=true;b.setAttribute("zen-pseudo-hidden","true");
        """)
        time.sleep(.9)
        check("an about:blank stand-in is not mistaken for a live page",
              m.js('return window.snapshotRecoveryTest.blank.linkedBrowser.hasAttribute("zen-pseudo-hidden")'))
        m.js('window.snapshotRecoveryTest.blank.linkedBrowser.removeAttribute("zen-pseudo-hidden");')

        # A real second browser window must suspend recovery, including private
        # windows which do not share this fixture's document.
        m.async_js("""
          const other=OpenBrowserWindow({private:true});
          window.snapshotRecoveryTest.other=other;
          for(let i=0;i<100&&!other.gBrowserInit?.delayedStartupFinished;i++)
            await new Promise(r=>setTimeout(r,50));
          await other.gZenStartup.promiseInitialized;
          return true;
        """)
        check("second window opened",
              m.js('return [...Services.wm.getEnumerator("navigator:browser")].length===2'))
        before = state()
        poison()
        time.sleep(1)
        check("multiple windows preserve native snapshots", state()["hidden"] and state()["images"] == 1)
        m.js('window.snapshotRecoveryTest.other.close();')
        after = settle()
        check("closing the other window triggers cleanup", not after["hidden"])
        check("closing-window recovery preserves the live page", unchanged(before, after))

        m.async_js("""
          const f=window.snapshotRecoveryTest;
          gZenViewSplitter.splitTabs([f.source,f.sibling],"grid");
          await new Promise(r=>setTimeout(r,600));
          return true;
        """)
        before = state()
        check("a native split is present for preservation testing", bool(before["splits"]))
        poison()
        after = settle()
        check("split membership and both tab identities are preserved", unchanged(before, after))

        m.js('window.snapshotRecoveryTest.oldAPI=window.WindowSyncRecovery;WindowSyncRecovery.destroy();')
        old_stats = m.js("return window.snapshotRecoveryTest.oldAPI.stats")
        poison()
        time.sleep(.9)
        check("unloading stops automatic cleanup", state()["hidden"] and state()["images"] == 1)
        load()
        settle()
        check("reloading recovers existing residue", True)
        check("the destroyed controller stays inactive",
              old_stats == m.js("return window.snapshotRecoveryTest.oldAPI.stats"))
        result["passed"] = True
    except Exception as error:
        result["error"] = str(error)
        raise
    finally:
        try:
            if fixture_created:
                m.async_js("""
                  const f=window.snapshotRecoveryTest;
                  if(f?.other&&!f.other.closed)f.other.close();
                  if(f){
                    for(const tab of [f.source,f.sibling,f.blank])
                      if(tab?.isConnected)gBrowser.removeTab(tab,{animate:false,skipPermitUnload:true});
                    if(f.original?.isConnected)gBrowser.selectedTab=f.original;
                  }
                  delete window.snapshotRecoveryTest;
                  return true;
                """)
        finally:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(result, indent=2) + "\n")
            m.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--port", type=int, default=2842)
    parser.add_argument("--report", type=Path, required=True)
    run(parser.parse_args())
