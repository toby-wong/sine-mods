"""Glance promotion regressions, restricted to an explicit disposable profile."""

import argparse
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time

from runtime import Marionette


REQUESTS = Counter()
PAGE = b"""<!doctype html><meta charset=utf-8><title>Glance tree test</title>
<style>body{font:18px system-ui;margin:40px}a,input{display:block;margin:20px}</style>
<input id=draft value="Unfinished draft">
<a id=preview href="/preview" target=_blank>Open a preview</a>
<script>window.pageMarker=Math.random();</script>"""


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


def run(args):
    report = {"checks": {}}
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    m = Marionette(args.port)
    verified = False

    def wait(expression):
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            value = m.js("return (" + expression + ");")
            if value:
                return value
            time.sleep(.05)
        raise AssertionError("Timed out: " + expression)

    def check(name, value):
        report["checks"][name] = value
        assert value, name
        print("PASS", name, flush=True)

    def chrome():
        m.command("Marionette:SetContext", {"value": "chrome"})

    def content():
        chrome()
        handle = m.command("WebDriver:GetWindowHandle")
        m.command("WebDriver:SwitchToWindow", {"handle": handle})
        m.command("Marionette:SetContext", {"value": "content"})

    def reload_tree():
        m.async_js("""
          Services.scriptloader.loadSubScriptWithOptions(
            "chrome://sine/content/tree-tabs-prototype/tree-tabs.uc.js",
            {target:window,ignoreCache:true});
          await window.TreeTabs.ready;
          return true;
        """)
        wait("window.TreeTabs?.status==='ready'")

    def open_preview(source="gpRoot"):
        m.js("gBrowser.selectedTab=window[arguments[0]];", [source])
        content()
        wait("document.readyState==='complete' && document.getElementById('preview')")
        point = m.js("""
          const rect=document.getElementById("preview").getBoundingClientRect();
          return {x:Math.round(rect.x+20),y:Math.round(rect.y+rect.height/2)};
        """)
        try:
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
        wait("gBrowser.selectedTab.hasAttribute('zen-glance-tab')"
             " && !gZenGlanceManager._animating && !gZenGlanceManager.animatingOpen")
        m.js("window.gpPreview=gBrowser.selectedTab;")
        content()
        wait("document.readyState==='complete' && document.getElementById('draft')")
        chrome()

    def expand():
        # Execute the visible native Expand control's command.
        m.js('document.querySelector("toolbarbutton[command=cmd_zenGlanceExpand]").doCommand();')
        wait("!gpPreview.hasAttribute('zen-glance-tab') && !gZenGlanceManager._animating"
             " && !gZenGlanceManager.animatingFullOpen")
        time.sleep(.15)

    def close_preview():
        m.async_js("""
          await gZenGlanceManager.closeGlance({hasFocused:true,skipPermitUnload:true});
          return true;
        """)
        wait("!gZenGlanceManager._animating && !gpPreview.isConnected")
        time.sleep(.1)

    try:
        actual = Path(m.js('return Services.dirsvc.get("ProfD",Ci.nsIFile).path;')).resolve()
        if actual != args.profile.resolve() or "test-profile" not in actual.name:
            raise RuntimeError("Refusing to run outside the specified disposable profile")
        verified = True
        m.async_js("""
          if(gZenGlanceManager.getFocusedTab()) {
            await gZenGlanceManager.closeGlance({hasFocused:true,skipPermitUnload:true});
          }
          Services.prefs.setBoolPref("uc.tree-tabs.enabled",true);
          Services.prefs.setBoolPref("uc.tree-tabs.auto-nest",true);
          Services.prefs.setBoolPref("uc.auto-glance.enabled",true);
          Services.prefs.setBoolPref("zen.glance.enabled",true);
          Services.prefs.setStringPref("zen.glance.activation-method","shift");
          return true;
        """)
        reload_tree()
        m.js("""
          window.gpRoot=gBrowser.addTrustedTab(arguments[0]+"/root",{inBackground:false});
          for(const tab of [...gZenWorkspaces.allStoredTabs]) {
            if(tab!==gpRoot && !tab.hasAttribute("zen-empty-tab"))
              gBrowser.removeTab(tab,{animate:false,skipPermitUnload:true});
          }
          gBrowser.selectedTab=gpRoot;
          window.gpIdentity=tab=>({
            context:tab.linkedBrowser.browsingContext.id,
            document:tab.linkedBrowser.browsingContext.currentWindowGlobal.innerWindowId,
          });
          window.gpSibling=gBrowser.addTrustedTab(arguments[0]+"/sibling",{inBackground:true});
          window.gpDescendant=gBrowser.addTrustedTab("about:blank",{inBackground:true});
          TreeTabs.nest(gpSibling,gpRoot);
          TreeTabs.nest(gpDescendant,gpSibling);
        """, [base])
        content()
        wait("document.readyState==='complete' && document.getElementById('draft')")
        m.js('document.getElementById("draft").value="Keep this edited source draft";')
        chrome()
        source_identity = m.js("return gpIdentity(gpRoot);")

        open_preview()
        check("preview_remains_outside_tree", m.js("""
          return !TreeTabs.parentOf(gpPreview) && !gpPreview.hasAttribute("uc-tree-node");
        """))
        content()
        m.js('document.getElementById("draft").value="Keep this edited preview draft";')
        chrome()
        preview_identity = m.js("return gpIdentity(gpPreview);")
        loads = REQUESTS.copy()
        expand()
        check("expand_becomes_child_of_origin", m.js("""
          return TreeTabs.parentOf(gpPreview)===gpRoot && TreeTabs.depthOf(gpPreview)===1
            && gBrowser.selectedTab===gpPreview;
        """))
        check("appended_after_existing_branch", m.js("""
          const tabs=[gpRoot,gpSibling,gpDescendant,gpPreview];
          return [...gZenWorkspaces.allStoredTabs].filter(t=>tabs.includes(t))
            .every((tab,index)=>tab===tabs[index]);
        """))
        check("promotion_preserves_both_documents", source_identity == m.js("return gpIdentity(gpRoot);")
              and preview_identity == m.js("return gpIdentity(gpPreview);") and REQUESTS == loads)
        content()
        check("preview_draft_preserved", m.js(
            'return document.getElementById("draft").value==="Keep this edited preview draft";'))
        chrome()
        m.js("window.gpPromoted=gpPreview;gBrowser.selectedTab=gpRoot;")
        content()
        check("source_draft_preserved", m.js(
            'return document.getElementById("draft").value==="Keep this edited source draft";'))
        chrome()

        open_preview("gpSibling")
        expand()
        check("nested_origin_gets_its_own_child", m.js("""
          return TreeTabs.parentOf(gpPreview)===gpSibling && TreeTabs.depthOf(gpPreview)===2;
        """))

        open_preview()
        m.js("TreeTabs.toggleCollapse(gpRoot);")
        check("origin_collapsed_before_promotion", m.js("return gpRoot.hasAttribute('uc-tree-collapsed');"))
        expand()
        check("promotion_reveals_child_of_collapsed_origin", m.js("""
          return TreeTabs.parentOf(gpPreview)===gpRoot && !gpRoot.hasAttribute("uc-tree-collapsed")
            && !gpPreview.hasAttribute("uc-tree-hidden");
        """))

        for pref, label in [("auto-nest", "auto_nest_off"), ("enabled", "tree_disabled")]:
            open_preview()
            m.js("Services.prefs.setBoolPref(arguments[0],false);", ["uc.tree-tabs." + pref])
            expand()
            check(label + "_keeps_promoted_tab_at_root", m.js("return !TreeTabs.parentOf(gpPreview);"))
            m.js("Services.prefs.setBoolPref(arguments[0],true);", ["uc.tree-tabs." + pref])

        m.js("""
          window.gpPin=gBrowser.addTrustedTab(arguments[0]+"/pinned",{inBackground:true});
          gBrowser.pinTab(gpPin);
          window.gpGroup=gBrowser.addTrustedTab(arguments[0]+"/grouped",{inBackground:true});
          gBrowser.addTabGroup([gpGroup],{label:"Existing group",insertBefore:gpGroup});
        """, [base])
        for source, label in [("gpPin", "pinned"), ("gpGroup", "grouped")]:
            open_preview(source)
            expand()
            check(label + "_origin_remains_excluded", m.js("""
              return !TreeTabs.parentOf(gpPreview) &&
                !window[arguments[0]].hasAttribute("uc-tree-node");
            """, [source]))

        m.js("window.gpSplit=gBrowser.addTrustedTab(arguments[0]+ '/split',{inBackground:true});", [base])
        open_preview("gpSplit")
        split_identities = m.js("return [gpIdentity(gpSplit),gpIdentity(gpPreview)];")
        m.async_js("await gZenGlanceManager.splitGlance();return true;")
        wait("gpSplit.hasAttribute('split-view') && gpPreview.hasAttribute('split-view')")
        check("split_promotion_preserves_native_membership", m.js("""
          const group=gpSplit.closest("tab-group[split-view-group]");
          return !!group && [gpSplit,gpPreview].every(tab=>!TreeTabs.parentOf(tab) &&
            !tab.hasAttribute("uc-tree-node") && tab.closest("tab-group")===group &&
            getComputedStyle(group).display!=="none" &&
            tab.linkedBrowser.getBoundingClientRect().width>100 &&
            tab.linkedBrowser.getBoundingClientRect().height>100);
        """))
        check("split_promotion_preserves_documents", split_identities == m.js(
            "return [gpIdentity(gpSplit),gpIdentity(gpPreview)];"))
        open_preview("gpSplit")
        expand()
        check("split_origin_remains_excluded", m.js("return !TreeTabs.parentOf(gpPreview);"))

        open_preview()
        close_preview()
        check("closed_preview_leaves_no_child", m.js("""
          return !gpPreview.isConnected && !TreeTabs.snapshot().some(node=>node.tab===gpPreview.id);
        """))
        reload_tree()
        check("promoted_relationship_survives_reload", m.js("""
          const parent=JSON.parse(SessionStore.getCustomTabValue(gpRoot,"uc-tree-tabs-state"));
          const child=JSON.parse(SessionStore.getCustomTabValue(gpPromoted,"uc-tree-tabs-state"));
          return TreeTabs.parentOf(gpPromoted)===gpRoot && child.parent===parent.id;
        """))

        # Pause native completion to verify that disabling/unloading while the
        # animation is in flight cannot leave a late write from the old instance.
        m.js("""
          TreeTabs.destroy();
          window.gpNative=gZenGlanceManager.fullyOpenGlance;
          window.gpGate=async function(...args) {
            const value=await window.gpNative.apply(this,args);
            await new Promise(resolve=>{window.gpRelease=resolve;});
            return value;
          };
          gZenGlanceManager.fullyOpenGlance=window.gpGate;
        """)
        reload_tree()
        open_preview()
        m.js("window.gpPending=gZenGlanceManager.fullyOpenGlance();")
        wait("typeof window.gpRelease==='function'")
        m.js("TreeTabs.destroy();window.gpRelease();")
        m.async_js("await window.gpPending;return true;")
        check("unload_restores_previous_promotion_method", m.js(
            "return gZenGlanceManager.fullyOpenGlance===window.gpGate;"))
        m.js("gZenGlanceManager.fullyOpenGlance=window.gpNative;")
        reload_tree()
        check("unload_during_promotion_does_not_attach_late", m.js("return !TreeTabs.parentOf(gpPreview);"))
        check("no_tree_errors", m.js("return !TreeTabs.lastError;"))
        report["passed"] = True
    except Exception as error:
        report["passed"] = False
        report["error"] = str(error)
        raise
    finally:
        try:
            if verified:
                chrome()
                m.js("""
                  window.gpRelease?.();
                  if(gZenGlanceManager.fullyOpenGlance===window.gpGate)
                    gZenGlanceManager.fullyOpenGlance=window.gpNative;
                  Services.prefs.setBoolPref("uc.tree-tabs.enabled",true);
                  Services.prefs.setBoolPref("uc.tree-tabs.auto-nest",true);
                """)
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
