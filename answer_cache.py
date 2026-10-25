"""
Cache jawaban untuk pertanyaan umum yang sering ditanya.

Hanya pertanyaan yang jawabannya sama untuk semua orang yang boleh masuk:
bukan tentang diri penanya (memory pribadi) dan tidak bergantung waktu.
Jawaban baru disimpan setelah pertanyaan yang sama ditanya dua kali.
Cache tinggal di memori proses server, jadi hilang saat app restart.
"""

import hashlib
import re
import threading
import time

ANSWER_CACHE_TTL = 24 * 3600
ANSWER_CACHE_MAX_ENTRIES = 500
MAX_QUESTION_CHARS = 300

# Jawaban sependek ini biasanya permintaan maaf atau tool yang gagal, bukan jawaban.
MIN_ANSWER_CHARS = 40

# Pertanyaan tentang diri penanya, memory, dataset, atau percakapan sebelumnya:
# jawaban anonim ("aku belum tahu namamu") salah jika disajikan ke pengguna login.
PERSONAL_WORDS = re.compile(
    r"\b(aku|saya|gue|gw|gua|ane|ku|sy|aq|kita|kami|i|me|my|mine|we|our|us"
    r"|ingat|ingatkan|lupa|lupakan|memori|memory|dataset|tersimpan|simpan"
    r"|lanjut|lanjutkan|tadi|sebelumnya|terakhir)\b"
)

# Akhiran milik "-ku" (namaku, skripsiku), kecuali kata umum yang memang berakhiran "ku".
POSSESSIVE_KU = re.compile(r"\b\w{2,}ku\b")
WORDS_ENDING_IN_KU = {"buku", "suku", "kuku", "paku", "saku", "laku", "baku", "beku", "perilaku", "selaku", "berlaku"}

# Pertanyaan yang jawabannya berubah seiring waktu cepat basi.
TIME_WORDS = re.compile(
    r"\b(hari ini|hari apa|sekarang|terbaru|terkini|kemarin|besok|lusa|minggu ini|bulan ini|tahun ini"
    r"|tahun depan|jam|tanggal|kapan|pagi|siang|sore|malam|berita|harga|kurs|cuaca|skor|jadwal"
    r"|today|now|yesterday|tomorrow|current|recent|update|latest|news|price|weather|20\d\d)\b"
)


def normalize_question(text):
    """
    Huruf kecil, spasi dirapatkan, tanda baca di ujung dibuang. Tanda baca
    di tengah tetap ada supaya "12/4" dan "12*4" tidak dianggap sama.
    """
    return " ".join(str(text).lower().split()).strip(" ?!.,")


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
    """
    {kunci: (waktu, jawaban atau None)} ber-TTL. None berarti pertanyaan baru
    ditanya sekali; entri tertua dibuang saat penuh.
    """

    def __init__(self, ttl=ANSWER_CACHE_TTL, max_entries=ANSWER_CACHE_MAX_ENTRIES, clock=time.time):
        self.ttl = ttl
        self.max_entries = max_entries
        self.clock = clock
        self.lock = threading.Lock()
        self.entries = {}

    def _live(self, key):
        entry = self.entries.get(key)

        if entry is not None and self.clock() - entry[0] > self.ttl:
            del self.entries[key]
            return None

        return entry

    def get(self, key):
        with self.lock:
            entry = self._live(key)
            return entry[1] if entry else None

    def put(self, key, answer):
        answer = str(answer)

        if len(answer.strip()) < MIN_ANSWER_CHARS:
            return

        with self.lock:
            # Pertama kali ditanya: hanya dicatat. Kedua kali: jawabannya disimpan.
            seen = self._live(key) is not None
            self.entries.pop(key, None)
            self.entries[key] = (self.clock(), answer if seen else None)

            while len(self.entries) > self.max_entries:
                del self.entries[next(iter(self.entries))]
