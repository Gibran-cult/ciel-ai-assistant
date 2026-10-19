import ast
import hashlib
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests
import streamlit


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
sys.path.insert(0, str(ROOT))

import chat_store  # noqa: E402

ENV = {"NGROK_URL": "http://127.0.0.1:9", "NGROK_USER": "u", "NGROK_PASSWORD": "p", "LANGFLOW_API_KEY": "k", "FLOW_ID": "f"}
SIGNED_IN = {"is_logged_in": True, "name": "Ciel Tester", "email": "ciel@example.com", "sub": "sub-1"}
ALICE = "a1b2c3d4e5f60718"
SIGNED_IN_OWNER = hashlib.sha256(b"ciel-memory:sub-1").hexdigest()[:16]  # memory_owner_id()


class Response:

    def __init__(self, payload=None, status=200):
        self.payload = payload
        self.status_code = status

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(str(self.status_code))


def sample_chat(chat_id="c1", **extra):
    return {
        "id": chat_id,
        "title": "Belajar limit",
        "project_id": None,
        "updated": 100.0,
        "messages": [
            {"role": "user", "content": "halo", "files": ["a.csv"],
             "images": [{"name": "x.jpg", "mime": "image/jpeg", "data": b"\xff\xd8thumb"}],
             "payload": "isi file yang besar"},
            {"role": "assistant", "content": "Hai!", "error": False},
        ],
        "tables": {"a.csv": {"text": "a,b\n1,2"}},
        **extra,
    }


def sample_project(project_id="p1", files=None):
    return {
        "id": project_id,
        "name": "Skripsi",
        "created": 50.0,
        "files": files if files is not None else [
            {"name": "data.csv", "text": "a,b\n1,2", "size": 8, "truncated": False, "rows": 1,
             "table": {"text": "a,b\n1,2", "truncated": False}},
        ],
    }


class SerializationTest(unittest.TestCase):

    def test_round_trip_keeps_messages_and_images(self):
        row = chat_store.to_row(ALICE, sample_chat(archived=True))
        chat = chat_store.from_row(row)

        self.assertEqual(row["owner"], ALICE)
        self.assertTrue(chat["archived"])
        self.assertEqual(chat["messages"][0]["images"][0]["data"], b"\xff\xd8thumb")
        self.assertEqual(chat["messages"][0]["files"], ["a.csv"])
        self.assertEqual(chat["messages"][1], {"role": "assistant", "content": "Hai!", "error": False})

    def test_payload_tables_and_large_images_are_not_stored(self):
        chat = sample_chat()
        chat["messages"][0]["images"].append(
            {"name": "asli.png", "mime": "image/png", "data": b"0" * (chat_store.MAX_STORED_IMAGE_BYTES + 1)}
        )
        row = chat_store.to_row(ALICE, chat)

        self.assertNotIn("tables", row)
        self.assertNotIn("payload", row["messages"][0])
        self.assertEqual([i["name"] for i in row["messages"][0]["images"]], ["x.jpg"])

    def test_error_answers_are_stored_as_plain_text(self):
        class CielError(str):
            pass

        row = chat_store.to_row(ALICE, {**sample_chat(), "messages": [
            {"role": "assistant", "content": CielError("Gagal"), "error": True},
        ]})
        self.assertIs(type(row["messages"][0]["content"]), str)

    def test_project_round_trip_keeps_files_and_tables(self):
        row = chat_store.to_project_row(ALICE, sample_project())
        self.assertEqual(row["owner"], ALICE)
        self.assertEqual(chat_store.from_project_row(row), sample_project())


