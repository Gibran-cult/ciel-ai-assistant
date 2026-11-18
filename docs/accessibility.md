# Aksesibilitas Ciel AI Agent

Status: draf untuk ditinjau pemilik. Tanggal: 14 November 2026.
Target: WCAG 2.2 tingkat AA di web app, aplikasi desktop, dan ekstensi. Token warna dan komponen ada di [design-system.md](design-system.md).

Agent punya satu kebutuhan aksesibilitas yang tidak ada di chatbot: pengguna harus selalu tahu apa yang sedang dikerjakan agent dan bisa menghentikannya, dengan cara apa pun mereka memakai komputer.

## 1. Alt text dan gambar

| Jenis gambar | Aturan |
|---|---|
| Logo | Alt "Ciel" sekali per halaman. Logo kedua di halaman yang sama memakai alt kosong |
| Ikon di dalam tombol berlabel | Disembunyikan dari pembaca layar (`aria-hidden`) |
| Tombol ikon tanpa teks | Punya nama yang bisa diakses, misalnya "Tutup dialog". Tombol Stop selalu berteks |
| Bukti label toko (potongan gambar) | Alt menyebut isinya: "Label Shopee Mall di halaman toko Nama Toko". Teks label juga ditulis sebagai teks biasa di sebelahnya |
| Tangkapan layar di log | Alt menyebut aplikasi dan aksi. Deskripsi aksi tetap ada sebagai teks di baris log |
| Grafik dan diagram | Deskripsi teks di bawahnya, seperti `visuals.describe` yang sudah ada |
| Gambar hiasan | Alt kosong |
| Gambar produk dari toko | Alt memakai nama produk yang dibaca dari halaman |

Uji otomatis menolak gambar tanpa atribut alt di web app dan ekstensi.

## 2. Kontras warna

- Semua pasangan warna teks lolos 4,5:1 di tema terang dan gelap. Angkanya ada di design-system.md bagian 2.
- Garis tepi kontrol, ikon bermakna, dan cincin fokus minimal 3:1 terhadap latar di sekitarnya.
- `--c-control` tidak dipakai untuk teks.
- Status tidak hanya dibedakan warna: bekerja, menunggu, gagal, toko resmi, dan ditolak masing-masing punya ikon dan teks.
- Teks di atas gambar atau tangkapan layar diberi latar padat.
- Setiap warna baru wajib lewat skrip pengecek kontras di CI sebelum masuk berkas token.

## 3. Navigasi penuh dengan keyboard

- Semua yang bisa diklik bisa dijangkau dan dijalankan dengan keyboard: Tab dan Shift+Tab untuk pindah, Enter atau Spasi untuk menjalankan, Escape untuk menutup.
- Urutan fokus mengikuti urutan baca. Tidak ada jebakan fokus.
- Dialog mengurung fokus selama terbuka dan mengembalikan fokus ke pemicunya saat ditutup.
- Fokus awal dialog konfirmasi ada di tombol yang aman ("Batal").
- Pintasan stop: `Ctrl+Shift+F12` di desktop dan `Alt+Shift+S` di ekstensi (usulan), bisa diganti di Pengaturan. Pintasan satu huruf tanpa tombol pengubah tidak dipakai.
- Tautan lewati ("Lewati ke isi") di web app.
- Log aktivitas bisa dijelajahi per baris dengan tombol panah, dan baris bisa dibuka dengan Enter.
- Tidak ada aksi yang hanya bisa dilakukan dengan menyeret. Mengurutkan langkah rencana punya tombol "Naik" dan "Turun".
- Di desktop, pil status dan menu tray bisa dijangkau keyboard.

## 4. Fokus yang kelihatan

- Cincin fokus 2px `--c-accent` dengan jarak 2px, tampil untuk fokus keyboard (`:focus-visible`).
- Fokus tidak pernah dihilangkan tanpa pengganti.
- Elemen yang sedang fokus tidak tertutup banner tab, pil status, atau kepala halaman yang menempel.
- Sorotan elemen yang akan disentuh agent berbeda dari cincin fokus pengguna: garis putus-putus `--c-agent-active`, supaya keduanya tidak tertukar.

## 5. Dukungan pembaca layar

- Struktur: satu `h1` per layar, judul berurutan, daftar sebagai daftar, tabel log sebagai tabel dengan kepala kolom.
- Dialog memakai peran dialog dengan judul dan deskripsi yang terhubung.
- Status agent diumumkan lewat area live. Pengumuman sopan (`polite`) untuk kemajuan langkah, dan paling banyak satu pengumuman per langkah supaya tidak membanjiri. Pengumuman mendesak (`assertive`) hanya untuk tiga hal: butuh konfirmasi, agent dihentikan, dan peringatan domain mirip.
- Dialog pembelian dibacakan berurutan: status toko, nama toko, barang, rincian biaya, total, lalu tombol. Total diberi label "Total" yang terhubung dengan angkanya.
- Label "Toko resmi" dibacakan sebagai teks, misalnya "Toko resmi, label Shopee Mall, dicek pukul 10.42".
- Kolom isian punya label yang terhubung. Pesan salah terhubung ke kolomnya dan diumumkan.
- Bahasa halaman diset `id`.
- Aplikasi desktop menyediakan nama dan peran setiap kontrol ke UI Automation (Windows) dan Accessibility API (macOS). Diuji dengan Narrator atau NVDA di Windows dan VoiceOver di macOS.
- Banner "Tab ini sedang dikontrol Ciel" diumumkan sekali saat muncul.

