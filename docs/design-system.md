# Design system Ciel AI Agent

Status: draf untuk ditinjau pemilik. Tanggal: 14 November 2026.
Berlaku untuk web app, aplikasi desktop, dan ekstensi. Website pemasaran punya sistem sendiri di `website/DESIGN.md` dan tidak diubah di sini.

## 1. Dasar

- Sumber kebenaran warna dan huruf adalah token `--c-*` dan `--font-*` di `CIEL_CSS` (`app.py`). Dokumen ini tidak membuat warna baru. Token agent di bagian 2 hanya nama baru untuk warna yang sudah ada.
- Saat implementasi, token dipindah ke satu berkas (`design/tokens.json`) yang menghasilkan variabel CSS untuk ketiga klien. Komponen tidak memakai kode warna mentah.
- Logo tetap logo Kepingan di `assets/brand`. Wordmark "Ciel" tetap Fraunces.
- Gaya: tenang, datar, banyak ruang kosong. Biru untuk struktur dan aksi, kuning hanya untuk label "Dugaan" dan kepingan logo seperti sekarang.
- Setiap status punya ikon dan teks. Warna tidak pernah menjadi satu-satunya penanda.

## 2. Warna

### Token yang sudah ada

| Token | Terang | Gelap | Dipakai untuk |
|---|---|---|---|
| `--c-bg` | `#f1f1ee` | `#0e0d0c` | Latar halaman |
| `--c-surface` | `#fbfbf9` | `#181715` | Panel, kartu, dialog |
| `--c-raised` | `#e6e6e2` | `#24231f` | Hover, baris terpilih |
| `--c-text` | `#161513` | `#f4f4f2` | Teks utama |
| `--c-muted` | `#4b4a46` | `#b4b3ad` | Teks sekunder |
| `--c-faint` | `#5c5b56` | `#959490` | Keterangan kecil |
| `--c-control` | `#86817a` | `#827c72` | Garis tepi kontrol |
| `--c-accent` | `#2b4886` | `#9db3e8` | Tautan, tombol sekunder, fokus |
| `--c-accent-ink` | `#ffffff` | `#141a2a` | Teks di atas aksen |
| `--c-primary` | `#161513` | `#f4f4f2` | Tombol utama |
| `--c-on-primary` | `#f1f1ee` | `#141311` | Teks di atas tombol utama |
| `--c-gold` | `#e9d06a` | `#e9d06a` | Label "Dugaan", kepingan logo |
| `--c-gold-ink` | `#3d3209` | `#2e2606` | Teks di atas kuning |
| `--c-ok` | `#2e6a4c` | `#7cc49d` | Berhasil, terverifikasi |
| `--c-warn` | `#855a00` | `#e3b24f` | Perlu perhatian, menunggu |
| `--c-err` | `#a33b2c` | `#f0907f` | Gagal, ditolak, stop |

### Rasio kontras

Dihitung dengan rumus WCAG 2.x dari nilai token di atas. Syarat AA: 4,5:1 untuk teks biasa, 3:1 untuk teks besar dan komponen antarmuka.

| Pasangan | Terang | Gelap | Lolos AA |
|---|---|---|---|
| `text` di atas `bg` | 16,13 | 17,63 | Ya |
| `text` di atas `surface` | 17,61 | 16,27 | Ya |
| `text` di atas `raised` | 14,58 | 14,28 | Ya |
| `muted` di atas `bg` | 7,84 | 9,24 | Ya |
| `muted` di atas `surface` | 8,56 | 8,52 | Ya |
| `muted` di atas `raised` | 7,09 | 7,48 | Ya |
| `faint` di atas `bg` | 6,01 | 6,40 | Ya |
| `faint` di atas `surface` | 6,57 | 5,90 | Ya |
| `accent` di atas `bg` | 7,82 | 9,29 | Ya |
| `accent` di atas `surface` | 8,54 | 8,57 | Ya |
| `accent-ink` di atas `accent` | 8,85 | 8,30 | Ya |
| `on-primary` di atas `primary` | 16,13 | 16,86 | Ya |
| `gold-ink` di atas `gold` | 8,26 | 9,81 | Ya |
| `ok` di atas `bg` | 5,65 | 9,47 | Ya |
| `ok` di atas `surface` | 6,18 | 8,74 | Ya |
| `warn` di atas `bg` | 5,36 | 9,94 | Ya |
| `warn` di atas `surface` | 5,86 | 9,17 | Ya |
| `err` di atas `bg` | 5,76 | 8,32 | Ya |
| `err` di atas `surface` | 6,30 | 7,68 | Ya |
| `control` di atas `bg` (garis tepi, syarat 3:1) | 3,41 | 4,69 | Ya |
| `control` di atas `surface` (garis tepi, syarat 3:1) | 3,73 | 4,33 | Ya |

