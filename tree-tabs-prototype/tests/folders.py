"""Folder/branch integration using a guarded, disposable Zen profile."""

import argparse
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time

from runtime import Marionette


REQUESTS = Counter()
PAGE = b"""<!doctype html><meta charset=utf-8><title>Folder trees test</title>
<style>body{font:18px system-ui;margin:40px}a,input{display:block;margin:20px}</style>
<h1>Folder trees</h1><input id=draft value="Keep this unfinished draft">
<button id=focus>Focus page</button>
<a id=next href="/opened">Open a child</a>
<a id=preview href="/preview" target=_blank>Open a Glance</a>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        REQUESTS[self.path] += 1
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(PAGE)

    def log_message(self, *_):
        pass


class FixtureServer(ThreadingHTTPServer):
    # Tab batches and speculative connections can exceed TCPServer's backlog.
    request_queue_size = 64


class PromptMarionette(Marionette):
    def command(self, name, params=None):
        if name == "WebDriver:NewSession":
            params["capabilities"]["alwaysMatch"]["unhandledPromptBehavior"] = "ignore"
        return super().command(name, params)


STATE = """
return {
  order:[...gZenWorkspaces.allStoredTabs].filter(t=>ft.tabs.includes(t)).map(t=>ft.tabs.indexOf(t)),
  parents:ft.tabs.map(t=>ft.tabs.indexOf(TreeTabs.parentOf(t))),
  documents:ft.tabs.map(t=>[t.linkedBrowser.browsingContext.id,
    t.linkedBrowser.browsingContext.currentWindowGlobal?.innerWindowId]),
  pinned:ft.tabs.map(t=>t.pinned),
  folders:ft.tabs.map(t=>t.group?.id||""),
  spaces:ft.tabs.map(t=>t.getAttribute("zen-workspace-id")),
  hidden:ft.tabs.map(t=>t.hasAttribute("uc-tree-hidden")),
  collapsed:ft.tabs.map(t=>TreeTabs.snapshot().find(n=>n.tab===t.id)?.collapsed||false),
  selected:ft.tabs.indexOf(gBrowser.selectedTab),
  errors:[TreeTabs.lastError,MultiTabMove.lastError].filter(Boolean)
};
"""


def run(args):
    report = {"checks": {}}
    server = FixtureServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    m = PromptMarionette(args.port)
    main = None
    original = None

    def wait(expression, timeout=15):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if value := m.js("return (" + expression + ");"):
                return value
            time.sleep(.05)
        raise AssertionError("Timed out: " + expression)

    def settle():
        time.sleep(.35)

    def check(name, expression, values=None):
        value = m.js("return (" + expression + ");", values)
        report["checks"][name] = value
        assert value, name
        print("PASS", name, flush=True)

    def preserved(name):
        settle()
        state = m.js(STATE)
        report["checks"][name] = state
        assert state["documents"] == original["documents"], name + ": documents changed"
        assert not state["errors"], state["errors"]
        print("PASS", name, flush=True)
        return state

    def chrome():
        m.command("Marionette:SetContext", {"value": "chrome"})

    def content():
        chrome()
        m.command("WebDriver:SwitchToWindow", {"handle": main})
        m.command("Marionette:SetContext", {"value": "content"})

    def pointer(expression, modifiers=()):
        element = m.js("return " + expression + ";")
        try:
            if modifiers:
                m.command("WebDriver:PerformActions", {"actions": [{
                    "type": "key", "id": "keys", "actions": [
                        {"type": "keyDown", "value": mod} for mod in modifiers],
                }]})
            m.command("WebDriver:PerformActions", {"actions": [{
                "type": "pointer", "id": "mouse", "parameters": {"pointerType": "mouse"},
                "actions": [
                    {"type": "pointerMove", "origin": element, "x": 0, "y": 0},
                    {"type": "pointerDown", "button": 0},
                    {"type": "pointerUp", "button": 0},
                ],
            }]})
        finally:
            m.command("WebDriver:ReleaseActions")
        settle()

    def drag(start_expression, target_expression, y=0):
        start = m.js("return " + start_expression + ";")
        end = m.js("return " + target_expression + ";")
        try:
            m.command("WebDriver:PerformActions", {"actions": [{
                "type": "pointer", "id": "mouse", "parameters": {"pointerType": "mouse"},
                "actions": [
                    {"type": "pointerMove", "origin": start, "x": 0, "y": 0},
                    {"type": "pointerDown", "button": 0},
                    {"type": "pointerMove", "origin": start, "x": 12, "y": 6, "duration": 150},
                    {"type": "pointerMove", "origin": end, "x": 0, "y": y, "duration": 300},
                    {"type": "pointerUp", "button": 0},
                ],
            }]})
        finally:
            m.command("WebDriver:ReleaseActions")
        settle()

    def shortcut(direction):
        content()
        m.js("document.getElementById('focus').focus();")
        arrow = "\ue014" if direction == "right" else "\ue012"
        try:
            m.command("WebDriver:PerformActions", {"actions": [{
                "type": "key", "id": "keys", "actions": [
                    {"type": "keyDown", "value": "\ue00a"},
                    {"type": "keyDown", "value": "\ue008"},
                    {"type": "keyDown", "value": arrow},
                    {"type": "keyUp", "value": arrow},
                    {"type": "keyUp", "value": "\ue008"},
                    {"type": "keyUp", "value": "\ue00a"},
                ],
            }]})
        finally:
            m.command("WebDriver:ReleaseActions")
            chrome()
        settle()

    try:
        actual = m.js('return Services.dirsvc.get("ProfD",Ci.nsIFile).path;')
        assert Path(actual).resolve() == args.profile.resolve() and "test-profile" in actual
        assert (args.profile / "folder-tree-test-profile").is_file()
        main = m.command("WebDriver:GetWindowHandle")
        wait("window.TreeTabs?.status==='ready' && window.MultiTabMove?.status==='ready'")
        # Other regression suites deliberately disable/unload Auto Glance.
        m.js("""
          Services.prefs.setBoolPref("uc.auto-glance.enabled",true);
          Services.prefs.setBoolPref("uc.auto-glance.modified-clicks",true);
          Services.prefs.setBoolPref("uc.auto-glance.cmd-click-background",true);
          Services.prefs.setBoolPref("zen.glance.enabled",true);
          if(window.AutoGlance?.status!=="ready") Services.scriptloader.loadSubScriptWithOptions(
            "chrome://sine/content/auto-glance/auto-glance.uc.js",{target:window,ignoreCache:true});
        """)
        wait("window.AutoGlance?.status==='ready'")
        m.command("WebDriver:SetWindowRect", {"width": 1400, "height": 1100})
        m.async_js("""
          for(const t of [...gZenWorkspaces.allStoredTabs])
            if(!t.hasAttribute("zen-empty-tab")) gBrowser.removeTab(t,{animate:false,skipPermitUnload:true});
          for(const folder of [...document.querySelectorAll("zen-folder")].reverse())
            if(folder.isConnected) await folder.delete();
          return true;
        """)
        m.js("""
          const names=["outside","root","child","grandchild","sibling","other","last","a","b","c"];
          const tabs=names.map(name=>gBrowser.addTrustedTab(arguments[0]+"/"+name,{inBackground:true}));
          gBrowser.moveTabsAfter(tabs.slice(1),tabs[0]);
          window.ft={tabs,...Object.fromEntries(names.map((name,i)=>[name,tabs[i]]))};
          ft.source=gZenWorkspaces.activeWorkspace;
          gBrowser.selectedTab=ft.outside;
        """, [base])
        wait("ft.tabs.every(t=>!t.hasAttribute('busy') && "
             "t.linkedBrowser.browsingContext.currentWindowGlobal?.documentURI.spec.startsWith(" +
             json.dumps(base) + "))")
        settle()
        m.js("""
          TreeTabs.nest(ft.child,ft.root);TreeTabs.nest(ft.grandchild,ft.child);
          TreeTabs.nest(ft.sibling,ft.root);TreeTabs.toggleCollapse(ft.child);
          TreeTabs.toggleCollapse(ft.root);
        """)
        original = m.js(STATE)
        report["versions"] = m.js("return {tree:TreeTabs.version,multi:MultiTabMove.version,zen:Services.appinfo.version};")
        m.js("""
          MultiTabMove.toggle(ft.root);TreeTabs.supportsSplitTrees=false;
          ft.oldTreeRejected=false;
          try {MultiTabMove.move({workspace:ft.source,anchor:ft.outside,before:true});}
          catch(error){ft.oldTreeRejected=error.message.includes("0.3.0");}
          finally{TreeTabs.supportsSplitTrees=true;MultiTabMove.clear();}
        """)
        check("older_tree_controller_is_rejected_before_move", "ft.oldTreeRejected")
        state = preserved("old_tree_rejection_preserves_documents")
        assert state["order"] == original["order"] and state["parents"] == original["parents"]

        m.js("ft.folder=gZenFolders.createFolder([ft.root],{label:'Project',renameFolder:false});")
        preserved("native_folder_creation_preserves_documents")
        check("creating_folder_with_parent_carries_whole_branch",
              "[ft.root,ft.child,ft.grandchild,ft.sibling].every(t=>t.group===ft.folder && t.pinned)")
        check("folder_creation_preserves_nested_links",
              "TreeTabs.parentOf(ft.child)===ft.root && TreeTabs.parentOf(ft.grandchild)===ft.child && TreeTabs.parentOf(ft.sibling)===ft.root")
        check("folder_creation_preserves_collapse", "ft.child.hasAttribute('uc-tree-hidden') && ft.grandchild.hasAttribute('uc-tree-collapsed')===false && ft.child.hasAttribute('uc-tree-collapsed')")

        m.js("ft.folder.collapsed=true;")
        settle()
        m.js("ft.folder.collapsed=false;")
        settle()
        check("folder_expansion_keeps_branch_collapsed",
              "ft.root.hasAttribute('uc-tree-collapsed') && ft.child.hasAttribute('uc-tree-hidden') && getComputedStyle(ft.child).display==='none'")
        m.js("TreeTabs.toggleCollapse(ft.root);")
        settle()
        check("nested_branch_collapse_stays_independent",
              "!ft.child.hasAttribute('uc-tree-hidden') && ft.grandchild.hasAttribute('uc-tree-hidden')")

        m.js("""
          ft.second=gZenFolders.createFolder([ft.other],{label:'Other folder',renameFolder:false});
          ft.second.addTabs([ft.root]);
        """)
        preserved("native_cross_folder_move_preserves_documents")
        check("native_cross_folder_move_carries_descendants",
              "[ft.root,ft.child,ft.grandchild,ft.sibling].every(t=>t.group===ft.second) && TreeTabs.parentOf(ft.child)===ft.root")
        check("branch_is_contiguous_inside_folder",
              "ft.root.nextElementSibling===ft.child && ft.child.nextElementSibling===ft.grandchild && ft.grandchild.nextElementSibling===ft.sibling")
        m.js("ft.folder.addTabs([ft.last]);")
        settle()
        check("cross_folder_nesting_rejected", "!TreeTabs.nest(ft.last,ft.root)")
        m.js("gBrowser.selectedTab=ft.last;")
        shortcut("right")
        check("keyboard_does_not_cross_folder_boundary", "TreeTabs.parentOf(ft.last)===null && ft.last.group===ft.folder")
        m.js("ft.second.addTabs([ft.last]);gBrowser.selectedTab=ft.last;")
        settle()
        shortcut("right")
        check("keyboard_nests_within_folder", "TreeTabs.parentOf(ft.last)===ft.sibling && ft.last.group===ft.second")
        shortcut("left")
        check("keyboard_outdents_one_level", "TreeTabs.parentOf(ft.last)===ft.root && ft.last.group===ft.second")
        shortcut("left")
        shortcut("left")
        check("root_outdent_stays_in_folder", "TreeTabs.parentOf(ft.last)===null && ft.last.group===ft.second")
        m.js("gBrowser.selectedTab=ft.outside;gBrowser.moveTabsBefore([ft.root],ft.other);")
        preserved("native_reorder_inside_folder")
        check("native_reorder_keeps_branch_contiguous",
              "ft.root.nextElementSibling===ft.child && ft.child.nextElementSibling===ft.grandchild && ft.grandchild.nextElementSibling===ft.sibling")

        m.js("gBrowser.ungroupTab(ft.root);")
        preserved("native_move_out_of_folder")
        check("leaving_folder_preserves_pinned_tree",
              "[ft.root,ft.child,ft.grandchild,ft.sibling].every(t=>!t.group && t.pinned) && TreeTabs.parentOf(ft.grandchild)===ft.child")
        m.js("gBrowser.unpinTab(ft.root);")
        preserved("native_unpin_branch")
        check("unpinning_branch_carries_children",
              "[ft.root,ft.child,ft.grandchild,ft.sibling].every(t=>!t.pinned && !t.group) && TreeTabs.parentOf(ft.child)===ft.root")

        # Trust actual Shift-click and pointer movement, including empty folders.
        pointer("ft.root.querySelector('.tab-label')", ("\ue008",))
        check("folder_move_selection_includes_hidden_descendants",
              "[ft.root,ft.child,ft.grandchild,ft.sibling].every(t=>MultiTabMove.snapshot().tabs.includes(t.id))")
        drag("ft.root.querySelector('.tab-label')", "ft.folder.labelContainerElement")
        preserved("pointer_drop_into_empty_folder")
        check("pointer_folder_drop_moves_and_pins_branch",
              "[ft.root,ft.child,ft.grandchild,ft.sibling].every(t=>t.group===ft.folder && t.pinned)")
        m.js("MultiTabMove.clear();ft.second.collapsed=true;")
        pointer("ft.root.querySelector('.tab-label')", ("\ue008",))
        drag("ft.root.querySelector('.tab-label')", "ft.second.labelContainerElement")
        preserved("pointer_drop_into_collapsed_folder")
        check("collapsed_folder_accepts_branch",
              "ft.root.group===ft.second && ft.child.group===ft.second && ft.grandchild.hasAttribute('uc-tree-hidden')")
        m.js("MultiTabMove.clear();ft.second.collapsed=false;")
        settle()
        m.js("MultiTabMove.toggle(ft.root);")
        drag("ft.root.querySelector('.tab-label')", "ft.last.querySelector('.tab-label')", y=8)
        preserved("pointer_reorder_within_folder")
        check("row_drop_keeps_folder_and_branch_boundary",
              "ft.root.group===ft.second && ft.last.nextElementSibling===ft.root && TreeTabs.parentOf(ft.child)===ft.root")
        m.js("MultiTabMove.clear();MultiTabMove.toggle(ft.last);")
        drag("ft.last.querySelector('.tab-label')", "ft.child.querySelector('.tab-label')", y=8)
        preserved("drop_beside_child_respects_whole_tree")
        check("unrelated_tab_does_not_enter_tree",
              "ft.sibling.nextElementSibling===ft.last && TreeTabs.parentOf(ft.last)===null && ft.last.group===ft.second")
        m.js("MultiTabMove.clear();MultiTabMove.toggle(ft.root);")
        offset = m.js("return Math.floor(ft.folder.labelContainerElement.getBoundingClientRect().height*.4);")
        drag("ft.root.querySelector('.tab-label')", "ft.folder.labelContainerElement", y=-offset)
        preserved("drop_before_empty_folder")
        check("empty_folder_top_edge_is_before_destination",
              "!ft.root.group && ft.sibling.nextElementSibling===ft.folder")
        drag("ft.root.querySelector('.tab-label')", "ft.folder.labelContainerElement", y=offset)
        preserved("drop_after_empty_folder")
        check("empty_folder_bottom_edge_is_after_destination",
              "!ft.root.group && ft.folder.nextElementSibling===ft.root")
        m.js("MultiTabMove.move({workspace:ft.source,folder:ft.second});")

        m.js("""
          MultiTabMove.clear();
          ft.nested=gZenFolders.createFolder([],{label:'Nested folder',renameFolder:false});
          gBrowser.zenHandleTabMove(ft.nested,()=>ft.second.groupContainer.appendChild(ft.nested));
          MultiTabMove.toggle(ft.root);
          MultiTabMove.move({workspace:ft.source,folder:ft.nested});
        """)
        preserved("nested_folder_destination")
        check("nested_folder_contains_independent_tree",
              "ft.nested.group===ft.second && ft.root.group===ft.nested && ft.grandchild.group===ft.nested && !TreeTabs.nest(ft.root,ft.other)")
        check("folder_cannot_be_dropped_into_itself",
              "(MultiTabMove.clear(),MultiTabMove.toggle(ft.second),!MultiTabMove.move({workspace:ft.source,folder:ft.nested}))")
        m.js("MultiTabMove.clear();")
        m.js("""
          ft.depthRoot=gZenFolders.createFolder([],{label:'Depth test',renameFolder:false});
          ft.depthTarget=ft.depthRoot;
          for(let i=0;i<12 && gZenFolders.canDropElement(ft.second,ft.depthTarget.tabs[0]);i++){
            const child=gZenFolders.createFolder([],{label:'Depth '+i,renameFolder:false});
            const parent=ft.depthTarget;
            gBrowser.zenHandleTabMove(child,()=>parent.groupContainer.appendChild(child));
            ft.depthTarget=child;
          }
          MultiTabMove.toggle(ft.second);
        """)
        check("native_folder_depth_limit_is_respected",
              "!gZenFolders.canDropElement(ft.second,ft.depthTarget.tabs[0]) && !MultiTabMove.move({workspace:ft.source,folder:ft.depthTarget}) && !ft.second.group")
        m.async_js("MultiTabMove.clear();await ft.depthRoot.delete();")

        target = m.async_js("""
          ft.destination=(await gZenWorkspaces.createAndSaveWorkspace('Folder tree destination',null,false)).uuid;
          return ft.destination;
        """)
        m.js("MultiTabMove.toggle(ft.second);")
        m.async_js("await MultiTabMove.moveToSpace(arguments[0]);", [target])
        preserved("folder_wrapper_space_move")
        check("moving_folder_keeps_nested_folder_and_internal_trees",
              "ft.nested.group===ft.second && ft.root.group===ft.nested && TreeTabs.parentOf(ft.grandchild)===ft.child && ft.root.getAttribute('zen-workspace-id')===ft.destination")
        m.async_js("await MultiTabMove.moveToSpace(ft.source);")
        preserved("folder_wrapper_space_round_trip")
        m.js("MultiTabMove.clear();gBrowser.selectedTab=ft.outside;")

        # A whole split enters/leaves a folder using its original native group.
        m.js("""
          gZenViewSplitter.splitTabs([ft.a,ft.b,ft.c],'vsep',0,{activate:false});
          ft.split=ft.a.group;
          ft.nativeLayout=()=>{
            const {ucTreeContainer,...native}=gZenViewSplitter.storeDataForSessionStore()
              .find(s=>s.groupId===ft.split.id);
            return JSON.stringify(native);
          };
          ft.layout=ft.nativeLayout();
          MultiTabMove.toggle(ft.b);MultiTabMove.toggle(ft.root);
          MultiTabMove.move({workspace:ft.source,folder:ft.folder});
        """)
        preserved("mixed_split_and_branch_folder_move")
        check("split_wrapper_is_preserved_inside_folder",
              "ft.a.group===ft.split && ft.b.group===ft.split && ft.c.group===ft.split && ft.split.group===ft.folder && ft.nativeLayout()===ft.layout")
        check("split_panes_have_no_individual_tree_ui",
              "[ft.a,ft.b,ft.c].every(t=>!t.hasAttribute('uc-tree-node') && !TreeTabs.parentOf(t))")
        m.js("MultiTabMove.move({workspace:ft.source,anchor:ft.outside,before:false});")
        preserved("mixed_split_and_branch_move_out_to_normal_tabs")
        check("explicit_section_drop_unpins_intact_split_and_tree",
              "[ft.a,ft.b,ft.c,ft.root,ft.child,ft.grandchild,ft.sibling].every(t=>!t.pinned) && ft.a.group===ft.split && !ft.split.group && TreeTabs.parentOf(ft.child)===ft.root")
        m.js("gBrowser.selectedTab=ft.b;")
        settle()
        check("all_three_split_panes_remain_visible",
              "[ft.a,ft.b,ft.c].every(t=>{const r=t.linkedBrowser.getBoundingClientRect();return r.width>100&&r.height>100})")

        m.js("""
          gBrowser.selectedTab=ft.outside;
          ft.savedMove=gBrowser.zenHandleTabMove;
          let count=0;
          gBrowser.zenHandleTabMove=function(...args){
            if(++count===2) throw new Error('Folder move test failure');
            return ft.savedMove.apply(this,args);
          };
          ft.failed=false;
          try {MultiTabMove.move({workspace:ft.source,folder:ft.folder});}
          catch(e){ft.failed=e.message==='Folder move test failure';}
          finally{gBrowser.zenHandleTabMove=ft.savedMove;}
        """)
        preserved("failed_folder_move_rolls_back_documents")
        check("failed_folder_move_restores_pin_state_and_links",
              "ft.failed && !ft.root.pinned && !ft.child.pinned && !ft.root.group && TreeTabs.parentOf(ft.child)===ft.root && ft.a.group===ft.split && !ft.split.group")
        m.js("MultiTabMove.clear();ft.folder.addTabs([ft.root]);")
        settle()

        m.js("gBrowser.selectedTab=ft.root;")
        content()
        pointer("document.getElementById('next')", ("\ue03d",) if m.js("return navigator.platform.includes('Mac');") else ("\ue009",))
        chrome()
        wait("[...gZenWorkspaces.allStoredTabs].some(t=>t.linkedBrowser.currentURI.spec.endsWith('/opened'))")
        m.js("ft.opened=[...gZenWorkspaces.allStoredTabs].find(t=>t.linkedBrowser.currentURI.spec.endsWith('/opened'));")
        settle()
        check("cmd_click_child_joins_parent_folder_in_background",
              "gBrowser.selectedTab===ft.root && ft.opened.group===ft.folder && TreeTabs.parentOf(ft.opened)===ft.root && !ft.opened.hasAttribute('zen-glance-tab')")
        content()
        pointer("document.getElementById('preview')")
        chrome()
        wait("gBrowser.selectedTab.hasAttribute('zen-glance-tab') && !gZenGlanceManager._animating && !gZenGlanceManager.animatingOpen")
        m.js("ft.preview=gBrowser.selectedTab;ft.previewContext=ft.preview.linkedBrowser.browsingContext.id;")
        m.js('document.querySelector("toolbarbutton[command=cmd_zenGlanceExpand]").doCommand();')
        wait("!ft.preview.hasAttribute('zen-glance-tab') && !gZenGlanceManager._animating && !gZenGlanceManager.animatingFullOpen")
        settle()
        check("expanded_glance_joins_tree_inside_folder",
              "ft.preview.group===ft.folder && TreeTabs.parentOf(ft.preview)===ft.root && ft.preview.linkedBrowser.browsingContext.id===ft.previewContext")
        preserved("opener_and_glance_keep_existing_documents")

        m.js("""
          gBrowser.selectedTab=ft.outside;MultiTabMove.clear();
          TreeTabs.toggleCollapse(ft.root);
          ft.saved=TreeTabs.snapshot().filter(n=>[ft.root.id,ft.child.id,ft.grandchild.id].includes(n.tab));
          TreeTabs.destroy();
        """)
        check("unload_keeps_native_folder_and_split",
              "ft.root.group===ft.folder && ft.a.group===ft.split && !document.querySelector('[uc-tree-hidden],.uc-tree-twisty')")
        m.js("""Services.scriptloader.loadSubScriptWithOptions(
          'chrome://sine/content/tree-tabs-prototype/tree-tabs.uc.js',{target:window,ignoreCache:true});""")
        wait("window.TreeTabs?.status==='ready'")
        settle()
        check("reload_restores_folder_relationships_and_collapse",
              "TreeTabs.parentOf(ft.child)===ft.root && TreeTabs.parentOf(ft.grandchild)===ft.child && ft.child.hasAttribute('uc-tree-hidden') && ft.root.group===ft.folder")
        preserved("reload_preserves_all_original_documents")
        check("fixture_pages_loaded_once", "arguments[0]", [
            all(REQUESTS["/" + name] == 1 for name in [
                "outside", "root", "child", "grandchild", "sibling", "other", "last", "a", "b", "c"])])

        m.js("""
          MultiTabMove.clear();MultiTabMove.toggle(ft.folder);MultiTabMove.toggle(ft.b);
          ft.spaceAction=null;
          MultiTabMove.createSpaceFromSelection().then(result=>ft.spaceAction=result);
        """)
        deadline = time.monotonic() + 8
        while True:
            try:
                assert m.command("WebDriver:GetAlertText")
                break
            except RuntimeError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(.05)
        m.command("WebDriver:SendAlertText", {"text": "Folder selection Space"})
        m.command("WebDriver:AcceptAlert")
        wait("ft.spaceAction!==null")
        preserved("new_space_action_keeps_folder_trees_and_split_documents")
        check("new_space_action_preserves_folder_and_split",
              "ft.spaceAction && ft.root.group===ft.folder && TreeTabs.parentOf(ft.child)===ft.root && ft.a.group===ft.split && ft.folder.getAttribute('zen-workspace-id')===gZenWorkspaces.activeWorkspace && ft.a.getAttribute('zen-workspace-id')===gZenWorkspaces.activeWorkspace")
        m.async_js("await MultiTabMove.moveToSpace(ft.source);")
        m.js("""
          MultiTabMove.clear();MultiTabMove.toggle(ft.child);
          gBrowser.selectedTab=ft.outside;
          ft.survivors=[ft.root,ft.sibling,ft.a,ft.b,ft.c,ft.outside].map(t=>({
            tab:t,context:t.linkedBrowser.browsingContext.id,
            document:t.linkedBrowser.browsingContext.currentWindowGlobal.innerWindowId}));
        """)
        m.async_js("return await MultiTabMove.closeSelection();")
        settle()
        check("closing_selected_child_branch_in_folder_keeps_other_tabs",
              "!ft.child.isConnected && !ft.grandchild.isConnected && ft.root.group===ft.folder && ft.a.group===ft.split && ft.survivors.every(s=>s.tab.isConnected && s.tab.linkedBrowser.browsingContext.id===s.context && s.tab.linkedBrowser.browsingContext.currentWindowGlobal.innerWindowId===s.document)")
        check("closing_folder_child_keeps_focus", "gBrowser.selectedTab===ft.outside")
        report["passed"] = True
    except Exception as error:
        report["passed"] = False
        report["error"] = str(error)
        try:
            chrome()
            report["diagnostics"] = m.js(STATE)
        except Exception:
            pass
        raise
    finally:
        report["requests"] = dict(REQUESTS)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        m.close()
        server.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--port", type=int, default=2832)
    parser.add_argument("--report", type=Path, required=True)
    run(parser.parse_args())