class ChatStoreRequestTest(unittest.TestCase):

    def setUp(self):
        self.store = chat_store.ChatStore("https://db.example.invalid/", "service-key")

    def test_every_request_is_filtered_by_owner(self):
        with patch("requests.request", return_value=Response([])) as request:
            self.store.load(ALICE)
            self.store.delete(ALICE, "c1")
            self.store.delete_all(ALICE)

        for call in request.call_args_list:
            self.assertEqual(call.args[1], "https://db.example.invalid/rest/v1/chats")
            self.assertEqual(call.kwargs["params"]["owner"], f"eq.{ALICE}")
            self.assertEqual(call.kwargs["headers"]["Authorization"], "Bearer service-key")

        self.assertEqual(request.call_args_list[1].kwargs["params"]["id"], "eq.c1")
        self.assertNotIn("id", request.call_args_list[2].kwargs["params"])

    def test_load_returns_chats_by_id(self):
        rows = [chat_store.to_row(ALICE, sample_chat("c1")), chat_store.to_row(ALICE, sample_chat("c2"))]
        with patch("requests.request", return_value=Response(rows)):
            chats = self.store.load(ALICE)
        self.assertEqual(sorted(chats), ["c1", "c2"])

    def test_save_upserts_one_row(self):
        with patch("requests.post", return_value=Response()) as post:
            self.assertTrue(self.store.save(ALICE, sample_chat()))
        self.assertIn("merge-duplicates", post.call_args.kwargs["headers"]["Prefer"])
        self.assertEqual(post.call_args.kwargs["json"]["owner"], ALICE)

    def test_project_requests_use_the_projects_table_and_owner(self):
        rows = [chat_store.to_project_row(ALICE, sample_project("p1")),
                chat_store.to_project_row(ALICE, sample_project("p2"))]
        with patch("requests.request", return_value=Response(rows)) as request, \
                patch("requests.post", return_value=Response()) as post:
            projects = self.store.load_projects(ALICE)
            self.assertTrue(self.store.save_project(ALICE, sample_project()))
            self.assertTrue(self.store.delete_project(ALICE, "p1"))

        self.assertEqual(list(projects), ["p1", "p2"])
        load, delete = request.call_args_list
        self.assertEqual(load.kwargs["params"]["order"], "created.asc")
        self.assertEqual(delete.args[0], "DELETE")
        self.assertEqual(delete.kwargs["params"]["id"], "eq.p1")
        for call in (load, delete):
            self.assertEqual(call.args[1], "https://db.example.invalid/rest/v1/projects")
            self.assertEqual(call.kwargs["params"]["owner"], f"eq.{ALICE}")
        self.assertEqual(post.call_args.args[0], "https://db.example.invalid/rest/v1/projects")
        self.assertEqual(post.call_args.kwargs["json"]["owner"], ALICE)

    def test_invalid_owner_or_chat_id_never_reaches_the_database(self):
        with self.assertLogs("ciel_ai.chat_store", level="ERROR"), \
                patch("requests.request") as request, patch("requests.post") as post:
            self.assertIsNone(self.store.load(""))
            self.assertFalse(self.store.delete_all("a,b"))
            self.assertFalse(self.store.delete(ALICE, "c1&owner=eq.bob"))
            self.assertFalse(self.store.save(ALICE, sample_chat("../x")))
            self.assertIsNone(self.store.load_projects("short"))
            self.assertFalse(self.store.delete_project(ALICE, "p1&owner=eq.bob"))
            self.assertFalse(self.store.save_project(ALICE, sample_project("p 1")))
        request.assert_not_called()
        post.assert_not_called()

    def test_failures_return_none_or_false_without_raising(self):
        down = requests.exceptions.ConnectionError("down")
        with self.assertLogs("ciel_ai.chat_store", level="ERROR"), \
                patch("requests.request", side_effect=down), \
                patch("requests.post", return_value=Response(status=500)):
            self.assertIsNone(self.store.load(ALICE))
            self.assertFalse(self.store.delete(ALICE, "c1"))
            self.assertFalse(self.store.save(ALICE, sample_chat()))
            self.assertIsNone(self.store.load_projects(ALICE))
            self.assertFalse(self.store.save_project(ALICE, sample_project()))


