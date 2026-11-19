# Fondasi keamanan sebelum beta: daftar situs yang selalu diblokir, lisensi aset, dan dua temuan minor

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Situs perbankan, dompet digital, dan pengelola kata sandi yang utama tidak pernah bisa disentuh agent; setiap aset punya catatan lisensi; dan dua temuan minor dari tinjauan tindak lanjut 3A ditutup.

**Architecture:** `guard/blocked_targets.json` tetap satu-satunya sumber daftar blokir. Layanan (`guard.risk.BLOCKED_HOSTS`), ekstensi (vektor `blocked.json`), dan panel memakai daftar yang sama, jadi menambah entri di sana langsung berlaku di semua tempat. Bukti setiap entri dicatat di dokumen baru `docs/blocked-targets.md`, dan uji memastikan berkas JSON dan dokumen itu selalu sama.

**Tech Stack:** Python 3.14 (`guard/`, `agent_api/`), TypeScript (ekstensi).

**Spec:** `docs/roadmap.md` task 0.14 dan 0.15, `docs/security.md` bagian D9, temuan minor di deskripsi PR #101.

## Keputusan yang dibutuhkan

**D21: kategori yang masuk daftar blokir awal.** D9 sudah menetapkan perbankan, dompet digital, dan pengelola kata sandi. Pertanyaannya, apakah situs keuangan lain ikut.

| Pilihan | Isi | Kelebihan | Kekurangan |
|---|---|---|---|
| A | Hanya kategori D9: bank, dompet digital, pengelola kata sandi | Sesuai keputusan yang sudah ada | Situs jual beli saham dan kripto, serta paylater dan pinjaman, tetap bisa dibuka agent. Di sana satu klik bisa menjadi transaksi atau utang |
| B (usulan) | Kategori D9, ditambah investasi (saham, reksa dana, kripto) dan paylater atau pinjaman daring | Semua tempat yang memindahkan uang atau membuat utang tertutup, sejalan dengan D4 (agent tidak pernah membayar) | Tugas seperti "baca harga saham di aplikasi broker" tidak bisa dikerjakan agent |

Apa pun pilihannya, situs yang juga menjadi marketplace (misalnya ShopeePay di dalam `shopee.co.id`, GoPay di aplikasi Gojek) tidak bisa diblokir lewat domain tanpa ikut memblokir tokonya. Untuk itu D4 dan jenis aksi `pay` (R3) yang menjaga.

## Calon daftar

Semua domain di bawah masih [PERLU DICEK]. Task 1 membuka setiap domain dan hanya memasukkan yang halamannya sendiri menyebut nama merek itu. Yang gagal tidak masuk dan dilaporkan ke pemilik. Daftar akhir ditunjukkan ke pemilik sebelum commit.

- **Bank:** `klikbca.com` (sudah ada), `bca.co.id`, `bankmandiri.co.id`, `bri.co.id`, `bni.co.id`, `bankbsi.co.id`, `cimbniaga.co.id`, `permatabank.com`, `danamon.co.id`, `btn.co.id`, `ocbc.id`, `maybank.co.id`, `panin.co.id`, `bankmega.com`, `uob.co.id`, `jago.com`, `seabank.co.id`, `bcadigital.co.id`, `jenius.com`, `allobank.com`
- **Dompet digital:** `dana.id`, `ovo.id`, `gopay.co.id`, `linkaja.id`
- **Pengelola kata sandi (versi web):** `1password.com`, `bitwarden.com`, `lastpass.com`, `dashlane.com`, `keepersecurity.com`, `nordpass.com`, `passwords.google.com`, `pass.proton.me`
- **Kalau D21 = B, investasi:** `indodax.com`, `tokocrypto.com`, `pintu.co.id`, `ajaib.co.id`, `stockbit.com`, `bibit.id`
- **Kalau D21 = B, paylater dan pinjaman:** `kredivo.com`, `akulaku.com`

## Global Constraints

- Tidak ada domain yang ditulis dari ingatan. Setiap entri punya bukti di `docs/blocked-targets.md`: alamat yang dibuka, alamat akhir setelah pengalihan, judul halaman, dan tanggal dicek.
- Pemeriksaan hanya memakai permintaan GET ke beranda situs, tanpa data pengguna, tanpa login.
- Daftar ini tidak boleh memuat domain toko yang ada di `guard/official_stores.json`, domain umum (`google.com`, `apple.com`, `microsoft.com`), atau akhiran publik. Uji memeriksanya.
- Vektor ekstensi (`extension/src/shared/vectors/blocked.json`) dibuat ulang dengan `tools/export_extension_vectors.py`.

## Review Focus

