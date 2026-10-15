import ast
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import requests

from tests.test_flow_v141_contract import (
    RESERVED_COMPONENT_ATTRIBUTES,
    compile_class,
    input_names,
    install_langflow_stub,
)


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
COMPONENT = ROOT / "flow" / "components" / "ciel_memory_admin.py"
ADMIN_FLOW = ROOT / "flow" / "memory_admin" / "Ciel_Memory_Admin.json"
ALICE = "aaaa1111aaaa1111"
BOB = "bbbb2222bbbb2222"


def load_app_functions(names, **namespace):
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(APP_PATH), "exec"), namespace)
    return namespace


class Response:
    def __init__(self, data=None, status_code=200):
        self.data, self.status_code = data, status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"{self.status_code}")

    def json(self):
        return self.data


# ------------------------------------------------------------
# Ciel Memory Admin component (real Chroma in a temp dir)
# ------------------------------------------------------------

@unittest.skipUnless(__import__("importlib").util.find_spec("chromadb"), "chromadb not installed")
class MemoryAdminComponentTest(unittest.TestCase):

    def setUp(self):
        self.uninstall_stub = install_langflow_stub()
        self.home = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.home_patch = patch.object(Path, "home", return_value=Path(self.home.name))
        self.home_patch.start()
        self.Admin = compile_class(COMPONENT.read_text(encoding="utf-8"), "CielMemoryAdmin")

        import chromadb
        self.collection = chromadb.PersistentClient(
            path=str(Path(self.home.name) / ".ciel_ai" / "long_term_memory")
        ).get_or_create_collection("ciel_long_term_memory", metadata={"hnsw:space": "cosine"})
        self.collection.add(
            ids=["a1", "a2", "b1", "legacy"],
            embeddings=[[0.1, 0.2], [0.2, 0.1], [0.3, 0.3], [0.4, 0.1]],
            documents=["Nama: Andi", "Belajar statistika", "Nama: Budi", "Memori lama tanpa pemilik"],
            metadatas=[
                {"user_id": ALICE, "created_at": "2026-10-01T00:00:00+00:00"},
                {"user_id": ALICE, "created_at": "2026-10-05T00:00:00+00:00"},
                {"user_id": BOB, "created_at": "2026-10-03T00:00:00+00:00"},
                {"source": "ciel_memory_engine"},
            ],
        )

    def tearDown(self):
        self.home_patch.stop()
        self.uninstall_stub()
        from chromadb.api.client import SharedSystemClient
        SharedSystemClient.clear_system_cache()
        self.home.cleanup()

    def run_admin(self, owner, action, memory_id=""):
        return self.Admin(memory_owner=owner, memory_action=action, memory_id=memory_id).handle()

    def remaining(self):
        return sorted(self.collection.get()["ids"])

    def test_list_returns_only_the_owners_memories_newest_first(self):
        result = self.run_admin(ALICE, "list")
        self.assertEqual(result["total"], 2)
        self.assertEqual([m["text"] for m in result["memories"]], ["Belajar statistika", "Nama: Andi"])

    def test_cannot_delete_someone_elses_memory(self):
        self.assertEqual(self.run_admin(ALICE, "delete", "b1"), {"ok": False, "error": "not_found"})
        self.assertEqual(self.run_admin(ALICE, "delete", "legacy"), {"ok": False, "error": "not_found"})
        self.assertEqual(self.remaining(), ["a1", "a2", "b1", "legacy"])

    def test_delete_one_and_delete_all_only_touch_the_owner(self):
        self.assertEqual(self.run_admin(ALICE, "delete", "a1"), {"ok": True, "deleted": 1})
        self.assertEqual(self.run_admin(ALICE, "delete_all"), {"ok": True, "deleted": 1})
        self.assertEqual(self.remaining(), ["b1", "legacy"])

    def test_anonymous_and_unknown_actions_are_refused(self):
        self.assertEqual(self.run_admin("", "list"), {"ok": False, "error": "login_required"})
        self.assertEqual(self.run_admin(ALICE, "drop"), {"ok": False, "error": "unknown_action"})
        self.assertEqual(self.remaining(), ["a1", "a2", "b1", "legacy"])

    def test_output_is_json_in_the_message_text(self):
        message = self.Admin(memory_owner=BOB, memory_action="list", memory_id="").run_action()
        self.assertEqual(json.loads(message.text)["memories"][0]["text"], "Nama: Budi")

    def test_inputs_do_not_shadow_langflow_attributes(self):
        names = input_names(COMPONENT.read_text(encoding="utf-8"))
        self.assertEqual(sorted(names), ["memory_action", "memory_id", "memory_owner"])
        self.assertFalse(RESERVED_COMPONENT_ATTRIBUTES & set(names))


class MemoryAdminFlowContractTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.flow = json.loads(ADMIN_FLOW.read_text(encoding="utf-8"))
        cls.nodes = {n["id"]: n for n in cls.flow["data"]["nodes"]}

    def test_flow_is_only_admin_to_chat_output(self):
        self.assertEqual(sorted(self.nodes), ["ChatOutput-adm1n", "CielMemoryAdmin-adm1n"])
        [edge] = self.flow["data"]["edges"]
        self.assertEqual((edge["source"], edge["data"]["sourceHandle"]["name"]), ("CielMemoryAdmin-adm1n", "result"))
        self.assertEqual((edge["target"], edge["data"]["targetHandle"]["fieldName"]), ("ChatOutput-adm1n", "input_value"))

    def test_node_runs_the_component_source(self):
        template = self.nodes["CielMemoryAdmin-adm1n"]["data"]["node"]["template"]
        normalize = lambda code: code.replace("\r\n", "\n").strip()
        self.assertEqual(normalize(template["code"]["value"]), normalize(COMPONENT.read_text(encoding="utf-8")))
        for name in ("memory_owner", "memory_action", "memory_id"):
            self.assertFalse(template[name].get("tool_mode"), name)

    def test_results_are_not_stored_as_chat_messages(self):
        template = self.nodes["ChatOutput-adm1n"]["data"]["node"]["template"]
        self.assertIs(template["should_store_message"]["value"], False)

    def test_app_default_node_id_matches_the_flow(self):
        self.assertIn('get_config("MEMORY_ADMIN_NODE_ID") or "CielMemoryAdmin-adm1n"', APP_PATH.read_text(encoding="utf-8"))

    def test_snapshot_holds_no_install_specific_values(self):
        raw = ADMIN_FLOW.read_text(encoding="utf-8")
        self.assertNotIn('"id": "', raw.split('"nodes"')[0])
        self.assertNotIn('"user_id"', raw)
        self.assertNotRegex(raw, r"sk-[A-Za-z0-9]{10,}")


# ------------------------------------------------------------
# App: data controls
# ------------------------------------------------------------

class AppDataControlsTest(unittest.TestCase):

    def namespace(self, owner):
        import logging
        import uuid
        return load_app_functions(
            ("memory_admin", "own_session_ids", "delete_server_chat_history"),
            requests=requests, uuid=uuid, json=json, logger=logging.getLogger("test_privacy"),
            memory_owner_id=lambda: owner,
            NGROK_URL="https://example.invalid", NGROK_USER="u", NGROK_PASSWORD="p",
            LANGFLOW_API_KEY="k", MEMORY_ADMIN_FLOW_ID="admin-flow", MEMORY_ADMIN_NODE_ID="CielMemoryAdmin-adm1n",
        )

    def test_own_session_ids_match_only_the_owner_prefix(self):
        own = self.namespace(ALICE)["own_session_ids"]
        sessions = [f"{ALICE}-chat1", f"{ALICE}-memory-admin", f"{BOB}-chat1", f"x{ALICE}-chat", ALICE, "livetest-quality-1"]
        self.assertEqual(own(sessions, ALICE), [f"{ALICE}-chat1", f"{ALICE}-memory-admin"])
        self.assertEqual(own(sessions, ""), [])

    def test_delete_history_deletes_only_own_sessions_in_batches(self):
        ns = self.namespace(ALICE)
        sessions = [f"{ALICE}-c{i}" for i in range(600)] + [f"{BOB}-c1", "anon1234anon1234-c1"]

        with self.assertLogs("test_privacy", level="INFO"), \
                patch("requests.get", return_value=Response(sessions)), \
                patch("requests.delete", return_value=Response({})) as delete:
            result = ns["delete_server_chat_history"]()

        self.assertEqual(result, {"ok": True, "deleted_sessions": 600})
        sent = [s for call in delete.call_args_list for s in call.kwargs["json"]]
        self.assertEqual(len(delete.call_args_list), 2)
        self.assertEqual(len(sent), 600)
        self.assertTrue(all(s.startswith(f"{ALICE}-") for s in sent))

    def test_delete_history_requires_login(self):
        with patch("requests.get") as get:
            self.assertEqual(self.namespace("")["delete_server_chat_history"](), {"ok": False, "error": "login_required"})
        get.assert_not_called()

    def test_memory_admin_uses_the_apps_owner_and_parses_json(self):
        ns = self.namespace(ALICE)
        reply = {"outputs": [{"outputs": [{"results": {"message": {"data": {"text": json.dumps({"ok": True, "deleted": 1})}}}}]}]}

        with self.assertLogs("test_privacy", level="INFO"), patch("requests.post", return_value=Response(reply)) as post:
            result = ns["memory_admin"]("delete", "a1")

        self.assertEqual(result, {"ok": True, "deleted": 1})
        tweaks = post.call_args.kwargs["json"]["tweaks"]["CielMemoryAdmin-adm1n"]
        self.assertEqual(tweaks, {"memory_owner": ALICE, "memory_action": "delete", "memory_id": "a1"})

    def test_memory_admin_failure_returns_a_request_id_without_raising(self):
        ns = self.namespace(ALICE)
        with self.assertLogs("test_privacy", level="ERROR"), \
                patch("requests.post", side_effect=requests.exceptions.ConnectionError("down")):
            result = ns["memory_admin"]("list")
        self.assertFalse(result["ok"])
        self.assertIn("request_id", result)

    def test_memory_admin_needs_login_and_configuration(self):
        with patch("requests.post") as post:
            self.assertEqual(self.namespace("")["memory_admin"]("list"), {"ok": False, "error": "unavailable"})
        post.assert_not_called()


