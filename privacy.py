"""Halaman privasi Ciel.

Isi halaman mengikuti konfigurasi yang dikirim app.py (lama retensi,
login, panel "Data saya", kontak), supaya yang dijanjikan ke pengguna
selalu sama dengan yang benar-benar terjadi.
"""

import html

import streamlit as st


PRIVACY_CSS = """
<style>
.ciel-privacy h1 {
    margin: 0 0 0.7rem;
    font-size: clamp(1.8rem, 3.6vw, 2.5rem);
    font-weight: 560;
    letter-spacing: -0.045em;
    line-height: 1.08;
    color: var(--c-text);
}
.ciel-privacy h2 {
    margin: 2rem 0 0.6rem;
    font-size: 1.05rem;
    font-weight: 560;
    letter-spacing: -0.01em;
    color: var(--c-text);
}
.stApp .ciel-privacy p,
.stApp .ciel-privacy li { font-size: 0.92rem; line-height: 1.65; color: var(--c-muted); }
.stApp .ciel-privacy ul { padding-left: 1.1rem; margin: 0; }
.stApp .ciel-privacy li { margin: 0 0 0.45rem; }
.stApp .ciel-privacy strong { color: var(--c-text); font-weight: 560; }
.stApp .ciel-privacy a { color: var(--c-accent); }
</style>
"""


def privacy_sections(retention_days, memory_enabled, data_controls, contact_url=None):
    """Kembalikan daftar (judul, [paragraf HTML]) untuk halaman privasi."""

    days = int(retention_days)

    processing = [
        "Pesan dan file yang kamu lampirkan dikirim ke server Ciel (Langflow "
        "yang berjalan di komputer pengelola) untuk dijawab.",
        "Untuk menyusun jawaban, isi pesan diproses oleh penyedia model AI "
        "pihak ketiga (<strong>DeepSeek</strong>). Pertanyaan riset web dikirim "
        "ke layanan pencarian (<strong>Exa</strong>).",
        "Foto dan embedding memory diproses oleh model yang berjalan di server "
        "Ciel sendiri.",
    ]

    stored = [
        "<strong>Riwayat chat di sidebar</strong> hanya ada di browsermu dan "
        "hilang saat tab ditutup.",
        f"<strong>Riwayat pesan di server:</strong> setiap pesan dan jawaban "
        f"disimpan di server Ciel paling lama <strong>{days} hari</strong>, "
        "lalu dihapus otomatis. Pesan tanpa login disimpan dengan kode acak, "
        "bukan namamu.",
    ]

    if memory_enabled:
        stored.append(
            "<strong>Long-term memory</strong> (hanya setelah login): hal penting "
            "yang kamu minta Ciel ingat, disimpan sampai kamu menghapusnya dan "
            "hanya bisa dibaca oleh akunmu."
        )
        stored.append(
            "<strong>Akun Google:</strong> nama dan email dipakai untuk "
            "menampilkan status login. Memory memakai kode yang diturunkan dari "
            "akunmu, bukan emailmu."
        )
    else:
        stored.append(
            "<strong>Long-term memory</strong> belum aktif di deployment ini, "
            "jadi Ciel tidak menyimpan memory jangka panjang."
        )

    stored.append(
        "<strong>Catatan teknis:</strong> saat terjadi error, server mencatat "
        "kode permintaan (Request ID) dan detail error untuk perbaikan."
    )

    controls = []

    if memory_enabled and data_controls:
        controls.append(
            "Setelah login, buka <strong>Data saya</strong> di sidebar untuk "
            "melihat dan menghapus memory-mu, serta menghapus riwayat chat-mu "
            "di server."
        )
    elif memory_enabled:
        controls.append(
            "Penghapusan memory dan riwayat chat belum bisa dilakukan sendiri "
            "dari aplikasi; sampaikan permintaan ke pengelola."
        )

    controls.append(
        "Riwayat pesan tanpa login tidak bisa dihubungkan ke dirimu, jadi tidak "
        f"bisa dihapus per orang; pesan itu terhapus otomatis setelah {days} hari."
    )

    if contact_url:
        controls.append(
            f'Pertanyaan atau permintaan soal datamu: <a href="{html.escape(contact_url, quote=True)}">hubungi kami</a>.'
        )

    advice = [
        "Jangan kirim kata sandi, nomor identitas, data kesehatan, data "
        "keuangan, atau informasi rahasia lain ke Ciel.",
    ]

    return [
        ("Apa yang terjadi saat kamu mengirim pesan", processing),
        ("Apa yang disimpan", stored),
        ("Kendali atas datamu", controls),
        ("Saran", advice),
    ]


def render_privacy(retention_days=30, memory_enabled=False, data_controls=False, contact_url=None):
    st.markdown(PRIVACY_CSS, unsafe_allow_html=True)

    parts = [
        '<div class="ciel-privacy">',
        "<h1>Privasi</h1>",
        "<p>Ringkasan data apa yang Ciel proses dan simpan, dan cara kamu "
        "mengendalikannya.</p>",
    ]

    for title, items in privacy_sections(retention_days, memory_enabled, data_controls, contact_url):
        parts.append(f"<h2>{html.escape(title)}</h2><ul>")
        parts.extend(f"<li>{item}</li>" for item in items)
        parts.append("</ul>")

    parts.append("</div>")

    st.markdown("".join(parts), unsafe_allow_html=True)
