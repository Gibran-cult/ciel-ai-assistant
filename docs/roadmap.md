# Roadmap Ciel AI Agent

Status: draf untuk ditinjau pemilik. Tanggal: 14 November 2026.

Urutan disusun dari yang paling krusial. Keamanan agent dan legal selesai sebelum fitur yang menyentuh uang atau laptop dibuka. Roadmap ini tidak memuat tanggal, karena kecepatannya bergantung pada urusan di luar kode (NIB, PSE, ahli hukum). Keputusan D1 sampai D10 sudah dijawab pada 14 November 2026 dan dicatat di [decisions.md](decisions.md).

Cara membaca:

- Setiap task dirancang selesai dalam 2 sampai 5 menit kerja, kecuali yang bertanda "tugas pemilik", yang lamanya di luar kendali.
- Fase 1 punya rencana implementasi rinci yang bisa langsung dikerjakan: [plans/2026-11-14-agent-guardrail-core.md](plans/2026-11-14-agent-guardrail-core.md).
- Fase 2 ke atas mengikuti keputusan pemilik. Tiap fase mendapat rencana implementasi rinci sendiri di `docs/plans/` sebelum dikerjakan.
- Nama berkas di Fase 2 ke atas adalah usulan.

## Ringkasan fase

| Fase | Isi | Bergantung pada | Yang dibuka ke pengguna |
|---|---|---|---|
| 0 | Keputusan dan fondasi | Pemilik | Belum ada |
| 1 | Inti guardrail | Tidak ada. Bisa mulai sekarang | Belum ada |
| 2 | Ciel Agent API, perangkat, log aktivitas | Fase 0 (VPS, D2, D6), Fase 1 | Halaman log dan izin di web |
| 3 | Ekstensi browser tanpa pembelian | Fase 2, D10 | Beta tertutup |
| 4 | Bantuan pembelian di toko resmi | Fase 3, D4, D5, D9, tinjauan hukum, NIB dan PSE | Beta, lalu publik |
| 5 | Aplikasi desktop Windows | Fase 2, D1, jalur code signing | Beta |
| 6 | macOS, tugas terjadwal, skala 1.000 pengguna | Fase 5 | Publik |
| 7 | Skala 10.000 pengguna dan opsi lanjutan | Fase 6, badan usaha | Publik |

## Fase 0: keputusan dan fondasi

Tujuan: semua hal yang menahan pekerjaan lain selesai atau punya jawaban.

