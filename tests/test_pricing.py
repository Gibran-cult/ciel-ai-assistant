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

    def test_monthly_price_is_unchanged(self):
        pro = next(p for p in pricing.PLANS if p["id"] == "pro")
        self.assertEqual(pricing.plan_price(pro, "monthly"), (79_000, 79_000, "bulan"))

    def test_yearly_price_charges_ten_months(self):
        pro = next(p for p in pricing.PLANS if p["id"] == "pro")
        shown, total, period = pricing.plan_price(pro, "yearly")
        self.assertEqual(total, 790_000)
        self.assertEqual(period, "tahun")
        self.assertAlmostEqual(shown, 790_000 / 12)
        self.assertLess(shown, pro["monthly"])

    def test_plans_have_unique_ids_and_one_highlight(self):
        ids = [p["id"] for p in pricing.PLANS]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(sum(p["highlight"] for p in pricing.PLANS), 1)
        self.assertEqual(pricing.PLANS[0]["monthly"], 0)

    def test_contact_url_only_allows_https_and_mailto(self):
        self.assertEqual(pricing.safe_contact_url(" https://ciel.ai/kontak "), "https://ciel.ai/kontak")
        self.assertEqual(pricing.safe_contact_url("mailto:halo@ciel.ai"), "mailto:halo@ciel.ai")
        self.assertIsNone(pricing.safe_contact_url("javascript:alert(1)"))
        self.assertIsNone(pricing.safe_contact_url("http://insecure.example"))
        self.assertIsNone(pricing.safe_contact_url(None))


class PricingHonestyTest(unittest.TestCase):
    # The page used to sell Pro (Rp79.000) for long-term memory, photos and
    # projects, which every visitor already gets for free. Until plans are
    # enforced, paid plans are "Segera hadir" and must not claim free features.

    FREE_FEATURE_WORDS = ("memory", "foto", "projects", "csv", "riset", "lampiran")

    def test_only_available_plans_can_be_highlighted(self):
        highlighted = [p for p in pricing.PLANS if p["highlight"]]
        self.assertTrue(all(p["available"] for p in highlighted))

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
        for word in ("riset", "csv", "foto", "projects"):
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
        self.assertIn("Semua fitur Ciel saat ini gratis.", html)

        disabled = [b for b in at.button if b.label == "Segera hadir"]
        self.assertEqual(len(disabled), 2)
        self.assertTrue(all(b.disabled for b in disabled))
        self.assertFalse(next(b for b in at.button if b.label == "Mulai chat").disabled)
        self.assertNotIn("Hubungi kami", html)

    def test_paid_plans_stay_disabled_even_with_contact_url(self):
        at = AppTest.from_function(render_page, kwargs={"contact_url": "mailto:halo@ciel.ai"}).run()

        self.assertFalse(at.exception)
        self.assertEqual(len([b for b in at.button if b.label == "Segera hadir" and b.disabled]), 2)
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

    def test_yearly_toggle_updates_prices(self):
        at = AppTest.from_function(render_page).run()
        at.button_group(key="pricing_billing").set_value("yearly").run()

        self.assertFalse(at.exception)
        html = page_text(at)
        self.assertIn("Rencana: Rp790.000 per tahun", html)
        self.assertIn("Rp65.833", html)


if __name__ == "__main__":
    unittest.main()
