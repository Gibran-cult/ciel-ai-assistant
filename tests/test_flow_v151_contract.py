import copy
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FLOW_V150 = ROOT / "flow" / "v1.5.0" / "Ciel_AI_Long-Term_Memory_Master.json"
FLOW_V151 = ROOT / "flow" / "v1.5.1" / "Ciel_AI_Long-Term_Memory_Master.json"


def agent(flow):
    return next(n for n in flow["data"]["nodes"] if n["id"].startswith("Agent-"))


def prompt_of(flow):
    return agent(flow)["data"]["node"]["template"]["system_prompt"]["value"]


class FlowV151ContractTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = FLOW_V151.read_text(encoding="utf-8")
        cls.flow = json.loads(cls.raw)
        cls.base = json.loads(FLOW_V150.read_text(encoding="utf-8"))
        cls.prompt = prompt_of(cls.flow)

    def test_only_the_system_prompt_changes(self):
        new, old = copy.deepcopy(self.flow), copy.deepcopy(self.base)
        for flow in (new, old):
            agent(flow)["data"]["node"]["template"]["system_prompt"]["value"] = ""
        self.assertEqual(new, old)

    def test_prompt_only_adds_the_format_rules(self):
        self.assertTrue(self.prompt.startswith("CIEL AI MASTER — SYSTEM PROMPT v14.2"))
        old_lines = prompt_of(self.base).replace("v14.1", "v14.2").splitlines()
        new_lines = self.prompt.splitlines()

        # Every v1.5.0 line is still there, in the same order...
        position = 0
        for line in old_lines:
            position = new_lines.index(line, position) + 1

        # ...and the only additions are the four format rules.
        added = [line for line in new_lines if line not in old_lines]
        self.assertEqual(len(added), 4)
        self.assertTrue(all(line.startswith("- ") for line in added))

    def test_indonesian_number_format_rules(self):
        self.assertIn("Tulis angka dalam format Indonesia: titik sebagai pemisah ribuan, koma sebagai desimal", self.prompt)
        self.assertIn("23.685 berarti dua puluh tiga koma enam delapan lima", self.prompt)
        self.assertIn("Hasil Ciel Table Analyst sudah memakai format Indonesia.", self.prompt)
        self.assertIn("Jangan mencampur dua format dalam satu jawaban.", self.prompt)

    def test_no_invented_currency(self):
        self.assertIn("Jangan menambahkan mata uang (Rp, $, dan lainnya) atau satuan yang tidak disebut", self.prompt)

    def test_snapshot_contains_no_hardcoded_api_keys(self):
        self.assertIsNone(re.search(r"sk-[A-Za-z0-9_-]{16,}", self.raw))


if __name__ == "__main__":
    unittest.main()
