#!/usr/bin/env python3
"""Exercise Sine Sync through two disposable, unsigned-in Zen profiles."""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "little-zen" / "scripts"))
from runtime import Marionette

CONTROLLER = 'ChromeUtils.importESModule("chrome://sine/content/sine-sync/SineSync.sys.mjs").controller'


def connect(profile, port):
    if not (profile / "sine-sync-test-profile").is_file():
        raise RuntimeError("A disposable sine-sync-test-profile marker is required.")
    client = Marionette(port)
    actual = client.js('return Services.dirsvc.get("ProfD", Ci.nsIFile).path;')
    assert actual == str(profile), actual
    assert client.js('return Services.prefs.getBoolPref("identity.fxaccounts.enabled", true);') is False
    return client


def job(client, expression):
    client.js(f"""
      window.__sineSyncJob = {{ done: false }};
      ({expression}).then(
        value => window.__sineSyncJob = {{done:true, value}},
        error => window.__sineSyncJob = {{done:true, error:String(error), stack:error.stack}}
      );
    """)
    deadline = time.monotonic() + 180
    last = None
    while time.monotonic() < deadline:
        result = client.js('return window.__sineSyncJob;')
        if result["done"]:
            if "error" in result:
                raise RuntimeError(result)
            return result.get("value")
        status = client.js('return Services.prefs.getStringPref("uc.sine-sync.status", "");')
        if status != last:
            print(status, flush=True)
            last = status
        time.sleep(0.5)
    raise TimeoutError("Disposable sync did not finish.")


def native_packet(client):
    return client.async_js("""
      const { Weave } = ChromeUtils.importESModule("resource://services-sync/main.sys.mjs");
      await Weave.Service.promiseInitialized;
      const values = Weave.Service.engineManager.get("prefs")._store._getAllPrefs();
      return Object.fromEntries(Object.entries(values).filter(([key]) =>
        key.startsWith("uc.sine-sync.data.") ||
        key.startsWith("services.sync.prefs.sync.uc.sine-sync.data.")));
    """)


def deliver(client, packet):
    client.async_js("""
      const { Weave } = ChromeUtils.importESModule("resource://services-sync/main.sys.mjs");
      await Weave.Service.promiseInitialized;
      await Weave.Service.engineManager.get("prefs")._store._setAllPrefs(arguments[0]);
      return true;
    """, [packet])


def identities(client):
    return client.js("""
      return [...gZenWorkspaces.allStoredTabs].map(tab => ({
        tab:tab.id, context:tab.linkedBrowser.browsingContext?.id,
        document:tab.linkedBrowser.browsingContext?.currentWindowGlobal?.innerWindowId
      }));
    """)


