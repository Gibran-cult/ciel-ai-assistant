"""Modul lokal dimuat ulang setelah file-nya berubah (deploy di Streamlit Cloud)."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import fresh_modules  # noqa: E402


class FreshModulesTest(unittest.TestCase):

    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.write("old_names = 1\n")
        sys.path.insert(0, str(self.folder))
        self.addCleanup(sys.path.remove, str(self.folder))
        self.addCleanup(sys.modules.pop, "ciel_fresh_probe", None)

    def write(self, text, bump=0):
        path = self.folder / "ciel_fresh_probe.py"
        path.write_text(text, encoding="utf-8")
        stamp = path.stat().st_mtime + bump
        os.utime(path, (stamp, stamp))

    def test_a_module_changed_after_import_is_dropped_once(self):
        # Live 2026-11-01 (PR #76): app.py arrived first, the rerun imported the
        # old payments.py, and "from payments import payment_window" failed
        # until the app was rebooted.
        self.assertEqual(fresh_modules.drop_stale_modules(self.folder), [])
        import ciel_fresh_probe
        self.assertEqual(fresh_modules.drop_stale_modules(self.folder), [])

        self.write("old_names = 1\nnew_name = 2\n", bump=10)
        self.assertEqual(fresh_modules.drop_stale_modules(self.folder), ["ciel_fresh_probe"])
        self.assertNotIn("ciel_fresh_probe", sys.modules)

        import ciel_fresh_probe as reloaded
        self.assertIsNot(reloaded, ciel_fresh_probe)
        self.assertEqual(reloaded.new_name, 2)
        self.assertEqual(fresh_modules.drop_stale_modules(self.folder), [])

    def test_modules_outside_the_folder_are_kept(self):
        fresh_modules.drop_stale_modules(self.folder)
        self.write("x = 1\n", bump=10)
        fresh_modules.drop_stale_modules(self.folder)
        self.assertIn("unittest", sys.modules)
        self.assertIn("fresh_modules", sys.modules)

    def test_app_checks_before_importing_its_own_modules(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertLess(source.index("drop_stale_modules("), source.index("from account_settings import"))


if __name__ == "__main__":
    unittest.main()
