# Kebijakan Privasi Ciel (draf untuk fitur agent)

> Draf, bukan nasihat hukum, dan belum berlaku. Kebijakan yang berlaku sekarang ada di `privacy.py` (halaman Privasi di aplikasi). Bagian bertanda [CEK HUKUM] wajib ditinjau ahli hukum sebelum dipakai. Isian bertanda [ISI: ...] menunggu data dari pemilik.

Terakhir diperbarui: [ISI: tanggal berlaku]

## 1. Siapa kami

Ciel dikelola oleh [ISI: nama pengelola atau badan usaha], beralamat di [ISI: alamat]. Nomor Induk Berusaha: [ISI: NIB]. Tanda daftar PSE: [ISI: nomor].

Pertanyaan dan permintaan soal data pribadi: [ISI: email kontak privasi].

## 2. Data yang kami proses

| Kelompok | Isinya | Kapan |
|---|---|---|
| Akun | Nama, alamat email, dan foto profil dari akun Google | Saat kamu masuk |
| Percakapan | Pesan, file, dan foto yang kamu kirim, serta jawaban Ciel | Saat kamu memakai chat |
| Memori | Hal yang kamu minta Ciel ingat | Setelah masuk, sampai kamu hapus |
| Profil | Nama panggilan, bidang studi, preferensi jawaban | Kalau kamu mengisinya |
| Perangkat | Nama perangkat, jenis klien (ekstensi atau desktop), versi, waktu terakhir aktif | Saat kamu menghubungkan ekstensi atau aplikasi desktop |
| Izin agent | Aplikasi, folder, dan situs yang kamu izinkan | Saat kamu mengaturnya |
| Tugas dan log aktivitas | Perintahmu, rencana, setiap aksi agent beserta target dan hasilnya | Saat agent bekerja |
| Isi halaman dan layar | Teks dan struktur halaman atau aplikasi yang sedang dikerjakan agent, dan tangkapan layar kalau diperlukan | Diproses selama tugas berjalan, tidak disimpan |
| Pembelian yang disiapkan | Nama toko, bukti status resmi, barang, harga, ongkos kirim, total, label alamat | Saat kamu memakai bantuan pembelian |
| Batas belanja | Batas per transaksi dan per bulan yang kamu atur | Saat kamu mengaktifkan pembelian |
| Usia | Pernyataan bahwa kamu berusia 18 tahun ke atas, dan tanggal lahir kalau diminta [CEK HUKUM] | Saat kamu mengaktifkan pembelian |
| Status mahasiswa | Alamat email kampus dan tanggal verifikasi | Kalau kamu meminta diskon mahasiswa |
| Pembayaran paket | Nomor order, nominal, status, dan waktu. Data kartu atau rekening tidak sampai ke Ciel | Saat kamu membeli paket |
| Persetujuan | Versi dokumen yang kamu setujui, pilihan per kategori, dan waktunya | Setiap kali kamu memberi atau mengubah persetujuan |
| Teknis | Alamat IP, jenis browser, dan catatan galat | Saat kamu memakai layanan |

## 3. Yang tidak kami kumpulkan

- Kata sandi, PIN, OTP, nomor kartu, dan CVV. Agent tidak membaca dan tidak mengetik kolom seperti itu.
- Riwayat browsing. Ekstensi hanya membaca tab yang sedang dipakai untuk tugas yang kamu perintahkan.
- Isi layar di luar jendela yang kamu izinkan.
- Tangkapan layar dan isi halaman sebagai arsip. Keduanya dibuang setelah tugas selesai.
- Data dari aplikasi perbankan, dompet digital, dan password manager.

## 4. Tujuan dan dasar pemrosesan [CEK HUKUM]

| Tujuan | Dasar |
|---|---|
| Menjawab pertanyaan dan menjalankan tugas yang kamu perintahkan | Persetujuanmu dan pelaksanaan layanan yang kamu minta |
| Mengingat konteks antar percakapan | Persetujuanmu |
| Mencatat aksi agent | Pelaksanaan layanan dan perlindungan untukmu sendiri |
| Memeriksa status resmi toko dan batas belanja | Pelaksanaan layanan |
| Memverifikasi usia dan status mahasiswa | Persetujuanmu dan kewajiban hukum |
| Menyimpan catatan order paket | Kewajiban hukum (pembukuan dan pajak) |
| Menjaga keamanan dan mencegah penyalahgunaan | Kepentingan yang sah [CEK HUKUM: dasar ini menurut UU 27/2022] |
| Mengirim info produk lewat email | Persetujuan terpisah yang bisa kamu tarik kapan saja |

Ciel tidak menjual data pribadimu dan tidak memakainya untuk iklan.

## 5. Pihak ketiga dan pemrosesan di luar Indonesia

Untuk menjalankan layanan, sebagian data diproses oleh pihak ketiga yang servernya bisa berada di luar Indonesia. Daftar lengkap dengan data yang dibagikan dan lokasi servernya ada di halaman Privasi dan di [../privacy-consent.md](../privacy-consent.md) bagian 6. Kelompoknya:

- Penyedia model AI: menerima isi pesan dan, untuk tugas agent, teks halaman atau layar yang sedang dikerjakan.
- Pencarian web: menerima kueri pencarian.
- Login: Google.
- Database dan hosting: menyimpan akun, percakapan, tugas, dan log.
- Pembayaran paket: menerima nama, email, dan nominal order.
- Toko aplikasi: Chrome Web Store dan toko lain tempat kamu mengunduh ekstensi atau aplikasi.

