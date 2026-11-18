import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import agent_log  # noqa: E402
from tools import export_extension_vectors as export  # noqa: E402

SHIPPED = ROOT / "extension" / "src" / "shared" / "vectors"


class VectorFilesTest(unittest.TestCase):
    def test_the_files_in_the_repo_match_the_python_code(self):
        # Kalau gagal: jalankan `python tools/export_extension_vectors.py` dan commit hasilnya.
        with tempfile.TemporaryDirectory() as folder:
            export.main(Path(folder))

            for name in export.VECTORS:
                with self.subTest(name=name):
                    fresh = (Path(folder) / name).read_text(encoding="utf-8")
                    shipped = (SHIPPED / name).read_text(encoding="utf-8").replace("\r\n", "\n")
                    self.assertEqual(shipped, fresh)


class TicketVectorTest(unittest.TestCase):
    def setUp(self):
        self.vectors = export.ticket_vectors()

    def test_every_reason_is_covered(self):
        reasons = {case["expect"] for case in self.vectors["cases"]}
        self.assertEqual(reasons, {None, "bad_form", "unknown_key", "bad_signature", "wrong_task", "wrong_device",
                                   "old_seq", "expired"})

    def test_rotation_cases_behave(self):
        expect = {case["name"]: case["expect"] for case in self.vectors["cases"]}
        self.assertIsNone(expect["rotation: new key signs, both listed"])
        self.assertIsNone(expect["rotation: old key still listed"])
        self.assertEqual(expect["rotation: new key, old list"], "unknown_key")

    def test_canonical_text_keeps_non_ascii(self):
        texts = [item["canonical"] for item in self.vectors["canonical"]]
        self.assertTrue(any("😀" in text and " " in text for text in texts))
        self.assertTrue(any("\\u001f" in text for text in texts))


class SecretVectorTest(unittest.TestCase):
    def test_vectors_cover_the_hard_inputs(self):
        spans = {item["text"]: item["spans"] for item in export.secret_vectors()}
        self.assertEqual(spans["Kirim ke Jl. Mawar 12, kode pos 40115, tahun 2026"], [])
        self.assertEqual(spans["😀 4111 1111 1111 1111"], [[2, 21, "card"]])
        self.assertTrue(spans["angka ٤١١١ ١١١١ ١١١١ ١١١١ arab"])
        self.assertEqual([span[2] for span in spans["dua kartu 5555 5555 5555 4444 dan 4111 1111 1111 1111"]], ["card", "card"])


class LogTextVectorTest(unittest.TestCase):
    def test_fallback_phrases_match_describe(self):
        text = export.log_text_vectors()
        line = agent_log.describe({"kind": "aneh", "decision": "block", "reason": "baru", "result": None}, date(2026, 11, 18))
        self.assertEqual(line.action, text["unknown_action"].format(kind="aneh"))
        self.assertEqual(line.reason, text["unknown_reason"].format(reason="baru"))
        self.assertEqual(set(text["chain"]), {"ok", "broken", "missing", "extra", "unchecked"})


if __name__ == "__main__":
    unittest.main()
