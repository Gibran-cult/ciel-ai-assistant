# Ciel Pro

Paket Pro berisi satu fitur khusus, **Riset Skripsi**, plus batas pesan lebih tinggi. Pengguna membelinya sendiri lewat Midtrans (sekali bayar Rp79.000 = Pro 30 hari, tanpa tagihan otomatis), atau pengelola memberikannya lewat SQL.

## Cara kerja

- Status Pro disimpan di tabel Supabase `pro_members` (skema di `docs/chat_store.sql`). Satu baris per akun berisi `owner` dan `expires_at`.
- `owner` adalah **ID memory** yang tampil di menu akun Ciel (`memory_owner_id()`, hash dari akun Google). Pengguna bisa menyalinnya dari menu akun untuk pengelola.
- App hanya membaca tabel ini (`ChatStore.load_pro_until`):
  - Tampilan (label tombol, baris "Paket" di menu akun) memakai cache 5 menit per sesi.
  - Setiap permintaan Riset Skripsi membaca ulang dari database sebelum kuota dipakai (`riset_refusal` di `app.py`). Akun gratis yang mengirim permintaan buatan sendiri tetap ditolak di server.
  - Kalau database tidak bisa dibaca, Riset Skripsi ditolak dengan pesan "Status Pro belum bisa diperiksa".

## Konfigurasi (Streamlit secrets)

| Nama | Wajib | Default | Fungsi |
|---|---|---|---|
| `RESEARCH_FLOW_ID` | ya, untuk fitur ini | – | ID flow "Ciel Riset Skripsi" di Langflow. Tanpa ini tombol Riset Skripsi tidak tampil. |
| `RESEARCH_SEARCH_ID` | tidak | `CielScholarSearch-r1s3t` | ID komponen pencarian di flow itu, penerima tweak `start_published_date` (awal rentang tahun sumber, difilter oleh Exa). |
| `RATE_LIMIT_PER_HOUR_PRO` | tidak | 150 | Pesan per jam untuk akun Pro. |
| `RATE_LIMIT_PER_DAY_PRO` | tidak | 800 | Pesan per hari untuk akun Pro. |
| `RISET_SKRIPSI_PER_DAY` | tidak | 5 | Riset Skripsi per hari per akun. |
| `MIDTRANS_SERVER_KEY` | ya, untuk pembelian | – | Server key Midtrans. Akun baru memakai awalan `Mid-server-` di sandbox maupun produksi (akun lama: `SB-Mid-server-` untuk sandbox); lingkungannya ditentukan `MIDTRANS_PRODUCTION`. Tanpa ini Pro tampil sebagai "sedang disiapkan". |
| `MIDTRANS_PRODUCTION` | tidak | `false` | `true` memakai akun produksi Midtrans. |
| `APP_URL` | disarankan | alamat yang sedang dibuka | Alamat publik app, tujuan kembali setelah bayar (`<APP_URL>/?page=pricing`). |

