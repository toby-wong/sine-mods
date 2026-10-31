"""Exercise real link clicks in an explicitly selected disposable Zen profile."""

import argparse
import base64
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit

from runtime import Marionette


REQUESTS = Counter()
PAGE = b"""<!doctype html><meta charset="utf-8"><title>Auto Glance test</title>
<style>body{font:17px system-ui;margin:40px;background:#fafbf8;color:#243127}
a,button,input{display:block;margin:18px 0}input{padding:8px}</style>
<h1>Auto Glance</h1><input id="draft" placeholder="An unfinished draft">
<a id="blank" href="/target?blank" target="_blank">Automatic new-tab link</a>
<a id="noopener" href="/target?noopener" target="_blank" rel="noopener noreferrer">No-referrer link</a>
<a id="plain" href="/target?plain">Normal link for modified clicks</a>
<a id="scriptlink" href="/target?scriptlink" onclick="event.preventDefault();window.open(this.href,'_blank')">Scripted link</a>
<a id="spalink" href="/target?spalink" onclick="event.preventDefault();history.pushState({},'',this.href)">Router link</a>
<div contenteditable="true">
  <a id="editable" href="/target?editable" onclick="event.preventDefault();window.open(this.href,'_blank')">Link in an editable document</a>
  <a id="editableblank" href="/target?editableblank" target="_blank" rel="noopener noreferrer">Editable new-tab link</a>
</div>
<button id="script" onclick="window.open('/target?script','_blank')">Script-created tab</button>
<form action="/post-target" method="post" target="_blank">
<input name="value" value="preserve-post-body"><button id="post">Submit into new tab</button></form>
<script>document.addEventListener('DOMContentLoaded',()=>{window.documentMarker=Math.random()})</script>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        REQUESTS[urlsplit(self.path).path] += 1
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(PAGE)))
        self.end_headers()
        self.wfile.write(PAGE)

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.server.post_body = body.decode()
        self.do_GET()

    def log_message(self, *_args):
        pass


def run(args):
    result = {"checks": {}}
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    m = Marionette(args.port)

    def wait(expr, seconds=12):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            value = m.js("return (" + expr + ");")
            if value:
                return value
            time.sleep(.05)
        details = m.js("""
          return {status:window.AutoGlance?.status,error:window.AutoGlance?.error,
            tabs:[...gZenWorkspaces.allStoredTabs].filter(t=>!t.hasAttribute("zen-empty-tab")).map(
              t=>({url:t.linkedBrowser?.currentURI?.spec,glance:t.hasAttribute("zen-glance-tab"),
                owner:!!t.owner,ownerClosing:t.owner?.closing,selected:t.selected,
                context:t.userContextId,ownerContext:t.owner?.userContextId}))};
        """)
        raise AssertionError(f"Timed out: {expr}\n{details}")

    def content():
        m.command("Marionette:SetContext", {"value": "chrome"})
        m.command("WebDriver:SwitchToWindow", {"handle": m.command("WebDriver:GetWindowHandle")})
        m.command("Marionette:SetContext", {"value": "content"})

    def chrome():
        m.command("Marionette:SetContext", {"value": "chrome"})

    def click(identifier, key=None, button=0):
        content()
        point = m.js("""
          const element=document.getElementById(arguments[0]);
          element.scrollIntoView({block:"center"});
          const r=element.getBoundingClientRect();
          return {x:Math.round(r.x+Math.min(r.width/2,80)),y:Math.round(r.y+r.height/2)};
        """, [identifier])
        if key:
            m.command("WebDriver:PerformActions", {"actions": [{
                "type": "key", "id": "modifier", "actions": [{"type": "keyDown", "value": key}],
            }]})
        try:
            m.command("WebDriver:PerformActions", {"actions": [{
                "type": "pointer", "id": "mouse", "parameters": {"pointerType": "mouse"},
                "actions": [
                    {"type": "pointerMove", "origin": "viewport", **point},
                    {"type": "pointerDown", "button": button},
                    {"type": "pointerUp", "button": button},
                ],
            }]})
        finally:
            m.command("WebDriver:ReleaseActions")
            chrome()

    def check(name, detail, passed):
        result["checks"][name] = detail
        if not passed:
            raise AssertionError(f"{name}: {detail}")
        print("PASS", name, flush=True)

    def glance_check(name, action, suffix):
        before = REQUESTS["/target"] + REQUESTS["/post-target"]
        action()
        wait("gBrowser.selectedTab.hasAttribute('zen-glance-tab')")
        wait("gBrowser.selectedBrowser.currentURI.spec === " + json.dumps(base + suffix))
        wait("!gZenGlanceManager._animating && !gZenGlanceManager.animatingOpen")
        details = m.js("""
          const overlay=gZenGlanceManager.overlay, wrapper=gZenGlanceManager.browserWrapper;
          const outer=gBrowser.tabpanels.getBoundingClientRect(), inner=wrapper.getBoundingClientRect();
          const parent=document.querySelector('[glance-id]:not([zen-glance-tab])');
          return {url:gBrowser.selectedBrowser.currentURI.spec,
            container:gBrowser.selectedTab.userContextId,
            private:PrivateBrowsingUtils.isWindowPrivate(window),
            parentContext:parent?.linkedBrowser?.browsingContext.id,
            centerError:Math.abs(inner.x+inner.width/2-outer.x-outer.width/2),
            widthRatio:inner.width/outer.width,
            backgroundFilter:getComputedStyle(parent.linkedBrowser.closest(".browserSidebarContainer")).filter};
        """)
        content()
        wait("document.readyState === 'complete'")
        details.update(m.js("return {cookie:document.cookie,hasOpener:!!window.opener};"))
        chrome()
        details["loads"] = REQUESTS["/target"] + REQUESTS["/post-target"] - before
        check(name, details, details["container"] == source["container"] and
              details["parentContext"] == source["context"] and details["loads"] == 1 and
              "auto-glance-login=source" in details["cookie"] and details["centerError"] < 2 and
              .78 < details["widthRatio"] < .82 and details["backgroundFilter"] == "blur(6px)")
        if name in ("target_blank", "glance_from_split"):
            image = m.command("WebDriver:TakeScreenshot", {"full": False, "scroll": False})
            args.report.with_name(name + ".png").write_bytes(base64.b64decode(image))
        m.async_js("await gZenGlanceManager.closeGlance({hasFocused:true,skipPermitUnload:true});return true;")
        wait("!gBrowser.selectedTab.hasAttribute('zen-glance-tab')")
        content()
        preserved = m.js("return document.getElementById('draft')?.value==='Keep this draft';")
        chrome()
        assert preserved, "The parent draft was lost"
        assert m.js("""
          return getComputedStyle(gBrowser.selectedBrowser.closest(".browserSidebarContainer")).filter;
        """) == "none", "Closing Glance left the parent blurred"
        return details

    def background_check(name, identifier, suffix):
        before_loads = REQUESTS["/target"]
        before = m.js("""
          return {selected:gBrowser.selectedTab.id,
            context:gBrowser.selectedBrowser.browsingContext.id,
            tabs:[...gZenWorkspaces.allStoredTabs].map(t=>t.id)};
        """)
        content()
        draft = m.js("return document.getElementById('draft')?.value;")
        chrome()
        click(identifier, key="\ue03d")
        new_id = wait(
            "[...gZenWorkspaces.allStoredTabs].find(t=>!" + json.dumps(before["tabs"]) +
            ".includes(t.id) && t.linkedBrowser?.currentURI?.spec===" +
            json.dumps(base + suffix) + ")?.id"
        )
        details = m.js("""
          const tab=document.getElementById(arguments[0]);
          return {selected:gBrowser.selectedTab.id,
            sourceContext:gBrowser.selectedBrowser.browsingContext.id,
            newCount:[...gZenWorkspaces.allStoredTabs].filter(t=>!arguments[1].includes(t.id)).length,
            background:!tab.selected,glance:tab.hasAttribute("zen-glance-tab"),
            split:!!tab.splitView,container:tab.userContextId};
        """, [new_id, before["tabs"]])
        content()
        details["draftPreserved"] = m.js("return document.getElementById('draft')?.value;") == draft
        chrome()
        details["loads"] = REQUESTS["/target"] - before_loads
        check(name, details,
              details["selected"] == before["selected"] and
              details["sourceContext"] == before["context"] and
              details["background"] and not details["glance"] and not details["split"] and
              details["newCount"] == 1 and details["loads"] == 1 and
              details["draftPreserved"] and details["container"] == source["container"])
        m.js("gBrowser.removeTab(document.getElementById(arguments[0]),{animate:false,skipPermitUnload:true});return true;", [new_id])

    try:
        actual = m.js('return Services.dirsvc.get("ProfD",Ci.nsIFile).path;')
        if Path(actual).resolve() != args.profile.resolve() or "test-profile" not in args.profile.name:
            raise RuntimeError("Integration tests require the disposable profile.")
        for handle in m.command("WebDriver:GetWindowHandles"):
            m.command("WebDriver:SwitchToWindow", {"handle": handle})
            if m.js("return !window._littleZenInfo && !PrivateBrowsingUtils.isWindowPrivate(window);"):
                main = handle
                break
        m.async_js("""
          Services.scriptloader.loadSubScriptWithOptions(
            "chrome://sine/content/auto-glance/auto-glance.uc.js",{target:window,ignoreCache:true});
          Services.prefs.setBoolPref("uc.auto-glance.enabled",true);
          Services.prefs.setBoolPref("uc.auto-glance.modified-clicks",true);
          Services.prefs.setBoolPref("uc.auto-glance.cmd-click-background",true);
          Services.prefs.setBoolPref("zen.glance.enabled",true);
          Services.prefs.setStringPref("zen.glance.activation-method","shift");
          await new Promise(r=>setTimeout(r,100));
          return true;
        """)
        wait("AutoGlance.status === 'ready'")
        m.js("""
          const t=gBrowser.addTrustedTab(arguments[0],{
            userContextId:gZenWorkspaces.getCurrentSpaceContainerId(),skipRoute:true});
          gBrowser.selectedTab=t;return true;
        """, [base + "/source"])
        content()
        m.command("WebDriver:Navigate", {"url": base + "/source"})
        m.js("document.cookie='auto-glance-login=source; path=/';document.getElementById('draft').value='Keep this draft';return true;")
        chrome()
        source = m.js("return {container:gBrowser.selectedTab.userContextId,context:gBrowser.selectedBrowser.browsingContext.id};")
        glance_check("target_blank", lambda: click("blank"), "/target?blank")
        no_referrer = glance_check("noopener_noreferrer", lambda: click("noopener"), "/target?noopener")
        assert not no_referrer["hasOpener"]
        script = glance_check("script_created_tab", lambda: click("script"), "/target?script")
        assert script["hasOpener"], "window.open lost its opener"
        # The explicit Command override must win even if Firefox's normal
        # new-tab preference would select the new tab.
        old_background = m.js("""
          const old=Services.prefs.getBoolPref("browser.tabs.loadInBackground");
          Services.prefs.setBoolPref("browser.tabs.loadInBackground",false);return old;
        """)
        background_check("cmd_click_background", "plain", "/target?plain")
        background_check("cmd_target_blank_background", "blank", "/target?blank")
        background_check("cmd_noopener_background", "noopener", "/target?noopener")
        background_check("cmd_script_link_background", "scriptlink", "/target?scriptlink")
        background_check("cmd_router_link_background", "spalink", "/target?spalink")
        background_check("cmd_editable_link_background", "editable", "/target?editable")
        background_check("cmd_editable_target_blank_background", "editableblank", "/target?editableblank")
        m.js("gBrowser.pinTab(gBrowser.selectedTab);return true;")
        background_check("cmd_pinned_source_background", "blank", "/target?blank")
        m.js("gBrowser.unpinTab(gBrowser.selectedTab);return true;")
        click("blank")
        wait("gBrowser.selectedTab.hasAttribute('zen-glance-tab') && !gZenGlanceManager._animating")
        background_check("cmd_from_glance_background", "plain", "/target?plain")
        background_check("cmd_editable_from_glance_background", "editable", "/target?editable")
        m.async_js("await gZenGlanceManager.closeGlance({hasFocused:true,skipPermitUnload:true});return true;")
        m.js("Services.prefs.setBoolPref('browser.tabs.loadInBackground',arguments[0]);return true;", [old_background])
        glance_check("middle_click", lambda: click("plain", button=1), "/target?plain")
        glance_check("shift_click_preserved", lambda: click("plain", key="\ue008"), "/target?plain")

        def context_open(command):
            click("plain", button=2)
            wait("!!window.gContextMenu?.onLink")
            m.js("""
              let item=document.getElementById(arguments[0]);
              if(arguments[0]==="context-openlinkintab" && item.hidden)
                item=document.getElementById("context-openlinkincontainertab");
              if(!item || item.hidden) throw Error("The requested menu command is not visible.");
              item.doCommand();
              document.getElementById("contentAreaContextMenu").hidePopup();
              return true;
            """, [command])

        glance_check("context_menu_new_tab", lambda: context_open("context-openlinkintab"), "/target?plain")
        glance_check("post_form", lambda: click("post"), "/post-target")
        check("post_body_preserved", {"body": server.post_body}, server.post_body == "value=preserve-post-body")

        # Expand a real preview; it must become a full tab without another load.
        click("blank")
        wait("gBrowser.selectedTab.hasAttribute('zen-glance-tab') && !gZenGlanceManager._animating")
        before_expand = m.js("return gBrowser.selectedBrowser.browsingContext.id;")
        loads = REQUESTS["/target"]
        m.async_js("await gZenGlanceManager.fullyOpenGlance();return true;")
        wait("!gBrowser.selectedTab.hasAttribute('zen-glance-tab')")
        expanded = m.js("return {context:gBrowser.selectedBrowser.browsingContext.id,url:gBrowser.selectedBrowser.currentURI.spec};")
        check("expand_to_full_tab", expanded, expanded["context"] == before_expand and REQUESTS["/target"] == loads)
        m.js("""
          const t=[...gZenWorkspaces.allStoredTabs].find(t=>t.linkedBrowser?.browsingContext?.id===arguments[0]);
          gBrowser.selectedTab=t;return true;
        """, [source["context"]])

        click("plain", key="\ue00a")
        wait("gBrowser.selectedTab.hasAttribute('split-view')")
        split = m.js("return {split:gBrowser.selectedTab.hasAttribute('split-view'),glance:gBrowser.selectedTab.hasAttribute('zen-glance-tab')};")
        check("option_click_split_preserved", split, split["split"] and not split["glance"])
        m.js("""
          gBrowser.selectedTab=[...gZenWorkspaces.allStoredTabs].find(
            t=>t.linkedBrowser?.browsingContext?.id===arguments[0]);
          gBrowser.selectedBrowser.fullZoom=0.8;
          return true;
        """, [source["context"]])
        background_check("cmd_from_split_background", "plain", "/target?plain")
        background_check("cmd_editable_from_split_background", "editable", "/target?editable")
        glance_check("glance_from_split", lambda: click("blank"), "/target?blank")
        m.js("gBrowser.selectedBrowser.fullZoom=1;return true;")

        # Disable and unload affect future openings, not existing tabs.
        m.js("""
          Services.prefs.setBoolPref("uc.auto-glance.enabled",false);
          gBrowser.selectedTab=[...gZenWorkspaces.allStoredTabs].find(t=>t.linkedBrowser?.browsingContext?.id===arguments[0]);
          return true;
        """, [source["context"]])
        click("blank")
        wait("gBrowser.selectedBrowser.currentURI.spec === " + json.dumps(base + "/target?blank"))
        disabled = m.js("return !gBrowser.selectedTab.hasAttribute('zen-glance-tab');")
        check("disable_restores_new_tabs", {"normalTab": disabled}, disabled)
        restored = m.js("""
          const ids=[...gZenWorkspaces.allStoredTabs].map(t=>t.id);
          AutoGlance.destroy();
          return {removed:!window.AutoGlance,
            stylesRemoved:!document.querySelector('link[href*="/auto-glance/auto-glance.css"]'),
            tabsPreserved:JSON.stringify(ids)===JSON.stringify([...gZenWorkspaces.allStoredTabs].map(t=>t.id))};
        """)
        check("unload_preserves_tabs", restored, all(restored.values()))
        result["passed"] = True
    except Exception as error:
        result["passed"] = False
        result["error"] = str(error)
        raise
    finally:
        args.report.write_text(json.dumps(result, indent=2) + "\n")
        try:
            m.close()
        finally:
            server.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--port", type=int, default=2832)
    run(parser.parse_args())