def content(client, script):
    client.command("Marionette:SetContext", {"value": "chrome"})
    handle = client.command("WebDriver:GetWindowHandle")
    client.command("WebDriver:SwitchToWindow", {"handle": handle})
    client.command("Marionette:SetContext", {"value": "content"})
    try:
        return client.js(script)
    finally:
        client.command("Marionette:SetContext", {"value": "chrome"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-profile", required=True, type=Path)
    parser.add_argument("--receiver-profile", required=True, type=Path)
    parser.add_argument("--source-port", type=int, default=2842)
    parser.add_argument("--receiver-port", type=int, default=2843)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    source = connect(args.source_profile, args.source_port)
    target = connect(args.receiver_profile, args.receiver_port)
    checks = []

    def check(name, condition):
        assert condition, name
        checks.append(name)
        print("PASS", name, flush=True)

    try:
        source.js("""
          Services.prefs.setStringPref("uc.sine-sync.channel","work");
          Services.prefs.setStringPref("uc.sine-sync.mode","send");
          Services.prefs.setStringPref("uc.findbar.text-size","7px");
          Services.prefs.setStringPref("extensions.downloads.mistral_api_key","SOURCE-SECRET-FIXTURE");
        """)
        result = job(source, f"{CONTROLLER}.run({{claim:true}})")
        check("all 15 installed mods are described", result["mods"] == 15)
        packet = native_packet(source)
        check("native prefs serialization includes the payload", "uc.sine-sync.data.work" in packet)
        check("secret fixture is absent from the payload", "SOURCE-SECRET-FIXTURE" not in json.dumps(packet))
        check("mode and channel are not synchronized", "uc.sine-sync.mode" not in packet and "uc.sine-sync.channel" not in packet)
        check("both channel control preferences are registered", all(
            packet.get("services.sync.prefs.sync.uc.sine-sync.data." + key) is True
            for key in ["work", "personal"]
        ))
        target.js("""
          Services.prefs.setStringPref("uc.sine-sync.mode","off");
          Services.prefs.setStringPref("extensions.downloads.mistral_api_key","DESTINATION-SECRET-FIXTURE");
          Services.prefs.setStringPref("uc.profile-switcher.external-profile","C:\\\\Users\\\\Test\\\\Work");
        """)
        deliver(target, packet)
        check("native prefs deserialization accepts the payload", target.js(
            'return Services.prefs.getStringPref("uc.sine-sync.data.work", "");'
        ) == packet["uc.sine-sync.data.work"])
        check("off mode does not install anything", target.async_js("""
          const p = Services.dirsvc.get("ProfD",Ci.nsIFile).path;
          return Object.keys(await IOUtils.readJSON(PathUtils.join(p,"chrome","sine-mods","mods.json"))).length;
        """) == 1)
        content(target, """
          document.body.innerHTML = '<input id="sync-draft">';
          document.getElementById("sync-draft").value = 'unsaved fixture';
          window.wrappedJSObject.syncFixture = 'same live document';
          return true;
        """)
        before = identities(target)
        target.js('Services.prefs.setStringPref("uc.sine-sync.mode","receive");')
        result = job(target, f"{CONTROLLER}.run()")
        check("receiver installs all 15 mods", result["mods"] == 15 and len(result["changedFiles"]) == 15)
        check("code installation requests a user restart", result["restartRequired"])
        check("tab and document identities survive installation", identities(target) == before)
        check("unsaved input and page state survive installation", content(target, """
          return document.getElementById("sync-draft").value === 'unsaved fixture' &&
            window.wrappedJSObject.syncFixture === 'same live document';
        """))
        check("portable setting is applied", target.js('return Services.prefs.getStringPref("uc.findbar.text-size");') == "7px")
        check("destination credentials stay local", target.js('return Services.prefs.getStringPref("extensions.downloads.mistral_api_key");') == "DESTINATION-SECRET-FIXTURE")
        check("destination profile path stays local", target.js('return Services.prefs.getStringPref("uc.profile-switcher.external-profile");') == "C:\\Users\\Test\\Work")
        check("no unrelated global JS rebuild occurs", target.js('return typeof window.WindowSyncRecovery;') == "undefined")
        again = job(target, f"{CONTROLLER}.run()")
        check("repeating the same sync makes no additional changes", not again["changedFiles"] and not again["changedPrefs"] and again["backup"] is None)
        work = source.js('return Services.prefs.getStringPref("uc.sine-sync.data.work");')
        source.js("""
          Services.prefs.setStringPref("uc.sine-sync.channel","personal");
          Services.prefs.setStringPref("uc.findbar.text-size","9px");
        """)
        job(source, f"{CONTROLLER}.run({{claim:true}})")
        check("publishing Personal preserves Work", source.js('return Services.prefs.getStringPref("uc.sine-sync.data.work");') == work)
        deliver(target, native_packet(source))
        job(target, f"{CONTROLLER}.run()")
        check("Personal arrival does not change a Work receiver", target.js('return Services.prefs.getStringPref("uc.findbar.text-size");') == "7px")
        check("receiver never alters the source payload", target.js('return Services.prefs.getStringPref("uc.sine-sync.data.work");') == work)
        target.async_js(f"""
          const manager = ChromeUtils.importESModule("chrome://userscripts/content/core/manager.sys.mjs").default;
          await manager.removeUnloadListeners("sine-sync");
          return true;
        """)
        check("Sine unload stops the process controller", target.js(f"return {CONTROLLER}.started;") is False)
        target.async_js(f"await {CONTROLLER}.start(); return true;")
        check("controller can restart after unload", target.js(f"return {CONTROLLER}.started;") is True)
        source.js("""
          Services.prefs.setStringPref("uc.sine-sync.channel","work");
          Services.prefs.setStringPref("uc.findbar.text-size","7px");
        """)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({"checks": checks, "passed": len(checks), "packetBytes": len(json.dumps(packet))}, indent=2) + "\n")
    finally:
        source.close()
        target.close()


if __name__ == "__main__":
    main()
