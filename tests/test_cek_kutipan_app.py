"""Cek kutipan & kemiripan end to end (AppTest): button, gate, no Langflow call, report, draft not kept."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import streamlit

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
sys.path.insert(0, str(ROOT))

from tests.test_chat_store import CONSENTED, ENV, SIGNED_IN, Response  # noqa: E402

SECRETS = {
    "auth": {"redirect_uri": "http://localhost/oauth2callback"},
    "SUPABASE_URL": "https://db.example.invalid",
    "SUPABASE_SERVICE_KEY": "service-key",
}

SOURCE_MAP = (
    "# Peta Sumber: Literasi digital UMKM\n\nRingkasan [1][2].\n\n"
    "## Daftar Pustaka\n\n[1] Dewi Sari. (2023). *Judul A*. https://example.org/a\n\n"
    "[2] Adi Putra. (2024). *Judul B*. https://example.org/b"
)
EXCERPT = (
    "Literasi digital memiliki pengaruh yang kuat terhadap kemampuan pelaku usaha mikro "
    "dalam memasarkan produk secara daring di berbagai kota."
)
DRAFT = (
    f"{EXCERPT} Menurut Sari (2023), pelatihan juga penting bagi pelaku usaha kecil. "
    "Penelitian lain menemukan hal berbeda (Wijaya, 2021). Bab ini ditulis sendiri sebagai latihan."
)


def chats():
    return {"c1": {
        "id": "c1", "title": "Riset Skripsi: Literasi digital UMKM", "project_id": None, "updated": 100.0,
        "messages": [
            {"role": "user", "content": "Riset Skripsi: Literasi digital UMKM", "files": [], "images": []},
            {"role": "assistant", "content": SOURCE_MAP, "error": False, "kind": "riset_skripsi",
             "topic": "Literasi digital UMKM", "excerpts": {"2": [EXCERPT]}},
        ],
    }}


def database(expires_at):
    rows = {**CONSENTED, "pro_members": [{"expires_at": expires_at}] if expires_at else []}
    return Mock(side_effect=lambda method, url, **kw: Response(rows.get(url.rsplit("/", 1)[1], [])))


class CekKutipanAppTest(unittest.TestCase):

    def run_app(self, expires_at, map_index=1, secrets=SECRETS):
        from streamlit.testing.v1 import AppTest

        post = Mock(return_value=Response({}))

        # Empty variables win over a parent .env (app.py calls load_dotenv).
        with patch.dict(os.environ, {**ENV, "WRITER_FLOW_ID": "", "RESEARCH_FLOW_ID": ""}), \
                patch.object(streamlit, "user", SIGNED_IN), \
                patch("requests.request", database(expires_at)), patch("requests.post", post):
            at = AppTest.from_file(str(APP_PATH), default_timeout=60)
            for key, value in secrets.items():
                at.secrets[key] = value
            at.session_state["chats"] = chats()
            at.session_state["active_chat"] = "c1"
            at.run()
            self.buttons = [b.key for b in at.button]
            if map_index is not None:
                at.session_state["pending"] = {
                    "text": "Cek kutipan & kemiripan: Literasi digital UMKM (52 kata)",
                    "files": [], "images": [], "payload": "",
                    "cek": {"topic": "Literasi digital UMKM", "draft": DRAFT, "map_index": map_index},
                }
                at.run()

        self.runs = [c for c in post.call_args_list if "/api/v1/run/" in c.args[0]]
        self.saves = [c.kwargs["json"] for c in post.call_args_list if c.args[0].endswith("/rest/v1/chats")]
        return at

    def test_pro_account_gets_a_report_without_any_model_call(self):
        at = self.run_app("2999-01-01T00:00:00+00:00")
        self.assertFalse(at.exception)
        self.assertIn("rscheck_c1_1", self.buttons)
        self.assertEqual(self.runs, [])

        messages = at.session_state["chats"]["c1"]["messages"]
        reply = messages[-1]
        self.assertEqual((reply["kind"], reply["topic"], reply["error"]), ("cek_kutipan", "Literasi digital UMKM", False))
        self.assertIn("100% rangkaian katanya sama dengan cuplikan sumber [2]", reply["content"])
        self.assertIn("- [1] Sari, 2023: dikutip 1 kali.", reply["content"])
        self.assertIn("(Wijaya, 2021): tidak ada di peta sumber", reply["content"])
        # The draft is not kept once the check succeeded, in the session or in Supabase.
        self.assertEqual(messages[-2]["cek"], {"topic": "Literasi digital UMKM", "map_index": 1})
        self.assertTrue(self.saves)
        self.assertNotIn("Bab ini ditulis sendiri", str(self.saves[-1]["messages"][-2]))

    def test_free_account_is_refused_and_the_draft_kept_for_retry(self):
        at = self.run_app(None)
        self.assertFalse(at.exception)
        messages = at.session_state["chats"]["c1"]["messages"]
        self.assertTrue(messages[-1]["error"])
        self.assertIn("Cek kutipan & kemiripan khusus Ciel Pro", messages[-1]["content"])
        self.assertEqual(messages[-2]["cek"]["draft"], DRAFT)

    def test_missing_source_map_is_refused(self):
        at = self.run_app("2999-01-01T00:00:00+00:00", map_index=0)
        self.assertFalse(at.exception)
        content = at.session_state["chats"]["c1"]["messages"][-1]["content"]
        self.assertIn("Peta sumber tidak ditemukan", content)
        self.assertIn('klik "Cek kutipan & kemiripan"', content)

    def test_button_is_hidden_without_supabase(self):
        secrets = {"auth": SECRETS["auth"]}
        at = self.run_app(None, map_index=None, secrets=secrets)
        self.assertFalse(at.exception)
        self.assertNotIn("rscheck_c1_1", self.buttons)


if __name__ == "__main__":
    unittest.main()