| No | Task | Berkas | Cara mengecek |
|---|---|---|---|
| 0.1 | Selesai 14 November 2026: D1 sampai D10 dijawab. Sisa tugas pemilik: isi D5 (marketplace dan brand pertama) | `docs/decisions.md` | Baris D5 di `docs/decisions.md` memuat daftar yang dipilih |
| 0.2 | Isi `OPERATOR_NAME` dan `CONTACT_URL` di secrets | Secrets Streamlit | Halaman Privasi dan Ketentuan menampilkan nama dan kontak |
| 0.3 | Kirim permintaan opt-out pelatihan ke DeepSeek | `docs/LEGAL.md` bagian 3 | Balasan tersimpan dan kotak dicentang |
| 0.4 | Minta dan tandatangani DPA Supabase | `docs/LEGAL.md` bagian 3 | Kotak dicentang |
| 0.5 | Simpan salinan perjanjian merchant Mayar | `docs/LEGAL.md` bagian 3 | Kotak dicentang |
| 0.6 | Tugas pemilik: urus NIB lewat OSS | `docs/LEGAL.md` bagian 2 | Nomor dan tanggal tercatat |
| 0.7 | Tugas pemilik: daftar PSE Lingkup Privat | `docs/LEGAL.md` bagian 2 | Nomor tanda daftar tercatat |
| 0.8 | Jalankan rencana VPS yang sudah ada | `docs/superpowers/plans/2026-10-27-ciel-foundation-vps.md` | Kriteria selesai di rencana itu |
| 0.9 | Sebagian selesai 15 November 2026: Lazada terbaca penuh, label resmi Tokopedia, Lazada, dan Blibli tercatat. Ringkasan syarat Blibli, Tokopedia, dan TikTok Shop dari hasil penelusuran yang ditempel pemilik sudah dicatat pada tanggal yang sama. Sisa tugas pemilik: cocokkan ringkasan itu dengan halaman yang tampil di akun sendiri, terutama syarat pembeli TikTok Shop versi Indonesia | `docs/business-ethics.md` bagian 7, `docs/security.md` bagian 4 | Status Lazada, Blibli, dan TikTok Shop diputuskan bersama ahli hukum, lalu dicatat di `guard/official_stores.json` |
| 0.10 | Selesai 15 November 2026: syarat data Anthropic, dukungan computer use di Claude Haiku 5.5, dan harga resmi Gemini sudah dicek. Penyedia dikunci pemilik: Claude Haiku 5.5, cadangan Gemini 3.5 Flash-Lite | `docs/agent-architecture.md` bagian 3 | Tercatat di `docs/decisions.md` |
| 0.11 | Selesai 15 November 2026: dua jalur tercatat dengan harga, yaitu MSIX lewat Microsoft Store dan sertifikat individu | `docs/agent-architecture.md` bagian 5, `docs/cicd-quality.md` bagian 5 | Sisa sebelum Fase 5: syarat akun perusahaan Microsoft tanpa badan hukum, dan dukungan MSIX di Tauri |
| 0.12 | Tugas pemilik: konsultasi ahli hukum dengan lima draf di `docs/legal/` dan daftar pertanyaan | `docs/legal/agent-usage-policy.md` bagian 10 | Catatan jawaban tersimpan, draf direvisi |
| 0.13 | Tugas pemilik: wawancara 8 sampai 10 calon pengguna | `docs/prd.md` bagian "Fakta dan asumsi" | Asumsi A1 sampai A4 diberi status terbukti atau tidak |
| 0.14 | Buat `docs/asset-licenses.md` dengan aset yang sekarang dipakai | `docs/asset-licenses.md` | Setiap gambar dan huruf punya baris lisensi |
| 0.15 | Isi daftar awal aplikasi dan situs yang selalu ditolak (perbankan, dompet digital, password manager) | `guard/blocked_targets.json` | Setiap entri punya sumber yang dicek |

Kriteria selesai: D1 sampai D10 terjawab, backend berjalan di VPS dengan cadangan dan peringatan, vendor yang dipakai punya status DPA yang jelas, dan ahli hukum sudah melihat draf legal.

## Fase 1: inti guardrail

Tujuan: mesin kebijakan sebagai kode murni yang teruji, sebelum ada satu pun aksi agent yang nyata. Tidak bergantung pada keputusan mana pun.

Rincian langkah, isi uji, dan tanda tangan fungsi ada di rencana implementasi. Ringkasannya:

| No | Task | Berkas | Cara mengecek |
|---|---|---|---|
| 1.1 | Pemeriksa alamat: normalisasi host, pencocokan persis, deteksi domain mirip | `guard/domains.py`, `tests/test_guard_domains.py` | `python -m unittest tests.test_guard_domains -v` |
| 1.2 | Daftar toko resmi dan pemuatnya, semua entri belum disetujui | `guard/registry.py`, `guard/official_stores.json`, `tests/test_guard_registry.py` | `python -m unittest tests.test_guard_registry -v` |
| 1.3 | Verifikasi toko dengan kode alasan | `guard/stores.py`, `tests/test_guard_stores.py` | `python -m unittest tests.test_guard_stores -v` |
| 1.4 | Tingkat risiko aksi R0 sampai R3 | `guard/risk.py`, `guard/blocked_targets.json`, `tests/test_guard_risk.py` | `python -m unittest tests.test_guard_risk -v` |
| 1.5 | Lingkup tugas dan pemeriksa jalur file | `guard/scope.py`, `tests/test_guard_scope.py` | `python -m unittest tests.test_guard_scope -v` |
| 1.6 | Batas belanja per transaksi dan per bulan | `guard/limits.py`, `tests/test_guard_limits.py` | `python -m unittest tests.test_guard_limits -v` |
| 1.7 | Ringkasan pembelian dan token konfirmasi sekali pakai | `guard/purchase.py`, `tests/test_guard_purchase.py` | `python -m unittest tests.test_guard_purchase -v` |
| 1.8 | Log aksi berantai hash dan tabel database | `guard/audit.py`, `docs/chat_store.sql`, `tests/test_guard_audit.py` | `python -m unittest tests.test_guard_audit -v` |
| 1.9 | Urutan keputusan: izinkan, konfirmasi, blokir, serah terima | `guard/decide.py`, `tests/test_guard_decide.py` | `python -m unittest tests.test_guard_decide -v` |
| 1.10 | Kumpulan red-team tanpa model | `tests/redteam/*.json`, `tests/test_guard_redteam.py` | `python -m unittest tests.test_guard_redteam -v` |

