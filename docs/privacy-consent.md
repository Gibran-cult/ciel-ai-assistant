# Privasi dan consent Ciel AI Agent

Status: draf untuk ditinjau pemilik. Tanggal: 14 November 2026.
Daftar kewajiban hukum yang sudah ada tetap di `docs/LEGAL.md`. Dokumen ini menambah hal baru untuk agent. Semua rujukan aturan di sini adalah daftar periksa produk dan belum ditinjau ahli hukum.

## 1. Banner persetujuan cookie

Kondisi sekarang (fakta): Ciel tidak memasang cookie analitik atau iklan, jadi belum ada banner. Banner di bawah wajib terpasang sebelum alat pertama di luar kategori Wajib dipakai. Sampai saat itu cukup pemberitahuan singkat dengan tautan ke [legal/cookie-policy.md](legal/cookie-policy.md).

### Aturan

| No | Aturan | Cara mengujinya |
|---|---|---|
| B1 | "Tolak semua" dan "Terima semua" sama ukuran, warna, bentuk, dan posisi baris | Uji otomatis membandingkan ukuran dan gaya kedua tombol |
| B2 | Ada tombol ketiga "Atur pilihan" yang membuka kategori terpisah: Wajib, Preferensi, Analitik, Pemasaran | Uji antarmuka |
| B3 | Semua kategori selain Wajib bawaannya mati. Tidak ada kotak yang tercentang otomatis | Uji memeriksa nilai awal setiap sakelar |
| B4 | Tidak ada cookie atau alat di luar kategori Wajib yang aktif sebelum pengguna memilih | Uji memuat halaman tanpa pilihan lalu memeriksa cookie dan permintaan jaringan |
| B5 | Menutup banner tanpa memilih dihitung menolak | Uji antarmuka |
| B6 | Setiap pilihan dicatat (lihat model data) | Uji memeriksa baris baru di tabel |
| B7 | Pilihan bisa diubah kapan saja dari Pengaturan > Privasi > Cookie, dengan jumlah langkah yang sama dengan saat memberi | Uji antarmuka |
| B8 | Banner tampil lagi kalau kategori atau alat baru ditambahkan, dan paling cepat 6 bulan setelah penolakan (usulan) | Uji versi kebijakan |
| B9 | Banner bisa dipakai penuh dengan keyboard dan pembaca layar, dan tidak menutupi tombol Stop | Uji aksesibilitas |
| B10 | Teks banner menyebut guna tiap kategori dengan bahasa biasa, tanpa kalimat yang menekan | Tinjauan teks dengan checklist dark pattern ([business-ethics.md](business-ethics.md) bagian 1) |

### Model data pencatatan

Tabel baru `consent_events`, hanya bisa ditambah:

| Kolom | Isi |
|---|---|
| `id` | ID kejadian |
| `owner` | ID pemilik akun, atau ID acak perangkat untuk pengguna tanpa login |
| `kind` | `cookies`, `terms`, `agent`, `purchase`, `marketing_email`, `student`, `data_setting` |
| `choice` | JSON pilihan, misalnya `{"analytics": false, "preferences": true}` atau `{"accepted": true}` |
| `version` | Versi dokumen atau banner yang ditampilkan |
| `surface` | `web`, `extension`, `desktop` |
| `created_at` | Waktu |

Tabel `consents` yang sekarang tetap dipakai untuk gerbang versi ketentuan. `consent_events` menambah riwayat lengkap, termasuk penarikan persetujuan, yang sekarang belum tercatat.

## 2. Audit form consent

### Yang sudah ada

