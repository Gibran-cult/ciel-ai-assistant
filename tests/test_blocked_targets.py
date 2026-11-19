"""Daftar situs yang selalu diblokir (roadmap 0.15, keputusan D9 dan D21).

Setiap entri di guard/blocked_targets.json harus punya bukti di
docs/blocked-targets.md, dan sebaliknya. Entri tidak boleh terlalu luas.
"""

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_api.plan import PUBLIC_SUFFIXES  # noqa: E402
from guard.domains import match_allowed, normalize_host  # noqa: E402
from guard.risk import BLOCKED_HOSTS  # noqa: E402

BLOCKED = json.loads((ROOT / "guard" / "blocked_targets.json").read_text(encoding="utf-8"))["host_suffixes"]
DOC = (ROOT / "docs" / "blocked-targets.md").read_text(encoding="utf-8") if (ROOT / "docs" / "blocked-targets.md").exists() else ""
# Baris tabel bukti: | `domain` | kategori | merek | ... |
DOC_DOMAINS = re.findall(r"^\| `([a-z0-9.-]+)` \|", DOC, flags=re.MULTILINE)
STORES = json.loads((ROOT / "guard" / "official_stores.json").read_text(encoding="utf-8"))
PROTECTED = {domain for entry in STORES["marketplaces"] + STORES["brand_sites"] for domain in entry["domains"]}
PROTECTED |= {"google.com", "apple.com", "microsoft.com", "icloud.com", "gojek.com"}


class BlockedTargetsTest(unittest.TestCase):
    def test_every_entry_has_its_evidence_and_every_evidence_an_entry(self):
        self.assertEqual(sorted(BLOCKED), sorted(set(DOC_DOMAINS)))
        self.assertEqual(len(DOC_DOMAINS), len(set(DOC_DOMAINS)), "satu baris bukti per domain")

    def test_entries_are_plain_hostnames_and_never_a_public_suffix(self):
        for host in BLOCKED:
            with self.subTest(host=host):
                self.assertEqual(normalize_host(host), host)
                self.assertNotIn(host, PUBLIC_SUFFIXES)

    def test_no_entry_swallows_a_shop_or_a_common_site(self):
        for host in BLOCKED:
            for site in PROTECTED:
                with self.subTest(host=host, site=site):
                    self.assertFalse(site == host or site.endswith("." + host))

    def test_the_main_categories_are_covered(self):
        # Contoh dari setiap kategori D9 dan D21 B.
        for host in ("klikbca.com", "ib.bri.co.id", "vault.bitwarden.com", "dana.id", "indodax.com", "kredivo.com"):
            with self.subTest(host=host):
                self.assertIsNotNone(match_allowed(host, BLOCKED_HOSTS))


if __name__ == "__main__":
    unittest.main()
