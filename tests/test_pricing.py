import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

import pricing


def render_page(contact_url=None, rate_limits=(20, 60), memory_enabled=False):
    import pricing as page

    page.render_pricing(contact_url=contact_url, rate_limits=rate_limits, memory_enabled=memory_enabled)


def page_text(at):
    return " ".join(md.value for md in at.markdown)


class PricingLogicTest(unittest.TestCase):

    def test_format_idr_uses_dot_thousands(self):
        self.assertEqual(pricing.format_idr(0), "Rp0")
        self.assertEqual(pricing.format_idr(79_000), "Rp79.000")
        self.assertEqual(pricing.format_idr(1_490_000), "Rp1.490.000")
        self.assertEqual(pricing.format_idr(65_833.33), "Rp65.833")

    def test_planned_price_names_the_plan_as_a_plan(self):
        pro = next(p for p in pricing.PLANS if p["id"] == "pro")
        team = next(p for p in pricing.PLANS if p["id"] == "team")
        self.assertEqual(pricing.planned_price(pro), "Rencana Rp79.000/bulan")
        self.assertEqual(pricing.planned_price(team), "Rencana Rp149.000/bulan per pengguna")

    def test_plans_have_unique_ids_and_one_available_free_plan(self):
        ids = [p["id"] for p in pricing.PLANS]
        self.assertEqual(len(ids), len(set(ids)))
        available = [p for p in pricing.PLANS if p["available"]]
        self.assertEqual([p["id"] for p in available], ["free"])
        self.assertEqual(available[0]["monthly"], 0)

    def test_contact_url_only_allows_https_and_mailto(self):
        self.assertEqual(pricing.safe_contact_url(" https://ciel.ai/kontak "), "https://ciel.ai/kontak")
        self.assertEqual(pricing.safe_contact_url("mailto:halo@ciel.ai"), "mailto:halo@ciel.ai")
        self.assertIsNone(pricing.safe_contact_url("javascript:alert(1)"))
        self.assertIsNone(pricing.safe_contact_url("http://insecure.example"))
        self.assertIsNone(pricing.safe_contact_url(None))


class PricingHonestyTest(unittest.TestCase):
    # The page used to sell Pro (Rp79.000) for long-term memory, photos and
    # projects, which every visitor already gets for free. Paid plans must not
    # claim free features. "riset web" is free; Riset Skripsi is Pro-only
    # (enforced in app.py by riset_refusal), so the check names the free one.

    FREE_FEATURE_WORDS = ("memory", "foto", "proyek", "csv", "riset web", "lampiran")

    def test_unavailable_plans_do_not_claim_free_features(self):
        for plan in pricing.PLANS:
            if plan["available"]:
                continue
            with self.subTest(plan=plan["id"]):
                for feature in plan["features"]:
                    self.assertFalse(
                        any(word in feature.lower() for word in self.FREE_FEATURE_WORDS),
                        f"{plan['id']} claims a free feature: {feature}",
                    )

    def test_free_plan_lists_what_the_app_offers(self):
        free = " ".join(pricing.PLANS[0]["features"]).lower()
        for word in ("riset", "csv", "foto", "proyek"):
            self.assertIn(word, free)

    def test_free_plan_extras_follow_the_app_config(self):
        self.assertEqual(
            pricing.free_plan_extras((5, 50), memory_enabled=True),
            ("Long-term memory pribadi (perlu login)", "5 pesan/jam tanpa login, 50 pesan/jam setelah login"),
        )
        self.assertEqual(pricing.free_plan_extras((5, 50), memory_enabled=False), ("5 pesan/jam",))

    def test_app_passes_its_limits_and_login_state(self):
        app = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
        self.assertIn("rate_limits=(RATE_LIMIT_PER_HOUR, RATE_LIMIT_PER_HOUR_LOGIN)", app)
        self.assertIn("memory_enabled=AUTH_ENABLED", app)


class PricingRenderTest(unittest.TestCase):

    def test_renders_all_plans_without_contact(self):
        at = AppTest.from_function(render_page).run()

        self.assertFalse(at.exception)
        html = page_text(at)
        for plan in pricing.PLANS:
            self.assertIn(plan["name"], html)
        self.assertIn("Rp79.000", html)
        self.assertIn("Fitur inti Ciel gratis.", html)
        self.assertIn("Riset Skripsi", html)
        self.assertIn("Apakah Riset Skripsi menuliskan skripsi saya?", html)

        self.assertIn("Rencana Rp149.000/bulan per pengguna", html)
        self.assertIn("Belum bisa dibeli", html)

        # Only the free plan has a button; paid plans are listed, not sold.
        self.assertEqual([b.label for b in at.button], ["Mulai chat"])
        self.assertFalse(at.button[0].disabled)
        self.assertEqual(len(at.button_group), 0)
        self.assertNotIn("Hubungi kami", html)

    def test_contact_url_adds_a_link_but_no_purchase_button(self):
        at = AppTest.from_function(render_page, kwargs={"contact_url": "mailto:halo@ciel.ai"}).run()

        self.assertFalse(at.exception)
        self.assertEqual([b.label for b in at.button], ["Mulai chat"])
        self.assertIn('<a href="mailto:halo@ciel.ai">Hubungi kami</a>', page_text(at))

    def test_free_plan_and_faq_follow_memory_state(self):
        with_login = page_text(AppTest.from_function(
            render_page, kwargs={"rate_limits": (5, 50), "memory_enabled": True}).run())
        self.assertIn("Long-term memory pribadi (perlu login)", with_login)
        self.assertIn("5 pesan/jam tanpa login, 50 pesan/jam setelah login", with_login)
        self.assertIn("hanya bisa dibaca oleh akunmu sendiri", with_login)

        without_login = page_text(AppTest.from_function(
            render_page, kwargs={"rate_limits": (5, 50), "memory_enabled": False}).run())
        self.assertNotIn("Long-term memory pribadi", without_login)
        self.assertIn("5 pesan/jam", without_login)
        self.assertIn("belum aktif di deployment ini", without_login)


if __name__ == "__main__":
    unittest.main()
