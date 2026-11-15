# PRD: Ciel AI Agent

Status: draf untuk ditinjau pemilik. Tanggal: 14 November 2026.
Dokumen terkait: [ringkasan](00-ringkasan.md), [arsitektur](agent-architecture.md), [keamanan](security.md), [roadmap](roadmap.md).

## Fakta dan asumsi

Fakta (dari repo dan produksi per 14 November 2026):

- Ciel sekarang adalah teman riset dan belajar. Fitur intinya: riset dengan sumber yang bisa dicek, analisis data CSV, memori jangka panjang per akun, dan paket Pro untuk skripsi (`pricing.py`, `docs/ARCHITECTURE.md`).
- Aplikasi berjalan di Streamlit, login hanya lewat Google, pembayaran Pro lewat Mayar (sekali bayar Rp79.000 untuk 30 hari).
- Backend (Langflow) masih di laptop pemilik lewat ngrok. Rencana pindah ke VPS sudah ditulis tetapi belum dijalankan.
- Pemilik adalah solo founder, belum punya badan usaha atau NIB.

Asumsi (belum divalidasi, perlu riset pengguna):

- A1. Mahasiswa dan pekerja muda mau memberi izin kontrol laptop ke Ciel kalau setiap aksi terlihat dan bisa dihentikan kapan saja.
- A2. Alasan utama orang mau dibantu belanja adalah takut barang palsu dan malas membandingkan toko, dan mereka menerima kalau pembayaran tetap mereka lakukan sendiri.
- A3. Pengguna lebih sering memakai agent di browser daripada di aplikasi desktop.
- A4. Mahasiswa mau memverifikasi status dengan email kampus demi diskon.

Cara menguji asumsi sebelum Fase 3: wawancara 8 sampai 10 orang (campuran mahasiswa dan umum) dan satu prototipe klik tanpa kode. Hasilnya dicatat di dokumen ini.

## 1. Masalah

1. Ciel bisa menjawab, tetapi pengguna masih mengerjakan sendiri semua langkah sesudahnya: menyalin hasil ke dokumen, mengisi formulir, merapikan file, membuka tab satu per satu.
2. Belanja online punya risiko barang palsu dan toko tiruan. Mengecek apakah sebuah toko resmi butuh waktu, dan website palsu yang meniru brand makin sulit dibedakan.
3. Agent AI umum sulit dipercaya. Pengguna tidak tahu apa yang sedang dikerjakan agent, tidak yakin bisa menghentikannya, dan takut agent salah klik, salah kirim, atau salah beli.

Ciel sudah punya reputasi "nggak ngarang" untuk riset. Agent harus membawa janji yang sama ke tindakan: setiap aksi punya jejak, dan aksi yang berisiko menunggu persetujuan pengguna.

## 2. Target pengguna

| Segmen | Siapa | Kebutuhan utama | Catatan |
|---|---|---|---|
| Umum | Usia 18 tahun ke atas, terbiasa belanja online dan kerja di laptop | Pekerjaan berulang selesai tanpa ditunggui, belanja aman di toko resmi | Segmen baru. Fitur pembelian hanya untuk segmen ini dan mahasiswa 18+ |
| Mahasiswa | Mahasiswa aktif perguruan tinggi di Indonesia | Semua kebutuhan umum, ditambah riset skripsi yang sudah ada | Segmen yang sekarang. Dapat diskon setelah verifikasi |
| Di bawah 18 tahun | Siswa atau mahasiswa baru | Chat dan riset saja | Butuh persetujuan orang tua. Tanpa fitur pembelian dan tanpa kontrol laptop sampai ada kajian hukum |

## 3. Persona

Persona ini rekaan untuk keperluan desain. Tidak ada data riset di baliknya sampai wawancara selesai.

**Nadia, 21, mahasiswa semester 7.** Sedang skripsi, laptop 8 GB penuh file tugas dengan nama acak. Butuh kalkulator ilmiah untuk sidang dan takut kena barang palsu. Ingin Ciel merapikan folder skripsinya dan mencarikan kalkulator dari toko resmi brand.

**Dimas, 26, staf administrasi.** Setiap minggu menyalin data dari email ke spreadsheet dan mengisi form internal. Mau menyerahkan pekerjaan itu ke agent, tetapi kantornya ketat soal data, jadi ia perlu melihat persis apa yang dibuka dan diketik agent.

**Fajar, 17, mahasiswa baru.** Memakai Ciel untuk belajar. Belum 18 tahun, jadi tidak boleh memakai fitur pembelian. Persona ini ada supaya alur verifikasi usia dan persetujuan orang tua ikut didesain sejak awal.

## 4. User story

Kontrol laptop

