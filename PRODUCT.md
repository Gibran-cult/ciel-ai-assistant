# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Website baru di `website/`, project greenfield di dalam repo app ini. Stack dipatok oleh brief pemilik (super prompt, 7 November 2026): Next.js App Router dengan TypeScript, Tailwind CSS yang mengambil semua warna dari CSS variables, React Three Fiber dengan drei, GSAP dengan ScrollTrigger, dan Lenis. Rencana hosting: static export ke GitHub Pages seperti landing sekarang, jadi tidak ada biaya hosting baru. Memindahkan ciel-ai.web.id dari `landing/` ke website baru adalah keputusan terpisah, diambil setelah pemilik mengecek sendiri di browser.

## Users

Mahasiswa Indonesia yang sedang mengerjakan tugas kuliah atau skripsi dan butuh rujukan yang bisa mereka cek sendiri sebelum dipakai. Mereka datang lewat tautan yang dibagikan Ciel (bio Instagram dan TikTok) atau dari mesin pencari, lalu memutuskan apakah Ciel layak dicoba.

## Product Purpose

Ciel adalah teman riset dan belajar berbahasa Indonesia. Sebelum menjawab, Ciel mencari sumber dulu, lalu menutup jawaban dengan daftar sumber bernomor yang bisa diklik. Kalau tidak menemukan apa-apa, Ciel bilang terus terang. Website ini berhasil kalau pengunjung paham cara kerja itu dalam beberapa detik, percaya karena melihat buktinya, lalu masuk ke aplikasi.

## Positioning

"Riset yang nggak ngarang." Sumber di jawaban Ciel datang dari pencarian di jawaban itu sendiri, angka dihitung alat, poin yang belum ada dasarnya ditandai sebagai dugaan, dan jurnal yang tidak pernah ada ditolak dengan jujur. Uji jurnal palsu di aplikasi pada 20 Oktober 2026 adalah bukti yang bisa ditunjukkan, dan chatbot umum tidak bisa mengklaim hal yang sama tanpa uji serupa.

## Operating Context

