# Ciel — Legal register

Daftar ini bukan nasihat hukum. Isinya daftar periksa produk berdasarkan UU 27/2022 (Pelindungan Data Pribadi), UU 8/1999 (Perlindungan Konsumen), PP 80/2019 (PMSE), dan Permenkominfo 5/2020 (PSE Lingkup Privat), serta checklist peluncuran aplikasi di reel breakingbreach (instagram.com/reel/DfKH360zRG4, dicek 2026-11-01). Minta konsultan hukum memeriksa halaman Ketentuan dan Privasi sebelum mengandalkannya.

Kotak kosong = belum dikerjakan. Pemiliknya Ciel, kecuali disebut lain.

## 1. Di mana tiap poin checklist berada

| Poin | Tempat di Ciel |
|---|---|
| Kebijakan privasi | `privacy.py`, tab Pengaturan > Privasi (`?page=privacy`) |
| Syarat dan ketentuan, pengembalian dana | `terms.py`, tab Pengaturan > Ketentuan (`?page=terms`) |
| Persetujuan tercatat | gerbang "Sebelum mulai" (`login.render_consent`, `app.consent_needed`), tabel `public.consents` |
| Daftar pihak ketiga (subprocessor) | `privacy.SUBPROCESSORS`, bagian "Pihak ketiga yang menerima datamu" |
| Pelacak dan cookie | `.streamlit/config.toml` (`gatherUsageStats = false`); halaman depan tanpa skrip pihak ketiga (`tests/test_landing.py`) |
| Retensi data | halaman Privasi: riwayat pesan `CHAT_RETENTION_DAYS` hari, cadangan 5 minggu, catatan pembelian 10 tahun |
| Akses dan penghapusan data | Pengaturan > Data saya (unduh, hapus per jenis, Hapus akun) |
| Label konten AI | catatan di Beranda, bagian "Ciel adalah AI" di Ketentuan, catatan penutup DOCX (`writing.py`, `riset_export.py`) |
| Tanpa tagihan otomatis, tanpa biaya tersembunyi | `pricing.py` ("Sekali bayar, tanpa langganan"), harga tetap Rp79.000 |
| Kontak pengelola | `OPERATOR_NAME` dan `CONTACT_URL` (secrets), email di halaman depan |

## 2. Pendaftaran

- [ ] **NIB lewat OSS RBA** (oss.go.id) sebagai usaha perseorangan. Pilih KBLI dengan pendampingan; NPWP Ciel memakai KLU 62199. Catat nomor NIB dan tanggalnya di sini.
- [ ] **Pendaftaran PSE Lingkup Privat** di Komdigi lewat OSS (Permenkominfo 5/2020). Wajib sebelum layanan dipakai publik; PSE yang belum terdaftar bisa diblokir aksesnya. Catat nomor tanda daftar di sini.

## 3. Ketentuan vendor dan DPA

Baca atau setujui ketentuan pemrosesan data (DPA) tiap pihak ketiga di `privacy.SUBPROCESSORS`, lalu catat tautan dan tanggalnya.

- [ ] Supabase: DPA dari dashboard (Organization > Legal). Region project: `ap-northeast-1` (Tokyo).
- [ ] Google Cloud: ketentuan Gemini API paket berbayar (data tidak dipakai untuk melatih model) dan Cloud Data Processing Addendum.
- [ ] DeepSeek: ketentuan API, terutama soal lama penyimpanan data dan pemakaian untuk pelatihan. Server di Tiongkok.
- [ ] Exa: ketentuan dan kebijakan privasi API.
- [ ] Streamlit Community Cloud (Snowflake): ketentuan layanan.
- [ ] ngrok: ketentuan layanan dan DPA.
- [ ] Mayar: perjanjian merchant.
- [ ] Google Fonts: kebijakan privasi Google (huruf di halaman depan dan aplikasi).

## 4. Secrets sebelum publik

- [ ] `OPERATOR_NAME` di Streamlit Cloud: nama pengelola yang tampil di halaman Privasi dan Ketentuan (UU PDP Pasal 5, PP 80/2019).
- [ ] `CONTACT_URL` di Streamlit Cloud (`mailto:` atau `https://`): tujuan permintaan data dan pengembalian dana.

## 5. Pajak dan catatan

- [ ] Simpan catatan order (`public.pro_orders`) dan bukti penarikan saldo Mayar selama 10 tahun. App tidak pernah menghapusnya, juga saat Hapus akun.
- [ ] Tanyakan ke konsultan pajak soal PPh Final UMKM 0,5% (PP 55/2022) atas omzet Ciel Pro.

## 6. Menangani pengembalian dana

Aturannya ada di Ketentuan > Pengembalian dana: refund penuh jika Pro tidak aktif dalam 1×24 jam atau order terbayar dua kali; perpanjangan masa Pro jika fitur Pro mati lebih dari 3 hari karena gangguan dari sisi Ciel; permintaan paling lambat 7 hari setelah bayar; jawaban paling lambat 3 hari kerja; dana dikirim paling lambat 14 hari kerja setelah disetujui. Pengguna Pro yang tidak menyetujui versi ketentuan baru mendapat pengembalian prorata untuk sisa hari Pro-nya (hitung: Rp79.000 × sisa hari ÷ 30).

1. Cari order dari nomor yang dikirim pengguna: `select * from public.pro_orders where id = '<nomor order>';`
2. Kirim dana kembali secara manual (transfer dari saldo Mayar atau rekening Ciel), lalu simpan buktinya.
3. Tandai order dan cabut Pro jika refund penuh:

```sql
update public.pro_orders set midtrans_status = 'refunded', updated_at = now() where id = '<nomor order>';
update public.pro_members set expires_at = now(), updated_at = now() where owner = '<owner order itu>';
```

4. Untuk perpanjangan karena gangguan: `update public.pro_members set expires_at = expires_at + interval '<n> days', updated_at = now() where owner = '<owner>';`

## 7. Aturan produk

- Tidak ada hitung mundur palsu, ulasan atau testimoni palsu, logo pelanggan tanpa izin, angka uptime, atau kalimat yang mempermalukan pengguna saat membatalkan.
- Email pemasaran di masa depan wajib opt-in dan punya tautan berhenti berlangganan.
- Jangan tulis kalimat "uang tidak dapat dikembalikan" atau "tidak bertanggung jawab atas segala ..." (UU 8/1999 Pasal 18); `tests/test_terms.py` menolaknya.
- Jika isi Ketentuan atau Privasi berubah secara material, naikkan `terms.LEGAL_VERSION` (semua akun diminta setuju lagi sekali) dan tanggal di halamannya (`TERMS_UPDATED`, `PRIVACY_UPDATED`).

## 8. Lisensi

- Huruf Fraunces dan Geist: SIL Open Font License 1.1. Logo Ciel: karya Ciel sendiri (`assets/brand`).
- [ ] Periksa lisensi dependensi sekali: `py -3.10 -m pip install pip-licenses` lalu `py -3.10 -m piplicenses --from=mixed --order=license`. Catat entri GPL, AGPL, atau yang tidak diketahui di sini.

## 9. Review hukum

- [ ] Konsultan hukum memeriksa halaman Ketentuan dan Privasi.
