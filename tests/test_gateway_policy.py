import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import check_gateway  # noqa: E402
import render_ngrok_policy as policy_tool  # noqa: E402


USER = "ciel-gateway"
PASSWORD = "p" * 32
FLOW = "11111111-2222-3333-4444-555555555555"
ADMIN = "66666666-7777-8888-9999-000000000000"


def policy():
    return policy_tool.build_policy(USER, PASSWORD, FLOW, ADMIN)


def path_check(path):
    return f"(req.url.path == '{path}' && req.url.raw_path == '{path}')"


class BuildPolicyTest(unittest.TestCase):

    def test_rules_run_in_order(self):
        rules = policy()["on_http_request"]
        self.assertEqual(
            [rule["actions"][0]["type"] for rule in rules],
            ["rate-limit", "basic-auth", "custom-response", "rate-limit"],
        )
        # The broad limit and Basic Auth apply to every request.
        self.assertNotIn("expressions", rules[0])
        self.assertNotIn("expressions", rules[1])
        self.assertEqual(rules[0]["actions"][0]["config"]["capacity"], 120)
        self.assertEqual(rules[1]["actions"][0]["config"], {"credentials": [f"{USER}:{PASSWORD}"]})

    def test_only_the_paths_the_app_uses_are_allowed(self):
        deny = policy()["on_http_request"][2]
        self.assertEqual(deny["actions"][0]["config"], {"status_code": 404, "body": "Not found"})
        expression = deny["expressions"][0]
        # The app's secret may hold a flow ID with or without dashes.
        allowed = [
            ("POST", f"/api/v1/run/{FLOW}"),
            ("POST", f"/api/v1/run/{FLOW.replace('-', '')}"),
            ("POST", f"/api/v1/run/{ADMIN}"),
            ("POST", f"/api/v1/run/{ADMIN.replace('-', '')}"),
            ("POST", f"/api/v1/files/upload/{FLOW}"),
            ("POST", f"/api/v1/files/upload/{FLOW.replace('-', '')}"),
            ("GET", "/api/v1/monitor/messages/sessions"),
            ("DELETE", "/api/v1/monitor/messages/sessions"),
            ("GET", "/health_check"),
        ]
        self.assertEqual(
            expression,
            "!(" + " || ".join(f"(req.method == '{m}' && {path_check(p)})" for m, p in allowed) + ")",
        )
        # Exact flow IDs only: a prefix match would also open archived flows.
        self.assertNotIn("startsWith", expression)
        self.assertNotIn("/api/v1/flows", expression)

    def test_run_and_upload_keep_the_tight_per_ip_limit(self):
        rule = policy()["on_http_request"][3]
        config = rule["actions"][0]["config"]
        self.assertEqual((config["name"], config["capacity"], config["rate"]), ("ciel-api-per-ip", 20, "60s"))
        self.assertEqual(config["bucket_key"], ["conn.client_ip"])
        for path in (f"/api/v1/run/{FLOW}", f"/api/v1/run/{ADMIN.replace('-', '')}", f"/api/v1/files/upload/{FLOW}"):
            self.assertIn(path_check(path), rule["expressions"][0])
        self.assertNotIn("sessions", rule["expressions"][0])

    def test_flow_ids_without_dashes_give_the_same_policy(self):
        self.assertEqual(
            policy_tool.build_policy(USER, PASSWORD, FLOW.replace("-", ""), ADMIN.replace("-", "")),
            policy(),
        )

    def test_refuses_weak_or_missing_settings(self):
        cases = {
            "no user": ("", PASSWORD, FLOW, ADMIN),
            "no password": (USER, "", FLOW, ADMIN),
            "short password": (USER, "x" * 23, FLOW, ADMIN),
            "too long": (USER, "x" * 129, FLOW, ADMIN),
            "colon in user": ("a:b", PASSWORD, FLOW, ADMIN),
            "expression": (USER, "${req.url}" + "x" * 30, FLOW, ADMIN),
            "flow not uuid": (USER, PASSWORD, "flow-1", ADMIN),
            "admin missing": (USER, PASSWORD, FLOW, ""),
            "path in id": (USER, PASSWORD, FLOW + "/../flows", ADMIN),
        }
        for name, args in cases.items():
            with self.subTest(case=name), self.assertRaises(policy_tool.PolicyError):
                policy_tool.build_policy(*args)


