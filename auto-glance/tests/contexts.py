"""Verify Auto Glance in private and Little Zen windows."""

import argparse
import json
from pathlib import Path
import threading
import time

from integration import Handler, ThreadingHTTPServer
from runtime import Marionette


def run(args):
    result = {}
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    m = Marionette(args.port)
    saved_prefs = None
    main = None

    def background_click(name, handle):
        m.command("Marionette:SetContext", {"value": "chrome"})
        m.command("WebDriver:SwitchToWindow", {"handle": handle})
        before = m.js("""
          return {tab:gBrowser.selectedTab.id,context:gBrowser.selectedBrowser.browsingContext.id,
            ids:[...gZenWorkspaces.allStoredTabs].map(t=>t.id),
            container:gBrowser.selectedTab.userContextId};
        """)
        m.command("Marionette:SetContext", {"value": "content"})
        point = m.js("""
          document.getElementById('draft').value='Keep this draft';
          const link=document.getElementById('blank');link.scrollIntoView({block:'center'});
          const r=link.getBoundingClientRect();return {x:Math.round(r.x+20),y:Math.round(r.y+r.height/2)};
        """)
        try:
            m.command("WebDriver:PerformActions", {"actions": [
                {"type": "key", "id": "background-modifier",
                 "actions": [{"type": "keyDown", "value": accelerator}]},
                {"type": "pointer", "id": "background-mouse", "parameters": {"pointerType": "mouse"},
                 "actions": [{"type": "pointerMove", "origin": "viewport", **point},
                             {"type": "pointerDown", "button": 0},
                             {"type": "pointerUp", "button": 0}]},
            ]})
        finally:
            m.command("WebDriver:ReleaseActions")
            m.command("Marionette:SetContext", {"value": "chrome"})
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            data = m.js("""
              const created=[...gZenWorkspaces.allStoredTabs].filter(t=>!arguments[0].ids.includes(t.id));
              return {ids:created.map(t=>t.id),loaded:created.some(t=>t.linkedBrowser?.currentURI?.spec===arguments[1]),
                background:created.every(t=>!t.selected && !t.hasAttribute('zen-glance-tab') && !t.splitView),
                containers:created.map(t=>t.userContextId),selected:gBrowser.selectedTab.id,
                context:gBrowser.selectedBrowser.browsingContext.id};
            """, [before, base + "/target?blank"])
            if data["loaded"]:
                break
            time.sleep(.05)
        assert data["loaded"] and len(data["ids"]) == 1 and data["background"], data
        assert data["selected"] == before["tab"] and data["context"] == before["context"], data
        assert data["containers"] == [before["container"]], data
        m.command("WebDriver:SwitchToWindow", {"handle": handle})
        m.command("Marionette:SetContext", {"value": "content"})
        assert m.js("return document.getElementById('draft').value==='Keep this draft';")
        m.command("Marionette:SetContext", {"value": "chrome"})
        m.js("gBrowser.removeTab(document.getElementById(arguments[0]),{animate:false,skipPermitUnload:true});",
             [data["ids"][0]])
        result[name] = data
        print("PASS", name, flush=True)

    try:
        actual = m.js('return Services.dirsvc.get("ProfD",Ci.nsIFile).path;')
        if Path(actual).resolve() != args.profile.resolve() or "test-profile" not in args.profile.name:
            raise RuntimeError("Context tests require the disposable profile.")
        accelerator = "\ue03d" if m.js("return Services.appinfo.OS;") == "Darwin" else "\ue009"
        for handle in m.command("WebDriver:GetWindowHandles"):
            m.command("WebDriver:SwitchToWindow", {"handle": handle})
            if m.js("return !window._littleZenInfo && !PrivateBrowsingUtils.isWindowPrivate(window);"):
                main = handle
                break
        assert main, "No regular test window"
        m.js("""
          for(const w of Services.wm.getEnumerator("navigator:browser"))
            if(w!==window && (w._littleZenInfo || PrivateBrowsingUtils.isWindowPrivate(w)))w.close();
          return true;
        """)
        saved_prefs = m.js("""
          return ['uc.auto-glance.enabled','uc.auto-glance.cmd-click-background',
            'browser.tabs.loadInBackground','zen.glance.activation-method'].map(key=>({
              key,user:Services.prefs.prefHasUserValue(key),
              value:key==='zen.glance.activation-method' ?
                Services.prefs.getStringPref(key,'ctrl') : Services.prefs.getBoolPref(key,true)}));
        """)
        m.js("""
          Services.prefs.setBoolPref("uc.auto-glance.enabled",true);
          Services.prefs.setBoolPref("uc.auto-glance.cmd-click-background",true);
          Services.prefs.setBoolPref("browser.tabs.loadInBackground",false);
          Services.prefs.setStringPref("zen.glance.activation-method",
            Services.appinfo.OS==="Darwin" ? "meta" : "ctrl");
          return true;
        """)
        for kind in ["private", "little"]:
            m.command("Marionette:SetContext", {"value": "chrome"})
            m.command("WebDriver:SwitchToWindow", {"handle": main})
            before = set(m.command("WebDriver:GetWindowHandles"))
            m.js("OpenBrowserWindow({private:true});return true;" if kind == "private"
                 else "LittleZen.open();return true;")
            deadline = time.monotonic() + 12
            child = None
            while time.monotonic() < deadline:
                new = set(m.command("WebDriver:GetWindowHandles")) - before
                if new:
                    child = new.pop()
                    break
                time.sleep(.05)
            assert child, kind
            m.command("WebDriver:SwitchToWindow", {"handle": child})
            status = m.async_js("""
              const end=Date.now()+10000;
              while(window.AutoGlance?.status!=="ready" && Date.now()<end)
                await new Promise(r=>setTimeout(r,50));
              return window.AutoGlance?.status;
            """)
            assert status == "ready", status
            m.js("""
              const tab=gBrowser.addTrustedTab(arguments[0],{
                userContextId:gZenWorkspaces.getCurrentSpaceContainerId(),skipRoute:true});
              gBrowser.selectedTab=tab;return true;
            """, [base + "/source"])
            m.command("WebDriver:SwitchToWindow", {"handle": child})
            m.command("Marionette:SetContext", {"value": "content"})
            m.command("WebDriver:Navigate", {"url": base + "/source"})
            m.command("Marionette:SetContext", {"value": "chrome"})
            source = m.js("""
              return {context:gBrowser.selectedBrowser.browsingContext.id,
                container:gBrowser.selectedTab.userContextId,
                private:PrivateBrowsingUtils.isWindowPrivate(window)};
            """)
            background_click(kind + "_background", child)
            m.js("""
              const b=gBrowser.selectedBrowser;
              openLinkIn(arguments[0],"tab",{
                triggeringPrincipal:b.contentPrincipal,originPrincipal:b.contentPrincipal,
                openerBrowser:b,userContextId:b.browsingContext.originAttributes.userContextId});
              return true;
            """, [base + "/target"])
            data = m.async_js("""
              const end=Date.now()+10000;
              while((!gBrowser.selectedTab.hasAttribute("zen-glance-tab") ||
                gBrowser.selectedBrowser.currentURI.spec!==arguments[0] ||
                gZenGlanceManager._animating) && Date.now()<end)
                  await new Promise(r=>setTimeout(r,50));
              return {glance:gBrowser.selectedTab.hasAttribute("zen-glance-tab"),
                private:PrivateBrowsingUtils.isWindowPrivate(window),
                container:gBrowser.selectedTab.userContextId,little:!!window._littleZenInfo,
                url:gBrowser.selectedBrowser.currentURI.spec};
            """, [base + "/target"])
            assert data["glance"] and data["container"] == source["container"], data
            assert data["private"] == (kind == "private") and data["little"] == (kind == "little"), data
            result[kind] = data
            print("PASS", kind, flush=True)
            background_click(kind + "_preview_background", child)
            m.async_js("await gZenGlanceManager.closeGlance({hasFocused:true,skipPermitUnload:true});return true;")
            m.js("window.close();")
        result["passed"] = True
    except Exception as error:
        result["passed"] = False
        result["error"] = str(error)
        raise
    finally:
        args.report.write_text(json.dumps(result, indent=2) + "\n")
        try:
            if saved_prefs is not None:
                m.command("Marionette:SetContext", {"value": "chrome"})
                m.command("WebDriver:SwitchToWindow", {"handle": main})
                m.js("""
                  for(const {key,user,value} of arguments[0]) {
                    if(!user)Services.prefs.clearUserPref(key);
                    else if(typeof value==='boolean')Services.prefs.setBoolPref(key,value);
                    else Services.prefs.setStringPref(key,value);
                  }
                """, [saved_prefs])
        finally:
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
