"""Native split sessions as tree nodes, in a guarded disposable Zen profile."""

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

    def content():
        m.command("WebDriver:SwitchToWindow", {"handle": main})
        m.command("Marionette:SetContext", {"value": "content"})

    def chrome():
        m.command("Marionette:SetContext", {"value": "chrome"})

    def key(value, modifiers=()):
        try:
            m.command("WebDriver:PerformActions", {"actions": [{
                "type": "key", "id": "keys", "actions": [
                    *({"type": "keyDown", "value": mod} for mod in modifiers),
                    {"type": "keyDown", "value": value},
                    {"type": "keyUp", "value": value},
                    *({"type": "keyUp", "value": mod} for mod in reversed(modifiers)),
                ],
            }]})
        finally:
            m.command("WebDriver:ReleaseActions")
        settle()

    def pointer(expression, button=0, shift=False):
        element = m.js("return " + expression + ";")
        try:
            if shift:
                m.command("WebDriver:PerformActions", {"actions": [{
                    "type": "key", "id": "keys",
                    "actions": [{"type": "keyDown", "value": "\ue008"}],
                }]})
            m.command("WebDriver:PerformActions", {"actions": [{
                "type": "pointer", "id": "mouse",
                "parameters": {"pointerType": "mouse"}, "actions": [
                    {"type": "pointerMove", "origin": element, "x": 0, "y": 0},
                    {"type": "pointerDown", "button": button},
                    {"type": "pointerUp", "button": button},
                ],
            }]})
        finally:
            m.command("WebDriver:ReleaseActions")
        settle()

    def shortcut(direction):
        content()
        wait("document.getElementById('focus')")
        m.js("document.getElementById('focus').focus();")
        try:
            key("\ue014" if direction == "right" else "\ue012", ("\ue00a", "\ue008"))
        finally:
            chrome()
        settle()

    def setup(name, kind="group"):
        chrome()
        m.async_js("""
          MultiTabMove.clear();
          if(gZenGlanceManager.getFocusedTab())
            await gZenGlanceManager.closeGlance({hasFocused:true,skipPermitUnload:true});
          for(const tab of [...gZenWorkspaces.allStoredTabs]) {
            if(!tab.hasAttribute("zen-empty-tab"))gBrowser.removeTab(tab,
              {animate:false,skipPermitUnload:true,closeWindowWithLastTab:false});
          }
          for(const folder of [...document.querySelectorAll("zen-folder")].reverse())
            if(folder.isConnected)await folder.delete();
          const names=["outside","parent","a","b","child","grandchild","tail","target","c","d"];
          const tabs=names.map(n=>gBrowser.addTrustedTab(arguments[0]+"/"+arguments[1]+"/"+n,
            {inBackground:true}));
          window.st={name:arguments[1],tabs,...Object.fromEntries(names.map((n,i)=>[n,tabs[i]]))};
          st.source=gZenWorkspaces.activeWorkspace;
          const members=[st.parent,st.a,st.b,st.child,st.grandchild,st.tail];
          st.folder=arguments[2]==="folder"
            ? gZenFolders.createFolder(members,{label:"Split tree folder",renameFolder:false})
            : gBrowser.addTabGroup(members,{label:"Split tree group",insertBefore:st.parent});
          st.destination=gBrowser.addTabGroup([st.target],
            {label:"Destination",insertBefore:st.target});
          gBrowser.selectedTab=st.a;
        """, [base, name, kind])
        wait("st.tabs.every(t=>!t.hasAttribute('busy') && "
             "t.linkedBrowser.browsingContext.currentWindowGlobal?.documentURI.spec.startsWith(" +
             json.dumps(base) + "))")
        settle()
        m.js("""
          TreeTabs.nest(st.a,st.parent);
          TreeTabs.nest(st.child,st.a);
          TreeTabs.nest(st.grandchild,st.child);
          st.role=TreeTabs.snapshot().find(n=>n.tab===st.a.id).id;
          st.documents=st.tabs.map(tab=>({tab,context:tab.linkedBrowser.browsingContext.id,
            document:tab.linkedBrowser.browsingContext.currentWindowGlobal.innerWindowId}));
          gZenViewSplitter.splitTabs([st.a,st.b],"vsep");
          st.split=st.a.group;
          st.native=gZenViewSplitter._data.find(group=>group.tabs.includes(st.a));
          st.native.layoutTree.children[0].sizeInParent=35;
          st.native.layoutTree.children[1].sizeInParent=65;
          gZenViewSplitter.applyGridLayout(st.native.layoutTree);
          st.layoutOf=group=>JSON.stringify(gZenViewSplitter.storeDataForSessionStore()
            .find(data=>data.groupId===group.tabs[0].group.id)?.layoutTree);
          st.layout=st.layoutOf(st.native);
        """)
        settle()
        content()
        m.js("document.getElementById('draft').value='Keep split tree draft';")
        chrome()

    def preserved(name):
        settle()
        check(name + "_live_documents", """st.documents.filter(x=>x.tab.isConnected).every(
          ({tab,context,document})=>tab.linkedBrowser.browsingContext.id===context &&
          tab.linkedBrowser.browsingContext.currentWindowGlobal?.innerWindowId===document) &&
          !TreeTabs.lastError && !MultiTabMove.lastError""")
        case = m.js("return st.name;")
        assert all(REQUESTS[f"/{case}/{name}"] == 1 for name in
                   ["outside", "parent", "a", "b", "child", "grandchild", "tail", "target", "c", "d"])
        report["checks"][name + "_no_reload_requests"] = True

    def geometry(name):
        wait("""(() => {
          const group=st.split, row=group.getBoundingClientRect();
          if(row.width<50||row.height<20||getComputedStyle(group).display==="none")return false;
          const rects=[...group.tabs].map(t=>{
            const pane=t.linkedBrowser.closest(".browserSidebarContainer");
            const r=pane.getBoundingClientRect();
            return {x:r.x,y:r.y,w:r.width,h:r.height,visible:getComputedStyle(pane).visibility==="visible"};
          });
          if(rects.some(r=>r.w<20||r.h<20||!r.visible))return false;
          for(let i=0;i<rects.length;i++)for(let j=i+1;j<rects.length;j++){
            const a=rects[i],b=rects[j];
            if(Math.min(a.x+a.w,b.x+b.w)-Math.max(a.x,b.x)>2 &&
               Math.min(a.y+a.h,b.y+b.h)-Math.max(a.y,b.y)>2)return false;
          }
          return true;
        })()""")
        report["checks"][name + "_visible_row_and_panes"] = True
        check(name + "_native_members_only", """st.split.tabs.length===st.native.tabs.length &&
          st.split.tabs.every(t=>!t.hasAttribute("uc-tree-node")&&!t.hasAttribute("uc-tree-hidden")) &&
          [...st.split.groupContainer.children].every(n=>!n.classList.contains("uc-tree-twisty"))""")

    def branch(name):
        check(name, """st.split.group===st.folder &&
          TreeTabs.parentOf(st.a)===st.parent && TreeTabs.parentOf(st.b)===st.parent &&
          TreeTabs.parentOf(st.child)===st.split && TreeTabs.parentOf(st.grandchild)===st.child &&
          TreeTabs.snapshot().find(n=>n.tab===st.split.id)?.id===st.role""")

    try:
        actual = m.js('return Services.dirsvc.get("ProfD",Ci.nsIFile).path;')
        assert Path(actual).resolve() == args.profile.resolve() and "test-profile" in actual
        assert (args.profile / "split-tree-test-profile").is_file()
        main = m.command("WebDriver:GetWindowHandle")
        wait("window.TreeTabs?.status==='ready' && window.MultiTabMove?.status==='ready'")
        m.command("WebDriver:SetWindowRect", {"width": 1400, "height": 1100})
        report["versions"] = m.js("""return {tree:TreeTabs.version,multi:MultiTabMove.version,
          zen:Services.appinfo.version,os:Services.appinfo.OS};""")
        m.js("""
          Services.prefs.setBoolPref("uc.tree-tabs.enabled",true);
          Services.prefs.setBoolPref("uc.tree-tabs.keyboard-shortcuts",true);
          Services.prefs.setBoolPref("uc.alt-click-split-view.enabled",true);
        """)

        for kind in ["group", "folder"]:
            setup("create-" + kind, kind)
            branch(kind + "_new_split_inherits_tree_in_container")
            geometry(kind + "_initial")
            check(kind + "_one_node_for_whole_session", """TreeTabs.snapshot().filter(
              n=>[st.split.id,st.a.id,st.b.id].includes(n.tab)).length===1 &&
              TreeTabs.itemOf(st.a)===st.split && TreeTabs.itemOf(st.b)===st.split""")
            check(kind + "_container_and_child_order", """st.parent.nextElementSibling===st.split &&
              st.split.nextElementSibling===st.child && st.child.nextElementSibling===st.grandchild""")
            check(kind + "_same_session_cannot_nest_into_itself", "!TreeTabs.nest(st.a,st.b)")
            check(kind + "_cannot_nest_across_folder_boundary", "!TreeTabs.nest(st.a,st.target)")
            check(kind + "_shortcut_eligible_on_pane", "TreeTabs.canHandleShortcut(gBrowser.selectedBrowser)")

            shortcut("left")
            check(kind + "_shortcut_outdents_whole_session", """!TreeTabs.parentOf(st.a) &&
              TreeTabs.parentOf(st.child)===st.split && st.split.group===st.folder &&
              gBrowser.selectedTab===st.a""")
            pointer("st.a.querySelector('.tab-content')", button=2)
            check(kind + "_native_context_menu_for_split", """!document.getElementById("uc-tree-tabs-menu").hidden &&
              !document.getElementById("uc-tree-nest").disabled""")
            pointer("document.getElementById('uc-tree-tabs-menu')")
            pointer("document.getElementById('uc-tree-nest')")
            branch(kind + "_context_menu_nests_whole_session")

            m.js("gBrowser.selectedTab=st.outside;TreeTabs.toggleCollapse(st.parent);")
            settle()
            check(kind + "_ancestor_collapse_hides_wrapper_only", """st.split.hasAttribute("uc-tree-hidden") &&
              st.child.hasAttribute("uc-tree-hidden") &&
              [st.a,st.b].every(t=>!t.hasAttribute("uc-tree-hidden"))""")
            m.js("gBrowser.selectedTab=st.b;")
            settle()
            check(kind + "_selecting_pane_reveals_ancestor", """!st.split.hasAttribute("uc-tree-hidden") &&
              !st.parent.hasAttribute("uc-tree-collapsed") && gBrowser.selectedTab===st.b""")
            geometry(kind + "_revealed")
            pointer("st.split.querySelector(':scope > .uc-tree-split-twisty')")
            check(kind + "_split_twisty_collapses_only_children", """st.child.hasAttribute("uc-tree-hidden") &&
              st.grandchild.hasAttribute("uc-tree-hidden") &&
              !st.split.hasAttribute("uc-tree-hidden") && gBrowser.selectedTab===st.b""")
            geometry(kind + "_children_collapsed")
            m.js("st.folder.collapsed=true;")
            settle()
            m.js("st.folder.collapsed=false;")
            settle()
            check(kind + "_folder_collapse_keeps_tree_collapse", """st.split.hasAttribute("uc-tree-collapsed") &&
              st.child.hasAttribute("uc-tree-hidden")""")
            m.js("gBrowser.selectedTab=st.child;TreeTabs.toggleCollapse(st.split);")
            settle()
            check(kind + "_collapse_focuses_last_used_pane", "gBrowser.selectedTab===st.b")
            pointer("st.split.querySelector(':scope > .uc-tree-split-twisty')")
            preserved(kind + "_tree_actions")
            check(kind + "_tree_actions_keep_native_layout", "st.layoutOf(st.native)===st.layout")

        setup("extension")
        for pane, count in [("c", 3), ("d", 4)]:
            m.js("gZenViewSplitter.splitTabs([st.a,st[arguments[0]]]);", [pane])
            settle()
            check(f"extend_to_{count}_same_native_session",
                  f"st.a.group===st.split && st.native.tabs.length==={count} && st.split.tabs.length==={count}")
            branch(f"extend_to_{count}_keeps_tree")
            geometry(f"extend_to_{count}")
        m.js("gZenViewSplitter.removeTabFromGroup(st.c,undefined,{forUnsplit:true});")
        settle()
        branch("removing_third_pane_keeps_session_tree")
        check("detached_pane_is_peer_not_child", """TreeTabs.parentOf(st.c)===st.parent &&
          st.c.group===st.folder && !st.c.splitView &&
          !SessionStore.getCustomTabValue(st.c,"uc-tree-tabs-split-state")""")
        m.js("gBrowser.selectedTab=st.a;gBrowser.removeTab(st.d,{animate:false,skipPermitUnload:true});")
        settle()
        branch("closing_fourth_pane_keeps_session_tree")
        check("closing_other_pane_keeps_focus", "gBrowser.selectedTab===st.a")
        geometry("after_member_removal")
        preserved("extension_and_removal")

        setup("shortcut", "folder")
        modifiers = ("\ue03d", "\ue009", "\ue008") if report["versions"]["os"] == "Darwin" else (
            "\ue009", "\ue00a", "\ue008")
        m.js("""
          const key=document.getElementById("zen-new-empty-split-view");
          key.setAttribute("key","T");
          key.setAttribute("modifiers",arguments[0]);
          // Re-register the keyset after assigning a shortcut in a fresh profile.
          const set=key.parentNode,parent=set.parentNode,next=set.nextSibling;
          set.remove();parent.insertBefore(set,next);
        """, ["accel,control,shift" if report["versions"]["os"] == "Darwin" else "accel,alt,shift"])
        key("t", modifiers)
        wait("gZenViewSplitter.waitingForSplitTab && gURLBar.focused && gURLBar.hasAttribute('zen-newtab')")
        check("unfinished_pane_is_not_a_tree_node", """TreeTabs.itemOf(gZenWorkspaces._emptyTab)!==st.split &&
          TreeTabs.snapshot().find(n=>n.tab===st.split.id)?.members.length===2 &&
          gZenViewSplitter.storeDataForSessionStore().every(group=>
            !group.tabs.includes(gZenWorkspaces._emptyTab.id))""")
        text = base + "/shortcut/added"
        actions = []
        for char in text:
            actions.extend([{"type": "keyDown", "value": char}, {"type": "keyUp", "value": char}])
        m.command("WebDriver:PerformActions", {"actions": [{"type": "key", "id": "typing", "actions": actions}]})
        m.command("WebDriver:ReleaseActions")
        key("\ue007")
        wait("!gZenViewSplitter.waitingForSplitTab && st.native.tabs.length===3 && "
             "gBrowser.selectedBrowser.currentURI.spec===" + json.dumps(text))
        branch("new_split_shortcut_keeps_folder_and_tree")
        geometry("new_split_shortcut")
        key("t", modifiers)
        wait("gZenViewSplitter.waitingForSplitTab && gURLBar.focused")
        key("\ue00c")
        if m.js("return gZenViewSplitter.waitingForSplitTab;"):
            key("\ue00c")
        wait("!gZenViewSplitter.waitingForSplitTab && st.native.tabs.length===3")
        branch("cancel_new_split_keeps_tree")
        preserved("new_split_shortcut")

        for kind in ["group", "folder"]:
            for action in ["close-first", "close-second", "separate", "close-whole"]:
                setup(kind + "-" + action, kind)
                if action == "close-whole":
                    m.js("gBrowser.selectedTab=st.outside;")
                    pointer("st.a.querySelector('.tab-content')", button=1)
                    wait("!st.a.isConnected && !st.b.isConnected")
                    check(kind + "_closing_session_promotes_children", """TreeTabs.parentOf(st.child)===st.parent &&
                      TreeTabs.parentOf(st.grandchild)===st.child && st.child.group===st.folder &&
                      gBrowser.selectedTab===st.outside""")
                else:
                    if action == "separate":
                        m.js("gZenViewSplitter.unsplitCurrentView();")
                        survivor = "a"
                    else:
                        closing, survivor = ("a", "b") if action == "close-first" else ("b", "a")
                        m.js("gBrowser.removeTab(st[arguments[0]],{animate:false,skipPermitUnload:true});", [closing])
                    settle()
                    check(kind + "_" + action + "_survivor_inherits_session",
                          f"""!st.split.isConnected && st.{survivor}.group===st.folder &&
                          TreeTabs.parentOf(st.{survivor})===st.parent &&
                          TreeTabs.parentOf(st.child)===st.{survivor} &&
                          TreeTabs.snapshot().find(n=>n.tab===st.{survivor}.id)?.id===st.role &&
                          !SessionStore.getCustomTabValue(st.{survivor},"uc-tree-tabs-split-state")""")
                    if action == "separate":
                        check(kind + "_separated_peer_keeps_folder",
                              "st.b.group===st.folder && TreeTabs.parentOf(st.b)===st.parent")
                preserved(kind + "_" + action)

        setup("split-under-split")
        m.js("""
          st.folder.addTabs([st.c,st.d]);
          gZenViewSplitter.splitTabs([st.c,st.d],"hsep");
          st.otherSplit=st.c.group;
          TreeTabs.nest(st.c,st.b);
          TreeTabs.nest(st.tail,st.d);
          st.otherNative=gZenViewSplitter._data.find(group=>group.tabs.includes(st.c));
          st.otherLayout=st.layoutOf(st.otherNative);
        """)
        settle()
        check("split_can_parent_another_split", """TreeTabs.parentOf(st.c)===st.split &&
          TreeTabs.parentOf(st.tail)===st.otherSplit && TreeTabs.depthOf(st.d)===2 &&
          !TreeTabs.nest(st.b,st.d)""")
        m.js("st.destination.addTabs([st.split]);")
        settle()
        check("native_folder_move_carries_both_sessions_and_children", """!TreeTabs.parentOf(st.split) &&
          [st.split,st.otherSplit,st.child,st.grandchild,st.tail].every(t=>t.group===st.destination) &&
          TreeTabs.parentOf(st.child)===st.split && TreeTabs.parentOf(st.otherSplit)===st.split &&
          TreeTabs.parentOf(st.tail)===st.otherSplit &&
          st.layoutOf(st.native)===st.layout &&
          st.layoutOf(st.otherNative)===st.otherLayout""")
        preserved("nested_sessions_native_move")

        setup("selected-move")
        m.js("""
          st.sleeping=gBrowser.addTrustedTab(arguments[0]+"/selected-move/sleeping",
            {inBackground:true,createLazyBrowser:true});
          st.sleeping.setAttribute("zen-workspace-id",st.source);
          st.folder.addTabs([st.sleeping]);TreeTabs.nest(st.sleeping,st.b);
          st.destination.collapsed=true;st.a.scrollIntoView({block:"center"});
        """, [base])
        pointer("st.a.querySelector('.tab-content')", shift=True)
        check("shift_click_selects_session_and_whole_branch", """MultiTabMove.snapshot().explicit.includes(st.split.id) &&
          [st.a,st.b,st.child,st.grandchild,st.sleeping].every(t=>MultiTabMove.snapshot().tabs.includes(t.id)) &&
          !MultiTabMove.snapshot().tabs.includes(st.parent.id) &&
          gBrowser.selectedTab===st.a""")
        start = m.js("return st.a.querySelector('.tab-content');")
        end = m.js("return st.destination.labelContainerElement;")
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
        check("pointer_drop_moves_session_branch_into_group", """[st.split,st.child,st.grandchild,st.sleeping]
          .every(t=>t.group===st.destination) && !TreeTabs.parentOf(st.split) &&
          TreeTabs.parentOf(st.child)===st.split && TreeTabs.parentOf(st.sleeping)===st.split &&
          gBrowser.selectedTab===st.a && st.layoutOf(st.native)===st.layout""")
        m.js("MultiTabMove.clear();st.destination.collapsed=false;")
        space = m.async_js("""
          return gZenWorkspaces.getWorkspaces().find(s=>s.name==="Split tree destination")?.uuid ||
            (await gZenWorkspaces.createAndSaveWorkspace("Split tree destination")).uuid;
        """)
        m.js("MultiTabMove.toggle(st.a);st.spaceMove=MultiTabMove.moveToSpace(arguments[0]);", [space])
        settle()
        check("space_move_preserves_split_and_tree", """st.spaceMove &&
          [st.a,st.b,st.child,st.grandchild,st.sleeping].every(t=>
            t.getAttribute("zen-workspace-id")===gZenWorkspaces.activeWorkspace) &&
          TreeTabs.parentOf(st.child)===st.split && TreeTabs.parentOf(st.sleeping)===st.split &&
          st.a.group===st.split && st.b.group===st.split &&
          st.layoutOf(st.native)===st.layout""")
        check("sleeping_child_remains_unloaded", "st.sleeping.hasAttribute('pending')")
        assert REQUESTS["/selected-move/sleeping"] == 0
        report["checks"]["sleeping_child_zero_requests"] = True
        preserved("selected_moves")
        m.js("MultiTabMove.clear();")

        setup("ancestor-merge")
        m.js("""
          gZenViewSplitter.unsplitCurrentView();
          TreeTabs.nest(st.child,st.a);TreeTabs.nest(st.grandchild,st.child);
          gZenViewSplitter.splitTabs([st.grandchild,st.a],"vsep");
          st.merged=st.a.group;
        """)
        settle()
        check("ancestor_descendant_merge_is_acyclic", """TreeTabs.parentOf(st.merged)===st.parent &&
          TreeTabs.parentOf(st.child)===st.merged && TreeTabs.depthOf(st.child)===2 &&
          TreeTabs.snapshot().filter(n=>n.id===st.role).length===1""")
        preserved("ancestor_merge")

        setup("reload")
        m.js("""
          st.treeState=()=>JSON.stringify(TreeTabs.snapshot().filter(n=>n.parent||n.children)
            .sort((a,b)=>a.id.localeCompare(b.id)));
          st.before=st.treeState();
          st.selected=gBrowser.selectedTab;
          st.saved=JSON.stringify(gZenViewSplitter.storeDataForSessionStore());
          st.controller=TreeTabs;
          Services.scriptloader.loadSubScriptWithOptions(
            "chrome://sine/content/tree-tabs-prototype/tree-tabs.uc.js",{target:window,ignoreCache:true});
        """)
        wait("TreeTabs.status==='ready'")
        settle()
        check("reload_restores_one_tree_node", """TreeTabs!==st.controller &&
          st.treeState()===st.before && st.a.group===st.split &&
          JSON.stringify(gZenViewSplitter.storeDataForSessionStore())===st.saved &&
          gBrowser.selectedTab===st.selected &&
          st.split.querySelectorAll(":scope > .uc-tree-split-twisty").length===1""")
        m.js('Services.prefs.setBoolPref("uc.tree-tabs.enabled",false);')
        settle()
        check("disabled_tree_leaves_native_split_in_folder", """st.split.group===st.folder &&
          !st.split.hasAttribute("uc-tree-node") && !st.split.querySelector(".uc-tree-split-twisty") &&
          st.a.group===st.split && st.b.group===st.split &&
          st.layoutOf(st.native)===st.layout""")
        m.js('Services.prefs.setBoolPref("uc.tree-tabs.enabled",true);')
        settle()
        branch("reenabled_tree_restores_session_relationships")
        geometry("reloaded_and_reenabled")
        preserved("reload_and_toggle")
        content()
        check("draft_survives_tree_lifecycle", "document.getElementById('draft').value==='Keep split tree draft'")
        chrome()
        before = m.js("return TreeTabs.reconciliations;")
        time.sleep(1)
        check("no_idle_reconciliation_polling", f"TreeTabs.reconciliations==={before}")
        report["passed"] = True
    except Exception as error:
        report["passed"] = False
        report["error"] = str(error)
        raise
    finally:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        m.close()
        server.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--port", type=int, default=2832)
    parser.add_argument("--report", type=Path, required=True)
    run(parser.parse_args())
