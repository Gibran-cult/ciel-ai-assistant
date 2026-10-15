"""Halaman harga Ciel.

Data paket dipisah dari tampilan supaya harga dan fitur bisa diubah
tanpa menyentuh layout, dan bisa dites tanpa menjalankan app.py.

Belum ada sistem pembayaran dan pembatasan per paket, jadi semua fitur
yang ada saat ini gratis. Halaman hanya menampilkan satu paket yang
benar-benar bisa dipakai (Gratis); paket berbayar tampil sebagai daftar
rencana tanpa tombol beli, toggle tagihan, atau kartu tiruan. Batas pesan
dan status memory dikirim oleh app.py agar halaman selalu sesuai
konfigurasi.
"""

import html

import streamlit as st


# ============================================================
# DATA
# ============================================================

PLANS = (
    {
        "id": "free",
        "name": "Gratis",
        "monthly": 0,
        "available": True,
        "tag": "Tersedia sekarang",
        "blurb": "Semua fitur Ciel yang ada saat ini, dengan batas pesan per jam.",
        "features": (
            "Chat, riset web dengan sumber, dan matematika",
            "Analisis angka dari file CSV/TSV",
            "Lampiran foto dan file teks",
            "Proyek dengan file konteks bersama",
            "Riwayat chat selama sesi",
        ),
        "cta": "Mulai chat",
    },
    {
        "id": "pro",
        "name": "Pro",
        "monthly": 79_000,
        "available": False,
        "blurb": "Untuk pelajar, peneliti, dan profesional yang riset tiap hari.",
        "features": (
            "Semua di paket Gratis",
            "Batas pesan per jam lebih tinggi",
        ),
    },
    {
        "id": "team",
        "name": "Tim",
        "monthly": 149_000,
        "available": False,
        "unit": "per pengguna",
        "blurb": "Untuk tim kecil yang butuh asisten riset bersama.",
        "features": (
            "Semua di paket Pro",
            "Minimal 3 pengguna",
            "Onboarding dan bantuan setup flow",
            "Dukungan via email",
        ),
    },
)


def free_plan_extras(rate_limits, memory_enabled):
    """Baris fitur Gratis yang bergantung pada konfigurasi app."""
    anonymous, signed_in = rate_limits
    extras = []

    if memory_enabled:
        extras.append("Long-term memory pribadi (perlu login)")
        extras.append(f"{anonymous} pesan/jam tanpa login, {signed_in} pesan/jam setelah login")
    else:
        extras.append(f"{anonymous} pesan/jam")

    return tuple(extras)


def faq_items(memory_enabled):
    memory_answer = (
        "Riwayat chat di sidebar hanya bertahan selama sesi browser. "
        "Long-term memory menyimpan konteks penting di backend Ciel sehingga "
        "bisa dipakai lagi di percakapan berikutnya. Memory hanya aktif "
        "setelah login dan hanya bisa dibaca oleh akunmu sendiri."
        if memory_enabled
        else "Riwayat chat di sidebar hanya bertahan selama sesi browser. "
        "Long-term memory (mengingat konteks lintas percakapan) belum aktif "
        "di deployment ini."
    )

    return (
        (
            "Apakah Ciel gratis?",
            "Ya. Semua fitur yang ada saat ini gratis, dengan batas pesan per "
            "jam. Paket berbayar masih disiapkan dan belum bisa dibeli.",
        ),
        ("Apa bedanya riwayat chat dan long-term memory?", memory_answer),
        (
            "Kenapa ada batas pesan per jam?",
            "Ciel memakai model AI berbayar dan server sendiri. Batas per jam "
            "menjaga biaya tetap terkendali dan Ciel tetap cepat untuk semua orang.",
        ),
    )


# ============================================================
# LOGIC
# ============================================================

def format_idr(amount):
    """Format angka ke Rupiah dengan titik ribuan, mis. 79000 -> Rp79.000."""
    return "Rp" + f"{int(round(amount)):,}".replace(",", ".")


def planned_price(plan):
    """Teks harga rencana untuk paket yang belum dibuka."""
    text = f"Rencana {format_idr(plan['monthly'])}/bulan"
    if plan.get("unit"):
        text += f" {plan['unit']}"
    return text


