import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_api.store import AgentStore  # noqa: E402

SQL = (ROOT / "docs" / "chat_store.sql").read_text(encoding="utf-8")
ALICE, TASK = "a1b2c3d4e5f60718", "t0001"


class Response:
    def __init__(self, payload=None, status=200):
        self.payload = payload
        self.status_code = status

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload

        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(str(self.status_code))


def store():
    return AgentStore("https://db.example", "service-key")


class AgentStoreTest(unittest.TestCase):
    def test_every_request_is_filtered_by_owner(self):
        calls = (
            lambda s: s.load_task(ALICE, TASK),
            lambda s: s.update_task(ALICE, TASK, status="running"),
            lambda s: s.request_stop(ALICE, TASK),
            lambda s: s.stop_requested(ALICE, TASK),
            lambda s: s.load_actions(ALICE, TASK),
        )

        for call in calls:
            with patch("requests.request", return_value=Response([])) as request:
                call(store())

            params = request.call_args.kwargs["params"]
            self.assertEqual(params["owner"], "eq." + ALICE)
            self.assertIn("eq." + TASK, (params.get("id"), params.get("task")))

    def test_load_task_returns_the_row_or_none(self):
        row = {"owner": ALICE, "id": TASK, "status": "running"}

        with patch("requests.request", return_value=Response([row])) as request:
            self.assertEqual(store().load_task(ALICE, TASK), row)

        self.assertEqual(request.call_args.args[:2], ("GET", "https://db.example/rest/v1/agent_tasks"))

        for payload in ([], {"x": 1}, ValueError("bukan json")):
            with patch("requests.request", return_value=Response(payload)):
                self.assertIsNone(store().load_task(ALICE, TASK))

    def test_create_task_reports_busy_on_conflict(self):
        for status, expected in ((201, "created"), (409, "busy"), (500, None)):
            with patch("requests.post", return_value=Response(status=status)) as post:
                self.assertEqual(store().create_task(ALICE, TASK, "d1", "Cari mouse"), expected)

            self.assertEqual(post.call_args.args[0], "https://db.example/rest/v1/agent_tasks")
            self.assertEqual(
                post.call_args.kwargs["json"],
                {"owner": ALICE, "id": TASK, "device": "d1", "instruction": "Cari mouse", "status": "planning"},
            )

    def test_bad_owner_task_or_device_never_reaches_the_database(self):
        with patch("requests.request") as request, patch("requests.post") as post:
            s = store()

            for owner, task in (("x", TASK), (ALICE, "../t"), (ALICE, "a b"), (None, TASK), (ALICE, None)):
                self.assertIsNone(s.load_task(owner, task))
                self.assertFalse(s.update_task(owner, task, status="done"))
                self.assertFalse(s.request_stop(owner, task))
                self.assertIsNone(s.stop_requested(owner, task))
                self.assertIsNone(s.load_actions(owner, task))
                self.assertIsNone(s.create_task(owner, task, "d1", "x"))
                self.assertFalse(s.append_action({"owner": owner, "task": task, "seq": 1}))

            self.assertIsNone(s.create_task(ALICE, TASK, "d 1", "x"))
            self.assertIsNone(s.create_task(ALICE, TASK, "d1", ""))
            self.assertIsNone(s.create_task(ALICE, TASK, "d1", None))

        request.assert_not_called()
        post.assert_not_called()

    def test_update_task_rejects_unknown_fields(self):
        with patch("requests.request", return_value=Response()) as request:
            self.assertFalse(store().update_task(ALICE, TASK, owner="lain"))
            self.assertFalse(store().update_task(ALICE, TASK, status="done", stop_requested=False))
            self.assertFalse(store().update_task(ALICE, TASK))
            request.assert_not_called()

        with patch("requests.request", return_value=Response([{"id": TASK}])) as request:
            self.assertTrue(store().update_task(ALICE, TASK, status="done", steps=3))

        self.assertEqual(request.call_args.args[0], "PATCH")
        self.assertEqual(request.call_args.kwargs["json"], {"status": "done", "steps": 3})
        self.assertEqual(request.call_args.kwargs["headers"]["Prefer"], "return=representation")

    def test_an_update_that_changes_no_row_is_a_failure(self):
        # PostgREST menjawab 200 dengan daftar kosong kalau tidak ada baris yang cocok.
        for payload in ([], None, {"id": TASK}, ["t0001"], ValueError("bukan json")):
            with self.subTest(payload=payload), patch("requests.request", return_value=Response(payload)):
                self.assertFalse(store().update_task(ALICE, TASK, head_hash="abc"))
                self.assertFalse(store().request_stop(ALICE, TASK))

    def test_stop_requested_is_none_when_unreadable(self):
        cases = (
            ([{"stop_requested": True}], True), ([{"stop_requested": False}], False),
            ([], None), ([{"stop_requested": "false"}], None), ([{}], None), (ValueError("x"), None),
        )

        for payload, expected in cases:
            with patch("requests.request", return_value=Response(payload)):
                self.assertIs(store().stop_requested(ALICE, TASK), expected)

        with patch("requests.request", side_effect=requests.exceptions.ConnectionError("mati")):
            self.assertIsNone(store().stop_requested(ALICE, TASK))

    def test_request_stop_sets_the_flag(self):
        with patch("requests.request", return_value=Response([{"id": TASK}])) as request:
            self.assertTrue(store().request_stop(ALICE, TASK))

        self.assertEqual(request.call_args.args[0], "PATCH")
        self.assertEqual(request.call_args.kwargs["json"], {"stop_requested": True})

    def test_append_action_needs_owner_task_and_seq(self):
        row = {"owner": ALICE, "task": TASK, "seq": 1, "kind": "tab_read"}

        with patch("requests.post", return_value=Response(status=201)) as post:
            self.assertTrue(store().append_action(row))
            self.assertEqual(post.call_args.args[0], "https://db.example/rest/v1/agent_actions")
            self.assertEqual(post.call_args.kwargs["json"], row)
            post.reset_mock()

            for broken in ({"owner": ALICE, "task": TASK}, {**row, "seq": "1"}, {**row, "seq": True}, {**row, "seq": 0}, None, []):
                self.assertFalse(store().append_action(broken))

            post.assert_not_called()

    def test_load_actions_is_ordered_by_seq(self):
        rows = [{"seq": 1}, {"seq": 2}]

        with patch("requests.request", return_value=Response(rows)) as request:
            self.assertEqual(store().load_actions(ALICE, TASK), rows)

        self.assertEqual(request.call_args.kwargs["params"]["order"], "seq.asc")

    def test_failures_return_none_or_false_without_raising(self):
        error = requests.exceptions.ConnectionError("mati")

        with patch("requests.request", side_effect=error), patch("requests.post", side_effect=error):
            s = store()
            self.assertIsNone(s.load_task(ALICE, TASK))
            self.assertFalse(s.update_task(ALICE, TASK, status="done"))
            self.assertFalse(s.request_stop(ALICE, TASK))
            self.assertIsNone(s.load_actions(ALICE, TASK))
            self.assertIsNone(s.create_task(ALICE, TASK, "d1", "x"))
            self.assertFalse(s.append_action({"owner": ALICE, "task": TASK, "seq": 1}))
            self.assertIsNone(s.cost_since("2026-11-15T00:00:00+07:00"))

    def test_cost_since_calls_the_rpc(self):
        with patch("requests.post", return_value=Response(1234)) as post:
            self.assertEqual(store().cost_since("2026-11-15T00:00:00+07:00"), 1234)

        self.assertEqual(post.call_args.args[0], "https://db.example/rest/v1/rpc/ciel_agent_cost_since")
        self.assertEqual(post.call_args.kwargs["json"], {"p_since": "2026-11-15T00:00:00+07:00"})

        for payload in (None, "12", 1.5, True, -1, [1]):
            with patch("requests.post", return_value=Response(payload)):
                self.assertIsNone(store().cost_since("2026-11-15T00:00:00+07:00"))

    def test_sql_creates_agent_tasks(self):
        for text in (
            "create table if not exists public.agent_tasks",
            "alter table public.agent_tasks enable row level security",
            "check (status in ('planning', 'running', 'done', 'stopped', 'failed'))",
            "check (mode in ('ask', 'auto'))",
            "create unique index if not exists agent_tasks_one_active",
            "where status in ('planning', 'running')",
            "create or replace function public.ciel_agent_cost_since",
            "revoke execute on function public.ciel_agent_cost_since(timestamptz) from public, anon, authenticated",
        ):
            self.assertIn(text, SQL)


if __name__ == "__main__":
    unittest.main()
