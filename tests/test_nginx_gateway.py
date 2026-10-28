import base64
import hashlib
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import render_nginx_gateway as nginx_tool  # noqa: E402
from render_ngrok_policy import allowed_requests  # noqa: E402


USER = "ciel-gateway"
PASSWORD = "p" * 32
FLOW = "11111111-2222-3333-4444-555555555555"
ADMIN = "66666666-7777-8888-9999-000000000000"
RESEARCH = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def build(*args, **kwargs):
    return nginx_tool.build_nginx_config(USER, PASSWORD, *args, **kwargs)


class BuildNginxConfigTest(unittest.TestCase):

    def test_every_allowed_path_has_an_exact_location(self):
        conf = build(FLOW, ADMIN)
        for _, path in allowed_requests(FLOW, ADMIN):
            self.assertIn(f"location = {path} {{", conf)
        self.assertIn("location / {\n        return 404;", conf)

    def test_sessions_path_allows_get_and_delete_only(self):
        self.assertRegex(
            build(FLOW, ADMIN),
            r"location = /api/v1/monitor/messages/sessions \{\s+limit_except GET DELETE",
        )

    def test_langflow_receives_the_normalized_path(self):
        conf = build(FLOW, ADMIN)
        self.assertNotIn("$request_uri", conf)
        self.assertEqual(
            conf.count("proxy_pass http://langflow_backend$uri$is_args$args;"),
            len({path for _, path in allowed_requests(FLOW, ADMIN)}),
        )

    def test_upstream_follows_langflows_address_after_a_restart(self):
        # a recreated or restarted langflow container can get a new IP: the upstream
        # re-resolves it through Docker's DNS instead of keeping the start-up address
        conf = build(FLOW, ADMIN)
        self.assertIn("resolver 127.0.0.11 valid=10s ipv6=off;", conf)
        self.assertIn(
            "upstream langflow_backend { zone langflow_backend 64k; server langflow:7860 resolve; }",
            conf,
        )
        # http-context directives: before the server block, the resolver before the upstream
        self.assertLess(conf.index("resolver "), conf.index("upstream langflow_backend"))
        self.assertLess(conf.index("upstream langflow_backend"), conf.index("server {"))
        self.assertNotIn("proxy_pass http://langflow:", conf)

    def test_gateway_basic_auth_never_reaches_langflow(self):
        conf = build(FLOW, ADMIN)
        blocks = [block.split("\n    }", 1)[0] for block in conf.split("    location = ")[1:]]
        self.assertTrue(blocks)
        for block in blocks:
            self.assertIn("proxy_pass ", block)
            self.assertIn('proxy_set_header Authorization "";', block)
        self.assertEqual(conf.count('proxy_set_header Authorization "";'), conf.count("proxy_pass "))

    def test_long_research_requests_are_not_cut(self):
        self.assertIn("proxy_read_timeout 600s;", build(FLOW, ADMIN))  # > RESEARCH_TIMEOUT 420

    def test_rate_limits_key_on_the_client_ip_caddy_forwards(self):
        conf = build(FLOW, ADMIN)
        self.assertIn("limit_req_zone $http_x_forwarded_for zone=ciel_all:10m rate=300r/m;", conf)
        self.assertIn("limit_req_zone $http_x_forwarded_for zone=ciel_api:10m rate=60r/m;", conf)
        self.assertIn("limit_req zone=ciel_all burst=60 nodelay;", conf)

    def test_run_limit_defaults_to_60_per_minute_and_is_configurable(self):
        self.assertIn("zone=ciel_api:10m rate=60r/m", build(FLOW, ADMIN))
        self.assertIn("zone=ciel_api:10m rate=90r/m", build(FLOW, ADMIN, run_per_minute=90))
        self.assertIn("zone=ciel_all:10m rate=500r/m", build(FLOW, ADMIN, all_per_minute=500))

    def test_costly_paths_get_the_api_limit_and_others_do_not(self):
        conf = build(FLOW, ADMIN)
        for _, path in allowed_requests(FLOW, ADMIN):
            block = conf.split(f"location = {path} {{", 1)[1].split("\n    }", 1)[0]
            costly = path.startswith(("/api/v1/run/", "/api/v1/files/upload/"))
            self.assertEqual("limit_req zone=ciel_api burst=20 nodelay;" in block, costly, path)
            # nginx drops the server-level limit_req once a location sets its own
            self.assertEqual("limit_req zone=ciel_all burst=60 nodelay;" in block, costly, path)

    def test_server_level_protection(self):
        conf = build(FLOW, ADMIN)
        for line in (
            "listen 8080;",
            "auth_basic_user_file /etc/nginx/ciel.htpasswd;",
            "client_max_body_size 30m;",
            "proxy_send_timeout 600s;",
        ):
            self.assertIn(line, conf)
        self.assertRegex(conf, r'auth_basic\s+"[^"]+";')
        # the zones are http-context directives: they must sit before the server block
        self.assertLess(conf.index("limit_req_zone"), conf.index("server {"))

    def test_optional_flows_only_when_configured(self):
        self.assertNotIn(RESEARCH, build(FLOW, ADMIN))
        self.assertIn(f"location = /api/v1/run/{RESEARCH} {{", build(FLOW, ADMIN, research_flow_id=RESEARCH))

    def test_weak_settings_raise(self):
        with self.assertRaises(nginx_tool.PolicyError):
            nginx_tool.build_nginx_config(USER, "short", FLOW, ADMIN)
        with self.assertRaises(nginx_tool.PolicyError):
            nginx_tool.build_nginx_config(USER, PASSWORD, "not-a-uuid", ADMIN)

    def test_config_never_contains_the_password(self):
        self.assertNotIn(PASSWORD, build(FLOW, ADMIN))


