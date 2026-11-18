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

-- Bukti persetujuan Syarat dan Ketentuan serta Kebijakan Privasi (UU PDP
-- Pasal 22-24): satu baris per akun per versi (terms.LEGAL_VERSION), ditulis
-- saat pengguna menekan "Setuju dan lanjut" (ChatStore.save_consent). Baris
-- ini sengaja tidak ikut terhapus oleh "Hapus akun": isinya hanya kode akun,
-- versi, dan waktu.
create table if not exists public.consents (
    owner text not null,
    version text not null,
    accepted_at timestamptz not null default now(),
    primary key (owner, version)
);

alter table public.consents enable row level security;

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

-- Pembelian Pro lewat Midtrans atau Mayar (docs/PRO.md). App membuat satu
-- baris per transaksi (status 'pending'). Hanya Edge Function midtrans-notify
-- atau mayar-notify yang menandainya lunas, setelah status dicek ulang ke API
-- penyedia, lewat ciel_settle_order di bawah.
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

-- Penyedia pembayaran order ini ('midtrans' atau 'mayar'). Untuk Mayar,
-- provider_ref = id payment request dan provider_tx = transactionId dari
-- respons pembuatan; Edge Function mayar-notify mencari order lewat keduanya.
-- Kolom midtrans_status tetap bernama begitu (tabel sudah live) tapi berisi
-- status dari penyedia mana pun.
alter table public.pro_orders add column if not exists provider text not null default 'midtrans';
alter table public.pro_orders add column if not exists provider_ref text;
alter table public.pro_orders add column if not exists provider_tx text;

create unique index if not exists pro_orders_provider_ref
    on public.pro_orders (provider_ref) where provider_ref is not null;
create unique index if not exists pro_orders_provider_tx
    on public.pro_orders (provider_tx) where provider_tx is not null;

-- Lunasi satu order dan tambah Pro 30 hari, dalam satu transaksi database.
-- Idempoten: notifikasi yang dikirim ulang untuk order yang sudah lunas
-- tidak menambah masa Pro lagi. Nominal harus sama dengan order.
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
    values (paid_order.owner, now() + interval '30 days', paid_order.provider)
    on conflict (owner) do update set
        expires_at = greatest(pro_members.expires_at, now()) + interval '30 days',
        source = paid_order.provider,
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

-- ============================================================
-- Ciel Agent (docs/security.md). Tabel di bawah belum dipakai app;
-- pengisinya adalah Ciel Agent API (docs/roadmap.md Fase 2).
-- ============================================================

-- Log aksi agent. Hanya ditambah; setiap baris memuat hash baris sebelumnya
-- (guard/audit.py), jadi baris yang diubah atau dihapus akan ketahuan.
create table if not exists public.agent_actions (
    owner text not null,
    task text not null,
    seq integer not null check (seq >= 1),
    device text not null,
    kind text not null,
    target text not null,
    level text not null check (level in ('R0', 'R1', 'R2', 'R3')),
    decision text not null check (decision in ('allow', 'confirm', 'block', 'handover')),
    reason text,
    approved_by text,
    result text,
    -- Teks yang sama persis dengan yang ikut di-hash. Kalau disimpan sebagai
    -- timestamptz, Postgres mencetaknya ulang dengan format lain dan rantai
    -- hash terbaca rusak. Tanpa nilai bawaan: waktunya ditentukan penulis log.
    at text not null,
    prev_hash text not null,
    hash text not null,
    primary key (owner, task, seq)
);

alter table public.agent_actions enable row level security;

-- Batas belanja per akun. 0 berarti fitur pembelian mati.
create table if not exists public.spend_limits (
    owner text primary key,
    per_tx bigint not null default 0 check (per_tx >= 0),
    per_month bigint not null default 0 check (per_month >= 0),
    updated_at timestamptz not null default now()
);

alter table public.spend_limits enable row level security;

-- Konfirmasi pembelian sekali pakai (guard/purchase.py). month memakai
-- zona Asia/Jakarta, sama dengan guard/limits.py.
create table if not exists public.purchase_confirmations (
    nonce text primary key,
    owner text not null,
    digest text not null,
    total bigint not null check (total > 0),
    month text not null,
    expires_at timestamptz not null,
    used_at timestamptz,
    paid_at timestamptz
);

alter table public.purchase_confirmations enable row level security;

-- Dipakai untuk menjumlah belanja satu akun dalam satu bulan.
create index if not exists purchase_confirmations_owner_month
    on public.purchase_confirmations (owner, month);

-- Riwayat persetujuan dan penarikannya (docs/privacy-consent.md). Hanya ditambah.
create table if not exists public.consent_events (
    id bigint generated always as identity primary key,
    owner text not null,
    kind text not null,
    choice jsonb not null,
    version text not null,
    surface text not null,
    created_at timestamptz not null default now()
);

alter table public.consent_events enable row level security;