`--c-control` hanya untuk garis tepi dan ikon kontrol. Di tema terang rasionya di bawah 4,5:1, jadi tidak boleh dipakai untuk teks.

### Token baru untuk agent

| Token | Nilai terang | Nilai gelap | Kontras teks di atasnya | Dipakai untuk |
|---|---|---|---|---|
| `--c-agent-active` | `--c-accent` | `--c-accent` | lihat tabel di atas | Bingkai jendela, pil status, banner tab saat agent bekerja |
| `--c-agent-wait` | `--c-warn` | `--c-warn` | lihat tabel di atas | Status menunggu konfirmasi atau serah terima |
| `--c-stop-bg` | `#a33b2c` | `#f0907f` | 6,52 dengan `#ffffff`, 7,96 dengan `#141311` | Latar tombol Stop |
| `--c-stop-ink` | `#ffffff` | `#141311` | | Teks tombol Stop |
| `--c-official-bg` | `#2e6a4c` | `#7cc49d` | 6,40 dengan `#ffffff`, 9,05 dengan `#141311` | Label "Toko resmi" |
| `--c-official-ink` | `#ffffff` | `#141311` | | Teks label "Toko resmi" |
| `--c-rejected` | `--c-err` | `--c-err` | lihat tabel di atas | Teks dan ikon toko ditolak |

Cincin fokus: 2px `--c-accent` dengan jarak 2px dari elemen. Rasionya terhadap latar 7,82 di tema terang dan 9,29 di tema gelap.

## 3. Tipografi

| Peran | Huruf | Ukuran | Tinggi baris |
|---|---|---|---|
| Judul halaman | Fraunces 400 | 1,75rem sampai 2,6rem | 1,1 |
| Judul bagian | Geist 600 | 1,05rem sampai 1,25rem | 1,3 |
| Isi | Geist 400 | 0,92rem sampai 1rem | 1,6 |
| Isi di side panel ekstensi | Geist 400 | 0,875rem | 1,55 |
| Keterangan | Geist 400 | 0,8125rem | 1,5 |
| Tombol | Geist 600 | 0,92rem | 1,2 |
| Angka harga dan total | Geist 600, `tabular-nums` | 1rem, total 1,25rem | 1,3 |
| Kode, jalur file, domain | Geist Mono 400 | 0,86em | 1,5 |

- Ukuran ditulis dalam rem supaya ikut pengaturan ukuran huruf pengguna.
- Lebar baris teks isi maksimal 66 karakter.
- Domain toko selalu ditulis dengan Geist Mono supaya huruf yang mirip (`l`, `1`, `I`) mudah dibedakan.
- Desktop dan ekstensi membundel berkas huruf di dalam paket. Tidak ada permintaan ke server huruf saat aplikasi dibuka. Fraunces dan Geist berlisensi SIL Open Font License 1.1 (`docs/LEGAL.md` bagian 8).

## 4. Spacing, bentuk, ukuran

- Skala jarak: 4, 8, 12, 16, 24, 32, 48, 64 px.
- Sudut: kontrol 8px, kartu 16px, dialog 20px, pil dan label 999px. Kalau `CIEL_CSS` sudah memakai nilai lain untuk komponen yang sama, nilai di `CIEL_CSS` yang dipakai.
- Ukuran target: tombol dan kontrol utama minimal 44 × 44 px. Target apa pun minimal 24 × 24 px.
- Kedalaman: datar. Bidang yang diangkat naik satu langkah nada (`bg` ke `surface` ke `raised`). Lapisan yang melayang di atas aplikasi lain (pil status desktop) memakai garis tepi 1px `--c-line-strong`.
- Lebar side panel ekstensi: dirancang untuk 360px, tetap utuh sampai 320px.

