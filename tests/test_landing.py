"""Landing page contract: prices from pricing.py, known app links, honest claims."""

import base64
import hashlib
import json
import re
import struct
import sys
import unittest
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import payments  # noqa: E402
import pricing  # noqa: E402

LANDING = ROOT / "landing" / "index.html"
PAGES = ROOT / ".github" / "workflows" / "pages.yml"
APP = "https://app.ciel-ai.web.id/"
CONTACT = "gibranahmadn6@gmail.com"
SITE = "https://ciel-ai.web.id/"


def page():
    return LANDING.read_text(encoding="utf-8")


def csp(source):
    match = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)">', source)
    return match.group(1) if match else ""


def meta(source, key):
    match = re.search(rf'<meta (?:name|property)="{re.escape(key)}" content="([^"]*)">', source)
    return unescape(match.group(1)) if match else None


def structured_data(source):
    items = []
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', source, flags=re.S):
        data = json.loads(block)
        items.extend(data.get("@graph", [data]))
    return items


def visible_text(source):
    source = re.sub(r"<(script|style)\b.*?</\1>", " ", source, flags=re.S)
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", source)).split())


def png_size(path):
    data = path.read_bytes()[:24]
    assert data[:8] == b"\x89PNG\r\n\x1a\n", path
    return struct.unpack(">II", data[16:24])


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
        self.assertNotIn("streamlit.app", page())
        for link in app_links:
            with self.subTest(link=link):
                self.assertIn(link, {APP, f"{APP}?page=login", f"{APP}?page=pricing", f"{APP}?page=privacy", f"{APP}?page=terms"})
        for match in re.finditer(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page(), flags=re.S):
            label = visible_text(match.group(2))
            if label.startswith("Masuk"):
                with self.subTest(label=label):
                    self.assertEqual(match.group(1), f"{APP}?page=login")
        for link in re.findall(r'<a\b[^>]*href="([^"]+)"', page()):
            with self.subTest(link=link):
                self.assertRegex(link, r"^(#|https://|mailto:)")

    def test_footer_links_terms_and_privacy(self):
        footer = page()[page().index("<footer"):]
        self.assertIn(f'href="{APP}?page=terms"', footer)
        self.assertIn(f'href="{APP}?page=privacy"', footer)

    def test_no_placeholders_or_contact_stubs(self):
        source = page()
        self.assertNotRegex(visible_text(source), r"\[(?:[A-Z@]|YOUR|Syarat|Kebijakan)[^\]]*\]")

    def test_social_links_are_ciels_accounts(self):
        # Ciel created these accounts on 2026-10-24.
        social = {link for link in re.findall(r'href="([^"]+)"', page()) if "instagram.com" in link or "tiktok.com" in link}
        self.assertEqual(social, {"https://www.instagram.com/ciel_ai.1/", "https://www.tiktok.com/@ciel_ai.1"})
        for link in social:
            anchor = re.search(rf'<a\b[^>]*href="{re.escape(link)}"[^>]*>', page()).group(0)
            with self.subTest(link=link):
                self.assertIn('rel="noopener noreferrer"', anchor)
                self.assertIn('target="_blank"', anchor)
        text = visible_text(page())
        self.assertIn("Instagram @ciel_ai.1", text)
        self.assertIn("TikTok @ciel_ai.1", text)

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
                # Google Fonts, a file that ships in landing/ itself, or the
                # canonical link to the site's own address (loads nothing).
                local = "://" not in href and (LANDING.parent / href).is_file()
                self.assertTrue(local or href == SITE or href.startswith(("https://fonts.googleapis.com", "https://fonts.gstatic.com")))

    def test_reduced_motion_is_respected(self):
        source = page()
        self.assertIn("@media (prefers-reduced-motion: no-preference)", source)
        self.assertIn("matchMedia('(prefers-reduced-motion: reduce)')", source)

    def test_csp_hash_matches_inline_script(self):
        source = page().replace("\r\n", "\n")
        scripts = re.findall(r"<script>(.*?)</script>", source, flags=re.S)
        self.assertEqual(len(scripts), 1)
        # Browsers normalize newlines to LF before hashing, as done above.
        digest = base64.b64encode(hashlib.sha256(scripts[0].encode("utf-8")).digest()).decode()
        self.assertIn(f"script-src 'sha256-{digest}'", csp(source))

    def test_csp_is_strict(self):
        source = page()
        policy = csp(source)
        for directive in ("default-src 'none'", "base-uri 'none'", "form-action 'none'", "object-src 'none'"):
            with self.subTest(directive=directive):
                self.assertIn(directive, policy)
        self.assertNotIn("'unsafe-eval'", policy)
        self.assertNotRegex(policy, r"(^|\s)\*(\s|;|$)")
        self.assertIn('<meta name="referrer" content="strict-origin-when-cross-origin">', source)

    def test_page_basics(self):
        source = page()
        self.assertIn('<html lang="id">', source)
        self.assertIn('<meta name="viewport" content="width=device-width, initial-scale=1">', source)
        self.assertRegex(source, r"<title>[^<]{2,40}</title>")
        self.assertIn('name="description"', source)


