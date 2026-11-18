import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_api.gemini import GeminiModel  # noqa: E402
from agent_api.model import ModelError, ModelReply, cost_micro_usd  # noqa: E402
from agent_api.prompts import PLAN_SCHEMA, render_view  # noqa: E402
from tests.test_agent_claude import INSTRUCTION, PLAN, VIEW  # noqa: E402

KEY = "kunci-gemini-uji"
URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent"


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload

        return self.payload


class FakeSession:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.posts = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.posts.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        response = self.responses.pop(0)

        if isinstance(response, Exception):
            raise response

        return response


def answer(parts, finish="STOP", prompt=1000, out=100, thoughts=0):
    return FakeResponse({
        "candidates": [{"content": {"role": "model", "parts": parts}, "finishReason": finish}],
        "usageMetadata": {"promptTokenCount": prompt, "candidatesTokenCount": out, "thoughtsTokenCount": thoughts},
    })


def call(name, args):
    return {"functionCall": {"name": name, "args": args}}


class GeminiTest(unittest.TestCase):
    def test_one_function_call_becomes_a_proposal(self):
        session = FakeSession(answer([call("tab_click", {"ref": 5})], thoughts=50))
        reply = GeminiModel(session, KEY).act(VIEW)
        self.assertEqual(reply, ModelReply({"tool": "tab_click", "args": {"ref": 5}}, cost_micro_usd("gemini-3.5-flash-lite", 1000, 150)))

    def test_the_key_is_in_a_header_never_in_the_address(self):
        session = FakeSession(answer([call("tab_read", {})]))
        GeminiModel(session, KEY).act(VIEW)
        sent = session.posts[-1]
        self.assertEqual(sent["url"], URL)
        self.assertEqual(sent["headers"]["x-goog-api-key"], KEY)
        self.assertNotIn(KEY, sent["url"])
        self.assertEqual(sent["timeout"], 60)
        self.assertEqual(sent["json"]["contents"], [{"role": "user", "parts": [{"text": render_view(VIEW)}]}])
        self.assertEqual(sent["json"]["toolConfig"], {"functionCallingConfig": {"mode": "AUTO"}})
        names = [declaration["name"] for declaration in sent["json"]["tools"][0]["functionDeclarations"]]
        self.assertIn("tab_click", names)

    def test_no_call_or_two_calls_are_empty_proposals(self):
        for parts in ([{"text": "Saya akan klik"}], [call("tab_read", {}), call("finish", {"report": "x"})]):
            with self.subTest(parts=parts):
                self.assertEqual(GeminiModel(FakeSession(answer(parts)), KEY).act(VIEW).output, {})

    def test_errors_are_model_errors(self):
        for response in (FakeResponse({}, status=503), FakeResponse(ValueError("x")), FakeResponse({"candidates": []}),
                         ConnectionError("putus"), answer([call("tab_read", {})], finish="SAFETY")):
            with self.subTest(response=response):
                with self.assertRaises(ModelError):
                    GeminiModel(FakeSession(response), KEY).act(VIEW)

    def test_the_plan_comes_back_as_json(self):
        session = FakeSession(answer([{"text": json.dumps(PLAN)}]))
        self.assertEqual(GeminiModel(session, KEY).plan(INSTRUCTION).output, PLAN)
        config = session.posts[-1]["json"]["generationConfig"]
        self.assertEqual(config, {"responseMimeType": "application/json", "responseJsonSchema": PLAN_SCHEMA})

        with self.assertRaises(ModelError):
            GeminiModel(FakeSession(answer([{"text": "bukan json"}])), KEY).plan(INSTRUCTION)


if __name__ == "__main__":
    unittest.main()
