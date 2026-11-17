"""Prepare/verify split-session trees across a real disposable Zen restart."""

import argparse
import json
from pathlib import Path
import time

from runtime import Marionette


SNAPSHOT = """
const ids=new Set(arguments[0]);
const name=tab=>SessionStore.getCustomTabValue(tab,"split-tree-test-name");
const items=TreeTabs.snapshot().filter(n=>ids.has(n.id));
return {
  tree:items.map(({tab,members,...n})=>({...n,
    members:members.map(id=>name(document.getElementById(id)))}))
    .sort((a,b)=>a.id.localeCompare(b.id)),
  containers:arguments[1].map(id=>{
    const group=document.getElementById(id);
    return {id,exists:!!group,parent:group?.group?.id||"",pinned:group?.pinned,
      collapsed:group?.collapsed,tag:group?.localName};
  }),
  order:[...gZenWorkspaces.allStoredTabs].map(name).filter(Boolean),
  splits:gZenViewSplitter.storeDataForSessionStore().filter(s=>arguments[2].includes(s.groupId)),
  selected:name(gBrowser.selectedTab),
};
"""


def run(args):
    report = {"checks": {}}
    m = Marionette(args.port)

    def wait(expression):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if value := m.js("return (" + expression + ");"):
                return value
            time.sleep(.1)
        raise AssertionError("Timed out: " + expression)

    def check(name, value):
        report["checks"][name] = value
        assert value, name
        print("PASS", name, flush=True)

    try:
        actual = m.js('return Services.dirsvc.get("ProfD",Ci.nsIFile).path;')
        assert Path(actual).resolve() == args.profile.resolve() and "test-profile" in actual
        assert (args.profile / "split-tree-test-profile").is_file()
        wait("window.TreeTabs?.status==='ready' && window.MultiTabMove?.status==='ready'")
        if args.advanced_tab_groups:
            wait("window.advancedTabGroups?._dragAndDropSyncAdded")
        if args.prepare:
            m.async_js("""
              MultiTabMove.clear();
              for(const tab of [...gZenWorkspaces.allStoredTabs]) {
                if(!tab.hasAttribute("zen-empty-tab"))gBrowser.removeTab(tab,
                  {animate:false,skipPermitUnload:true,closeWindowWithLastTab:false});
              }
              for(const folder of [...document.querySelectorAll("zen-folder")].reverse())
                if(folder.isConnected)await folder.delete();
              const names=["outside","groupParent","a","b","c","d","groupChild","grandchild",
                "folderParent","e","f","g","folderChild","nestedRoot","h","i","nestedChild"];
              const tabs=names.map(name=>gBrowser.addTrustedTab("data:text/html,"+
                encodeURIComponent("<title>Restore "+name+"</title><input id=draft value='Saved "+
                  name+" draft'><h1>Restore "+name+"</h1>"),{inBackground:true}));
              window.sr={tabs,...Object.fromEntries(names.map((n,i)=>[n,tabs[i]]))};
              tabs.forEach((tab,i)=>SessionStore.setCustomTabValue(tab,"split-tree-test-name",names[i]));
              sr.group=gBrowser.addTabGroup(
                [sr.groupParent,sr.a,sr.b,sr.c,sr.d,sr.groupChild,sr.grandchild],
                {label:"Restore group splits",insertBefore:sr.groupParent});
              sr.folder=gZenFolders.createFolder([sr.folderParent,sr.e,sr.f,sr.g,sr.folderChild],
                {label:"Restore folder splits",renameFolder:false});
              sr.inner=gBrowser.addTabGroup([sr.nestedRoot,sr.h,sr.i,sr.nestedChild],
                {label:"Restore nested group splits",insertBefore:sr.nestedRoot});
              if(arguments[0]) {
                MultiTabMove.toggle(sr.inner);
                MultiTabMove.move({workspace:gZenWorkspaces.activeWorkspace,folder:sr.group});
                MultiTabMove.clear();
              }
              TreeTabs.nest(sr.a,sr.groupParent);TreeTabs.nest(sr.groupChild,sr.a);
              TreeTabs.nest(sr.grandchild,sr.groupChild);
              TreeTabs.nest(sr.e,sr.folderParent);TreeTabs.nest(sr.folderChild,sr.e);
              TreeTabs.nest(sr.h,sr.nestedRoot);TreeTabs.nest(sr.nestedChild,sr.h);
              gZenViewSplitter.splitTabs([sr.a,sr.b,sr.c,sr.d],"grid",0,{activate:false});
              gZenViewSplitter.splitTabs([sr.e,sr.f,sr.g],"vsep",0,{activate:false});
              gZenViewSplitter.splitTabs([sr.h,sr.i],"hsep",0,{activate:false});
              sr.splits=[sr.a.group,sr.e.group,sr.h.group];
              gBrowser.selectedTab=sr.outside;
            """, [args.advanced_tab_groups])
            wait("sr.tabs.every(t=>!t.hasAttribute('busy') && "
                 "t.linkedBrowser.browsingContext.currentWindowGlobal?.documentURI.spec.startsWith('data:'))")
            m.js("""
              TreeTabs.toggleCollapse(sr.a);TreeTabs.toggleCollapse(sr.e);
              TreeTabs.toggleCollapse(sr.nestedRoot);
              sr.folder.collapsed=true;
              if(arguments[0])sr.inner.collapsed=true;
            """, [args.advanced_tab_groups])
            time.sleep(.6)
            ids = m.js("return TreeTabs.snapshot().filter(n=>n.children||n.parent).map(n=>n.id);")
            containers = m.js("return [sr.group.id,sr.folder.id,sr.inner.id];")
            splits = m.js("return sr.splits.map(s=>s.id);")
            check("three_split_nodes_prepared", m.js(
                "return TreeTabs.snapshot().filter(n=>n.kind==='split' && (n.parent||n.children)).length===3;"))
            expected = m.js(SNAPSHOT, [ids, containers, splits])
            check("every_split_has_saved_container",
                  all(item.get("ucTreeContainer", {}).get("id") in containers for item in expected["splits"]))
            m.async_js("await Promise.all(sr.tabs.map(t=>gBrowser.TabStateFlusher.flush(t.linkedBrowser)));")
            args.expected.write_text(json.dumps({
                "ids": ids, "containers": containers, "splits": splits, "state": expected,
                "advancedTabGroups": args.advanced_tab_groups,
            }, indent=2) + "\n")
            with (args.profile / "user.js").open("a") as stream:
                stream.write('\nuser_pref("browser.startup.page", 3);\n'
                             'user_pref("zen.workspaces.continue-where-left-off", true);\n')
            m.js("""
              Services.prefs.setIntPref("browser.startup.page",3);
              Services.prefs.setBoolPref("zen.workspaces.continue-where-left-off",true);
              Services.prefs.savePrefFile(null);
            """)
        else:
            expected = json.loads(args.expected.read_text())
            assert expected["advancedTabGroups"] == args.advanced_tab_groups
            deadline = time.monotonic() + 12
            while True:
                actual = m.js(SNAPSHOT, [expected["ids"], expected["containers"], expected["splits"]])
                if actual == expected["state"] or time.monotonic() >= deadline:
                    break
                time.sleep(.1)
            report["actual"] = actual
            for field in ["tree", "containers", "order", "splits", "selected"]:
                check(field + "_restored", actual[field] == expected["state"][field])
            check("restored_panes_have_no_tree_ui", m.js("""
              return arguments[0].every(id=>document.getElementById(id).tabs.every(tab=>
                !tab.hasAttribute("uc-tree-node")&&!tab.hasAttribute("uc-tree-hidden")));
            """, [expected["splits"]]))

            # Selecting any restored pane must reveal its folder/tree and layout.
            for split_id, count in zip(expected["splits"], [4, 3, 2]):
                m.js("""
                  const group=document.getElementById(arguments[0]);
                  for(let container=group.group;container;container=container.group)container.collapsed=false;
                  gBrowser.selectedTab=group.tabs[1];
                """, [split_id])
                wait("""(() => {
                  const group=document.getElementById(""" + json.dumps(split_id) + """);
                  const row=group.getBoundingClientRect();
                  return group.tabs.length===""" + str(count) + """ && row.width>40 && row.height>20 &&
                    group.tabs.every(tab=>{
                      const pane=tab.linkedBrowser.closest(".browserSidebarContainer"),r=pane.getBoundingClientRect();
                      return r.width>20&&r.height>20&&getComputedStyle(pane).visibility==="visible";
                    });
                })()""")
                report["checks"][f"restored_{count}_pane_layout_visible"] = True
                check(f"restored_{count}_pane_tree_role", m.js("""
                  const group=document.getElementById(arguments[0]);
                  return !!TreeTabs.parentOf(group) &&
                    TreeTabs.snapshot().find(n=>n.tab===group.id)?.children>0;
                """, [split_id]))
            check("no_controller_error", m.js("return !TreeTabs.lastError&&!MultiTabMove.lastError;"))
        report["passed"] = True
    except Exception as error:
        report["passed"] = False
        report["error"] = str(error)
        raise
    finally:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        m.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--port", type=int, default=2832)
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--advanced-tab-groups", action="store_true")
    run(parser.parse_args())
