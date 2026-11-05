"""Edit gambar and Ilustrasi end to end (AppTest): free manual edits, Pro AI gate, quota, failures."""

import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import streamlit
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
sys.path.insert(0, str(ROOT))

from tests.test_chat_store import CONSENTED, ENV, SIGNED_IN, Response  # noqa: E402

IMAGE_FLOW = "image-flow-id"
DATABASE = {"SUPABASE_URL": "https://db.example.invalid", "SUPABASE_SERVICE_KEY": "service-key"}
PRO = "2999-01-01T00:00:00+00:00"
SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600" onload="alert(1)">'
    '<rect x="0" y="0" width="800" height="600" fill="#e3f2fd"/>'
    '<circle cx="680" cy="110" r="60" fill="#fbc02d"/>'
    '<text x="60" y="80" font-size="28">Penguapan</text>'
    '<script>alert(1)</script></svg>'
)
AI_HEADING = '<p class="ciel-edit-h">Minta AI · Pro</p>'


def photo_bytes():
    image = Image.new("RGB", (120, 80), (200, 120, 40))
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


def langflow(text):
    return Response({"outputs": [{"outputs": [{"results": {"message": {"data": {"text": text}}}}]}]})


class ErrorResponse(Response):
    """Langflow 500 whose detail names the component's error."""

    def __init__(self, text, status=500):
        super().__init__({"detail": text}, status)
        self.text = text


