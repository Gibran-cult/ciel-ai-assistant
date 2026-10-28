import copy
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import migrate_flows  # noqa: E402
from migrate_flows import MigrationError, importable, migrate, remap_run_flows, run_flow_targets  # noqa: E402


def run_flow_node(target):
    return {
        "id": f"RunFlow-{target}",
        "data": {
            "type": "RunFlow",
            "node": {"template": {"flow_id_selected": {"value": target}}},
        },
    }


def other_node():
    return {"id": "ChatInput-1", "data": {"type": "ChatInput", "node": {"template": {}}}}


def make_flow(flow_id, name, targets=()):
    return {
        "id": flow_id,
        "name": name,
        "description": "d",
        "user_id": "user-1",
        "folder_id": "folder-1",
        "updated_at": "2026-10-27T00:00:00",
        "webhook": False,
        "endpoint_name": name.lower().replace(" ", "-"),
        "is_component": False,
        "locked": False,
        "tags": [],
        "data": {"nodes": [other_node()] + [run_flow_node(t) for t in targets], "edges": []},
    }


MAIN = make_flow("main-old", "Ciel AI Long-Term Memory Master", ["math-old", "kb-old"])
MATH = make_flow("math-old", "Math Tutor Agent")
KB = make_flow("kb-old", "Knowledge Retriever")


def fake_response(payload):
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


class FakeLangflow(unittest.TestCase):
    """Patches requests.get/post: GET serves self.source, POST numbers new flows."""

    def setUp(self):
        self.source = {"main-old": MAIN, "math-old": MATH, "kb-old": KB}
        self.created = 0

        def fake_get(url, **kwargs):
            return fake_response(copy.deepcopy(self.source[url.rsplit("/", 1)[1]]))

        def fake_post(url, **kwargs):
            self.created += 1
            return fake_response({"id": f"new-{self.created}", "name": kwargs["json"]["name"]})

        get_patch = patch.object(migrate_flows.requests, "get", side_effect=fake_get)
        post_patch = patch.object(migrate_flows.requests, "post", side_effect=fake_post)
        self.get = get_patch.start()
        self.post = post_patch.start()
        self.addCleanup(get_patch.stop)
        self.addCleanup(post_patch.stop)

    def fail_post(self, number, error=None, body=""):
        """Make POST number `number` fail: raise_for_status raises `error`, or the
        call itself raises it when it is a KeyboardInterrupt (Ctrl+C mid-request)."""
        original = self.post.side_effect
        error = RuntimeError("500") if error is None else error

        def flaky(url, **kwargs):
            if self.post.call_count == number:
                if isinstance(error, KeyboardInterrupt):
                    raise error
                bad = fake_response({})
                bad.raise_for_status.side_effect = error
                bad.text = body
                return bad
            return original(url, **kwargs)

        self.post.side_effect = flaky

    def fail_second_post(self, error=None, body=""):
        self.fail_post(2, error, body)


