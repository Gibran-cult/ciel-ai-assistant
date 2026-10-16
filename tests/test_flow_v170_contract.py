import copy
import hashlib
import json
import re
import unittest
from pathlib import Path

from tests.test_flow_v141_contract import RESERVED_COMPONENT_ATTRIBUTES, input_names, normalize


ROOT = Path(__file__).resolve().parents[1]
FLOW_V160 = ROOT / "flow" / "v1.6.0" / "Ciel_AI_Long-Term_Memory_Master.json"
FLOW_V170 = ROOT / "flow" / "v1.7.0" / "Ciel_AI_Long-Term_Memory_Master.json"
COMPONENTS = ROOT / "flow" / "components"
APP_PATH = ROOT / "app.py"

STORE_ID = "CielDatasetStore-d4tA5"
TABLE_ID = "CielTableAnalyst-t4bL3"
ML_ID = "CielMLAnalyst-m7Lq2"
SOURCES = {
    STORE_ID: "ciel_dataset_store.py",
    TABLE_ID: "ciel_table_analyst.py",
    ML_ID: "ciel_ml_analyst.py",
}


def agent(flow):
    return next(n for n in flow["data"]["nodes"] if n["id"].startswith("Agent-"))


def prompt_of(flow):
    return agent(flow)["data"]["node"]["template"]["system_prompt"]["value"]


