"""Check promotion after the main window closes and alternate Zen window defaults."""

import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from runtime import Marionette


def run(args):
    m = Marionette(args.port)
    result = {}
    try:
        actual = m.js('return Services.dirsvc.get("ProfD", Ci.nsIFile).path;')
        if Path(actual).resolve() != args.profile.resolve() or "test-profile" not in args.profile.name:
            raise RuntimeError("Lifecycle checks require the disposable test profile.")
        m.js("""
          for(const w of Services.wm.getEnumerator("navigator:browser"))
            if(w!==window && w._littleZenInfo)w.close();
          Services.scriptloader.loadSubScriptWithOptions(
            "chrome://sine/content/little-zen/little-zen.uc.js",{target:window,ignoreCache:true});
          Services.prefs.setBoolPref("zen.window-sync.prefer-unsynced-windows",true);
          return true;
        """)
        m.async_js("await new Promise(r=>setTimeout(r,100));return true;")
        before = set(m.command("WebDriver:GetWindowHandles"))
        m.js("LittleZen.open();return true;")
        deadline = time.monotonic() + 10
        mini = None
        while time.monotonic() < deadline:
            created = set(m.command("WebDriver:GetWindowHandles")) - before
            if created:
                mini = created.pop()
                break
            time.sleep(.05)
        assert mini
        m.command("WebDriver:SwitchToWindow", {"handle": mini})
        ready = m.async_js("""
          const deadline=Date.now()+10000;
          while(window.LittleZen?.status!=="ready" && Date.now()<deadline)
            await new Promise(r=>setTimeout(r,50));
          return {ready:LittleZen.status==="ready",syncing:gZenWorkspaces.currentWindowIsSyncing};
        """)
        assert ready["ready"] and not ready["syncing"], ready
        result["alternate_window_default"] = ready
        print("PASS alternate_window_default", flush=True)
        state = m.js("""
          const context=gBrowser.selectedBrowser.browsingContext.id;
          for(const w of Services.wm.getEnumerator("navigator:browser")) {
            if(w!==window && !w._littleZenInfo)w.close();
          }
          return {context};
        """)
        m.async_js("await new Promise(r=>setTimeout(r,150));return true;")
        surviving = m.js("""
          return {windows:[...Services.wm.getEnumerator("navigator:browser")].length,
            context:gBrowser.selectedBrowser.browsingContext.id,ready:LittleZen.status==="ready"};
        """)
        assert surviving["windows"] == 1 and surviving["context"] == state["context"] and surviving["ready"]
        result["main_close_preserves_mini"] = surviving
        print("PASS main_close_preserves_mini", flush=True)
        m.js("LittleZen.promote().catch(console.error);return true;")
        deadline = time.monotonic() + 12
        main = None
        while time.monotonic() < deadline:
            remaining = set(m.command("WebDriver:GetWindowHandles"))
            if mini not in remaining and remaining:
                main = next(iter(remaining))
                break
            time.sleep(.05)
        assert main, "Promotion did not complete after the original main window closed."
        m.command("WebDriver:SwitchToWindow", {"handle": main})
        promoted = m.js("""
          return {context:gBrowser.selectedBrowser.browsingContext.id,
            syncing:gZenWorkspaces.currentWindowIsSyncing,mini:!!window._littleZenInfo};
        """)
        assert promoted["context"] == state["context"] and promoted["syncing"] and not promoted["mini"]
        result["promotion_creates_main"] = promoted
        print("PASS promotion_creates_main", flush=True)
        schemes = m.js("""
          const before=[...Services.wm.getEnumerator("navigator:browser")].length;
          const rejected=[];
          for(const url of ["javascript:void(0)","data:text/html,test","file:///tmp/little-zen-test"]) {
            try{LittleZen.open({url});}catch{rejected.push(url.split(":")[0]);}
          }
          return {rejected,unchanged:before===[...Services.wm.getEnumerator("navigator:browser")].length};
        """)
        assert len(schemes["rejected"]) == 3 and schemes["unchanged"], schemes
        result["link_command_scheme_guard"] = schemes
        print("PASS link_command_scheme_guard", flush=True)
        m.js('Services.prefs.setBoolPref("zen.window-sync.prefer-unsynced-windows",false);return true;')
        result["passed"] = True
    except Exception as error:
        result["passed"] = False
        result["error"] = str(error)
        raise
    finally:
        args.report.write_text(json.dumps(result, indent=2) + "\n")
        m.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=2832)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    run(parser.parse_args())
