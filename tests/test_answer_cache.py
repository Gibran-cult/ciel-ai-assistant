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

    def test_time_sensitive_questions_are_not_cacheable(self):
        for text in ("berita hari ini apa", "harga emas sekarang", "jadwal UTBK 2026", "latest news"):
            self.assertFalse(cacheable_question(text), text)

    def test_general_questions_are_cacheable(self):
        for text in ("Apa itu machine learning?", "Bedanya regresi dan klasifikasi", "halo", "rekomendasi buku statistik"):
            self.assertTrue(cacheable_question(text), text)
        self.assertFalse(cacheable_question("?!"))
        self.assertFalse(cacheable_question("a" * 301))


class AnswerCacheTest(unittest.TestCase):
    def test_get_returns_stored_answer_until_ttl(self):
        now = [1000.0]
        cache = AnswerCache(ttl=60, clock=lambda: now[0])
        cache.put("k", "jawaban")
        self.assertEqual(cache.get("k"), "jawaban")
        now[0] += 61
        self.assertIsNone(cache.get("k"))
        self.assertIsNone(cache.get("tidak-ada"))

    def test_oldest_entry_is_evicted_when_full(self):
        cache = AnswerCache(max_entries=2)
        cache.put("a", "1")
        cache.put("b", "2")
        cache.put("c", "3")
        self.assertIsNone(cache.get("a"))
        self.assertEqual((cache.get("b"), cache.get("c")), ("2", "3"))


if __name__ == "__main__":
    unittest.main()