1. **Domain yang terlalu luas.** Entri seperti `google.com` akan memblokir hal yang tidak dimaksud. Uji di Task 1.
2. **Subdomain tetap terblokir.** `ib.bri.co.id` dan `vault.bitwarden.com` diblokir lewat entri induknya. Uji di Task 1.
3. **Dokumen dan JSON tidak sinkron.** Entri tanpa bukti, atau bukti tanpa entri, membuat CI gagal. Uji di Task 1.
4. **`end` dari tugas yang dihentikan sebelum aksi pertama.** Tidak menutup tugas baru. Uji di Task 3.

---

### Task 1: Daftar situs yang selalu diblokir

**Files:**
- Modify: `guard/blocked_targets.json`
- Create: `docs/blocked-targets.md`, `tools/check_blocked_domains.py` (membuka setiap calon domain dan menulis baris bukti)
- Test: `tests/test_blocked_targets.py` (baru, masuk `ci.yml`), `tests/test_extension_vectors.py`

- [ ] **Step 1: Uji yang gagal:** setiap `host_suffixes` punya baris di `docs/blocked-targets.md` dan sebaliknya; setiap entri lolos `normalize_host` dan bukan akhiran publik; tidak ada entri yang sama dengan atau menjadi induk domain di `official_stores.json`, `google.com`, `apple.com`, atau `microsoft.com`; `ib.bri.co.id` dan `vault.bitwarden.com` terblokir lewat `match_allowed`.
- [ ] **Step 2:** Jalankan `tools/check_blocked_domains.py` untuk calon daftar. Tunjukkan hasilnya ke pemilik.
- [ ] **Step 3:** Isi JSON dan dokumen dengan entri yang lolos dan disetujui. Buat ulang vektor ekstensi.
- [ ] **Step 4:** Uji lulus, termasuk `tests.test_guard_risk` dan uji ekstensi.
- [ ] **Step 5: Commit.** `git commit -m "Block the main banks, e-wallets and password managers, each with a checked source"`

### Task 2: Lisensi aset

**Files:**
- Create: `docs/asset-licenses.md`
- Test: `tests/test_asset_licenses.py` (baru, masuk `ci.yml`)

- [ ] **Step 1: Uji yang gagal:** setiap folder yang berisi gambar atau huruf di repo (`assets/brand`, `extension/public/icons`, `landing`, `website/public`, `tests/assets`) dan setiap keluarga huruf yang dimuat (Fraunces, Geist, Geist Mono) punya baris di `docs/asset-licenses.md`.
- [ ] **Step 2 sampai 4:** gagal, tulis, lulus. Lisensi huruf diambil dari berkas lisensinya sendiri (`extension/public/licenses/Geist-OFL.txt`, dan halaman Google Fonts untuk Fraunces [PERLU DICEK]).
- [ ] **Step 5: Commit.** `git commit -m "Record where every image and font comes from and its licence"`

### Task 3: Nomor tugas di pesan rencana

**Files:**
- Modify: `agent_api/ws.py` (`plan` membawa `task`), `extension/src/socket.ts`, `extension/src/controller.ts`, `docs/agent-protocol.md`
- Test: `tests/test_agent_ws.py`, `extension/tests/socket.test.ts`, `controller.test.ts`

- [ ] **Step 1: Uji yang gagal:** pesan `plan` membawa `task`. Panel mencatat tugas yang sedang ditunggu sejak rencana tiba. `end` dari tugas yang dihentikan sebelum aksi pertama tidak menutup tugas baru. `end` tugas lama tidak tampil sebagai hasil tugas baru yang juga dihentikan.
- [ ] **Step 2 sampai 4:** gagal, tulis, lulus.
- [ ] **Step 5: Commit.** `git commit -m "Name the task in the plan message so late ends never close the wrong task"`

### Task 4: Halaman awal tercatat di log aksi

**Files:**
- Modify: `agent_api/loop.py`
- Test: `tests/test_agent_ws.py`

- [ ] **Step 1: Uji yang gagal:** tugas dengan halaman awal menulis satu baris log `tab_read` dengan alasan `start_page`, host halaman itu, dan hasil `ok`, setelah rencana disetujui. Rantai log tetap utuh (`verify_chain`).
- [ ] **Step 2 sampai 4:** gagal, tulis, lulus.
- [ ] **Step 5: Commit.** `git commit -m "Log the start page like any other read"`

### Task 5: Dokumen

**Files:**
- Modify: `docs/roadmap.md` (0.14 dan 0.15 selesai), `docs/decisions.md` (D21), `docs/security.md` (bagian D9 merujuk `docs/blocked-targets.md`), `RELEASE_CHECKLIST.md` (`AGENT_MIN_CLIENT_VERSION=0.2.0` saat layanan dideploy)

- [ ] **Step 1:** Perbarui dokumen. `tests.test_ci_coverage` lulus.
- [ ] **Step 2: Commit.** `git commit -m "Record the blocked list, asset licences and D21"`

---

## Langkah pemilik

1. Menjawab D21.
2. Menyetujui daftar akhir hasil Task 1 sebelum di-commit.
