import ast
import unittest
from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def load_app_function(name):
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"))

    function_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )

    namespace = {}
    exec(compile(ast.Module(body=[function_node], type_ignores=[]), str(APP_PATH), "exec"), namespace)
    return namespace[name]


rate_limit_ok = load_app_function("rate_limit_ok")


class RateLimitTest(unittest.TestCase):

    def test_allows_up_to_limit_then_blocks(self):
        store = {}

        results = [rate_limit_ok(store, {"u": 3}, now=100 + i) for i in range(4)]

        self.assertEqual(results, [True, True, True, False])
        self.assertEqual(len(store["u"]), 3)

    def test_window_slides(self):
        store = {"u": [0, 10, 20]}

        self.assertFalse(rate_limit_ok(store, {"u": 3}, now=3599))
        self.assertTrue(rate_limit_ok(store, {"u": 3}, now=3600))
        self.assertEqual(store["u"], [10, 20, 3600])

    def test_shared_budget_blocks_new_visitors(self):
        store = {}
        limits = lambda visitor: {visitor: 5, "anon:total": 2}

        self.assertTrue(rate_limit_ok(store, limits("v1"), now=1))
        self.assertTrue(rate_limit_ok(store, limits("v2"), now=2))
        # Reloading the page gives a new visitor id, but the shared budget holds.
        self.assertFalse(rate_limit_ok(store, limits("v3"), now=3))

    def test_blocked_request_is_not_recorded(self):
        store = {"anon:total": [1, 2]}

        self.assertFalse(rate_limit_ok(store, {"v": 5, "anon:total": 2}, now=3))
        self.assertNotIn("v", store)
        self.assertEqual(store["anon:total"], [1, 2])

    def test_expired_keys_are_pruned(self):
        store = {"u": [0]}

        rate_limit_ok(store, {"u": 1, "other": 1}, now=10_000)

        self.assertEqual(store, {"u": [10_000], "other": [10_000]})
        store2 = {"old": [0]}
        rate_limit_ok(store2, {"old": 0}, now=10_000)
        self.assertNotIn("old", store2)


if __name__ == "__main__":
    unittest.main()
