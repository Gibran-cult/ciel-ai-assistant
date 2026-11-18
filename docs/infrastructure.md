# Infrastruktur Ciel AI Agent

Status: draf untuk ditinjau pemilik. Tanggal: 14 November 2026.
Keputusan D6 (hosting) dijawab pemilik pada 14 November 2026: opsi B dalam dua langkah. Catatannya di [decisions.md](decisions.md). Rencana pindah backend ke VPS sudah ada di `docs/superpowers/plans/2026-10-27-ciel-foundation-vps.md` dan menjadi dasar dokumen ini.

## 1. Kondisi sekarang (fakta)

| Bagian | Sekarang | Masalah untuk agent |
|---|---|---|
| Tampilan aplikasi | Streamlit Community Cloud | Syaratnya hanya untuk pemakaian non-komersial (`docs/LEGAL.md`). Tidak bisa melayani WebSocket dari ekstensi dan desktop |
| Backend | Langflow di laptop pemilik (RAM 8 GB) lewat ngrok gratis | Mati kalau laptop mati. Tidak cukup untuk layanan baru |
| Database | Supabase (Tokyo) | Bisa dipakai terus |
| Memori | Chroma lokal, satu proses | Tidak aman dipakai banyak proses, jadi Langflow harus satu worker |
| Rate limit dan kuota | Di proses Streamlit, hilang saat reboot | Rencana VPS memindahkannya ke Supabase |
| Cadangan | Belum otomatis | Rencana VPS menambah restic ke Cloudflare R2 |
| Peringatan | GitHub Actions memeriksa backend | Rencana VPS menambah Healthchecks.io dan cek saldo DeepSeek |

Rencana VPS menyelesaikan sebagian besar kolom kanan dan belum dijalankan. Menjalankannya adalah syarat pertama sebelum pekerjaan agent di server dimulai.

## 2. Hosting (keputusan D6)

Yang perlu ditampung: Langflow, layanan baru Ciel Agent API, gateway, dan nantinya tampilan aplikasi.

| Opsi | Isi | Kelebihan | Kekurangan | Biaya |
|---|---|---|---|---|
| A. Satu VPS untuk backend, tampilan tetap di Streamlit Community Cloud | Jalankan rencana VPS, tambah Ciel Agent API di VPS yang sama | Paling cepat. Anggaran sudah disetujui pemilik | Risiko syarat non-komersial Streamlit tetap ada | Rp100 ribu sampai Rp250 ribu per bulan (anggaran yang disetujui di rencana VPS) |
| B. Satu VPS untuk backend dan tampilan (rekomendasi, dua langkah) | Langkah 1 sama dengan A. Langkah 2: Streamlit dijalankan sendiri di VPS | Menghilangkan risiko terbesar di daftar vendor. Satu tempat untuk dikelola | Butuh RAM lebih besar, pemilik mengurus pembaruan sendiri | VPS dengan RAM lebih besar [PERLU DICEK harga] |
| C. Platform terkelola (PaaS) | Agent API dan tampilan di PaaS, Langflow di VPS | Deploy dan sertifikat otomatis | Biaya lebih tinggi dan dua tempat untuk dikelola | [PERLU DICEK harga] |

Rekomendasi: B, dimulai dari langkah yang sama dengan A. Lokasi server Indonesia atau Singapura supaya dekat dengan pengguna [ISI: pilihan pemilik].

## 3. Susunan per skala

"Pengguna" di sini berarti pengguna aktif per hari.

| Bagian | 100 pengguna | 1.000 pengguna | 10.000 pengguna |
|---|---|---|---|
| Server aplikasi | 1 VPS: Caddy, nginx, Langflow, Agent API | 1 VPS lebih besar, atau 2 VPS (Langflow terpisah dari Agent API) | 3 atau lebih node Agent API di belakang load balancer, Langflow di node sendiri |
| Database | Supabase yang sekarang | Supabase paket berbayar [PERLU DICEK harga] | Postgres terkelola dengan replika baca |
| Memori (vector store) | Chroma lokal, satu worker | Pindah ke penyimpanan vektor berbasis server (pgvector di Postgres atau Chroma mode server) | Sama, dengan indeks per pemilik |
| Antrean dan sesi WebSocket | Di memori proses | Redis untuk sesi dan rate limit | Redis dengan pub/sub supaya aksi sampai ke node yang memegang koneksi klien |
| Tampilan | Streamlit | Streamlit di VPS | Kaji frontend yang lebih ringan dari Streamlit |
| Cadangan | restic harian ke R2 | Sama, ditambah cadangan database terjadwal | Sama, ditambah uji pulih bulanan otomatis |