class State(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


class Upload:

    def __init__(self, name):
        self.name = name


class ProjectFileCapTest(unittest.TestCase):

    def setUp(self):
        source = APP_PATH.read_text(encoding="utf-8")
        nodes = [n for n in ast.parse(source).body
                 if isinstance(n, ast.FunctionDef) and n.name in ("add_project_files", "project_file_chars")]
        self.st = SimpleNamespace(session_state=State(upload_nonce=0), toast=Mock())
        self.persist = Mock()
        self.app = {
            "st": self.st,
            "MAX_PROJECT_CHARS": 100,
            "persist_project": self.persist,
            # "50.txt" reads as a 50-character file.
            "read_text_file": lambda u: ({"name": u.name, "text": "x" * int(u.name.split(".")[0]), "size": 1}, None),
        }
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(APP_PATH), "exec"), self.app)

    def upload(self, project, *names):
        self.st.session_state.projects = {"p1": project}
        self.st.session_state["up"] = [Upload(n) for n in names]
        self.app["add_project_files"]("p1", "up")

    def test_files_past_the_project_budget_are_rejected_and_the_rest_saved(self):
        # A table file counts both its preview text and its full table: 40 here.
        project = sample_project(files=[{"name": "old.csv", "text": "y" * 10, "table": {"text": "y" * 30}}])

        self.upload(project, "50.txt", "20.txt", "5.txt")

        self.assertEqual([f["name"] for f in project["files"]], ["old.csv", "50.txt", "5.txt"])
        self.assertIn("20.txt", self.st.toast.call_args.args[0])
        self.persist.assert_called_once_with(project)

    def test_nothing_is_saved_when_no_file_was_added(self):
        project = sample_project(files=[{"name": "50.txt", "text": "x" * 50}])
        self.upload(project, "50.txt", "60.txt")

        self.assertEqual(len(project["files"]), 1)
        self.persist.assert_not_called()


