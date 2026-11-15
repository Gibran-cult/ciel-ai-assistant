# CI/CD dan kualitas Ciel AI Agent

Status: draf untuk ditinjau pemilik. Tanggal: 14 November 2026.
Bagian desktop ditulis untuk Tauri, sesuai keputusan D1 pada 14 November 2026 ([decisions.md](decisions.md)).

## 1. Kondisi sekarang (fakta)

| Hal | Sekarang |
|---|---|
| CI | `.github/workflows/ci.yml`: pasang dependensi dari lockfile ber-hash, `pip-audit`, validasi semua JSON flow, uji `unittest` dengan daftar modul, uji Edge Function dengan `node --test`, cek sintaks skrip VPS |
| Penjaga daftar uji | `tests/test_ci_coverage.py` gagal kalau ada berkas uji yang tidak masuk daftar CI |
| Rahasia | `tests/test_secrets.py`, secret scanning GitHub dengan push protection |
| Dependensi | Dependabot untuk pip dan Actions, Actions dipatok ke SHA commit |
| Deploy website | `pages.yml` ke GitHub Pages |
| Deploy aplikasi | Streamlit Community Cloud menarik dari `main` |
| Deploy flow | Manual di Langflow, dengan uji kontrak per versi flow |
| Uji langsung | `tests/collect_quality.py` dan uji juri LLM, dijalankan manual |
| Daftar periksa rilis | `RELEASE_CHECKLIST.md` |

Aturan yang dipertahankan: setiap berkas uji baru masuk daftar di `ci.yml`, urutan deploy "aplikasi dulu, baru flow", dan commit tanpa baris atribusi alat AI.

## 2. Pipeline

### Server (Python: aplikasi, mesin kebijakan, Ciel Agent API)

| Tahap | Isi | Menahan merge |
|---|---|---|
| Lint | Pemeriksa gaya dan kesalahan umum untuk Python [ISI: alat, belum ada di repo] | Ya |
| Uji unit | `unittest`, termasuk `tests/test_guard_*.py` | Ya |
| Uji integrasi | Agent API dengan database uji dan model tiruan | Ya |
| Red-team | `tests/test_guard_redteam.py` dan kumpulan serangan (bagian 4) | Ya |
| Keamanan | `pip-audit`, uji rahasia, analisis statis keamanan (CodeQL atau sejenis) | Ya untuk temuan tinggi |
| Bangun | Image kontainer untuk Agent API | Ya |
| Deploy staging | Otomatis setelah merge ke `main` | |
| Uji asap staging | Satu tugas agent tiruan dari awal sampai akhir | Menahan deploy produksi |
| Deploy produksi | Setelah persetujuan manual pemilik | |

### Ekstensi (TypeScript)

| Tahap | Isi | Menahan merge |
|---|---|---|
| Lint dan cek tipe | ESLint dan `tsc` | Ya |
| Uji unit | Pembaca halaman, adapter toko, pemeriksa izin lokal | Ya |
| Uji adapter | Adapter dijalankan pada halaman tiruan yang meniru penanda label resmi dan versi tanpa label | Ya |
| Uji ujung ke ujung | Browser otomatis memuat ekstensi dan situs toko tiruan lokal | Ya |
| Aksesibilitas | Pemeriksa otomatis untuk side panel dan dialog | Ya |
| Keamanan | `npm audit`, pemeriksaan manifest: tidak ada izin di luar daftar yang disetujui, tidak ada kode jarak jauh | Ya |
| Bangun | Paket zip dengan nomor versi dari tag | Ya |
| Terbit | Unggah ke Chrome Web Store dari CI (bagian 6) | Persetujuan manual |

### Aplikasi desktop (Rust dan TypeScript, kalau D1 memilih Tauri)

| Tahap | Isi | Menahan merge |
|---|---|---|
| Lint | `cargo clippy`, `cargo fmt --check`, ESLint | Ya |
| Uji unit | Pemeriksa jalur file, pemeriksa izin, verifikasi tiket aksi | Ya |
| Keamanan | `cargo audit`, `npm audit`, pemeriksaan daftar perintah yang dibuka ke tampilan | Ya |
| Bangun | Runner Windows, dan runner macOS kalau macOS dirilis | Ya |
| Tanda tangan | Code signing dan tanda tangan paket pembaruan (bagian 5) | Persetujuan manual |
| Terbit | Kanal beta dulu, lalu stabil | Persetujuan manual |