Hambatan yang harus diselesaikan sebelum lebih dari satu node: Chroma `PersistentClient` tidak aman lintas proses (catatan di rencana VPS). Selama memori masih di Chroma lokal, Langflow tidak bisa digandakan.

## 4. Load balancing

- Sampai 1.000 pengguna: tidak perlu. Satu server dengan gateway di depannya.
- 10.000 pengguna: load balancer di depan node Agent API. Agent API dibuat tanpa keadaan di proses: keadaan tugas di Postgres, sesi dan rate limit di Redis. Koneksi WebSocket boleh jatuh ke node mana pun karena aksi dikirim lewat pub/sub.
- Pemeriksaan kesehatan: endpoint `/healthz` yang mengecek database dan Redis. Node yang gagal dikeluarkan dari putaran.
- Deploy bergilir: satu node dalam satu waktu. Klien menyambung ulang sendiri dan tugas berlanjut dari keadaan di database.
- Permintaan panjang: Riset Skripsi menunggu sampai 420 detik, jadi batas waktu proxy minimal 600 detik (sudah dicatat di rencana VPS).

## 5. Rate limiting

Nilai chat diambil dari `.streamlit/secrets.toml.example`. Nilai agent adalah usulan.

| Lapis | Batas | Nilai |
|---|---|---|
| Per IP di gateway | Permintaan per menit | 60 per menit (dari rencana VPS), 404 untuk jalur di luar daftar |
| Per pengguna, chat, tanpa login | Pesan per jam | 10 |
| Per pengguna, chat, login | Pesan per jam dan per hari | 60 dan 300 |
| Per pengguna, chat, Pro | Pesan per jam dan per hari | 150 dan 800 |
| Semua tamu | Per jam dan per hari | 60 dan 300 |
| Semua pengguna | Per hari | 1.500 |
| Per pengguna, agent | Tugas berjalan bersamaan | 1 (usulan) |
| Per pengguna, agent | Aksi per menit | 30 (usulan) |
| Per tugas | Langkah dan waktu | 40 langkah, 15 menit (usulan) |
| Per paket, agent | Tugas per bulan | Mengikuti D7 |
| Per pengguna, pembelian | Ringkasan pembelian per hari | 10 (usulan) |
| Per perangkat | Percobaan sambung per menit | 10 (usulan) |
| Plafon biaya | Belanja model per hari untuk semua pengguna | [ISI: plafon harian], agent berhenti menerima tugas baru kalau terlewati |

Aturan: batas diperiksa di server sebelum memanggil model. Hitungan disimpan di Postgres atau Redis supaya tidak hilang saat restart. Saat penyimpanan itu tidak terjangkau, pakai hitungan di proses, tidak pernah "tanpa batas" (aturan dari rencana VPS). Pesan batas terlewati menyebut kapan bisa mencoba lagi.

Catatan: selama tampilan masih di Streamlit Community Cloud, semua permintaan chat datang dari satu alamat IP, jadi batas per IP di gateway sebenarnya batas bersama. Ekstensi dan desktop menyambung langsung dari IP pengguna, jadi batas per IP di sana bekerja semestinya.

## 6. Caching

| Yang di-cache | Aturan |
|---|---|
| Jawaban chat umum | Tetap seperti `answer_cache.py`: hanya dari tamu, 1 hari, tidak menyimpan jawaban berisi tautan. Tidak diperluas ke agent |
| Prompt sistem dan definisi tool | Pakai prompt caching dari penyedia model kalau tersedia: awalan permintaan yang sama dihitung lebih murah. Susun permintaan supaya bagian yang tetap ada di depan |
| Daftar toko resmi | Dimuat ke memori saat layanan mulai, dimuat ulang saat berubah |
| Hasil verifikasi toko | Berlaku paling lama 10 menit dan selalu diulang tepat sebelum checkout diserahkan |
| Isi halaman dan struktur aplikasi | Tidak di-cache. Selalu dibaca segar |
| Status paket dan batas belanja | Cache pendek 60 detik untuk tampilan. Keputusan pembelian selalu membaca langsung dari database |
| Aset statis website | CDN, dengan nama berkas ber-hash |

