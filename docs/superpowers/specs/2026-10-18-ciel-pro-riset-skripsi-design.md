# Ciel Pro, proyek 1: Gerbang Pro + Riset Skripsi

## Context

Ciel mau mulai dijual. Paket Pro (Rp79.000/bulan) sudah tercantum di `pricing.py`, tapi `available: False` dan isinya cuma "batas pesan lebih tinggi". Belum ada pembayaran, belum ada status Pro di mana pun, dan semua fitur gratis untuk semua orang.

Keputusan Ciel di sesi ini:
- **User Pro:** mahasiswa yang sedang skripsi atau persiapan ujian.
- **Fitur andalan:** **Riset Skripsi**. Hasilnya **peta sumber**, bukan draf Bab 2: 10–15 sumber relevan, tiap sumber diringkas (temuan, metode, relevansi), dikelompokkan per tema, plus celah riset dan daftar pustaka APA 7, bisa diekspor ke DOCX. Mahasiswa tetap menulis babnya sendiri.
- **Cara jadi Pro:** pembayaran otomatis lewat **Midtrans**, tapi itu **proyek 2** (butuh akun merchant + verifikasi). Proyek 1 ini membangun gerbang Pro dan fiturnya. Status Pro bisa diberikan manual oleh admin untuk tes, dan tabel yang sama nanti diisi webhook Midtrans.

Tujuan: fitur yang kerjanya berat, hasilnya nyata, dan setiap sumbernya bisa dicek, sesuai identitas Ciel yang anti-ngarang. Versi gratis tetap utuh.

**Non-goal:** pembayaran/Midtrans, auto-renew, paket Tim, draf Bab 2, latihan ujian, cek klaim.
**Anti-goal:** daftar pustaka berisi penulis/tahun/URL yang tidak berasal dari hasil Exa run itu; user gratis kehilangan fitur yang sekarang mereka punya; gerbang Pro yang cuma disembunyikan di UI tapi bisa dilewati.

## Desain

### 1. Status Pro (Supabase, additive)
- Tambah tabel di `docs/chat_store.sql`:
  `pro_members(owner text primary key, expires_at timestamptz not null, source text not null default 'manual', updated_at timestamptz not null default now())`, RLS aktif tanpa policy (pola sama dengan `chats`/`projects`). `owner` = `memory_owner_id()` (app.py:1165).
- `chat_store.py`: tambah `load_pro_until(owner)` mengikuti pola `_request`/validasi owner yang ada (timeout 15 s, gagal → None, tidak raise).
- `app.py`: `pro_until()` di-cache di `st.session_state` beberapa menit untuk tampilan UI; **dicek ulang ke Supabase saat request Riset Skripsi dikirim** (enforcement di server Streamlit, bukan cuma tombol yang disembunyikan). Kalau Supabase gagal → anggap bukan Pro, dengan pesan jelas.
- Menu akun menampilkan **"ID akun"** (owner hash) dan status "Pro aktif sampai …". Admin pakai ID itu untuk grant manual.
- Snippet SQL grant/perpanjang 30 hari ditulis di `docs/chat_store.sql` (komentar) atau `docs/PRO.md`.
- Proyek 2 (Midtrans) nanti cukup menulis ke tabel ini dari Supabase Edge Function. Tidak ada perubahan skema lagi.

### 2. Batas pemakaian
- Ikuti pola `get_int_config` + `rate_limits_for_request()` (app.py:1053, 1322):
  - Pro mendapat batas chat lebih tinggi: `RATE_LIMIT_PER_HOUR_PRO`, `RATE_LIMIT_PER_DAY_PRO`.
  - Riset Skripsi punya kuota sendiri: `RISET_SKRIPSI_PER_DAY` (default 5 per akun), tetap dihitung ke `all:total:day`.
- *Keputusan gw (bisa diubah lewat secrets):* default Pro 150/jam dan 800/hari, Riset Skripsi 5/hari.
- Catatan: penyimpanan rate limit ada di memori proses dan reset saat app restart. Risiko biaya kecil, dan kondisi ini sudah diterima untuk chat biasa.

