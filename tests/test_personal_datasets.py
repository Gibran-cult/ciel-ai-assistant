import ast
import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from tests.test_flow_v141_contract import compile_class, install_langflow_stub
from tests.test_privacy import Response, load_app_functions


ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / "flow" / "components"
SOURCES = {
    "store": COMPONENTS / "ciel_dataset_store.py",
    "table": COMPONENTS / "ciel_table_analyst.py",
    "ml": COMPONENTS / "ciel_ml_analyst.py",
    "admin": COMPONENTS / "ciel_memory_admin.py",
}
ALICE = "aaaa1111aaaa1111"
BOB = "bbbb2222bbbb2222"

WEEK1 = "tanggal;jam_belajar;nilai_kuis\n01-10-2026;2,5;70\n02-10-2026;4;82\n"
WEEK2 = "tanggal,jam_belajar,nilai_kuis\n08-10-2026,3.5,78\n09-10-2026,5,90\n"


def functions(path):
    source = path.read_text(encoding="utf-8")
    return {n.name: ast.dump(n) for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)}


def tables(**files):
    return json.dumps({name.replace("_csv", ".csv"): {"text": text, "truncated": False} for name, text in files.items()})


class SharedHelpersTest(unittest.TestCase):

    def test_saved_dataset_helpers_are_identical_everywhere(self):
        found = {name: functions(path) for name, path in SOURCES.items()}
        for helper in ("owner_dir", "saved_tables"):
            for name in SOURCES:
                with self.subTest(helper=helper, component=name):
                    self.assertEqual(found[name][helper], found["store"][helper])

    def test_both_analysts_pick_tables_the_same_way(self):
        self.assertEqual(functions(SOURCES["table"])["pick_table"], functions(SOURCES["ml"])["pick_table"])

    def test_dataset_store_reads_files_like_the_table_analyst(self):
        store, table = functions(SOURCES["store"]), functions(SOURCES["table"])
        for helper in ("load_tables", "clean", "detect_style", "to_number", "parse_table", "find_column"):
            with self.subTest(helper=helper):
                self.assertEqual(store[helper], table[helper])


class DatasetTestCase(unittest.TestCase):
    """Runs the components against a temporary home folder."""

    @classmethod
    def setUpClass(cls):
        uninstall = install_langflow_stub()
        try:
            cls.Store = compile_class(SOURCES["store"].read_text(encoding="utf-8"), "CielDatasetStore")
            cls.Table = compile_class(SOURCES["table"].read_text(encoding="utf-8"), "CielTableAnalyst")
            cls.ML = compile_class(SOURCES["ml"].read_text(encoding="utf-8"), "CielMLAnalyst")
        finally:
            uninstall()

    def setUp(self):
        self.home = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.home_patch = patch.object(Path, "home", return_value=Path(self.home.name))
        self.home_patch.start()

    def tearDown(self):
        self.home_patch.stop()
        self.home.cleanup()

    def folder(self, owner=ALICE):
        return Path(self.home.name) / ".ciel_ai" / "user_datasets" / owner

    def store(self, owner=ALICE, attached="", **args):
        inputs = {"action": "", "dataset": "", "file_name": "", "rows": ""}
        inputs.update(args)
        return self.Store(memory_owner=owner, attached_tables=attached, **inputs).manage_dataset()

    def table(self, owner=ALICE, attached="", **args):
        inputs = {"file_name": "", "operation": "", "column": "", "group_by": ""}
        inputs.update(args)
        return self.Table(memory_owner=owner, attached_tables=attached, **inputs).analyze_table()

    def ml(self, owner=ALICE, attached="", **args):
        inputs = {"file_name": "", "task": "", "target": "", "features": "", "clusters": "", "predict_for": ""}
        inputs.update(args)
        return self.ML(memory_owner=owner, attached_tables=attached, **inputs).train_model()


