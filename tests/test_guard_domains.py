"""guard/domains.py: pemeriksa alamat, pencocokan persis, dan deteksi domain mirip."""

import unittest

from guard.domains import HostCheck, check_url, lookalike_of, match_allowed

ALLOWED = ("shopee.co.id", "tokopedia.com")


class CheckUrlTest(unittest.TestCase):
    def test_normalizes_case_port_and_trailing_dot(self):
        self.assertEqual(check_url("https://Shopee.co.id.:443/mall"), HostCheck("shopee.co.id", None))

    def test_problems(self):
        cases = {
            "http://shopee.co.id/": ("shopee.co.id", "insecure"),
            "https://shopee.co.id@evil.example/": ("evil.example", "userinfo"),
            "https://192.168.1.10/": ("192.168.1.10", "ip"),
            "https://[::1]/": ("::1", "ip"),
            "https://xn--shope-9ua.co.id/": ("xn--shope-9ua.co.id", "punycode"),
            "https://shopée.co.id/": (None, "punycode"),
            "javascript:alert(1)": (None, "malformed"),
            "shopee.co.id": (None, "malformed"),
            "https://localhost/": (None, "malformed"),
            "": (None, "malformed"),
        }
        for url, expected in cases.items():
            with self.subTest(url=url):
                self.assertEqual(check_url(url), HostCheck(*expected))

    def test_never_raises_on_garbage(self):
        for junk in (None, 12, "https://", "https://[", "\x00"):
            self.assertEqual(check_url(junk).problem, "malformed")


class MatchAllowedTest(unittest.TestCase):
    def test_exact_and_subdomain(self):
        self.assertEqual(match_allowed("shopee.co.id", ALLOWED), "shopee.co.id")
        self.assertEqual(match_allowed("mall.shopee.co.id", ALLOWED), "shopee.co.id")

    def test_label_boundary(self):
        self.assertIsNone(match_allowed("notshopee.co.id", ALLOWED))
        self.assertIsNone(match_allowed("shopee.co.id.evil.com", ALLOWED))


class LookalikeTest(unittest.TestCase):
    def test_flags_imitations(self):
        cases = {
            "shopee.co.id.promo-murah.com": "shopee.co.id",
            "sh0pee.co.id": "shopee.co.id",
            "shoppe.co.id": "shopee.co.id",
            "tokopedia-official.shop": "tokopedia.com",
            "tokopedla.com": "tokopedia.com",
        }
        for host, expected in cases.items():
            with self.subTest(host=host):
                self.assertEqual(lookalike_of(host, ALLOWED), expected)

    def test_leaves_real_and_unrelated_hosts(self):
        self.assertIsNone(lookalike_of("mall.shopee.co.id", ALLOWED))
        self.assertIsNone(lookalike_of("example.org", ALLOWED))


if __name__ == "__main__":
    unittest.main()
