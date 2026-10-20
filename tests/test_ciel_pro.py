"""Ciel Pro: status Pro (pro_members), gerbang Riset Skripsi, kuota, dan ekspor DOCX."""

import ast
import io
import os
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import docx
import requests
import streamlit

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
sys.path.insert(0, str(ROOT))

import chat_store  # noqa: E402
import riset_export  # noqa: E402
from tests.test_chat_store import ALICE, ENV, SIGNED_IN, SIGNED_IN_OWNER, Response, State  # noqa: E402

SOURCE = APP_PATH.read_text(encoding="utf-8")


def load_app(names, **namespace):
    """Fungsi dan konstanta app.py tertentu, dengan dependensi dari `namespace`."""
    nodes = [
        node for node in ast.parse(SOURCE).body
        if (isinstance(node, ast.FunctionDef) and node.name in names)
        or (isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) in names)
    ]
    # Dekorator (@st.dialog, @st.cache_resource) tidak dibutuhkan di sini.
    for node in nodes:
        if isinstance(node, ast.FunctionDef):
            node.decorator_list = []
    app = {"time": time, **namespace}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(APP_PATH), "exec"), app)
    return app


# ============================================================
# DATABASE
# ============================================================

class ProMembersStoreTest(unittest.TestCase):

    def setUp(self):
        self.store = chat_store.ChatStore("https://db.example.invalid", "service-key")

    def test_reads_only_this_owners_row(self):
        rows = [{"expires_at": "2026-11-17T00:00:00+00:00"}]
        with patch("requests.request", return_value=Response(rows)) as request:
            until = self.store.load_pro_until(ALICE)

        self.assertEqual(until, 1_794_873_600.0)
        call = request.call_args
        self.assertEqual(call.args, ("GET", "https://db.example.invalid/rest/v1/pro_members"))
        self.assertEqual(call.kwargs["params"]["owner"], f"eq.{ALICE}")
        self.assertEqual(call.kwargs["params"]["select"], "expires_at")

    def test_never_pro_is_zero_and_failures_are_none(self):
        with patch("requests.request", return_value=Response([])):
            self.assertEqual(self.store.load_pro_until(ALICE), 0.0)

        with self.assertLogs("ciel_ai.chat_store", level="ERROR"):
            with patch("requests.request", return_value=Response(status=503)):
                self.assertIsNone(self.store.load_pro_until(ALICE))
            with patch("requests.request", return_value=Response([{"expires_at": "besok"}])):
                self.assertIsNone(self.store.load_pro_until(ALICE))
            with patch("requests.request") as request:
                self.assertIsNone(self.store.load_pro_until("a,b"))
        request.assert_not_called()

    def test_postgrest_timestamps_parse_on_python_310(self):
        base = 1_794_873_600.0  # 2026-11-17T00:00:00Z
        cases = {
            "2026-11-17T00:00:00+00:00": base,
            "2026-11-17T00:00:00Z": base,
            "2026-11-17 00:00:00": base,
            "2026-11-17T00:00:00.5+00:00": base + 0.5,
            "2026-11-17T00:00:00.12345+00:00": base + 0.12345,
            "2026-11-17T07:00:00+07:00": base,
            "2026-11-16T19:30:00-04:30": base,
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertAlmostEqual(chat_store.parse_timestamp(text), expected, places=5)

        with self.assertRaises(ValueError):
            chat_store.parse_timestamp("17/11/2026")


# ============================================================
# PRO STATUS AND LIMITS (app.py functions)
# ============================================================

class ProGateTest(unittest.TestCase):

    def setUp(self):
        self.store = Mock()
        self.st = SimpleNamespace(session_state=State())
        self.owner = ALICE
        self.signed_in = True
        self.events = []
        self.app = load_app(
            (
                "PRO_STATUS_TTL", "pro_until", "is_pro", "MONTHS_ID", "format_date_id",
                "rate_limits_for_request", "rate_limit_message", "pro_refusal", "riset_refusal", "RISET_KIND",
                "kerangka_refusal", "KERANGKA_KIND", "pro_status_html", "FEATURE_QUOTAS",
                "cek_refusal", "CEK_KIND",
            ),
            st=self.st,
            CHAT_STORE=self.store,
            chat_owner=lambda: self.owner,
            logged_in=lambda: self.signed_in,
            user_key=lambda: self.owner or "visitor1",
            security_event=lambda kind, **fields: self.events.append(kind),
            CielError=type("CielError", (str,), {}),
            RISET_ENABLED=True,
            WRITER_ENABLED=True,
            CHECK_ENABLED=True,
            HOUR=3600,
            DAY=86400,
            RATE_LIMIT_PER_HOUR=10,
            RATE_LIMIT_PER_HOUR_LOGIN=60,
            RATE_LIMIT_PER_DAY_LOGIN=300,
            RATE_LIMIT_PER_HOUR_PRO=150,
            RATE_LIMIT_PER_DAY_PRO=800,
            RISET_SKRIPSI_PER_DAY=5,
            KERANGKA_PER_DAY=10,
            CEK_KUTIPAN_PER_DAY=20,
            RATE_LIMIT_ANON_TOTAL_PER_HOUR=60,
            RATE_LIMIT_ANON_TOTAL_PER_DAY=300,
            RATE_LIMIT_TOTAL_PER_DAY=1500,
        )

    def pro_for(self, seconds):
        self.store.load_pro_until.return_value = time.time() + seconds

    def test_status_is_cached_for_display_and_refreshed_on_demand(self):
        self.pro_for(3600)
        self.assertTrue(self.app["is_pro"]())
        self.assertTrue(self.app["is_pro"]())
        self.assertEqual(self.store.load_pro_until.call_count, 1)

        self.pro_for(-10)
        self.assertTrue(self.app["is_pro"]())  # still the cached value
        self.assertFalse(self.app["is_pro"](refresh=True))
        self.assertEqual(self.store.load_pro_until.call_count, 2)

    def test_cache_is_per_owner_and_anonymous_never_reads_the_database(self):
        self.pro_for(3600)
        self.assertTrue(self.app["is_pro"]())
        self.owner = "b2c3d4e5f6071829"
        self.store.load_pro_until.return_value = 0.0
        self.assertFalse(self.app["is_pro"]())

        self.owner = ""
        self.store.reset_mock()
        self.assertEqual(self.app["pro_until"](), 0.0)
        self.store.load_pro_until.assert_not_called()

    def test_unreadable_status_is_not_pro(self):
        self.store.load_pro_until.return_value = None
        self.assertFalse(self.app["is_pro"]())

    def test_pro_accounts_get_higher_chat_limits(self):
        limits = self.app["rate_limits_for_request"]
        self.store.load_pro_until.return_value = 0.0
        self.assertEqual(limits()[f"user:{ALICE}:hour"], (60, 3600))

        self.st.session_state.clear()
        self.pro_for(3600)
        self.assertEqual(limits()[f"user:{ALICE}:hour"], (150, 3600))
        self.assertEqual(limits()[f"user:{ALICE}:day"], (800, 86400))
        self.assertNotIn(f"riset:{ALICE}:day", limits())

    def test_riset_has_its_own_daily_quota_on_top_of_the_others(self):
        self.pro_for(3600)
        limits = self.app["rate_limits_for_request"]("riset")
        self.assertEqual(limits[f"riset:{ALICE}:day"], (5, 86400))
        self.assertIn(f"user:{ALICE}:hour", limits)
        self.assertIn("all:total:day", limits)
        self.assertIn("5 kali per hari", self.app["rate_limit_message"](f"riset:{ALICE}:day", 5))

    def test_riset_refusal_checks_the_database_every_time(self):
        refusal = self.app["riset_refusal"]

        self.pro_for(3600)
        self.assertTrue(self.app["is_pro"]())  # cached as Pro for display
        self.store.load_pro_until.return_value = 0.0
        self.assertIn("belum Pro", refusal())  # but the send path re-reads it
        self.assertEqual(self.events, ["pro_required"])

        self.pro_for(3600)
        self.assertIsNone(refusal())

        self.store.load_pro_until.return_value = time.time() - 86400
        self.assertIn("berakhir", refusal())

        self.store.load_pro_until.return_value = None
        self.assertIn("belum bisa diperiksa", refusal())

        self.signed_in = False
        self.assertIn("Masuk dengan akun Google", refusal())

    def test_riset_refusal_when_the_feature_is_off(self):
        self.app["RISET_ENABLED"] = False
        self.pro_for(3600)
        self.assertIn("belum aktif", self.app["riset_refusal"]())
        self.store.load_pro_until.assert_not_called()

    def test_kerangka_uses_the_same_server_side_pro_check(self):
        refusal = self.app["kerangka_refusal"]
        self.store.load_pro_until.return_value = 0.0
        self.assertIn("Kerangka Bab 1–3 khusus Ciel Pro", refusal())
        self.assertEqual(self.events, ["pro_required"])
        self.pro_for(3600)
        self.assertIsNone(refusal())
        self.app["WRITER_ENABLED"] = False
        self.assertIn("Kerangka Bab 1–3 belum aktif", refusal())
        # Riset Skripsi keeps its own wording through the shared check.
        self.app["RISET_ENABLED"] = True
        self.store.load_pro_until.return_value = 0.0
        self.assertIn("Riset Skripsi khusus Ciel Pro", self.app["riset_refusal"]())

    def test_kerangka_has_its_own_daily_quota(self):
        self.pro_for(3600)
        limits = self.app["rate_limits_for_request"]("kerangka")
        self.assertEqual(limits[f"kerangka:{ALICE}:day"], (10, 86400))
        self.assertNotIn(f"riset:{ALICE}:day", limits)
        self.assertIn("all:total:day", limits)
        self.assertIn("10 kali per hari", self.app["rate_limit_message"](f"kerangka:{ALICE}:day", 10))

    def test_cek_kutipan_is_pro_only_with_its_own_quota(self):
        refusal = self.app["cek_refusal"]
        self.store.load_pro_until.return_value = 0.0
        self.assertIn("Cek kutipan & kemiripan khusus Ciel Pro", refusal())
        self.assertEqual(self.events, ["pro_required"])
        self.pro_for(3600)
        self.assertIsNone(refusal())
        self.app["CHECK_ENABLED"] = False
        self.assertIn("Cek kutipan & kemiripan belum aktif", refusal())

        limits = self.app["rate_limits_for_request"]("cek")
        self.assertEqual(limits[f"cek:{ALICE}:day"], (20, 86400))
        self.assertNotIn(f"kerangka:{ALICE}:day", limits)
        self.assertEqual(
            self.app["rate_limit_message"](f"cek:{ALICE}:day", 20),
            "Cek kutipan & kemiripan bisa dipakai 20 kali per hari per akun. Kuota hari ini sudah habis, coba lagi besok.",
        )

    def test_account_menu_plan_line(self):
        html = self.app["pro_status_html"]
        self.store.load_pro_until.return_value = 1_794_873_600.0 + 10**9  # far future
        self.assertIn("<b>Pro</b>, aktif sampai", html())
        self.st.session_state.clear()
        self.store.load_pro_until.return_value = 0.0
        self.assertEqual(html(), "<p>Paket: Gratis.</p>")
        self.app["CHAT_STORE"] = None
        self.assertEqual(html(), "")

    def test_dates_are_in_indonesian_and_wib(self):
        fmt = self.app["format_date_id"]
        self.assertEqual(fmt(1_794_873_600.0), "17 November 2026")
        # 20:00 UTC on 16 Nov is already 17 Nov in Jakarta.
        self.assertEqual(fmt(1_794_873_600.0 - 4 * 3600), "17 November 2026")


# ============================================================
# RISET REQUEST AND FOLLOW-UP CONTEXT
# ============================================================

class RisetRequestTest(unittest.TestCase):

    def setUp(self):
        self.app = load_app(
            ("RISET_KIND", "riset_payload", "make_riset_pending", "riset_report"),
        )

    def test_request_keeps_every_input_so_retry_can_rebuild_it(self):
        pending = self.app["make_riset_pending"]("Literasi digital UMKM", "Manajemen", 5)
        year = time.gmtime().tm_year

        self.assertEqual(pending["riset"], {"topic": "Literasi digital UMKM", "field": "Manajemen", "min_year": year - 5})
        self.assertEqual(pending["payload"], self.app["riset_payload"](**pending["riset"]))
        self.assertIn(f"tahun {year - 5} sampai sekarang", pending["payload"])
        self.assertIn("Bidang ilmu: Manajemen", pending["payload"])
        self.assertEqual(pending["text"], "Riset Skripsi: Literasi digital UMKM")
        self.assertNotIn("Bidang ilmu", self.app["riset_payload"]("x", "", 2020))

    def test_latest_report_becomes_follow_up_context(self):
        chat = {"messages": [
            {"role": "assistant", "content": "lama", "kind": "riset_skripsi"},
            {"role": "user", "content": "lanjut"},
            {"role": "assistant", "content": "baru", "kind": "riset_skripsi"},
            {"role": "assistant", "content": "gagal", "kind": "riset_skripsi", "error": True},
        ]}
        (report,) = self.app["riset_report"](chat)
        self.assertEqual(report["text"], "baru")
        self.assertTrue(report["name"].endswith(".md"))
        self.assertEqual(self.app["riset_report"]({"messages": [{"role": "assistant", "content": "hai"}]}), [])
        self.assertEqual(self.app["riset_report"](None), [])

    def test_send_path_gates_before_quota_and_uses_the_research_flow(self):
        self.assertIn('riset_refusal() or check_rate_limit("riset")', SOURCE)
        self.assertIn("flow_id=RESEARCH_FLOW_ID", SOURCE)
        self.assertIn('tweaks={RESEARCH_SEARCH_ID: {"start_published_date": riset_start_date(riset)}}', SOURCE)
        self.assertIn('"riset": user.get("riset")', SOURCE)  # retry stays a riset request
        self.assertIn("riset_report(chat)", SOURCE)


# ============================================================
# END TO END (AppTest)
# ============================================================

class RisetAppTest(unittest.TestCase):

    SECRETS = {
        "auth": {"redirect_uri": "http://localhost/oauth2callback"},
        "SUPABASE_URL": "https://db.example.invalid",
        "SUPABASE_SERVICE_KEY": "service-key",
        "RESEARCH_FLOW_ID": "riset-flow-id",
    }

    REPORT = (
        "# Peta Sumber: Literasi digital UMKM\n\nRingkasan [1].\n\n"
        "## Daftar Pustaka\n[1] Sari, D. (2023). Judul. https://example.org/a"
    )
    # base64 of [{"n": 1, "highlights": ["Cuplikan."]}]
    EXCERPTS = "\n\n<!-- ciel-excerpts:v1 W3sibiI6IDEsICJoaWdobGlnaHRzIjogWyJDdXBsaWthbi4iXX1d -->"

    def database(self, expires_at):
        rows = {"pro_members": [{"expires_at": expires_at}] if expires_at else []}
        return Mock(side_effect=lambda method, url, **kw: Response(rows.get(url.rsplit("/", 1)[1], [])))

    def run_riset(self, expires_at):
        from streamlit.testing.v1 import AppTest

        answer = {"outputs": [{"outputs": [{"results": {"message": {"data": {"text": self.REPORT + self.EXCERPTS}}}}]}]}
        langflow = Mock(return_value=Response(answer))

        with patch.dict(os.environ, ENV), patch.object(streamlit, "user", SIGNED_IN), \
                patch("requests.request", self.database(expires_at)), \
                patch("requests.post", langflow):
            at = AppTest.from_file(str(APP_PATH), default_timeout=60)
            for key, value in self.SECRETS.items():
                at.secrets[key] = value
            at.run()
            self.assertTrue(at.button(key="riset_open"))
            at.session_state["pending"] = {
                "text": "Riset Skripsi: Literasi digital UMKM",
                "files": [],
                "images": [],
                "payload": "Topik skripsi: Literasi digital UMKM",
                "riset": {"topic": "Literasi digital UMKM", "field": "", "min_year": 2021},
            }
            at.run()

        runs = [c for c in langflow.call_args_list if "/api/v1/run/" in c.args[0]]
        self.saves = [c for c in langflow.call_args_list if "/rest/v1/" in c.args[0]]
        return at, runs

    def test_free_account_is_refused_on_the_server(self):
        at, runs = self.run_riset(expires_at=None)

        self.assertFalse(at.exception)
        self.assertEqual(runs, [])
        (chat,) = at.session_state["chats"].values()
        reply = chat["messages"][-1]
        self.assertTrue(reply["error"])
        self.assertIn("khusus Ciel Pro", reply["content"])
        self.assertNotIn("kind", reply)
        self.assertEqual(at.button(key="riset_open").label, "Riset Skripsi · Pro")

    def test_pro_account_runs_the_research_flow_and_gets_a_docx(self):
        at, (run,) = self.run_riset(expires_at="2999-01-01T00:00:00+00:00")

        self.assertFalse(at.exception)
        self.assertTrue(run.args[0].endswith("/api/v1/run/riset-flow-id"))
        self.assertEqual(run.kwargs["timeout"], 420)
        self.assertEqual(run.kwargs["json"]["tweaks"], {"CielScholarSearch-r1s3t": {"start_published_date": "2021-01-01"}})
        self.assertIn("Topik skripsi: Literasi digital UMKM", run.kwargs["json"]["input_value"])

        (chat,) = at.session_state["chats"].values()
        reply = chat["messages"][-1]
        self.assertEqual((reply["kind"], reply["topic"], reply["error"]), ("riset_skripsi", "Literasi digital UMKM", False))
        self.assertEqual(reply["content"], self.REPORT)  # no excerpts line on screen or in the DOCX
        self.assertEqual(reply["excerpts"], {"1": ["Cuplikan."]})
        self.assertEqual(chat["messages"][-2]["riset"]["min_year"], 2021)
        self.assertEqual(at.button(key="riset_open").label, "Riset Skripsi")

        # Saved under the signed-in owner, with the marker kept for reloads.
        (save,) = [c for c in self.saves if c.args[0].endswith("/rest/v1/chats")]
        self.assertEqual(save.kwargs["json"]["owner"], SIGNED_IN_OWNER)
        self.assertEqual(save.kwargs["json"]["messages"][-1]["kind"], "riset_skripsi")
        self.assertEqual(save.kwargs["json"]["messages"][-1]["excerpts"], {"1": ["Cuplikan."]})

    def test_feature_is_hidden_without_the_research_flow(self):
        from streamlit.testing.v1 import AppTest

        # app.py calls load_dotenv(), which finds a parent .env such as the
        # host's (it has RESEARCH_FLOW_ID since the production launch). An
        # empty variable wins over it, so the flow is really unset here.
        with patch.dict(os.environ, {**ENV, "RESEARCH_FLOW_ID": ""}), patch.object(streamlit, "user", SIGNED_IN), \
                patch("requests.request", self.database(None)):
            at = AppTest.from_file(str(APP_PATH), default_timeout=60)
            for key, value in self.SECRETS.items():
                if key != "RESEARCH_FLOW_ID":
                    at.secrets[key] = value
            at.run()

        self.assertFalse(at.exception)
        self.assertNotIn("riset_open", [b.key for b in at.button])


# ============================================================
# DOCX EXPORT
# ============================================================

REPORT = """# Peta Sumber: Literasi digital UMKM

Ringkasan **singkat** tentang topik [1].
Baris kedua paragraf yang sama.

## Tema: Adopsi teknologi
- Temuan A, metode survei [1][2].
* Lihat [Kemenkop](https://kemenkop.go.id).

## Pertanyaan untuk dosen pembimbing
1. Apakah fokus pada Jawa Barat cukup?

## Daftar Pustaka
[1] Sari, D. (2023). *Literasi digital UMKM*. Jurnal X. https://example.org/a
- [2] Kemenkop. (t.t.). Data UMKM. https://kemenkop.go.id
"""


class RisetExportTest(unittest.TestCase):

    def test_blocks_follow_the_fixed_report_format(self):
        blocks = riset_export.parse_blocks(REPORT)

        self.assertEqual([kind for kind, _ in blocks], [
            "h1", "paragraph", "h2", "bullet", "bullet", "h2", "number", "h2", "reference", "reference",
        ])
        self.assertEqual(blocks[1][1], "Ringkasan **singkat** tentang topik [1]. Baris kedua paragraf yang sama.")
        self.assertEqual(blocks[-1][1], "[2] Kemenkop. (t.t.). Data UMKM. https://kemenkop.go.id")

    def test_inline_markup(self):
        self.assertEqual(
            riset_export.inline_runs("a **b** *c* [d](https://e.example/f) https://g.example"),
            [("a ", False, False), ("b", True, False), (" ", False, False), ("c", False, True),
             (" ", False, False), ("d (https://e.example/f)", False, False), (" https://g.example", False, False)],
        )

    def test_docx_uses_thesis_formatting_and_hanging_indent_references(self):
        document = docx.Document(io.BytesIO(riset_export.report_docx(REPORT, "Literasi digital UMKM")))
        paragraphs = document.paragraphs

        self.assertEqual(paragraphs[0].style.name, "Heading 1")
        self.assertEqual(document.styles["Normal"].font.name, "Times New Roman")
        self.assertEqual(document.styles["Normal"].font.size.pt, 12)
        self.assertEqual(document.core_properties.title, "Peta Sumber: Literasi digital UMKM")

        references = [p for p in paragraphs if p.text.startswith("[")]
        self.assertEqual(len(references), 2)
        for paragraph in references:
            self.assertLess(paragraph.paragraph_format.first_line_indent, 0)
            self.assertGreater(paragraph.paragraph_format.left_indent, 0)
        self.assertTrue(any(run.italic for run in references[0].runs))
        self.assertIn("https://example.org/a", references[0].text)

        self.assertIn("buka dan baca setiap sumber", paragraphs[-1].text)

    def test_filename_is_safe(self):
        self.assertEqual(
            riset_export.report_filename("Literasi digital: UMKM/Jabar?"),
            "Peta Sumber - Literasi digital UMKM Jabar.docx",
        )
        self.assertEqual(riset_export.report_filename("../../"), "Peta Sumber - Riset Skripsi.docx")
        # Long topics are cut between words (live run: "...menggunakan IndoBER").
        self.assertEqual(
            riset_export.report_filename("Deteksi berita hoaks berbahasa Indonesia menggunakan IndoBERT"),
            "Peta Sumber - Deteksi berita hoaks berbahasa Indonesia menggunakan.docx",
        )


if __name__ == "__main__":
    unittest.main()
