"""Pemecah jawaban jadi segmen markdown/grafik/kuis dan perapian matematika (answer_blocks.py)."""

import json
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from answer_blocks import (  # noqa: E402
    VISUAL_KINDS, Broken, Markdown, Quiz, Visual, parse_answer, tidy_math,
)

GRAFIK = '```ciel-grafik\n{"jenis": "fungsi", "fungsi": [{"rumus": "x^2 - 4x + 3"}], "x": [-1, 5]}\n```'
KUIS = '```ciel-kuis\n{"soal": "Akar dari $x^2=9$?", "pilihan": ["3", "±3"], "jawaban": 1}\n```'

CONTRACT_VISUALS = [
    {"jenis": "batang", "label": ["A", "B"], "nilai": [12, 7], "satuan": "siswa"},
    {"jenis": "garis", "x": ["Jan", "Feb", "Mar"], "seri": [{"label": "Penjualan", "nilai": [5, 8, 6]}]},
    {"jenis": "garis-bilangan",
     "interval": [{"dari": 2, "sampai": None, "dari_tutup": False, "sampai_tutup": False}]},
    {"jenis": "bangun", "bentuk": "segitiga", "sisi": {"a": "6 cm", "b": "8 cm", "c": "10 cm"}},
    {"jenis": "alur", "langkah": ["Penguapan", "Kondensasi", "Presipitasi"], "siklus": True},
    {"jenis": "fungsi", "judul": "f(x) = x^2 - 4x + 3",
     "fungsi": [{"rumus": "x^2 - 4x + 3", "label": "f(x)"}], "x": [-1, 5],
     "titik": [{"x": 1, "y": 0, "label": "(1, 0)"}, {"x": 3, "y": 0, "label": "(3, 0)"}]},
]
CONTRACT_QUIZ = {"soal": "Berapa akar dari $x^2 - 5x + 6 = 0$?", "pilihan": ["2 dan 3", "1 dan 6", "-2 dan -3"],
                 "jawaban": 0, "pembahasan": "$(x-2)(x-3) = 0$."}


def fence(kind, payload):
    body = payload if isinstance(payload, str) else json.dumps(payload)
    return f"```ciel-{kind}\n{body}\n```"


def only(text):
    segs = parse_answer(text)
    assert len(segs) == 1, segs
    return segs[0]


