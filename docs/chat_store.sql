-- Riwayat chat dan proyek Ciel untuk pengguna yang login (dipakai chat_store.py).
-- Jalankan sekali di Supabase: SQL Editor -> New query -> Run.
--
-- App memakai service key dari secrets (SUPABASE_SERVICE_KEY) dan selalu
-- memfilter per owner. RLS aktif tanpa policy, jadi anon key yang ada di
-- dashboard Supabase tidak bisa membaca tabel-tabel ini.

create table if not exists public.chats (
    owner text not null,
    id text not null,
    title text not null,
    project_id text,
    archived boolean not null default false,
    updated double precision not null,
    messages jsonb not null default '[]'::jsonb,
    primary key (owner, id)
);

create index if not exists chats_owner_updated on public.chats (owner, updated desc);

alter table public.chats enable row level security;

-- Proyek sidebar beserta file-nya (teks hasil ekstraksi; CSV/TSV juga isi
-- tabel utuh untuk Ciel Table Analyst). App membatasi ukuran di sisi upload:
-- maks. MAX_PROJECTS proyek per akun dan MAX_PROJECT_CHARS karakter file per
-- proyek (lihat app.py), jadi satu baris tidak lebih dari beberapa MB.
create table if not exists public.projects (
    owner text not null,
    id text not null,
    name text not null,
    created double precision not null,
    files jsonb not null default '[]'::jsonb,
    primary key (owner, id)
);

alter table public.projects enable row level security;

-- Profil dari halaman Pengaturan (ChatStore.load_profile/save_profile): nama
-- yang dipakai Ciel untuk menyapa dan konteks singkat untuk jawabannya. App
-- membersihkan isinya (satu baris, panjang dibatasi; lihat account_settings.py).
create table if not exists public.profiles (
    owner text primary key,
    full_name text not null default '',
    nickname text not null default '',
    field text not null default '',
    preferences text not null default '',
    updated_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

-- Status Ciel Pro per akun. App hanya membaca (ChatStore.load_pro_until);
-- yang menulis adalah admin lewat SQL di bawah, atau nanti webhook pembayaran.
-- owner = "ID memory" yang tampil di menu akun Ciel (memory_owner_id).
create table if not exists public.pro_members (
    owner text primary key,
    expires_at timestamptz not null,
    source text not null default 'manual',
    updated_at timestamptz not null default now()
);

alter table public.pro_members enable row level security;

-- Beri atau perpanjang Pro 30 hari (ganti ID memory). Perpanjangan dihitung
-- dari masa aktif yang tersisa, bukan dari hari ini:
--
-- insert into public.pro_members (owner, expires_at, source)
-- values ('<ID memory>', now() + interval '30 days', 'manual')
-- on conflict (owner) do update set
--     expires_at = greatest(pro_members.expires_at, now()) + interval '30 days',
--     source = excluded.source,
--     updated_at = now();
--
-- Cabut Pro: update public.pro_members set expires_at = now() where owner = '<ID memory>';

-- Pembelian Pro lewat Midtrans (docs/PRO.md). App membuat satu baris per
-- transaksi Snap (status 'pending'). Hanya Edge Function midtrans-notify
-- yang menandainya lunas, setelah signature dan Status API Midtrans dicek,
-- lewat ciel_settle_order di bawah.
create table if not exists public.pro_orders (
    id text primary key,
    owner text not null,
    amount integer not null,
    status text not null default 'pending',
    midtrans_status text,
    created_at timestamptz not null default now(),
    paid_at timestamptz,
    updated_at timestamptz not null default now()
);

create index if not exists pro_orders_owner on public.pro_orders (owner, created_at desc);

alter table public.pro_orders enable row level security;

-- Lunasi satu order dan tambah Pro 30 hari, dalam satu transaksi database.
-- Idempoten: notifikasi Midtrans yang dikirim ulang untuk order yang sudah
-- lunas tidak menambah masa Pro lagi. Nominal harus sama dengan order.
create or replace function public.ciel_settle_order(
    p_order_id text,
    p_gross_amount numeric,
    p_midtrans_status text
) returns text
language plpgsql
security definer
set search_path = public
as $$
declare
    paid_order public.pro_orders%rowtype;
begin
    select * into paid_order from public.pro_orders where id = p_order_id for update;

    if not found then
        return 'unknown_order';
    end if;

    if paid_order.status = 'paid' then
        return 'already_paid';
    end if;

    if p_gross_amount is distinct from paid_order.amount then
        return 'amount_mismatch';
    end if;

    update public.pro_orders
    set status = 'paid', midtrans_status = p_midtrans_status, paid_at = now(), updated_at = now()
    where id = p_order_id;

    insert into public.pro_members (owner, expires_at, source)
    values (paid_order.owner, now() + interval '30 days', 'midtrans')
    on conflict (owner) do update set
        expires_at = greatest(pro_members.expires_at, now()) + interval '30 days',
        source = 'midtrans',
        updated_at = now();

    return 'paid';
end;
$$;

-- Hanya service key (Edge Function) yang boleh memanggilnya.
revoke execute on function public.ciel_settle_order(text, numeric, text) from public, anon, authenticated;

-- Batas pesan dan kuota harian Pro yang bertahan saat app restart. Satu baris
-- per pesan per key batas (lihat rate_limits_for_request di app.py), `at` =
-- epoch detik. Baris lebih tua dari 24 jam dibuang oleh ciel_rate_limit_hit.
create table if not exists public.rate_limit_hits (
    key text not null,
    at double precision not null
);

create index if not exists rate_limit_hits_key_at on public.rate_limit_hits (key, at);
create index if not exists rate_limit_hits_at on public.rate_limit_hits (at);

alter table public.rate_limit_hits enable row level security;

-- Sama seperti rate_limit_full di app.py. p_limits adalah array JSON
-- [[key, batas, jendela_detik], ...] (array, karena objek jsonb tidak
-- menjaga urutan key dan key pertama yang penuh menentukan pesannya).
-- Jika ada key yang sudah mencapai batas, kembalikan key pertama itu dan jangan
-- catat apa pun. Jika tidak, catat satu baris per key dan kembalikan null.
-- Satu advisory lock membuat hitung-lalu-catat tidak balapan antar proses.
create or replace function public.ciel_rate_limit_hit(
    p_limits jsonb,
    p_now double precision
) returns text
language plpgsql
security definer
set search_path = public
as $$
declare
    item jsonb;
    hits integer;
begin
    perform pg_advisory_xact_lock(727274);

    delete from public.rate_limit_hits where at < p_now - 86400;

    for item in
        select e.value from jsonb_array_elements(p_limits) with ordinality as e(value, n) order by e.n
    loop
        select count(*) into hits
        from public.rate_limit_hits
        where key = item->>0 and at > p_now - (item->>2)::double precision;

        if hits >= (item->>1)::integer then
            return item->>0;
        end if;
    end loop;

    insert into public.rate_limit_hits (key, at)
    select e.value->>0, p_now from jsonb_array_elements(p_limits) as e(value);

    return null;
end;
$$;

-- Hanya service key (app) yang boleh memanggilnya.
revoke execute on function public.ciel_rate_limit_hit(jsonb, double precision) from public, anon, authenticated;