class RenderMainTest(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.env = Path(self.folder.name) / ".env"
        self.out = Path(self.folder.name) / "policy.yml"

    def tearDown(self):
        self.folder.cleanup()

    def render(self, env_text):
        self.env.write_text(env_text, encoding="utf-8")
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.dict("os.environ", {}, clear=True), redirect_stdout(stdout), redirect_stderr(stderr):
            code = policy_tool.main(["--env-file", str(self.env), "--output", str(self.out)])
        return code, stdout.getvalue() + stderr.getvalue()

    def test_writes_json_from_env_without_printing_secrets(self):
        code, output = self.render(
            f"NGROK_USER={USER}\nNGROK_PASSWORD={PASSWORD}\nFLOW_ID={FLOW.upper()}\nMEMORY_ADMIN_FLOW_ID={ADMIN}\n"
        )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(self.out.read_text(encoding="utf-8")), policy())
        self.assertNotIn(PASSWORD, output)
        written = self.out.read_text(encoding="utf-8")
        self.assertNotIn("FLOW_ID", written)
        self.assertIn(FLOW, written)  # the ID from .env, lowercased

    def test_nothing_is_written_when_a_setting_is_missing(self):
        code, output = self.render(f"NGROK_USER={USER}\nNGROK_PASSWORD={PASSWORD}\nFLOW_ID={FLOW}\n")
        self.assertEqual(code, 1)
        self.assertIn("MEMORY_ADMIN_FLOW_ID", output)
        self.assertFalse(self.out.exists())
        self.assertNotIn(PASSWORD, output)


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


class CheckGatewayTest(unittest.TestCase):

    def run_probes(self, answer):
        calls = []

        def send(method, url, **kwargs):
            calls.append((method, url, kwargs))
            return answer(method, url, kwargs)

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            failures = check_gateway.run_probes("https://ciel.example", (USER, PASSWORD), FLOW, ADMIN, send=send)
        return failures, calls, stdout.getvalue()

    @staticmethod
    def locked(method, url, kwargs):
        path = url.removeprefix("https://ciel.example").split("?")[0]
        if kwargs["auth"] is None:
            return FakeResponse(401)
        if path == "/health_check":
            return FakeResponse(200)
        if path in (f"/api/v1/run/{FLOW}", f"/api/v1/run/{ADMIN}", "/api/v1/monitor/messages/sessions"):
            return FakeResponse(403)  # Langflow without an API key
        return FakeResponse(404)

    def test_locked_gateway_passes_without_sending_the_api_key(self):
        failures, calls, output = self.run_probes(self.locked)
        self.assertEqual(failures, 0)
        self.assertNotIn("FAIL", output)
        self.assertNotIn(PASSWORD, output)
        for _, _, kwargs in calls:
            self.assertNotIn("x-api-key", {k.lower() for k in kwargs["headers"]})

    def test_open_gateway_fails(self):
        def open_gateway(method, url, kwargs):
            return FakeResponse(401 if kwargs["auth"] is None else 200)

        failures, _, output = self.run_probes(open_gateway)
        self.assertGreaterEqual(failures, 6)
        self.assertIn("FAIL  GET    /api/v1/flows/", output)

    def test_blocking_a_path_the_app_needs_fails(self):
        def too_strict(method, url, kwargs):
            if kwargs["auth"] is None:
                return FakeResponse(401)
            return FakeResponse(200 if url.endswith("/health_check") else 404)

        failures, _, output = self.run_probes(too_strict)
        self.assertEqual(failures, 3)
        self.assertIn(f"FAIL  POST   /api/v1/run/{FLOW}", output)

    def test_connection_errors_count_as_failures(self):
        def down(method, url, kwargs):
            raise requests.exceptions.ConnectionError("tunnel down")

        failures, _, output = self.run_probes(down)
        self.assertEqual(failures, len(check_gateway.probes(FLOW, ADMIN)))
        self.assertIn("ConnectionError", output)


if __name__ == "__main__":
    unittest.main()