Kriteria selesai: semua uji lulus di CI, nol kasus red-team lolos, `guard/` tidak mengimpor Streamlit atau `app.py`, dan tidak ada dependensi baru.

## Fase 2: Ciel Agent API, perangkat, dan log aktivitas

Tujuan: server bisa menjalankan loop agent dengan klien tiruan, dan pengguna bisa melihat log serta mengatur izin di web. Belum ada kontrol browser atau laptop.

Fase ini dikerjakan dalam tiga rencana, supaya bagian yang tidak butuh server selesai lebih dulu:

| Rencana | Task | Status |
|---|---|---|
| 2A, inti loop sebagai pustaka `agent_api/` ([rencana](plans/2026-11-15-agent-loop-core.md)) | 2.3 (tabel `agent_tasks`), 2.4, 2.10 sampai 2.18 | Selesai 15 November 2026. Tanpa dependensi baru dan tanpa VPS |
| 2B, layanan, perangkat, tiket, WebSocket, adaptor model, kontainer | 2.1, 2.2, 2.3 (tabel `agent_devices`), 2.5 sampai 2.9, 2.23, 2.24 | Rencana ditulis 18 November 2026 ([rencana](plans/2026-11-18-agent-service.md)), keputusan D11 sampai D13 sudah dijawab. Task 1 sampai 9 tidak butuh VPS, Task 10 dijalankan di VPS paling akhir |
| 2C, halaman log, perangkat dan izin di Pengaturan, Hapus akun, `consent_events` | 2.19 sampai 2.22 | Belum ditulis. Perubahan UI, menunggu cek pemilik di browser |

Catatan dari 2A untuk 2B: tugas yang gagal ditutup barisnya tetap berstatus `running` dan mengunci akun dari tugas baru. Layanan butuh pembersih tugas macet. Syarat pembersih itu dan gerbang lain dari tinjauan cabang 2A ada di bagian "Gerbang untuk rencana 2B" di [rencana 2A](plans/2026-11-15-agent-loop-core.md).

