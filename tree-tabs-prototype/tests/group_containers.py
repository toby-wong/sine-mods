"""Existing ordinary tab groups must support the same tree actions as folders."""

import argparse
import json
from pathlib import Path
import threading
import time

from folders import FixtureServer, Handler, REQUESTS
from runtime import Marionette


def run(args):
    report = {"checks": {}}
    server = FixtureServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    m = Marionette(args.port)

    def wait(expression):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if value := m.js("return (" + expression + ");"):
                return value
            time.sleep(.05)
        raise AssertionError("Timed out: " + expression)

    def settle():
        time.sleep(.3)

    def check(name, expression):
        value = m.js("return (" + expression + ");")
        report["checks"][name] = value
        assert value, name
        print("PASS", name, flush=True)

    def pointer(expression, button=0, shift=False):
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

    def shortcut(direction):
        m.command("WebDriver:SwitchToWindow", {"handle": main})
        m.command("Marionette:SetContext", {"value": "content"})
        wait("document.getElementById('focus')")
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
            m.command("Marionette:SetContext", {"value": "chrome"})
        settle()

    def preserved(name):
        settle()
        check(name, """gt.documents.every(({tab,context,document})=>
          tab.isConnected && tab.linkedBrowser.browsingContext.id===context &&
          tab.linkedBrowser.browsingContext.currentWindowGlobal?.innerWindowId===document) &&
          !TreeTabs.lastError && !MultiTabMove.lastError""")

    try:
        actual = m.js('return Services.dirsvc.get("ProfD",Ci.nsIFile).path;')
        assert Path(actual).resolve() == args.profile.resolve() and "test-profile" in actual
        assert (args.profile / "folder-tree-test-profile").is_file()
        main = m.command("WebDriver:GetWindowHandle")
        wait("window.TreeTabs?.status==='ready' && window.MultiTabMove?.status==='ready'")
        m.command("WebDriver:SetWindowRect", {"width": 1400, "height": 1100})
        m.async_js("""
          for(const tab of [...gZenWorkspaces.allStoredTabs]) {
            if(!tab.hasAttribute("zen-empty-tab"))gBrowser.removeTab(tab,
              {animate:false,skipPermitUnload:true,closeWindowWithLastTab:false});
          }
          for(const folder of [...document.querySelectorAll("zen-folder")].reverse()) {
            if(folder.isConnected)await folder.delete();
          }
        """)
        m.js("""
          MultiTabMove.clear();
          TreeTabs.destroy();
          const names=["outside","root","child","grandchild","spare","target",
            "innerRoot","innerChild","splitA","splitB"];
          const tabs=names.map(name=>gBrowser.addTrustedTab(arguments[0]+"/group-"+name,
            {inBackground:true}));
          window.gt={tabs,...Object.fromEntries(names.map((name,i)=>[name,tabs[i]]))};
          gt.source=gZenWorkspaces.activeWorkspace;
          gt.group=gBrowser.addTabGroup([gt.root,gt.child,gt.grandchild,gt.spare],
            {label:"Existing folder-like group",insertBefore:gt.root});
          gt.destination=gBrowser.addTabGroup([gt.target],
            {label:"Group destination",insertBefore:gt.target});
          gt.inner=gBrowser.addTabGroup([gt.innerRoot,gt.innerChild],
            {label:"Nested group",insertBefore:gt.innerRoot});
          // Advanced Tab Groups adds decorative non-tab children to containers.
          const grain=document.createElement("div");grain.className="grain";
          gt.group.groupContainer.append(grain);
          gBrowser.selectedTab=gt.child;
          gt.child.scrollIntoView({block:"center"});
          Services.scriptloader.loadSubScriptWithOptions(
            "chrome://sine/content/tree-tabs-prototype/tree-tabs.uc.js",
            {target:window,ignoreCache:true});
        """, [base])
        wait("TreeTabs.status==='ready' && gt.tabs.every(t=>t.linkedBrowser.currentURI.spec.startsWith('http:') && t.linkedBrowser.browsingContext.currentWindowGlobal?.documentURI.spec.startsWith('http:'))")
        settle()
        m.js("""gt.documents=gt.tabs.map(tab=>({tab,context:tab.linkedBrowser.browsingContext.id,
          document:tab.linkedBrowser.browsingContext.currentWindowGlobal.innerWindowId}));""")
        check("existing_group_stays_native_and_unpinned",
              "gt.group.localName==='tab-group' && !gt.group.isZenFolder && !gt.child.pinned && gt.child.group===gt.group")
        check("shortcut_available_for_existing_group", "TreeTabs.canHandleShortcut(gBrowser.selectedBrowser)")
        pointer("gt.child.querySelector('.tab-content')", button=2)
        check("tree_menu_visible_for_existing_group",
              "TabContextMenu.contextTab===gt.child && !document.getElementById('uc-tree-tabs-menu').hidden && !document.getElementById('uc-tree-nest').disabled")
        pointer("document.getElementById('uc-tree-tabs-menu')")
        pointer("document.getElementById('uc-tree-nest')")
        check("native_menu_nests_existing_tab", "TreeTabs.parentOf(gt.child)===gt.root && gt.child.group===gt.group")
        shortcut("left")
        check("content_shortcut_outdents_existing_tab", "!TreeTabs.parentOf(gt.child) && gt.child.group===gt.group")
        shortcut("right")
        check("content_shortcut_nests_existing_tab", "TreeTabs.parentOf(gt.child)===gt.root && gBrowser.selectedTab===gt.child")
        m.js("gBrowser.selectedTab=gt.grandchild;")
        shortcut("right")
        check("group_supports_grandchildren", "TreeTabs.parentOf(gt.grandchild)===gt.child")
        preserved("nesting_keeps_live_documents")
        m.js("""
          gBrowser.selectedTab=gt.outside;
          TreeTabs.toggleCollapse(gt.root);
          gt.group.collapsed=true;
        """)
        settle()
        m.js("gt.group.collapsed=false;")
        settle()
        check("group_and_branch_collapse_are_independent",
              "gt.child.hasAttribute('uc-tree-hidden') && gt.grandchild.hasAttribute('uc-tree-hidden') && gt.root.hasAttribute('uc-tree-collapsed')")
        m.js("TreeTabs.toggleCollapse(gt.root);")
        check("root_outdent_keeps_its_group", "!TreeTabs.outdent(gt.root) && gt.root.group===gt.group")
        check("cross_group_parent_rejected", "!TreeTabs.nest(gt.target,gt.root) && gt.target.group===gt.destination")
        m.js("gt.destination.addTabs([gt.root]);")
        settle()
        check("native_group_move_carries_branch",
              "[gt.root,gt.child,gt.grandchild].every(t=>t.group===gt.destination && !t.pinned) && TreeTabs.parentOf(gt.grandchild)===gt.child")
        preserved("native_group_move_keeps_documents")

        # A sleeping child must remain lazy through both group and pin changes.
        m.js("""
          gt.sleeping=gBrowser.addTrustedTab(arguments[0]+"/sleeping-group-child",
            {inBackground:true,createLazyBrowser:true});
          gt.sleeping.setAttribute("zen-workspace-id",gt.source);
          gt.destination.addTabs([gt.sleeping]);
          TreeTabs.nest(gt.sleeping,gt.root);
          gt.folder=gZenFolders.createFolder([gt.root],
            {label:"Native folder destination",renameFolder:false});
        """, [base])
        settle()
        check("native_folder_move_keeps_group_branch",
              "[gt.root,gt.child,gt.grandchild,gt.sleeping].every(t=>t.group===gt.folder && t.pinned) && TreeTabs.parentOf(gt.sleeping)===gt.root")
        check("sleeping_child_stays_unloaded_in_folder", "gt.sleeping.hasAttribute('pending')")
        m.js("gt.group.collapsed=true;gt.root.scrollIntoView({block:'center'});")
        pointer("gt.root.querySelector('.tab-content')", shift=True)
        start = m.js("return gt.root.querySelector('.tab-content');")
        end = m.js("return gt.group.labelContainerElement;")
        try:
            m.command("WebDriver:PerformActions", {"actions": [{
                "type": "pointer", "id": "mouse", "parameters": {"pointerType": "mouse"},
                "actions": [
                    {"type": "pointerMove", "origin": start, "x": 0, "y": 0},
                    {"type": "pointerDown", "button": 0},
                    {"type": "pointerMove", "origin": start, "x": 12, "y": 6, "duration": 150},
                    {"type": "pointerMove", "origin": end, "x": 0, "y": 0, "duration": 300},
                    {"type": "pointerUp", "button": 0},
                ],
            }]})
        finally:
            m.command("WebDriver:ReleaseActions")
        settle()
        check("pointer_drop_into_collapsed_group",
              "[gt.root,gt.child,gt.grandchild,gt.sleeping].every(t=>t.group===gt.group && !t.pinned) && TreeTabs.parentOf(gt.grandchild)===gt.child")
        check("sleeping_child_stays_unloaded_in_group", "gt.sleeping.hasAttribute('pending')")
        m.js("MultiTabMove.clear();gt.group.collapsed=false;")
        preserved("group_folder_roundtrip_keeps_documents")

        m.js("""
          TreeTabs.nest(gt.innerChild,gt.innerRoot);
          MultiTabMove.toggle(gt.inner);
          gt.nestedMove=MultiTabMove.move({workspace:gt.source,folder:gt.group});
          MultiTabMove.clear();
        """)
        settle()
        check("nested_group_keeps_its_own_tree",
              "gt.nestedMove && gt.inner.group===gt.group && TreeTabs.parentOf(gt.innerChild)===gt.innerRoot && !TreeTabs.nest(gt.innerRoot,gt.root)")
        m.js("""
          gZenViewSplitter.splitTabs([gt.splitA,gt.splitB],"vsep",0,{activate:false});
          gt.split=gt.splitA.group;
          gt.nativeLayout=()=>{
            const {ucTreeContainer,...native}=gZenViewSplitter.storeDataForSessionStore()
              .find(s=>s.groupId===gt.split.id);
            return JSON.stringify(native);
          };
          gt.layout=gt.nativeLayout();
          MultiTabMove.toggle(gt.splitA);
          gt.splitMove=MultiTabMove.move({workspace:gt.source,folder:gt.group});
          MultiTabMove.clear();
        """)
        settle()
        check("complete_split_moves_into_group_as_one_tree_node",
              "gt.splitMove && gt.split.group===gt.group && gt.splitA.group===gt.split && gt.splitB.group===gt.split && TreeTabs.nest(gt.splitA,gt.root) && TreeTabs.parentOf(gt.splitB)===gt.root && !TreeTabs.nest(gt.root,gt.splitB)")
        check("split_layout_and_rows_preserved",
              "gt.nativeLayout()===gt.layout && [gt.splitA,gt.splitB].every(t=>!t.hasAttribute('uc-tree-node') && !t.hasAttribute('uc-tree-hidden'))")
        # Inactive/restoring split panes may not have individual split attributes.
        m.js("""
          gt.splitAttributes=[gt.splitA,gt.splitB].map(t=>t.getAttribute("split-view"));
          for(const tab of [gt.splitA,gt.splitB])tab.removeAttribute("split-view");
        """)
        settle()
        check("same_session_panes_cannot_nest_into_each_other",
              "!TreeTabs.nest(gt.splitB,gt.splitA) && [gt.splitA,gt.splitB].every(t=>!t.hasAttribute('uc-tree-node'))")
        m.js("""[gt.splitA,gt.splitB].forEach((t,i)=>{
          if(gt.splitAttributes[i]!==null)t.setAttribute("split-view",gt.splitAttributes[i]);
        });""")
        target = m.async_js("""
          return gZenWorkspaces.getWorkspaces().find(s=>s.name==="Group compatibility destination")?.uuid ||
            (await gZenWorkspaces.createAndSaveWorkspace("Group compatibility destination")).uuid;
        """)
        m.js("""
          MultiTabMove.toggle(gt.group);
          gt.spaceMove=MultiTabMove.moveToSpace(arguments[0]);
          MultiTabMove.clear();
        """, [target])
        settle()
        check("whole_group_space_move_preserves_branches",
              "gt.spaceMove && gt.inner.group===gt.group && TreeTabs.parentOf(gt.child)===gt.root && TreeTabs.parentOf(gt.innerChild)===gt.innerRoot && gt.splitA.group===gt.split && gt.split.group===gt.group && !gt.root.pinned")
        preserved("group_space_move_keeps_documents")
        check("sleeping_child_remains_pending_after_space_move", "gt.sleeping.hasAttribute('pending')")
        report["checks"]["sleeping_child_zero_requests"] = REQUESTS["/sleeping-group-child"] == 0
        assert report["checks"]["sleeping_child_zero_requests"]
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
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--port", type=int, default=2832)
    parser.add_argument("--report", type=Path, required=True)
    run(parser.parse_args())
