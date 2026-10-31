"""Remove Little Zen only, preserving later browser and Hammerspoon changes."""

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess

from install import atomic_text, require_browser_closed


def main(args):
    profile = args.profile.expanduser().resolve()
    require_browser_closed(profile)
    mods = profile / "chrome/sine-mods"
    registry = mods / "mods.json"
    metadata = json.loads(registry.read_text())
    if "little-zen" not in metadata:
        raise RuntimeError("Little Zen is not registered in this profile.")
    backup = args.backup.expanduser().resolve()
    backup.mkdir(parents=True, exist_ok=False)
    backup.chmod(0o700)
    shutil.copy2(registry, backup / "mods.json")
    del metadata["little-zen"]
    atomic_text(registry, json.dumps(metadata, indent=2) + "\n")
    directory = mods / "little-zen"
    if directory.exists():
        shutil.move(str(directory), str(backup / "little-zen"))
    if args.hammerspoon:
        lua = args.hammerspoon.expanduser().resolve()
        init = lua / "init.lua"
        if init.exists():
            old = init.read_text()
            new, count = re.subn(
                r"\n?-- BEGIN Little Zen\n.*?\n-- END Little Zen\n?", "\n", old, flags=re.S
            )
            if count:
                shutil.copy2(init, backup / "hammerspoon-init.lua")
                atomic_text(init, new)
        module = lua / "little-zen.lua"
        if module.exists():
            shutil.move(str(module), str(backup / "little-zen.lua"))
        hs = shutil.which("hs")
        if hs:
            subprocess.run([
                hs, "-c",
                'if littleZen and littleZen.stop then littleZen.stop() end; '
                'littleZen=nil; package.loaded["little-zen"]=nil',
            ], check=False)
    print(f"Little Zen removed. Preserved files: {backup}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("--backup", type=Path, required=True, help="A new folder for removed files")
    parser.add_argument("--hammerspoon", type=Path)
    main(parser.parse_args())
