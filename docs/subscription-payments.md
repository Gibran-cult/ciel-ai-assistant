# Subscription dan pembayaran Ciel

Status: draf untuk ditinjau pemilik. Tanggal: 14 November 2026.
Keputusan D3, D7, dan D8 dijawab pemilik pada 14 November 2026 mengikuti rekomendasi: tetap Mayar, opsi 2 dengan harga umum Rp129.000, dan harga mahasiswa tetap Rp79.000. Angka harga dan kuota dikonfirmasi ulang setelah biaya per tugas terukur di beta. Catatannya di [decisions.md](decisions.md).

## 1. Kondisi sekarang (fakta dari repo)

| Hal | Nilai |
|---|---|
| Paket Gratis | Rp0, dengan batas pesan per jam |
| Paket Pro | Rp79.000 sekali bayar untuk 30 hari, tanpa tagihan otomatis (`pricing.py`) |
| Paket Tim | Rp149.000 per pengguna, ada di `PLANS` tetapi tidak dijual |
| Penyedia pembayaran | Mayar, produksi sejak 1 November 2026. Midtrans menolak pengajuan pada 30 Oktober 2026 (`docs/PRO.md`) |
| Pengembalian dana | Diatur di `terms.py`, dikerjakan manual (`docs/LEGAL.md` bagian 6) |
| Sumber kebenaran harga | `PLANS` di `pricing.py`. Website wajib sama dan dijaga uji otomatis |

## 2. Dasar hitungan harga

Harga paket harus menutup biaya model per pengguna. Angka di bagian ini hitungan dari asumsi, belum data nyata.

Biaya satu tugas agent (dari [agent-architecture.md](agent-architecture.md) bagian 3, asumsi 15 langkah per tugas), dengan kurs asumsi Rp16.500 per US$ [PERLU DICEK]:

| Model | Per tugas | Dalam rupiah |
|---|---|---|
| `claude-haiku-5-5` | US$0,014 | sekitar Rp230 |
| `deepseek-flash` jam sibuk | US$0,041 | sekitar Rp680 |
| `gemini-3.5-flash-lite` | US$0,047 | sekitar Rp780 |
| `claude-sonnet-5-5` | US$0,285 | sekitar Rp4.700 |

Biaya terburuk per pengguna per bulan = kuota tugas × biaya per tugas:

| Kuota per bulan | Model murah (Rp230) | Model computer use (Rp4.700) |
|---|---|---|
| 30 tugas | Rp6.900 | Rp141.000 |
| 100 tugas | Rp23.000 | Rp470.000 |
| 150 tugas | Rp34.500 | Rp705.000 |
| 300 tugas | Rp69.000 | Rp1.410.000 |

Yang terlihat dari tabel: kuota harus dihitung per bulan, dan langkah yang memakai model computer use harus jarang atau punya kuota sendiri. Biaya chat per pengguna belum ada di tabel ini [ISI: dari data produksi].

Biaya pembayaran lewat Mayar (dari halaman harga dan FAQ Mayar): QRIS 0,7%, e-wallet 1,5% (Jenius 2%), virtual account Rp4.000 per transaksi, belum termasuk pajak, ditambah biaya admin platform yang besarnya tergantung paket Mayar [PERLU DICEK di dashboard]. Untuk order Rp79.000: QRIS sekitar Rp553, e-wallet sekitar Rp1.185, virtual account Rp4.000.

## 3. Paket (keputusan D7)

Semua angka harga dan kuota di bawah adalah usulan.

| Opsi | Susunan | Kelebihan | Kekurangan |
|---|---|---|---|
| 1. Satu paket berbayar, harga tetap | Gratis. Pro Rp79.000 untuk semua, termasuk agent 100 tugas per bulan | Paling sederhana, tidak ada perubahan harga | Tidak ada ruang untuk diskon mahasiswa. Margin tipis untuk pemakai berat |
| 2. Harga umum naik, harga mahasiswa tetap (rekomendasi) | Gratis. Pro umum Rp129.000. Pro mahasiswa Rp79.000. Keduanya berisi fitur yang sama, termasuk agent 150 tugas per bulan | Mahasiswa yang sekarang tidak kena kenaikan. Selisih harga umum menutup biaya agent. Tetap satu paket berbayar | Pengguna umum yang sudah membeli Rp79.000 perlu masa peralihan |
| 3. Dua tingkat berbayar | Gratis. Pro Rp79.000 (fitur skripsi, agent 30 tugas). Agent Rp149.000 (agent 300 tugas dan bantuan belanja). Masing-masing punya harga mahasiswa | Pengguna membayar sesuai pemakaian | Enam kombinasi harga, halaman harga lebih rumit, lebih banyak yang diuji |

