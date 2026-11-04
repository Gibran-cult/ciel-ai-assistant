"""Contract for flow/image_ai/v1.0.0 (Ciel Image AI, Pro): Chat Input -> Ciel Image AI -> Chat Output."""

import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOW_PATH = ROOT / "flow" / "image_ai" / "v1.0.0" / "Ciel_Image_AI.json"
COMPONENT = ROOT / "flow" / "components" / "ciel_image_ai.py"

CHAT_IN = "ChatInput-1m4g3"
IMAGE_AI = "CielImageAI-1m4g3"
CHAT_OUT = "ChatOutput-1m4g3"


class ImageAIFlowContractTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw_bytes = FLOW_PATH.read_bytes()
        cls.raw = cls.raw_bytes.decode("utf-8")
        cls.flow = json.loads(cls.raw)
        cls.nodes = {node["id"]: node for node in cls.flow["data"]["nodes"]}
        cls.component = cls.nodes[IMAGE_AI]["data"]["node"]

    def test_three_nodes_in_one_chain(self):
        self.assertEqual(self.flow["name"], "Ciel Image AI")
        self.assertEqual(set(self.nodes), {CHAT_IN, IMAGE_AI, CHAT_OUT})
        self.assertEqual(self.nodes[IMAGE_AI]["data"]["type"], "CielImageAI")
        edges = {(e["source"], e["target"], e["data"]["sourceHandle"]["name"], e["data"]["targetHandle"]["fieldName"])
                 for e in self.flow["data"]["edges"]}
        self.assertEqual(edges, {(CHAT_IN, IMAGE_AI, "message", "input_value"), (IMAGE_AI, CHAT_OUT, "reply", "input_value")})
        for edge in self.flow["data"]["edges"]:
            self.assertEqual(edge["data"]["sourceHandle"]["id"], edge["source"])
            self.assertEqual(edge["data"]["targetHandle"]["id"], edge["target"])
            self.assertEqual(
                edge["sourceHandle"],
                json.dumps(edge["data"]["sourceHandle"], separators=(",", ":")).replace('"', "œ"),
            )
            self.assertEqual(
                edge["targetHandle"],
                json.dumps(edge["data"]["targetHandle"], separators=(",", ":")).replace('"', "œ"),
            )
        self.assertEqual([o["name"] for o in self.component["outputs"]], ["reply"])
        self.assertEqual(self.component["outputs"][0]["method"], "reply")

    def test_embedded_code_matches_the_repository_source(self):
        code = self.component["template"]["code"]["value"]
        self.assertEqual(code.splitlines(), COMPONENT.read_text(encoding="utf-8").splitlines())
        self.assertEqual(self.component["metadata"]["code_hash"], hashlib.sha256(code.encode()).hexdigest()[:12])

    def test_chat_nodes_do_not_store_messages(self):
        # Photos must not be kept in Langflow's message table.
        for node_id in (CHAT_IN, CHAT_OUT):
            with self.subTest(node=node_id):
                self.assertIs(self.nodes[node_id]["data"]["node"]["template"]["should_store_message"]["value"], False)

    def test_key_comes_from_a_global_variable_and_the_model_is_deepseek_flash(self):
        template = self.component["template"]
        self.assertEqual(template["api_key"]["value"], "DEEPSEEK_API_KEY")
        self.assertTrue(template["api_key"]["load_from_db"])
        self.assertTrue(template["api_key"]["password"])
        self.assertEqual(template["model_name"]["value"], "deepseek-flash")
        self.assertEqual(template["api_base"]["value"], "https://api.deepseek.com")
        self.assertEqual(self.component["field_order"], ["input_value", "api_key", "api_base", "model_name"])

    def test_snapshot_convention(self):
        self.assertNotIn(b"\n", self.raw_bytes.replace(b"\r\n", b""))
        self.assertFalse(self.raw_bytes.endswith(b"\n"))
        self.assertEqual(json.dumps(self.flow, indent=2, ensure_ascii=False).replace("\n", "\r\n"), self.raw)

    def test_snapshot_contains_no_hardcoded_api_keys(self):
        self.assertIsNone(re.search(r"sk-[A-Za-z0-9_-]{16,}", self.raw))
        self.assertIsNone(re.search(r"AIza[0-9A-Za-z_-]{20,}", self.raw))


if __name__ == "__main__":
    unittest.main()
