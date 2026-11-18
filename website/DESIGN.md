---
name: Ciel AI website
description: Landing page Ciel AI, digambar sebagai peta penyelidikan malam dengan rute kuning ke sumber asli.
colors:
  bg: "#141311"
  surface: "#1f1d1a"
  surface-2: "#2a2824"
  text: "#ececea"
  muted: "#b4b3ad"
  blue-text: "#9db3e8"
  blue-hi: "#b4c5ef"
  blue-fill: "#2b4886"
  blue-fill-hi: "#34558f"
  yellow: "#e9d06a"
  yellow-hi: "#f1df90"
typography:
  display:
    fontFamily: "Alegreya, Georgia, serif"
    fontSize: "clamp(2.75rem, 5.2vw, 4.75rem)"
    fontWeight: 800
    lineHeight: 0.98
    letterSpacing: "-0.02em"
  display-closing:
    fontFamily: "Alegreya, Georgia, serif"
    fontSize: "clamp(2.75rem, 6.2vw, 5.5rem)"
    fontWeight: 800
    lineHeight: 0.98
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Alegreya, Georgia, serif"
    fontSize: "clamp(2.25rem, 4.4vw, 4rem)"
    fontWeight: 800
    lineHeight: 0.98
    letterSpacing: "-0.02em"
  quote:
    fontFamily: "Alegreya, Georgia, serif"
    fontSize: "clamp(1.5rem, 3vw, 2.25rem)"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Alegreya, Georgia, serif"
    fontSize: "1.375rem"
    fontWeight: 700
    lineHeight: 1.25
  note:
    fontFamily: "Alegreya, Georgia, serif"
    fontSize: "1.5rem"
    fontWeight: 400
    lineHeight: 1.3
    letterSpacing: "-0.01em"
  marginal:
    fontFamily: "Alegreya, Georgia, serif"
    fontSize: "1.1875rem"
    fontWeight: 400
    lineHeight: 1.55
  price:
    fontFamily: "Alegreya, Georgia, serif"
    fontSize: "clamp(2rem, 3.9vw, 3.5rem)"
    fontWeight: 800
    lineHeight: 0.98
    letterSpacing: "-0.02em"
    fontFeature: "\"lnum\", \"tnum\""
  lede:
    fontFamily: "Alegreya Sans, system-ui, sans-serif"
    fontSize: "1.1875rem"
    fontWeight: 400
    lineHeight: 1.55
  body:
    fontFamily: "Alegreya Sans, system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Alegreya Sans, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.55
  button:
    fontFamily: "Alegreya Sans, system-ui, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 700
    lineHeight: 1.55
  wordmark:
    fontFamily: "Fraunces, Georgia, serif"
    fontSize: "1.625rem"
    fontWeight: 500
    lineHeight: 1
    letterSpacing: "-0.01em"
  wordmark-footer:
    fontFamily: "Fraunces, Georgia, serif"
    fontSize: "clamp(4rem, 12vw, 10rem)"
    fontWeight: 500
    lineHeight: 0.9
    letterSpacing: "-0.03em"
rounded:
  row: "6px"
  bubble: "16px"
  sample: "18px"
  panel: "22px"
  case: "24px"
  pill: "999px"
spacing:
  gutter: "clamp(16px, 4.4vw, 64px)"
  nav-h: "72px"
  container: "1440px"
  section: "clamp(88px, 11vw, 184px)"
  section-map: "clamp(72px, 9vw, 120px)"
  stack-lg: "clamp(48px, 6vw, 96px)"
components:
  button-primary:
    backgroundColor: "{colors.yellow}"
    textColor: "{colors.bg}"
    typography: "{typography.button}"
    rounded: "{rounded.pill}"
    padding: "0 22px"
    height: "48px"
  button-primary-hover:
    backgroundColor: "{colors.yellow-hi}"
    textColor: "{colors.bg}"
  button-secondary:
    backgroundColor: "{colors.blue-fill}"
    textColor: "{colors.text}"
    rounded: "{rounded.pill}"
    padding: "0 18px"
    height: "44px"
  button-secondary-hover:
    backgroundColor: "{colors.blue-fill-hi}"
    textColor: "{colors.text}"
  chip-case:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.pill}"
    padding: "0 16px"
    height: "44px"
  chip-case-hover:
    backgroundColor: "{colors.surface-2}"
  chip-case-active:
    backgroundColor: "{colors.blue-fill}"
    textColor: "{colors.text}"
  link-quiet:
    textColor: "{colors.blue-text}"
    height: "44px"
  sample-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.sample}"
    padding: "16px"
  plan-pro:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.panel}"
    padding: "clamp(24px, 3.6vw, 56px)"
  case-file:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.muted}"
    rounded: "{rounded.case}"
    padding: "32px"
  menu-panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.panel}"
