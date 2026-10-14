import copy
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FLOW_V130 = ROOT / "flow" / "v1.3.0" / "Ciel_AI_Long-Term_Memory_Master.json"
FLOW_V140 = ROOT / "flow" / "v1.4.0" / "Ciel_AI_Long-Term_Memory_Master.json"


def agent_node(flow):
    return next(n for n in flow["data"]["nodes"] if n["id"].startswith("Agent-"))


def system_prompt(flow):
    return agent_node(flow)["data"]["node"]["template"]["system_prompt"]["value"]


class FlowV140ContractTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = FLOW_V140.read_text(encoding="utf-8")
        cls.flow = json.loads(cls.raw)
        cls.base = json.loads(FLOW_V130.read_text(encoding="utf-8"))
        cls.prompt = system_prompt(cls.flow)

    def test_only_the_system_prompt_changes(self):
        # v1.4.0 = v1.3.0 + identitas Ciel; isolasi memory dan tools tidak boleh berubah.
        new = copy.deepcopy(self.flow)
        old = copy.deepcopy(self.base)
        agent_node(new)["data"]["node"]["template"]["system_prompt"]["value"] = ""
        agent_node(old)["data"]["node"]["template"]["system_prompt"]["value"] = ""
        self.assertEqual(new, old)

    def test_existing_rules_are_kept(self):
        base_prompt = system_prompt(self.base)
        for heading in (
            "1. LONG-TERM MEMORY",
            "2. ROUTING SPECIALIST",
            "3. INPUT GAMBAR / VISION",
            "4. CONTEXT ISOLATION / OUTPUT HYGIENE",
            "5. BAHASA DAN FORMAT",
        ):
            with self.subTest(heading=heading):
                self.assertIn(heading, base_prompt)
                self.assertIn(heading, self.prompt)
        self.assertIn("Jangan gunakan LaTeX.", self.prompt)
        self.assertIn("USER REQUEST > TOOL RESULT > INFERENCE", self.prompt)

    def test_identity_sections_present_in_order(self):
        headings = [
            "6. KEPRIBADIAN: DUA MODE",
            "7. ANTI-NGARANG (BERLAKU DI SEMUA MODE)",
            "8. TEMAN BELAJAR",
            "9. FINAL RESPONSE",
        ]
        positions = [self.prompt.index(h) for h in headings]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("6. FINAL RESPONSE", self.prompt)

    def test_persona_modes(self):
        self.assertIn("MODE SANTAI (DEFAULT)", self.prompt)
        self.assertIn("MODE ANALISIS (GAYA GREAT SAGE)", self.prompt)
        self.assertIn('Baris pertama selalu: "Analisis dimulai."', self.prompt)
        for label in ("Kesimpulan:", "Tingkat keyakinan:", "Batasan:", "[Terverifikasi]", "[Dugaan]"):
            self.assertIn(label, self.prompt)
        # Uji live pertama: 9 poin dan penutup gaya santai. Dua aturan ini menjaga mode tetap ringkas.
        self.assertIn("Bagian Dasar paling banyak 5 poin", self.prompt)
        self.assertIn("Akhiri tepat setelah baris Batasan.", self.prompt)

    def test_anti_fabrication_rules(self):
        self.assertIn("Jangan pernah mengarang sumber", self.prompt)
        self.assertIn("jangan membuat daftar pustaka", self.prompt)
        self.assertIn('"Sumber:"', self.prompt)

    def test_snapshot_contains_no_hardcoded_api_keys(self):
        self.assertIsNone(re.search(r"sk-[A-Za-z0-9_-]{16,}", self.raw))


if __name__ == "__main__":
    unittest.main()
