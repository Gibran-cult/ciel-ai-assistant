"""Pengaturan > Agent end to end (AppTest), rencana 2C Task 5."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_consent import AGENT_CONSENT_VERSION  # noqa: E402
from tests.test_chat_store import SIGNED_IN, SIGNED_IN_OWNER, Response  # noqa: E402
from tests import test_settings_app as settings_tests  # noqa: E402

FEATURES = settings_tests.FEATURES

AGENT = {**FEATURES, "AGENT_WEB_ENABLED": "1"}
CONSENT = {"choice": {"accepted": True}, "version": AGENT_CONSENT_VERSION}
TASK = {"id": "t0001", "instruction": "Cari mouse wireless di shopee.co.id", "status": "done", "reason": None, "steps": 3,
        "created_at": "2026-11-18T03:40:00+00:00", "chain_status": "broken", "chain_checked_at": "2026-11-18T04:00:00+00:00"}
ACTIONS = [
    {"seq": 1, "device": "d0000000000000001", "kind": "tab_type", "target": "shopee.co.id", "level": "R1", "decision": "allow",
     "reason": "tab_type", "approved_by": None, "result": None, "at": "2026-11-18T03:42:00+00:00"},
    {"seq": 2, "device": "d0000000000000001", "kind": "tab_type", "target": "shopee.co.id", "level": "R1", "decision": "allow",
     "reason": "tab_type", "approved_by": None, "result": "ok", "at": "2026-11-18T03:42:05+00:00"},
    {"seq": 3, "device": "d0000000000000001", "kind": "<b>tebal</b>", "target": "<i>miring</i>", "level": "R3", "decision": "block",
     "reason": "unknown_kind", "approved_by": None, "result": None, "at": "2026-11-18T03:43:00+00:00"},
]
DEVICE = {"id": "a1b2c3d4e5f60718", "name": "Chrome di laptop", "platform": "extension", "created_at": "2026-11-18T03:00:00+00:00",
          "last_seen_at": "2026-11-18T03:43:00+00:00", "revoked_at": None}


# Helper dipinjam lewat modul, tidak lewat nama kelas: kelas uji yang
# diimpor langsung ikut dijalankan lagi oleh unittest di modul ini.
class AgentSettingsAppTest(unittest.TestCase):
    start = settings_tests.SettingsAppTest.start
    database = settings_tests.SettingsAppTest.database
    text = settings_tests.SettingsAppTest.text
    keys = settings_tests.SettingsAppTest.keys

    def open_tab(self, secrets=AGENT, rows=None, user=SIGNED_IN, down=()):
        at = self.start(user=user, secrets=secrets, rows=rows, query={"page": "settings", "tab": "agent"}, down=down)
        self.post.side_effect = self.rpc
        return at

    def rpc(self, url, **kwargs):
        name = url.rsplit("/", 1)[1]
        return Response({"ciel_agent_withdraw": 1, "ciel_agent_revoke_device": True}.get(name), status=201 if "rpc/" not in url else 200)

    def posts(self, suffix):
        return [call.kwargs.get("json") for call in self.post.call_args_list if call.args[0].endswith(suffix)]

    def everything(self, at):
        parts = [md.value for md in at.markdown] + [c.value for c in at.caption] + [e.label for e in at.expander]
        parts += [b.label for b in at.button] + [c.label for c in at.checkbox] + [t.value for t in at.text]
        parts += [e.value for e in at.error] + [e.value for e in at.success]
        parts += [w.value for w in at.warning]
        return " ".join(str(part) for part in parts)

    def test_the_tab_is_hidden_without_the_secret_or_without_login(self):
        at = self.open_tab(secrets=FEATURES)
        self.assertNotIn("settab_agent", self.keys(at))
        self.assertNotIn("settabactive_agent", self.keys(at))

        at = self.open_tab(user={})
        self.assertNotIn("settab_agent", self.keys(at))

        at = self.open_tab()
        self.assertIn("settabactive_agent", self.keys(at))

    def test_activation_needs_the_box_and_records_one_event(self):
        at = self.open_tab()
        self.assertTrue(at.button(key="agent_activate").disabled)
        at.checkbox(key="agent_consent_box").check().run()
        self.assertFalse(at.button(key="agent_activate").disabled)
        at.button(key="agent_activate").click().run()
        self.assertFalse(at.exception)
        self.assertEqual(self.posts("/consent_events"), [{
            "owner": SIGNED_IN_OWNER, "kind": "agent", "choice": {"accepted": True}, "version": AGENT_CONSENT_VERSION, "surface": "web",
        }])

    def test_turning_the_agent_off_records_and_revokes_every_device(self):
        at = self.open_tab(rows={"consent_events": [CONSENT]})
        self.assertIn("Agent aktif", self.everything(at))
        at.button(key="agent_withdraw").click().run()
        self.assertFalse(at.exception)
        self.assertEqual(self.posts("/consent_events")[-1]["choice"], {"accepted": False})
        self.assertEqual(self.posts("/rpc/ciel_agent_withdraw"), [{"p_owner": SIGNED_IN_OWNER}])

    def test_the_log_shows_rows_and_the_chain_label(self):
        at = self.open_tab(rows={"consent_events": [CONSENT], "agent_tasks": [TASK], "agent_actions": ACTIONS})
        page = self.everything(at)
        self.assertIn("Log rusak: ada catatan yang berubah", [w.value for w in at.warning])
        self.assertIn("Mengetik di kolom", page)
        self.assertIn("shopee.co.id", page)
        self.assertIn("Selesai", page)
        self.assertEqual(len(at.get("download_button")), 1)

    def test_html_in_the_log_is_shown_as_text(self):
        at = self.open_tab(rows={"consent_events": [CONSENT], "agent_tasks": [TASK], "agent_actions": ACTIONS})
        markdown = " ".join(md.value for md in at.markdown)
        self.assertNotIn("<b>tebal</b>", markdown)
        self.assertNotIn("<i>miring</i>", markdown)
        self.assertIn("Aksi lain (<b>tebal</b>)", self.everything(at))

    def test_revoking_a_device_only_touches_the_signed_in_owner(self):
        at = self.open_tab(rows={"consent_events": [CONSENT], "agent_devices": [DEVICE]})
        self.assertIn("Chrome di laptop", self.everything(at))
        at.button(key=f"agent_revoke_{DEVICE['id']}").click().run()
        self.assertFalse(at.exception)
        self.assertEqual(self.posts("/rpc/ciel_agent_revoke_device"), [{"p_owner": SIGNED_IN_OWNER, "p_device": DEVICE["id"]}])

    def test_log_days_choice_is_saved_and_recorded(self):
        at = self.open_tab(rows={"consent_events": [CONSENT]})
        at.radio(key="agent_log_days").set_value(90).run()
        self.assertFalse(at.exception)
        self.assertEqual(self.posts("/agent_settings"), [{"owner": SIGNED_IN_OWNER, "log_days": 90}])
        self.assertEqual(self.posts("/consent_events")[-1]["choice"], {"agent_log_days": 90})

    def test_database_errors_show_a_message_not_a_crash(self):
        at = self.open_tab(down={"consent_events"})
        self.assertIn("belum bisa dibaca", self.everything(at))
        self.assertNotIn("agent_activate", self.keys(at))

        at = self.open_tab(rows={"consent_events": [CONSENT]}, down={"agent_tasks", "agent_devices"})
        self.assertIn("belum bisa dimuat", self.everything(at))

    def test_delete_account_text_names_agent_data_only_when_the_agent_is_on(self):
        memory = {"MEMORY_ADMIN_FLOW_ID": "admin-flow"}
        on = self.start(user=SIGNED_IN, secrets=AGENT, env=memory, query={"page": "settings", "tab": "data"})
        self.assertIn("dan data agentmu", " ".join(md.value for md in on.markdown))
        off = self.start(user=SIGNED_IN, secrets=FEATURES, env=memory, query={"page": "settings", "tab": "data"})
        self.assertNotIn("data agent", " ".join(md.value for md in off.markdown))


    # Tinjauan 2C temuan 3: penarikan yang gagal setengah jalan bisa diulang dari tab.
    def test_live_devices_without_consent_can_still_be_revoked(self):
        withdrawn = {"choice": {"accepted": False}, "version": AGENT_CONSENT_VERSION}
        at = self.open_tab(rows={"consent_events": [withdrawn], "agent_devices": [DEVICE]})
        self.assertIn("masih terhubung", self.everything(at))
        at.button(key="agent_revoke_all").click().run()
        self.assertFalse(at.exception)
        self.assertEqual(self.posts("/rpc/ciel_agent_withdraw"), [{"p_owner": SIGNED_IN_OWNER}])

    def test_no_extra_button_when_nothing_is_live(self):
        revoked = {**DEVICE, "revoked_at": "2026-11-18T05:00:00+00:00"}
        at = self.open_tab(rows={"agent_devices": [revoked]})
        self.assertNotIn("agent_revoke_all", self.keys(at))


if __name__ == "__main__":
    unittest.main()
