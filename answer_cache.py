"""
Cache jawaban untuk pertanyaan umum yang sering ditanya.

Hanya pertanyaan yang jawabannya sama untuk semua orang yang boleh masuk:
bukan tentang diri penanya (memory pribadi) dan tidak bergantung waktu.
Cache tinggal di memori proses server, jadi hilang saat app restart.
"""

import hashlib
import re
import threading
import time

ANSWER_CACHE_TTL = 3 * 24 * 3600
ANSWER_CACHE_MAX_ENTRIES = 500
MAX_QUESTION_CHARS = 300

# Pertanyaan tentang diri penanya: jawaban anonim ("aku belum tahu namamu")
# salah jika disajikan ke pengguna login yang punya memory.
PERSONAL_WORDS = re.compile(r"\b(aku|saya|gue|gw|gua|ane|i|me|my|mine)\b")

# Akhiran milik "-ku" (namaku, skripsiku), kecuali kata umum yang memang berakhiran "ku".
POSSESSIVE_KU = re.compile(r"\b\w{2,}ku\b")
WORDS_ENDING_IN_KU = {"buku", "suku", "kuku", "paku", "saku", "laku", "baku", "beku", "perilaku", "selaku", "berlaku"}

# Pertanyaan yang jawabannya berubah seiring waktu cepat basi.
TIME_WORDS = re.compile(
    r"\b(hari ini|sekarang|terbaru|terkini|kemarin|besok|minggu ini|bulan ini|tahun ini"
    r"|berita|harga|kurs|cuaca|skor|jadwal|today|now|latest|news|price|weather|20\d\d)\b"
)


def normalize_question(text):
    """Huruf kecil, tanda baca jadi spasi (kecuali + dan #), spasi dirapatkan."""
    text = re.sub(r"[^\w\s+#]", " ", str(text).lower())
    return " ".join(text.split())


def cacheable_question(text):
    question = normalize_question(text)

    if not question or len(question) > MAX_QUESTION_CHARS:
        return False

    if PERSONAL_WORDS.search(question) or TIME_WORDS.search(question):
        return False

    return all(word in WORDS_ENDING_IN_KU for word in POSSESSIVE_KU.findall(question))


def question_key(text):
    return hashlib.sha256(normalize_question(text).encode("utf-8")).hexdigest()


class AnswerCache:
    """{kunci: (waktu simpan, jawaban)} ber-TTL; entri tertua dibuang saat penuh."""

    def __init__(self, ttl=ANSWER_CACHE_TTL, max_entries=ANSWER_CACHE_MAX_ENTRIES, clock=time.time):
        self.ttl = ttl
        self.max_entries = max_entries
        self.clock = clock
        self.lock = threading.Lock()
        self.entries = {}

    def get(self, key):
        with self.lock:
            entry = self.entries.get(key)

            if entry is None:
                return None

            if self.clock() - entry[0] > self.ttl:
                del self.entries[key]
                return None

            return entry[1]

    def put(self, key, answer):
        with self.lock:
            # Ditimpa = pindah ke paling baru dalam urutan dict.
            self.entries.pop(key, None)
            self.entries[key] = (self.clock(), str(answer))

            while len(self.entries) > self.max_entries:
                del self.entries[next(iter(self.entries))]