---

# Design System: Ciel AI website

> Reading this as: landing page produk (mode Persuade) untuk mahasiswa Indonesia yang sedang mengerjakan tugas atau skripsi, gaya peta penyelidikan malam dengan robot 3D yang menyorot rute ke sumber asli, dial ENERGY 3 / RHYTHM 3 / MOTION 3.

Dokumen ini mencatat sistem visual seperti yang terkirim di `website/` (dicek ulang dari kode dan screenshot pada 8 November 2026). Fakta produk ada di `../PRODUCT.md`; kontrak arah untuk reviewer ada di `.impeccable/surfaces/website-src-app-page-tsx.md`; token yang bisa dibaca mesin ada di frontmatter di atas dan di `.impeccable/design.json`. Kalau aturan di sini bertabrakan dengan Hard Gate antislop (kejujuran, fungsi, aksesibilitas), Hard Gate yang menang.

## Overview

**Creative North Star: "Peta penyelidikan"**

Riset digambar sebagai peta yang bisa dicek. Setiap jawaban adalah rute ke sumber bernama, dan jejak ke sumber yang tidak ada berakhir di laut kosong lalu dicoret. Peta itu dibuat dengan kode sebagai lembar bagan malam: garis tepi bergradasi, garis kedalaman putus-putus, pulau berbintik dengan garis kontur, nama domain ditulis miring menyusuri pantai, dan kotak Keterangan untuk tiga simbol juru peta.

Arah ini dipilih Ciel di halaman keputusan pada 7 November 2026 dari delapan kartu, karena paling jelas memperlihatkan cara kerja Ciel (asal-usul setiap kesimpulan). Asalnya dunia katalog "peta harta karun di atas vellum", diterjemahkan ke palet Ciel: vellum jadi tanah malam, tinta sepia jadi tinta terang, rute merah jadi rute kuning. Yang ditolak dengan sengaja: judul AI di tengah di atas mockup chat lalu deretan kartu fitur, karena itu tampilan default kategori ini.

Dial ENERGY 3 / RHYTHM 3 / MOTION 3, dan build-nya cocok dengan ketiganya. ENERGY 3: brief meminta website yang sangat interaktif dengan objek 3D yang mengikuti pengunjung, dan halaman ini punya robot yang menoleh, cahaya yang mengikuti pointer, dan tiga kasus yang bisa dipilih. RHYTHM 3: setiap section punya komposisi sendiri karena isinya berbeda jenis. MOTION 3: gerak dipakai untuk satu ritual, yaitu menyusuri rute dari pertanyaan ke sumber; tidak ada fade-up yang sama di semua elemen, dan tidak ada gerak yang berulang sendiri.

**Key Characteristics:**
- Tanah malam yang hangat dengan satu aksen kuning untuk rute dan aksi utama.
- Peta sebagai bagan juru peta yang digambar dengan SVG, bersudut siku, tanpa tekstur kertas.
- Alegreya untuk suara peta dan judul, Alegreya Sans untuk antarmuka, Fraunces hanya untuk wordmark.
- Datar: kedalaman datang dari langkah nada dan urutan lapisan.
- Robot android berlapis lacquer teal gelap dengan inlay emas sebagai objek 3D, selalu dipotong sebagai patung dada di belakang sesuatu.

## Colors

Palet Ciel yang sekarang, dipilih pemilik dan dipatok di PRODUCT.md: netral satu suhu yang hangat, biru untuk struktur, kuning untuk satu hal saja. Rasio dihitung dengan rumus WCAG 2.x.

