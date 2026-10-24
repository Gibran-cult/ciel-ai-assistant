"""Landing page contract: prices from pricing.py, known app links, honest claims."""

import re
import sys
import unittest
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pricing  # noqa: E402

LANDING = ROOT / "landing" / "index.html"
PAGES = ROOT / ".github" / "workflows" / "pages.yml"
APP = "https://ciel-ai-assistant-hywsyrnfpyhxc5e9pjgaho.streamlit.app/"
CONTACT = "gibranahmadn6@gmail.com"


def page():
    return LANDING.read_text(encoding="utf-8")


def visible_text(source):
    source = re.sub(r"<(script|style)\b.*?</\1>", " ", source, flags=re.S)
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", source)).split())


class LandingContentTest(unittest.TestCase):

    def test_prices_and_plans_match_pricing_py(self):
        text = visible_text(page())
        free = next(plan for plan in pricing.PLANS if plan["id"] == "free")
        pro = next(plan for plan in pricing.PLANS if plan["id"] == "pro")
        self.assertIn(free["name"], text)
        self.assertRegex(text, r"Rp ?0(?![\d.])")
        self.assertIn(pro["name"], text)
        self.assertRegex(text, pricing.format_idr(pro["monthly"]).replace("Rp", "Rp ?").replace(".", r"\."))
        self.assertIn("per 30 hari", text)
        for feature in pro["features"]:
            with self.subTest(feature=feature):
                self.assertIn(feature, text)
        for feature in free["features"]:
            with self.subTest(feature=feature):
                self.assertIn(feature, text)
        self.assertNotIn("Rp149.000", text)
        self.assertNotRegex(text, r"\bTim\b")
        # The landing is static and cannot read the Cloud limits.
        self.assertNotRegex(text, r"\d+\s*pesan\s*/?\s*(per\s*)?jam")

    def test_app_links_use_known_pages(self):
        links = re.findall(r'href="([^"]+)"', page())
        app_links = [link for link in links if link.startswith(APP)]
        self.assertTrue(app_links)
        for link in app_links:
            with self.subTest(link=link):
                self.assertIn(link, {APP, f"{APP}?page=login", f"{APP}?page=pricing", f"{APP}?page=privacy"})
        for match in re.finditer(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page(), flags=re.S):
            label = visible_text(match.group(2))
            if label.startswith("Masuk"):
                with self.subTest(label=label):
                    self.assertEqual(match.group(1), f"{APP}?page=login")
        for link in re.findall(r'<a\b[^>]*href="([^"]+)"', page()):
            with self.subTest(link=link):
                self.assertRegex(link, r"^(#|https://|mailto:)")
                self.assertNotIn("streamlit.app", link.replace(APP, ""))

    def test_no_placeholders_or_contact_stubs(self):
        source = page()
        self.assertNotRegex(visible_text(source), r"\[(?:[A-Z@]|YOUR|Syarat|Kebijakan)[^\]]*\]")
        # TikTok and Instagram stay out until Ciel has accounts.
        for word in ("TikTok", "Instagram"):
            with self.subTest(word=word):
                self.assertNotIn(word, source)

    def test_contact_email_is_ciels_address(self):
        # Ciel gave this address for the footer on 2026-10-24; no other mailto.
        mailtos = set(re.findall(r'href="(mailto:[^"]+)"', page()))
        self.assertEqual(mailtos, {f"mailto:{CONTACT}"})
        self.assertIn(CONTACT, visible_text(page()))

    def test_only_the_real_test_date(self):
        text = visible_text(page())
        self.assertIn("20 Oktober 2026", text)
        self.assertEqual(re.findall(r"(?<!20 )Oktober 2026", text), [])

    def test_fake_journal_is_quoted_verbatim(self):
        text = visible_text(page())
        self.assertIn("Aku nggak bisa meringkas jurnal itu, karena sejauh pencarianku, jurnal tersebut tidak ada.", text)
        self.assertIn("Mau aku lanjut cari penelitian asli yang paling dekat dengan topik ini?", text)
        self.assertIn("Hendrawan &amp; Sulistyo".replace("&amp;", "&"), text)

    def test_rewritten_claims_are_gone(self):
        text = visible_text(page()).lower()
        for claim in (
            "lagi dibaca", "selesai dibaca", "gratis buat mahasiswa", "rp0/bulan", "/bulan",
            "ingatan proyek", "tiap proyek skripsi", "ciel ingat semuanya", "kenapa harus login",
            "kotak kuning muncul tiap", "ditandai kuning kalau nggak ada", "sekitar dua menit",
            "sekitar 2 menit", "1 sumber ketemu", "smsa", "amini", "nazariah", "tenggat",
        ):
            with self.subTest(claim=claim):
                self.assertNotIn(claim, text)

    def test_illustrations_are_labelled(self):
        self.assertGreaterEqual(visible_text(page()).count("Contoh"), 3)

    def test_no_third_party_scripts_or_styles(self):
        source = page()
        self.assertEqual(re.findall(r"<script[^>]+src=", source), [])
        for href in re.findall(r'<link[^>]+href="([^"]+)"', source):
            with self.subTest(href=href):
                # Google Fonts, or a file that ships in landing/ itself.
                local = "://" not in href and (LANDING.parent / href).is_file()
                self.assertTrue(local or href.startswith(("https://fonts.googleapis.com", "https://fonts.gstatic.com")))

    def test_reduced_motion_is_respected(self):
        source = page()
        self.assertIn("@media (prefers-reduced-motion: no-preference)", source)
        self.assertIn("matchMedia('(prefers-reduced-motion: reduce)')", source)

    def test_page_basics(self):
        source = page()
        self.assertIn('<html lang="id">', source)
        self.assertIn('<meta name="viewport" content="width=device-width, initial-scale=1">', source)
        self.assertRegex(source, r"<title>[^<]{2,40}</title>")
        self.assertIn('name="description"', source)


class PagesWorkflowTest(unittest.TestCase):

    def test_pages_workflow_deploys_the_landing_folder(self):
        workflow = PAGES.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertRegex(workflow, r"branches:\s*\[\s*main\s*\]")
        self.assertIn("- landing/**", workflow)
        for line in ("pages: write", "id-token: write", "contents: read", "path: landing"):
            with self.subTest(line=line):
                self.assertIn(line, workflow)
        uses = re.findall(r"uses:\s*(\S+)", workflow)
        self.assertEqual(
            sorted(use.split("@")[0] for use in uses),
            ["actions/checkout", "actions/configure-pages", "actions/deploy-pages", "actions/upload-pages-artifact"],
        )
        for use in uses:
            with self.subTest(use=use):
                self.assertRegex(use, r"@[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main()
