import copy
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FLOW_V1110 = ROOT / "flow" / "v1.11.0" / "Ciel_AI_Long-Term_Memory_Master.json"
FLOW_V1120 = ROOT / "flow" / "v1.12.0" / "Ciel_AI_Long-Term_Memory_Master.json"

AGENT_ID = "Agent-puarO"
CALC_ID = "CalculatorComponent-c4lc1"
DEEPSEEK_ID = "ext:deepseek:DeepSeekModelComponent@official-WscEJ"
RUN_FLOW_IDS = ("RunFlow-m4thT", "RunFlow-PTruN")


def nodes(flow):
    return {n["id"]: n for n in flow["data"]["nodes"]}


def template(flow, node_id):
    return nodes(flow)[node_id]["data"]["node"]["template"]


def prompt(flow):
    return template(flow, AGENT_ID)["system_prompt"]["value"]


class FlowV1120ContractTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = FLOW_V1120.read_text(encoding="utf-8")
        cls.flow = json.loads(cls.raw)
        cls.base = json.loads(FLOW_V1110.read_text(encoding="utf-8"))
        cls.prompt = prompt(cls.flow)

    def test_main_agent_answers_without_thinking_mode(self):
        # Thinking mode made analysis answers take ~25 s; with it off the 26
        # exact-answer checks stayed correct (2026-10-18).
        self.assertEqual(
            template(self.flow, DEEPSEEK_ID)["model_kwargs"]["value"],
            {"extra_body": {"thinking": {"type": "disabled"}}},
        )
        self.assertEqual(template(self.flow, DEEPSEEK_ID)["model_name"]["value"], "deepseek-flash")

    def test_sub_flows_are_cached_between_requests(self):
        for node_id in RUN_FLOW_IDS:
            with self.subTest(node=node_id):
                self.assertTrue(template(self.flow, node_id)["cache_flow"]["value"])

    def test_main_agent_has_the_calculator_as_a_tool(self):
        node = nodes(self.flow)[CALC_ID]["data"]
        self.assertEqual(node["type"], "CalculatorComponent")
        self.assertTrue(node["node"]["tool_mode"])
        self.assertEqual(node["node"]["template"]["tools_metadata"]["value"][0]["name"], "evaluate_expression")
        # Langflow's Calculator: AST allowlist of + - * / ** on floats, no names or calls.
        code = node["node"]["template"]["code"]["value"]
        self.assertIn("ast.parse(self.expression, mode=\"eval\")", code)
        self.assertNotIn("eval(self.expression", code)
        edges = [e for e in self.flow["data"]["edges"] if e["source"] == CALC_ID]
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["target"], AGENT_ID)
        self.assertEqual(edges[0]["data"]["targetHandle"]["fieldName"], "tools")
        self.assertEqual(edges[0]["data"]["sourceHandle"]["name"], "component_as_tool")

    def test_prompt_v148_sends_calculations_to_the_calculator(self):
        self.assertTrue(self.prompt.startswith("CIEL AI MASTER — SYSTEM PROMPT v14.8\n"))
        section = self.prompt.split("A. MATEMATIKA", 1)[1].split("B. DATA / DATASET", 1)[0]
        self.assertIn("WAJIB gunakan Calculator (tool evaluate_expression) untuk setiap hitungan angka", section)
        self.assertIn("Setiap angka hasil hitungan di jawaban harus berasal dari Calculator.", section)
        # The nested Math Tutor agent added ~4 s; it is kept for long worksheets only.
        self.assertIn("WAJIB gunakan Math Tutor untuk banyak soal sekaligus (lembar kerja)", section)
        self.assertIn("Cek setiap kunci jawaban dan contoh angka dengan Calculator.", section)
        self.assertIn("jangan mengarang hasil hitungan", section)
        self.assertNotIn("Jangan menyelesaikan soal matematika kompleks sendiri", self.prompt)

    def test_prompt_v148_names_health_and_official_facts_as_research(self):
        # With v14.7 a paracetamol dose was answered without a search (2026-10-18).
        section = self.prompt.split("D. RESEARCH", 1)[1].split("E. MULTI-SPECIALIST", 1)[0]
        self.assertIn("- kesehatan, gizi, obat, dan keselamatan,", section)
        self.assertIn("- hukum, aturan resmi, beasiswa, harga, dan angka resmi (misalnya UMR, kurs, pajak),", section)

    def test_only_the_planned_changes_from_v1110(self):
        def strip(flow):
            flow = copy.deepcopy(flow)
            data = flow["data"]
            data["nodes"] = [n for n in data["nodes"] if n["id"] != CALC_ID]
            data["edges"] = [e for e in data["edges"] if e["source"] != CALC_ID]
            template(flow, DEEPSEEK_ID)["model_kwargs"]["value"] = None
            template(flow, AGENT_ID)["system_prompt"]["value"] = None
            for node_id in RUN_FLOW_IDS:
                template(flow, node_id)["cache_flow"]["value"] = None
            return flow

        self.assertEqual(strip(self.flow), strip(self.base))

    def test_prompt_keeps_every_v147_line_outside_the_changed_rules(self):
        removed = set(prompt(self.base).splitlines()) - set(self.prompt.splitlines())
        old_math_rules = {
            "WAJIB gunakan Math Tutor untuk:",
            "- limit", "- turunan", "- statistika", "- himpunan", "- aljabar",
            "- perhitungan yang membutuhkan langkah",
            "Jangan menyelesaikan soal matematika kompleks sendiri jika Math Tutor tersedia.",
            "Jika Math Tutor gagal:",
            "- jelaskan specialist matematika tidak tersedia;",
            "- jangan mengarang hasil specialist.",
            "  → Vision + Math Tutor",
            "CIEL AI MASTER — SYSTEM PROMPT v14.7",
        }
        reworded = removed - old_math_rules
        self.assertEqual({line[:40] for line in reworded}, {
            "- Math Tutor dan riset web biasanya mema",
            "- Untuk angka, statistik, dan hitungan y",
        })
        self.assertIn("10. KEAMANAN", self.prompt)

    def test_snapshot_contains_no_hardcoded_api_keys(self):
        self.assertIsNone(re.search(r"sk-[A-Za-z0-9_-]{16,}", self.raw))
        self.assertIsNone(re.search(r"AIza[0-9A-Za-z_-]{20,}", self.raw))


if __name__ == "__main__":
    unittest.main()
