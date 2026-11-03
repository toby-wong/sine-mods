#!/usr/bin/env python3
"""Install this collection's browser mods into an existing, closed Sine profile."""

import argparse
import csv
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
COMMON = ("theme.json", "preferences.json", "README.md")
MOD_FILES = {
    "little-zen": COMMON + ("little-zen.uc.js", "chrome.css"),
    "auto-glance": COMMON + (
        "auto-glance.uc.js", "auto-glance.css", "AutoGlanceClickChild.sys.mjs",
    ),
    "tree-tabs-prototype": COMMON + ("tree-tabs.uc.js", "tree-tabs.css"),
    "alt-click-split-view": COMMON + (
        "alt-click-split-view.uc.js", "settings.uc.js",
        "AltClickSplitViewChild.sys.mjs", "LICENSE",
    ),
    "keyword-tab-search": COMMON + ("keyword-tab-search.uc.js",),
    "findbar-pane-fix": COMMON + ("findbar.css", "findbar-zoom.uc.js"),
    "ctrl-tab-theme": COMMON + ("ctrl-tab.css",),
}


def require_zen_closed():
    """Use the native process listing; never terminate a user's browser."""
    if platform.system() == "Windows":
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq zen.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, check=True,
        )
        running = any(
            row and row[0].lower() == "zen.exe"
            for row in csv.reader(io.StringIO(result.stdout))
        )
    else:
        result = subprocess.run(
            ["ps", "-axo", "comm="], capture_output=True, text=True, check=True,
        )
        running = any(
            Path(line.strip()).name.lower() in {"zen", "zen-bin", "zen.exe"}
            for line in result.stdout.splitlines()
        )
    if running:
        raise RuntimeError("Quit all Zen processes before installing. No changes applied.")


def atomic_write(path, contents):
    descriptor, temporary = tempfile.mkstemp(prefix=".sine-mods-", dir=path.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(contents)
        if path.exists():
            shutil.copymode(path, temporary)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def install(profile, backup, selected, dry_run=False):
    profile = Path(profile).expanduser().resolve()
    backup = Path(backup).expanduser().resolve()
    selected = list(dict.fromkeys(selected))
    if not selected or any(mod_id not in MOD_FILES for mod_id in selected):
        raise ValueError("Select at least one supported Sine mod.")
    if backup.is_relative_to(profile) or backup.is_relative_to(ROOT):
        raise ValueError("Choose a new backup directory outside the profile and checkout.")
    mods = profile / "chrome" / "sine-mods"
    registry = mods / "mods.json"
    if not registry.is_file() or registry.is_symlink():
        raise RuntimeError("Choose an existing profile with Sine installed (mods.json required).")
    original = registry.read_bytes()
    metadata = json.loads(original)
    if not isinstance(metadata, dict):
        raise ValueError("The Sine registry must be a JSON object.")
    existed = {}
    for mod_id in selected:
        source = ROOT / mod_id
        for filename in MOD_FILES[mod_id]:
            if not (source / filename).is_file():
                raise FileNotFoundError(f"Missing source file: {source / filename}")
        theme = json.loads((source / "theme.json").read_text(encoding="utf-8"))
        if theme.get("id") != mod_id:
            raise ValueError(f"Manifest ID does not match directory: {mod_id}")
        previous = metadata.get(mod_id, {})
        if not isinstance(previous, dict):
            raise ValueError(f"Invalid registry entry: {mod_id}")
        destination = mods / mod_id
        if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
            raise ValueError(f"Expected a regular mod directory: {destination}")
        existed[mod_id] = destination.exists()
        entry = {**previous, **theme, "enabled": previous.get("enabled", True), "no-updates": True}
        entry.pop("origin", None)  # A local copy must not claim marketplace verification.
        metadata[mod_id] = entry
    plan = {
        "profile": str(profile), "backup": str(backup),
        "mods": selected, "previouslyInstalled": existed, "dryRun": dry_run,
    }
    if backup.exists():
        raise FileExistsError(f"Use a new backup directory: {backup}")
    if dry_run:
        return plan
    require_zen_closed()
    backup.mkdir(parents=True, mode=0o700)
    (backup / "mods.json").write_bytes(original)
    for mod_id in selected:
        if existed[mod_id]:
            shutil.copytree(mods / mod_id, backup / "mods" / mod_id, symlinks=True)
    receipt = {
        **plan, "createdAt": datetime.now(timezone.utc).isoformat(), "status": "prepared",
    }
    receipt_path = backup / "receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    require_zen_closed()
    if registry.read_bytes() != original:
        raise RuntimeError("Sine's registry changed during backup; no installation applied.")
    with tempfile.TemporaryDirectory(prefix=".sine-mods-stage-", dir=mods) as stage_name:
        stage = Path(stage_name)
        for mod_id in selected:
            staged = stage / mod_id
            staged.mkdir()
            for filename in MOD_FILES[mod_id]:
                shutil.copy2(ROOT / mod_id / filename, staged / filename)
        saved = stage / "previous"
        saved.mkdir()
        touched = []
        registry_changed = False
        try:
            for mod_id in selected:
                destination = mods / mod_id
                previous = saved / mod_id if existed[mod_id] else None
                if previous:
                    destination.rename(previous)
                touched.append((mod_id, previous))
                (stage / mod_id).rename(destination)
            atomic_write(registry, (json.dumps(metadata, indent=2) + "\n").encode("utf-8"))
            registry_changed = True
            receipt["status"] = "installed"
            receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        except Exception:
            for mod_id, previous in reversed(touched):
                destination = mods / mod_id
                if destination.exists():
                    shutil.rmtree(destination)
                if previous:
                    previous.rename(destination)
            if registry_changed:
                atomic_write(registry, original)
            raise
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True, help="Path shown in about:support")
    parser.add_argument("--backup", type=Path, required=True, help="New directory outside the profile/checkout")
    parser.add_argument("--mods", nargs="+", choices=MOD_FILES, default=list(MOD_FILES))
    parser.add_argument("--dry-run", action="store_true", help="Show the plan without changing files")
    args = parser.parse_args()
    try:
        receipt = install(args.profile, args.backup, args.mods, args.dry_run)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Installation stopped: {error}\n")
    print(json.dumps(receipt, indent=2))
    if not args.dry_run:
        print("Installation complete. Restart Zen and check Settings > Sine.")


if __name__ == "__main__":
    main()