| Form | Lokasi | Temuan | Tindakan |
|---|---|---|---|
| Gerbang "Sebelum mulai" | `login.render_consent`, `app.consent_needed`, tabel `consents` | Satu kotak centang yang bawaannya kosong, tombol baru aktif setelah dicentang, tersimpan per versi. Ketentuan, Privasi, dan pemrosesan di luar negeri digabung dalam satu centang | Pertahankan sebagai persetujuan dasar. Persetujuan agent, pembelian, dan pemasaran dibuat terpisah, tidak ditumpuk ke centang ini |
| Pengguna tanpa login | Aplikasi bisa dicoba tanpa masuk | Tidak ada persetujuan yang tercatat untuk tamu | Tampilkan pemberitahuan privasi singkat sebelum pesan pertama dan catat di `consent_events` dengan ID perangkat acak [CEK HUKUM] |
| Penarikan persetujuan | Pengaturan > Data saya (hapus per jenis, Hapus akun) | Bisa menghapus data, tetapi penarikan tidak dicatat sebagai kejadian | Catat penarikan di `consent_events` |
| Edit AI dan Ilustrasi | Halaman Privasi menyebut foto dikirim ke DeepSeek yang bisa melatih model | Peringatannya ada di halaman Privasi, belum tentu ada di tempat fitur dipakai | Tambah keterangan singkat di dialog Edit AI sebelum foto dikirim |
| Pembelian paket | `pricing.py`, halaman bayar Mayar | Data nama dan email dikirim ke Mayar | Sebut di samping tombol beli |
| Usia | `terms.py` dan `privacy.py` hanya berupa pernyataan | Tidak ada pemeriksaan | Lihat bagian 5 |
| Email pemasaran | Belum ada | Tidak ada | Kalau dibuat: opt-in terpisah dan tautan berhenti berlangganan |

### Yang baru untuk agent

| Form | Kapan muncul | Isi persetujuan | Bawaan |
|---|---|---|---|
| Aktivasi agent | Pertama kali memakai ekstensi atau desktop | Agent membaca halaman atau jendela yang diizinkan, mencatat aksi, dan mengirim teks halaman ke penyedia model. Tautan ke Kebijakan Penggunaan Agent | Belum disetujui |
| Izin situs | Saat tugas pertama kali menyentuh sebuah situs | Dialog izin browser untuk situs itu | Ditolak |
| Izin aplikasi dan folder | Saat pengguna mengaturnya di desktop | Pilihan per aplikasi dan per folder | Tidak boleh |
| Izin sistem macOS | Saat fitur pertama kali butuh | Accessibility dan Screen Recording, dengan penjelasan sebelum dialog sistem muncul | Ditolak |
| Tangkapan layar | Saat tugas pertama kali butuh gambar | Tangkapan layar jendela yang diizinkan dikirim ke penyedia model dan tidak disimpan | Mati |
| Aktivasi pembelian | Saat pengguna membuka fitur pembelian | Pernyataan usia 18 tahun ke atas, batas belanja, dan pemahaman bahwa pengguna membayar sendiri | Mati |
| Verifikasi mahasiswa | Saat meminta diskon | Email kampus dipakai hanya untuk verifikasi | Tidak diminta |
| Pengaturan data opsional | Pengaturan > Privasi | Lihat bagian 4 | Mati |

Aturan untuk semua form: satu tujuan per centang, tidak ada centang yang terisi otomatis, menolak tidak mengurangi fitur yang tidak bergantung pada data itu, teks memakai bahasa biasa, dan setiap pilihan masuk `consent_events`.

## 3. Minimalisasi data

"Wajib" berarti fitur terkait tidak bisa jalan tanpanya. Masa simpan bertanda (usulan) menunggu keputusan pemilik.

### Akun dan chat (sudah ada)

| Data | Alasan | Wajib atau opsional | Disimpan | Cara menghapus |
|---|---|---|---|---|
| Nama, email, foto profil Google | Identitas akun | Wajib untuk login. Chat bisa dicoba tanpa login | Selama akun ada | Hapus akun |
| Pesan, file, foto, jawaban | Menjawab | Wajib untuk chat | Riwayat di akun sampai dihapus. Di server model `CHAT_RETENTION_DAYS` hari | Hapus chat, Data saya |
| Memori jangka panjang | Mengingat konteks | Opsional | Sampai dihapus | Data saya |
| Profil (panggilan, bidang studi) | Menyesuaikan jawaban | Opsional | Sampai dihapus | Pengaturan > Profil |
| Dataset pribadi | Analisis data | Opsional | Sampai dihapus | Data saya |
| Catatan order paket | Pembukuan dan pajak | Wajib kalau membeli | 10 tahun | Tidak bisa dihapus pengguna |
| Catatan persetujuan | Bukti persetujuan | Wajib | Selama akun ada, lalu [ISI] | Tidak bisa dihapus pengguna [CEK HUKUM] |

### Agent, ekstensi, dan desktop (baru)

