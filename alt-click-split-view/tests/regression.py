"""Real modified-click regression checks; only operates in a disposable profile."""

import argparse
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time

from runtime import Marionette

COUNTS = Counter()
PAGE = b"""<!doctype html><meta charset="utf-8"><title>Split regression</title>
<style>body{font:16px system-ui;margin:24px}a{display:block;margin:16px 0}</style>
<input id="draft" value=""><div id="links">
<a id="plain" href="/target/plain">Ordinary link</a>
<a id="blank" href="/target/blank" target="_blank">New tab link</a>
<a id="script" href="/target/script" onclick="event.preventDefault();window.open(this.href,'_blank')">Script new tab</a>
<a id="spa" href="/target/spa" onclick="event.preventDefault();history.pushState({},'',this.href)">SPA link</a>
<a id="stop" href="/target/stop" onclick="event.preventDefault();event.stopPropagation()">Suppressed link</a>
</div><script>document.documentElement.dataset.marker=crypto.randomUUID();</script>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        COUNTS[self.path] += 1
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(PAGE)))
        self.end_headers()
        self.wfile.write(PAGE)

    def log_message(self, *_args):
        pass


def run(args):
    report = {"cases": {}}
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    m = Marionette(args.port)

    def chrome():
        m.command("Marionette:SetContext", {"value": "chrome"})

    def content():
        chrome()
        m.command("WebDriver:SwitchToWindow", {
            "handle": m.command("WebDriver:GetWindowHandle"),
        })
        m.command("Marionette:SetContext", {"value": "content"})

    def wait(expr, seconds=6):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            result = m.js("return (" + expr + ");")
            if result:
                return result
            time.sleep(.05)
        raise AssertionError("Timed out: " + expr)

    def click(identifier, key="\ue00a", frame=False):
        content()
        if frame:
            element = m.command("WebDriver:FindElement", {"using": "css selector", "value": "#test-frame"})
            m.command("WebDriver:SwitchToFrame", {"element": element})
        point = m.js("""
            const r=document.getElementById(arguments[0]).getBoundingClientRect();
            return {x:Math.round(r.x+70),y:Math.round(r.y+r.height/2)};
        """, [identifier])
        if key:
            m.command("WebDriver:PerformActions", {"actions": [{
                "type": "key", "id": "modifier",
                "actions": [{"type": "keyDown", "value": key}],
            }]})
        try:
            m.command("WebDriver:PerformActions", {"actions": [{
                "type": "pointer", "id": "mouse",
                "parameters": {"pointerType": "mouse"},
                "actions": [
                    {"type": "pointerMove", "origin": "viewport", **point},
                    {"type": "pointerDown", "button": 0},
                    {"type": "pointerUp", "button": 0},
                ],
            }]})
        finally:
            m.command("WebDriver:ReleaseActions")
            chrome()

    def setup(name, kind):
        chrome()
        m.async_js("""
            if(gZenGlanceManager.getFocusedTab())
                await gZenGlanceManager.closeGlance({hasFocused:true,skipPermitUnload:true});
            for(const t of [...gZenWorkspaces.allStoredTabs]) {
                if(t.linkedBrowser?.currentURI?.spec.startsWith(arguments[0]))
                    gBrowser.removeTab(t,{animate:false,skipPermitUnload:true});
            }
            window.__splitProbeSource=gBrowser.addTrustedTab(arguments[0]+"/source/"+arguments[1],{
                skipRoute:true,userContextId:gZenWorkspaces.getCurrentSpaceContainerId()});
            gBrowser.selectedTab=window.__splitProbeSource;
            if(arguments[2]==="pinned")gBrowser.pinTab(window.__splitProbeSource);
            if(arguments[2]==="essential")gZenPinnedTabManager.addToEssentials([window.__splitProbeSource]);
            return true;
        """, [base, name, kind])
        content()
        wait("document.readyState==='complete' && !!document.getElementById('draft')")
        return snapshot()

    def snapshot():
        content()
        marker = m.js("""
            document.getElementById('draft').value='Keep this exact draft';
            return {marker:document.documentElement.dataset.marker,draft:document.getElementById('draft').value};
        """)
        chrome()
        identity = m.js("""
            const t=window.__splitProbeSource,b=t.linkedBrowser;
            return {tab:t.id,context:b.browsingContext.id,inner:b.browsingContext.currentWindowGlobal.innerWindowId,
                pinned:t.pinned,essential:t.hasAttribute("zen-essential"),url:b.currentURI.spec};
        """)
        return {**marker, **identity}

    try:
        profile = m.js('return Services.dirsvc.get("ProfD",Ci.nsIFile).path;')
        if Path(profile).resolve() != args.profile.resolve() or "test-profile" not in args.profile.name:
            raise RuntimeError("Refusing to run outside the specified disposable profile")
        m.async_js("""
            await gZenStartup.promiseInitialized;
            Services.prefs.setBoolPref("uc.alt-click-split-view.enabled",true);
            Services.prefs.setStringPref("uc.alt-click-split-view.trigger","alt");
            Services.prefs.setStringPref("zen.glance.activation-method","shift");
            Services.prefs.setBoolPref("uc.auto-glance.enabled",true);
            Services.prefs.setBoolPref("uc.auto-glance.modified-clicks",true);
            return true;
        """)
        cases = [
            ("normal_option", "normal", "plain", "option"),
            ("new_tab_option", "normal", "blank", "option"),
            ("script_option", "normal", "script", "option"),
            ("spa_option", "normal", "spa", "option"),
            ("suppressed_option", "normal", "stop", "option"),
            ("pinned_option", "pinned", "plain", "option"),
            ("essential_option", "essential", "plain", "option"),
            ("normal_glance_split", "normal", "blank", "glance"),
            ("pinned_glance_split", "pinned", "blank", "glance"),
            ("essential_glance_split", "essential", "blank", "glance"),
            ("inside_glance_option", "normal", "plain", "inside_glance"),
            ("iframe_option", "normal", "script", "iframe"),
        ]
        if args.case:
            cases = [c for c in cases if c[0] in args.case]
        for name, kind, link, action in cases:
            result = report["cases"][name] = {}
            try:
                before = result["before"] = setup(name, kind)
                if action == "inside_glance":
                    click("blank", key=None)
                    wait("gBrowser.selectedTab.hasAttribute('zen-glance-tab') && !gZenGlanceManager._animating")
                    m.js("window.__splitProbeSource=gBrowser.selectedTab;return true;")
                    content()
                    wait("document.readyState==='complete' && !!document.getElementById('draft')")
                    before = result["before"] = snapshot()
                if action == "iframe":
                    content()
                    m.js("""
                        const f=document.createElement("iframe");f.id="test-frame";
                        f.src="/frame";f.width="500";f.height="320";
                        document.getElementById("links").replaceWith(f);return true;
                    """)
                    wait("!!document.getElementById('test-frame').contentDocument?.getElementById('script')")
                    chrome()
                counts = COUNTS.copy()
                click(link, key=None if action == "glance" else "\ue00a", frame=action == "iframe")
                if action == "glance":
                    wait("gBrowser.selectedTab.hasAttribute('zen-glance-tab') && !gZenGlanceManager._animating")
                    m.async_js("await gZenGlanceManager.splitGlance();return true;")
                time.sleep(.6)
                result["after"] = m.js("""
                    const t=window.__splitProbeSource,b=t?.linkedBrowser;
                    const data=gZenViewSplitter._data;
                    const group=data.find(g=>g.tabs.includes(gBrowser.selectedTab));
                    return {sourceAlive:!!t?.isConnected,sourceURL:b?.currentURI?.spec,
                        sourceContext:b?.browsingContext?.id,sourceInner:b?.browsingContext?.currentWindowGlobal?.innerWindowId,
                        sourcePinned:t?.pinned,sourceEssential:t?.hasAttribute("zen-essential"),
                        glance:!!gZenGlanceManager.getFocusedTab(),
                        split:!!group,sourceInSplit:!!group?.tabs.includes(t),
                        panes:group?.tabs.map(x=>({tab:x.id,context:x.linkedBrowser.browsingContext.id,
                            url:x.linkedBrowser.currentURI.spec,pinned:x.pinned,essential:x.hasAttribute("zen-essential")}))};
                """)
                result["requests"] = dict(COUNTS - counts)
                m.js("gBrowser.selectedTab=window.__splitProbeSource;return true;")
                content()
                result["content"] = m.js("""
                    return {marker:document.documentElement.dataset.marker,draft:document.getElementById('draft')?.value};
                """)
                chrome()
                after = result["after"]
                result["passed"] = (
                    after["split"] and after["sourceInSplit"] and not after["glance"] and
                    after["sourceContext"] == before["context"] and
                    after["sourceInner"] == before["inner"] and after["sourceURL"] == before["url"] and
                    result["content"] == {k: before[k] for k in ["marker", "draft"]} and
                    not result["requests"].get(f"/source/{name}")
                )
                if after["split"]:
                    result["unsplit"] = m.async_js("""
                        gBrowser.selectedTab=window.__splitProbeSource;
                        gZenViewSplitter.unsplitCurrentView();
                        await new Promise(r=>setTimeout(r,80));
                        const t=window.__splitProbeSource,b=t.linkedBrowser;
                        return {pinned:t.pinned,essential:t.hasAttribute("zen-essential"),
                            split:!!t.splitView,context:b.browsingContext.id,
                            inner:b.browsingContext.currentWindowGlobal.innerWindowId,
                            stored:SessionStore.getCustomTabValue(t,"uc-split-return-state")};
                    """)
                    unsplit = result["unsplit"]
                    result["passed"] = result["passed"] and (
                        unsplit["pinned"] == before["pinned"] and
                        unsplit["essential"] == before["essential"] and
                        unsplit["context"] == before["context"] and
                        unsplit["inner"] == before["inner"] and
                        not unsplit["split"] and not unsplit["stored"]
                    )
            except Exception as e:
                result["passed"] = False
                result["error"] = str(e)
                chrome()
            print(name, "PASS" if result["passed"] else "FAIL", json.dumps(result), flush=True)
            args.report.write_text(json.dumps(report, indent=2) + "\n")
        if not args.case:
            for kind in ["normal", "pinned", "essential"]:
                name = f"{kind}_repeated_reload_close"
                result = report["cases"][name] = {}
                try:
                    before = result["before"] = setup(name, kind)
                    counts = COUNTS.copy()
                    for count in range(1, 4):
                        m.js("gBrowser.selectedTab=window.__splitProbeSource;return true;")
                        click("plain")
                        wait(f"gZenViewSplitter._data.some(g=>g.tabs.includes(window.__splitProbeSource) && g.tabs.length==={count+1})")
                    tabs_before = m.js("return [...gZenWorkspaces.allStoredTabs].map(t=>t.id).sort();")
                    m.js("gBrowser.selectedTab=window.__splitProbeSource;return true;")
                    click("plain")
                    time.sleep(.3)
                    result["limitRespected"] = tabs_before == m.js("return [...gZenWorkspaces.allStoredTabs].map(t=>t.id).sort();")
                    result["hotReload"] = m.async_js("""
                        const before=[...gZenWorkspaces.allStoredTabs].map(t=>[t.id,t.linkedBrowser?.browsingContext?.id]);
                        // Simulate restoration with only the persisted session value.
                        window.__splitProbeSource.removeAttribute("uc-split-return-state");
                        Services.scriptloader.loadSubScriptWithOptions(
                            "chrome://sine/content/alt-click-split-view/alt-click-split-view.uc.js",
                            {target:window,ignoreCache:true});
                        await AltClickSplitView.ready;
                        return JSON.stringify(before)===JSON.stringify(
                            [...gZenWorkspaces.allStoredTabs].map(t=>[t.id,t.linkedBrowser?.browsingContext?.id])) &&
                            gZenViewSplitter._data.some(g=>g.tabs.includes(window.__splitProbeSource) && g.tabs.length===4);
                    """)
                    result["restored"] = m.async_js("""
                        const source=window.__splitProbeSource;
                        const group=gZenViewSplitter._data.find(g=>g.tabs.includes(source));
                        for(const tab of [...group.tabs].filter(t=>t!==source))
                            gBrowser.removeTab(tab,{animate:false,skipPermitUnload:true});
                        await new Promise(r=>setTimeout(r,100));
                        return {split:!!source.splitView,pinned:source.pinned,
                            essential:source.hasAttribute("zen-essential"),
                            context:source.linkedBrowser.browsingContext.id,
                            inner:source.linkedBrowser.browsingContext.currentWindowGlobal.innerWindowId,
                            stored:SessionStore.getCustomTabValue(source,"uc-split-return-state")};
                    """)
                    restored = result["restored"]
                    result["requests"] = dict(COUNTS - counts)
                    result["passed"] = (
                        result["limitRespected"] and result["hotReload"] and
                        restored["context"] == before["context"] and restored["inner"] == before["inner"] and
                        restored["pinned"] == before["pinned"] and restored["essential"] == before["essential"] and
                        not restored["split"] and not restored["stored"] and
                        not result["requests"].get(f"/source/{name}")
                    )
                except Exception as e:
                    result["passed"] = False
                    result["error"] = str(e)
                    chrome()
                print(name, "PASS" if result["passed"] else "FAIL", json.dumps(result), flush=True)
                args.report.write_text(json.dumps(report, indent=2) + "\n")
        report["passed"] = all(r["passed"] for r in report["cases"].values())
    finally:
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        m.close()
        server.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--port", type=int, default=2832)
    parser.add_argument("--case", action="append")
    run(parser.parse_args())
