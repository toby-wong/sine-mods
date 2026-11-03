"""Adaptive split layout checks in an explicitly selected disposable Zen profile."""

import argparse
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
from urllib.parse import parse_qs, urlsplit

from regression import COUNTS, Handler
from runtime import Marionette


def run(args):
    report = {"checks": {}, "layouts": {}}
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    m = Marionette(args.port)

    def wait(expression):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            value = m.js("return (" + expression + ");")
            if value:
                return value
            time.sleep(.05)
        raise AssertionError("Timed out: " + expression)

    def check(name, value):
        assert value, name
        report["checks"][name] = True
        print("PASS", name, flush=True)

    def content():
        m.command("Marionette:SetContext", {"value": "chrome"})
        m.command("WebDriver:SwitchToWindow", {"handle": main})
        m.command("Marionette:SetContext", {"value": "content"})

    def chrome():
        m.command("Marionette:SetContext", {"value": "chrome"})

    def resize(width, height):
        chrome()
        m.command("WebDriver:SetWindowRect", {"width": width, "height": height})
        wait(f"window.outerWidth==={width} && window.outerHeight==={height}")

    def key(value, modifiers=()):
        actions = [{"type": "keyDown", "value": modifier} for modifier in modifiers]
        actions += [{"type": "keyDown", "value": value}, {"type": "keyUp", "value": value}]
        actions += [{"type": "keyUp", "value": modifier} for modifier in reversed(modifiers)]
        m.command("WebDriver:PerformActions", {"actions": [{"type": "key", "id": "keyboard", "actions": actions}]})

    def type_text(value):
        field = m.command("WebDriver:FindElement", {"using": "css selector", "value": "#urlbar-input"})
        m.command("WebDriver:ElementSendKeys", {
            "id": field["element-6066-11e4-a52e-4f735466cecf"], "text": value,
        })

    def click(link, alt=False):
        content()
        point = m.js("""
          const r=document.getElementById(arguments[0]).getBoundingClientRect();
          return {x:Math.round(r.x+60),y:Math.round(r.y+r.height/2)};
        """, [link])
        if alt:
            m.command("WebDriver:PerformActions", {"actions": [{
                "type": "key", "id": "modifier", "actions": [{"type": "keyDown", "value": "\ue00a"}],
            }]})
        try:
            m.command("WebDriver:PerformActions", {"actions": [{
                "type": "pointer", "id": "mouse", "parameters": {"pointerType": "mouse"},
                "actions": [{"type": "pointerMove", "origin": "viewport", **point},
                            {"type": "pointerDown", "button": 0}, {"type": "pointerUp", "button": 0}],
            }]})
        finally:
            m.command("WebDriver:ReleaseActions")
            chrome()

    def scenario(name, width, height, method, direction, kind="normal"):
        resize(width, height)
        m.async_js("""
          if(gZenGlanceManager.getFocusedTab())
            await gZenGlanceManager.closeGlance({hasFocused:true,skipPermitUnload:true});
          for(const tab of [...gZenWorkspaces.allStoredTabs]) {
            if(tab.linkedBrowser?.currentURI.spec.startsWith(arguments[0]))
              gBrowser.removeTab(tab,{animate:false,skipPermitUnload:true});
          }
          window.__adaptiveSource=gBrowser.addTrustedTab(arguments[0]+"/source/"+arguments[1],{skipRoute:true});
          gBrowser.selectedTab=__adaptiveSource;
          if(arguments[2]==="pinned") gBrowser.pinTab(__adaptiveSource);
          if(arguments[2]==="essential") gZenPinnedTabManager.addToEssentials([__adaptiveSource]);
          return true;
        """, [base, name, kind])
        wait("gBrowser.selectedBrowser.currentURI.spec===" + json.dumps(base + "/source/" + name) +
             " && !gBrowser.selectedBrowser.webProgress.isLoadingDocument")
        content()
        wait("document.readyState==='complete' && !!document.getElementById('draft')")
        draft = m.js("""
          document.getElementById('draft').value='Unsaved adaptive split draft';
          return {draft:document.getElementById('draft').value,marker:document.documentElement.dataset.marker};
        """)
        chrome()
        before = m.js("""
          return {tab:__adaptiveSource.id,context:__adaptiveSource.linkedBrowser.browsingContext.id,
            inner:__adaptiveSource.linkedBrowser.browsingContext.currentWindowGlobal.innerWindowId,
            count:gBrowser.tabs.length};
        """)
        if method in ("keyboard", "explicit-side"):
            if method == "keyboard":
                key("t", modifiers=split_modifiers)
            else:
                m.js("gZenViewSplitter.createEmptySplit('right');return true;")
            wait("gZenViewSplitter.waitingForSplitTab && gURLBar.focused && gURLBar.hasAttribute('zen-newtab')")
            check(name + "_placeholder_direction", m.js("""
              return gZenViewSplitter._data.find(g=>g.tabs.includes(__adaptiveSource)).layoutTree.direction===arguments[0];
            """, [direction]))
            type_text("adapt")
            key("\ue004")
            wait("gURLBar.searchMode?.engineName==='Adaptive split test'")
            type_text(name + " a & b/雪?=")
            key("\ue007")
            url = wait("gBrowser.selectedBrowser.currentURI.spec.startsWith(" +
                       json.dumps(base + "/search?") + ") && gBrowser.selectedBrowser.currentURI.spec")
            wait("!gZenViewSplitter.waitingForSplitTab && !gURLBar.hasAttribute('zen-newtab')")
            check(name + "_native_query", parse_qs(urlsplit(url).query)["q"] == [name + " a & b/雪?="])
        elif method == "alt":
            click("plain", alt=True)
        elif method == "glance":
            click("blank")
            wait("gBrowser.selectedTab.hasAttribute('zen-glance-tab') && !gZenGlanceManager._animating")
            m.async_js("await gZenGlanceManager.splitGlance();return true;")
        elif method == "explicit-layout":
            m.js("""
              const target=gBrowser.addTrustedTab(arguments[0]+"/target/explicit",{skipRoute:true});
              gZenViewSplitter.splitTabs([__adaptiveSource,target],"vsep",1);
              return true;
            """, [base])
        else:
            raise ValueError(method)
        wait("gZenViewSplitter._data.some(g=>g.tabs.includes(__adaptiveSource) && g.tabs.length===2 && !g.tabs.some(t=>t.hasAttribute('zen-empty-tab')))")
        geometry = wait("""(() => {
          const group=gZenViewSplitter._data.find(g=>g.tabs.includes(__adaptiveSource));
          if(group?.layoutTree.direction!==""" + json.dumps(direction) + """) return false;
          const [a,b]=group.tabs.map(t=>t.linkedBrowser.closest('.browserSidebarContainer').getBoundingClientRect());
          const column=group.layoutTree.direction==='column';
          if(column ? Math.abs(a.x-b.x)>2 || b.y<a.bottom-2 :
            Math.abs(a.y-b.y)>2 || b.x<a.right-2) return false;
          return {direction:group.layoutTree.direction,gridType:group.gridType,
            panes:[a,b].map(r=>({x:r.x,y:r.y,width:r.width,height:r.height})),
            window:{width:outerWidth,height:outerHeight}};
        })()""")
        report["layouts"][name] = geometry
        check(name + "_rendered_layout", before["count"] + 1 == m.js("return gBrowser.tabs.length;"))
        after = m.js("""
          return {tab:__adaptiveSource.id,context:__adaptiveSource.linkedBrowser.browsingContext.id,
            inner:__adaptiveSource.linkedBrowser.browsingContext.currentWindowGlobal.innerWindowId};
        """)
        check(name + "_source_identity", after == {k: before[k] for k in after} and COUNTS["/source/" + name] == 1)
        m.js("gBrowser.selectedTab=__adaptiveSource;return true;")
        content()
        check(name + "_draft", draft == m.js("""
          return {draft:document.getElementById('draft').value,marker:document.documentElement.dataset.marker};
        """))
        chrome()

    try:
        actual = m.js('return Services.dirsvc.get("ProfD",Ci.nsIFile).path;')
        if Path(actual).resolve() != args.profile.resolve() or "test-profile" not in args.profile.name:
            raise RuntimeError("Refusing to run outside the specified disposable profile")
        main = m.command("WebDriver:GetWindowHandle")
        is_mac = m.js("return Services.appinfo.OS==='Darwin';")
        split_modifiers = ("\ue03d", "\ue009", "\ue008") if is_mac else ("\ue009", "\ue00a", "\ue008")
        m.async_js("""
          await gZenStartup.promiseInitialized;
          await AltClickSplitView.ready;
          const {SearchService}=ChromeUtils.importESModule("moz-src:///toolkit/components/search/SearchService.sys.mjs");
          await SearchService.init();
          const old=SearchService.getEngineByName("Adaptive split test");
          if(old) await SearchService.removeEngine(old);
          await SearchService.addUserEngine({name:"Adaptive split test",alias:"adapt",
            url:arguments[0]+"/search?q={searchTerms}",method:"GET"});
          Services.prefs.setBoolPref("uc.alt-click-split-view.enabled",true);
          Services.prefs.setBoolPref("uc.alt-click-split-view.adaptive-direction",true);
          Services.prefs.setStringPref("uc.alt-click-split-view.trigger","alt");
          Services.prefs.setStringPref("zen.glance.activation-method","shift");
          const key=document.getElementById("zen-new-empty-split-view");
          key.setAttribute("key","T");
          key.setAttribute("modifiers",arguments[1]);
          return true;
        """, [base, "accel,control,shift" if is_mac else "accel,alt,shift"])
        for case in [
            ("tall_keyboard", 800, 1200, "keyboard", "column"),
            ("wide_keyboard", 1200, 800, "keyboard", "row"),
            ("square_keyboard", 900, 900, "keyboard", "row"),
            ("tall_alt", 800, 1200, "alt", "column"),
            ("wide_alt", 1200, 800, "alt", "row"),
            ("tall_glance", 800, 1200, "glance", "column"),
            ("wide_glance", 1200, 800, "glance", "row"),
            ("tall_pinned_alt", 800, 1200, "alt", "column", "pinned"),
            ("tall_essential_alt", 800, 1200, "alt", "column", "essential"),
            ("tall_pinned_glance", 800, 1200, "glance", "column", "pinned"),
            ("tall_essential_glance", 800, 1200, "glance", "column", "essential"),
            ("tall_explicit_side", 800, 1200, "explicit-side", "row"),
            ("tall_explicit_layout", 800, 1200, "explicit-layout", "row"),
        ]:
            scenario(*case)
        m.js("""
          window.__adaptiveSettings=gBrowser.addTrustedTab("about:preferences#zenTabs",{skipRoute:true});
          return true;
        """)
        wait("__adaptiveSettings.linkedBrowser.contentDocument?.querySelector('#split-link-adaptive-direction')")
        check("settings_toggle_defaults_on", m.js("""
          const toggle=__adaptiveSettings.linkedBrowser.contentDocument.querySelector('#split-link-adaptive-direction');
          const wasChecked=toggle.checked;
          toggle.click();
          return wasChecked && !Services.prefs.getBoolPref("uc.alt-click-split-view.adaptive-direction");
        """))
        scenario("tall_toggle_off", 800, 1200, "keyboard", "row")
        m.js("""
          __adaptiveSettings.linkedBrowser.contentDocument.querySelector('#split-link-adaptive-direction').click();
          return true;
        """)
        scenario("tall_toggle_on", 800, 1200, "keyboard", "column")
        m.js("gBrowser.removeTab(__adaptiveSettings,{animate:false});return true;")
        saved = m.js("return JSON.stringify(gZenViewSplitter.storeDataForSessionStore());")
        resize(1200, 800)
        check("existing_layout_survives_resize", saved == m.js("return JSON.stringify(gZenViewSplitter.storeDataForSessionStore());"))
        m.async_js("""
          Services.scriptloader.loadSubScriptWithOptions(
            "chrome://sine/content/alt-click-split-view/alt-click-split-view.uc.js",{target:window,ignoreCache:true});
          await AltClickSplitView.ready;
          return true;
        """)
        check("hot_reload_preserves_existing_layout", saved == m.js("return JSON.stringify(gZenViewSplitter.storeDataForSessionStore());"))
        scenario("tall_after_reload", 800, 1200, "alt", "column")
        resize(1200, 800)
        report["passed"] = True
    except Exception as error:
        report["passed"] = False
        report["error"] = str(error)
        raise
    finally:
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        m.close()
        server.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--port", type=int, default=2833)
    parser.add_argument("--report", type=Path, required=True)
    run(parser.parse_args())