### Primary
- **Kuning rute** (#e9d06a): tombol utama, focus ring, rute dan pin di peta, kepingan emas logo (termasuk modul telinga robot), inlay emas di wajah dan bahu robot, dan sorot emas di scene 3D. 12,11:1 terhadap latar; teks di atasnya selalu warna latar (12,11:1).
- **Kuning terang** (#f1df90): hover tombol utama dan pusat cahaya di rute peta, tempat sorot jatuh.

### Secondary
- **Biru tinta** (#9db3e8): link, nomor sumber, ikon garis, centang harga, dan cahaya tepi robot. 8,88:1 terhadap latar, 7,04:1 di atas surface-2. Biru adalah warna struktur: tautan dan cahaya di scene 3D.
- **Biru tinta terang** (#b4c5ef): hover link.
- **Biru isi** (#2b4886): tombol sekunder (Masuk, tombol paket), chip kasus yang aktif, gelembung pertanyaan di cerita, seleksi teks. Teks di atasnya `text` (7,48:1). Tidak pernah dipakai untuk teks di atas latar.
- **Biru isi terang** (#34558f): hover tombol sekunder (teks 6,25:1).

### Neutral
- **Tanah malam** (#141311): latar halaman. Hitam hangat yang sama dengan app, jadi pindah ke app tidak terasa ganti merek.
- **Lembar peta** (#1f1d1a): bidang peta, panel, footer, panel menu HP. Satu langkah nada di atas latar; bedanya cuma 1,10:1, jadi batas dibuat dengan jarak.
- **Daratan** (#2a2824): isi pulau di peta, hover dan state ditekan, gelembung di contoh layar app.
- **Tinta terang** (#ececea): teks utama (15,70:1). Terang tanpa putih murni, supaya tidak silau di layar gelap.
- **Tinta peta** (#b4b3ad): teks sekunder (8,83:1) dan semua garis peta. Satu suhu dengan latar, tidak kebiruan. Garis peta memakai warna ini dengan opacity rendah (garis kedalaman 0,16, kontur 0,2 turun ke 0,11, pantai 0,55, bintik 0,22 sampai 0,3).

### Named Rules
**The Yellow Law Rule.** Kuning hanya muncul di tombol utama, focus ring (dan skip link, yang hanya terlihat saat difokus), rute dan pin peta termasuk genangan cahayanya, dan kepingan emas logo termasuk modul telinga, inlay emas, dan sorot emas robot. Satu-satunya pengecualian adalah tiruan antarmuka app di section Legenda (`[data-ui]`), yang memakai kuning persis seperti app memakainya untuk label Dugaan. Di tempat lain kuning dilarang, supaya rute tetap jadi hal yang paling menarik mata.

**The One Temperature Rule.** Netral tetap satu suhu hangat dan tidak diwarnai biru. Biru hanya masuk sebagai tinta (link, ikon, cahaya tepi) atau sebagai isi tombol.

## Typography

**Display Font:** Alegreya (dengan Georgia, serif)
**Body Font:** Alegreya Sans (dengan system-ui, sans-serif)
**Label/Mono Font:** Fraunces 500 hanya untuk wordmark "Ciel"

**Character:** Alegreya adalah huruf sastra dengan ritme kaligrafis yang terasa seperti tulisan tangan juru peta, dan versi miringnya jadi suara peta itu sendiri. Alegreya Sans memakai kerangka huruf yang sama dan jelas di ukuran kecil, jadi halaman terasa satu keluarga. Fraunces adalah komitmen merek dari spec redesign 20 Oktober 2026 dan tidak dipakai untuk teks lain. Semua font di-host sendiri lewat `next/font`, tanpa permintaan ke server font saat halaman dibuka.

### Hierarchy
- **Display** (Alegreya 800, clamp(2,75rem, 5,2vw, 4,75rem), line-height 0,98, tracking -0,02em, text-wrap balance): judul hero, dua baris yang dipatah manual.
- **Display penutup** (800, sampai 5,5rem): judul section penutup, judul terbesar di halaman.
- **Headline** (800, clamp(2,25rem, 4,4vw, 4rem)): judul setiap section lain. Di bawah 360px judul Harga turun ke 2rem supaya tetap dua baris.
- **Quote** (Alegreya 600, clamp(1,5rem, 3vw, 2,25rem), 1,2): jawaban Ciel yang dikutip apa adanya di uji jurnal palsu. Kutipan yang lebih kecil memakai Alegreya 400 di 1,25rem sampai 1,375rem.
- **Title** (Alegreya 700, 1,375rem, 1,25): istilah di Legenda. Nama paket memakai bobot yang sama di clamp(1,375rem, 1,9vw, 1,75rem).
- **Note** (Alegreya miring 400, 1,5rem, 1,3): pertanyaan FAQ.
- **Marginal** (Alegreya miring 400, 1,1875rem atau ukuran body): catatan pinggir, seperti ajakan memilih referensi, catatan di bawah jawaban, syarat paket, dan keterangan "Contoh".
- **Price** (gaya display, clamp(2rem, 3,9vw, 3,5rem), angka tabular dan lining): harga paket.
- **Lede** (Alegreya Sans 400, 1,1875rem, 1,55): paragraf pembuka di hero dan penutup.
- **Body** (Alegreya Sans 400, 1,125rem, 1,55, maksimal 66ch): semua teks isi.
- **Label** (Alegreya Sans 400, 0,9375rem): keterangan kecil berwarna muted, seperti "Gratis untuk mulai.", label "Kamu" dan "Ciel", footnote.
- **Button** (Alegreya Sans 700, 1,0625rem): tombol; menu nav memakai 500 di ukuran yang sama.

Di dalam SVG peta, nama pulau ditulis Alegreya miring 400 di 22 unit viewBox (28 unit di peta cerita yang tampil lebih kecil), "Pertanyaanmu" dan "tidak ada" miring 700, dan nomor pin `[n]` Alegreya Sans 700.

### Named Rules
**The Map Voice Rule.** Teks miring Alegreya adalah suara peta: nama tempat, keterangan, catatan pinggir. Antarmuka dan isi tidak pernah miring.

**The Lining Figures Rule.** Angka harga dan nomor sumber memakai angka tabular; harga juga lining, karena angka gaya lama membuat Rp0 terbaca seperti Rpo.

## Layout

Kontainer maksimal 1440px di tengah, dengan gutter clamp(16px, 4,4vw, 64px) di kiri dan kanan. Nav 72px. Section memakai padding vertikal clamp(88px, 11vw, 184px); hero dan cerita sedikit lebih rapat (clamp(72px, 9vw, ...)). Di dalam section, jarak antarbaris kecil (12px sampai 24px) dan jarak antarkelompok besar (48px sampai clamp(56px, 7vw, 104px)), jadi kelompok isi terbaca sebagai blok.

Breakpoint yang bekerja: 48rem (menu nav melebar), 900px (dua paket harga berdampingan), 64rem (layout dua kolom, robot 3D desktop, pin cerita, Lenis, pose section), 80rem (robot berdiri di sudut cerita). Semua query lebar ditulis dalam rem supaya zoom dan ukuran font bawaan yang besar ikut menggeser layout.

Setiap section punya komposisinya sendiri:
- Hero, dari 1024px: judul memegang pita atas, lalu grid dua kolom. Kiri (17rem sampai 23rem) berisi lede, tombol, dan chip kasus; kanan berisi lembar peta yang rata kanan dan, di layar pendek, mengecil (tidak pernah di bawah 30rem) supaya seluruh rute muat di layar pertama. Jawaban dan daftar sumber ada di bawah peta.
- Hero di HP dan tablet: blok robot di bawah nav (tinggi sekitar 42% layar), dengan strip rute 360 x 128 di dasar blok; judul dan lede menyusul di bawahnya.
- Cerita: daftar langkah di kiri (22rem, 26rem dari 1280px), peta di kanan. Dari 1280px, 21% kanan dikosongkan untuk robot di sudut layar.
- Uji jurnal palsu: semua isi di 58% kiri, robot di kanan.
- Legenda: kunci bernomor di kiri (21rem), tiruan layar app di kanan.
- Harga: dua paket berdampingan dari 900px, masing-masing selebar isinya. Gratis berdiri di tanah malam, Pro di bidang surface; Gratis memakai padding Pro sebagai jarak atas supaya nama, harga, dan daftar sejajar.
- Tanya jawab: grid 12 kolom; judul sticky di 4 kolom kiri (top 96px), pertanyaan di kolom 6 sampai 12 dengan lebar 62ch.
- Penutup: setinggi 86% layar dari 1024px, isi di 55% kiri, robot di kanan bawah.
- Footer: tepi bawah lembar peta. Sisi atasnya garis tepi bergradasi yang sama dengan lembar peta, jadi robot penutup berdiri di belakangnya seperti robot hero di belakang lembar peta. Rute terakhir masuk dari tepi kiri dan berhenti di cincin Kepingan pada wordmark besar di bawah robot. Di bawah wordmark ada tagline dan tautan yang disusun seperti keterangan peta (istilah miring: Mulai, Ikuti, Hubungi, Lihat); di kiri, catatan "Sumber data peta" berisi tiga referensi uji 20 Oktober 2026 dengan simbol cincin-titik dan silang. Tanpa kolom sitemap karena situsnya satu halaman.

**The Clear Lane Rule.** Robot tidak pernah lewat di belakang teks. Setiap section tempat robot berdiri menyisakan jalur kanan untuknya (58%, 55%, atau 21% kanan), dan di bawah 1024px robot hanya punya bloknya sendiri di hero.

## Elevation & Depth

Sistem ini datar. Tidak ada `box-shadow`, tidak ada blur latar. Kedalaman datang dari tiga langkah nada (tanah malam, lembar peta, daratan) dan dari urutan lapisan: robot berdiri di lapisan paling bawah, dan potongan dada patungnya selalu tertutup oleh sesuatu di depannya (lembar peta, strip rute, tepi bawah layar, atau tepi atas footer). Satu-satunya cahaya adalah cahaya robot: genangan kuning lembut (opacity 0,13) yang bergerak di atas lembar peta di hero, dan sorot emas di scene 3D.

### Named Rules
**The Tone Step Rule.** Bidang yang diangkat naik satu langkah nada. State hover dan ditekan naik satu langkah lagi. Garis 1px hanya muncul di dalam tiruan antarmuka app, karena begitulah app menggambarnya.

**The Hidden Cut Rule.** Robot selalu tampil sebagai patung dada (dari atas kepala sampai potongan di dada), dan potongan itu tidak pernah terlihat: ia selalu berada di belakang sesuatu atau di luar layar.

## Shapes

Dua bahasa bentuk yang sengaja dipisah. Peta adalah bagan juru peta: sudut siku, garis tepi ganda dengan pita skala yang diisi berselang-seling, kotak Keterangan bersudut siku, dan pulau bergaris pantai halus dengan kontur di dalamnya. Antarmuka bersudut lembut: tombol dan chip berbentuk pil (999px), contoh di cerita dan layar app 18px, paket Pro dan panel menu HP 22px, berkas uji jurnal palsu 20px di HP dan 24px dari 640px, gelembung pertanyaan 16px, baris yang bisa di-hover 6px. Focus ring 2px kuning dengan jarak 3px dan sudut 6px.

Tiga simbol juru peta dipakai di mana pun rute muncul: cincin kuning berisi warna latar untuk pertanyaan, titik kuning penuh dengan cincin tipis (opacity 0,4) untuk sumber yang ditemukan, dan silang muted untuk sumber yang tidak ada. Rute adalah garis kuning putus-putus 2,4 unit (dash 6, celah 7, ujung bulat); jejak palsu adalah garis muted putus-putus 2 unit (dash 4, celah 8), diakhiri silang, label yang dicoret, dan catatan miring tebal "tidak ada".

**The Route Motif Rule.** Rute kuning putus-putus dengan tiga simbol adalah satu-satunya motif identitas. Ia muncul di peta hero, strip rute di HP, peta cerita, berkas uji jurnal palsu, penutup (garis yang masuk dari tepi kiri lalu berhenti di cincin dengan titik), dan berakhir di footer, di cincin Kepingan pada wordmark. Rute footer tergambar mengikuti scroll di browser yang mendukung animasi berbasis scroll (diam di reduced motion), dan menyala saat "Kembali ke atas" di-hover atau difokus. Motif ini membawa isi, jadi ia tidak dipakai sebagai hiasan di tempat yang tidak bicara soal sumber.

## Components

### Buttons
- **Shape:** pil (999px).
- **Primary:** latar kuning, teks warna latar, 700, tinggi minimal 48px, padding 0 22px. Hanya untuk satu aksi: "Masuk dengan Google" di hero dan penutup. Hover naik ke kuning terang; ditekan turun 1px dan mengecil 1%; transisi 160ms dengan ease-out ekspo.
- **Hover / Focus:** saat di-hover atau difokus lewat keyboard, robot menoleh ke tombol dan sorot emasnya menguat 60%, jadi pengguna mouse dan keyboard mendapat reaksi yang sama.
- **Secondary:** latar biru isi, teks terang, tinggi minimal 44px, padding 0 18px. Dipakai untuk Masuk di nav dan tombol di tiap paket. Hover ke biru isi terang.
- **Link tenang:** teks biru tanpa bidang, tinggi 44px, dipakai untuk aksi kedua di samping tombol utama ("Coba tanpa masuk") dan tautan footer. Di footer, garis bawah setebal 1px tergambar di bawah labelnya saat hover atau fokus keyboard.

### Chips
- **Style:** tiga chip kasus uji di hero, pil 44px, latar lembar peta, teks terang 500 di 1rem. Di HP berderet, dari 1024px bertumpuk.
- **State:** yang aktif berlatar biru isi dengan titik kecil terang di depan teksnya (`aria-pressed`); hover naik ke daratan; ditekan turun 1px.

### Cards / Containers
- **Corner Style:** 18px sampai 24px (lihat Shapes).
- **Background:** lembar peta, satu langkah di atas latar.
- **Shadow Strategy:** tidak ada (lihat Elevation & Depth).
- **Border:** tidak ada, kecuali garis 1px dengan opacity 10% di dalam tiruan layar app.
- **Internal Padding:** 16px untuk contoh di cerita, 20px sampai 40px untuk berkas uji jurnal palsu, clamp(24px, 3,6vw, 56px) untuk paket Pro.
- Bidang dipakai untuk benda yang memang benda: contoh jawaban, berkas uji, paket berbayar, layar app. Struktur halaman tidak dibangun dari deretan kartu.

### Navigation
- Bar polos 72px di atas lapisan 3D: logo Kepingan 28px dan wordmark Fraunces di kiri, empat tautan section (Alegreya Sans 500, 1,0625rem, muted, terang saat hover dan fokus), dan Masuk sebagai tombol sekunder di kanan.
- Di bawah 768px tautan dan Masuk masuk ke satu panel lembar peta di bawah bar, bersudut bawah 22px, dengan baris 52px. Tombol menu adalah dua garis yang berputar jadi silang (220ms). Escape menutup panel, Tab berputar di dalam menu termasuk tombolnya, dan panel tertutup sendiri kalau layar melebar.

### FAQ
- `<details>` asli, jadi tetap jalan tanpa JavaScript. Pertanyaan ditulis miring 1,5rem, hover dan fokus memberi bidang daratan yang melebar ke gutter supaya teksnya tetap rata dengan jawaban. Plus berubah jadi minus karena garis tegaknya berputar 90 derajat (300ms).

### Peta penyelidikan (signature)
- Lembar SVG yang digambar dari kode (`mapGeometry.ts`), dipakai dua kali: hero dan cerita. Semua isinya juga tertulis sebagai HTML di sebelahnya, jadi SVG-nya `aria-hidden`.
- Hero: tiga chip memakai hasil asli dari uji 20 Oktober 2026. Vaswani dan Koto menggambar ulang rute dari Pertanyaanmu ke sumbernya (garis digambar 1,5 detik, pin muncul 600ms ditambah 160ms per pin). Selama itu jejak jurnal palsu tetap ada di lembar dan berangkat dari cincinnya sendiri, "Uji jurnal palsu", karena di uji itu ia pertanyaan terpisah. Hendrawan & Sulistyo menghapus rute, meredupkan semua pulau sumber ke 45%, dan menarik jejak langsung dari Pertanyaanmu ke laut kosong, lalu robot menggeleng sekali. Jawaban di bawah peta diperbarui lewat `aria-live`.
- Cahaya: pointer di mana pun di dalam hero menggeser genangan cahaya di lembar dengan peluruhan eksponensial. Rute paling terang di bawah cahaya (kuning terang) dan tetap terbaca di tempat lain (kuning di opacity 55%); pin dalam jangkauan cahaya naik dari opacity 0,6 ke 1. Dengan reduced motion cahaya diam di tengah rute.
- Cerita, dari 1024px dengan gerak diizinkan: hanya kolom peta yang di-pin di tengah layar, sementara empat langkah lewat di sebelahnya. Langkah pertama menunjukkan pertanyaan, langkah kedua menggambar rute mengikuti scroll, langkah ketiga memunculkan pin dan sumber, langkah keempat menarik jejak palsu dari cincin "Uji jurnal palsu". Kalimat langkah yang sedang aktif tampil penuh, yang lain turun ke 55%; contoh di setiap langkah tetap kontras penuh. Semua langkah selalu ada di halaman, jadi keyboard dan pembaca layar sampai ke semuanya. Tanpa pin (HP, reduced motion, tanpa JavaScript) peta langsung menunjukkan rute yang selesai.

### Robot Ciel (signature)
- Kepala android dengan wajah yang dipahat: alis, mata berbentuk almond dengan kelopak atas dan bawah, hidung dengan cuping dan lubang hidung, tulang pipi, bibir dengan lekuk di tengah, dagu, dan garis rahang yang tegas di bawahnya. Lapisannya lacquer teal keabuan yang mengilap. Pelat wajah dipisah dari tengkorak oleh alur yang benar-benar terpotong ke permukaan, dengan strip emas di dasarnya: dari pelipis ke rahang dan dagu, di bawah mata, dari pipi ke telinga, melintasi kepala, dan di pelat belakang. Di kulitnya ada titik emas cetak yang kebanyakan mengikuti alur, deretan via pendek, simpul gelap berbingkai emas di pertemuan alur, dan chip emas kecil. Telinga berupa dial: dudukan lacquer, mangkuk gelap, dua kerah emas, hub baja bubut yang membawa logo Kepingan 3D, dan tuas baja. Leher berupa selongsong hitam berlapis dengan dua kolom yang membawa garis emas, bahu lacquer dengan garis tulang selangka emas. Arahnya dari gambar referensi pemilik (8 November 2026); bentuk dan detailnya dibuat sendiri dari kode.
- Override pemilik: robot bentrok dengan antislop R-22 (robot adalah gambar AI generik) dan Bagian 6 super prompt. Pemilik memilihnya setelah bentrok itu disebutkan pada 7 November 2026. Keterhubungan ke produk dijaga lewat logo Kepingan di telinga dan cahaya emas di dunia yang sama dengan rute.
- Model dibangun dari kode saat runtime (dua siluet kepala, depan dan belakang, yang dipadukan mengelilingi kepala; wajah dan alur dipahat sebagai pergeseran di permukaan itu, dengan mesh yang lebih rapat di wajah; cekungan digelapkan per vertex karena tidak ada shadow map; detail cetak sebagai instanced mesh; ekstrusi dari path SVG logo), sekitar 40 KB kode sumber. Ini menggantikan file GLB di brief, karena lebih ringan dari GLB terkompresi mana pun dan tetap tajam di semua resolusi.
- Cahaya: lacquer-nya mengilap, jadi bentuk wajah dibaca dari pantulan. Environment-nya studio kecil yang dipanggang sekali: jendela lembut di depan kiri atas, strip di atas kepala, kartu sempit di kanan, cahaya tepi dingin di kanan belakang dan hangat di kiri belakang, dan cahaya hangat redup dari peta di bawah. Sorot emas dari peta tinggal isian lembut dari bawah. Tone mapping Neutral, supaya teal dan emas tetap di warnanya.
- Penempatan: robot mengisi kotak patung dada (`[data-robot-anchor]`, rasio 780:848) yang ada di halaman, jadi ukuran dan posisinya ikut layout di setiap lebar layar.
  - Hero dari 1024px: di belakang ujung kanan lembar peta, selebar 40% lembar, tepi atas lembar memotong bingkai di 63,4% tingginya (tepat di bawah dagu). Kepala menunduk ke peta dalam sudut tiga perempat.
  - HP dan tablet: di blok robot hero, di belakang strip rute. Robot hanya ada di sini dan ikut ter-scroll pergi; tidak ada pose section di layar kecil.
  - Cerita: dari 1280px berdiri kecil di sudut kanan bawah layar, dengan 10% bawah kotaknya di luar layar. Di antara 1024px dan 1280px robot keluar layar supaya peta dapat ruang.
  - Uji jurnal palsu: berdiri di kanan dengan cahaya diredupkan dan menggeleng sekali saat section ini tiba.
  - Legenda, Harga, Tanya jawab: robot keluar layar di kanan, dan section memakai lebar penuh.
  - Penutup: di kanan bawah section, dadanya di belakang tepi atas footer, menghadap pengunjung dengan cahaya paling kuat.
- Gerak: pindah pose memakai redaman berbobot lalu menahan kotaknya persis, jadi robot ikut ter-scroll bersama lembar peta. Kepala menoleh dan mengangguk dari pangkal leher, dan mengikuti pointer (dan sentuhan yang dilaporkan sebagai gerak pointer) diukur dari posisi kepala di layar, dengan batas per pose: di luar section penutup kepala tidak pernah menghadap pengunjung, dan pointer di peta membuatnya menunduk ke peta. Gerakannya memakai peluruhan eksponensial, terasa berbobot dan sedikit tertinggal. Giroskop tidak dipakai, karena izinnya menambah satu prompt tanpa membantu tugas pengunjung. Robot bukan kontrol: ia tidak menerima fokus dan tidak membuka apa pun.
- Mata: bola mata hitam mengilap di balik kelopak almond, dengan iris cahaya berbentuk apertur lensa, kornea kaca yang menangkap pantulan, dan kelopak atas yang bisa berkedip, menyipit, dan ikut turun saat mata melihat ke bawah. Lampu kecil di depan mata menerpa rongga mata dan pangkal hidung dengan warna iris. Bola mata berputar mengikuti pointer lebih cepat daripada kepala (tatapan dulu, kepala menyusul). Semua ekspresi dipicu kejadian, tidak ada yang berulang sendiri, dan yang terpanjang 2,9 detik:
  - Bangun: saat 3D pertama tampil, mata sama dengan gambar diam, padam sebentar, lalu menyala berkedip.
  - Kedip: kelopak atas menutup sebentar setiap kali pindah pose, dan saat pengunjung menyentuh kepalanya.
  - "Ketemu": mata menyipit dan menyapu kiri-kanan selama 1,1 detik sambil kepala ikut memindai, lalu iris menghangat jadi emas, warna yang sama dengan pin sumber di peta, dan kepala mengangguk sekali. Dipicu chip Vaswani dan Koto, dan langkah mencari di cerita.
  - "Tidak ada": menyapu, lalu iris meredup, kelopak turun setengah, dan kepala menunduk sedikit sambil menggeleng. Dipicu chip Hendrawan, langkah terakhir cerita, dan bagian uji jurnal palsu.
  - Penasaran: mata membesar saat tombol utama di-hover atau difokus.
  - Menyapa: pointer yang diam di kepala robot (atau ketukan di sana) membuat matanya lebih terang dan sedikit hangat, dan kepalanya miring sedikit.
  Warna dasarnya biru. Emas hanya muncul saat sumber ketemu, karena di situ ia menyambung ke rute dan pin di peta.
- Aksesibilitas dan performa:
  - Lapisan 3D memakai `aria-hidden="true"` dan `pointer-events: none`. Semua isi yang ditunjukkan robot tertulis sebagai teks.
  - LCP adalah patung dada diam (`robot-bust.webp`, `fetchpriority="high"`), ditangkap dari robot 3D yang sama di situs (Chrome headless dengan GPU, latar transparan, dipotong di kotaknya) dan berdiri di kotak yang sama, jadi serah terimanya cross-fade 700ms di tempat, mata sudah menyala sejak gambar pertama. Patung penutup dimuat lazy, dan still pose uji jurnal palsu mengisi tempat robot di desktop sampai robot hidup.
  - three.js baru dimuat setelah gerak pertama pengunjung (pointer, sentuh, roda, scroll, atau tombol) dan saat browser senggang; di HP juga menunggu blok robot terlihat. Butuh WebGL2; kalau tidak ada atau renderer gagal, patung diam tetap tampil dan halaman tetap utuh.
  - Shader robot dikompilasi paralel di luar main thread (`compileAsync`) sebelum robot pertama kali digambar; selama itu patung diam tetap tampil. Di laptop uji, tugas terpanjang saat robot dimuat turun dari sekitar 6 detik ke sekitar 1,1 detik.
  - Scene digambar sesuai kebutuhan: satu frame per gerak pointer, scroll, resize, fokus, atau event robot, dan berhenti begitu robot diam di posenya. Di HP tidak ada yang digambar saat blok di luar layar. DPR dibatasi `[1, 2]` dan mulai di 1,5, atau di rasio piksel layar kalau lebih kecil; `PerformanceMonitor` hanya menilai saat robot bergerak dan menurunkan DPR ke 1 kalau FPS jatuh.
  - Dengan `prefers-reduced-motion`: tidak ada scene 3D, hanya patung diam, tanpa ikut kursor, tanpa Lenis, tanpa pin cerita, dan tanpa pose scroll.

### Gerak halaman
- Lenis (lerp 0,12) hanya dari 1024px dengan gerak diizinkan, supaya cerita terasa seperti satu perjalanan menyusuri rute. Tautan di halaman ikut lewat Lenis, dan fokus dipindah ke section tujuan untuk pengguna keyboard dan pembaca layar.
- GSAP dan Lenis hanya diunduh di tempat mereka bekerja. Satu easing untuk semua transisi antarmuka: ease-out ekspo `cubic-bezier(0.16, 1, 0.3, 1)`.
- Tidak ada gerak yang berulang sendiri, jadi tidak ada animasi lebih dari 5 detik yang perlu tombol jeda. Semua gerak lahir dari scroll, pointer, fokus, atau klik.

## Do's and Don'ts

### Do:
- **Do** ambil setiap warna dari variabel CSS di `globals.css`; komponen tidak memakai hex mentah (scene three.js mencerminkan hex yang sama karena tidak bisa membaca variabel CSS).
- **Do** gambar rute sebagai garis kuning putus-putus (2,4 unit, 6/7, ujung bulat) dengan cincin untuk pertanyaan, titik untuk sumber, dan silang untuk sumber yang tidak ada.
- **Do** tulis setiap fakta yang ada di peta atau ditunjukkan robot juga sebagai teks HTML, dan sembunyikan gambarnya dari teknologi bantu.
- **Do** buat batas dengan jarak dan langkah nada; garis 1px hanya di dalam tiruan antarmuka app.
- **Do** beri robot kotak patung dada yang menyembunyikan potongan dadanya, dan sisakan jalur kanan supaya ia tidak lewat di belakang teks.
- **Do** jaga target sentuh minimal 44px (tombol utama 48px).
- **Do** sediakan versi diam untuk setiap gerak: patung dada, peta yang sudah selesai, cahaya yang diam.

### Don't:
- **Don't** pakai kuning di luar Yellow Law: tombol utama, focus ring dan skip link, rute peta, kepingan emas logo dan emas robot (inlay, telinga, iris saat sumber ketemu), dan label Dugaan di tiruan app.
- **Don't** pakai mawar angin, tekstur perkamen, warna merah, atau deretan kartu sebagai struktur halaman.
- **Don't** pakai bayangan atau blur latar untuk mengangkat bidang.
- **Don't** buat form untuk aksi utama: aksinya masuk ke app lewat Google, jadi form di website akan jadi kontrol palsu.
- **Don't** muat model 3D dari file GLB; geometri robot dibangun dari kode.
- **Don't** minta izin giroskop; tidak membantu tugas pengunjung.
- **Don't** tampilkan testimoni, deretan logo, angka pengguna, atau metrik karangan, karena datanya tidak ada. Harga cukup dua paket berdampingan.
- **Don't** buat gerak yang berulang sendiri atau fade-up yang sama untuk semua elemen.
- **Don't** pakai Fraunces untuk apa pun selain wordmark "Ciel", dan jangan pakai huruf miring untuk teks antarmuka.