-- Log aksi dan riwayat persetujuan tidak boleh diubah setelah ditulis.
-- Menghapus tetap bisa, untuk Hapus akun dan masa simpan.
create or replace function public.ciel_reject_update()
returns trigger
language plpgsql
as $$
begin
    raise exception 'baris di % tidak boleh diubah', tg_table_name;
end;
$$;

drop trigger if exists agent_actions_no_update on public.agent_actions;
create trigger agent_actions_no_update
    before update on public.agent_actions
    for each row execute function public.ciel_reject_update();

drop trigger if exists consent_events_no_update on public.consent_events;
create trigger consent_events_no_update
    before update on public.consent_events
    for each row execute function public.ciel_reject_update();

-- Keadaan tugas agent (agent_api/store.py). Satu akun hanya boleh punya satu
-- tugas aktif; indeks unik di bawah yang menjaganya, tanpa balapan.
create table if not exists public.agent_tasks (
    owner text not null,
    id text not null,
    device text not null,
    instruction text not null,
    plan jsonb not null default '{}'::jsonb,
    scope jsonb not null default '{}'::jsonb,
    mode text not null default 'ask' check (mode in ('ask', 'auto')),
    status text not null default 'planning' check (status in ('planning', 'running', 'done', 'stopped', 'failed')),
    reason text,
    steps integer not null default 0 check (steps >= 0),
    cost bigint not null default 0 check (cost >= 0),
    head_hash text not null default '',
    stop_requested boolean not null default false,
    created_at timestamptz not null default now(),
    primary key (owner, id)
);

alter table public.agent_tasks enable row level security;

create unique index if not exists agent_tasks_one_active
    on public.agent_tasks (owner) where status in ('planning', 'running');
create index if not exists agent_tasks_created on public.agent_tasks (created_at);

-- Jumlah biaya model semua tugas sejak p_since, untuk plafon harian.
create or replace function public.ciel_agent_cost_since(p_since timestamptz)
returns bigint
language sql
security definer
set search_path = public
as $$
    select coalesce(sum(cost), 0)::bigint from public.agent_tasks where created_at >= p_since;
$$;

-- Hanya service key (Ciel Agent API) yang boleh memanggilnya.
revoke execute on function public.ciel_agent_cost_since(timestamptz) from public, anon, authenticated;

-- Ciel Agent API, rencana 2B. Perangkat (ekstensi atau desktop) milik satu
-- akun, dan tokennya. Token hanya disimpan sebagai hash SHA-256.
create table if not exists public.agent_devices (
    owner text not null,
    id text not null,
    name text not null check (char_length(name) between 1 and 60),
    platform text not null check (platform in ('extension', 'desktop')),
    created_at timestamptz not null default now(),
    last_seen_at timestamptz,
    revoked_at timestamptz,
    primary key (owner, id)
);

alter table public.agent_devices enable row level security;

create table if not exists public.agent_device_tokens (
    owner text not null,
    hash text not null check (hash ~ '^[0-9a-f]{64}$'),
    kind text not null check (kind in ('code', 'access', 'refresh')),
    device text,
    challenge text,
    redirect text,
    expires_at timestamptz not null,
    used_at timestamptz,
    created_at timestamptz not null default now(),
    primary key (owner, hash)
);

alter table public.agent_device_tokens enable row level security;

create index if not exists agent_device_tokens_expires on public.agent_device_tokens (expires_at);

-- Waktu aktivitas terakhir tugas, untuk pembersih tugas macet. Diisi
-- database di setiap perubahan baris, jadi loop tidak perlu mengirimnya.
alter table public.agent_tasks add column if not exists updated_at timestamptz not null default now();

create or replace function public.ciel_touch_updated_at()
returns trigger
language plpgsql
set search_path = public
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists agent_tasks_touch on public.agent_tasks;
create trigger agent_tasks_touch
    before update on public.agent_tasks
    for each row execute function public.ciel_touch_updated_at();

create index if not exists agent_tasks_active_updated on public.agent_tasks (updated_at) where status in ('planning', 'running');

-- Tutup tugas yang tidak bergerak lebih dari p_idle_seconds. Stop dan status
-- dipasang dalam satu pernyataan, jadi loop yang ternyata masih hidup
-- melihat stop di aksi berikutnya. Token yang sudah lewat sehari dibuang.
create or replace function public.ciel_agent_sweep(p_idle_seconds integer)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
    swept integer;
begin
    update public.agent_tasks
       set stop_requested = true, status = 'failed', reason = 'swept'
     where status in ('planning', 'running')
       and updated_at < now() - make_interval(secs => p_idle_seconds);
    get diagnostics swept = row_count;
    delete from public.agent_device_tokens where expires_at < now() - interval '1 day';
    return swept;
end;
$$;

revoke execute on function public.ciel_agent_sweep(integer) from public, anon, authenticated;

-- Cabut satu perangkat dan semua tokennya sekaligus. True kalau perangkat
-- itu ada dan milik pemilik ini.
create or replace function public.ciel_agent_revoke_device(p_owner text, p_device text)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
    found_device boolean;