class ParseAnswerTest(unittest.TestCase):
    def test_splits_markdown_visual_and_quiz(self):
        segs = parse_answer(f"Intro.\n\n{GRAFIK}\n\nTengah.\r\n\n{KUIS}\n\nPenutup.")
        self.assertEqual([type(s).__name__ for s in segs],
                         ["Markdown", "Visual", "Markdown", "Quiz", "Markdown"])
        self.assertEqual(segs[1].spec["jenis"], "fungsi")
        self.assertEqual(segs[3].jawaban, 1)

    def test_plain_text_and_empty(self):
        self.assertEqual(parse_answer("Halo dunia"), [Markdown("Halo dunia")])
        self.assertEqual(parse_answer(""), [])

    def test_contract_examples_parse(self):
        for spec in CONTRACT_VISUALS:
            with self.subTest(jenis=spec["jenis"]):
                seg = only(fence("grafik", spec))
                self.assertIsInstance(seg, Visual, seg)
                self.assertIn(seg.spec["jenis"], VISUAL_KINDS)
                json.dumps(seg.spec, sort_keys=True)
        quiz = only(fence("kuis", CONTRACT_QUIZ))
        self.assertIsInstance(quiz, Quiz)
        self.assertEqual(quiz.pilihan, ("2 dan 3", "1 dan 6", "-2 dan -3"))

    def test_defaults_are_filled(self):
        spec = only(GRAFIK).spec
        self.assertEqual(spec["judul"], "")
        self.assertEqual(spec["titik"], [])
        self.assertEqual(spec["fungsi"][0]["label"], "f(x)")
        self.assertIsInstance(spec["x"], list)
        alur = only(fence("grafik", {"jenis": "alur", "langkah": ["a", "b"]})).spec
        self.assertIs(alur["siklus"], False)
        quiz = only(fence("kuis", {"soal": "Ibu kota?", "jawaban": "Jakarta"}))
        self.assertEqual((quiz.pilihan, quiz.pembahasan, quiz.jawaban), ((), "", "Jakarta"))

    def test_unknown_keys_are_dropped(self):
        spec = only(fence("grafik", {"jenis": "alur", "langkah": ["a", "b"], "evil": "<script>"})).spec
        self.assertNotIn("evil", spec)

    def test_broken_blocks_degrade(self):
        cases = ['```ciel-grafik\n{"jenis": "pie"}\n```',
                 '```ciel-grafik\n{jenis: fungsi}\n```',
                 '```ciel-grafik\n{"jenis": "fungsi", "fungsi": [{"rumus": "__import__(1)"}], "x": [0, 1]}\n```',
                 '```ciel-kuis\n{"soal": "a", "pilihan": ["x"], "jawaban": 3}\n```',
                 '```ciel-grafik\n' + '{"jenis": "alur", "langkah": ["a"' + ', "a"' * 3000 + ']}\n```',
                 'Teks.\n\n```ciel-grafik\n{"jenis": "alur"']           # never closed
        for text in cases:
            with self.subTest(text=text[:40]):
                segs = parse_answer(text)
                self.assertTrue(any(isinstance(s, Broken) for s in segs))
                self.assertFalse(any("{" in s.text for s in segs if isinstance(s, Markdown)))

    def test_broken_kind(self):
        self.assertEqual(only('```ciel-grafik\n[]\n```').kind, "grafik")
        self.assertEqual(only('```ciel-kuis\nbukan json\n```').kind, "kuis")

    def test_invalid_specs(self):
        bad = [
            {"jenis": "fungsi", "fungsi": [], "x": [0, 1]},
            {"jenis": "fungsi", "fungsi": [{"rumus": "x"}] * 5, "x": [0, 1]},
            {"jenis": "fungsi", "fungsi": [{"rumus": "x"}], "x": [1, 1]},
            {"jenis": "fungsi", "fungsi": [{"rumus": "x"}], "x": [0, 1001]},
            {"jenis": "fungsi", "fungsi": [{"rumus": "x"}], "x": [0, 1], "titik": [{"x": 0, "y": 0}] * 11},
            {"jenis": "fungsi", "fungsi": [{"rumus": "x"}]},
            {"jenis": "batang", "label": ["A"], "nilai": [True]},
            {"jenis": "batang", "label": ["A"], "nilai": [1e999]},
            {"jenis": "batang", "label": ["A", "B"], "nilai": [1]},
            {"jenis": "batang", "label": list("abcdefghijklm"), "nilai": list(range(13))},
            {"jenis": "garis", "x": ["a", "b"], "seri": [{"label": "s", "nilai": [1]}]},
            {"jenis": "garis", "x": ["a"], "seri": [{"label": "s", "nilai": [1]}] * 5},
            {"jenis": "garis-bilangan", "interval": [{"dari": 0, "sampai": 1}] * 4},
            {"jenis": "bangun", "bentuk": "kubus"},
            {"jenis": "bangun", "bentuk": "segitiga", "sisi": {"a": "x" * 21, "b": "1", "c": "1"}},
            {"jenis": "alur", "langkah": ["satu"]},
            {"jenis": "alur", "langkah": ["a"] * 9},
            {"jenis": "alur", "langkah": ["a", "b" * 61]},
            {"jenis": "alur", "langkah": ["a", "b"], "siklus": "ya"},
        ]
        for spec in bad:
            with self.subTest(spec=str(spec)[:70]):
                self.assertIsInstance(only(fence("grafik", spec)), Broken)

    def test_nan_constant_rejected(self):
        self.assertIsInstance(only(fence("grafik", '{"jenis": "batang", "label": ["A"], "nilai": [NaN]}')), Broken)

    def test_deeply_nested_json_is_broken_not_crash(self):
        self.assertIsInstance(only(fence("grafik", "[" * 3900)), Broken)

    def test_quiz_rules(self):
        self.assertIsInstance(only(fence("kuis", {"soal": "a", "pilihan": ["x", "y"], "jawaban": True})), Broken)
        self.assertIsInstance(only(fence("kuis", {"soal": "a", "pilihan": ["x", "y"], "jawaban": "x"})), Broken)
        self.assertIsInstance(only(fence("kuis", {"soal": "a", "pilihan": list("abcdef"), "jawaban": 0})), Broken)
        self.assertIsInstance(only(fence("kuis", {"pilihan": ["x", "y"], "jawaban": 0})), Broken)
        self.assertIsInstance(only(fence("kuis", {"soal": "a", "jawaban": 2})), Broken)

    def test_fifth_visual_is_broken(self):
        segs = parse_answer("\n\n".join([GRAFIK] * 5))
        self.assertEqual([type(s).__name__ for s in segs],
                         ["Visual"] * 4 + ["Broken"])

    def test_twenty_first_quiz_is_broken(self):
        segs = parse_answer("\n\n".join([KUIS] * 21))
        self.assertEqual(sum(isinstance(s, Quiz) for s in segs), 20)
        self.assertIsInstance(segs[-1], Broken)

    def test_math_is_tidied_in_markdown_segments(self):
        segs = parse_answer(r"Nilai \(x = 2,5\) ya.")
        self.assertEqual(segs[0].text, "Nilai $x = 2{,}5$ ya.")