Aksi agent dan keputusan kebijakan tidak pernah di-cache antar pengguna.

## 7. Reverse proxy dan CDN

- Caddy di depan untuk TLS dan sertifikat otomatis, lalu nginx untuk autentikasi dasar ke Langflow, daftar jalur yang diizinkan, dan batas per IP. Susunan ini sudah ada di `deploy/vps/`.
- Ciel Agent API mendapat subdomain sendiri di belakang Caddy, dengan jalur WebSocket.
- Header keamanan di gateway: HSTS, `X-Content-Type-Options`, kebijakan `frame-ancestors`, dan CORS yang hanya mengizinkan asal milik Ciel dan ID ekstensi.
- CDN untuk website statis tetap GitHub Pages. Kalau tampilan aplikasi pindah ke VPS, aset statisnya bisa lewat CDN.
- Proxy Cloudflare untuk backend: sekarang dimatikan (DNS saja) karena memutus respons di 100 detik. Untuk Agent API yang memakai WebSocket dan respons pendek, proxy Cloudflare bisa dinyalakan demi perlindungan DDoS [PERLU DICEK batas WebSocket di paket gratis].
- Langflow, Redis, dan Postgres tidak dibuka ke internet.

## 8. Monitoring

| Yang dipantau | Cara | Peringatan |
|---|---|---|
| Layanan hidup | Pemeriksaan `/healthz` dari luar setiap beberapa menit (GitHub Actions yang sudah ada dan Healthchecks.io dari rencana VPS) | Mati lebih dari 5 menit |
| Saldo penyedia model | Skrip `tools/check_deepseek_balance.py` yang sudah ada, ditambah penyedia agent | Saldo di bawah ambang |
| Biaya model per hari | Hitungan token per panggilan di log | Mendekati plafon harian |
| Latensi dan galat per endpoint | Metrik dari Agent API | Galat di atas ambang selama 10 menit |
| Guardrail | Jumlah blokir R3, penolakan toko, dan deteksi suntikan per jam | Lonjakan mendadak |
| Kegagalan adapter toko | Jumlah `badge_unverifiable` per marketplace | Naik tajam, tanda tampilan situs berubah |
| Cadangan | Ping setelah cadangan dan setelah uji pulih | Tidak ada ping pada jadwalnya |
| Sumber daya server | CPU, RAM, disk | Disk di atas 80% |

Peringatan dikirim ke email atau aplikasi pesan pemilik [ISI: saluran]. Halaman status sederhana untuk pengguna masuk prioritas Should.

## 9. Logging

- Log aplikasi: terstruktur (JSON), dengan Request ID, ID tugas, dan ID perangkat. Tidak memuat isi pesan, isi halaman, token, atau teks yang diketik.
- Log keamanan: `security_event` yang sudah ada, ditambah kejadian agent (blokir, konfirmasi ditolak, perangkat dicabut, token ditolak).
- Log aksi agent untuk pengguna ada di database (`agent_actions`) dan terpisah dari log aplikasi.
- Masa simpan log aplikasi: 30 hari (usulan). Log keamanan: 90 hari (usulan).
- Log disimpan di server dan ikut cadangan terenkripsi. Layanan log pihak ketiga hanya dipakai setelah masuk daftar vendor.
- Berkas log diputar harian dan yang lama dihapus sesuai masa simpan, supaya disk tidak penuh.

## 10. Cadangan dan pemulihan

Mengikuti rencana VPS dan `docs/BACKUP_AND_DISASTER_RECOVERY.md`:

- Cadangan harian terenkripsi dengan restic ke penyimpanan di luar server, dengan retensi 7 harian dan 4 mingguan.
- Yang dicadangkan: database Langflow, memori, dataset pribadi, dump Supabase, konfigurasi, dan daftar toko resmi.
- Tabel agent (`agent_tasks`, `agent_actions`, `spend_limits`, `consent_events`) ikut dump database.
- Uji pulih otomatis setiap bulan, dan uji manual sebelum setiap perubahan besar.
- Kata sandi cadangan disimpan pemilik di luar server.
- Data yang dihapus pengguna hilang dari cadangan dalam sekitar 5 minggu, sesuai retensi. Halaman Privasi menyebut angka yang sama.
- Sasaran pemulihan: kehilangan data paling banyak 24 jam, layanan kembali dalam 4 jam (usulan untuk satu orang pengelola).

