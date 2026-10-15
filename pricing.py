"""Halaman harga Ciel.

Data paket dipisah dari tampilan supaya harga dan fitur bisa diubah
tanpa menyentuh layout, dan bisa dites tanpa menjalankan app.py.

Belum ada sistem pembayaran dan pembatasan per paket, jadi semua fitur
yang ada saat ini gratis. Paket berbayar tampil sebagai rencana
("Segera hadir") dan tidak bisa dibeli, supaya halaman ini tidak menjual
fitur yang sebenarnya gratis. Batas pesan dan status memory dikirim oleh
app.py agar halaman selalu sesuai konfigurasi.
"""

import html

import streamlit as st


# ============================================================
# DATA
# ============================================================

YEARLY_MONTHS_CHARGED = 10  # Bayar tahunan = 2 bulan gratis

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
            "Projects dengan file konteks bersama",
            "Riwayat chat selama sesi",
        ),
        "cta": "Mulai chat",
        "highlight": True,
    },
    {
        "id": "pro",
        "name": "Pro",
        "monthly": 79_000,
        "available": False,
        "tag": "Segera hadir",
        "blurb": "Rencana untuk pelajar, peneliti, dan profesional yang riset tiap hari.",
        "features": (
            "Semua di paket Gratis",
            "Batas pesan per jam lebih tinggi",
        ),
        "cta": "Pilih Pro",
        "highlight": False,
    },
    {
        "id": "team",
        "name": "Tim",
        "monthly": 149_000,
        "available": False,
        "tag": "Segera hadir",
        "unit": "per pengguna",
        "blurb": "Rencana untuk tim kecil yang butuh asisten riset bersama.",
        "features": (
            "Semua di paket Pro",
            "Minimal 3 pengguna",
            "Onboarding dan bantuan setup flow",
            "Dukungan via email",
        ),
        "cta": "Hubungi kami",
        "highlight": False,
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


def plan_price(plan, billing):
    """Kembalikan (harga per bulan yang ditampilkan, total tagihan, periode)."""
    monthly = plan["monthly"]

    if billing == "yearly":
        total = monthly * YEARLY_MONTHS_CHARGED
        return total / 12, total, "tahun"

    return monthly, monthly, "bulan"


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
    font-size: clamp(1.8rem, 3.6vw, 2.5rem);
    font-weight: 560;
    letter-spacing: -0.045em;
    line-height: 1.08;
    text-wrap: balance;
    color: var(--c-text);
}
.stApp .ciel-pricehead p { margin: 0 0 1.4rem; max-width: 34rem; color: var(--c-muted); line-height: 1.65; }

[class*="st-key-plan_"] {
    height: 100%;
    padding: 1.2rem 1.15rem 1.1rem;
    border: 1px solid var(--c-line-strong);
    border-radius: var(--r-lg);
    background: var(--c-surface);
}
[class*="st-key-plan_"][class*="-hl"] {
    border-color: var(--c-accent);
    box-shadow: inset 0 2px 0 var(--c-accent);
}
.ciel-plan-top { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; }
.ciel-plan-name { font-size: 1rem; font-weight: 560; letter-spacing: -0.01em; color: var(--c-text); }
.ciel-plan-tag {
    padding: 0.1rem 0.45rem;
    border-radius: 3px;
    background: var(--c-accent);
    color: var(--c-accent-ink);
    font-family: var(--font-mono);
    font-size: 0.68rem;
    font-weight: 500;
}
.ciel-plan-tag.is-soon {
    background: transparent;
    border: 1px solid var(--c-line-strong);
    color: var(--c-muted);
}
.stApp .ciel-pricenote a { color: var(--c-accent); }
.ciel-plan-price { margin: 0.9rem 0 0.15rem; display: flex; align-items: baseline; gap: 0.35rem; flex-wrap: wrap; }
.ciel-plan-price strong {
    font-size: 1.85rem;
    font-weight: 560;
    letter-spacing: -0.04em;
    font-variant-numeric: tabular-nums;
    color: var(--c-text);
}
.ciel-plan-price span { font-size: 0.82rem; color: var(--c-muted); }
.stApp .ciel-plan-bill { min-height: 1.2rem; margin: 0; font-family: var(--font-mono); font-size: 0.72rem; color: var(--c-faint); }
.stApp .ciel-plan-blurb { margin: 0.75rem 0 0.9rem; font-size: 0.86rem; line-height: 1.55; color: var(--c-muted); }
.stApp .ciel-plan-feats { list-style: none; margin: 0 0 1rem; padding: 0.85rem 0 0; width: 100%; border-top: 1px solid var(--c-line); }
.stApp .ciel-plan-feats li {
    position: relative;
    margin: 0 0 0.5rem;
    padding-left: 1.3rem;
    font-size: 0.86rem;
    line-height: 1.5;
    color: var(--c-text);
}
.ciel-plan-feats li::before {
    content: "\\2713";
    position: absolute;
    left: 0;
    color: var(--c-accent);
    font-family: var(--font-mono);
}
[class*="st-key-plan_"] [data-testid="stElementContainer"]:has(.stButton, .stLinkButton),
[class*="st-key-plan_"] .stButton,
[class*="st-key-plan_"] .stLinkButton,
.stApp [class*="st-key-plan_"] .stButton > button,
.stApp [class*="st-key-plan_"] .stLinkButton > a { width: 100%; }

