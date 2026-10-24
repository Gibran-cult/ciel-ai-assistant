"""Beranda end to end (AppTest): greeting, centred composer, templates, panels."""

import os
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import streamlit

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
sys.path.insert(0, str(ROOT))

from tests.test_chat_store import ENV, SIGNED_IN, Response  # noqa: E402

FEATURES = {
    "SUPABASE_URL": "https://db.example.invalid",
    "SUPABASE_SERVICE_KEY": "service-key",
    "WRITER_FLOW_ID": "writer-flow-id",
    "RESEARCH_FLOW_ID": "research-flow-id",
}
MAP = "# Peta Sumber: UMKM\n\n## Daftar Pustaka\n\n[1] Sari, D. (2023). *Judul A*. https://example.org/a"
ANSWER = {"outputs": [{"outputs": [{"results": {"message": {"data": {"text": "Jawaban Ciel."}}}}]}]}


def chat(chat_id, project, updated, riset=False, title=None):
    reply = {"role": "assistant", "content": MAP if riset else "Jawaban.", "error": False}
    if riset:
        reply.update(kind="riset_skripsi", topic="UMKM")
    return {"id": chat_id, "title": title or f"Chat {chat_id}", "project_id": project, "updated": updated,
            "messages": [{"role": "user", "content": "q", "files": [], "images": []}, reply]}


def no_database():
    return Mock(side_effect=lambda method, url, **kw: Response([]))


