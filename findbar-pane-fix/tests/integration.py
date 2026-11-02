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
        m.js("gURLBar.blur();gBrowser.selectedBrowser.focus();return true;")
        key("f", accelerator=True)
        m.async_js("window.__findProbe=await gBrowser.getFindBar(gBrowser.selectedTab);return true;")
        wait("!window.__findProbe.hidden")
        time.sleep(.4)

    def measure():
        return m.js("""
          const bar=window.__findProbe, pane=bar.closest('.browserContainer');
          const box=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom}};
          const css=getComputedStyle(bar);
          return {bar:box(bar),pane:box(pane),input:box(bar._findField),
            close:box(bar.querySelector('.findbar-closebutton')),background:css.backgroundColor,
            backdropFilter:css.backdropFilter,position:css.position,hidden:bar.hidden,
            scrollWidth:bar.scrollWidth,clientWidth:bar.clientWidth,
            focused:document.activeElement===bar._findField};
        """)

    def visible_inside(outer, inner):
        return inner["width"] > 0 and inner["height"] > 0 and (
            inner["x"] >= outer["x"] - 1 and inner["right"] <= outer["right"] + 1 and
            inner["y"] >= outer["y"] - 1 and inner["bottom"] <= outer["bottom"] + 1
        )

    def check_layout(name):
        result = measure()
        report["checks"][name] = result
        assert visible_inside(result["pane"], result["bar"]), (name, result)
        assert visible_inside(result["bar"], result["input"]), (name, result)
        assert visible_inside(result["bar"], result["close"]), (name, result)
        assert result["scrollWidth"] <= result["clientWidth"] + 1, (name, result)
        assert result["backdropFilter"] == "none", result
        assert result["background"].startswith("rgb("), result
        assert result["focused"], (name, result)
        print("PASS", name, flush=True)

    def screenshot(name):
        image = m.command("WebDriver:TakeScreenshot", {"full": False, "scroll": False})
        args.report.with_name(name + ".png").write_bytes(base64.b64decode(image))

    try:
        actual = m.js('return Services.dirsvc.get("ProfD",Ci.nsIFile).path;')
        if Path(actual).resolve() != args.profile.resolve() or "test-profile" not in args.profile.name:
            raise RuntimeError("Refusing to test an everyday profile")
        m.command("WebDriver:SetWindowRect", {"width": 1300, "height": 900})
        m.js("""
          window.__findTabs=['left','right'].map(name=>gBrowser.addTrustedTab(arguments[0]+'/'+name,{skipRoute:true}));
          gBrowser.selectedTab=window.__findTabs[1];
          gZenViewSplitter.splitTabs(window.__findTabs,undefined,1);
          return true;
        """, [base])
        wait("!gBrowser.selectedBrowser.webProgress.isLoadingDocument && gBrowser.selectedTab.splitView")
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