class HtpasswdTest(unittest.TestCase):

    def test_htpasswd_is_nginx_ssha(self):
        line = nginx_tool.htpasswd_line("ciel", "p" * 32, b"12345678")
        user, hashed = line.split(":", 1)
        self.assertEqual(user, "ciel")
        self.assertTrue(hashed.startswith("{SSHA}"))
        raw = base64.b64decode(hashed.removeprefix("{SSHA}"))
        self.assertEqual(raw, hashlib.sha1(b"p" * 32 + b"12345678").digest() + b"12345678")


class MainTest(unittest.TestCase):

    def run_main(self, env, env_file_text=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        conf, htpasswd = Path(tmp.name) / "ciel.conf", Path(tmp.name) / "ciel.htpasswd"
        env_file = Path(tmp.name) / ("deploy.env" if env_file_text is not None else "missing.env")
        if env_file_text is not None:
            env_file.write_text(env_file_text, encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        with patch.dict("os.environ", env, clear=True), redirect_stdout(out), redirect_stderr(err):
            code = nginx_tool.main([
                "--env-file", str(env_file),
                "--conf-out", str(conf),
                "--htpasswd-out", str(htpasswd),
            ])
        return code, conf, htpasswd, out.getvalue() + err.getvalue()

    def env(self, **overrides):
        values = {
            "NGROK_USER": USER,
            "NGROK_PASSWORD": PASSWORD,
            "FLOW_ID": FLOW,
            "MEMORY_ADMIN_FLOW_ID": ADMIN,
        }
        values.update(overrides)
        return values

    def test_writes_both_files_and_prints_no_secret(self):
        code, conf, htpasswd, output = self.run_main(self.env())
        self.assertEqual(code, 0)
        self.assertIn("location = /health_check {", conf.read_text(encoding="utf-8"))
        self.assertTrue(htpasswd.read_text(encoding="utf-8").startswith(f"{USER}:{{SSHA}}"))
        self.assertNotIn(PASSWORD, output)
        self.assertNotIn(PASSWORD, htpasswd.read_text(encoding="utf-8"))

    def test_rate_limits_come_from_the_environment(self):
        code, conf, _, _ = self.run_main(self.env(GATEWAY_RUN_PER_MINUTE="90", GATEWAY_ALL_PER_MINUTE="500"))
        self.assertEqual(code, 0)
        text = conf.read_text(encoding="utf-8")
        self.assertIn("zone=ciel_api:10m rate=90r/m", text)
        self.assertIn("zone=ciel_all:10m rate=500r/m", text)

    def test_weak_settings_write_nothing(self):
        code, conf, htpasswd, output = self.run_main(self.env(NGROK_PASSWORD="short"))
        self.assertEqual(code, 1)
        self.assertFalse(conf.exists())
        self.assertFalse(htpasswd.exists())
        self.assertNotIn("short", output)

    def test_an_explicit_env_file_wins_over_the_environment(self):
        # README re-renders after `set -a; . ./.env`: a stale exported FLOW_ID must not win
        stale = "99999999-9999-9999-9999-999999999999"
        env_file = "".join(f"{k}={v}\n" for k, v in self.env().items())
        code, conf, _, output = self.run_main(self.env(FLOW_ID=stale), env_file_text=env_file)
        self.assertEqual(code, 0)
        text = conf.read_text(encoding="utf-8")
        self.assertIn(f"location = /api/v1/run/{FLOW}", text)
        self.assertNotIn(stale, text)
        self.assertNotIn(stale, output)

    def test_a_name_left_empty_in_the_env_file_is_not_taken_from_the_environment(self):
        # .env no longer uses the writer flow, the shell still exports an old one
        stale = "99999999-9999-9999-9999-999999999999"
        env_file = "".join(f"{k}={v}\n" for k, v in self.env().items()) + "WRITER_FLOW_ID=\n"
        code, conf, _, output = self.run_main(self.env(WRITER_FLOW_ID=stale), env_file_text=env_file)
        self.assertEqual(code, 0)
        self.assertNotIn(stale, conf.read_text(encoding="utf-8"))
        self.assertIn("WRITER_FLOW_ID=-", output)

    def test_without_env_file_flag_the_environment_still_wins(self):
        # the default lookup keeps render_ngrok_policy.load_settings' precedence
        calls = []

        def fake_load_settings(env_file):
            calls.append(env_file)
            return self.env()

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        conf = Path(tmp.name) / "ciel.conf"
        with patch.object(nginx_tool, "load_settings", fake_load_settings), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = nginx_tool.main(["--conf-out", str(conf), "--htpasswd-out", str(Path(tmp.name) / "h")])
        self.assertEqual(code, 0)
        self.assertEqual(calls, [nginx_tool.ROOT / ".env"])

    def test_prints_the_flow_ids_it_used(self):
        code, _, _, output = self.run_main(self.env(RESEARCH_FLOW_ID=RESEARCH))
        self.assertEqual(code, 0)
        self.assertIn(f"FLOW_ID={FLOW}", output)
        self.assertIn(f"MEMORY_ADMIN_FLOW_ID={ADMIN}", output)
        self.assertIn(f"RESEARCH_FLOW_ID={RESEARCH}", output)
        self.assertIn("WRITER_FLOW_ID=-", output)
        self.assertNotIn(PASSWORD, output)

    def test_bad_rate_limit_writes_nothing(self):
        code, conf, htpasswd, _ = self.run_main(self.env(GATEWAY_RUN_PER_MINUTE="banyak"))
        self.assertEqual(code, 1)
        self.assertFalse(conf.exists())
        self.assertFalse(htpasswd.exists())


if __name__ == "__main__":
    unittest.main()
