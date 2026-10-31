"""Install Little Zen locally. Quit Zen before running this script."""

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

SOURCE = Path(__file__).resolve().parents[1]
MOD_FILES = ["theme.json", "preferences.json", "little-zen.uc.js", "chrome.css", "README.md"]
LUA_BLOCK = """
-- BEGIN Little Zen
if littleZen and littleZen.stop then littleZen.stop() end
littleZen = require("little-zen")
-- END Little Zen
"""


def require_browser_closed(profile):
    processes = subprocess.run(
        ["ps", "-axo", "pid=,command="], capture_output=True, text=True, check=True
    ).stdout.splitlines()
    for process in processes:
        fields = process.strip().split(None, 1)
        if len(fields) != 2:
            continue
        command = fields[1]
        if command.startswith("/Applications/Zen.app/Contents/MacOS/zen"):
            if "-profile" not in command or str(profile) in command:
                raise RuntimeError("Quit the Zen instance using this profile before installation.")


def atomic_text(path, text):
    temporary = path.with_name(path.name + ".little-zen.tmp")
    if temporary.exists():
        raise RuntimeError(f"Unexpected temporary file: {temporary}")
    temporary.write_text(text)
    temporary.chmod(path.stat().st_mode & 0o777 if path.exists() else 0o600)
    temporary.replace(path)


def main(args):
    profile = args.profile.expanduser().resolve()
    require_browser_closed(profile)
    mods = profile / "chrome/sine-mods"
    registry = mods / "mods.json"
    destination = mods / "little-zen"
    if not registry.is_file():
        raise RuntimeError("Sine must already be installed in the selected profile.")
    if destination.exists():
        raise RuntimeError("An existing little-zen mod was found. Preserve it before updating.")
    for name in MOD_FILES:
        if not (SOURCE / name).is_file():
            raise RuntimeError(f"Missing source file: {name}")
    original = registry.read_text()
    metadata = json.loads(original)
    if "little-zen" in metadata:
        raise RuntimeError("An existing Little Zen registration was found.")

    lua_directory = args.hammerspoon.expanduser().resolve() if args.hammerspoon else None
    lua_init = lua_directory / "init.lua" if lua_directory else None
    lua_module = lua_directory / "little-zen.lua" if lua_directory else None
    old_init = lua_init.read_text() if lua_init and lua_init.exists() else ""
    if lua_directory and (lua_module.exists() or "-- BEGIN Little Zen" in old_init):
        raise RuntimeError("An existing Little Zen Hammerspoon integration was found.")

    backup = args.backup.expanduser().resolve()
    before = backup / "before"
    before.mkdir(parents=True, exist_ok=True)
    backup.chmod(0o700)
    backed_up = []
    for relative in [
        "chrome", "prefs.js", "user.js", "containers.json", "xulstore.json",
        "sessionstore.jsonlz4", "sessionstore-backups", "zen-sessions.json",
        "zen-sessions.jsonlz4", "zen-sessions-backup", "sessionCheckpoints.json",
        "zen-keyboard-shortcuts.json", "search.json.mozlz4", "zen-themes.json",
    ]:
        source = profile / relative
        if not source.exists():
            continue
        target = before / "Zen-profile" / relative
        if target.exists():
            raise RuntimeError(f"Backup target already exists: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
        backed_up.append(relative)
    if lua_init and lua_init.exists():
        target = before / "hammerspoon-init.lua"
        if target.exists():
            raise RuntimeError("Hammerspoon backup already exists.")
        shutil.copy2(lua_init, target)
    # Recheck the exact inputs immediately before committing the narrow merge.
    if registry.read_text() != original:
        raise RuntimeError("The Sine registry changed during backup; installation was not applied.")
    if lua_init and lua_init.exists() and lua_init.read_text() != old_init:
        raise RuntimeError("Hammerspoon changed during backup; installation was not applied.")

    destination.mkdir()
    for name in MOD_FILES:
        shutil.copy2(SOURCE / name, destination / name)
    mod = json.loads((SOURCE / "theme.json").read_text())
    mod.update({"enabled": True, "no-updates": True})
    metadata[mod["id"]] = mod
    atomic_text(registry, json.dumps(metadata, indent=2) + "\n")
    if lua_directory:
        lua_directory.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE / "hammerspoon/little-zen.lua", lua_module)
        atomic_text(lua_init, old_init.rstrip() + "\n" + LUA_BLOCK)

    receipt = {
        "installedAt": datetime.now().astimezone().isoformat(),
        "profile": str(profile), "backup": str(backup), "source": str(SOURCE),
        "hammerspoon": str(lua_directory) if lua_directory else None,
        "backedUp": backed_up, "previousModIds": list(json.loads(original)),
        "sha256": {name: hashlib.sha256((destination/name).read_bytes()).hexdigest() for name in MOD_FILES},
    }
    (backup / "installation.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--hammerspoon", type=Path)
    main(parser.parse_args())
