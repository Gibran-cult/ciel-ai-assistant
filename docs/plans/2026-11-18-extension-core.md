# Ekstensi Browser Inti (Fase 3A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ekstensi Chromium Manifest V3 yang bisa login sebagai perangkat, menerima aksi bertiket dari Ciel Agent API, membaca halaman tanpa kolom rahasia, menjalankan aksi di situs yang diizinkan, dan selalu bisa dihentikan, diuji di laptop terhadap layanan agent sungguhan yang memakai model tiruan.

**Architecture:** Kode ekstensi di folder baru `extension/`, TypeScript, dibangun Vite dengan `manifest.json` yang ditulis sendiri (D17). Service worker memegang koneksi WebSocket, token, dan antrean aksi. Content script membaca dan bertindak di tab tugas saja. Side panel React (D18) menampilkan rencana, dialog, log, dan Stop. Setiap aksi diperiksa di klien dulu: tiket Ed25519 (D19), host tab, izin situs, dan daftar target yang selalu diblokir. Kontraknya `docs/agent-protocol.md`, dan nilai bersama (target yang diblokir, pola rahasia, vektor tiket) diambil dari kode Python yang sama dengan server.

**Tech Stack:** TypeScript, Vite, React, Vitest dan Testing Library (jsdom), axe-core, Playwright (Chromium) untuk uji ujung ke ujung, Node 24. Python hanya untuk server uji dan pembuat vektor.

**Spec:** [`docs/agent-architecture.md`](../agent-architecture.md) bagian 4 dan 6. [`docs/agent-protocol.md`](../agent-protocol.md). [`docs/security.md`](../security.md) bagian 2, 3, 5, 7. [`docs/design-system.md`](../design-system.md) bagian 2 sampai 9. [`docs/privacy-consent.md`](../privacy-consent.md) bagian 2. [`docs/decisions.md`](../decisions.md) D10, D17, D18, D19. [`docs/roadmap.md`](../roadmap.md) Fase 3.

## Cakupan

Fase 3 dipecah dua.

| Rencana | Isi | Task roadmap | Butuh |
|---|---|---|---|
| 3A (dokumen ini) | Ekstensi yang bisa dipakai dan diuji di laptop | 3.1 sampai 3.17, 3.19 sampai 3.21, 3.23 | Tidak butuh VPS. Panel dan banner butuh cek pemilik di browser |
| 3B | Uji red-team dengan model sungguhan, halaman Chrome Web Store, rilis ke penguji, dokumen legal agent | 3.22, 3.24 sampai 3.26 | VPS dan staging, akun developer Chrome Web Store, anggaran API, tinjauan ahli hukum |

Task 3.18 (antrean log lokal saat luring) tidak dikerjakan di 3A. Di layanan 2B, tugas berakhir `client_gone` saat koneksi putus, dan koneksi baru tidak bisa melanjutkan tugas lama. Antrean hasil aksi baru berguna setelah server bisa melanjutkan tugas, jadi task ini dipindah ke rencana sesudah 3B bersama fitur lanjut tugas.

## Global Constraints

