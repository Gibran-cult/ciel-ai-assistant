"""Kerangka Bab 1-3 end to end (AppTest): button, gate, writer flow, citations, DOCX."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import streamlit

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
sys.path.insert(0, str(ROOT))

from tests.test_chat_store import ENV, SIGNED_IN, Response  # noqa: E402

SECRETS = {
    "auth": {"redirect_uri": "http://localhost/oauth2callback"},
    "SUPABASE_URL": "https://db.example.invalid",
    "SUPABASE_SERVICE_KEY": "service-key",
    "WRITER_FLOW_ID": "writer-flow-id",
}

SOURCE_MAP = (
    "# Peta Sumber: Literasi digital UMKM\n\nRingkasan [1][2].\n\n"
    "## Daftar Pustaka\n\n[1] Sari, D. (2023). *Judul A*. https://example.org/a\n\n"
    "[2] Putra, A. (2024). *Judul B*. https://example.org/b"
)

# [9] and the model's own reference list must not reach the user.
ANSWER = (
    "# Kerangka Bab 1–3: Literasi digital UMKM\n\n## BAB I PENDAHULUAN\n### 1.1 Latar Belakang\n"
    "- Poin yang didukung [1][9]\n\n## Daftar Pustaka\n[9] Karangan. (2099). https://karangan.example"
)


def chats():
    return {"c1": {
        "id": "c1", "title": "Riset Skripsi: Literasi digital UMKM", "project_id": None, "updated": 100.0,
        "messages": [
            {"role": "user", "content": "Riset Skripsi: Literasi digital UMKM", "files": [], "images": []},
            {"role": "assistant", "content": SOURCE_MAP, "error": False,
             "kind": "riset_skripsi", "topic": "Literasi digital UMKM"},
        ],
    }}


def database(expires_at):
    rows = {"pro_members": [{"expires_at": expires_at}] if expires_at else []}
    return Mock(side_effect=lambda method, url, **kw: Response(rows.get(url.rsplit("/", 1)[1], [])))


class KerangkaAppTest(unittest.TestCase):

    def run_app(self, expires_at, map_index=1, secrets=None):
        from streamlit.testing.v1 import AppTest

        answer = {"outputs": [{"outputs": [{"results": {"message": {"data": {"text": ANSWER}}}}]}]}
        post = Mock(return_value=Response(answer))

        # Empty variables win over a parent .env (app.py calls load_dotenv), so
        # only the secrets below decide whether the feature is on.
        with patch.dict(os.environ, {**ENV, "WRITER_FLOW_ID": "", "RESEARCH_FLOW_ID": ""}), \
                patch.object(streamlit, "user", SIGNED_IN), \
                patch("requests.request", database(expires_at)), patch("requests.post", post):
            at = AppTest.from_file(str(APP_PATH), default_timeout=60)
            for key, value in (SECRETS if secrets is None else secrets).items():
                at.secrets[key] = value
            at.session_state["chats"] = chats()
            at.session_state["active_chat"] = "c1"
            at.run()
            self.buttons = [b.key for b in at.button]
            if map_index is not None:
                at.session_state["pending"] = {
                    "text": "Kerangka Bab 1–3: Literasi digital UMKM", "files": [], "images": [], "payload": "",
                    "kerangka": {"topic": "Literasi digital UMKM", "approach": "Kuantitatif",
                                 "object": "UMKM Bandung", "map_index": map_index},
                }
                at.run()

        self.runs = [c for c in post.call_args_list if "/api/v1/run/" in c.args[0]]
        return at

    def test_pro_account_gets_a_kerangka_from_the_writer_flow(self):
        at = self.run_app("2999-01-01T00:00:00+00:00")
        self.assertFalse(at.exception)
        self.assertIn("rsframe_c1_1", self.buttons)  # under the source map

        (run,) = self.runs
        self.assertTrue(run.args[0].endswith("/api/v1/run/writer-flow-id"))
        self.assertEqual(run.kwargs["timeout"], 240)
        sent = run.kwargs["json"]["input_value"]
        self.assertTrue(sent.startswith(
            "[KERANGKA]\nTopik skripsi: Literasi digital UMKM\nPendekatan penelitian: Kuantitatif"))
        self.assertIn("Objek atau lokasi penelitian: UMKM Bandung", sent)
        self.assertIn("PETA SUMBER:\n# Peta Sumber: Literasi digital UMKM", sent)
        self.assertNotIn("tweaks", run.kwargs["json"])

        messages = at.session_state["chats"]["c1"]["messages"]
        reply = messages[-1]
        self.assertEqual((reply["kind"], reply["topic"], reply["error"]),
                         ("kerangka_skripsi", "Literasi digital UMKM", False))
        self.assertIn("- Poin yang didukung [1]", reply["content"])
        self.assertNotIn("[9]", reply["content"])
        self.assertNotIn("karangan", reply["content"])
        self.assertIn("## Daftar Pustaka (dari peta sumber)", reply["content"])
        self.assertIn("[2] Putra, A. (2024).", reply["content"])
        self.assertEqual(messages[-2]["kerangka"]["map_index"], 1)  # kept for "Coba lagi"
        # AppTest gives download buttons no key: one for the map, one for the kerangka.
        self.assertEqual(len(at.get("download_button")), 2)

    def test_free_account_is_refused_before_the_writer_flow(self):
        at = self.run_app(None)
        self.assertFalse(at.exception)
        self.assertEqual(self.runs, [])
        reply = at.session_state["chats"]["c1"]["messages"][-1]
        self.assertTrue(reply["error"])
        self.assertIn("Kerangka Bab 1–3 khusus Ciel Pro", reply["content"])

    def test_missing_source_map_is_refused(self):
        at = self.run_app("2999-01-01T00:00:00+00:00", map_index=0)  # index 0 is the user message
        self.assertFalse(at.exception)
        self.assertEqual(self.runs, [])
        self.assertIn("Peta sumber tidak ditemukan", at.session_state["chats"]["c1"]["messages"][-1]["content"])

    def test_button_is_hidden_without_the_writer_flow(self):
        secrets = {k: v for k, v in SECRETS.items() if k != "WRITER_FLOW_ID"}
        at = self.run_app("2999-01-01T00:00:00+00:00", map_index=None, secrets=secrets)
        self.assertFalse(at.exception)
        self.assertNotIn("rsframe_c1_1", self.buttons)
        self.assertEqual(len(at.get("download_button")), 1)  # the map's "Unduh DOCX" stays


if __name__ == "__main__":
    unittest.main()