## 6. Hal khusus agent

| Kebutuhan | Aturan |
|---|---|
| Batas waktu konfirmasi | Pengguna diberi tahu sebelum waktu habis dan bisa memperpanjang. Konfirmasi yang habis waktu berarti aksi batal dengan aman |
| Gerak | Dengan `prefers-reduced-motion`, bingkai dan pil status tidak berdenyut dan tidak ada animasi masuk |
| Agent dan teknologi bantu | Saat agent mengontrol jendela, pembaca layar pengguna tetap bisa membaca jendela itu. Agent jeda kalau pengguna menekan tombol apa pun |
| Kecepatan | Di mode "Tanya dulu", agent menunggu tanpa batas waktu untuk aksi R0 dan R1 |
| Bahasa sederhana | Teks konfirmasi ditulis dengan kalimat pendek dan kata sehari-hari |
| Pembesaran | Tampilan tetap utuh pada pembesaran 200% dan pada lebar 320px tanpa gulir mendatar |
| Bantuan | Tautan bantuan ada di tempat yang sama di semua layar |
| Login | Login lewat Google tanpa teka-teki. Ciel tidak menambah CAPTCHA sendiri |

## 7. Pemetaan ke kriteria WCAG 2.2

| Kriteria | Tingkat | Penerapan di Ciel |
|---|---|---|
| 1.1.1 Non-text Content | A | Bagian 1 |
| 1.3.1 Info and Relationships | A | Struktur judul, tabel log, label kolom |
| 1.4.1 Use of Color | A | Ikon dan teks di setiap status |
| 1.4.3 Contrast (Minimum) | AA | Bagian 2 |
| 1.4.4 Resize Text | AA | Ukuran rem, uji 200% |
| 1.4.10 Reflow | AA | Lebar 320px |
| 1.4.11 Non-text Contrast | AA | Garis tepi kontrol dan cincin fokus minimal 3:1 |
| 2.1.1 Keyboard | A | Bagian 3 |
| 2.1.2 No Keyboard Trap | A | Dialog bisa ditutup dengan Escape |
| 2.1.4 Character Key Shortcuts | A | Pintasan memakai tombol pengubah dan bisa diganti |
| 2.2.1 Timing Adjustable | A | Perpanjangan konfirmasi |
| 2.3.3 Animation from Interactions | AAA, dipenuhi sukarela | `prefers-reduced-motion` dihormati |
| 2.4.3 Focus Order | A | Urutan fokus mengikuti urutan baca |
| 2.4.7 Focus Visible | AA | Bagian 4 |
| 2.4.11 Focus Not Obscured (Minimum) | AA | Banner dan pil tidak menutupi fokus |
| 2.5.7 Dragging Movements | AA | Tombol "Naik" dan "Turun" |
| 2.5.8 Target Size (Minimum) | AA | Minimal 24 × 24 px, kontrol utama 44 × 44 px |
| 3.1.1 Language of Page | A | `lang="id"` |
| 3.2.6 Consistent Help | A | Tautan bantuan di tempat yang sama |
| 3.3.1 Error Identification | A | Pesan salah di bawah kolom |
| 3.3.3 Error Suggestion | AA | Pesan menyebut cara memperbaiki |
| 3.3.4 Error Prevention (Legal, Financial, Data) | AA | Konfirmasi pembelian dan konfirmasi hapus, dengan ringkasan yang bisa diperiksa |
| 3.3.7 Redundant Entry | A | Batas belanja dan alamat tidak diminta ulang dalam satu alur |
| 3.3.8 Accessible Authentication (Minimum) | AA | Login Google, tanpa teka-teki tambahan |
| 4.1.2 Name, Role, Value | A | Nama dan peran untuk semua kontrol, termasuk di desktop |
| 4.1.3 Status Messages | AA | Area live untuk status agent |

## 8. Cara menguji

| Uji | Alat | Kapan |
|---|---|---|
| Otomatis: alt, label, kontras, peran | Pemeriksa aksesibilitas di CI untuk web app dan ekstensi | Setiap pull request |
| Kontras token | Skrip rumus WCAG atas berkas token | Setiap perubahan token |
| Keyboard saja | Manual: selesaikan satu tugas, satu konfirmasi pembelian, dan satu stop tanpa mouse | Setiap rilis |
| Pembaca layar | NVDA atau Narrator di Windows, VoiceOver di macOS, untuk alur yang sama | Setiap rilis yang mengubah antarmuka |
| Pembesaran 200% dan lebar 320px | Manual | Setiap rilis yang mengubah tata letak |
| Tema terang dan gelap | Manual untuk semua dialog agent | Setiap rilis yang mengubah antarmuka |
| Gerak dikurangi | Manual dengan pengaturan sistem | Setiap rilis yang menambah animasi |

Rilis ditahan kalau ada temuan yang membuat stop, konfirmasi, atau log tidak bisa dipakai dengan keyboard atau pembaca layar.

## 9. Yang belum ada

- Web app sekarang berjalan di Streamlit, yang membatasi kontrol atas urutan fokus dan peran elemen. Temuan yang tidak bisa diperbaiki di Streamlit dicatat dan menjadi masukan untuk keputusan pindah frontend.
- Belum ada uji dengan pengguna pembaca layar sungguhan. Direncanakan sebelum fitur pembelian dibuka [ISI: kapan dan dengan siapa].
