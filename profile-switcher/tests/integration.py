"""Profile Switcher UI checks; requires an explicitly selected disposable profile."""

import argparse
import base64
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "little-zen/scripts"))
from runtime import Marionette


def run(args):
    report = {"checks": {}}
    m = Marionette(args.port)

    def check(name, value):
        assert value, name
        report["checks"][name] = True
        print("PASS", name, flush=True)

    def wait(expression):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            value = m.js("return (" + expression + ");")
            if value:
                return value
            time.sleep(.05)
        raise AssertionError("Timed out: " + expression)

    def key(value):
        m.command("WebDriver:PerformActions", {"actions": [{
            "type": "key", "id": "keyboard",
            "actions": [{"type": "keyDown", "value": value}, {"type": "keyUp", "value": value}],
        }]})

    def close_menu():
        m.js("document.getElementById('profile-switcher-menu').hidePopup();return true;")
        wait("document.getElementById('profile-switcher-menu').state==='closed'")

    try:
        actual = Path(m.js('return Services.dirsvc.get("ProfD",Ci.nsIFile).path;')).resolve()
        if actual != args.profile.resolve() or "test-profile" not in actual.name:
            raise RuntimeError("Refusing to run outside the specified disposable profile")
        if "test-profile" not in args.other_profile.name or args.other_profile.resolve() == actual:
            raise RuntimeError("A second distinct disposable path is required")
        m.async_js("""
          await gZenStartup.promiseInitialized;
          window.ProfileSwitcher?.destroy();
          if(gBrowser.getWindowTitleForBrowser===window.__profileLaterTitle) {
            gBrowser.getWindowTitleForBrowser=window.__profileOriginalTitle;
          }
          const target={module:{exports:{}},ChromeUtils,Services,Cc,Ci,IOUtils,PathUtils,console};
          Services.scriptloader.loadSubScriptWithOptions(
            "chrome://sine/content/profile-switcher/profile-switcher.uc.js",{target,ignoreCache:true});
          window.__profileModule=target.module.exports;
          window.__profileEntries=[
            {name:"Test Work",path:arguments[0]}, {name:"Test Personal",path:arguments[1]}];
          window.__profileLaunches=[];
          window.__profileManaged=0;
          window.__profileEnvironment={
            currentPath:arguments[0],fallbackName:"Test fallback",prefs:Services.prefs,isPrivate:false,
            readProfiles:async()=>window.__profileEntries,
            // UI checks deliberately record launches. Cross-process testing is
            // separate and must validate that both paths are test profiles.
            launch:entry=>window.__profileLaunches.push(entry),
            manage:()=>window.__profileManaged++,
          };
          window.__profileOriginalTitle=gBrowser.getWindowTitleForBrowser;
          window.ProfileSwitcher=__profileModule.createController(window,__profileEnvironment);
          await ProfileSwitcher.ready;
          Services.prefs.setStringPref("uc.profile-switcher.colour","blue");
          Services.prefs.setBoolPref("uc.profile-switcher.show-in-title",true);
          Services.prefs.setStringPref("uc.profile-switcher.external-profile","");
          return true;
        """, [str(actual), str(args.other_profile.resolve())])
        check("current_profile_named", m.js("return ProfileSwitcher.current.name==='Test Work';"))
        check("title_identifies_profile", m.js("return document.title.startsWith('[Test Work] ');"))
        geometry = m.js("""
          const row=document.getElementById("profile-switcher-row");
          const button=document.getElementById("profile-switcher-button");
          const rect=button.getBoundingClientRect();
          return {outsideTabs:!row.closest("#tabbrowser-tabs"),beforeTabs:
            !!(row.compareDocumentPosition(document.getElementById("TabsToolbar"))&Node.DOCUMENT_POSITION_FOLLOWING),
            width:rect.width,height:rect.height,colour:getComputedStyle(row).getPropertyValue("--profile-switcher-colour")};
        """)
        check("visible_control_outside_tab_strip", geometry["outsideTabs"] and geometry["beforeTabs"]
              and geometry["width"] > 100 and geometry["height"] >= 28)
        check("configured_colour", geometry["colour"] == "#377cde")

        m.js("document.getElementById('profile-switcher-button').focus();return true;")
        key("\ue015")  # Down Arrow
        wait("document.getElementById('profile-switcher-menu').state==='open'")
        check("keyboard_opens_native_menu", m.js("""
          return document.getElementById("profile-switcher-button").getAttribute("aria-expanded")==="true";
        """))
        check("current_profile_marked", m.js("""
          const items=[...document.querySelectorAll(".profile-switcher-item")];
          return items.length===2 && items[0].getAttribute("checked")==="true" &&
            items[0].disabled && items[1].getAttribute("label")==="Test Personal" &&
            items.filter(item=>item.hasAttribute("checked")).length===1;
        """))
        check("normal_routing_is_only_initial_destination_marked", m.js("""
          const selected=[...document.querySelectorAll(".profile-switcher-external-destination[checked]")];
          return selected.length===1 && selected[0].getAttribute("data-profile-path")==="";
        """))
        m.js("""
          const menu=document.getElementById("profile-switcher-external-links");
          window.__externalPopup=menu.querySelector("menupopup");
          window.__externalPopup.openPopup(menu,"end_before");
        """)
        wait("window.__externalPopup.state==='open'")
        if m.js("return Services.appinfo.OS;") == "Darwin":
            check("only_selected_items_render_native_checkmarks", m.js("""
              for(const selector of [".profile-switcher-item", ".profile-switcher-external-destination"]) {
                const items=[...document.querySelectorAll(selector)];
                const marked=items.filter(item=>getComputedStyle(item,"::before").visibility==="visible");
                if(marked.length!==1 || !marked[0].hasAttribute("checked")) return false;
              }
              return true;
            """))
        m.js("window.__externalPopup.hidePopup();")
        wait("window.__externalPopup.state==='closed'")
        check("closing_submenu_keeps_button_expanded", m.js("""
          return document.getElementById("profile-switcher-menu").state==="open" &&
            document.getElementById("profile-switcher-button").getAttribute("aria-expanded")==="true";
        """))
        m.js("""
          [...document.querySelectorAll(".profile-switcher-external-destination")]
            .find(item=>item.getAttribute("data-profile-path")===arguments[0]).doCommand();
        """, [str(args.other_profile.resolve())])
        check("external_destination_can_be_configured_in_menu", m.js("""
          return Services.prefs.getStringPref("uc.profile-switcher.external-profile")===arguments[0]
            && window.__profileLaunches.length===0;
        """, [str(args.other_profile.resolve())]))
        close_menu()
        m.async_js("await ProfileSwitcher.openMenu();return true;")
        wait("document.getElementById('profile-switcher-menu').state==='open'")
        check("external_destination_selection_persists", m.js("""
          const selected=[...document.querySelectorAll(".profile-switcher-external-destination[checked]")];
          return selected.length===1 && selected[0].getAttribute("data-profile-path")===arguments[0];
        """, [str(args.other_profile.resolve())]))
        m.js("""
          document.querySelector('.profile-switcher-external-destination[data-profile-path=""]').doCommand();
        """)
        check("normal_external_routing_can_be_restored", m.js("""
          return Services.prefs.getStringPref("uc.profile-switcher.external-profile")==="";
        """))
        close_menu()
        m.async_js("await ProfileSwitcher.openMenu();return true;")
        wait("document.getElementById('profile-switcher-menu').state==='open'")
        check("normal_routing_is_only_restored_destination_marked", m.js("""
          const selected=[...document.querySelectorAll(".profile-switcher-external-destination[checked]")];
          return selected.length===1 && selected[0].getAttribute("data-profile-path")==="";
        """))
        screenshot = m.command("WebDriver:TakeScreenshot", {"full": False})
        args.report.with_suffix(".png").write_bytes(base64.b64decode(screenshot))
        key("\ue00c")  # Escape
        wait("document.getElementById('profile-switcher-menu').state==='closed'")
        check("escape_closes_menu", m.js("""
          return document.getElementById("profile-switcher-button").getAttribute("aria-expanded")==="false";
        """))

        m.async_js("await ProfileSwitcher.openMenu();return true;")
        wait("document.getElementById('profile-switcher-menu').state==='open'")
        m.js("document.querySelectorAll('.profile-switcher-item')[1].doCommand();return true;")
        wait("__profileLaunches.length===1")
        check("menu_routes_exact_profile", m.js(
            "return __profileLaunches[0].path===arguments[0];", [str(args.other_profile.resolve())]))
        close_menu()
        m.async_js("await ProfileSwitcher.openMenu();return true;")
        wait("document.getElementById('profile-switcher-menu').state==='open'")
        m.js("document.getElementById('profile-switcher-manage').doCommand();return true;")
        check("manage_profiles_action", m.js("return __profileManaged===1;"))
        close_menu()

        m.js("Services.prefs.setStringPref('uc.profile-switcher.colour','purple');return true;")
        check("colour_changes_live", m.js("return ProfileSwitcher.current.colour==='#9765cf';"))
        m.js("Services.prefs.setBoolPref('uc.profile-switcher.show-in-title',false);return true;")
        check("title_toggle_restores_native_title", m.js("""
          return document.title===__profileOriginalTitle.call(gBrowser,gBrowser.selectedBrowser);
        """))
        m.js("Services.prefs.setBoolPref('uc.profile-switcher.show-in-title',true);return true;")
        m.async_js("""
          __profileEntries[0].name="Renamed test profile";
          await ProfileSwitcher.refresh();
          return true;
        """)
        check("renames_refresh_without_identity_change", m.js("""
          return ProfileSwitcher.current.name==="Renamed test profile" &&
            ProfileSwitcher.current.path===arguments[0] &&
            document.title.startsWith("[Renamed test profile] ");
        """, [str(actual)]))

        m.js("""
          window.__profilePage=gBrowser.addTrustedTab("data:text/html,<title>Draft page</title><textarea>draft</textarea>",{skipRoute:true});
          gBrowser.selectedTab=__profilePage;
          return true;
        """)
        wait("document.title.includes('Draft page')")
        check("page_titles_keep_profile_prefix", m.js("""
          return document.title.startsWith("[Renamed test profile] ") && document.title.includes("Draft page");
        """))
        m.js("""
          window.__profileSettings=gBrowser.addTrustedTab("about:preferences",{skipRoute:true});
          gBrowser.selectedTab=__profileSettings;
          return true;
        """)
        wait("__profileSettings.linkedBrowser.currentURI.spec==='about:preferences'")
        m.js("gBrowser.removeTab(__profileSettings,{animate:false});return true;")
        check("child_document_unload_keeps_switcher", m.js("return ProfileSwitcher.status==='ready';"))

        state = m.js("""
          return {tabs:[...gBrowser.tabs].filter(t=>t.isConnected&&!t.closing)
            .map(t=>({id:t.id,bc:t.linkedBrowser.browsingContext?.id,
            inner:t.linkedBrowser.browsingContext?.currentWindowGlobal?.innerWindowId})),
            selected:gBrowser.selectedTab.id};
        """)
        m.async_js("""
          ProfileSwitcher.destroy();
          window.ProfileSwitcher=__profileModule.createController(window,__profileEnvironment);
          await ProfileSwitcher.ready;
          return true;
        """)
        check("reload_leaves_one_control_and_prefix", m.js("""
          return document.querySelectorAll("#profile-switcher-row").length===1 &&
            document.title.split("[Renamed test profile]").length===2;
        """))
        after = m.js("""
          return {tabs:[...gBrowser.tabs].filter(t=>t.isConnected&&!t.closing)
            .map(t=>({id:t.id,bc:t.linkedBrowser.browsingContext?.id,
            inner:t.linkedBrowser.browsingContext?.currentWindowGlobal?.innerWindowId})),
            selected:gBrowser.selectedTab.id};
        """)
        check("reload_preserves_tabs_and_documents", state == after)

        m.async_js("""
          window.__profileEntries=window.__profileEntries.slice(0,1);
          await ProfileSwitcher.switchTo(arguments[0]);
          return true;
        """, [str(args.other_profile.resolve())])
        wait("document.getElementById('profile-switcher-menu').state==='open'")
        check("removed_profile_does_not_launch", m.js("return __profileLaunches.length===1;"))
        check("removed_profile_error_visible", m.js("""
          return [...document.querySelectorAll("#profile-switcher-menu menuitem")]
            .some(item=>item.getAttribute("label").includes("no longer registered"));
        """))
        close_menu()

        m.js("""
          window.__profileWrapper=gBrowser.getWindowTitleForBrowser;
          window.__profileLaterTitle=function(...args){return window.__profileWrapper.apply(this,args)+" later";};
          gBrowser.getWindowTitleForBrowser=window.__profileLaterTitle;
          ProfileSwitcher.destroy();
          return true;
        """)
        wait("document.title.endsWith(' later') && !document.title.includes('[Renamed test profile]')")
        unloaded = m.js("""
          return {same:gBrowser.getWindowTitleForBrowser===window.__profileLaterTitle,
            title:document.title,rows:document.querySelectorAll("#profile-switcher-row").length,
            popups:document.querySelectorAll("#profile-switcher-menu").length};
        """)
        report["unloadState"] = unloaded
        check("unload_preserves_later_title_wrapper", unloaded["same"] and unloaded["title"].endswith(" later")
              and "[Renamed test profile]" not in unloaded["title"]
              and unloaded["rows"] == 0 and unloaded["popups"] == 0)
        m.js("gBrowser.getWindowTitleForBrowser=window.__profileOriginalTitle;gBrowser.updateTitlebar();return true;")
        m.async_js("""
          window.ProfileSwitcher=__profileModule.createController(window,{
            ...__profileEnvironment,isPrivate:true,
          });
          await ProfileSwitcher.ready;
          return true;
        """)
        check("private_window_control_label", m.js("""
          return document.querySelector(".profile-switcher-name").textContent.endsWith(" · Private");
        """))
        m.js("""
          ProfileSwitcher.destroy();
          window.__profileResolve=null;
          window.ProfileSwitcher=__profileModule.createController(window,{
            ...__profileEnvironment,readProfiles:()=>new Promise(resolve=>{window.__profileResolve=resolve;}),
          });
          window.__pendingProfileReady=ProfileSwitcher.ready;
          ProfileSwitcher.destroy();
          __profileResolve(__profileEntries);
          return true;
        """)
        m.async_js("await __pendingProfileReady;return true;")
        check("unload_discards_pending_reads", m.js("""
          return !document.getElementById("profile-switcher-row") &&
            gBrowser.getWindowTitleForBrowser===window.__profileOriginalTitle;
        """))
        report["passed"] = True
    except Exception as error:
        report["passed"] = False
        report["error"] = str(error)
        raise
    finally:
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        m.js("""
          window.ProfileSwitcher?.destroy();
          if(gBrowser.getWindowTitleForBrowser===window.__profileLaterTitle) {
            gBrowser.getWindowTitleForBrowser=window.__profileOriginalTitle;
            gBrowser.updateTitlebar();
          }
          return true;
        """)
        m.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--other-profile", type=Path, required=True)
    parser.add_argument("--port", type=int, default=2840)
    parser.add_argument("--report", type=Path, required=True)
    run(parser.parse_args())
