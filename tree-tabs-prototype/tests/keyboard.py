"""Trusted nesting shortcuts, restricted to an explicit disposable Zen profile."""

import argparse
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time

from runtime import Marionette


REQUESTS = Counter()
PAGE = b"""<!doctype html><meta charset=utf-8><title>Tree keyboard test</title>
<button id=focus>Focus page</button>
<input id=draft value="one two three">
<textarea id=textarea>one two three</textarea>
<div id=editor contenteditable>one two three</div>
<a id=preview href="/preview" target=_blank>Preview</a>
<script>
window.pageMarker=Math.random();
window.cancelTreeKeys=false;
document.addEventListener('keydown', event=>{
  if(window.cancelTreeKeys && event.altKey && event.shiftKey)event.preventDefault();
});
window.fakeTreeShortcut=()=>{
  const event=new KeyboardEvent('keydown',{
    key:'ArrowLeft',altKey:true,shiftKey:true,bubbles:true,cancelable:true
  });
  document.getElementById('focus').dispatchEvent(event);
  return event.isTrusted;
};
if(location.pathname!='/frame'){
  const frame=document.createElement('iframe');
  frame.id='frame';frame.src='/frame';document.body.append(frame);
}
</script>"""


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
            if value := m.js("return (" + expression + ");"):
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
        m.command("WebDriver:SwitchToWindow", {"handle": main})
        m.command("Marionette:SetContext", {"value": "content"})

    def settle():
        chrome()
        m.async_js("await new Promise(resolve=>setTimeout(resolve,120));return true;")
        assert not m.js("return TreeTabs.lastError || null;")

    def key(direction, modifiers=("\ue00a", "\ue008"), repeat=False):
        value = "\ue014" if direction == "right" else "\ue012"
        actions = [{"type": "keyDown", "value": mod} for mod in modifiers]
        actions += [{"type": "keyDown", "value": value}]
        if repeat:
            actions += [{"type": "keyDown", "value": value}]
        actions += [{"type": "keyUp", "value": value}]
        actions += [{"type": "keyUp", "value": mod} for mod in reversed(modifiers)]
        try:
            m.command("WebDriver:PerformActions", {
                "actions": [{"type": "key", "id": "tree-keyboard", "actions": actions}],
            })
        finally:
            m.command("WebDriver:ReleaseActions")
        settle()

    def page_focus():
        content()
        wait("document.readyState==='complete' && document.getElementById('focus')")
        m.js("document.getElementById('focus').focus();")

    def parent_is(parent):
        return m.js("return TreeTabs.parentOf(ktTabs[1])===" + parent + ";")

    def identities():
        return m.js("""return ktTabs.map(tab=>[
          tab.linkedBrowser.browsingContext.id,
          tab.linkedBrowser.browsingContext.currentWindowGlobal.innerWindowId
        ]);""")

    def reload_tree():
        m.js("""Services.scriptloader.loadSubScriptWithOptions(
          'chrome://sine/content/tree-tabs-prototype/tree-tabs.uc.js',
          {target:window,ignoreCache:true});""")
        wait("window.TreeTabs?.status==='ready'")
        settle()

    try:
        actual = m.js('return Services.dirsvc.get("ProfD",Ci.nsIFile).path;')
        assert Path(actual).resolve() == args.profile.resolve() and "test-profile" in actual
        verified = True
        main = m.command("WebDriver:GetWindowHandle")
        wait("window.TreeTabs?.status==='ready'")
        report["browser"] = m.js("return Services.appinfo.version;")
        report["os"] = m.js("return Services.appinfo.OS;")
        m.async_js("""
          Services.prefs.setBoolPref('uc.tree-tabs.enabled',true);
          Services.prefs.setBoolPref('uc.tree-tabs.keyboard-shortcuts',true);
          window.ktTabs=Array.from({length:5},(_,i)=>
            gBrowser.addTrustedTab(arguments[0]+'/tab-'+i,{inBackground:true}));
          for(const tab of [...gZenWorkspaces.allStoredTabs]){
            if(!ktTabs.includes(tab)&&!tab.hasAttribute('zen-empty-tab'))
              gBrowser.removeTab(tab,{animate:false,skipPermitUnload:true});
          }
          for(let i=1;i<ktTabs.length;i++)gBrowser.moveTabAfter(ktTabs[i],ktTabs[i-1]);
          await new Promise(resolve=>setTimeout(resolve,200));
          TreeTabs.nest(ktTabs[2],ktTabs[1]);
          TreeTabs.nest(ktTabs[3],ktTabs[2]);
          gBrowser.selectedTab=ktTabs[1];
          TreeTabs.toggleCollapse(ktTabs[2]);
          return true;
        """, [base])
        for i in range(5):
            m.js("gBrowser.selectedTab=ktTabs[arguments[0]];", [i])
            page_focus()
            m.js("document.getElementById('draft').value='Preserved draft '+arguments[0];", [i])
            chrome()
        m.js("""
          gBrowser.selectedTab=ktTabs[1];
          if(!ktTabs[2].hasAttribute('uc-tree-collapsed'))TreeTabs.toggleCollapse(ktTabs[2]);
        """)
        settle()
        before_identity = identities()
        before_requests = [REQUESTS[f"/tab-{i}"] for i in range(5)]
        check("native_keys_registered", m.js("""
          return document.querySelectorAll('#uc-tree-tabs-keys key').length===2 &&
            document.getElementById('uc-tree-nest-key').getAttribute('modifiers')==='alt,shift' &&
            document.getElementById('uc-tree-outdent-key').getAttribute('keycode')==='VK_LEFT' &&
            document.getElementById('uc-tree-nest').getAttribute('key')==='uc-tree-nest-key';
        """))
        page_focus()
        key("right")
        check("page_shortcut_nests_selected_tab", parent_is("ktTabs[0]"))
        check("children_and_collapsed_grandchildren_follow", m.js("""
          return TreeTabs.parentOf(ktTabs[2])===ktTabs[1] &&
            TreeTabs.parentOf(ktTabs[3])===ktTabs[2] &&
            ktTabs[2].hasAttribute('uc-tree-collapsed') &&
            ktTabs[3].hasAttribute('uc-tree-hidden') &&
            JSON.stringify([...gZenWorkspaces.allStoredTabs].filter(t=>ktTabs.includes(t)).map(t=>t.id))===
              JSON.stringify(ktTabs.map(t=>t.id));
        """))
        check("selection_and_documents_preserved", m.js("return gBrowser.selectedTab===ktTabs[1];")
              and identities() == before_identity)
        page_focus()
        key("left")
        check("page_shortcut_outdents_whole_branch", parent_is("null") and m.js("""
          return TreeTabs.parentOf(ktTabs[2])===ktTabs[1] &&
            TreeTabs.parentOf(ktTabs[3])===ktTabs[2] && gBrowser.selectedTab===ktTabs[1];
        """))
        page_focus()
        key("left")
        check("outdenting_a_root_is_a_noop", parent_is("null"))
        page_focus()
        chrome()
        key("right")
        check("browser_routed_page_shortcut_nests_selected_tab", parent_is("ktTabs[0]"))

        for element in ["draft", "textarea", "editor"]:
            content()
            m.js("""
              const element=document.getElementById(arguments[0]);
              element.focus();
              if(element.setSelectionRange)element.setSelectionRange(element.value.length,element.value.length);
              else {
                const range=document.createRange();range.selectNodeContents(element);range.collapse(false);
                const selection=getSelection();selection.removeAllRanges();selection.addRange(range);
              }
            """, [element])
            chrome()
            key("left")
            check(element + "_keeps_its_tree_relationship", parent_is("ktTabs[0]"))
            if report["os"] == "Darwin":
                content()
                check(element + "_keeps_native_word_selection", m.js("""
                  const element=document.getElementById(arguments[0]);
                  return element.setSelectionRange
                    ? element.selectionStart<element.selectionEnd : !getSelection().isCollapsed;
                """, [element]))
                chrome()

        page_focus()
        m.js("window.wrappedJSObject.cancelTreeKeys=true;")
        key("left")
        check("page_cancelled_shortcut_stays_on_page", parent_is("ktTabs[0]"))
        content()
        m.js("window.wrappedJSObject.cancelTreeKeys=false;")
        for name, modifiers in [
            ("plain_arrow", ()), ("alt_only", ("\ue00a",)), ("shift_only", ("\ue008",)),
            ("ctrl_alt_shift", ("\ue00a", "\ue008", "\ue009")),
        ]:
            page_focus()
            key("left", modifiers)
            check(name + "_does_not_move_tabs", parent_is("ktTabs[0]"))
        page_focus()
        check("page_generated_event_is_untrusted",
              m.js("return window.wrappedJSObject.fakeTreeShortcut()===false;"))
        settle()
        check("untrusted_page_events_cannot_move_tabs", parent_is("ktTabs[0]"))

        content()
        frame = m.command("WebDriver:FindElement", {"using": "css selector", "value": "#frame"})
        m.command("WebDriver:SwitchToFrame", {"id": frame})
        wait("document.getElementById('focus')")
        m.js("document.getElementById('focus').focus();")
        key("left")
        check("frame_shortcut_uses_its_own_selected_tab", parent_is("null"))
        page_focus()
        key("right")
        content()
        frame = m.command("WebDriver:FindElement", {"using": "css selector", "value": "#frame"})
        m.command("WebDriver:SwitchToFrame", {"id": frame})
        m.js("const e=document.getElementById('draft');e.focus();e.setSelectionRange(13,13);")
        chrome()
        key("left")
        check("frame_editor_keeps_its_tree_relationship", parent_is("ktTabs[0]"))

        chrome()
        m.js("gURLBar.focus();gURLBar.value='one two three';gURLBar.inputField.setSelectionRange(13,13);")
        key("left")
        check("address_bar_keeps_its_tree_relationship", parent_is("ktTabs[0]"))
        if report["os"] == "Darwin":
            check("address_bar_keeps_native_word_selection", m.js("""
              return gURLBar.inputField.selectionStart<gURLBar.inputField.selectionEnd;
            """))
        m.js("gURLBar.blur();gBrowser.selectedTab.focus();")
        key("left")
        check("sidebar_shortcut_outdents_selected_tab", parent_is("null"))

        m.js("Services.prefs.setBoolPref('uc.tree-tabs.keyboard-shortcuts',false);")
        settle()
        check("shortcut_toggle_updates_keys_and_menu", m.js("""
          return document.getElementById('uc-tree-nest-key').getAttribute('disabled')==='true' &&
            !document.getElementById('uc-tree-nest').hasAttribute('key');
        """))
        page_focus()
        key("right")
        check("shortcut_toggle_disables_content_handling", parent_is("null"))
        m.js("Services.prefs.setBoolPref('uc.tree-tabs.keyboard-shortcuts',true);")
        settle()
        page_focus()
        key("right")
        check("shortcut_toggle_takes_effect_without_reload", parent_is("ktTabs[0]"))
        m.js("Services.prefs.setBoolPref('uc.tree-tabs.enabled',false);")
        settle()
        page_focus()
        key("left")
        check("master_toggle_disables_shortcuts", parent_is("ktTabs[0]"))
        m.js("Services.prefs.setBoolPref('uc.tree-tabs.enabled',true);")
        settle()

        for _ in range(2):
            reload_tree()
        check("hot_reload_does_not_duplicate_keys", m.js("""
          return document.querySelectorAll('#uc-tree-tabs-keys').length===1 &&
            document.querySelectorAll('#uc-tree-tabs-keys key').length===2;
        """))
        m.js("gBrowser.selectedTab=ktTabs[2];")
        settle()
        page_focus()
        key("left", repeat=True)
        check("held_arrow_moves_only_one_level_after_reload", m.js("""
          return TreeTabs.parentOf(ktTabs[2])===ktTabs[0] &&
            TreeTabs.parentOf(ktTabs[3])===ktTabs[2] && gBrowser.selectedTab===ktTabs[2];
        """))
        check("original_documents_and_request_counts_preserved", identities() == before_identity
              and before_requests == [REQUESTS[f"/tab-{i}"] for i in range(5)])
        for i in range(5):
            m.js("gBrowser.selectedTab=ktTabs[arguments[0]];", [i])
            content()
            check("draft_" + str(i) + "_preserved", m.js("""
              return document.getElementById('draft').value==='Preserved draft '+arguments[0];
            """, [i]))
            chrome()

        m.async_js("""
          window.ktSplit=[
            gBrowser.addTrustedTab(arguments[0]+'/split-a',{inBackground:true}),
            gBrowser.addTrustedTab(arguments[0]+'/split-b',{inBackground:true})
          ];
          gZenViewSplitter.splitTabs(ktSplit);
          gBrowser.selectedTab=ktSplit[0];
          await new Promise(resolve=>setTimeout(resolve,200));
          return true;
        """, [base])
        split_before = m.js("""return {
          data:gZenViewSplitter.storeDataForSessionStore(),
          ids:ktSplit.map(t=>t.linkedBrowser.browsingContext.id),
          selected:gBrowser.selectedTab.id
        };""")
        page_focus()
        key("right")
        page_focus()
        key("left")
        check("native_split_members_layout_and_focus_untouched", split_before == m.js("""return {
          data:gZenViewSplitter.storeDataForSessionStore(),
          ids:ktSplit.map(t=>t.linkedBrowser.browsingContext.id),
          selected:gBrowser.selectedTab.id
        };""") and m.js("""
          return ktSplit.every(t=>!t.hasAttribute('uc-tree-node')&&
            !t.hasAttribute('uc-tree-hidden')&&getComputedStyle(t).display!=='none');
        """))
        m.js("gBrowser.selectedTab=ktTabs[1];")
        settle()
        m.js("TreeTabs.destroy();")
        check("unload_removes_native_keys", m.js("""
          return !window.TreeTabs && !document.getElementById('uc-tree-tabs-keys');
        """))
        content()
        m.js("document.getElementById('focus').focus();")
        # An unloaded actor must not reserve the gesture or change saved ancestry.
        values = ["\ue00a", "\ue008", "\ue012"]
        m.command("WebDriver:PerformActions", {"actions": [{
            "type": "key", "id": "tree-keyboard",
            "actions": [{"type": "keyDown", "value": v} for v in values] +
                       [{"type": "keyUp", "value": v} for v in reversed(values)],
        }]})
        m.command("WebDriver:ReleaseActions")
        chrome()
        reload_tree()
        check("unload_leaves_saved_relationships_unchanged", parent_is("ktTabs[0]"))
        check("no_runtime_errors", not m.js("return TreeTabs.lastError || null;"))
    except BaseException as error:
        report["error"] = str(error)
        raise
    finally:
        if verified:
            try:
                chrome()
                m.js("""
                  Services.prefs.setBoolPref('uc.tree-tabs.enabled',true);
                  Services.prefs.setBoolPref('uc.tree-tabs.keyboard-shortcuts',true);
                """)
            except Exception:
                pass
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2))
        m.close()
        server.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--port", type=int, default=2832)
    parser.add_argument("--report", type=Path, required=True)
    run(parser.parse_args())
