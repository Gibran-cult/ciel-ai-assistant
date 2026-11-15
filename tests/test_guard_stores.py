"""guard/stores.py: verifikasi toko resmi dengan kode alasan untuk setiap penolakan."""

import unittest
from dataclasses import replace
from datetime import datetime, timezone

from guard.registry import BrandSite, Marketplace, Registry
from guard.stores import StoreEvidence, verify_store

SHOPEE = Marketplace(
    id="shopee", name="Shopee", domains=("shopee.co.id",), official_labels=("Shopee Mall",),
    automation="allowed", approved=True, tos_url="https://help.shopee.co.id/portal/4/article/71187",
    checked="2026-11-14",
)
TOKOPEDIA = Marketplace(
    id="tokopedia", name="Tokopedia", domains=("tokopedia.com",), official_labels=(),
    automation="forbidden", approved=False, tos_url="https://www.tokopedia.com/help/article/terms-conditions",
    checked="2026-11-14",
)
BRAND = BrandSite(
    brand="Merek Contoh", domain="merek-contoh.example", automation="allowed", approved=True,
    evidence=("profil media sosial terverifikasi", "halaman toko resmi di marketplace"), checked="2026-11-14",
)
REGISTRY = Registry(marketplaces=(SHOPEE, TOKOPEDIA), brand_sites=(BRAND,))
NOW = datetime(2026, 11, 20, tzinfo=timezone.utc)


def registry_with(**kw):
    return Registry(marketplaces=(replace(SHOPEE, **kw), TOKOPEDIA), brand_sites=(BRAND,))


def good():
    return StoreEvidence(
        url="https://shopee.co.id/tokocontoh", nav_origin="typed", store_name="Toko Contoh",
        store_page_name="Toko Contoh", badge_text="Shopee Mall", adapter_ok=True,
    )


class VerifyStoreTest(unittest.TestCase):
    def check(self, evidence, reason, automated=True, registry=REGISTRY, now=NOW):
        verdict = verify_store(evidence, registry, now, automated)
        self.assertFalse(verdict.official)
        self.assertEqual(verdict.reason, reason)
        return verdict

    def test_official_marketplace_store(self):
        verdict = verify_store(good(), REGISTRY, NOW, True)
        self.assertTrue(verdict.official)
        self.assertEqual((verdict.kind, verdict.domain, verdict.reason), ("marketplace", "shopee.co.id", None))
        self.assertEqual(verdict.proof["badge_text"], "Shopee Mall")
        self.assertEqual(verdict.proof["checked_at"], NOW.isoformat())

    def test_official_brand_site(self):
        verdict = verify_store(replace(good(), url="https://merek-contoh.example/produk", badge_text=""), REGISTRY, NOW, True)
        self.assertEqual((verdict.official, verdict.kind), (True, "brand_site"))

    def test_rejections(self):
        self.check(replace(good(), url="http://shopee.co.id/tokocontoh"), "insecure")
        self.check(replace(good(), url="https://shopee.co.id@evil.example/"), "lookalike_domain")
        self.check(replace(good(), url="https://xn--shope-9ua.co.id/"), "lookalike_domain")
        self.check(replace(good(), url="https://192.168.1.10/"), "not_listed")
        self.check(replace(good(), url="https://example.org/toko"), "not_listed")
        self.check(replace(good(), url="https://tokopedia.com/toko"), "not_listed")
        self.check(replace(good(), nav_origin="ad"), "untrusted_navigation")
        self.check(replace(good(), nav_origin="message"), "untrusted_navigation")
        self.check(replace(good(), badge_text="Star Seller"), "no_official_badge")
        self.check(replace(good(), badge_text=""), "no_official_badge")
        self.check(replace(good(), adapter_ok=False), "badge_unverifiable")
        self.check(replace(good(), store_page_name="Toko Lain"), "badge_unverifiable")
        self.check(replace(good(), store_name="", store_page_name=""), "badge_unverifiable")

    def test_lookalike_is_named(self):
        verdict = self.check(replace(good(), url="https://sh0pee.co.id/tokocontoh"), "lookalike_domain")
        self.assertEqual(verdict.lookalike_of, "shopee.co.id")

    def test_lookalike_wins_over_navigation(self):
        self.check(replace(good(), url="https://shoppe.co.id/x", nav_origin="ad"), "lookalike_domain")

    def test_stale_registry_entry(self):
        self.check(good(), "registry_stale", now=datetime(2027, 3, 1, tzinfo=timezone.utc))

    def test_automation_rules(self):
        forbidden = registry_with(automation="forbidden")
        self.check(good(), "automation_forbidden", registry=forbidden)
        self.check(good(), "automation_forbidden", registry=registry_with(automation="unknown"))
        self.assertTrue(verify_store(good(), forbidden, NOW, automated=False).official)

    def test_badge_match_ignores_case_and_spaces(self):
        self.assertTrue(verify_store(replace(good(), badge_text="  shopee mall "), REGISTRY, NOW, True).official)

    def test_garbage_evidence_is_rejected_without_raising(self):
        self.check(replace(good(), url=None), "not_listed")
        self.check(replace(good(), nav_origin=None), "untrusted_navigation")
        self.check(replace(good(), nav_origin=["typed"]), "untrusted_navigation")
        self.check(replace(good(), badge_text=None), "no_official_badge")
        self.check(replace(good(), store_name=7, store_page_name=7), "badge_unverifiable")
        self.check(replace(good(), adapter_ok="ya"), "badge_unverifiable")

    def test_unclear_automated_flag_counts_as_automated(self):
        self.check(good(), "automation_forbidden", automated=None, registry=registry_with(automation="forbidden"))

    def test_backslash_host_is_not_official(self):
        # Browser membaca "\" sebagai "/", jadi alamat ini sebenarnya milik evil.com (temuan C1).
        self.check(replace(good(), url="https://evil.com\\.shopee.co.id/toko"), "not_listed")
        self.check(replace(good(), url="https://evil.com\\.merek-contoh.example/produk", badge_text=""), "not_listed")

    def test_rejections_carry_no_proof(self):
        self.assertEqual(self.check(replace(good(), badge_text="Star Seller"), "no_official_badge").proof, {})


if __name__ == "__main__":
    unittest.main()
