"""guard/audit.py: log aksi berantai hash, penyaringan teks, dan tabel database agent."""

import unittest
from dataclasses import replace
from pathlib import Path

from guard.audit import AuditEvent, chain_hash, redact, target_of, verify_chain
from guard.risk import Action

ROOT = Path(__file__).resolve().parents[1]


def event(seq, **kw):
    base = dict(owner="o", device="d", task="t", seq=seq, kind="tab_click", target="shopee.co.id",
                level="R1", decision="allow", reason=None, approved_by=None, result="ok",
                at="2026-11-14T03:42:00+00:00")
    base.update(kw)
    return AuditEvent(**base)


def chain(events, first_prev="", key=None):
    rows, prev = [], first_prev
    for e in events:
        prev = chain_hash(prev, e, key=key) if key else chain_hash(prev, e)
        rows.append((e, prev))
    return rows


class ChainHeadAndKeyTest(unittest.TestCase):
    """Temuan minor tinjauan akhir: baris terakhir yang dipotong, dan rantai berkunci."""

    def test_missing_tail_rows_are_found_when_the_head_is_known(self):
        rows = chain([event(1), event(2), event(3)])
        head = rows[-1][1]
        self.assertIsNone(verify_chain(rows, head=head))
        self.assertEqual(verify_chain(rows[:2], head=head), 2)
        self.assertEqual(verify_chain([], head=head), 0)
        self.assertIsNone(verify_chain([], head=""))

    def test_keyed_chain_needs_the_key(self):
        key = b"kunci-rantai-uji-0123456789abcdef"
        keyed = chain_hash("", event(1), key=key)
        self.assertRegex(keyed, r"^[0-9a-f]{64}$")
        self.assertNotEqual(keyed, chain_hash("", event(1)))
        self.assertNotEqual(keyed, chain_hash("", event(1), key=b"kunci-lain-uji-0123456789abcdef-x"))
        rows = chain([event(1), event(2)], key=key)
        self.assertIsNone(verify_chain(rows, key=key))
        self.assertEqual(verify_chain(rows), 0)

    def test_short_key_is_refused(self):
        with self.assertRaises(ValueError):
            chain_hash("", event(1), key=b"pendek")


class ChainTest(unittest.TestCase):
    def test_intact_chain(self):
        self.assertIsNone(verify_chain(chain([event(1), event(2), event(3)])))
        self.assertIsNone(verify_chain([]))

    def test_edited_row_is_found(self):
        rows = chain([event(1), event(2), event(3)])
        rows[1] = (replace(rows[1][0], decision="block"), rows[1][1])
        self.assertEqual(verify_chain(rows), 1)

    def test_edited_first_row_is_found(self):
        rows = chain([event(1), event(2)])
        rows[0] = (replace(rows[0][0], target="example.org"), rows[0][1])
        self.assertEqual(verify_chain(rows), 0)

    def test_removed_row_is_found(self):
        rows = chain([event(1), event(2), event(3)])
        del rows[1]
        self.assertEqual(verify_chain(rows), 1)

    def test_swapped_rows_are_found(self):
        rows = chain([event(1), event(2), event(3)])
        rows[1], rows[2] = rows[2], rows[1]
        self.assertEqual(verify_chain(rows), 1)

    def test_chain_can_continue_from_an_earlier_hash(self):
        first = chain([event(1), event(2)])
        later = chain([event(3), event(4)], first_prev=first[-1][1])
        self.assertIsNone(verify_chain(later, first_prev=first[-1][1]))
        self.assertEqual(verify_chain(later), 0)

    def test_hash_is_sha256_hex(self):
        self.assertRegex(chain_hash("", event(1)), r"^[0-9a-f]{64}$")

    def test_hash_depends_on_the_previous_hash(self):
        self.assertNotEqual(chain_hash("", event(1)), chain_hash("x", event(1)))


