"""Exercise the native URL command between two explicitly selected test profiles."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "little-zen/scripts"))
from runtime import Marionette


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"<!doctype html><title>External routing test</title><textarea>Keep this draft</textarea>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


def run(args):
    report = {"checks": {}}
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    source = Marionette(args.port)
    target = Marionette(args.other_port)
    verified = False

    def wait(client, expression, seconds=15):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            value = client.js("return (" + expression + ");")
            if value:
                return value
            time.sleep(.05)
        raise AssertionError("Timed out: " + expression)

    def check(name, value):
        report["checks"][name] = value
        assert value, name
        print("PASS", name, flush=True)

    def send(path):
        return source.async_js("""
          const args=["-url",arguments[0]];
          const command=Cu.createCommandLine(args,Services.dirsvc.get("CurWorkD",Ci.nsIFile),
            Ci.nsICommandLine.STATE_REMOTE_EXPLICIT);
          Cc[window.erClass.contractID].createInstance(Ci.nsICommandLineHandler).handle(command);
          await window.erRouter.idle();
          return {handled:command.preventDefault,remaining:command.length};
        """, [base + path])

    try:
        for client, expected in [(source, args.profile), (target, args.other_profile)]:
            actual = Path(client.js('return Services.dirsvc.get("ProfD",Ci.nsIFile).path;')).resolve()
            if actual != expected.resolve() or "test-profile" not in actual.name:
                raise RuntimeError("Refusing to run outside the explicit disposable profiles")
        if args.profile.resolve() == args.other_profile.resolve():
            raise RuntimeError("Two distinct disposable profiles are required")
        verified = True
        target.js('Services.prefs.setStringPref("uc.profile-switcher.external-profile","");')
        source.async_js("""
          window.erModule=ChromeUtils.importESModule(
            "chrome://sine/content/profile-switcher/ExternalProfileRouting.sys.mjs?v=0.2.0");
          window.erModule.uninstall();
          window.erClass=ChromeUtils.importESModule(
            "resource:///modules/profiles/SelectableProfileService.sys.mjs").CommandLineHandler;
          window.erOriginal=window.erClass.prototype.handle;
          window.erTarget=arguments[1];
          window.erProfiles=[{name:"Test source",path:arguments[0]},{name:"Test destination",path:arguments[1]}];
          window.erLaunches=[];
          window.erErrors=[];
          const native=new window.erClass();
          window.erRouter=window.erModule.createCommandRouter({
            original:window.erOriginal,currentPath:arguments[0],
            remoteExplicit:Ci.nsICommandLine.STATE_REMOTE_EXPLICIT,
            getTarget:()=>window.erTarget,readProfiles:async()=>window.erProfiles,
            isWebURL:value=>{const uri=Services.io.newURI(value);return uri.schemeIs("http")||uri.schemeIs("https");},
            launch:(profile,urls)=>{
              if(profile.path!==arguments[1])throw Error("Unexpected launch destination");
              window.erLaunches.push({path:profile.path,urls});
              window.erModule.launchProfile(profile,urls);
            },
            replay:args=>native.openUrls(args),
            report:error=>window.erErrors.push(String(error)),
          });
          window.erClass.prototype.handle=window.erRouter.handle;
          window.erSource=gBrowser.addTrustedTab(arguments[2]+"/source",{inBackground:false});
          gBrowser.selectedTab=window.erSource;
          return true;
        """, [str(args.profile.resolve()), str(args.other_profile.resolve()), base])
        wait(source, "!window.erSource.hasAttribute('busy') && window.erSource.linkedBrowser.currentURI.spec.endsWith('/source')")
        identity = source.js("""
          return {id:window.erSource.id,context:window.erSource.linkedBrowser.browsingContext.id,
            document:window.erSource.linkedBrowser.browsingContext.currentWindowGlobal.innerWindowId};
        """)

        check("native_external_command_consumed_once", send("/forwarded") == {"handled": True, "remaining": 0})
        wait(target, "[...gZenWorkspaces.allStoredTabs].some(t=>t.linkedBrowser?.currentURI?.spec===" +
             json.dumps(base + "/forwarded") + ")")
        check("url_arrives_in_destination_profile", target.js("""
          return [...gZenWorkspaces.allStoredTabs].filter(t=>t.linkedBrowser?.currentURI?.spec===arguments[0]).length===1;
        """, [base + "/forwarded"]))
        check("source_profile_has_no_copy", source.js("""
          return ![...gZenWorkspaces.allStoredTabs].some(t=>t.linkedBrowser?.currentURI?.spec===arguments[0])
            && gBrowser.selectedTab===window.erSource;
        """, [base + "/forwarded"]))
        check("forwarding_preserves_source_document", identity == source.js("""
          return {id:window.erSource.id,context:window.erSource.linkedBrowser.browsingContext.id,
            document:window.erSource.linkedBrowser.browsingContext.currentWindowGlobal.innerWindowId};
        """))

        source.js("window.erProfiles=window.erProfiles.slice(0,1);")
        send("/missing-destination")
        wait(source, "[...gZenWorkspaces.allStoredTabs].some(t=>t.linkedBrowser?.currentURI?.spec===" +
             json.dumps(base + "/missing-destination") + ")")
        check("missing_destination_uses_native_local_fallback", source.js("return window.erLaunches.length===1;"))

        # Register the production process hook, then exercise Sine's real unload
        # and reload paths. The routing preference remains empty throughout.
        source.async_js("""
          window.erRouter.destroy();
          window.erClass.prototype.handle=window.erOriginal;
          Services.prefs.setStringPref("uc.profile-switcher.external-profile","");
          window.erModule.install();
          window.erInstalled=window.erClass.prototype.handle;
          const manager=ChromeUtils.importESModule("chrome://userscripts/content/core/manager.sys.mjs").default;
          manager.removeListenersForDOM(window);
          return true;
        """)
        check("process_route_survives_window_listener_cleanup", source.js(
            "return window.erClass.prototype.handle===window.erInstalled;"))
        source.async_js("""
          await ChromeUtils.importESModule("chrome://userscripts/content/core/manager.sys.mjs").default
            .removeUnloadListeners("profile-switcher");
          return true;
        """)
        check("sine_unload_restores_native_handler", source.js(
            "return window.erClass.prototype.handle===window.erOriginal;"))
        source.async_js("""
          Services.scriptloader.loadSubScriptWithOptions(
            "chrome://sine/content/profile-switcher/profile-switcher.uc.js",{target:window,ignoreCache:true});
          await window.ProfileSwitcher.ready;
          return true;
        """)
        check("sine_reload_reinstalls_one_control_and_route", source.js("""
          return window.ProfileSwitcher.version==="0.2.0" && window.ProfileSwitcher.status==="ready" &&
            document.querySelectorAll("#profile-switcher-row").length===1 &&
            window.erClass.prototype.__profileSwitcherExternalRouting?.version==="0.2.0";
        """))
        report["passed"] = True
    except Exception as error:
        report["passed"] = False
        report["error"] = str(error)
        raise
    finally:
        try:
            if verified:
                source.js("""
                  window.erRouter?.destroy();
                  if(window.erClass.prototype.handle===window.erRouter?.handle)
                    window.erClass.prototype.handle=window.erOriginal;
                  Services.prefs.setStringPref("uc.profile-switcher.external-profile","");
                  window.erModule.install();
                """)
        finally:
            args.report.write_text(json.dumps(report, indent=2) + "\n")
            source.close()
            target.close()
            server.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--other-profile", type=Path, required=True)
    parser.add_argument("--port", type=int, default=2842)
    parser.add_argument("--other-port", type=int, default=2843)
    parser.add_argument("--report", type=Path, required=True)
    run(parser.parse_args())
