"""Exercise the local installer against disposable profiles, never a real browser."""

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


SPEC = importlib.util.spec_from_file_location(
    "install_collection", Path(__file__).resolve().parents[1] / "scripts" / "install.py"
)
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.profile = self.root / "Profile with spaces"
        self.mods = self.profile / "chrome" / "sine-mods"
        self.mods.mkdir(parents=True)
        self.registry = self.mods / "mods.json"
        self.initial = {"unrelated": {"id": "unrelated", "enabled": False, "custom": 7}}
        self.registry.write_text(json.dumps(self.initial), encoding="utf-8")
        (self.profile / "prefs.js").write_text("keep these preferences", encoding="utf-8")
        self.backup = self.root / "backup"
        patch = mock.patch.object(installer, "require_zen_closed")
        self.closed = patch.start()
        self.addCleanup(patch.stop)

    def run_install(self, selected=None, **kwargs):
        return installer.install(
            self.profile, self.backup,
            list(installer.MOD_FILES) if selected is None else selected, **kwargs,
        )

    def test_all_mods_include_actors_styles_and_preserve_other_configuration(self):
        result = self.run_install()
        self.assertEqual(result["status"], "installed")
        registry = json.loads(self.registry.read_text())
        self.assertEqual(registry["unrelated"], self.initial["unrelated"])
        for mod_id, filenames in installer.MOD_FILES.items():
            self.assertEqual(
                {p.name for p in (self.mods / mod_id).iterdir()}, set(filenames),
            )
            self.assertTrue(registry[mod_id]["enabled"])
            self.assertTrue(registry[mod_id]["no-updates"])
            self.assertNotIn("origin", registry[mod_id])
        self.assertEqual((self.profile / "prefs.js").read_text(), "keep these preferences")
        self.assertEqual(json.loads((self.backup / "mods.json").read_text()), self.initial)
        self.closed.assert_called()

    def test_update_backs_up_old_files_and_retains_disabled_state(self):
        old = self.mods / "auto-glance"
        old.mkdir()
        (old / "old-file.js").write_text("previous version")
        self.initial["auto-glance"] = {
            "id": "auto-glance", "enabled": False, "origin": "store", "custom": "keep",
        }
        self.registry.write_text(json.dumps(self.initial))
        self.run_install(["auto-glance"])
        self.assertEqual((self.backup / "mods" / "auto-glance" / "old-file.js").read_text(),
                         "previous version")
        self.assertFalse((old / "old-file.js").exists())
        entry = json.loads(self.registry.read_text())["auto-glance"]
        self.assertFalse(entry["enabled"])
        self.assertEqual(entry["custom"], "keep")
        self.assertNotIn("origin", entry)
        self.assertFalse((self.mods / "little-zen").exists())

    def test_registry_write_failure_restores_existing_and_removes_new_mods(self):
        old = self.mods / "auto-glance"
        old.mkdir()
        (old / "original.js").write_text("keep me")
        before = self.registry.read_bytes()
        with mock.patch.object(installer, "atomic_write", side_effect=OSError("write failure")):
            with self.assertRaisesRegex(OSError, "write failure"):
                self.run_install(["auto-glance", "little-zen"])
        self.assertEqual([p.name for p in old.iterdir()], ["original.js"])
        self.assertEqual((old / "original.js").read_text(), "keep me")
        self.assertFalse((self.mods / "little-zen").exists())
        self.assertEqual(self.registry.read_bytes(), before)
        self.assertEqual(json.loads((self.backup / "receipt.json").read_text())["status"], "prepared")

    def test_dry_run_does_not_write_or_require_browser_exit(self):
        before = self.registry.read_bytes()
        self.assertTrue(self.run_install(dry_run=True)["dryRun"])
        self.assertEqual(self.registry.read_bytes(), before)
        self.assertFalse(self.backup.exists())
        self.assertEqual([p.name for p in self.mods.iterdir()], ["mods.json"])
        self.closed.assert_not_called()

    def test_existing_backup_is_never_overwritten(self):
        self.backup.mkdir()
        (self.backup / "keep").write_text("existing")
        with self.assertRaises(FileExistsError):
            self.run_install()
        self.assertEqual((self.backup / "keep").read_text(), "existing")
        self.assertEqual(json.loads(self.registry.read_text()), self.initial)

    def test_changed_registry_aborts_before_replacing_mods(self):
        calls = 0

        def concurrent_edit():
            nonlocal calls
            calls += 1
            if calls == 2:
                self.registry.write_text('{"concurrent": {"enabled": true}}')

        self.closed.side_effect = concurrent_edit
        with self.assertRaisesRegex(RuntimeError, "changed during backup"):
            self.run_install()
        self.assertEqual(json.loads(self.registry.read_text()), {"concurrent": {"enabled": True}})
        self.assertFalse((self.mods / "little-zen").exists())

    def test_invalid_registry_and_missing_source_fail_before_writing(self):
        self.registry.write_text("[]")
        with self.assertRaisesRegex(ValueError, "JSON object"):
            self.run_install()
        self.assertFalse(self.backup.exists())
        self.registry.write_text(json.dumps(self.initial))
        with mock.patch.object(installer, "ROOT", self.root / "missing-source"):
            with self.assertRaises(FileNotFoundError):
                self.run_install()
        self.assertFalse(self.backup.exists())

    def test_backup_inside_profile_is_rejected(self):
        self.backup = self.profile / "backup"
        with self.assertRaisesRegex(ValueError, "outside"):
            self.run_install()
        self.assertFalse(self.backup.exists())


class ProcessTests(unittest.TestCase):
    def test_mac_and_windows_process_guards(self):
        samples = [
            ("Darwin", "/Applications/Zen.app/Contents/MacOS/zen\n", True),
            ("Darwin", "/usr/bin/python3\n", False),
            ("Windows", '"zen.exe","123","Console","1","50,000 K"\n', True),
            ("Windows", "INFO: No tasks are running which match the specified criteria.\n", False),
        ]
        for system, stdout, running in samples:
            with self.subTest(system=system, running=running):
                result = subprocess.CompletedProcess([], 0, stdout=stdout)
                with mock.patch.object(installer.platform, "system", return_value=system), \
                     mock.patch.object(installer.subprocess, "run", return_value=result):
                    if running:
                        with self.assertRaisesRegex(RuntimeError, "Quit all Zen"):
                            installer.require_zen_closed()
                    else:
                        installer.require_zen_closed()


if __name__ == "__main__":
    unittest.main()
