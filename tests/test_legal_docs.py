"""docs/LEGAL.md: daftar kewajiban hukum yang tidak bisa dikerjakan kode."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LegalRegisterTest(unittest.TestCase):

    def test_legal_register_lists_the_manual_obligations(self):
        text = (ROOT / "docs" / "LEGAL.md").read_text(encoding="utf-8")
        for item in ("PSE", "OSS", "OPERATOR_NAME", "CONTACT_URL", "DPA", "10 tahun", "LEGAL_VERSION", "bukan nasihat hukum"):
            self.assertIn(item, text)
        self.assertIn("docs/LEGAL.md", (ROOT / "RELEASE_CHECKLIST.md").read_text(encoding="utf-8"))

    def test_vendor_review_records_the_findings(self):
        text = (ROOT / "docs" / "LEGAL.md").read_text(encoding="utf-8")
        for item in ("non-commercial", "privacy@deepseek.com", "PandaDoc", "Enterprise", "Paid Services"):
            self.assertIn(item, text)

    def test_privacy_change_asks_for_consent_again(self):
        import sys
        sys.path.insert(0, str(ROOT))
        import terms
        self.assertNotEqual(terms.LEGAL_VERSION, "2026-11-01")


if __name__ == "__main__":
    unittest.main()