## 11. Perkiraan biaya

Angka model di bawah adalah hitungan dari asumsi, belum data nyata. Harga server dan layanan lain belum dicek dan diberi tanda. Kurs asumsi Rp16.500 per US$ [PERLU DICEK].

Asumsi pemakaian:

- Chat: 6 pesan per pengguna aktif per hari, 3.000 token input dan 600 token output per pesan, memakai `deepseek-flash` harga jam sibuk (US$0,30 dan US$1,20 per 1 juta token). Biaya per pesan: 0,003 × 0,30 + 0,0006 × 1,20 = US$0,0016.
- Agent: 20% pengguna aktif menjalankan 3 tugas per hari dengan model teks murah (US$0,014 per tugas).
- 30 hari per bulan.

| Pos | 100 pengguna | 1.000 pengguna | 10.000 pengguna |
|---|---|---|---|
| Model untuk chat | sekitar US$29 (Rp480 ribu) | sekitar US$290 (Rp4,8 juta) | sekitar US$2.900 (Rp48 juta) |
| Model untuk agent | sekitar US$25 (Rp415 ribu) | sekitar US$250 (Rp4,2 juta) | sekitar US$2.500 (Rp42 juta) |
| Pencarian web (Exa) | [PERLU DICEK] | [PERLU DICEK] | [PERLU DICEK] |
| Server | Rp100 ribu sampai Rp250 ribu (anggaran rencana VPS) | [PERLU DICEK] | [PERLU DICEK] |
| Database | Paket gratis Supabase selama masih muat [PERLU DICEK batasnya] | [PERLU DICEK] | [PERLU DICEK] |
| Redis | Tidak perlu | Di VPS yang sama | [PERLU DICEK] |
| Cadangan (R2) | [PERLU DICEK] | [PERLU DICEK] | [PERLU DICEK] |
| Biaya pembayaran | 0,7% sampai 1,5% dari omzet, atau Rp4.000 per order virtual account | Sama | Sama |
| Apple Developer Program (kalau macOS dirilis) | US$99 per tahun | Sama | Sama |
| Chrome Web Store | Sekali bayar, US$5 [PERLU DICEK] | | |
| Sertifikat code signing Windows | Gratis lewat Microsoft Store (MSIX, kemungkinan butuh akun perusahaan). Di luar Store: US$129 per tahun (SSL.com IV) ditambah token US$379 atau langganan cloud, atau mulai €139 (Certum Standard) | Sama | Sama |
| Domain | [ISI: biaya perpanjangan ciel-ai.web.id] | Sama | Sama |

Rumus supaya bisa dihitung ulang dengan data nyata:

- Biaya chat per bulan = pengguna aktif × pesan per hari × 30 × biaya per pesan.
- Biaya agent per bulan = pengguna aktif × bagian yang memakai agent × tugas per hari × 30 × biaya per tugas.

Yang paling memengaruhi hasil: jumlah langkah per tugas, seberapa sering model computer use dipakai (sekitar 20 kali lebih mahal per tugas dari model teks murah), dan jumlah pesan per pengguna. Ketiganya harus diukur di beta sebelum harga paket dikunci.

## 12. Urutan pengerjaan

1. Jalankan rencana VPS yang sudah ada (backend, cadangan, peringatan, rate limit yang bertahan).
2. Tambah Ciel Agent API di VPS, subdomain, dan jalur WebSocket.
3. Pindahkan tampilan dari Streamlit Community Cloud ke VPS.
4. Sebelum 1.000 pengguna: pindahkan memori ke penyimpanan vektor berbasis server dan tambah Redis.
5. Sebelum 10.000 pengguna: load balancer, node tambahan, database terkelola.

## 13. Sumber

- Rencana VPS: `docs/superpowers/plans/2026-10-27-ciel-foundation-vps.md`
- Harga DeepSeek: https://api-docs.deepseek.com/quick_start/pricing
- Harga Claude: referensi model Anthropic (cache 3 November 2026)
- Harga Mayar: https://mayar.id/pricing
