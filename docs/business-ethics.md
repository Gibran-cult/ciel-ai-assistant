# Etika bisnis dan kepatuhan Ciel

Status: draf untuk ditinjau pemilik. Tanggal: 14 November 2026.
Aturan produk yang sudah berlaku ada di `docs/LEGAL.md` bagian 7 dan tetap dipakai. Dokumen ini memperluasnya untuk agent, ekstensi, dan aplikasi desktop.

## 1. Checklist dark pattern

Dark pattern adalah desain yang mendorong orang melakukan hal yang sebenarnya tidak mereka inginkan. Setiap layar baru diperiksa dengan daftar ini sebelum rilis. Kolom "Sekarang" diisi dari kondisi repo per 14 November 2026.

| No | Pola yang dilarang | Aturan Ciel | Sekarang |
|---|---|---|---|
| 1 | Hitung mundur atau stok palsu | Tidak ada penghitung waktu atau "tinggal sedikit" yang tidak nyata | Tidak ada (`docs/LEGAL.md` bagian 7) |
| 2 | Kalimat yang mempermalukan saat menolak | Tombol tolak ditulis netral: "Batal", "Tidak sekarang" | Tidak ada |
| 3 | Tombol tolak disembunyikan atau dibuat pucat | Tombol terima dan tolak setara di consent, konfirmasi, dan banner | Perlu dijaga di layar baru |
| 4 | Kotak yang tercentang otomatis | Semua pilihan persetujuan bawaannya kosong | Gerbang consent sudah kosong |
| 5 | Biaya yang baru muncul di akhir | Harga penuh tampil sebelum tombol bayar, termasuk biaya layanan | Harga tetap Rp79.000 |
| 6 | Sulit berhenti berlangganan | Berhenti semudah mendaftar, di tempat yang sama | Sekarang tanpa perpanjangan otomatis |
| 7 | Perpanjangan otomatis diam-diam | Hanya kalau pengguna memilih, dengan pengingat sebelumnya | Tidak ada perpanjangan otomatis |
| 8 | Uji coba gratis yang berubah jadi tagihan | Tidak meminta data pembayaran untuk mencoba | Tidak ada |
| 9 | Paket termahal dipilih otomatis | Tidak ada paket yang terpilih otomatis | Perlu dijaga |
| 10 | Izin berlebihan diminta di awal | Izin diminta saat dibutuhkan, satu per satu, dengan alasan | Berlaku untuk ekstensi dan desktop |
| 11 | Persetujuan ditumpuk | Satu tujuan per persetujuan | Lihat [privacy-consent.md](privacy-consent.md) bagian 2 |
| 12 | Gangguan berulang setelah ditolak | Setelah menolak, permintaan yang sama tidak muncul lagi sampai pengguna membukanya sendiri | Perlu dijaga |
| 13 | Agent mendorong belanja | Agent tidak menambah barang, garansi, atau asuransi yang tidak diminta, dan tidak menyarankan menaikkan batas belanja | Aturan baru |
| 14 | Rekomendasi berbayar tanpa label | Ciel tidak menerima komisi toko. Kalau berubah, rekomendasi berkomisi diberi label | Aturan baru, tunggu konfirmasi pemilik |
| 15 | Hapus akun dipersulit | Hapus akun dari Pengaturan tanpa perlu menghubungi siapa pun | Sudah ada |
| 16 | Pertanyaan menjebak (negasi ganda) | Kalimat pilihan ditulis positif dan pendek | Perlu dijaga |

Cara memakai: setiap pull request yang mengubah layar harga, persetujuan, konfirmasi, atau pengaturan menyertakan hasil checklist ini di deskripsinya.

## 2. Klaim, harga, dan ulasan