Toko tempat kamu berbelanja adalah pihak terpisah. Ciel tidak mengirim datamu ke toko. Kamu sendiri yang berinteraksi dengan toko lewat browsermu.

Dengan memakai Ciel, kamu menyetujui pemrosesan di luar Indonesia ini [CEK HUKUM: syarat transfer data ke luar negeri menurut UU 27/2022].

## 6. Berapa lama data disimpan

| Data | Lama | Catatan |
|---|---|---|
| Riwayat chat dan proyek | Sampai kamu hapus | |
| Riwayat pesan di server model | [ISI: `CHAT_RETENTION_DAYS`, sekarang 30] hari | Dihapus otomatis |
| Memori | Sampai kamu hapus | |
| Tugas dan log aktivitas agent | 90 hari (usulan) | Bisa dihapus lebih cepat dari Pengaturan |
| Isi halaman, tangkapan layar | Selama tugas berjalan | Tidak disimpan |
| Bukti status toko | Sama dengan log aktivitas | |
| Foto kartu mahasiswa (kalau dipakai) | Dihapus setelah verifikasi selesai, paling lama 7 hari (usulan) | Hanya hasil verifikasi yang disimpan |
| Catatan order paket | 10 tahun | Tidak dihapus saat akun dihapus, sesuai `docs/LEGAL.md` |
| Catatan persetujuan | Selama akun ada, ditambah [ISI: masa simpan setelah akun dihapus] [CEK HUKUM] | Sebagai bukti persetujuan |
| Cadangan | Paling lama 5 minggu | Data yang dihapus hilang dari cadangan dalam waktu itu |

## 7. Hak kamu [CEK HUKUM]

Kamu bisa:

- melihat dan mengunduh datamu,
- memperbaiki data yang keliru,
- menghapus data per jenis atau menghapus akun,
- menarik persetujuan, termasuk per kategori,
- meminta pemrosesan dibatasi atau ditunda,
- mengajukan keberatan atas keputusan yang dibuat hanya oleh proses otomatis.

Caranya: Pengaturan > Data saya, atau hubungi [ISI: email kontak privasi]. Kami menjawab paling lambat [ISI: tenggat menurut UU 27/2022, PERLU DICEK].

Menarik persetujuan untuk fitur agent mematikan fitur itu. Chat tetap bisa dipakai.

## 8. Anak dan usia [CEK HUKUM]

- Pengguna di bawah 18 tahun memakai Ciel dengan persetujuan orang tua atau wali.
- Fitur pembelian dan kontrol laptop hanya untuk pengguna 18 tahun ke atas.
- Ciel tidak membuat profil perilaku pengguna di bawah 18 tahun dan tidak mengirimi mereka pemasaran.
- Data yang dipakai untuk memeriksa usia hanya dipakai untuk keperluan itu.

Aturan yang perlu dicocokkan ahli hukum: UU 27/2022 soal data pribadi anak dan PP 17/2025 (PP Tunas) soal verifikasi usia dan persetujuan orang tua.

## 9. Keamanan

Data dikirim lewat koneksi terenkripsi. Akses ke data dibatasi per akun. Token perangkat disimpan di penyimpanan rahasia sistem operasi. Rincian teknis ada di [../security.md](../security.md). Tidak ada sistem yang kebal, jadi jangan kirim data rahasia yang tidak perlu ke Ciel.

## 10. Kalau terjadi kebocoran data [CEK HUKUM]

Kalau ada kegagalan pelindungan data pribadi yang menyangkut datamu, kami memberi tahu kamu dan lembaga yang berwenang secara tertulis dalam tenggat yang diatur undang-undang [ISI: tenggat, PERLU DICEK], berisi data apa yang terdampak, kapan dan bagaimana terjadinya, dan apa yang kami lakukan.

## 11. Perubahan kebijakan

Perubahan diumumkan di halaman ini sebelum berlaku. Kalau perubahannya besar, kamu diminta menyetujuinya lagi saat masuk berikutnya, seperti mekanisme versi yang sekarang (`terms.LEGAL_VERSION`).

## 12. Kontak dan pengaduan

[ISI: nama pengelola], [ISI: email], [ISI: alamat]. Kalau jawaban kami tidak memuaskan, kamu bisa mengadu ke lembaga pelindungan data pribadi yang berwenang [PERLU DICEK: nama lembaga dan cara mengadu].

## 13. Catatan untuk ahli hukum

- Asumsi: Ciel hanya menyasar pengguna di Indonesia. Kalau melayani pengguna di Uni Eropa, perlu tambahan sesuai GDPR (dasar hukum per tujuan, perwakilan di UE, klausul transfer).
- `privacy.py` sekarang merujuk Pasal 5, 6 sampai 14, 20 sampai 21, 25, 46, dan 56 UU 27/2022. Rujukan itu daftar periksa produk dan belum pernah ditinjau ahli hukum (`docs/LEGAL.md` bagian 9).
- Yang paling perlu dicek: dasar pemrosesan untuk log aktivitas, pemrosesan isi layar oleh penyedia model di luar negeri, dan cara verifikasi usia yang sah.