# ------------------------------------------------------------
# Privacy page
# ------------------------------------------------------------

class PrivacyPageTest(unittest.TestCase):

    def text(self, **kwargs):
        import privacy
        return " ".join(item for _, items in privacy.privacy_sections(**kwargs) for item in items)

    def test_page_follows_the_configuration(self):
        full = self.text(retention_days=30, memory_enabled=True, data_controls=True, contact_url="mailto:halo@ciel.ai")
        self.assertIn("paling lama <strong>30 hari</strong>", full)
        self.assertIn("<strong>Data saya</strong>", full)
        self.assertIn("dikirim ke server Ciel untuk dijawab", full)
        self.assertIn('<a href="mailto:halo@ciel.ai">hubungi kami</a>', full)

        minimal = self.text(retention_days=90, memory_enabled=False, data_controls=False)
        self.assertIn("90 hari", minimal)
        self.assertIn("belum aktif di deployment ini", minimal)
        self.assertNotIn("Data saya", minimal)
        self.assertNotIn("hubungi kami", minimal)

    def test_app_renders_the_privacy_page(self):
        from streamlit.testing.v1 import AppTest
        sys.path.insert(0, str(ROOT))
        env = {"NGROK_URL": "http://127.0.0.1:9", "NGROK_USER": "u", "NGROK_PASSWORD": "p", "LANGFLOW_API_KEY": "k", "FLOW_ID": "f"}
        with patch.dict(os.environ, env):
            at = AppTest.from_file(str(APP_PATH), default_timeout=60)
            at.query_params["page"] = "privacy"
            at.run()
        self.assertFalse(at.exception)
        page = " ".join(md.value for md in at.markdown)
        self.assertIn("<h1>Privasi</h1>", page)
        self.assertIn("30 hari", page)
        self.assertEqual(len(at.chat_input), 0)


# ------------------------------------------------------------
# Retention script
# ------------------------------------------------------------

class PruneChatHistoryTest(unittest.TestCase):

    NOW = datetime(2026, 11, 20, tzinfo=timezone.utc)

    def setUp(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import prune_chat_history
        self.prune = prune_chat_history

    def test_parses_langflow_timestamps(self):
        expected = datetime(2026, 10, 14, 11, 28, 48, tzinfo=timezone.utc)
        for raw in ("2026-10-14 11:28:48 UTC", "2026-10-14T11:28:48Z", "2026-10-14T11:28:48+00:00", "2026-10-14 11:28:48"):
            with self.subTest(raw=raw):
                self.assertEqual(self.prune.parse_timestamp(raw), expected)
        self.assertIsNone(self.prune.parse_timestamp("kemarin"))

    def test_selects_only_messages_older_than_the_cutoff(self):
        messages = [
            {"id": "old", "timestamp": "2026-10-01 10:00:00 UTC"},
            {"id": "new", "timestamp": "2026-11-15 10:00:00 UTC"},
            {"id": "weird", "timestamp": "?"},
        ]
        cutoff = datetime(2026, 10, 21, tzinfo=timezone.utc)
        self.assertEqual(self.prune.select_expired(messages, cutoff), ["old"])

    def test_pages_through_messages_and_deletes_expired_ones(self):
        page1 = [{"id": f"n{i}", "timestamp": "2026-11-19 00:00:00 UTC"} for i in range(200)]
        page2 = [{"id": "o1", "timestamp": "2026-09-01 00:00:00 UTC"}, {"id": "o2", "timestamp": "2026-10-01 00:00:00 UTC"}]

        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "k"}), \
                patch("requests.get", side_effect=[Response(page1), Response(page2)]) as get, \
                patch("requests.delete", return_value=Response({})) as delete, \
                patch("builtins.print"):
            self.assertEqual(self.prune.main(["--days", "30"], now=self.NOW), 0)

        self.assertEqual([c.kwargs["params"]["offset"] for c in get.call_args_list], [0, 200])
        self.assertEqual(delete.call_args.kwargs["json"], ["o1", "o2"])

    def test_dry_run_deletes_nothing(self):
        old = [{"id": "o1", "timestamp": "2026-09-01 00:00:00 UTC"}]
        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "k"}), \
                patch("requests.get", return_value=Response(old)), \
                patch("requests.delete") as delete, \
                patch("builtins.print"):
            self.prune.main(["--days", "30", "--dry-run"], now=self.NOW)
        delete.assert_not_called()


if __name__ == "__main__":
    unittest.main()
