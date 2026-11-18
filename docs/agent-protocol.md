# Protokol Ciel Agent API

Kontrak antara Ciel Agent API (`agent_api/`) dan kliennya: ekstensi browser (Fase 3) dan aplikasi desktop (Fase 5). Server yang menjalankan loop dan mesin kebijakan. Klien hanya menampilkan, bertanya ke pengguna, dan menjalankan aksi yang tiketnya sah.

Alamat produksi `https://agent.ciel-ai.web.id`, staging `https://agent-staging.ciel-ai.web.id`.

## 1. Login perangkat

Setiap pemasangan ekstensi atau desktop adalah satu perangkat. Login memakai akun Google yang sama dengan web, dengan PKCE antara perangkat dan layanan.

1. Klien membuat `verifier` acak (43 sampai 128 karakter `A-Z a-z 0-9 . _ ~ -`) dan `challenge = base64url(sha256(verifier))` tanpa padding (43 karakter).
2. Klien membuka browser ke `GET /v1/device/login?challenge=...&redirect=...&state=...`.
   - `redirect` harus persis salah satu alamat terdaftar di server (`AGENT_DEVICE_REDIRECTS`). Ekstensi memakai `https://<id-ekstensi>.chromiumapp.org/` lewat `chrome.identity.launchWebAuthFlow`. Desktop memakai skema sendiri, misalnya `ciel://auth`.
   - `state` adalah teks acak klien (1 sampai 128 karakter `A-Z a-z 0-9 . _ ~ -`), untuk dicocokkan saat kembali.
3. Pengguna login di Google. Server kembali ke `redirect?code=cdc1...&state=<state klien>`. Kode berlaku 60 detik dan hanya sekali pakai.
   Kalau akun itu belum mengaktifkan agent di Pengaturan > Agent di web, server kembali ke `redirect?error=consent_required&state=<state klien>` tanpa kode. Klien menampilkan ajakan untuk mengaktifkan agent di web, lalu login lagi. Persetujuan dicek lagi saat kode ditukar di `/v1/device/token` (403 `consent_required`).
4. Klien menukar kode: `POST /v1/device/token` dengan JSON `{"code", "verifier", "name", "platform"}`. `name` 1 sampai 60 karakter, `platform` `extension` atau `desktop`. Jawabannya `{"device", "access_token", "refresh_token", "expires_in": 900}`.
5. Token akses berlaku 15 menit. Sebelum habis, klien memanggil `POST /v1/device/refresh` dengan `{"refresh_token"}` dan menerima pasangan baru. Token pembaruan hanya bisa dipakai sekali. Kalau token lama dipakai lagi, perangkat itu dicabut.

Penyimpanan token: desktop di Windows Credential Manager atau macOS Keychain. Ekstensi menyimpan token akses di memori sesi dan token pembaruan di penyimpanan ekstensi (`docs/security.md` bagian 7). Token tidak pernah ditulis ke log klien.

Endpoint lain dengan `Authorization: Bearer <token akses>`:

| Endpoint | Isi |
|---|---|
| `GET /v1/devices` | Daftar perangkat akun ini: `id`, `name`, `platform`, `created_at`, `last_seen_at`, `revoked` |
| `DELETE /v1/devices/{id}` | Cabut satu perangkat. 204, atau 404 kalau tidak ada |
| `GET /v1/ticket-keys` (tanpa token) | Kunci publik tiket: `[{"kid", "alg": "Ed25519", "key"}]` |
| `GET /healthz` (tanpa token) | 200 kalau layanan siap |

Login, callback, token, dan refresh dibatasi 10 permintaan per 10 menit per alamat IP (429).

Endpoint HTTP mengirim header CORS hanya untuk origin yang terdaftar di `AGENT_WS_ORIGINS`, tanpa cookie. Ekstensi tidak punya izin host tetap untuk layanan ini, jadi tanpa header itu browser tidak membiarkan jawabannya terbaca.

## 2. WebSocket

`wss://<host>/v1/ws`. Kalau klien mengirim header `Origin`, nilainya harus persis salah satu `AGENT_WS_ORIGINS` (ekstensi: `chrome-extension://<id>`). Klien tanpa `Origin` (desktop) diterima, karena autentikasinya dari token.

Token tidak pernah dikirim di URL. Pesan pertama harus `hello` dalam 10 detik.

| Arah | `type` | Kunci lain (persis) | Balasan |
|---|---|---|---|
| Klien | `hello` | `token`, `client` (`extension` atau `desktop`), `version` (`x.y.z`) | `ready` dengan `device` |
| Klien | `start` | `instruction` (1 sampai 2.000 karakter), dan boleh `page`: bacaan tab yang sedang dibuka, dengan bentuk `observation` (bagian berikut) | Tugas dimulai. Kalau sudah ada tugas berjalan: `end` dengan status `refused`, alasan `busy`. Kalau agent sedang dimatikan atau plafon biaya harian terlewati: `end` dengan status `refused`, alasan `agent_off` atau `cost_cap`. Kalau persetujuan agent sudah ditarik atau versinya naik: `end` dengan status `refused`, alasan `consent_required`. Token dan perangkat diperiksa lagi di setiap `start`: token kedaluwarsa atau perangkat yang dicabut menutup koneksi dengan 4401 |
| Server | `plan` | `id`, `steps`, `scope` (`hosts`, `kinds`, `spend_cap`, dan `start_host`: situs tab awal yang masuk lingkup, atau `null`) | `answer` dengan `id` dan `value`: `"ask"`, `"auto"`, atau `null` untuk menolak |
| Server | `confirm` | `id`, `prompt` | `answer` dengan `value` `true` atau `false` |
| Server | `handover` | `id`, `prompt` | `answer` dengan `value` `true` (pengguna sudah mengerjakannya sendiri) atau `false` |
| Server | `ask` | `id`, `question` | `answer` dengan `value` teks |
| Server | `action` | `ticket`, `kid`, `sig` | `result` dengan `task` dan `seq` (sama dengan `ticket.task` dan `ticket.seq`) dan `observation` |
| Server | `end` | `task` (nomor tugas, atau `null` kalau `start` ditolak sebelum tugas dibuat), `status`, `reason`, `steps`, `report` | Tidak ada |
| Klien | `stop` | Tidak ada | Tugas berakhir `stopped`. Server menolak semua aksi berikutnya |

