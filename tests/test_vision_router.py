import asyncio
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import requests


SOURCE = (Path(__file__).resolve().parents[1] / "flow" / "components" / "ciel_vision_router.py").read_text(encoding="utf-8")
IMAGE = {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,QUJD"}}
KEY = "test-key-not-real"


class FakeOllama:
    calls = 0

    def __init__(self, **kwargs):
        pass

    async def ainvoke(self, messages):
        FakeOllama.calls += 1
        return types.SimpleNamespace(content="bacaan model lokal")


def install_stubs():
    class Component:
        def __init__(self, **inputs):
            self.__dict__.update(inputs)
            self.status = None

    class Message:
        def __init__(self, text="", **kwargs):
            self.text = text
            self.files = kwargs.get("files", [])

    def spec(*args, **kwargs):
        return kwargs

    modules = {name: types.ModuleType(name) for name in (
        "langflow", "langflow.custom", "langflow.io", "langflow.schema", "langflow.schema.message",
        "langchain_core", "langchain_core.messages", "langchain_ollama",
    )}
    modules["langflow.custom"].Component = Component
    for name in ("IntInput", "MessageInput", "MessageTextInput", "MultilineInput", "Output", "SecretStrInput"):
        setattr(modules["langflow.io"], name, spec)
    modules["langflow.schema.message"].Message = Message
    modules["langchain_core.messages"].HumanMessage = lambda content: content
    modules["langchain_core.messages"].SystemMessage = lambda content: content
    modules["langchain_ollama"].ChatOllama = FakeOllama
    added = [name for name in modules if name not in sys.modules]
    for name in added:
        sys.modules[name] = modules[name]
    return lambda: [sys.modules.pop(name, None) for name in added]


def gemini_response(status=200, text="bacaan Gemini"):
    response = requests.Response()
    response.status_code = status
    response._content = (
        b'{"candidates": [{"content": {"parts": [{"text": "dipikirkan", "thought": true}, {"text": "%s"}]}}]}'
        % text.encode()
    )
    return response


class VisionRouterTest(unittest.TestCase):

    def setUp(self):
        uninstall = install_stubs()
        try:
            self.ns = {}
            exec(compile(SOURCE, "ciel_vision_router", "exec"), self.ns)
            self.Message = sys.modules["langflow.schema.message"].Message
        finally:
            uninstall()
        FakeOllama.calls = 0

    def router(self, key="", images=(IMAGE,), fallback="gemini-3.5-flash-lite"):
        router = self.ns["CielVisionRouter"](
            message=self.Message("Hitung limitnya"), model_name="qwen2.5vl:3b", base_url="http://127.0.0.1:11434",
            system_prompt="SYS", instruction="Baca gambar", num_ctx=4096,
            vision_api_key=key, api_model="gemini-3.1-flash-lite", api_fallback_model=fallback, api_timeout=20,
        )
        router._image_contents = lambda message: list(images)
        return router

    def run_route(self, router):
        return asyncio.run(router.route())

    def test_text_only_messages_skip_both_engines(self):
        with patch.object(self.ns["requests"], "post") as post:
            result = self.run_route(self.router(key=KEY, images=()))
        post.assert_not_called()
        self.assertEqual(result.text, "Hitung limitnya")
        self.assertEqual(FakeOllama.calls, 0)

    def test_api_reads_the_image_when_a_key_is_set(self):
        with patch.object(self.ns["requests"], "post", return_value=gemini_response()) as post:
            result = self.run_route(self.router(key=KEY))
        self.assertIn("bacaan Gemini", result.text)
        self.assertNotIn("dipikirkan", result.text)
        self.assertEqual(FakeOllama.calls, 0)
        url = post.call_args.args[0]
        body = post.call_args.kwargs["json"]
        self.assertIn("gemini-3.1-flash-lite:generateContent", url)
        self.assertEqual(post.call_args.kwargs["headers"], {"x-goog-api-key": KEY})
        self.assertEqual(body["contents"][0]["parts"][1], {"inline_data": {"mime_type": "image/jpeg", "data": "QUJD"}})
        self.assertEqual(post.call_args.kwargs["timeout"], 20)

    def test_api_error_falls_back_to_the_local_model_without_leaking_the_key(self):
        with patch.object(self.ns["requests"], "post", return_value=gemini_response(status=403)):
            router = self.router(key=KEY)
            result = self.run_route(router)
        self.assertIn("bacaan model lokal", result.text)
        self.assertEqual(FakeOllama.calls, 1)
        self.assertIn("gemini-3.1-flash-lite: RuntimeError: HTTP 403", router.status)
        self.assertIn("gemini-3.5-flash-lite: RuntimeError: HTTP 403", router.status)
        self.assertNotIn(KEY, router.status + result.text)

    def test_backup_model_reads_the_image_when_the_main_model_is_unavailable(self):
        # Production 2026-10-18: the main model answered HTTP 503 for a while.
        with patch.object(self.ns["requests"], "post", side_effect=[gemini_response(status=503), gemini_response()]) as post:
            router = self.router(key=KEY)
            result = self.run_route(router)
        self.assertIn("bacaan Gemini", result.text)
        self.assertEqual(FakeOllama.calls, 0)
        self.assertEqual([c.args[0].split("/models/")[1] for c in post.call_args_list],
                         ["gemini-3.1-flash-lite:generateContent", "gemini-3.5-flash-lite:generateContent"])
        self.assertEqual(router.status, "1 gambar dibaca lewat gemini-3.5-flash-lite.")

    def test_same_main_and_backup_model_is_tried_once(self):
        with patch.object(self.ns["requests"], "post", return_value=gemini_response(status=503)) as post:
            self.run_route(self.router(key=KEY, fallback="gemini-3.1-flash-lite"))
        self.assertEqual(post.call_count, 1)
        self.assertEqual(FakeOllama.calls, 1)

    def test_api_timeout_falls_back_to_the_local_model(self):
        with patch.object(self.ns["requests"], "post", side_effect=requests.Timeout("lambat")):
            result = self.run_route(self.router(key=KEY))
        self.assertIn("bacaan model lokal", result.text)

    def test_without_a_key_only_the_local_model_runs(self):
        with patch.object(self.ns["requests"], "post") as post:
            result = self.run_route(self.router(key=""))
        post.assert_not_called()
        self.assertIn("bacaan model lokal", result.text)

    def test_gemini_parts_rejects_non_base64_images(self):
        with self.assertRaises(ValueError):
            self.ns["gemini_parts"]([{"type": "image_url", "image_url": {"url": "https://example.com/a.jpg"}}])

    def test_empty_gemini_answer_is_an_error(self):
        with self.assertRaises(ValueError):
            self.ns["gemini_text"]({"candidates": [{"content": {"parts": []}}]})


if __name__ == "__main__":
    unittest.main()
