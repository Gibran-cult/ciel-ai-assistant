"""Penggambar grafik/diagram dari spec jawaban (visuals.py)."""

import json
import subprocess
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from answer_blocks import VISUAL_KINDS, Visual, parse_answer  # noqa: E402
from visuals import LIGHT, build_figure, describe, render_png, render_svg  # noqa: E402

PROMPT_EXAMPLE = {
    "fungsi": '{"jenis": "fungsi", "judul": "f(x) = x^2 - 4x + 3", "fungsi": [{"rumus": "x^2 - 4x + 3", "label": "f(x)"}], "x": [-1, 5], "titik": [{"x": 1, "y": 0, "label": "(1, 0)"}, {"x": 3, "y": 0, "label": "(3, 0)"}]}',
    "batang": '{"jenis": "batang", "label": ["A", "B"], "nilai": [12, 7], "satuan": "siswa"}',
    "garis": '{"jenis": "garis", "x": ["Jan", "Feb", "Mar"], "seri": [{"label": "Penjualan", "nilai": [5, 8, 6]}]}',
    "garis-bilangan": '{"jenis": "garis-bilangan", "interval": [{"dari": 2, "sampai": null, "dari_tutup": false, "sampai_tutup": false}]}',
    "bangun": '{"jenis": "bangun", "bentuk": "segitiga", "sisi": {"a": "6 cm", "b": "8 cm", "c": "10 cm"}}',
    "alur": '{"jenis": "alur", "langkah": ["Penguapan", "Kondensasi", "Presipitasi"], "siklus": true}',
}


def visual_from_json(body):
    segments = parse_answer(f"```ciel-grafik\n{body}\n```")
    assert len(segments) == 1 and isinstance(segments[0], Visual), segments
    return segments[0].spec


SPECS = {kind: visual_from_json(PROMPT_EXAMPLE[kind]) for kind in VISUAL_KINDS}


def valid_fungsi(rumus, x):
    return visual_from_json(json.dumps({"jenis": "fungsi", "fungsi": [{"rumus": rumus}], "x": x}))


def valid_alur(langkah, siklus=False):
    return visual_from_json(json.dumps({"jenis": "alur", "langkah": langkah, "siklus": siklus}))


class VisualsTest(unittest.TestCase):
    def test_every_kind_renders_png_and_svg(self):
        for kind, spec in SPECS.items():
            with self.subTest(kind=kind):
                self.assertTrue(render_png(spec).startswith(b"\x89PNG"))
                self.assertIn("<svg", render_svg(spec))

    def test_svg_uses_theme_tokens_only(self):
        for kind, spec in SPECS.items():
            with self.subTest(kind=kind):
                svg = render_svg(spec)
                self.assertNotRegex(svg, r"#0[0-8]0[0-8]0[0-8]")
                self.assertNotRegex(svg, r"(fill|stroke):\s*#(?!ffffff00)")
                self.assertIn('width="100%"', svg)
                self.assertIn('role="img"', svg)
                self.assertIn("viewBox", svg)
                self.assertIn("var(--c-", svg)

    def test_svg_keeps_text_as_text_and_has_alt(self):
        svg = render_svg(SPECS["batang"])
        self.assertIn("aria-label=", svg)
        self.assertIn(">A<", svg)

    def test_asymptote_plot_renders_fast(self):
        spec = valid_fungsi("tan(x)", x=[-6, 6])
        render_png(SPECS["batang"])          # impor malas matplotlib bukan bagian dari render
        start = time.perf_counter()
        render_png(spec)
        self.assertLess(time.perf_counter() - start, 3)

    def test_asymptote_has_no_vertical_connectors(self):
        from visuals import _curve_segments
        import numpy as np
        xs = np.linspace(-6, 6, 600)
        with np.errstate(all="ignore"):
            ys = np.tan(xs)
        segs = _curve_segments(xs, ys)
        self.assertGreaterEqual(len(segs), 5)      # 4 asimtot -> 5 cabang
        for sx, sy in segs:
            self.assertFalse(np.any((sy[:-1] * sy[1:] < 0) & (np.abs(sy[:-1] - sy[1:]) > 10)))

    def test_labels_are_escaped_in_svg(self):
        svg = render_svg(valid_alur(["<script>alert(1)</script>", "b"]))
        self.assertNotIn("<script>", svg)

    def test_variants_render(self):
        extra = [
            visual_from_json('{"jenis": "bangun", "bentuk": "persegi-panjang", "panjang": "8 cm", "lebar": "5 cm"}'),
            visual_from_json('{"jenis": "bangun", "bentuk": "lingkaran", "jari_jari": "7 cm"}'),
            visual_from_json('{"jenis": "bangun", "bentuk": "segitiga", "sisi": {"a": "3", "b": "4", "c": "5"}, "tinggi": "2,4"}'),
            visual_from_json('{"jenis": "fungsi", "fungsi": [{"rumus": "sin(x)"}, {"rumus": "cos(x)"}], "x": [-6, 6], "y": [-2, 2]}'),
            visual_from_json('{"jenis": "fungsi", "fungsi": [{"rumus": "1/x"}], "x": [-5, 5]}'),
            valid_alur(["a", "b", "c", "d"]),
            valid_alur(["a", "b", "c", "d", "e", "f", "g", "h"], siklus=True),
            visual_from_json('{"jenis": "garis-bilangan", "interval": [{"dari": null, "sampai": -1, "sampai_tutup": true}, {"dari": 2, "sampai": 5, "dari_tutup": true}], "titik": [0]}'),
        ]
        for spec in extra:
            with self.subTest(spec=spec):
                self.assertTrue(render_png(spec).startswith(b"\x89PNG"))
                self.assertIn("<svg", render_svg(spec))

    def test_bangun_notes_not_to_scale(self):
        self.assertIn("(tidak sesuai skala)", render_svg(SPECS["bangun"]))

    def test_describe_is_indonesian_alt_text(self):
        self.assertEqual(describe(SPECS["fungsi"]),
                         "Grafik fungsi f(x) = x^2 - 4x + 3 untuk x dari -1 sampai 5")
        for spec in SPECS.values():
            self.assertTrue(describe(spec))

    def test_light_palette_and_figure(self):
        self.assertEqual(LIGHT["text"], "#161513")
        fig = build_figure(SPECS["batang"], LIGHT)
        self.assertTrue(hasattr(fig, "savefig"))

    def test_png_width(self):
        import struct
        png = render_png(SPECS["batang"], width_px=800)
        self.assertEqual(struct.unpack(">I", png[16:20])[0], 800)

    def test_invalid_specs_raise_value_error(self):
        for bad in ({}, {"jenis": "nope"}, {"jenis": "fungsi"}, "teks", None, [1]):
            for fn in (render_svg, render_png, describe, lambda s: build_figure(s, LIGHT)):
                with self.subTest(bad=bad, fn=getattr(fn, "__name__", "lambda")):
                    with self.assertRaises(ValueError) as ctx:
                        fn(bad)
                    self.assertIn("tidak valid", str(ctx.exception))

    def test_all_nan_function_shows_note_without_warnings(self):
        import warnings
        spec = valid_fungsi("sqrt(x)", x=[-5, -1])
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            svg = render_svg(spec)
            render_png(spec)
        self.assertIn("Tidak ada nilai real pada selang ini", svg)

    def test_importing_visuals_does_not_import_matplotlib(self):
        code = "import sys; sys.path.insert(0, %r); import visuals; print('matplotlib' in sys.modules)" % str(ROOT)
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
        self.assertEqual(out.stdout.strip(), "False")


if __name__ == "__main__":
    unittest.main()