| No | Task | Berkas | Cara mengecek |
|---|---|---|---|
| 2.1 | Kerangka layanan dengan endpoint `/healthz` | `agent_api/main.py`, `tests/test_agent_api_health.py` | Uji memanggil `/healthz` dan menerima 200 |
| 2.2 | Tambah dependensi server ke lockfile ber-hash | `requirements-agent.in`, `requirements-agent.txt` | `pip install --require-hashes` lulus di CI |
| 2.3 | Tabel `agent_devices` dan `agent_tasks` | `docs/chat_store.sql`, `tests/test_agent_store.py` | Uji memeriksa RLS aktif tanpa policy |
| 2.4 | Penyimpanan tugas: buat, baca, ubah status, selalu dengan filter pemilik | `agent_api/store.py`, `tests/test_agent_store.py` | Akun B tidak bisa membaca tugas akun A |
| 2.5 | Pendaftaran perangkat dengan PKCE | `agent_api/devices.py`, `tests/test_agent_devices.py` | Kode sekali pakai, token berumur 15 menit |
| 2.6 | Token pembaruan yang berganti, pencabutan saat token lama dipakai lagi | `agent_api/devices.py` | Uji pemakaian ulang token lama mencabut semua token perangkat |
| 2.7 | Endpoint daftar dan cabut perangkat | `agent_api/devices.py` | Perangkat yang dicabut ditolak di permintaan berikutnya |
| 2.8 | Tiket aksi bertanda tangan dengan nomor urut | `agent_api/tickets.py`, `tests/test_agent_tickets.py` | Tiket dengan nomor urut lama atau tanda tangan salah ditolak |
| 2.9 | Endpoint WebSocket dengan pemeriksaan asal dan token | `agent_api/ws.py`, `tests/test_agent_ws.py` | Sambungan tanpa token atau dari asal lain ditolak |
| 2.10 | Antarmuka model dengan model tiruan untuk uji | `agent_api/model.py`, `tests/test_agent_model.py` | Model tiruan mengembalikan aksi sesuai naskah uji |
| 2.11 | Amplop data untuk isi tidak tepercaya | `agent_api/envelope.py`, `tests/test_agent_envelope.py` | Isi halaman tidak pernah masuk saluran instruksi |
| 2.12 | Skema argumen setiap tool. Keluaran model diikat ke aksi guard oleh `agent_api.tools.bind` memakai fakta dari klien | `agent_api/tools.py`, `tests/test_agent_tools.py` | Argumen di luar skema ditolak sebelum sampai ke klien, dan aksi dengan kolom yang tidak dikenal diblokir |
| 2.13 | Loop agent: rencana, lingkup, satu aksi per putaran, `guard.decide` di setiap aksi | `agent_api/loop.py`, `tests/test_agent_loop.py` | Aksi R2 tidak dikirim tanpa konfirmasi, R3 tidak pernah dikirim |
| 2.14 | Batas langkah dan waktu per tugas | `agent_api/loop.py` | Tugas berhenti di langkah ke-41 |
| 2.15 | Stop di server: tugas dibatalkan dan aksi berikutnya ditolak | `agent_api/loop.py` | Uji stop di tengah tugas |
| 2.16 | Penulisan log ke `agent_actions` lewat `guard.audit`, memakai kunci rantai dari secrets server. Hash catatan terakhir disimpan per tugas di `agent_tasks` | `agent_api/store.py` | `verify_chain` dengan `key` dan `head` utuh setelah satu tugas, dan catatan terakhir yang dihapus ketahuan |
| 2.17 | Rate limit agent per akun dan per paket | `agent_api/limits.py`, `tests/test_agent_limits.py` | Tugas kedua yang bersamaan ditolak |
| 2.18 | Plafon biaya harian dan sakelar mati fitur agent | `agent_api/limits.py` | Tugas baru ditolak saat sakelar mati |
| 2.19 | Halaman log aktivitas di web | `agent_log.py`, `tests/test_agent_log_app.py` | Baris tampil dengan waktu, risiko, aksi, target, hasil |
| 2.20 | Pengaturan > Perangkat dan Izin agent di web | `account_settings.py`, `tests/test_settings_app.py` | Cabut perangkat dari web bekerja |
| 2.21 | Hapus akun ikut menghapus tabel agent | `chat_store.py`, `tests/test_chat_store.py` | Setelah hapus akun, tabel agent kosong untuk pemilik itu |
| 2.22 | Tabel `consent_events` dipakai untuk aktivasi agent dan penarikan | `chat_store.py`, `tests/test_consent_app.py` | Baris baru tercatat saat setuju dan saat menarik |
| 2.23 | Kontainer dan entri di `deploy/vps/docker-compose.yml`, subdomain di Caddy | `deploy/vps/` | `tests/test_vps_deploy.py` |
| 2.24 | Environment staging dengan kunci terpisah | `deploy/vps/`, `docs/cicd-quality.md` | Uji asap di staging lulus |

Kriteria selesai: klien tiruan di uji bisa menjalankan satu tugas dari awal sampai akhir. Uji akses silang antar akun lulus. Log berantai utuh. Pengguna bisa melihat log dan mencabut perangkat di web.

## Fase 3: ekstensi browser tanpa pembelian

