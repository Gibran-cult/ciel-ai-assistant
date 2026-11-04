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

from chat_sources import Source, answer_parts, count_line, source_buttons_html, summarize  # noqa: E402
from tests.test_chat_sources import KOTO_SUMBER, RISET_TEXT, VASWANI_SUMBER  # noqa: E402
from tests.test_chat_store import ENV, SIGNED_IN, Response  # noqa: E402
from tests.test_theme import app_constants  # noqa: E402


class AnswerDisplayTest(unittest.TestCase):

    def test_sumber_moves_to_buttons_and_leftover_shows_below_them(self):
        # Spec 4: URL-less entries and the guard note stay as text *under*
        # the source buttons.
        text = ("Ringkasan.\n\nSumber:\n[1] Web — Judul — https://x.org/a\n[2] File lampiran — catatan.pdf\n\n"
                "(1 sumber dihapus karena tidak ada di hasil pencarian.)")
        before, sources, after = answer_parts(text)
        self.assertEqual(before, "Ringkasan.")
        self.assertEqual([s.url for s in sources], ["https://x.org/a"])
        self.assertNotIn("https://x.org/a", before + after)
        self.assertIn("[2] File lampiran — catatan.pdf", after)
        self.assertIn("(1 sumber dihapus karena tidak ada di hasil pencarian.)", after)

    def test_sumber_without_any_link_stays_as_written(self):
        text = "Isi.\n\nSumber:\n[1] File lampiran — catatan.pdf"
        self.assertEqual(answer_parts(text), (text, [], ""))

    def test_daftar_pustaka_stays_in_the_text(self):
        before, sources, after = answer_parts(RISET_TEXT)
        self.assertIn("## Daftar Pustaka", before)
        self.assertIn("https://jurnal.ugm.ac.id/jbs/article/view/123", before)
        self.assertEqual((sources, after), ([], ""))

    def test_labels_become_badges_without_html(self):
        before, _, _ = answer_parts("1. Geometri lemah. [Dugaan]\n2. Rata 78. [Terverifikasi]")
        self.assertIn(":orange-badge[Dugaan]", before)
        self.assertIn(":blue-badge[Terverifikasi]", before)
        self.assertNotIn("<span", before)
        _, _, after = answer_parts("Isi.\n\nSumber: [1] A — B — https://a.org\n\nPoin lanjutan. [Dugaan]")
        self.assertIn(":orange-badge[Dugaan]", after)

    def test_source_pills_have_a_readable_name(self):
        html_out = source_buttons_html([Source(2, "IndoNLU", "arxiv.org", "https://arxiv.org/abs/2009.05387")])
        self.assertIn('aria-label="Sumber 2: IndoNLU, arxiv.org (buka di tab baru)"', html_out)

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

    def test_download_button_css_leaves_the_icon_font_alone(self):
        css = app_constants()["CIEL_CSS"]
        rules = [r for r in css.split("}") if "st-key-ansimg_" in r]
        self.assertTrue(rules)
        for rule in rules:
            selector, _, body = rule.partition("{")
            if "stIconMaterial" in selector:
                self.assertNotIn("font:", body)
                self.assertNotIn("font-family", body)
            elif not selector.rstrip().endswith("p"):
                self.assertNotIn("font:", body)
                self.assertNotIn("font-family", body)
        joined = "".join(rules)
        self.assertIn("margin-top: 0.5rem", joined)
        self.assertIn(":focus-visible", joined)

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

    def test_hostile_sources_render_as_escaped_text_end_to_end(self):
        at = self.start([
            {"role": "user", "content": "q"},
            {"role": "assistant", "error": False, "content": (
                "Isi.\n\nSumber: [1] Evil — <script>alert(1)</script> — javascript:alert(1) "
                "[2] Web — <img src=x onerror=alert(2)> — https://ok.org/a")},
            {"role": "user", "content": "Riset Skripsi: x"},
            {"role": "assistant", "error": False, "kind": "riset_skripsi", "topic": "x", "content": (
                "# Peta\n\n## Daftar Pustaka\n\n[1] A. (2020). *<b onmouseover=alert(3)>T</b>*. https://ok.org/b")},
        ])
        html_parts = [md.value for md in at.markdown if "ciel-src" in md.value or "ciel-rail" in md.value]
        self.assertTrue(html_parts)
        for part in html_parts:
            with self.subTest(part=part[:60]):
                self.assertNotIn("<script", part)
                self.assertNotIn("<img", part)
                self.assertNotIn("<b onmouseover", part)
                self.assertNotIn('href="javascript:', part)

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