| Data | Alasan | Wajib atau opsional | Disimpan | Cara menghapus |
|---|---|---|---|---|
| Daftar perangkat (nama, jenis, versi, terakhir aktif) | Keamanan akun | Wajib untuk agent | Sampai perangkat dicabut | Pengaturan > Perangkat |
| Izin aplikasi, folder, situs | Membatasi agent | Wajib untuk agent | Sampai dicabut | Pengaturan > Izin agent |
| Perintah tugas dan rencana | Menjalankan tugas | Wajib untuk agent | 90 hari (usulan) | Hapus tugas, Data saya |
| Log aktivitas (aksi, target, keputusan, hasil) | Bukti dan keamanan | Wajib untuk agent | 90 hari (usulan) | Data saya. Menghapus log tidak membatalkan aksi yang sudah terjadi |
| Teks dan struktur halaman yang sedang dikerjakan | Agent perlu membaca untuk bertindak | Wajib untuk tugas browser | Tidak disimpan | Tidak ada yang perlu dihapus |
| Struktur jendela aplikasi (nama tombol dan kolom) | Agent perlu membaca untuk bertindak | Wajib untuk tugas desktop | Tidak disimpan | Tidak ada yang perlu dihapus |
| Tangkapan layar jendela yang diizinkan | Hanya untuk aplikasi tanpa struktur yang bisa dibaca | Opsional, bawaan mati | Tidak disimpan | Matikan di Pengaturan |
| Daftar dan nama file di folder yang diizinkan | Tugas file | Wajib untuk tugas file | Nama file yang disentuh masuk log | Data saya |
| Isi file | Hanya kalau tugas memintanya dibaca | Opsional per tugas | Tidak disimpan | Tidak ada yang perlu dihapus |
| Riwayat browsing | Tidak dikumpulkan | Tidak ada | Tidak ada | Tidak ada |
| Alamat tab yang dikerjakan agent | Bagian dari log aksi | Wajib untuk tugas browser | Sama dengan log, hanya domain dan jalur, tanpa parameter kueri | Data saya |
| Kolom kata sandi dan pembayaran | Tidak dibaca | Tidak ada | Tidak ada | Tidak ada |
| Ringkasan pembelian (toko, barang, harga, total, label alamat) | Konfirmasi dan batas belanja | Wajib untuk pembelian | Sama dengan log | Data saya |
| Bukti status toko | Menunjukkan dasar keputusan | Wajib untuk pembelian | Sama dengan log | Data saya |
| Batas belanja | Menegakkan batas | Wajib untuk pembelian | Sampai diubah | Pengaturan > Pembelian |
| Alamat pengiriman lengkap | Tidak disimpan Ciel. Alamat ada di akun toko pengguna | Tidak ada | Tidak ada | Tidak ada |
| Pernyataan usia 18 tahun ke atas | Syarat pembelian | Wajib untuk pembelian | Selama akun ada | Hapus akun |
| Tanggal lahir | Hanya kalau cara verifikasi usia yang dipilih membutuhkannya [CEK HUKUM] | Lihat bagian 5 | Hanya hasil "18+ ya atau tidak" | Hapus akun |
| Email kampus | Verifikasi mahasiswa | Opsional | Email disimpan sebagai hash setelah verifikasi (usulan), ditambah domain kampus dan tanggal | Pengaturan > Paket |
| Foto kartu mahasiswa | Cadangan kalau tidak punya email kampus | Opsional | Dihapus setelah verifikasi, paling lama 7 hari (usulan) | Otomatis |
| Catatan galat klien | Memperbaiki bug | Opsional, bawaan mati | 30 hari (usulan) | Matikan di Pengaturan |
| Statistik pemakaian fitur | Memperbaiki produk | Opsional, bawaan mati | Digabung tanpa identitas setelah 30 hari (usulan) | Matikan di Pengaturan |

Aturan penyaringan sebelum data keluar dari perangkat: kolom kata sandi, kolom pembayaran, dan teks berpola nomor kartu atau OTP dibuang dari teks halaman sebelum dikirim ke server.

## 4. Pilihan pengumpulan data di Pengaturan

Halaman Pengaturan > Privasi, sama di web, desktop, dan ekstensi:

