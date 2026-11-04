"""Evaluator rumus aman untuk grafik.

Teks rumus dari model itu TIDAK tepercaya, jadi tidak pernah lewat eval/exec.
Alurnya: tokenisasi dengan daftar karakter yang diizinkan, sisipkan perkalian
implisit (2x, 3(x+1), 2pi), parse dengan ast, periksa tiap node terhadap
allowlist, lalu kompilasi jadi closure numpy. Semua konstanta dijadikan
float64 sehingga pangkat besar menjadi inf (lalu nan), bukan bilangan bulat raksasa.
"""

import ast
import re
from typing import Callable

import numpy as np

MAX_CHARS = 120
MAX_NODES = 60

_FUNCTIONS: dict[str, Callable] = {
    "sin": np.sin, "cos": np.cos, "tan": np.tan,
    "asin": np.arcsin, "acos": np.arccos, "atan": np.arctan,
    "sqrt": np.sqrt, "exp": np.exp, "abs": np.abs,
    "ln": np.log, "log": np.log10,
}
_CONSTANTS = {"pi": np.pi, "e": np.e}
_VALUE_NAMES = {"x", *_CONSTANTS}  # nama yang boleh langsung dikalikan dengan tetangganya

_TOKEN = re.compile(r"\s*(?:(\d+\.?\d*|\.\d+)|([A-Za-z_]\w*)|(\*\*|[-+*/^()×−]))")
_BINOPS = {ast.Add: np.add, ast.Sub: np.subtract, ast.Mult: np.multiply,
           ast.Div: np.divide, ast.Pow: np.power}


class ExpressionError(ValueError):
    """Rumus tidak valid atau tidak diizinkan; pesannya berbahasa Indonesia."""


def _tokenize(text: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    pos = 0
    text = text.rstrip()
    while pos < len(text):
        match = _TOKEN.match(text, pos)
        if not match:
            raise ExpressionError(f"Karakter tidak dikenali di dekat '{text[pos:pos + 5].strip()}'.")
        number, name, op = match.groups()
        if number is not None:
            tokens.append(("num", number))
        elif name is not None:
            tokens.append(("name", name))
        else:
            tokens.append(("op", {"^": "**", "×": "*", "−": "-"}.get(op, op)))
        pos = match.end()
    return tokens


def _preprocess(text: str) -> str:
    out: list[str] = []
    prev: tuple[str, str] | None = None
    for kind, value in _tokenize(text):
        if prev is not None:
            left_ok = prev[0] == "num" or prev[1] == ")" or (prev[0] == "name" and prev[1] in _VALUE_NAMES)
            right_ok = kind in ("num", "name") or value == "("
            if left_ok and right_ok and not (prev[0] == "num" and kind == "num"):
                out.append("*")
        out.append(value)
        prev = (kind, value)
    return " ".join(out)


def _build(node: ast.AST) -> Callable[[np.ndarray], np.ndarray]:
    if isinstance(node, ast.Constant):
        if type(node.value) not in (int, float):
            raise ExpressionError("Hanya angka yang boleh dipakai sebagai konstanta.")
        value = np.float64(node.value)
        return lambda x: value
    if isinstance(node, ast.Name):
        if node.id == "x":
            return lambda x: x
        if node.id in _CONSTANTS:
            value = np.float64(_CONSTANTS[node.id])
            return lambda x: value
        raise ExpressionError(f"Nama '{node.id}' tidak dikenal. Gunakan x, pi, atau e.")
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        op, left, right = _BINOPS[type(node.op)], _build(node.left), _build(node.right)
        return lambda x: op(left(x), right(x))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        operand = _build(node.operand)
        if isinstance(node.op, ast.USub):
            return lambda x: np.negative(operand(x))
        return operand
    if isinstance(node, ast.Call):
        if not (isinstance(node.func, ast.Name) and node.func.id in _FUNCTIONS):
            raise ExpressionError("Fungsi tidak dikenal. Yang tersedia: " + ", ".join(_FUNCTIONS) + ".")
        if len(node.args) != 1 or node.keywords:
            raise ExpressionError(f"Fungsi {node.func.id} butuh tepat satu argumen.")
        func, arg = _FUNCTIONS[node.func.id], _build(node.args[0])
        return lambda x: func(arg(x))
    raise ExpressionError("Rumus hanya boleh berisi angka, x, pi, e, operator + - * / ^, dan fungsi dasar.")


def compile_expression(text: str) -> Callable[[np.ndarray], np.ndarray]:
    """Parse rumus dalam x sekali, kembalikan fungsi vektor; hasil tak hingga jadi nan."""
    if not isinstance(text, str) or not text.strip():
        raise ExpressionError("Rumus kosong.")
    if len(text) > MAX_CHARS:
        raise ExpressionError(f"Rumus terlalu panjang (maksimal {MAX_CHARS} karakter).")
    try:
        tree = ast.parse(_preprocess(text), mode="eval")
    except (SyntaxError, ValueError) as exc:
        raise ExpressionError("Rumus tidak bisa dibaca; periksa tanda kurung dan operatornya.") from exc
    if sum(1 for _ in ast.walk(tree)) > MAX_NODES:
        raise ExpressionError("Rumus terlalu rumit untuk digambar.")
    evaluate = _build(tree.body)

    def run(x: np.ndarray) -> np.ndarray:
        xs = np.asarray(x, dtype=np.float64)
        with np.errstate(all="ignore"):
            y = np.broadcast_to(np.asarray(evaluate(xs), dtype=np.float64), xs.shape)
            return np.where(np.isfinite(y), y, np.nan)

    return run
