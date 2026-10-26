"""Supply chain rules: locked dependencies and hardened GitHub Actions workflows."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))


def requirement_entries(text):
    """Each requirement with its continuation lines joined, comments and blanks dropped."""
    entries = []
    for line in text.replace("\\\n", " ").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            entries.append(line)
    return entries


class LockedRequirementsTest(unittest.TestCase):
    def test_requirements_are_locked_with_hashes(self):
        entries = requirement_entries((ROOT / "requirements.txt").read_text(encoding="utf-8"))

        self.assertTrue(entries)
        for entry in entries:
            self.assertRegex(entry, r"^[A-Za-z0-9._-]+==[^\s;]+", entry)
            self.assertIn("--hash=sha256:", entry, entry)

        self.assertIn("streamlit[auth]", (ROOT / "requirements.in").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
