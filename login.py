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
/* Two columns as in the design artifact: the sign-in form on the left, an
   example project on the right. */
/* The page widens for two columns; Streamlit sizes the columns with its own
   gap, so the gap comes from st.columns(gap="large"), not from CSS. */
.stMain .block-container:has(.st-key-loginpage) { max-width: 72rem; }
.st-key-loginpage { margin-top: 1rem; }
.st-key-loginpage [data-testid="stHorizontalBlock"] { align-items: center; }
.ciel-loginbrand { display: flex; align-items: center; gap: 0.6rem; margin-bottom: 2.5rem; font-family: var(--font-serif); font-size: 1.375rem; font-weight: 500; letter-spacing: -0.02em; color: var(--c-text); }
.ciel-loginbrand svg { width: 1.6rem; height: 1.6rem; }
.ciel-loginhead { margin-bottom: 0.6rem; }
.ciel-loginhead h1 {
    margin: 0 0 0.6rem;
    padding: 0;
    font-family: var(--font-sans);
    font-size: 1.75rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    line-height: 1.2;
    color: var(--c-text);
}
.stApp .ciel-loginhead p { margin: 0; max-width: 26rem; font-size: 1rem; line-height: 1.5; color: var(--c-muted); text-wrap: pretty; }
.st-key-loginform .stButton button { min-height: 3.25rem; font-size: 0.95rem; }
.st-key-loginform [data-testid="stElementContainer"]:has(.stButton),
.st-key-loginform .stButton,
.st-key-loginform .stButton button { width: 100%; max-width: 26rem; }
.stApp .ciel-loginscope { margin: 0.2rem 0 0; font-size: 0.8125rem; color: var(--c-faint); }
.stApp .ciel-loginnotes { list-style: none; max-width: 26rem; margin: 0.6rem 0 0.4rem; padding: 0.9rem 0 0; border-top: 1px solid var(--c-line); }
.stApp .ciel-loginnotes li { margin: 0 0 0.35rem; font-size: 0.8125rem; line-height: 1.55; color: var(--c-muted); }
.st-key-loginback .stButton > button[kind="secondary"] { border-color: transparent; color: var(--c-muted); }
.st-key-loginback .stButton > button[kind="secondary"]:hover { background: var(--c-raised); color: var(--c-text); }
.st-key-loginlegal .stButton > button { width: auto; min-height: 0; padding: 0; color: var(--c-faint); font-size: 0.8125rem; text-decoration: underline; text-underline-offset: 3px; }
.st-key-loginlegal .stButton > button:hover { background: transparent; color: var(--c-text); }
.stApp .ciel-peek h2 { margin: 0 0 1rem; padding: 0; font-family: var(--font-sans); font-size: 0.875rem; font-weight: 600; color: var(--c-muted); }
.ciel-peekcard {
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
    padding: 1.5rem;
    border-radius: var(--r-lg);
    background: var(--c-surface);
    box-shadow: 0 0 0 5px var(--c-bg), 0 0 0 6px var(--c-line);
}
.ciel-peekhead { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; }
.ciel-peekhead b { display: block; font-size: 1.125rem; font-weight: 600; color: var(--c-text); }
.ciel-peekhead span { display: block; margin-top: 0.25rem; font-size: 0.875rem; color: var(--c-muted); }
.ciel-peekhead .ciel-av { display: inline-flex; align-items: center; justify-content: center; flex: none; width: 1.75rem; height: 1.75rem; margin: 0; border-radius: 999px; background: var(--c-accent-soft); color: var(--c-accent); font-size: 0.75rem; font-weight: 600; }
.ciel-stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); margin: 0; border-radius: var(--r-md); background: var(--c-raised); }
.ciel-stats div { padding: 0.85rem 1rem; }
.ciel-stats div + div { border-left: 1px solid var(--c-line); }
.ciel-stats dt { font-size: 0.75rem; color: var(--c-faint); }
.ciel-stats dd { margin: 0.25rem 0 0; font-size: 1.5rem; font-variant-numeric: tabular-nums; color: var(--c-text); }
.ciel-stats .is-gap dd { color: var(--c-mark-piece); }
.stApp .ciel-why { display: flex; flex-direction: column; gap: 0.5rem; margin: 0; padding: 0; list-style: none; }
.stApp .ciel-why li { display: flex; align-items: center; gap: 0.75rem; margin: 0; padding: 0.75rem 0.9rem; border-radius: var(--r-md); background: var(--c-raised); font-size: 0.875rem; color: var(--c-text); }
.ciel-why li span { margin-left: auto; font-size: 0.75rem; color: var(--c-faint); white-space: nowrap; }
.stApp .ciel-peekcap { margin: 1rem 0 0; font-size: 0.8125rem; color: var(--c-faint); }
.st-key-loginbox {
    max-width: 26rem;
    margin: 1.5rem auto 0;
    padding: 2rem 1.75rem 1.5rem;
    border-radius: var(--r-lg);
    background: var(--c-surface);
    box-shadow: 0 0 0 5px var(--c-bg), 0 0 0 6px var(--c-line);
}
.st-key-loginbox .stButton, .st-key-loginbox .stButton button { width: 100%; }
@media (max-width: 900px) {
    .st-key-loginpage [data-testid="stHorizontalBlock"] { flex-direction: column; }
    .st-key-loginpage [data-testid="stColumn"] { width: 100% !important; flex: 1 1 auto !important; }
    .ciel-loginbrand { margin-bottom: 1.5rem; }
}
</style>
"""

MARK = (
    '<svg viewBox="0 0 32 32" aria-hidden="true">'
    '<path fill="var(--c-accent)" d="M24.89 10.6A11.8 11.8 0 1 0 24.89 21.4H20.57A8.2 8.2 0 1 1 20.57 10.6Z"/>'
    '<path fill="var(--c-mark-piece)" d="M28.39 10.6A11.8 11.8 0 0 1 28.39 21.4H24.07A8.2 8.2 0 0 0 24.07 10.6Z"/>'
    "</svg>"
)

# Example project on the right. Only things the app really has: chats, project
# files, claims without a source, remembered items.
PEEK_HTML = (
    '<section class="ciel-peek">'
    "<h2>Begini proyekmu nanti</h2>"
    '<div class="ciel-peekcard">'
    '<div class="ciel-peekhead"><div><b>Skripsi sentimen ojol</b><span>Terakhir dibuka tadi malam, 21.42</span></div>'
    '<span class="ciel-av" aria-hidden="true">RP</span></div>'
    '<dl class="ciel-stats">'
    "<div><dt>Chat</dt><dd>12</dd></div>"
    "<div><dt>File proyek</dt><dd>2</dd></div>"
    '<div class="is-gap"><dt>Belum ketemu</dt><dd>2</dd></div>'
    "</dl>"
    '<ul class="ciel-why">'
    "<li>Format sitasi APA 7<span>diingat</span></li>"
    "<li>Data ulasan diambil dari Play Store<span>diingat</span></li>"
    "<li>Lebih ngerti kalau dikasih contoh angka<span>diingat</span></li>"
    "</ul>"
    "</div>"
    '<p class="ciel-peekcap">Contoh proyek. Isinya mulai kosong, lalu keisi sendiri sambil kamu ngobrol sama Ciel.</p>'
    "</section>"
)


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


def render_login(auth_enabled=False, on_google=None, on_back=None, rate_limits=(20, 60), signed_in_as=None, history_saved=False, on_privacy=None):
    """Render halaman masuk.

    auth_enabled: True jika login Google (st.login) dikonfigurasi.
    on_google: callback tombol Google (st.login dari app.py).
    on_back: callback kembali ke chat.
    rate_limits: (batas pesan/jam tanpa login, batas setelah login) dari app.py.
    signed_in_as: nama/email jika pengguna sudah masuk.
    history_saved: True jika riwayat chat pengguna login disimpan di database.
    on_privacy: callback ke halaman Privasi.
    """

    st.markdown(LOGIN_CSS, unsafe_allow_html=True)

    if signed_in_as:
        with st.container(key="loginbox"):
            st.markdown(
                '<div class="ciel-loginhead">'
                "<h1>Kamu sudah masuk</h1>"
                f"<p>Masuk sebagai <strong>{html.escape(signed_in_as)}</strong>.</p>"
                "</div>",
                unsafe_allow_html=True,
            )
            st.button("Kembali ke chat", key="login_tochat", type="primary", on_click=on_back)
        return

    if not auth_enabled:
        intro = "Masuk belum tersedia di deployment ini, tapi kamu tetap bisa chat tanpa masuk."
    elif history_saved:
        intro = "Satu akun Google buat semua proyekmu. Riwayat chat dan yang Ciel ingat ikut tersimpan di akunmu."
    else:
        intro = "Satu akun Google buat semua proyekmu, dan Ciel bisa ingat konteks penting dari percakapanmu."

    with st.container(key="loginpage"):

        form, peek = st.columns([5, 7], gap="large")

        with form, st.container(key="loginform"):

            st.markdown(
                f'<div class="ciel-loginbrand">{MARK}Ciel</div>'
                '<div class="ciel-loginhead">'
                "<h1>Masuk ke Ciel</h1>"
                f"<p>{html.escape(intro)}</p>"
                "</div>",
                unsafe_allow_html=True,
            )

            if auth_enabled:
                st.button(
                    "Lanjutkan dengan Google",
                    key="login_google",
                    type="primary",
                    on_click=on_google,
                )
                st.markdown(
                    '<p class="ciel-loginscope">Ciel cuma minta nama, email, dan foto profil dari akun Google kamu.</p>',
                    unsafe_allow_html=True,
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

            with st.container(key="loginlegal"):
                st.button("Kebijakan privasi", key="login_privacy", type="tertiary", on_click=on_privacy)

        with peek:
            st.markdown(PEEK_HTML, unsafe_allow_html=True)
