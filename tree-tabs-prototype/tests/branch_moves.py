"""Exercise whole-branch moves in a disposable, running Zen test profile."""

import argparse
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time

from integration import Handler
from runtime import Marionette


STATE = """
const tabs = bmTabs;
const tree = TreeTabs.snapshot();
return {
  order: [...gZenWorkspaces.allStoredTabs].filter(t => tabs.includes(t)).map(t => tabs.indexOf(t)),
  parents: tabs.map(t => tabs.indexOf(TreeTabs.parentOf(t))),
  depths: tabs.map(t => TreeTabs.depthOf(t)),
  collapsed: tabs.map(t => tree.find(n => n.tab === t.id)?.collapsed),
  hidden: tabs.map(t => t.hasAttribute("uc-tree-hidden")),
  spaces: tabs.map(t => t.getAttribute("zen-workspace-id")),
  containers: tabs.map(t => t.closest("zen-workspace")?.id),
  browsers: tabs.map(t => [t.linkedBrowser.browsingContext.id,
    t.linkedBrowser.browsingContext.currentWindowGlobal?.innerWindowId]),
  selected: tabs.indexOf(gBrowser.selectedTab),
  activeSpace: gZenWorkspaces.activeWorkspace,
  dragStylesClear: tabs.every(t => !t.style.transform && !t.style.visibility),
  error: TreeTabs.lastError || null,
};
"""