- Keputusan pemilik: D17 Vite dengan `extension/manifest.json` tulisan sendiri. D18 React dan TypeScript. D19 tiket diperiksa dengan WebCrypto Ed25519, dengan pustaka cadangan untuk browser yang belum mendukungnya.
- Fakta yang dicek 18 November 2026: Chrome mendukung Ed25519 di WebCrypto sejak versi 137. `@noble/ed25519` v2 dan v3 belum diaudit independen (audit Cure53 hanya untuk v1). Pustaka cadangan dipilih di Task 3 dan dicatat sebagai ruling: pustaka dengan audit independen untuk versi yang dipakai, kalau ada [PERLU DICEK `@noble/curves`]. Kalau tidak ada yang memenuhi, cadangan memakai `@noble/ed25519` versi terbaru dan risikonya ditulis di `docs/security.md`.
- Izin manifest persis: `sidePanel`, `storage`, `scripting`, `activeTab`, `identity`, `alarms`, dan `optional_host_permissions: ["https://*/*"]`. Tidak ada `host_permissions` tetap, `debugger`, `tabs`, `history`, `cookies`, `webRequest`, atau `<all_urls>`. Tidak ada `externally_connectable`.
- `minimum_chrome_version` mengikuti versi minimum Side Panel API [PERLU DICEK di dokumentasi Chrome saat Task 1]. Jalur cadangan tiket dipakai di browser antara versi itu dan Chrome 137.
- Tidak ada kode yang diunduh saat berjalan, tidak ada `eval`, tidak ada `unsafe-eval` atau `unsafe-inline` di CSP. Semua huruf dibundel di paket.
- Semua versi paket npm dipatok persis dan dikunci `package-lock.json`. `npm ci` dan `npm audit --audit-level=high` di CI.
- Ekstensi tidak pernah membaca, mengetik, atau mengirim isi kolom kata sandi, kartu, OTP, PIN, atau kolom ber-`autocomplete` pembayaran (`cc-*`, `current-password`, `new-password`, `one-time-code`), apa pun isi tiketnya.
- Nilai bersama diambil dari Python, tidak ditulis ulang tangan: target yang selalu diblokir dari `guard/blocked_targets.json`, vektor pola rahasia dari `guard.risk.find_secrets`, vektor tiket dari `agent_api.tickets`. Berkas vektor dibuat skrip `tools/export_extension_vectors.py` dan CI memeriksa bahwa berkas itu sama dengan hasil skrip.
- Token akses hanya di `chrome.storage.session`, token pembaruan di `chrome.storage.local`. Token tidak pernah masuk log, pesan galat, URL, atau panel.
- Bahasa teks antarmuka mengikuti `docs/design-system.md` bagian 10. Ukuran panel 360px, tetap utuh sampai 320px.
- Perubahan tampilan (panel, banner, badge, dialog) tidak di-commit sebelum pemilik mengecek ekstensi di browsernya dan menulis "commit".
- Komentar kode bahasa Indonesia, nama fungsi dan variabel bahasa Inggris. Pesan commit tanpa baris atribusi alat AI.

## Review Focus

1. **Tab pindah situs di antara tiket dibuat dan aksi dijalankan.** Host tab sekarang tidak sama dengan `ticket.host`: aksi ditolak di klien dan hasilnya `ok: false`. Uji di Task 7.
2. **Halaman berubah setelah dibaca.** Nomor rujukan lama dipakai pada DOM baru: aksi ditolak, tidak mengenai elemen lain. Uji di Task 6.
3. **Stop saat koneksi putus atau saat dialog terbuka.** Antrean kosong, tidak ada aksi lagi, dan `stop` dikirim begitu tersambung. Uji di Task 8.
4. **Isi halaman yang meniru dialog Ciel atau banner.** Halaman tidak bisa membuat, menutup, atau menekan tombol di dialog konfirmasi, karena dialog hanya ada di side panel. Uji di Task 9.
5. **Kolom rahasia yang menyamar.** Kolom `type="text"` dengan `autocomplete="cc-number"` atau `name` berisi `password`, atau kolom di dalam iframe lintas asal, tidak ikut dibaca dan tidak bisa diketik. Uji di Task 5.

---

### Task 1: Kerangka, manifest, CI

**Files:**
- Create: `extension/package.json`, `extension/package-lock.json`, `extension/tsconfig.json`, `extension/vite.config.ts`, `extension/manifest.json`, `extension/src/background.ts` (kosong dulu), `extension/src/content/index.ts`, `extension/src/panel/index.html`, `extension/src/panel/main.tsx`
- Create: `extension/tests/manifest.test.ts`
- Create: `.github/workflows/extension.yml`

**Interfaces:**
- Produces: `npm run build` menghasilkan `extension/dist/` berisi `manifest.json`, `background.js`, `content.js`, `panel/index.html` dan asetnya. `npm test` menjalankan Vitest. `npm run lint` menjalankan `tsc --noEmit` dan ESLint.

- [ ] **Step 1: Tulis uji yang gagal** `extension/tests/manifest.test.ts`:

```ts
test("only the approved permissions", () => {
  expect([...manifest.permissions].sort()).toEqual(["activeTab", "alarms", "identity", "scripting", "sidePanel", "storage"]);
  expect(manifest.optional_host_permissions).toEqual(["https://*/*"]);
  for (const banned of ["host_permissions", "externally_connectable", "web_accessible_resources"]) expect(manifest).not.toHaveProperty(banned);
});
test("content script is not injected everywhere", () => { expect(manifest).not.toHaveProperty("content_scripts"); });
test("the CSP forbids eval and inline script", () => {
  expect(manifest.content_security_policy.extension_pages).toBe("script-src 'self'; object-src 'none'; base-uri 'none'");
});
test("the built manifest equals the source manifest", () => { /* setelah build: dist/manifest.json sama dengan manifest.json */ });
```

- [ ] **Step 2: Jalankan, pastikan gagal.** Run: `cd extension && npm test` Expected: FAIL.
- [ ] **Step 3: Isi kerangka.** Content script disuntikkan lewat `chrome.scripting.executeScript` hanya ke tab tugas (Task 6), jadi manifest tidak punya `content_scripts`. Ikon terang dan gelap dari `assets/brand` (Kepingan).
- [ ] **Step 4: Tulis `extension.yml`**: Node 24, `npm ci`, `npm run lint`, `npm test`, `npm audit --audit-level=high`, `npm run build`, unggah `dist` sebagai artefak. Hanya berjalan kalau `extension/**`, `guard/**`, `agent_api/**`, atau `tools/export_extension_vectors.py` berubah.
- [ ] **Step 5: Jalankan uji dan build.** Expected: OK.
- [ ] **Step 6: Commit.** `git commit -m "Start the browser extension with a locked-down manifest"`

---

### Task 2: Token desain dan tema

**Files:**
- Create: `design/tokens.json` (nilai dari `docs/design-system.md` bagian 2), `extension/scripts/tokens.mjs` (membuat `extension/src/theme.css`), `extension/tests/tokens.test.ts`

**Interfaces:**
- Produces: variabel CSS `--c-*` untuk tema terang (`:root`) dan gelap (`@media (prefers-color-scheme: dark)` dan `[data-theme="dark"]`), termasuk token agent (`--c-agent-active`, `--c-agent-wait`, `--c-stop-bg`, `--c-stop-ink`).

- [ ] **Step 1: Uji yang gagal:** setiap pasangan di tabel rasio kontras `design-system.md` bagian 2 dihitung dari `tokens.json` dengan rumus WCAG dan memenuhi syaratnya (4,5 untuk teks, 3 untuk garis tepi). `theme.css` yang ada di repo sama dengan hasil `tokens.mjs`.
- [ ] **Step 2 sampai 4:** gagal, tulis, lulus.
- [ ] **Step 5: Commit.** `git commit -m "Generate the extension theme from shared design tokens"`

---

### Task 3: Pemeriksa tiket dan vektor bersama

**Files:**
- Create: `tools/export_extension_vectors.py`, `extension/src/shared/vectors/` (`tickets.json`, `secrets.json`, `blocked.json`)
- Create: `extension/src/tickets.ts`, `extension/tests/tickets.test.ts`
- Test: `tests/test_extension_vectors.py` (berkas vektor sama dengan hasil skrip)

**Interfaces:**
- Consumes: `agent_api.tickets.TicketSigner`, `make_ticket`, `verify_ticket`; `guard.risk.find_secrets`, `BLOCKED_HOSTS`, `BLOCKED_APPS`.
- Produces:
  - `canonical(ticket: object): Uint8Array`: JSON dengan kunci terurut di setiap tingkat, tanpa spasi, karakter non-ASCII apa adanya. Sama byte demi byte dengan `json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False)`.
  - `verifyTicket(signed, keys, {task, device, lastSeq, now}): Promise<string | null>`: alasan yang sama persis dengan `verify_ticket` Python (`bad_form`, `unknown_key`, `bad_signature`, `wrong_task`, `wrong_device`, `old_seq`, `expired`).
  - `ed25519Verify(publicKey, signature, message): Promise<boolean>`: WebCrypto dulu; kalau `crypto.subtle.importKey("raw", ..., {name: "Ed25519"})` melempar `NotSupportedError`, pustaka cadangan.
  - `log_text.json`: kalimat aksi, hasil, alasan, dan label rantai dari `agent_log.py`, supaya log di panel sama dengan log di web.
  - `tickets.json`: tiket sah, tiket yang diubah (argumen, host, tanda tangan), nomor urut lama, kedaluwarsa, kunci tak dikenal, rotasi dua kunci, dan teks non-ASCII, masing-masing dengan alasan yang diharapkan dari Python.