Usulan isi paket Gratis untuk agent: 10 tugas per bulan tanpa bantuan pembelian, supaya orang bisa mencoba.

Aturan yang berlaku di semua opsi:

- Bantuan pembelian hanya untuk akun 18 tahun ke atas.
- Kuota tugas terlihat di aplikasi, dengan sisa kuota dan tanggal reset.
- Masa peralihan: pembeli sebelum tanggal perubahan harga tetap memakai harga lama sampai masa paketnya habis.
- Harga baru masuk `PLANS` di `pricing.py` dulu, lalu website, dan `terms.LEGAL_VERSION` dinaikkan.

## 4. Diskon mahasiswa (keputusan D8)

Dihitung dari harga umum Rp129.000 (opsi 2):

| Opsi | Harga mahasiswa | Catatan |
|---|---|---|
| 30% | Rp90.300 | Lebih mahal dari Pro sekarang |
| Sekitar 39% (rekomendasi) | Rp79.000 | Sama dengan harga Pro sekarang, jadi tidak ada kenaikan untuk mahasiswa |
| 50% | Rp64.500 | Margin paling tipis. Biaya terburuk agent 150 tugas (Rp34.500) ditambah biaya bayar sudah lebih dari setengahnya |

Kalau D7 memilih opsi 1, diskon mahasiswa berarti menurunkan harga dari Rp79.000, dan hitungannya perlu diulang dengan data biaya chat nyata.

## 5. Verifikasi mahasiswa

Tujuan: mengambil data sesedikit mungkin.

| Cara | Data yang diambil | Kapan dipakai |
|---|---|---|
| Email kampus (rekomendasi) | Alamat email berakhiran `.ac.id`. Ciel mengirim tautan verifikasi ke alamat itu | Cara utama |
| Domain kampus di luar `.ac.id` | Sama, untuk domain yang ditambahkan pemilik ke daftar setelah dicek | Kalau kampus memakai domain lain |
| Foto kartu mahasiswa | Foto kartu, diperiksa manual | Hanya kalau pengguna tidak punya email kampus |

Aturan:

- Yang disimpan setelah verifikasi: hash alamat email, domain kampus, tanggal verifikasi, dan tanggal kedaluwarsa. Alamat email utuh tidak disimpan (usulan).
- Foto kartu mahasiswa dihapus setelah verifikasi selesai, paling lama 7 hari setelah diunggah (usulan). Yang disimpan hanya hasilnya. NIM dan data lain di kartu tidak dicatat.
- Satu email kampus untuk satu akun Ciel.
- Cek ulang setiap 12 bulan (usulan). Pengguna diingatkan 14 hari sebelum kedaluwarsa. Kalau tidak diverifikasi ulang, pembelian berikutnya memakai harga umum. Masa paket yang sudah dibayar tidak berubah.
- Pengguna bisa menghapus status mahasiswanya dari Pengaturan > Paket.
- Email kampus tidak dipakai untuk pemasaran.

Keterbatasan yang diterima: alumni yang email kampusnya masih aktif bisa lolos. Menutup celah ini butuh data lebih banyak, dan itu bertentangan dengan tujuan minimalisasi.

Tabel baru: `student_verifications (owner, method, email_hash, domain, verified_at, expires_at)`.

## 6. Harga yang transparan

- Harga penuh, masa berlaku, dan isi paket tampil sebelum tombol bayar.
- Biaya pembayaran ditanggung Ciel dan tidak ditambahkan di halaman bayar. Kalau suatu saat dibebankan ke pembeli, jumlahnya tampil sebelum tombol bayar.
- Harga mahasiswa dan harga umum tampil berdampingan, dengan syarat verifikasinya.
- Kuota dan batas ditulis dengan angka kalau angkanya tetap. Website statis memakai kalimat tanpa angka kalau angkanya datang dari konfigurasi aplikasi (aturan di `PRODUCT.md`).
- Tidak ada harga coret kecuali harga itu memang pernah berlaku.
- Perubahan harga diumumkan minimal 14 hari sebelumnya (usulan).

## 7. Berhenti langganan dan pengingat

