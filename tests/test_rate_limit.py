import ast
import unittest
from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
SOURCE = APP_PATH.read_text(encoding="utf-8")


def load_app_function(name):
    tree = ast.parse(SOURCE)

    function_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )

    namespace = {}
    exec(compile(ast.Module(body=[function_node], type_ignores=[]), str(APP_PATH), "exec"), namespace)
    return namespace[name]


def default_limit(name):
    """Default of `NAME = get_int_config("NAME", default)` in app.py."""
    call = next(
        node.value
        for node in ast.parse(SOURCE).body
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == name
    )
    return call.args[1].value


rate_limit_full = load_app_function("rate_limit_full")
rate_limit_message = load_app_function("rate_limit_message")
# Pro feature quotas (FEATURE_QUOTAS in app.py) are covered in test_ciel_pro.
rate_limit_message.__globals__["FEATURE_QUOTAS"] = {}

HOUR, DAY = 3600, 86400


class RateLimitTest(unittest.TestCase):

    def test_allows_up_to_limit_then_blocks(self):
        store = {}

        results = [rate_limit_full(store, {"u": (3, HOUR)}, now=100 + i) for i in range(4)]

        self.assertEqual(results, [None, None, None, "u"])
        self.assertEqual(len(store["u"]), 3)

    def test_window_slides(self):
        store = {"u": [0, 10, 20]}

        self.assertEqual(rate_limit_full(store, {"u": (3, HOUR)}, now=3599), "u")
        self.assertIsNone(rate_limit_full(store, {"u": (3, HOUR)}, now=3600))
        self.assertEqual(store["u"], [10, 20, 3600])

    def test_shared_budget_blocks_new_visitors(self):
        store = {}
        limits = lambda visitor: {visitor: (5, HOUR), "anon:total:hour": (2, HOUR)}

        self.assertIsNone(rate_limit_full(store, limits("v1"), now=1))
        self.assertIsNone(rate_limit_full(store, limits("v2"), now=2))
        # Reloading the page gives a new visitor id, but the shared budget holds.
        self.assertEqual(rate_limit_full(store, limits("v3"), now=3), "anon:total:hour")

    def test_blocked_request_is_not_recorded(self):
        store = {"anon:total:hour": [1, 2]}

        self.assertEqual(rate_limit_full(store, {"v": (5, HOUR), "anon:total:hour": (2, HOUR)}, now=3), "anon:total:hour")
        self.assertNotIn("v", store)
        self.assertEqual(store["anon:total:hour"], [1, 2])

    def test_daily_limit_holds_after_the_hour_passes(self):
        store = {}
        limits = {"user:a:hour": (2, HOUR), "user:a:day": (3, DAY)}

        self.assertIsNone(rate_limit_full(store, limits, now=0))
        self.assertIsNone(rate_limit_full(store, limits, now=1))
        self.assertEqual(rate_limit_full(store, limits, now=2), "user:a:hour")
        # The hourly window has emptied, the daily one has not.
        self.assertIsNone(rate_limit_full(store, limits, now=HOUR + 5))
        self.assertEqual(rate_limit_full(store, limits, now=HOUR + 6), "user:a:day")
        self.assertIsNone(rate_limit_full(store, limits, now=DAY + 2))

    def test_expired_keys_are_pruned(self):
        store = {"u": [0]}

        rate_limit_full(store, {"u": (1, HOUR), "other": (1, HOUR)}, now=10_000)

        self.assertEqual(store, {"u": [10_000], "other": [10_000]})
        store2 = {"old": [0]}
        rate_limit_full(store2, {"old": (0, HOUR)}, now=10_000)
        self.assertNotIn("old", store2)

    def test_message_names_the_limit_that_was_hit(self):
        self.assertIn("60 pesan per jam per akun", rate_limit_message("user:abc:hour", 60))
        self.assertIn("300 pesan per hari per akun", rate_limit_message("user:abc:day", 300))
        self.assertIn("Tanpa login, Ciel menerima hingga 10 pesan per jam", rate_limit_message("visitor:x:hour", 10))
        self.assertIn("tanpa login (300 pesan per hari)", rate_limit_message("anon:total:day", 300))
        self.assertIn("terlalu banyak pesan hari ini", rate_limit_message("all:total:day", 1500))

    def test_defaults_keep_guests_and_the_bill_in_check(self):
        self.assertEqual(
            {name: default_limit(name) for name in (
                "RATE_LIMIT_PER_HOUR",
                "RATE_LIMIT_PER_HOUR_LOGIN",
                "RATE_LIMIT_PER_DAY_LOGIN",
                "RATE_LIMIT_ANON_TOTAL_PER_HOUR",
                "RATE_LIMIT_ANON_TOTAL_PER_DAY",
                "RATE_LIMIT_TOTAL_PER_DAY",
            )},
            {
                "RATE_LIMIT_PER_HOUR": 10,
                "RATE_LIMIT_PER_HOUR_LOGIN": 60,
                "RATE_LIMIT_PER_DAY_LOGIN": 300,
                "RATE_LIMIT_ANON_TOTAL_PER_HOUR": 60,
                "RATE_LIMIT_ANON_TOTAL_PER_DAY": 300,
                "RATE_LIMIT_TOTAL_PER_DAY": 1500,
            },
        )

    def test_every_request_counts_toward_the_daily_total(self):
        source = ast.get_source_segment(SOURCE, next(
            n for n in ast.parse(SOURCE).body if isinstance(n, ast.FunctionDef) and n.name == "rate_limits_for_request"
        ))
        self.assertIn('limits["all:total:day"] = (RATE_LIMIT_TOTAL_PER_DAY, DAY)', source)
        self.assertIn('"anon:total:day": (RATE_LIMIT_ANON_TOTAL_PER_DAY, DAY)', source)
        self.assertIn('f"user:{user_key()}:day": (RATE_LIMIT_PER_DAY_PRO if pro else RATE_LIMIT_PER_DAY_LOGIN, DAY)', source)

    def test_pro_defaults_are_higher_but_still_capped(self):
        self.assertEqual(default_limit("RATE_LIMIT_PER_HOUR_PRO"), 150)
        self.assertEqual(default_limit("RATE_LIMIT_PER_DAY_PRO"), 800)
        self.assertEqual(default_limit("RISET_SKRIPSI_PER_DAY"), 5)
        # Pro traffic still counts toward the emergency daily total.
        self.assertLess(default_limit("RATE_LIMIT_PER_DAY_PRO"), default_limit("RATE_LIMIT_TOTAL_PER_DAY"))


if __name__ == "__main__":
    unittest.main()
