"""Website contract (website/): prices from pricing.py, known app links, honest claims.

Mirrors tests/test_landing.py for the new Next.js site. The source checks always run; the
rendered-page checks run when `npm run build` has produced website/out/index.html.
"""

import base64
import hashlib
import re
import sys
import unittest
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pricing  # noqa: E402

WEBSITE = ROOT / "website"
SRC = WEBSITE / "src"
CONTENT = SRC / "content" / "site.ts"
BUILT = WEBSITE / "out" / "index.html"
APP = "https://app.ciel-ai.web.id/"
CONTACT = "gibranahmadn6@gmail.com"
ALLOWED_APP_LINKS = {APP, f"{APP}?page=login", f"{APP}?page=pricing", f"{APP}?page=privacy", f"{APP}?page=terms"}
FAKE_REPLY = "Aku nggak bisa meringkas jurnal itu, karena sejauh pencarianku, jurnal tersebut tidak ada."


def source_files():
    return [p for p in SRC.rglob("*") if p.suffix in {".ts", ".tsx", ".css"}]


def content():
    return CONTENT.read_text(encoding="utf-8")


def visible_text(source):
    source = re.sub(r"<(script|style)\b.*?</\1>", " ", source, flags=re.S)
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", source)).split())


def plan(plan_id):
    return next(p for p in pricing.PLANS if p["id"] == plan_id)


class WebsiteSourceTest(unittest.TestCase):
    def test_legend_sample_matches_the_app(self):
        """The "Contoh" screen claims the app's layout: its panel titles come from render_rail() and
        its question from a real Beranda template."""
        text = content()
        rail = (ROOT / "app.py").read_text(encoding="utf-8")
        rail = rail[rail.index("def render_rail(") :]
        rail = rail[: rail.index("\ndef ", 1)]
        for key in ("railSources", "railGaps", "railMemory"):
            with self.subTest(key=key):
                title = re.search(rf'{key}: "([^"]+)"', text)
                self.assertIsNotNone(title)
                self.assertIn(f'"{title.group(1)}"', rail)
        beranda = (ROOT / "beranda.py").read_text(encoding="utf-8")
        self.assertIn('"Analisis metode", "Analisis: [metode] cocok nggak buat data [jenis data]-ku?"', beranda)
        self.assertIn('question: "Analisis: IndoBERT cocok nggak buat data ulasan ojol-ku?"', text)

    def test_plans_match_pricing_py(self):
        text = content()
        free, pro = plan("free"), plan("pro")
        self.assertIn(f'name: "{free["name"]}"', text)
        self.assertIn('price: "Rp0"', text)
        self.assertIn(f'name: "{pro["name"]}"', text)
        self.assertIn(f'price: "{pricing.format_idr(pro["monthly"])}"', text)
        self.assertIn("per 30 hari", text)
        for p in (free, pro):
            for feature in p["features"]:
                with self.subTest(plan=p["id"], feature=feature):
                    self.assertIn(f'"{feature}"', text)

    def test_no_team_plan_and_no_hourly_numbers(self):
        text = content()
        self.assertNotIn("Rp149.000", text)
        self.assertNotRegex(text, r"\bTim\b")
        self.assertNotRegex(text, r"\d+\s*pesan\s*/?\s*(per\s*)?jam")

    def test_app_links_use_known_pages(self):
        for path in source_files():
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path.name):
                self.assertNotIn("streamlit.app", text)
        text = content()
        self.assertIn(f'export const APP = "{APP}";', text)
        for query in re.findall(r"\$\{APP\}(\?page=[a-z]+)", text):
            with self.subTest(query=query):
                self.assertIn(f"{APP}{query}", ALLOWED_APP_LINKS)

    def test_fake_journal_quoted_verbatim(self):
        text = content()
        self.assertIn(FAKE_REPLY, text)
        self.assertIn("Mau aku lanjut cari penelitian asli yang paling dekat dengan topik ini?", text)
        self.assertIn("Hendrawan & Sulistyo (2019)", text)

    def test_only_the_real_test_date(self):
        text = content()
        self.assertIn('testDate = "20 Oktober 2026"', text)
        self.assertEqual(re.findall(r"(?<!20 )Oktober 2026", text), [])

    def test_the_likely_wrong_smsa_claim_is_left_out(self):
        self.assertNotIn("SmSA", content())

    def test_no_em_dash_in_site_source(self):
        for path in source_files():
            with self.subTest(path=path.name):
                self.assertNotIn("—", path.read_text(encoding="utf-8"))

    def test_contact_and_social_accounts(self):
        text = content()
        self.assertIn(f'contactEmail = "{CONTACT}"', text)
        self.assertIn("https://www.instagram.com/ciel_ai.1/", text)
        self.assertIn("https://www.tiktok.com/@ciel_ai.1", text)