- Sebagai pengguna, aku mau memilih aplikasi dan folder mana saja yang boleh disentuh Ciel, supaya sisanya tetap aman.
- Sebagai pengguna, aku mau melihat rencana langkah sebelum Ciel mulai, supaya aku bisa membatalkan atau mengubahnya.
- Sebagai pengguna, aku mau satu tombol stop yang selalu terlihat dan satu pintasan keyboard, supaya aku bisa menghentikan Ciel dalam sekejap.
- Sebagai pengguna, aku mau Ciel berhenti dan bertanya sebelum menghapus file, mengirim pesan, atau memasang aplikasi.

Pembelian

- Sebagai pembeli, aku mau Ciel hanya membeli di toko resmi dan menunjukkan buktinya, supaya aku yakin barangnya asli.
- Sebagai pembeli, aku mau Ciel menolak toko yang tidak resmi dan menawarkan toko resmi sebagai gantinya.
- Sebagai pembeli, aku mau melihat nama toko, barang, harga, ongkir, dan total sebelum checkout, lalu menyetujuinya sendiri.
- Sebagai pembeli, aku mau mengatur batas belanja per transaksi dan per bulan.
- Sebagai pembeli, aku mau tahu cara membatalkan atau mengembalikan barang kalau tidak sesuai.

Tugas mandiri

- Sebagai pengguna, aku mau memberi satu perintah ("rapikan folder skripsi per bab") dan Ciel mengerjakannya sampai selesai, lalu melapor.
- Sebagai pengguna, aku mau Ciel bilang terus terang kalau sebuah langkah gagal atau tidak bisa dipastikan hasilnya.

Kepercayaan dan akun

- Sebagai pengguna, aku mau satu log aktivitas yang sama di web, desktop, dan ekstensi.
- Sebagai pengguna, aku mau mencabut akses sebuah perangkat dari halaman pengaturan.
- Sebagai mahasiswa, aku mau diskon dengan verifikasi yang tidak meminta dokumen berlebihan.

## 5. Fitur per prioritas

### Must (tanpa ini fitur agent tidak boleh rilis)

| ID | Fitur | Dokumen acuan |
|---|---|---|
| M1 | Mesin kebijakan: tingkat risiko aksi R0 sampai R3, lingkup tugas, keputusan izinkan, konfirmasi, atau blokir | [security.md](security.md) bagian 2 |
| M2 | Tombol stop darurat di desktop dan ekstensi, ditambah pintasan keyboard | security.md bagian 3 |
| M3 | Indikator saat agent aktif | [design-system.md](design-system.md) bagian 7 |
| M4 | Log semua aksi, satu untuk semua perangkat | security.md bagian 3, [agent-architecture.md](agent-architecture.md) bagian 6 |
| M5 | Konfirmasi wajib untuk aksi berisiko | security.md bagian 2 |
| M6 | Verifikasi toko resmi sebelum checkout, tolak toko tidak resmi, tawarkan alternatif | security.md bagian 4 |
| M7 | Dialog konfirmasi pembelian dengan bukti status resmi | security.md bagian 4, design-system.md bagian 7 |
| M8 | Batas belanja per transaksi dan per bulan | security.md bagian 4 |
| M9 | Pertahanan prompt injection | security.md bagian 5 |
| M10 | Izin per aplikasi, per folder, dan per situs | security.md bagian 3 |
| M11 | Dokumen legal dan consent untuk fitur agent, verifikasi usia 18+ untuk pembelian | [legal/](legal/), [privacy-consent.md](privacy-consent.md) |
| M12 | Ekstensi browser: baca halaman, isi form, kelola tab | agent-architecture.md bagian 4 |

### Should

| ID | Fitur |
|---|---|
| S1 | Aplikasi desktop Windows: kelola file dan folder yang diizinkan, buka aplikasi yang diizinkan |
| S2 | Bantuan pembatalan dan pengembalian barang |
| S3 | Diskon mahasiswa dengan verifikasi email kampus |
| S4 | Daftar perangkat dan cabut akses dari web |
| S5 | Ringkasan tugas selesai dengan bukti (apa yang berubah, di mana) |

### Could

| ID | Fitur |
|---|---|
| C1 | Aplikasi desktop macOS |
| C2 | Kontrol keyboard dan mouse lewat tangkapan layar untuk aplikasi tanpa struktur yang bisa dibaca |
| C3 | Tugas terjadwal ("setiap Senin rapikan folder Unduhan") |
| C4 | Resep tugas yang bisa disimpan dan dipakai ulang |

### Tidak dikerjakan sekarang

Lihat bagian 7.

## 6. Metrik sukses

Angka target di bawah adalah usulan. Baseline belum ada, jadi target selain yang bertanda "wajib" diisi ulang setelah dua minggu data beta.

