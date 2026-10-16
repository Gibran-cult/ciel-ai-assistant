import ast
import importlib
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.live_session import answer_from, app_tweaks, new_session_id


ROOT = Path(__file__).resolve().parents[1]
LIVE_SCRIPTS = (
    "tests/test_response_quality.py",
    "tests/test_performance_snapshot.py",
    "tests/test_ciel_master.py",
)
FIXTURE = ROOT / "tests" / "assets" / "langflow_agent_message.json"


def run_payloads(tree):
    """Dict literals that are /api/v1/run payloads (they have an "input_type" key)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            keys = {k.value for k in node.keys if isinstance(k, ast.Constant)}
            if "input_type" in keys:
                yield keys


class LiveScriptsContractTest(unittest.TestCase):
    # Without a session_id every live test shared Langflow's default session;
    # its research sub-agent history reached ~490k characters and cases
    # influenced each other (a 9/9 suite flaked to 8/9).

    def test_every_run_payload_has_its_own_session_and_app_tweaks(self):
        for rel in LIVE_SCRIPTS:
            tree = ast.parse((ROOT / rel).read_text(encoding="utf-8-sig"))
            payloads = list(run_payloads(tree))
            with self.subTest(script=rel):
                self.assertTrue(payloads)
                for keys in payloads:
                    self.assertIn("session_id", keys)
                    self.assertIn("tweaks", keys)

    def test_scripts_judge_the_answer_users_see(self):
        for rel in LIVE_SCRIPTS:
            source = (ROOT / rel).read_text(encoding="utf-8-sig")
            with self.subTest(script=rel):
                self.assertNotIn('["data"]["text"]', source.replace("\n", "").replace(" ", ""))
                self.assertIn("answer_from(data)", source)


class LiveSessionHelpersTest(unittest.TestCase):

    def test_session_ids_are_unique(self):
        ids = {new_session_id("quality") for _ in range(50)}
        self.assertEqual(len(ids), 50)
        self.assertTrue(all(i.startswith("livetest-quality-") for i in ids))

    def test_tweaks_match_an_anonymous_app_visitor(self):
        tweaks = app_tweaks({"ChatInput-X8W7I": {"files": "f.png"}})
        self.assertEqual(tweaks["CielMemorySearch-BC6pl"], {"memory_owner": ""})
        self.assertEqual(tweaks["CielMemoryStore-uBmzx"], {"memory_owner": ""})
        self.assertEqual(tweaks["CielTableAnalyst-t4bL3"], {"attached_tables": ""})
        self.assertEqual(tweaks["CielMLAnalyst-m7Lq2"], {"attached_tables": ""})
        self.assertEqual(tweaks["ChatInput-X8W7I"], {"files": "f.png"})

    def test_answer_from_returns_the_final_answer(self):
        message = json.loads(FIXTURE.read_text(encoding="utf-8"))
        data = {"outputs": [{"outputs": [{"results": {"message": message}}]}]}
        self.assertEqual(
            answer_from(data),
            "Rata-rata Quantity_Sold pada dataset adalah **23,685** — kalau dibulatkan jadi **23,69**.",
        )


class Response:
    status_code = 200

    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


class ResponseQualityRequestsTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        env = {
            "NGROK_URL": "https://example.invalid", "NGROK_USER": "u", "NGROK_PASSWORD": "p",
            "LANGFLOW_API_KEY": "k", "FLOW_ID": "flow",
        }
        with patch.dict(os.environ, env):
            cls.module = importlib.import_module("tests.test_response_quality")

    def test_each_case_gets_a_fresh_session(self):
        message = {"data": {"text": "jawaban"}, "content_blocks": []}
        answer = {"outputs": [{"outputs": [{"results": {"message": message}}]}]}

        with patch("requests.post", return_value=Response(answer)) as post:
            self.assertEqual(self.module.ask_ciel("soal 1"), "jawaban")
            self.module.ask_ciel("soal 2")

        sessions = [c.kwargs["json"]["session_id"] for c in post.call_args_list]
        self.assertEqual(len(set(sessions)), 2)
        self.assertEqual(post.call_args.kwargs["json"]["tweaks"]["CielMemoryStore-uBmzx"], {"memory_owner": ""})

    def test_vision_case_keeps_its_image_tweak(self):
        image = ROOT / "tests" / "assets" / "vision_math_small.png"
        message = {"data": {"text": "6"}, "content_blocks": []}
        responses = [Response({"file_path": "flow/img.png"}), Response({"outputs": [{"outputs": [{"results": {"message": message}}]}]})]

        with patch("requests.post", side_effect=responses) as post:
            self.assertEqual(self.module.ask_ciel_with_image("hitung", image), "6")

        payload = post.call_args.kwargs["json"]
        self.assertTrue(payload["session_id"].startswith("livetest-quality-vision-"))
        self.assertEqual(payload["tweaks"]["ChatInput-X8W7I"], {"files": "flow/img.png", "input_value": "hitung"})
        self.assertIn("CielMemorySearch-BC6pl", payload["tweaks"])


class CollectorFailedCasesTest(unittest.TestCase):

    def test_failed_cases_are_named(self):
        from tests.collect_quality import parse_failed_cases

        output = (
            "✅ math_limit_01                  PASS\n"
            "   Output: 6\n\n"
            "❌ research_python_01             FAIL\n"
            "   └─ Tidak menemukan kata kunci: 'Python'\n"
            "   └─ Jawaban terlalu pendek\n"
            "   Output: Ini rangkuman terbaru soal bahasa pemrograman...\n\n"
            "✅ knowledge_data_science_01      PASS\n"
            "   Output: Data Science adalah...\n\n"
            "❌ vision_math_01                 FAIL\n"
            "RESULT: 7/9 PASSED\n"
        )

        self.assertEqual(parse_failed_cases(output), [
            {
                "id": "research_python_01",
                "reasons": ["Tidak menemukan kata kunci: 'Python'", "Jawaban terlalu pendek"],
                "answer_preview": "Ini rangkuman terbaru soal bahasa pemrograman...",
            },
            {"id": "vision_math_01", "reasons": [], "answer_preview": ""},
        ])
        self.assertEqual(parse_failed_cases("RESULT: 9/9 PASSED"), [])


class EvaluationCaseChecksTest(unittest.TestCase):
    # research_machine_learning_01 flaked once with "Tidak menemukan: 'machine'"
    # while two reruns answered correctly; an Indonesian answer may say
    # "pembelajaran mesin" instead of "machine learning".

    @classmethod
    def setUpClass(cls):
        env = {
            "NGROK_URL": "https://example.invalid", "NGROK_USER": "u", "NGROK_PASSWORD": "p",
            "LANGFLOW_API_KEY": "k", "FLOW_ID": "flow",
        }
        with patch.dict(os.environ, env):
            cls.module = importlib.import_module("tests.test_response_quality")
        cases = json.loads((ROOT / "tests" / "evaluation_cases.json").read_text(encoding="utf-8"))
        cls.ml_checks = next(c for c in cases if c["id"] == "research_machine_learning_01")["checks"]

    def passes(self, answer):
        # evaluate_answer returns the list of failures; empty means passed.
        return not self.module.evaluate_answer(answer, self.ml_checks)

    def test_machine_learning_case_accepts_english_or_indonesian_term(self):
        filler = " Sumber dan tanggal rilis dicantumkan untuk setiap temuan." * 3
        self.assertTrue(self.passes("Perkembangan terbaru machine learning tahun ini." + filler))
        self.assertTrue(self.passes("Perkembangan terbaru pembelajaran mesin tahun ini." + filler))
        self.assertFalse(self.passes("Perkembangan terbaru basis data relasional tahun ini." + filler))


if __name__ == "__main__":
    unittest.main()