def run(args):
    result = {"checks": {}}
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    m = Marionette(args.port)
    authorized = False
    fixture_number = 0
    before = None

    def wait(script, seconds=10):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            value = m.js("return (" + script + ");")
            if value:
                return value
            time.sleep(.05)
        raise AssertionError("Timed out: " + script)

    def settle():
        time.sleep(.25)
        error = m.js("return TreeTabs.lastError || null;")
        assert not error, error

    def check(name, condition):
        state = m.js(STATE)
        result["checks"][name] = state
        assert condition(state), f"{name}: {state}"
        assert state["browsers"] == before["browsers"], f"{name}: a page was recreated or reloaded"
        assert not state["error"], state["error"]
        print("PASS", name, flush=True)

    def fixture():
        nonlocal fixture_number, before
        fixture_number += 1
        m.async_js("await gZenWorkspaces.changeWorkspaceWithID(arguments[0]);", [source_space])
        m.js("""
          for (const tab of window.bmTabs || []) {
            if (tab.isConnected && !tab.closing)
              gBrowser.removeTab(tab, {animate:false, skipPermitUnload:true});
          }
          window.bmTabs = ["before", "root", "child", "grandchild", "sibling", "after"].map(
            name => gBrowser.addTrustedTab(arguments[0] + "/" + name, {inBackground:true}));
          window.bm = Object.fromEntries(
            ["before", "root", "child", "grandchild", "sibling", "after"].map((name, i) => [name, bmTabs[i]]));
          gBrowser.moveTabsAfter(bmTabs.slice(1),bmTabs[0]);
          gBrowser.selectedTab = bm.before;
        """, [base + f"/{fixture_number}"])
        wait("""bmTabs.every(t => !t.hasAttribute("busy") &&
          t.linkedBrowser.browsingContext.currentWindowGlobal?.documentURI.spec.startsWith(""" +
             json.dumps(base) + "))")
        settle()
        m.js("""
          TreeTabs.nest(bm.child, bm.root);
          TreeTabs.nest(bm.grandchild, bm.child);
          TreeTabs.nest(bm.sibling, bm.root);
        """)
        settle()
        before = m.js(STATE)
        assert before["order"] == [0, 1, 2, 3, 4, 5], before
        assert before["parents"] == [-1, -1, 1, 2, 1, -1], before

    def same_tree(state):
        return state["parents"] == [-1, -1, 1, 2, 1, -1]

    def in_other_space(state):
        return (same_tree(state) and
                all(state["spaces"][i] == other_space and state["containers"][i] == other_space
                    for i in [1, 2, 3, 4]) and
                all(state["spaces"][i] == source_space for i in [0, 5]) and
                [i for i in state["order"] if i in [1, 2, 3, 4]] == [1, 2, 3, 4])

    try:
        profile = m.js('return Services.dirsvc.get("ProfD", Ci.nsIFile).path;')
        assert Path(profile).resolve() == args.profile.resolve() and "test-profile" in profile
        authorized = True
        wait("window.TreeTabs?.status === 'ready'")
        result["version"] = m.js("return TreeTabs.version;")
        source_space = m.js("return gZenWorkspaces.activeWorkspace;")
        other_space = m.async_js("""
          const space = await gZenWorkspaces.createAndSaveWorkspace("Branch move test");
          return space.uuid;
        """)

        fixture()
        m.js("gBrowser.moveTabAfter(bm.root, bm.after);")
        settle()
        check("parent_moves_down_with_descendants", lambda s:
              s["order"] == [0, 5, 1, 2, 3, 4] and same_tree(s) and s["selected"] == 0)

        m.js("gBrowser.moveTabBefore(bm.root, bm.before);")
        settle()
        check("parent_moves_up_with_descendants", lambda s:
              s["order"] == [1, 2, 3, 4, 0, 5] and same_tree(s) and s["selected"] == 0)

        m.js("TreeTabs.toggleCollapse(bm.root);gBrowser.moveTabAfter(bm.root, bm.after);")
        settle()
        check("collapsed_branch_moves_intact", lambda s:
              s["order"] == [0, 5, 1, 2, 3, 4] and same_tree(s) and
              s["collapsed"][1] and all(s["hidden"][i] for i in [2, 3, 4]))

        fixture()
        m.js("gBrowser.moveTabAfter(bm.child, bm.after);")
        settle()
        check("nested_branch_detaches_only_its_root", lambda s:
              s["order"] == [0, 1, 4, 5, 2, 3] and
              s["parents"] == [-1, -1, -1, 2, 1, -1])

        fixture()
        m.js("gBrowser.moveTabsAfter([bm.root, bm.child], bm.after);")
        settle()
        check("multi_tab_move_keeps_selected_child_attached", lambda s:
              s["order"] == [0, 5, 1, 2, 3, 4] and same_tree(s))

        fixture()
        m.js("gBrowser.moveTabsAfter([bm.before, bm.root], bm.after);")
        settle()
        check("multi_root_move_preserves_branch_order", lambda s:
              s["order"] == [5, 0, 1, 2, 3, 4] and same_tree(s))

        fixture()
        m.js("""
          gBrowser.moveTabAfter(bm.child, bm.after);
          TreeTabs.nest(bm.child, bm.root);
        """)
        settle()
        check("explicit_nesting_wins_over_pending_move", lambda s:
              s["order"] == [0, 1, 4, 2, 3, 5] and same_tree(s))

        fixture()
        m.js("gBrowser.selectedTab=bm.grandchild;gBrowser.moveTabAfter(bm.root,bm.after);")
        settle()
        check("moving_parent_preserves_selected_descendant", lambda s:
              s["order"] == [0, 5, 1, 2, 3, 4] and same_tree(s) and s["selected"] == 3)

        fixture()
        m.js("gZenWorkspaces.moveTabToWorkspace(bm.root, arguments[0]);", [other_space])
        settle()
        check("native_space_move_carries_branch", lambda s: in_other_space(s) and s["selected"] == 0)

        fixture()
        m.js("TreeTabs.toggleCollapse(bm.root);TabContextMenu.contextTab=bm.root;")
        m.async_js("await gZenWorkspaces.changeTabWorkspace(arguments[0]);", [other_space])
        settle()
        check("space_menu_moves_collapsed_branch", lambda s:
              in_other_space(s) and s["activeSpace"] == other_space and s["collapsed"][1] and
              all(s["hidden"][i] for i in [2, 3, 4]))

        fixture()
        m.js("gZenWorkspaces.moveTabsToWorkspace([bm.root,bm.child],arguments[0]);", [other_space])
        settle()
        check("multi_tab_space_move_keeps_child_attached", in_other_space)

        fixture()
        m.js("""
          const container=gZenWorkspaces.workspaceElement(arguments[0]).tabsContainer;
          gBrowser.zenHandleTabMove(bm.root, () => container.insertBefore(bm.root,container.lastChild));
          bm.root.setAttribute("zen-workspace-id",arguments[0]);
          gZenWorkspaces.updateTabsContainers();
        """, [other_space])
        settle()
        check("late_drag_workspace_attribute_carries_branch", in_other_space)

        fixture()
        m.js("bm.root.setAttribute('zen-workspace-id',arguments[0]);", [other_space])
        settle()
        check("attribute_only_space_move_carries_branch", in_other_space)

        fixture()
        m.js("gZenWorkspaces.moveTabToWorkspace(bm.child,arguments[0]);", [other_space])
        settle()
        check("nested_branch_moves_to_space_independently", lambda s:
              s["parents"] == [-1, -1, -1, 2, 1, -1] and
              all(s["spaces"][i] == other_space for i in [2, 3]) and
              all(s["spaces"][i] == source_space for i in [0, 1, 4, 5]))

        fixture()
        m.js("""
          Services.prefs.setBoolPref("uc.tree-tabs.enabled",false);
          gBrowser.moveTabAfter(bm.root,bm.after);
        """)
        settle()
        check("disabled_mod_does_not_move_descendants", lambda s:
              s["order"] == [0, 2, 3, 4, 5, 1])
        m.js("Services.prefs.setBoolPref('uc.tree-tabs.enabled',true);")
        settle()

        fixture()
        m.js("gBrowser.moveTabAfter(bm.root,bm.after);")
        settle()
        saved = m.js(STATE)
        m.js("""
          Services.scriptloader.loadSubScriptWithOptions(
            "chrome://sine/content/tree-tabs-prototype/tree-tabs.uc.js",{target:window,ignoreCache:true});
        """)
        wait("window.TreeTabs?.status === 'ready'")
        check("branch_move_survives_mod_reload", lambda s:
              same_tree(s) and s["order"] == saved["order"])

        fixture()
        m.js("""
          const r=bm.root.getBoundingClientRect(), target=bm.after.getBoundingClientRect();
          const transfer=new DataTransfer();
          transfer.mozSetDataAt("application/x-moz-tabbrowser-tab",bm.root,0);
          transfer.effectAllowed="move";
          transfer.dropEffect="move";
          bm.root._dragData={
            movingTabs:[bm.root],movingTabsSet:new Set([bm.root]),
            dropElement:bm.after,dropBefore:false,fromTabList:false,
            translateX:0,translateY:target.bottom-r.bottom,
            tabWidth:r.width,tabHeight:r.height,screenX:bm.root.screenX,screenY:bm.root.screenY,
          };
          bm.after.dispatchEvent(new DragEvent("drop",{
            bubbles:true,cancelable:true,dataTransfer:transfer,
            clientX:target.x+target.width/2,clientY:target.bottom-3,
            screenX:window.mozInnerScreenX+target.x+target.width/2,
            screenY:window.mozInnerScreenY+target.bottom-3,
          }));
        """)
        time.sleep(1.2)
        check("native_drop_handler_moves_whole_branch", lambda s:
              s["order"] == [0, 5, 1, 2, 3, 4] and same_tree(s) and s["dragStylesClear"])

        result["passed"] = True
    except Exception as error:
        result.update(passed=False, error=str(error))
        if authorized:
            result["diagnostics"] = m.js(STATE)
        raise
    finally:
        if authorized:
            m.js("""
              Services.prefs.setBoolPref("uc.tree-tabs.enabled",true);
              for(const tab of window.bmTabs || []) {
                if(tab.isConnected && !tab.closing)
                  gBrowser.removeTab(tab,{animate:false,skipPermitUnload:true});
              }
            """)
            settle()
            result["cleanup"] = m.js("return bmTabs.every(t=>!t.isConnected || t.closing);")
        args.report.write_text(json.dumps(result, indent=2) + "\n")
        m.close()
        server.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--port", type=int, default=2832)
    run(parser.parse_args())
