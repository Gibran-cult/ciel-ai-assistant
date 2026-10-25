# Ciel Answer Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pertanyaan umum yang sering ditanya dijawab dari cache, tanpa memanggil Langflow/DeepSeek lagi.

**Architecture:** Modul murni baru `answer_cache.py` memegang normalisasi pertanyaan, filter "boleh di-cache", dan cache in-memory ber-TTL + batas entri. `app.py` memegang satu instance lewat `@st.cache_resource` (pola yang sama dengan `rate_limit_state()`), mencarinya sebelum `check_rate_limit()` di jalur kirim pesan, dan hanya mengisinya dari jawaban pengunjung anonim (tanpa long-term memory). Balasan dari cache ditandai `"cached": True`; pesan berikutnya di chat itu membawa tanya-jawab tadi sebagai konteks, karena session Langflow tidak pernah melihatnya.

**Tech Stack:** Python 3, Streamlit (`st.cache_resource`), `threading.Lock`, `hashlib`, `unittest`.

**Spec:** Permintaan Ciel 2026-10-25 di sesi ini ("pakai cache buat jawab pertanyaan yang sering ditanya") dan keputusan cakupan "Bersama, aman": cache diisi hanya dari jawaban pengunjung anonim, dipakai semua orang (anonim dan login) untuk pesan pertama di chat baru.

## Global Constraints

- Cache **diisi** hanya jika `memory_owner_id() == ""` (anonim). Jawaban user login tidak pernah masuk cache (bisa memuat memory pribadi).
- Cache **dipakai** hanya untuk pesan pertama chat, teks saja: tanpa gambar, tanpa file terlampir, tanpa file proyek/peta riset (`payload == text`), tanpa tabel di chat, bukan Riset/Kerangka/Cek kutipan.
- `CielError` (jawaban gagal) tidak pernah disimpan.
- TTL `ANSWER_CACHE_TTL = 3 * 24 * 3600` detik; batas `ANSWER_CACHE_MAX_ENTRIES = 500`, entri tertua dibuang dulu.
- Cache in-process saja (hilang saat Streamlit Cloud reboot) — tanpa tabel Supabase, tanpa biaya baru.
- Log tidak boleh memuat teks pertanyaan; cukup 8 karakter pertama hash kunci.
- Teks UI dan komentar kode dalam Bahasa Indonesia, mengikuti gaya `app.py`. Tidak ada penanda UI baru untuk jawaban cache (aturan anti-slop).

## Review Focus

1. Pertanyaan pribadi dari anonim ("siapa namaku?", "tugas saya apa") di-cache lalu disajikan ke user login yang berharap Ciel ingat dirinya → harus ditolak oleh `cacheable_question` (kata ganti orang pertama). Tes di Task 1.
2. Pertanyaan berbasis waktu ("berita hari ini", "harga emas sekarang", "jadwal 2026") menyajikan jawaban basi → ditolak `cacheable_question`. Tes di Task 1.
3. Pertanyaan lanjutan setelah jawaban cache ("jelasin lebih detail") dikirim ke session Langflow kosong → payload harus membawa tanya-jawab sebelumnya. Tes di Task 2.
4. Variasi huruf besar/spasi/tanda baca ("Apa itu AI?" vs "apa itu ai") meleset → kunci sama. Tes di Task 1.
5. Jawaban gagal atau jawaban user login masuk cache → tidak pernah disimpan. Tes di Task 2.

---

### Task 1: Modul `answer_cache.py`

**Files:**
- Create: `answer_cache.py`
- Test: `tests/test_answer_cache.py`
- Modify: `.github/workflows/ci.yml` (tambahkan `tests.test_answer_cache` ke daftar "Run offline test suite")