- [ ] **Step 1: Uji yang gagal.** Python: `tests/test_extension_vectors.py` memanggil skrip ke folder sementara dan membandingkan dengan berkas di repo. TypeScript: setiap kasus di `tickets.json` menghasilkan alasan yang sama lewat WebCrypto, dan sekali lagi dengan WebCrypto dibuat melempar `NotSupportedError` supaya jalur cadangan teruji.
- [ ] **Step 2: Jalankan, pastikan gagal.**
- [ ] **Step 3: Pilih pustaka cadangan** sesuai Global Constraints, catat versinya dan status auditnya di pesan commit dan ledger. Tulis skrip, `tickets.ts`, dan tambahkan `tests.test_extension_vectors` ke `ci.yml`.
- [ ] **Step 4: Jalankan uji Python dan TypeScript.** Expected: OK.
- [ ] **Step 5: Commit.** `git commit -m "Verify action tickets in the extension against the server's own vectors"`

---

### Task 4: Login perangkat dan penyimpanan token

**Files:**
- Create: `extension/src/auth.ts`, `extension/src/config.ts`, `extension/tests/auth.test.ts`

**Interfaces:**
- Consumes: `docs/agent-protocol.md` bagian 1.
- Produces:
  - `config.ts`: `API_BASE` (produksi `https://agent.ciel-ai.web.id`, staging dan lokal lewat `chrome.storage.local` kunci `apiBase` yang hanya bisa diubah di build pengembangan).
  - `login(): Promise<LoginResult>`: buat verifier (`crypto.getRandomValues`, 64 karakter), challenge SHA-256 base64url, state acak, buka `chrome.identity.launchWebAuthFlow` ke `/v1/device/login` dengan `redirect = chrome.identity.getRedirectURL()`, cocokkan `state`, tangani `error=consent_required` (hasil `{kind: "consent_required"}`, panel mengarahkan ke Pengaturan > Agent di web), tukar kode di `/v1/device/token` dengan `name` dari `navigator.userAgentData` atau "Chrome", `platform: "extension"`.
  - `accessToken(): Promise<string | null>`: dari `chrome.storage.session`, disegarkan lewat `/v1/device/refresh` satu menit sebelum habis (`chrome.alarms`). Galat 401 menghapus semua token dan mengembalikan `null`.
  - `logout()`: hapus token lokal. Mencabut perangkat dilakukan dari web.

- [ ] **Step 1: Uji yang gagal** dengan `chrome` tiruan dan `fetch` tiruan: verifier dan challenge sesuai RFC 7636 (vektor contoh dari RFC [PERLU DICEK nilai lampiran B]); state yang tidak cocok ditolak; `consent_required` dikenali; token akses tidak pernah ditulis ke `storage.local`; refresh yang dijawab 401 menghapus token; tidak ada token di argumen `console.*`.
- [ ] **Step 2 sampai 4:** gagal, tulis, lulus.
- [ ] **Step 5: Commit.** `git commit -m "Register the extension as a device with PKCE"`

---

### Task 5: Pembaca halaman dan penyaring rahasia

**Files:**
- Create: `extension/src/content/reader.ts`, `extension/src/content/redact.ts`, `extension/tests/reader.test.ts`, `extension/tests/redact.test.ts`, `extension/tests/pages/*.html` (halaman contoh)

**Interfaces:**
- Produces:
  - `readPage(doc: Document, maxChars = 20000): Observation`: `{ok: true, source: "page", text, host, controls}` sesuai `agent-protocol.md`. Teks terlihat saja (bukan `display:none`, `visibility:hidden`, `aria-hidden`), nomor rujukan untuk tautan, tombol, kolom isian, dan pilihan. `field_type` dari `type` input dan `autocomplete`; kolom rahasia (`password`, `cc-*`, `one-time-code`, `current-password`, `new-password`, atau `name`/`id` yang memuat `pass`, `otp`, `pin`, `cvv`, `card`) dilaporkan `field_type: "password"` dan isinya tidak pernah dibaca. `submits` benar untuk tombol `submit`, input di dalam `form` tanpa tombol lain, dan tautan ke metode POST. `effect` dari teks dan atribut tombol: `cart_add`, `checkout_prepare`, `form_submit`, `order_cancel`, `download`.
  - Rujukan disimpan di `WeakRef` per `generation`; setiap navigasi atau perubahan DOM besar (MutationObserver, lebih dari 20 node) menaikkan `generation` dan membatalkan rujukan lama.
  - `redact(text): string`: setiap temuan `secrets.json` diganti `[disaring]` sebelum teks keluar dari tab.