Fitur ini juga butuh login Google (`[auth]`) dan Supabase (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`), karena status Pro tersimpan di sana. Flow riset juga harus diizinkan di policy ngrok (`tools/render_ngrok_policy.py`).

Catatan: penghitung batas ada di memori proses app dan kembali ke nol saat app restart, sama seperti batas chat biasa.

## Pembelian lewat Midtrans

```
Pricing: "Beli Pro 30 hari"
  -> app: baris pro_orders (pending) + transaksi Snap (server key, nominal Rp79.000)
  -> pengguna membayar di halaman Midtrans (QRIS, e-wallet, VA), lalu kembali ke Pricing
Midtrans -> Supabase Edge Function midtrans-notify
  -> cek signature (sha512 order_id + status_code + gross_amount + server key)
  -> ambil ulang status dari Status API Midtrans
  -> lunas: ciel_settle_order (sekali per order, nominal harus sama) -> pro_members +30 hari
  -> gagal/kedaluwarsa: status order dicatat
```

- App **tidak pernah** memberi Pro dari parameter URL saat pengguna kembali. Halaman Pricing membaca order terakhir akun itu dari database (2 jam terakhir) dan status Pro yang dibaca ulang.
- Order yang belum dibayar kedaluwarsa setelah 60 menit.
- Pembelian berikutnya menambah 30 hari dari sisa masa aktif.
- Refund atau chargeback hanya dicatat di `pro_orders.midtrans_status`. Pencabutan Pro diputuskan pengelola (SQL di bawah).
- Logika notifikasi ada di `supabase/functions/midtrans-notify/notification.js` dan dites dengan `node --test supabase/functions/midtrans-notify/notification.test.mjs`.

### Menyiapkan (sekali, sandbox dulu)

1. Daftar di dashboard.midtrans.com sebagai **Merchant**. Pindah ke mode **Sandbox** dan salin **Server Key** dari halaman kunci akses (Access Keys) ke `MIDTRANS_SERVER_KEY` di `.streamlit/secrets.toml`, di atas bagian `[auth]` (di bawahnya, TOML membacanya sebagai `auth.MIDTRANS_SERVER_KEY`).
2. Jalankan bagian `pro_orders` dan `ciel_settle_order` dari `docs/chat_store.sql` di Supabase → SQL Editor.
3. Deploy Edge Function dari folder repo:
   ```bash
   npx supabase login
   python -c "import toml,subprocess; k=toml.load('.streamlit/secrets.toml')['MIDTRANS_SERVER_KEY']; subprocess.run(['npx','supabase','secrets','set','--project-ref','<ref>','MIDTRANS_SERVER_KEY='+k,'MIDTRANS_PRODUCTION=false'],check=True,shell=True)"
   npx supabase functions deploy midtrans-notify --project-ref <ref> --no-verify-jwt
   ```
   Perintah kedua mengambil key dari `secrets.toml`, jadi tidak ada key atau placeholder yang disalin tangan. Pada tes pertama (2026-10-19), secret function sempat berisi teks placeholder sehingga setiap notifikasi ditolak 403. Cek kecocokannya tanpa membuka nilai: digest `MIDTRANS_SERVER_KEY` di `npx supabase secrets list --project-ref <ref>` harus sama dengan `python -c "import toml,hashlib;print(hashlib.sha256(toml.load('.streamlit/secrets.toml')['MIDTRANS_SERVER_KEY'].encode()).hexdigest())"`.
   `<ref>` adalah bagian depan `SUPABASE_URL` (`https://<ref>.supabase.co`). `--no-verify-jwt` wajib karena Midtrans tidak mengirim token Supabase; keamanannya ada di signature dan Status API.
4. Di pengaturan dashboard Midtrans, isi **Payment Notification URL** dengan `https://<ref>.supabase.co/functions/v1/midtrans-notify`.
5. Tambah secrets app: `MIDTRANS_SERVER_KEY`, `APP_URL` (dan `MIDTRANS_PRODUCTION = "true"` hanya setelah produksi siap).
6. Tes sandbox: beli Pro dengan akun tes, lalu bayar di **simulator.sandbox.midtrans.com** (pilih metode yang sama, tempel nomor VA atau QR). Jangan pakai aplikasi bank asli: nomor VA sandbox tidak terdaftar di bank ("Kode Perusahaan Tidak Ada"). Pricing harus menampilkan "Pembayaran diterima. Ciel Pro aktif sampai …" dan `pro_orders` berstatus `paid`.

Pindah ke produksi (dilakukan 2026-10-19): ulangi langkah 3–5 dengan server key produksi dan `MIDTRANS_PRODUCTION=true` di kedua tempat (secrets function dan secrets app). Isi juga Payment Notification URL di dashboard mode **Production**, karena pengaturan sandbox dan produksi terpisah.

Akun Midtrans baru memakai awalan `Mid-server-` di sandbox maupun produksi, jadi pastikan key-nya benar-benar produksi sebelum dipasang. Perintah di bawah meminta key tanpa menampilkannya, mengeceknya ke Status API produksi, lalu memasangnya di function hanya jika produksi menerimanya:

```bash
python -c "import getpass,requests,subprocess,hashlib; k=getpass.getpass('Server key produksi: ').strip(); st=lambda h: requests.get(h+'/v2/'+'0'*32+'/status',auth=(k,''),timeout=20).json().get('status_code'); p=st('https://api.midtrans.com'); print('production:', 'OK' if p=='404' else 'DITOLAK ('+str(p)+')', '| digest', hashlib.sha256(k.encode()).hexdigest()[:12]); assert p=='404', 'bukan key produksi, berhenti'; r=subprocess.run(['npx','--yes','supabase','secrets','set','--project-ref','<ref>','MIDTRANS_SERVER_KEY='+k,'MIDTRANS_PRODUCTION=true'],shell=True); print('exit', r.returncode)"
```

Lalu redeploy function, dan pastikan digest `MIDTRANS_SERVER_KEY` di `npx supabase secrets list` sama dengan digest key di secrets Streamlit Cloud.

```sql
-- Order 7 hari terakhir.
select id, owner, amount, status, midtrans_status, created_at, paid_at
from public.pro_orders where created_at > now() - interval '7 days' order by created_at desc;
```

## Memberi, memperpanjang, dan mencabut Pro

Jalankan di Supabase → SQL Editor. Ganti `<ID memory>` dengan ID dari menu akun pengguna.

```sql
-- Beri Pro 30 hari, atau perpanjang 30 hari dari sisa masa aktif.
insert into public.pro_members (owner, expires_at, source)
values ('<ID memory>', now() + interval '30 days', 'manual')
on conflict (owner) do update set
    expires_at = greatest(pro_members.expires_at, now()) + interval '30 days',
    source = excluded.source,
    updated_at = now();

-- Cabut Pro sekarang.
update public.pro_members set expires_at = now() where owner = '<ID memory>';

-- Lihat semua akun Pro yang masih aktif.
select owner, expires_at, source from public.pro_members where expires_at > now() order by expires_at;
```

Perubahan terlihat di menu akun paling lambat 5 menit kemudian, dan langsung berlaku saat pengguna menjalankan Riset Skripsi.

## Rollback

Pembelian: hapus secret `MIDTRANS_SERVER_KEY` dari app. Pro kembali tampil sebagai "sedang disiapkan", dan Pro yang sudah dibeli tetap berlaku sampai masanya habis. Notifikasi Midtrans yang tertunda tetap diproses oleh Edge Function.

Riset Skripsi: hapus secret `RESEARCH_FLOW_ID`. Tombol dan dialog hilang, dan chat biasa tidak terpengaruh. Tabel `pro_members` boleh tetap ada. Batas Pro tetap berlaku untuk akun yang ada di tabel itu; kosongkan tabelnya kalau batas Pro juga mau dimatikan.
