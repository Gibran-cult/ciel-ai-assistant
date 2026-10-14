import ast
import unittest
from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


class AppHygieneTest(unittest.TestCase):
    # check_backend_health (117 lines) stayed in app.py after the status panel
    # that used it was removed. Fail when a top-level function or constant is
    # never referenced, so dead code is noticed in review.

    def test_no_unused_top_level_functions_or_constants(self):
        tree = ast.parse(APP_PATH.read_text(encoding="utf-8"))

        defined = {}
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                defined[node.name] = node.lineno
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        defined[target.id] = node.lineno

        used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
        used |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}

        unused = {name: line for name, line in defined.items() if name not in used}
        self.assertEqual(unused, {}, f"unused top-level names in app.py (name: line): {unused}")


if __name__ == "__main__":
    unittest.main()
