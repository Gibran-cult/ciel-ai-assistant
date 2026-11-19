"""Setiap gambar dan huruf punya catatan asal dan lisensi (roadmap 0.14)."""

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "asset-licenses.md"
ASSET = re.compile(r"\.(png|jpe?g|svg|webp|gif|ico|woff2?|ttf|otf)$", re.IGNORECASE)
SKIP = {"node_modules", ".git", "dist", "dist-e2e", "out", ".next", ".superpowers", "test-results", "playwright-report",
        ".claude", ".impeccable", "__pycache__"}
FONTS = ("Fraunces", "Geist", "Geist Mono")


def tracked_files():
    """Berkas yang dilacak git; kalau git tidak ada, semua berkas di luar folder alat dan hasil build."""

    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        return [ROOT / line for line in out.splitlines() if line]
    except (OSError, subprocess.CalledProcessError):
        return [path for path in ROOT.rglob("*") if path.is_file() and not SKIP & set(path.relative_to(ROOT).parts)]


def asset_folders():
    """Folder (relatif ke repo) yang berisi gambar atau berkas huruf."""

    return {path.parent.relative_to(ROOT).as_posix() for path in tracked_files() if ASSET.search(path.name)}


class AssetLicensesTest(unittest.TestCase):
    def test_every_asset_folder_has_a_row(self):
        text = DOC.read_text(encoding="utf-8") if DOC.exists() else ""

        for folder in sorted(asset_folders()):
            with self.subTest(folder=folder):
                self.assertIn(f"`{folder}/", text)

    def test_every_font_has_a_row(self):
        text = DOC.read_text(encoding="utf-8") if DOC.exists() else ""

        for font in FONTS:
            with self.subTest(font=font):
                self.assertRegex(text, rf"(?m)^\| {re.escape(font)} \|")


if __name__ == "__main__":
    unittest.main()
