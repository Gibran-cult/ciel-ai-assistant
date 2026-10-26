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


def steps(text):
    """Workflow step blocks: each starts at a '- ' list item under 'steps:'."""
    return re.split(r"\n(?=\s*- (?:name|uses|run|id):)", text)


class WorkflowRulesTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(WORKFLOWS)
        self.texts = {path.name: path.read_text(encoding="utf-8") for path in WORKFLOWS}

    def test_actions_are_pinned_to_commit_shas(self):
        for name, text in self.texts.items():
            for action in re.findall(r"uses:\s*(\S+)", text):
                self.assertRegex(action, r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$", f"{name}: {action}")

    def test_checkouts_do_not_persist_credentials(self):
        for name, text in self.texts.items():
            for step in steps(text):
                if "actions/checkout@" in step:
                    self.assertRegex(step, r"persist-credentials:\s*false", name)

    def test_run_steps_do_not_interpolate_event_data(self):
        for name, text in self.texts.items():
            self.assertNotRegex(text, r"\$\{\{\s*github\.(event\.|head_ref)", name)

    def test_workflows_declare_permissions(self):
        for name, text in self.texts.items():
            self.assertRegex(text, r"(?m)^permissions:", name)
            self.assertNotIn("write-all", text, name)
            self.assertNotIn("pull_request_target", text, name)


if __name__ == "__main__":
    unittest.main()
