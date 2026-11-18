# Catatan keputusan Ciel AI Agent

Perbandingan opsi untuk setiap keputusan ada di dokumen yang dirujuk. Berkas ini hanya mencatat jawabannya.

## Keputusan pemilik

Dijawab pada 14 November 2026. Pemilik menyetujui semua rekomendasi.

| ID | Keputusan | Jawaban | Akibat langsung | Yang masih harus dicek |
|---|---|---|---|---|
| D1 | Stack aplikasi desktop | Tauri 2, dimulai dari Windows | Bagian desktop di roadmap Fase 5 dan `cicd-quality.md` ditulis untuk Tauri | Dicek 15 November 2026: MSIX lewat Microsoft Store (gratis, kemungkinan butuh akun perusahaan) atau sertifikat individu (mulai US$129 per tahun ditambah token). Masih dicek: syarat akun perusahaan tanpa badan hukum, dan dukungan MSIX di Tauri |
| D2 | Penyedia LLM untuk agent | Dipisah menurut kepekaan data: chat tetap seperti sekarang, agent memakai penyedia dengan komitmen tanpa pelatihan dan DPA | Isi halaman dan layar pengguna tidak dikirim ke DeepSeek | Dikunci 15 November 2026 (lihat riwayat di bawah) |
| D3 | Payment gateway langganan | Tetap Mayar sampai ada badan usaha | Tidak ada pekerjaan integrasi baru | Biaya admin platform Mayar dan dukungan tagihan berulang |
| D4 | Cara bayar agent | Opsi a: agent mengisi keranjang, pengguna membayar sendiri | Agent tidak pernah menyentuh data pembayaran. Jenis aksi `pay` masuk R3 | Dikaji ulang di Fase 7 setelah ada badan usaha |
| D5 | Daftar toko resmi awal | Cara verifikasi disetujui. Isi daftarnya belum dipilih | Semua entri di `guard/official_stores.json` tetap `approved: false` | Pemilik memilih marketplace yang masuk dan 5 sampai 10 brand pertama. Keadaan per 15 November 2026: Shopee dan Tokopedia melarang alat otomatis; Lazada tidak melarang secara eksplisit tetapi perlu pendapat ahli hukum; Blibli melarang pengambilan isi situs secara sistematis (butir 2.2) dan tidak menyebut akses otomatis secara umum; syarat pembeli TikTok Shop tidak menyebut bot, larangan bot ada di syarat kreator dan Syarat Layanan TikTok yang umum. Keduanya tetap `unknown` sampai halaman aslinya dicocokkan dan ada pendapat ahli hukum (roadmap 0.9) |
| D6 | Hosting | Opsi B dalam dua langkah: satu VPS untuk backend, lalu tampilan dipindah dari Streamlit Community Cloud | Rencana VPS 27 Oktober 2026 dijalankan lebih dulu | Harga VPS dengan RAM lebih besar, lokasi server |
| D7 | Harga paket | Opsi 2: Pro umum Rp129.000, isi paket sama untuk semua | `pricing.py`, website, dan `terms.LEGAL_VERSION` diubah di roadmap 4.20, tidak sekarang | Rp129.000 dan kuota 150 tugas per bulan masih usulan. Keduanya dikonfirmasi ulang setelah biaya per tugas terukur di beta |
| D8 | Diskon mahasiswa | Sekitar 39%, jadi harga mahasiswa tetap Rp79.000 | Mahasiswa yang sekarang tidak kena kenaikan | Ikut berubah kalau angka D7 berubah |
| D9 | Password manager dan m-banking | Blokir total dan serah terima ke pengguna | Lebih ketat dari "wajib konfirmasi" di brief awal. Aplikasi dan situs itu masuk R3 dan tidak bisa diizinkan pengguna | Daftar awal aplikasi dan situs yang diblokir dilengkapi pemilik (roadmap 0.15) |
| D10 | Urutan rilis | Ekstensi browser dulu, aplikasi desktop menyusul | Fase 3 dan 4 sebelum Fase 5 | Biaya daftar Chrome Web Store yang sekarang |

## Keputusan untuk layanan agent (rencana 2B dan 2C)

D11 sampai D13 dijawab pada 18 November 2026 sebelum [rencana 2B](plans/2026-11-18-agent-service.md) ditulis, D14 sampai D16 sebelum [rencana 2C](plans/2026-11-18-agent-web.md). Pemilik menyetujui semua rekomendasi.

