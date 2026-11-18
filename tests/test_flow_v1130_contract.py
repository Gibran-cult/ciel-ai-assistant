import copy
import hashlib
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FLOW_V1120 = ROOT / "flow" / "v1.12.0" / "Ciel_AI_Long-Term_Memory_Master.json"
FLOW_V1130 = ROOT / "flow" / "v1.13.0" / "Ciel_AI_Long-Term_Memory_Master.json"
COMPONENTS = ROOT / "flow" / "components"

AGENT_ID = "Agent-puarO"
DEEPSEEK_ID = "ext:deepseek:DeepSeekModelComponent@official-WscEJ"
FALLBACK_ID = "CielFallbackModel-fb1k0"
GUARD_ID = "CielSourceGuard-m41n0"
EMBEDDED = {FALLBACK_ID: "ciel_fallback_model.py", GUARD_ID: "ciel_source_guard.py"}


def nodes(flow):
    return {n["id"]: n for n in flow["data"]["nodes"]}


def template(flow, node_id):
    return nodes(flow)[node_id]["data"]["node"]["template"]


class FlowV1130ContractTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = FLOW_V1130.read_text(encoding="utf-8")
        cls.flow = json.loads(cls.raw)
        cls.base = json.loads(FLOW_V1120.read_text(encoding="utf-8"))

    def test_the_agent_model_is_deepseek_with_a_gemini_fallback(self):
        # DeepSeek 503 "too busy" and 402 (empty balance) took the app down.
        self.assertNotIn(DEEPSEEK_ID, nodes(self.flow))
        self.assertEqual(nodes(self.flow)[FALLBACK_ID]["data"]["type"], "CielFallbackModel")
        edges = [e for e in self.flow["data"]["edges"] if e["target"] == AGENT_ID and e["data"]["targetHandle"]["fieldName"] == "model"]
        self.assertEqual([(e["source"], e["data"]["sourceHandle"]["name"]) for e in edges], [(FALLBACK_ID, "model_output")])

    def test_deepseek_settings_carry_over_and_keys_come_from_global_variables(self):
        model = template(self.flow, FALLBACK_ID)
        old = template(self.base, DEEPSEEK_ID)
        for field in ("model_name", "api_base", "model_kwargs", "temperature", "seed"):
            with self.subTest(field=field):
                self.assertEqual(model[field]["value"], old[field]["value"])
        self.assertEqual(model["model_kwargs"]["value"], {"extra_body": {"thinking": {"type": "disabled"}}})
        # Only flash-lite answered reliably on this key (2026-11-03): 16/16.
        self.assertEqual(model["fallback_model_name"]["value"], "gemini-3.5-flash-lite")
        for field, variable in (("api_key", "DEEPSEEK_API_KEY"), ("fallback_api_key", "GEMINI_API_KEY")):
            with self.subTest(field=field):
                self.assertEqual(model[field]["value"], variable)
                self.assertTrue(model[field]["load_from_db"])

    def test_embedded_code_matches_repository_sources(self):
        for node_id, filename in EMBEDDED.items():
            with self.subTest(node=node_id):
                code = template(self.flow, node_id)["code"]["value"]
                self.assertEqual(code.splitlines(), (COMPONENTS / filename).read_text(encoding="utf-8").splitlines())
        guard = nodes(self.flow)[GUARD_ID]["data"]["node"]
        self.assertEqual(guard["metadata"]["code_hash"], hashlib.sha256(guard["template"]["code"]["value"].encode()).hexdigest()[:12])

    def test_only_the_model_node_and_the_guard_code_change_from_v1120(self):
        def strip(flow):
            flow = copy.deepcopy(flow)
            data = flow["data"]
            model_nodes = {DEEPSEEK_ID, FALLBACK_ID}
            data["nodes"] = [n for n in data["nodes"] if n["id"] not in model_nodes]
            data["edges"] = [e for e in data["edges"] if e["source"] not in model_nodes]
            guard = nodes(flow)[GUARD_ID]["data"]["node"]
            guard["template"]["code"]["value"] = None
            guard["metadata"]["code_hash"] = None
            return flow

        self.assertEqual(strip(self.flow), strip(self.base))

    def test_snapshot_contains_no_hardcoded_api_keys(self):
        self.assertIsNone(re.search(r"sk-[A-Za-z0-9_-]{16,}", self.raw))
        self.assertIsNone(re.search(r"AIza[0-9A-Za-z_-]{20,}", self.raw))


if __name__ == "__main__":
    unittest.main()
