import copy
import hashlib
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FLOW_V1100 = ROOT / "flow" / "v1.10.0" / "Ciel_AI_Long-Term_Memory_Master.json"
FLOW_V1101 = ROOT / "flow" / "v1.10.1" / "Ciel_AI_Long-Term_Memory_Master.json"


def router(flow):
    return next(n for n in flow["data"]["nodes"] if n["id"].startswith("CielVisionRouter-"))


class FlowV1101ContractTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = FLOW_V1101.read_text(encoding="utf-8")
        cls.flow = json.loads(cls.raw)
        cls.base = json.loads(FLOW_V1100.read_text(encoding="utf-8"))
        cls.node = router(cls.flow)["data"]["node"]
        cls.template = cls.node["template"]

    def test_only_the_vision_router_changes_from_v1100(self):
        def strip(flow):
            flow = copy.deepcopy(flow)
            for node in flow["data"]["nodes"]:
                if node["id"].startswith("CielVisionRouter-"):
                    node["data"]["node"] = None
            return flow

        self.assertEqual(strip(self.flow), strip(self.base))

    def test_router_code_matches_repository_source(self):
        # Snapshot historis: v1.10.2 swaps the model order and lowers the
        # timeout; the current code is checked in tests/test_flow_v1102_contract.py.
        code = self.template["code"]["value"]
        self.assertIn('value="gemini-3.1-flash-lite"', code)
        self.assertIn("api_fallback_model", code)
        self.assertEqual(self.node["metadata"]["code_hash"], hashlib.sha256(code.encode()).hexdigest()[:12])

    def test_backup_gemini_model_before_the_local_model(self):
        # Production 2026-10-18: the main model answered HTTP 503 for a while and
        # the local model then took 136 s; gemini-3.5-flash-lite still answered.
        self.assertEqual(self.template["api_model"]["value"], "gemini-3.1-flash-lite")
        self.assertEqual(self.template["api_fallback_model"]["value"], "gemini-3.5-flash-lite")
        self.assertEqual(self.template["vision_api_key"]["value"], "GEMINI_API_KEY")
        self.assertTrue(self.template["vision_api_key"]["load_from_db"])

    def test_other_router_settings_are_kept(self):
        old = router(self.base)["data"]["node"]["template"]
        for field in ("model_name", "base_url", "system_prompt", "instruction", "num_ctx", "api_timeout"):
            with self.subTest(field=field):
                self.assertEqual(self.template[field]["value"], old[field]["value"])

    def test_snapshot_contains_no_hardcoded_api_keys(self):
        self.assertIsNone(re.search(r"sk-[A-Za-z0-9_-]{16,}", self.raw))
        self.assertIsNone(re.search(r"AIza[0-9A-Za-z_-]{20,}", self.raw))


if __name__ == "__main__":
    unittest.main()
