"""Browser checks restricted to the disposable Tree Tabs test profile."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time

from runtime import Marionette


PAGE = b"""<!doctype html><meta charset=utf-8><title>Tree Tabs test</title>
<style>body{font:18px system-ui;margin:40px}a,input{display:block;margin:20px}</style>
<h1>Tree Tabs test</h1><input id=draft value="Keep this unfinished draft">
<a id=next href="/child">Open a child tab</a>
<a id=blank href="/preview" target=_blank>Open a preview</a>
<script>window.pageMarker=Math.random();</script>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(PAGE)

    def log_message(self, *_):
        pass


def run(args):
    result = {"checks": {}}
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    m = Marionette(args.port)

    def wait(script, seconds=12):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            value = m.js("return (" + script + ");")
            if value:
                return value
            time.sleep(.05)
        raise AssertionError("Timed out: " + script)

    def check(name, value, passed=None):
        result["checks"][name] = value
        if passed is None:
            passed = value if isinstance(value, bool) else True
        if not passed:
            raise AssertionError(f"{name}: {value}")
        print("PASS", name, flush=True)

    def settle():
        time.sleep(.2)
        error = m.js("return TreeTabs.lastError || null;")
        assert not error, error

    def content():
        m.command("Marionette:SetContext", {"value": "chrome"})
        m.command("WebDriver:SwitchToWindow", {"handle": m.command("WebDriver:GetWindowHandle")})
        m.command("Marionette:SetContext", {"value": "content"})

    def chrome():
        m.command("Marionette:SetContext", {"value": "chrome"})

    def click(identifier, modifier=None):
        content()
        wait("document.readyState === 'complete'")
        point = m.js("""
          const rect=document.getElementById(arguments[0]).getBoundingClientRect();
          return {x:Math.round(rect.x+30),y:Math.round(rect.y+rect.height/2)};
        """, [identifier])
        try:
            if modifier:
                m.command("WebDriver:PerformActions", {"actions": [{
                    "type": "key", "id": "modifier",
                    "actions": [{"type": "keyDown", "value": modifier}],
                }]})
            m.command("WebDriver:PerformActions", {"actions": [{
                "type": "pointer", "id": "mouse", "parameters": {"pointerType": "mouse"},
                "actions": [
                    {"type": "pointerMove", "origin": "viewport", **point},
                    {"type": "pointerDown", "button": 0},
                    {"type": "pointerUp", "button": 0},
                ],
            }]})
        finally:
            m.command("WebDriver:ReleaseActions")
            chrome()

    try:
        profile = m.js('return Services.dirsvc.get("ProfD",Ci.nsIFile).path;')
        assert Path(profile).resolve() == args.profile.resolve() and "test-profile" in profile
        wait("window.TreeTabs?.status === 'ready'")
        check("startup", m.js("return {tree:TreeTabs.status,autoGlance:AutoGlance.status};"))
        m.js("""
          Services.prefs.setBoolPref("uc.tree-tabs.enabled",true);
          Services.prefs.setBoolPref("uc.tree-tabs.auto-nest",true);
          Services.prefs.setBoolPref("uc.auto-glance.enabled",true);
          Services.prefs.setBoolPref("uc.auto-glance.cmd-click-background",true);
          window.ttRoot=gBrowser.addTrustedTab(arguments[0]+"/root",{inBackground:false});
          for(const tab of [...gZenWorkspaces.allStoredTabs]){
            if(tab!==ttRoot&&!tab.hasAttribute("zen-empty-tab"))
              gBrowser.removeTab(tab,{animate:false,skipPermitUnload:true});
          }
          gBrowser.selectedTab=ttRoot;
        """, [base])
        wait("gBrowser.selectedBrowser.currentURI.spec === " + json.dumps(base + "/root"))
        content()
        wait("document.readyState === 'complete'")
        original_marker = m.js("""
          document.getElementById("draft").value="A draft changed after loading";
          return window.wrappedJSObject.pageMarker;
        """)
        assert original_marker is not None
        chrome()
        original_context = m.js("return ttRoot.linkedBrowser.browsingContext.id;")

        click("next", "\ue03d")
        wait("TreeTabs.snapshot().some(n=>n.depth===1)")
        child = m.js("""
          window.ttChild=[...gZenWorkspaces.allStoredTabs].find(t=>TreeTabs.parentOf(t)===ttRoot);
          return {selected:gBrowser.selectedTab===ttRoot,depth:TreeTabs.depthOf(ttChild),
            preview:ttChild.hasAttribute("zen-glance-tab"),split:ttChild.hasAttribute("split-view")};
        """)
        check("command_click_creates_background_child", child,
              child["selected"] and child["depth"] == 1 and not child["preview"] and not child["split"])

        m.js("gBrowser.selectedTab=ttChild;")
        click("next", "\ue03d")
        wait("TreeTabs.snapshot().some(n=>n.depth===2)")
        detail = m.js("""
          window.ttGrandchild=[...gZenWorkspaces.allStoredTabs].find(t=>TreeTabs.parentOf(t)===ttChild);
          return {depth:TreeTabs.depthOf(ttGrandchild),
            margin:getComputedStyle(ttGrandchild.querySelector(".tab-stack")).marginInlineStart,
            parentLabelX:ttChild.querySelector(".tab-label").getBoundingClientRect().x,
            childLabelX:ttGrandchild.querySelector(".tab-label").getBoundingClientRect().x};
        """)
        check("nested_child_and_visible_indentation", detail,
              detail["depth"] == 2 and float(detail["margin"].removesuffix("px")) >= 28 and
              detail["childLabelX"] - detail["parentLabelX"] >= 10)

        m.js("gBrowser.selectedTab=ttGrandchild;ttRoot.querySelector('.uc-tree-twisty').click();")
        detail = m.js("""
          return {selected:gBrowser.selectedTab===ttRoot,
            child:getComputedStyle(ttChild).display,grandchild:getComputedStyle(ttGrandchild).display,
            expanded:ttRoot.querySelector(".uc-tree-twisty").getAttribute("aria-expanded")};
        """)
        check("collapse_arrow_hides_branch", detail, detail == {
            "selected": True, "child": "none", "grandchild": "none", "expanded": "false",
        })

        m.js("gBrowser.selectedTab=ttGrandchild;")
        detail = m.js("""
          return {child:!ttChild.hasAttribute("uc-tree-hidden"),
            grandchild:!ttGrandchild.hasAttribute("uc-tree-hidden"),
            expanded:ttRoot.querySelector(".uc-tree-twisty").getAttribute("aria-expanded")};
        """)
        check("selecting_hidden_child_expands_ancestors", detail,
              detail["child"] and detail["grandchild"] and detail["expanded"] == "true")

        m.js("gBrowser.selectedTab=ttRoot;")
        content()
        preserved = m.js("return {marker:window.wrappedJSObject.pageMarker,draft:document.getElementById('draft').value};")
        chrome()
        preserved["context"] = m.js("return ttRoot.linkedBrowser.browsingContext.id;")
        check("source_page_not_reloaded", preserved,
              preserved["marker"] == original_marker and preserved["context"] == original_context and
              preserved["draft"] == "A draft changed after loading")

        check("cycle_rejected", m.js("return TreeTabs.nest(ttRoot,ttGrandchild)===false;"))
        assert result["checks"]["cycle_rejected"]
        m.js("window.ttPlain=gBrowser.addTrustedTab('about:blank',{inBackground:false,ownerTab:ttRoot});")
        settle()
        check("ordinary_new_tab_stays_at_root", m.js("return TreeTabs.parentOf(ttPlain)===null;"))
        assert result["checks"]["ordinary_new_tab_stays_at_root"]
        m.js("gBrowser.moveTabAfter(ttPlain,ttGrandchild);")
        settle()
        m.js("""
          TabContextMenu.contextTab=ttPlain;
          document.getElementById("uc-tree-nest").doCommand();
        """)
        settle()
        check("context_menu_nests_existing_tab", m.js("return TreeTabs.parentOf(ttPlain)!==null;"))
        assert result["checks"]["context_menu_nests_existing_tab"]
        check("outdent", m.js("return TreeTabs.outdent(ttGrandchild)&&TreeTabs.parentOf(ttGrandchild)===ttRoot;"))
        assert result["checks"]["outdent"]

        root_identity = m.js("return TreeTabs.snapshot().find(n=>n.tab===ttRoot.id).id;")
        m.js("""
          window.ttDuplicate=gBrowser.duplicateTab(ttRoot);
          gBrowser.moveTabBefore(ttDuplicate,ttRoot);
        """)
        wait("!ttDuplicate.hasAttribute('busy')")
        settle()
        duplicate = m.js("""
          const tree=TreeTabs.snapshot();
          return {root:tree.find(n=>n.tab===ttRoot.id).id,
            clone:tree.find(n=>n.tab===ttDuplicate.id).id,
            childUnchanged:TreeTabs.parentOf(ttChild)===ttRoot};
        """)
        check("duplicate_keeps_original_tree_identity", duplicate,
              duplicate["root"] == root_identity and duplicate["clone"] != root_identity and
              duplicate["childUnchanged"])

        m.js("gBrowser.moveTabAfter(ttGrandchild,ttPlain);")
        settle()
        check("native_reorder_detaches_moved_branch", m.js("return TreeTabs.parentOf(ttGrandchild)===null;"))

        m.js("""
          window.ttOrder=Array.from({length:4},()=>gBrowser.addTrustedTab("about:blank",{inBackground:true}));
          TreeTabs.nest(ttOrder[1],ttOrder[0]);
          TreeTabs.nest(ttOrder[2],ttOrder[1]);
          TreeTabs.nest(ttOrder[3],ttOrder[0]);
          TreeTabs.outdent(ttOrder[2]);
        """)
        settle()
        m.js("""
          ttOrder.push(gBrowser.addTrustedTab("about:blank",{
            inBackground:true,openerBrowser:ttOrder[0].linkedBrowser}));
        """)
        settle()
        order = m.js("""
          return [...gZenWorkspaces.allStoredTabs].filter(t=>ttOrder.includes(t)).map(t=>ttOrder.indexOf(t));
        """)
        check("new_children_follow_reordered_subtree", order, order == [0, 1, 3, 2, 4])
        m.js("for(const tab of ttOrder)gBrowser.removeTab(tab,{animate:false,skipPermitUnload:true});")
        settle()

        m.js("""
          window.ttPin=gBrowser.addTrustedTab("about:blank",{inBackground:true});
          window.ttPinChild=gBrowser.addTrustedTab("about:blank",{inBackground:true});
          TreeTabs.nest(ttPinChild,ttPin);
          gBrowser.pinTab(ttPin);
        """)
        settle()
        check("pinning_promotes_children", m.js(
            "return TreeTabs.parentOf(ttPinChild)===null&&!ttPin.hasAttribute('uc-tree-node');"))
        assert result["checks"]["pinning_promotes_children"]

        m.js("""
          window.ttGroupA=gBrowser.addTrustedTab("about:blank",{inBackground:true});
          window.ttGroupB=gBrowser.addTrustedTab("about:blank",{inBackground:true});
          gBrowser.addTabGroup([ttGroupA,ttGroupB],{label:"Existing group",insertBefore:ttGroupA});
        """)
        settle()
        check("native_groups_excluded", m.js(
            "return !TreeTabs.nest(ttGroupA,ttRoot)&&!TreeTabs.nest(ttRoot,ttGroupB);"))
        assert result["checks"]["native_groups_excluded"]

        current_space = m.js("return gZenWorkspaces.activeWorkspace;")
        other_space = m.async_js("""
          const space=await gZenWorkspaces.createAndSaveWorkspace("Tree test Space");
          window.ttOther=gBrowser.addTrustedTab("about:blank",{inBackground:false});
          return space.uuid;
        """)
        settle()
        check("cross_space_nesting_rejected", m.js("return !TreeTabs.nest(ttOther,ttRoot);"))
        assert result["checks"]["cross_space_nesting_rejected"]
        m.async_js("await gZenWorkspaces.changeWorkspaceWithID(arguments[0]);return true;", [current_space])
        m.js("gBrowser.selectedTab=ttRoot;")

        click("blank")
        wait("gBrowser.selectedTab.hasAttribute('zen-glance-tab')")
        wait("!gZenGlanceManager._animating && !gZenGlanceManager.animatingOpen")
        settle()
        preview = m.js("""
          return {preview:gBrowser.selectedTab.hasAttribute("zen-glance-tab"),
            parent:!!TreeTabs.parentOf(gBrowser.selectedTab),
            styled:gBrowser.selectedTab.hasAttribute("uc-tree-node")};
        """)
        check("automatic_glance_excluded", preview,
              preview["preview"] and not preview["parent"] and not preview["styled"])
        m.async_js("await gZenGlanceManager.closeGlance({hasFocused:true,skipPermitUnload:true});return true;")
        wait("!gBrowser.selectedTab.hasAttribute('zen-glance-tab')")
        wait("!gZenGlanceManager._animating && !gZenGlanceManager.animatingOpen")
        m.js("gBrowser.selectedTab=ttRoot;")
        click("next", "\ue00a")
        wait("ttRoot.hasAttribute('split-view')")
        settle()
        split = m.js("""
          window.ttSplit=ttRoot.group;
          return {split:ttRoot.hasAttribute("split-view"),
            styled:ttSplit.hasAttribute("uc-tree-node"),
            context:ttRoot.linkedBrowser.browsingContext.id,
            childrenKept:TreeTabs.parentOf(ttChild)===ttSplit,
            units:TreeTabs.snapshot().filter(n=>n.kind==="split"&&n.tab===ttSplit.id).length};
        """)
        check("option_split_preserves_source_and_tree", split,
              split["split"] and split["styled"] and split["units"] == 1 and
              split["context"] == original_context and split["childrenKept"])

        m.js("""
          window.ttSplitParent=gBrowser.addTrustedTab("about:blank",{inBackground:true});
          window.ttSplitPanes=[...ttSplit.tabs];
          window.ttSplitContexts=ttSplitPanes.map(t=>t.linkedBrowser.browsingContext.id);
          window.ttSplitDocuments=ttSplitPanes.map(t=>t.linkedBrowser.browsingContext.currentWindowGlobal.innerWindowId);
          window.ttSplitIdentity=TreeTabs.snapshot().find(n=>n.tab===ttSplit.id).id;
          TreeTabs.nest(ttSplitPanes[1],ttSplitParent);
        """)
        settle()
        check("split_is_one_child_from_either_pane", m.js("""
          return ttSplitPanes.every(t=>TreeTabs.parentOf(t)===ttSplitParent&&TreeTabs.depthOf(t)===1)
            && TreeTabs.parentOf(ttChild)===ttSplit && TreeTabs.depthOf(ttChild)===2
            && ttSplit.tabs.length===2;
        """))

        m.js("gBrowser.selectedTab=ttSplitPanes[1];")
        click("next", "\ue03d")
        settle()
        check("command_click_from_second_pane_nests_under_session", m.js("""
          window.ttSplitLink=[...gZenWorkspaces.allStoredTabs].find(t=>
            t.openerTab===ttSplitPanes[1]&&!ttSplitPanes.includes(t));
          return !!ttSplitLink&&TreeTabs.parentOf(ttSplitLink)===ttSplit
            && gBrowser.selectedTab===ttSplitPanes[1]
            && !ttSplitLink.group&&!ttSplitLink.hasAttribute("zen-glance-tab");
        """))

        m.js("""
          window.ttNestedA=gBrowser.addTrustedTab("about:blank",{inBackground:true});
          window.ttNestedB=gBrowser.addTrustedTab("about:blank",{inBackground:true});
          gZenViewSplitter.splitTabs([ttNestedA,ttNestedB],"grid",-1,{activate:false});
          window.ttNestedSplit=ttNestedA.group;
        """)
        settle()
        check("split_can_be_child_of_another_split", m.js("""
          return TreeTabs.nest(ttNestedB,ttSplitPanes[0]) &&
            TreeTabs.parentOf(ttNestedA)===ttSplit && TreeTabs.depthOf(ttNestedB)===2 &&
            ttNestedA.group===ttNestedSplit&&ttNestedB.group===ttNestedSplit;
        """))
        m.js("""
          window.ttNestedChild=gBrowser.addTrustedTab("about:blank",{inBackground:true});
          TreeTabs.nest(ttNestedChild,ttNestedB);
          gBrowser.selectedTab=ttNestedChild;
          ttSplitParent.querySelector(".uc-tree-twisty").click();
        """)
        check("collapse_hides_whole_split_sessions", m.js("""
          return gBrowser.selectedTab===ttSplitParent&&getComputedStyle(ttSplit).display==="none"&&
            getComputedStyle(ttNestedSplit).display==="none"&&
            ttSplitPanes.every(t=>t.getBoundingClientRect().height===0);
        """))
        m.js("gBrowser.selectedTab=ttNestedB;")
        check("selecting_either_pane_reveals_ancestors", m.js("""
          return !ttSplit.hasAttribute("uc-tree-hidden")&&!ttNestedSplit.hasAttribute("uc-tree-hidden")&&
            ttSplitParent.querySelector(".uc-tree-twisty").getAttribute("aria-expanded")==="true";
        """))
        m.js("""
          gBrowser.selectedTab=ttNestedChild;
          ttSplit.querySelector(":scope > .uc-tree-twisty").click();
        """)
        check("split_arrow_collapses_children_without_hiding_panes", m.js("""
          return ttSplit.tabs.includes(gBrowser.selectedTab)&&
            !ttSplit.hasAttribute("uc-tree-hidden")&&ttNestedSplit.hasAttribute("uc-tree-hidden")&&
            ttSplitPanes.every(t=>t.getBoundingClientRect().height>0)&&
            ttSplit.querySelectorAll(".uc-tree-twisty").length===1;
        """))
        m.js("TreeTabs.toggleCollapse(ttSplit);")
        check("split_indentation", m.js("""
          return parseFloat(getComputedStyle(ttSplit).marginInlineStart)>=14 &&
            parseFloat(getComputedStyle(ttNestedSplit).marginInlineStart)>=28;
        """))

        m.js("""
          TabContextMenu.contextTab=ttNestedB;
          document.getElementById("uc-tree-outdent").doCommand();
        """)
        settle()
        check("pane_context_menu_outdents_whole_session", m.js("""
          return TreeTabs.parentOf(ttNestedA)===ttSplitParent&&
            TreeTabs.parentOf(ttNestedB)===ttSplitParent&&ttNestedSplit.tabs.length===2&&
            TreeTabs.parentOf(ttNestedChild)===ttNestedSplit;
        """))
        check("split_state_saved_on_each_pane", m.js("""
          const values=ttSplitPanes.map(t=>JSON.parse(SessionStore.getCustomTabValue(t,"uc-tree-tabs-state")));
          return values.every(v=>v.id===ttSplitIdentity&&v.split===ttSplit.id)&&
            JSON.stringify(values[0])===JSON.stringify(values[1]);
        """))
        check("split_reparenting_preserves_panes_and_documents", m.js("""
          return ttSplitPanes.every((t,i)=>t.group===ttSplit&&
            t.linkedBrowser.browsingContext.id===ttSplitContexts[i]&&
            t.linkedBrowser.browsingContext.currentWindowGlobal.innerWindowId===ttSplitDocuments[i]);
        """))

        m.js("""
          window.ttThirdPane=gBrowser.addTrustedTab("about:blank",{inBackground:true});
          window.ttNestedIdentity=TreeTabs.snapshot().find(n=>n.tab===ttNestedSplit.id).id;
          gZenViewSplitter.splitTabs([ttNestedB,ttThirdPane],"grid",-1,{activate:false});
        """)
        settle()
        check("adding_pane_preserves_session_tree", m.js("""
          return ttNestedSplit.tabs.length===3&&TreeTabs.parentOf(ttThirdPane)===ttSplitParent&&
            TreeTabs.parentOf(ttNestedChild)===ttNestedSplit&&
            TreeTabs.snapshot().find(n=>n.tab===ttNestedSplit.id).id===ttNestedIdentity;
        """))
        m.js("gBrowser.removeTab(ttNestedA,{animate:false,skipPermitUnload:true});")
        settle()
        check("closing_first_of_three_panes_keeps_session_identity", m.js("""
          return ttNestedSplit.tabs.length===2&&TreeTabs.parentOf(ttNestedB)===ttSplitParent&&
            TreeTabs.parentOf(ttNestedChild)===ttNestedSplit&&
            TreeTabs.snapshot().find(n=>n.tab===ttNestedSplit.id).id===ttNestedIdentity;
        """))
        m.js("gBrowser.removeTab(ttNestedB,{animate:false,skipPermitUnload:true});")
        settle()
        check("last_surviving_pane_inherits_session_tree", m.js("""
          return ttThirdPane.isConnected&&!ttThirdPane.group&&TreeTabs.parentOf(ttThirdPane)===ttSplitParent&&
            TreeTabs.parentOf(ttNestedChild)===ttThirdPane&&
            TreeTabs.snapshot().find(n=>n.tab===ttThirdPane.id).id===ttNestedIdentity;
        """))

        m.js("""
          window.ttUnsplitA=gBrowser.addTrustedTab("about:blank",{inBackground:true});
          window.ttUnsplitB=gBrowser.addTrustedTab("about:blank",{inBackground:true});
          gZenViewSplitter.splitTabs([ttUnsplitA,ttUnsplitB],"grid",-1,{activate:false});
        """)
        settle()
        m.js("""
          window.ttUnsplitGroup=ttUnsplitA.group;
          window.ttUnsplitChild=gBrowser.addTrustedTab("about:blank",{inBackground:true});
          TreeTabs.nest(ttUnsplitA,ttSplitParent);
          TreeTabs.nest(ttUnsplitChild,ttUnsplitB);
          gZenViewSplitter.removeGroup(gZenViewSplitter._data.findIndex(g=>g.tabs.includes(ttUnsplitA)));
        """)
        settle()
        check("unsplitting_keeps_surviving_tree_and_peer", m.js("""
          return !ttUnsplitA.group&&!ttUnsplitB.group&&
            TreeTabs.parentOf(ttUnsplitA)===ttSplitParent&&TreeTabs.parentOf(ttUnsplitB)===ttSplitParent&&
            TreeTabs.parentOf(ttUnsplitChild)===ttUnsplitA;
        """))

        m.js("""
          window.ttMergeA=gBrowser.addTrustedTab("about:blank",{inBackground:true});
          window.ttMergeB=gBrowser.addTrustedTab("about:blank",{inBackground:true});
          window.ttMergeChild=gBrowser.addTrustedTab("about:blank",{inBackground:true});
          TreeTabs.nest(ttMergeA,ttSplitParent);
          TreeTabs.nest(ttMergeB,ttMergeA);
          TreeTabs.nest(ttMergeChild,ttMergeB);
          gZenViewSplitter.splitTabs([ttMergeA,ttMergeB],"grid",-1,{activate:false});
        """)
        settle()
        check("splitting_parent_with_child_merges_without_cycle", m.js("""
          window.ttMergeGroup=ttMergeA.group;
          return TreeTabs.parentOf(ttMergeA)===ttSplitParent&&
            TreeTabs.parentOf(ttMergeChild)===ttMergeGroup&&
            !TreeTabs.nest(ttMergeA,ttMergeB)&&!TreeTabs.nest(ttMergeGroup,ttMergeChild);
        """))
        m.js("gBrowser.moveTabAfter(ttMergeGroup,ttSplitParent);")
        settle()
        check("native_split_reorder_detaches_whole_session", m.js("""
          return ttMergeGroup.tabs.length===2&&TreeTabs.parentOf(ttMergeB)===null&&
            TreeTabs.parentOf(ttMergeChild)===ttSplitParent;
        """))
        m.js("""
          TreeTabs.nest(ttMergeA,ttSplitParent);
          TreeTabs.nest(ttMergeChild,ttMergeB);
          for(const tab of [...ttMergeGroup.tabs])
            gBrowser.removeTab(tab,{animate:false,skipPermitUnload:true});
        """)
        settle()
        check("closing_whole_split_promotes_children_without_closing_them", m.js("""
          return ttMergeChild.isConnected&&!ttMergeChild.closing&&
            TreeTabs.parentOf(ttMergeChild)===ttSplitParent;
        """))

        m.js("""
          window.ttCloseParent=gBrowser.addTrustedTab("about:blank",{inBackground:true});
          window.ttCloseChild=gBrowser.addTrustedTab("about:blank",{inBackground:true});
          TreeTabs.nest(ttCloseChild,ttCloseParent);
          gBrowser.removeTab(ttCloseParent,{animate:false,skipPermitUnload:true});
        """)
        settle()
        check("closing_parent_keeps_child", m.js(
            "return ttCloseChild.isConnected&&!ttCloseChild.closing&&TreeTabs.parentOf(ttCloseChild)===null;"))
        assert result["checks"]["closing_parent_keeps_child"]

        m.js("""
          window.ttPerf=[];
          for(let i=0;i<160;i++)ttPerf.push(gBrowser.addTrustedTab(
            "https://example.invalid/tree-test/"+i,{inBackground:true,createLazyBrowser:true}));
        """)
        settle()
        perf = m.js("""
          return {tabs:gZenWorkspaces.allStoredTabs.length,lastReconcileMs:TreeTabs.lastReconcileMs,
            lazy:ttPerf.every(t=>t.hasAttribute("pending"))};
        """)
        check("large_lazy_tab_set", perf, perf["lazy"] and perf["lastReconcileMs"] < 250)
        idle_before = m.js("return TreeTabs.reconciliations;")
        time.sleep(.5)
        idle_after = m.js("return TreeTabs.reconciliations;")
        check("no_idle_polling", {"before": idle_before, "after": idle_after}, idle_before == idle_after)
        m.js("for(const t of ttPerf)gBrowser.removeTab(t,{animate:false,skipPermitUnload:true});")
        settle()

        # Keep a split between an ordinary parent and child for restart checks.
        m.js("""
          window.ttSaveRoot=gBrowser.addTrustedTab("about:blank",{inBackground:false});
          window.ttSaveChild=gBrowser.addTrustedTab("about:blank",{inBackground:true});
          window.ttSaveGrandchild=gBrowser.addTrustedTab("about:blank",{inBackground:true});
          window.ttSavePane=gBrowser.addTrustedTab("about:blank",{inBackground:true});
          for(const t of [...gZenWorkspaces.allStoredTabs]){
            if(![ttSaveRoot,ttSaveChild,ttSaveGrandchild,ttSavePane].includes(t)&&!t.hasAttribute("zen-empty-tab"))
              gBrowser.removeTab(t,{animate:false,skipPermitUnload:true});
          }
          gZenViewSplitter.splitTabs([ttSaveChild,ttSavePane],"grid",-1,{activate:false});
        """)
        settle()
        m.js("""
          TreeTabs.nest(ttSaveChild,ttSaveRoot);
          TreeTabs.nest(ttSaveGrandchild,ttSaveChild);
          gBrowser.selectedTab=ttSaveRoot;
          TreeTabs.toggleCollapse(ttSaveRoot);
        """)
        before_unload = m.js("""
          return {ids:[ttSaveRoot,ttSaveChild,ttSaveGrandchild,ttSavePane].map(t=>t.linkedBrowser.browsingContext.id),
            tree:TreeTabs.snapshot()};
        """)
        m.js('Services.prefs.setBoolPref("uc.tree-tabs.enabled",false);')
        settle()
        check("disable_restores_flat_tabs", m.js(
            "return !document.querySelector('[uc-tree-hidden],.uc-tree-twisty');"))
        assert result["checks"]["disable_restores_flat_tabs"]
        m.js('Services.prefs.setBoolPref("uc.tree-tabs.enabled",true);')
        settle()
        check("reenable_restores_tree", m.js(
            "return TreeTabs.depthOf(ttSaveGrandchild)===2&&TreeTabs.itemOf(ttSaveChild).hasAttribute('uc-tree-hidden');"))
        assert result["checks"]["reenable_restores_tree"]
        m.js("TreeTabs.destroy();")
        check("unload_preserves_live_tabs", m.js("""
          return {clear:!document.querySelector("[uc-tree-hidden],.uc-tree-twisty"),
            ids:[ttSaveRoot,ttSaveChild,ttSaveGrandchild,ttSavePane].map(t=>t.linkedBrowser.browsingContext.id)};
        """))
        assert result["checks"]["unload_preserves_live_tabs"]["clear"]
        assert result["checks"]["unload_preserves_live_tabs"]["ids"] == before_unload["ids"]
        m.js("""
          Services.scriptloader.loadSubScriptWithOptions(
            "chrome://sine/content/tree-tabs-prototype/tree-tabs.uc.js",{target:window,ignoreCache:true});
        """)
        wait("window.TreeTabs?.status==='ready'")
        check("reload_restores_relationships", m.js("return TreeTabs.depthOf(ttSaveGrandchild)===2;"))
        assert result["checks"]["reload_restores_relationships"]
        result["restartExpected"] = m.js("return TreeTabs.snapshot();")
        result["otherWorkspace"] = other_space
        result["passed"] = True
    except Exception as error:
        result["passed"] = False
        result["error"] = str(error)
        try:
            chrome()
            result["diagnostics"] = m.js("return {tree:window.TreeTabs?.snapshot(),error:window.TreeTabs?.lastError};")
        except Exception:
            pass
        raise
    finally:
        args.report.write_text(json.dumps(result, indent=2) + "\n")
        try:
            m.close()
        finally:
            server.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--port", type=int, default=2832)
    run(parser.parse_args())