**Interfaces:**
- Produces:
  - `ANSWER_CACHE_TTL: int = 259200`, `ANSWER_CACHE_MAX_ENTRIES: int = 500`
  - `normalize_question(text: str) -> str` — huruf kecil, karakter selain `\w`, spasi, `+`, `#` jadi spasi, spasi dirapatkan, di-strip.
  - `cacheable_question(text: str) -> bool` — `False` jika hasil normalisasi kosong atau > 300 karakter, memuat kata utuh orang pertama (`aku saya gue gw gua ane i me my mine`), memuat kata waktu (`hari ini, sekarang, terbaru, terkini, kemarin, besok, minggu ini, bulan ini, tahun ini, berita, harga, kurs, cuaca, skor, jadwal, today, now, latest, news, price, weather`), atau memuat tahun `20\d\d`.
  - `question_key(text: str) -> str` — `sha256(normalize_question(text)).hexdigest()`.
  - `class AnswerCache(ttl=ANSWER_CACHE_TTL, max_entries=ANSWER_CACHE_MAX_ENTRIES, clock=time.time)` dengan `get(key: str) -> str | None` (buang dan kembalikan `None` jika kedaluwarsa) dan `put(key: str, answer: str) -> None` (menimpa kunci sama; buang entri tertua saat penuh). Semua akses di bawah satu `threading.Lock`. Penyimpanan: `dict` berurutan `{key: (stored_at, answer)}`.

- [ ] **Step 1: Write the failing tests** di `tests/test_answer_cache.py` (`unittest`, impor langsung dari `answer_cache` seperti `tests/test_draft_check.py`):

```python
def test_normalize_ignores_case_spacing_and_punctuation(self):
    self.assertEqual(normalize_question("  Apa itu   AI?! "), "apa itu ai")
    self.assertEqual(question_key("Apa itu AI?"), question_key("apa itu ai"))
    self.assertNotEqual(normalize_question("c++"), normalize_question("c"))

def test_personal_questions_are_not_cacheable(self):
    for text in ("siapa namaku? aku lupa", "Tugas saya apa ya", "gw harus belajar apa", "what is my name"):
        self.assertFalse(cacheable_question(text), text)

def test_time_sensitive_questions_are_not_cacheable(self):
    for text in ("berita hari ini apa", "harga emas sekarang", "jadwal UTBK 2026", "latest news"):
        self.assertFalse(cacheable_question(text), text)

def test_general_questions_are_cacheable(self):
    for text in ("Apa itu machine learning?", "Bedanya regresi dan klasifikasi", "halo"):
        self.assertTrue(cacheable_question(text), text)
    self.assertFalse(cacheable_question("?!"))
    self.assertFalse(cacheable_question("a" * 301))

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
    cache.put("a", "1"); cache.put("b", "2"); cache.put("c", "3")
    self.assertIsNone(cache.get("a"))
    self.assertEqual((cache.get("b"), cache.get("c")), ("2", "3"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest -v tests.test_answer_cache`
Expected: FAIL — `ModuleNotFoundError: No module named 'answer_cache'`