def safe_contact_url(url):
    """Hanya izinkan tautan https/mailto agar tidak bisa disisipi skema lain."""
    if url and url.strip().lower().startswith(("https://", "mailto:")):
        return url.strip()
    return None


# ============================================================
# STYLE
# ============================================================
# Memakai token warna dari CIEL_CSS di app.py (--c-*, --r-*, --font-*).

PRICING_CSS = """
<style>
.ciel-pricehead h1 {
    margin: 0 0 0.7rem;
    font-family: var(--font-serif);
    font-size: clamp(1.9rem, 3.8vw, 2.6rem);
    font-weight: 400;
    letter-spacing: -0.025em;
    line-height: 1.08;
    text-wrap: balance;
    color: var(--c-text);
}
.stApp .ciel-pricehead p { margin: 0 0 1.6rem; max-width: 34rem; color: var(--c-muted); line-height: 1.65; }

.st-key-plan_free {
    padding: 1.3rem 1.3rem 1.2rem;
    border: 1px solid var(--c-line);
    border-radius: var(--r-lg);
    background: var(--c-surface);
    box-shadow: var(--shadow-sm);
}
.ciel-plan-top { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; }
.ciel-plan-name { font-size: 1rem; font-weight: 600; letter-spacing: -0.01em; color: var(--c-text); }
.ciel-plan-tag {
    padding: 0.1rem 0.55rem;
    border-radius: 999px;
    background: var(--c-gold);
    color: var(--c-gold-ink);
    font-size: 0.74rem;
    font-weight: 500;
}
.ciel-plan-price { margin: 0.8rem 0 0.2rem; display: flex; align-items: baseline; gap: 0.35rem; }
.ciel-plan-price strong {
    font-size: 1.85rem;
    font-weight: 600;
    letter-spacing: -0.04em;
    font-variant-numeric: tabular-nums;
    color: var(--c-text);
}
.ciel-plan-price span { font-size: 0.82rem; color: var(--c-muted); }
.stApp .ciel-plan-blurb { margin: 0.4rem 0 0.9rem; font-size: 0.9rem; line-height: 1.55; color: var(--c-muted); }
.stApp .ciel-plan-feats {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.45rem 1.5rem;
    width: 100%;
    list-style: none;
    margin: 0 0 1.1rem;
    padding: 0.9rem 0 0;
    border-top: 1px solid var(--c-line);
}
.stApp .ciel-plan-feats li {
    position: relative;
    margin: 0;
    padding-left: 1.2rem;
    font-size: 0.88rem;
    line-height: 1.5;
    color: var(--c-text);
}
.ciel-plan-feats li::before {
    content: "";
    position: absolute;
    left: 0.15rem;
    top: 0.6em;
    width: 0.4rem;
    height: 0.4rem;
    border-radius: 50%;
    background: var(--c-accent);
}

.ciel-planned-title { margin: 2.4rem 0 0.4rem; font-size: 1.05rem; font-weight: 600; letter-spacing: -0.01em; }
.stApp .ciel-planned-note { margin: 0 0 0.6rem; font-size: 0.86rem; color: var(--c-muted); }
.ciel-planned { border-top: 1px solid var(--c-line); }
.ciel-planned-row { display: grid; grid-template-columns: 11rem 1fr; gap: 1rem; padding: 0.95rem 0; border-bottom: 1px solid var(--c-line); }
.ciel-planned-row strong { display: block; font-size: 0.95rem; font-weight: 600; }
.ciel-planned-row em { display: block; margin-top: 0.15rem; font-style: normal; font-size: 0.82rem; color: var(--c-faint); font-variant-numeric: tabular-nums; }
.stApp .ciel-planned-row p { margin: 0; font-size: 0.88rem; line-height: 1.6; color: var(--c-muted); }
.stApp .ciel-pricenote { margin: 0.9rem 0 0; font-size: 0.82rem; color: var(--c-faint); }
.stApp .ciel-pricenote a { color: var(--c-accent); }

.ciel-faq-title { margin: 2.6rem 0 0.4rem; font-size: 1.05rem; font-weight: 600; letter-spacing: -0.01em; }
.ciel-faq { border-top: 1px solid var(--c-line); }
.ciel-faq div { display: grid; grid-template-columns: 15rem 1fr; gap: 1rem; padding: 0.95rem 0; border-bottom: 1px solid var(--c-line); }
.ciel-faq strong { font-size: 0.9rem; font-weight: 600; }
.stApp .ciel-faq span { font-size: 0.88rem; line-height: 1.6; color: var(--c-muted); }

@media (max-width: 640px) {
    .stApp .ciel-plan-feats { grid-template-columns: 1fr; }
    .ciel-planned-row, .ciel-faq div { grid-template-columns: 1fr; gap: 0.25rem; }
}
</style>
"""