class RedactTest(unittest.TestCase):
    def test_secrets_are_replaced(self):
        self.assertEqual(redact("kartu 4111 1111 1111 1111 ya"), "kartu [disaring] ya")

    def test_keys_and_several_secrets(self):
        key = "sk-" + "a1B2" * 10
        self.assertEqual(redact(f"kunci {key} dan 4111-1111-1111-1111"), "kunci [disaring] dan [disaring]")

    def test_ordinary_text_is_kept(self):
        self.assertEqual(redact("kalkulator ilmiah 2026"), "kalkulator ilmiah 2026")

    def test_long_text_is_cut(self):
        self.assertEqual(len(redact("a" * 500)), 120)
        self.assertEqual(redact("abcdef", limit=3), "abc")

    def test_non_text(self):
        self.assertEqual(redact(None), "")
        self.assertEqual(redact(4111111111111111), "")


class TargetTest(unittest.TestCase):
    def test_targets(self):
        self.assertEqual(target_of(Action(kind="tab_read", host="mall.shopee.co.id")), "mall.shopee.co.id")
        self.assertEqual(target_of(Action(kind="ui_click", app="WINWORD")), "winword")
        self.assertEqual(target_of(Action(kind="file_move", path="C:/Users/nadia/Dokumen/Skripsi/bab1/draf.docx")), "bab1/draf.docx")
        self.assertEqual(target_of(Action(kind="finish")), "")

    def test_backslashes_short_paths_and_case(self):
        self.assertEqual(target_of(Action(kind="file_move", path="C:\\Users\\nadia\\a.txt")), "nadia/a.txt")
        self.assertEqual(target_of(Action(kind="file_list", path="catatan.txt")), "catatan.txt")
        self.assertEqual(target_of(Action(kind="tab_read", host="Mall.Shopee.co.id")), "mall.shopee.co.id")

    def test_only_a_real_hostname_reaches_the_log(self):
        # Temuan C2: parameter kueri tidak boleh ikut tercatat.
        leaky = Action(kind="tab_read", host="shopee.co.id/search?q=kartu+4111111111111111&token=abc")
        self.assertEqual(target_of(leaky), "")
        self.assertEqual(target_of(Action(kind="tab_read", host="Shopee.co.id.:443")), "shopee.co.id")

    def test_card_with_trailing_digits_is_redacted(self):
        self.assertNotIn("4111", redact("4111 1111 1111 1111 123"))

    def test_wrong_typed_fields(self):
        self.assertEqual(target_of(Action(kind="tab_read", host=7, app=["x"], path=None)), "")


class SqlTest(unittest.TestCase):
    def test_tables_exist_with_rls_and_no_policy(self):
        sql = (ROOT / "docs" / "chat_store.sql").read_text(encoding="utf-8")
        for table in ("agent_actions", "spend_limits", "purchase_confirmations", "consent_events"):
            with self.subTest(table=table):
                self.assertIn(f"create table if not exists public.{table}", sql)
                self.assertIn(f"alter table public.{table} enable row level security;", sql)
                self.assertNotRegex(sql, rf"create policy[^;]*public\.{table}")

    def test_constraints_index_and_no_update_triggers(self):
        sql = (ROOT / "docs" / "chat_store.sql").read_text(encoding="utf-8")
        for text in (
            "check (seq >= 1)",
            "check (level in ('R0', 'R1', 'R2', 'R3'))",
            "check (decision in ('allow', 'confirm', 'block', 'handover'))",
            "check (per_tx >= 0)",
            "check (per_month >= 0)",
            "check (total > 0)",
            "create index if not exists purchase_confirmations_owner_month",
            "before update on public.agent_actions",
            "before update on public.consent_events",
        ):
            with self.subTest(text=text):
                self.assertIn(text, sql)

    def test_action_log_keeps_the_chain_columns(self):
        sql = (ROOT / "docs" / "chat_store.sql").read_text(encoding="utf-8")
        table = sql.split("create table if not exists public.agent_actions", 1)[1].split(");", 1)[0]
        # "at" disimpan sebagai teks yang sama persis dengan yang di-hash (temuan I10):
        # timestamptz dicetak ulang Postgres dengan format lain, jadi rantainya putus.
        self.assertNotIn("at timestamptz", table)
        for column in ("at text not null", "prev_hash text not null", "hash text not null", "primary key (owner, task, seq)"):
            with self.subTest(column=column):
                self.assertIn(column, table)


if __name__ == "__main__":
    unittest.main()