- [ ] **Step 1: Uji yang gagal** di jsdom dengan halaman contoh: formulir login (kolom kata sandi tidak terbaca, dilaporkan `password`), checkout (kolom `cc-number` bertipe teks dilaporkan rahasia, tombol "Bayar" punya `effect`), toko (tombol "Tambah ke keranjang" `cart_add`), teks tersembunyi tidak ikut, iframe lintas asal tidak dibaca, setiap kasus `secrets.json` tersaring dengan hasil sama seperti Python, dan halaman yang berubah membatalkan rujukan lama.
- [ ] **Step 2 sampai 4:** gagal, tulis, lulus.
- [ ] **Step 5: Commit.** `git commit -m "Read pages without secret fields and filter secrets before they leave the tab"`

---

### Task 6: Pelaksana aksi

**Files:**
- Create: `extension/src/content/act.ts`, `extension/tests/act.test.ts`

**Interfaces:**
- Consumes: rujukan dan `generation` dari Task 5.
- Produces: `act(tool, args, generation): Observation`. `tab_click`, `form_submit`, `tab_type`, `tab_select`, `tab_scroll`, `tab_read`. Rujukan dari `generation` lama atau elemen yang sudah lepas dari DOM menghasilkan `{ok: false}`. `tab_type` menolak kolom rahasia dengan `{ok: false}` walau tiketnya sah. Setelah aksi, halaman dibaca ulang dan hasilnya dikirim sebagai observasi baru.

- [ ] **Step 1: Uji yang gagal:** klik tombol keranjang di halaman contoh melaporkan `effect: "cart_add"` di observasi sebelumnya, ketik ke kolom kata sandi ditolak, rujukan lama setelah DOM diganti ditolak tanpa mengenai elemen lain, `tab_select` hanya menerima nilai yang ada di daftar.
- [ ] **Step 2 sampai 4:** gagal, tulis, lulus.
- [ ] **Step 5: Commit.** `git commit -m "Run clicks, typing and scrolling by reference, never on secret fields"`

---

### Task 7: Klien WebSocket, izin situs, dan pemeriksaan lokal

**Files:**
- Create: `extension/src/socket.ts`, `extension/src/permissions.ts`, `extension/src/runner.ts`, tests yang sesuai

**Interfaces:**
- Consumes: Task 3 (`verifyTicket`), Task 4 (`accessToken`), Task 5 dan 6 (lewat `chrome.scripting.executeScript` ke tab tugas).
- Produces:
  - `Socket`: sambung ke `wss://.../v1/ws`, kirim `hello`, sambung ulang dengan jeda 1, 2, 4, 8, 30 detik (acak ±20%), validasi setiap pesan server dengan daftar kunci persis, kirim `answer`, `result` (dengan `task` dan `seq`), dan `stop`.
  - `checkAction(ticket, tab): string | null` di `runner.ts`: urutan tetap, alasan pertama yang cocok: `verifyTicket` gagal, host tab tidak sama dengan `ticket.host` (`host_changed`; untuk `tab_open` yang dibandingkan adalah host alamat di `args.url`), host ada di `blocked.json` (`blocked_host`), izin situs belum diberikan (`no_permission`). Aksi yang ditolak tidak dijalankan dan dijawab `{ok: false}`.
  - `ensurePermission(host)`: `chrome.permissions.request({origins: ["https://<host>/*"]})`, hanya dari klik pengguna di panel (aturan Chrome). Tanpa izin, aksi ditolak dan panel menampilkan tombol izin untuk situs itu.
  - Tab tugas: tab aktif saat tugas dimulai. `tab_open` membuka tab baru di jendela yang sama dan menjadikannya tab tugas.

