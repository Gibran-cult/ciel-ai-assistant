import copy
import hashlib
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FLOW_V170 = ROOT / "flow" / "v1.7.0" / "Ciel_AI_Long-Term_Memory_Master.json"
FLOW_V180 = ROOT / "flow" / "v1.8.0" / "Ciel_AI_Long-Term_Memory_Master.json"
RESEARCH_SUBFLOW = ROOT / "flow" / "subflows" / "Web_Research_Assistant.json"
COMPONENTS = ROOT / "flow" / "components"
GUARDED = {"CielExaSearch": "ciel_exa_search.py", "CielSourceGuard": "ciel_source_guard.py"}


def agent(flow):
    return next(n for n in flow["data"]["nodes"] if n["id"].startswith("Agent-"))


def prompt_of(flow):
    return agent(flow)["data"]["node"]["template"]["system_prompt"]["value"]


class FlowV180ContractTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = FLOW_V180.read_text(encoding="utf-8")
        cls.flow = json.loads(cls.raw)
        cls.base = json.loads(FLOW_V170.read_text(encoding="utf-8"))
        cls.prompt = prompt_of(cls.flow)

    def test_only_the_prompt_changes_from_v170(self):
        def strip(flow):
            flow = copy.deepcopy(flow)
            agent(flow)["data"]["node"]["template"]["system_prompt"]["value"] = ""
            return flow

        self.assertEqual(strip(self.flow), strip(self.base))

    def test_prompt_keeps_every_v170_line_in_order(self):
        self.assertTrue(self.prompt.startswith("CIEL AI MASTER — SYSTEM PROMPT v14.5"))
        old = prompt_of(self.base).replace("v14.4", "v14.5").splitlines()
        new = self.prompt.splitlines()
        position = 0
        for line in old:
            position = new.index(line, position) + 1

    def test_prompt_picks_a_research_mode(self):
        # Live data (2026-10-17): research answers took 100-160 s because the
        # Research Agent searched 7-9 rounds and wrote a ~20k-character report.
        research = self.prompt[self.prompt.index("D. RESEARCH"):self.prompt.index("E. MULTI-SPECIALIST")]
        self.assertIn("- [RISET CEPAT] untuk semua riset di Mode Santai (default).", research)
        self.assertIn("- [RISET DALAM] hanya jika sedang di Mode Analisis (Gaya Great Sage).", research)
        self.assertIn("Panggil Research Agent sekali per pertanyaan.", research)
        self.assertIn('lalu tutup dengan bagian "Sumber:"', research)
        self.assertIn("Di Mode Santai, jawaban riset cukup inti saja", research)
        self.assertLess(research.index("Kirim pertanyaan lengkap pengguna"), research.index("[RISET CEPAT]"))

    def test_snapshot_contains_no_hardcoded_api_keys(self):
        self.assertIsNone(re.search(r"sk-[A-Za-z0-9_-]{16,}", self.raw))


class ResearchSubflowContractTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = RESEARCH_SUBFLOW.read_text(encoding="utf-8")
        cls.flow = json.loads(cls.raw)
        cls.nodes = {n["id"].split("-")[0]: n["data"]["node"]["template"] for n in cls.flow["data"]["nodes"]}
        cls.prompt = cls.nodes["Agent"]["system_prompt"]["value"]

    def test_research_agent_follows_both_modes(self):
        self.assertIn("[RISET CEPAT] atau tanpa penanda: lakukan tepat SATU putaran pencarian", self.prompt)
        self.assertIn("[RISET DALAM]: paling banyak 3 putaran pencarian", self.prompt)
        # Live run: get_contents returned ~25k characters and a separate
        # get_current_date round cost an extra model call.
        self.assertIn("Di kedua mode: Jangan memanggil get_contents.", self.prompt)
        self.assertIn("panggil get_current_date bersamaan dengan search di putaran yang sama", self.prompt)
        self.assertIn("RISET CEPAT: paling banyak 5 temuan, masing-masing satu kalimat, dan paling banyak 4 sumber", self.prompt)
        self.assertIn("RISET DALAM: paling banyak 10 temuan", self.prompt)

    def test_research_agent_keeps_anti_ngarang_rules(self):
        self.assertIn("Jangan mengarang fakta yang tidak didukung hasil tool.", self.prompt)
        self.assertIn("Selalu pisahkan FAKTA dari INTERPRETASI.", self.prompt)
        self.assertIn("Jika sumber saling bertentangan, laporkan konflik tersebut.", self.prompt)
        self.assertIn('Jangan menyebut suatu informasi sebagai "terbaru" tanpa memeriksa tanggal sumber.', self.prompt)

    def test_hard_limits_on_rounds_and_results(self):
        self.assertEqual(self.nodes["Agent"]["max_iterations"]["value"], 6)
        exa = self.nodes["CielExaSearch"]
        # With 3 results the agent sometimes padded its sources from memory.
        self.assertEqual(exa["search_num_results"]["value"], 5)
        # 0 means unlimited highlights: one search returned up to 37k characters.
        self.assertEqual(exa["highlights_max_characters"]["value"], 1500)

    def test_sources_come_only_from_search_results(self):
        # Live test (2026-10-17): after one search the notes cited hai.stanford.edu
        # URLs and numbers that no search had returned.
        self.assertIn("lakukan tepat SATU putaran pencarian berisi 2 query search berbeda", self.prompt)
        self.assertIn("SUMBER HANYA DARI HASIL SEARCH: setiap sumber dan URL wajib muncul di hasil search", self.prompt)
        self.assertIn("Jangan menambah sumber dari ingatan, walaupun daftarnya jadi lebih pendek.", self.prompt)
        self.assertIn("Temuan yang tidak didukung hasil search tidak boleh ditulis.", self.prompt)

    def test_research_model_does_not_think(self):
        # DeepSeek Chat Completions: thinking={"type": "disabled"}; the OpenAI SDK
        # only forwards unknown fields through extra_body. Measured: about 2-3 s
        # faster per research call, notes of the same quality.
        deepseek = next(t for key, t in self.nodes.items() if "DeepSeek" in key)
        self.assertEqual(deepseek["model_kwargs"]["value"], {"extra_body": {"thinking": {"type": "disabled"}}})

    def test_source_guard_sits_between_agent_and_output(self):
        edges = {(e["source"].split("-")[0], e["target"].split("-")[0], e["data"]["targetHandle"]["fieldName"])
                 for e in self.flow["data"]["edges"]}
        self.assertIn(("CielExaSearch", "Agent", "tools"), edges)
        self.assertIn(("Agent", "CielSourceGuard", "notes"), edges)
        self.assertIn(("CielSourceGuard", "ChatOutput", "input_value"), edges)
        self.assertNotIn(("Agent", "ChatOutput", "input_value"), edges)
        self.assertFalse([key for key in self.nodes if "ExaSearchToolkit" in key])

    def test_embedded_guard_code_matches_repository_sources(self):
        nodes = {n["id"].split("-")[0]: n["data"]["node"] for n in self.flow["data"]["nodes"]}
        for kind, filename in GUARDED.items():
            with self.subTest(component=kind):
                code = nodes[kind]["template"]["code"]["value"]
                source = (COMPONENTS / filename).read_text(encoding="utf-8")
                self.assertEqual(code.splitlines(), source.splitlines())
                self.assertEqual(nodes[kind]["metadata"]["code_hash"], hashlib.sha256(code.encode()).hexdigest()[:12])
                self.assertNotIn("[probe", code)

    def test_keys_are_global_variable_names_only(self):
        self.assertIsNone(re.search(r"sk-[A-Za-z0-9_-]{16,}", self.raw))
        for template in self.nodes.values():
            for field in ("api_key", "exa_api_key"):
                if field in template:
                    self.assertIn(template[field]["value"], (None, "", "DEEPSEEK_API_KEY", "EXA_API_KEY"))


if __name__ == "__main__":
    unittest.main()
