"""Prepare/verify a real disposable-profile restart with native folder trees."""

import argparse
import json
from pathlib import Path
import time

from runtime import Marionette


SNAPSHOT = """
const expectedIds=new Set(arguments[0]);
const tree=TreeTabs.snapshot().filter(n=>expectedIds.has(n.id)).map(({tab,...n})=>n);
tree.sort((a,b)=>a.id.localeCompare(b.id));
return {tree,folders:arguments[1].map(id=>{
  const f=document.getElementById(id);
  return {id,exists:!!f,parent:f?.group?.id||"",collapsed:f?.collapsed};
}),order:[...gZenWorkspaces.allStoredTabs].map(t=>{
  try{return JSON.parse(SessionStore.getCustomTabValue(t,"uc-tree-tabs-state")).id;}catch{return "";}
}).filter(id=>expectedIds.has(id))};
"""


def run(args):
    m = Marionette(args.port)
    report = {"checks": {}}
    try:
        actual = m.js('return Services.dirsvc.get("ProfD",Ci.nsIFile).path;')
        assert Path(actual).resolve() == args.profile.resolve()
        assert (args.profile / "folder-tree-test-profile").is_file()
        deadline = time.monotonic() + 20
        while not m.js("return window.TreeTabs?.status==='ready' && window.MultiTabMove?.status==='ready';"):
            assert time.monotonic() < deadline
            time.sleep(.1)

        if args.prepare:
            m.js("""
              MultiTabMove.clear();
              const names=["outside","root","child","grandchild","sibling","nestedRoot","nestedChild","a","b"];
              const tabs=names.map(name=>gBrowser.addTrustedTab(
                "data:text/html,<title>Restore "+name+"</title><h1>Restore "+name+"</h1>",
                {inBackground:true}));
              window.fr={tabs,...Object.fromEntries(names.map((name,i)=>[name,tabs[i]]))};
              gBrowser.selectedTab=fr.outside;
              TreeTabs.nest(fr.child,fr.root);TreeTabs.nest(fr.grandchild,fr.child);
              TreeTabs.nest(fr.sibling,fr.root);TreeTabs.nest(fr.nestedChild,fr.nestedRoot);
              fr.folder=gZenFolders.createFolder([fr.root],{label:"Restore tree",renameFolder:false});
              fr.nested=gZenFolders.createFolder([fr.nestedRoot],{label:"Restore nested tree",renameFolder:false});
            """)
            time.sleep(.5)
            m.js("""
              MultiTabMove.toggle(fr.nested);
              MultiTabMove.move({workspace:gZenWorkspaces.activeWorkspace,folder:fr.folder});
              MultiTabMove.clear();
              gZenViewSplitter.splitTabs([fr.a,fr.b],'vsep',0,{activate:false});
              fr.split=fr.a.group;
              MultiTabMove.toggle(fr.a);
              MultiTabMove.move({workspace:gZenWorkspaces.activeWorkspace,folder:fr.folder});
              MultiTabMove.clear();
              TreeTabs.toggleCollapse(fr.root);TreeTabs.toggleCollapse(fr.nestedRoot);
              fr.folder.collapsed=true;fr.nested.collapsed=true;
              gBrowser.selectedTab=fr.outside;
            """)
            time.sleep(.5)
            ids = m.js("return TreeTabs.snapshot().filter(n=>fr.tabs.some(t=>t.id===n.tab) && n.id && (n.children || n.parent)).map(n=>n.id);")
            folders = m.js("return [fr.folder.id,fr.nested.id];")
            expected = m.js(SNAPSHOT, [ids, folders])
            assert len(expected["tree"]) == 6, expected
            m.async_js("await Promise.all(fr.tabs.map(t=>gBrowser.TabStateFlusher.flush(t.linkedBrowser)));")
            args.expected.write_text(json.dumps({
                "ids": ids, "folders": folders, "state": expected,
                "split": m.js("""return {id:fr.split.id,layout:JSON.stringify(
                  gZenViewSplitter.storeDataForSessionStore().find(s=>s.groupId===fr.split.id))};"""),
            }, indent=2) + "\n")
            with (args.profile / "user.js").open("a") as stream:
                stream.write('\nuser_pref("browser.startup.page", 3);\n')
            m.js('Services.prefs.setIntPref("browser.startup.page",3);Services.prefs.savePrefFile(null);')
            report["checks"]["prepared"] = True
        else:
            expected = json.loads(args.expected.read_text())
            actual = m.js(SNAPSHOT, [expected["ids"], expected["folders"]])
            report["actual"] = actual
            report["checks"]["folder_tree_restored"] = actual == expected["state"]
            assert report["checks"]["folder_tree_restored"], (actual, expected["state"])
            split = expected["split"]
            intact = m.js("""
              const split=document.getElementById(arguments[0]);
              return !!split && split.tabs.length===2 &&
                JSON.stringify(gZenViewSplitter.storeDataForSessionStore().find(s=>s.groupId===split.id))===arguments[1] &&
                split.tabs.every(t=>!t.hasAttribute("uc-tree-node") && !t.hasAttribute("uc-tree-hidden"));
            """, [split["id"], split["layout"]])
            report["checks"]["split_restored_intact"] = intact
            assert intact
        report["passed"] = True
        print(json.dumps(report["checks"]))
    except Exception as error:
        report["passed"] = False
        report["error"] = str(error)
        raise
    finally:
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        m.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--port", type=int, default=2832)
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true")
    run(parser.parse_args())
