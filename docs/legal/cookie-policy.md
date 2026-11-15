# Kebijakan Cookie Ciel (draf)

> Draf, bukan nasihat hukum, dan belum berlaku. Bagian bertanda [CEK HUKUM] wajib ditinjau ahli hukum. Nama cookie bertanda [PERLU DICEK] harus dicocokkan dengan yang benar-benar terpasang di browser sebelum halaman ini terbit.

Terakhir diperbarui: [ISI: tanggal berlaku]

## 1. Apa itu cookie

Cookie adalah berkas kecil yang disimpan situs di browsermu. Halaman ini juga mencakup penyimpanan sejenis: penyimpanan lokal browser, penyimpanan ekstensi, dan berkas pengaturan aplikasi desktop.

## 2. Yang dipakai Ciel sekarang

Fakta per 14 November 2026: Ciel tidak memasang cookie analitik atau iklan. Statistik pemakaian bawaan Streamlit dimatikan (`.streamlit/config.toml`), dan halaman depan tidak memuat skrip pihak ketiga (`tests/test_landing.py`).

| Nama | Dipasang oleh | Guna | Kategori | Umur |
|---|---|---|---|---|
| Cookie sesi login [PERLU DICEK nama persisnya] | Aplikasi Ciel | Menjaga kamu tetap masuk | Wajib | [PERLU DICEK] |
| Cookie pengaman formulir [PERLU DICEK nama persisnya] | Aplikasi Ciel | Mencegah permintaan palsu dari situs lain | Wajib | Sesi |
| Cookie Google saat login | Google | Proses masuk dengan akun Google | Wajib, dipasang Google di domainnya sendiri | Diatur Google |
| Pilihan tema dan persetujuan cookie | Aplikasi Ciel | Mengingat pilihanmu | Wajib | [ISI: umur] |

Permintaan huruf ke Google Fonts dari aplikasi membuat Google menerima alamat IP-mu. Rencananya huruf dibundel sendiri supaya permintaan ini hilang ([../privacy-consent.md](../privacy-consent.md) bagian 6).

## 3. Kategori

| Kategori | Isi | Butuh persetujuan |
|---|---|---|
| Wajib | Login, keamanan, mengingat pilihan persetujuan | Tidak. Tanpa ini layanan tidak jalan |
| Preferensi | Pengaturan tampilan yang tidak wajib | Ya |
| Analitik | Mengukur pemakaian fitur untuk memperbaiki produk | Ya |
| Pemasaran | Mengukur kampanye | Ya. Sekarang tidak ada dan tidak direncanakan |

Selama Ciel hanya memakai kategori Wajib, yang tampil adalah pemberitahuan singkat dengan tautan ke halaman ini. Banner persetujuan penuh wajib tampil sebelum cookie atau alat pertama dari kategori lain dipasang.

## 4. Banner persetujuan

Aturan banner (rinciannya di privacy-consent.md bagian 1):

- Tombol "Tolak semua" dan "Terima semua" sama ukuran, sama warna, dan sejajar.
- Ada pilihan per kategori. Semua kategori selain Wajib bawaannya mati.
- Tidak ada cookie di luar kategori Wajib yang dipasang sebelum kamu memilih.
- Menutup banner tanpa memilih sama dengan menolak.
- Pilihanmu dicatat dengan waktu dan versi kebijakan.

## 5. Mengubah pilihan

Buka Pengaturan > Privasi > Cookie kapan saja. Menarik persetujuan semudah memberikannya. Kamu juga bisa menghapus cookie lewat pengaturan browser. Menghapus cookie login membuatmu keluar.

## 6. Ekstensi dan aplikasi desktop

- Ekstensi dan aplikasi desktop tidak memakai cookie untuk melacak.
- Ekstensi menyimpan token masuk, daftar izin situs, dan pengaturan di penyimpanan ekstensi.
- Aplikasi desktop menyimpan token masuk di penyimpanan rahasia sistem operasi dan pengaturan di folder aplikasi.
- Ekstensi tidak membaca cookie situs lain dan tidak meminta izin `cookies`.

## 7. Perubahan

Setiap cookie atau alat baru ditambahkan ke tabel di bagian 2 sebelum dipasang. Kalau kategori baru dipakai, banner tampil lagi untuk semua pengguna.

## 8. Catatan untuk ahli hukum [CEK HUKUM]

- Indonesia belum punya aturan cookie yang serinci Uni Eropa. Draf ini mengikuti praktik persetujuan ala GDPR dan ePrivacy karena pemilik memintanya, dan memakai persetujuan sebagai dasar pemrosesan untuk kategori selain Wajib.
- Perlu dicek apakah pengukuran pemakaian yang sepenuhnya di server tanpa cookie tetap membutuhkan persetujuan menurut UU 27/2022.
