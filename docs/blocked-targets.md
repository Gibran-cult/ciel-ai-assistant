# Situs yang selalu diblokir untuk agent

Daftar di `guard/blocked_targets.json` (`host_suffixes`). Agent tidak pernah membuka, membaca, atau mengisi situs ini dan semua subdomainnya, apa pun izin pengguna (keputusan D9 dan D21 opsi B). Ekstensi memakai daftar yang sama lewat `extension/src/shared/vectors/blocked.json`.

Setiap entri diperiksa dari situsnya sendiri, tanpa login dan tanpa data pengguna:

- **skrip:** `tools/check_blocked_domains.py` membuka beranda dan menemukan nama merek di judul halaman, tanda meta situs, atau teks halaman.
- **browser:** situs yang judulnya baru muncul setelah JavaScript berjalan, atau yang menolak permintaan skrip, dibuka di browser dan judulnya dibaca setelah halaman selesai dirender.

`uob.co.id` tanpa `www` memakai sertifikat untuk alamat lain; situs resminya ada di `www.uob.co.id`, yang tercakup entri ini. `kredivo.com` mengalihkan ke `kredivo.id`, jadi keduanya masuk.

Yang tidak bisa diblokir lewat domain: dompet digital yang ada di dalam marketplace atau aplikasi lain (ShopeePay di `shopee.co.id`, GoPay di aplikasi Gojek). Untuk itu berlaku D4: agent tidak pernah membayar, dan jenis aksi `pay` adalah R3.

Garis miring (/) di kolom judul menggantikan tanda | dari judul aslinya.

