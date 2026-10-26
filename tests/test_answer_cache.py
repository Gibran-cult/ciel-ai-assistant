"""Cache jawaban untuk pertanyaan umum yang sering ditanya (answer_cache.py)."""

import unittest

from answer_cache import AnswerCache, cacheable_question, normalize_question, question_key


class QuestionKeyTest(unittest.TestCase):
    def test_normalize_ignores_case_spacing_and_punctuation(self):
        self.assertEqual(normalize_question("  Apa itu   AI?! "), "apa itu ai")
        self.assertEqual(question_key("Apa itu AI?"), question_key("apa itu ai"))
        self.assertNotEqual(normalize_question("c++"), normalize_question("c"))


class CacheableQuestionTest(unittest.TestCase):
    def test_personal_questions_are_not_cacheable(self):
        for text in ("siapa namaku? aku lupa", "Tugas saya apa ya", "gw harus belajar apa", "what is my name"):
            self.assertFalse(cacheable_question(text), text)

    def test_possessive_ku_suffix_is_personal(self):
        for text in ("siapa namaku", "skripsiku tentang apa", "ingat tugasku?"):
            self.assertFalse(cacheable_question(text), text)
        for text in ("apa itu perilaku konsumen", "rekomendasi buku statistik", "contoh bahasa baku", "suku bunga itu apa"):
            self.assertTrue(cacheable_question(text), text)

    def test_review_personal_and_memory_requests_are_not_cacheable(self):
        for text in (
            "siapa nama ku", "tugas sy apa", "apa yang kita bahas terakhir kali", "lanjutkan pembahasan",
            "what is our deadline", "ingat ya: jurusan teknik informatika",
            "lupakan semua memori tentang jurusan", "tampilkan dataset tersimpan",
        ):
            self.assertFalse(cacheable_question(text), text)

    def test_review_date_and_clock_questions_are_not_cacheable(self):
        for text in ("jam berapa?", "tanggal berapa", "hari apa ini", "kapan pendaftaran snbp", "selamat pagi", "yesterday", "current president"):
            self.assertFalse(cacheable_question(text), text)

    def test_operators_keep_different_questions_apart(self):
        for a, b in (("hitung 12/4", "hitung 12*4"), ("berapa 2^10", "berapa 2-10"), ("apakah 0.1 > 0.01", "apakah 0.1 < 0.01"), ("x != y", "x == y")):
            self.assertNotEqual(question_key(a), question_key(b), (a, b))

    def test_time_sensitive_questions_are_not_cacheable(self):
        for text in ("berita hari ini apa", "harga emas sekarang", "jadwal UTBK 2026", "latest news"):
            self.assertFalse(cacheable_question(text), text)

    def test_general_questions_are_cacheable(self):
        for text in ("Apa itu machine learning?", "Bedanya regresi dan klasifikasi", "halo", "rekomendasi buku statistik"):
            self.assertTrue(cacheable_question(text), text)
        self.assertFalse(cacheable_question("?!"))
        self.assertFalse(cacheable_question("a" * 301))


ANSWER = "Machine learning adalah cabang AI yang belajar dari data."


def asked_twice(cache, key, answer=ANSWER):
    cache.put(key, answer)
    cache.put(key, answer)


class AnswerCacheTest(unittest.TestCase):
    def test_answer_is_served_only_after_the_question_was_asked_twice(self):
        cache = AnswerCache()
        cache.put("k", ANSWER)
        self.assertIsNone(cache.get("k"))
        cache.put("k", ANSWER)
        self.assertEqual(cache.get("k"), ANSWER)

    def test_very_short_answers_are_not_stored(self):
        cache = AnswerCache()
        asked_twice(cache, "k", "Maaf.")
        self.assertIsNone(cache.get("k"))

    def test_get_returns_stored_answer_until_ttl(self):
        now = [1000.0]
        cache = AnswerCache(ttl=60, clock=lambda: now[0])
        asked_twice(cache, "k")
        self.assertEqual(cache.get("k"), ANSWER)
        now[0] += 61
        self.assertIsNone(cache.get("k"))
        self.assertIsNone(cache.get("tidak-ada"))
        # Setelah kedaluwarsa, hitungan tanya mulai dari nol lagi.
        cache.put("k", ANSWER)
        self.assertIsNone(cache.get("k"))

    def test_oldest_entry_is_evicted_when_full(self):
        cache = AnswerCache(max_entries=2)
        asked_twice(cache, "a", ANSWER + " 1")
        asked_twice(cache, "b", ANSWER + " 2")
        asked_twice(cache, "c", ANSWER + " 3")
        self.assertIsNone(cache.get("a"))
        self.assertEqual((cache.get("b"), cache.get("c")), (ANSWER + " 2", ANSWER + " 3"))


class SharedAnswerSafetyTest(unittest.TestCase):
    def test_answers_with_links_are_not_cached(self):
        for link in (
            "https://contoh.com/a", "http://x.id", "www.contoh.com", "[klik](https://a.b)",
            "buka masuk-akun-ciel.com sekarang", "daftar di ciel-login.xyz",
            # Final review: TLD lain, link protocol-relative, pemendek URL, alamat IP.
            "masuk ke ciel-login.ai", "[Login](//ciel-login.ai/a)", "[Login](ciel-login.zz)",
            "rb.gy/abc123", "lnkd.in/xyz", "http-nya 10.0.0.5/login", "buka promo.vip",
        ):
            cache = AnswerCache()
            asked_twice(cache, "k", f"{ANSWER} Lihat juga {link} untuk detailnya.")
            self.assertIsNone(cache.get("k"), link)

    def test_answers_without_links_are_still_cached(self):
        for detail in ("simpan sebagai data.csv", "pakai Python 3.12", "nilai 2.5 dan 3.75", "file laporan.docx", "contoh: a.b = c"):
            cache = AnswerCache()
            answer = f"{ANSWER} Contohnya {detail}."
            asked_twice(cache, "k", answer)
            self.assertEqual(cache.get("k"), answer, detail)


if __name__ == "__main__":
    unittest.main()
