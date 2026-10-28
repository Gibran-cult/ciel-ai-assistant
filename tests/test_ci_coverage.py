import re
import unittest
from pathlib import Path


TESTS_DIR = Path(__file__).resolve().parent
CI_TEXT = (TESTS_DIR.parent / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

# Test modules that need a live backend (a running app, live LLM or judge).
# They are deliberately kept out of CI, so CI must never list them.
LIVE_TESTS = frozenset({
    "test_ciel_master",
    "test_judge_calibration",
    "test_llm_judge",
    "test_memory_context_optimization",
    "test_memory_engine",
    "test_memory_multi_query",
    "test_response_quality",
})


class CiCoverageTest(unittest.TestCase):
    # A new offline test module that is missing from the CI unittest list would
    # never run in CI. Fail when one is left out, so it is noticed in review.

    def test_every_offline_test_module_runs_in_ci(self):
        on_disk = {p.stem for p in TESTS_DIR.glob("test_*.py")}
        in_ci = set(re.findall(r"tests\.(test_[a-z0-9_]+)", CI_TEXT))
        self.assertEqual(on_disk - LIVE_TESTS - in_ci, set())

    def test_live_tests_are_not_in_ci(self):
        in_ci = set(re.findall(r"tests\.(test_[a-z0-9_]+)", CI_TEXT))
        self.assertEqual(LIVE_TESTS & in_ci, set())

    def test_every_flow_json_is_validated(self):
        # The step loops over git-tracked flow JSON instead of naming files.
        self.assertIn("git ls-files 'flow/*.json' 'flow/**/*.json'", CI_TEXT)
        self.assertIn("python -m json.tool", CI_TEXT)


if __name__ == "__main__":
    unittest.main()
