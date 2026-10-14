import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FLOW_PATH = ROOT / "flow" / "v1.2.0" / "Ciel_AI_Long-Term_Memory_Master.json"
COMPONENT_PATH = ROOT / "flow" / "components" / "ciel_vision_router.py"

CHAT_INPUT_ID = "ChatInput-X8W7I"


class FlowV120ContractTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = FLOW_PATH.read_text(encoding="utf-8")
        cls.flow = json.loads(cls.raw)
        cls.nodes = {node["id"]: node for node in cls.flow["data"]["nodes"]}
        cls.edges = cls.flow["data"]["edges"]

    def router_id(self):
        ids = [i for i in self.nodes if i.startswith("CielVisionRouter")]
        self.assertEqual(len(ids), 1)
        return ids[0]

    def test_chat_input_id_is_stable(self):
        # app.py mengirim gambar lewat tweaks ke ID ini (CHAT_INPUT_ID).
        self.assertIn(CHAT_INPUT_ID, self.nodes)

    def test_chat_input_feeds_only_the_router(self):
        targets = [e["target"] for e in self.edges if e["source"] == CHAT_INPUT_ID]
        self.assertEqual(targets, [self.router_id()])

    def test_router_feeds_agent_input(self):
        router = self.router_id()
        out = [e for e in self.edges if e["source"] == router]
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0]["target"].startswith("Agent-"))
        self.assertEqual(out[0]["data"]["targetHandle"]["fieldName"], "input_value")

    def test_old_vision_node_is_gone(self):
        self.assertFalse(any("ChatOllamaComponent" in i for i in self.nodes))

    def test_router_code_matches_repository_source(self):
        code = self.nodes[self.router_id()]["data"]["node"]["template"]["code"]["value"]
        # Bandingkan tanpa beda CRLF/LF (checkout Windows vs JSON flow).
        def normalize(text):
            return text.replace("\r\n", "\n").strip()

        self.assertEqual(
            normalize(code),
            normalize(COMPONENT_PATH.read_text(encoding="utf-8")),
        )

    def test_math_tutor_runs_as_native_run_flow_tool(self):
        # Dulu Math Tutor dipanggil lewat HTTP dengan API key tertanam di kode.
        math_nodes = [
            node_id
            for node_id, node in self.nodes.items()
            if node_id.startswith("RunFlow")
            and node["data"]["node"]["template"]["flow_name_selected"]["value"] == "Math Tutor Agent"
        ]
        self.assertEqual(len(math_nodes), 1)
        tool_sources = {
            e["source"]
            for e in self.edges
            if e["data"]["targetHandle"].get("fieldName") == "tools"
        }
        self.assertIn(math_nodes[0], tool_sources)
        self.assertNotIn("CustomComponent-aoG7C", self.nodes)

    def test_snapshot_contains_no_hardcoded_api_keys(self):
        self.assertIsNone(re.search(r"sk-[A-Za-z0-9_-]{16,}", self.raw))
        self.assertNotIn("REDACTED", self.raw)


if __name__ == "__main__":
    unittest.main()
