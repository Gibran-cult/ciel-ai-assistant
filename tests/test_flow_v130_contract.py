import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FLOW_PATH = ROOT / "flow" / "v1.3.0" / "Ciel_AI_Long-Term_Memory_Master.json"

CHAT_INPUT_ID = "ChatInput-X8W7I"
MEMORY_SEARCH_ID = "CielMemorySearch-BC6pl"
MEMORY_STORE_ID = "CielMemoryStore-uBmzx"


class FlowV130ContractTest(unittest.TestCase):
    # Snapshot historis. Input `user_id` di v1.3.0/v1.4.0 tertimpa atribut
    # bawaan Component.user_id milik Langflow, sehingga isolasi memory tidak
    # bekerja. Diperbaiki di v1.4.1 (lihat tests/test_flow_v141_contract.py).

    @classmethod
    def setUpClass(cls):
        cls.raw = FLOW_PATH.read_text(encoding="utf-8")
        cls.flow = json.loads(cls.raw)
        cls.nodes = {node["id"]: node for node in cls.flow["data"]["nodes"]}
        cls.edges = cls.flow["data"]["edges"]

    def template(self, node_id):
        return self.nodes[node_id]["data"]["node"]["template"]

    def test_ids_used_by_app_are_stable(self):
        # app.py mengirim tweaks ke ID ini (CHAT_INPUT_ID, MEMORY_*_ID).
        for node_id in (CHAT_INPUT_ID, MEMORY_SEARCH_ID, MEMORY_STORE_ID):
            self.assertIn(node_id, self.nodes)

    def test_memory_tools_still_feed_agent(self):
        tool_sources = {
            e["source"]
            for e in self.edges
            if e["target"].startswith("Agent-")
            and e["data"]["targetHandle"].get("fieldName") == "tools"
        }
        self.assertIn(MEMORY_SEARCH_ID, tool_sources)
        self.assertIn(MEMORY_STORE_ID, tool_sources)

    def test_user_id_is_not_controlled_by_the_agent(self):
        for node_id in (MEMORY_SEARCH_ID, MEMORY_STORE_ID):
            with self.subTest(node=node_id):
                field = self.template(node_id)["user_id"]
                self.assertFalse(field["tool_mode"])
                self.assertEqual(field["value"], "")
                self.assertIn("user_id", self.nodes[node_id]["data"]["node"]["field_order"])
                tool_args = self.template(node_id)["tools_metadata"]["value"][0]["args"]
                self.assertNotIn("user_id", tool_args)

    def test_store_output_does_not_leak_internals(self):
        code = self.template(MEMORY_STORE_ID)["code"]["value"]
        self.assertNotIn("Database:", code)
        self.assertNotIn("Total memory", code)

    def test_orphan_research_api_tool_is_gone(self):
        self.assertNotIn("CustomComponent-2R2c7", self.nodes)
        self.assertFalse(any("127.0.0.1:7860" in json.dumps(n) for n in self.nodes.values()))

    def test_edges_only_reference_existing_nodes(self):
        for edge in self.edges:
            self.assertIn(edge["source"], self.nodes)
            self.assertIn(edge["target"], self.nodes)

    def test_snapshot_contains_no_hardcoded_api_keys(self):
        self.assertIsNone(re.search(r"sk-[A-Za-z0-9_-]{16,}", self.raw))


if __name__ == "__main__":
    unittest.main()
