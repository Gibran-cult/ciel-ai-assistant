"""Pengaturan end to end (AppTest): profil di sesi, sapaan, pesan ke Langflow."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests
import streamlit

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
sys.path.insert(0, str(ROOT))

from tests.test_chat_store import ENV, SIGNED_IN, SIGNED_IN_OWNER, Response  # noqa: E402

FEATURES = {
    "SUPABASE_URL": "https://db.example.invalid",
    "SUPABASE_SERVICE_KEY": "service-key",
}
ANSWER = {"outputs": [{"outputs": [{"results": {"message": {"data": {"text": "Jawaban Ciel."}}}}]}]}
OTHER = {"is_logged_in": True, "name": "Dina Lestari", "email": "dina@example.com", "sub": "sub-2"}


def at_requests(test):
    """Semua panggilan requests.request (Supabase) di tes ini."""
    return test.request.call_args_list


def question(text):
    return {"text": text, "files": [], "images": [], "payload": text}


class SettingsAppTest(unittest.TestCase):

    def start(self, user=None, secrets=None, env=None, query=None, rows=None, down=()):
        """Jalankan app. `rows` = {tabel: baris} untuk GET Supabase, `down` = tabel yang gagal."""
        from streamlit.testing.v1 import AppTest

        self.rows = rows if rows is not None else {}
        self.down = set(down)
        self.post = Mock(return_value=Response(ANSWER))
        self.user = patch.object(streamlit, "user", user or {})
        self.request = Mock(side_effect=self.database)
        self.patches = [
            patch.dict(os.environ, {**ENV, "WRITER_FLOW_ID": "", "RESEARCH_FLOW_ID": "", **(env or {})}),
            self.user,
            patch("requests.request", self.request),
            patch("requests.post", self.post),
        ]
        for item in self.patches:
            item.start()
        self.addCleanup(lambda: [item.stop() for item in reversed(self.patches)])
        at = AppTest.from_file(str(APP_PATH), default_timeout=60)
        if user:
            at.secrets["auth"] = {"redirect_uri": "http://localhost/oauth2callback"}
        for key, value in (secrets or {}).items():
            at.secrets[key] = value
        for key, value in (query or {}).items():
            at.query_params[key] = value
        at.run()
        self.assertFalse(at.exception)
        return at

    def database(self, method, url, **kwargs):
        table = url.rsplit("/", 1)[1]
        if table in self.down:
            raise requests.exceptions.ConnectionError("down")
        return Response(self.rows.get(table, []) if method == "GET" else None)

    def switch_user(self, user):
        self.user.stop()
        self.user = patch.object(streamlit, "user", user)
        self.user.start()

    def text(self, at):
        return " ".join(md.value for md in at.markdown)

    def keys(self, at):
        return [b.key for b in at.button]

    def runs(self):
        return [c for c in self.post.call_args_list if "/api/v1/run/" in c.args[0]]

    def post_json(self, table):
        return [c for c in self.post.call_args_list if c.args[0].endswith(f"/rest/v1/{table}")][-1].kwargs["json"]

    def send(self, at, text):
        at.session_state["pending"] = question(text)
        at.run()
        self.assertFalse(at.exception)
        return self.runs()[-1].kwargs["json"]["input_value"]

    # --------------------------------------------------------
    # Task 3: profil di sesi, Beranda, dan pesan ke Langflow
    # --------------------------------------------------------

    def test_signed_in_profile_loads_once_and_shapes_the_greeting(self):
        at = self.start(user=SIGNED_IN, secrets=FEATURES, rows={"profiles": [{"nickname": "Kak <b>Raka</b>"}]})
        self.assertIn("Kak &lt;b&gt;Raka&lt;/b&gt;.", self.text(at))
        self.assertEqual(at.session_state["profile"]["nickname"], "Kak <b>Raka</b>")

    def test_greeting_falls_back_to_the_google_first_name(self):
        at = self.start(user=SIGNED_IN, secrets=FEATURES)
        self.assertRegex(self.text(at), r"(Pagi|Siang|Sore|Malam), Ciel\.")

    def test_chat_message_carries_the_profile_block_first(self):
        at = self.start(user=SIGNED_IN, secrets=FEATURES, rows={"profiles": [{"nickname": "Raka", "field": "Akuntansi"}]})
        sent = self.send(at, "apa itu regresi")
        self.assertTrue(sent.startswith("### Profil pengguna"))
        self.assertIn("Panggil pengguna: Raka", sent)
        self.assertTrue(sent.endswith("### Pesan\napa itu regresi"))

    def test_riset_request_has_no_profile_block(self):
        rows = {"profiles": [{"nickname": "Raka"}], "pro_members": [{"expires_at": "2999-01-01T00:00:00+00:00"}]}
        at = self.start(user=SIGNED_IN, secrets={**FEATURES, "RESEARCH_FLOW_ID": "riset-flow-id"}, rows=rows)
        at.session_state["pending"] = {
            **question("Riset Skripsi: UMKM"),
            "payload": "Topik skripsi: UMKM",
            "riset": {"topic": "UMKM", "field": "", "min_year": 2021},
        }
        at.run()
        (run,) = self.runs()
        self.assertTrue(run.args[0].endswith("/api/v1/run/riset-flow-id"))
        self.assertNotIn("### Profil pengguna", run.kwargs["json"]["input_value"])

    def test_failed_profile_load_keeps_chat_working_with_one_notice(self):
        with self.assertLogs("ciel_ai.chat_store", level="ERROR"):
            at = self.start(user=SIGNED_IN, secrets=FEATURES, down={"profiles"})
        self.assertEqual([t.value for t in at.toast], ["Profil tersimpan gagal dimuat."])
        at.run()
        self.assertEqual(len(at.toast), 0)
        self.assertEqual(self.send(at, "halo"), "halo")

    def test_history_failure_notice_is_not_hidden_by_the_profile_notice(self):
        with self.assertLogs("ciel_ai.chat_store", level="ERROR"):
            at = self.start(user=SIGNED_IN, secrets=FEATURES, down={"chats", "profiles"})
        self.assertEqual([t.value for t in at.toast], ["Riwayat chat tersimpan gagal dimuat."])

    def test_failed_profile_load_blocks_saving_over_the_stored_profile(self):
        with self.assertLogs("ciel_ai.chat_store", level="ERROR"):
            at = self.start(user=SIGNED_IN, secrets=FEATURES, down={"profiles"},
                            query={"page": "settings", "tab": "profil"})
        self.assertTrue(at.button(key="profile_save").disabled)
        self.assertIn("belum bisa dimuat", " ".join(w.value for w in at.warning))

        # Opening Profil again retries the load; once it works the form is usable.
        self.down.clear()
        self.rows["profiles"] = [{"nickname": "Raka", "full_name": "Raka Pradipta"}]
        at.run()
        self.assertFalse(at.button(key="profile_save").disabled)
        self.assertEqual(at.text_input(key="profile_full_name").value, "Raka Pradipta")

    def test_switching_accounts_drops_the_old_profile(self):
        at = self.start(user=SIGNED_IN, secrets=FEATURES, rows={"profiles": [{"nickname": "Raka"}]})
        self.rows["profiles"] = []
        self.switch_user(OTHER)
        at.run()
        self.assertEqual(at.session_state["profile"]["nickname"], "")
        self.assertNotIn("Raka", self.text(at))
        self.assertIn("Dina.", self.text(at))

    def test_switching_accounts_without_a_database_drops_the_old_profile(self):
        at = self.start(user=SIGNED_IN)
        at.session_state["profile"] = {"full_name": "", "nickname": "Raka", "field": "", "preferences": ""}
        at.run()
        self.switch_user(OTHER)
        at.run()
        self.assertEqual(at.session_state["profile"]["nickname"], "")

    def test_anonymous_visitor_sends_no_profile(self):
        at = self.start()
        self.assertEqual(self.send(at, "apa itu regresi"), "apa itu regresi")

    # --------------------------------------------------------
    # Task 4: Pengaturan sebagai dialog (seperti Settings di aplikasi Claude)
    # --------------------------------------------------------

    def tab_keys(self, at):
        return [key for key in self.keys(at) if key and key.startswith("settab")]

    def test_settings_is_a_dialog_over_the_app_not_a_page(self):
        # Ciel, 2026-10-28: a modal like the Claude app's Settings, not a new page.
        source = APP_PATH.read_text(encoding="utf-8")
        self.assertIn('@st.dialog("Pengaturan", width="large", on_dismiss=close_settings)', source)
        self.assertNotIn('current_view() == "settings"', source)
        at = self.start(query={"page": "settings"})
        self.assertEqual(len(at.chat_input), 1)  # Beranda stays behind the dialog
        self.assertNotIn("page", at.query_params)  # opened once, not on every reload

    def test_settings_lists_tabs_for_the_login_state(self):
        at = self.start(query={"page": "settings"})
        self.assertEqual(self.tab_keys(at), ["settabactive_tampilan", "settab_paket", "settab_privasi"])

        at = self.start(user=SIGNED_IN, query={"page": "settings"})
        self.assertEqual(
            self.tab_keys(at),
            ["settabactive_profil", "settab_tampilan", "settab_data", "settab_paket", "settab_privasi"],
        )

    def test_tab_buttons_switch_the_tab_inside_the_dialog(self):
        at = self.start(user=SIGNED_IN, query={"page": "settings"})
        at.button(key="settab_privasi").click().run()
        self.assertEqual(at.session_state["settings_open"], "privasi")
        self.assertIn("settabactive_privasi", self.keys(at))
        self.assertIn("<h1>Privasi</h1>", self.text(at))

    def test_signed_out_profile_link_falls_back_to_tampilan(self):
        at = self.start(query={"page": "settings", "tab": "data"})
        self.assertIn("settabactive_tampilan", self.keys(at))
        self.assertFalse([t.key for t in at.text_input if t.key.startswith("profile_")])
        self.assertNotIn("load_memories", self.keys(at))

    def test_old_pricing_and_privacy_links_open_their_tabs(self):
        for page, tab, heading in (
            ("pricing", "paket", "<h1>Fitur inti Ciel gratis.</h1>"),
            ("privacy", "privasi", "<h1>Privasi</h1>"),
        ):
            with self.subTest(page=page):
                at = self.start(query={"page": page})
                self.assertIn(f"settabactive_{tab}", self.keys(at))
                self.assertIn(heading, self.text(at))
                self.assertNotIn("page", at.query_params)

    def test_midtrans_return_lands_on_paket_with_the_order(self):
        payments = {**FEATURES, "MIDTRANS_SERVER_KEY": "SB-Mid-server-test"}
        at = self.start(user=SIGNED_IN, secrets=payments, query={"page": "pricing?order_id=ciel-x"})
        self.assertIn("settabactive_paket", self.keys(at))
        self.assertIn("<h1>Fitur inti Ciel gratis.</h1>", self.text(at))

    def test_free_plan_button_closes_the_dialog(self):
        at = self.start(query={"page": "settings", "tab": "paket"})
        at.button(key="cta_free").click().run()
        self.assertIsNone(at.session_state["settings_open"])
        self.assertEqual(self.tab_keys(at), [])

    def test_sign_in_to_buy_closes_the_dialog_and_opens_the_login_page(self):
        payments = {**FEATURES, "MIDTRANS_SERVER_KEY": "SB-Mid-server-test", "APP_URL": "https://ciel.example",
                    "auth": {"redirect_uri": "http://localhost/oauth2callback"}}
        at = self.start(secrets=payments, query={"page": "pricing"})
        at.button(key="pro_login").click().run()
        self.assertIsNone(at.session_state["settings_open"])
        self.assertEqual(at.query_params["page"], ["login"])
        self.assertIn("<h1>Masuk ke Ciel</h1>", self.text(at))

    def test_profile_form_saves_and_shows_the_account(self):
        at = self.start(user=SIGNED_IN, secrets=FEATURES, query={"page": "settings", "tab": "profil"})
        at.text_input(key="profile_nickname").set_value("Raka")
        at.text_input(key="profile_full_name").set_value("Raka  Pradipta")
        at.button(key="profile_save").click().run()
        self.assertFalse(at.exception)
        self.assertEqual(self.post_json("profiles")["nickname"], "Raka")
        self.assertEqual(self.post_json("profiles")["owner"], SIGNED_IN_OWNER)
        self.assertEqual(at.session_state["profile"]["full_name"], "Raka Pradipta")
        self.assertEqual([s.value for s in at.success], ["Profil tersimpan."])
        self.assertIn("ciel@example.com", self.text(at))
        self.assertIn(SIGNED_IN_OWNER, self.text(at))

    def account_card(self, at):
        cards = [md.value for md in at.markdown if 'class="ciel-account-card"' in md.value]
        self.assertEqual(len(cards), 1)
        return cards[0]

    def test_account_details_are_a_card_of_labelled_rows(self):
        # Ciel, 2026-10-28: the Akun text should look better than plain lines.
        rows = {"pro_members": [{"expires_at": "2999-01-01T00:00:00+00:00"}]}
        user = {**SIGNED_IN, "email": "ciel<x>@example.com"}
        at = self.start(user=user, secrets=FEATURES, rows=rows, query={"page": "settings", "tab": "profil"})
        card = self.account_card(at)
        for label in ("Email", "Paket", "Long-term memory", "ID memory"):
            self.assertIn(f'<span class="ciel-account-label">{label}</span>', card)
        self.assertIn("ciel&lt;x&gt;@example.com", card)
        self.assertIn('<span class="ciel-plan-pill ciel-plan-pro">Pro</span>', card)
        self.assertIn("Aktif sampai 1 Januari 2999", card)
        self.assertIn(f"<code>{SIGNED_IN_OWNER}</code>", card)

    def test_free_account_card_shows_a_free_badge(self):
        at = self.start(user=SIGNED_IN, secrets=FEATURES, query={"page": "settings", "tab": "profil"})
        self.assertIn('<span class="ciel-plan-pill">Gratis</span>', self.account_card(at))

    def test_profile_form_starts_from_the_saved_profile(self):
        at = self.start(user=SIGNED_IN, secrets=FEATURES, rows={"profiles": [{"nickname": "Raka", "field": "Akuntansi"}]},
                        query={"page": "settings", "tab": "profil"})
        self.assertEqual(at.text_input(key="profile_nickname").value, "Raka")
        self.assertEqual(at.text_input(key="profile_field").value, "Akuntansi")

    def test_clear_profile_needs_confirmation_and_deletes_the_row(self):
        at = self.start(user=SIGNED_IN, secrets=FEATURES, rows={"profiles": [{"nickname": "Raka"}]},
                        query={"page": "settings", "tab": "profil"})
        self.assertTrue(at.button(key="profile_clear").disabled)
        at.checkbox(key="confirm_clear_profile").check().run()
        at.button(key="profile_clear").click().run()
        self.assertEqual(at.session_state["profile"]["nickname"], "")
        deletes = [c for c in at_requests(self) if c.args[0] == "DELETE"]
        self.assertTrue(deletes[-1].args[1].endswith("/rest/v1/profiles"))

    def test_data_tab_holds_the_old_controls_and_the_export(self):
        at = self.start(user=SIGNED_IN, env={"MEMORY_ADMIN_FLOW_ID": "admin"}, query={"page": "settings", "tab": "data"})
        for key in ("load_memories", "delete_all_memories", "load_datasets", "delete_all_datasets", "delete_history"):
            self.assertIn(key, self.keys(at))
        (download,) = at.get("download_button")
        self.assertEqual(download.proto.label, "Unduh riwayat chat (JSON)")

    # --------------------------------------------------------
    # Task 5: ⚙ di kanan nama akun, tema pindah dari top bar
    # --------------------------------------------------------

    def account_menu(self, at):
        """Popover akun: yang terakhir di sidebar (AppTest memberinya sebagai Block biasa)."""
        return at.sidebar.get("popover")[-1]

    def test_gear_sits_right_of_the_account_name(self):
        at = self.start(user=SIGNED_IN, secrets=FEATURES, rows={"profiles": [{"full_name": "Raka Pradipta"}]})
        self.assertEqual(self.account_menu(at).proto.popover.label, "Raka Pradipta")
        gear = at.sidebar.button(key="opensettings")
        self.assertEqual(gear.label, "Pengaturan")
        self.assertEqual(gear.proto.icon, ":material/settings:")
        # Popover first, then ⚙, in one horizontal row inside the sticky account block.
        source = APP_PATH.read_text(encoding="utf-8")
        block = source[source.index('with st.container(key="sideaccount"):'):source.index("# HEADER")]
        block = block[block.index('key="accountrow"'):]
        self.assertLess(block.index("st.popover("), block.index('key="opensettings"'))
        gear.click().run()
        self.assertEqual(at.session_state["settings_open"], "profil")
        self.assertIn("settabactive_profil", self.keys(at))

    def test_account_menu_keeps_only_email_pro_and_logout(self):
        at = self.start(user=SIGNED_IN, secrets=FEATURES)
        menu = [b.key for b in self.account_menu(at).button]
        self.assertEqual(menu, ["logout"])
        self.assertIn("ciel@example.com", " ".join(md.value for md in self.account_menu(at).markdown))

    def test_account_without_an_email_can_open_profil(self):
        # The sidebar once assigned a top-level `account_name` string, which
        # shadowed account_name() and broke the Profil tab for such accounts.
        at = self.start(user={"is_logged_in": True, "name": "Tanpa Email", "sub": "sub-3"},
                        query={"page": "settings", "tab": "profil"})
        self.assertIn("Tanpa Email", self.text(at))
        self.assertNotIn("account_name =", APP_PATH.read_text(encoding="utf-8"))

    def test_signed_out_sidebar_still_reaches_settings(self):
        at = self.start()
        at.sidebar.button(key="opensettings").click().run()
        self.assertIn("settabactive_tampilan", self.keys(at))
        self.assertEqual(len(at.chat_input), 1)

    def test_top_bar_has_no_theme_toggle(self):
        at = self.start()
        main = " ".join(h.proto.body for h in at.main.get("html"))
        self.assertNotIn("ciel-theme-toggle", main)

    def test_tampilan_tab_offers_both_themes(self):
        at = self.start(query={"page": "settings", "tab": "tampilan"})
        page = " ".join(h.proto.body for h in at.get("html"))
        self.assertIn('data-ciel-theme-set="dark"', page)
        self.assertIn('data-ciel-theme-set="light"', page)


if __name__ == "__main__":
    unittest.main()
