# Ciel Pro

Paket Pro saat ini berisi satu fitur khusus, **Riset Skripsi**, plus batas pesan lebih tinggi. Pembayaran belum ada; status Pro diberikan pengelola lewat SQL. Rencana berikutnya: pembayaran Midtrans yang menulis tabel yang sama lewat webhook.

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

Fitur ini juga butuh login Google (`[auth]`) dan Supabase (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`), karena status Pro tersimpan di sana. Flow riset juga harus diizinkan di policy ngrok (`tools/render_ngrok_policy.py`).

Catatan: penghitung batas ada di memori proses app dan kembali ke nol saat app restart, sama seperti batas chat biasa.

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

Hapus secret `RESEARCH_FLOW_ID`. Tombol dan dialog hilang, dan chat biasa tidak terpengaruh. Tabel `pro_members` boleh tetap ada. Batas Pro tetap berlaku untuk akun yang ada di tabel itu; kosongkan tabelnya kalau batas Pro juga mau dimatikan.