- Aplikasi: https://app.ciel-ai.web.id/ (redirect Cloudflare ke Streamlit Community Cloud, query string ikut). Masuk dengan Google bersifat opsional; tanpa masuk tetap bisa mencoba.
- Landing yang live sekarang: `landing/index.html` di GitHub Pages (https://ciel-ai.web.id/), dijaga oleh `tests/test_landing.py`.
- Pembelian Pro terjadi di aplikasi (`?page=pricing`, pembayaran lewat Mayar). Website hanya menautkan ke sana.
- Backend Ciel (Langflow, Ollama, ngrok) masih berjalan di laptop pemilik yang RAM-nya 8 GB, jadi build dan verifikasi website di mesin itu harus hemat memori.

## Capabilities and Constraints

- Paket dan harga di website wajib sama persis dengan `PLANS` di `pricing.py`: Gratis Rp0 dan Pro Rp79.000 per 30 hari, dengan daftar fitur yang sama kata per kata. Paket Tim tidak ditampilkan.
- Angka batas pesan per jam tidak boleh ditulis, karena website statis tidak bisa membaca secrets aplikasi. Cukup "dengan batas pesan per jam" dan "batas pesan per jam lebih tinggi".
- Tautan ke aplikasi hanya boleh ke `/`, `?page=login`, `?page=pricing`, `?page=privacy`, dan `?page=terms`. Alamat `streamlit.app` tidak boleh muncul.
- Aksi utama adalah tautan: "Masuk dengan Google" ke `?page=login`, dengan jalan kedua "coba tanpa masuk" ke `/`. Website tidak butuh form.
- Dari uji 20 Oktober 2026: chat biasa selesai di bawah semenit; Riset Skripsi bisa beberapa menit.
- Belum diputuskan: kapan domain ciel-ai.web.id dipindah ke website baru, dan nasib `landing/` sesudahnya.

## Brand Commitments

- Nama Ciel AI, wordmark "Ciel". Domain ciel-ai.web.id (bukan .my.id).
- Logo Kepingan di `assets/brand`: cincin yang dipotong rata di kanan, dengan kepingan emas yang bergeser keluar. Maknanya potongan yang hilang ditemukan, bukan dikarang. Pemilik menolak motif garis Lapisan; pakai Kepingan saja. Logo harus tetap terbaca di 16px.
- Palet Ciel yang sekarang, dipilih pemilik pada 7 November 2026: latar `#141311`, panel `#1f1d1a`, teks `#ececea`, teks sekunder `#b4b3ad`, biru teks `#9db3e8`, biru isi `#2b4886`, kuning `#e9d06a` (teks di atas kuning memakai warna latar). Netral tetap satu suhu dan tidak diwarnai biru. Tema gelap tanpa toggle, karena hitam adalah identitas merek.
- Wordmark "Ciel" ditulis dengan Fraunces (komitmen dari spec redesign 20 Oktober 2026). Huruf lain untuk website diputuskan di `website/DESIGN.md`.
- Suara: bahasa Indonesia santai ("kamu", "nggak"), seperti kakak tingkat yang ramah. Tanpa kata hype, tanpa label campur bahasa Inggris, tanpa emoji di teks sistem.
- Kepribadian dari brief: jujur, hangat, teliti.
- Objek 3D website: robot atau karakter yang realistis, besar, dan disorot cahaya studio, mengikuti referensi yang dikirim pemilik pada 7 November 2026 (halaman robot humanoid putih dengan visor gelap). Pilihan ini menggantikan usulan Kepingan 3D di brief awal. Override pemilik: robot bentrok dengan antislop R-22 dan Bagian 6 super prompt (objek harus berhubungan langsung dengan produk), dan pemilik tetap memilihnya setelah bentrok itu disebutkan. Desain robotnya orisinal, tidak meniru karakter berhak cipta mana pun, dan baru final setelah pemilik menyetujui render-nya.
- Setiap klaim di website harus cocok dengan aplikasi.

## Evidence on Hand

- Copy landing yang live: `landing/index.html`.
- Uji jurnal palsu 20 Oktober 2026: Ciel diminta meringkas jurnal fiktif Hendrawan & Sulistyo (2019) dan menolak dengan kalimat yang dikutip apa adanya di landing. Kalimat itu dijaga `tests/test_landing.py`.
- Contoh jawaban dengan sumber asli dari uji yang sama: Vaswani dkk. (2017) dan Koto dkk. (2020), dengan tautan arXiv, ACL Anthology, dan NeurIPS. Jawaban Koto menyebut data sentimen IndoLEM sebagai "SmSA"; itu kemungkinan keliru dan tidak boleh dikutip.
- Contoh tampilan aplikasi berlabel "Contoh" di landing: riset dengan sumber, analisis CSV dengan label Terverifikasi dan Dugaan, panel ingatan.
- FAQ landing yang sudah ada, berisi pertanyaan nyata pengguna.
- Kontak: gibranahmadn6@gmail.com, Instagram @ciel_ai.1, TikTok @ciel_ai.1.
- Belum ada dan tidak boleh dikarang: testimoni, jumlah pengguna, logo kampus atau klien, foto orang, dan angka performa di luar yang terukur pada uji 20 Oktober 2026.

## Product Principles

1. Tunjukkan bukti dulu, klaim belakangan. Setiap janji di halaman dibuktikan dengan contoh nyata dari aplikasi.
2. Jujur soal batas. Halaman bilang apa yang belum bisa, sama seperti Ciel bilang "nggak nemu".
3. Satu merek dari website sampai aplikasi: warna, logo, dan bahasa yang sama, supaya pindah ke aplikasi tidak terasa ganti tempat.
4. Interaksi yang kaya tidak boleh membuat halaman berat di HP kelas menengah.

## Accessibility & Inclusion

WCAG 2.x AA, bisa dipakai penuh dengan keyboard, dan menghormati `prefers-reduced-motion` (brief pemilik). Isi penting yang ditunjukkan objek 3D juga tertulis sebagai teks di halaman.
