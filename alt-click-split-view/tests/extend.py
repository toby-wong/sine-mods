"""Extend existing splits using real keyboard input in a disposable Zen profile."""

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
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            result = m.js("return (" + expression + ");")
            if result:
                return result
            time.sleep(.03)
        raise AssertionError("Timed out: " + expression)

    def check(name, result):
        assert result, name
        report["checks"][name] = True
        print("PASS", name, flush=True)

    def chrome():
        m.command("Marionette:SetContext", {"value": "chrome"})

    def content():
        chrome()
        m.command("WebDriver:SwitchToWindow", {"handle": main})
        m.command("Marionette:SetContext", {"value": "content"})

    def key(value, modifiers=()):
        actions = [{"type": "keyDown", "value": mod} for mod in modifiers]
        actions += [{"type": "keyDown", "value": value}, {"type": "keyUp", "value": value}]
        actions += [{"type": "keyUp", "value": mod} for mod in reversed(modifiers)]
        m.command("WebDriver:PerformActions", {
            "actions": [{"type": "key", "id": "keyboard", "actions": actions}],
        })

    def type_text(value):
        field = m.command("WebDriver:FindElement", {"using": "css selector", "value": "#urlbar-input"})
        m.command("WebDriver:ElementSendKeys", {
            "id": field["element-6066-11e4-a52e-4f735466cecf"], "text": value,
        })

    def state():
        return m.js("""
          const f=window.__extendFixture;
          return {groupId:f.group.groupId,tabs:f.group.tabs.map(t=>t.id),
            selected:gBrowser.selectedTab.id,groupCount:gZenViewSplitter._data.length,
            layout:gZenViewSplitter.storeDataForSessionStore().find(g=>g.groupId===f.group.groupId)};
        """)

    def identities():
        return m.js("""
          return __extendFixture.members.map(t=>({id:t.id,context:t.linkedBrowser.browsingContext.id,
            inner:t.linkedBrowser.browsingContext.currentWindowGlobal.innerWindowId,
            pinned:t.pinned,essential:t.hasAttribute('zen-essential')}));
        """)

    def setup(name, grid="vsep", count=2, kind="normal"):
        chrome()
        m.async_js("""
          if(gZenGlanceManager.getFocusedTab())
            await gZenGlanceManager.closeGlance({hasFocused:true,skipPermitUnload:true});
          const previous=new Set([
            ...(window.__extendFixture?.members || []),
            ...(window.__extendFixture?.group.tabs || []),
          ]);
          for(const tab of [...gZenWorkspaces.allStoredTabs]) {
            if(!tab.hasAttribute('zen-empty-tab') &&
                (previous.has(tab) || tab.linkedBrowser?.currentURI.spec.startsWith(arguments[0])))
              gBrowser.removeTab(tab,{animate:false,skipPermitUnload:true});
          }
          const members=Array.from({length:arguments[2]},(_,i)=>
            gBrowser.addTrustedTab(arguments[0]+"/source/"+arguments[1]+"-"+i,{skipRoute:true}));
          if(arguments[3]==="pinned") gBrowser.pinTab(members[0]);
          if(arguments[3]==="essential") gZenPinnedTabManager.addToEssentials([members[0]]);
          if(arguments[3]==="essentials") gZenPinnedTabManager.addToEssentials(members);
          gBrowser.selectedTab=members[0];
          gZenViewSplitter.splitTabs(members,arguments[4],0);
          const group=gZenViewSplitter._data.find(g=>g.tabs.includes(members[0]));
          // Unequal sizes catch accidental rebuilding or equalizing of the old panes.
          if(group.layoutTree.children.length===2) {
            group.layoutTree.children[0].sizeInParent=35;
            group.layoutTree.children[1].sizeInParent=65;
            gZenViewSplitter.applyGridLayout(group.layoutTree);
          }
          window.__extendFixture={members,group};
          return true;
        """, [base, name, count, kind, grid])
        drafts = {}
        for i in range(count):
            m.js("gBrowser.selectedTab=__extendFixture.members[arguments[0]];return true;", [i])
            content()
            wait("document.readyState==='complete' && !!document.getElementById('draft')")
            drafts[i] = m.js("""
              document.getElementById('draft').value='Keep original split draft '+arguments[0];
              return {draft:document.getElementById('draft').value,marker:document.documentElement.dataset.marker};
            """, [i])
            chrome()
        m.js("gBrowser.selectedTab=__extendFixture.members[0];return true;")
        return {"state": state(), "identities": identities(), "drafts": drafts, "name": name}

    def preserved(before, name):
        check(name + "_documents_and_pin_state", identities() == before["identities"])
        selection = m.js("return gBrowser.selectedTab.id;")
        drafts = {}
        for i in before["drafts"]:
            m.js("gBrowser.selectedTab=__extendFixture.members[arguments[0]];return true;", [i])
            content()
            drafts[i] = m.js("""
              return {draft:document.getElementById('draft').value,marker:document.documentElement.dataset.marker};
            """)
            chrome()
        m.js("gBrowser.selectedTab=document.getElementById(arguments[0]);return true;", [selection])
        check(name + "_drafts_and_request_counts", drafts == before["drafts"] and
              all(COUNTS["/source/" + before["name"] + "-" + str(i)] == 1 for i in before["drafts"]))

    def geometry(name, expected_count):
        result = wait("""(() => {
          const g=__extendFixture.group;
          if(g.tabs.length!==""" + str(expected_count) + """) return false;
          const rects=g.tabs.map(t=>{
            const c=t.linkedBrowser.closest('.browserSidebarContainer'),r=c.getBoundingClientRect();
            return {x:r.x,y:r.y,width:r.width,height:r.height,visibility:getComputedStyle(c).visibility};
          });
          if(rects.some(r=>r.width<20 || r.height<20 || r.visibility!=='visible')) return false;
          for(let i=0;i<rects.length;i++) for(let j=i+1;j<rects.length;j++) {
            const a=rects[i],b=rects[j];
            if(Math.min(a.x+a.width,b.x+b.width)-Math.max(a.x,b.x)>2 &&
               Math.min(a.y+a.height,b.y+b.height)-Math.max(a.y,b.y)>2) return false;
          }
          return {direction:g.layoutTree.direction,rects};
        })()""")
        report["layouts"][name] = result
        check(name + "_visible_nonoverlapping_panes", True)

    def begin(name):
        before = state()
        key("t", split_modifiers)
        wait("gZenViewSplitter.waitingForSplitTab && gURLBar.focused && gURLBar.hasAttribute('zen-newtab')")
        check(name + "_same_group_preview", m.js("""
          return gZenViewSplitter._data.includes(__extendFixture.group) &&
            __extendFixture.group.tabs.includes(gZenWorkspaces._emptyTab) &&
            gZenViewSplitter._data.filter(g=>g.tabs.includes(gZenWorkspaces._emptyTab)).length===1;
        """) and state()["groupCount"] == before["groupCount"] and
              len(state()["tabs"]) == len(before["tabs"]) + 1)
        preview = state()
        check(name + "_session_excludes_temporary_pane",
              preview["layout"]["tabs"] == before["tabs"] and
              m.js("""
                const emptyId=gZenWorkspaces._emptyTab.id;
                const complete=node=>node.type==='leaf' ? node.tabId!==emptyId : node.children.every(complete);
                return gZenViewSplitter.storeDataForSessionStore()
                  .every(group=>!group.tabs.includes(emptyId) && complete(group.layoutTree));
              """))
        m.js("gZenViewSplitter.createEmptySplit();return true;")
        check(name + "_repeated_command_keeps_one_placeholder", state() == preview)
        return before

    def add(name, search=False):
        before = begin(name)
        query = name + " & /雪?="
        if search:
            type_text("extend")
            key("\ue004")
            wait("gURLBar.searchMode?.engineName==='Extend split test'")
            type_text(query)
        else:
            type_text(base + "/target/" + name)
        key("\ue007")
        wait("!gZenViewSplitter.waitingForSplitTab && !gURLBar.hasAttribute('zen-newtab')")
        wait("gBrowser.selectedBrowser.currentURI.spec.startsWith(" +
             json.dumps(base + ("/search?" if search else "/target/" + name)) + ")")
        wait("gBrowser.selectedTab.splitView && !gBrowser.selectedBrowser.webProgress.isLoadingDocument")
        after = state()
        check(name + "_committed_into_same_group", before["groupId"] == after["groupId"] and
              before["groupCount"] == after["groupCount"] and
              after["tabs"][:-1] == before["tabs"] and after["selected"] == after["tabs"][-1] and
              after["layout"]["layoutTree"]["direction"] == before["layout"]["layoutTree"]["direction"] and
              m.js("return !gZenWorkspaces._emptyTab.splitView;"))
        if search:
            url = m.js("return gBrowser.selectedBrowser.currentURI.spec;")
            check(name + "_native_keyword_query", parse_qs(urlsplit(url).query)["q"] == [query])
        geometry(name, len(after["tabs"]))
        return after

    def cancel(name):
        before = begin(name)
        type_text("unsubmitted third pane")
        # Native Escape first leaves a retained search mode or suggestion.
        for _ in range(3):
            key("\ue00c")
            time.sleep(.1)
            if not m.js("return gURLBar.hasAttribute('zen-newtab');"):
                break
        wait("!gZenViewSplitter.waitingForSplitTab && !gURLBar.hasAttribute('zen-newtab')")
        after = state()
        # Native size arithmetic may introduce a final floating-point ulp.
        def rounded(value):
            if isinstance(value, float):
                return round(value, 8)
            if isinstance(value, list):
                return [rounded(item) for item in value]
            if isinstance(value, dict):
                return {key: rounded(item) for key, item in value.items()}
            return value
        check(name + "_escape_restores_group_selection_and_sizes", rounded(before) == rounded(after))
        check(name + "_command_ready_again", not m.js("""
          return document.getElementById('cmd_zenNewEmptySplit').hasAttribute('disabled') ||
            gZenWorkspaces._emptyTab.splitView;
        """))

    def reload_mod():
        m.async_js("""
          Services.scriptloader.loadSubScriptWithOptions(
            'chrome://sine/content/alt-click-split-view/alt-click-split-view.uc.js',
            {target:window,ignoreCache:true});
          await AltClickSplitView.ready;return true;
        """)

    try:
        actual = m.js('return Services.dirsvc.get("ProfD",Ci.nsIFile).path;')
        if Path(actual).resolve() != args.profile.resolve() or "test-profile" not in args.profile.name:
            raise RuntimeError("Refusing to run outside the specified disposable profile")
        main = m.command("WebDriver:GetWindowHandle")
        is_mac = m.js("return Services.appinfo.OS==='Darwin';")
        split_modifiers = ("\ue03d", "\ue009", "\ue008") if is_mac else ("\ue009", "\ue00a", "\ue008")
        m.async_js("""
          await gZenStartup.promiseInitialized;await AltClickSplitView.ready;
          Services.prefs.setBoolPref('uc.alt-click-split-view.enabled',true);
          Services.prefs.setBoolPref('uc.alt-click-split-view.adaptive-direction',true);
          const key=document.getElementById('zen-new-empty-split-view');
          key.setAttribute('key','T');key.setAttribute('modifiers',arguments[1]);
          const {SearchService}=ChromeUtils.importESModule('moz-src:///toolkit/components/search/SearchService.sys.mjs');
          await SearchService.init();
          const old=SearchService.getEngineByName('Extend split test');
          if(old) await SearchService.removeEngine(old);
          await SearchService.addUserEngine({name:'Extend split test',alias:'extend',
            url:arguments[0]+'/search?q={searchTerms}',method:'GET'});
          return true;
        """, [base, "accel,control,shift" if is_mac else "accel,alt,shift"])

        m.command("WebDriver:SetWindowRect", {"width": 1200, "height": 800})
        original = setup("ordinary")
        cancel("cancel_third")
        preserved(original, "cancel_third")
        before = begin("blur_cancel")
        m.js("gURLBar.inputField.blur();return true;")
        wait("!gZenViewSplitter.waitingForSplitTab && !gURLBar.hasAttribute('zen-newtab')")
        check("blurred_urlbar_cancellation_keeps_group", state()["tabs"] == before["tabs"] and
              state()["selected"] == before["selected"])
        preserved(original, "blur_cancel")
        add("third_url")
        preserved(original, "third_url")
        add("fourth_keyword", search=True)
        preserved(original, "fourth_keyword")
        before = state()
        key("t", split_modifiers)
        time.sleep(.1)
        check("four_pane_limit", state() == before and m.js("""
          return document.getElementById('cmd_zenNewEmptySplit').hasAttribute('disabled') &&
            !gZenViewSplitter.waitingForSplitTab;
        """))
        m.js("gBrowser.removeTab(gBrowser.selectedTab,{animate:false,skipPermitUnload:true});return true;")
        wait("!document.getElementById('cmd_zenNewEmptySplit').hasAttribute('disabled')")
        cancel("cancel_fourth_after_close")
        add("replacement_fourth", search=True)
        preserved(original, "replacement_fourth")

        for name, grid, count, kind, width, height in [
            ("column_in_wide", "hsep", 2, "normal", 1200, 800),
            ("row_in_tall", "vsep", 2, "normal", 800, 1200),
            ("nested_grid", "grid", 3, "normal", 1200, 800),
            ("pinned", "vsep", 2, "pinned", 1200, 800),
            ("essential", "hsep", 2, "essential", 1200, 800),
            ("essentials_pair", "vsep", 2, "essentials", 1200, 800),
        ]:
            m.command("WebDriver:SetWindowRect", {"width": width, "height": height})
            original = setup(name, grid, count, kind)
            cancel(name + "_cancel")
            add(name, search=True)
            preserved(original, name)

        original = setup("switch_cancel")
        before = begin("switch_cancel")
        m.js("gBrowser.selectedTab=__extendFixture.members[1];return true;")
        wait("!gZenViewSplitter.waitingForSplitTab && !gURLBar.hasAttribute('zen-newtab')")
        check("switch_cancel_keeps_chosen_pane", state()["tabs"] == before["tabs"] and
              state()["selected"] == before["tabs"][1])
        preserved(original, "switch_cancel")
        begin("blur_switch")
        m.js("gURLBar.inputField.blur();gBrowser.selectedTab=__extendFixture.members[0];return true;")
        wait("!gZenViewSplitter.waitingForSplitTab && !gURLBar.hasAttribute('zen-newtab')")
        check("blurred_urlbar_switch_keeps_chosen_pane", state()["tabs"] == before["tabs"] and
              state()["selected"] == before["tabs"][0])
        preserved(original, "blur_switch")

        original = setup("open_refused")
        m.js("""
          window.__extendOriginalNewTab=gZenUIManager.handleNewTab;
          gZenUIManager.handleNewTab=()=>false;return true;
        """)
        try:
            key("t", split_modifiers)
            wait("!gZenViewSplitter.waitingForSplitTab && !gZenWorkspaces._emptyTab.splitView")
            check("refused_urlbar_restores_group", state()["tabs"] == original["state"]["tabs"])
        finally:
            m.js("gZenUIManager.handleNewTab=__extendOriginalNewTab;delete window.__extendOriginalNewTab;return true;")
        preserved(original, "open_refused")

        original = setup("source_closed")
        begin("source_closed")
        m.js("gBrowser.removeTab(__extendFixture.members[0],{animate:false,skipPermitUnload:true});return true;")
        wait("!gZenViewSplitter.waitingForSplitTab && !gZenWorkspaces._emptyTab.splitView")
        check("closing_source_keeps_other_document", m.js("""
          const tab=__extendFixture.members[1];
          return tab.isConnected && !tab.closing && !tab.splitView &&
            tab.linkedBrowser.browsingContext.currentWindowGlobal.innerWindowId===arguments[0];
        """, [original["identities"][1]["inner"]]))

        original = setup("sibling_closed")
        begin("sibling_closed")
        m.js("gBrowser.removeTab(__extendFixture.members[1],{animate:false,skipPermitUnload:true});return true;")
        wait("!gZenViewSplitter.waitingForSplitTab && !gZenWorkspaces._emptyTab.splitView")
        check("closing_sibling_keeps_source_document", m.js("""
          const tab=__extendFixture.members[0];
          return tab.isConnected && !tab.closing && !tab.splitView &&
            tab.linkedBrowser.browsingContext.currentWindowGlobal.innerWindowId===arguments[0];
        """, [original["identities"][0]["inner"]]))

        original = setup("unsplit")
        begin("unsplit_pending")
        m.js("gZenViewSplitter.unsplitCurrentView();return true;")
        wait("!gZenViewSplitter.waitingForSplitTab && !gZenWorkspaces._emptyTab.splitView")
        check("unsplitting_cleans_pending_state", m.js("""
          return __extendFixture.members.every(t=>t.isConnected && !t.splitView) &&
            !gZenViewSplitter._data.includes(__extendFixture.group);
        """))
        preserved(original, "unsplit")

        original = setup("disabled")
        begin("disable_pending")
        m.js("Services.prefs.setBoolPref('uc.alt-click-split-view.enabled',false);return true;")
        wait("!gZenViewSplitter.waitingForSplitTab && !gZenWorkspaces._emptyTab.splitView")
        check("disable_cleans_preview", state()["tabs"] == original["state"]["tabs"])
        m.js("Services.prefs.setBoolPref('uc.alt-click-split-view.enabled',true);return true;")
        wait("!document.getElementById('cmd_zenNewEmptySplit').hasAttribute('disabled')")
        add("after_enable")
        preserved(original, "after_enable")

        original = setup("reload")
        before = state()
        reload_mod()
        check("reload_keeps_completed_group", state() == before)
        begin("reload_pending")
        reload_mod()
        wait("!gZenViewSplitter.waitingForSplitTab && !gZenWorkspaces._emptyTab.splitView")
        wait("!document.getElementById('cmd_zenNewEmptySplit').hasAttribute('disabled')")
        check("reload_cleans_only_pending_leaf", state()["tabs"] == before["tabs"])
        add("after_reload")
        preserved(original, "after_reload")
        m.js("AltClickSplitView.destroy({reloading:true});return true;")
        check("unload_restores_native_command", m.js("""
          return document.getElementById('cmd_zenNewEmptySplit').hasAttribute('disabled');
        """))
        reload_mod()
        add("after_reinstall", search=True)
        preserved(original, "after_reinstall")

        normal_handle = main
        existing_handles = set(m.command("WebDriver:GetWindowHandles"))
        m.js("OpenBrowserWindow({private:true});return true;")
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            added = set(m.command("WebDriver:GetWindowHandles")) - existing_handles
            if added:
                break
            time.sleep(.05)
        else:
            raise AssertionError("Private test window did not open")
        main = added.pop()
        m.command("WebDriver:SwitchToWindow", {"handle": main})
        try:
            m.async_js("""
              await gZenStartup.promiseInitialized;await AltClickSplitView.ready;
              const key=document.getElementById('zen-new-empty-split-view');
              key.setAttribute('key','T');key.setAttribute('modifiers',arguments[0]);
              return true;
            """, ["accel,control,shift" if is_mac else "accel,alt,shift"])
            check("private_context", m.js("return PrivateBrowsingUtils.isWindowPrivate(window);"))
            original = setup("private")
            cancel("private_cancel")
            add("private_third", search=True)
            preserved(original, "private_third")
        finally:
            m.js("setTimeout(()=>window.close(),0);return true;")
            main = normal_handle
            m.command("WebDriver:SwitchToWindow", {"handle": main})
        report["passed"] = len(report["checks"])
    except Exception as error:
        report["error"] = str(error)
        try:
            chrome()
            report["failureState"] = m.js("""
              return {waiting:gZenViewSplitter.waitingForSplitTab,
                newtab:gURLBar.hasAttribute('zen-newtab'),focused:gURLBar.focused,
                searchMode:gURLBar.searchMode,active:document.activeElement?.id,
                windowFocused:document.hasFocus(),selected:gBrowser.selectedTab.id,
                empty:gZenWorkspaces._emptyTab.id};
            """)
        except Exception:
            pass
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
