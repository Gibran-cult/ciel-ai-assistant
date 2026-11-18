# Tindak lanjut 3A: tugas di tab yang sedang dibuka, dan temuan minor

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ciel bisa mulai bekerja di halaman yang sedang dibuka pengguna (task 3.27), dan temuan minor dari tinjauan cabang 3A yang menyangkut keamanan atau keandalan ditutup.

**Architecture:** Pesan `start` boleh membawa `page`, yaitu `observation` dari tab aktif. Layanan menyimpannya sebagai halaman awal dan memasukkan host-nya ke lingkup tugas sesuai keputusan D20. Isi halaman baru sampai ke model setelah rencana disetujui, lewat amplop "tidak tepercaya" yang sama dengan hasil aksi lain. Perbaikan minor ada di `extension/src/socket.ts`, `auth.ts`, `runner.ts`, `content/reader.ts`, `background.ts`, dan pesan `end`.

**Tech Stack:** Python 3.14 (FastAPI, layanan `agent_api/`), TypeScript, React, Vitest, Playwright.

**Spec:** `docs/agent-protocol.md`, `docs/plans/2026-11-18-extension-core.md` (bagian Review Focus dan temuan tinjauan di ledger yang dicatat di deskripsi PR #100), task 3.27 di `docs/roadmap.md`.

## Keputusan yang dibutuhkan

**D20: situs tab awal dan lingkup tugas.** Halaman awal datang dari tab yang dipilih pengguna sendiri, tetapi rencana disusun model dari perintah saja, jadi host tab awal belum tentu ada di lingkup.

| Pilihan | Isi | Kelebihan | Kekurangan |
|---|---|---|---|
| A (usulan) | Host tab awal otomatis masuk lingkup dan ditampilkan di kartu rencana ("Mulai di: toko.test"). Isi halaman sampai ke model setelah rencana disetujui. Perencana tetap hanya membaca perintah | Tanpa dialog tambahan; pengguna melihat dan menyetujui situsnya di kartu rencana | Satu situs masuk lingkup tanpa disebut model |
| B | Host tidak masuk lingkup. Model harus meminta `tab_read`, dan pengguna menyetujui perluasan lingkup di dialog | Lingkup hanya dari rencana | Setiap tugas yang dimulai di halaman butuh satu dialog lagi |
| C | Perencana juga membaca isi halaman | Rencana lebih cocok dengan halaman | Teks halaman bisa mengarahkan rencana dan lingkup (prompt injection di tahap paling berwenang). Tidak disarankan |

Situs yang selalu diblokir (`guard/blocked_targets.json`) tidak pernah masuk lingkup lewat jalur ini, apa pun pilihannya.

## Global Constraints

- Semua aturan Global Constraints rencana 3A tetap berlaku: izin manifest persis, token akses hanya di `chrome.storage.session`, tidak ada kolom rahasia yang dibaca atau diketik, perubahan tampilan menunggu cek pemilik dan kata "commit".
- `start` tanpa `page` tetap sah (klien lama dan tab yang tidak bisa dibaca). Layanan dideploy sebelum ekstensi versi baru.
- Halaman awal hanya dikirim kalau tab-nya https, host-nya bukan situs yang diblokir, dan izin situsnya ada. Izin diminta dari klik "Mulai" di panel (gerakan pengguna).
- Isi halaman awal diperlakukan sama dengan hasil aksi: amplop tidak tepercaya, `flags_injection` menurunkan mode ke "Tanya dulu", dan host di luar lingkup tidak diberikan ke model.
- Versi ekstensi naik ke `0.2.0` karena protokol berubah (`page` di `start`, `task` di `end`).

## Review Focus

1. **Tab awal di situs yang diblokir atau tanpa izin.** Tidak ada `page` yang dikirim, dan layanan menolak `page` yang host-nya diblokir. Uji di Task 1 dan Task 2.
2. **Halaman awal berisi perintah untuk AI.** Mode turun ke "Tanya dulu" seperti hasil `tab_read`. Uji di Task 1.
3. **`page` yang bentuknya salah atau terlalu besar.** Koneksi ditutup 4400, sama dengan `result` yang rusak. Uji di Task 1.
4. **Perangkat dicabut saat tersambung.** Panel menampilkan "keluar", bukan "koneksi putus" yang berulang. Uji di Task 3.
5. **`end` milik tugas lama datang setelah tugas baru dimulai.** Diabaikan. Uji di Task 5.

---

### Task 1: Layanan menerima halaman awal

**Files:**
- Modify: `agent_api/ws.py` (`CLIENT_MESSAGES["start"]`, jalur `start`), `agent_api/loop.py` (halaman awal sesudah rencana), `agent_api/plan.py` (lingkup ditambah host awal, kalau D20 = A)
- Test: `tests/test_agent_ws.py`, `tests/test_agent_loop.py`

**Interfaces:**
- Produces: `start` boleh berisi `page` dengan bentuk `observation` (`OBSERVATION_KEYS`). `run_one(..., start_page)` dan `AgentLoop.start_page: Observation | None`. Pesan `plan` ke klien membawa `scope.start_host` (string atau null).

- [ ] **Step 1: Uji yang gagal:** `start` dengan `page` dari `toko.test`, rencana dengan `hosts: []`, lalu `tab_type` ke rujukan dari halaman itu tanpa `tab_open` lebih dulu: aksi diizinkan (tidak `no_page`), dan amplop yang dilihat model memuat teks halaman awal. `page` dari `klikbca.com` diabaikan (tugas jalan tanpa halaman). `page` dengan kunci tambahan menutup koneksi 4400. Halaman awal berisi "abaikan instruksi" menurunkan mode ke `ask`. `start` tanpa `page` tetap berjalan seperti sekarang.
- [ ] **Step 2 sampai 4:** gagal, tulis, lulus. Jalankan semua modul di job `agent-service`.
- [ ] **Step 5: Commit.** `git commit -m "Let a task start on the page the user already has open"`

### Task 2: Ekstensi mengirim halaman awal

**Files:**
- Modify: `extension/src/runner.ts` (`readStart(tabId): Promise<Observation | null>`), `extension/src/controller.ts` (`start` membaca tab awal), `extension/src/socket.ts` (`startTask(instruction, page?)`), `extension/src/panel/App.tsx` dan `Plan.tsx` (izin diminta saat Mulai, kartu rencana menampilkan "Mulai di"), `extension/manifest.json` (versi 0.2.0)
- Test: `extension/tests/runner.test.ts`, `controller.test.ts`, `panel.test.tsx`, `extension/tests/e2e/task.spec.ts`

- [ ] **Step 1: Uji yang gagal:** `readStart` mengembalikan `null` untuk tab http, host yang diblokir, atau tanpa izin, dan tidak pernah menyuntik skrip di sana. `start` membawa `page` hasil `readStart`. Kartu rencana menampilkan "Mulai di: toko.test". Uji ujung ke ujung baru: tugas dimulai di `daftar.html` dengan naskah `tab_read`, `tab_type`, `form_submit` tanpa `tab_open`, dan formulir terkirim.
- [ ] **Step 2 sampai 4:** gagal, tulis, lulus.
- [ ] **Step 5: Berhenti sebelum commit** untuk perubahan kartu rencana dan panel (tampilan). Logika boleh di-commit dulu: `git commit -m "Send the open tab as the start page"`.

### Task 3: Koneksi dan token

**Files:**
- Modify: `extension/src/socket.ts`, `extension/src/auth.ts`, `extension/src/background.ts`, `extension/src/panel/Offline.tsx`, `extension/src/panel/strings.ts`
- Test: `extension/tests/socket.test.ts`, `auth.test.ts`, `extension/tests/e2e/task.spec.ts`

- [ ] **Step 1: Uji yang gagal:**
  - 4401 memaksa satu kali penyegaran token; kalau token tetap tidak ada atau ditolak lagi, keadaan menjadi `signed_out` tanpa sambung ulang.
  - 4403 berhenti menyambung dengan keadaan baru `origin_refused`, dan panel menulis "Layanan menolak ekstensi ini. Pasang ulang ekstensi dari Chrome Web Store."
  - `save` menulis token pembaruan ke `storage.local` sebelum token akses.
  - Service worker memanggil `chrome.storage.local.setAccessLevel({accessLevel: "TRUSTED_CONTEXTS"})` saat mulai. Uji ujung ke ujung: skrip yang disuntik ke tab toko tidak bisa membaca `refreshToken`.
- [ ] **Step 2 sampai 4:** gagal, tulis, lulus.
- [ ] **Step 5: Commit.** `git commit -m "Sign out on a revoked device and keep the refresh token from content scripts"`

### Task 4: Runner dan pembaca

**Files:**
- Modify: `extension/src/runner.ts`, `extension/src/content/reader.ts`
- Test: `extension/tests/runner.test.ts`, `extension/tests/reader.test.ts`

- [ ] **Step 1: Uji yang gagal:**
  - Kalau kunci tiket gagal diambil, aksi tetap dijawab `{ok: false}` (layanan tidak menunggu 60 detik).
  - Kunci tiket diambil ulang kalau sudah lebih dari 10 menit.
  - Tombol "Pesan sekarang", "Selesaikan pesanan", "Place your order", "Complete purchase", dan "Confirm order" mendapat `effect: "pay"`.
- [ ] **Step 2 sampai 4:** gagal, tulis, lulus.
- [ ] **Step 5: Commit.** `git commit -m "Answer every action even when ticket keys fail, and catch more pay buttons"`

### Task 5: `end` membawa nomor tugas

**Files:**
- Modify: `agent_api/ws.py` (setiap `end` membawa `task`, null kalau tugas belum dibuat), `extension/src/socket.ts` (kunci `end`), `extension/src/controller.ts`, `extension/src/runner.ts` (getter `task`), `docs/agent-protocol.md`
- Test: `tests/test_agent_ws.py`, `extension/tests/socket.test.ts`, `controller.test.ts`

- [ ] **Step 1: Uji yang gagal:** setiap `end` dari layanan punya `task`. Di panel, `end` dengan `task` yang berbeda dari tugas yang sedang berjalan diabaikan; `end` dengan `task` null (penolakan sebelum tugas dibuat) tetap ditampilkan.
- [ ] **Step 2 sampai 4:** gagal, tulis, lulus.
- [ ] **Step 5: Commit.** `git commit -m "Tie every end message to its task"`

### Task 6: Dokumen

**Files:**
- Modify: `docs/agent-protocol.md` (`page` di `start`, `task` di `end`, batas lama dihapus), `docs/decisions.md` (D20), `docs/roadmap.md` (3.27 selesai), `docs/security.md` (akses `storage.local`)

- [ ] **Step 1:** Perbarui dokumen. `tests.test_ci_coverage` dan `tests.test_extension_vectors` lulus.
- [ ] **Step 2: Commit.** `git commit -m "Record the start page and end task id in the protocol"`

---

## Yang tidak dikerjakan di sini

- Sorotan elemen di preview (3.14), red-team dengan model sungguhan (3.22), dan semua task 3B.
- Temuan minor yang tersisa: tugas baru bisa menunggu aksi lama paling lama satu kali `waitForLoad` (15 detik), dan jalur permintaan izin situs belum diuji ujung ke ujung karena prompt izin Chrome tidak bisa diklik oleh Playwright.

## Langkah pemilik

1. Menjawab D20.
2. Mengecek kartu rencana yang menampilkan "Mulai di" di browser, lalu menulis "commit".