### 3. Flow baru "Ciel Riset Skripsi" (Langflow, terpisah dari flow utama)
- Flow utama v1.12.0 **tidak diubah**. Flow riset di-clone dari `flow/subflows/Web_Research_Assistant.json`, yang sudah punya Agent + DeepSeek + Exa + guard sendiri, lalu disimpan sebagai `flow/riset_skripsi/v1.0.0/Ciel_Riset_Skripsi.json`.
- Perubahan dari hasil clone:
  - **Prompt** khusus peta sumber, dengan format keluaran tetap:
    - Judul
    - Ringkasan 2–3 kalimat
    - `## Tema …` berisi poin `[n]` (temuan, metode, relevansi)
    - `## Celah riset`
    - `## Pertanyaan untuk dosen pembimbing`
    - **Daftar pustaka tidak ditulis model.**
  - **Exa:** `search_num_results` ~10, highlights tetap on, `max_iterations` ~10, maksimal 3–4 putaran pencarian. Utamakan sumber akademik (jurnal, repositori kampus, Google Scholar/Garuda/SINTA bila muncul).
  - **Pencatat metadata:** recorder Exa juga mencatat `{url, title, author, published_date}` ke graph context. Ini bersifat additive: daftar URL lama untuk guard tetap sama.
    - Kalau `tests/` memaksa kode komponen identik dengan snapshot v1.12.0, buat komponen baru (`ciel_scholar_search.py`) daripada mengubah `ciel_exa_search.py`.
    - **Filter tahun:** hasil yang lebih tua dari `min_year` (input komponen, dikirim app lewat tweak) dibuang sebelum sampai ke Agent. Hasil tanpa tanggal tetap ada, ditandai "t.t.".
  - **Komponen baru `ciel_reference_builder.py`** (setelah `CielSourceGuard`): membuang sitasi yang tidak di-retrieve (pakai logika guard yang ada), lalu **menyusun "Daftar Pustaka (APA 7)" secara deterministik dari metadata Exa** untuk sumber yang benar-benar dikutip. Penulis kosong → nama situs/judul di depan sesuai APA. Tahun kosong → "(t.t.)". Model tidak bisa mengarang penulis atau tahun.
- ngrok: tambahkan `RESEARCH_FLOW_ID` ke allowlist lewat `tools/render_ngrok_policy.py` dan update `tests/test_gateway_policy.py`. Policy hanya diubah lewat render script (aturan keamanan v1.11.0).
- Contract test baru `tests/test_flow_riset_v100_contract.py` mengikuti pola `test_flow_v1120_contract.py`: node, setting Exa/Agent, potongan prompt, dan tidak ada key hardcoded.

### 4. UI di app.py
- Tombol **"Riset Skripsi"** di area composer/empty state membuka `st.dialog`:
  - topik (wajib)
  - bidang ilmu (opsional)
  - rentang tahun (3 / 5 / 10 tahun terakhir, default 5)
- Submit membuat chat baru berjudul "Riset: <topik>", lalu `ask_langflow` dipanggil dengan `RESEARCH_FLOW_ID`.
  - `ask_langflow` mendapat parameter flow/timeout.
  - Timeout riset 420 s (riset biasa 240 s) dan diukur saat live test.
  - Teks loading menjelaskan bahwa proses bisa sampai beberapa menit.
- Pesan hasil diberi `kind: "riset_skripsi"`, tersimpan lewat `persist_chat` yang ada, dan menampilkan tombol **"Unduh DOCX"** (pola dua langkah seperti unduhan dataset, app.py:3254).
- Pertanyaan lanjutan di chat itu dikirim ke flow utama, dengan peta sumber diikutkan sebagai file konteks lewat mekanisme `build_payload` (`project_files`), supaya "sumber nomor 3 tadi apa?" tetap bisa dijawab.
- User gratis/anonim: tombol tetap terlihat dengan label kecil "Pro". Klik → dialog singkat yang menjelaskan fitur + tautan ke halaman Pricing. Tidak ada riset yang dijalankan.
- Fitur disembunyikan sepenuhnya kalau `RESEARCH_FLOW_ID` atau Supabase tidak dikonfigurasi (pola `st.stop`/optional config yang ada).
- Ikuti aturan UI: tanpa pola AI-slop, cek kontras dark mode, popover di luar `.stApp`, dan tampilan mobile.

### 5. Ekspor DOCX
- Modul baru `riset_export.py` dengan fungsi murni `report_docx(markdown, topic) -> bytes`. Modul ini mendukung subset markdown dari format tetap di atas: heading, bullet, paragraf, dan marker `[n]`. Daftar pustaka memakai hanging indent, font Times New Roman 12 / spasi 1.5 (standar skripsi), dan URL tetap utuh.
- Dependensi baru: `python-docx` di `requirements.txt`. Ini satu-satunya dependensi baru. Library ini kecil dan murni Python, dan menulis DOCX tanpa library justru lebih rapuh.

### 6. Pricing
- `pricing.py`: isi fitur Pro diganti menjadi Riset Skripsi (peta sumber + APA 7 + DOCX), batas chat lebih tinggi, dan kuota riset per hari. Paket tetap `available: False` ("Segera dibuka") sampai proyek 2. FAQ ditambah satu pertanyaan tentang Riset Skripsi dan integritas akademik ("Ciel tidak menulis skripsimu").

