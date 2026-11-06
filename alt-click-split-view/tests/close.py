"""Native split-close input checks, restricted to a disposable Zen profile."""

import argparse
from collections import Counter
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
import uuid

from runtime import Marionette


COUNTS = Counter()
PAGE = b"""<!doctype html><meta charset="utf-8"><title>Split close fixture</title>
<style>body{font:16px system-ui;margin:24px}input,button{display:block;margin:12px}</style>
<input id="draft"><button id="arm">Protect unsaved draft</button>
<script>
document.documentElement.dataset.marker=crypto.randomUUID();
document.getElementById('arm').onclick=()=>{
  window.onbeforeunload=e=>{e.preventDefault();e.returnValue='';};
};
</script>"""


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


class PromptMarionette(Marionette):
    def command(self, name, params=None):
        if name == "WebDriver:NewSession":
            params["capabilities"]["alwaysMatch"]["unhandledPromptBehavior"] = "ignore"
        return super().command(name, params)


def run(args):
    report = {"checks": {}, "transitions": {}}
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    m = PromptMarionette(args.port)
    observer_path = None

    def wait(expression, seconds=8):
        deadline = time.monotonic() + seconds
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

    def pointer(element, button=0, move_only=False):
        actions = [{"type": "pointerMove", "origin": element, "x": 0, "y": 0}]
        if not move_only:
            actions += [{"type": "pointerDown", "button": button},
                        {"type": "pointerUp", "button": button}]
        m.command("WebDriver:PerformActions", {
            "actions": [{"type": "pointer", "id": "mouse",
                         "parameters": {"pointerType": "mouse"}, "actions": actions}],
        })

    def key(value, modifiers=()):
        actions = [{"type": "keyDown", "value": mod} for mod in modifiers]
        actions += [{"type": "keyDown", "value": value}, {"type": "keyUp", "value": value}]
        actions += [{"type": "keyUp", "value": mod} for mod in reversed(modifiers)]
        m.command("WebDriver:PerformActions", {
            "actions": [{"type": "key", "id": "keyboard", "actions": actions}],
        })

    def select(expression):
        chrome()
        m.js("gBrowser.selectedTab=" + expression + ";return true;")

    def page_state():
        content()
        result = m.js("""
          return {marker:document.documentElement.dataset.marker,
            draft:document.getElementById('draft').value,active:document.activeElement.id};
        """)
        chrome()
        return result

    def identities():
        return m.js("""
          return __splitCloseFixture.all.filter(t=>t.isConnected&&!t.closing).map(t=>({
            tab:t.id,context:t.linkedBrowser.browsingContext.id,
            inner:t.linkedBrowser.browsingContext.currentWindowGlobal.innerWindowId}));
        """)

    def begin_trace():
        m.js("__splitCloseProbe.events=[];return true;")

    def transitions(name):
        events = m.js("return __splitCloseProbe.events;")
        report["transitions"][name] = events
        return events

    def setup(name, count=3, active="keeper", other_split=False, kind="normal"):
        chrome()
        m.async_js("""
          for(const tab of [...gZenWorkspaces.allStoredTabs]) {
            if(tab.linkedBrowser?.currentURI.spec.startsWith(arguments[0]))
              gBrowser.removeTab(tab,{animate:false,skipPermitUnload:true});
          }
          const keeper=gBrowser.addTrustedTab(arguments[0]+'/'+arguments[1]+'/keeper',{skipRoute:true});
          const members=Array.from({length:arguments[2]},(_,i)=>
            gBrowser.addTrustedTab(arguments[0]+'/'+arguments[1]+'/'+i,{skipRoute:true}));
          if(arguments[4]==='pinned')gBrowser.pinTab(members[0]);
          if(arguments[4]==='essential')gZenPinnedTabManager.addToEssentials([members[0]]);
          gBrowser.selectedTab=members[0];
          gZenViewSplitter.splitTabs(members,'vsep',0);
          const group=gZenViewSplitter._data.find(g=>g.tabs.includes(members[0]));
          const others=arguments[3]?[keeper,gBrowser.addTrustedTab(
            arguments[0]+'/'+arguments[1]+'/other',{skipRoute:true})]:[keeper];
          if(arguments[3])gZenViewSplitter.splitTabs(others,'hsep',0);
          window.__splitCloseFixture={keeper,members,group,others,all:[...members,...others]};
          return true;
        """, [base, name, count, other_split, kind])
        for index in range(count + (2 if other_split else 1)):
            select(f"__splitCloseFixture.all[{index}]")
            content()
            wait("document.readyState==='complete' && !!document.getElementById('draft')")
            m.js("document.getElementById('draft').value=arguments[0];return true;",
                 [f"Keep {name} draft {index}"])
            chrome()
        select("__splitCloseFixture.keeper" if active == "keeper" else
               f"__splitCloseFixture.members[{active}]")
        content()
        field = m.command("WebDriver:FindElement", {"using": "css selector", "value": "#draft"})
        pointer(field)
        chrome()
        before = {
            "identities": identities(), "page": page_state(),
            "selected": m.js("return gBrowser.selectedTab.id;"),
            "members": m.js("return __splitCloseFixture.members.map(t=>t.id);"),
        }
        begin_trace()
        return before

    def preserved(before, name):
        after = identities()
        check(name + "_surviving_documents", all(item in before["identities"] for item in after))
        check(name + "_one_request_per_page",
              all(value == 1 for path, value in COUNTS.items() if path.startswith("/" + name + "/")))

    def middle_group():
        element = m.js("return __splitCloseFixture.members[0].querySelector('.tab-content');")
        pointer(element, 1)

    def close_button(index):
        element = m.js("return __splitCloseFixture.members[arguments[0]];", [index])
        pointer(element, move_only=True)
        wait("__splitCloseFixture.members[" + str(index) +
             "].querySelector('.tab-close-button').getBoundingClientRect().width>0")
        pointer(m.js("return __splitCloseFixture.members[arguments[0]].querySelector('.tab-close-button');",
                     [index]))

    def close_menu(index):
        pointer(m.js("return __splitCloseFixture.members[arguments[0]];", [index]), 2)
        wait("document.getElementById('tabContextMenu').state==='open'")
        pointer(m.js("return document.getElementById('context_closeTab');"))

    def closed_group():
        wait("__splitCloseFixture.members.every(t=>!t.isConnected)")
        check("no_orphan_split_groups_" + str(len(report["checks"])), m.js("""
          return !gZenViewSplitter._data.includes(__splitCloseFixture.group) &&
            !document.getElementById(__splitCloseFixture.group.groupId);
        """))

    def reload_mod():
        m.async_js("""
          Services.scriptloader.loadSubScriptWithOptions(
            'chrome://sine/content/alt-click-split-view/alt-click-split-view.uc.js',
            {target:window,ignoreCache:true});
          await AltClickSplitView.ready;return true;
        """)

    def alert(action):
        deadline = time.monotonic() + 8
        while True:
            try:
                text = m.command("WebDriver:GetAlertText")
                break
            except RuntimeError as error:
                if "no such alert" not in str(error) or time.monotonic() >= deadline:
                    raise
                time.sleep(.05)
        check("native_prompt_" + action, bool(text))
        m.command("WebDriver:DismissAlert" if action == "cancel" else "WebDriver:AcceptAlert")

    try:
        actual = m.js('return Services.dirsvc.get("ProfD",Ci.nsIFile).path;')
        if Path(actual).resolve() != args.profile.resolve() or "test-profile" not in args.profile.name:
            raise RuntimeError("Refusing to run outside the specified disposable profile")
        main = m.command("WebDriver:GetWindowHandle")
        report["version"] = m.js("return AltClickSplitView.version;")
        m.js("""
          Services.prefs.setBoolPref('uc.alt-click-split-view.enabled',true);
          Services.prefs.setBoolPref('uc.alt-click-split-view.focus-on-hover',false);
          Services.prefs.setBoolPref('browser.tabs.closeWindowWithLastTab',false);
          Services.prefs.setBoolPref('browser.tabs.warnOnClose',false);
          return true;
        """)
        observer_path = args.profile / "chrome/sine-mods/alt-click-split-view" / (
            "close-test-" + uuid.uuid4().hex + ".js")
        observer_path.write_text("""
          (() => {
            if (!Services.dirsvc.get('ProfD',Ci.nsIFile).path.includes('test-profile'))
              throw new Error('Not a disposable profile');
            window.__splitCloseProbe?.destroy();
            const probe={events:[]};
            const record=e=>probe.events.push({type:e.type,tab:e.target.id,
              selected:gBrowser.selectedTab.id,previous:e.detail?.previousTab?.id});
            for(const name of ['TabSelect','TabClose'])window.addEventListener(name,record,true);
            probe.destroy=()=>{
              for(const name of ['TabSelect','TabClose'])window.removeEventListener(name,record,true);
              delete window.__splitCloseProbe;
            };
            window.__splitCloseProbe=probe;
          })();
        """)
        m.js("""
          Services.scriptloader.loadSubScriptWithOptions(arguments[0],{target:window,ignoreCache:true});
          return true;
        """, ["chrome://sine/content/alt-click-split-view/" + observer_path.name])

        for count in [2, 3, 4]:
            for other_split in [False, True]:
                name = f"background_{count}_{'split' if other_split else 'ordinary'}"
                before = setup(name, count, other_split=other_split)
                layout = m.js("return JSON.stringify(gZenViewSplitter.storeDataForSessionStore().filter(g=>g.groupId!==__splitCloseFixture.group.groupId));")
                middle_group()
                closed_group()
                events = transitions(name)
                check(name + "_focus_unchanged", m.js("return gBrowser.selectedTab.id;") ==
                      before["selected"] and not any(e["type"] == "TabSelect" for e in events))
                check(name + "_only_target_group_closed", sorted(e["tab"] for e in events
                      if e["type"] == "TabClose") == sorted(before["members"]))
                check(name + "_other_layouts_unchanged", layout == m.js(
                    "return JSON.stringify(gZenViewSplitter.storeDataForSessionStore());"))
                check(name + "_focused_draft_unchanged", page_state() == before["page"])
                preserved(before, name)

        for count in [2, 3, 4]:
            name = f"active_group_{count}"
            before = setup(name, count, active=0)
            middle_group()
            closed_group()
            events = transitions(name)
            check(name + "_no_intermediate_pane_selection",
                  not any(e["type"] == "TabSelect" and e["tab"] in before["members"] for e in events))
            check(name + "_keeper_survives", m.js("return __splitCloseFixture.keeper.isConnected;"))
            preserved(before, name)

        for kind in ["normal", "pinned", "essential"]:
            name = "single_unfocused_" + kind
            before = setup(name, 2, active=0, kind=kind)
            if kind == "normal":
                close_button(1)
            else:
                close_menu(1)
            wait("!__splitCloseFixture.members[1].isConnected")
            events = transitions(name)
            check(name + "_only_one_closed", m.js("return __splitCloseFixture.members[0].isConnected;")
                  and [e["tab"] for e in events if e["type"] == "TabClose"] == [before["members"][1]])
            check(name + "_focus_unchanged", m.js("return gBrowser.selectedTab.id;") ==
                  before["selected"] and not any(e["type"] == "TabSelect" for e in events))
            check(name + "_draft_unchanged", page_state() == before["page"])
            preserved(before, name)

        for count in [2, 3, 4]:
            name = f"selected_keyboard_{count}"
            before = setup(name, count, active=0)
            m.js("__splitCloseFixture.members[0].owner=__splitCloseFixture.keeper;return true;")
            accel = "\ue03d" if m.js("return Services.appinfo.OS;") == "Darwin" else "\ue009"
            key("w", [accel])
            wait("!__splitCloseFixture.members[0].isConnected")
            events = transitions(name)
            check(name + "_stays_in_split", m.js("return __splitCloseFixture.members.slice(1).includes(gBrowser.selectedTab);"))
            check(name + "_only_selected_pane_closed",
                  [e["tab"] for e in events if e["type"] == "TabClose"] == [before["members"][0]])
            check(name + "_no_opener_detour",
                  all(e["tab"] in before["members"][1:] for e in events if e["type"] == "TabSelect"))
            preserved(before, name)

        name = "programmatic_single"
        before = setup(name, 3)
        m.js("gBrowser.removeTab(__splitCloseFixture.members[1],{animate:false});return true;")
        wait("!__splitCloseFixture.members[1].isConnected")
        check(name + "_not_expanded", m.js("return __splitCloseFixture.members.filter(t=>t.isConnected).length===2;"))
        check(name + "_focus_unchanged", m.js("return gBrowser.selectedTab.id;") == before["selected"])
        preserved(before, name)

        name = "programmatic_selected"
        before = setup(name, 3, active=0)
        m.js("""
          __splitCloseFixture.members[0].owner=__splitCloseFixture.keeper;
          gBrowser.removeTab(__splitCloseFixture.members[0],{animate:false,skipPermitUnload:true});
          return true;
        """)
        wait("!__splitCloseFixture.members[0].isConnected")
        check(name + "_native_focus_unchanged",
              m.js("return gBrowser.selectedTab===__splitCloseFixture.keeper;"))
        check(name + "_not_expanded", m.js("return __splitCloseFixture.members.filter(t=>t.isConnected).length===2;"))
        preserved(before, name)

        name = "background_context_menu"
        before = setup(name, 3, other_split=True)
        close_menu(1)
        wait("!__splitCloseFixture.members[1].isConnected")
        check(name + "_only_one_pane_closed",
              m.js("return __splitCloseFixture.members.filter(t=>t.isConnected).length===2;"))
        check(name + "_focus_unchanged", m.js("return gBrowser.selectedTab.id;") == before["selected"]
              and not any(e["type"] == "TabSelect" for e in transitions(name)))
        preserved(before, name)

        for action in ["cancel", "accept"]:
            name = "prompt_" + action
            before = setup(name, 3)
            select("__splitCloseFixture.members[1]")
            content()
            pointer(m.command("WebDriver:FindElement", {"using": "css selector", "value": "#arm"}))
            chrome()
            wait("__splitCloseFixture.members[1].linkedBrowser.hasBeforeUnload")
            select("__splitCloseFixture.keeper")
            begin_trace()
            middle_group()
            alert(action)
            if action == "cancel":
                check(name + "_entire_group_preserved", m.js("return __splitCloseFixture.members.every(t=>t.isConnected&&!t.closing);"))
                check(name + "_no_tab_closed", not any(e["type"] == "TabClose" for e in transitions(name)))
            else:
                closed_group()
                check(name + "_all_panes_closed", len([e for e in transitions(name)
                      if e["type"] == "TabClose"]) == 3)
            preserved(before, name)

        name = "reload"
        before = setup(name, 3)
        reload_mod()
        check(name + "_documents_unchanged", identities() == before["identities"])
        check(name + "_selection_unchanged", m.js("return gBrowser.selectedTab.id;") == before["selected"])
        middle_group()
        closed_group()
        check(name + "_closed_once", len([e for e in transitions(name) if e["type"] == "TabClose"]) == 3)

        name = "disabled"
        setup(name, 3)
        m.js("AltClickSplitView.destroy({reloading:true});return true;")
        middle_group()
        wait("!__splitCloseFixture.members[0].isConnected")
        check(name + "_native_middle_click_restored",
              m.js("return __splitCloseFixture.members.filter(t=>t.isConnected).length===2;"))
        reload_mod()
        report["passed"] = True
    finally:
        try:
            with suppress(RuntimeError):
                m.command("WebDriver:DismissAlert")
            chrome()
            m.js("window.__splitCloseProbe?.destroy();return true;")
        finally:
            m.close()
            if observer_path:
                observer_path.unlink(missing_ok=True)
            server.shutdown()
            server.server_close()
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--port", type=int, default=2832)
    parser.add_argument("--report", required=True, type=Path)
    run(parser.parse_args())
