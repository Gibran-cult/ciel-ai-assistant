"""Ekspor jawaban ke PDF dan gambar (answer_pdf.py)."""

import io
import subprocess
import sys
import unittest
from pathlib import Path

from PIL import Image
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from answer_pdf import (  # noqa: E402
    answer_pdf,
    answer_png,
    SPILL_NOTE,
    _compose,
    document_title,
    latex_to_text,
    wants_document,
)
from riset_export import report_filename  # noqa: E402

KUIS = '```ciel-kuis\n{"soal": "Akar dari $x^2=9$?", "pilihan": ["3", "±3", "9"], "jawaban": 1, "pembahasan": "Karena $x=3$ atau $x=-3$."}\n```'
GRAFIK = '```ciel-grafik\n{"jenis": "fungsi", "judul": "f(x) = x^2 - 4x + 3", "fungsi": [{"rumus": "x^2 - 4x + 3", "label": "f(x)"}], "x": [-1, 5]}\n```'
RUSAK = '```ciel-grafik\n{bukan json\n```'

MATH_ANSWER = (
    "# Persamaan Kuadrat\n\n"
    "Bentuk umum $ax^2 + bx + c = 0$ dengan **a** tidak nol.\n\n"
    "## Rumus\n\n" + r"$$x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$$" + "\n\n"
    "- Diskriminan positif: dua akar\n- Diskriminan nol: satu akar\n\n"
    "1. Hitung D\n2. Cari akar\n\n"
    "| D | Akar |\n|---|---|\n| > 0 | dua |\n| = 0 | satu |\n\n"
    "> Ingat: tanda minus pada $-b$.\n\n"
    f"{GRAFIK}\n\n{KUIS}\n\n{KUIS}\n\n"
    "Sumber:\n[1] Kemdikbud — Matematika SMA — https://buku.kemdikbud.go.id/mat\n"
)


def answer_pdf_png_source(content):
    """PDF 120 x 600 mm yang dirasterisasi answer_png, setelah catatan lanjutan."""
    from answer_pdf import _write_footer, _write_spill_note

    pdf = _compose(content, "Uji", png=True).pdf
    (_write_spill_note if pdf.page_no() > 1 else _write_footer)(pdf)
    return bytes(pdf.output())


def pdf_text(data):
    return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(data)).pages)


class AnswerPdfTest(unittest.TestCase):
    def test_pdf_has_title_quiz_key_and_sources(self):
        text = pdf_text(answer_pdf(MATH_ANSWER, "Persamaan Kuadrat"))
        for needle in ("Persamaan Kuadrat", "Latihan", "Kunci jawaban", "Sumber", "ciel-ai.web.id", "buku.kemdikbud.go.id"):
            self.assertIn(needle, text)
        self.assertNotIn('"jenis"', text)

    def test_broken_block_never_shows_raw_json(self):
        text = pdf_text(answer_pdf(f"Halo\n\n{RUSAK}\n\nSelesai", "Uji"))
        self.assertNotIn("bukan json", text)
        self.assertIn("Selesai", text)

    def test_latex_to_text(self):
        self.assertEqual(latex_to_text(r"\frac{x+1}{2} \le \sqrt{9} \times \pi"), "(x+1)/2 ≤ √9 × π")
        self.assertEqual(latex_to_text("x^2 + 2{,}5"), "x² + 2,5")
        self.assertEqual(latex_to_text(r"\frac{1}{2} + x_1 + \sqrt{x+1}"), "1/2 + x₁ + √(x+1)")

    def test_long_answer_paginates_and_png_is_capped(self):
        long = "\n\n".join(["Paragraf " + "kata " * 200] * 20 + [KUIS] * 20)
        self.assertGreater(len(PdfReader(io.BytesIO(answer_pdf(long, "Panjang"))).pages), 3)
        png = Image.open(io.BytesIO(answer_png(long, "Panjang")))
        self.assertEqual(png.width, 1080)
        self.assertLessEqual(png.height, 5400)

    def test_blockquote_is_a_tinted_box(self):
        def streams(data):
            return b"".join(p.get_contents().get_data() for p in PdfReader(io.BytesIO(data)).pages)

        tint = b"0.902 0.902 0.8863 rg"
        self.assertIn(tint, streams(answer_pdf("> **Ingat** ini penting\n\nIsi.", "Uji")))
        self.assertNotIn(tint, streams(answer_pdf("Tanpa callout.", "Uji")))
        # callout panjang yang melewati batas halaman tidak boleh error
        answer_pdf("Awal\n\n" + "> " + "kalimat callout panjang " * 400, "Uji")

    def test_png_spill_note_is_written_on_page_one(self):
        long = "\n\n".join(["Paragraf " + "kata " * 200] * 20)
        first_page = PdfReader(io.BytesIO(answer_pdf_png_source(long))).pages[0].extract_text()
        self.assertIn(SPILL_NOTE, first_page)
        self.assertNotIn(SPILL_NOTE, pdf_text(answer_pdf_png_source("Halo")))

    def test_png_of_short_answer_is_cropped(self):
        png = Image.open(io.BytesIO(answer_png("Halo dunia", "Uji")))
        self.assertEqual(png.width, 1080)
        self.assertLess(png.height, 1500)

    def test_emoji_and_symbols_do_not_raise(self):
        answer_pdf("Halo 😊 — 你好 — ∑ ∫ √2", "Uji")
        answer_png("Halo 😊", "Uji")

    def test_wants_document(self):
        for yes in ("buatkan PDF-nya", "lembar soal pecahan buat dicetak", "bisa di-print?"):
            self.assertTrue(wants_document(yes))
        for no in ("apa itu fotosintesis", "gambarkan grafik y = x^2", "printilan acara"):
            self.assertFalse(wants_document(no))

    def test_document_title(self):
        self.assertEqual(document_title("# Judul Saya\n\nisi", "apa saja"), "Judul Saya")
        self.assertEqual(document_title("tanpa judul", "jelaskan " * 20), "jelaskan " * 5 + "jelaskan")
        self.assertEqual(document_title("x", ""), "Jawaban Ciel")

    def test_report_filename_ext(self):
        self.assertEqual(report_filename("Kuadrat", prefix="Ciel", ext="pdf"), "Ciel - Kuadrat.pdf")
        self.assertTrue(report_filename("x").endswith(".docx"))

    def test_importing_answer_pdf_does_not_import_heavy_libs(self):
        code = (
            "import sys; sys.path.insert(0, %r); import answer_pdf; "
            "print([m for m in ('fpdf', 'pypdfium2', 'matplotlib') if m in sys.modules])" % str(ROOT)
        )
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
        self.assertEqual(out.stdout.strip(), "[]")


if __name__ == "__main__":
    unittest.main()
