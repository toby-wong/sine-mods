"""Verify Little Zen's compact toolbar and its three keep actions."""

import argparse
import base64
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from runtime import Marionette


def run(args):
    m = Marionette(args.port)
    result = {"checks": {}}
    try:
        actual = m.js('return Services.dirsvc.get("ProfD",Ci.nsIFile).path;')
        if Path(actual).resolve() != args.profile.resolve() or "test-profile" not in args.profile.name:
            raise RuntimeError("Toolbar checks require the disposable test profile.")
        main = m.command("WebDriver:GetWindowHandle")
        setup = m.async_js("""
          if (window._littleZenInfo) throw Error("Start in the regular test window.");
          Services.scriptloader.loadSubScriptWithOptions(
            "chrome://sine/content/little-zen/little-zen.uc.js",{target:window,ignoreCache:true});
          await ChromeUtils.importESModule(
            "chrome://userscripts/content/services/stylesheets.sys.mjs").default.rebuildMods();
          const space=gZenWorkspaces.getActiveWorkspaceFromCache();
          space.name="Oncall";
          gZenWorkspaces.saveWorkspace(space);
          await new Promise(r=>setTimeout(r,100));
          return {space:space.uuid,
            alternate:gZenWorkspaces.getWorkspaces().find(s=>s.uuid!==space.uuid).uuid};
        """)

        for action in ["keyboard", "button", "space_menu"]:
            m.command("Marionette:SetContext", {"value": "chrome"})
            m.command("WebDriver:SwitchToWindow", {"handle": main})
            before = set(m.command("WebDriver:GetWindowHandles"))
            m.js("LittleZen.open();return true;")
            deadline = time.monotonic() + 10
            mini = None
            while time.monotonic() < deadline:
                added = set(m.command("WebDriver:GetWindowHandles")) - before
                if added:
                    mini = added.pop()
                    break
                time.sleep(.05)
            assert mini, "No temporary window opened"
            m.command("WebDriver:SwitchToWindow", {"handle": mini})
            details = m.async_js("""
              const deadline=Date.now()+10000;
              while(window.LittleZen?.status!=="ready" && Date.now()<deadline)
                await new Promise(r=>setTimeout(r,50));
              const box=id=>{
                const r=document.getElementById(id).getBoundingClientRect();
                return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right};
              };
              return {status:LittleZen.status,context:gBrowser.selectedBrowser.browsingContext.id,
                label:document.getElementById("little-zen-keep").getAttribute("label"),
                toolbar:box("navigator-toolbox"),address:box("urlbar-container"),
                controls:box("little-zen-controls"),extensions:box("unified-extensions-button"),
                persist:document.documentElement.hasAttribute("persist")};
            """)
            assert details["status"] == "ready" and details["label"] == "Open in Oncall", details
            assert details["toolbar"]["height"] <= 55 and details["address"]["width"] > 300, details
            assert details["address"]["right"] < details["controls"]["x"], details
            assert details["extensions"]["width"] > 0 and not details["persist"], details

            m.command("WebDriver:SwitchToWindow", {"handle": mini})
            m.command("Marionette:SetContext", {"value": "content"})
            m.js("""
              document.body.innerHTML='<main style="font:18px system-ui;padding:36px"><h1>Little Zen</h1><p>Keep this page without losing your work.</p><input id="draft"></main>';
              document.getElementById("draft").value="Keep my unfinished draft";
              window.littleZenLiveValue=42;
              return true;
            """)
            m.command("Marionette:SetContext", {"value": "chrome"})
            if action == "keyboard":
                image = m.command("WebDriver:TakeScreenshot", {"full": False})
                args.report.with_suffix(".png").write_bytes(base64.b64decode(image))
                m.js("window.focus();gURLBar.select();return true;")
                try:
                    m.command("WebDriver:PerformActions", {"actions": [{
                        "type": "key", "id": "keep-page", "actions": [
                            {"type": "keyDown", "value": "\ue03d"},
                            {"type": "keyDown", "value": "o"},
                        ],
                    }]})
                except RuntimeError as error:
                    # The shortcut can close its source window while WebDriver
                    # is acknowledging the key event. Verify the move below.
                    if "no such window" not in str(error):
                        raise
                m.command("WebDriver:SwitchToWindow", {"handle": main})
                m.command("WebDriver:ReleaseActions")
            else:
                m.command("WebDriver:SwitchToWindow", {"handle": main})
                m.async_js("""
                  const child=[...Services.wm.getEnumerator("navigator:browser")].find(w=>w._littleZenInfo);
                  if(arguments[0]==="button") child.document.getElementById("little-zen-keep").doCommand();
                  else {
                    const popup=child.document.getElementById("little-zen-spaces");
                    popup.openPopup(child.document.getElementById("little-zen-choose-space"),"after_end");
                    await new Promise(r=>setTimeout(r,50));
                    const item=[...popup.children].find(i=>i.getAttribute("data-space-id")===arguments[1]);
                    if(!item) throw Error("The destination Space is missing from the menu.");
                    item.doCommand();
                    popup.hidePopup();
                  }
                  return true;
                """, [action, setup["alternate"]])

            deadline = time.monotonic() + 10
            while mini in m.command("WebDriver:GetWindowHandles") and time.monotonic() < deadline:
                time.sleep(.05)
            details["closed"] = mini not in m.command("WebDriver:GetWindowHandles")
            promoted = m.js("""
              return {context:gBrowser.selectedBrowser.browsingContext.id,
                space:gBrowser.selectedTab.getAttribute("zen-workspace-id")};
            """)
            m.command("WebDriver:SwitchToWindow", {"handle": main})
            m.command("Marionette:SetContext", {"value": "content"})
            preserved = m.js("""
              return document.getElementById("draft")?.value==="Keep my unfinished draft"
                && window.littleZenLiveValue===42;
            """)
            m.command("Marionette:SetContext", {"value": "chrome"})
            wanted = setup["alternate"] if action == "space_menu" else setup["space"]
            details.update({"destination": promoted, "draftPreserved": preserved})
            assert details["closed"] and promoted["context"] == details["context"], details
            assert promoted["space"] == wanted and preserved, details
            result["checks"][action] = details
            print("PASS", action, flush=True)
        result["passed"] = True
    except Exception as error:
        result["passed"] = False
        result["error"] = str(error)
        raise
    finally:
        args.report.write_text(json.dumps(result, indent=2) + "\n")
        m.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=2832)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    run(parser.parse_args())