class VisualAnswerTest(unittest.TestCase):
    """Graphs, quizzes and callouts in answers (Task 4) and download buttons (Task 6)."""

    start = ChatPageTest.start
    text = ChatPageTest.text

    def answer(self, content, request="jelaskan"):
        return self.start([
            {"role": "user", "content": request},
            {"role": "assistant", "error": False, "content": content},
        ])

    def test_visual_block_renders_as_figure(self):
        from tests.test_answer_blocks import GRAFIK

        at = self.answer(f"Lihat grafik ini.\n\n{GRAFIK}\n\nSelesai.")
        # st.html runs DOMPurify's html profile, which strips every SVG element, so the
        # figure goes through st.markdown(unsafe_allow_html=True) as one HTML block.
        figures = self.figures(at)
        self.assertEqual(len(figures), 1)
        self.assertTrue(figures[0].value.startswith('<figure class="ciel-visual">'))
        self.assertNotIn("\n\n", figures[0].value)   # a blank line would end the HTML block
        self.assertFalse([el for el in at.get("html") if "ciel-visual" in el.proto.body])
        self.assertFalse([md for md in at.markdown if "jenis" in md.value])

    def figures(self, at):
        return [md for md in at.markdown if "ciel-visual" in md.value and "<svg" in md.value]

    def test_wrong_choice_shows_the_answer_as_math(self):
        quiz = '```ciel-kuis\n{"soal": "Turunan dari $x^3$?", "pilihan": ["$3x^2$", "$x^2$"], "jawaban": 0}\n```'
        at = self.answer(quiz)
        at.radio[0].set_value(1)
        at.run()
        next(b for b in at.button if b.label == "Cek jawaban").click()
        at.run()
        self.assertFalse(at.exception)
        self.assertIn("Belum tepat", self.text(at))
        self.assertIn("Jawabannya: $3x^2$", [md.value for md in at.markdown])
        self.assertFalse([md for md in at.markdown if "&#x27;" in md.value or "\\$3x" in md.value])

    def test_quiz_checks_the_choice(self):
        from tests.test_answer_blocks import KUIS

        at = self.answer(f"Coba ini.\n\n{KUIS}")
        self.assertIn("Coba sendiri", self.text(at))
        at.radio[0].set_value("±3")
        at.run()
        next(b for b in at.button if b.label == "Cek jawaban").click()
        at.run()
        self.assertFalse(at.exception)
        self.assertIn("Benar", self.text(at))
        self.assertEqual(len(at.session_state["chats"]["c1"]["messages"]), 2)

    def test_broken_block_shows_note_not_json(self):
        at = self.answer('Ini:\n\n```ciel-grafik\n{"jenis": "pie"}\n```\n\nSelesai.')
        self.assertIn("Grafik ini tidak bisa ditampilkan.", [c.value for c in at.caption])
        self.assertFalse([md for md in at.markdown if '"pie"' in md.value or "jenis" in md.value])

    def test_plain_answer_unchanged(self):
        at = self.answer("Pecahan adalah **bagian** dari keseluruhan.")
        self.assertIn("Pecahan adalah **bagian** dari keseluruhan.", [md.value for md in at.markdown])
        self.assertFalse(self.figures(at))

    def test_fixture_renders_every_kind_and_wrong_choice_is_explained(self):
        fixture = ROOT / ".superpowers" / "sdd" / "2026-11-04-ciel-visual-answers" / "ui-fixture.md"
        if not fixture.exists():
            self.skipTest("fixture not present")
        at = self.answer(fixture.read_text(encoding="utf-8"))
        self.assertEqual(len(self.figures(at)), 4)
        self.assertFalse([md for md in self.figures(at) if "\n\n" in md.value])
        self.assertEqual(len(at.expander), 1)
        self.assertIn("Grafik ini tidak bisa ditampilkan.", [c.value for c in at.caption])
        at.radio[0].set_value(0)
        at.run()
        next(b for b in at.button if b.label == "Cek jawaban").click()
        at.run()
        self.assertIn("Belum tepat", self.text(at))

    def test_quiz_widget_keys_never_match_the_card_selector(self):
        from tests.test_answer_blocks import KUIS

        css = app_constants()["CIEL_CSS"]
        self.assertIn('[class*="_quizcard"]', css)
        self.assertNotIn('[class*="_quiz"]', css)
        at = self.answer(f"{KUIS}\n\n{KUIS}")
        keys = [w.key for w in list(at.radio) + list(at.button) if w.key]
        self.assertTrue(keys)
        self.assertFalse([k for k in keys if "quizcard" in k])
        self.assertEqual(len(keys), len(set(keys)))

    def test_old_user_message_without_content_renders(self):
        at = self.start([
            {"role": "user"},
            {"role": "assistant", "error": False, "content": "Jawaban lama."},
        ])
        self.assertEqual(len(self.buttons(at, "Unduh PDF")), 0)
        self.assertEqual(len(self.buttons(at, "Simpan gambar")), 1)

    def buttons(self, at, label):
        return [b for b in at.get("download_button") if b.proto.label == label]

    def test_every_answer_has_simpan_gambar(self):
        at = self.start([
            {"role": "user", "content": "apa itu pecahan"},
            {"role": "assistant", "error": False, "content": "Bagian dari keseluruhan."},
            {"role": "user", "content": "contohnya"},
            {"role": "assistant", "error": False, "content": "Setengah adalah 1/2."},
        ])
        self.assertEqual(len(self.buttons(at, "Simpan gambar")), 2)
        self.assertEqual(len(self.buttons(at, "Unduh PDF")), 0)

    def test_pdf_button_only_when_asked(self):
        at = self.start([
            {"role": "user", "content": "buatkan lembar soal pecahan pdf"},
            {"role": "assistant", "error": False, "content": "# Lembar Soal\n\n1. 1/2 + 1/4"},
            {"role": "user", "content": "apa itu pecahan"},
            {"role": "assistant", "error": False, "content": "Bagian dari keseluruhan."},
        ])
        self.assertEqual(len(self.buttons(at, "Unduh PDF")), 1)
        self.assertEqual(len(self.buttons(at, "Simpan gambar")), 2)

    def test_riset_and_error_messages_get_no_new_buttons(self):
        at = self.start([
            {"role": "user", "content": "Riset Skripsi: x"},
            {"role": "assistant", "error": False, "kind": "riset_skripsi", "topic": "x", "content": RISET_TEXT},
            {"role": "user", "content": "q"},
            {"role": "assistant", "error": True, "content": "Permintaan gagal diproses. Silakan coba lagi."},
        ])
        self.assertEqual(len(self.buttons(at, "Simpan gambar")), 0)
        self.assertEqual(len(self.buttons(at, "Unduh PDF")), 0)
        self.assertEqual(len(self.buttons(at, "Unduh DOCX")), 1)


if __name__ == "__main__":
    unittest.main()
