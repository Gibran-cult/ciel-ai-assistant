import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import streamlit


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
ENV = {"NGROK_URL": "http://127.0.0.1:9", "NGROK_USER": "u", "NGROK_PASSWORD": "p", "LANGFLOW_API_KEY": "k", "FLOW_ID": "f"}
SIGNED_IN = {"is_logged_in": True, "name": "Ciel Tester", "email": "ciel@example.com", "sub": "sub-1"}


def run_app(page=None, user=None):
    from streamlit.testing.v1 import AppTest
    sys.path.insert(0, str(ROOT))
    with patch.dict(os.environ, ENV), patch.object(streamlit, "user", user or {}):
        at = AppTest.from_file(str(APP_PATH), default_timeout=60)
        if user:
            at.secrets["auth"] = {"redirect_uri": "http://localhost/oauth2callback"}
        if page:
            at.query_params["page"] = page
        at.run()
    return at


def page_text(at):
    return " ".join(md.value for md in at.markdown)


class LoginNotesTest(unittest.TestCase):

    def notes(self, **kwargs):
        sys.path.insert(0, str(ROOT))
        import login
        return " ".join(login.login_notes(**kwargs))

    def test_notes_follow_the_configuration(self):
        on = self.notes(auth_enabled=True, rate_limits=(20, 60))
        self.assertIn("20 pesan per jam", on)
        self.assertIn("60 pesan per jam", on)
        self.assertNotIn("belum dikonfigurasi", on)

        off = self.notes(auth_enabled=False, rate_limits=(15, 45))
        self.assertIn("15 pesan per jam", off)
        self.assertIn("belum dikonfigurasi", off)
        self.assertIn("long-term memory nonaktif", off)
        self.assertNotIn("45", off)

    def test_notes_explain_memory_versus_session_history(self):
        self.assertIn("sesi browser ini", self.notes(auth_enabled=True, rate_limits=(20, 60)))

        saved = self.notes(auth_enabled=True, rate_limits=(20, 60), history_saved=True)
        self.assertIn("dimuat ulang", saved)
        self.assertNotIn("sesi browser ini", saved)

    def test_email_login_is_never_promised_as_working(self):
        self.assertIn("sedang disiapkan", self.notes(auth_enabled=True, rate_limits=(20, 60)))


class ConsentGateTest(unittest.TestCase):

    def test_accept_and_logout_fill_the_card_width(self):
        # Streamlit 1.65 on Cloud sizes a button's element container to its
        # text, so CSS on the button alone left them narrow there. width=
        # "stretch" is Streamlit's own setting and works on every version.
        from unittest.mock import MagicMock
        sys.path.insert(0, str(ROOT))
        import login

        fake = MagicMock()
        with patch.object(login, "st", fake):
            login.render_consent(None, None, None, None)

        widths = {c.kwargs["key"]: c.kwargs.get("width") for c in fake.button.call_args_list}
        self.assertEqual(widths["consent_accept"], "stretch")
        self.assertEqual(widths["consent_logout"], "stretch")
        self.assertIsNone(widths["consent_terms"])
        self.assertNotIn('button[kind="primary"]', login.LOGIN_CSS)


