"""Gerbang persetujuan Syarat dan Ketentuan serta Privasi setelah login (AppTest)."""

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

from terms import LEGAL_VERSION  # noqa: E402
from tests.test_chat_store import ENV, SIGNED_IN, SIGNED_IN_OWNER, Response  # noqa: E402

FEATURES = {"SUPABASE_URL": "https://db.example.invalid", "SUPABASE_SERVICE_KEY": "service-key"}
ANSWER = {"outputs": [{"outputs": [{"results": {"message": {"data": {"text": "Jawaban Ciel."}}}}]}]}


class ConsentAppTest(unittest.TestCase):

    def start(self, user=SIGNED_IN, rows=None, down=(), post_down=(), env=None, query=None):
        """Jalankan app. `rows` = {tabel: baris} untuk GET, `down` / `post_down` = tabel yang gagal."""
        from streamlit.testing.v1 import AppTest

        self.rows = rows if rows is not None else {}
        self.down, self.post_down = set(down), set(post_down)
        self.post = Mock(side_effect=self.posting)
        self.request = Mock(side_effect=self.database)
        self.patches = [
            patch.dict(os.environ, {**ENV, **FEATURES, "WRITER_FLOW_ID": "", "RESEARCH_FLOW_ID": "", **(env or {})}),
            patch.object(streamlit, "user", user or {}),
            patch("requests.request", self.request),
            patch("requests.post", self.post),
        ]
        for item in self.patches:
            item.start()
        self.addCleanup(lambda: [item.stop() for item in reversed(self.patches)])
        at = AppTest.from_file(str(APP_PATH), default_timeout=60)
        if user:
            at.secrets["auth"] = {"redirect_uri": "http://localhost/oauth2callback"}
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

    def posting(self, url, **kwargs):
        if url.rsplit("/", 1)[1] in self.post_down:
            raise requests.exceptions.ConnectionError("down")
        return Response(ANSWER)

    def text(self, at):
        return " ".join(md.value for md in at.markdown)

    def consent_posts(self):
        return [c.kwargs["json"] for c in self.post.call_args_list if c.args[0].endswith("/rest/v1/consents")]

    def test_signed_in_without_consent_sees_the_gate_not_the_composer(self):
        at = self.start(rows={"consents": []})
        self.assertIn("Sebelum mulai", self.text(at))
        self.assertEqual(len(at.chat_input), 0)

    def test_accept_needs_the_checkbox_and_saves_the_version(self):
        at = self.start(rows={"consents": []})
        self.assertTrue(at.button(key="consent_accept").disabled)

        at.checkbox(key="consent_check").check().run()
        self.assertFalse(at.button(key="consent_accept").disabled)
        at.button(key="consent_accept").click().run()

        self.assertFalse(at.exception)
        self.assertEqual(self.consent_posts(), [{"owner": SIGNED_IN_OWNER, "version": LEGAL_VERSION}])
        self.assertNotIn("Sebelum mulai", self.text(at))
        self.assertEqual(len(at.chat_input), 1)

    def test_current_consent_skips_the_gate(self):
        at = self.start(rows={"consents": [{"version": LEGAL_VERSION}]})
        self.assertNotIn("Sebelum mulai", self.text(at))
        self.assertEqual(len(at.chat_input), 1)

    def test_older_version_asks_again(self):
        at = self.start(rows={"consents": [{"version": "2026-01-01"}]})
        self.assertIn("Sebelum mulai", self.text(at))

    def test_database_down_does_not_lock_the_user_out(self):
        with self.assertLogs("ciel_ai", level="WARNING") as logs:
            at = self.start(down={"consents"})
        self.assertNotIn("Sebelum mulai", self.text(at))
        self.assertEqual(len(at.chat_input), 1)
        self.assertTrue(any("consent_load_failed" in line for line in logs.output))

    def test_failed_save_still_lets_the_user_in(self):
        at = self.start(rows={"consents": []}, post_down={"consents"})
        at.checkbox(key="consent_check").check().run()
        with self.assertLogs("ciel_ai", level="ERROR") as logs:
            at.button(key="consent_accept").click().run()
        self.assertFalse(at.exception)
        self.assertEqual(len(at.chat_input), 1)
        self.assertTrue(any("consent_save_failed" in line for line in logs.output))

    def test_anonymous_visitor_never_sees_the_gate(self):
        at = self.start(user=None)
        self.assertNotIn("Sebelum mulai", self.text(at))
        self.assertFalse([c for c in self.request.call_args_list if c.args[1].endswith("/consents")])

    def test_gate_terms_button_shows_the_terms_over_the_gate(self):
        at = self.start(rows={"consents": []})
        at.button(key="consent_terms").click().run()
        self.assertFalse(at.exception)
        self.assertIn("<h1>Syarat dan Ketentuan</h1>", self.text(at))
        self.assertIn("Sebelum mulai", self.text(at))

    def test_gate_hides_the_sidebar_and_every_feature(self):
        # Nothing may process data before consent: no Riset, projects, new chat, or settings.
        at = self.start(rows={"consents": []}, env={"RESEARCH_FLOW_ID": "riset-flow"})
        keys = [b.key for b in at.button]
        for key in ("riset_open", "createproj", "newchat", "opensettings"):
            self.assertNotIn(key, keys)
        self.assertEqual(len(at.sidebar.button), 0)

    def test_gate_keeps_a_pricing_link_for_after_consent(self):
        at = self.start(rows={"consents": []}, query={"page": "pricing"})
        self.assertIn("Sebelum mulai", self.text(at))
        self.assertNotIn("pro_buy", [b.key for b in at.button])


if __name__ == "__main__":
    unittest.main()