class MigrateTests(FakeLangflow):
    def test_finds_run_flow_targets(self):
        self.assertEqual(run_flow_targets(MAIN), {"math-old", "kb-old"})

    def test_ignores_flows_without_run_flow_nodes_and_unset_targets(self):
        self.assertEqual(run_flow_targets(MATH), set())
        self.assertEqual(run_flow_targets(make_flow("x", "X", [""])), set())

    def test_remap_replaces_targets_and_leaves_input_untouched(self):
        out = remap_run_flows(MAIN, {"math-old": "math-new", "kb-old": "kb-new"})
        self.assertEqual(run_flow_targets(out), {"math-new", "kb-new"})
        self.assertEqual(run_flow_targets(MAIN), {"math-old", "kb-old"})

    def test_remap_refuses_unknown_target(self):
        with self.assertRaisesRegex(KeyError, "kb-old"):
            remap_run_flows(MAIN, {"math-old": "math-new"})

    def test_importable_drops_instance_specific_fields(self):
        out = importable(MAIN)
        for key in ("id", "user_id", "folder_id", "updated_at", "webhook", "endpoint_name"):
            self.assertNotIn(key, out)
        self.assertEqual(out["name"], MAIN["name"])
        self.assertIn("id", MAIN)

    def test_sub_flows_are_imported_before_the_flow_that_calls_them(self):
        id_map = migrate("http://src", "k1", "http://dst", "k2", ["main-old"])
        posted = [c.kwargs["json"]["name"] for c in self.post.call_args_list]
        self.assertLess(posted.index("Math Tutor Agent"), posted.index("Ciel AI Long-Term Memory Master"))
        self.assertLess(posted.index("Knowledge Retriever"), posted.index("Ciel AI Long-Term Memory Master"))
        self.assertEqual(set(id_map), {"main-old", "math-old", "kb-old"})

    def test_imported_flows_carry_no_source_ids(self):
        migrate("http://src", "k1", "http://dst", "k2", ["main-old"])
        for call in self.post.call_args_list:
            self.assertFalse({"id", "user_id", "folder_id"} & set(call.kwargs["json"]))

    def test_imported_main_flow_points_at_the_new_sub_flows(self):
        id_map = migrate("http://src", "k1", "http://dst", "k2", ["main-old"])
        main_body = next(c.kwargs["json"] for c in self.post.call_args_list if c.kwargs["json"]["name"] == MAIN["name"])
        self.assertEqual(run_flow_targets(main_body), {id_map["math-old"], id_map["kb-old"]})

    def test_each_server_gets_its_own_key_and_urls_are_normalised(self):
        migrate("http://src/", "k1", "http://dst/", "k2", ["main-old"])
        for call in self.get.call_args_list:
            self.assertTrue(call.args[0].startswith("http://src/api/v1/flows/"))
            self.assertEqual(call.kwargs["headers"]["x-api-key"], "k1")
            self.assertIn("timeout", call.kwargs)
        for call in self.post.call_args_list:
            self.assertEqual(call.args[0], "http://dst/api/v1/flows/")
            self.assertEqual(call.kwargs["headers"]["x-api-key"], "k2")
            self.assertIn("timeout", call.kwargs)

    def test_shared_sub_flow_is_exported_and_imported_once(self):
        self.source["other-old"] = make_flow("other-old", "Other", ["math-old"])
        migrate("http://src", "k1", "http://dst", "k2", ["main-old", "other-old"])
        posted = [c.kwargs["json"]["name"] for c in self.post.call_args_list]
        self.assertEqual(posted.count("Math Tutor Agent"), 1)

    def test_circular_run_flow_references_are_refused(self):
        self.source["a-old"] = make_flow("a-old", "A", ["b-old"])
        self.source["b-old"] = make_flow("b-old", "B", ["a-old"])
        with self.assertRaisesRegex(ValueError, "a-old"):
            migrate("http://src", "k1", "http://dst", "k2", ["a-old"])
        self.post.assert_not_called()

    def test_failed_import_reports_the_flows_already_created(self):
        self.fail_second_post()
        with self.assertRaises(MigrationError) as caught:
            migrate("http://src", "k1", "http://dst", "k2", ["main-old"])
        self.assertEqual(caught.exception.partial, {"kb-old": "new-1"})
        self.assertIsInstance(caught.exception.__cause__, RuntimeError)
        self.assertEqual(self.post.call_count, 2)

    def test_interrupted_import_reports_the_flows_already_created(self):
        self.fail_second_post(KeyboardInterrupt())
        with self.assertRaises(MigrationError) as caught:
            migrate("http://src", "k1", "http://dst", "k2", ["main-old"])
        self.assertEqual(caught.exception.partial, {"kb-old": "new-1"})
        self.assertIsInstance(caught.exception.__cause__, KeyboardInterrupt)
        self.assertIn("interrupted", str(caught.exception))

    def test_http_error_names_the_status_and_a_truncated_body(self):
        self.fail_second_post(requests.HTTPError("422 Client Error: Unprocessable Entity"), body="e" * 1000)
        with self.assertRaises(MigrationError) as caught:
            migrate("http://src", "k1", "http://dst", "k2", ["main-old"])
        message = str(caught.exception)
        self.assertIn("422", message)
        self.assertIn("e" * 500, message)
        self.assertNotIn("e" * 501, message)

    def test_export_http_error_includes_the_body(self):
        def bad_get(url, **kwargs):
            response = fake_response({})
            response.raise_for_status.side_effect = requests.HTTPError("404 Client Error: Not Found")
            response.text = '{"detail":"Flow not found"}'
            return response

        self.get.side_effect = bad_get
        with self.assertRaisesRegex(requests.HTTPError, "Flow not found"):
            migrate("http://src", "k1", "http://dst", "k2", ["main-old"])
        self.post.assert_not_called()