class LoginPageTest(unittest.TestCase):

    def test_app_renders_the_login_page_without_the_composer(self):
        at = run_app("login")
        self.assertFalse(at.exception)
        self.assertIn("<h1>Masuk ke Ciel</h1>", page_text(at))
        self.assertEqual(len(at.chat_input), 0)

    def test_page_shows_no_controls_that_do_nothing(self):
        # The first version showed a disabled Google button and a disabled
        # email/password form. Only working controls are shown now.
        at = run_app("login")
        self.assertEqual([b.key for b in at.main.button if b.key.startswith("login_")], ["login_skip", "login_terms", "login_privacy"])
        self.assertEqual(len(at.main.text_input), 0)
        self.assertFalse(any(b.disabled for b in at.main.button))
        self.assertEqual(at.button(key="login_skip").proto.type, "primary")

    def test_google_button_appears_when_auth_is_configured(self):
        sys.path.insert(0, str(ROOT))
        from streamlit.testing.v1 import AppTest

        def page():
            import login
            login.render_login(auth_enabled=True, on_google=lambda: None, on_back=lambda: None)

        at = AppTest.from_function(page).run()
        self.assertFalse(at.button(key="login_google").disabled)
        self.assertEqual(at.button(key="login_skip").proto.type, "secondary")

    def test_google_button_comes_with_the_consent_line(self):
        at = self.render(auth_enabled=True)
        self.assertIn(
            "Dengan masuk, kamu menyetujui Syarat dan Ketentuan dan Kebijakan Privasi Ciel.",
            page_text(at),
        )
        keys = [b.key for b in at.button]
        self.assertIn("login_terms", keys)
        self.assertIn("login_privacy", keys)

    def render(self, **kwargs):
        sys.path.insert(0, str(ROOT))
        from streamlit.testing.v1 import AppTest

        def page(kwargs):
            import login
            login.render_login(on_google=lambda: None, on_back=lambda: None, **kwargs)

        return AppTest.from_function(page, kwargs={"kwargs": kwargs}).run()

    def test_two_column_layout_with_example_project(self):
        at = self.render(auth_enabled=True)
        text = page_text(at)
        self.assertEqual(len(at.columns), 2)
        self.assertIn("<h1>Masuk ke Ciel</h1>", text)
        self.assertIn("Begini proyekmu nanti", text)
        self.assertIn("Contoh proyek. Isinya mulai kosong, lalu keisi sendiri sambil kamu ngobrol sama Ciel.", text)
        self.assertNotIn("Sumber tersimpan", text)

    def test_example_card_has_no_deadline(self):
        # Deadlines are not a Ciel feature (spec non-goal).
        self.assertNotIn("dikumpulin", page_text(self.render(auth_enabled=True)))

    def test_intro_does_not_promise_google_when_sign_in_is_off(self):
        intro = page_text(self.render(auth_enabled=False)).split("</h1>")[1].split("</p>")[0]
        self.assertNotIn("Google", intro)
        self.assertIn("tanpa masuk", intro)

    def test_google_button_copy_and_scope_note(self):
        at = self.render(auth_enabled=True)
        self.assertEqual(at.button(key="login_google").label, "Lanjutkan dengan Google")
        self.assertIn("Ciel cuma minta nama, email, dan foto profil dari akun Google kamu.", page_text(at))

    def test_intro_only_promises_saved_history_when_it_is_saved(self):
        self.assertIn("Riwayat chat dan yang Ciel ingat ikut tersimpan di akunmu.", page_text(self.render(auth_enabled=True, history_saved=True)))
        self.assertNotIn("Riwayat chat", page_text(self.render(auth_enabled=True, history_saved=False)).split("</h1>")[1].split("</p>")[0])

    def test_privacy_link_and_no_terms_link(self):
        sys.path.insert(0, str(ROOT))
        from streamlit.testing.v1 import AppTest

        def page():
            import login
            import streamlit as st
            login.render_login(on_back=lambda: None, on_privacy=lambda: st.session_state.update(privacy_opened=True))

        at = AppTest.from_function(page).run()
        self.assertNotIn("Syarat layanan", page_text(at))
        at.button(key="login_privacy").click().run()
        self.assertTrue(at.session_state["privacy_opened"])

    def test_continue_without_signing_in_returns_to_chat(self):
        at = run_app("login")
        with patch.dict(os.environ, ENV):
            at.button(key="login_skip").click().run()
        self.assertNotIn("page", at.query_params)
        self.assertEqual(len(at.chat_input), 1)


