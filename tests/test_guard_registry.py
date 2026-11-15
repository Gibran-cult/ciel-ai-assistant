"""guard/registry.py: daftar toko resmi dan pemuatnya."""

import itertools
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from guard.registry import is_stale, load_registry

GOOD_MARKET = {
    "id": "shopee", "name": "Shopee", "domains": ["shopee.co.id"], "official_labels": ["Shopee Mall"],
    "automation": "forbidden", "approved": False,
    "tos_url": "https://help.shopee.co.id/portal/4/article/71187", "checked": "2026-11-14",
}

GOOD_BRAND = {
    "brand": "Merek Contoh", "domain": "merek-contoh.example", "automation": "allowed", "approved": False,
    "evidence": ["profil media sosial terverifikasi", "halaman toko resmi di marketplace"],
    "checked": "2026-11-14",
}

COUNTER = itertools.count()
TMP = None


def setUpModule():
    global TMP
    TMP = tempfile.TemporaryDirectory()
    unittest.addModuleCleanup(TMP.cleanup)


def write_temp(data):
    path = Path(TMP.name) / f"registry-{next(COUNTER)}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class ShippedRegistryTest(unittest.TestCase):
    def setUp(self):
        self.registry = load_registry()

    def test_nothing_is_approved_before_owner_decision(self):
        entries = self.registry.marketplaces + self.registry.brand_sites
        self.assertTrue(entries)
        self.assertFalse(any(e.approved for e in entries))

    def test_tos_findings_are_recorded(self):
        by_id = {m.id: m for m in self.registry.marketplaces}
        self.assertEqual(by_id["shopee"].automation, "forbidden")
        self.assertEqual(by_id["tokopedia"].automation, "forbidden")
        self.assertEqual(by_id["lazada"].automation, "unknown")

    def test_find_matches_subdomains(self):
        self.assertEqual(self.registry.find("mall.shopee.co.id").id, "shopee")
        self.assertIsNone(self.registry.find("example.org"))


class ValidationTest(unittest.TestCase):
    def test_good_file_loads(self):
        brand = {**GOOD_BRAND, "approved": True}
        registry = load_registry(write_temp({"marketplaces": [GOOD_MARKET], "brand_sites": [brand]}))
        self.assertEqual(registry.allowed_domains(), ("shopee.co.id", "merek-contoh.example"))
        self.assertEqual(registry.find("merek-contoh.example").brand, "Merek Contoh")
        self.assertEqual(registry.marketplaces[0].official_labels, ("Shopee Mall",))

    def test_bad_files_fail_at_load(self):
        bad = [
            {"marketplaces": [{**GOOD_MARKET, "domains": ["Shopee.co.id"]}], "brand_sites": []},
            {"marketplaces": [{**GOOD_MARKET, "automation": "maybe"}], "brand_sites": []},
            {"marketplaces": [GOOD_MARKET, GOOD_MARKET], "brand_sites": []},
            {"marketplaces": [], "brand_sites": [{**GOOD_BRAND, "approved": True, "evidence": ["satu"]}]},
            {"marketplaces": [{**GOOD_MARKET, "checked": "14-11-2026"}], "brand_sites": []},
        ]
        for data in bad:
            with self.subTest(data=data), self.assertRaises(ValueError):
                load_registry(write_temp(data))

    def test_empty_labels_duplicate_evidence_and_bad_urls_fail_at_load(self):
        bad = [
            {"marketplaces": [{**GOOD_MARKET, "official_labels": ["", " "]}], "brand_sites": []},
            {"marketplaces": [{**GOOD_MARKET, "tos_url": 5}], "brand_sites": []},
            {"marketplaces": [], "brand_sites": [{**GOOD_BRAND, "approved": True, "evidence": ["x", "x "]}]},
        ]
        for data in bad:
            with self.subTest(data=data), self.assertRaises(ValueError):
                load_registry(write_temp(data))

    def test_broken_json_fails_at_load(self):
        path = Path(TMP.name) / "rusak.json"
        path.write_text("{bukan json", encoding="utf-8")
        with self.assertRaises(ValueError):
            load_registry(path)


class StaleTest(unittest.TestCase):
    def test_ninety_days(self):
        self.assertFalse(is_stale("2026-11-14", date(2027, 2, 12)))
        self.assertTrue(is_stale("2026-11-14", date(2027, 2, 13)))
        self.assertTrue(is_stale("bukan tanggal", date(2026, 11, 14)))

    def test_a_date_in_the_future_is_stale(self):
        self.assertTrue(is_stale("2099-01-01", date(2026, 11, 14)))
        self.assertFalse(is_stale("2026-11-14", date(2026, 11, 14)))


if __name__ == "__main__":
    unittest.main()
