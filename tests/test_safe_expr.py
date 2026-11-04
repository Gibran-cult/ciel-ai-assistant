"""Evaluator rumus yang aman untuk grafik (safe_expr.py)."""

import sys
import time
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from safe_expr import ExpressionError, compile_expression  # noqa: E402


class SafeExprTest(unittest.TestCase):
    def test_school_notation(self):
        f = compile_expression("2x^2 - 4x + 3")
        self.assertEqual(f(np.array([1.0]))[0], 1.0)
        self.assertAlmostEqual(compile_expression("log(100) + ln(e)")(np.array([0.0]))[0], 3.0)
        self.assertAlmostEqual(compile_expression("(x+1)(x-1)")(np.array([3.0]))[0], 8.0)

    def test_written_like_a_textbook(self):
        xs = np.array([0.5, 2.0])
        for text, expected in (("y = x^2", xs ** 2), ("f(x) = x^2", xs ** 2), ("g (x)=x^2", xs ** 2),
                               ("y=x²", xs ** 2), ("x²", xs ** 2), ("x³", xs ** 3), ("2·x", 2 * xs),
                               ("sin(πx)", np.sin(np.pi * xs)), ("2π", np.full(2, 2 * np.pi))):
            with self.subTest(text=text):
                np.testing.assert_allclose(compile_expression(text)(xs), expected)

    def test_rejects_non_math(self):
        for text in ("__import__('os')", "x.__class__", "open('a')", "[x]", "x if x else 1",
                     "lambda: 1", "y + 1", "x" * 121, "y = __import__('os')", "f(x) = x.__class__",
                     "y = x = 1", "z = x", "y == x", "ff(x) = x", "f(x) = ", "y = "):
            with self.subTest(text=text), self.assertRaises(ExpressionError):
                compile_expression(text)

    def test_huge_powers_are_fast_and_finite_or_nan(self):
        start = time.perf_counter()
        y = compile_expression("9**9**9")(np.linspace(-1, 1, 5))
        self.assertLess(time.perf_counter() - start, 0.5)
        self.assertTrue(np.all(np.isnan(y)))

    def test_singularities_become_gaps(self):
        y = compile_expression("1/x")(np.array([-1.0, 0.0, 1.0]))
        self.assertTrue(np.isnan(y[1]))
        self.assertEqual((y[0], y[2]), (-1.0, 1.0))


if __name__ == "__main__":
    unittest.main()