- [ ] **Step 1: Uji yang gagal:** vektor tiket ditolak dengan alasan yang benar; host tab yang berpindah setelah tiket dibuat ditolak (`host_changed`); `klikbca.com` ditolak walau tiketnya sah; tanpa izin situs tidak ada `executeScript`; pesan server dengan kunci tambahan ditutup; sambung ulang memakai token baru; `result` membawa `task` dan `seq` tiket.
- [ ] **Step 2 sampai 4:** gagal, tulis, lulus.
- [ ] **Step 5: Commit.** `git commit -m "Check every ticket, host and site permission before an action runs"`

---

### Task 8: Stop, banner, badge, jeda saat diambil alih, serah terima

**Files:**
- Create: `extension/src/stop.ts`, `extension/src/content/banner.ts`, `extension/src/content/takeover.ts`, `extension/src/handover.ts`, tests yang sesuai

**Interfaces:**
- Produces:
  - `stop()`: antrean aksi dikosongkan, penantian dibatalkan, banner berganti "Dihentikan", lalu `stop` dikirim; kalau koneksi putus, `stop` dikirim saat tersambung lagi dan aksi baru ditolak sampai tugas baru dimulai. Pintasan `Alt+Shift+S` lewat `commands` di manifest (izin `commands` tidak diperlukan, tetapi uji manifest diperbarui untuk kunci `commands`).
  - Banner di dalam Shadow DOM tertutup, menempel di atas tanpa menutupi isi, teks "Tab ini sedang dikontrol Ciel" atau "Giliranmu. Ciel tidak melihat tab ini.", dengan tombol Stop. Badge ikon: kosong, "ON", atau "!" menunggu.
  - `takeover.ts`: klik atau ketikan pengguna sungguhan (`isTrusted`) di tab tugas saat agent bekerja menjeda antrean dan meminta keputusan di panel.
  - `handover.ts`: selama serah terima, pembaca halaman mati; hanya tombol "Lanjutkan" di panel yang menyalakannya lagi.

- [ ] **Step 1: Uji yang gagal:** stop saat luring tidak menjalankan aksi berikutnya dan mengirim `stop` setelah tersambung; banner tidak bisa ditekan atau dihapus oleh skrip halaman (Shadow DOM tertutup, dipasang ulang kalau dihapus); ketikan pengguna menjeda antrean; selama serah terima `readPage` tidak dipanggil.
- [ ] **Step 2 sampai 4:** gagal, tulis, lulus.
- [ ] **Step 5: Berhenti sebelum commit** untuk bagian banner dan badge (tampilan). Logika stop, jeda, dan serah terima boleh di-commit dulu: `git commit -m "Stop the agent on the device first and pause when the user takes over"`.

---

### Task 9: Side panel

**Files:**
- Create: `extension/src/panel/App.tsx`, `SignedOut.tsx`, `Plan.tsx`, `Preview.tsx`, `Confirm.tsx`, `Handover.tsx`, `Log.tsx`, `StopButton.tsx`, `Offline.tsx`, `extension/src/panel/strings.ts`, tests per komponen, `extension/tests/a11y.test.ts`

**Interfaces:**
- Consumes: pesan `plan`, `confirm`, `handover`, `ask`, `end` dari Task 7; `CHAIN_TEXT` dan kalimat aksi diselaraskan dengan `agent_log.py` (vektor dibuat skrip Task 3 ke `extension/src/shared/vectors/log_text.json`).
- Produces:
  - Keadaan: belum masuk (tombol "Masuk dengan Google", dan pesan arahan kalau `consent_required`), masuk tanpa tugas (kolom perintah), tugas berjalan, menunggu kamu, luring ("Koneksi putus. Ciel berhenti dulu sampai tersambung lagi.", Stop tetap aktif).
  - `Plan`: langkah bernomor, lingkup situs, pilihan mode dengan bawaan "Tanya dulu", tombol setara "Mulai" dan "Ubah".
  - `Confirm`: judul berupa efek, alamat lengkap (`prompt.url`), teks yang akan diketik (`prompt.text`), tanda situs tiruan (`prompt.lookalike`) dengan kedua alamat berdampingan, keterangan "diambil dari halaman" kalau `from_page`. Fokus awal di "Batal", Escape sama dengan Batal. Semua teks dari server ditampilkan sebagai teks biasa.
  - `Log`: baris log tugas yang sedang berjalan, dengan kalimat yang sama dengan web.
  - `StopButton`: selalu terlihat di kanan atas, minimal 88 × 44 px, `--c-stop-bg`.

