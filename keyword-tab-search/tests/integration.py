"""Real keyboard checks, restricted to an explicitly selected disposable profile."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "little-zen/scripts"))
from runtime import Marionette


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.requests.append(self.path)
        page = b'<!doctype html><title>Keyword test</title><input id="draft" value="Keep this draft"><input id="next"><p>Search fixture</p>'
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
    server.requests = []
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

    def key(value, shift=False, modifiers=()):
        held = [*modifiers, *(["\ue008"] if shift else [])]
        actions = [{"type": "keyDown", "value": modifier} for modifier in held]
        actions += [{"type": "keyDown", "value": value}, {"type": "keyUp", "value": value}]
        actions += [{"type": "keyUp", "value": modifier} for modifier in reversed(held)]
        m.command("WebDriver:PerformActions", {"actions": [{"type": "key", "id": "keyboard", "actions": actions}]})

    def type_text(value):
        field = m.command("WebDriver:FindElement", {"using": "css selector", "value": "#urlbar-input"})
        m.command("WebDriver:ElementSendKeys", {
            "id": field["element-6066-11e4-a52e-4f735466cecf"], "text": value,
        })
        return field

    def type_keyword(value):
        m.js("gURLBar.searchMode=null;gURLBar.select();return true;")
        return type_text(value)

    def no_mode(name):
        time.sleep(.15)
        check(name, m.js("return !gURLBar.searchMode;"))

    def activate(keyword, name="Keyword test"):
        type_keyword(keyword)
        key("\ue004")
        wait("gURLBar.searchMode?.engineName===" + json.dumps(name))
        return m.js("return gURLBar.value==='' && document.activeElement===gURLBar.inputField;")

    try:
        actual = m.js('return Services.dirsvc.get("ProfD",Ci.nsIFile).path;')
        if Path(actual).resolve() != args.profile.resolve() or "test-profile" not in args.profile.name:
            raise RuntimeError("Refusing to test an everyday browser profile")
        main = None
        for handle in m.command("WebDriver:GetWindowHandles"):
            m.command("WebDriver:SwitchToWindow", {"handle": handle})
            if m.js("return !window._littleZenInfo && !PrivateBrowsingUtils.isWindowPrivate(window);"):
                main = handle
                break
        assert main, "No regular test window"
        main_context = m.js("return window.browsingContext.id;")
        m.async_js("""
          await gZenStartup.promiseInitialized;
          await KeywordTabSearch.ready;
          const {SearchService}=ChromeUtils.importESModule("moz-src:///toolkit/components/search/SearchService.sys.mjs");
          await SearchService.init();
          for(const name of ["Keyword test","Token keyword test"]) {
            const old=SearchService.getEngineByName(name);
            if(old) await SearchService.removeEngine(old);
          }
          window.__keywordTestEngine=await SearchService.addUserEngine({
            name:"Keyword test",alias:"kwtest",url:arguments[0]+"/search?q={searchTerms}",method:"GET"});
          await SearchService.addUserEngine({
            name:"Token keyword test",alias:"@kwtoken",url:arguments[0]+"/token?q={searchTerms}",method:"GET"});
          gBrowser.selectedTab=gBrowser.addTrustedTab(arguments[0]+"/source",{skipRoute:true});
          return true;
        """, [base])
        wait("KeywordTabSearch.status==='ready' && gBrowser.selectedBrowser.currentURI.spec===" +
             json.dumps(base + "/source") + " && !gBrowser.selectedBrowser.webProgress.isLoadingDocument")
        identity = m.js("return gBrowser.selectedBrowser.browsingContext.id;")
        check("keyword_tab", activate("kwtest"))
        check("activation_does_not_navigate", identity == m.js("return gBrowser.selectedBrowser.browsingContext.id;") and not any("/search?" in p for p in server.requests))
        text = "a & b/雪?="
        field = m.command("WebDriver:FindElement", {"using": "css selector", "value": "#urlbar-input"})
        m.command("WebDriver:ElementSendKeys", {
            "id": field["element-6066-11e4-a52e-4f735466cecf"], "text": text,
        })
        key("\ue007")
        url = wait("gBrowser.selectedBrowser.currentURI.spec.startsWith(" + json.dumps(base + "/search?") + ") && gBrowser.selectedBrowser.currentURI.spec")
        check("native_query_encoding", parse_qs(urlsplit(url).query)["q"] == [text])
        check("case_insensitive_keyword", activate("KWTEST"))
        check("stripped_token_alias", activate("kwtoken", "Token keyword test"))
        type_keyword("kwtest ")
        check("native_space_keyword", wait("gURLBar.searchMode?.engineName==='Keyword test'"))

        # Match the user's actual shortcut in this disposable window. The
        # production mod must not register or change any keyboard shortcut.
        is_mac = m.js("return Services.appinfo.OS==='Darwin';")
        accelerator = "\ue03d" if is_mac else "\ue009"
        split_modifiers = (accelerator, "\ue009" if is_mac else "\ue00a", "\ue008")
        m.js("""
          const key=document.getElementById("zen-new-empty-split-view");
          key.setAttribute("key","T");
          key.setAttribute("modifiers",arguments[0]);
          window.__keywordMainTab=gBrowser.selectedTab;
          return true;
        """, ["accel,control,shift" if is_mac else "accel,alt,shift"])
        for scenario in ("regular", "pinned", "cancel"):
            source_path = "/split-source-" + scenario
            m.js("""
              gURLBar.searchMode=null;
              gBrowser.selectedTab=gBrowser.addTrustedTab(arguments[0],{skipRoute:true});
              window.__keywordSplitSource=gBrowser.selectedTab;
              if(arguments[1]) gBrowser.pinTab(__keywordSplitSource);
              return true;
            """, [base + source_path, scenario == "pinned"])
            wait("gBrowser.selectedBrowser.currentURI.spec===" + json.dumps(base + source_path) +
                 " && !gBrowser.selectedBrowser.webProgress.isLoadingDocument")
            m.command("WebDriver:SwitchToWindow", {"handle": main})
            m.command("Marionette:SetContext", {"value": "content"})
            wait("document.getElementById('draft')")
            m.js("document.getElementById('draft').value='Unsaved split draft';return true;")
            m.command("Marionette:SetContext", {"value": "chrome"})
            source_identity = m.js("""
              return [__keywordSplitSource.linkedBrowser.browsingContext.id,
                __keywordSplitSource.linkedBrowser.browsingContext.currentWindowGlobal.innerWindowId];
            """)
            tab_count = m.js("return gBrowser.tabs.length;")
            key("t", modifiers=split_modifiers)
            wait("gZenViewSplitter.waitingForSplitTab && gURLBar.focused && gURLBar.hasAttribute('zen-newtab')")
            type_text("kwtest")
            key("\ue004")
            wait("gURLBar.searchMode?.engineName==='Keyword test'")
            check("split_" + scenario + "_keyword_keeps_placeholder", m.js("""
              return gZenViewSplitter.waitingForSplitTab &&
                gBrowser.selectedTab.hasAttribute('zen-empty-tab') &&
                gBrowser.selectedTab.splitView && gURLBar.hasAttribute('zen-newtab');
            """) and tab_count == m.js("return gBrowser.tabs.length;"))
            if scenario == "cancel":
                # The first Escape exits engine mode; the next closes the
                # pending split. Neither should submit or create a real tab.
                submitted_before = len([p for p in server.requests if p.startswith("/search?")])
                key("\ue00c")
                key("\ue00c")
                wait("!gZenViewSplitter.waitingForSplitTab && !gURLBar.hasAttribute('zen-newtab')")
                check("split_escape_cancels_without_navigation",
                      tab_count == m.js("return gBrowser.tabs.length;") and
                      submitted_before == len([p for p in server.requests if p.startswith("/search?")]))
            else:
                query = scenario + " a & b/雪?="
                type_text(query)
                key("\ue007")
                url = wait("gBrowser.selectedBrowser.currentURI.spec.startsWith(" +
                           json.dumps(base + "/search?") + ") && gBrowser.selectedBrowser.currentURI.spec")
                wait("!gZenViewSplitter.waitingForSplitTab && !gURLBar.hasAttribute('zen-newtab')")
                check("split_" + scenario + "_submission_stays_beside_source", m.js("""
                  return gBrowser.selectedTab!==__keywordSplitSource &&
                    gBrowser.selectedTab.splitView && __keywordSplitSource.splitView &&
                    gBrowser.selectedTab.group===__keywordSplitSource.group &&
                    gBrowser.selectedTab.group.tabs.length===2 &&
                    !gZenWorkspaces._emptyTab.splitView;
                """) and tab_count + 1 == m.js("return gBrowser.tabs.length;") and
                      parse_qs(urlsplit(url).query)["q"] == [query])
                m.js("window.__keywordSplitResult=gBrowser.selectedTab;return true;")
                if scenario == "regular":
                    check("existing_split_accepts_keyword", activate("kwtest"))
                    type_text("search in existing pane")
                    key("\ue007")
                    wait("gBrowser.selectedBrowser.currentURI.spec.includes('search+in+existing+pane')")
                    check("existing_split_reuses_active_pane", m.js("""
                      return gBrowser.selectedTab===__keywordSplitResult &&
                        gBrowser.selectedTab.splitView &&
                        gBrowser.selectedTab.group===__keywordSplitSource.group;
                    """) and tab_count + 1 == m.js("return gBrowser.tabs.length;"))
            check("split_" + scenario + "_source_document_preserved", source_identity == m.js("""
              return [__keywordSplitSource.linkedBrowser.browsingContext.id,
                __keywordSplitSource.linkedBrowser.browsingContext.currentWindowGlobal.innerWindowId];
            """) and server.requests.count(source_path) == 1)
            m.js("gBrowser.selectedTab=__keywordSplitSource;return true;")
            m.command("WebDriver:SwitchToWindow", {"handle": main})
            m.command("Marionette:SetContext", {"value": "content"})
            check("split_" + scenario + "_draft_preserved",
                  m.js("return document.getElementById('draft').value==='Unsaved split draft';"))
            m.command("Marionette:SetContext", {"value": "chrome"})
            m.js("""
              if(window.__keywordSplitResult?.isConnected) {
                gBrowser.removeTab(__keywordSplitResult,{animate:false});
              }
              delete window.__keywordSplitResult;
              gBrowser.selectedTab=__keywordMainTab;
              gBrowser.removeTab(__keywordSplitSource,{animate:false});
              return true;
            """)

        tab_count = m.js("return gBrowser.tabs.length;")
        key("t", modifiers=(accelerator,))
        wait("gURLBar.hasAttribute('zen-newtab') && gURLBar.focused")
        type_text("kwtest")
        key("\ue004")
        wait("gURLBar.searchMode?.engineName==='Keyword test'")
        type_text("ordinary new tab")
        key("\ue007")
        wait("gBrowser.selectedBrowser.currentURI.spec.includes('ordinary+new+tab')")
        wait("!gURLBar.hasAttribute('zen-newtab')")
        check("ordinary_new_tab_search_stays_unsplit",
              not m.js("return !!gBrowser.selectedTab.splitView;") and
              tab_count + 1 == m.js("return gBrowser.tabs.length;"))
        m.js("""
          const result=gBrowser.selectedTab;
          gBrowser.selectedTab=__keywordMainTab;
          gBrowser.removeTab(result,{animate:false});
          return true;
        """)

        # Settings replaces a child about:blank document. Its unload used to
        # reach the chrome window's capture listener and destroy this mod.
        m.js("""
          window.__keywordLife=KeywordTabSearch;
          window.__keywordSource=gBrowser.selectedTab;
          window.__keywordSettings=gBrowser.addTrustedTab("about:preferences#sineMods",{skipRoute:true});
          gBrowser.selectedTab=__keywordSettings;
          return true;
        """)
        wait("__keywordSettings.linkedBrowser.contentDocument?.querySelector('#sineModsList')")
        m.js("gBrowser.selectedTab=__keywordSource;return true;")
        check("settings_open_preserves_keyword", m.js(
            "return window.KeywordTabSearch===__keywordLife && __keywordLife.status==='ready';"
        ) and activate("kwtest"))

        m.js("""
          window.__keywordSettingsDocument=__keywordSettings.linkedBrowser.browsingContext.currentWindowGlobal.innerWindowId;
          __keywordSettings.linkedBrowser.reload();
          return true;
        """)
        wait("__keywordSettings.linkedBrowser.browsingContext.currentWindowGlobal.innerWindowId!==__keywordSettingsDocument && "
             "__keywordSettings.linkedBrowser.contentDocument?.querySelector('#sineModsList')")
        check("settings_reload_preserves_keyword", m.js(
            "return window.KeywordTabSearch===__keywordLife && __keywordLife.status==='ready';"
        ) and activate("kwtest"))

        m.js("gBrowser.removeTab(__keywordSettings,{animate:false});return true;")
        wait("!__keywordSettings.isConnected")
        check("settings_close_preserves_keyword", m.js(
            "return window.KeywordTabSearch===__keywordLife && __keywordLife.status==='ready';"
        ) and activate("kwtest"))

        type_keyword("zz-no-such-keyword")
        key("\ue004")
        no_mode("unknown_keyword_keeps_native_tab")
        type_keyword("unrecognized words")
        key("\ue004")
        no_mode("multiword_input_keeps_native_tab")
        type_keyword("kwtest")
        key("\ue004", shift=True)
        no_mode("shift_tab_keeps_native_navigation")

        m.js("Services.prefs.setBoolPref('uc.keyword-tab-search.enabled',false);return true;")
        type_keyword("kwtest")
        key("\ue004")
        no_mode("disable_restores_tab")
        m.js("Services.prefs.setBoolPref('uc.keyword-tab-search.enabled',true);return true;")

        m.async_js("""
          window.__keywordTestEngine.alias="kwnew";
          await new Promise(resolve=>setTimeout(resolve,100));
          await KeywordTabSearch.ready;
          return true;
        """)
        type_keyword("kwtest")
        key("\ue004")
        no_mode("old_alias_removed")
        check("alias_edit_refreshes_automatically", activate("kwnew"))

        m.async_js("""
          const old=KeywordTabSearch;
          Services.scriptloader.loadSubScriptWithOptions(
            "chrome://sine/content/keyword-tab-search/keyword-tab-search.uc.js",{target:window,ignoreCache:true});
          await KeywordTabSearch.ready;
          if(old.status!=="destroyed") throw Error("Old instance retained");
          return true;
        """)
        check("hot_reload", activate("kwnew"))

        m.js("gURLBar.searchMode=null;gURLBar.blur();gBrowser.selectedBrowser.focus();return true;")
        m.command("WebDriver:SwitchToWindow", {"handle": m.command("WebDriver:GetWindowHandle")})
        m.command("Marionette:SetContext", {"value": "content"})
        m.js("document.getElementById('draft').focus();return true;")
        key("\ue004")
        check("page_input_tab", m.js("return document.activeElement.id==='next';"))
        m.command("Marionette:SetContext", {"value": "chrome"})

        before = m.command("WebDriver:GetWindowHandles")
        m.js("LittleZen.open({url:arguments[0]+'/little'});return true;", [base])
        deadline = time.monotonic() + 10
        mini = None
        while not mini and time.monotonic() < deadline:
            mini = next((h for h in m.command("WebDriver:GetWindowHandles") if h not in before), None)
            time.sleep(.05)
        assert mini, "Little Zen window not created"
        m.command("WebDriver:SwitchToWindow", {"handle": mini})
        wait("window.KeywordTabSearch?.status==='ready'")
        check("little_zen_keyword_tab", activate("kwnew"))
        m.js("""
          const main=[...Services.wm.getEnumerator("navigator:browser")]
            .find(win=>win.browsingContext.id===arguments[0]);
          main.__closedKeywordProbe=KeywordTabSearch;
          return true;
        """, [main_context])
        # Little Zen may replace its initial empty tab while search mode opens.
        # Rebind Marionette to the window's current browsing context before close.
        m.command("WebDriver:SwitchToWindow", {"handle": mini})
        m.command("WebDriver:CloseWindow")
        m.command("WebDriver:SwitchToWindow", {"handle": main})
        check("browser_window_unload_cleans_up", wait("__closedKeywordProbe.status==='destroyed'"))
        m.js("delete window.__closedKeywordProbe;return true;")
        check("other_window_close_preserves_keyword", activate("kwnew"))

        m.js("KeywordTabSearch.destroy();return true;")
        type_keyword("kwnew")
        key("\ue004")
        no_mode("unload_restores_native_tab")
        m.async_js("""
          Services.scriptloader.loadSubScriptWithOptions(
            "chrome://sine/content/keyword-tab-search/keyword-tab-search.uc.js",{target:window,ignoreCache:true});
          await KeywordTabSearch.ready;
          return true;
        """)
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
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--port", default=2832, type=int)
    parser.add_argument("--report", required=True, type=Path)
    run(parser.parse_args())