## 5. Komponen

| Komponen | Varian | Catatan |
|---|---|---|
| Tombol | Utama (`primary`), sekunder (`accent`), tenang (teks saja), Stop (`stop-bg`) | Satu tombol utama per layar. Label berupa kata kerja: "Mulai", "Setuju", "Batal" |
| Kolom isian | Teks, angka rupiah, pilihan | Label selalu terlihat di atas kolom. Pesan salah muncul di bawah kolom dan menyebut cara memperbaikinya |
| Sakelar dan kotak centang | | Bawaan mati untuk semua pilihan pengumpulan data |
| Dialog | Konfirmasi biasa, konfirmasi pembelian, izin | Judul berupa pertanyaan atau efek ("Hapus 3 file?"). Fokus awal di tombol yang aman |
| Toast | Info, berhasil, gagal | Hilang sendiri setelah 6 detik kecuali berisi aksi. Diumumkan ke pembaca layar |
| Label status | Bekerja, menunggu, selesai, gagal, dihentikan, toko resmi, ditolak | Selalu ikon dan teks |
| Kartu | Rencana, aksi, ringkasan pembelian, laporan | Dipakai untuk benda yang memang satu kesatuan |
| Baris log | Lihat bagian 7 | |
| Banner | Tab dikontrol, serah terima, peringatan domain mirip | Menempel di atas, tidak menutupi isi |

Keadaan setiap komponen interaktif: biasa, hover, fokus keyboard, ditekan, mati, dan memuat. Keadaan hover tidak boleh menjadi satu-satunya cara melihat sebuah informasi.

## 6. Status

| Status | Aturan | Contoh teks |
|---|---|---|
| Memuat | Tunjukkan apa yang sedang dikerjakan. Pemutar tanpa teks tidak dipakai untuk agent | "Membaca halaman keranjang" |
| Bekerja lama | Setelah 10 detik, tambahkan langkah ke berapa dari berapa | "Langkah 4 dari 9: memindahkan file Bab 2" |
| Gagal | Sebut apa yang terjadi, apa yang sudah dan belum berubah, dan langkah berikutnya. Sertakan Request ID | "Aku nggak bisa membuka folder itu. Belum ada file yang berubah. Cek izin folder di Pengaturan." |
| Kosong | Jelaskan gunanya dan beri satu aksi | "Belum ada aktivitas. Tugas yang dikerjakan Ciel akan tercatat di sini." |
| Luring | Stop tetap bisa ditekan. Aksi baru ditahan | "Koneksi putus. Ciel berhenti dulu sampai tersambung lagi." |
| Dihentikan | Sebut yang sudah selesai dan yang berhenti di tengah | "Dihentikan. 3 dari 7 file sudah dipindah. Sisanya tidak disentuh." |

## 7. Antarmuka khusus agent

### Kartu rencana

Muncul sebelum agent mulai. Isinya: langkah bernomor dengan bahasa biasa, lingkup (situs, aplikasi, folder yang akan disentuh), aksi yang nanti butuh konfirmasi, dan dua tombol setara: "Mulai" dan "Ubah". Pilihan mode "Tanya dulu" atau "Jalan sendiri" ada di kartu ini, dengan "Tanya dulu" sebagai bawaan.

### Preview aksi

Di mode "Tanya dulu", setiap aksi tampil sebagai satu kalimat dengan targetnya sebelum dijalankan: "Ketik 'kalkulator ilmiah' di kolom pencarian". Elemen yang akan disentuh diberi garis sorot di halaman. Tombol: "Jalankan", "Lewati", "Stop".

### Dialog konfirmasi aksi berisiko

```
+--------------------------------------------------+
|  Hapus 3 file?                                   |
|                                                  |
|  File dipindah ke Recycle Bin dan masih bisa     |
|  dikembalikan dari sana.                         |
|                                                  |
|    draft-lama.docx                               |
|    catatan (2).txt                               |
|    Untitled.png                                  |
|                                                  |
|  Folder: Dokumen/Skripsi                         |
|                                                  |
|  [ Batal ]                    [ Hapus 3 file ]   |
+--------------------------------------------------+
```

