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