.stApp .ciel-pricenote { margin: 1.1rem 0 0; font-size: 0.8rem; color: var(--c-faint); }
.ciel-faq-title { margin: 2.6rem 0 0.4rem; font-size: 1.05rem; font-weight: 560; letter-spacing: -0.01em; }
.ciel-faq { border-top: 1px solid var(--c-line); }
.ciel-faq div { display: grid; grid-template-columns: 15rem 1fr; gap: 1rem; padding: 0.95rem 0; border-bottom: 1px solid var(--c-line); }
.ciel-faq strong { font-size: 0.9rem; font-weight: 560; }
.stApp .ciel-faq span { font-size: 0.88rem; line-height: 1.6; color: var(--c-muted); }

@media (max-width: 640px) {
    .ciel-faq div { grid-template-columns: 1fr; gap: 0.25rem; }
}
</style>
"""


# ============================================================
# RENDER
# ============================================================

def _plan_html(plan, billing, extras=()):
    shown, total, period = plan_price(plan, billing)
    unit = plan.get("unit", "")

    if plan["monthly"] == 0:
        price_html = "<strong>Rp0</strong><span>selamanya</span>"
        bill_html = ""
    else:
        price_html = f"<strong>{format_idr(shown)}</strong><span>/ bulan</span>"
        bill_html = (
            f"Rencana: {format_idr(total)} per tahun"
            if billing == "yearly"
            else "Rencana harga bulanan"
        )
        if unit:
            bill_html += f", {html.escape(unit)}"

    tag_class = "ciel-plan-tag" if plan["available"] else "ciel-plan-tag is-soon"
    tag = f'<span class="{tag_class}">{html.escape(plan["tag"])}</span>' if plan.get("tag") else ""
    features = "".join(f"<li>{html.escape(item)}</li>" for item in plan["features"] + tuple(extras))

    return (
        f'<div class="ciel-plan-top"><span class="ciel-plan-name">{html.escape(plan["name"])}</span>{tag}</div>'
        f'<div class="ciel-plan-price">{price_html}</div>'
        f'<p class="ciel-plan-bill">{bill_html}</p>'
        f'<p class="ciel-plan-blurb">{html.escape(plan["blurb"])}</p>'
        f'<ul class="ciel-plan-feats">{features}</ul>'
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
        "<p>Paket berbayar sedang disiapkan. Untuk sementara, pemakaian "
        "dibatasi per jam agar Ciel tetap lancar untuk semua orang.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    choice = st.segmented_control(
        "Periode tagihan",
        options=("monthly", "yearly"),
        format_func=lambda value: (
            "Bulanan" if value == "monthly" else "Tahunan (hemat 2 bulan)"
        ),
        default="monthly",
        key="pricing_billing",
        label_visibility="collapsed",
    )
    billing = choice or "monthly"
    contact = safe_contact_url(contact_url)
    extras = free_plan_extras(rate_limits, memory_enabled)

    columns = st.columns(len(PLANS), gap="small")

    for column, plan in zip(columns, PLANS):

        key = f"plan_{plan['id']}" + ("-hl" if plan["highlight"] else "")

        with column, st.container(key=key):
            st.markdown(
                _plan_html(plan, billing, extras if plan["id"] == "free" else ()),
                unsafe_allow_html=True,
            )

            if plan["available"]:
                st.button(
                    plan["cta"],
                    key=f"cta_{plan['id']}",
                    type="primary" if plan["highlight"] else "secondary",
                    on_click=on_start_chat,
                )
            else:
                st.button(
                    "Segera hadir",
                    key=f"cta_{plan['id']}",
                    disabled=True,
                    help="Paket berbayar belum dibuka dan belum bisa dibeli.",
                )

    note = "Harga paket berbayar masih rencana dan bisa berubah sebelum dibuka."

    if contact:
        note += (
            ' Tertarik atau punya pertanyaan? '
            f'<a href="{html.escape(contact, quote=True)}">Hubungi kami</a>.'
        )

    st.markdown(f'<p class="ciel-pricenote">{note}</p>', unsafe_allow_html=True)

    faq_html = "".join(
        f"<div><strong>{html.escape(q)}</strong><span>{html.escape(a)}</span></div>"
        for q, a in faq_items(memory_enabled)
    )

    st.markdown(
        '<div class="ciel-faq-title">Pertanyaan umum</div>'
        f'<div class="ciel-faq">{faq_html}</div>',
        unsafe_allow_html=True,
    )
