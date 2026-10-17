"""Halaman masuk Ciel.

Masuk dengan Google memakai st.login yang sudah ada (aktif hanya jika blok
[auth] ada di secrets). Halaman hanya menampilkan kontrol yang benar-benar
berfungsi: tanpa [auth] tidak ada tombol Google, dan masuk dengan email
belum punya backend, jadi cukup disebut di catatan. Chat tetap bisa dipakai
tanpa masuk.
"""

import html

import streamlit as st


LOGIN_CSS = """
<style>
.st-key-loginbox {
    max-width: 26rem;
    margin: 1.5rem auto 0;
    padding: 2rem 1.75rem 1.5rem;
    border: 1px solid var(--c-line);
    border-radius: var(--r-lg);
    background: var(--c-surface);
    box-shadow: var(--shadow-md);
}
.ciel-loginhead { text-align: center; margin-bottom: 1rem; }
.ciel-loginhead h1 {
    margin: 0 0 0.5rem;
    padding: 0;
    font-family: var(--font-serif);
    font-size: 1.75rem;
    font-weight: 400;
    letter-spacing: -0.02em;
    line-height: 1.15;
    color: var(--c-text);
}
.stApp .ciel-loginhead p { margin: 0; font-size: 0.9rem; line-height: 1.6; color: var(--c-muted); text-wrap: pretty; }
.st-key-loginbox [data-testid="stElementContainer"]:has(.stButton),
.st-key-loginbox .stButton,
.st-key-loginbox .stButton div,
.st-key-loginbox .stButton button { width: 100%; }
.st-key-loginbox .stButton button { min-height: 2.75rem; }
.stApp .ciel-loginnotes { list-style: none; width: 100%; margin: 0.4rem 0 0.6rem; padding: 0.9rem 0 0; border-top: 1px solid var(--c-line); }
.stApp .ciel-loginnotes li { margin: 0 0 0.35rem; font-size: 0.82rem; line-height: 1.55; color: var(--c-muted); }
.st-key-loginback .stButton > button[kind="secondary"] { border-color: transparent; color: var(--c-muted); }
.st-key-loginback .stButton > button[kind="secondary"]:hover { background: transparent; color: var(--c-accent); }
@media (max-width: 640px) {
    .st-key-loginbox { margin-top: 0.5rem; padding: 1.5rem 1.1rem 1.1rem; }
}
</style>
"""


def login_notes(auth_enabled, rate_limits, history_saved=False):
    """Catatan di bawah tombol, mengikuti konfigurasi yang sebenarnya."""

    anon, logged = rate_limits
    notes = [f"Tanpa masuk kamu tetap bisa chat, hingga {anon} pesan per jam."]

    if auth_enabled:
        notes.append(
            f"Setelah masuk, Ciel bisa mengingat progres belajarmu lintas "
            f"percakapan dan batasnya naik menjadi {logged} pesan per jam."
        )
    else:
        notes.append(
            "Masuk dengan Google belum dikonfigurasi di deployment ini, jadi "
            "long-term memory nonaktif."
        )

    notes.append(
        "Riwayat chat dan proyek di sidebar berbeda dari memory: setelah masuk, "
        "keduanya tetap ada saat halaman dimuat ulang dan bisa kamu hapus."
        if history_saved
        else "Riwayat chat dan proyek di sidebar berbeda dari memory: hanya "
        "tersimpan selama sesi browser ini."
    )
    notes.append("Masuk dengan email dan kata sandi sedang disiapkan.")
    return notes


def render_login(auth_enabled=False, on_google=None, on_back=None, rate_limits=(20, 60), signed_in_as=None, history_saved=False):
    """Render halaman masuk.

    auth_enabled: True jika login Google (st.login) dikonfigurasi.
    on_google: callback tombol Google (st.login dari app.py).
    on_back: callback kembali ke chat.
    rate_limits: (batas pesan/jam tanpa login, batas setelah login) dari app.py.
    signed_in_as: nama/email jika pengguna sudah masuk.
    history_saved: True jika riwayat chat pengguna login disimpan di database.
    """

    st.markdown(LOGIN_CSS, unsafe_allow_html=True)

    with st.container(key="loginbox"):

        if signed_in_as:
            st.markdown(
                '<div class="ciel-loginhead">'
                "<h1>Kamu sudah masuk</h1>"
                f"<p>Masuk sebagai <strong>{html.escape(signed_in_as)}</strong>.</p>"
                "</div>",
                unsafe_allow_html=True,
            )
            st.button("Kembali ke chat", key="login_tochat", type="primary", on_click=on_back)
            return

        st.markdown(
            '<div class="ciel-loginhead">'
            "<h1>Masuk ke Ciel</h1>"
            "<p>Simpan progres belajarmu dan biarkan Ciel mengingat konteks "
            "penting dari percakapan sebelumnya.</p>"
            "</div>",
            unsafe_allow_html=True,
        )

        if auth_enabled:
            st.button(
                "Masuk dengan Google",
                key="login_google",
                type="primary",
                on_click=on_google,
            )

        notes = "".join(f"<li>{html.escape(n)}</li>" for n in login_notes(auth_enabled, rate_limits, history_saved))
        st.markdown(f'<ul class="ciel-loginnotes">{notes}</ul>', unsafe_allow_html=True)

        # Tanpa login yang aktif, kembali ke chat adalah satu-satunya aksi.
        with st.container(key="loginback"):
            st.button(
                "Lanjut tanpa masuk",
                key="login_skip",
                type="secondary" if auth_enabled else "primary",
                on_click=on_back,
            )