begin
    update public.agent_devices
       set revoked_at = now()
     where owner = p_owner and id = p_device and revoked_at is null;
    found_device := exists (select 1 from public.agent_devices where owner = p_owner and id = p_device);
    delete from public.agent_device_tokens where owner = p_owner and device = p_device;
    return found_device;
end;
$$;

revoke execute on function public.ciel_agent_revoke_device(text, text) from public, anon, authenticated;

-- Ciel Agent di web, rencana 2C. Masa simpan log per akun (30 atau 90 hari).
create table if not exists public.agent_settings (
    owner text primary key,
    log_days integer not null default 30 check (log_days in (30, 90)),
    updated_at timestamptz not null default now()
);

alter table public.agent_settings enable row level security;

-- Hasil pemeriksaan rantai log per tugas, diisi layanan agent di VPS
-- (keputusan D14: kunci rantai tidak pernah keluar dari VPS).
alter table public.agent_tasks add column if not exists chain_status text
    check (chain_status in ('ok', 'broken', 'extra', 'missing'));
alter table public.agent_tasks add column if not exists chain_checked_at timestamptz;

create index if not exists consent_events_owner_kind on public.consent_events (owner, kind, created_at);

-- Menarik persetujuan agent: semua perangkat dicabut dan tokennya dibuang.
create or replace function public.ciel_agent_withdraw(p_owner text)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
    revoked integer;
begin
    update public.agent_devices set revoked_at = now() where owner = p_owner and revoked_at is null;
    get diagnostics revoked = row_count;
    delete from public.agent_device_tokens where owner = p_owner;
    return revoked;
end;
$$;

revoke execute on function public.ciel_agent_withdraw(text) from public, anon, authenticated;

-- Hapus akun: semua data agent pemilik ini dalam satu transaksi. Riwayat
-- consent_events sengaja tidak ikut, sama dengan consents.
create or replace function public.ciel_agent_delete_owner(p_owner text)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
begin
    delete from public.agent_device_tokens where owner = p_owner;
    delete from public.agent_devices where owner = p_owner;
    delete from public.agent_actions where owner = p_owner;
    delete from public.agent_tasks where owner = p_owner;
    delete from public.agent_settings where owner = p_owner;
    delete from public.spend_limits where owner = p_owner;
    delete from public.purchase_confirmations where owner = p_owner;
    return true;
end;
$$;

revoke execute on function public.ciel_agent_delete_owner(text) from public, anon, authenticated;

-- Masa simpan log: tugas yang sudah selesai dan lognya, lebih tua dari
-- pilihan pemiliknya (bawaan 30 hari). Tugas yang masih berjalan tidak disentuh.
create or replace function public.ciel_agent_retention()
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
    removed integer;
begin
    -- Baris log yang tugasnya sudah tidak ada (ditulis sebelum aturan
    -- agent_actions_task_fk berlaku) juga dibuang.
    delete from public.agent_actions a
     where not exists (select 1 from public.agent_tasks t where t.owner = a.owner and t.id = a.task);

    with expired as (
        select t.owner, t.id
          from public.agent_tasks t
          left join public.agent_settings s on s.owner = t.owner
         where t.status not in ('planning', 'running')
           and t.created_at < now() - make_interval(days => coalesce(s.log_days, 30))
    ), expired_actions as (
        delete from public.agent_actions a using expired e where a.owner = e.owner and a.task = e.id
    )
    delete from public.agent_tasks t using expired e where t.owner = e.owner and t.id = e.id;
    get diagnostics removed = row_count;
    return removed;
end;
$$;

revoke execute on function public.ciel_agent_retention() from public, anon, authenticated;

-- Tugas yang perlu diperiksa rantainya: sudah selesai, dan belum pernah
-- atau sudah lama tidak diperiksa.
create or replace function public.ciel_agent_tasks_to_check(p_before timestamptz, p_limit integer)
returns table (owner text, id text, head_hash text)
language sql
security definer
set search_path = public
as $$
    select t.owner, t.id, t.head_hash
      from public.agent_tasks t
     where t.status not in ('planning', 'running')
       and (t.chain_checked_at is null or t.chain_checked_at < p_before)
     order by t.created_at
     limit p_limit;
$$;

revoke execute on function public.ciel_agent_tasks_to_check(timestamptz, integer) from public, anon, authenticated;

-- Baris log hanya boleh ada untuk tugas yang masih ada. Tanpa aturan ini,
-- aksi yang sedang berjalan saat Hapus akun bisa menulis satu atau dua baris
-- lagi setelah tugasnya terhapus, dan baris itu tersisa selamanya. Tidak
-- divalidasi untuk baris lama; masa simpan membuang baris lama yang yatim.
do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'agent_actions_task_fk') then
        alter table public.agent_actions
            add constraint agent_actions_task_fk
            foreign key (owner, task) references public.agent_tasks (owner, id) on delete cascade not valid;
    end if;
end;
$$;
