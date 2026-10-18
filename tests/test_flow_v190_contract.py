import copy
import hashlib
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FLOW_V180 = ROOT / "flow" / "v1.8.0" / "Ciel_AI_Long-Term_Memory_Master.json"
FLOW_V190 = ROOT / "flow" / "v1.9.0" / "Ciel_AI_Long-Term_Memory_Master.json"
COMPONENTS = ROOT / "flow" / "components"

EXA_ID = "CielExaSearch-m41n0"
GUARD_ID = "CielSourceGuard-m41n0"
EMBEDDED = {
    EXA_ID: "ciel_exa_search.py",
    GUARD_ID: "ciel_source_guard.py",
    "CielMemorySearch-BC6pl": "ciel_memory_search.py",
    "CielMemoryStore-uBmzx": "ciel_memory_store.py",
}
# v1.8.0 lines that v14.6 replaces: the main Agent now searches itself.
REPLACED = ("  → Research + Knowledge",)


def agent(flow):
    return next(n for n in flow["data"]["nodes"] if n["id"].startswith("Agent-"))


def prompt_of(flow):
    return agent(flow)["data"]["node"]["template"]["system_prompt"]["value"]


def research_section(prompt):
    return prompt[prompt.index("D. RESEARCH"):prompt.index("E. MULTI-SPECIALIST")]


def research_run_flow(flow):
    return [
        n["id"] for n in flow["data"]["nodes"]
        if n["id"].startswith("RunFlow-")
        and n["data"]["node"]["template"]["flow_name_selected"]["value"] == "Web Research Assistant"
    ]


class FlowV190ContractTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = FLOW_V190.read_text(encoding="utf-8")
        cls.flow = json.loads(cls.raw)
        cls.base = json.loads(FLOW_V180.read_text(encoding="utf-8"))
        cls.nodes = {n["id"]: n["data"]["node"] for n in cls.flow["data"]["nodes"]}
        cls.prompt = prompt_of(cls.flow)

    def test_only_expected_parts_change_from_v180(self):
        def strip(flow):
            flow = copy.deepcopy(flow)
            agent_id = agent(flow)["id"]
            dropped = set(research_run_flow(flow)) | {EXA_ID, GUARD_ID}
            flow["data"]["nodes"] = [n for n in flow["data"]["nodes"] if n["id"] not in dropped]
            flow["data"]["edges"] = [
                e for e in flow["data"]["edges"]
                if e["source"] not in dropped and e["target"] not in dropped
                and not (e["source"] == agent_id and e["target"].startswith("ChatOutput-"))
            ]
            for node in flow["data"]["nodes"]:
                if node["id"] in EMBEDDED:
                    node["data"]["node"]["template"]["code"]["value"] = ""
                    node["data"]["node"]["metadata"]["code_hash"] = ""
            agent(flow)["data"]["node"]["template"]["system_prompt"]["value"] = ""
            return flow

        self.assertEqual(strip(self.flow), strip(self.base))

    def test_main_agent_searches_and_the_guard_checks_its_answer(self):
        edges = {(e["source"], e["target"], e["data"]["targetHandle"]["fieldName"]) for e in self.flow["data"]["edges"]}
        agent_id = agent(self.flow)["id"]
        output_id = next(n for n in self.nodes if n.startswith("ChatOutput-"))
        self.assertIn((EXA_ID, agent_id, "tools"), edges)
        self.assertIn((agent_id, GUARD_ID, "notes"), edges)
        self.assertIn((GUARD_ID, output_id, "input_value"), edges)
        self.assertNotIn((agent_id, output_id, "input_value"), edges)
        self.assertEqual(research_run_flow(self.flow), [])
        self.assertEqual(len(research_run_flow(self.base)), 1)

    def test_embedded_code_matches_repository_sources(self):
        for node_id, filename in EMBEDDED.items():
            with self.subTest(node=node_id):
                code = self.nodes[node_id]["template"]["code"]["value"]
                source = (COMPONENTS / filename).read_text(encoding="utf-8")
                self.assertEqual(code.splitlines(), source.splitlines())
                self.assertEqual(self.nodes[node_id]["metadata"]["code_hash"], hashlib.sha256(code.encode()).hexdigest()[:12])

    def test_memory_embeddings_stay_loaded_for_an_hour(self):
        # Reloading the embedding model after Ollama's 5-minute default took 14 s.
        for filename in ("ciel_memory_search.py", "ciel_memory_store.py"):
            with self.subTest(component=filename):
                self.assertIn('"keep_alive": "1h",', (COMPONENTS / filename).read_text(encoding="utf-8"))

    def test_exa_settings_and_key(self):
        template = self.nodes[EXA_ID]["template"]
        self.assertEqual(template["search_num_results"]["value"], 5)
        self.assertEqual(template["highlights_max_characters"]["value"], 1500)
        self.assertTrue(template["include_highlights"]["value"])
        self.assertEqual(template["exa_api_key"]["value"], "EXA_API_KEY")
        self.assertTrue(template["exa_api_key"]["load_from_db"])

    def test_prompt_routes_research_to_the_search_tool(self):
        self.assertTrue(self.prompt.startswith("CIEL AI MASTER — SYSTEM PROMPT v14.6"))
        self.assertNotIn("Research Agent", self.prompt)
        research = research_section(self.prompt)
        self.assertIn("WAJIB gunakan tool search (pencarian web Exa) untuk:", research)
        self.assertIn("Mode Santai (riset cepat): satu putaran. Panggil search dengan 2 query berbeda sekaligus", research)
        self.assertIn("Mode Analisis (riset dalam): paling banyak 3 putaran", research)
        self.assertIn("Jangan memanggil get_contents.", research)
        self.assertIn("SUMBER HANYA DARI HASIL SEARCH", research)
        self.assertIn("Jangan menambah sumber dari ingatan", research)
        self.assertIn("Sumber:\n[1] <nama sumber> — <judul> — <URL> — <tanggal publikasi jika tersedia>", research)
        self.assertIn("Di Mode Santai, jawaban riset cukup inti saja", research)
        self.assertIn("jangan mengarang hasil riset", research)
        # Production v1.8.0: only 3 of 6 analysis answers listed sources, because
        # Mode Analisis said to end right after the Batasan line.
        self.assertIn("- Di Mode Analisis, bagian Sumber: tetap ditulis, tepat setelah baris Batasan.", research)
        self.assertIn("- Akhiri tepat setelah baris Batasan, kecuali bagian Sumber: untuk jawaban yang memakai search.", self.prompt)
        self.assertIn("  → search + Knowledge", self.prompt)
        self.assertIn("berasal dari hasil tool search,", self.prompt)

    def test_prompt_keeps_every_other_v180_line_in_order(self):
        old_prompt = prompt_of(self.base).replace("v14.5", "v14.6")
        old_research = set(research_section(old_prompt).splitlines())
        new = self.prompt.splitlines()
        position = 0
        for line in old_prompt.splitlines():
            if line in old_research or line in REPLACED:
                continue
            if "berasal dari hasil Research Agent," in line:
                line = line.replace("hasil Research Agent,", "hasil tool search,")
            if line.startswith("- Akhiri tepat setelah baris Batasan."):
                line = line.replace(
                    "baris Batasan.", "baris Batasan, kecuali bagian Sumber: untuk jawaban yang memakai search.")
            position = new.index(line, position) + 1

    def test_snapshot_contains_no_hardcoded_api_keys(self):
        self.assertIsNone(re.search(r"sk-[A-Za-z0-9_-]{16,}", self.raw))
        self.assertNotIn("[probe", self.raw)


if __name__ == "__main__":
    unittest.main()
