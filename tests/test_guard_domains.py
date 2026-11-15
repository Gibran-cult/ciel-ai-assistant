"""guard/domains.py: pemeriksa alamat, pencocokan persis, dan deteksi domain mirip."""

import unittest
from unittest import mock

from guard.domains import HostCheck, check_url, lookalike_of, match_allowed, normalize_host

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


class StrictHostTest(unittest.TestCase):
    """Temuan tinjauan akhir C1 dan C2: host hanya boleh berisi karakter nama host."""

    def test_urls_with_non_hostname_characters_are_malformed(self):
        for url in (
            "https://evil.com\\.shopee.co.id/toko",
            "https://evil.com%2f.shopee.co.id/",
            "https://evil.com .shopee.co.id/",
            "https://.shopee.co.id/",
            "https://shopee_mall.co.id/",
            "https://-shopee.co.id/",
            "https://" + "a" * 64 + ".co.id/",
            "https://" + ".".join(["abcdefgh"] * 40) + "/",
        ):
            with self.subTest(url=url):
                self.assertEqual(check_url(url), HostCheck(None, "malformed"))

    def test_normalize_host_accepts_what_a_browser_reports(self):
        cases = {
            "Shopee.co.id.": "shopee.co.id",
            "ibank.klikbca.com:443": "ibank.klikbca.com",
            "shopee.co.id.:443": "shopee.co.id",
            "mall.shopee.co.id": "mall.shopee.co.id",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_host(raw), expected)

    def test_normalize_host_refuses_everything_else(self):
        for raw in (
            "ibank.klikbca.com/login", "ibank.klikbca.com ", "evil.com/.shopee.co.id", "evil.com\\.shopee.co.id",
            "evil.com#.shopee.co.id", "user@evil.com", "https://shopee.co.id", "shopee.co.id\n", "localhost",
            "shopée.co.id", "", None, 7,
        ):
            with self.subTest(raw=raw):
                self.assertIsNone(normalize_host(raw))


class OversizedHostTest(unittest.TestCase):
    def test_oversized_host_is_refused_without_comparing(self):
        # Temuan minor: perbandingan huruf demi huruf pada label raksasa makan detik.
        with mock.patch("guard.domains.edit_distance", side_effect=AssertionError("label raksasa dibandingkan")):
            self.assertIsNone(lookalike_of("a" * 300 + ".com", ALLOWED))


if __name__ == "__main__":
    unittest.main()
