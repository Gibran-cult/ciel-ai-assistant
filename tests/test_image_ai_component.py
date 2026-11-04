"""Ciel Image AI component: request parsing, DeepSeek payload, reply handling. No network."""

import asyncio
import base64
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

SOURCE = (Path(__file__).resolve().parents[1] / "flow" / "components" / "ciel_image_ai.py").read_text(encoding="utf-8")
KEY = "sk-test-key-not-real-0000"


def install_stubs():
    class Component:
        def __init__(self, **inputs):
            self.__dict__.update(inputs)
            self.status = None

    class Message:
        def __init__(self, text="", **kwargs):
            self.text = text

    def spec(*args, **kwargs):
        return kwargs

    modules = {name: types.ModuleType(name) for name in (
        "langflow", "langflow.custom", "langflow.io", "langflow.schema", "langflow.schema.message",
    )}
    modules["langflow.custom"].Component = Component
    for name in ("MessageTextInput", "Output", "SecretStrInput"):
        setattr(modules["langflow.io"], name, spec)
    modules["langflow.schema.message"].Message = Message
    added = [name for name in modules if name not in sys.modules]
    for name in added:
        sys.modules[name] = modules[name]
    return lambda: [sys.modules.pop(name, None) for name in added]


def base64_of(size):
    return base64.b64encode(b"\xff" * size).decode()


def edit_request(instruction="lingkari jawaban nomor 3"):
    return json.dumps({"mode": "edit", "instruction": instruction, "image": base64_of(30), "width": 1200, "height": 900})


def response(status=200, content="{}"):
    resp = requests.Response()
    resp.status_code = status
    resp._content = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
    return resp