class CliTests(FakeLangflow):
    def run_main(self, *extra, env=None):
        args = ["--source-url", "http://src", "--target-url", "http://dst", "--flow-id", "main-old", *extra]
        env = {"SOURCE_LANGFLOW_API_KEY": "k1", "TARGET_LANGFLOW_API_KEY": "k2"} if env is None else env
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(migrate_flows.os.environ, env, clear=True), \
                patch.object(migrate_flows, "load_env_file"), \
                redirect_stdout(out), redirect_stderr(err):
            code = migrate_flows.main(args)
        return code, out.getvalue(), err.getvalue()

    def test_map_out_holds_the_id_map_and_no_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "map.json"
            code, _, _ = self.run_main("--map-out", str(path))
            text = path.read_text(encoding="utf-8")
        self.assertEqual(code, 0)
        self.assertEqual(set(json.loads(text)), {"main-old", "math-old", "kb-old"})
        self.assertNotIn("k1", text)
        self.assertNotIn("k2", text)

    def test_snapshot_dir_gets_only_the_run_flow_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, _ = self.run_main("--snapshot-dir", tmp)
            files = sorted(p.name for p in Path(tmp).iterdir())
            raw = (Path(tmp) / "Math_Tutor_Agent.json").read_bytes()
        self.assertEqual(code, 0)
        self.assertEqual(files, ["Knowledge_Retriever.json", "Math_Tutor_Agent.json"])
        self.assertTrue(raw.endswith(b"}\n"))
        self.assertNotIn(b"\r", raw)
        self.assertIn(b'\n  "name": "Math Tutor Agent"', raw)
        snapshot = json.loads(raw)
        self.assertNotIn("id", snapshot)
        self.assertNotIn("user_id", snapshot)

    def test_missing_api_key_is_a_usage_error(self):
        with self.assertRaises(SystemExit), patch("sys.stderr", new_callable=io.StringIO):
            self.run_main(env={"SOURCE_LANGFLOW_API_KEY": "k1"})
        self.post.assert_not_called()

    def test_partial_migration_exits_1_and_keeps_the_partial_map(self):
        self.fail_second_post()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "map.json"
            code, out, err = self.run_main("--map-out", str(path))
            written = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(code, 1)
        self.assertEqual(written, {"kb-old": "new-1"})
        self.assertIn("kb-old -> new-1", out)
        self.assertIn("partially migrated", err)
        self.assertIn("new-1", err)
        for text in (out, err):
            self.assertNotIn("k1", text)
            self.assertNotIn("k2", text)

    def test_ctrl_c_during_imports_exits_non_zero_with_the_partial_map(self):
        self.fail_second_post(KeyboardInterrupt())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "map.json"
            code, out, err = self.run_main("--map-out", str(path))
            written = json.loads(path.read_text(encoding="utf-8"))
        self.assertNotEqual(code, 0)
        self.assertEqual(written, {"kb-old": "new-1"})
        self.assertIn("kb-old -> new-1", out)
        self.assertIn("partially migrated", err)

    def test_first_import_failure_says_nothing_was_created(self):
        self.fail_post(1)
        code, out, err = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("Nothing was created", err)
        self.assertNotIn("partially migrated", err)
        self.assertNotIn("->", out)


if __name__ == "__main__":
    unittest.main()