Tujuan: agent bisa membaca halaman, mengisi form, dan mengelola tab di situs yang diizinkan, dengan stop, indikator, dan konfirmasi yang lengkap. Fitur pembelian belum ada.

| No | Task | Berkas | Cara mengecek |
|---|---|---|---|
| 3.1 | Kerangka ekstensi dan manifest dengan izin minimal | `extension/manifest.json`, `extension/tests/manifest.test.ts` | Uji menolak izin di luar daftar yang disetujui |
| 3.2 | Side panel dengan keadaan belum masuk, masuk, dan luring | `extension/src/panel/` | Uji komponen untuk ketiga keadaan |
| 3.3 | Login perangkat dengan PKCE | `extension/src/auth.ts` | Uji alur dengan server tiruan |
| 3.4 | Klien WebSocket dengan sambung ulang dan verifikasi tiket | `extension/src/socket.ts` | Tiket tidak sah ditolak di klien |
| 3.5 | Pembaca halaman: teks terlihat, kontrol bernomor, tanpa kolom kata sandi dan pembayaran | `extension/src/content/reader.ts` | Uji pada halaman contoh: kolom sensitif tidak ikut |
| 3.6 | Penyaring pola rahasia sebelum data dikirim | `extension/src/content/redact.ts` | Nomor kartu uji tidak keluar dari perangkat |
| 3.7 | Pelaksana aksi: klik, ketik, pilih, gulir berdasarkan nomor rujukan. Klik pada tombol keranjang, checkout, kirim, batal pesanan, atau unduh dilaporkan dengan `effect` | `extension/src/content/act.ts` | Uji pada halaman contoh: klik tombol keranjang membawa `effect: "cart_add"` |
| 3.8 | Permintaan izin situs saat dibutuhkan | `extension/src/permissions.ts` | Tanpa izin, aksi ditolak di klien |
| 3.9 | Pemeriksaan izin lokal sebelum setiap aksi | `extension/src/permissions.ts` | Aksi ke situs di luar izin tidak dijalankan |
| 3.10 | Banner "Tab ini sedang dikontrol Ciel" dan badge ikon | `extension/src/content/banner.ts` | Banner muncul dan hilang sesuai keadaan |
| 3.11 | Tombol Stop di panel dan banner, pintasan keyboard | `extension/src/stop.ts` | Stop mengosongkan antrean tanpa menunggu server |
| 3.12 | Jeda otomatis saat pengguna mengetik atau mengklik di tab yang dikontrol | `extension/src/content/takeover.ts` | Uji interaksi |
| 3.13 | Kartu rencana dengan pilihan mode | `extension/src/panel/Plan.tsx` | Mode bawaan "Tanya dulu" |
| 3.14 | Preview aksi dan sorotan elemen | `extension/src/panel/Preview.tsx` | Uji komponen |
| 3.15 | Dialog konfirmasi R2 dengan efek dari kode | `extension/src/panel/Confirm.tsx` | Fokus awal di "Batal", Escape membatalkan |
| 3.16 | Serah terima: pembacaan halaman mati sampai pengguna menekan "Lanjutkan" | `extension/src/handover.ts` | Selama serah terima tidak ada data halaman yang dikirim |
| 3.17 | Tampilan log aktivitas di panel | `extension/src/panel/Log.tsx` | Sama dengan log di web |
| 3.18 | Antrean log lokal saat luring | `extension/src/queue.ts` | Aksi terkirim setelah tersambung lagi |
| 3.19 | Tema terang dan gelap dari berkas token | `design/tokens.json`, `extension/src/theme.css` | Uji kontras token di CI |
| 3.20 | Uji aksesibilitas otomatis untuk panel dan dialog | `extension/tests/a11y.test.ts` | Nol temuan |
| 3.21 | Situs tiruan lokal dan uji ujung ke ujung | `extension/tests/e2e/` | Satu tugas isi form selesai di browser otomatis |
| 3.22 | Uji red-team dengan model terhadap halaman bersuntikan | `tests/redteam/`, workflow terjadwal | Nol aksi berbahaya dijalankan |
| 3.23 | Workflow CI ekstensi | `.github/workflows/extension.yml` | Lint, uji, audit, bangun |
| 3.24 | Halaman toko: deskripsi, tangkapan layar, kebijakan privasi, formulir praktik data | Chrome Web Store | Checklist `docs/business-ethics.md` bagian 6 |
| 3.25 | Terbitkan ke penguji | Chrome Web Store | Penguji bisa memasang |
| 3.26 | Aktifkan dokumen legal agent dan naikkan `LEGAL_VERSION` | `terms.py`, `privacy.py` | Pengguna diminta setuju lagi sekali |