class TopBarNavTest(unittest.TestCase):

    def test_sign_in_lives_in_the_top_bar_and_page_links_stay_hidden(self):
        at = run_app()
        self.assertFalse(at.exception)
        main_labels = [b.label for b in at.main.button]
        sidebar_labels = [b.label for b in at.sidebar.button]
        self.assertIn("Masuk", main_labels)
        # Pricing and Privasi only show in the account menu, after sign-in.
        for label in ("Pricing", "Harga", "Privasi"):
            self.assertNotIn(label, main_labels)
        for label in ("Harga & paket", "Pricing", "Privasi", "Masuk", "Masuk dengan Google", "Keluar"):
            self.assertNotIn(label, sidebar_labels)
        self.assertNotIn("About long-term memory", [e.label for e in at.sidebar.expander])
        # Sidebar labels are Indonesian like the rest of the app.
        # "Hapus chat" now lives in each history row's menu, so an empty
        # sidebar has no delete button.
        for label in ("Chat baru", "Semua chat"):
            self.assertIn(label, sidebar_labels)
        for label in ("New chat", "All chats", "Clear chat"):
            self.assertNotIn(label, sidebar_labels)

    def test_top_bar_shows_the_crumb(self):
        at = run_app()
        self.assertIn('<p class="ciel-crumb">Semua chat</p>', page_text(at))
        with patch.dict(os.environ, ENV):
            at.session_state.projects = {"p1": {"id": "p1", "name": "Skripsi <ojol>", "created": 0, "files": []}}
            at.session_state.active_project = "p1"
            at.run()
        self.assertIn('<p class="ciel-crumb">Proyek · <b>Skripsi &lt;ojol&gt;</b></p>', page_text(at))

    def test_sign_in_button_opens_the_login_page(self):
        at = run_app()
        with patch.dict(os.environ, ENV):
            at.button(key="login").click().run()
        self.assertIn("<h1>Masuk ke Ciel</h1>", page_text(at))

    def test_hide_on_scroll_script_and_css_use_the_same_state(self):
        # The browser behavior itself is checked by hand; this guards the
        # contract between NAV_SCROLL_JS and the CSS rule that hides the bar.
        source = APP_PATH.read_text(encoding="utf-8")
        bar = '[data-testid="stLayoutWrapper"]:has(> .st-key-topbar)'
        self.assertIn("body.style.setProperty('--ciel-nav-offset'", source)
        self.assertIn("calc(var(--ciel-nav-offset, 0px) * -1)", source)
        self.assertIn("body.dataset.cielNav = 'hidden'", source)
        self.assertIn(f'body[data-ciel-nav="hidden"] {bar}', source)
        self.assertIn("body.dataset.cielNavMoving = '1'", source)
        self.assertIn(f"body[data-ciel-nav-moving] {bar}", source)
        self.assertIn("st.html(NAV_SCROLL_JS, unsafe_allow_javascript=True)", source)

    def test_hide_on_scroll_listens_on_document_not_a_streamlit_element(self):
        # On Streamlit Cloud the navbar never hid: the listener was bound to
        # section.stMain, which the Cloud app shell can replace after the
        # script ran. A capture-phase listener on document survives that.
        source = APP_PATH.read_text(encoding="utf-8")
        self.assertIn("document.addEventListener('scroll'", source)
        self.assertIn("{ capture: true, passive: true }", source)
        self.assertIn("if (window.__cielNav) return;", source)
        self.assertNotIn("main.addEventListener('scroll'", source)

    def test_signed_in_user_gets_an_account_menu_at_the_bottom_of_the_sidebar(self):
        at = run_app(user=SIGNED_IN)
        self.assertFalse(at.exception)
        main_labels = [b.label for b in at.main.button]
        sidebar_labels = [b.label for b in at.sidebar.button]
        for label in ("Masuk", "Pricing", "Privasi", "Keluar", "Pengaturan"):
            self.assertNotIn(label, main_labels)
        # The menu holds the email, Pro status and Keluar; Pricing, Privasi,
        # the memory note and "Data saya" moved to Pengaturan (the ⚙ button).
        for label in ("Pricing", "Privasi"):
            self.assertNotIn(label, sidebar_labels)
        self.assertEqual(sidebar_labels.count("Keluar"), 1)
        self.assertEqual(sidebar_labels.count("Pengaturan"), 1)
        self.assertNotIn("Data saya", [e.label for e in at.sidebar.expander])
        self.assertNotIn("Long-term memory aktif", page_text(at))
        # Last in the sidebar, after the history.
        source = APP_PATH.read_text(encoding="utf-8")
        self.assertGreater(source.index('with st.container(key="sideaccount"):'), source.index('with st.container(key="history"):'))
        self.assertLess(source.index('with st.container(key="sideaccount"):'), source.index("# HEADER"))


if __name__ == "__main__":
    unittest.main()