@unittest.skipUnless(BUILT.exists(), "run `npm run build` in website/ first")
class WebsiteBuildTest(unittest.TestCase):
    def page(self):
        return BUILT.read_text(encoding="utf-8")

    def test_rendered_links_are_known(self):
        source = self.page()
        app_links = set(re.findall(r'href="(https://app\.ciel-ai\.web\.id/[^"]*)"', source))
        self.assertTrue(app_links)
        self.assertLessEqual({unescape(link) for link in app_links}, ALLOWED_APP_LINKS)
        self.assertIn(f'href="{APP}?page=terms"', source)
        self.assertIn(f'href="{APP}?page=privacy"', source)
        self.assertEqual(set(re.findall(r'href="mailto:([^"]+)"', source)), {CONTACT})

    def test_social_links_open_safely(self):
        source = self.page()
        for url in ("https://www.instagram.com/ciel_ai.1/", "https://www.tiktok.com/@ciel_ai.1"):
            anchor = re.search(rf'<a[^>]*href="{re.escape(url)}"[^>]*>', source)
            with self.subTest(url=url):
                self.assertIsNotNone(anchor)
                self.assertIn('rel="noopener noreferrer"', anchor.group(0))
                self.assertIn('target="_blank"', anchor.group(0))
        text = visible_text(source)
        self.assertIn("Instagram @ciel_ai.1", text)
        self.assertIn("TikTok @ciel_ai.1", text)

    def test_rendered_text_is_honest(self):
        text = visible_text(self.page())
        self.assertIn(FAKE_REPLY, text)
        self.assertIn("Rp79.000", text)
        self.assertNotIn("—", text)
        self.assertEqual(re.findall(r"(?<!20 )Oktober 2026", text), [])

    def test_page_basics(self):
        source = self.page()
        self.assertIn('<html lang="id"', source)
        self.assertEqual(len(re.findall(r"<h1\b", source)), 1)
        self.assertNotRegex(source, r"user-scalable=no|maximum-scale=1")
        poster = re.search(r'<img[^>]*src="/robot-bust\.webp"[^>]*>', source)
        self.assertIsNotNone(poster)
        self.assertIn('fetchPriority="high"', poster.group(0).replace("fetchpriority", "fetchPriority"))
        self.assertNotIn('loading="lazy"', poster.group(0))

    def test_csp_hashes_every_inline_script(self):
        source = self.page()
        policy = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)"', source)
        self.assertIsNotNone(policy, "postbuild should insert the CSP meta")
        policy = unescape(policy.group(1))
        for directive in ("default-src 'none'", "base-uri 'none'", "form-action 'none'", "object-src 'none'"):
            self.assertIn(directive, policy)
        self.assertNotIn("'unsafe-eval'", policy)
        for body in re.findall(r"<script(?![^>]*\bsrc=)(?![^>]*application/ld\+json)[^>]*>(.*?)</script>", source, flags=re.S):
            digest = base64.b64encode(hashlib.sha256(body.encode("utf-8")).digest()).decode()
            with self.subTest(script=body[:40]):
                self.assertIn(f"'sha256-{digest}'", policy)


if __name__ == "__main__":
    unittest.main()