| Domain | Kategori | Merek | Alamat akhir | Judul halaman | Bukti | Dicek |
|---|---|---|---|---|---|---|
| `allobank.com` | Bank | Allo Bank | https://allobank.com/ | Allobank / All for One, One for All | skrip: judul | 2026-11-18 |
| `jago.com` | Bank | Bank Jago | https://www.jago.com/ | Jago - Sesuai Maumu | skrip: judul | 2026-11-18 |
| `bankmandiri.co.id` | Bank | Bank Mandiri | https://www.bankmandiri.co.id/ | Bank Mandiri - Terdepan, Terpercaya, Tumbuh Bersama Anda | skrip: judul | 2026-11-18 |
| `bankmega.com` | Bank | Bank Mega | https://bankmega.com/id/ | Bank Mega - Keuntungan Sepanjang Masa | skrip: judul | 2026-11-18 |
| `bankbsi.co.id` | Bank | Bank Syariah Indonesia | https://www.bankbsi.co.id/ | Halaman Utama / Bank Syariah Indonesia | browser: judul setelah dirender | 2026-11-18 |
| `bca.co.id` | Bank | BCA | https://www.bca.co.id/id/individu | BCA - Senantiasa di sisi Anda | skrip: judul | 2026-11-18 |
| `klikbca.com` | Bank | BCA | https://www.klikbca.com/ | Internet Banking - KlikBCA | skrip: judul | 2026-11-18 |
| `bcadigital.co.id` | Bank | blu by BCA Digital | https://bcadigital.co.id/ | BCA Digital / Mulai Langkahmu | browser: judul setelah dirender | 2026-11-18 |
| `bni.co.id` | Bank | BNI | https://www.bni.co.id/en-us/ | Home / BNI | browser: judul setelah dirender | 2026-11-18 |
| `bri.co.id` | Bank | BRI | https://bri.co.id/web/guest | Home - Bank BRI / Melayani Dengan Setulus Hati | browser: judul setelah dirender | 2026-11-18 |
| `btn.co.id` | Bank | BTN | https://www.btn.co.id/id | PT Bank Tabungan Negara (Persero) Tbk / PT Bank Tabungan Negara (Persero) Tbk | browser: judul setelah dirender | 2026-11-18 |
| `cimbniaga.co.id` | Bank | CIMB Niaga | https://www.cimbniaga.co.id/id/home/welcome | CIMB Niaga - Layanan Perbankan Digital & Bisnis | skrip: judul | 2026-11-18 |
| `danamon.co.id` | Bank | Danamon | https://www.danamon.co.id/ | Bank Danamon - Tumbuh Bersama Danamon Group | skrip: judul | 2026-11-18 |
| `jenius.com` | Bank | Jenius | https://www.jenius.com/ | Jenius | skrip: judul | 2026-11-18 |
| `maybank.co.id` | Bank | Maybank Indonesia | https://www.maybank.co.id/ | Maybank Indonesia / Kemudahan Transaksi Finansial di Ujung Jari Anda | skrip: judul | 2026-11-18 |
| `ocbc.id` | Bank | OCBC Indonesia | https://www.ocbc.id/id | Terus Bersama Melaju Jauh / OCBC | skrip: judul | 2026-11-18 |
| `panin.co.id` | Bank | Panin Bank | https://www.panin.co.id/id | Individual / Panin Bank | skrip: judul | 2026-11-18 |
| `permatabank.com` | Bank | PermataBank | https://www.permatabank.com/ | Growing Together with Permata Bank | skrip: judul | 2026-11-18 |
| `seabank.co.id` | Bank | SeaBank | https://www.seabank.co.id/ | Simple, Untung, untuk Semua / PT Bank Seabank Indonesia | skrip: judul | 2026-11-18 |
| `uob.co.id` | Bank | UOB Indonesia | https://www.uob.co.id/personal/index.page | UOB Personal Banking / UOB Indonesia | browser: judul setelah dirender | 2026-11-18 |
| `dana.id` | Dompet digital | DANA | https://www.dana.id/ | DANA / Dompet Digital Terbaik #BUKANDOMPETBIASA | skrip: judul | 2026-11-18 |
| `gopay.co.id` | Dompet digital | GoPay | https://gopay.co.id/ | GoPay - Aplikasi Ringan untuk Transfer & Bayar | skrip: judul | 2026-11-18 |
| `linkaja.id` | Dompet digital | LinkAja | https://linkaja.id/ | Semua kebutuhan pembayaran, dalam satu aplikasi — LinkAja | skrip: judul | 2026-11-18 |
| `ovo.id` | Dompet digital | OVO | https://ovo.id/ | OVO / Join the rOVOlution in Payment, Points & Priority! | skrip: judul | 2026-11-18 |
| `1password.com` | Pengelola kata sandi | 1Password | https://1password.com/ | Password Manager, Secrets, and Access Management / 1Password | skrip: judul | 2026-11-18 |
| `bitwarden.com` | Pengelola kata sandi | Bitwarden | https://bitwarden.com/ | Best Password Manager for Business, Enterprise & Personal / Bitwarden / Bitwarden | skrip: judul | 2026-11-18 |
| `dashlane.com` | Pengelola kata sandi | Dashlane | https://www.dashlane.com/ | Dashlane: Password management & credential security platform | skrip: judul | 2026-11-18 |
| `passwords.google.com` | Pengelola kata sandi | Google Password Manager | https://passwords.google.com/ | Password Manager | browser: judul setelah dirender | 2026-11-18 |
| `keepersecurity.com` | Pengelola kata sandi | Keeper | https://www.keepersecurity.com/ | Keeper Security / Identity Security for Humans, Machines and AI Agents | skrip: judul | 2026-11-18 |
| `lastpass.com` | Pengelola kata sandi | LastPass | https://www.lastpass.com/ | #1 Password Manager with Shadow IT & AI Governance - LastPass | skrip: judul | 2026-11-18 |
| `nordpass.com` | Pengelola kata sandi | NordPass | https://nordpass.com/ | Securely Store, Manage & Autofill Passwords / NordPass | browser: judul setelah dirender | 2026-11-18 |
| `pass.proton.me` | Pengelola kata sandi | Proton Pass | https://pass.proton.me/ | Proton Pass Web App | skrip: judul | 2026-11-18 |
| `ajaib.co.id` | Investasi | Ajaib | https://ajaib.co.id/ | Aplikasi Investasi Online Terpercaya - Berizin Diawasi OJK | skrip: teks halaman | 2026-11-18 |
| `bibit.id` | Investasi | Bibit | https://bibit.id/ | Bibit - Investasi Reksa Dana, Obligasi Negara, & Saham | browser: judul setelah dirender | 2026-11-18 |
| `indodax.com` | Investasi | Indodax | https://indodax.com/ | Jual Beli Bitcoin dan Trading Kripto Indonesia - INDODAX | skrip: judul | 2026-11-18 |
| `pintu.co.id` | Investasi | Pintu | https://pintu.co.id/ | Pintu: Trading Crypto & Futures / Aplikasi Crypto All in One | skrip: judul | 2026-11-18 |
| `stockbit.com` | Investasi | Stockbit | https://stockbit.com/ | Stockbit - Investasi Saham Bersama Komunitas Saham Terbesar di Indonesia | browser: judul setelah dirender | 2026-11-18 |
| `tokocrypto.com` | Investasi | Tokocrypto | https://www.tokocrypto.com/ | Tokocrypto - Bursa Kripto yang Diawasi OJK | skrip: judul | 2026-11-18 |
| `akulaku.com` | Paylater dan pinjaman | Akulaku | https://www.akulaku.com/ | Belanja dengan Mudah: Pembayaran Cicilan dan Pinjaman Tunai / Teknologi Finansial Akulaku | skrip: judul | 2026-11-18 |
| `kredivo.com` | Paylater dan pinjaman | Kredivo | https://kredivo.id/ | Kredivo Paylater - Cicilan 0% hingga 24 Bulan - Kredivo | skrip: judul | 2026-11-18 |
| `kredivo.id` | Paylater dan pinjaman | Kredivo | https://kredivo.id/ | Kredivo Paylater - Cicilan 0% hingga 24 Bulan - Kredivo | skrip: judul | 2026-11-18 |

## Menambah entri

Tambahkan calon di `tools/check_blocked_domains.py`, jalankan skripnya, periksa yang gagal di browser, lalu tambahkan baris di sini dan domainnya di `guard/blocked_targets.json`. `tests/test_blocked_targets.py` memastikan keduanya sama dan tidak ada entri yang terlalu luas. Setelah itu buat ulang vektor ekstensi dengan `python tools/export_extension_vectors.py`.
