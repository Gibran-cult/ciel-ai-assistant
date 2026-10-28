import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from beranda import RISET_KIND, TEMPLATES, greeting, has_riset_map, latest_riset, relative_time, templates_for


WIB = ZoneInfo("Asia/Jakarta")


def wib(*parts):
    return datetime(*parts, tzinfo=WIB).timestamp()


class TemplatesTest(unittest.TestCase):

    def keys(self, *args):
        return [template.key for template in templates_for(*args)]

    def test_templates_follow_the_context(self):
        self.assertEqual(self.keys(False, False, True, True), ["cari_jurnal", "jelasin", "analisis", "cek_referensi"])
        self.assertEqual(
            self.keys(True, True, True, True),
            ["cari_jurnal", "jelasin", "analisis", "cek_referensi", "ringkas_file", "kerangka"],
        )
        self.assertNotIn("cari_jurnal", self.keys(True, True, False, True))
        self.assertNotIn("kerangka", self.keys(True, True, True, False))
        self.assertNotIn("kerangka", self.keys(True, False, True, True))
        self.assertNotIn("ringkas_file", self.keys(False, True, True, True))

    def test_fill_templates_keep_their_brackets(self):
        texts = {template.key: template.text for template in TEMPLATES}
        self.assertEqual(texts["jelasin"], "Jelasin [konsep] pelan-pelan pakai contoh angka, lalu kasih 2 soal latihan.")
        self.assertEqual(texts["analisis"], "Analisis: [metode] cocok nggak buat data [jenis data]-ku?")
        self.assertEqual(texts["cek_referensi"], "Cek apakah referensi ini beneran ada: [tempel referensi]")
        self.assertEqual(texts["ringkas_file"], "Ringkas file proyek ini dan tandai klaim yang belum ada sumbernya.")

    def test_pro_templates_open_dialogs_instead_of_filling(self):
        by_key = {template.key: template for template in TEMPLATES}
        self.assertEqual((by_key["cari_jurnal"].action, by_key["cari_jurnal"].pro), ("riset", True))
        self.assertEqual((by_key["kerangka"].action, by_key["kerangka"].pro, by_key["kerangka"].label), ("kerangka", True, "Kerangka Bab 1–3"))
        self.assertEqual({template.action for template in TEMPLATES if not template.pro}, {"fill"})


class LatestRisetTest(unittest.TestCase):

    def chat(self, chat_id, project, updated, kinds, archived=False):
        messages = []
        for kind in kinds:
            messages.append({"role": "user", "content": "q"})
            messages.append({"role": "assistant", "content": "a", **({"kind": kind} if kind else {}), **({"error": True} if kind == "error" else {})})
        return {"id": chat_id, "project_id": project, "updated": updated, "messages": messages, "archived": archived}

    def test_latest_riset_in_project_and_everywhere(self):
        chats = [
            self.chat("a", "p1", 10, [RISET_KIND, None]),
            self.chat("b", None, 30, [RISET_KIND, RISET_KIND]),
            self.chat("c", "p1", 40, [None]),
            self.chat("d", "p1", 50, [RISET_KIND], archived=True),
        ]
        chat, index = latest_riset(chats, "p1")
        self.assertEqual((chat["id"], index), ("a", 1))
        chat, index = latest_riset(chats, None)
        self.assertEqual((chat["id"], index), ("b", 3))
        self.assertIsNone(latest_riset(chats, "p2"))

    def test_has_riset_map_counts_archived_chats(self):
        archived = self.chat("a", None, 10, [RISET_KIND], archived=True)
        self.assertTrue(has_riset_map(archived))
        self.assertFalse(has_riset_map(self.chat("b", None, 10, [None])))
        failed = self.chat("c", None, 10, ["error"])
        failed["messages"][1]["kind"] = RISET_KIND
        self.assertFalse(has_riset_map(failed))

    def test_app_uses_the_same_kind(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
        self.assertIn(f'RISET_KIND = "{RISET_KIND}"', source)

    def test_error_maps_do_not_count(self):
        chats = [self.chat("a", None, 10, ["error"])]
        chats[0]["messages"][1]["kind"] = RISET_KIND
        self.assertIsNone(latest_riset(chats, None))


def sentence_preview(text, limit=220):
    # Lives in app.py (re-run on every deploy) rather than beranda.py, after
    # Streamlit Cloud kept a stale beranda module and the app failed to import.
    import re
    from tests.test_ciel_pro import load_app
    return load_app(("MEMORY_PREVIEW_LIMIT", "SENTENCE_END", "sentence_preview"), re=re)["sentence_preview"](text, limit)


class SentencePreviewTest(unittest.TestCase):

    def test_short_text_is_whole(self):
        self.assertEqual(sentence_preview("Format sitasi APA 7"), ("Format sitasi APA 7", ""))

    def test_long_text_stops_at_a_sentence_end(self):
        text = "Satu dua tiga. " * 30
        preview, rest = sentence_preview(text.strip(), limit=50)
        self.assertEqual(preview, "Satu dua tiga. Satu dua tiga. Satu dua tiga.")
        self.assertEqual(f"{preview} {rest}", text.strip())

    def test_a_first_sentence_longer_than_the_limit_is_kept_whole(self):
        first = "Kalimat pertama yang sangat panjang " * 10 + "selesai."
        preview, rest = sentence_preview(f"{first} Kalimat kedua.", limit=50)
        self.assertEqual((preview, rest), (first, "Kalimat kedua."))


class TimeTextTest(unittest.TestCase):

    def test_greeting_uses_wib(self):
        self.assertEqual(greeting(wib(2026, 10, 20, 21, 0), "Kak Raka"), "Malam, Kak Raka.")
        self.assertEqual(greeting(wib(2026, 10, 20, 21, 0), None), "Malam.")
        self.assertEqual(greeting(wib(2026, 10, 20, 7, 0), "Raka"), "Pagi, Raka.")
        self.assertEqual(greeting(wib(2026, 10, 20, 12, 0), ""), "Siang.")
        self.assertEqual(greeting(wib(2026, 10, 20, 16, 30), "Raka"), "Sore, Raka.")
        self.assertEqual(greeting(wib(2026, 10, 20, 2, 0), "Raka"), "Malam, Raka.")

    def test_relative_time(self):
        now = wib(2026, 10, 20, 22, 0)  # Selasa
        self.assertEqual(relative_time(wib(2026, 10, 20, 21, 42), now), "21.42")
        self.assertEqual(relative_time(wib(2026, 10, 19, 23, 0), now), "Kemarin")
        self.assertEqual(relative_time(wib(2026, 10, 16, 9, 0), now), "Jum")
        self.assertEqual(relative_time(wib(2026, 10, 14, 9, 0), now), "Rab")
        self.assertEqual(relative_time(wib(2026, 10, 13, 9, 0), now), "13 Okt")
        self.assertEqual(relative_time(wib(2025, 12, 3, 9, 0), now), "3 Des 2025")


if __name__ == "__main__":
    unittest.main()