- [ ] **Step 1: Uji yang gagal** dengan Testing Library dan axe: tiga keadaan utama tampil benar; fokus awal dialog di "Batal" dan Escape membatalkan; `<script>` dan tautan Markdown di `prompt.text` tampil sebagai teks; axe tanpa temuan di semua komponen pada tema terang dan gelap; lebar 320px tanpa gulir horizontal.
- [ ] **Step 2 sampai 4:** gagal, tulis, lulus.
- [ ] **Step 5: Berhenti. Jangan commit.** Siapkan build pengembangan dan server lokal Task 10, lalu minta pemilik memasang ekstensi tanpa paket (`chrome://extensions` atau `brave://extensions`, mode pengembang) dan mengecek panel, banner, dan badge. Commit setelah pemilik menulis "commit": `git commit -m "Add the side panel, banner and badge"`.

---

### Task 10: Server lokal, situs tiruan, dan uji ujung ke ujung

**Files:**
- Create: `tools/agent_e2e_server.py`, `extension/tests/e2e/shop/` (situs tiruan statis), `extension/tests/e2e/task.spec.ts`, `extension/playwright.config.ts`

**Interfaces:**
- Consumes: `agent_api.main.create_app` dengan `MemoryStore`, `ScriptedModel`, dan Google tiruan; ekstensi hasil build.
- Produces:
  - `tools/agent_e2e_server.py --port 8611 --origin chrome-extension://<id> --script <berkas naskah>`: layanan agent sungguhan di `127.0.0.1` dengan penyimpanan di memori, model bernaskah, dan endpoint uji `POST /test/device` yang membuat perangkat dan token untuk satu akun uji (hanya ada di skrip ini, tidak di aplikasi produksi).
  - Situs tiruan: halaman formulir pendaftaran dan toko dengan tombol keranjang, disajikan di `127.0.0.1:8612` lewat HTTPS buatan Playwright atau HTTP dengan pengecualian lokal [PERLU DICEK: izin opsional `https://*/*` tidak mencakup `http://127.0.0.1`; uji memakai `--allowlisted-extension-id` atau izin pengembangan khusus build e2e].
  - Uji: satu tugas isi formulir selesai dari rencana sampai laporan, satu tugas dengan konfirmasi R2 yang ditolak, satu tugas yang dihentikan dengan Stop, dan satu halaman bersuntikan yang tidak menghasilkan aksi berbahaya.

- [ ] **Step 1: Tulis uji yang gagal**, jalankan dengan `npx playwright test`. Expected: FAIL.
- [ ] **Step 2: Tulis server dan situs tiruan.**
- [ ] **Step 3: Jalankan.** Expected: empat skenario lulus. Tambah job e2e di `extension.yml` (Chromium headless dengan ekstensi).
- [ ] **Step 4: Commit.** `git commit -m "Run the extension end to end against the real agent service"`

---

### Task 11: Dokumen

**Files:**
- Modify: `docs/roadmap.md` (Fase 3 dipecah 3A dan 3B, 3.18 dipindah), `docs/agent-protocol.md` (klien acuan sudah ada), `docs/security.md` (pustaka cadangan dan status auditnya), `docs/cicd-quality.md` (workflow ekstensi), `RELEASE_CHECKLIST.md` (build ekstensi), `README.md` (cara memasang build pengembangan)

- [ ] **Step 1: Perbarui dokumen** dan pastikan `tests.test_ci_coverage` dan `tests.test_extension_vectors` lulus.
- [ ] **Step 2: Commit.** `git commit -m "Record the extension core in the roadmap and docs"`

---

## Langkah pemilik

1. Mengecek panel, banner, dan badge di browser sendiri (Task 8 dan 9) lalu menulis "commit".
2. Untuk rencana 3B, nanti: akun developer Chrome Web Store, jumlah penguji beta, anggaran uji red-team dengan model sungguhan, dan VPS beserta staging.