class FlowV170ContractTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = FLOW_V170.read_text(encoding="utf-8")
        cls.flow = json.loads(cls.raw)
        cls.base = json.loads(FLOW_V160.read_text(encoding="utf-8"))
        cls.nodes = {n["id"]: n for n in cls.flow["data"]["nodes"]}
        cls.prompt = prompt_of(cls.flow)

    def template(self, node_id):
        return self.nodes[node_id]["data"]["node"]["template"]

    def test_dataset_store_is_an_agent_tool(self):
        node = self.nodes[STORE_ID]["data"]["node"]
        self.assertTrue(node["tool_mode"])
        self.assertEqual([o["name"] for o in node["outputs"]], ["component_as_tool"])
        edges = [e for e in self.flow["data"]["edges"] if e["source"] == STORE_ID]
        self.assertEqual(len(edges), 1)
        self.assertTrue(edges[0]["target"].startswith("Agent-"))
        self.assertEqual(edges[0]["data"]["targetHandle"]["fieldName"], "tools")
        self.assertEqual(edges[0]["data"]["sourceHandle"]["dataType"], "CielDatasetStore")

    def test_embedded_code_matches_repository_sources(self):
        for node_id, filename in SOURCES.items():
            with self.subTest(node=node_id):
                code = self.template(node_id)["code"]["value"]
                self.assertEqual(normalize(code), normalize((COMPONENTS / filename).read_text(encoding="utf-8")))
                metadata = self.nodes[node_id]["data"]["node"]["metadata"]
                self.assertEqual(metadata["code_hash"], hashlib.sha256(code.encode()).hexdigest()[:12])

    def test_owner_and_files_come_from_the_app_not_the_agent(self):
        for node_id in SOURCES:
            with self.subTest(node=node_id):
                template = self.template(node_id)
                self.assertFalse(template["memory_owner"]["tool_mode"])
                self.assertFalse(template["attached_tables"]["tool_mode"])
                args = template["tools_metadata"]["value"][0]["args"]
                self.assertNotIn("memory_owner", args)
                self.assertNotIn("attached_tables", args)

    def test_dataset_tool_cannot_delete(self):
        tool = self.template(STORE_ID)["tools_metadata"]["value"][0]
        self.assertEqual(tool["name"], "manage_dataset")
        self.assertEqual(sorted(tool["args"]), ["action", "dataset", "file_name", "rows"])
        self.assertIn("Tidak bisa menghapus", tool["description"])
        self.assertIn("HANYA jika pengguna secara eksplisit meminta", tool["description"])
        source = (COMPONENTS / SOURCES[STORE_ID]).read_text(encoding="utf-8")
        self.assertIn('ACTIONS = ("list", "show", "save_file", "add_rows")', source)
        self.assertNotIn("unlink", source)

    def test_inputs_do_not_shadow_langflow_attributes(self):
        for filename in SOURCES.values():
            with self.subTest(component=filename):
                names = input_names((COMPONENTS / filename).read_text(encoding="utf-8"))
                self.assertIn("memory_owner", names)
                self.assertFalse(RESERVED_COMPONENT_ATTRIBUTES & set(names))

    def test_only_expected_parts_change_from_v160(self):
        def strip(flow):
            flow = copy.deepcopy(flow)
            flow["data"]["nodes"] = [n for n in flow["data"]["nodes"] if n["id"] != STORE_ID]
            flow["data"]["edges"] = [e for e in flow["data"]["edges"] if e["source"] != STORE_ID]
            for node in flow["data"]["nodes"]:
                if node["id"] in (TABLE_ID, ML_ID):
                    d = node["data"]["node"]
                    d["template"].pop("memory_owner", None)
                    d["template"]["code"]["value"] = ""
                    d["metadata"]["code_hash"] = ""
                    d["field_order"] = [f for f in d["field_order"] if f != "memory_owner"]
            agent(flow)["data"]["node"]["template"]["system_prompt"]["value"] = ""
            return flow

        self.assertEqual(strip(self.flow), strip(self.base))

    def test_prompt_keeps_every_v160_line_in_order(self):
        self.assertTrue(self.prompt.startswith("CIEL AI MASTER — SYSTEM PROMPT v14.4"))
        old = prompt_of(self.base).replace("v14.3", "v14.4").splitlines()
        new = self.prompt.splitlines()
        position = 0
        for line in old:
            position = new.index(line, position) + 1

    def test_prompt_routes_personal_datasets(self):
        self.assertIn("WAJIB gunakan Ciel Dataset Store (tool manage_dataset) jika pengguna secara eksplisit meminta", self.prompt)
        self.assertIn("Jangan pernah menyimpan dataset tanpa permintaan eksplisit pengguna.", self.prompt)
        self.assertIn("panggil analyze_table atau train_model dengan file_name berisi nama dataset", self.prompt)
        self.assertIn("Ciel tidak bisa menghapusnya dari chat", self.prompt)
        self.assertIn("butuh masuk dengan Google dan tidak ada yang disimpan", self.prompt)
        self.assertIn("- data tabel atau baris data (untuk itu ada Ciel Dataset Store),", self.prompt)
        # Live test: the Agent listed datasets even when the user named one,
        # and called the current message, seen again in the history, a duplicate.
        self.assertIn("Panggil action=list dulu hanya jika pengguna tidak menyebut namanya", self.prompt)
        self.assertIn("Itu satu pesan yang sama, bukan pesan ganda dari pengguna; jangan membahasnya.", self.prompt)
        self.assertIn("catat sekali saja dan jangan mengatakan pesannya terkirim dua kali", self.prompt)
        self.assertLess(self.prompt.index("3. Machine learning"), self.prompt.index("4. Dataset pribadi"))
        self.assertLess(self.prompt.index("4. Dataset pribadi"), self.prompt.index("Jangan pernah menjawab pertanyaan tentang file pengguna"))

    def test_snapshot_contains_no_hardcoded_api_keys(self):
        self.assertIsNone(re.search(r"sk-[A-Za-z0-9_-]{16,}", self.raw))


class AppDatasetWiringTest(unittest.TestCase):

    def test_app_sends_owner_and_files_to_every_data_tool(self):
        source = APP_PATH.read_text(encoding="utf-8")
        self.assertIn(f'DATASET_STORE_ID = get_config("DATASET_STORE_ID") or "{STORE_ID}"', source)
        for name in ("TABLE_ANALYST_ID", "ML_ANALYST_ID", "DATASET_STORE_ID"):
            self.assertIn(f'{name}: {{"attached_tables": encoded_tables, "memory_owner": owner}}', source)


if __name__ == "__main__":
    unittest.main()
