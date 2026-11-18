import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from agent_api.main import create_app  # noqa: E402
from agent_api.settings import load_settings  # noqa: E402
from tests.agent_fakes import MemoryStore  # noqa: E402
from tests.agent_service_fakes import ENV, Clock  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def app(settings):
    return TestClient(create_app(settings, store=MemoryStore(), models=None, google=None, clock=Clock()))


class SettingsTest(unittest.TestCase):
    def test_full_settings_load(self):
        settings, missing = load_settings(ENV)
        self.assertEqual(missing, [])
        self.assertEqual(settings.ticket_keys, (bytes.fromhex("11" * 32),))
        self.assertEqual(settings.device_redirects, frozenset({"https://abcdefghijklmnop.chromiumapp.org/", "ciel://auth"}))
        self.assertEqual(settings.switch_file, "/data/agent_off")
        self.assertEqual(settings.min_client_version, (0, 0, 0))
        self.assertIs(settings.agent.enabled, True)

    def test_missing_settings_are_named_without_values(self):
        settings, missing = load_settings({**ENV, "AGENT_CHAIN_KEY": "", "ANTHROPIC_API_KEY": ""})
        self.assertIsNone(settings)
        self.assertEqual(set(missing), {"AGENT_CHAIN_KEY", "ANTHROPIC_API_KEY"})

    def test_short_or_broken_keys_are_refused(self):
        for name, value in (("AGENT_CHAIN_KEY", "ab" * 31), ("AGENT_TICKET_KEY", "ab" * 31), ("AGENT_STATE_KEY", "zz" * 32),
                            ("AGENT_TICKET_KEY_OLD", "ab" * 33), ("AGENT_MIN_CLIENT_VERSION", "1.x")):
            with self.subTest(name=name):
                self.assertIn(name, load_settings({**ENV, name: value})[1])

    def test_an_old_ticket_key_is_kept_second(self):
        settings, _ = load_settings({**ENV, "AGENT_TICKET_KEY_OLD": "44" * 32, "AGENT_MIN_CLIENT_VERSION": "0.2.10"})
        self.assertEqual(settings.ticket_keys, (bytes.fromhex("11" * 32), bytes.fromhex("44" * 32)))
        self.assertEqual(settings.min_client_version, (0, 2, 10))

    def test_settings_never_raise(self):
        for env in ({}, {"AGENT_TICKET_KEY": None}, {"AGENT_WS_ORIGINS": 5}):
            settings, missing = load_settings(env)
            self.assertIsNone(settings)
            self.assertTrue(missing)


class ProductionAppTest(unittest.TestCase):
    def test_the_production_app_is_built_from_the_environment_without_network(self):
        from agent_api.main import build_app

        with patch("requests.Session.request") as request:
            client = TestClient(build_app(ENV))
            self.assertEqual(client.get("/healthz").json(), {"ok": True})
            self.assertEqual(len(client.get("/v1/ticket-keys").json()["keys"]), 1)
        request.assert_not_called()

        self.assertEqual(TestClient(build_app({})).get("/healthz").status_code, 503)

    def test_uvicorn_can_serve_websockets(self):
        import importlib.util

        self.assertIsNotNone(importlib.util.find_spec("websockets"), "uvicorn needs websockets to serve /v1/ws")


class HealthTest(unittest.TestCase):
    def test_healthz_is_ok_with_full_settings(self):
        response = app(load_settings(ENV)[0]).get("/healthz")
        self.assertEqual((response.status_code, response.json()), (200, {"ok": True}))

    def test_healthz_names_what_is_missing_without_values(self):
        settings, missing = load_settings({**ENV, "AGENT_CHAIN_KEY": ""})
        response = TestClient(create_app(None, store=None, models=None, google=None, clock=Clock(), missing=missing)).get("/healthz")
        self.assertEqual((response.status_code, response.json()), (503, {"ok": False, "missing": ["AGENT_CHAIN_KEY"]}))
        self.assertNotIn(ENV["SUPABASE_SERVICE_KEY"], response.text)

    def test_the_service_does_not_import_streamlit(self):
        code = "import sys, agent_api.main; print('streamlit' in sys.modules, 'app' in sys.modules)"
        done = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.stdout.strip(), "False False", done.stderr)


if __name__ == "__main__":
    unittest.main()
