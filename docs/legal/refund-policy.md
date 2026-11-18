# Kebijakan Pengembalian Dana Ciel (draf)

> Draf, bukan nasihat hukum, dan belum berlaku. Aturan pengembalian dana yang berlaku sekarang ada di `terms.py` bagian "Pengembalian dana" dan cara menanganinya di `docs/LEGAL.md` bagian 6. Bagian bertanda [CEK HUKUM] wajib ditinjau ahli hukum.

Terakhir diperbarui: [ISI: tanggal berlaku]

Kebijakan ini memisahkan dua hal yang berbeda: uang yang kamu bayar ke Ciel untuk paket, dan uang yang kamu bayar ke toko untuk barang.

## 1. Paket Ciel

Aturan di bagian ini sama dengan yang berlaku sekarang.

| Keadaan | Yang kamu dapat |
|---|---|
| Sudah membayar tetapi paket tidak aktif dalam 1×24 jam | Uang kembali penuh |
| Terbayar dua kali untuk order yang sama | Uang kembali penuh untuk pembayaran kedua |
| Fitur berbayar tidak bisa dipakai lebih dari 3 hari berturut-turut karena gangguan dari sisi Ciel | Masa paket diperpanjang sebanyak hari gangguan |
| Kamu tidak menyetujui perubahan ketentuan saat masa paket masih berjalan | Sisa masa paket dikembalikan prorata |
| Ciel menghentikan fitur berbayar yang sudah kamu beli | Sisa masa paket dikembalikan prorata |
| Alasan lain | Ditinjau satu per satu |

Cara mengajukan:

1. Hubungi [ISI: email atau tautan kontak] paling lambat 7 hari setelah membayar, dengan menyebut nomor order.
2. Kami menjawab paling lambat 3 hari kerja.
3. Dana dikirim paling lambat 14 hari kerja setelah permintaan disetujui, ke metode pembayaran asal atau rekening yang kamu sebutkan.

Hitungan prorata: harga paket × sisa hari ÷ 30.

## 2. Diskon mahasiswa

- Kalau verifikasi mahasiswa gagal setelah kamu membayar harga mahasiswa karena kesalahan sistem Ciel, kamu bisa memilih uang kembali penuh atau membayar selisih ke harga umum.
- Kalau kamu membayar harga umum lalu terverifikasi sebagai mahasiswa dalam 7 hari, selisihnya dikembalikan. [ISI: konfirmasi pemilik]

## 3. Kalau nanti ada perpanjangan otomatis

Sekarang tidak ada tagihan otomatis. Kalau fitur itu ditambahkan:

- kamu mendapat pengingat sebelum tanggal perpanjangan,
- tagihan perpanjangan yang kamu batalkan dalam [ISI: jumlah hari] hari tanpa memakai fitur berbayar dikembalikan penuh,
- berhenti berlangganan bisa dilakukan dari halaman yang sama dengan tempat mendaftar.

## 4. Barang yang kamu beli di toko

Ciel tidak menerima uang pembelian barang. Uang itu kamu bayarkan langsung ke toko atau marketplace, jadi pengembaliannya mengikuti aturan mereka.

Yang dilakukan Ciel:

- menyimpan catatan pesanan yang disiapkan agent (toko, barang, total, waktu) di log aktivitas,
- menunjukkan langkah pembatalan atau pengembalian di toko itu,
- menyiapkan ringkasan dan bukti untuk keluhanmu ke toko atau marketplace.

## 5. Kalau kesalahannya dari Ciel [CEK HUKUM]

Kalau kamu rugi karena agent menjalankan aksi yang berbeda dari ringkasan yang kamu setujui, atau karena Ciel keliru menyatakan sebuah toko resmi, berlaku [Kebijakan Penggunaan Agent](agent-usage-policy.md) bagian 5 dan 6. Urutannya:

1. Laporkan lewat [ISI: email] dengan waktu kejadian.
2. Kami memeriksa log aktivitas dan menjawab paling lambat 3 hari kerja.
3. Kami membantu pembatalan atau pengembalian di toko lebih dulu.
4. Kerugian yang tersisa dan menjadi tanggungan Ciel diganti sesuai batas di kebijakan itu.

## 6. Catatan untuk pemilik

- Pengembalian dana masih dikerjakan manual lewat SQL dan transfer (`docs/LEGAL.md` bagian 6). Untuk jumlah pengguna yang lebih besar perlu alat admin sederhana.
- Catatan order tetap disimpan 10 tahun, termasuk order yang dikembalikan.
- Kalimat "uang tidak dapat dikembalikan" tidak boleh dipakai di halaman mana pun (aturan yang sudah ada di `docs/LEGAL.md` bagian 7).
