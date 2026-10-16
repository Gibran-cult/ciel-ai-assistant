import ast
import base64
import json
import re
import unittest
from pathlib import Path

import numpy as np

from tests.test_flow_v141_contract import compile_class, install_langflow_stub


ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / "flow" / "components"
ML_SOURCE = (COMPONENTS / "ciel_ml_analyst.py").read_text(encoding="utf-8")
TABLE_SOURCE = (COMPONENTS / "ciel_table_analyst.py").read_text(encoding="utf-8")

# Copied from the Table Analyst because Langflow components cannot import
# each other; both tools must read a file the same way.
SHARED = ("load_tables", "clean", "detect_style", "to_number", "fmt", "parse_table", "find_column")


def functions(source):
    return {n.name: ast.dump(n) for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)}


def number_after(label, text):
    match = re.search(re.escape(label) + r" ([+-]?[\d.]+(?:,\d+)?)", text)
    return float(match.group(1).replace(".", "").replace(",", "."))


def students(n=120, seed=0):
    """nilai = 30 + 4 jam + 0,3 hadir + 5 (Bandung) + noise; lulus is derived from nilai."""
    rng = np.random.default_rng(seed)
    rows = ["No;Nama;jam_belajar;kehadiran;kota;nilai;lulus"]
    for i in range(n):
        jam, hadir = rng.uniform(0, 10), rng.uniform(50, 100)
        kota = rng.choice(["Jakarta", "Bandung", "Surabaya"], p=[0.5, 0.3, 0.2])
        nilai = 30 + 4 * jam + 0.3 * hadir + (5 if kota == "Bandung" else 0) + rng.normal(0, 3)
        rows.append(
            f"{i + 1};Siswa {i};{jam:.2f};{hadir:.0f};{kota};{nilai:.2f};{'ya' if nilai > 70 else 'tidak'}"
            .replace(".", ",")
        )
    return "\n".join(rows)


class MLAnalystTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        uninstall = install_langflow_stub()
        try:
            cls.Analyst = compile_class(ML_SOURCE, "CielMLAnalyst")
        finally:
            uninstall()
        cls.STUDENTS = students()

    def run_tool(self, text=None, tables=None, **args):
        if tables is None:
            tables = {"siswa.csv": {"text": self.STUDENTS if text is None else text, "truncated": False}}
        inputs = {"file_name": "", "task": "", "target": "", "features": "", "clusters": "", "predict_for": "", "memory_owner": ""}
        inputs.update(args)
        return self.Analyst(attached_tables=json.dumps(tables), **inputs).train_model()

    def test_file_reading_matches_the_table_analyst(self):
        ml, table = functions(ML_SOURCE), functions(TABLE_SOURCE)
        for name in SHARED:
            with self.subTest(function=name):
                self.assertEqual(ml[name], table[name])

    def test_regression_recovers_the_true_effects(self):
        out = self.run_tool(task="predict", target="nilai", features="jam_belajar, kehadiran, kota")
        self.assertIn("Jenis: regresi linear, memprediksi angka nilai.", out)
        self.assertIn("uji silang 5 lipatan", out)
        self.assertGreater(number_after("R² =", out), 0.9)
        self.assertAlmostEqual(number_after("jam_belajar: setiap +1, nilai", out), 4.0, delta=0.3)
        self.assertAlmostEqual(number_after("kehadiran: setiap +1, nilai", out), 0.3, delta=0.08)
        self.assertAlmostEqual(number_after("kota = Bandung (dibanding Jakarta): nilai", out), 5.0, delta=1.5)
        self.assertLess(number_after("Rata-rata meleset (MAE) =", out), number_after("menebak rata-rata saja meleset", out))
        self.assertIn("bukan bukti sebab-akibat", out)

    def test_effects_come_with_a_comparable_scale_and_keep_their_order(self):
        # Per +1, kota=Bandung (+5) looks bigger than kehadiran (+0,3), but one
        # standard deviation of kehadiran (~14 points) moves nilai by ~4.
        out = self.run_tool(task="predict", target="nilai", features="jam_belajar, kehadiran, kota")
        self.assertIn("pertahankan urutannya dan jangan mengurutkan ulang dari angka 'setiap +1'", out)
        effects = [line for line in out.splitlines() if line.startswith("- ") and ": " in line and "nilai" in line]
        self.assertTrue(effects[0].startswith("- jam_belajar: setiap +1"))
        self.assertTrue(effects[1].startswith("- kehadiran: setiap +1"))
        per_sd = re.search(r"kehadiran: .*naik 1 standar deviasi \(([\d,]+)\), nilai \+([\d,]+)", out)
        self.assertAlmostEqual(float(per_sd.group(1).replace(",", ".")), 14, delta=2)
        self.assertAlmostEqual(float(per_sd.group(2).replace(",", ".")), 0.3 * 14, delta=1)

    def test_results_are_deterministic(self):
        args = {"task": "predict", "target": "lulus", "predict_for": "jam_belajar=6"}
        self.assertEqual(self.run_tool(**args), self.run_tool(**args))
        self.assertEqual(self.run_tool(task="cluster"), self.run_tool(task="cluster"))

    def test_row_numbers_and_names_are_not_features(self):
        out = self.run_tool(task="predict", target="nilai")
        self.assertIn("No (nomor urut)", out)
        self.assertIn("Nama (hampir semua nilainya beda, seperti ID atau nama)", out)
        features = next(line for line in out.splitlines() if line.startswith("Fitur ("))
        self.assertNotIn("No", features.split(": ", 1)[1].split(", "))
        self.assertNotIn("nilai", features.split(": ", 1)[1].split(", "))

    def test_classification_beats_the_majority_baseline(self):
        out = self.run_tool(task="predict", target="lulus", features="jam_belajar, kehadiran, kota")
        self.assertIn("Jenis: klasifikasi (regresi logistik), memprediksi kategori lulus", out)
        accuracy = number_after("Akurasi =", out)
        baseline = float(re.search(r"saja: ([\d,]+)%", out).group(1).replace(",", "."))
        self.assertGreater(accuracy, baseline + 15)
        self.assertIn("presisi", out)
        self.assertIn("recall", out)
        self.assertNotIn("Model lemah", out)

    def test_useless_features_are_reported_as_a_weak_model(self):
        rng = np.random.default_rng(3)
        text = "noise,target\n" + "\n".join(f"{rng.normal():.3f},{rng.normal() * 10:.3f}" for _ in range(80))
        out = self.run_tool(text=text, task="predict", target="target")
        self.assertIn("Model lemah", out)
        self.assertLess(number_after("R² =", out), 0.1)

    def test_a_leaky_feature_triggers_a_warning(self):
        text = "x,copy\n" + "\n".join(f"{i * 1.5 + 7},{i * 3}" for i in range(0, 60, 2))
        out = self.run_tool(text=text, task="predict", target="copy")
        self.assertIn("Hasil hampir sempurna", out)
        self.assertIn("bocoran", out)

    def test_predict_for_fills_missing_values_and_reports_what_it_assumed(self):
        out = self.run_tool(
            task="predict", target="nilai", features="jam_belajar, kehadiran, kota",
            predict_for="jam_belajar=5; kota=Bandung; warna=biru",
        )
        self.assertIn("Prediksi untuk data baru (jam_belajar=5; kota=Bandung):", out)
        # 30 + 4*5 + 0,3*median(hadir ~ 75) + 5 = ~77,5
        self.assertAlmostEqual(number_after("Perkiraan nilai =", out), 77.5, delta=4)
        self.assertIn("kehadiran=", out)
        self.assertIn("(median)", out)
        self.assertIn("Diabaikan karena bukan fitur model: warna", out)

    def test_predict_for_classification_gives_probabilities(self):
        out = self.run_tool(task="predict", target="lulus", features="jam_belajar, kehadiran", predict_for="jam_belajar=9,5; kehadiran=95")
        self.assertIn("Perkiraan lulus: 'ya'", out)
        self.assertIn("Kemungkinan lain: 'tidak'", out)

    def test_predict_for_rejects_text_in_a_number_column_and_flags_unseen_categories(self):
        out = self.run_tool(task="predict", target="nilai", predict_for="jam_belajar=banyak")
        self.assertIn("Prediksi tidak dibuat: nilai bukan angka untuk jam_belajar=banyak.", out)
        out = self.run_tool(task="predict", target="nilai", features="jam_belajar, kota", predict_for="jam_belajar=5; kota=Medan")
        self.assertIn("Nilai yang tidak pernah muncul di data (model tidak tahu efeknya): kota=Medan", out)

    def test_cluster_finds_separated_groups(self):
        rng = np.random.default_rng(5)
        rows = ["belanja,kunjungan"]
        for center in ((10, 1), (50, 8), (90, 2)):
            rows += [f"{center[0] + rng.normal():.2f},{center[1] + rng.normal() * 0.3:.2f}" for _ in range(30)]
        out = self.run_tool(text="\n".join(rows), task="cluster")
        self.assertIn("Jumlah kelompok: 3 (dipilih otomatis", out)
        self.assertIn(": jelas", out)
        self.assertEqual(len(re.findall(r"^Kelompok \d — 30 baris", out, re.M)), 3)
        self.assertIn("bukan label yang benar", out)

    def test_rare_categories_do_not_become_their_own_cluster(self):
        out = self.run_tool(task="cluster", features="jam_belajar, kehadiran, kota")
        self.assertNotIn("(100,0%;", out)

    def test_requested_cluster_count_is_validated(self):
        self.assertIn("Jumlah kelompok: 4 (diminta).", self.run_tool(task="cluster", clusters="4"))
        self.assertIn("Jumlah kelompok harus angka 2 sampai 10.", self.run_tool(task="cluster", clusters="12"))
        self.assertIn("Jumlah kelompok harus angka", self.run_tool(task="cluster", clusters="tiga"))

    def test_input_errors_never_produce_numbers(self):
        cases = [
            ({"tables": {}, "task": "predict", "target": "nilai"}, "Tidak ada file CSV/TSV pengguna"),
            ({"tables": {"a.csv": {"text": "x"}}, "file_name": "b.csv", "task": "cluster"}, "File atau dataset 'b.csv' tidak ditemukan"),
            ({"task": "predict"}, "isi target dengan kolom yang ingin diprediksi"),
            ({"task": "predict", "target": "skor"}, "Kolom yang tersedia di siswa.csv: No, Nama"),
            ({"task": "terbang"}, "Task 'terbang' tidak dikenal"),
            ({"task": "predict", "target": "nilai", "features": "tinggi"}, "Kolom 'tinggi' tidak ada di siswa.csv"),
            ({"text": "a,b\n1,2\n2,3\n3,5", "task": "predict", "target": "b"}, "Data terlalu sedikit"),
            ({"text": "a,b\n1,2", "task": "cluster"}, "Data terlalu sedikit untuk dikelompokkan"),
        ]
        for args, expected in cases:
            with self.subTest(expected=expected):
                out = self.run_tool(**args)
                self.assertIn(expected, out)
                self.assertNotIn("HASIL MODEL", out)

    def test_target_alone_implies_predict_and_synonyms_work(self):
        self.assertIn("regresi linear", self.run_tool(target="nilai"))
        self.assertIn("pengelompokan k-means", self.run_tool(task="segmentasi"))

    def test_too_many_classes_is_refused(self):
        text = "x,kode\n" + "\n".join(f"{i % 7},K{i % 25}" for i in range(100))
        self.assertIn("terlalu banyak untuk diprediksi sebagai kategori", self.run_tool(text=text, task="predict", target="kode"))

    def test_unreadable_payload_is_reported(self):
        out = self.Analyst(attached_tables="bukan json", memory_owner="", file_name="", task="cluster", target="",
                           features="", clusters="", predict_for="").train_model()
        self.assertIn("tidak bisa dibaca", out)

    def test_truncated_and_sampled_files_are_flagged(self):
        out = self.run_tool(tables={"siswa.csv": {"text": self.STUDENTS, "truncated": True}}, task="cluster")
        self.assertIn("PERINGATAN: file terlalu besar dan dipotong", out)

        limits = self.Analyst.train_model.__globals__
        original, limits["MAX_ROWS"] = limits["MAX_ROWS"], 50
        try:
            out = self.run_tool(task="predict", target="nilai")
        finally:
            limits["MAX_ROWS"] = original
        self.assertIn("file punya 120 baris; model memakai sampel acak 50 baris", out)
        self.assertIn("(50 baris dipakai)", out)

    def test_tables_from_the_app_survive_langflow_str_processing(self):
        encoded = base64.b64encode(json.dumps({"siswa.csv": {"text": self.STUDENTS, "truncated": False}}).encode()).decode()
        out = self.Analyst(attached_tables=encoded.replace("\\n", "\n"), memory_owner="", file_name="", task="predict",
                           target="nilai", features="", clusters="", predict_for="").train_model()
        self.assertIn("HASIL MODEL — dilatih langsung dari file siswa.csv (120 baris dipakai).", out)

    def test_folds_keep_every_class_in_every_fold(self):
        folds_for = self.Analyst.train_model.__globals__["folds_for"]
        labels = np.array([0] * 40 + [1] * 10)
        fold = folds_for(len(labels), labels)
        for f in range(5):
            self.assertEqual(sorted(set(labels[fold == f])), [0, 1])
            self.assertEqual(int((fold == f).sum()), 10)


if __name__ == "__main__":
    unittest.main()