Sekarang paket dibayar sekali dan berhenti sendiri setelah 30 hari, jadi tidak ada yang perlu dibatalkan.

| Opsi | Isi | Kelebihan | Kekurangan |
|---|---|---|---|
| a. Tetap sekali bayar (rekomendasi) | Pengingat di aplikasi 3 hari sebelum masa paket habis, dengan tombol beli lagi | Tidak mungkin ada tagihan yang tidak disadari. Tidak perlu fitur batal | Pengguna harus membeli ulang tiap bulan |
| b. Perpanjangan otomatis sebagai pilihan | Pengguna menyalakannya sendiri | Lebih praktis untuk pengguna setia | Butuh penyedia pembayaran yang mendukung tagihan berulang [PERLU DICEK untuk Mayar], dan fitur batal, pengingat, serta pengembalian |

Kalau opsi b diambil nanti, aturannya:

- Perpanjangan otomatis bawaannya mati.
- Pengingat 7 hari dan 1 hari sebelum tagihan, lewat aplikasi dan email transaksi.
- Berhenti dari Pengaturan > Paket, tempat yang sama dengan mengaktifkannya, dalam jumlah langkah yang sama.
- Berhenti tidak butuh alasan dan tidak melewati layar bujukan.
- Setelah berhenti, paket tetap aktif sampai akhir masa yang sudah dibayar.

## 8. Alur pengembalian dana

Aturannya ada di [legal/refund-policy.md](legal/refund-policy.md). Alur kerjanya:

1. Pengguna mengajukan lewat kontak dengan nomor order.
2. Pemilik mencari order di `pro_orders` dan memeriksa status.
3. Jawaban paling lambat 3 hari kerja.
4. Dana dikirim paling lambat 14 hari kerja setelah disetujui, lalu order ditandai dan paket dicabut kalau pengembaliannya penuh.

Yang perlu dibuat sebelum pengguna bertambah banyak: halaman admin kecil untuk langkah 2 sampai 4, menggantikan SQL manual.

## 9. Payment gateway (keputusan D3)

| Opsi | Syarat | Biaya | Catatan |
|---|---|---|---|
| A. Tetap Mayar (rekomendasi) | Akun individu cukup KTP dan swafoto (`docs/PRO.md`) | QRIS 0,7%, e-wallet 1,5% (Jenius 2%), virtual account Rp4.000, ditambah biaya admin platform [PERLU DICEK], belum termasuk pajak | Sudah berjalan. Webhook tidak ditandatangani, sudah ditangani dengan pengecekan ulang ke API (`docs/PRO.md`). Dukungan tagihan berulang [PERLU DICEK] |
| B. Midtrans | Menolak pengajuan Ciel pada 30 Oktober 2026. Kemungkinan butuh badan usaha [PERLU DICEK] | Menurut sumber sekunder: virtual account sekitar Rp4.000, kartu 2,9% ditambah Rp2.000, QRIS 0,7% [PERLU DICEK di halaman resmi] | Kode integrasi masih ada di repo |
| C. Xendit | [PERLU DICEK] | Menurut sumber sekunder ada biaya proses tambahan per transaksi dan biaya minimum bulanan [PERLU DICEK] | Belum pernah dicoba |

Catatan QRIS: satu sumber menyebut sejak 1 Oktober 2026 transaksi QRIS sampai Rp100.000 bebas biaya merchant [PERLU DICEK ke Bank Indonesia atau Mayar]. Kalau benar, order Rp79.000 lewat QRIS lebih murah dari hitungan di bagian 2.

Rekomendasi: A sampai ada badan usaha. Setelah itu bandingkan lagi dengan angka resmi.

Payment gateway ini hanya untuk paket Ciel. Pembelian barang oleh agent tidak lewat sini (lihat D4 di [security.md](security.md) bagian 4).

## 10. Pajak dan catatan

- Catatan order disimpan 10 tahun (`docs/LEGAL.md` bagian 5).
- Pertanyaan untuk konsultan pajak: PPh final UMKM atas omzet, dan apakah harga perlu memuat PPN [PERLU DICEK].

## 11. Sumber yang dicek (14 November 2026)

- Harga Mayar: https://mayar.id/pricing dan https://mayar.id/faq
- Biaya di dokumentasi Mayar: https://docs.mayar.id/mor/fees
- Perbandingan biaya payment gateway (sumber sekunder): https://www.matthewswong.com/en/indonesia/payment-gateway-fees/