| Metrik | Cara ukur | Target |
|---|---|---|
| Pembelian yang disiapkan di toko tidak resmi | Log `agent_actions`, uji red-team | 0 (wajib) |
| Aksi R2 yang jalan tanpa konfirmasi | Log, uji otomatis | 0 (wajib) |
| Aksi R3 yang lolos | Log, uji otomatis | 0 (wajib) |
| Uji red-team prompt injection dan toko palsu yang lolos | CI | 0 kasus lolos (wajib) |
| Waktu dari tekan stop sampai agent berhenti | Uji di klien | di bawah 1 detik di perangkat (usulan) |
| Tugas selesai tanpa campur tangan | Log tugas | [ISI: target setelah baseline] |
| Tugas yang dibatalkan pengguna di tengah jalan | Log tugas | [ISI: target setelah baseline] |
| Pengguna yang memakai agent lagi dalam 7 hari | Log tugas per akun | [ISI: target setelah baseline] |
| Keluhan "agent salah aksi" per 1.000 tugas | Kotak masuk dukungan | [ISI: target setelah baseline] |
| Konversi gratis ke berbayar | Tabel order | [ISI: target setelah baseline] |

## 7. Di luar scope

- Agent membayar sendiri dengan kartu atau saldo pengguna. Keputusan cara bayar ada di D4; rekomendasi sekarang pengguna membayar sendiri.
- Menyimpan nomor kartu, PIN, OTP, atau kata sandi dalam bentuk apa pun.
- Membuka aplikasi m-banking, dompet digital, dan password manager (lihat D9).
- Trading, kripto, judi, dan pembelian barang yang dibatasi hukum.
- Marketplace atau situs yang syarat layanannya melarang akses otomatis, sampai ada izin tertulis (lihat [business-ethics.md](business-ethics.md) bagian 7).
- Aplikasi HP (Android, iOS).
- Kontrol perangkat milik orang lain atau perangkat kantor yang dikelola admin.
- Pengguna di bawah 18 tahun untuk fitur pembelian.

## 8. Risiko

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Agent menjalankan perintah yang diselipkan di halaman web (prompt injection) | Data bocor, aksi salah, pembelian salah | Lingkup tugas terkunci, gerbang konfirmasi dari kode, uji red-team di CI (security.md bagian 5) |
| Website palsu meniru toko resmi | Uang pengguna hilang | Daftar domain resmi, deteksi domain mirip, navigasi hanya dari alamat yang diketik agent sendiri (security.md bagian 4) |
| Syarat layanan marketplace melarang akses otomatis | Akun pengguna dibekukan, Ciel melanggar perjanjian | Tandai per marketplace, jangan otomatisasi yang melarang, minta izin tertulis (business-ethics.md bagian 7) |
| Tanpa badan usaha, tanggung jawab jatuh ke pemilik secara pribadi | Risiko hukum dan keuangan pribadi | Urus NIB dan PSE sebelum fitur pembelian rilis, tinjauan ahli hukum (docs/LEGAL.md) |
| Biaya LLM per tugas lebih besar dari harga paket | Rugi per pengguna | Kuota tugas per paket, model murah untuk langkah teks, pantau biaya per tugas ([subscription-payments.md](subscription-payments.md)) |
| Sertifikat code signing Windows sulit didapat individu di Indonesia | Aplikasi desktop memunculkan peringatan keamanan | Rilis ekstensi dulu (D10), kaji jalur Microsoft Store dan sertifikat CA ([cicd-quality.md](cicd-quality.md)) |
| Toko aplikasi menolak ekstensi atau aplikasi | Rilis tertunda | Izin minimal, satu tujuan yang jelas, kebijakan privasi lengkap (business-ethics.md bagian 6) |
| Satu orang mengerjakan semuanya | Lambat, tidak ada yang meninjau keamanan | Rilis bertahap, uji otomatis sebagai peninjau, audit pihak luar sebelum pembelian dibuka |
| Data layar pengguna sampai ke penyedia LLM | Privasi | Kirim teks struktur halaman lebih dulu, tangkapan layar hanya jika perlu dan tidak disimpan, penyedia dengan komitmen tanpa pelatihan (D2) |

## 9. Urutan rilis

Keamanan dan legal selesai sebelum fitur yang menyentuh uang atau laptop dibuka. Urutan lengkap ada di [roadmap.md](roadmap.md):

1. Keputusan pemilik, fondasi legal, pindah ke VPS.
2. Mesin kebijakan dan guardrail (bisa mulai sekarang, tidak bergantung keputusan).
3. Ciel Agent API, akun perangkat, log aktivitas.
4. Ekstensi browser tanpa pembelian.
5. Bantuan pembelian di toko resmi.
6. Aplikasi desktop Windows, lalu macOS.

## 10. Pertanyaan terbuka

Semua keputusan besar (D1 sampai D10) ada di [00-ringkasan.md](00-ringkasan.md). Pertanyaan yang lebih kecil:

- Apakah mode "Jalan sendiri" (tanpa tanya untuk aksi yang bisa dibatalkan) dibuka untuk paket gratis, atau hanya berbayar?
- Berapa lama log aktivitas disimpan? Usulan di [privacy-consent.md](privacy-consent.md): 90 hari.
- Apakah pengguna 17 tahun boleh memakai kontrol laptop dengan persetujuan orang tua? Perlu jawaban ahli hukum.
