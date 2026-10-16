import copy
import hashlib
import json
import re
import unittest
from pathlib import Path

from tests.test_flow_v141_contract import RESERVED_COMPONENT_ATTRIBUTES, input_names, normalize


ROOT = Path(__file__).resolve().parents[1]
FLOW_V151 = ROOT / "flow" / "v1.5.1" / "Ciel_AI_Long-Term_Memory_Master.json"
FLOW_V160 = ROOT / "flow" / "v1.6.0" / "Ciel_AI_Long-Term_Memory_Master.json"
COMPONENT = ROOT / "flow" / "components" / "ciel_ml_analyst.py"
APP_PATH = ROOT / "app.py"

ML_ID = "CielMLAnalyst-m7Lq2"
TOOL_ARGS = ["clusters", "features", "file_name", "predict_for", "target", "task"]


def agent(flow):
    return next(n for n in flow["data"]["nodes"] if n["id"].startswith("Agent-"))


def prompt_of(flow):
    return agent(flow)["data"]["node"]["template"]["system_prompt"]["value"]


class FlowV160ContractTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = FLOW_V160.read_text(encoding="utf-8")
        cls.flow = json.loads(cls.raw)
        cls.base = json.loads(FLOW_V151.read_text(encoding="utf-8"))
        cls.nodes = {n["id"]: n for n in cls.flow["data"]["nodes"]}
        cls.node = cls.nodes[ML_ID]["data"]["node"]
        cls.prompt = prompt_of(cls.flow)

    def test_ml_analyst_is_an_agent_tool(self):
        self.assertTrue(self.node["tool_mode"])
        self.assertEqual([o["name"] for o in self.node["outputs"]], ["component_as_tool"])
        edges = [e for e in self.flow["data"]["edges"] if e["source"] == ML_ID]
        self.assertEqual(len(edges), 1)
        self.assertTrue(edges[0]["target"].startswith("Agent-"))
        self.assertEqual(edges[0]["data"]["targetHandle"]["fieldName"], "tools")
        self.assertEqual(edges[0]["data"]["sourceHandle"]["dataType"], "CielMLAnalyst")

    def test_ml_analyst_code_matches_repository_source(self):
        code = self.node["template"]["code"]["value"]
        self.assertEqual(normalize(code), normalize(COMPONENT.read_text(encoding="utf-8")))
        self.assertEqual(self.node["metadata"]["code_hash"], hashlib.sha256(code.encode()).hexdigest()[:12])

    def test_file_contents_come_from_app_not_agent(self):
        template = self.node["template"]
        self.assertFalse(template["attached_tables"]["tool_mode"])
        tool = template["tools_metadata"]["value"][0]
        self.assertEqual(tool["name"], "train_model")
        self.assertEqual(sorted(tool["args"]), TOOL_ARGS)
        self.assertEqual(sorted(input_names(COMPONENT.read_text(encoding="utf-8"))), sorted(TOOL_ARGS + ["attached_tables"]))

    def test_inputs_do_not_shadow_langflow_attributes(self):
        names = input_names(COMPONENT.read_text(encoding="utf-8"))
        self.assertFalse(RESERVED_COMPONENT_ATTRIBUTES & set(names))

    def test_tool_description_guards_against_leakage_and_overlap(self):
        description = self.node["template"]["tools_metadata"]["value"][0]["description"]
        self.assertIn("DILAMPIRKAN PENGGUNA", description)
        self.assertIn("Jangan memasukkan kolom turunan atau bocoran target ke features", description)
        self.assertIn("Untuk statistik biasa (total, rata-rata, per kelompok) gunakan analyze_table", description)

    def test_only_expected_parts_change_from_v151(self):
        def strip(flow):
            flow = copy.deepcopy(flow)
            flow["data"]["nodes"] = [n for n in flow["data"]["nodes"] if n["id"] != ML_ID]
            flow["data"]["edges"] = [e for e in flow["data"]["edges"] if e["source"] != ML_ID]
            agent(flow)["data"]["node"]["template"]["system_prompt"]["value"] = ""
            return flow

        self.assertEqual(strip(self.flow), strip(self.base))

    def test_prompt_keeps_every_v151_line_in_order(self):
        self.assertTrue(self.prompt.startswith("CIEL AI MASTER — SYSTEM PROMPT v14.3"))
        old = prompt_of(self.base).replace("v14.2", "v14.3")
        old = old.replace("Hasil Ciel Table Analyst sudah", "Hasil Ciel Table Analyst dan Ciel ML Analyst sudah")
        old = old.replace(
            "Ciel Table Analyst (file pengguna), atau",
            "Ciel Table Analyst (file pengguna), Ciel ML Analyst (model dan prediksi dari file pengguna), atau",
        )
        new_lines = self.prompt.splitlines()
        position = 0
        for line in old.splitlines():
            position = new_lines.index(line, position) + 1

    def test_prompt_routes_machine_learning_to_the_tool(self):
        self.assertIn("WAJIB gunakan Ciel ML Analyst (tool train_model)", self.prompt)
        self.assertIn("Jangan menebak akurasi, pengaruh fitur, kelompok, atau hasil prediksi.", self.prompt)
        self.assertIn("Jangan masukkan kolom turunan atau bocoran target ke features", self.prompt)
        self.assertIn("Selalu sampaikan kualitas model (R² atau akurasi, dibanding tebakan sederhana)", self.prompt)
        self.assertIn("bukan sebab-akibat", self.prompt)
        self.assertIn("Hasil Ciel Table Analyst dan Ciel ML Analyst sudah memakai format Indonesia.", self.prompt)
        self.assertIn("melatih model dengan Ciel ML Analyst lalu menjelaskan arti hasilnya", self.prompt)
        # The ML route sits between the two data sources and the rule that keeps them apart.
        self.assertLess(self.prompt.index("2. Dataset penjualan bawaan Ciel"), self.prompt.index("3. Machine learning"))
        self.assertLess(self.prompt.index("3. Machine learning"), self.prompt.index("Jangan pernah menjawab pertanyaan tentang file pengguna"))

    def test_snapshot_contains_no_hardcoded_api_keys(self):
        self.assertIsNone(re.search(r"sk-[A-Za-z0-9_-]{16,}", self.raw))


class AppMLWiringTest(unittest.TestCase):

    def test_app_sends_the_same_tables_to_the_ml_analyst(self):
        source = APP_PATH.read_text(encoding="utf-8")
        self.assertIn(f'ML_ANALYST_ID = get_config("ML_ANALYST_ID") or "{ML_ID}"', source)
        self.assertIn('ML_ANALYST_ID: {"attached_tables": encoded_tables}', source)
        self.assertIn('TABLE_ANALYST_ID: {"attached_tables": encoded_tables}', source)


if __name__ == "__main__":
    unittest.main()
