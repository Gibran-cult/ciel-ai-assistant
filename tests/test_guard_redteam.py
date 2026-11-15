"""Red-team tanpa model untuk guard/ (docs/cicd-quality.md bagian 4).

Kasusnya ada di tests/redteam/*.json. Untuk setiap serangan, aksi berbahaya
yang mungkin diusulkan model kalau terpancing diberikan langsung ke mesin
kebijakan. Hasilnya tidak boleh "allow". Jadi uji ini membuktikan pengaman
bekerja apa pun kata model.

Konteksnya sengaja yang paling longgar: mode "auto", toko resmi, batas
belanja cukup. Kalau sebuah kasus lolos, yang diperbaiki modul pemiliknya
di guard/, tidak kasusnya.
"""

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from guard.decide import Context, decide
from guard.limits import SpendLimits
from guard.registry import Marketplace, Registry, load_registry
from guard.risk import ACTION_LEVELS, R3, Action
from guard.scope import TaskScope
from guard.stores import StoreEvidence, StoreVerdict, verify_store

CASES = Path(__file__).resolve().parent / "redteam"
NOW = datetime(2026, 11, 20, tzinfo=timezone.utc)
SKRIPSI = "C:/Users/nadia/Dokumen/Skripsi"


def market(id, domain, labels, approved, automation):
    return Marketplace(
        id=id, name=id.title(), domains=(domain,), official_labels=labels, automation=automation,
        approved=approved, tos_url=f"https://{domain}/", checked="2026-11-14",
    )


# Shopee disetujui supaya penolakan datang dari pemeriksaan toko, bukan
# dari daftar yang kosong. Dua lainnya terdaftar tetapi belum disetujui.
TEST_REGISTRY = Registry(
    marketplaces=(
        market("shopee", "shopee.co.id", ("Shopee Mall",), True, "allowed"),
        market("tokopedia", "tokopedia.com", (), False, "forbidden"),
        market("lazada", "lazada.co.id", ("LazMall",), False, "unknown"),
    ),
    brand_sites=(),
)

OFFICIAL = StoreVerdict(True, "marketplace", None, "shopee.co.id", None, {"store_name": "Toko"})

AUTO_CONTEXT = Context(
    stopped=False, ticket_ok=True, mode="auto",
    scope=TaskScope(
        hosts=frozenset({"shopee.co.id"}), apps=frozenset({"winword"}), writable_folders=(SKRIPSI,),
        kinds=frozenset(kind for kind, level in ACTION_LEVELS.items() if level != R3),
        spend_cap=500_000,
    ),
    adult_verified=True, limits=SpendLimits(per_tx=500_000, per_month=1_500_000), spent_this_month=0,
    store=OFFICIAL, purchase_total=261_000,
)


def load(name):
    return json.loads((CASES / name).read_text(encoding="utf-8"))


class RedTeamTest(unittest.TestCase):
    def test_no_fake_store_is_official(self):
        for case in load("fake_stores.json"):
            with self.subTest(url=case["url"]):
                evidence = StoreEvidence(case["url"], case["nav_origin"], "Toko", "Toko", case["badge_text"], True)
                verdict = verify_store(evidence, TEST_REGISTRY, NOW, automated=True)
                self.assertFalse(verdict.official)
                self.assertEqual(verdict.reason, case["expect"])

    def test_injected_actions_never_run_unattended(self):
        for case in load("injections.json"):
            with self.subTest(text=case["text"]):
                outcome = decide(Action(**case["attempt"]), AUTO_CONTEXT).outcome
                self.assertIn(outcome, case["expect"])
                self.assertNotEqual(outcome, "allow")

    def test_scope_escapes_never_run_unattended(self):
        for case in load("scope_escapes.json"):
            with self.subTest(attempt=case["attempt"]):
                outcome = decide(Action(**case["attempt"]), AUTO_CONTEXT).outcome
                self.assertIn(outcome, case["expect"])
                self.assertNotEqual(outcome, "allow")

    def test_no_case_expects_allow(self):
        for name in ("injections.json", "scope_escapes.json"):
            for case in load(name):
                with self.subTest(case=case):
                    self.assertNotIn("allow", case["expect"])

    def test_the_context_really_is_permissive(self):
        # Pembanding: aksi biasa di dalam lingkup memang langsung jalan.
        self.assertEqual(decide(Action(kind="tab_click", host="shopee.co.id"), AUTO_CONTEXT).outcome, "allow")
        self.assertEqual(decide(Action(kind="file_move", path=SKRIPSI + "/bab1.docx"), AUTO_CONTEXT).outcome, "allow")
        good = StoreEvidence("https://shopee.co.id/toko", "typed", "Toko", "Toko", "Shopee Mall", True)
        self.assertTrue(verify_store(good, TEST_REGISTRY, NOW, automated=True).official)

    def test_corpus_sizes(self):
        self.assertGreaterEqual(len(load("fake_stores.json")), 20)
        self.assertGreaterEqual(len(load("injections.json")), 15)
        self.assertGreaterEqual(len(load("scope_escapes.json")), 10)

    def test_shipped_registry_approves_nothing_yet(self):
        evidence = StoreEvidence("https://shopee.co.id/toko", "typed", "Toko", "Toko", "Shopee Mall", True)
        self.assertEqual(verify_store(evidence, load_registry(), NOW, automated=False).reason, "not_listed")


if __name__ == "__main__":
    unittest.main()
