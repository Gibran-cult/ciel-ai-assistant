"""Flow v1.14.2 (prompt v15.2): v1.14.1 with the "belum bisa membuat ilustrasi" line replaced.

Plan 2 adds Edit gambar (free manual edits, Pro "Minta AI") and Ilustrasi (Pro) on Beranda.
The prompt now points to those tools and still says Ciel cannot remove backgrounds or change
what is in a photo. Ship this flow only after the app with the tools is live.
"""

import copy
import json
import unittest
from pathlib import Path

from answer_blocks import Broken, parse_answer


ROOT = Path(__file__).resolve().parents[1]
FLOW_V1141 = ROOT / "flow" / "v1.14.1" / "Ciel_AI_Long-Term_Memory_Master.json"
FLOW_V1142 = ROOT / "flow" / "v1.14.2" / "Ciel_AI_Long-Term_Memory_Master.json"
AGENT_ID = "Agent-puarO"

OLD_LINE = "- Ciel belum bisa membuat ilustrasi atau mengedit foto. Katakan itu dengan jujur jika diminta."
EDIT_TOOL = ("- Untuk mengedit foto (potong, putar, rapikan foto catatan, beri label, blur), arahkan "
             "pengguna ke tombol Edit gambar di Beranda. Pengguna Pro bisa meminta AI di sana. Ciel "
             "tidak bisa menghapus latar atau mengubah isi foto.")
ILLUSTRATION_TOOL = ("- Untuk ilustrasi, arahkan pengguna Pro ke Ilustrasi di Beranda: hasilnya diagram "
                     "berlabel, bukan foto atau lukisan. Di dalam jawaban tetap pakai ciel-grafik untuk grafik.")


def prompt_of(flow):
    for node in flow["data"]["nodes"]:
        if node["id"] == AGENT_ID:
            return node["data"]["node"]["template"]["system_prompt"]["value"]
    raise AssertionError("Agent node missing")


def blank_prompt(flow):
    flow = copy.deepcopy(flow)
    for node in flow["data"]["nodes"]:
        if node["id"] == AGENT_ID:
            node["data"]["node"]["template"]["system_prompt"]["value"] = ""
    return flow


class FlowV1142ContractTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = FLOW_V1142.read_bytes()
        cls.flow = json.loads(cls.raw)
        cls.base = json.loads(FLOW_V1141.read_text(encoding="utf-8"))
        cls.prompt = prompt_of(cls.flow)
        cls.old = prompt_of(cls.base)

    def test_only_the_system_prompt_changes(self):
        self.assertEqual(blank_prompt(self.flow), blank_prompt(self.base))

    def test_header_is_v15_2(self):
        first = self.prompt.splitlines()[0]
        self.assertIn("v15.2", first)
        self.assertNotIn("v15.1", self.prompt)

    def test_tool_lines_replace_the_old_line_inside_the_pdf_block(self):
        self.assertNotIn("belum bisa membuat ilustrasi", self.prompt)
        self.assertEqual(self.prompt.count(EDIT_TOOL), 1)
        self.assertEqual(self.prompt.count(ILLUSTRATION_TOOL), 1)
        block = self.prompt.index("PDF dan gambar:")
        # The "PDF dan gambar:" block closes the prompt.
        end = self.prompt.find("\n\n", block) if "\n\n" in self.prompt[block:] else len(self.prompt)
        self.assertLess(block, self.prompt.index(EDIT_TOOL))
        self.assertLess(self.prompt.index(EDIT_TOOL), self.prompt.index(ILLUSTRATION_TOOL))
        self.assertLess(self.prompt.index(ILLUSTRATION_TOOL), end)

    def test_nothing_else_in_the_prompt_changes(self):
        restored = self.prompt.replace(EDIT_TOOL + "\n" + ILLUSTRATION_TOOL, OLD_LINE).replace("v15.2", "v15.1")
        self.assertEqual(restored, self.old)

    def test_no_claim_of_painting_or_background_removal(self):
        self.assertIn("tidak bisa menghapus latar atau mengubah isi foto", self.prompt)
        self.assertIn("bukan foto atau lukisan", self.prompt)

    def test_prompt_examples_still_parse(self):
        start = self.prompt.index("11. TAMPILAN JAWABAN")
        parts = parse_answer(self.prompt[start:])
        self.assertFalse([p for p in parts if isinstance(p, Broken)])

    def test_snapshot_serialization_matches_v1141(self):
        self.assertNotIn(b"\r", self.raw)
        self.assertFalse(self.raw.endswith(b"\n"))
        self.assertEqual(json.dumps(self.flow, indent=2, ensure_ascii=False).encode("utf-8"), self.raw)


if __name__ == "__main__":
    unittest.main()