| Pilihan | Bawaan | Akibat kalau mati |
|---|---|---|
| Memori jangka panjang | Mati sampai pengguna menyalakan [ISI: sekarang aktif otomatis setelah login, perlu keputusan pemilik] | Ciel tidak mengingat konteks antar percakapan |
| Simpan riwayat chat di akun | Nyala | Riwayat hanya di sesi browser |
| Tangkapan layar untuk agent | Mati | Agent hanya bekerja di aplikasi yang strukturnya bisa dibaca |
| Simpan log aktivitas lebih dari 30 hari | Mati (30 hari), bisa dinaikkan ke 90 hari | Log lama terhapus lebih cepat |
| Kirim catatan galat | Mati | Bug lebih lama ditemukan |
| Statistik pemakaian | Mati | Tidak ada |
| Email info produk | Mati | Tidak ada email pemasaran |
| Cookie Preferensi dan Analitik | Mati | Tidak ada |

Di halaman yang sama: unduh data, hapus per jenis, hapus akun, daftar perangkat, daftar izin agent, dan riwayat persetujuan.

Log aktivitas minimal tetap ada selama agent dipakai, karena itu pengaman bagi pengguna sendiri. Pilihannya hanya lama simpan.

## 5. Verifikasi usia

Aturan yang diminta pemilik: di bawah 18 tahun wajib ada persetujuan orang tua, dan fitur pembelian hanya untuk 18 tahun ke atas.

Yang ditemukan saat pengecekan 14 November 2026: PP 17/2025 (PP Tunas) mengatur verifikasi usia dan persetujuan orang tua di layanan digital, dengan mekanisme yang disesuaikan tingkat risiko layanan. Data untuk verifikasi usia hanya boleh dipakai untuk itu dan dihapus setelah selesai, dan profiling anak dilarang. Sumber-sumber berita menyebut kelompok usia dan ambang yang berbeda-beda, jadi rinciannya [PERLU DICEK ke naskah resmi oleh ahli hukum].

| Tahap | Usulan | Catatan |
|---|---|---|
| Chat dan riset | Pernyataan usia saat pertama masuk. Kalau di bawah 18 tahun: layar persetujuan orang tua atau wali | Cara membuktikan persetujuan orang tua [CEK HUKUM]. Usulan paling ringan: tautan persetujuan dikirim ke email orang tua |
| Kontrol laptop | Hanya 18 tahun ke atas sampai ada jawaban ahli hukum | |
| Pembelian | Hanya 18 tahun ke atas. Pernyataan usia ditambah satu cara verifikasi | Pilihan cara verifikasi di bawah |

Cara verifikasi 18 tahun ke atas untuk pembelian:

| Cara | Data yang diambil | Kekuatan | Catatan |
|---|---|---|---|
| Pernyataan sendiri dengan tanggal lahir | Tanggal lahir | Lemah | Paling sedikit data, mudah dibohongi |
| Email kampus yang sudah terverifikasi | Tidak ada data baru | Sedang | Mahasiswa umumnya 17 tahun ke atas, jadi tidak membuktikan 18 |
| Pembayaran paket dengan metode yang mensyaratkan usia dewasa | Tidak ada data baru | Sedang | [PERLU DICEK apakah bisa diandalkan] |
| Verifikasi identitas lewat pihak ketiga | Data KTP diproses pihak ketiga | Kuat | Mahal, banyak data, perlu DPA [PERLU DICEK biaya] |

Usulan: mulai dengan pernyataan tanggal lahir dan batas belanja bawaan yang rendah, lalu naik ke cara yang lebih kuat kalau ahli hukum memintanya. Yang disimpan hanya hasil "18+ ya atau tidak" dan tanggal pemeriksaan.

Untuk pengguna di bawah 18 tahun: tidak ada statistik pemakaian, tidak ada email pemasaran, dan tidak ada profil perilaku.

## 6. Audit pihak ketiga

Status vendor yang sudah dipakai diambil dari `docs/LEGAL.md` bagian 3 (pemeriksaan 1 November 2026).

### Vendor sekarang