- [ ] **Step 3: Implement `answer_cache.py`** sesuai Interfaces di atas. Regex kata dipakai dengan batas kata `\b` pada teks yang sudah dinormalisasi, supaya "buku" tidak tertangkap sebagai "ku" dan "nowhere" tidak tertangkap sebagai "now".

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest -v tests.test_answer_cache`
Expected: 6 tests, OK

- [ ] **Step 5: Add `tests.test_answer_cache` to CI** di `.github/workflows/ci.yml`, tepat setelah `tests.test_draft_check \`.

- [ ] **Step 6: Commit**

```bash
git add answer_cache.py tests/test_answer_cache.py .github/workflows/ci.yml
git commit -m "Add an in-memory cache for frequently asked questions"
```

---

### Task 2: Pakai cache di jalur kirim pesan `app.py`

**Files:**
- Modify: `app.py` — impor (dekat `from draft_check import ...`, baris ~27); fungsi baru dekat `rate_limit_state()` (~baris 1896); jalur kirim pesan (~baris 4870–4990)
- Test: `tests/test_answer_cache_app.py`
- Modify: `.github/workflows/ci.yml` (tambahkan `tests.test_answer_cache_app` setelah `tests.test_answer_cache`)
- Modify: `CHANGELOG.md`, `docs/ARCHITECTURE.md` (satu paragraf: apa yang di-cache, siapa yang mengisi, TTL, hilang saat reboot)

**Interfaces:**
- Consumes: `AnswerCache`, `cacheable_question`, `question_key` dari Task 1.
- Produces (di `app.py`):
  - `answer_cache() -> AnswerCache` dengan `@st.cache_resource`.
  - `answer_cache_key(chat: dict, pending_request: dict) -> str | None` — `question_key(text)` hanya jika: chat berisi tepat satu pesan (pesan user yang baru ditambahkan), `pending_request["payload"] == pending_request["text"]`, tidak ada `images`, `chat_tables(chat)` kosong, tidak ada `riset`/`kerangka`/`cek`, dan `cacheable_question(text)`. Selain itu `None`.
  - `cached_turn_context(chat: dict) -> str` — jika balasan asisten non-error di chat (sebelum pesan user terakhir) tepat satu dan bertanda `cached`, kembalikan `"### Percakapan sebelumnya (dijawab tanpa riwayat Agent)\nPengguna: {q}\nCiel: {a}\n\n### Pesan baru\n"`; selain itu `""`.
  - Balasan dari cache: `reply["cached"] = True` (ikut tersimpan di Supabase lewat `encode_message`, jadi tetap berlaku setelah reload).

- [ ] **Step 1: Write the failing tests** di `tests/test_answer_cache_app.py`, memakai pola `load_app(names, **namespace)` dari `tests/test_ciel_pro.py`. `NAMES = {"answer_cache_key", "cached_turn_context"}`; `setUp` memuat `self.app = load_app(NAMES, chat_tables=lambda chat: {}, question_key=question_key, cacheable_question=cacheable_question)`. `cached_turn_context` memakai pertanyaan dan balasan cache yang pertama ditemukan:

```python
def test_first_plain_message_gets_a_key(self):
    chat = {"messages": [{"role": "user", "content": "Apa itu AI?"}]}
    pending = {"text": "Apa itu AI?", "payload": "Apa itu AI?", "images": []}
    self.assertEqual(self.app["answer_cache_key"](chat, pending), question_key("apa itu ai"))

def test_ineligible_requests_get_no_key(self):
    base = {"text": "Apa itu AI?", "payload": "Apa itu AI?", "images": []}
    one = {"messages": [{"role": "user", "content": "x"}]}
    three = {"messages": [{"role": "user"}, {"role": "assistant"}, {"role": "user"}]}
    for chat, pending in (
        (three, base),
        (one, {**base, "payload": "Gunakan isi file berikut...\n### Pertanyaan\nApa itu AI?"}),
        (one, {**base, "images": [{"name": "a.png"}]}),
        (one, {**base, "riset": {"topic": "x"}}),
        (one, {**base, "text": "siapa namaku", "payload": "siapa namaku"}),
    ):
        self.assertIsNone(self.app["answer_cache_key"](chat, pending))

def test_chat_with_tables_gets_no_key(self):
    app = load_app(NAMES, chat_tables=lambda chat: {"data.csv": "..."}, question_key=question_key, cacheable_question=cacheable_question)
    chat = {"messages": [{"role": "user", "content": "Apa itu AI?"}]}
    pending = {"text": "Apa itu AI?", "payload": "Apa itu AI?", "images": []}
    self.assertIsNone(app["answer_cache_key"](chat, pending))

def test_follow_up_after_cached_reply_carries_previous_turn(self):
    chat = {"messages": [
        {"role": "user", "content": "Apa itu AI?"},
        {"role": "assistant", "content": "AI adalah ...", "cached": True},
        {"role": "user", "content": "jelasin lebih detail"},
    ]}
    context = self.app["cached_turn_context"](chat)
    self.assertIn("Pengguna: Apa itu AI?", context)
    self.assertIn("Ciel: AI adalah ...", context)
    self.assertTrue(context.endswith("### Pesan baru\n"))