| ID | Keputusan | Jawaban | Akibat langsung | Yang masih harus dicek |
|---|---|---|---|---|
| D11 | Tanda tangan tiket aksi | Ed25519: server menandatangani dengan kunci privat, ekstensi dan desktop memeriksa dengan kunci publik | Klien tidak menyimpan rahasia. Ekstensi yang dibobol tidak bisa memalsukan tiket untuk desktop. Paket `cryptography` masuk lockfile layanan | Versi Chrome minimum untuk Ed25519 di WebCrypto [PERLU DICEK] |
| D12 | Dependensi server | FastAPI dan Uvicorn, SDK resmi `anthropic` untuk Claude. Cadangan Gemini lewat HTTP biasa | Lockfile terpisah `requirements-agent.txt` | Daftar paket lengkapnya terlihat saat lockfile dibuat |
| D13 | Tempat login perangkat | Login Google di layanan agent sendiri, dengan PKCE antara perangkat dan layanan | Tidak bergantung pada Streamlit. Pemilik menambah redirect URI layanan di Google Cloud Console. ID pemilik dihitung sama persis dengan app | Tidak ada |
| D14 | Tempat rantai log diperiksa | Layanan agent di VPS memeriksa rantai log per tugas dan menyimpan hasilnya. Web hanya membaca hasil itu | `AGENT_CHAIN_KEY` tetap hanya di VPS, tidak masuk secrets Streamlit | Tidak ada |
| D15 | Tempat persetujuan aktivasi agent | Di web, Pengaturan > Agent, tercatat di `consent_events`. Layanan menolak login perangkat sebelum ada persetujuan. Menarik persetujuan mencabut semua perangkat | Teks persetujuan masih draf | Teks persetujuan ditinjau ahli hukum [PERLU DICEK] |
| D16 | Tempat halaman log | Tab "Agent" di dialog Pengaturan: Aktivitas, Perangkat, serta Persetujuan dan masa simpan. Hanya untuk akun yang login | Tampilan baris log dibuat bisa dibuka-tutup supaya muat di ponsel | Cek tampilan oleh pemilik di browser |

## Yang belum diputuskan dan memakai usulan sampai diubah

Angka dan pilihan ini ditulis sebagai usulan di dokumen masing-masing. Pemilik belum memutuskannya satu per satu.

| Hal | Usulan yang dipakai | Dokumen |
|---|---|---|
| Masa simpan log aktivitas | 90 hari, bawaan 30 hari di Pengaturan | `privacy-consent.md` bagian 3 dan 4 |
| Batas langkah dan waktu per tugas | 40 langkah, 15 menit | `agent-architecture.md` bagian 2 |
| Plafon belanja sistem selama beta | Belum ada angka | `security.md` bagian 4 |
| Cara verifikasi mahasiswa | Email kampus `.ac.id`, foto kartu hanya sebagai cadangan, cek ulang tiap 12 bulan | `subscription-payments.md` bagian 5 |
| Perpanjangan otomatis | Tetap sekali bayar | `subscription-payments.md` bagian 7 |
| Bawaan memori jangka panjang | Mati sampai dinyalakan (sekarang aktif otomatis setelah login) | `privacy-consent.md` bagian 4 |
| Cara verifikasi usia 18 tahun ke atas | Pernyataan tanggal lahir, menunggu ahli hukum | `privacy-consent.md` bagian 5 |
| Batas ganti rugi kalau agent salah | Belum ada angka, menunggu ahli hukum | `legal/agent-usage-policy.md` bagian 6 |
| Pintasan stop | `Ctrl+Shift+F12` di desktop, `Alt+Shift+S` di ekstensi | `security.md` bagian 3 |

## Riwayat keputusan lanjutan

| Tanggal | ID | Keputusan | Dasar |
|---|---|---|---|
| 15 November 2026 | D2 | Model utama agent: Claude Haiku 5.5 (`claude-haiku-5-5`), untuk langkah teks dan langkah yang butuh tangkapan layar. Cadangan saat Anthropic gagal: Gemini 3.5 Flash-Lite berbayar. Langkah yang sering gagal di beta dinaikkan ke Claude Sonnet 5.5 | Anthropic tidak boleh melatih model dengan konten pelanggan, menghapus input dan output API dalam 30 hari, dan DPA-nya otomatis berlaku. Haiku 5.5 mendukung tool computer use resmi dan paling murah di perbandingan (`agent-architecture.md` bagian 3) |

Sebelum agent dirilis, Anthropic harus masuk daftar pihak ketiga di halaman Privasi (`privacy.SUBPROCESSORS`) dan `terms.LEGAL_VERSION` dinaikkan, mengikuti urutan yang dipakai saat Gemini ditambahkan.

## Cara mengubah keputusan

Tambah baris baru di bawah tabel dengan tanggal dan alasannya, lalu perbarui dokumen yang terdampak. Baris lama tidak dihapus.
