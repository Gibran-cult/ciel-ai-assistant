import copy
import hashlib
import json
import re
import unittest
from pathlib import Path

from answer_blocks import VISUAL_KINDS, Broken, Quiz, Visual, parse_answer


ROOT = Path(__file__).resolve().parents[1]
FLOW_V1130 = ROOT / "flow" / "v1.13.0" / "Ciel_AI_Long-Term_Memory_Master.json"
FLOW_V1140 = ROOT / "flow" / "v1.14.0" / "Ciel_AI_Long-Term_Memory_Master.json"
COMPONENTS = ROOT / "flow" / "components"

AGENT_ID = "Agent-puarO"
FALLBACK_ID = "CielFallbackModel-fb1k0"
GUARD_ID = "CielSourceGuard-m41n0"
EMBEDDED = {FALLBACK_ID: "ciel_fallback_model.py", GUARD_ID: "ciel_source_guard.py"}


def nodes(flow):
    return {n["id"]: n for n in flow["data"]["nodes"]}


def template(flow, node_id):
    return nodes(flow)[node_id]["data"]["node"]["template"]


def prompt_of(flow):
    return template(flow, AGENT_ID)["system_prompt"]["value"]


class FlowV1140ContractTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.flow = json.loads(FLOW_V1140.read_text(encoding="utf-8"))
        cls.base = json.loads(FLOW_V1130.read_text(encoding="utf-8"))
        cls.prompt = prompt_of(cls.flow)

    def test_only_the_system_prompt_changes(self):
        def blank(flow):
            flow = copy.deepcopy(flow)
            template(flow, AGENT_ID)["system_prompt"]["value"] = None
            return flow

        self.assertNotEqual(prompt_of(self.flow), prompt_of(self.base))
        self.assertEqual(blank(self.flow), blank(self.base))

    def test_latex_ban_is_lifted_with_guardrails(self):
        self.assertNotIn("Jangan gunakan LaTeX.", self.prompt)
        self.assertNotIn("Untuk matematika gunakan teks matematika biasa.", self.prompt)
        self.assertIn("Jangan pakai $ untuk mata uang", self.prompt)
        # Single backslashes and real newlines survive the JSON round trip.
        self.assertIn("$2,5 \\times 4 = 10$", self.prompt)
        self.assertNotIn("\\\\times", self.prompt)

    def test_section_11_is_last_and_names_every_kind(self):
        self.assertGreater(self.prompt.index("11. TAMPILAN JAWABAN"), self.prompt.index("10. KEAMANAN"))
        self.assertEqual(self.prompt.count("11. TAMPILAN JAWABAN"), 1)
        self.assertIn("- Blok ciel-grafik dan ciel-kuis bukan gambar markdown", self.prompt)
        tail = self.prompt[self.prompt.index("11. TAMPILAN JAWABAN"):]
        self.assertNotIn("\n10. ", tail)
        for kind in VISUAL_KINDS:
            with self.subTest(kind=kind):
                self.assertIn(f'"jenis": "{kind}"', self.prompt)

    def test_prompt_examples_parse(self):
        section = self.prompt[self.prompt.index("11. TAMPILAN JAWABAN"):]
        fences = re.findall(r"```(ciel-grafik|ciel-kuis)\n(.*?)\n```", section, re.S)
        self.assertGreaterEqual(len(fences), 2)
        samples = [(lang, body) for lang, body in fences]
        other = section[section.index("Jenis lain:"):]
        for line in re.findall(r"^- (\{.*\})$", other.split("Rumus memakai")[0], re.M):
            samples.append(("ciel-grafik", line))
        self.assertEqual(len(samples), len(fences) + 5)
        for lang, body in samples:
            with self.subTest(body=body[:50]):
                parts = parse_answer(f"```{lang}\n{body}\n```")
                self.assertEqual(len(parts), 1)
                self.assertNotIsInstance(parts[0], Broken)
                self.assertIsInstance(parts[0], Quiz if lang == "ciel-kuis" else Visual)

    def test_consistency_rules_live_in_section_11(self):
        start = self.prompt.index("11. TAMPILAN JAWABAN")
        for sentence in (
            "Dalam mode analisis (bagian 6B), format 6B tetap dipakai apa adanya",
            'Kuis "Coba sendiri" menggantikan pertanyaan cek pemahaman di bagian 8.',
            "Angka di dalam JSON ditulis sebagai angka JSON biasa dengan titik desimal (2.5)",
            'Di dalam JSON, tulis backslash LaTeX dua kali: "$\\\\frac{1}{2}$".',
        ):
            with self.subTest(sentence=sentence[:40]):
                self.assertEqual(self.prompt.count(sentence), 1)
                self.assertGreater(self.prompt.index(sentence), start)
        banner = "=" * 64
        self.assertIn(banner + "\n11. TAMPILAN JAWABAN\n" + banner + "\n", self.prompt)

    def test_version_and_old_math_rules(self):
        self.assertIn("v15.0", self.prompt.split("\n", 1)[0])
        self.assertNotIn("v14.8", self.prompt)
        self.assertNotIn("- Jangan gunakan $, $$", self.prompt)

    def test_no_illustration_promise(self):
        self.assertIn("belum bisa membuat ilustrasi atau mengedit foto", self.prompt)

    def test_embedded_components_match_sources(self):
        for node_id, filename in EMBEDDED.items():
            with self.subTest(node=node_id):
                code = template(self.flow, node_id)["code"]["value"]
                self.assertEqual(code.splitlines(), (COMPONENTS / filename).read_text(encoding="utf-8").splitlines())
        guard = nodes(self.flow)[GUARD_ID]["data"]["node"]
        self.assertEqual(guard["metadata"]["code_hash"], hashlib.sha256(guard["template"]["code"]["value"].encode()).hexdigest()[:12])


if __name__ == "__main__":
    unittest.main()