Judul menyebut efeknya. Daftar target lengkap, bisa digulir kalau panjang. Tombol aksi mengulang efeknya ("Hapus 3 file"), tidak hanya "OK". Fokus awal di "Batal". Tombol Escape sama dengan "Batal".

### Dialog konfirmasi pembelian

```
+--------------------------------------------------+
|  Lanjut ke pembayaran?                           |
|                                                  |
|  [v Toko resmi]  Nama Toko                       |
|  Label "…" di marketplace.co.id                  |
|  Dicek 14 Nov 2026 10.42 · Lihat bukti           |
|                                                  |
|  Nama barang, varian                    1 ×      |
|                                    Rp 000.000    |
|  ------------------------------------------      |
|  Subtotal                          Rp 000.000    |
|  Ongkos kirim                      Rp  00.000    |
|  Biaya layanan                     Rp   0.000    |
|  Potongan                        - Rp   0.000    |
|  Total                             Rp 000.000    |
|                                                  |
|  Dikirim ke: Kos                                 |
|  Sisa batas bulan ini setelah ini: Rp 000.000    |
|  Kebijakan pengembalian toko                     |
|                                                  |
|  Kamu yang membayar di halaman toko.             |
|  Konfirmasi ini berlaku 10 menit.                |
|                                                  |
|  [ Batal ]              [ Lanjut ke pembayaran ] |
+--------------------------------------------------+
```

- Label "Toko resmi" memakai `--c-official-bg`, ikon centang, dan teks. Di sebelahnya nama toko, lalu bukti: teks label yang dibaca, domain dengan Geist Mono, dan waktu pengecekan.
- Angka rata kanan dengan `tabular-nums`. Total paling besar.
- Sisa waktu konfirmasi diumumkan ke pembaca layar saat tinggal 1 menit, dan ada tombol "Perpanjang" yang mengulang pengecekan toko dan harga.
- Kedua tombol sama tinggi dan sama lebar.

### Pesan saat toko ditolak

```
+--------------------------------------------------+
|  (!) Aku nggak bisa membeli di toko ini          |
|                                                  |
|  Toko ini tidak punya label resmi dari           |
|  marketplace, jadi aku nggak bisa memastikan     |
|  barangnya asli.                                 |
|                                                  |
|  [ Cari di toko resmi ]        [ Tutup ]         |
+--------------------------------------------------+
```

Kalimat penjelasan per alasan:

| Kode | Kalimat |
|---|---|
| `not_listed` | "Situs ini belum ada di daftar toko resmi Ciel." |
| `no_official_badge` | "Toko ini tidak punya label resmi dari marketplace, jadi aku nggak bisa memastikan barangnya asli." |
| `badge_unverifiable` | "Aku nggak berhasil memeriksa label resmi toko ini. Daripada menebak, aku berhenti di sini." |
| `lookalike_domain` | "Alamat situs ini mirip toko resmi tetapi berbeda. Situs seperti ini sering dipakai untuk menipu." |
| `untrusted_navigation` | "Tautan ini datang dari iklan atau pesan. Aku hanya membeli lewat alamat resmi yang kubuka sendiri." |
| `insecure` | "Koneksi ke situs ini tidak aman." |
| `automation_forbidden` | "Aturan situs ini melarang alat otomatis. Aku bisa menunjukkan toko resminya, lalu kamu yang melanjutkan sendiri." |
| `registry_stale` | "Status resmi toko ini sudah lama tidak dicek ulang. Aku berhenti sampai pengecekannya diperbarui." |
| `underage` | "Fitur pembelian hanya untuk pengguna 18 tahun ke atas." |
| `purchases_off` | "Fitur pembelian belum kamu aktifkan. Atur batas belanja dulu di Pengaturan." |
| `limit_exceeded` | "Total ini melewati batas belanja yang kamu atur." |

