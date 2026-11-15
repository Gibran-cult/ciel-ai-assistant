"""guard/limits.py: batas belanja per transaksi dan per bulan."""

import unittest
from datetime import datetime, timezone

from guard.limits import LimitVerdict, SpendLimits, check_spend, month_key

LIMITS = SpendLimits(per_tx=500_000, per_month=1_500_000)


class MonthKeyTest(unittest.TestCase):
    def test_month_follows_jakarta_time(self):
        self.assertEqual(month_key(datetime(2026, 11, 30, 16, 59, tzinfo=timezone.utc)), "2026-11")
        self.assertEqual(month_key(datetime(2026, 11, 30, 17, 30, tzinfo=timezone.utc)), "2026-12")

    def test_year_boundary(self):
        self.assertEqual(month_key(datetime(2026, 12, 31, 17, 0, tzinfo=timezone.utc)), "2027-01")

    def test_naive_time_is_read_as_utc(self):
        self.assertEqual(month_key(datetime(2026, 11, 30, 17, 30)), "2026-12")


class CheckSpendTest(unittest.TestCase):
    def test_within_limits(self):
        self.assertEqual(check_spend(200_000, LIMITS, 1_000_000, 300_000), LimitVerdict(True, None, 100_000, 300_000))

    def test_purchases_off_by_default(self):
        self.assertEqual(check_spend(10_000, SpendLimits(), 0, 50_000).reason, "purchases_off")
        self.assertEqual(check_spend(10_000, SpendLimits(per_tx=100_000), 0, 50_000).reason, "purchases_off")

    def test_broken_limits_turn_purchases_off(self):
        for limits in (SpendLimits(per_tx=True, per_month=1_000_000), SpendLimits(per_tx="500000", per_month=1_000_000),
                       SpendLimits(per_tx=500_000, per_month=None), SpendLimits(per_tx=-1, per_month=1_000_000)):
            with self.subTest(limits=limits):
                self.assertEqual(check_spend(10_000, limits, 0, 50_000), LimitVerdict(False, "purchases_off", 0, 0))

    def test_limit_exceeded(self):
        for total, spent, cap in ((500_001, 0, 600_000), (400_000, 1_200_000, 500_000), (200_000, 0, 150_000), (200_000, 0, 0)):
            with self.subTest(total=total, spent=spent, cap=cap):
                verdict = check_spend(total, LIMITS, spent, cap)
                self.assertEqual((verdict.ok, verdict.reason), (False, "limit_exceeded"))

    def test_exactly_at_limit_is_allowed(self):
        self.assertTrue(check_spend(500_000, LIMITS, 1_000_000, 500_000).ok)

    def test_broken_amounts_are_refused(self):
        for total in (0, -5, 199_999.5, True, "200000", None):
            with self.subTest(total=total):
                self.assertEqual(check_spend(total, LIMITS, 0, 500_000).reason, "limit_exceeded")
        self.assertEqual(check_spend(100_000, LIMITS, -1, 500_000).reason, "limit_exceeded")

    def test_broken_spent_or_cap_is_refused(self):
        for spent in (None, "0", 10.5, True):
            with self.subTest(spent=spent):
                self.assertEqual(check_spend(100_000, LIMITS, spent, 500_000).reason, "limit_exceeded")
        for cap in (None, "500000", True, -1):
            with self.subTest(cap=cap):
                self.assertEqual(check_spend(100_000, LIMITS, 0, cap).reason, "limit_exceeded")

    def test_remaining_never_negative(self):
        verdict = check_spend(100_000, LIMITS, 1_600_000, 500_000)
        self.assertEqual(verdict.remaining_month, 0)
        self.assertEqual(check_spend(None, LIMITS, 0, 500_000), LimitVerdict(False, "limit_exceeded", 500_000, 1_500_000))


if __name__ == "__main__":
    unittest.main()