class ImageAIComponentTest(unittest.TestCase):

    def setUp(self):
        uninstall = install_stubs()
        try:
            self.ns = {}
            exec(compile(SOURCE, "ciel_image_ai", "exec"), self.ns)
        finally:
            uninstall()

    def __getattr__(self, name):
        if name in ("parse_request", "build_payload", "reply_text", "call_deepseek"):
            return self.ns[name]
        raise AttributeError(name)

    def component(self, text):
        return self.ns["CielImageAI"](input_value=text, api_key=KEY, api_base="https://api.deepseek.com",
                                      model_name="deepseek-flash")

    def test_edit_payload_puts_the_image_in_the_user_message(self):
        payload = self.build_payload(self.parse_request(edit_request()), "deepseek-flash")
        self.assertEqual(payload["model"], "deepseek-flash")
        self.assertEqual(payload["thinking"], {"type": "disabled"})
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertEqual((payload["temperature"], payload["max_tokens"]), (0.2, 1500))
        system, user = payload["messages"]
        self.assertEqual((system["role"], user["role"]), ("system", "user"))
        self.assertIsInstance(system["content"], str)
        self.assertEqual(user["content"][1]["image_url"]["url"][:23], "data:image/jpeg;base64,")
        self.assertEqual(user["content"][1]["image_url"]["detail"], "high")
        self.assertIn("lingkari jawaban nomor 3", user["content"][0]["text"])
        self.assertIn("1200x900", user["content"][0]["text"])
        for op in ("blur", "adjust", "grayscale", "document", "mark", "arrow", "text",
                   "crop", "straighten", "rotate", "flip", "resize"):
            self.assertIn(f"- {op}: ", system["content"])
        self.assertIn('{"ops": [], "catatan": "..."}', system["content"])

    def test_edit_prompt_names_every_op_the_app_accepts(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import image_edit
        prompt = self.ns["EDIT_SYSTEM_PROMPT"]
        for op in image_edit.OPS:
            self.assertIn(f'{{"op": "{op}"', prompt)

    def test_illustration_payload_has_no_image_and_no_json_mode(self):
        payload = self.build_payload(self.parse_request(json.dumps({"mode": "ilustrasi", "instruction": "siklus air"})),
                                     "deepseek-flash")
        system, user = payload["messages"]
        self.assertIsInstance(user["content"], str)
        self.assertIn("siklus air", user["content"])
        self.assertNotIn("response_format", payload)
        self.assertEqual((payload["temperature"], payload["max_tokens"]), (0.7, 8000))
        self.assertEqual(payload["thinking"], {"type": "disabled"})
        for piece in ("polygon", "TOLAK:", 'viewBox="0 0 800 600"', "font-size minimal 22", "300 elemen"):
            self.assertIn(piece, system["content"])

    def test_illustration_prompt_lists_exactly_the_cleaner_allowlist(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import illustration
        prompt = self.ns["ILLUSTRATION_SYSTEM_PROMPT"]
        elements = next(line for line in prompt.splitlines() if "Elemen yang boleh:" in line)
        attributes = next(line for line in prompt.splitlines() if "Atribut yang boleh:" in line)
        listed = lambda line: {w.strip(" .") for w in line.split(":", 1)[1].split(",")}
        self.assertEqual(listed(elements), set(illustration.ALLOWED_ELEMENTS))
        self.assertEqual(listed(attributes), set(illustration.ALLOWED_ATTRIBUTES))

    def test_parse_request_rejects_bad_input(self):
        for bad in ("", "{}", "[]", "bukan json", '{"mode": "paint", "instruction": "x"}',
                    json.dumps({"mode": "edit", "instruction": "x" * 301}),
                    json.dumps({"mode": "ilustrasi", "instruction": "   "}),
                    json.dumps({"mode": "edit", "instruction": "ok"}),
                    json.dumps({"mode": "edit", "instruction": "ok", "image": "@@@", "width": 10, "height": 10}),
                    json.dumps({"mode": "edit", "instruction": "ok", "image": base64_of(1_600_000), "width": 10, "height": 10}),
                    json.dumps({"mode": "edit", "instruction": "ok", "image": base64_of(30), "width": "10", "height": 10}),
                    json.dumps({"mode": "edit", "instruction": "ok", "image": base64_of(30), "width": True, "height": 10}),
                    json.dumps({"mode": "edit", "instruction": "ok", "image": base64_of(30), "width": 0, "height": 10})):
            with self.subTest(bad=bad[:60]), self.assertRaises(ValueError):
                self.parse_request(bad)

    def test_parse_request_accepts_the_limits(self):
        request = self.parse_request(json.dumps({"mode": "edit", "instruction": "x" * 300,
                                                 "image": base64_of(1_500_000), "width": 10, "height": 10}))
        self.assertEqual(len(request["instruction"]), 300)

    def test_reply_that_is_not_json_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "^Ciel image AI unavailable"):
            self.reply_text({"choices": [{"message": {"content": "Tentu! Berikut langkahnya..."}}]}, "edit")
        for broken in ({}, {"choices": []}, {"choices": [{"message": {"content": "  "}}]}, {"choices": [{"message": {}}]}):
            with self.subTest(broken=broken), self.assertRaisesRegex(ValueError, "^Ciel image AI unavailable"):
                self.reply_text(broken, "ilustrasi")
        with self.assertRaisesRegex(ValueError, "^Ciel image AI unavailable"):
            self.reply_text({"choices": [{"message": {"content": "[1, 2]"}}]}, "edit")

    def test_edit_reply_is_normalized_json(self):
        content = json.dumps({"ops": [{"op": "grayscale"}], "catatan": "x" * 400, "extra": 1})
        out = json.loads(self.reply_text({"choices": [{"message": {"content": content}}]}, "edit"))
        self.assertEqual(out["ops"], [{"op": "grayscale"}])
        self.assertEqual(len(out["catatan"]), 160)
        self.assertNotIn("extra", out)
        out = json.loads(self.reply_text({"choices": [{"message": {"content": '{"ops": "lol"}'}}]}, "edit"))
        self.assertEqual(out, {"ops": [], "catatan": ""})

    def test_illustration_reply_is_passed_through(self):
        svg = '<svg viewBox="0 0 800 600"><rect x="1" y="1" width="5" height="5"/></svg>'
        self.assertEqual(self.reply_text({"choices": [{"message": {"content": f"\n{svg}\n"}}]}, "ilustrasi"), svg)
        self.assertEqual(self.reply_text({"choices": [{"message": {"content": "TOLAK: maaf"}}]}, "ilustrasi"), "TOLAK: maaf")

    def test_http_402_and_timeout_become_unavailable(self):
        requests_mod = self.ns["requests"]
        for side_effect in (response(status=402), response(status=503), requests.Timeout(f"slow {KEY}"),
                            requests.ConnectionError(f"down {KEY}")):
            kwargs = {"return_value": side_effect} if isinstance(side_effect, requests.Response) else {"side_effect": side_effect}
            with self.subTest(case=repr(side_effect)[:40]), patch.object(requests_mod, "post", **kwargs):
                with self.assertRaises(ValueError) as caught:
                    asyncio.run(self.component(edit_request()).reply())
                message = str(caught.exception)
                self.assertTrue(message.startswith("Ciel image AI unavailable"), message)
                self.assertNotIn(KEY, message)
        with patch.object(requests_mod, "post", return_value=response(status=402)):
            with self.assertRaisesRegex(ValueError, "HTTP 402"):
                asyncio.run(self.component(edit_request()).reply())

    def test_successful_edit_calls_deepseek_once_with_the_key_in_the_header(self):
        content = json.dumps({"ops": [{"op": "mark", "shape": "ellipse", "box": [0.1, 0.1, 0.3, 0.2]}], "catatan": "Sudah dilingkari."})
        with patch.object(self.ns["requests"], "post", return_value=response(content=content)) as post:
            message = asyncio.run(self.component(edit_request()).reply())
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.args[0], "https://api.deepseek.com/chat/completions")
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], f"Bearer {KEY}")
        self.assertEqual(post.call_args.kwargs["timeout"], 60)
        self.assertEqual(json.loads(message.text)["catatan"], "Sudah dilingkari.")

    def test_bad_request_never_calls_deepseek(self):
        with patch.object(self.ns["requests"], "post") as post:
            with self.assertRaises(ValueError):
                asyncio.run(self.component('{"mode": "paint"}').reply())
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
