"""Check that folder and pin transitions do not wake a sleeping tree child."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time

from runtime import Marionette


def run(args):
    requests = []
    report = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Sleeping branch test")

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    m = Marionette(args.port)
    authorized = False
    try:
        actual = m.js('return Services.dirsvc.get("ProfD",Ci.nsIFile).path;')
        assert Path(actual).resolve() == args.profile.resolve()
        assert (args.profile / "folder-tree-test-profile").is_file()
        authorized = True
        m.js("""
          MultiTabMove.clear();
          window.slp={selected:gBrowser.selectedTab};
          slp.root=gBrowser.addTrustedTab("about:blank",{inBackground:true});
          slp.child=gBrowser.addTrustedTab(arguments[0],{createLazyBrowser:true,inBackground:true});
          // Raw lazy-tab creation omits the Space metadata that restored tabs carry.
          slp.child.setAttribute("zen-workspace-id",gZenWorkspaces.activeWorkspace);
          if(!TreeTabs.nest(slp.child,slp.root))throw new Error("Fixture could not form a tree");
        """, [f"http://127.0.0.1:{server.server_port}/sleeping"])
        for name, script in [
            ("native_folder", 'slp.folder=gZenFolders.createFolder([slp.root],{label:"Sleeping tree",renameFolder:false});'),
            ("native_unpin", "gBrowser.unpinTab(slp.root);"),
            ("selection_into_folder", "MultiTabMove.toggle(slp.root);MultiTabMove.move({workspace:gZenWorkspaces.activeWorkspace,folder:slp.folder});"),
            ("selection_out_of_folder", "MultiTabMove.move({workspace:gZenWorkspaces.activeWorkspace,pinned:false});"),
        ]:
            m.js(script)
            time.sleep(.35)
            state = m.js("""return {
              pending:slp.child.hasAttribute("pending"),
              parent:TreeTabs.parentOf(slp.child)===slp.root,
              focus:gBrowser.selectedTab===slp.selected,
            };""")
            state["requests"] = len(requests)
            report[name] = state
            assert all(state[k] for k in ["pending", "parent", "focus"]) and not requests, state
            print("PASS", name)
    finally:
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        if authorized:
            m.async_js("""
              MultiTabMove.clear();
              for(const tab of [window.slp?.child,window.slp?.root])
                if(tab?.isConnected)gBrowser.removeTab(tab,{animate:false,skipPermitUnload:true});
              if(window.slp?.folder?.isConnected)await slp.folder.delete();
            """)
        m.close()
        server.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--port", type=int, default=2832)
    parser.add_argument("--report", type=Path, required=True)
    run(parser.parse_args())
