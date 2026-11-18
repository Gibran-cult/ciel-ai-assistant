"""Pemeriksa rantai log dan masa simpan di layanan agent (rencana 2C, Task 2, keputusan D14)."""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_api.journal import Journal  # noqa: E402
from agent_api.ws import TaskRunner  # noqa: E402
from guard.decide import Decision  # noqa: E402
from guard.risk import Action  # noqa: E402
from tests.agent_fakes import MemoryStore  # noqa: E402

KEY = b"kunci-rantai-uji-0123456789"
ALICE = "a1b2c3d4e5f60718"
NOW = datetime(2026, 11, 18, 3, 0, tzinfo=timezone.utc)


def finished_task(store, task_id, rows=3, status="done"):
    """Satu tugas selesai dengan rantai log utuh sepanjang `rows` baris."""

    store.create_task(ALICE, task_id, "d1", "tugas uji")
    journal = Journal(store, KEY, ALICE, "d1", task_id)

    for number in range(rows):
        journal.record(Action(kind="tab_read", host="shopee.co.id"), Decision("allow", "R0", "tab_read"), NOW + timedelta(seconds=number), result="ok")

    store.update_task(ALICE, task_id, status=status)


def statuses(store):
    return {key[1]: task.get("chain_status") for key, task in store.tasks.items()}


class ChainCheckTest(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.runner = TaskRunner(self.store)

    def test_each_finished_task_gets_its_chain_status(self):
        for task_id in ("t1", "t2", "t3"):
            finished_task(self.store, task_id)

        # t2: satu baris diubah. t3: baris terakhir dihapus.
        changed = next(row for row in self.store.actions if row["task"] == "t2" and row["seq"] == 2)
        changed["result"] = "failed"
        last = max((row for row in self.store.actions if row["task"] == "t3"), key=lambda row: row["seq"])
        self.store.actions.remove(last)

        self.assertEqual(self.runner.check_chains(KEY, NOW), 3)
        self.assertEqual(statuses(self.store), {"t1": "ok", "t2": "broken", "t3": "missing"})
        self.assertEqual(self.store.tasks[(ALICE, "t1")]["chain_checked_at"], NOW.isoformat())

    def test_running_and_recently_checked_tasks_are_skipped(self):
        finished_task(self.store, "t1")
        finished_task(self.store, "t2", status="running")
        self.assertEqual(self.runner.check_chains(KEY, NOW), 1)
        self.assertEqual(self.runner.check_chains(KEY, NOW + timedelta(hours=1)), 0)
        self.assertEqual(self.runner.check_chains(KEY, NOW + timedelta(hours=25)), 1)
        self.assertIsNone(statuses(self.store)["t2"])

    def test_a_wrong_key_reports_broken_not_ok(self):
        finished_task(self.store, "t1")
        self.runner.check_chains(b"kunci-lain-yang-salah-000", NOW)
        self.assertEqual(statuses(self.store), {"t1": "broken"})

    def test_an_unreadable_log_is_skipped_not_marked(self):
        finished_task(self.store, "t1")
        self.store.fail.add("load_actions")
        self.assertEqual(self.runner.check_chains(KEY, NOW), 0)
        self.assertIsNone(statuses(self.store)["t1"])

    def test_a_task_without_rows_and_an_empty_head_is_ok(self):
        self.store.create_task(ALICE, "t9", "d1", "tugas kosong")
        self.store.update_task(ALICE, "t9", status="failed")
        self.runner.check_chains(KEY, NOW)
        self.assertEqual(statuses(self.store), {"t9": "ok"})

    def test_a_store_outage_checks_nothing(self):
        self.store.fail.add("tasks_to_check")
        self.assertEqual(self.runner.check_chains(KEY, NOW), 0)


class RetentionTest(unittest.TestCase):
    def test_retention_runs_the_database_function(self):
        store = MemoryStore()
        store.retained = 4
        self.assertEqual(TaskRunner(store).retain_once(), 4)
        store.fail.add("retention")
        self.assertIsNone(TaskRunner(store).retain_once())


class ScheduleTest(unittest.TestCase):
    def test_retention_runs_soon_after_start_and_then_daily(self):
        from agent_api.ws import due_jobs

        self.assertIn("retention", due_jobs(1))
        self.assertIn("retention", due_jobs(1441))
        self.assertNotIn("retention", due_jobs(1440))
        self.assertEqual(due_jobs(10), ["sweep", "chains"])
        self.assertEqual(due_jobs(7), ["sweep"])

    def test_one_failing_job_does_not_stop_the_others(self):
        store = MemoryStore()
        runner = TaskRunner(store)

        def broken(*args):
            raise RuntimeError("rusak")

        with self.assertLogs("ciel.agent_api.ws", level="ERROR"):
            self.assertIsNone(runner.run_job("chains", broken))

        self.assertEqual(runner.run_job("sweep", runner.sweep_once), 0)

if __name__ == "__main__":
    unittest.main()