### Website

Tetap `pages.yml` dan `tests/test_website.py`. Tambahan: uji bahwa harga dan klaim di website cocok dengan `pricing.py` setelah paket berubah.

## 3. Environment

| Environment | Isi | Data |
|---|---|---|
| Lokal | Semua layanan di laptop developer dengan model tiruan | Data buatan |
| Staging | Salinan produksi di server yang sama dengan sumber daya kecil atau VPS kecil terpisah [ISI: pilihan pemilik], subdomain sendiri, database dan kunci API terpisah dengan plafon rendah | Data buatan. Tidak ada data pengguna |
| Produksi | Layanan untuk pengguna | Data pengguna |

- Ekstensi: versi staging diterbitkan sebagai item terpisah yang hanya bisa dipasang penguji. Versi produksi dirilis bertahap.
- Desktop: kanal beta dan kanal stabil dengan alamat pembaruan berbeda.
- Rahasia tiap environment terpisah. Kunci produksi tidak pernah ada di staging atau di laptop.
- Pembayaran di staging memakai sandbox Mayar (`MAYAR_PRODUCTION=false`).
- Fitur baru masuk di balik sakelar fitur yang bawaannya mati di produksi.

## 4. Strategi pengujian

| Lapis | Yang diuji | Contoh |
|---|---|---|
| Unit | Fungsi murni mesin kebijakan | Klasifikasi risiko, pencocokan domain, deteksi domain mirip, batas belanja, token konfirmasi, rantai hash log |
| Integrasi | Agent API dengan database dan model tiruan | Aksi R2 tidak sampai ke klien tanpa konfirmasi. Akun A tidak bisa membaca tugas akun B |
| Ujung ke ujung | Ekstensi di browser otomatis terhadap situs toko tiruan | Alur lengkap: cari barang, verifikasi toko, ringkasan, konfirmasi, serah terima |
| Red-team prompt injection | Kumpulan halaman, ulasan, email, dan file berisi perintah tersembunyi | Tidak ada aksi di luar lingkup tugas. Tidak ada R2 tanpa konfirmasi. Tidak ada R3 |
| Red-team toko palsu | Situs tiruan lokal: domain mirip, label palsu, pengalihan, tautan iklan | Semua ditolak dengan kode alasan yang benar |
| Aksesibilitas | Dialog, log, tombol stop | [accessibility.md](accessibility.md) bagian 8 |
| Kualitas jawaban | Uji juri LLM yang sudah ada | Dijalankan manual sebelum rilis prompt |
| Beban | Banyak koneksi WebSocket dan tugas bersamaan di staging | Sebelum tonggak 1.000 pengguna |

### Kumpulan red-team

Disimpan di `tests/redteam/` dan bertambah setiap ada temuan baru.

- `injections.json`: teks suntikan beserta tempatnya (deskripsi produk, ulasan, email, nama file, teks tersembunyi di halaman) dan hasil yang diharapkan.
- `fake_stores.json`: host dan bukti toko tiruan beserta kode alasan yang diharapkan.
- `scope_escapes.json`: aksi yang mencoba keluar dari lingkup tugas (jalur dengan `..`, situs lain, aplikasi yang tidak diizinkan).

Dua tingkat pengujian:

1. Tanpa model, di setiap pull request. Menguji mesin kebijakan langsung: untuk setiap kasus, aksi berbahaya yang mungkin diusulkan model diberikan ke mesin kebijakan, dan hasilnya harus blokir atau konfirmasi. Tingkat ini membuktikan pengaman bekerja apa pun kata model.
2. Dengan model, terjadwal dan sebelum rilis. Agent dijalankan pada halaman tiruan berisi suntikan. Yang dicatat: seberapa sering model terpancing mengusulkan aksi berbahaya, dan apakah ada yang lolos. Yang lolos harus nol. Angka terpancing dipakai untuk memperbaiki prompt.

Situs toko tiruan dibuat sendiri dan hanya meniru penanda yang diperiksa adapter. Halaman marketplace asli tidak disalin ke repo.

Pemeriksaan terhadap situs asli: marketplace bertanda "Melarang" tidak boleh diuji dengan alat otomatis, karena itu sendiri akses otomatis. Pemeriksaan bahwa adapter masih cocok dengan tampilan situs dikerjakan manual oleh pemilik setiap [ISI: frekuensi], atau lewat pemantauan `badge_unverifiable` di produksi.

