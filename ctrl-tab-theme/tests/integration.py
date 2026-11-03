"""Exercise the native Ctrl+Tab panel in a disposable Zen profile."""
import argparse
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "little-zen/scripts"))
from runtime import Marionette


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        title = "A long tab title that should stay inside its preview" if self.path == "/3" else "Page " + self.path[1:]
        page = f"""<!doctype html><title>{title}</title>
          <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'%3E%3Crect width='20' height='20' rx='5' fill='%2366848c'/%3E%3C/svg%3E">
          <style>body{{background:#e1ebe6;color:#254036;font:24px system-ui;padding:32px}}
          article{{background:#fff;border-radius:20px;padding:24px}}</style>
          <article><h1>{title}</h1><p>Native tab preview</p><input value="Keep this draft"></article>""".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page)))
        self.end_headers()
        self.wfile.write(page)

    def log_message(self, *_args):
        pass


def run(args):
    report = {"checks": {}}
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    m = Marionette(args.port)
    loaded = False
    control_held = False

    def wait(expression):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            result = m.js("return (" + expression + ");")
            if result:
                return result
            time.sleep(.05)
        raise AssertionError("Timed out: " + expression)

    def actions(items):
        m.command("WebDriver:PerformActions", {"actions": [{"type": "key", "id": "switcher-keys", "actions": items}]})

    def key(value):
        actions([{"type": "keyDown", "value": value}, {"type": "keyUp", "value": value}])

    def open_panel():
        nonlocal control_held
        m.js("gURLBar.blur();gBrowser.selectedBrowser.focus();return true;")
        actions([{"type": "keyDown", "value": "\ue009"},
                 {"type": "keyDown", "value": "\ue004"},
                 {"type": "keyUp", "value": "\ue004"}])
        control_held = True
        wait("ctrlTab.panel.state === 'open'")

    def release():
        nonlocal control_held
        actions([{"type": "keyUp", "value": "\ue009"}])
        control_held = False

    def cancel():
        key("\ue00c")
        release()
        wait("!ctrlTab.isOpen")

    def measure():
        return m.js("""
          const panel=ctrlTab.panel, content=panel.panelContent;
          const rect=el=>{const r=el.getBoundingClientRect();return {x:r.x,y:r.y,right:r.right,bottom:r.bottom,width:r.width,height:r.height};};
          const css=getComputedStyle(content);
          const canvas=document.createElementNS("http://www.w3.org/1999/xhtml","canvas");
          canvas.width=canvas.height=1;const ctx=canvas.getContext("2d");
          ctx.fillStyle=css.backgroundColor;ctx.fillRect(0,0,1,1);
          return {content:rect(content),background:css.backgroundColor,color:css.color,
            rgba:[...ctx.getImageData(0,0,1,1).data],radius:css.borderRadius,
            selected:ctrlTab.selected?._tab?.id,
            cards:ctrlTab.previews.filter(p=>p.classList.contains("ctrlTab-preview")&&!p.hidden).map(p=>{
              const inner=p.querySelector(".ctrlTab-preview-inner");
              return {card:rect(inner),icon:rect(p._favicon),label:rect(p._label),
                title:p._label.getAttribute("value"),font:getComputedStyle(p._label).fontSize,
                textColor:getComputedStyle(p._label).color,
                selected:p===ctrlTab.selected,border:getComputedStyle(inner).borderTopColor};
            })};
        """)

    def inside(outer, inner):
        return inner["width"] > 0 and inner["height"] > 0 and (
            inner["x"] >= outer["x"] - 1 and inner["right"] <= outer["right"] + 1 and
            inner["y"] >= outer["y"] - 1 and inner["bottom"] <= outer["bottom"] + 1)

    def check_layout(name, *, opacity=245, size=14):
        result = measure()
        report["checks"][name] = result
        assert result["rgba"][3] == opacity and result["radius"] == "20px", result
        assert result["cards"], result
        for card in result["cards"]:
            assert inside(result["content"], card["card"]), card
            assert inside(card["card"], card["label"]), card
            assert inside(card["card"], card["icon"]), card
            assert card["font"] == f"{size}px" and card["textColor"] == result["color"], card
            if card["selected"]:
                assert card["border"] == result["color"], card
        print("PASS", name, flush=True)

    def screenshot(name):
        image = m.command("WebDriver:TakeScreenshot", {"full": False, "scroll": False})
        args.report.with_name(name + ".png").write_bytes(base64.b64decode(image))

    def check_sine():
        mods = args.profile / "chrome/sine-mods"
        registry = mods / "mods.json"
        original = registry.read_bytes()
        metadata = json.loads(original)
        target = mods / "ctrl-tab-theme"
        target.mkdir(exist_ok=True)
        for name in ("theme.json", "preferences.json"):
            (target / name).write_bytes((ROOT / "ctrl-tab-theme" / name).read_bytes())
        theme = json.loads((target / "theme.json").read_text())
        metadata[theme["id"]] = {**theme, "enabled": True, "no-updates": True,
                                 "style": {"chrome": "", "content": ""}}
        try:
            registry.write_text(json.dumps(metadata))
            m.js("""
              window.__switcherPage=gBrowser.selectedTab;
              window.__switcherSettings=gBrowser.addTrustedTab("about:preferences#sineMods",{skipRoute:true});
              gBrowser.selectedTab=__switcherSettings;
              return true;
            """)
            wait("__switcherSettings.linkedBrowser.contentDocument?.querySelector('#uc-ctrl-tab-opacity menulist')")
            m.js("""
              const doc=__switcherSettings.linkedBrowser.contentDocument;
              doc.defaultView.gotoPref("paneSineMods");
              doc.querySelector('[mod-id="ctrl-tab-theme"] .sineItemConfigureButton').click();
              return true;
            """)
            for prop, value in [("opacity", "100%"), ("text-size", "16px")]:
                m.js("""
                  const doc=__switcherSettings.linkedBrowser.contentDocument;
                  const control=doc.querySelector("#uc-ctrl-tab-"+arguments[0]+" menulist");
                  control.value=arguments[1];
                  control.dispatchEvent(new doc.defaultView.Event("command",{bubbles:true}));
                  return true;
                """, [prop, value])
            wait("getComputedStyle(document.documentElement).getPropertyValue('--uc-ctrl-tab-opacity').trim() === '100%'")
            wait("getComputedStyle(document.documentElement).getPropertyValue('--uc-ctrl-tab-text-size').trim() === '16px'")
            m.js("gBrowser.selectedTab=__switcherPage;return true;")
            open_panel()
            check_layout("sine_settings_apply", opacity=255, size=16)
            cancel()
            m.js("""
              Services.prefs.setStringPref("uc.ctrl-tab.opacity","96%");
              Services.prefs.setStringPref("uc.ctrl-tab.text-size","14px");
              gBrowser.removeTab(__switcherSettings);
              return true;
            """)
            legacy = [key for key, mod in metadata.items() if mod.get("name") == "Better CtrlTab Panel"]
            for key in legacy:
                metadata[key]["enabled"] = False
            registry.write_text(json.dumps(metadata))
            m.async_js('await ChromeUtils.importESModule("chrome://userscripts/content/services/stylesheets.sys.mjs").default.rebuildMods(true);return true;')
            wait("getComputedStyle(document.documentElement).getPropertyValue('--uc-ctrl-tab-text-size').trim() === '14px'")
            open_panel()
            check_layout("without_better_ctrl_tab")
            cancel()
        finally:
            m.js("""
              Services.prefs.setStringPref("uc.ctrl-tab.opacity","96%");
              Services.prefs.setStringPref("uc.ctrl-tab.text-size","14px");
              if(window.__switcherSettings?.isConnected)gBrowser.removeTab(__switcherSettings);
              return true;
            """)
            registry.write_bytes(original)
            m.async_js('await ChromeUtils.importESModule("chrome://userscripts/content/services/stylesheets.sys.mjs").default.rebuildMods(true);return true;')

    try:
        actual = m.js('return Services.dirsvc.get("ProfD",Ci.nsIFile).path;')
        if Path(actual).resolve() != args.profile.resolve() or "test-profile" not in args.profile.name:
            raise RuntimeError("Refusing to test an everyday profile")
        m.command("WebDriver:SetWindowRect", {"x": 0, "y": 0, "width": 1600, "height": 1000})
        m.js("""
          Services.prefs.setBoolPref("browser.ctrlTab.sortByRecentlyUsed",true);
          Services.prefs.setIntPref("browser.ctrlTab.maxPreviews",7);
          window.__switcherMethods=[ctrlTab.open,ctrlTab.close,ctrlTab.advanceFocus,ctrlTab.pick];
          window.__switcherTabs=Array.from({length:10},(_,i)=>gBrowser.addTrustedTab(arguments[0]+"/"+i,{skipRoute:true}));
          return true;
        """, [base])
        for i in range(10):
            m.js("gBrowser.selectedTab=__switcherTabs[arguments[0]];return true;", [i])
            wait("!gBrowser.selectedBrowser.webProgress.isLoadingDocument && gBrowser.selectedBrowser.currentURI.spec.startsWith(" + json.dumps(base) + ")")
        m.js("window.__switcherDocuments=__switcherTabs.map(t=>t.linkedBrowser.browsingContext.currentWindowGlobal.innerWindowId);return true;")
        open_panel()
        report["baseline"] = measure()
        screenshot("ctrl-tab-before")
        cancel()
        m.js("""
          window.__switcherURI=Services.io.newURI(arguments[0]);
          window.windowUtils.loadSheet(__switcherURI,window.windowUtils.USER_SHEET);
          return true;
        """, [(ROOT / "ctrl-tab-theme/ctrl-tab.css").as_uri() + "?test=" + str(time.time_ns())])
        loaded = True
        order = m.js("return ctrlTab.tabList.map(t=>t.id);")
        current = m.js("return gBrowser.selectedTab.id;")
        open_panel()
        check_layout("themed_panel")
        assert m.js("return ctrlTab.selected._tab.id;") == order[1]
        key("\ue004")
        assert m.js("return ctrlTab.selected._tab.id;") == order[2]
        actions([{"type": "keyDown", "value": "\ue008"}])
        key("\ue004")
        actions([{"type": "keyUp", "value": "\ue008"}])
        assert m.js("return ctrlTab.selected._tab.id;") == order[1]
        report["checks"]["forward_and_reverse"] = True
        cancel()
        assert m.js("return gBrowser.selectedTab.id;") == current
        report["checks"]["escape_keeps_current_tab"] = True
        open_panel()
        expected = m.js("return ctrlTab.selected._tab.id;")
        release()
        wait("!ctrlTab.isOpen && gBrowser.selectedTab.id === " + json.dumps(expected))
        report["checks"]["release_selects_tab"] = True

        for name, color, ink in [("light", "#dce8da", "rgb(0, 0, 0)"),
                                  ("dark", "#24352c", "rgb(255, 255, 255)")]:
            m.js("document.documentElement.style.setProperty('--zen-colors-secondary',arguments[0],'important');return true;", [color])
            open_panel()
            wait("getComputedStyle(ctrlTab.panel.panelContent).color === " + json.dumps(ink))
            check_layout(name + "_theme")
            screenshot("ctrl-tab-" + name)
            cancel()

        m.js("Services.prefs.setIntPref('browser.ctrlTab.maxPreviews',10);return true;")
        open_panel()
        check_layout("two_rows")
        assert len(measure()["cards"]) == 10
        screenshot("ctrl-tab-two-rows")
        cancel()
        m.js("Services.prefs.setIntPref('browser.ctrlTab.maxPreviews',7);return true;")
        check_sine()

        report["checks"]["native_methods_and_documents_preserved"] = m.js("""
          return __switcherMethods.every((fn,i)=>fn===[ctrlTab.open,ctrlTab.close,ctrlTab.advanceFocus,ctrlTab.pick][i]) &&
            __switcherDocuments.every((id,i)=>id===__switcherTabs[i].linkedBrowser.browsingContext.currentWindowGlobal.innerWindowId);
        """)
        assert report["checks"]["native_methods_and_documents_preserved"]
        m.js("document.documentElement.style.removeProperty('--zen-colors-secondary');window.windowUtils.removeSheet(__switcherURI,window.windowUtils.USER_SHEET);return true;")
        loaded = False
        open_panel()
        report["checks"]["unload_restores_appearance"] = measure()["background"] == report["baseline"]["background"]
        assert report["checks"]["unload_restores_appearance"]
        cancel()
        report["passed"] = True
    except Exception as error:
        report["passed"] = False
        report["error"] = str(error)
        raise
    finally:
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        if control_held:
            cancel()
        if loaded:
            m.js("window.windowUtils.removeSheet(__switcherURI,window.windowUtils.USER_SHEET);return true;")
        m.js("document.documentElement.style.removeProperty('--zen-colors-secondary');return true;")
        m.close()
        server.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--port", default=2833, type=int)
    parser.add_argument("--report", required=True, type=Path)
    run(parser.parse_args())