class ImageAppTest(unittest.TestCase):

    def start(self, user=None, pro_until=None, image_flow=IMAGE_FLOW, ai_reply=None, quota_full=False):
        from streamlit.testing.v1 import AppTest

        rows = {**CONSENTED, "pro_members": [{"expires_at": pro_until}] if pro_until else []}
        self.ai_reply = ai_reply or langflow(json.dumps({"ops": [{"op": "grayscale"}], "catatan": "Sudah hitam-putih."}))

        def post(url, **kwargs):
            if url.endswith("/rpc/ciel_rate_limit_hit"):
                full = None
                if quota_full:
                    full = next((key for key, *_ in kwargs["json"]["p_limits"] if key.startswith("gambar:")), None)
                return Response(full)
            if "/api/v1/run/" in url:
                return self.ai_reply
            return Response({})

        self.post = Mock(side_effect=post)
        self.patches = [
            patch.dict(os.environ, {**ENV, "WRITER_FLOW_ID": "", "RESEARCH_FLOW_ID": "", "MEMORY_ADMIN_FLOW_ID": "",
                                    "IMAGE_FLOW_ID": image_flow, "AI_IMAGE_PER_DAY": ""}),
            patch.object(streamlit, "user", user or {}),
            patch("requests.request", Mock(side_effect=lambda method, url, **kw: Response(rows.get(url.rsplit("/", 1)[1], [])))),
            patch("requests.post", self.post),
        ]
        patches = self.patches
        for item in patches:
            item.start()
        # start() can run more than once per test: stop every set, not only the last.
        self.addCleanup(lambda: [item.stop() for item in reversed(patches)])
        at = AppTest.from_file(str(APP_PATH), default_timeout=60)
        # Login and Supabase are configured; `user` decides whether this visitor is signed in.
        at.secrets["auth"] = {"redirect_uri": "http://localhost/oauth2callback"}
        for key, value in DATABASE.items():
            at.secrets[key] = value
        at.run()
        self.assertFalse(at.exception)
        return at

    def open_edit(self, at):
        at.button(key="tpl_edit_gambar").click().run()
        self.assertFalse(at.exception)
        at.file_uploader(key="edit_upload").set_value(("foto kelas.png", photo_bytes(), "image/png")).run()
        self.assertFalse(at.exception)
        return at

    def runs(self):
        return [c for c in self.post.call_args_list if "/api/v1/run/" in c.args[0]]

    def text(self, at):
        parts = [e.value for e in at.markdown] + [e.value for e in at.caption] + [e.value for e in at.error] + [e.value for e in at.info]
        return " ".join(str(p) for p in parts)

    def images(self, at):
        return at.get("image")

    def ask_ai(self, at, instruction="lingkari jawaban nomor 3"):
        at.text_input(key="edit_ai_text").input(instruction)
        at.button(key="edit_ai_go").click().run()
        self.assertFalse(at.exception)
        return at

    # ---------------------------------------------------------------- Edit gambar

    def test_manual_edit_works_for_a_guest_without_any_flow_call(self):
        at = self.open_edit(self.start())
        self.assertTrue(self.images(at))
        at.slider(key="edit_bright").set_value(1.4).run()
        at.toggle(key="edit_doc").set_value(True).run()
        at.text_input(key="edit_label").input("Soal 3").run()
        self.assertFalse(at.exception)
        self.assertTrue(self.images(at))
        names = [b.proto.label for b in at.get("download_button")]
        self.assertIn("Unduh", names)
        self.assertEqual(self.runs(), [])
        # A guest sees the Pro offer for the AI part instead of the input.
        self.assertIn(AI_HEADING, self.text(at))
        self.assertIn("khusus <b>Ciel Pro</b>", self.text(at))
        self.assertFalse([w for w in at.text_input if w.key == "edit_ai_text"])

    def test_ai_edit_checks_pro_then_quota_before_calling(self):
        # Free account: the lock, no input, no call.
        at = self.open_edit(self.start(user=SIGNED_IN))
        self.assertIn("khusus <b>Ciel Pro</b>", self.text(at))
        self.assertEqual(self.runs(), [])

        # Pro with the quota used up: the quota message, no call.
        at = self.open_edit(self.start(user=SIGNED_IN, pro_until=PRO, quota_full=True))
        self.ask_ai(at)
        self.assertIn("Edit AI & ilustrasi bisa dipakai 3 kali", self.text(at))
        self.assertEqual(self.runs(), [])

        # Pro with quota: exactly one call to the image flow, mode "edit".
        at = self.open_edit(self.start(user=SIGNED_IN, pro_until=PRO))
        self.ask_ai(at)
        runs = self.runs()
        self.assertEqual(len(runs), 1)
        self.assertTrue(runs[0].args[0].endswith(f"/api/v1/run/{IMAGE_FLOW}"))
        request = json.loads(runs[0].kwargs["json"]["input_value"])
        self.assertEqual((request["mode"], request["instruction"]), ("edit", "lingkari jawaban nomor 3"))
        self.assertEqual((request["width"], request["height"]), (120, 80))
        self.assertTrue(Image.open(io.BytesIO(__import__("base64").b64decode(request["image"]))).format == "JPEG")

    def test_pro_that_expired_while_the_dialog_was_open_gets_the_pro_message(self):
        at = self.open_edit(self.start(user=SIGNED_IN, pro_until=PRO))
        rows = {**CONSENTED, "pro_members": [{"expires_at": "2001-01-01T00:00:00+00:00"}]}
        with patch("requests.request", Mock(side_effect=lambda method, url, **kw: Response(rows.get(url.rsplit("/", 1)[1], [])))):
            self.ask_ai(at)
        self.assertIn("Edit AI & ilustrasi khusus Ciel Pro", self.text(at))
        self.assertEqual(self.runs(), [])

    def test_ai_ops_are_applied_and_cleared(self):
        at = self.open_edit(self.start(user=SIGNED_IN, pro_until=PRO))
        self.ask_ai(at)
        self.assertEqual(at.session_state["edit_ai"]["ops"], [{"op": "grayscale"}])
        self.assertIn("Sudah hitam-putih.", self.text(at))
        at.button(key="edit_ai_clear").click().run()
        self.assertFalse(at.exception)
        self.assertIsNone(at.session_state["edit_ai"])

    def test_ai_reply_without_valid_ops_asks_to_be_more_specific(self):
        reply = langflow(json.dumps({"ops": [{"op": "explode"}], "catatan": ""}))
        at = self.open_edit(self.start(user=SIGNED_IN, pro_until=PRO, ai_reply=reply))
        self.ask_ai(at)
        self.assertIn("AI belum menangkap maksudnya. Coba tulis lebih spesifik.", self.text(at))
        self.assertIsNone(at.session_state["edit_ai"])
        # A reply that is not JSON counts as zero valid ops too.
        self.ai_reply = langflow("Tentu! Berikut langkahnya")
        self.ask_ai(at)
        self.assertIn("AI belum menangkap maksudnya. Coba tulis lebih spesifik.", self.text(at))

    def test_ai_refusal_note_is_shown_when_nothing_can_be_done(self):
        reply = langflow(json.dumps({"ops": [], "catatan": "Latar foto belum bisa dihapus."}))
        at = self.open_edit(self.start(user=SIGNED_IN, pro_until=PRO, ai_reply=reply))
        self.ask_ai(at, "hapus background")
        self.assertIn("Latar foto belum bisa dihapus.", self.text(at))

    def test_ai_failure_keeps_manual_edits(self):
        failure = ErrorResponse('{"detail": "ValueError: Ciel image AI unavailable: HTTP 402"}')
        at = self.open_edit(self.start(user=SIGNED_IN, pro_until=PRO, ai_reply=failure))
        at.slider(key="edit_bright").set_value(1.4).run()
        self.ask_ai(at)
        self.assertIn("AI sedang tidak tersedia", self.text(at))
        self.assertIn("Edit manual tetap bisa dipakai", self.text(at))
        self.assertNotIn("Traceback", self.text(at))
        self.assertEqual(at.slider(key="edit_bright").value, 1.4)
        self.assertIsNone(at.session_state["edit_ai"])
        self.assertTrue(self.images(at))

    def test_ai_section_hidden_without_image_flow(self):
        at = self.open_edit(self.start(user=SIGNED_IN, pro_until=PRO, image_flow=""))
        self.assertNotIn(AI_HEADING, self.text(at))
        self.assertFalse([w for w in at.text_input if w.key == "edit_ai_text"])
        self.assertTrue(self.images(at))
        self.assertNotIn("tpl_ilustrasi", [b.key for b in at.button])

    def test_unreadable_file_shows_the_format_message(self):
        at = self.start()
        at.button(key="tpl_edit_gambar").click().run()
        at.file_uploader(key="edit_upload").set_value(("scan.png", b"not an image", "image/png")).run()
        self.assertFalse(at.exception)
        self.assertIn("Format ini belum bisa diedit. Pakai JPG atau PNG.", self.text(at))
        self.assertFalse(self.images(at))

    # ---------------------------------------------------------------- Ilustrasi

    def open_ilustrasi(self, at):
        at.button(key="tpl_ilustrasi").click().run()
        self.assertFalse(at.exception)
        return at

    def ask_illustration(self, at, description="siklus air dengan label"):
        at.text_area(key="ilustrasi_text").input(description)
        at.button(key="ilustrasi_go").click().run()
        self.assertFalse(at.exception)
        return at

    def test_illustration_is_pro_only_and_uses_the_quota(self):
        at = self.open_ilustrasi(self.start(user=SIGNED_IN))
        self.assertIn("khusus <b>Ciel Pro</b>", self.text(at))
        self.assertIn("Lihat paket Pro", [b.label for b in at.button])
        self.assertFalse([w for w in at.text_area if w.key == "ilustrasi_text"])
        self.assertEqual(self.runs(), [])

        at = self.open_ilustrasi(self.start(user=SIGNED_IN, pro_until=PRO, quota_full=True))
        self.assertIn("Kuota 3 per hari", self.text(at))
        self.ask_illustration(at)
        self.assertIn("Edit AI & ilustrasi bisa dipakai 3 kali", self.text(at))
        self.assertEqual(self.runs(), [])

        at = self.open_ilustrasi(self.start(user=SIGNED_IN, pro_until=PRO, ai_reply=langflow(SVG)))
        self.ask_illustration(at)
        runs = self.runs()
        self.assertEqual(len(runs), 1)
        self.assertTrue(runs[0].args[0].endswith(f"/api/v1/run/{IMAGE_FLOW}"))
        self.assertEqual(json.loads(runs[0].kwargs["json"]["input_value"]),
                         {"mode": "ilustrasi", "instruction": "siklus air dengan label"})

    def test_illustration_shows_png_never_raw_svg(self):
        at = self.open_ilustrasi(self.start(user=SIGNED_IN, pro_until=PRO, ai_reply=langflow(SVG)))
        self.ask_illustration(at)
        self.assertEqual(len(self.images(at)), 1)
        # The app's own logo is inline SVG; the model's SVG must never reach the page.
        for element in list(at.markdown) + list(at.get("html")):
            shown = str(getattr(element, "value", "") or getattr(element, "proto", ""))
            for needle in ("Penguapan", "#fbc02d", "#e3f2fd"):
                self.assertNotIn(needle, shown)
        downloads = {b.proto.label: b for b in at.get("download_button")}
        self.assertEqual(set(downloads), {"Unduh PNG", "Unduh SVG"})
        last = at.session_state["ilustrasi_last"]
        self.assertTrue(last["png"].startswith(b"\x89PNG"))
        self.assertNotIn("onload", last["svg"])
        self.assertEqual(last["name"], "Ilustrasi - siklus air dengan label")

    def test_refusal_reason_is_shown(self):
        reply = langflow("TOLAK: Ciel tidak menggambar wajah orang sungguhan.")
        at = self.open_ilustrasi(self.start(user=SIGNED_IN, pro_until=PRO, ai_reply=reply))
        self.ask_illustration(at, "wajah presiden")
        self.assertIn("Ciel tidak menggambar wajah orang sungguhan.", self.text(at))
        self.assertNotIn("TOLAK:", self.text(at))
        self.assertFalse(self.images(at))

    def test_broken_svg_shows_friendly_error(self):
        at = self.open_ilustrasi(self.start(user=SIGNED_IN, pro_until=PRO, ai_reply=langflow("Maaf, ini gambarnya: <svg")))
        with self.assertLogs("ciel_ai", level="WARNING") as logs:
            self.ask_illustration(at)
        self.assertIn("Ilustrasinya gagal digambar. Coba lagi dengan deskripsi lain.", self.text(at))
        self.assertFalse(self.images(at))
        self.assertTrue(any("illustration_failed" in line for line in logs.output))
        self.assertFalse(any("<svg" in line for line in logs.output))

    def test_illustration_ai_failure_is_a_friendly_card(self):
        failure = ErrorResponse('{"detail": "ValueError: Ciel image AI unavailable: DeepSeek terlalu lama"}')
        at = self.open_ilustrasi(self.start(user=SIGNED_IN, pro_until=PRO, ai_reply=failure))
        self.ask_illustration(at)
        self.assertIn("AI sedang tidak tersedia", self.text(at))
        self.assertFalse(self.images(at))


if __name__ == "__main__":
    unittest.main()