def test_no_context_once_langflow_has_seen_the_chat(self):
    q = {"role": "user", "content": "Apa itu AI?"}
    hit = {"role": "assistant", "content": "AI adalah ...", "cached": True}
    fresh = {"role": "assistant", "content": "Lebih detail ..."}
    error = {"role": "assistant", "content": "Gagal", "error": True}
    new = {"role": "user", "content": "lagi"}
    context = self.app["cached_turn_context"]
    self.assertEqual(context({"messages": [q, hit, q, fresh, new]}), "")
    self.assertEqual(context({"messages": [q, fresh, new]}), "")
    self.assertEqual(context({"messages": [new]}), "")
    # balasan error tidak dihitung: konteks cache masih perlu dikirim
    self.assertIn("Ciel: AI adalah ...", context({"messages": [q, hit, q, error, new]}))
```

Plus tes sumber (gaya `tests/test_app_hygiene.py`, membaca `SOURCE`) yang memastikan jalur kirim pesan: (a) lookup cache dipanggil sebelum `check_rate_limit`, (b) `put` dijaga `not failed` **dan** `not memory_owner_id()`, (c) `cached_turn_context(chat)` diprefiks ke payload pada kedua pemanggilan `ask_langflow` flow utama (dengan dan tanpa gambar).

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest -v tests.test_answer_cache_app`
Expected: FAIL — `KeyError: 'answer_cache_key'`

- [ ] **Step 3: Implement di `app.py`**
  - Tambah `answer_cache()`, `answer_cache_key()`, `cached_turn_context()` sesuai Interfaces.
  - Di jalur kirim pesan, setelah `tables = chat_tables(chat)`: hitung `cache_key = answer_cache_key(chat, pending_request)` dan `cached = answer_cache().get(cache_key) if cache_key else None`. Rantai `answer = (...)` yang ada menjadi `answer = cached or (rantai lama)`; karena `cached` bukan `None`, semua cabang `elif answer is None` terlewati.
  - Kedua pemanggilan `ask_langflow(pending_request["payload"], ...)` flow utama memakai `cached_turn_context(chat) + pending_request["payload"]`.
  - Setelah `failed = is_error_answer(answer)`: jika `cache_key and not cached and not failed and not memory_owner_id()` → `answer_cache().put(cache_key, answer)`. Jika `cached` → `reply["cached"] = True` dan `logger.info("answer_cache_hit key=%s", cache_key[:8])`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest -v tests.test_answer_cache tests.test_answer_cache_app tests.test_rate_limit tests.test_project_context tests.test_app_hygiene`
Expected: semua OK

- [ ] **Step 5: Full offline suite**

Run: perintah "Run offline test suite" dari `.github/workflows/ci.yml` (dengan `tests.test_answer_cache_app` sudah ditambahkan). Pindahkan `.streamlit/secrets.toml` lokal sementara jika ada (secrets lokal merusak tes).
Expected: semua OK

- [ ] **Step 6: Docs** — entri `CHANGELOG.md` mengikuti format entri teratas; paragraf di `docs/ARCHITECTURE.md`.

- [ ] **Step 7: Cek manual di browser (oleh Ciel)** — jalankan app lokal, tanpa login: tanya "Apa itu machine learning?" di chat baru, lalu chat baru lagi dengan pertanyaan sama → jawaban muncul hampir instan dan log berisi `answer_cache_hit`. Lalu kirim "jelasin lebih detail" → jawaban nyambung. Tunggu konfirmasi Ciel sebelum commit.

- [ ] **Step 8: Commit** (hanya setelah Ciel bilang "commit")

```bash
git add app.py tests/test_answer_cache_app.py .github/workflows/ci.yml CHANGELOG.md docs/ARCHITECTURE.md
git commit -m "Answer repeated first questions from the cache"
```
