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

Hasil pemeriksaan 2026-11-01 dari dokumen resmi tiap vendor di `privacy.SUBPROCESSORS`. Periksa ulang jika ada vendor yang mengubah kebijakannya.

| Vendor | Temuan | Status / tindakan |
|---|---|---|
| **Streamlit Community Cloud** | [Terms of Use](https://streamlit.io/sharing/terms-of-use) (Nov 2025), Community Cloud Content Addendum butir 4: hanya untuk "personal and non-commercial purposes", dan tidak untuk data dengan perlindungan khusus. Pasal 10: akses bisa dihentikan tanpa pemberitahuan. | **Risiko terbesar.** Ciel menjual Pro di sini. Pindah ke VPS (`docs/superpowers/plans/2026-10-27-ciel-foundation-vps.md`) atau Streamlit berbayar. Sampai pindah, simpan cadangan secrets dan siap deploy ulang. |
| **DeepSeek** | [Kebijakan privasi](https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html) (10 Feb 2026): data disimpan di Tiongkok selama akun ada; input dipakai untuk melatih model, dengan hak opt-out lewat email. [Ketentuan Open Platform](https://cdn.deepseek.com/policies/en-US/deepseek-open-platform-terms-of-service.html) (berlaku 29 Apr 2026) tidak menyebut pelatihan, tidak ada retensi tetap atau zero data retention; Pasal 5.5 menjadikan Ciel pengendali data pengguna. | [ ] Kirim permintaan opt-out pelatihan ke **privacy@deepseek.com** dari email akun API, lalu simpan balasannya di sini. Halaman Privasi sudah menyebut DeepSeek bisa melatih model. |
| **Exa** | [Kebijakan privasi](https://exa.ai/privacy-policy) (29 Jun 2026): "Query Data is used to improve our products". Zero data retention dan DPA hanya untuk paket **Enterprise** ([security](https://docs.exa.ai/reference/security)). | Diterima untuk sekarang; halaman Privasi menyebutnya. Kueri pencarian dibuat agent, tetapi bisa memuat topik pengguna. Pertimbangkan Enterprise jika pengguna bertambah. |
| **Google (Gemini API)** | [Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms), bagian **Paid Services**: prompt dan respons tidak dipakai untuk meningkatkan produk, dicatat sementara hanya untuk mendeteksi penyalahgunaan, dan diproses di bawah *Data Processing Addendum for Products Where Google is a Data Processor*. | [x] Berlaku otomatis selama project Cloud punya billing aktif. Pastikan billing tetap aktif, karena paket gratis memakai data untuk pelatihan. |
| **Supabase** | [DPA](https://supabase.com/legal/dpa) baru mengikat setelah ditandatangani lewat **PandaDoc** yang diminta dari dashboard (Organization > Legal documents). Region project: `ap-northeast-1` (Tokyo). | [ ] Minta dan tandatangani DPA dari dashboard Supabase. |
| **ngrok** | [DPA](https://ngrok.com/dpa) berlaku antara ngrok dan pelanggan yang menyetujui Terms of Service (versi 31 Mar 2023), dengan SCC terlampir. | [x] Berlaku lewat ToS. Lalu lintas Ciel melewati edge ngrok. |
| **Mayar** | Perjanjian merchant saat verifikasi akun (2026-11-01). | [ ] Simpan salinan perjanjian merchant di sini. |
| **Google Fonts, GitHub Pages, Google login** | Kebijakan privasi Google dan GitHub; menerima alamat IP pengunjung. | [x] Disebut di halaman Privasi; tidak perlu DPA terpisah untuk skala ini. |

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
