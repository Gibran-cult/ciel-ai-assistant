import ast
import io
import logging
import unittest
from pathlib import Path

from pypdf import PdfReader, PdfWriter


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
SOURCE = APP_PATH.read_text(encoding="utf-8")


def app_constant(name):
    for node in ast.parse(SOURCE).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == name:
            return ast.literal_eval(node.value)
    raise KeyError(name)


def load(**overrides):
    namespace = {
        "io": io,
        "PdfReader": PdfReader,
        "logger": logging.getLogger("test_pdf_attachments"),
        "MAX_FILE_CHARS": app_constant("MAX_FILE_CHARS"),
        "MAX_PDF_PAGES": app_constant("MAX_PDF_PAGES"),
        "TABLE_FILE_TYPES": app_constant("TABLE_FILE_TYPES"),
        "TABLE_PREVIEW_ROWS": app_constant("TABLE_PREVIEW_ROWS"),
        "MAX_TABLE_CHARS": app_constant("MAX_TABLE_CHARS"),
        **overrides,
    }
    for node in ast.parse(SOURCE).body:
        if isinstance(node, ast.FunctionDef) and node.name in (
            "pdf_text", "read_text_file", "read_table_text", "file_extension",
        ):
            exec(compile(ast.Module(body=[node], type_ignores=[]), str(APP_PATH), "exec"), namespace)
    return namespace


def make_pdf(pages):
    """Minimal valid PDF, one page per string (Helvetica text)."""
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for text in pages:
        content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET" if text else ""
        objects.append(f"<< /Length {len(content)} >>\nstream\n{content}\nendstream")
        content_ref = len(objects)
        objects.append(
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {content_ref} 0 R /Resources << /Font << /F1 3 0 R >> >> >>"
        )
        kids.append(f"{len(objects)} 0 R")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"

    out, offsets = b"%PDF-1.4\n", []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{offset:010d} 00000 n \n" for offset in offsets).encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


class Upload:
    def __init__(self, name, data):
        self.name, self._data = name, data

    def getvalue(self):
        return self._data


class PdfAttachmentTest(unittest.TestCase):

    def read(self, name, data, **overrides):
        return load(**overrides)["read_text_file"](Upload(name, data))

    def test_pdf_text_is_extracted_like_a_text_file(self):
        data, error = self.read("bab1.pdf", make_pdf(["Hukum Newton pertama", "Inersia dan gaya"]))
        self.assertIsNone(error)
        self.assertEqual(data["name"], "bab1.pdf")
        self.assertIn("Hukum Newton pertama", data["text"])
        self.assertIn("Inersia dan gaya", data["text"])
        self.assertFalse(data["truncated"])

    def test_extraction_stops_at_the_character_limit(self):
        pages = [f"Halaman {i} " + "isi " * 20 for i in range(30)]
        data, error = self.read("panjang.PDF", make_pdf(pages), MAX_FILE_CHARS=200)
        self.assertIsNone(error)
        self.assertTrue(data["truncated"])
        self.assertEqual(len(data["text"]), 200)

    def test_extraction_stops_at_the_page_limit(self):
        ns = load(MAX_PDF_PAGES=3)
        text = ns["pdf_text"](make_pdf([f"halaman{i}" for i in range(10)]))
        self.assertIn("halaman2", text)
        self.assertNotIn("halaman3", text)

    def test_scanned_pdf_without_text_is_refused_with_a_hint(self):
        data, error = self.read("scan.pdf", make_pdf(["", ""]))
        self.assertIsNone(data)
        self.assertIn("hasil scan", error)
        self.assertIn("foto", error)

    def test_damaged_pdf_is_refused_without_raising(self):
        with self.assertLogs("test_pdf_attachments", level="WARNING"):
            data, error = self.read("rusak.pdf", b"%PDF-1.4\nbukan pdf sungguhan")
        self.assertIsNone(data)
        self.assertEqual(error, "rusak.pdf: PDF tidak bisa dibaca.")

    def test_password_protected_pdf_is_refused(self):
        writer = PdfWriter(clone_from=PdfReader(io.BytesIO(make_pdf(["rahasia"]))))
        try:
            writer.encrypt(user_password="sandi", algorithm="RC4-128")
        except Exception as error:  # pragma: no cover - depends on crypto support
            self.skipTest(f"PDF encryption unavailable: {error}")
        buffer = io.BytesIO()
        writer.write(buffer)

        data, error = self.read("kunci.pdf", buffer.getvalue())
        self.assertIsNone(data)
        self.assertEqual(error, "kunci.pdf: PDF ini dikunci kata sandi.")

    def test_text_files_still_work_and_binary_non_pdf_is_refused(self):
        data, error = self.read("catatan.md", "# Judul\nisi".encode())
        self.assertIsNone(error)
        self.assertEqual(data["text"], "# Judul\nisi")
        self.assertEqual(self.read("foto.txt", b"\x00\x01\x02")[1], "foto.txt: bukan file teks.")

    def test_pdf_is_accepted_in_chat_and_projects_and_installed_on_deploy(self):
        self.assertIn("pdf", app_constant("ALLOWED_FILE_TYPES"))
        self.assertIn("file_type=ALLOWED_FILE_TYPES + ALLOWED_IMAGE_TYPES", SOURCE)
        self.assertIn("type=ALLOWED_FILE_TYPES", SOURCE)
        requirements = (APP_PATH.parent / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("pypdf", requirements)


if __name__ == "__main__":
    unittest.main()