# ============================================================
# RENDER
# ============================================================

def _free_plan_html(plan, extras):
    features = "".join(f"<li>{html.escape(item)}</li>" for item in plan["features"] + tuple(extras))

    return (
        f'<div class="ciel-plan-top"><span class="ciel-plan-name">{html.escape(plan["name"])}</span>'
        f'<span class="ciel-plan-tag">{html.escape(plan["tag"])}</span></div>'
        '<div class="ciel-plan-price"><strong>Rp0</strong><span>selamanya</span></div>'
        f'<p class="ciel-plan-blurb">{html.escape(plan["blurb"])}</p>'
        f'<ul class="ciel-plan-feats">{features}</ul>'
    )


def _as_sentence(items):
    """("Semua di paket Pro", "Minimal 3 pengguna") -> "Semua di paket Pro, minimal 3 pengguna."."""
    first, *rest = items
    return ", ".join([first] + [item[:1].lower() + item[1:] for item in rest]) + "."


def _planned_html(plans):
    rows = "".join(
        '<div class="ciel-planned-row">'
        f'<div><strong>{html.escape(plan["name"])}</strong><em>{html.escape(planned_price(plan))}</em></div>'
        f'<p>{html.escape(plan["blurb"])} {html.escape(_as_sentence(plan["features"]))}</p>'
        "</div>"
        for plan in plans
    )

    return (
        '<div class="ciel-planned-title">Sedang disiapkan</div>'
        '<p class="ciel-planned-note">Belum bisa dibeli. Harga masih rencana dan bisa berubah sebelum dibuka.</p>'
        f'<div class="ciel-planned">{rows}</div>'
    )


def render_pricing(contact_url=None, on_start_chat=None, rate_limits=(20, 60), memory_enabled=False):
    """Render halaman harga.

    contact_url: tautan https/mailto untuk yang tertarik dengan paket berbayar.
    on_start_chat: callback tombol paket Gratis (kembali ke chat).
    rate_limits: (batas pesan/jam tanpa login, batas setelah login) dari app.py.
    memory_enabled: True jika login (dan long-term memory) aktif.
    """

    st.markdown(PRICING_CSS, unsafe_allow_html=True)

    st.markdown(
        '<div class="ciel-pricehead">'
        "<h1>Semua fitur Ciel saat ini gratis.</h1>"
        "<p>Pemakaian dibatasi per jam agar Ciel tetap lancar untuk semua "
        "orang. Paket berbayar baru akan dibuka setelah siap.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    free = next(plan for plan in PLANS if plan["available"])

    with st.container(key="plan_free"):
        st.markdown(
            _free_plan_html(free, free_plan_extras(rate_limits, memory_enabled)),
            unsafe_allow_html=True,
        )
        st.button(free["cta"], key="cta_free", type="primary", on_click=on_start_chat)

    planned = [plan for plan in PLANS if not plan["available"]]
    contact = safe_contact_url(contact_url)
    note = (
        'Tertarik atau punya pertanyaan? '
        f'<a href="{html.escape(contact, quote=True)}">Hubungi kami</a>.'
        if contact
        else ""
    )

    st.markdown(
        _planned_html(planned)
        + (f'<p class="ciel-pricenote">{note}</p>' if note else ""),
        unsafe_allow_html=True,
    )

    faq_html = "".join(
        f"<div><strong>{html.escape(q)}</strong><span>{html.escape(a)}</span></div>"
        for q, a in faq_items(memory_enabled)
    )

    st.markdown(
        '<div class="ciel-faq-title">Pertanyaan umum</div>'
        f'<div class="ciel-faq">{faq_html}</div>',
        unsafe_allow_html=True,
    )
