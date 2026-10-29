"""Reproduce a closed placeholder left in Zen's active, temporary split."""

import argparse
import base64
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time

from integration import Handler
from runtime import Marionette


def run(args):
    args.report.parent.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    m = Marionette(args.port)
    result = {}

    def snapshot():
        return m.js("""
          const m=gZenGlanceManager, f=window.staleSplitFixture;
          const outer=gBrowser.tabpanels.getBoundingClientRect();
          const wrapper=m.browserWrapper;
          const inner=wrapper?.getBoundingClientRect();
          return {
            animating:m._animating,opening:m.animatingOpen,
            preview:gBrowser.selectedTab.hasAttribute("zen-glance-tab"),
            finished:wrapper?.getAttribute("has-finished-animation"),
            centerError:inner && Math.abs(inner.x+inner.width/2-outer.x-outer.width/2),
            widthRatio:inner && inner.width/outer.width,
            filter:getComputedStyle(f.source.linkedBrowser.closest(".browserSidebarContainer")).filter,
            sourceContext:f.source.linkedBrowser.browsingContext.id,
            sourceDocument:f.source.linkedBrowser.browsingContext.currentWindowGlobal.innerWindowId,
            previewContext:f.preview?.linkedBrowser.browsingContext.id,
            previewDocument:f.preview?.linkedBrowser.browsingContext.currentWindowGlobal.innerWindowId,
            currentView:gZenViewSplitter.currentView,
            staleRecordPresent:gZenViewSplitter._data.includes(f.stale),
            workingSplits:gZenViewSplitter.storeDataForSessionStore().filter(g=>g.groupId),
            repairedRecords:window.AutoGlance?.repairedTransientSplits || 0,
            recoveredPreview:window.AutoGlance?.recoveredPreview || false
          };
        """)

    def wait_settled():
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            state = snapshot()
            if state["preview"] and state["finished"] == "true" and not state["animating"]:
                return state
            time.sleep(.05)
        raise AssertionError(f"Glance did not finish opening: {snapshot()}")

    def poison_split():
        # The live failure involved a closed placeholder and a surviving tab
        # also belonging to another split. Preserve that other split exactly.
        return m.js("""
          const f=window.staleSplitFixture, s=gZenViewSplitter;
          const closed=gBrowser.addTrustedTab("about:blank",{skipRoute:true});
          const stale={tabs:[closed,f.shared],gridType:"vsep",
            layoutTree:s.calculateLayoutTree([closed,f.shared],"vsep")};
          gBrowser.removeTab(closed,{animate:false,skipPermitUnload:true});
          if(closed.isConnected || closed.linkedBrowser)throw Error("Fixture tab is not closed");
          f.stale=stale;
          s._data.push(stale);
          s.currentView=s._data.indexOf(stale);
          return {closed:closed.closing,hasBrowser:!!closed.linkedBrowser};
        """)

    def open_preview():
        m.js("""
          const f=window.staleSplitFixture;
          f.preview=gBrowser.addTrustedTab(arguments[0],{skipRoute:true});
          f.promise=gZenGlanceManager.openGlance({},f.preview,f.source);
          return true;
        """, [base + "/target"])

    def check_layout(state):
        assert state["preview"] and not state["animating"], state
        assert state["finished"] == "true" and state["centerError"] < 2, state
        assert .78 < state["widthRatio"] < .82 and state["filter"] == "blur(6px)", state
        assert not state["staleRecordPresent"], state
        assert state["workingSplits"] == result["before"]["workingSplits"], state
        for key in ("sourceContext", "sourceDocument"):
            assert state[key] == result["before"][key], state

    try:
        actual = m.js('return Services.dirsvc.get("ProfD",Ci.nsIFile).path;')
        if Path(actual).resolve() != args.profile.resolve() or "test-profile" not in args.profile.name:
            raise RuntimeError("This test requires the disposable profile.")
        m.async_js("""
          await gZenStartup.promiseInitialized;
          window.AutoGlance?.destroy();
          const source=gBrowser.addTrustedTab(arguments[0],{skipRoute:true});
          const shared=gBrowser.addTrustedTab("about:blank",{skipRoute:true});
          const sibling=gBrowser.addTrustedTab("about:blank",{skipRoute:true});
          gZenViewSplitter.splitTabs([shared,sibling],"grid");
          gBrowser.selectedTab=source;
          window.staleSplitFixture={source,shared,sibling};
          return true;
        """, [base + "/source"])
        m.command("Marionette:SetContext", {"value": "content"})
        m.command("WebDriver:Navigate", {"url": base + "/source"})
        m.js("document.getElementById('draft').value='Keep this draft';return true;")
        m.command("Marionette:SetContext", {"value": "chrome"})
        result["before"] = snapshot()
        result["fixture"] = poison_split()
        open_preview()
        time.sleep(1)
        result["interrupted"] = snapshot()
        broken = result["interrupted"]
        assert broken["animating"] and broken["finished"] is None and broken["centerError"] > 20, broken
        image = m.command("WebDriver:TakeScreenshot", {"full": False, "scroll": False})
        args.report.with_name("stale-split-before.png").write_bytes(base64.b64decode(image))
        if args.expect_broken:
            result["reproduced"] = True
            return

        m.js("""
          Services.scriptloader.loadSubScriptWithOptions(
            "chrome://sine/content/auto-glance/auto-glance.uc.js",
            {target:window,ignoreCache:true});
          return true;
        """)
        result["recovered"] = wait_settled()
        check_layout(result["recovered"])
        for key in ("previewContext", "previewDocument"):
            assert result["recovered"][key] == broken[key], result["recovered"]
        assert result["recovered"]["recoveredPreview"], result["recovered"]
        image = m.command("WebDriver:TakeScreenshot", {"full": False, "scroll": False})
        args.report.with_name("stale-split-after.png").write_bytes(base64.b64decode(image))
        m.async_js("await gZenGlanceManager.closeGlance({hasFocused:true,skipPermitUnload:true});return true;")
        m.command("Marionette:SetContext", {"value": "content"})
        assert m.js("return document.getElementById('draft').value;") == "Keep this draft"
        m.command("Marionette:SetContext", {"value": "chrome"})
        assert snapshot()["filter"] == "none"

        # With the guard installed, future stale placeholders must never
        # interrupt opening, including when the caller awaits the native promise.
        poison_split()
        open_preview()
        result["prevented"] = wait_settled()
        check_layout(result["prevented"])
        assert m.async_js("await staleSplitFixture.promise;return true;")
        m.async_js("await gZenGlanceManager.closeGlance({hasFocused:true,skipPermitUnload:true});return true;")
        result["passed"] = True
        print("PASS interrupted Glance recovered without reloading either page", flush=True)
        print("PASS future stale split prevented; working split unchanged", flush=True)
    except Exception as error:
        result["error"] = str(error)
        raise
    finally:
        # Clear only the deliberately injected record before test-tab cleanup.
        try:
            m.async_js("""
              const f=window.staleSplitFixture;
              if(f){
                gZenViewSplitter.currentView=-1;
                gZenViewSplitter._data=gZenViewSplitter._data.filter(g=>g!==f.stale);
                if(gBrowser.selectedTab.hasAttribute("zen-glance-tab"))
                  await gZenGlanceManager.closeGlance({onTabClose:true,skipPermitUnload:true});
                for(const t of [f.preview,f.source,f.shared,f.sibling])
                  if(t?.isConnected)gBrowser.removeTab(t,{animate:false,skipPermitUnload:true});
                delete window.staleSplitFixture;
              }
              return true;
            """)
        finally:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(result, indent=2) + "\n")
            m.close()
            server.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--port", type=int, default=2832)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--expect-broken", action="store_true")
    run(parser.parse_args())
