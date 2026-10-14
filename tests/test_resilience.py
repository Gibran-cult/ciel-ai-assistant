import ast
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import requests


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def load_ask_langflow():
    source = APP_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    function_nodes = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in ("ask_langflow", "final_answer_text")
    ]

    namespace = {
        "requests": requests,
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

    return namespace["ask_langflow"]


ask_langflow = load_ask_langflow()


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
                    "Authentication gagal",
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
            "Request terlalu banyak",
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
            "Request timeout",
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
            "Tidak dapat terhubung",
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