class DatasetStoreTest(DatasetTestCase):

    def test_file_then_another_file_then_chat_grow_one_dataset(self):
        out = self.store(action="save_file", dataset="Belajar Harian", attached=tables(minggu1_csv=WEEK1))
        self.assertIn("TERSIMPAN — dataset 'belajar_harian' dibuat: 2 baris baru dari file minggu1.csv", out)
        out = self.store(action="save_file", dataset="belajar_harian", attached=tables(minggu2_csv=WEEK2))
        self.assertIn("sekarang 4 baris", out)
        out = self.store(action="add_rows", dataset="belajar_harian", rows="tanggal=16-10-2026; jam belajar=3,5; nilai_kuis=85")
        self.assertIn("1 baris baru dari chat, sekarang 5 baris", out)
        # The dot-decimal file was rewritten in the dataset's own format.
        self.assertEqual(
            (self.folder() / "belajar_harian.csv").read_text(encoding="utf-8"),
            "tanggal;jam_belajar;nilai_kuis\n01-10-2026;2,5;70\n02-10-2026;4;82\n"
            "08-10-2026;3,5;78\n09-10-2026;5;90\n16-10-2026;3,5;85\n",
        )

    def test_saving_the_same_file_twice_is_refused(self):
        self.store(action="save_file", dataset="belajar", attached=tables(minggu1_csv=WEEK1))
        out = self.store(action="save_file", dataset="belajar", attached=tables(minggu1_csv=WEEK1))
        self.assertIn("sudah tersimpan", out)
        self.assertIn("Tidak disimpan lagi", out)

    def test_mismatched_columns_change_nothing(self):
        self.store(action="save_file", dataset="belajar", attached=tables(minggu1_csv=WEEK1))
        before = (self.folder() / "belajar.csv").read_text(encoding="utf-8")
        self.assertIn("Hilang: tanggal, jam_belajar, nilai_kuis; baru: a, b", self.store(action="save_file", dataset="belajar", attached=tables(x_csv="a,b\n1,2\n")))
        self.assertIn("Kolom mood tidak ada di dataset", self.store(action="add_rows", dataset="belajar", rows="tanggal=1; mood=senang"))
        self.assertEqual((self.folder() / "belajar.csv").read_text(encoding="utf-8"), before)

    def test_chat_rows_create_a_dataset_with_indonesian_numbers(self):
        out = self.store(action="add_rows", dataset="pengeluaran",
                         rows="tanggal=16-10-2026; kategori=makan; jumlah=25.000\ntanggal=16-10-2026; kategori=buku; jumlah=80.000")
        self.assertIn("dataset 'pengeluaran' dibuat: 2 baris baru dari chat", out)
        total = self.table(file_name="pengeluaran", operation="sum", column="jumlah")
        self.assertIn("dihitung langsung dari dataset tersimpan pengeluaran", total)
        self.assertIn("sum(jumlah) = 105.000", total)

    def test_list_and_show(self):
        self.assertIn("Belum ada dataset tersimpan", self.store(action="list"))
        self.store(action="save_file", dataset="belajar", attached=tables(minggu1_csv=WEEK1))
        listing = self.store(action="list")
        self.assertIn("- belajar: 2 baris; kolom: tanggal, jam_belajar, nilai_kuis", listing)
        shown = self.store(action="show", dataset="belajar")
        self.assertIn("- tanggal=02-10-2026; jam_belajar=4; nilai_kuis=82", shown)
        self.assertIn("Dataset 'lain' belum ada", self.store(action="show", dataset="lain"))

    def test_anonymous_visitors_store_nothing(self):
        for owner in ("", "short", "../../etc/passwd", "a" * 65):
            with self.subTest(owner=owner):
                out = self.store(owner=owner, action="save_file", dataset="belajar", attached=tables(minggu1_csv=WEEK1))
                self.assertIn("hanya tersedia untuk pengguna yang login", out)
        self.assertFalse((Path(self.home.name) / ".ciel_ai").exists())

    def test_dataset_names_cannot_leave_the_owner_folder(self):
        self.store(action="add_rows", dataset="../../../evil", rows="a=1")
        self.assertEqual([p.name for p in self.folder().iterdir()], ["evil.csv"])
        self.assertIn("tidak bisa dipakai", self.store(action="show", dataset="///"))

    def test_limits(self):
        for i in range(5):
            self.store(action="add_rows", dataset=f"d{i}", rows="a=1")
        self.assertIn("batas maksimal", self.store(action="add_rows", dataset="d5", rows="a=1"))
        self.assertIn("TERSIMPAN", self.store(action="add_rows", dataset="d0", rows="a=2"))

        limits = self.Store.manage_dataset.__globals__
        original, limits["MAX_DATASET_ROWS"] = limits["MAX_DATASET_ROWS"], 3
        try:
            self.assertIn("melebihi batas 3", self.store(action="add_rows", dataset="d0", rows="a=3\na=4"))
        finally:
            limits["MAX_DATASET_ROWS"] = original

        truncated = json.dumps({"besar.csv": {"text": WEEK1, "truncated": True}})
        self.assertIn("terpotong, jadi tidak disimpan", self.store(action="save_file", dataset="d1", attached=truncated))

    def test_unknown_action_and_unreadable_rows(self):
        self.assertIn("Action 'delete' tidak dikenal", self.store(action="delete", dataset="belajar"))
        self.assertIn("Tidak ada baris yang bisa dibaca", self.store(action="add_rows", dataset="belajar", rows="tanpa format"))


