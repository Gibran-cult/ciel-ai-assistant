import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_api.journal import Journal  # noqa: E402
from guard.audit import AuditEvent, verify_chain  # noqa: E402
from guard.decide import Decision  # noqa: E402
from guard.risk import Action  # noqa: E402
from tests.agent_fakes import MemoryStore  # noqa: E402

KEY = b"kunci-rantai-uji-0123456789"
NOW = datetime(2026, 11, 15, 3, 0, tzinfo=timezone.utc)
ALICE, TASK = "a1b2c3d4e5f60718", "t0001"
CLICK = Action(kind="tab_click", host="Shopee.co.id")
ALLOW = Decision("allow", "R1", "tab_click")


def chain(store):
    fields = AuditEvent.__dataclass_fields__
    return [(AuditEvent(**{name: row[name] for name in fields}), row["hash"]) for row in store.load_actions(ALICE, TASK)]


def journal_for(store):
    store.create_task(ALICE, TASK, "d1", "x")
    return Journal(store, KEY, ALICE, "d1", TASK)


class JournalTest(unittest.TestCase):
    def test_rows_form_a_keyed_chain_with_the_head_on_the_task(self):
        store = MemoryStore()
        journal = journal_for(store)
        self.assertTrue(journal.record(CLICK, ALLOW, NOW))
        self.assertTrue(journal.record(CLICK, ALLOW, NOW, result="ok"))
        self.assertTrue(journal.record(Action(kind="pay"), Decision("block", "R3", "pay"), NOW))

        rows = store.load_actions(ALICE, TASK)
        head = store.load_task(ALICE, TASK)["head_hash"]
        self.assertEqual([row["seq"] for row in rows], [1, 2, 3])
        self.assertEqual([row["prev_hash"] for row in rows], ["", rows[0]["hash"], rows[1]["hash"]])
        self.assertEqual((journal.seq, journal.head), (3, head))
        self.assertEqual(head, rows[2]["hash"])
        self.assertIsNone(verify_chain(chain(store), head=head, key=KEY))
        self.assertEqual(verify_chain(chain(store)[:2], head=head, key=KEY), 2)
        self.assertEqual(verify_chain(chain(store), head=head), 0)

    def test_a_row_holds_what_the_log_needs_and_nothing_else(self):
        store = MemoryStore()
        journal = journal_for(store)
        journal.record(CLICK, Decision("confirm", "R2", "submits"), NOW, approved_by="user", result="ok")
        self.assertEqual(store.actions[0], {
            "owner": ALICE, "device": "d1", "task": TASK, "seq": 1, "kind": "tab_click", "target": "shopee.co.id",
            "level": "R2", "decision": "confirm", "reason": "submits", "approved_by": "user", "result": "ok",
            "at": "2026-11-15T03:00:00+00:00", "prev_hash": "", "hash": journal.head,
        })

    def test_a_failed_write_changes_nothing(self):
        for method in ("append_action", "update_task"):
            with self.subTest(method=method):
                store = MemoryStore()
                journal = journal_for(store)
                store.fail.add(method)
                self.assertFalse(journal.record(CLICK, ALLOW, NOW))
                self.assertEqual((journal.seq, journal.head), (0, ""))

    def test_the_next_row_after_a_failure_reuses_the_number(self):
        store = MemoryStore()
        journal = journal_for(store)
        store.fail.add("append_action")
        journal.record(CLICK, ALLOW, NOW)
        store.fail.clear()
        self.assertTrue(journal.record(CLICK, ALLOW, NOW))
        self.assertEqual([row["seq"] for row in store.actions], [1])

    def test_target_and_kind_are_safe_for_the_log(self):
        store = MemoryStore()
        journal = journal_for(store)
        journal.record(Action(kind=None, host="evil.com/x?token=abc"), Decision("block", "R3", "unknown_kind"), NOW)
        journal.record(Action(kind=["pay"]), Decision("block", "R3", "bad_call"), NOW)
        journal.record(Action(kind="x" * 500), Decision("block", "R3", "tool_unavailable"), NOW)
        self.assertEqual([(row["kind"], row["target"]) for row in store.actions[:2]], [("unknown", ""), ("unknown", "")])
        self.assertLessEqual(len(store.actions[2]["kind"]), 40)
        self.assertIsNone(verify_chain(chain(store), head=journal.head, key=KEY))

    def test_typed_text_is_never_logged(self):
        store = MemoryStore()
        journal = journal_for(store)
        journal.record(Action(kind="tab_type", host="shopee.co.id", text="4111 1111 1111 1111"), ALLOW, NOW)
        self.assertNotIn("4111", repr(store.actions))

    def test_a_short_key_is_refused(self):
        with self.assertRaises(ValueError):
            Journal(MemoryStore(), b"pendek", ALICE, "d1", TASK)


if __name__ == "__main__":
    unittest.main()
