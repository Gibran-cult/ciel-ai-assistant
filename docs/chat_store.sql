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
