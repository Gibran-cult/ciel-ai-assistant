"""Halaman harga Ciel.

Data paket dipisah dari tampilan supaya harga dan fitur bisa diubah
tanpa menyentuh layout, dan bisa dites tanpa menjalankan app.py.
Belum ada sistem pembayaran: paket berbayar diarahkan ke CONTACT_URL.
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
        "blurb": "Untuk mencoba Ciel dan kebutuhan riset ringan.",
        "features": (
            "Chat dengan Ciel",
            "Riset web dan perhitungan",
            "Lampiran file teks",
            "Riwayat chat selama sesi",
        ),
        "cta": "Mulai chat",
        "highlight": False,
    },
    {
        "id": "pro",
        "name": "Pro",
        "monthly": 79_000,
        "blurb": "Untuk pelajar, peneliti, dan profesional yang riset tiap hari.",
        "features": (
            "Semua di paket Gratis",
            "Long-term memory lintas percakapan",
            "Lampiran foto dan analisis gambar",
            "Projects dengan file konteks bersama",
        ),
        "cta": "Pilih Pro",
        "highlight": True,
    },
    {
        "id": "team",
        "name": "Tim",
        "monthly": 149_000,
        "unit": "per pengguna",
        "blurb": "Untuk tim kecil yang butuh asisten riset bersama.",
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

FAQ = (
    (
        "Bagaimana cara membayar?",
        "Pembayaran online belum tersedia. Pilih paket lalu hubungi kami, "
        "dan kami kirimkan instruksi pembayaran secara manual.",
    ),
    (
        "Apa bedanya riwayat chat dan long-term memory?",
        "Riwayat chat di sidebar hanya bertahan selama sesi browser. "
        "Long-term memory menyimpan konteks penting di backend Ciel sehingga "
        "bisa dipakai lagi di percakapan berikutnya.",
    ),
    (
        "Bisa berhenti kapan saja?",
        "Bisa. Paket bulanan tidak diperpanjang otomatis, dan paket tahunan "
        "berlaku sampai akhir periode yang sudah dibayar.",
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

def _plan_html(plan, billing):
    shown, total, period = plan_price(plan, billing)
    unit = plan.get("unit", "")

    if plan["monthly"] == 0:
        price_html = "<strong>Rp0</strong><span>selamanya</span>"
        bill_html = ""
    else:
        price_html = f"<strong>{format_idr(shown)}</strong><span>/ bulan</span>"
        bill_html = (
            f"Ditagih {format_idr(total)} per tahun"
            if billing == "yearly"
            else "Ditagih bulanan"
        )
        if unit:
            bill_html += f", {html.escape(unit)}"

    tag = '<span class="ciel-plan-tag">Paling populer</span>' if plan["highlight"] else ""
    features = "".join(f"<li>{html.escape(item)}</li>" for item in plan["features"])

    return (
        f'<div class="ciel-plan-top"><span class="ciel-plan-name">{html.escape(plan["name"])}</span>{tag}</div>'
        f'<div class="ciel-plan-price">{price_html}</div>'
        f'<p class="ciel-plan-bill">{bill_html}</p>'
        f'<p class="ciel-plan-blurb">{html.escape(plan["blurb"])}</p>'
        f'<ul class="ciel-plan-feats">{features}</ul>'
    )


def render_pricing(contact_url=None, on_start_chat=None):
    """Render halaman harga.

    contact_url: tautan https/mailto tujuan tombol paket berbayar.
    on_start_chat: callback tombol paket Gratis (kembali ke chat).
    """
    st.markdown(PRICING_CSS, unsafe_allow_html=True)

    st.markdown(
        '<div class="ciel-pricehead">'
        "<h1>Harga yang sederhana.</h1>"
        "<p>Mulai gratis. Upgrade saat Ciel sudah jadi bagian dari "
        "cara kamu riset.</p>"
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
    columns = st.columns(len(PLANS), gap="small")

    for column, plan in zip(columns, PLANS):

        key = f"plan_{plan['id']}" + ("-hl" if plan["highlight"] else "")

        with column, st.container(key=key):

            st.markdown(_plan_html(plan, billing), unsafe_allow_html=True)

            button_type = "primary" if plan["highlight"] else "secondary"

            if plan["monthly"] == 0:
                st.button(
                    plan["cta"],
                    key=f"cta_{plan['id']}",
                    type=button_type,
                    on_click=on_start_chat,
                )
            elif contact:
                st.link_button(plan["cta"], contact, type=button_type)
            else:
                st.button(
                    "Segera hadir",
                    key=f"cta_{plan['id']}",
                    disabled=True,
                    help="Kontak penjualan belum dikonfigurasi (CONTACT_URL).",
                )

    st.markdown(
        '<p class="ciel-pricenote">Harga dalam Rupiah. Pembayaran diproses manual untuk sementara.</p>',
        unsafe_allow_html=True,
    )

    faq_html = "".join(
        f"<div><strong>{html.escape(q)}</strong><span>{html.escape(a)}</span></div>"
        for q, a in FAQ
    )

    st.markdown(
        '<div class="ciel-faq-title">Pertanyaan umum</div>'
        f'<div class="ciel-faq">{faq_html}</div>',
        unsafe_allow_html=True,
    )