- Setiap klaim di website, toko aplikasi, dan aplikasi harus bisa ditunjukkan buktinya. Aturan ini sudah ada di `PRODUCT.md` ("setiap klaim di website harus cocok dengan aplikasi").
- Tidak ada testimoni, jumlah pengguna, logo kampus atau klien, dan angka performa kalau datanya belum ada.
- Kata "aman", "100%", dan "dijamin asli" tidak dipakai. Yang ditulis adalah apa yang dikerjakan: "Ciel hanya membantu pembelian di toko berlabel resmi dan menunjukkan buktinya".
- Ciel tidak menjanjikan barang asli. Keaslian barang tanggung jawab toko. Ciel hanya memeriksa status resmi toko.
- Harga paket di semua tempat sama dengan `PLANS` di `pricing.py`, dan diuji otomatis seperti sekarang.
- Tidak ada ulasan palsu, ulasan berbayar tanpa label, atau permintaan ulasan yang hanya dikirim ke pengguna yang puas.
- Deskripsi di toko aplikasi menyebut batas produk: situs yang tidak didukung, dan bahwa pengguna membayar sendiri.

## 3. Email pemasaran

Sekarang Ciel tidak mengirim email pemasaran. Kalau dimulai:

- Hanya ke pengguna yang memilih sendiri (opt-in terpisah, bawaan mati).
- Setiap email punya tautan berhenti berlangganan yang bekerja dengan satu klik tanpa login.
- Permintaan berhenti diproses segera dan dicatat di `consent_events`.
- Email menyebut nama dan kontak pengelola.
- Tidak dikirim ke pengguna di bawah 18 tahun.
- Email transaksi (bukti pembayaran, pengingat masa paket, peringatan keamanan) dipisah dari pemasaran dan tidak memuat promosi.

## 4. Halaman info bisnis

Halaman "Tentang dan kontak" di website dan aplikasi, ditautkan dari footer, toko aplikasi, dan dokumen legal:

| Isi | Nilai |
|---|---|
| Nama pengelola atau badan usaha | [ISI: nama] |
| Bentuk usaha | [ISI: perorangan atau badan usaha] |
| NIB | [ISI: nomor, setelah terbit] |
| Tanda daftar PSE | [ISI: nomor, setelah terbit] |
| Alamat | [ISI: alamat] |
| Email dukungan | [ISI: email] |
| Email privasi | [ISI: email] |
| Jam layanan dan waktu balas | [ISI: misalnya balasan paling lambat 3 hari kerja] |
| Media sosial | Instagram dan TikTok `@ciel_ai.1` (dari `PRODUCT.md`) |

Sekarang nama pengelola dan kontak datang dari secrets `OPERATOR_NAME` dan `CONTACT_URL`, dan keduanya belum diisi (`docs/LEGAL.md` bagian 4). Mengisinya adalah syarat sebelum fitur agent dibuka.

Catatan: alamat rumah pemilik perorangan menjadi data publik kalau ditulis di sini. Pilihan alamat yang dipakai perlu dibicarakan dengan ahli hukum [CEK HUKUM: informasi pelaku usaha yang wajib ditampilkan menurut aturan perdagangan elektronik].

## 5. Gambar dan aset

- Gambar stok hanya dari sumber yang lisensinya jelas mengizinkan pemakaian komersial.
- Setiap aset dicatat di `docs/asset-licenses.md` (berkas baru): nama berkas, sumber, pembuat, lisensi, tautan lisensi, tanggal diambil, dan di mana dipakai.
- Sekarang (fakta): logo dan robot 3D dibuat sendiri dari kode, huruf Fraunces dan Geist berlisensi SIL OFL 1.1, dan website tidak memakai foto stok.
- Gambar buatan AI dicatat dengan alat dan tanggalnya, dan tidak meniru karakter atau merek orang lain.
- Logo marketplace dan brand tidak dipakai di materi pemasaran tanpa izin. Di dalam aplikasi, nama toko ditulis sebagai teks.
- Tangkapan layar situs pihak ketiga tidak dipakai sebagai materi promosi.

## 6. Aturan toko aplikasi

### Chrome Web Store

