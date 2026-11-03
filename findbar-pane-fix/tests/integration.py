"""Find-bar geometry and keyboard checks in a disposable Zen profile."""
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
        page = b"""<!doctype html><style>
          body{font:22px system-ui;background:repeating-linear-gradient(30deg,#cde8ed 0 35px,#fff 35px 70px)}
          p{padding:20px;background:#fff9}input{font:inherit}</style>
          <h1>Find-bar test page</h1><input id="draft" value="Keep this draft">
          <p>First needle</p><p>Second needle</p><p>Third needle</p>
          <a id="preview" href="/preview" target="_blank">Open preview</a>"""
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
    fixed = False
    clipboard = None
    original_color = None

    def wait(expression):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            result = m.js("return (" + expression + ");")
            if result:
                return result
            time.sleep(.05)
        raise AssertionError("Timed out: " + expression)

    def key(value, accelerator=False, shift=False):
        modifier = "\ue03d" if m.js("return Services.appinfo.OS==='Darwin';") else "\ue009"
        actions = []
        if accelerator:
            actions.append({"type": "keyDown", "value": modifier})
        if shift:
            actions.append({"type": "keyDown", "value": "\ue008"})
        actions += [{"type": "keyDown", "value": value}, {"type": "keyUp", "value": value}]
        if shift:
            actions.append({"type": "keyUp", "value": "\ue008"})
        if accelerator:
            actions.append({"type": "keyUp", "value": modifier})
        m.command("WebDriver:PerformActions", {"actions": [{"type": "key", "id": "find-keyboard", "actions": actions}]})

    def open_find():
        m.async_js("window.__findProbe=await gBrowser.getFindBar(gBrowser.selectedTab);return true;")
        m.command("WebDriver:SwitchToWindow", {"handle": m.command("WebDriver:GetWindowHandle")})
        m.js("window.__findProbe.close();gURLBar.blur();gBrowser.selectedBrowser.focus();return true;")
        key("f", accelerator=True)
        wait("!window.__findProbe.hidden")
        time.sleep(.4)

    def measure():
        return m.js("""
          const bar=window.__findProbe, pane=bar.closest('.browserContainer');
          const box=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom}};
          const css=getComputedStyle(bar);
          const canvas=document.createElementNS("http://www.w3.org/1999/xhtml","canvas");
          canvas.width=canvas.height=1;
          const context=canvas.getContext("2d");
          context.fillStyle=css.backgroundColor;context.fillRect(0,0,1,1);
          const label=bar.querySelector(".findbar-case-sensitive .checkbox-label") ||
            bar.querySelector(".findbar-case-sensitive");
          return {bar:box(bar),pane:box(pane),input:box(bar._findField),
            close:box(bar.querySelector('.findbar-closebutton')),background:css.backgroundColor,
            backgroundRGBA:Array.from(context.getImageData(0,0,1,1).data),
            color:css.color,labelColor:getComputedStyle(label).color,
            inputColor:getComputedStyle(bar._findField).color,
            buttonColor:getComputedStyle(bar.querySelector('.findbar-closebutton')).color,
            labelFont:getComputedStyle(label).fontSize,inputFont:getComputedStyle(bar._findField).fontSize,
            controls:[...bar.querySelectorAll(".findbar-container > checkbox, .findbar-label")]
              .map(box).filter(rect=>rect.width && rect.height),
            backdropFilter:css.backdropFilter,position:css.position,zoom:Number(css.zoom),hidden:bar.hidden,
            scrollWidth:bar.scrollWidth,clientWidth:bar.clientWidth,
            focused:document.activeElement===bar._findField};
        """)

    def visible_inside(outer, inner):
        return inner["width"] > 0 and inner["height"] > 0 and (
            inner["x"] >= outer["x"] - 1 and inner["right"] <= outer["right"] + 1 and
            inner["y"] >= outer["y"] - 1 and inner["bottom"] <= outer["bottom"] + 1
        )

    def check_layout(name, *, opacity=245, size=14, blur=8, zoom=1):
        result = measure()
        report["checks"][name] = result
        assert visible_inside(result["pane"], result["bar"]), (name, result)
        assert visible_inside(result["bar"], result["input"]), (name, result)
        assert visible_inside(result["bar"], result["close"]), (name, result)
        assert all(visible_inside(result["bar"], control) for control in result["controls"]), (name, result)
        assert result["scrollWidth"] <= result["clientWidth"] + 1, (name, result)
        assert result["backdropFilter"] == f"blur({blur}px)", result
        assert result["backgroundRGBA"][3] == opacity, result
        assert result["color"] in ("rgb(0, 0, 0)", "rgb(255, 255, 255)"), result
        assert result["labelColor"] == result["buttonColor"] == result["color"], result
        assert result["labelFont"] == f"{size}px" and result["inputFont"] == f"{size + 1}px", result
        assert abs(result["zoom"] - zoom) < .001, result
        assert result["focused"], (name, result)
        print("PASS", name, flush=True)

    def screenshot(name):
        image = m.command("WebDriver:TakeScreenshot", {"full": False, "scroll": False})
        args.report.with_name(name + ".png").write_bytes(base64.b64decode(image))

    def check_settings():
        """Exercise the real Sine Configure controls, not direct preference writes."""
        mods = args.profile / "chrome/sine-mods"
        registry = mods / "mods.json"
        preferences_file = mods / "findbar-pane-fix/preferences.json"
        original_registry = registry.read_bytes()
        original_preferences = preferences_file.read_bytes()
        site_zoom_pref = m.js("""return {
          hasValue:Services.prefs.prefHasUserValue("browser.zoom.siteSpecific"),
          value:Services.prefs.getBoolPref("browser.zoom.siteSpecific")
        };""")
        preferences = json.loads((ROOT / "findbar-pane-fix/preferences.json").read_text())
        defaults = {pref["property"]: pref["defaultValue"] for pref in preferences if "property" in pref}
        metadata = json.loads(original_registry)
        theme = json.loads((ROOT / "findbar-pane-fix/theme.json").read_text())
        # Keep CSS under this test's explicit load/unload control.
        metadata[theme["id"]] = {**theme, "enabled": True, "no-updates": True,
                                 "style": {"chrome": "", "content": ""}}
        try:
            preferences_file.write_text(json.dumps(preferences))
            registry.write_text(json.dumps(metadata))
            m.async_js("""
              window.__findSettingsPage=gBrowser.selectedTab;
              window.__findSettingsDocument=__findSettingsPage.linkedBrowser.browsingContext.currentWindowGlobal.innerWindowId;
              window.__findSettingsTab=gBrowser.addTrustedTab("about:preferences#sineMods",{skipRoute:true});
              gBrowser.selectedTab=__findSettingsTab;
              return true;
            """)
            wait("window.__findSettingsTab.linkedBrowser.contentDocument?.querySelector('#uc-findbar-opacity menulist')")
            m.js("""
              const doc=__findSettingsTab.linkedBrowser.contentDocument;
              doc.defaultView.gotoPref("paneSineMods");
              doc.querySelector('[mod-id="findbar-pane-fix"] .sineItemConfigureButton').click();
              return true;
            """)
            wait("__findSettingsTab.linkedBrowser.contentDocument.querySelector('[mod-id=\"findbar-pane-fix\"] dialog').getBoundingClientRect().height > 0")
            wait("""(() => {
              const doc=__findSettingsTab.linkedBrowser.contentDocument;
              return doc.defaultView.getComputedStyle(doc.querySelector('[mod-id="findbar-pane-fix"] dialog')).opacity === "1";
            })()""")
            screenshot("findbar-settings")

            def change(property_name, value, expression):
                m.js("""
                  gBrowser.selectedTab=__findSettingsTab;
                  const doc=__findSettingsTab.linkedBrowser.contentDocument;
                  const row=doc.getElementById(arguments[0].replaceAll(".","-"));
                  if(typeof arguments[1]==="boolean"){
                    if(Services.prefs.getBoolPref(arguments[0],false)!==arguments[1])row.click();
                    return true;
                  }
                  const control=row.querySelector("menulist,input");
                  control.value=arguments[1];
                  control.dispatchEvent(new doc.defaultView.Event(control.localName==="input"?"change":"command",{bubbles:true}));
                  return true;
                """, [property_name, value])
                getter = "getBoolPref" if isinstance(value, bool) else "getStringPref"
                fallback = ", false" if isinstance(value, bool) else ""
                wait("Services.prefs." + getter + "(" + json.dumps(property_name) + fallback + ") === " + json.dumps(value))
                wait(expression)
                m.js("gBrowser.selectedTab=__findSettingsPage;__findProbe._findField.focus();return true;")

            change("uc.findbar.opacity", "70%", "getComputedStyle(__findProbe).backgroundColor.includes('0.7')")
            change("uc.findbar.text-size", "20px", "getComputedStyle(__findProbe).fontSize === '20px'")
            change("uc.findbar.blur", "0px", "getComputedStyle(__findProbe).backdropFilter === 'blur(0px)'")
            open_find()
            check_layout("configured_large_text", opacity=179, size=20, blur=0)
            m.async_js("await gZenViewSplitter.splitTabs(__findTabs,undefined,1);return true;")
            open_find()
            check_layout("configured_narrow_split", opacity=179, size=20, blur=0)
            screenshot("findbar-configured-narrow")

            change("uc.findbar.text-color", "white", "getComputedStyle(__findProbe).color === 'rgb(255, 255, 255)'")
            report["checks"]["configured_white"] = measure()["inputColor"] == "rgb(255, 255, 255)"
            change("uc.findbar.text-color", "black", "getComputedStyle(__findProbe).color === 'rgb(0, 0, 0)'")
            report["checks"]["configured_black"] = measure()["inputColor"] == "rgb(0, 0, 0)"
            assert report["checks"]["configured_white"] and report["checks"]["configured_black"]

            change("uc.findbar.background", "custom", "document.querySelector('#theme-Find-Bar-Pane-Fix')?.getAttribute('uc-findbar-background') === 'custom'")
            change("uc.findbar.custom-background", "#f6efd7", "getComputedStyle(__findProbe).getPropertyValue('--uc-findbar-custom-background').trim() === 'rgb(246, 239, 215)'")
            change("uc.findbar.text-color", "auto", "getComputedStyle(__findProbe).color === 'rgb(0, 0, 0)'")
            light = measure()
            assert all(abs(a - b) <= 1 for a, b in zip(light["backgroundRGBA"][:3], [246, 239, 215])), light
            report["checks"]["configured_custom_light"] = light["color"]
            change("uc.findbar.custom-background", "#20242a80", "getComputedStyle(__findProbe).color === 'rgb(255, 255, 255)'")
            dark = measure()
            assert dark["backgroundRGBA"][3] == 179, dark
            report["checks"]["configured_custom_dark"] = dark["color"]
            change("uc.findbar.custom-background", "not-a-colour", "getComputedStyle(__findProbe).getPropertyValue('--uc-findbar-custom-background').trim() === 'rgb(82, 95, 46)'")
            report["checks"]["invalid_colour_fallback"] = measure()["color"] == "rgb(255, 255, 255)"
            assert report["checks"]["invalid_colour_fallback"]
            for name, value in defaults.items():
                change(name, value, "document.querySelector('#theme-Find-Bar-Pane-Fix') !== null")
            wait("getComputedStyle(__findProbe).fontSize === '14px' && getComputedStyle(__findProbe).backgroundColor.includes('0.96')")
            open_find()
            check_layout("configured_defaults_restored")

            change("uc.findbar.text-size", "8px", "getComputedStyle(__findProbe).fontSize === '8px'")
            open_find()
            check_layout("eight_pixel_text", size=8)
            # Both test pages share a host. Use native per-tab zoom so changing
            # one pane does not overwrite the other pane's saved site zoom.
            m.js('Services.prefs.setBoolPref("browser.zoom.siteSpecific",false);return true;')
            change("uc.findbar.scale-with-page-zoom", True,
                   "Services.prefs.getBoolPref('uc.findbar.scale-with-page-zoom')")
            m.js("FullZoom.setZoom(.8,__findSettingsPage.linkedBrowser);return true;")
            wait("Number(getComputedStyle(__findProbe).zoom) === .8")
            open_find()
            check_layout("zoom_eighty_percent", size=8, zoom=.8)
            m.js("FullZoom.setZoom(1.5,__findSettingsPage.linkedBrowser);return true;")
            wait("Number(getComputedStyle(__findProbe).zoom) === 1.5")
            open_find()
            check_layout("zoom_one_fifty_percent", size=8, zoom=1.5)
            screenshot("findbar-zoomed")
            m.async_js("""
              FullZoom.setZoom(1.25,__findTabs[0].linkedBrowser);
              window.__leftZoomBar=await gBrowser.getFindBar(__findTabs[0]);
              return true;
            """)
            wait("Number(getComputedStyle(__leftZoomBar).zoom) === 1.25")
            report["checks"]["independent_pane_zoom"] = m.js("""
              return Number(getComputedStyle(__findProbe).zoom)===1.5 &&
                Number(getComputedStyle(__leftZoomBar).zoom)===1.25;
            """)
            assert report["checks"]["independent_pane_zoom"]
            change("uc.findbar.scale-with-page-zoom", False,
                   "Number(getComputedStyle(__findProbe).zoom) === 1 && Number(getComputedStyle(__leftZoomBar).zoom) === 1")
            report["checks"]["zoom_toggle_restores_fixed_size"] = True
            change("uc.findbar.scale-with-page-zoom", True,
                   "Number(getComputedStyle(__findProbe).zoom) === 1.5")
            m.js("FindbarPageZoom.destroy();return true;")
            report["checks"]["zoom_unload_restores_fixed_size"] = m.js("""
              return Number(getComputedStyle(__findProbe).zoom)===1 &&
                !__findProbe.style.getPropertyValue("--uc-findbar-page-zoom") &&
                !__leftZoomBar.style.getPropertyValue("--uc-findbar-page-zoom");
            """)
            assert report["checks"]["zoom_unload_restores_fixed_size"]
            change("uc.findbar.scale-with-page-zoom", False, "true")
            change("uc.findbar.text-size", "14px", "getComputedStyle(__findProbe).fontSize === '14px'")
            m.js("for(const tab of __findTabs)ZoomManager.setZoomForBrowser(tab.linkedBrowser,1);return true;")
            report["checks"]["settings_preserve_document"] = m.js("""
              return __findSettingsPage.linkedBrowser.browsingContext.currentWindowGlobal.innerWindowId === __findSettingsDocument;
            """)
            assert report["checks"]["settings_preserve_document"]
        finally:
            m.js("""if(arguments[0].hasValue)
              Services.prefs.setBoolPref("browser.zoom.siteSpecific",arguments[0].value);
              else Services.prefs.clearUserPref("browser.zoom.siteSpecific");
              return true;""", [site_zoom_pref])
            m.js("""for(const [name,value] of Object.entries(arguments[0])){
              if(typeof value==="boolean")Services.prefs.setBoolPref(name,value);
              else Services.prefs.setStringPref(name,value);
            }return true;""", [defaults])
            m.js("if(window.__findSettingsTab?.isConnected)gBrowser.removeTab(__findSettingsTab);return true;")
            preferences_file.write_bytes(original_preferences)
            registry.write_bytes(original_registry)
            m.async_js('await ChromeUtils.importESModule("chrome://userscripts/content/services/stylesheets.sys.mjs").default.rebuildMods(false);return true;')

    try:
        actual = m.js('return Services.dirsvc.get("ProfD",Ci.nsIFile).path;')
        if Path(actual).resolve() != args.profile.resolve() or "test-profile" not in args.profile.name:
            raise RuntimeError("Refusing to test an everyday profile")
        m.command("WebDriver:SetWindowRect", {"width": 1300, "height": 900})
        m.async_js("""
          window.__findTabs=['left','right'].map(name=>gBrowser.addTrustedTab(arguments[0]+'/'+name,{skipRoute:true}));
          gBrowser.selectedTab=window.__findTabs[1];
          await gZenViewSplitter.splitTabs(window.__findTabs,undefined,1);
          return true;
        """, [base])
        wait("gBrowser.selectedBrowser.currentURI.spec === " + json.dumps(base + "/right") +
             " && !gBrowser.selectedBrowser.webProgress.isLoadingDocument && gBrowser.selectedTab.splitView")
        open_find()
        clipboard = m.js("return window.__findProbe.browser.finder.clipboardSearchString;")
        report["baseline"] = measure()
        screenshot("findbar-before")
        m.js("""
          window.__findFixURI=Services.io.newURI(arguments[0]);
          window.windowUtils.loadSheet(window.__findFixURI,window.windowUtils.USER_SHEET);
          return true;
        """, [(ROOT / "findbar-pane-fix/findbar.css").as_uri() + "?test=" + str(time.time_ns())])
        fixed = True
        (args.profile / "chrome/sine-mods/findbar-pane-fix/findbar-zoom.uc.js").write_bytes(
            (ROOT / "findbar-pane-fix/findbar-zoom.uc.js").read_bytes())
        m.js("""Services.scriptloader.loadSubScriptWithOptions(
          "chrome://sine/content/findbar-pane-fix/findbar-zoom.uc.js",
          {target:window,ignoreCache:true});return true;""")
        time.sleep(.2)
        check_layout("split_pane")
        screenshot("findbar-after")

        field = m.js("return window.__findProbe._findField;")
        m.command("WebDriver:ElementSendKeys", {
            "id": field["element-6066-11e4-a52e-4f735466cecf"], "text": "needle",
        })
        wait("JSON.parse(window.__findProbe.querySelector('.found-matches').getAttribute('data-l10n-args') || '{}').total === 3")
        found = wait("window.__findProbe.querySelector('.found-matches').getAttribute('value')")
        report["checks"]["find_matches"] = found
        assert "3" in found, found

        original_color = m.js("""
          const style=document.documentElement.style;
          return [style.getPropertyValue("--var-findbar-background-color"),
            style.getPropertyPriority("--var-findbar-background-color")];
        """)
        for name, background, foreground in [
            ("olive", "#6a6a28", "rgb(255, 255, 255)"),
            ("light", "#f6efd7", "rgb(0, 0, 0)"),
            ("dark", "#20242a", "rgb(255, 255, 255)"),
        ]:
            m.js('document.documentElement.style.setProperty("--var-findbar-background-color",arguments[0],"important");return true;', [background])
            wait("getComputedStyle(window.__findProbe).color === " + json.dumps(foreground))
            result = measure()
            assert result["labelColor"] == result["inputColor"] == result["buttonColor"] == foreground, result
            channels = [value / 255 for value in result["backgroundRGBA"][:3]]
            linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
            luminance = sum(a * b for a, b in zip(linear, [.2126, .7152, .0722]))
            ratio = (luminance + .05) / .05 if foreground == "rgb(0, 0, 0)" else 1.05 / (luminance + .05)
            assert ratio >= 4.5, (name, ratio)
            report["checks"]["contrast_" + name] = {"foreground": foreground, "fillContrast": ratio}
            screenshot("findbar-" + name)
        m.js('document.documentElement.style.setProperty("--var-findbar-background-color",arguments[0],arguments[1]);return true;', original_color)
        original_color = None

        key("\ue007")
        wait("JSON.parse(window.__findProbe.querySelector('.found-matches').getAttribute('data-l10n-args') || '{}').current === 2")
        key("\ue007", shift=True)
        wait("JSON.parse(window.__findProbe.querySelector('.found-matches').getAttribute('data-l10n-args') || '{}').current === 1")
        report["checks"]["enter_and_shift_enter"] = True
        key("\ue00c")
        wait("window.__findProbe.hidden")
        report["checks"]["escape_hides_bar"] = m.js("return window.__findProbe.getBoundingClientRect().height===0;")
        assert report["checks"]["escape_hides_bar"]

        m.command("WebDriver:SetWindowRect", {"width": 860, "height": 780})
        open_find()
        check_layout("narrow_split_pane")
        screenshot("findbar-narrow")
        key("\ue00c")
        m.js("gZenViewSplitter.unsplitCurrentView();return true;")
        open_find()
        check_layout("ordinary_tab")
        key("\ue00c")

        m.js("gBrowser.selectedBrowser.focus();return true;")
        m.command("WebDriver:SwitchToWindow", {"handle": m.command("WebDriver:GetWindowHandle")})
        m.command("Marionette:SetContext", {"value": "content"})
        link = m.command("WebDriver:FindElement", {"using": "css selector", "value": "#preview"})
        m.command("WebDriver:ElementClick", {"id": link["element-6066-11e4-a52e-4f735466cecf"]})
        m.command("Marionette:SetContext", {"value": "chrome"})
        wait("gBrowser.selectedTab.hasAttribute('zen-glance-tab') && !gZenGlanceManager._animating")
        open_find()
        check_layout("glance")
        key("\ue00c")
        m.async_js("await gZenGlanceManager.closeGlance({hasFocused:true,skipPermitUnload:true});return true;")
        open_find()

        check_settings()

        m.js("window.windowUtils.removeSheet(window.__findFixURI,window.windowUtils.USER_SHEET);return true;")
        fixed = False
        time.sleep(.2)
        report["checks"]["stylesheet_unload"] = measure()["position"] == report["baseline"]["position"]
        assert report["checks"]["stylesheet_unload"]
        report["passed"] = True
    except Exception as error:
        report["passed"] = False
        report["error"] = str(error)
        raise
    finally:
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        if fixed:
            m.js("window.windowUtils.removeSheet(window.__findFixURI,window.windowUtils.USER_SHEET);return true;")
        m.js("window.FindbarPageZoom?.destroy();return true;")
        if original_color is not None:
            m.js('document.documentElement.style.setProperty("--var-findbar-background-color",arguments[0],arguments[1]);return true;', original_color)
        if clipboard is not None:
            m.js("""
              if (Services.clipboard.isClipboardTypeSupported(Services.clipboard.kFindClipboard)) {
                if (arguments[0]) {
                  Cc["@mozilla.org/widget/clipboardhelper;1"].getService(Ci.nsIClipboardHelper)
                    .copyStringToClipboard(arguments[0], Services.clipboard.kFindClipboard);
                } else {
                  Services.clipboard.emptyClipboard(Services.clipboard.kFindClipboard);
                }
              }
              return true;
            """, [clipboard])
        m.close()
        server.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--port", default=2832, type=int)
    parser.add_argument("--report", required=True, type=Path)
    run(parser.parse_args())
