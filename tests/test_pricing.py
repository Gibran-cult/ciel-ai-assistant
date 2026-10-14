import unittest

from streamlit.testing.v1 import AppTest

import pricing


def render_page(contact_url=None):
    import pricing as page

    page.render_pricing(contact_url=contact_url)


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


class PricingRenderTest(unittest.TestCase):

    def test_renders_all_plans_without_contact(self):
        at = AppTest.from_function(render_page).run()

        self.assertFalse(at.exception)
        html = " ".join(md.value for md in at.markdown)
        for plan in pricing.PLANS:
            self.assertIn(plan["name"], html)
        self.assertIn("Rp79.000", html)

        disabled = [b for b in at.button if b.label == "Segera hadir"]
        self.assertEqual(len(disabled), 2)
        self.assertTrue(all(b.disabled for b in disabled))

    def test_yearly_toggle_updates_prices(self):
        at = AppTest.from_function(render_page).run()
        at.button_group(key="pricing_billing").set_value("yearly").run()

        self.assertFalse(at.exception)
        html = " ".join(md.value for md in at.markdown)
        self.assertIn("Ditagih Rp790.000 per tahun", html)
        self.assertIn("Rp65.833", html)


if __name__ == "__main__":
    unittest.main()