Untuk `lookalike_domain`, pesan menampilkan kedua alamat berdampingan dengan Geist Mono dan bagian yang berbeda ditandai.

### Log aktivitas

Satu baris per aksi:

```
10.42  [R1]  Mengetik di kolom pencarian      marketplace.co.id   Selesai
10.43  [R2]  Menyerahkan checkout             marketplace.co.id   Disetujui kamu
10.44  [R3]  Mengetik di kolom kata sandi     marketplace.co.id   Diblokir
```

Kolom: waktu, tingkat risiko, aksi dengan bahasa biasa, target, hasil. Baris bisa dibuka untuk melihat alasan keputusan dan perangkat. Saringan: tugas, perangkat, tingkat risiko, hasil. Ada tombol "Unduh" dan tautan ke pengaturan penghapusan. Log yang sama tampil di web, desktop, dan ekstensi.

### Tombol stop

- Selalu berlabel teks "Stop" dengan ikon kotak. Tidak pernah ikon saja.
- Warna `--c-stop-bg` dengan teks `--c-stop-ink`. Tidak ada tombol lain di produk yang memakai kombinasi ini.
- Ukuran minimal 44px tinggi, lebar minimal 88px.
- Posisi tetap: di pil status desktop, di kanan atas side panel, dan di banner tab. Tidak pernah tertutup dialog lain.
- Sekali tekan langsung berhenti. Tidak ada dialog "yakin?".
- Pintasan keyboard ditulis di tooltip dan di Pengaturan.

### Indikator agent aktif

| Keadaan | Warna | Teks |
|---|---|---|
| Bekerja | `--c-agent-active` | "Ciel sedang bekerja" |
| Menunggu kamu | `--c-agent-wait` | "Menunggu persetujuanmu" |
| Serah terima | `--c-agent-wait` | "Giliranmu. Ciel tidak melihat jendela ini." |
| Jeda karena kamu mengambil alih | `--c-muted` | "Dijeda. Lanjutkan atau stop?" |

Bingkai jendela desktop setebal 3px. Dengan `prefers-reduced-motion`, bingkai dan pil diam tanpa denyut.

### Izin

Daftar aplikasi, folder, dan situs dengan pilihan per baris. Baris yang selalu ditolak (perbankan, password manager) tampil dengan penjelasan singkat kenapa tidak bisa diizinkan.

## 8. Mode terang dan gelap

- Bawaan mengikuti sistem (`prefers-color-scheme`), dengan pilihan manual di Pengaturan. Pilihan tersimpan per akun.
- Setiap komponen diuji di kedua tema, termasuk popover dan dialog yang digambar di luar wadah utama, karena di situlah warna tema paling sering tidak ikut.
- Tidak ada informasi yang hanya terlihat saat hover.
- Ikon tray dan ikon ekstensi punya versi untuk bilah terang dan gelap.
- Tangkapan layar dan bukti toko ditampilkan dengan garis tepi 1px supaya tidak menyatu dengan latar.

## 9. Catatan per platform

| Platform | Catatan |
|---|---|
| Web (Streamlit sekarang) | Mengikuti `CIEL_CSS`. Dialog memakai `st.dialog`. Popover Streamlit digambar di luar `.stApp`, jadi gaya tema harus menjangkaunya |
| Desktop | Jendela utama, ikon tray, pil status yang selalu di atas, bingkai jendela yang dikontrol. Mengikuti skala huruf sistem |
| Ekstensi | Side panel sebagai tampilan utama, banner di tab, badge di ikon. Tidak ada popup kecil untuk konfirmasi pembelian karena terlalu sempit |

## 10. Suara dan teks

- Bahasa Indonesia santai, memakai "kamu" dan "aku". Tanpa kata hype, tanpa emoji di teks sistem, tanpa label campur bahasa Inggris kalau ada padanannya.
- Ciel jujur soal batas: "Aku nggak bisa memastikan" lebih baik daripada menebak.
- Kalimat konfirmasi menyebut efek dan cara membatalkannya.
- Angka rupiah ditulis "Rp79.000". Tanggal ditulis "14 November 2026".
- Tidak ada kalimat yang membuat pengguna merasa bersalah saat menolak atau membatalkan.