| Vendor | Data yang dibagikan | Lokasi server | Status DPA | Catatan untuk agent |
|---|---|---|---|---|
| Google (login) | Permintaan login. Ciel menerima nama, email, foto | Amerika Serikat | Kebijakan Google, tanpa DPA terpisah | Tidak berubah |
| DeepSeek | Isi pesan, foto untuk Edit AI | Tiongkok | Belum ada. Opt-out pelatihan belum dikirim | Jangan dipakai untuk isi halaman atau layar pengguna sebelum opt-out dikonfirmasi tertulis (D2) |
| Google (Gemini API, berbayar) | Isi pesan saat DeepSeek gagal, foto | Amerika Serikat | Berlaku otomatis selama billing aktif | Kandidat untuk agent |
| Exa | Kueri pencarian | Amerika Serikat | Hanya di paket Enterprise | Kueri agent bisa memuat nama barang yang dicari pengguna |
| Supabase | Riwayat chat, proyek, profil, status paket, persetujuan | Jepang (Tokyo) | Belum ditandatangani | Akan memuat tugas, log, dan batas belanja. Tandatangani DPA sebelum agent rilis |
| Streamlit Community Cloud | Semua yang lewat tampilan aplikasi | Amerika Serikat | Syaratnya hanya untuk pemakaian non-komersial | Risiko terbesar yang sudah tercatat. Lihat D6 |
| ngrok | Lalu lintas ke backend | Amerika Serikat | Berlaku lewat ToS | Hilang setelah pindah ke VPS |
| Mayar | Nama, email, nominal order | Indonesia | Perjanjian merchant, salinan belum disimpan | Tidak berubah |
| Google Fonts | Alamat IP pengunjung | Amerika Serikat | Kebijakan Google | Dihilangkan dengan membundel huruf sendiri |
| GitHub Pages | Alamat IP pengunjung halaman depan | Amerika Serikat | Kebijakan GitHub | Tidak berubah |

### Vendor baru yang mungkin dipakai

| Vendor | Data yang dibagikan | Lokasi server | Status DPA |
|---|---|---|---|
| Penyedia LLM untuk agent (D2): Anthropic, Claude Haiku 5.5 | Teks halaman, struktur aplikasi, tangkapan layar kalau diizinkan | [PERLU DICEK lokasi pemrosesan] | DPA otomatis menjadi bagian dari Commercial Terms. Tidak boleh melatih model dengan konten pelanggan. Input dan output dihapus dalam 30 hari |
| Penyedia VPS (D6) | Semua data backend | [ISI: pilih lokasi Indonesia atau Singapura] | [PERLU DICEK] |
| Cloudflare R2 (cadangan, dari rencana VPS) | Cadangan terenkripsi | [PERLU DICEK] | [PERLU DICEK] |
| Chrome Web Store | Data pemasangan ekstensi dikelola Google | Amerika Serikat | Perjanjian developer |
| Apple (notarisasi, kalau macOS dirilis) | Berkas aplikasi | Amerika Serikat | Perjanjian developer |
| Layanan email (verifikasi kampus, pengingat) | Alamat email | [PERLU DICEK] | [PERLU DICEK] |
| Layanan pemantau galat (kalau dipakai) | Catatan galat tanpa isi pesan | [PERLU DICEK] | [PERLU DICEK] |
| Analitik | Tidak direncanakan | | |

Marketplace dan toko tidak menerima data dari Ciel. Pengguna berinteraksi dengan mereka lewat browsernya sendiri.

Aturan menambah vendor: masuk tabel ini dulu, DPA atau syarat datanya dicek, halaman Privasi diperbarui, dan `terms.LEGAL_VERSION` dinaikkan kalau perubahannya material. Urutan ini sudah dipakai saat Gemini ditambahkan sebagai model cadangan.

## 7. Pekerjaan yang muncul dari audit ini

1. Kirim permintaan opt-out pelatihan ke DeepSeek dan tandatangani DPA Supabase (keduanya sudah tercatat belum selesai di `docs/LEGAL.md`).
2. Buat tabel `consent_events` dan catat penarikan persetujuan.
3. Tambah pemberitahuan privasi untuk pengguna tanpa login.
4. Tambah keterangan DeepSeek di dialog Edit AI.
5. Putuskan bawaan memori jangka panjang (nyala atau mati).
6. Minta ahli hukum memeriksa: persetujuan orang tua, verifikasi usia, pemrosesan isi layar di luar negeri, dan apakah perlu penilaian dampak pelindungan data untuk fitur agent.

## 8. Sumber yang dicek (14 November 2026)

- Ketentuan verifikasi pengguna anak di PP Tunas: https://teknologi.bisnis.com/read/20260505/84/1971467/pse-simak-ini-ketentuan-verifikasi-pengguna-anak-di-pp-tunas
- PP Tunas, verifikasi usia dan batas profiling: https://industri.kontan.co.id/news/pp-tunas-berlaku-platform-digital-wajib-verifikasi-usia-dan-batasi-profiling-anak
- Pembaruan kebijakan data pengguna Chrome Web Store 2026: https://developer.chrome.com/blog/cws-policy-updates-2026
