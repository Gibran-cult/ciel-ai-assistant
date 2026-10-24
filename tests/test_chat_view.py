"""Chat page: answer display, source buttons, header counts and the rail."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import streamlit

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
sys.path.insert(0, str(ROOT))

from chat_sources import Source, answer_markdown, count_line, source_buttons_html, summarize  # noqa: E402
from tests.test_chat_sources import KOTO_SUMBER, RISET_TEXT, VASWANI_SUMBER  # noqa: E402
from tests.test_chat_store import ENV, SIGNED_IN, Response  # noqa: E402
from tests.test_theme import app_constants  # noqa: E402


class AnswerDisplayTest(unittest.TestCase):

    def test_answer_markdown_moves_sumber_to_buttons_and_keeps_leftover(self):
        text = ("Ringkasan.\n\nSumber:\n[1] Web — Judul — https://x.org/a\n[2] File lampiran — catatan.pdf\n\n"
                "(1 sumber dihapus karena tidak ada di hasil pencarian.)")
        md = answer_markdown(text)
        self.assertTrue(md.startswith("Ringkasan."))
        self.assertNotIn("https://x.org/a", md)
        self.assertIn("[2] File lampiran — catatan.pdf", md)
        self.assertIn("(1 sumber dihapus karena tidak ada di hasil pencarian.)", md)

    def test_sumber_without_any_link_stays_as_written(self):
        text = "Isi.\n\nSumber:\n[1] File lampiran — catatan.pdf"
        self.assertEqual(answer_markdown(text), text)

    def test_daftar_pustaka_stays_in_the_text(self):
        self.assertIn("## Daftar Pustaka", answer_markdown(RISET_TEXT))
        self.assertIn("https://jurnal.ugm.ac.id/jbs/article/view/123", answer_markdown(RISET_TEXT))

    def test_labels_become_badges_without_html(self):
        md = answer_markdown("1. Geometri lemah. [Dugaan]\n2. Rata 78. [Terverifikasi]")
        self.assertIn(":orange-badge[Dugaan]", md)
        self.assertIn(":blue-badge[Terverifikasi]", md)
        self.assertNotIn("<span", md)

    def test_source_html_is_escaped(self):
        html_out = source_buttons_html([Source(1, '<img src=x onerror=1>', "evil.org", "https://evil.org/a?b=<c>")])
        self.assertNotIn("<img", html_out)
        self.assertIn('href="https://evil.org/a?b=&lt;c&gt;"', html_out)
        self.assertIn('rel="noopener noreferrer"', html_out)

    def test_non_http_sources_never_become_links(self):
        self.assertEqual(source_buttons_html([Source(1, "x", "x", "javascript:alert(1)")]), "")

    def test_header_counts(self):
        messages = [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a\n\n" + VASWANI_SUMBER}]
        self.assertEqual(count_line(summarize(messages)), "4 sumber")
        messages.append({"role": "assistant", "content": "1. Data SmSA. [Dugaan]\n\n" + KOTO_SUMBER})
        self.assertEqual(count_line(summarize(messages)), "8 sumber · 1 belum ketemu")
        self.assertEqual(count_line(summarize([{"role": "assistant", "content": "Halo."}])), "")


class LabelBadgeTest(unittest.TestCase):

    def test_label_badges_use_ciel_colours_in_both_themes(self):
        # Streamlit paints badges with inline colours from its (dark) base
        # theme: 1.25:1 for "Dugaan" on light paper. UI_JS tags them by text
        # and the CSS points them at the tokens.
        js = app_constants()["UI_JS"]
        css = app_constants()["CIEL_CSS"]
        self.assertIn("badge.textContent === 'Dugaan'", js)
        self.assertIn(".stMarkdownBadge.ciel-guess { background: var(--c-gold) !important; color: var(--c-gold-ink) !important; }", css)
        self.assertIn(".stMarkdownBadge.ciel-ok { background: var(--c-accent-soft) !important; color: var(--c-accent) !important; }", css)


class CopyButtonScriptTest(unittest.TestCase):

    def test_copy_button_script_targets_finished_answers(self):
        js = app_constants()["UI_JS"]
        self.assertIn("navigator.clipboard", js)
        self.assertIn("execCommand('copy')", js)
        self.assertIn("Salin jawaban", js)
        self.assertIn("Tersalin", js)
        self.assertIn('[aria-label="Chat message from assistant"]', js)

    def test_copied_answer_includes_its_sources_and_is_read_at_click_time(self):
        # Final review: the Sumber block moved into separate buttons, so the
        # copy must add them back; the text is looked up when clicked.
        js = app_constants()["UI_JS"]
        self.assertIn(".ciel-srcs a", js)
        self.assertIn("const copyText = (answer) =>", js)
        self.assertIn("copyText(answer)", js)


def chat(messages, **extra):
    return {"c1": {"id": "c1", "title": "Model sentimen <IndoBERT>", "project_id": None, "updated": 100.0,
                   "messages": messages, **extra}}


class ChatPageTest(unittest.TestCase):

    def start(self, messages):
        from streamlit.testing.v1 import AppTest

        with patch.dict(os.environ, {**ENV, "MEMORY_ADMIN_FLOW_ID": "", "RESEARCH_FLOW_ID": "", "WRITER_FLOW_ID": ""}), \
                patch.object(streamlit, "user", {}), patch("requests.post", Mock(return_value=Response({}))):
            at = AppTest.from_file(str(APP_PATH), default_timeout=60)
            at.session_state["chats"] = chat(messages)
            at.session_state["active_chat"] = "c1"
            at.run()
        self.assertFalse(at.exception)
        return at

    def text(self, at):
        return " ".join(md.value for md in at.markdown)

    def rail(self, at):
        found = [c for c in at.main.children.values() if getattr(c, "key", None) == "rail"]
        return found

    def test_rail_lists_sources_guesses_and_riset_facts(self):
        at = self.start([
            {"role": "user", "content": "Ringkas Vaswani"},
            {"role": "assistant", "content": "Ringkasan.\n\n" + VASWANI_SUMBER, "error": False},
            {"role": "user", "content": "analisis: data"},
            {"role": "assistant", "content": "1. Nilai geometri rendah. [Dugaan]", "error": False},
            {"role": "user", "content": "Riset Skripsi: UMKM"},
            {"role": "assistant", "content": RISET_TEXT, "error": False, "kind": "riset_skripsi", "topic": "UMKM", "elapsed": 112},
        ])
        text = self.text(at)
        self.assertIn('class="ciel-rail"', text)
        self.assertIn("Sumber di chat ini", text)
        self.assertIn("Attention Is All You Need (Vaswani dkk., 2017)", text)
        self.assertIn("Belum ketemu", text)
        self.assertIn("Nilai geometri rendah.", text)
        self.assertIn("Riset ini", text)
        self.assertIn("1 m 52 d", text)
        self.assertIn("Model sentimen &lt;IndoBERT&gt;", text)
        self.assertIn("7 sumber · 1 belum ketemu", text)
        self.assertIn('class="ciel-srcs"', text)  # buttons under the Vaswani answer

    def test_rail_hidden_when_chat_has_nothing_to_show(self):
        at = self.start([{"role": "user", "content": "Halo"}, {"role": "assistant", "content": "Halo juga.", "error": False}])
        self.assertNotIn('class="ciel-rail"', self.text(at))
        self.assertIn("<h1>Model sentimen &lt;IndoBERT&gt;</h1>", self.text(at))

    def test_old_chat_without_new_fields_renders(self):
        at = self.start([
            {"role": "user", "content": "Pertanyaan lama"},
            {"role": "assistant", "content": "Jawaban lama tanpa kind dan elapsed."},
            {"role": "user", "content": "Lagi"},
            {"role": "assistant", "content": "Permintaan gagal diproses. Silakan coba lagi.", "error": True},
        ])
        self.assertIn("retry_3", [b.key for b in at.button])

    def test_new_answers_record_how_long_they_took(self):
        from streamlit.testing.v1 import AppTest

        answer = {"outputs": [{"outputs": [{"results": {"message": {"data": {"text": "Jawaban."}}}}]}]}
        with patch.dict(os.environ, {**ENV, "MEMORY_ADMIN_FLOW_ID": ""}), patch.object(streamlit, "user", {}), \
                patch("requests.post", Mock(return_value=Response(answer))):
            at = AppTest.from_file(str(APP_PATH), default_timeout=60)
            at.run()
            at.session_state["pending"] = {"text": "Halo", "files": [], "images": [], "payload": "Halo"}
            at.run()
        (stored,) = at.session_state["chats"].values()
        self.assertIsInstance(stored["messages"][-1]["elapsed"], int)


if __name__ == "__main__":
    unittest.main()
