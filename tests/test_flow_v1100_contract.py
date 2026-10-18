import copy
import hashlib
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FLOW_V190 = ROOT / "flow" / "v1.9.0" / "Ciel_AI_Long-Term_Memory_Master.json"
FLOW_V1100 = ROOT / "flow" / "v1.10.0" / "Ciel_AI_Long-Term_Memory_Master.json"
ROUTER_SOURCE = ROOT / "flow" / "components" / "ciel_vision_router.py"


def router(flow):
    return next(n for n in flow["data"]["nodes"] if n["id"].startswith("CielVisionRouter-"))


class FlowV1100ContractTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = FLOW_V1100.read_text(encoding="utf-8")
        cls.flow = json.loads(cls.raw)
        cls.base = json.loads(FLOW_V190.read_text(encoding="utf-8"))
        cls.node = router(cls.flow)["data"]["node"]
        cls.template = cls.node["template"]

    def test_only_the_vision_router_changes_from_v190(self):
        def strip(flow):
            flow = copy.deepcopy(flow)
            for node in flow["data"]["nodes"]:
                if node["id"].startswith("CielVisionRouter-"):
                    node["data"]["node"] = None
            return flow

        self.assertEqual(strip(self.flow), strip(self.base))
        self.assertEqual(router(self.flow)["id"], router(self.base)["id"])

    def test_router_code_matches_repository_source(self):
        code = self.template["code"]["value"]
        self.assertEqual(code.splitlines(), ROUTER_SOURCE.read_text(encoding="utf-8").splitlines())
        self.assertEqual(self.node["metadata"]["code_hash"], hashlib.sha256(code.encode()).hexdigest()[:12])

    def test_gemini_reads_images_with_the_key_from_a_global_variable(self):
        # Local qwen2.5vl:3b on the laptop CPU took ~66 s per new photo (2026-10-18).
        self.assertEqual(self.template["vision_api_key"]["value"], "GEMINI_API_KEY")
        self.assertTrue(self.template["vision_api_key"]["load_from_db"])
        self.assertEqual(self.template["api_model"]["value"], "gemini-3.1-flash-lite")
        self.assertEqual(self.template["api_timeout"]["value"], 20)

    def test_local_model_settings_are_kept_as_the_fallback(self):
        old = router(self.base)["data"]["node"]["template"]
        for field in ("model_name", "base_url", "system_prompt", "instruction", "num_ctx"):
            with self.subTest(field=field):
                self.assertEqual(self.template[field]["value"], old[field]["value"])

    def test_snapshot_contains_no_hardcoded_api_keys(self):
        self.assertIsNone(re.search(r"sk-[A-Za-z0-9_-]{16,}", self.raw))
        self.assertIsNone(re.search(r"AIza[0-9A-Za-z_-]{20,}", self.raw))


if __name__ == "__main__":
    unittest.main()