## File yang diubah
- `app.py`: status Pro, batas pemakaian, dialog Riset Skripsi, render hasil + unduhan DOCX, ID akun di menu
- `chat_store.py`, `docs/chat_store.sql`: tabel dan loader `pro_members`
- `pricing.py`: konten paket Pro + FAQ
- Baru: `riset_export.py`, `flow/components/ciel_reference_builder.py` (+ mungkin `ciel_scholar_search.py`), `flow/riset_skripsi/v1.0.0/Ciel_Riset_Skripsi.json`
- `tools/render_ngrok_policy.py`, `requirements.txt`, `CHANGELOG.md`, `docs/ARCHITECTURE.md`, `RELEASE_CHECKLIST.md`
- Spec ini disalin ke `docs/superpowers/specs/2026-10-18-ciel-pro-riset-skripsi-design.md`
- Tes baru: gerbang Pro (kedaluwarsa, Supabase gagal, anonim), kunci rate limit Pro/riset, `report_docx`, reference builder (APA dari metadata, sitasi tak dikenal dibuang, t.t.), filter tahun, contract flow riset, gateway policy

## Rollout dan rollback
1. Jalankan SQL `pro_members` di Supabase. Ini additive dan tidak menyentuh tabel lama.
2. Import flow riset ke Langflow lokal → catat ID → tes di flow itu langsung.
3. Re-render policy ngrok dengan `RESEARCH_FLOW_ID` → restart ngrok (bukan sebagai admin).
4. Tambah secret `RESEARCH_FLOW_ID` di Streamlit Cloud → deploy app.
5. Grant Pro ke akun Ciel sendiri lewat SQL → tes end-to-end.

**Rollback:** hapus secret `RESEARCH_FLOW_ID`, dan fitur hilang dari UI tanpa mengganggu chat. Tabel `pro_members` boleh tetap ada. Flow utama tidak pernah disentuh.

Langkah 1, 3, 4, dan 5 dilakukan atau dikonfirmasi Ciel karena menyentuh layanan luar. DeepSeek bersifat prabayar: cek saldo sebelum live test (setiap riset memanggil model + 3–4 pencarian Exa).

## Verifikasi
- `python -m pytest`: semua tes lama tetap hijau, dan tes baru di atas juga lulus.
- Live test flow riset dengan 3 topik nyata (mis. ekonomi, kesehatan masyarakat, informatika) lewat `tests/live_session.py` atau skrip serupa. Cek:
  - waktu per run (target < 240 s; kalau sering lewat, pecah jadi 2 panggilan cari → susun)
  - semua URL di daftar pustaka ada di hasil Exa run itu
  - tidak ada sumber di luar rentang tahun kecuali "t.t."
  - DOCX bisa dibuka di Word dan rapi
- Cek browser oleh Ciel sendiri:
  - akun gratis (lihat label Pro + dialog upsell)
  - akun Pro (dialog → hasil → unduh DOCX)
  - Pro kedaluwarsa
  - light/dark mode dan mobile
- **Commit hanya setelah Ciel cek di browser dan bilang "commit".** Commit/PR tanpa baris atribusi Claude.

## Proyek 2 (berikutnya, terpisah)
Pembayaran Midtrans:
- Halaman beli Pro 30 hari (QRIS/e-wallet/VA, sekali bayar)
- Supabase Edge Function untuk webhook (verifikasi signature, idempotent per `order_id`) yang menulis `pro_members.expires_at`
- Paket Pro jadi `available: True`

Mulai setelah akun merchant Midtrans Ciel siap.

## Perubahan saat implementasi (2026-10-18)

- **Filter tahun memakai filter Exa sendiri.** App mengirim tweak `start_published_date` (`<tahun>-01-01`) ke `CielScholarSearch-r1s3t`, bukan `min_year` yang dibuang setelah pencarian. Exa memfilter di sisinya, jadi 10 hasil per kueri semuanya masuk rentang.
- **Komponen baru `ciel_scholar_search.py`.** Komponen ini menggantikan `ciel_exa_search.py` di flow riset, karena tes kontrak v1.8.0/v1.9.0 mengunci isi file lama. Agent hanya mendapat tool `search` (tanpa `get_contents`).
- **Agent tidak menulis daftar pustaka.** Agent menulis `Sumber:` berisi `[n] URL` saja. Ciel Reference Builder menyusun APA 7 dari metadata, menomori ulang, memakai nama jurnal dari judul halaman OJS ("Artikel | Jurnal"), dan menulis tautan DOI tanpa "doi.org" sebagai nama situs. Nama penulis tidak diubah ke format "Nama, I.".
- **Unduh DOCX satu langkah.** Streamlit 1.54 menerima fungsi sebagai `data` di `download_button`, jadi DOCX baru dibuat saat diklik. Pola "Siapkan unduhan" tidak dipakai.
- **Tombol sidebar tanpa `help=`.** Tooltip membungkus tombol, sehingga aturan warna mode gelap tidak berlaku. Dialog memakai aturan CSS sendiri karena dirender di luar `.stApp`.
- **Policy ngrok:** `RESEARCH_FLOW_ID` opsional. Tanpa nilai ini, policy sama persis dengan sebelumnya.
- **Uji live** (Langflow lokal, flow tes "Ciel Riset Skripsi (test)", 3 topik): 20–33 detik, 15–20 sumber, semua tahun dalam rentang, dan setiap `[n]` punya entri. Detail ada di `CHANGELOG.md`.