Kriteria selesai: beta tertutup dengan [ISI: jumlah] penguji selama minimal dua minggu, nol insiden aksi tanpa persetujuan, uji keyboard dan pembaca layar lulus, dan dokumen legal agent sudah ditinjau ahli hukum.

## Fase 4: bantuan pembelian di toko resmi

Tujuan: Ciel menemukan barang di toko resmi, menunjukkan bukti, menyiapkan ringkasan, dan menyerahkan pembayaran ke pengguna. Syarat masuk fase ini: D4, D5, dan D9 terjawab, NIB dan PSE selesai, dan Kebijakan Penggunaan Agent sudah ditinjau ahli hukum.

| No | Task | Berkas | Cara mengecek |
|---|---|---|---|
| 4.1 | Tugas pemilik: setujui daftar toko awal | `guard/official_stores.json` | Entri yang disetujui bertanda `approved: true` lewat pull request |
| 4.2 | Verifikasi brand pertama dengan dua bukti | `guard/official_stores.json` | Uji registry menolak entri brand dengan kurang dari dua bukti |
| 4.3 | Adapter toko pertama: penanda label di halaman produk dan di halaman toko, alamat halaman toko, nama toko, elemen keranjang | `extension/src/adapters/` | Uji pada halaman tiruan dengan dan tanpa label |
| 4.4 | Pengiriman bukti toko ke server dan pemanggilan `guard.verify_store` | `agent_api/shopping.py`, `tests/test_agent_shopping.py` | Setiap kode alasan punya uji |
| 4.5 | Pembaca ringkasan pesanan: barang, jumlah, harga, ongkir, biaya, total | `extension/src/adapters/` | Total sama dengan jumlah bagian pada halaman tiruan |
| 4.6 | Pernyataan usia dan aktivasi pembelian | `agent_shopping_settings.py`, `tests/test_agent_shopping_app.py` | Tanpa aktivasi, alasan `purchases_off` |
| 4.7 | Pengaturan batas belanja dengan login ulang untuk menaikkan | `agent_shopping_settings.py` | Menaikkan batas tanpa login ulang ditolak |
| 4.8 | Tabel `spend_limits` dan `purchase_confirmations` dipakai | `agent_api/store.py` | Nonce yang sudah dipakai ditolak |
| 4.9 | Dialog konfirmasi pembelian | `extension/src/panel/PurchaseConfirm.tsx` | Tombol setara, bukti toko tampil, hitung mundur diumumkan |
| 4.10 | Pesan toko ditolak dengan kalimat per kode alasan | `extension/src/panel/StoreRejected.tsx` | Setiap kode punya kalimat |
| 4.11 | Tawaran alternatif: cari barang yang sama di toko resmi | `agent_api/shopping.py` | Uji dengan model tiruan |
| 4.12 | Verifikasi ulang toko dan total tepat sebelum serah terima | `agent_api/shopping.py` | Perubahan harga membatalkan konfirmasi |
| 4.13 | Serah terima checkout dan pencatatan pesanan | `agent_api/shopping.py` | Agent tidak membuka halaman pembayaran |
| 4.14 | Mode pendamping untuk situs yang melarang alat otomatis, hanya kalau ahli hukum membolehkan | `extension/src/companion.ts` | Tidak ada klik atau ketik dari agent di situs itu |
| 4.15 | "Bantu batalkan" dan bahan keluhan | `agent_api/shopping.py` | Uji alur |
| 4.16 | Situs toko palsu tiruan dan uji ujung ke ujung | `extension/tests/e2e/fake-stores/` | Semua ditolak dengan alasan yang benar |
| 4.17 | Pemantauan `badge_unverifiable` per marketplace | `agent_api/metrics.py` | Peringatan muncul saat melonjak |
| 4.18 | Halaman bantuan "Cara Ciel memeriksa toko resmi" | Website dan aplikasi | Isi sama dengan `docs/security.md` bagian 4 |
| 4.19 | Tugas pemilik: audit keamanan pihak luar | Laporan audit | Temuan tinggi sudah ditutup |
| 4.20 | Perbarui paket dan harga sesuai D7 dan D8 | `pricing.py`, website, `terms.py` | `tests/test_pricing.py` dan `tests/test_website.py` |
| 4.21 | Verifikasi mahasiswa lewat email kampus | `student.py`, `tests/test_student.py` | Hanya hash email yang tersimpan |

