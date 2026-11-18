"""Flow v1.14.1 (prompt v15.1): v1.14.0 plus two lines that stop Ciel refusing PDF requests.

Live 2026-11-04 on v1.14.0: "selesaikan ... lalu buatkan pdfnya" got "maaf, aku belum
bisa membuat file PDF langsung". The prompt only said the button exists; it never said
Ciel can make a PDF, and the "belum bisa membuat ilustrasi" line sat right below.
"""

import copy
import json
import unittest
from pathlib import Path

from answer_blocks import Broken, parse_answer


ROOT = Path(__file__).resolve().parents[1]
FLOW_V1140 = ROOT / "flow" / "v1.14.0" / "Ciel_AI_Long-Term_Memory_Master.json"
FLOW_V1141 = ROOT / "flow" / "v1.14.1" / "Ciel_AI_Long-Term_Memory_Master.json"
AGENT_ID = "Agent-puarO"

CAN_PDF = ("- Ciel BISA membuat PDF: aplikasi mengubah jawabanmu menjadi file PDF lewat tombol "
           "Unduh PDF di bawahnya. Jangan pernah bilang tidak bisa membuat PDF, dan jangan "
           "menyuruh pengguna menyalin ke Word atau Google Docs.")
SAME_MESSAGE = ("- Jika permintaan PDF datang bersama soal atau pertanyaan dalam pesan yang sama, "
                "langsung jawab dalam bentuk dokumen itu (diawali judul #). Jangan menunda atau "
                "bertanya dulu.")


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


class FlowV1141ContractTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.flow = json.loads(FLOW_V1141.read_text(encoding="utf-8"))
        cls.base = json.loads(FLOW_V1140.read_text(encoding="utf-8"))
        cls.prompt = prompt_of(cls.flow)
        cls.old = prompt_of(cls.base)

    def test_only_the_system_prompt_changes(self):
        self.assertEqual(blank_prompt(self.flow), blank_prompt(self.base))

    def test_header_is_v15_1(self):
        first = self.prompt.splitlines()[0]
        self.assertIn("v15.1", first)
        self.assertNotIn("v15.0", self.prompt)

    def test_pdf_lines_sit_first_in_the_pdf_block(self):
        block = self.prompt.index("PDF dan gambar:")
        self.assertEqual(self.prompt.count(CAN_PDF), 1)
        self.assertEqual(self.prompt.count(SAME_MESSAGE), 1)
        self.assertGreater(self.prompt.index("11. TAMPILAN JAWABAN"), 0)
        self.assertLess(block, self.prompt.index(CAN_PDF))
        self.assertLess(self.prompt.index(CAN_PDF), self.prompt.index(SAME_MESSAGE))
        self.assertLess(self.prompt.index(SAME_MESSAGE), self.prompt.index("- Jika pengguna minta PDF, lembar soal"))

    def test_nothing_else_in_the_prompt_changes(self):
        stripped = self.prompt.replace(CAN_PDF + "\n", "").replace(SAME_MESSAGE + "\n", "")
        self.assertEqual(stripped.replace("v15.1", "v15.0"), self.old)

    def test_illustration_limit_is_still_stated(self):
        self.assertIn("belum bisa membuat ilustrasi atau mengedit foto", self.prompt)

    def test_prompt_examples_still_parse(self):
        start = self.prompt.index("11. TAMPILAN JAWABAN")
        parts = parse_answer(self.prompt[start:])
        self.assertFalse([p for p in parts if isinstance(p, Broken)])


if __name__ == "__main__":
    unittest.main()
