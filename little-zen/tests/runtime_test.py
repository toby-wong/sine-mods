"""Exercise Little Zen in a disposable profile using the installed browser.

Run against an already started test profile:
  python3 tests/runtime_test.py --profile /path/to/test-profile --report /path/report.json
"""

import argparse
import base64
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import time
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from runtime import Marionette


REQUESTS = Counter()
PAGE = b"""<!doctype html><html><head><meta charset="utf-8"><title>Little Zen test page</title>
<style>body{font:16px system-ui;margin:48px;max-width:660px;color:#26332a;background:#fafbf8}
h1{font-size:28px}input{display:block;margin:20px 0;padding:12px;width:80%;font:inherit}
a{display:block;margin:18px 0;color:#245c47}p{line-height:1.6}</style></head><body>
<h1>A small window, your normal browser.</h1>
<p>This local page checks that Little Zen preserves your search, login context and unfinished work.</p>
<input id="draft" placeholder="An unfinished draft">
<a id="next" href="/linked">A link to another local page</a>
<a id="newtab" href="/new-tab" target="_blank">A link that opens another tab</a>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        REQUESTS[urlsplit(self.path).path] += 1
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(PAGE)))
        self.end_headers()
        self.wfile.write(PAGE)

    def log_message(self, *_args):
        pass


def run(args):
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    result = {"checks": {}, "base": base}
    m = Marionette(args.port)

    def check(name, details, passed):
        result["checks"][name] = details
        if not passed:
            raise AssertionError(f"{name}: {details}")
        print("PASS", name, flush=True)

    def context(name="chrome"):
        if name == "content":
            # A tab selected by browser chrome is not automatically Marionette's
            # current content target. Reselect its window before content work.
            m.command("Marionette:SetContext", {"value": "chrome"})
            handle = m.command("WebDriver:GetWindowHandle")
            m.command("WebDriver:SwitchToWindow", {"handle": handle})
        m.command("Marionette:SetContext", {"value": name})

    def switch(handle):
        context()
        m.command("WebDriver:SwitchToWindow", {"handle": handle})

    def handles():
        context()
        return set(m.command("WebDriver:GetWindowHandles"))

    def wait(expression, timeout=12):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = m.js("return (" + expression + ");")
            if value:
                return value
            time.sleep(0.05)
        raise AssertionError("Timed out waiting for: " + expression)

    def new_window(action, parent, jsargs=None):
        switch(parent)
        before = handles()
        m.js(action, jsargs)
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            added = handles() - before
            if len(added) == 1:
                handle = added.pop()
                switch(handle)
                wait("window.LittleZen?.status === 'ready' || window.LittleZen?.status === 'error'")
                status = m.js("return {status:LittleZen.status,error:LittleZen.error};")
                if status["status"] != "ready":
                    raise AssertionError(status)
                return handle
            time.sleep(.05)
        raise AssertionError("Expected one new browser window")

    def navigate(url):
        context("content")
        m.command("WebDriver:Navigate", {"url": url})
        context()

    try:
        actual = m.js('return Services.dirsvc.get("ProfD", Ci.nsIFile).path;')
        if Path(actual).resolve() != args.profile.resolve() or "test-profile" not in args.profile.name:
            raise RuntimeError("Runtime tests must use the explicitly named disposable test profile.")

        # Locate and retain the ordinary main window.
        main = None
        for handle in handles():
            switch(handle)
            if m.js("return !window._littleZenInfo && !PrivateBrowsingUtils.isWindowPrivate(window);"):
                main = handle
                break
        if main is None:
            raise RuntimeError("No regular test window")
        switch(main)
        m.js("""
          for (const win of Services.wm.getEnumerator("navigator:browser")) {
            if (win !== window && win._littleZenInfo) win.close();
          }
          return true;
        """)
        wait("!!window.LittleZen && LittleZen.status === 'ready'")
        m.js('Services.prefs.setBoolPref("uc.little-zen.external-links",false);return true;')
        source = m.async_js("""
          const {ContextualIdentityService} = ChromeUtils.importESModule(
            "moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs");
          const identity = ContextualIdentityService.create("Little Zen runtime test", "fingerprint", "green");
          const workspace = gZenWorkspaces.getActiveWorkspaceFromCache();
          workspace.containerTabId = identity.userContextId;
          gZenWorkspaces.saveWorkspace(workspace);
          const destination = await gZenWorkspaces.createAndSaveWorkspace(
            "Little Zen destination", undefined, true, 0);
          const tab = gBrowser.addTrustedTab(arguments[0] + "/source", {
            userContextId: identity.userContextId, skipRoute:true});
          gBrowser.selectedTab = tab;
          window.__lzDestination = destination.uuid;
          window.__lzContext = identity.userContextId;
          return {container:identity.userContextId,source:workspace.uuid,
            destination:destination.uuid,destinationContainer:0};
        """, [base])
        navigate(base + "/source")
        context("content")
        m.js('document.cookie="littlezen-login=from-source; path=/"; return true;')
        context()
        baseline = m.js("""
          return [...gBrowser.tabs].filter(t=>!t.closing).map(t=>({
            id:t.id,url:t.linkedBrowser?.currentURI?.spec,space:t.getAttribute("zen-workspace-id")}));
        """)

        mini = new_window("LittleZen.open(); return true;", main)
        opened = m.js("""
          return {unsynced:document.documentElement.hasAttribute("zen-unsynced-window"),
            syncing:gZenWorkspaces.currentWindowIsSyncing,container:gBrowser.selectedTab.userContextId,
            realTabs:LittleZen.realTabs().length,controls:!!document.getElementById("little-zen-controls"),
            width:outerWidth,height:outerHeight,
            addressWidth:document.getElementById("urlbar-container").getBoundingClientRect().width,
            contentHeight:document.getElementById("zen-appcontent-wrapper").getBoundingClientRect().height};
        """)
        check("independent_window", opened,
              opened["unsynced"] and not opened["syncing"] and opened["realTabs"] == 1
              and opened["container"] == source["container"] and opened["controls"]
              and opened["addressWidth"] > 300 and opened["contentHeight"] > 350)
        switch(main)
        after = m.js("""
          return [...gBrowser.tabs].filter(t=>!t.closing).map(t=>({
            id:t.id,url:t.linkedBrowser?.currentURI?.spec,space:t.getAttribute("zen-workspace-id")}));
        """)
        check("main_tabs_unchanged", {"before": len(baseline), "after": len(after)}, baseline == after)

        switch(mini)
        navigate(base + "/page")
        context("content")
        cookie = m.js("return document.cookie;")
        check("container_login_inherited", {"cookie": cookie}, "littlezen-login=from-source" in cookie)
        context()
        engine = m.async_js("""
          const {SearchService} = ChromeUtils.importESModule(
            "moz-src:///toolkit/components/search/SearchService.sys.mjs");
          await SearchService.init();
          const previous=SearchService.getEngineByName("Little Zen runtime search");
          if(previous)await SearchService.removeEngine(previous);
          const engine=await SearchService.addUserEngine({
            name:"Little Zen runtime search",alias:"lztest",url:arguments[0]+"/search?q={searchTerms}",method:"GET"});
          return engine.alias;
        """, [base])
        m.js("window.focus();gURLBar.select();return true;")
        wait("document.activeElement === gURLBar.inputField")
        field = m.command("WebDriver:FindElement", {"using": "css selector", "value": "#urlbar-input"})
        field_id = field["element-6066-11e4-a52e-4f735466cecf"]
        m.command("WebDriver:ElementSendKeys", {"id": field_id, "text": "lztest "})
        wait("gURLBar.searchMode?.engineName === 'Little Zen runtime search'")
        m.command("WebDriver:ElementSendKeys", {"id": field_id, "text": "keyboard phrase\ue007"})
        search_url = wait(f"gBrowser.selectedBrowser.currentURI.spec.startsWith({json.dumps(base+'/search')}) && gBrowser.selectedBrowser.currentURI.spec")
        check("native_keyword_search", {"alias": engine, "url": search_url},
              "keyboard" in search_url and "phrase" in search_url)

        navigate(base + "/page")
        context("content")
        draft = m.js("""
          document.getElementById("draft").value="Keep my unfinished draft";
          window.littleZenTransient="same live document";
          history.replaceState({draft:42},"","/page?draft=42");
          return {value:document.getElementById("draft").value,transient:window.littleZenTransient,state:history.state};
        """)
        context()
        before_context = m.js("return gBrowser.selectedBrowser.browsingContext.id;")
        before_requests = REQUESTS["/page"]
        image = m.command("WebDriver:TakeScreenshot", {"full": False})
        args.report.with_suffix(".png").write_bytes(base64.b64decode(image))
        switch(main)
        promotion = m.async_js("""
          const child=[...Services.wm.getEnumerator("navigator:browser")].find(w=>w._littleZenInfo);
          const tab=await child.LittleZen.promote(arguments[0]);
          return {context:tab.linkedBrowser.browsingContext.id,container:tab.userContextId,
            space:tab.getAttribute("zen-workspace-id"),active:gZenWorkspaces.activeWorkspace,
            childClosed:child.closed,url:tab.linkedBrowser.currentURI.spec};
        """, [source["destination"]])
        context("content")
        preserved = m.js("""
          return {value:document.getElementById("draft")?.value,transient:window.littleZenTransient,state:history.state};
        """)
        context()
        promotion["liveDocumentPreserved"] = preserved == draft
        promotion["noReload"] = REQUESTS["/page"] == before_requests
        check("promote_without_reload", promotion,
              promotion["context"] == before_context and promotion["container"] == source["container"]
              and promotion["space"] == source["destination"] and promotion["active"] == source["destination"]
              and promotion["liveDocumentPreserved"] and promotion["noReload"] and promotion["childClosed"])

        # Multiple temporary tabs stay accessible; keeping one leaves the rest.
        mini = new_window("LittleZen.open({url:arguments[0]+'/first'}); return true;", main, [base])
        wait(f"gBrowser.selectedBrowser.currentURI.spec === {json.dumps(base+'/first')}")
        m.js("""
          const tab=gBrowser.addTrustedTab(arguments[0]+"/second",{userContextId:gBrowser.selectedTab.userContextId,skipRoute:true});
          gBrowser.selectedTab=tab;return true;
        """, [base])
        wait(f"gBrowser.selectedBrowser.currentURI.spec === {json.dumps(base+'/second')}")
        tabs_ui = m.js("""
          return {count:LittleZen.realTabs().length,hidden:document.getElementById("little-zen-tabs").hidden};
        """)
        switch(main)
        multi = m.async_js("""
          const child=[...Services.wm.getEnumerator("navigator:browser")].find(w=>w._littleZenInfo);
          await child.LittleZen.promote(arguments[0]);
          return {childClosed:child.closed,remaining:child.LittleZen.realTabs().map(t=>t.linkedBrowser.currentURI.spec)};
        """, [source["destination"]])
        check("multiple_tabs", {**tabs_ui, **multi},
              tabs_ui["count"] == 2 and not tabs_ui["hidden"] and not multi["childClosed"]
              and multi["remaining"] == [base + "/first"])
        switch(mini)
        m.js("window.close();")
        switch(main)

        # Open a real content context menu, then invoke its added command.
        navigate(base + "/context-source")
        context("content")
        point = m.js("""
          const rect=document.getElementById("next").getBoundingClientRect();
          return {x:Math.round(rect.x+60),y:Math.round(rect.y+rect.height/2)};
        """)
        m.command("WebDriver:PerformActions", {"actions": [{
            "type": "pointer", "id": "context-menu", "parameters": {"pointerType": "mouse"},
            "actions": [
                {"type": "pointerMove", "origin": "viewport", **point},
                {"type": "pointerDown", "button": 2}, {"type": "pointerUp", "button": 2},
            ],
        }]})
        m.command("WebDriver:ReleaseActions")
        context()
        wait("window.gContextMenu?.onLink && !document.getElementById('little-zen-open-link').hidden")
        mini = new_window("""
          document.getElementById("little-zen-open-link").doCommand();
          document.getElementById("contentAreaContextMenu").hidePopup();
          return true;
        """, main)
        wait(f"gBrowser.selectedBrowser.currentURI.spec === {json.dumps(base+'/linked')}")
        link_open = m.js("""
          return {url:gBrowser.selectedBrowser.currentURI.spec,context:gBrowser.selectedTab.userContextId};
        """)
        check("link_context_menu", link_open,
              link_open["url"] == base + "/linked" and link_open["context"] == source["destinationContainer"])
        m.js("window.close();")
        switch(main)

        # Both external-link branches use the actual BrowserDOMWindow entry.
        before = handles()
        m.js("""
          Services.prefs.setBoolPref("uc.little-zen.external-links",false);
          browserDOMWindow.openURI(Services.io.newURI(arguments[0]+"/external-off"),null,
            Ci.nsIBrowserDOMWindow.OPEN_NEWTAB,Ci.nsIBrowserDOMWindow.OPEN_EXTERNAL,
            Services.scriptSecurityManager.getSystemPrincipal(),null);
          return true;
        """, [base])
        wait(f"[...gBrowser.tabs].some(t=>t.linkedBrowser?.currentURI?.spec === {json.dumps(base+'/external-off')})")
        check("external_routing_default_off", {"windowsBefore": len(before), "windowsAfter": len(handles())},
              handles() == before)
        mini = new_window("""
          Services.prefs.setBoolPref("uc.little-zen.external-links",true);
          browserDOMWindow.openURI(Services.io.newURI(arguments[0]+"/external-on"),null,
            Ci.nsIBrowserDOMWindow.OPEN_NEWTAB,Ci.nsIBrowserDOMWindow.OPEN_EXTERNAL,
            Services.scriptSecurityManager.getSystemPrincipal(),null);
          return true;
        """, main, [base])
        wait(f"gBrowser.selectedBrowser.currentURI.spec === {json.dumps(base+'/external-on')}")
        routed = m.js("""
          return {external:window._littleZenInfo.external,container:gBrowser.selectedTab.userContextId,
            unsynced:document.documentElement.hasAttribute("zen-unsynced-window")};
        """)
        check("external_routing_enabled", routed,
              routed["external"] and routed["unsynced"] and routed["container"] == source["destinationContainer"])
        m.js("window.close();")
        switch(main)
        m.js('Services.prefs.setBoolPref("uc.little-zen.external-links",false);return true;')

        # Private promotion must use a private destination.
        private_main = new_window("OpenBrowserWindow({private:true});return true;", main)
        private_mini = new_window("LittleZen.open({url:arguments[0]+'/private'});return true;", private_main, [base])
        wait(f"gBrowser.selectedBrowser.currentURI.spec === {json.dumps(base+'/private')}")
        privacy = m.js("""
          return {private:PrivateBrowsingUtils.isWindowPrivate(window),
            container:gBrowser.selectedTab.userContextId,
            keepLabel:document.getElementById("little-zen-keep").getAttribute("label")};
        """)
        switch(private_main)
        privacy["promotedPrivate"] = m.async_js("""
          const child=[...Services.wm.getEnumerator("navigator:browser")].find(
            w=>w._littleZenInfo && PrivateBrowsingUtils.isWindowPrivate(w));
          const tab=await child.LittleZen.promote();
          return PrivateBrowsingUtils.isWindowPrivate(tab.documentGlobal);
        """)
        check("private_context_preserved", privacy,
              privacy["private"] and privacy["promotedPrivate"] and privacy["container"] == 0)
        m.js("window.close();")
        switch(main)

        # Live disable/unload returns to an ordinary blank window without loss.
        mini = new_window("LittleZen.open({url:arguments[0]+'/disable'});return true;", main, [base])
        wait(f"gBrowser.selectedBrowser.currentURI.spec === {json.dumps(base+'/disable')}")
        disabled = m.js("""
          const before=LittleZen.realTabs().map(t=>t.linkedBrowser.currentURI.spec);
          Services.prefs.setBoolPref("uc.little-zen.enabled",false);
          const disabled=!document.documentElement.hasAttribute("little-zen") && LittleZen.open()===null;
          Services.prefs.setBoolPref("uc.little-zen.enabled",true);
          LittleZen.destroy();
          return {disabled,markerRemoved:!document.documentElement.hasAttribute("little-zen"),
            controlsRemoved:!document.getElementById("little-zen-controls"),
            unchanged:JSON.stringify(before)===JSON.stringify([...gBrowser.tabs].filter(
              t=>!t.closing&&!t.hasAttribute("zen-empty-tab")).map(t=>t.linkedBrowser.currentURI.spec))};
        """)
        check("disable_preserves_tabs", disabled, all(disabled.values()))
        m.js("window.close();")
        switch(main)
        restored = m.js("""
          LittleZen.destroy();
          const {BrowserDOMWindow}=ChromeUtils.importESModule("resource:///modules/BrowserDOMWindow.sys.mjs");
          return {routingRestored:!Object.hasOwn(BrowserDOMWindow.prototype,"__littleZenExternalRouting"),
            menuRemoved:!document.getElementById("little-zen-new-menu"),
            splitModPresent:!!window.AltClickSplitView};
        """)
        check("unload_restores_hooks", restored, all(restored.values()))
        result["passed"] = True
    except Exception as error:
        result["passed"] = False
        result["error"] = str(error)
        raise
    finally:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2) + "\n")
        try:
            m.close()
        finally:
            server.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=2832)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    run(parser.parse_args())