class SidebarHistoryTest(unittest.TestCase):

    def run_app(self, user=None, secrets=None, chats=None, at=None):
        from streamlit.testing.v1 import AppTest

        with patch.dict(os.environ, ENV), patch.object(streamlit, "user", user or {}):
            if at is None:
                at = AppTest.from_file(str(APP_PATH), default_timeout=60)
                for key, value in (secrets or {}).items():
                    at.secrets[key] = value
                if chats is not None:
                    at.session_state["chats"] = chats
            at.run()
        return at

    def history_labels(self, at):
        return [b.label for b in at.sidebar.button if b.key.startswith(("chat_", "chatactive_"))]

    def test_archive_restore_and_delete_without_login(self):
        at = self.run_app(chats={"c1": sample_chat("c1"), "c2": sample_chat("c2", title="Statistik")})
        self.assertFalse(at.exception)
        self.assertEqual(sorted(self.history_labels(at)), ["Belajar limit", "Statistik"])

        at.button(key="archive_c1").click()
        at = self.run_app(at=at)
        self.assertTrue(at.session_state["chats"]["c1"]["archived"])
        self.assertIn("Diarsipkan (1)", [e.label for e in at.sidebar.expander])
        self.assertTrue(at.button(key="unarchive_c1"))

        at.button(key="unarchive_c1").click()
        at = self.run_app(at=at)
        self.assertFalse(at.session_state["chats"]["c1"]["archived"])

        self.assertTrue(at.button(key="delchat_c2").disabled)
        at.checkbox(key="delok_c2").check()
        at = self.run_app(at=at)
        at.button(key="delchat_c2").click()
        # Patched, never the real server: a local .streamlit/secrets.toml
        # would otherwise point NGROK_URL at the live Langflow.
        down = requests.exceptions.ConnectionError("down")
        with self.assertLogs("ciel_ai", level="ERROR"), \
                patch("requests.delete", side_effect=down) as delete:
            at = self.run_app(at=at)
        self.assertEqual(list(at.session_state["chats"]), ["c1"])
        sent = delete.call_args.kwargs["json"]
        self.assertEqual(len(sent), 1)
        self.assertTrue(sent[0].endswith("-c2"))

    SECRETS = {
        "auth": {"redirect_uri": "http://localhost/oauth2callback"},
        "SUPABASE_URL": "https://db.example.invalid",
        "SUPABASE_SERVICE_KEY": "service-key",
    }

    def signed_in_store(self, projects=(), chats=()):
        rows = {
            "projects": [chat_store.to_project_row(ALICE, p) for p in projects],
            "chats": [chat_store.to_row(ALICE, c) for c in chats],
        }
        # Other tables (pro_members for the account menu's plan line) are empty.
        return Mock(side_effect=lambda method, url, **kw: Response(
            rows.get(url.rsplit("/", 1)[1], []) if method == "GET" else None
        ))

    def test_signed_in_history_loads_and_saves_through_the_store(self):
        request = self.signed_in_store(chats=[sample_chat("c1")])
        with patch("requests.request", request):
            at = self.run_app(user=SIGNED_IN, secrets=self.SECRETS)

        self.assertFalse(at.exception)
        self.assertEqual(self.history_labels(at), ["Belajar limit"])
        self.assertEqual(request.call_args.args[0], "GET")

        at.button(key="archive_c1").click()
        with patch("requests.post", return_value=Response()) as post, patch("requests.request") as again:
            at = self.run_app(user=SIGNED_IN, at=at)
        self.assertTrue(post.call_args.kwargs["json"]["archived"])
        again.assert_not_called()  # loaded once per session, not on every rerun

    def test_projects_load_before_chats_so_chats_keep_their_project(self):
        request = self.signed_in_store(projects=[sample_project("p1")],
                                       chats=[sample_chat("c1", project_id="p1")])
        with patch("requests.request", request):
            at = self.run_app(user=SIGNED_IN, secrets=self.SECRETS)

        self.assertFalse(at.exception)
        tables = [c.args[1].rsplit("/", 1)[1] for c in request.call_args_list]
        self.assertEqual(tables[:2], ["projects", "chats"])
        self.assertLessEqual(set(tables[2:]), {"pro_members"})
        self.assertEqual(at.session_state["projects"]["p1"]["files"][0]["name"], "data.csv")
        self.assertEqual(at.session_state["chats"]["c1"]["project_id"], "p1")
        self.assertTrue(at.button(key="proj_p1"))

    def test_chats_keep_their_project_id_when_projects_fail_to_load(self):
        chats = [chat_store.to_row(ALICE, sample_chat("c1", project_id="p1"))]
        down = Mock(side_effect=lambda method, url, **kw: (
            Response(chats) if url.endswith("/chats") else Response(status=503)))
        with self.assertLogs("ciel_ai.chat_store", level="ERROR"), patch("requests.request", down):
            at = self.run_app(user=SIGNED_IN, secrets=self.SECRETS)

        self.assertFalse(at.exception)
        self.assertEqual(at.session_state["chats"]["c1"]["project_id"], "p1")
        self.assertEqual(self.history_labels(at), ["Belajar limit"])  # still under "Semua chat"

    def test_creating_and_deleting_a_project_goes_through_the_store(self):
        with patch("requests.request", self.signed_in_store(chats=[sample_chat("c1")])):
            at = self.run_app(user=SIGNED_IN, secrets=self.SECRETS)

        at.text_input(key="newproj_name").set_value("Skripsi")
        at.button(key="createproj").click()
        with patch("requests.post", return_value=Response()) as post:
            at = self.run_app(user=SIGNED_IN, at=at)

        (project_id,) = at.session_state["projects"]
        row = post.call_args.kwargs["json"]
        self.assertTrue(post.call_args.args[0].endswith("/rest/v1/projects"))
        self.assertEqual((row["owner"], row["id"], row["name"], row["files"]), (SIGNED_IN_OWNER, project_id, "Skripsi", []))

        # A chat moved into the project, then the project is deleted.
        at.session_state["chats"]["c1"]["project_id"] = project_id
        self.assertTrue(at.button(key=f"delproj_{project_id}").disabled)
        at.checkbox(key=f"delprojok_{project_id}").check()
        at = self.run_app(user=SIGNED_IN, at=at)

        at.button(key=f"delproj_{project_id}").click()
        with patch("requests.request", return_value=Response(status=500)), \
                self.assertLogs("ciel_ai.chat_store", level="ERROR"):
            at = self.run_app(user=SIGNED_IN, at=at)
        self.assertIn(project_id, at.session_state["projects"])  # kept when the database delete fails

        at.button(key=f"delproj_{project_id}").click()
        with patch("requests.request", return_value=Response()) as request, \
                patch("requests.post", return_value=Response()) as post:
            at = self.run_app(user=SIGNED_IN, at=at)

        self.assertEqual(at.session_state["projects"], {})
        self.assertEqual(request.call_args.args[:2], ("DELETE", "https://db.example.invalid/rest/v1/projects"))
        self.assertEqual(request.call_args.kwargs["params"]["id"], f"eq.{project_id}")
        self.assertIsNone(post.call_args.kwargs["json"]["project_id"])  # the chat left the project


if __name__ == "__main__":
    unittest.main()