Pesan yang bukan JSON, lebih dari 256 KB, `type`-nya tidak dikenal, atau membawa kunci di luar daftar di atas menutup koneksi dengan kode 4400. Balasan dengan `id` atau `seq` yang tidak sedang ditunggu diabaikan.

Nomor urut mulai lagi dari 1 di setiap tugas, karena itu `result` wajib membawa `task`. Hasil untuk tugas yang sudah selesai diabaikan.

Kode penutupan lain: 4401 token tidak sah atau perangkat dicabut (dicek saat `hello` dan setiap `start`), 4403 `Origin` tidak terdaftar, 4408 tidak ada `hello`, 4426 versi klien di bawah `AGENT_MIN_CLIENT_VERSION` (klien harus diperbarui).

Batas waktu menunggu balasan: rencana dan pertanyaan 300 detik, konfirmasi dan serah terima 130 detik (jawaban setelah 120 detik tidak berlaku), hasil aksi 60 detik. Yang lewat batas dihitung "tidak".

### Isi `prompt`

`tool`, `target` (host, aplikasi, atau folder), `level` (`R1` sampai `R3`), `reason`, `widens` (situs atau jenis aksi yang akan ditambahkan ke lingkup tugas, atau `null`), `from_page` (tujuan berasal dari isi halaman), `url`, `ref`, `text` (awal teks yang akan diketik, paling banyak 200 karakter, kosong di serah terima), `lookalike` (situs di lingkup tugas yang namanya ditiru situs tujuan).

### Isi `observation`

```json
{"ok": true, "source": "page", "text": "...", "host": "shopee.co.id",
 "controls": {"5": {"field_type": null, "submits": false, "effect": null}}}
```

`source` salah satu `page`, `file`, `screen`, `listing`, `tool`. `controls` memetakan nomor rujukan (teks angka) ke fakta kontrol. `submits` yang tidak dilaporkan dihitung mengirim data. `field_type` yang tidak dilaporkan dihitung kolom rahasia. `effect` diisi untuk tombol yang menambah ke keranjang, checkout, mengirim, membatalkan, atau mengunduh. Kunci di luar daftar ini membuat hasilnya ditolak dan langkahnya dihitung gagal.

## 3. Tiket aksi

```json
{"ticket": {"v": 1, "task": "...", "device": "...", "seq": 3, "tool": "tab_click",
            "args": {"ref": 5}, "host": "shopee.co.id", "exp": 1795000060},
 "kid": "0123456789abcdef", "sig": "<base64url>"}
```

`sig` adalah tanda tangan Ed25519 atas `JSON.stringify` tiket dengan kunci terurut dan tanpa spasi (bentuk yang sama dengan `json.dumps(ticket, sort_keys=True, separators=(",", ":"), ensure_ascii=False)` di `agent_api/tickets.py`).

## 4. Aturan wajib di klien

- Periksa setiap tiket sebelum menjalankan aksi, dengan aturan yang sama dengan `verify_ticket` di `agent_api/tickets.py`: kunci dikenal, tanda tangan cocok, `task` dan `device` sesuai, `seq` lebih besar dari tiket terakhir, dan belum lewat `exp`. Tiket yang gagal tidak dijalankan.
- Tolak aksi kalau host tab sekarang berbeda dari `ticket.host`.
- Nomor rujukan kontrol dibatalkan setiap halaman berubah. Rujukan lama tidak dipakai lagi.
- Isi dialog, pertanyaan, dan laporan ditampilkan sebagai teks biasa, tanpa tautan atau gambar aktif.
- Stop bekerja di perangkat dulu: klien mengosongkan antrean dan melepas kontrol tanpa menunggu server, lalu mengirim `stop`.
- Kolom kata sandi, kartu, dan pembayaran tidak pernah dibaca atau diisi klien, apa pun isi tiketnya.

## 5. Klien acuan

Ekstensi di `extension/` adalah klien acuan untuk protokol ini: `src/tickets.ts` memeriksa tiket dengan vektor yang dibuat dari `agent_api/tickets.py`, `src/socket.ts` menangani koneksi dan sambung ulang, `src/runner.ts` memeriksa tiket, host tab, daftar blokir, dan izin situs sebelum setiap aksi, dan `src/content/reader.ts` membuat `observation`. Kontrol di teks halaman ditulis `[ref N: ...]`.

Halaman awal (task 3.27, keputusan D20): `page` di `start` dikirim hanya untuk tab https di situs yang tidak diblokir dan sudah diizinkan. Layanan memeriksanya seperti `observation` di `result` (bentuk yang salah menutup koneksi 4400), memasukkan host-nya ke lingkup kalau `allowed_host` menerimanya, dan baru memberikan isinya ke model setelah rencana disetujui. Perencana tetap hanya membaca perintah. `page` yang `ok`-nya `false` atau `null` sama dengan tanpa halaman.

`end` dengan `task` dari tugas yang sudah ditinggalkan klien (Stop atau tugas baru) diabaikan selama tugas baru berjalan.