class LandingAssetsTest(unittest.TestCase):

    def test_share_image_is_1200_by_630(self):
        self.assertEqual(png_size(LANDING.parent / "og.png"), (1200, 630))
        self.assertLess((LANDING.parent / "og.png").stat().st_size, 300_000)

    def test_png_icons_match_brand_files(self):
        for size in (192, 512):
            with self.subTest(size=size):
                name = f"ciel-icon-{size}.png"
                self.assertEqual((LANDING.parent / name).read_bytes(), (ROOT / "assets" / "brand" / name).read_bytes())


class SearchTagsTest(unittest.TestCase):

    def test_title_names_ciel_ai(self):
        self.assertIn("<title>Ciel AI: riset yang nggak ngarang</title>", page())

    def test_canonical_url_is_consistent(self):
        source = page()
        self.assertIn(f'<link rel="canonical" href="{SITE}">', source)
        self.assertEqual(meta(source, "og:url"), SITE)
        self.assertIn(f"<loc>{SITE}</loc>", (LANDING.parent / "sitemap.xml").read_text(encoding="utf-8"))
        self.assertIn(f"Sitemap: {SITE}sitemap.xml", (LANDING.parent / "robots.txt").read_text(encoding="utf-8"))

    def test_open_graph_and_twitter_tags(self):
        source = page()
        expected = {
            "og:type": "website", "og:site_name": "Ciel AI", "og:locale": "id_ID",
            "og:title": "Ciel AI: riset yang nggak ngarang",
            "og:image": f"{SITE}og.png", "og:image:width": "1200", "og:image:height": "630",
            "twitter:card": "summary_large_image",
        }
        for key, value in expected.items():
            with self.subTest(key=key):
                self.assertEqual(meta(source, key), value)
        self.assertEqual(meta(source, "og:description"), meta(source, "description"))
        self.assertTrue(meta(source, "og:image:alt"))

    def test_robots_allow_everything(self):
        robots = (LANDING.parent / "robots.txt").read_text(encoding="utf-8")
        self.assertIn("User-agent: *", robots)
        self.assertNotRegex(robots, r"(?m)^Disallow:\s*/\s*$")
        self.assertNotIn('name="robots"', page())

    def test_site_name_for_google(self):
        site = next(item for item in structured_data(page()) if item["@type"] == "WebSite")
        self.assertEqual((site["name"], site["url"]), ("Ciel AI", SITE))
        self.assertIn("Ciel", site["alternateName"])

    def test_structured_data_prices_match_pricing_py(self):
        app = next(item for item in structured_data(page()) if item["@type"] == "WebApplication")
        self.assertEqual(app["url"], SITE)
        offers = {offer["name"]: offer for offer in app["offers"]}
        for plan in pricing.PLANS:
            if plan["id"] in ("free", "pro"):
                with self.subTest(plan=plan["id"]):
                    self.assertEqual(offers[plan["name"]]["price"], str(plan["monthly"]))
                    self.assertEqual(offers[plan["name"]]["priceCurrency"], "IDR")
        # Pro is a one-time purchase for PRO_DAYS, not a recurring subscription.
        self.assertEqual(
            offers["Pro"]["eligibleDuration"],
            {"@type": "QuantitativeValue", "value": payments.PRO_DAYS, "unitCode": "DAY"},
        )

    def test_sitemap_has_no_hand_kept_lastmod(self):
        # Nothing bumps a hard-coded date when the page changes, and Google
        # stops trusting lastmod that is wrong, so the sitemap leaves it out.
        self.assertNotIn("<lastmod>", (LANDING.parent / "sitemap.xml").read_text(encoding="utf-8"))

    def test_organization_links_ciels_accounts(self):
        org = next(item for item in structured_data(page()) if item["@type"] == "Organization")
        self.assertEqual(org["logo"], f"{SITE}ciel-icon-512.png")
        self.assertEqual(set(org["sameAs"]), {"https://www.instagram.com/ciel_ai.1/", "https://www.tiktok.com/@ciel_ai.1"})


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