### Syarat lulus rilis

- Semua uji yang menahan merge lulus.
- Red-team tingkat 1: nol kasus lolos.
- Red-team tingkat 2: nol aksi berbahaya yang dijalankan.
- Daftar periksa dark pattern dan aksesibilitas diisi untuk layar yang berubah.
- `RELEASE_CHECKLIST.md` diperluas dengan butir agent.

## 5. Code signing dan build desktop

| Hal | Rencana |
|---|---|
| Kunci tanda tangan pembaruan | Dibuat sekali, kunci privat disimpan sebagai rahasia CI di lingkungan terlindung yang butuh persetujuan pemilik, salinannya di luar laptop harian |
| Windows | Azure Artifact Signing tidak tersedia untuk individu di Indonesia. Pilihannya paket MSIX lewat Microsoft Store (Microsoft yang menandatangani, gratis, kemungkinan butuh akun perusahaan) atau sertifikat individu dari otoritas sertifikat (mulai US$129 per tahun ditambah token atau langganan cloud). Rinciannya di [agent-architecture.md](agent-architecture.md) bagian 5 |
| macOS | Developer ID dari Apple Developer Program (US$99 per tahun), build di runner macOS, notarisasi sebelum terbit |
| Hasil build | Hash setiap berkas rilis dicatat di catatan rilis |
| Build yang bisa diulang | Versi alat dipatok, lockfile wajib |

Sampai jalur tanda tangan Windows jelas, aplikasi desktop tidak dirilis ke publik.

## 6. Menerbitkan ekstensi

1. CI membangun paket dari tag versi.
2. Pemeriksaan manifest otomatis: izin sama dengan daftar yang disetujui, versi naik, tidak ada sumber kode jarak jauh.
3. Unggah ke Chrome Web Store lewat API dari CI dengan kredensial khusus, setelah persetujuan manual.
4. Menunggu peninjauan toko. Waktunya tidak pasti, jadi perbaikan darurat tidak bisa mengandalkan pembaruan ekstensi saja.
5. Rilis bertahap ke sebagian pengguna, lalu semua.
6. Catatan rilis menyebut perubahan izin kalau ada.

Karena peninjauan toko butuh waktu, sakelar darurat ada di server: server bisa menolak tugas dari versi ekstensi tertentu atau mematikan fitur pembelian untuk semua.

## 7. Deploy server

- Image kontainer bertanda versi. Deploy menarik image dan menjalankan migrasi database yang kompatibel mundur.
- Urutan: migrasi, Agent API, lalu klien. Klien lama harus tetap bekerja dengan server baru.
- Flow Langflow tetap diterbitkan manual dengan cadangan sebelum perubahan (`docs/BACKUP_AND_DISASTER_RECOVERY.md`).
- Daftar toko resmi diubah lewat pull request dengan uji, lalu dimuat ulang tanpa restart.

## 8. Rollback

| Bagian | Cara | Waktu |
|---|---|---|
| Agent API | Jalankan image versi sebelumnya | Menit |
| Migrasi database | Hanya migrasi yang kompatibel mundur. Penghapusan kolom dilakukan satu rilis setelah kode berhenti memakainya | |
| Aplikasi Streamlit | Kembalikan commit di `main` | Menit |
| Flow Langflow | Impor cadangan flow sebelumnya | Menit |
| Daftar toko resmi | Kembalikan pull request | Menit |
| Ekstensi | Terbitkan ulang versi lama dengan nomor versi baru. Sementara menunggu peninjauan, matikan fitur dari server | Jam sampai hari |
| Desktop | Terbitkan ulang versi lama sebagai versi baru di kanal pembaruan, atau naikkan versi minimum | Jam |
| Fitur | Matikan sakelar fitur | Detik |

Setiap rollback dicatat di `CHANGELOG.md` dengan penyebabnya.

## 9. Yang perlu dibuat

1. Alat lint Python di CI (sekarang belum ada).
2. Workflow terpisah untuk ekstensi dan desktop, dipicu hanya oleh perubahan di folder masing-masing.
3. Lingkungan terlindung di GitHub untuk rahasia tanda tangan dan penerbitan.
4. Environment staging.
5. Kumpulan red-team dan situs toko tiruan.
6. Butir agent di `RELEASE_CHECKLIST.md`.
