# Ringkasan rencana Ciel AI Agent

Tanggal: 14 November 2026. Semua dokumen di bawah adalah draf, dan belum ada kode yang ditulis. Keputusan D1 sampai D10 dijawab pemilik pada tanggal yang sama dan dicatat di [decisions.md](decisions.md).

## Tiga temuan yang mengubah rencana

1. Syarat layanan Shopee dan Tokopedia melarang akses dengan bot atau alat otomatis. Lazada, Blibli, dan TikTok Shop belum bisa dipastikan: syarat pembelinya tidak melarang akses otomatis secara umum, tetapi memuat larangan yang lebih sempit (mengambil isi situs, mengakses tanpa izin, mengakali pembatasan teknis) yang bisa mencakupnya. Jadi "agent checkout sampai selesai" di marketplace besar belum bisa dijalankan tanpa melanggar syarat mereka. Yang bisa: Ciel mencari dan memeriksa toko resmi, menyiapkan ringkasan, lalu kamu yang membayar.
2. Layanan tanda tangan kode termurah untuk Windows tidak menerima developer individu dari Indonesia. Ini alasan ekstensi browser diusulkan rilis lebih dulu daripada aplikasi desktop.
3. Isi layar pengguna jauh lebih sensitif daripada pertanyaan riset. DeepSeek bisa memakai data untuk melatih model, jadi agent diusulkan memakai penyedia lain yang punya komitmen tanpa pelatihan.

## Daftar dokumen

| No | Dokumen | Isi |
|---|---|---|
| 1 | [prd.md](prd.md) | Masalah, pengguna, persona, user story, prioritas fitur, metrik, risiko |
| 2 | [agent-architecture.md](agent-architecture.md) | Loop agent, tools, memori, model, ekstensi, desktop, sinkronisasi, diagram |
| 3 | [security.md](security.md) | Guardrail kontrol laptop dan pembelian, prompt injection, threat model, audit OWASP |
| 4 | [design-system.md](design-system.md) | Warna dengan rasio kontras terhitung, tipografi, komponen, antarmuka agent |
| 5 | [accessibility.md](accessibility.md) | Alt text, kontras, keyboard, fokus, pembaca layar, pemetaan WCAG 2.2 |
| 6 | [legal/](legal/) | Draf Privacy Policy, Terms of Service, Cookie Policy, Refund Policy, Kebijakan Penggunaan Agent |
| 7 | [privacy-consent.md](privacy-consent.md) | Banner cookie, audit consent, tabel minimalisasi data, verifikasi usia, audit vendor |
| 8 | [business-ethics.md](business-ethics.md) | Checklist dark pattern, aturan toko aplikasi, syarat layanan marketplace |
| 9 | [subscription-payments.md](subscription-payments.md) | Paket, diskon dan verifikasi mahasiswa, payment gateway |
| 10 | [infrastructure.md](infrastructure.md) | Hosting, rate limit, cache, monitoring, cadangan, perkiraan biaya |
| 11 | [cicd-quality.md](cicd-quality.md) | Pipeline, staging, strategi uji, red-team, rollback |
| 12 | [roadmap.md](roadmap.md) | Fase 0 sampai 7 dengan task, berkas, cara uji, kriteria selesai |
| Rencana | [plans/2026-11-14-agent-guardrail-core.md](plans/2026-11-14-agent-guardrail-core.md) | Rencana implementasi Fase 1, bisa dikerjakan tanpa menunggu keputusan |

## Keputusan pemilik

Semua dijawab mengikuti rekomendasi.

| ID | Keputusan | Jawaban (14 November 2026) | Rincian |
|---|---|---|---|
| D1 | Stack aplikasi desktop | Tauri 2, mulai dari Windows | agent-architecture.md bagian 5 |
| D2 | Penyedia LLM untuk agent | Dipisah menurut kepekaan data: chat tetap, agent di penyedia tanpa pelatihan. Dikunci 15 November 2026: Claude Haiku 5.5, cadangan Gemini 3.5 Flash-Lite | agent-architecture.md bagian 3 |
| D3 | Payment gateway langganan | Tetap Mayar sampai ada badan usaha | subscription-payments.md bagian 9 |
| D4 | Cara bayar agent | Opsi a: agent mengisi keranjang, kamu membayar sendiri | security.md bagian 4 |
| D5 | Daftar toko resmi awal | Cara verifikasi disetujui. Isi daftar masih menunggu pilihanmu: marketplace mana yang masuk dan 5 sampai 10 brand pertama | security.md bagian 4 |
| D6 | Hosting | Satu VPS, lalu tampilan dipindah dari Streamlit Cloud | infrastructure.md bagian 2 |
| D7 | Harga paket | Pro umum Rp129.000, isi sama untuk semua | subscription-payments.md bagian 3 |
| D8 | Diskon mahasiswa | Sekitar 39%, jadi harga mahasiswa tetap Rp79.000 | subscription-payments.md bagian 4 |
| D9 | Password manager dan m-banking | Blokir total dan serah terima ke kamu, lebih ketat dari "konfirmasi" | security.md bagian 2 |
| D10 | Urutan rilis | Ekstensi dulu, desktop menyusul | agent-architecture.md bagian 7 |

Harga di D7 dan D8 masih usulan dan dikonfirmasi ulang setelah biaya per tugas terukur di beta. Hal yang lebih kecil dan masih memakai usulan ada di decisions.md.

## Yang belum bisa dipastikan

Bagian bertanda [PERLU DICEK] belum terverifikasi dari sumber resmi, antara lain: syarat layanan Lazada, Blibli, dan TikTok Shop, harga resmi Gemini, syarat data Anthropic, harga sertifikat code signing, dan rincian PP Tunas. Semua draf legal wajib ditinjau ahli hukum. Perkiraan biaya di infrastructure.md dan subscription-payments.md adalah hitungan dari asumsi, belum data nyata.

## Langkah berikutnya

1. Isi D5: pilih marketplace yang masuk dan 5 sampai 10 brand pertama.
2. Fase 1 (inti guardrail) bisa mulai kapan saja karena tidak bergantung pada keputusan mana pun.
3. Fase 0 berisi urusan di luar kode yang paling lama: NIB, PSE, ahli hukum, pindah ke VPS.