| Aturan | Penerapan |
|---|---|
| Manifest V3 dan tanpa kode dari server | Semua logika di dalam paket. Server hanya mengirim data aksi |
| Satu tujuan yang jelas | "Ciel mengerjakan tugas di browser atas perintahmu, dengan persetujuan untuk aksi berisiko" |
| Izin sesedikit mungkin | `activeTab`, `scripting`, `sidePanel`, `storage`, izin situs diminta saat dibutuhkan. Tanpa `debugger`, tanpa akses semua situs, tanpa riwayat |
| Pemakaian data terbatas | Data hanya dipakai untuk tujuan yang diumumkan. Pembaruan kebijakan Juli 2026 (berlaku 1 Agustus 2026) mempertegas: hanya data yang benar-benar perlu untuk tujuan itu |
| Kebijakan privasi dan pengungkapan data | Tautan kebijakan privasi dan formulir praktik data diisi sesuai [privacy-consent.md](privacy-consent.md) bagian 3 |
| Tidak menyesatkan | Deskripsi dan tangkapan layar sesuai fungsi nyata |
| Biaya | Biaya daftar developer sekali bayar, US$5 menurut sumber sejak 2020 [PERLU DICEK jumlah sekarang] |

Aturan khusus untuk ekstensi yang mengotomatisasi browser dengan AI [PERLU DICEK di halaman kebijakan terbaru sebelum unggah].

### Microsoft

| Hal | Temuan |
|---|---|
| Akun developer individu | Gratis lewat alur pendaftaran baru. Menurut panduan Microsoft, akun individu untuk distribusi yang tidak terkait usaha, dan tidak bisa diubah menjadi akun perusahaan. Ciel adalah usaha, jadi kemungkinan butuh akun perusahaan dan badan usaha [PERLU DICEK] |
| Tanda tangan kode | Azure Artifact Signing untuk individu hanya tersedia di Amerika Serikat dan Kanada. Paket MSIX yang terbit di Microsoft Store ditandatangani ulang oleh Microsoft, jadi tidak perlu sertifikat sendiri. Installer EXE atau MSI tetap harus ditandatangani sendiri, juga kalau lewat Store |
| Aplikasi yang mengontrol aplikasi lain | Kelayakan di Microsoft Store [PERLU DICEK] |
| Edge Add-ons untuk ekstensi | Syarat dan biaya [PERLU DICEK] |

### Apple

| Hal | Temuan |
|---|---|
| Apple Developer Program | US$99 per tahun keanggotaan, harga bisa berbeda per wilayah |
| Distribusi | Lewat unduhan langsung dengan Developer ID dan notarisasi. Mac App Store mewajibkan sandbox yang tidak cocok dengan kontrol aplikasi lain |
| Izin sistem | Accessibility dan Screen Recording dijelaskan alasannya sebelum diminta |
| Aturan rinci untuk aplikasi otomatisasi | [PERLU DICEK] |

## 7. Syarat layanan marketplace soal pembelian otomatis

Hasil pengecekan 14 dan 15 November 2026. Rincian kutipan ada di [security.md](security.md) bagian 4.

| Marketplace | Mengizinkan alat otomatis | Tanda | Dasar |
|---|---|---|---|
| Shopee | Tidak | Melarang | Syarat Layanan butir 3.1 dan 6.3(k): robot, spider, perangkat otomatis, dan akses dengan perangkat tidak resmi termasuk bot |
| Tokopedia | Tidak | Melarang | Syarat dan ketentuan: dilarang memakai emulator, robot, macro, crawler, atau perangkat otomatis untuk mengakses layanan, termasuk otomatisasi dalam transaksi dan jual beli. Ringkasan dari tempelan pemilik 15 November 2026, belum dicocokkan dengan halaman aslinya [PERLU DICEK] |
| Lazada | Belum jelas | Belum jelas | Seluruh ketentuan sudah dibaca. Tidak ada larangan bot yang eksplisit, tetapi ada larangan akses tidak sah dan mengganggu sistem (bagian 2.2 butir 3) yang bisa ditafsirkan mencakup bot |
| Blibli | Belum jelas | Belum jelas | Butir 2.2 melarang mengambil isi situs secara sistematis untuk menyusun koleksi atau database, dengan perangkat otomatis atau manual, tanpa izin tertulis. Akses otomatis secara umum tidak disebut. Ringkasan dari tempelan pemilik 15 November 2026 [PERLU DICEK] |
| TikTok Shop | Belum jelas | Belum jelas | Syarat pembeli, termasuk versi Indonesia yang diterbitkan PT Tokopedia, tidak menyebut bot. Isinya larangan mengakali pembatasan teknis. Larangan bot yang eksplisit ada di syarat kreator dan disebut ada di Syarat Layanan TikTok yang umum. Ringkasan dari tempelan pemilik 15 November 2026 [PERLU DICEK] |