Kriteria selesai: nol pembelian yang disiapkan di toko tidak resmi selama beta, semua uji toko palsu lulus, audit pihak luar selesai, dan alur pembatalan pernah diuji dengan pesanan nyata oleh pemilik.

## Fase 5: aplikasi desktop Windows

Tujuan: agent bisa mengelola file di folder yang diizinkan dan mengoperasikan aplikasi yang diizinkan. Syarat masuk: D1 terjawab dan ada jalur code signing.

| No | Task | Berkas | Cara mengecek |
|---|---|---|---|
| 5.1 | Kerangka aplikasi dan daftar perintah yang dibuka ke tampilan | `desktop/` | Uji menolak perintah di luar daftar |
| 5.2 | Login perangkat, token di Windows Credential Manager | `desktop/src-tauri/src/auth.rs` | Token tidak ada di berkas biasa |
| 5.3 | Penyimpanan izin aplikasi dan folder, dengan daftar yang selalu ditolak | `desktop/src-tauri/src/permissions.rs` | Uji daftar tolak |
| 5.4 | Pemeriksa jalur dengan resolusi nyata (shortcut dan `..`) | `desktop/src-tauri/src/paths.rs` | Uji jalur keluar folder ditolak |
| 5.5 | Tool file: daftar, baca, tulis, pindah (selalu dengan jalur tujuan `dest`), buat folder | `desktop/src-tauri/src/files.rs` | Uji di folder sementara |
| 5.6 | Hapus ke Recycle Bin | `desktop/src-tauri/src/files.rs` | File bisa dikembalikan |
| 5.7 | Pembaca struktur aplikasi lewat UI Automation | `desktop/src-tauri/src/uia.rs` | Uji pada aplikasi contoh |
| 5.8 | Klik dan ketik berdasarkan nama kontrol | `desktop/src-tauri/src/uia.rs` | Uji pada aplikasi contoh |
| 5.9 | Pil status selalu di atas dan bingkai jendela yang dikontrol | `desktop/src/overlay/` | Uji tampilan di tema terang dan gelap |
| 5.10 | Ikon tray dengan menu Stop | `desktop/src-tauri/src/tray.rs` | Uji manual |
| 5.11 | Pintasan stop global | `desktop/src-tauri/src/hotkey.rs` | Stop bekerja saat jendela lain aktif |
| 5.12 | Jeda saat pengguna menggerakkan mouse atau mengetik | `desktop/src-tauri/src/takeover.rs` | Uji manual |
| 5.13 | Native messaging dengan ekstensi, tanpa port localhost | `desktop/src-tauri/src/native_msg.rs` | Asal di luar daftar ditolak |
| 5.14 | Dialog konfirmasi R2 dan serah terima | `desktop/src/` | Sama perilakunya dengan ekstensi |
| 5.15 | Pembaruan bertanda tangan dan versi minimum dari server | `desktop/src-tauri/tauri.conf.json` | Pembaruan dengan tanda tangan salah ditolak |
| 5.16 | Workflow CI desktop dengan tahap tanda tangan | `.github/workflows/desktop.yml` | Build bertanda tangan di runner Windows |
| 5.17 | Uji pembaca layar (Narrator atau NVDA) | `docs/accessibility.md` bagian 8 | Alur tugas, konfirmasi, dan stop bisa dipakai |
| 5.18 | Kanal beta | Server pembaruan | Penguji menerima pembaruan |

