"""Multi Tab Move checks restricted to a disposable running Zen profile."""

import argparse
from collections import Counter
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tree-tabs-prototype/tests"))
from runtime import Marionette


COUNTS = Counter()
PAGE = b"""<!doctype html><meta charset=utf-8><title>Multi Tab Move fixture</title>
<style>body{font:18px system-ui;margin:30px}input{margin:20px}</style>
<h1>Multi Tab Move fixture</h1><input id=draft value="Keep this draft">
<button id=arm>Protect unsaved draft</button>
<script>
document.documentElement.dataset.marker=crypto.randomUUID();
document.getElementById('arm').onclick=()=>{
  window.onbeforeunload=e=>{e.preventDefault();e.returnValue='';};
};
</script>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(PAGE)))
            self.end_headers()
            self.wfile.write(PAGE)
            COUNTS[self.path] += 1
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *_):
        pass


class Server(ThreadingHTTPServer):
    request_queue_size = 128
    daemon_threads = True


class PromptMarionette(Marionette):
    def command(self, name, params=None):
        if name == "WebDriver:NewSession":
            params["capabilities"]["alwaysMatch"]["unhandledPromptBehavior"] = "ignore"
        return super().command(name, params)


STATE = """
const f=window.mt;
return {
  order:[...gZenWorkspaces.allStoredTabs].filter(t=>f.tabs.includes(t)).map(t=>f.tabs.indexOf(t)),
  parents:f.tabs.map(t=>f.tabs.indexOf(TreeTabs.parentOf(t))),
  collapsed:f.tabs.map(t=>t.hasAttribute('uc-tree-collapsed')),
  hidden:f.tabs.map(t=>t.hasAttribute('uc-tree-hidden')),
  selected:f.tabs.indexOf(gBrowser.selectedTab),
  spaces:f.tabs.map(t=>t.getAttribute('zen-workspace-id')),
  documents:f.tabs.map(t=>[t.linkedBrowser?.browsingContext?.id,
    t.linkedBrowser?.browsingContext?.currentWindowGlobal?.innerWindowId]),
  splitSame:f.a.group===f.split && f.b.group===f.split && f.c.group===f.split,
  layout:JSON.stringify(gZenViewSplitter.storeDataForSessionStore()),
  splitOrder:f.split.tabs.map(t=>f.tabs.indexOf(t)),
  splitVisible:[f.a,f.b,f.c].every(t=>t.isConnected&&!t.hasAttribute('uc-tree-hidden')&&
    getComputedStyle(t).display!=='none'),
  selection:MultiTabMove.snapshot(),
  nativeSelection:gBrowser.multiSelectedTabsCount,
  error:MultiTabMove.lastError||TreeTabs.lastError||null,
};
"""


def run(args):
    report = {"checks": {}, "pointerDrag": False}
    server = Server(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    m = PromptMarionette(args.port)
    fixture_count = 0

    def wait(expression, timeout=20):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = m.js("return (" + expression + ");")
            if value:
                return value
            time.sleep(.04)
        raise AssertionError("Timed out: " + expression)

    def check(name, condition, detail=None):
        report["checks"][name] = {"passed": bool(condition), "detail": detail}
        assert condition, f"{name}: {detail}"
        print("PASS", name, flush=True)

    def settle():
        time.sleep(.25)

    def pointer(expression, shift=False, button=0):
        element = m.js("return " + expression + ";")
        try:
            if shift:
                m.command("WebDriver:PerformActions", {"actions": [{
                    "type": "key", "id": "keys",
                    "actions": [{"type": "keyDown", "value": "\ue008"}],
                }]})
            m.command("WebDriver:PerformActions", {"actions": [{
                "type": "pointer", "id": "mouse", "parameters": {"pointerType": "mouse"},
                "actions": [
                    {"type": "pointerMove", "origin": element, "x": 0, "y": 0},
                    {"type": "pointerDown", "button": button},
                    {"type": "pointerUp", "button": button},
                ],
            }]})
        finally:
            m.command("WebDriver:ReleaseActions")
        settle()

    def drag_rows(start_expression, end_expression, cancel=False):
        start = m.js("return " + start_expression + ";")
        end = m.js("return " + end_expression + ";")
        m.command("WebDriver:PerformActions", {"actions": [{
            "type": "pointer", "id": "mouse", "parameters": {"pointerType": "mouse"},
            "actions": [
                {"type": "pointerMove", "origin": start, "x": 0, "y": 0},
                {"type": "pointerDown", "button": 0},
                {"type": "pointerMove", "origin": start, "x": 12, "y": 8, "duration": 200},
                {"type": "pointerMove", "origin": end, "x": 0, "y": 8, "duration": 400},
            ],
        }]})
        if cancel:
            m.command("WebDriver:PerformActions", {"actions": [{
                "type": "key", "id": "keys",
                "actions": [{"type": "keyDown", "value": "\ue00c"}, {"type": "keyUp", "value": "\ue00c"}],
            }]})
        m.command("WebDriver:PerformActions", {"actions": [{
            "type": "pointer", "id": "mouse", "parameters": {"pointerType": "mouse"},
            "actions": [{"type": "pointerUp", "button": 0}],
        }]})
        m.command("WebDriver:ReleaseActions")
        settle()

    def fixture(four_panes=False):
        nonlocal fixture_count
        fixture_count += 1
        m.async_js("await gZenWorkspaces.changeWorkspaceWithID(arguments[0]);", [source])
        m.js("""
          MultiTabMove.clear();
          for(const t of [...gZenWorkspaces.allStoredTabs])
            if(!t.hasAttribute('zen-empty-tab'))
              gBrowser.removeTab(t,{animate:false,skipPermitUnload:true});
          const names=['before','root','child','grandchild','sibling','middle','a','b','c','after'];
          const tabs=names.map(name=>gBrowser.addTrustedTab(arguments[0]+'/'+name,
            {inBackground:true,skipRoute:true}));
          gBrowser.moveTabsAfter(tabs.slice(1),tabs[0]);
          window.mt={tabs,...Object.fromEntries(names.map((name,i)=>[name,tabs[i]]))};
          gBrowser.selectedTab=mt.before;
        """, [base + f"/case-{fixture_count}"])
        wait("mt.tabs.every(t=>!t.hasAttribute('busy')&&"
             "t.linkedBrowser.browsingContext?.currentWindowGlobal?.documentURI.spec.startsWith(" +
             json.dumps(base) + "))")
        settle()
        m.js("""
          TreeTabs.nest(mt.child,mt.root);
          TreeTabs.nest(mt.grandchild,mt.child);
          TreeTabs.nest(mt.sibling,mt.root);
          gZenViewSplitter.splitTabs([mt.a,mt.b,mt.c,...(arguments[0]?[mt.middle]:[])],
            'vsep',0,{activate:false});
          mt.split=mt.a.group;
          gBrowser.selectedTab=mt.before;
        """, [four_panes])
        settle()
        state = m.js(STATE)
        assert state["parents"] == [-1, -1, 1, 2, 1, -1, -1, -1, -1, -1], state
        return state

    def preserved(name, before, same_tree=True):
        settle()
        state = m.js(STATE)
        check(name + "_documents", state["documents"] == before["documents"])
        check(name + "_split", state["splitSame"] and state["splitVisible"] and
              state["layout"] == before["layout"] and state["splitOrder"] == before["splitOrder"], state)
        if same_tree:
            check(name + "_tree", state["parents"] == before["parents"] and
                  state["collapsed"] == before["collapsed"] and state["hidden"] == before["hidden"])
        check(name + "_no_errors", not state["error"] and state["nativeSelection"] == 0, state["error"])
        return state

    def context_action(action, row="mt.root"):
        pointer(row + ".querySelector('.tab-label')", button=2)
        wait("document.getElementById('uc-multi-tab-menu').state==='open'")
        pointer("document.getElementById(" + json.dumps("uc-multi-tab-" + action) + ")")

    def alert(action, text=None):
        deadline = time.monotonic() + 8
        while True:
            try:
                message = m.command("WebDriver:GetAlertText")
                assert message, "Expected a native prompt"
                break
            except RuntimeError as error:
                if "no such alert" not in str(error) or time.monotonic() >= deadline:
                    raise
                time.sleep(.05)
        if text is not None:
            m.command("WebDriver:SendAlertText", {"text": text})
        m.command("WebDriver:DismissAlert" if action == "cancel" else "WebDriver:AcceptAlert")
        settle()
        return message

    try:
        actual = m.js('return Services.dirsvc.get("ProfD",Ci.nsIFile).path;')
        assert Path(actual).resolve() == args.profile.resolve() and "test-profile" in actual
        main = m.command("WebDriver:GetWindowHandle")
        wait("window.TreeTabs?.status==='ready'&&window.MultiTabMove?.status==='ready'")
        m.js("Services.prefs.setBoolPref('uc.multi-tab-move.enabled',true);Services.prefs.setBoolPref('uc.tree-tabs.enabled',true);")
        m.command("WebDriver:SetWindowRect", {"width": 1400, "height": 1100})
        source = m.js("return gZenWorkspaces.activeWorkspace;")
        target = m.async_js("""
          const existing=gZenWorkspaces.getWorkspaces().find(s=>s.name==='Multi move destination');
          return existing?.uuid || (await gZenWorkspaces.createAndSaveWorkspace('Multi move destination')).uuid;
        """)
        report["versions"] = m.js("return {tree:TreeTabs.version,multi:MultiTabMove.version,zen:Services.appinfo.version};")

        before = fixture()
        pointer("mt.root.querySelector('.tab-label')", shift=True)
        state = m.js(STATE)
        check("shift_click_selects_only_clicked_branch", len(state["selection"]["explicit"]) == 1 and
              state["selection"]["tabs"] == m.js("return [mt.root,mt.child,mt.grandchild,mt.sibling].map(t=>t.id);"),
              state["selection"])
        check("shift_selection_does_not_switch_tabs", state["selected"] == 0)
        pointer("mt.middle.querySelector('.tab-label')", shift=True)
        check("shift_click_toggles_noncontiguous_row", len(m.js(STATE)["selection"]["explicit"]) == 2)
        pointer("mt.middle.querySelector('.tab-label')", shift=True)
        check("shift_click_deselects_row", len(m.js(STATE)["selection"]["explicit"]) == 1)
        pointer("mt.a.querySelector('.tab-label')", shift=True)
        state = m.js(STATE)
        check("split_row_selects_all_three_panes", m.js("return [mt.a,mt.b,mt.c].every(t=>MultiTabMove.snapshot().tabs.includes(t.id));"))
        check("selection_keeps_native_close_scope", state["nativeSelection"] == 0)
        preserved("selection", before)

        if args.pointer_drag:
            start = m.js("return mt.root.querySelector('.tab-label');")
            end = m.js("return mt.after.querySelector('.tab-label');")
            try:
                m.command("WebDriver:PerformActions", {"actions": [{
                    "type": "pointer", "id": "mouse", "parameters": {"pointerType": "mouse"},
                    "actions": [
                        {"type": "pointerMove", "origin": start, "x": 0, "y": 0},
                        {"type": "pointerDown", "button": 0},
                        {"type": "pointerMove", "origin": start, "x": 12, "y": 8, "duration": 250},
                        {"type": "pause", "duration": 150},
                        {"type": "pointerMove", "origin": end, "x": 0, "y": 10, "duration": 800},
                        {"type": "pause", "duration": 150},
                        {"type": "pointerUp", "button": 0},
                    ],
                }]})
            finally:
                m.command("WebDriver:ReleaseActions")
            state = preserved("pointer_drag", before)
            check("pointer_drag_moved_tree_and_split", state["order"] == [0, 5, 9, 1, 2, 3, 4, 6, 7, 8], state)
            report["pointerDrag"] = "WebDriver pointer"
        else:
            m.js("MultiTabMove.move({workspace:gZenWorkspaces.activeWorkspace,anchor:mt.after,before:false});")
            state = preserved("move_down", before)
            check("tree_and_split_order_down", state["order"] == [0, 5, 9, 1, 2, 3, 4, 6, 7, 8], state)

        m.js("MultiTabMove.move({workspace:gZenWorkspaces.activeWorkspace,anchor:mt.before,before:true});")
        state = preserved("move_up", before)
        check("tree_and_split_order_up", state["order"] == [1, 2, 3, 4, 6, 7, 8, 0, 5, 9], state)
        check("moving_keeps_focused_tab", state["selected"] == 0)

        before = fixture()
        m.js("MultiTabMove.toggle(mt.root);MultiTabMove.toggle(mt.b);")
        if args.pointer_drag:
            drag_rows("mt.b.querySelector('.tab-label')", "mt.after.querySelector('.tab-label')")
            state = preserved("drag_from_split_pane", before)
            check("dragging_split_carries_other_selection", state["order"] == [0, 5, 9, 1, 2, 3, 4, 6, 7, 8], state)

            before = fixture()
            m.js("MultiTabMove.toggle(mt.root);MultiTabMove.toggle(mt.a);")
            drag_rows("mt.root.querySelector('.tab-label')", "mt.after.querySelector('.tab-label')", cancel=True)
            state = preserved("cancelled_drag", before)
            check("escape_during_drag_does_not_move", state["order"] == before["order"] and
                  not state["selection"]["dragging"] and not state["selection"]["explicit"], state)

        before = fixture()
        m.js("TreeTabs.toggleCollapse(mt.root);MultiTabMove.toggle(mt.root);MultiTabMove.toggle(mt.child);MultiTabMove.toggle(mt.b);")
        before = m.js(STATE)
        m.js("MultiTabMove.move({workspace:gZenWorkspaces.activeWorkspace,anchor:mt.after,before:false});")
        state = preserved("collapsed_branch", before)
        check("parent_and_child_not_moved_twice", state["order"] == [0, 5, 9, 1, 2, 3, 4, 6, 7, 8])
        check("collapsed_children_stay_collapsed", all(state["hidden"][i] for i in [2, 3, 4]))

        m.async_js("return await MultiTabMove.moveToSpace(arguments[0]);", [target])
        state = preserved("space_move", before)
        check("all_branch_and_split_members_change_space",
              all(state["spaces"][i] == target for i in [1, 2, 3, 4, 6, 7, 8]) and
              all(state["spaces"][i] == source for i in [0, 5, 9]), state)
        check("space_move_order", [i for i in state["order"] if i in [1, 2, 3, 4, 6, 7, 8]] ==
              [1, 2, 3, 4, 6, 7, 8], state)
        m.async_js("return await MultiTabMove.moveToSpace(arguments[0]);", [source])
        preserved("space_round_trip", before)

        before = fixture()
        m.js("MultiTabMove.toggle(mt.root);MultiTabMove.toggle(mt.a);")
        pointer("mt.root.querySelector('.tab-label')", button=2)
        check("selection_context_menu_opens", m.js("return document.getElementById('uc-multi-tab-menu').state==='open';"))
        check("context_menu_has_destination", m.js("""
          return [...document.querySelectorAll('#uc-multi-tab-menu menuitem')].some(
            e=>e.getAttribute('data-workspace-id')===arguments[0]&&!e.disabled);
        """, [target]))
        m.js("""
          const entry=[...document.querySelectorAll('#uc-multi-tab-menu menuitem')].find(
            e=>e.getAttribute('data-workspace-id')===arguments[0]);
          document.getElementById('uc-multi-tab-menu').hidePopup();
          entry.doCommand();
        """, [target])
        wait("gZenWorkspaces.activeWorkspace===" + json.dumps(target))
        state = preserved("context_space_command", before)
        check("context_command_moves_whole_selection", all(state["spaces"][i] == target
              for i in [1, 2, 3, 4, 6, 7, 8]))

        if args.pointer_drag:
            before = fixture()
            m.js("MultiTabMove.toggle(mt.root);MultiTabMove.toggle(mt.a);window.mtTargetSpace=arguments[0];", [target])
            icon = "[...gZenWorkspaces.workspaceIcons.children].find(e=>e.getAttribute('zen-workspace-id')===mtTargetSpace)"
            check("space_icon_available", m.js("return (" + icon + ").getBoundingClientRect().width>0;"))
            drag_rows("mt.root.querySelector('.tab-label')", icon)
            wait("gZenWorkspaces.activeWorkspace===" + json.dumps(target))
            state = preserved("space_icon_drop", before)
            check("space_icon_moves_selection", all(state["spaces"][i] == target
                  for i in [1, 2, 3, 4, 6, 7, 8]))

        before = fixture(four_panes=True)
        m.js("MultiTabMove.toggle(mt.root);MultiTabMove.toggle(mt.a);MultiTabMove.move({workspace:gZenWorkspaces.activeWorkspace,anchor:mt.after,before:false});")
        state = preserved("four_pane_move", before)
        check("all_four_panes_move_as_one_session", len(state["splitOrder"]) == 4 and
              state["order"] == [0, 9] + [i for i in before["order"] if i not in [0, 9]], state)

        before = fixture()
        m.js("""
          window.mtFolder=gZenFolders.createFolder([mt.middle],{label:'Move test folder',renameFolder:false});
          MultiTabMove.toggle(mtFolder);MultiTabMove.toggle(mt.a);
          window.mtFolderTabs=[...mtFolder.tabs];
        """)
        settle()
        before = m.js(STATE)
        m.async_js("return await MultiTabMove.moveToSpace(arguments[0]);", [target])
        preserved("folder_and_split_space_move", before)
        check("native_folder_identity_and_contents_survive", m.js("""
          return mt.middle.group===mtFolder && mtFolderTabs.every(t=>mtFolder.tabs.includes(t)) &&
            mtFolder.tabs.every(t=>t.getAttribute('zen-workspace-id')===arguments[0]) &&
            mtFolder.getAttribute('zen-workspace-id')===arguments[0] && mt.middle.pinned;
        """, [target]))
        check("mixed_pinned_selection_stays_in_its_sections", m.js("""
          const space=gZenWorkspaces.workspaceElement(arguments[0]);
          return space.pinnedTabsContainer.contains(mtFolder) && space.tabsContainer.contains(mt.a.group);
        """, [target]))

        before = fixture()
        m.js("MultiTabMove.toggle(mt.child);MultiTabMove.toggle(mt.b);MultiTabMove.move({workspace:gZenWorkspaces.activeWorkspace,anchor:mt.after,before:false});")
        state = preserved("child_branch", before, same_tree=False)
        check("moving_child_detaches_only_branch_root",
              state["parents"] == [-1, -1, -1, 2, 1, -1, -1, -1, -1, -1], state)

        before = fixture()
        m.js("""
          MultiTabMove.toggle(mt.root);MultiTabMove.toggle(mt.a);
          const native=gBrowser.moveTabsAfter;
          gBrowser.moveTabsAfter=function(...args){native.apply(this,args);throw new Error('Injected move failure');};
          try{MultiTabMove.move({workspace:gZenWorkspaces.activeWorkspace,anchor:mt.after,before:false});}
          catch(e){window.mtRollbackError=String(e);}
          finally{gBrowser.moveTabsAfter=native;}
        """)
        state = preserved("rollback", before)
        check("failed_move_restores_order", state["order"] == before["order"] and
              m.js("return mtRollbackError.includes('Injected move failure');"), state)

        before = fixture()
        m.js("""
          MultiTabMove.toggle(mt.root);MultiTabMove.toggle(mt.a);
          const status=TreeTabs.status;TreeTabs.status='starting';
          try{MultiTabMove.move({workspace:gZenWorkspaces.activeWorkspace,anchor:mt.after,before:false});}
          catch(error){window.mtStartupError=String(error);}
          finally{TreeTabs.status=status;}
        """)
        state = preserved("tree_startup_guard", before)
        check("incomplete_tree_cannot_move_without_its_children", state["order"] == before["order"] and
              m.js("return mtStartupError.includes('finish loading');"), state)

        before = fixture()
        m.js("MultiTabMove.toggle(mt.root);MultiTabMove.toggle(mt.b);")
        pointer("mt.root.querySelector('.uc-tree-twisty')", shift=True)
        check("shift_twisty_is_native_not_selection_toggle", len(m.js(STATE)["selection"]["explicit"]) == 2)
        m.command("WebDriver:PerformActions", {"actions": [{
            "type": "key", "id": "keys",
            "actions": [{"type": "keyDown", "value": "\ue00c"}, {"type": "keyUp", "value": "\ue00c"}],
        }]})
        m.command("WebDriver:ReleaseActions")
        check("escape_clears_selection", not m.js(STATE)["selection"]["explicit"])
        m.js("MultiTabMove.toggle(mt.root);")
        pointer("mt.after.querySelector('.tab-label')")
        check("plain_click_clears_and_selects", not m.js(STATE)["selection"]["explicit"] and
              m.js("return gBrowser.selectedTab===mt.after;"))

        before = fixture()
        m.js("""
          window.mtLazy=gBrowser.addTrustedTab(arguments[0]+'/sleeping',{createLazyBrowser:true,inBackground:true,skipRoute:true});
          mtLazy.setAttribute('label','Sleeping tab');
        """, [base])
        wait("mtLazy.hasAttribute('pending')")
        pointer("mtLazy.querySelector('.tab-label')", shift=True)
        check("shift_selection_does_not_load_sleeping_tab", m.js("return mtLazy.hasAttribute('pending') && gBrowser.selectedTab===mt.before;"))
        m.js("MultiTabMove.move({workspace:gZenWorkspaces.activeWorkspace,anchor:mt.before,before:true});")
        check("moving_does_not_load_sleeping_tab", m.js("return mtLazy.hasAttribute('pending');") and not COUNTS["/sleeping"])

        before = fixture()
        m.js("MultiTabMove.toggle(mt.root);MultiTabMove.toggle(mt.b);")
        before = m.js(STATE)
        m.js("""
          Services.prefs.setBoolPref('uc.multi-tab-move.enabled',false);
        """)
        check("disable_clears_owned_styles", m.js("return [...gZenWorkspaces.allStoredTabs].every(t=>!t.hasAttribute('uc-multi-tab-selected')&&!t.hasAttribute('uc-multi-tab-carried'));"))
        check("disabled_mod_cannot_move", m.js("return MultiTabMove.move({workspace:gZenWorkspaces.activeWorkspace,anchor:mt.after,before:false})===false;"))
        m.js("Services.prefs.setBoolPref('uc.multi-tab-move.enabled',true);MultiTabMove.toggle(mt.root);")
        m.js("""
          Services.scriptloader.loadSubScriptWithOptions(
            'chrome://sine/content/multi-tab-move/multi-tab-move.uc.js',{target:window,ignoreCache:true});
        """)
        wait("MultiTabMove.status==='ready'")
        state = preserved("hot_reload", before)
        check("hot_reload_clears_selection_without_moving", not state["selection"]["explicit"] and state["order"] == before["order"])
        check("owned_ui_not_duplicated", m.js("return document.querySelectorAll('#uc-multi-tab-menu').length===1 && document.querySelectorAll('#uc-multi-tab-indicator').length===1;"))
        before = fixture()
        m.js("MultiTabMove.toggle(mt.root);MultiTabMove.toggle(mt.a);")
        context_action("close")
        wait("[mt.root,mt.child,mt.grandchild,mt.sibling,mt.a,mt.b,mt.c].every(t=>!t.isConnected)")
        check("close_selection_closes_whole_branch_and_split", m.js("""
          return !mt.split.isConnected &&
            !gZenViewSplitter._data.some(g=>g.tabs.some(t=>[mt.a,mt.b,mt.c].includes(t)));
        """))
        check("close_selection_keeps_unselected_tabs_and_focus", m.js("""
          return [mt.before,mt.middle,mt.after].every(t=>t.isConnected&&!t.closing) &&
            gBrowser.selectedTab===mt.before;
        """))
        check("close_selection_preserves_surviving_documents", m.js(STATE)["documents"][0] == before["documents"][0])
        check("close_selection_clears_only_closed_rows", not m.js("return MultiTabMove.snapshot().tabs.length;"))
        check("close_selection_keeps_window", m.js("return !window.closed;"))

        before = fixture()
        m.js("MultiTabMove.toggle(mt.child);")
        context_action("close", "mt.child")
        wait("!mt.child.isConnected&&!mt.grandchild.isConnected")
        check("close_child_branch_keeps_parent_and_sibling", m.js("""
          return mt.root.isConnected&&mt.sibling.isConnected&&TreeTabs.parentOf(mt.sibling)===mt.root;
        """))
        check("close_child_branch_keeps_unselected_split", m.js(STATE)["layout"] == before["layout"] and
              m.js(STATE)["splitSame"])

        for action in ["cancel", "accept"]:
            before = fixture()
            m.js("gBrowser.selectedTab=mt.b;")
            m.command("WebDriver:SwitchToWindow", {"handle": main})
            m.command("Marionette:SetContext", {"value": "content"})
            pointer("document.getElementById('arm')")
            m.command("Marionette:SetContext", {"value": "chrome"})
            wait("mt.b.linkedBrowser.hasBeforeUnload")
            m.js("gBrowser.selectedTab=mt.before;MultiTabMove.toggle(mt.root);MultiTabMove.toggle(mt.a);")
            selected_ids = m.js("return MultiTabMove.snapshot().tabs;")
            context_action("close")
            check("close_native_prompt_" + action, bool(alert(action)))
            if action == "cancel":
                state = preserved("cancel_close", before)
                check("cancel_close_preserves_every_selected_tab", m.js("""
                  return mt.tabs.every(t=>t.isConnected&&!t.closing);
                """) and state["selection"]["tabs"] == selected_ids)
            else:
                wait("[mt.root,mt.child,mt.grandchild,mt.sibling,mt.a,mt.b,mt.c].every(t=>!t.isConnected)")
                check("accept_close_removes_entire_selection", m.js("return !mt.split.isConnected;"))
                check("accept_close_preserves_other_tabs", m.js("""
                  return [mt.before,mt.middle,mt.after].every(t=>t.isConnected&&!t.closing);
                """))

        for action, name in [("cancel", None), ("accept", "   ")]:
            before = fixture()
            spaces = m.js("return gZenWorkspaces.getWorkspaces().map(s=>s.uuid);")
            m.js("MultiTabMove.toggle(mt.root);MultiTabMove.toggle(mt.a);")
            context_action("new-space")
            check("new_space_native_prompt_" + action, bool(alert(action, name)))
            state = preserved("new_space_" + action, before)
            check("new_space_" + action + "_does_not_create_or_move",
                  m.js("return gZenWorkspaces.getWorkspaces().map(s=>s.uuid);") == spaces and
                  state["order"] == before["order"] and state["spaces"] == before["spaces"] and
                  state["selected"] == before["selected"])

        before = fixture()
        m.js("""
          TreeTabs.toggleCollapse(mt.root);
          gBrowser.pinTab(mt.middle);
          gBrowser.selectedTab=mt.b;
          MultiTabMove.toggle(mt.root);MultiTabMove.toggle(mt.a);MultiTabMove.toggle(mt.middle);
        """)
        before = m.js(STATE)
        spaces = m.js("return gZenWorkspaces.getWorkspaces().map(s=>s.uuid);")
        context_action("new-space")
        alert("accept", "  Selection action space  ")
        wait("gZenWorkspaces.getActiveWorkspace().name==='Selection action space'")
        destination_id = m.js("return gZenWorkspaces.activeWorkspace;")
        check("new_space_created_once_with_name", destination_id not in spaces and
              len(m.js("return gZenWorkspaces.getWorkspaces();")) == len(spaces) + 1)
        state = preserved("new_space_moves_selection", before)
        check("new_space_contains_whole_selection", all(state["spaces"][i] == destination_id
              for i in [1, 2, 3, 4, 5, 6, 7, 8]))
        check("new_space_leaves_unselected_tabs_in_source", state["spaces"][0] == source and
              state["spaces"][9] == source)
        check("new_space_keeps_active_split_pane_and_pin", state["selected"] == 7 and
              m.js("return mt.middle.pinned;"))
        check("new_space_preserves_container", m.js("""
          return gZenWorkspaces.getActiveWorkspace().containerTabId ===
            gZenWorkspaces.getWorkspaceFromId(arguments[0]).containerTabId;
        """, [source]))

        before = fixture()
        spaces = m.js("return gZenWorkspaces.getWorkspaces().map(s=>s.uuid);")
        m.js("""
          MultiTabMove.toggle(mt.root);MultiTabMove.toggle(mt.a);
          window.mtOriginalMove=TreeTabs.moveBranches;
          TreeTabs.moveBranches=()=>{throw new Error('Injected create-space move failure');};
        """)
        context_action("new-space")
        alert("accept", "Failed move should not leave a Space")
        wait("MultiTabMove.lastError?.includes('Injected create-space move failure')")
        m.js("TreeTabs.moveBranches=mtOriginalMove;delete MultiTabMove.lastError;")
        state = preserved("failed_new_space", before)
        check("failed_new_space_removes_only_empty_created_space",
              m.js("return gZenWorkspaces.getWorkspaces().map(s=>s.uuid);") == spaces and
              state["spaces"] == before["spaces"] and state["order"] == before["order"])

        before = fixture()
        m.js("""
          MultiTabMove.toggle(mt.root);MultiTabMove.toggle(mt.a);
          window.mtOriginalPreflight=gBrowser.runBeforeUnloadForTabs;
          window.mtCloseGate=Promise.withResolvers();
          gBrowser.runBeforeUnloadForTabs=()=>mtCloseGate.promise;
          window.mtCloseResult=MultiTabMove.closeSelection();
        """)
        check("duplicate_close_is_ignored", m.async_js("return await MultiTabMove.closeSelection();") is False)
        m.js("MultiTabMove.destroy();mtCloseGate.resolve(false);")
        check("unload_during_close_aborts", m.async_js("return await mtCloseResult;") is False)
        m.js("""
          gBrowser.runBeforeUnloadForTabs=mtOriginalPreflight;
          Services.scriptloader.loadSubScriptWithOptions(
            'chrome://sine/content/multi-tab-move/multi-tab-move.uc.js',{target:window,ignoreCache:true});
        """)
        wait("MultiTabMove.status==='ready'")
        state = preserved("unload_during_close", before)
        check("unload_during_close_keeps_every_tab", m.js("return mt.tabs.every(t=>t.isConnected&&!t.closing);"))
        check("all_pages_loaded_once", all(count == 1 for path, count in COUNTS.items() if "/case-" in path and not path.endswith("favicon.ico")), dict(COUNTS))
    finally:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        try:
            with suppress(RuntimeError):
                m.command("WebDriver:DismissAlert")
            m.command("Marionette:SetContext", {"value": "chrome"})
            m.js("""
              if(window.mtOriginalPreflight)gBrowser.runBeforeUnloadForTabs=mtOriginalPreflight;
              if(window.mtOriginalMove)TreeTabs.moveBranches=mtOriginalMove;
            """)
        finally:
            m.close()
            server.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--port", type=int, default=2832)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--pointer-drag", action="store_true")
    run(parser.parse_args())