class BerandaAppTest(unittest.TestCase):

    def start(self, user=None, secrets=None, chats=None, projects=None, project=None, env=None, post=None):
        from streamlit.testing.v1 import AppTest

        self.post = post or Mock(return_value=Response(ANSWER))
        self.patches = [
            patch.dict(os.environ, {**ENV, "WRITER_FLOW_ID": "", "RESEARCH_FLOW_ID": "", "MEMORY_ADMIN_FLOW_ID": "", **(env or {})}),
            patch.object(streamlit, "user", user or {}),
            patch("requests.request", no_database()),
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
        if chats is not None:
            at.session_state["chats"] = chats
        if projects is not None:
            at.session_state["projects"] = projects
            at.session_state["active_project"] = project
        at.run()
        self.assertFalse(at.exception)
        return at

    def text(self, at):
        return " ".join(md.value for md in at.markdown)

    def keys(self, at):
        return [b.key for b in at.button]

    def test_beranda_shows_greeting_composer_and_templates(self):
        at = self.start()
        self.assertRegex(self.text(at), r"(Pagi|Siang|Sore|Malam)\.")
        self.assertIn("Semua chat · 0 chat", self.text(at))
        self.assertEqual(len(at.chat_input), 1)
        self.assertEqual(at.chat_input[0].placeholder, "Tanyakan sesuatu kepada Ciel...")
        for key in ("tpl_jelasin", "tpl_analisis", "tpl_cek_referensi"):
            self.assertIn(key, self.keys(at))
        # Riset Skripsi and Kerangka are off in this deployment, and there is no project file.
        for key in ("tpl_cari_jurnal", "tpl_kerangka", "tpl_ringkas_file"):
            self.assertNotIn(key, self.keys(at))

    def test_fill_template_puts_text_in_the_composer(self):
        at = self.start()
        at.button(key="tpl_jelasin").click().run()
        # Streamlit writes the text into the field (set_value) without
        # submitting it; the student edits the brackets and presses Enter.
        proto = at.chat_input(key="composer").proto
        self.assertTrue(proto.set_value)
        self.assertEqual(proto.value, "Jelasin [konsep] pelan-pelan pakai contoh angka, lalu kasih 2 soal latihan.")
        self.assertEqual(len(at.chat_message), 0)

    def test_project_with_files_and_a_map_shows_all_six(self):
        projects = {"p1": {"id": "p1", "name": "Skripsi ojol", "created": 0,
                           "files": [{"name": "bab1.md", "text": "isi", "size": 3}]}}
        at = self.start(user=SIGNED_IN, secrets=FEATURES, chats={"c1": chat("c1", "p1", 100, riset=True)},
                        projects=projects, project="p1")
        self.assertIn("Skripsi ojol · 1 chat · 1 file proyek", self.text(at))
        self.assertEqual(at.chat_input[0].placeholder, "Tanya soal skripsimu")
        tpl = [key for key in self.keys(at) if key.startswith("tpl_")]
        self.assertEqual(tpl, ["tpl_cari_jurnal", "tpl_jelasin", "tpl_analisis", "tpl_cek_referensi", "tpl_ringkas_file", "tpl_kerangka"])
        self.assertEqual(at.button(key="tpl_cari_jurnal").label, "Cari jurnal · Pro")

    def test_kerangka_template_opens_the_latest_map(self):
        chats = {"c1": chat("c1", None, 100, riset=True), "c2": chat("c2", None, 200)}
        at = self.start(user=SIGNED_IN, secrets=FEATURES, chats=chats)
        at.button(key="tpl_kerangka").click().run()
        self.assertEqual(at.session_state["active_chat"], "c1")
        # The Kerangka dialog is open (a free account sees its Pro offer).
        self.assertIn("Lihat paket Pro", [b.label for b in at.button])
        self.assertNotIn("tpl_jelasin", self.keys(at))  # the chat is open now

    def test_submitting_from_beranda_shows_the_chat(self):
        # AppTest cannot submit a chat input that accepts files (its value
        # needs an upload state), so the submitted request is set directly;
        # the composer path itself is checked in the browser.
        at = self.start()
        at.session_state["pending"] = {"text": "Halo Ciel", "files": [], "images": [], "payload": "Halo Ciel"}
        at.run()
        self.assertFalse(at.exception)
        self.assertNotIn("tpl_jelasin", self.keys(at))
        self.assertEqual(len(at.chat_message), 2)
        self.assertIn("Jawaban Ciel.", self.text(at))

    def test_beranda_is_only_cleared_once_a_request_is_pending(self):
        # A submit that makes no request (an over-long crafted message) must
        # leave the Beranda, and its composer, on screen.
        source = APP_PATH.read_text(encoding="utf-8").replace("\r\n", "\n")
        self.assertIn("        take_composer_value(render_beranda())\n\n    if st.session_state.pending:\n        beranda_slot.empty()", source)

    def test_kerangka_topic_falls_back_to_riset_skripsi(self):
        source = APP_PATH.read_text(encoding="utf-8")
        self.assertIn('topic = chat["messages"][index].get("topic") or "Riset Skripsi"', source)

    def test_guest_beranda_never_lists_memories(self):
        at = self.start(env={"MEMORY_ADMIN_FLOW_ID": "mem-flow"})
        self.assertNotIn("Yang Ciel ingat", self.text(at))
        self.assertFalse([c for c in self.post.call_args_list if "mem-flow" in str(c)])

    def test_memory_listing_runs_once_even_when_it_fails(self):
        import requests
        post = Mock(side_effect=requests.exceptions.ConnectionError("down"))
        at = self.start(user=SIGNED_IN, env={"MEMORY_ADMIN_FLOW_ID": "mem-flow"}, post=post)
        at.run()
        at.run()
        self.assertEqual(len([c for c in post.call_args_list if "mem-flow" in str(c)]), 1)
        self.assertNotIn("Yang Ciel ingat", self.text(at))

    def test_slow_memory_listing_gives_up_quickly(self):
        # Final review: the listing blocks the Beranda's run, so it must not
        # use memory_admin's 60 s default.
        import requests
        post = Mock(side_effect=requests.exceptions.Timeout("slow"))
        at = self.start(user=SIGNED_IN, env={"MEMORY_ADMIN_FLOW_ID": "mem-flow"}, post=post)
        calls = [c for c in post.call_args_list if "mem-flow" in str(c)]
        self.assertEqual(len(calls), 1)
        self.assertLessEqual(calls[0].kwargs["timeout"], 8)
        self.assertNotIn("Yang Ciel ingat", self.text(at))

    def test_memories_show_when_listing_works(self):
        listing = {"ok": True, "total": 2, "memories": [{"id": "m1", "text": "Format sitasi APA 7"}, {"id": "m2", "text": "Suka contoh <angka>"}]}
        reply = {"outputs": [{"outputs": [{"results": {"message": {"data": {"text": __import__("json").dumps(listing)}}}}]}]}
        at = self.start(user=SIGNED_IN, env={"MEMORY_ADMIN_FLOW_ID": "mem-flow"}, post=Mock(return_value=Response(reply)))
        text = self.text(at)
        self.assertIn("Yang Ciel ingat", text)
        self.assertIn("Format sitasi APA 7", text)
        self.assertIn("Suka contoh &lt;angka&gt;", text)

    def test_lanjutkan_riset_lists_three_latest_chats(self):
        chats = {f"c{i}": chat(f"c{i}", None, 100 + i, title=f"Judul {i}") for i in range(5)}
        chats["c4"]["archived"] = True
        at = self.start(chats=chats)
        recent = [key for key in self.keys(at) if key.startswith("home_chat_")]
        self.assertEqual(recent, ["home_chat_c3", "home_chat_c2", "home_chat_c1"])
        at.button(key="home_chat_c2").click().run()
        self.assertEqual(at.session_state["active_chat"], "c2")


if __name__ == "__main__":
    unittest.main()