Kriteria selesai: beta dengan installer bertanda tangan, uji jalur dan izin lulus, stop bekerja saat luring, dan tidak ada data file yang tersimpan di server selain nama file di log.

## Fase 6: macOS, tugas terjadwal, skala 1.000 pengguna

Tujuan: jangkauan lebih luas dan infrastruktur yang tahan.

| No | Task | Berkas | Cara mengecek |
|---|---|---|---|
| 6.1 | Tugas pemilik: daftar Apple Developer Program | Akun Apple | Developer ID terbit |
| 6.2 | Pembaca struktur aplikasi lewat Accessibility API | `desktop/src-tauri/src/ax.rs` | Uji pada aplikasi contoh |
| 6.3 | Penjelasan sebelum izin Accessibility dan Screen Recording | `desktop/src/` | Uji manual |
| 6.4 | Build, tanda tangan, dan notarisasi di runner macOS | `.github/workflows/desktop.yml` | Aplikasi terbuka tanpa peringatan |
| 6.5 | Uji VoiceOver | `docs/accessibility.md` | Alur utama bisa dipakai |
| 6.6 | Tugas terjadwal dengan persetujuan rencana di awal dan R2 tetap menunggu | `agent_api/schedule.py` | Tugas terjadwal tidak menjalankan R2 tanpa pengguna |
| 6.7 | Pindahkan memori ke penyimpanan vektor berbasis server | `flow/components/`, `tools/` | Jumlah memori per pemilik sama sebelum dan sesudah |
| 6.8 | Redis untuk sesi dan rate limit | `deploy/vps/` | Batas bertahan setelah restart |
| 6.9 | Pindahkan tampilan dari Streamlit Community Cloud ke VPS | `deploy/vps/` | Aplikasi berjalan di domain Ciel tanpa Streamlit Cloud |
| 6.10 | Uji beban di staging | `tests/load/` | Sasaran latensi [ISI] tercapai |
| 6.11 | Halaman status layanan | Website | Menampilkan keadaan layanan |
| 6.12 | Halaman admin untuk pengembalian dana | `admin_refunds.py` | Menggantikan SQL manual |

Kriteria selesai: macOS dirilis dengan notarisasi, layanan tahan 1.000 pengguna aktif per hari di uji beban, dan tampilan tidak lagi bergantung pada layanan bersyarat non-komersial.

## Fase 7: skala 10.000 pengguna dan opsi lanjutan

Tujuan: siap untuk pertumbuhan besar. Syarat masuk: badan usaha sudah ada.

| No | Task | Cara mengecek |
|---|---|---|
| 7.1 | Load balancer dan node Agent API tambahan | Deploy bergilir tanpa tugas terputus |
| 7.2 | Pub/sub untuk aksi antar node | Uji dengan dua node |
| 7.3 | Database terkelola dengan replika baca | Uji pulih |
| 7.4 | Kaji ulang cara bayar agent (opsi b dan c di D4) bersama ahli hukum | Keputusan tertulis |
| 7.5 | Kaji izin tertulis atau kemitraan dengan marketplace | Jawaban tertulis dari marketplace |
| 7.6 | Kaji ulang payment gateway dengan badan usaha | Perbandingan dengan angka resmi |
| 7.7 | Paket Tim | Keputusan pemilik |
| 7.8 | Kaji frontend pengganti Streamlit | Dokumen keputusan |
| 7.9 | Audit keamanan tahunan | Laporan |

Kriteria selesai ditentukan saat fase ini direncanakan rinci.

## Yang sengaja tidak masuk roadmap

- Agent membayar sendiri. Menunggu D4 dan badan usaha.
- Otomatisasi di marketplace yang melarang alat otomatis.
- Aplikasi HP.
- Kontrol keyboard dan mouse lewat tangkapan layar (prioritas Could, dikaji setelah Fase 5).
