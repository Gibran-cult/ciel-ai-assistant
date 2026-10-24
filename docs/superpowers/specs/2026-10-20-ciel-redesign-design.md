# Ciel redesign: tampilan baru, Beranda, chat tiga kolom, landing page

## Konteks

Ciel minta tampilan Ciel diubah mengikuti desain di artifact "Ciel AI: landing page dan aplikasi" (https://claude.ai/artifact/L46T2XDbYUwe8Zo8fNvwbK, 4 artboard: Landing page, Masuk, Beranda proyek, Chat riset). Salinan artboard yang dibaca sesi ini: `scratchpad/artifact-files/.../project/*.dc.html`. Builder membaca ulang artifact itu (Artifact tool, action `read`) untuk angka persis yang tidak ditulis di sini.

Ciel memilih cakupan penuh: gaya visual app, landing page terpisah, dan fitur baru (Beranda proyek, chat tiga kolom). Mockup yang disetujui ada di `.superpowers/brainstorm/1497-1792502262/content/` (`beranda-b-v2.html` untuk Beranda, `chat-layout.html` opsi A untuk chat).

Ciel adalah app Streamlit (`app.py`, ~4.500 baris) di Streamlit Community Cloud. Lokal Streamlit 1.54, Cloud 1.65. Identitas produk: teman riset yang anti-ngarang, untuk mahasiswa Indonesia, bahasa santai.

## Keputusan Ciel

1. **Cakupan:** semua, termasuk fitur baru.
2. **Tema:** terang dan gelap, **gelap jadi default**. Tombol bulan/matahari tetap ada.
3. **Beranda proyek:** versi B. Kotak tanya di tengah, template prompt sebagai tombol di bawahnya, lalu panel "Lanjutkan riset" dan "Yang Ciel ingat". Bukan dasbor angka seperti artboard.
4. **Template prompt:** kalimat lengkapnya masuk ke kotak tanya saat tombol diklik; mahasiswa mengganti bagian dalam kurung lalu kirim. Template bawaan dari Ciel saja.
5. **Halaman chat:** versi A, tiga kolom (sidebar, percakapan, panel kanan).
6. **Landing page:** halaman terpisah dengan link baru, di-hosting GitHub Pages dari repo ini. Ciel akan mulai membagikan link itu.
7. **Harga di landing:** Gratis dan Pro berdampingan.
8. **Cerita jurnal palsu:** dipakai, dengan jawaban asli Ciel dari uji 20 Oktober 2026 (lampiran A). Bukan teks karangan artboard.
11. **Teks landing:** semua klaim artboard yang tidak didukung app ditulis ulang supaya sesuai kenyataan, bukan hanya yang tercantum di bagian 7. Contohnya: kotak kuning hanya di mode analisis, tidak ada daftar "sumber yang lagi dibaca", ingatan per akun bukan per proyek, masuk tidak wajib, contoh jurnal palsu berlabel chat biasa dengan jumlah sumber asli. Ciel membaca teks final landing sebelum GitHub Pages dinyalakan.
10. **Urutan rilis:** dua tahap. (1) Seluruh redesign app (bagian 1–6 dan 8) dalam satu PR: satu cek browser oleh Ciel, "commit", merge. (2) Landing page (bagian 7) di PR kedua; GitHub Pages baru dinyalakan setelah app baru live di Cloud.
9. Semua gambaran per bagian (Beranda, chat, landing, Masuk/tema/gaya umum) dikonfirmasi Ciel "nggak ada yang salah", termasuk poin yang ditandai tebakan. Poin itu sekarang keputusan.

## Tujuan

- Ciel terlihat dan terasa seperti artboard: dasar hampir hitam, pill putih, aksen biru, kuning untuk yang belum ada sumbernya, Geist + Fraunces, bingkai ganda tipis, gerak "spring".
- Mahasiswa yang membuka proyek langsung tahu cara mulai: template prompt yang terhubung ke fitur nyata Ciel.
- Sumber di tiap chat bisa dicek dari satu tempat (panel kanan), tanpa scroll mencari blok "Sumber:".
- Orang yang belum kenal Ciel dapat halaman depan yang cepat dibuka dan jujur isinya.

## Non-goal

- Mengubah flow Langflow mana pun (utama v1.12.0, Riset Skripsi, Penulis, memory admin). Semua data panel kanan diambil dari teks jawaban yang sudah ada.
- Fitur tenggat, "Sumber tersimpan" per proyek, tombol "Simpan ke sumber proyek", angka-angka dasbor artboard Beranda.
- Template buatan pengguna.
- Tab saring "Semua / Riset Skripsi" di daftar chat, kotak cari Ctrl K, tombol "Ganti proyek" di bar atas (artboard Chat/Beranda). Sidebar sudah menangani pindah proyek.
- Paket Tim di landing, domain sendiri, halaman Syarat layanan.
- Mengubah perilaku fitur yang ada (rate limit, Pro gate, Midtrans, memory, riwayat, file proyek).

## Anti-goal (gagal walau secara teknis jalan)

- Landing page memuat klaim, angka, atau kutipan yang tidak terjadi. Termasuk "uji coba Oktober 2026" untuk hal yang tidak diuji, waktu riset yang tidak sesuai, atau dua penelitian "mirip" yang disebut Ciel di uji jurnal palsu (belum diverifikasi).
- Harga atau isi paket di landing berbeda dari `pricing.py`.
- Teks tak terbaca di salah satu tema, terutama di popover, dialog, state hover/disabled, dan Streamlit 1.65 (lihat Batasan).
- Fitur yang sekarang ada hilang atau rusak: arsip/hapus chat, file proyek, Data saya, Riset Skripsi/Kerangka/Cek kutipan, Coba lagi, Unduh DOCX/CSV, pricing/privasi, login.
- Template yang langsung terkirim tanpa memberi kesempatan mengisi bagian kurung.
- Panggilan Langflow/ngrok tambahan di setiap rerun (biaya dan kuota ngrok).
- Pola "AI slop": section template, kartu fitur generik, emoji, label campur Inggris/Indonesia, tagline berulang.

## Batasan

- **Streamlit 1.54 lokal, 1.65 di Cloud.** DOM berbeda (mis. `stTextInputRootElement`, segmented control `aria-checked`). Cek di keduanya; venv scratch 1.65 untuk verifikasi.
- **Popover, dialog, dan tooltip dirender di luar `.stApp`.** Aturan widget memakai `:is(.stApp, [data-testid="stPopoverBody"], [data-testid="stDialog"])` (pola yang sudah ada).
- **`st.html` membuang SVG inline**; `st.markdown(unsafe_allow_html=True)` mempertahankannya tetapi tidak menjalankan script. Ikon di HTML Streamlit: SVG lewat `st.markdown`, atau mask CSS (pola tombol tema).
- **Streamlit mewarnai ikon/SVG stroke dan teks disabled sendiri dari tema dasarnya.** Warna di wrapper tidak sampai; targetkan elemen yang benar-benar memegang warna (ukur dengan `getComputedStyle`).
- **`st.chat_input` 1.54 mendukung isi teks lewat `st.session_state[key]`** (lihat docstring `streamlit/elements/widgets/chat.py`, contoh "set the text of the chat input"), dan dirender inline bila dipanggil di dalam container. Pastikan juga di 1.65.
- **Satu `st.chat_input` per run.** Beranda dan chat memanggilnya di tempat berbeda, dengan key yang sama.
- **Kontrak di `tests/test_theme.py`** (paritas token terang/gelap, AA 4.5:1, selector popover/dialog/disabled, tombol tema, badge Cloud) harus tetap lolos atau diperbarui sengaja bersama perubahannya.
- **Budget kecil.** Uji/verifikasi yang memanggil DeepSeek seminimal mungkin; saldo prepaid habis = Ciel mati.
- **Alur kerja Ciel:** jangan commit sebelum Ciel cek sendiri di browser dan bilang "commit". Preview lokal tetap jalan dan linknya diberikan.
- Repo publik `Gibran-cult/ciel-ai-assistant`. GitHub Pages belum aktif; menyalakannya mengubah pengaturan repo dan **perlu konfirmasi Ciel saat itu**.

## Desain

### 1. Sistem visual

**Token.** Tetap memakai nama `--c-*` yang ada (CIEL_CSS + DARK_TOKENS), ditambah token baru di kedua tema:
- `--c-primary`, `--c-on-primary`: tombol utama (pill). Gelap `#f4f4f2` / `#141311`; terang `#161513` / `#f1f1ee`.
- `--c-gap-bg`: latar kotak "belum ada sumbernya". Gelap `#2b2716`; terang turunan kuning yang lolos AA dengan teksnya.

Nilai gelap dari artboard app: bg `#0e0d0c`, surface `#181715`, raised `#24231f`, raised-strong/active `#2a2926`, text `#f4f4f2`, muted `#b4b3ad`, faint `#959490`, accent `#9db3e8`, accent-ink `#141a2a`, gold `#e9d06a`, gold-ink `#2e2606`. Nilai terang dari artboard landing: bg `#f1f1ee`, raised `#e6e6e2`, text `#161513`, muted `#4b4a46`, accent (link) `#2b4886`, gold `#e9d06a`, gold-ink `#3d3209`. Token yang tidak disebut artboard (line, line-strong, control, faint terang, surface terang, ok/warn/err, mark-piece, shimmer, shadow) dipilih builder supaya lolos uji AA dan `--c-control` vs surface ≥ 3:1. `#4a4843` dari artboard untuk control **gagal** 3:1, jadi jangan dipakai untuk border input.

**Tema default gelap.** UI_JS: tanpa pilihan tersimpan, `data-ciel-theme` = `dark` (bukan lagi mengikuti `prefers-color-scheme`). Pilihan lewat tombol tetap disimpan di localStorage dan tetap berfungsi kalau storage diblokir. CSS: token gelap di `:root`, token terang di `:root[data-ciel-theme="light"]`. Hindari kilatan terang saat load: `.streamlit/config.toml` diganti ke `base = "dark"` dengan warna gelap yang sama. Komentar "Keep in step" diperbarui.

**Bentuk.** Tombol utama dan sekunder pill (radius 999px). Tombol ghost di sidebar/menu tetap radius 8px seperti artboard (`.navi`). Kartu/panel radius 16–17px di dalam "bingkai" tipis (padding 5px, radius 22px, `inset 0 0 0 1px rgba(255,255,255,0.055)`, pola `.bz-a`). Satu tingkat bingkai saja, tidak bersarang. Tombol pill dengan ikon panah bersarang (`.has-ic` + `.ic`) untuk aksi utama seperti di artboard.

**Tipe.** Geist untuk UI, Fraunces untuk wordmark "Ciel" dan sapaan Beranda. Ukuran dasar UI 14px/20px seperti artboard app. Teks jawaban 15px/24px.

**Gerak.** Easing `cubic-bezier(0.32,0.72,0,1)`. Animasi masuk halus untuk isi Beranda dan pesan baru. Tirai logo (`.curtain-a`) **hanya sekali per sesi browser** (flag sessionStorage), `pointer-events:none`, maksimal ~0,8 dtk. Semua gerak mati di `prefers-reduced-motion: reduce` (aturan yang ada).

### 2. Kerangka app: sidebar dan bar atas

Ikuti `chat-layout.html` opsi A dan artboard Chat:
- **Sidebar:** wordmark Ciel; "Chat baru" (pill primer); "Riset Skripsi" (atau "Riset Skripsi · Pro") tetap; "Proyek" berisi "Semua chat", daftar proyek, "Proyek baru" (popover yang ada), file proyek (expander yang ada); lalu "Chat di proyek ini" (atau "Riwayat" untuk Semua chat). Tiap baris chat: judul, waktu relatif (21.42 / Kemarin / Sen / 15 Okt, WIB), penanda "Riset" untuk chat Riset Skripsi, menu ⋯ (arsip/hapus) tetap. "Diarsipkan" tetap. Akun di bawah tetap (popover yang ada).
- **Bar atas:** crumb kiri ("Proyek · <nama>" atau "Semua chat"; di chat: nama chat dipindah ke header percakapan), tombol tema dan "Masuk" (kalau belum masuk) di kanan. Bar ikut-scroll yang ada (NAV_SCROLL_JS) dipertahankan.
- **HP:** sidebar Streamlit yang bisa dibuka/tutup dipakai sebagai menu. Hanya restyle, tanpa membuat drawer sendiri.

### 3. Beranda (pengganti halaman chat kosong)

Tampil saat tidak ada chat aktif dan tidak ada pesan yang sedang dikirim, di konteks proyek mana pun termasuk "Semua chat". Mockup: `beranda-b-v2.html`.

Dari atas, kolom tengah ±660px:
1. **Sapaan** Fraunces: "Pagi/Siang/Sore/Malam, <nama depan>." menurut jam WIB (Asia/Jakarta). Tanpa nama kalau belum masuk. Baris bawah: "<nama proyek> · N chat · M file proyek", atau "Semua chat · N chat".
2. **Kotak tanya:** `st.chat_input` yang sama (key tetap, lampiran file tetap), dirender inline di sini. Placeholder "Tanya soal skripsimu" di proyek, "Tanyakan sesuatu kepada Ciel..." di Semua chat. Setelah pesan pertama terkirim, halaman menjadi tampilan chat dan kotak tanya kembali ke bawah.
3. **Tombol template** (urutan tetap):
   - **Cari jurnal · Pro**: membuka dialog Riset Skripsi yang ada (`open_riset_dialog`). Tidak mengisi kotak tanya. Untuk akun gratis tetap tampil; dialognya sudah menjelaskan Pro.
   - **Jelasin konsep**: "Jelasin [konsep] pelan-pelan pakai contoh angka, lalu kasih 2 soal latihan."
   - **Analisis metode**: "Analisis: [metode] cocok nggak buat data [jenis data]-ku?"
   - **Cek referensi**: "Cek apakah referensi ini beneran ada: [tempel referensi]"
   - **Ringkas file proyek**: "Ringkas file proyek ini dan tandai klaim yang belum ada sumbernya." Hanya tampil kalau proyek aktif punya file.
   - **Kerangka Bab 1–3 · Pro**: membuka dialog Kerangka dari peta sumber terakhir di konteks ini. Di proyek: chat Riset Skripsi terbaru di proyek itu. Di "Semua chat": chat Riset Skripsi terbaru dari semua chat (termasuk yang tanpa proyek). Hanya tampil kalau chat seperti itu ada. Klik: chat itu dijadikan aktif lalu dialog dibuka dengan map_index peta terakhirnya (pola `open_kerangka_dialog`).
   - Tombol biasa mengisi kotak tanya lewat `st.session_state[<key chat_input>] = teks`, lalu kotak mendapat fokus. Teks persis seperti di atas; kurung tetap `[...]`. Kalau kotak sudah berisi teks, template menggantinya.
   - Kalau `RISET_ENABLED`/`WRITER_ENABLED` mati, tombol Pro terkait tidak tampil.
4. **Panel "Lanjutkan riset"**: 3 chat terbaru di konteks ini (judul + waktu), klik membuka chat. Disembunyikan kalau belum ada chat.
5. **Panel "Yang Ciel ingat"**: hanya kalau sudah masuk dan `MEMORY_ADMIN_FLOW_ID` ada. Isi dari `memory_admin("list")`, **dimuat sekali per sesi** (simpan di `st.session_state`, pakai `my_memories` yang sudah ada kalau terisi), maksimal 4 baris, teks + kategori kalau ada. Kalau gagal atau kosong, panel disembunyikan. Tidak memanggil ulang di tiap rerun.

Contoh jawaban mode analisis (SAMPLE_ANSWER_HTML) dan STARTER_PROMPTS lama dilepas dari halaman ini; template menggantikannya.

### 4. Halaman chat (tiga kolom)

Mockup: `chat-layout.html` opsi A, plus artboard Chat untuk detail.

- **Header percakapan:** judul chat (18px/600) dan ringkasan "N sumber · M belum ketemu" (bagian yang nol dihilangkan; kalau dua-duanya nol, cukup judul).
- **Pesan pengguna:** gelembung kanan, latar surface, radius 16px, maks 80% lebar. Lampiran/gambar tetap.
- **Jawaban Ciel:** logo kecil + "Ciel", teks 15px/24px, maks ±66ch. **Isi pesan yang tersimpan tidak pernah diubah** (report_docx, Kerangka di `writing.py`, dan Cek kutipan di `draft_check.py` membaca ulang isi itu). Semua perubahan di bawah hanya saat menampilkan:
  - label `[Terverifikasi]` dan `[Dugaan]` ditampilkan sebagai label kecil (pola `.ciel-label` yang ada; dugaan = kuning). Tidak ada kotak kuning yang membungkus poin di dalam jawaban.
  - blok "Sumber:" di akhir jawaban chat biasa dipindah dari teks ke deretan tombol sumber bernomor di bawah jawaban (nomor biru + domain + judul), bisa diklik, buka tab baru. Entri tanpa URL http(s) (file lampiran, knowledge base; Source Guard sengaja menyimpannya) dan catatan guard "(N sumber dihapus karena tidak ada di hasil pencarian.)" **tetap tampil sebagai teks** di bawah tombol.
  - "## Daftar Pustaka" (Riset Skripsi, lewat `flow/components/ciel_reference_builder.py`) dan "## Daftar Pustaka (dari peta sumber)" (Kerangka, `writing.py`) **tetap di teks jawaban apa adanya**, karena itu hasil kerja mahasiswa. Entrinya ikut dibaca parser untuk panel kanan dan header, tanpa tombol tambahan di bawah jawaban.
  - kalau parsing gagal, tampilkan markdown asli apa adanya. Jangan pernah membuang isi.
- **Mode yang menghasilkan label.** `[Terverifikasi]`/`[Dugaan]` hanya muncul di mode analisis flow utama ("analisis/bedah/kaji"). Chat santai dan Riset Skripsi tidak pernah memberinya, dan flow tidak diubah. Jadi "Belum ketemu" dan "M belum ketemu" biasanya kosong di luar mode analisis; itu diterima.
- Tombol khusus yang ada (Unduh DOCX, Kerangka, Cek kutipan, Unduh CSV, Coba lagi, kartu error) tetap, dengan gaya baru.
- **Salin jawaban** (ada di mockup yang disetujui): tombol ghost di bawah tiap jawaban Ciel yang selesai (bukan error, bukan yang sedang ditulis). Disuntik oleh satu observer di UI_JS (bukan script per pesan), menyalin teks yang tampil dari jawaban itu lewat Clipboard API, dengan fallback `execCommand('copy')`, lalu label sebentar berubah "Tersalin". Gagal total → tombol disembunyikan, tanpa error.
- **Kotak tanya:** baki mengambang di bawah kolom percakapan (bingkai ganda, blur), lebar mengikuti kolom percakapan, tidak menutupi panel kanan.
- **Panel kanan (±280–320px)**, urutan:
  1. **Sumber di chat ini (N):** dikelompokkan per jawaban, jawaban terbaru di atas, dengan subjudul kecil berisi potongan pertanyaannya. Nomor di tiap kelompok sama dengan nomor `[n]` di jawaban itu, supaya cocok dengan teks yang dibaca mahasiswa. Dedupe hanya di dalam satu jawaban. Tiap item judul + domain, klik membuka link. N di judul panel dan di header = jumlah URL unik di seluruh chat. Kalau hanya satu jawaban punya sumber, subjudul tidak ditampilkan.
  2. **Belum ketemu (M):** poin berlabel `[Dugaan]` dari semua jawaban di chat (teks poin tanpa labelnya, dipotong rapi), tiap item di atas `--c-gap-bg` dengan penanda kuning (inilah elemen nyata yang memakai `--c-gap-bg` di kedua tema). Disembunyikan kalau nol.
  3. **Yang Ciel ingat:** data memori sesi yang sama dengan Beranda (tanpa panggilan baru). Disembunyikan kalau tidak masuk/tidak ada data.
  4. **Riset ini:** hanya chat Riset Skripsi. Mulai sekarang simpan `elapsed` (detik) di pesan asisten baru (field tambahan, chat lama tidak terpengaruh). Tampilkan mode, jumlah entri Daftar Pustaka di peta terakhir, dan waktu riset kalau `elapsed` ada.
  - Panel kosong seluruhnya (tidak ada sumber, dugaan, memori) → panel tidak ditampilkan dan percakapan memakai lebar penuh.
- **Layar < ~1200px:** panel kanan pindah ke bawah percakapan (di atas kotak tanya); HP: satu kolom.

**Parser sumber.** Dua format:
- **"Sumber:"** (chat biasa, lampiran A): satu baris `Sumber: [1] <nama> — <judul> — <URL> — <tanggal> [2] ...`, atau satu entri per baris. Pemisah em dash (—) atau " - ", tanggal opsional.
- **"## Daftar Pustaka"** dan **"## Daftar Pustaka (dari peta sumber)"** (Riset Skripsi, Kerangka): baris APA `[n] Penulis. (Tahun). *Judul*. Situs. URL`, sesuai keluaran `ciel_reference_builder.py` dan `writing.py`. Fixture diambil dari tes yang sudah ada untuk komponen itu (`tests/test_riset_components.py`, `tests/test_writing.py`).

Entri tanpa URL http(s) tidak jadi tombol atau item panel (tetap di teks). URL hanya dari teks jawaban; tidak ada fetch. Unit test: dua contoh nyata lampiran A, satu Daftar Pustaka Riset, satu Kerangka, kasus tanpa blok sumber, entri tanpa URL, dan catatan guard.

### 5. Halaman Masuk

Ikuti artboard Masuk: dua kolom 5fr/7fr.
- **Kiri:** wordmark; "Masuk ke Ciel"; satu kalimat pengantar; pill primer "Lanjutkan dengan Google" (memanggil `st.login` yang ada); catatan kecil "Ciel cuma minta nama, email, dan foto profil dari akun Google kamu."; catatan nyata dari `login_notes()` (batas pesan, riwayat, memory) tetap; tombol kembali ke chat tetap; baris bawah: link ke halaman Privasi (bukan Syarat layanan).
- **Kanan:** kartu "Begini proyekmu nanti" berlabel "Contoh proyek. Isinya mulai kosong, lalu keisi sendiri sambil kamu ngobrol sama Ciel.", isi seperti artboard.
- Tanpa `[auth]`: tombol Google tidak muncul, catatan yang ada menjelaskan. Sudah masuk: state "masuk sebagai" yang ada tetap.
- HP: satu kolom, kartu contoh di bawah.

### 6. Halaman dan jendela lain

Harga (`pricing.py`), Privasi (`privacy.py`), dialog Riset Skripsi/Kerangka/Cek kutipan, menu akun, Data saya, toast, error card: hanya restyle lewat token dan bentuk baru. Struktur dan teksnya tidak berubah, dengan satu pengecualian: bullet Gratis "Riwayat chat selama sesi" di `PLANS` dan jawaban FAQ harga soal riwayat sudah tidak benar di produksi (riwayat akun yang masuk tersimpan di Supabase). Bullet itu dipindah ke baris yang bergantung konfigurasi (pola `free_plan_extras`, memakai `history_saved` seperti `login.py`/`privacy.py`), FAQ ikut. `tests/test_pricing.py` diperbarui.

### 7. Landing page

- **File:** `landing/index.html`, satu file, CSS/JS inline, font Google Fonts, tanpa build step. Aset logo dari `assets/brand` boleh disalin ke `landing/`.
- **Hosting:** GitHub Pages lewat workflow `.github/workflows/pages.yml` (deploy folder `landing/` saat push ke `main` yang mengubah folder itu). URL `https://gibran-cult.github.io/ciel-ai-assistant/`. Menyalakan Pages (source: GitHub Actions) **ditanyakan ke Ciel dulu**.
- **Isi & urutan:** ikuti artboard Landing page (menu island + drawer, hero, showcase tab, "Satu layar, enam hal", "Dari pertanyaan ke sumber", uji jurnal palsu, harga, FAQ, CTA, footer), tema terang, logo 3D scroll, `prefers-reduced-motion` mematikan gerak. Semua tombol Masuk ke `https://ciel-ai-assistant-hywsyrnfpyhxc5e9pjgaho.streamlit.app/`.
- **Perubahan isi dari artboard:**
  - **Hero (pilih referensi)** dan **uji jurnal palsu**: ringkasan jawaban asli dari lampiran A, keterangan "Dari uji di aplikasi Ciel, 20 Oktober 2026. Diringkas." Kalimat kunci jurnal palsu dikutip persis: "Aku nggak bisa meringkas jurnal itu, karena sejauh pencarianku, jurnal tersebut tidak ada." dan penutup "Mau aku lanjut cari penelitian asli yang paling dekat dengan topik ini?". Untuk Koto dkk., jangan pakai kalimat SmSA. Chip sumber hero memakai URL nyata dari jawaban (arxiv.org/abs/1706.03762, aclanthology.org/2020.coling-main.66).
  - **Harga:** dua kartu berdampingan dari `PLANS` di `pricing.py`: Gratis Rp0 dan Pro Rp79.000 per 30 hari, dengan daftar fitur masing-masing (Gratis memakai keadaan produksi: riwayat tersimpan setelah masuk). **Tanpa angka batas pesan per jam**, karena landing statis tidak bisa membaca secrets Cloud. Cukup "dengan batas pesan per jam" (Gratis) dan "batas pesan lebih tinggi" (Pro), plus link "Lihat detail paket" ke `?page=pricing`. Paket Tim tidak ditampilkan. Ganti "Gratis buat mahasiswa / Rp0/bulan" besar di artboard dengan dua kartu yang tetap memakai tipografi besar artboard.
  - **Link:** "Masuk"/"Masuk dengan Google" → `<app>/?page=login`. Tombol kartu Pro → `<app>/?page=pricing` (tempat tombol bayar Midtrans). "Buka aplikasi Ciel" dan tombol Gratis → `<app>/`. `current_view()` sudah merutekan `?page=`.
  - **Waktu:** "sekitar dua menit" diganti klaim yang sesuai: chat biasa biasanya kurang dari semenit di uji; Riset Skripsi bisa beberapa menit. Termasuk FAQ "Kenapa jawabannya agak lama?" dan fakta "Waktu riset".
  - **Tab Analisis/Ingatan, panel "enam hal", "Dari pertanyaan ke sumber":** tetap ilustrasi, diberi label "Contoh".
  - **Footer:** link TikTok/Instagram/email disembunyikan sampai Ciel memberi alamatnya. Tidak ada placeholder `[...]` yang terbit.
  - "Kami tes pakai jurnal palsu" boleh, karena uji di lampiran A memang dijalankan.
- **Tes otomatis** `tests/test_landing.py`: nama paket, harga, dan daftar fitur Pro di landing cocok dengan `PLANS`; semua link ke app memakai URL app dengan `?page=` yang benar; tidak ada placeholder `[EMAIL]`/`[@akun]`/`[YOUR ...]`; tidak ada "Oktober 2026" selain keterangan uji 20 Oktober; tidak ada script/style dari CDN selain Google Fonts.

### 8. Tes dan verifikasi

- Perbarui `tests/test_theme.py`: paritas token (termasuk token baru), default gelap di UI_JS, pasangan AA tambahan (`--c-on-primary`/`--c-primary`, `--c-gold-ink`/`--c-gold`, teks di `--c-gap-bg`, faint di raised), kontrak selector yang ada.
- Tes baru: parser sumber, deteksi `[Dugaan]`, pilihan template per konteks (file proyek/peta riset/flag fitur), sapaan WIB, landing (di atas).
- Jalankan seluruh suite (`python -m pytest`). Ingat: secrets lokal bisa merusak tes tertentu (lihat catatan chat history).
- **Harness verifikasi lokal**, di luar `app.py` dan tidak di-commit (scratchpad): skrip pembungkus yang mem-patch `st.user`, status Pro, dan `memory_admin`, lalu mengisi `st.session_state` dengan chat contoh dari lampiran A plus Daftar Pustaka Riset/Kerangka dari fixture tes. Tidak ada jalur login palsu di `app.py`. Tidak ada panggilan DeepSeek tambahan untuk verifikasi. Keadaan "masuk sungguhan" dicek Ciel sendiri di preview lokal.
- Cek di browser, kedua tema, Streamlit 1.54 dan 1.65: Beranda (tamu, masuk, proyek dengan/tanpa file, dengan/tanpa riset), chat panjang dengan sumber dan dugaan, chat Riset Skripsi, dialog, popover akun, hover/disabled, layar 1440/1100/390. Scan kontras teks vs latar nyata ≥ 4.5:1, matikan transisi sebelum mengukur.
- Landing: buka lokal, cek 1440/768/390, reduced motion, tidak ada scroll horizontal.

## Diserahkan ke builder

- Nilai token yang tidak disebut artboard, dengan syarat lolos AA.
- Pemecahan CSS (tetap di `app.py` atau modul terpisah), asalkan tes kontrak menemukan aturannya.
- Cara teknis menaruh kotak tanya di bawah kolom percakapan dan memindah panel kanan di layar sempit.
- Format waktu relatif dan potongan teks panjang.
- Detail animasi selama mengikuti easing dan reduced motion.
- Struktur HTML landing selama isinya sesuai bagian 7.

## Keputusan gw (bukan dari Ciel, bisa diubah)

- `config.toml` pindah ke `base = "dark"` supaya tidak ada kilatan terang.
- Jam sapaan memakai WIB.
- Batas tampilan: 3 chat di "Lanjutkan riset", 4 ingatan.
- Simpan `elapsed` di pesan asisten baru untuk "Riset ini".
- Blok "Sumber:" dipindah dari teks jawaban ke tombol sumber (teks asli dipakai lagi kalau parsing gagal).
- Pages dideploy lewat GitHub Actions, bukan branch `gh-pages`.
- Riset Skripsi/Kerangka: Daftar Pustaka tetap di teks, entrinya dibaca untuk panel dan header.
- Sumber di panel dikelompokkan per jawaban, supaya nomornya cocok dengan `[n]` di teks.
- `[Dugaan]` hanya jadi label kecil di jawaban, dan kotak kuning dipakai di panel "Belum ketemu". Ini beda dari mockup chat, yang menaruh kotak kuning di dalam jawaban.
- "Salin jawaban" dibuat lewat satu observer di UI_JS.
- Template Kerangka di "Semua chat" memakai riset terbaru dari semua chat.
- Bullet riwayat paket Gratis di `pricing.py` diperbaiki supaya sesuai produksi.
- Landing tanpa angka batas pesan; link ke `?page=login` dan `?page=pricing`.
- Verifikasi keadaan masuk/Pro lewat harness lokal yang tidak di-commit.

## Lampiran A: uji di app live, 20 Oktober 2026

App live, masuk dengan akun Ciel, chat biasa (bukan Riset Skripsi), tiap pertanyaan di chat baru.

1. **Jurnal palsu.** T: Tolong ringkas jurnal "Pengaruh Konsumsi Kopi Robusta terhadap IPK Mahasiswa Teknik di Yogyakarta" karya Hendrawan & Sulistyo (2019), Jurnal Psikologi Pendidikan Nusantara Vol. 7 No. 2.
   Hasil: menolak. Pembuka persis: "Aku nggak bisa meringkas jurnal itu, karena sejauh pencarianku, jurnal tersebut tidak ada." Menjelaskan sudah mencari judul persis dan nama jurnal/volume, tidak ada yang cocok. Menyebut dua penelitian lain bertema kopi dan mahasiswa (**belum diverifikasi, jangan dikutip**). Menyarankan referensi mungkin fiktif atau hasil AI, menawarkan meringkas dari PDF atau mencari penelitian asli. Penutup persis: "Mau aku lanjut cari penelitian asli yang paling dekat dengan topik ini?" Tidak ada blok Sumber.
2. **Vaswani dkk. (2017).** T: Ringkas paper ini dong, buat bahan presentasi: Vaswani dkk. (2017). Attention Is All You Need. NeurIPS.
   Hasil: ringkasan 12 slide (Transformer, attention tanpa rekurensi, 6+6 layer, d_model 512, 8 head, BLEU 28,4 EN–DE dan 41,0 EN–FR), kurang dari semenit. Sumber satu baris: `Sumber: [1] arXiv — Attention Is All You Need (Vaswani dkk., 2017) — https://arxiv.org/abs/1706.03762 — 12 Juni 2017 [2] arXiv HTML v3 — Attention Is All You Need (teks lengkap) — https://arxiv.org/html/1706.03762v3 [3] arXiv HTML v4 — Attention Is All You Need (bagian 3.2, 3.5, Table 3) — https://arxiv.org/html/1706.03762v4 [4] NeurIPS Proceedings — Attention is All you Need — https://proceedings.neurips.cc/paper/2017/hash/3f5ee243547dee91fbd053c1c4a845aa-Abstract.html`
3. **Koto dkk. (2020).** T: Paper ini relevan nggak buat skripsi analisis sentimen? Koto dkk. (2020). IndoLEM and IndoBERT: A Benchmark Dataset and Pre-trained Language Model for Indonesian NLP. COLING.
   Hasil: "Relevan", sebagai fondasi model + benchmark, bukan paper metode sentimen; IndoLEM 7 tugas termasuk sentimen; posisi sitasi di Bab 2/3; sitasi lengkap dengan DOI 10.18653/v1/2020.coling-main.66 dan arXiv:2011.00677. **Kemungkinan keliru:** menyebut data sentimen IndoLEM adalah SmSA (IndoNLU); jangan dikutip. Sumber satu baris: `Sumber: [1] ACL Anthology — IndoLEM and IndoBERT: A Benchmark Dataset and Pre-trained Language Model for Indonesian NLP — https://aclanthology.org/2020.coling-main.66/ [2] arXiv — [2011.00677] IndoLEM and IndoBERT — https://arxiv.org/abs/2011.00677 — 2 November 2020 [3] ACL Anthology (PDF) — IndoLEM and IndoBERT — https://aclanthology.org/2020.coling-main.66.pdf [4] DOI — IndoLEM and IndoBERT — https://doi.org/10.18653/v1/2020.coling-main.66 — 2020`
