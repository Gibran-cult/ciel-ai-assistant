"""Halaman Syarat dan Ketentuan (terms.py) dan tab Ketentuan di Pengaturan."""

import os
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
sys.path.insert(0, str(ROOT))

import terms  # noqa: E402


class TermsContentTest(unittest.TestCase):

    def text(self, **kwargs):
        return " ".join(item for _, items in terms.terms_sections(**kwargs) for item in items)

    def test_sections_in_order_and_paid_sections_follow_payments(self):
        paid = [title for title, _ in terms.terms_sections(payments="Mayar")]
        self.assertEqual(paid[0], "Siapa yang mengelola Ciel")
        self.assertEqual(paid[-1], "Hukum dan sengketa")
        self.assertIn("Pengembalian dana", paid)

        free = [title for title, _ in terms.terms_sections()]
        self.assertNotIn("Ciel Pro", free)
        self.assertNotIn("Pengembalian dana", free)

    def test_ai_and_academic_notices(self):
        text = self.text()
        self.assertIn("dibuat oleh AI dan bisa keliru", text)
        self.assertIn("aturan kampusmu", text)

    def test_refund_rules(self):
        text = self.text(payments="Mayar")
        for phrase in ("1&times;24 jam", "dua kali", "3 hari", "7 hari setelah membayar",
                       "nomor order", "3 hari kerja", "14 hari kerja", "tetap kami tinjau"):
            self.assertIn(phrase, text)

    def test_declining_new_terms_refunds_the_rest_of_paid_pro(self):
        # UU 8/1999 Pasal 18(1)(g): later terms cannot take away a paid period.
        text = self.text(payments="Mayar")
        self.assertIn("tidak menyetujui perubahan ketentuan", text)
        self.assertIn("prorata", text)
        self.assertIn("batas Pro tidak diturunkan", text)

    def test_no_circular_operator_line_without_a_name(self):
        self.assertNotIn("dikelola oleh pengelola Ciel", self.text())

    def test_price_comes_from_pricing(self):
        from pricing import PLANS, format_idr
        pro = next(plan for plan in PLANS if plan["id"] == "pro")
        self.assertIn(format_idr(pro["monthly"]), self.text(payments="Mayar"))

    def test_no_banned_standard_clauses(self):
        # UU 8/1999 Pasal 18: standard clauses that refuse refunds outright or
        # shift all liability are void.
        text = self.text(payments="Mayar", operator="X", contact_url="mailto:a@b.c").lower()
        for banned in (r"tidak (dapat|bisa) dikembalikan", r"tidak bertanggung jawab atas (segala|apa pun)"):
            self.assertIsNone(re.search(banned, text), banned)
        self.assertIn("tidak mengurangi masa pro yang sudah kamu bayar", text)

    def test_operator_is_escaped_and_fallback_is_clean(self):
        self.assertIn("<strong>Tim &lt;Ciel&gt;</strong>", self.text(operator="Tim <Ciel>"))
        self.assertIn('<a href="mailto:halo@ciel.ai">', self.text(contact_url="mailto:halo@ciel.ai"))

        bare = self.text()
        self.assertIn("pengelola Ciel", bare)
        self.assertNotIn("None", bare)
        self.assertNotIn('href=""', bare)


class TermsAppTest(unittest.TestCase):

    def test_anonymous_terms_link_opens_the_ketentuan_tab(self):
        from streamlit.testing.v1 import AppTest
        env = {"NGROK_URL": "http://127.0.0.1:9", "NGROK_USER": "u", "NGROK_PASSWORD": "p", "LANGFLOW_API_KEY": "k", "FLOW_ID": "f"}
        with patch.dict(os.environ, env):
            at = AppTest.from_file(str(APP_PATH), default_timeout=60)
            at.query_params["page"] = "terms"
            at.run()
        self.assertFalse(at.exception)
        page = " ".join(md.value for md in at.markdown)
        self.assertIn("<h1>Syarat dan Ketentuan</h1>", page)
        self.assertIn("Terakhir diperbarui:", page)
        self.assertIn("settabactive_ketentuan", [b.key for b in at.button])


if __name__ == "__main__":
    unittest.main()
