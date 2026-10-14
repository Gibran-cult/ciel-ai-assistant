import ast
import copy
import json
import re
import unittest
from pathlib import Path

from tests.test_flow_v141_contract import (
    RESERVED_COMPONENT_ATTRIBUTES,
    compile_class,
    input_names,
    install_langflow_stub,
    normalize,
)


ROOT = Path(__file__).resolve().parents[1]
FLOW_V141 = ROOT / "flow" / "v1.4.1" / "Ciel_AI_Long-Term_Memory_Master.json"
FLOW_V150 = ROOT / "flow" / "v1.5.0" / "Ciel_AI_Long-Term_Memory_Master.json"
COMPONENT = ROOT / "flow" / "components" / "ciel_table_analyst.py"
APP_PATH = ROOT / "app.py"

TABLE_ID = "CielTableAnalyst-t4bL3"
VDA_ID = "RunFlow-DhbyQ"


def agent(flow):
    return next(n for n in flow["data"]["nodes"] if n["id"].startswith("Agent-"))


class FlowV150ContractTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = FLOW_V150.read_text(encoding="utf-8")
        cls.flow = json.loads(cls.raw)
        cls.base = json.loads(FLOW_V141.read_text(encoding="utf-8"))
        cls.nodes = {n["id"]: n for n in cls.flow["data"]["nodes"]}
        cls.prompt = agent(cls.flow)["data"]["node"]["template"]["system_prompt"]["value"]

    def test_table_analyst_is_an_agent_tool(self):
        node = self.nodes[TABLE_ID]["data"]["node"]
        self.assertTrue(node["tool_mode"])
        self.assertEqual([o["name"] for o in node["outputs"]], ["component_as_tool"])
        edges = [e for e in self.flow["data"]["edges"] if e["source"] == TABLE_ID]
        self.assertEqual(len(edges), 1)
        self.assertTrue(edges[0]["target"].startswith("Agent-"))
        self.assertEqual(edges[0]["data"]["targetHandle"]["fieldName"], "tools")
        self.assertEqual(edges[0]["data"]["sourceHandle"]["dataType"], "CielTableAnalyst")

    def test_table_analyst_code_matches_repository_source(self):
        code = self.nodes[TABLE_ID]["data"]["node"]["template"]["code"]["value"]
        self.assertEqual(normalize(code), normalize(COMPONENT.read_text(encoding="utf-8")))

    def test_file_contents_come_from_app_not_agent(self):
        template = self.nodes[TABLE_ID]["data"]["node"]["template"]
        self.assertFalse(template["attached_tables"]["tool_mode"])
        args = template["tools_metadata"]["value"][0]["args"]
        self.assertEqual(sorted(args), ["column", "file_name", "group_by", "operation"])

    def test_inputs_do_not_shadow_langflow_attributes(self):
        names = input_names(COMPONENT.read_text(encoding="utf-8"))
        self.assertFalse(RESERVED_COMPONENT_ATTRIBUTES & set(names))

    def test_verified_data_analyst_is_limited_to_builtin_dataset(self):
        description = self.nodes[VDA_ID]["data"]["node"]["template"]["tools_metadata"]["value"][0]["description"]
        self.assertIn("HANYA tentang dataset penjualan bawaan", description)
        self.assertIn("JANGAN dipakai untuk file CSV/TSV", description)

    def test_prompt_routes_data_by_source(self):
        self.assertTrue(self.prompt.startswith("CIEL AI MASTER — SYSTEM PROMPT v14.1"))
        self.assertIn("WAJIB gunakan Ciel Table Analyst (tool analyze_table)", self.prompt)
        self.assertIn("Gunakan Verified Data Analyst HANYA untuk dataset ini", self.prompt)
        self.assertIn("Jangan pernah menjawab pertanyaan tentang file pengguna dengan angka dari Verified Data Analyst", self.prompt)
        self.assertNotIn("- CSV\n", self.prompt)

    def test_only_expected_parts_change_from_v141(self):
        def strip(flow):
            flow = copy.deepcopy(flow)
            flow["data"]["nodes"] = [n for n in flow["data"]["nodes"] if n["id"] not in (TABLE_ID, VDA_ID) and not n["id"].startswith("Agent-")]
            flow["data"]["edges"] = [e for e in flow["data"]["edges"] if e["source"] != TABLE_ID]
            return flow

        self.assertEqual(strip(self.flow), strip(self.base))

    def test_snapshot_contains_no_hardcoded_api_keys(self):
        self.assertIsNone(re.search(r"sk-[A-Za-z0-9_-]{16,}", self.raw))


class AppTableWiringTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.source = APP_PATH.read_text(encoding="utf-8")

    def app_function(self, name, **namespace):
        tree = ast.parse(self.source)
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
        exec(compile(ast.Module(body=[fn], type_ignores=[]), str(APP_PATH), "exec"), namespace)
        return namespace[name]

    def test_app_sends_tables_to_the_table_analyst(self):
        self.assertIn(f'TABLE_ANALYST_ID = get_config("TABLE_ANALYST_ID") or "{TABLE_ID}"', self.source)
        self.assertIn('"attached_tables": encode_tables(tables)', self.source)

    def test_tables_survive_langflow_str_processing(self):
        # Langflow runs every str input through unescape_string, which turns each
        # backslash-n into a newline. Plain JSON broke there (live: the tool always
        # said "no file"); base64 carries the table through byte for byte.
        def langflow_unescape(value):
            return value.replace("\\n", "\n")

        import base64
        encode_tables = self.app_function("encode_tables", base64=base64, json=json)
        tables = {"toko.csv": {"text": "path;nilai\nC:\\new;1.250\nD:\\data;2\n", "truncated": False}}

        uninstall = install_langflow_stub()
        try:
            namespace = {}
            exec(compile(COMPONENT.read_text(encoding="utf-8"), "ciel_table_analyst.py", "exec"), namespace)
        finally:
            uninstall()
        load_tables = namespace["load_tables"]

        self.assertEqual(load_tables(langflow_unescape(encode_tables(tables))), tables)
        self.assertNotEqual(load_tables(langflow_unescape(json.dumps(tables))), tables)
        self.assertEqual(encode_tables({}), "")
        self.assertEqual(load_tables(""), {})
        self.assertIsNone(load_tables("not json or base64"))

    def test_prompt_gets_a_preview_and_the_tool_gets_the_whole_file(self):
        tree = ast.parse(self.source)
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "read_table_text")
        namespace = {"TABLE_PREVIEW_ROWS": 20, "MAX_TABLE_CHARS": 1_000_000}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), str(APP_PATH), "exec"), namespace)

        text = "a,b\n" + "\n".join(f"{i},{i * 2}" for i in range(100))
        item = namespace["read_table_text"]("data.csv", text, len(text))

        self.assertEqual(item["rows"], 100)
        self.assertEqual(len(item["text"].splitlines()), 21)
        self.assertEqual(item["table"], {"text": text, "truncated": False})