class RobustnessTest(unittest.TestCase):
    def test_unhashable_jenis_is_broken(self):
        for body in ('{"jenis": []}', '{}', '{"jenis": {"a": 1}}', '{"jenis": 5}'):
            with self.subTest(body=body):
                self.assertIsInstance(only(f"```ciel-grafik\n{body}\n```"), Broken)

    def test_nul_placeholder_text_does_not_raise(self):
        self.assertIsInstance(parse_answer("a \x000\x00 b")[0], Markdown)
        self.assertNotIn("\x00", tidy_math("pakai `kode` \x000\x00 \x001\x00"))

    def test_fuzz_never_raises(self):
        rng = random.Random(1234)
        pieces = ["```ciel-grafik\n", "```ciel-kuis\n", "```\n", "```", "$", "$$", "\\(", "\\)", "\\[", "\\]",
                  "\x00", "\x000\x00", "{", "}", "[", "]", '"jenis"', '"alur"', ":", ",", "1,5", "`", "\n",
                  "\r\n", " ", "x", "5", '"soal"', '"jawaban"', "null", "NaN", "\\"]
        for _ in range(3000):
            text = "".join(rng.choice(pieces) for _ in range(rng.randint(0, 30)))
            self.assertIsInstance(parse_answer(text), list)


class TidyMathTest(unittest.TestCase):
    def test_currency_dollars_are_escaped(self):
        self.assertEqual(tidy_math("harga $5 dan $10"), r"harga \$5 dan \$10")
        for kept in ("$5x + 3 = 8$", "$x^2$", "$$\\frac{1}{2}$$", "`$5`"):
            self.assertEqual(tidy_math(kept), kept)

    def test_stray_dollar_on_odd_line(self):
        self.assertEqual(tidy_math("biaya $x$ dan $"), r"biaya $x$ dan \$")

    def test_decimal_comma_and_delimiters(self):
        self.assertEqual(tidy_math(r"Jadi \(x = 2,5\)."), "Jadi $x = 2{,}5$.")
        self.assertEqual(tidy_math(r"\[y = 0,25x\]"), "$$y = 0{,}25x$$")
        self.assertEqual(tidy_math("1,5 kg"), "1,5 kg")   # outside math: unchanged

    def test_code_is_left_alone(self):
        fenced = "```python\nharga = '$5 dan $10'  # 1,5 \\(x\\)\n```"
        self.assertEqual(tidy_math(fenced), fenced)
        unclosed = "```\n$5 dan 1,5"
        self.assertEqual(tidy_math(unclosed), unclosed)
        self.assertEqual(tidy_math(r"pakai `\(x\)` dan \(y\)"), r"pakai `\(x\)` dan $y$")

    def test_multiline_display_math(self):
        self.assertEqual(tidy_math("$$\nx = 1,5\n$$"), "$$\nx = 1{,}5\n$$")

    def test_idempotent(self):
        once = tidy_math(r"harga $5 dan $10, \(x = 2,5\)")
        self.assertEqual(tidy_math(once), once)


if __name__ == "__main__":
    unittest.main()