Aturan produk yang mengikuti temuan ini:

1. Marketplace bertanda "Melarang" tidak diotomatisasi. Agent tidak mengklik, mengetik, atau checkout di sana.
2. Marketplace bertanda "Belum jelas" diperlakukan sama dengan "Melarang" sampai ada pendapat ahli hukum atau izin tertulis. Tidak adanya larangan eksplisit, seperti di Lazada, belum berarti boleh.
3. Website brand hanya masuk daftar kalau syarat layanannya tidak melarang akses otomatis.
4. Sebelum mode pendamping dipakai di marketplace yang melarang, minta pendapat ahli hukum dan, kalau bisa, izin tertulis atau jalur resmi (program afiliasi atau API mitra) dari marketplace. Syarat program afiliasi Shopee sendiri melarang robot atau alat kueri otomatis, jadi jalur itu pun perlu dibaca teliti.
5. Status tiap marketplace disimpan di daftar toko (`automation`: `forbidden`, `unknown`, `allowed`) dan dicek ulang setiap 90 hari (usulan), karena syarat layanan bisa berubah.

Dampak ke visi produk: "agent membeli sampai selesai" di marketplace besar tidak bisa dijalankan sekarang tanpa melanggar syarat mereka. Yang bisa dijalankan: Ciel mencari dan memeriksa toko resmi, menyiapkan ringkasan, lalu pengguna yang menyelesaikan pembelian. Ini selaras dengan rekomendasi cara bayar opsi a (D4).

## 8. Kepatuhan usaha

Daftar ini melanjutkan `docs/LEGAL.md` bagian 2 dan 9, yang semuanya masih belum dicentang:

- NIB lewat OSS.
- Pendaftaran PSE Lingkup Privat.
- Tinjauan ahli hukum atas Ketentuan dan Privasi.
- Konsultasi pajak.

Usulan urutan: keempatnya selesai sebelum fitur pembelian dibuka. NIB dan PSE sebaiknya selesai sebelum ekstensi dirilis ke publik, karena tanpa pendaftaran PSE akses layanan bisa diblokir (`docs/LEGAL.md`).

## 9. Sumber yang dicek (14 November 2026)

- Kebijakan Chrome Web Store dan pembaruan 2026: https://developer.chrome.com/docs/webstore/program-policies/policies dan https://developer.chrome.com/blog/cws-policy-updates-2026
- Aturan Manifest V3: https://developer.chrome.com/docs/webstore/program-policies/mv3-requirements
- Pendaftaran developer Microsoft Store untuk individu: https://learn.microsoft.com/en-us/windows/apps/publish/whats-new-individual-developer
- Opsi tanda tangan kode Windows: https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options
- Penandatanganan ulang MSIX oleh Microsoft Store: https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/app-package-requirements
- Jenis akun developer Microsoft: https://learn.microsoft.com/en-us/windows/apps/publish/partner-center/open-a-developer-account
- Apple Developer Program: https://developer.apple.com/programs/enroll/
- Syarat Layanan Shopee: https://help.shopee.co.id/portal/4/article/71187
- Syarat program afiliasi Shopee: https://shopee.co.id/docs/6937
- Syarat dan ketentuan Tokopedia: https://www.tokopedia.com/help/article/terms-conditions
- Ketentuan Penggunaan Lazada Indonesia: https://www.lazada.co.id/terms-of-use/
- Syarat dan Ketentuan Blibli: https://www.blibli.com/faq/tentang-blibli/syarat-ketentuan/
