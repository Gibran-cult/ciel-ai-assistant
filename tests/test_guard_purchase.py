"""guard/purchase.py: ringkasan pembelian dan token konfirmasi sekali pakai."""

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from guard.purchase import (
    PURCHASE_TTL,
    Item,
    PurchaseSummary,
    check_confirmation,
    issue_confirmation,
    summary_digest,
    totals_consistent,
)

SECRET = b"rahasia-uji-32-byte-0123456789ab"
NOW = datetime(2026, 11, 14, 3, 42, tzinfo=timezone.utc)
SUMMARY = PurchaseSummary(
    store_domain="shopee.co.id", store_name="Toko Contoh", badge_text="Shopee Mall",
    items=(Item("Kalkulator ilmiah", "Hitam", 1, 250_000),),
    shipping=15_000, fees=1_000, discount=5_000, total=261_000,
)


class TotalsTest(unittest.TestCase):
    def test_consistent(self):
        self.assertTrue(totals_consistent(SUMMARY))
        two = replace(SUMMARY, items=(Item("Pensil", "2B", 3, 4_000), Item("Penghapus", "", 1, 3_000)), total=26_000)
        self.assertTrue(totals_consistent(two))

    def test_inconsistent(self):
        for broken in (
            replace(SUMMARY, total=260_000),
            replace(SUMMARY, items=()),
            replace(SUMMARY, items=(Item("Kalkulator", "", 0, 250_000),)),
            replace(SUMMARY, shipping=-1, total=245_000),
            replace(SUMMARY, total=261_000.0),
            replace(SUMMARY, fees=True, total=261_000),
            replace(SUMMARY, items=({"name": "Kalkulator", "qty": 1, "unit_price": 250_000},)),
            replace(SUMMARY, items=None),
            None,
        ):
            with self.subTest(broken=broken):
                self.assertFalse(totals_consistent(broken))


class ConfirmationTest(unittest.TestCase):
    def setUp(self):
        self.token = issue_confirmation(SUMMARY, "owner-a", NOW, SECRET, "nonce-1")

    def check(self, **kw):
        args = dict(token=self.token, summary=SUMMARY, owner="owner-a", now=NOW + timedelta(seconds=60), secret=SECRET, used_nonces=set())
        args.update(kw)
        return check_confirmation(**args)

    def test_ttl_is_ten_minutes(self):
        self.assertEqual(PURCHASE_TTL, 600)

    def test_valid(self):
        self.assertEqual(self.check(), (True, None))

    def test_valid_until_ttl(self):
        self.assertEqual(self.check(now=NOW + timedelta(seconds=600)), (True, None))
        self.assertEqual(self.check(now=NOW + timedelta(seconds=601)), (False, "expired"))

    def test_single_use(self):
        self.assertEqual(self.check(used_nonces={"nonce-1"}), (False, "used"))

    def test_changed_price_invalidates(self):
        self.assertEqual(self.check(summary=replace(SUMMARY, shipping=20_000, total=266_000)), (False, "mismatch"))

    def test_other_owner_or_secret(self):
        self.assertEqual(self.check(owner="owner-b"), (False, "mismatch"))
        self.assertEqual(self.check(secret=b"lain"), (False, "mismatch"))

    def test_extended_expiry_is_a_forgery(self):
        exp, nonce, mac = self.token.split(".")
        later = f"{int(exp) + 3600}.{nonce}.{mac}"
        self.assertEqual(self.check(token=later, now=NOW + timedelta(seconds=700)), (False, "mismatch"))

    def test_other_nonce_is_a_forgery(self):
        exp, _, mac = self.token.split(".")
        self.assertEqual(self.check(token=f"{exp}.nonce-2.{mac}"), (False, "mismatch"))

    def test_malformed(self):
        for token in ("", "abc", "1.2", None, self.token + ".x", "besok.nonce-1.abc", "-5.nonce-1.abc", 12):
            with self.subTest(token=token):
                self.assertEqual(self.check(token=token), (False, "malformed"))

    def test_broken_summary_or_owner_never_raises(self):
        self.assertEqual(self.check(summary=None), (False, "mismatch"))
        self.assertEqual(self.check(summary=replace(SUMMARY, total=1)), (False, "mismatch"))
        self.assertEqual(self.check(owner=None), (False, "mismatch"))
        self.assertEqual(self.check(secret=None), (False, "mismatch"))

    def test_no_token_for_inconsistent_summary(self):
        self.assertIsNone(issue_confirmation(replace(SUMMARY, total=1), "owner-a", NOW, SECRET, "n"))

    def test_no_token_for_unusable_inputs(self):
        for nonce in ("", "a.b", "a|b", None):
            with self.subTest(nonce=nonce):
                self.assertIsNone(issue_confirmation(SUMMARY, "owner-a", NOW, SECRET, nonce))
        for owner in ("", "a|b", None):
            with self.subTest(owner=owner):
                self.assertIsNone(issue_confirmation(SUMMARY, owner, NOW, SECRET, "n"))
        for secret in (b"", b"pendek", "bukan-bytes-tetapi-cukup-panjang", None):
            with self.subTest(secret=secret):
                self.assertIsNone(issue_confirmation(SUMMARY, "owner-a", NOW, secret, "n"))

    def test_token_shape(self):
        exp, nonce, mac = self.token.split(".")
        self.assertEqual(int(exp), int(NOW.timestamp()) + 600)
        self.assertEqual(nonce, "nonce-1")
        self.assertRegex(mac, r"^[0-9a-f]{64}$")

    def test_digest_is_stable_and_sensitive(self):
        self.assertEqual(summary_digest(SUMMARY), summary_digest(replace(SUMMARY)))
        self.assertNotEqual(summary_digest(SUMMARY), summary_digest(replace(SUMMARY, store_name="Toko contoh")))
        self.assertRegex(summary_digest(SUMMARY), r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