class TableAnalystBehaviourTest(unittest.TestCase):

    SALES = (
        "Kota;Produk;Penjualan;Unit\n"
        "Jakarta;Kopi;Rp 1.250.000;10\n"
        "Bandung;Teh;Rp 750.000;5\n"
        "Jakarta;Teh;Rp 500.000;4\n"
        "Surabaya;Kopi;1.234,5;\n"
    )

    def setUp(self):
        self.uninstall_stub = install_langflow_stub()
        source = COMPONENT.read_text(encoding="utf-8")
        self.Analyst = compile_class(source, "CielTableAnalyst")
        namespace = {}
        exec(compile(source, "ciel_table_analyst.py", "exec"), namespace)
        self.to_number = namespace["to_number"]
        self.detect_style = namespace["detect_style"]

    def tearDown(self):
        self.uninstall_stub()

    def run_tool(self, tables=None, **args):
        tables = {"penjualan.csv": {"text": self.SALES, "truncated": False}} if tables is None else tables
        inputs = {"file_name": "", "operation": "", "column": "", "group_by": ""}
        inputs.update(args)
        return self.Analyst(attached_tables=json.dumps(tables), **inputs).analyze_table()

    def test_number_style_is_decided_per_column(self):
        cases = [
            (["Rp 1.250.000", "Rp 750.000"], False, "comma_decimal"),   # multi-dot thousands
            (["750.000", "500.000"], True, "comma_decimal"),            # ambiguous, ';' file
            (["Rp 750.000"], False, "comma_decimal"),                   # ambiguous, Rupiah
            (["750.000", "500.000"], False, "dot_decimal"),             # ambiguous, no hint
            (["1.234,5", "12"], False, "comma_decimal"),
            (["1,234.5", "12.5"], False, "dot_decimal"),
            (["0,75", "1,5"], False, "comma_decimal"),
            (["1,250", "2,500"], False, "dot_decimal"),                 # comma thousands
        ]
        for values, semicolon, expected in cases:
            with self.subTest(values=values, semicolon=semicolon):
                self.assertEqual(self.detect_style(values, semicolon), expected)

    def test_parses_numbers_in_both_styles(self):
        cases = [
            ("Rp 1.250.000", "comma_decimal", 1250000.0), ("1.234,5", "comma_decimal", 1234.5),
            ("0,75", "comma_decimal", 0.75), ("12%", "comma_decimal", 12.0),
            ("1,234.5", "dot_decimal", 1234.5), ("750.000", "dot_decimal", 750.0),
            ("-3", "dot_decimal", -3.0), ("abc", "dot_decimal", None), ("", "comma_decimal", None),
            ("12-3", "dot_decimal", None),
        ]
        for raw, style, expected in cases:
            with self.subTest(raw=raw, style=style):
                self.assertEqual(self.to_number(raw, style), expected)

    def test_sum_and_mean_are_exact(self):
        total = self.run_tool(operation="sum", column="Penjualan")
        self.assertIn("HASIL TERVERIFIKASI", total)
        self.assertIn("Format angka kolom Penjualan dibaca sebagai: titik = pemisah ribuan, koma = desimal.", total)
        self.assertIn("sum(Penjualan) = 2.501.234,5", total)
        self.assertIn("mean(Penjualan) = 625.308,625", self.run_tool(operation="mean", column="penjualan"))

    def test_group_by(self):
        result = self.run_tool(operation="sum", column="Unit", group_by="Kota")
        self.assertIn("- Jakarta: 14", result)
        self.assertIn("- Bandung: 5", result)
        self.assertNotIn("Surabaya", result)  # its Unit is empty

    def test_count_and_top_values(self):
        self.assertIn("count(baris) = 4", self.run_tool(operation="count"))
        top = self.run_tool(operation="top_values", column="Produk")
        self.assertIn("- Kopi: 2 baris", top)
        self.assertIn("- Teh: 2 baris", top)

    def test_describe_lists_columns(self):
        result = self.run_tool(operation="describe")
        self.assertIn("Kolom (4): Kota, Produk, Penjualan, Unit", result)
        self.assertIn("- Penjualan (angka): jumlah=2.501.234,5", result)
        self.assertIn("- Kota (teks): 3 nilai unik", result)

    def test_unknown_column_and_operation_are_reported(self):
        self.assertIn("Kolom yang tersedia: Kota, Produk, Penjualan, Unit", self.run_tool(operation="sum", column="Omzet"))
        self.assertIn("tidak dikenal", self.run_tool(operation="variance", column="Unit"))

    def test_english_decimal_file(self):
        tables = {"scores.csv": {"text": "name,score\nA,12.5\nB,7.25\nC,1,000.5\n", "truncated": False}}
        # "1,000.5" splits into two cells in a comma file, so only A and B are numeric scores.
        result = self.run_tool(tables=tables, operation="sum", column="score")
        self.assertIn("sum(score) = 20,75", result)
        self.assertIn("koma = pemisah ribuan, titik = desimal", result)

    def test_no_attached_file_refuses_to_guess(self):
        result = self.run_tool(tables={}, operation="sum", column="Penjualan")
        self.assertIn("Tidak ada file CSV/TSV pengguna", result)
        self.assertIn("Jangan menebak angka", result)

    def test_unreadable_table_data_is_reported_not_hidden(self):
        result = self.Analyst(
            attached_tables="{broken", file_name="", operation="sum", column="x", group_by=""
        ).analyze_table()
        self.assertIn("tidak bisa dibaca", result)
        self.assertIn("Jangan menebak angka", result)

    def test_picks_named_file_and_warns_when_truncated(self):
        tables = {
            "a.csv": {"text": "x\n1\n2\n", "truncated": False},
            "b.csv": {"text": "x\n10\n20\n", "truncated": True},
        }
        self.assertIn("File 'c.csv' tidak ditemukan", self.run_tool(tables=tables, file_name="c.csv", operation="sum", column="x"))
        result = self.run_tool(tables=tables, file_name="B.CSV", operation="sum", column="x")
        self.assertIn("sum(x) = 30", result)
        self.assertIn("PERINGATAN: file terlalu besar", result)


if __name__ == "__main__":
    unittest.main()
