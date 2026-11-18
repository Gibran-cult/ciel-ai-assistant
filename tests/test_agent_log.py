import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_log import ACTION_TEXT, CHAIN_TEXT, LogLine, describe, export_csv, filter_lines, pair_rows  # noqa: E402

TODAY = date(2026, 11, 18)


def row(**over):
    base = {"seq": 1, "device": "d1", "kind": "tab_read", "target": "shopee.co.id", "level": "R0", "decision": "allow",
            "reason": "tab_read", "approved_by": None, "result": "ok", "at": "2026-11-18T03:42:00+00:00"}
    base.update(over)
    return base


class DescribeTest(unittest.TestCase):
    def test_a_row_reads_in_plain_language(self):
        line = describe(row(kind="tab_type", level="R1"), TODAY)
        self.assertEqual(line, LogLine(1, "10.42", "R1", "Mengetik di kolom", "shopee.co.id", "Selesai", "", "d1"))

    def test_older_rows_show_the_date_in_jakarta_time(self):
        self.assertEqual(describe(row(at="2026-11-02T03:42:00+00:00"), TODAY).time, "2 Nov 10.42")
        # 18.30 UTC sudah tanggal 19 di Jakarta.
        self.assertEqual(describe(row(at="2026-11-18T18:30:00+00:00"), date(2026, 11, 19)).time, "01.30")

    def test_results_follow_the_decision(self):
        cases = ((("allow", "ok", None), "Selesai"), (("confirm", "ok", "user"), "Disetujui kamu"), (("block", None, None), "Diblokir"),
                 (("handover", "handed_over", None), "Kamu kerjakan sendiri"), (("confirm", "declined", None), "Kamu tolak"),
                 (("confirm", "expired", None), "Kedaluwarsa"), (("allow", "failed", None), "Gagal"), (("allow", None, None), "Dikirim"),
                 (("confirm", "widened", "user"), "Lingkup diperluas"))

        for (decision, result, approved), expected in cases:
            with self.subTest(decision=decision, result=result):
                self.assertEqual(describe(row(decision=decision, result=result, approved_by=approved), TODAY).result, expected)

    def test_reasons_are_explained_only_when_something_was_held_back(self):
        self.assertEqual(describe(row(decision="block", reason="not_listed", result=None), TODAY).reason,
                         "Situs ini belum ada di daftar toko resmi Ciel.")
        self.assertEqual(describe(row(decision="block", reason="aneh_baru", result=None), TODAY).reason,
                         "Diblokir aturan keamanan (aneh_baru).")
        self.assertEqual(describe(row(decision="confirm", reason="submits", result="ok", approved_by="user"), TODAY).reason,
                         "Aksi ini mengirim data, jadi butuh persetujuanmu.")
        self.assertEqual(describe(row(), TODAY).reason, "")

    def test_unknown_or_odd_values_stay_plain_text(self):
        line = describe(row(kind="<b>x</b>", reason=None, target="a" * 200, decision="block", result=None), TODAY)
        self.assertEqual((line.action, len(line.target), line.target[-1], line.result), ("Aksi lain (<b>x</b>)", 60, "…", "Diblokir"))

        broken = describe({"seq": "x", "at": "bukan waktu", "kind": None, "target": None, "level": 7}, TODAY)
        self.assertEqual((broken.time, broken.action, broken.target, broken.level), ("?", "Aksi lain (?)", "", "?"))

    def test_every_tool_has_a_phrase(self):
        from agent_api.tools import TOOLS

        self.assertTrue(set(TOOLS) <= set(ACTION_TEXT))


class PairTest(unittest.TestCase):
    def test_sent_and_result_rows_become_one_line(self):
        rows = [row(seq=1, result=None), row(seq=2, result="ok"), row(seq=3, kind="finish", result="ok")]
        self.assertEqual([item["seq"] for item in pair_rows(rows)], [2, 3])

    def test_a_sent_row_without_its_result_stays(self):
        rows = [row(seq=1, result=None), row(seq=2, kind="tab_click", result=None)]
        self.assertEqual([item["seq"] for item in pair_rows(rows)], [1, 2])

    def test_a_widened_row_is_its_own_line(self):
        rows = [row(seq=1, decision="confirm", result="widened"), row(seq=2, decision="allow", result=None), row(seq=3, result="ok")]
        self.assertEqual([item["seq"] for item in pair_rows(rows)], [1, 3])


class FilterTest(unittest.TestCase):
    def test_filters(self):
        lines = [describe(row(seq=1, device="d1", level="R1"), TODAY), describe(row(seq=2, device="d2", level="R2", decision="block", result=None), TODAY)]
        self.assertEqual([line.seq for line in filter_lines(lines, device="d2")], [2])
        self.assertEqual([line.seq for line in filter_lines(lines, level="R1")], [1])
        self.assertEqual([line.seq for line in filter_lines(lines, result="Diblokir")], [2])
        self.assertEqual(len(filter_lines(lines)), 2)


class ExportTest(unittest.TestCase):
    def test_csv_has_the_columns_and_cannot_start_a_formula(self):
        text = export_csv([describe(row(target="=HYPERLINK(1)"), TODAY), describe(row(target="+1", device="@d"), TODAY)])
        lines = text.splitlines()
        self.assertEqual(lines[0], "waktu,risiko,aksi,target,hasil,alasan,perangkat")
        self.assertIn("'=HYPERLINK(1)", lines[1])
        self.assertIn("'+1", lines[2])
        self.assertIn("'@d", lines[2])

    def test_chain_labels_cover_every_status(self):
        self.assertEqual(set(CHAIN_TEXT), {"ok", "broken", "missing", "extra", None})


if __name__ == "__main__":
    unittest.main()