class AnalystsReadSavedDatasetsTest(DatasetTestCase):

    def setUp(self):
        super().setUp()
        self.store(action="save_file", dataset="belajar", attached=tables(minggu1_csv=WEEK1))
        self.store(action="save_file", dataset="belajar", attached=tables(minggu2_csv=WEEK2))

    def test_table_analyst_uses_the_whole_history(self):
        out = self.table(file_name="belajar", operation="mean", column="nilai_kuis")
        self.assertIn("dihitung langsung dari dataset tersimpan belajar (4 baris data)", out)
        self.assertIn("mean(nilai_kuis) = 80", out)
        # The only saved dataset is the default when nothing is attached.
        self.assertIn("dataset tersimpan belajar", self.table(operation="count"))

    def test_attached_file_wins_and_names_are_forgiving(self):
        out = self.table(attached=tables(baru_csv="x\n1\n2\n"), operation="count")
        self.assertIn("dihitung langsung dari file baru.csv", out)
        self.assertIn("dataset tersimpan belajar", self.table(attached=tables(baru_csv="x\n1\n"), file_name="Belajar.csv", operation="count"))

    def test_ml_analyst_trains_on_the_saved_dataset(self):
        rows = "\n".join(f"tanggal=d{i}; jam_belajar={i % 7}; nilai_kuis={50 + 5 * (i % 7)}" for i in range(30))
        self.store(action="add_rows", dataset="belajar", rows=rows)
        out = self.ml(file_name="belajar", task="predict", target="nilai_kuis", features="jam_belajar")
        self.assertIn("HASIL MODEL — dilatih langsung dari dataset tersimpan belajar (34 baris dipakai).", out)

    def test_another_account_cannot_see_the_dataset(self):
        out = self.table(owner=BOB, file_name="belajar", operation="count")
        self.assertIn("Tidak ada file CSV/TSV pengguna atau dataset tersimpan", out)
        self.assertIn("Tidak ada file CSV/TSV pengguna atau dataset tersimpan", self.ml(owner="", task="cluster"))
        self.assertIn("Belum ada dataset tersimpan", self.store(owner=BOB, action="list"))


@unittest.skipUnless(importlib.util.find_spec("chromadb"), "chromadb not installed")
class MemoryAdminDatasetsTest(DatasetTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        uninstall = install_langflow_stub()
        try:
            cls.Admin = compile_class(SOURCES["admin"].read_text(encoding="utf-8"), "CielMemoryAdmin")
        finally:
            uninstall()

    def admin(self, action, owner=ALICE, name=""):
        return self.Admin(memory_owner=owner, memory_action=action, memory_id="", dataset_name=name).handle()

    def test_list_export_and_delete_only_touch_the_owner(self):
        self.store(action="save_file", dataset="belajar", attached=tables(minggu1_csv=WEEK1))
        self.store(owner=BOB, action="add_rows", dataset="punya_bob", rows="a=1")

        listing = self.admin("list_datasets")
        self.assertEqual([(d["name"], d["rows"]) for d in listing["datasets"]], [("belajar", 2)])
        self.assertEqual(self.admin("export_dataset", name="belajar")["text"], WEEK1)

        self.assertEqual(self.admin("export_dataset", name="punya_bob"), {"ok": False, "error": "not_found"})
        self.assertEqual(self.admin("delete_dataset", name="../bbbb2222bbbb2222/punya_bob"), {"ok": False, "error": "not_found"})
        self.assertEqual(self.admin("delete_dataset", name="belajar"), {"ok": True, "deleted": 1})
        self.assertTrue((self.folder(BOB) / "punya_bob.csv").exists())

    def test_delete_all_and_login(self):
        self.store(action="add_rows", dataset="a", rows="x=1")
        self.store(action="add_rows", dataset="b", rows="x=1")
        self.assertEqual(self.admin("delete_all_datasets"), {"ok": True, "deleted": 2})
        self.assertEqual(self.admin("list_datasets"), {"ok": True, "total": 0, "datasets": []})
        self.assertEqual(self.admin("list_datasets", owner=""), {"ok": False, "error": "login_required"})


class AppDatasetControlsTest(unittest.TestCase):

    def namespace(self, owner):
        import logging
        import uuid
        return load_app_functions(
            ("memory_admin",),
            requests=requests, uuid=uuid, json=json, logger=logging.getLogger("test_personal_datasets"),
            memory_owner_id=lambda: owner,
            NGROK_URL="https://example.invalid", NGROK_USER="u", NGROK_PASSWORD="p",
            LANGFLOW_API_KEY="k", MEMORY_ADMIN_FLOW_ID="admin-flow", MEMORY_ADMIN_NODE_ID="CielMemoryAdmin-adm1n",
        )

    def test_dataset_actions_send_the_dataset_name(self):
        reply = {"outputs": [{"outputs": [{"results": {"message": {"data": {"text": json.dumps({"ok": True})}}}}]}]}
        with self.assertLogs("test_personal_datasets", level="INFO"), \
                patch("requests.post", return_value=Response(reply)) as post:
            self.namespace(ALICE)["memory_admin"]("delete_dataset", dataset_name="belajar")
        tweak = post.call_args.kwargs["json"]["tweaks"]["CielMemoryAdmin-adm1n"]
        self.assertEqual(tweak, {"memory_owner": ALICE, "memory_action": "delete_dataset", "memory_id": "", "dataset_name": "belajar"})

    def test_privacy_page_describes_datasets_only_when_login_works(self):
        import privacy
        text = lambda **kw: " ".join(i for _, items in privacy.privacy_sections(retention_days=30, **kw) for i in items)
        full = text(memory_enabled=True, data_controls=True)
        self.assertIn("<strong>Dataset pribadi</strong> (hanya setelah login)", full)
        self.assertIn("tidak menyimpan dataset tanpa permintaanmu", full)
        self.assertIn("mengunduh, dan menghapus dataset pribadimu", full)
        self.assertNotIn("Dataset pribadi", text(memory_enabled=False, data_controls=False))


if __name__ == "__main__":
    unittest.main()
