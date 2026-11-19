# Lisensi aset

Asal dan lisensi setiap gambar dan huruf yang dipakai Ciel AI (roadmap 0.14). `tests/test_asset_licenses.py` gagal kalau ada folder gambar atau huruf baru yang belum dicatat di sini.

## Huruf

| Huruf | Dipakai di | Cara dimuat | Lisensi | Sumber catatan |
|---|---|---|---|---|
| Fraunces | Aplikasi Streamlit, landing, website | Google Fonts | SIL Open Font License 1.1 | `docs/LEGAL.md` bagian 8 |
| Geist | Aplikasi Streamlit, landing, website, panel ekstensi | Google Fonts; di ekstensi dibundel dari paket npm `geist` 1.8.2 | SIL Open Font License 1.1 | `docs/LEGAL.md` bagian 8, teks lisensi di `extension/public/licenses/Geist-OFL.txt` |
| Geist Mono | Panel ekstensi (domain dan kode) | Dibundel dari paket npm `geist` 1.8.2 | SIL Open Font License 1.1 | Paket yang sama dengan Geist, teks lisensi di `extension/public/licenses/Geist-OFL.txt` |

Lisensi OFL 1.1 mengizinkan huruf dibundel dan dibagikan bersama perangkat lunak, asalkan teks lisensinya ikut. Untuk ekstensi, teks itu ada di paket (`licenses/Geist-OFL.txt`).

## Gambar

| Folder | Isi | Asal | Lisensi |
|---|---|---|---|
| `assets/brand/` | Logo Ciel (Kepingan) dan ikon 32, 192, 512 px | Karya Ciel sendiri, dibuat untuk proyek ini (`docs/LEGAL.md` bagian 8) | Milik Ciel AI |
| `extension/public/icons/` | Ikon ekstensi 16, 32, 48, 128 px | Diperkecil dari `assets/brand/ciel-icon-512.png` (rencana 3A, Task 1) | Milik Ciel AI |
| `landing/` | Ikon 192 dan 512 px, `ciel-icon.svg`, gambar pratinjau tautan `og.png` | Ikon disalin dari `assets/brand/`. `og.png` dirender dari `assets/brand/og-card.html` yang dibuat untuk proyek ini (rencana domain dan pencarian, 27 Oktober 2026) | Milik Ciel AI |
| `website/public/` | Ikon, `og.png`, dan gambar diam robot (`robot-bust.webp`, `robot-bust-closing.webp`, `robot-palsu.webp`) | Ikon dari `assets/brand/`. Gambar robot ditangkap dari adegan three.js robot yang dibangun dengan kode di `website/` (`website/README.md`). Cara `og.png` website dibuat tidak tercatat [PERLU DICEK] | Milik Ciel AI; `og.png` website [PERLU DICEK] |
| `tests/assets/` | `vision_math_small.png`, gambar soal matematika untuk uji alur Vision | Diunggah pemilik lewat GitHub pada 3 Oktober 2026; asal gambarnya tidak tercatat [PERLU DICEK] | [PERLU DICEK] |

## Menambah aset

Catat asal dan lisensinya di sini pada commit yang sama. Gambar dari pihak ketiga hanya dipakai kalau lisensinya mengizinkan penggunaan komersial, dan sumbernya ditulis.
