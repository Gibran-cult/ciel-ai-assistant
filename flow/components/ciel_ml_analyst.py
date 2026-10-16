from langflow.custom import Component
from langflow.io import MessageTextInput, Output

import base64
import binascii
import csv
import io
import json
import re

import numpy as np


TASKS = {
    "predict": "predict", "prediksi": "predict", "regression": "predict", "regresi": "predict",
    "classification": "predict", "klasifikasi": "predict",
    "cluster": "cluster", "clustering": "cluster", "kelompok": "cluster", "segmentasi": "cluster",
}
NUMERIC = re.compile(r"^[+-]?[\d.,]*\d[\d.,]*$")

SEED = 42
FOLDS = 5
MIN_ROWS_PREDICT = 20
MIN_ROWS_CLUSTER = 10
MAX_ROWS = 10_000
MAX_CLASSES = 20
MAX_CATEGORIES = 10
REGRESSION_MIN_DISTINCT = 11
MAX_EFFECTS_SHOWN = 8
RIDGE = 1.0
L2 = 0.01
STEPS = 500
KMEANS_INITS = 4
KMEANS_STEPS = 100
AUTO_K = range(2, 7)
SILHOUETTE_SAMPLE = 1000
OTHER = "(lainnya)"
EMPTY = "(kosong)"


# ---------------------------------------------------------------------------
# Membaca file: disalin apa adanya dari ciel_table_analyst.py (komponen Langflow
# tidak bisa saling import). tests/test_ml_analyst.py memastikan keduanya sama.
# ---------------------------------------------------------------------------

def load_tables(raw):
    """
    The app sends {name: {"text", "truncated"}} as base64-encoded JSON.
    Langflow runs str inputs through unescape_string (every backslash-n becomes
    a newline), which breaks plain JSON; base64 has no backslashes. Plain JSON
    is still accepted for manual runs. Returns None if the value is unreadable.
    """
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        text = base64.b64decode(text, validate=True).decode("utf-8")
    except (binascii.Error, ValueError):
        pass
    try:
        data = json.loads(text, strict=False)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def clean(value):
    return (
        str(value).replace("Rp", "").replace("rp", "").replace("%", "")
        .replace(" ", "").replace(" ", "").strip()
    )


def detect_style(values, semicolon=False):
    """
    Decide per column whether "." or "," is the decimal mark, using every value.
    750.000 alone is ambiguous; Rupiah values or a ";"-separated file (Excel in
    Indonesian locale) tip it to "titik = ribuan".
    """
    comma_votes = dot_votes = 0
    ambiguous = rupiah = False
    for raw in values:
        rupiah = rupiah or "rp" in str(raw).lower()
        text = clean(raw)
        if not text or not NUMERIC.match(text):
            continue
        if "," in text and "." in text:
            if text.rfind(",") > text.rfind("."):
                comma_votes += 1
            else:
                dot_votes += 1
        elif "," in text:
            tail = text.rsplit(",", 1)[1]
            if text.count(",") > 1 or len(tail) == 3:
                dot_votes += 1
            else:
                comma_votes += 1
        elif "." in text:
            tail = text.rsplit(".", 1)[1]
            if text.count(".") > 1:
                comma_votes += 1
            elif len(tail) == 3:
                ambiguous = True
            else:
                dot_votes += 1
    if comma_votes != dot_votes:
        return "comma_decimal" if comma_votes > dot_votes else "dot_decimal"
    if ambiguous and (rupiah or semicolon):
        return "comma_decimal"
    return "dot_decimal"


def to_number(value, style="dot_decimal"):
    text = clean(value)
    if not text or not NUMERIC.match(text):
        return None
    if style == "comma_decimal":
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def fmt(value):
    if isinstance(value, float):
        if value.is_integer():
            return f"{int(value):,}".replace(",", ".")
        return f"{value:,.4f}".rstrip("0").rstrip(".").replace(",", "_").replace(".", ",").replace("_", ".")
    return str(value)


def parse_table(text):
    """Return (header, records, delimiter)."""
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel_tab if sample.count("\t") > sample.count(",") else csv.excel
    rows = list(csv.reader(io.StringIO(text), dialect))
    rows = [r for r in rows if any(cell.strip() for cell in r)]
    if not rows:
        return [], [], dialect.delimiter
    header = [h.strip() or f"kolom_{i + 1}" for i, h in enumerate(rows[0])]
    records = []
    for r in rows[1:]:
        r = (r + [""] * len(header))[: len(header)]
        records.append(dict(zip(header, (c.strip() for c in r))))
    return header, records, dialect.delimiter


def find_column(header, name):
    if not name:
        return None
    for h in header:
        if h == name:
            return h
    lowered = {h.lower(): h for h in header}
    return lowered.get(name.strip().lower())


# ---------------------------------------------------------------------------
# Format angka hasil model (format Indonesia, sama seperti Table Analyst).
# ---------------------------------------------------------------------------

def show(value):
    value = float(value)
    return fmt(round(value, 2 if abs(value) >= 10 else 4) + 0.0)


def signed(value):
    return f"+{show(value)}" if value > 0 else show(value)


def pct(value):
    return f"{value * 100:.1f}%".replace(".", ",")


# ---------------------------------------------------------------------------
# Memilih fitur dan mengubah baris menjadi matriks angka.
# ---------------------------------------------------------------------------

def is_row_number(numbers):
    if len(numbers) < 3 or any(x is None or not x.is_integer() for x in numbers):
        return False
    start = int(numbers[0])
    return [int(x) for x in numbers] == list(range(start, start + len(numbers)))


def choose_features(records, columns, styles):
    """Return ({column: "number" | "text"}, [alasan kolom yang dilewati])."""
    kinds, skipped = {}, []
    for column in columns:
        values = [r[column] for r in records]
        filled = [v for v in values if v != ""]
        distinct = len(set(filled))
        numbers = [to_number(v, styles[column]) for v in values]
        is_number = bool(filled) and all(to_number(v, styles[column]) is not None for v in filled)
        if not filled:
            skipped.append(f"{column} (kosong)")
        elif distinct == 1:
            skipped.append(f"{column} (nilainya sama semua)")
        elif is_number and is_row_number(numbers):
            skipped.append(f"{column} (nomor urut)")
        elif not is_number and distinct > MAX_CATEGORIES and distinct > 0.5 * len(filled):
            skipped.append(f"{column} (hampir semua nilainya beda, seperti ID atau nama)")
        else:
            kinds[column] = "number" if is_number else "text"
    return kinds, skipped


def fit_design(records, kinds, styles):
    """
    Numeric columns: missing values become the median. Text columns: one 0/1
    column per category, with the most common category as the reference, so
    each effect reads as "dibanding <kategori terbanyak>".
    """
    specs = []
    for column, kind in kinds.items():
        values = [r[column] for r in records]
        if kind == "number":
            numbers = [x for x in (to_number(v, styles[column]) for v in values) if x is not None]
            specs.append({"column": column, "kind": kind, "fill": float(np.median(numbers)) if numbers else 0.0})
            continue
        counts = {}
        for v in values:
            counts[v or EMPTY] = counts.get(v or EMPTY, 0) + 1
        ranked = sorted(counts, key=lambda key: (-counts[key], key))
        specs.append({
            "column": column, "kind": kind, "reference": ranked[0],
            "levels": ranked[1:MAX_CATEGORIES], "other": len(ranked) > MAX_CATEGORIES,
        })
    return specs


def design_labels(specs):
    labels = []
    for spec in specs:
        if spec["kind"] == "number":
            labels.append((spec, None))
            continue
        labels.extend((spec, level) for level in spec["levels"])
        if spec["other"]:
            labels.append((spec, OTHER))
    return labels


def transform(specs, records, styles):
    rows = []
    for r in records:
        row = []
        for spec in specs:
            raw = r.get(spec["column"], "")
            if spec["kind"] == "number":
                x = to_number(raw, styles[spec["column"]])
                row.append(spec["fill"] if x is None else x)
                continue
            key = raw or EMPTY
            row.extend(1.0 if key == level else 0.0 for level in spec["levels"])
            if spec["other"]:
                row.append(0.0 if key == spec["reference"] or key in spec["levels"] else 1.0)
        rows.append(row)
    return np.array(rows, dtype=float).reshape(len(records), -1)


def scale(X):
    mu = X.mean(axis=0)
    sd = X.std(axis=0)
    sd[sd == 0] = 1.0
    return mu, sd


# ---------------------------------------------------------------------------
# Model: regresi linear (ridge), regresi logistik, k-means. Hanya numpy dan
# seed tetap, jadi file yang sama selalu memberi hasil yang sama.
# ---------------------------------------------------------------------------

def fit_regression(X, y):
    mu, sd = scale(X)
    Z = (X - mu) / sd
    d = Z.shape[1]
    w = np.linalg.solve(Z.T @ Z + RIDGE * np.eye(d), Z.T @ (y - y.mean())) if d else np.zeros(0)
    return {"mu": mu, "sd": sd, "w": w, "b": float(y.mean())}


def predict_regression(model, X):
    return ((X - model["mu"]) / model["sd"]) @ model["w"] + model["b"]


def softmax(scores):
    scores = scores - scores.max(axis=1, keepdims=True)
    e = np.exp(scores)
    return e / e.sum(axis=1, keepdims=True)


def fit_classifier(X, y, k):
    mu, sd = scale(X)
    Z = (X - mu) / sd
    n, d = Z.shape
    Y = np.eye(k)[y]
    W = np.zeros((d, k))
    b = np.log(Y.mean(axis=0) + 1e-9)
    # Step 1/L with L an upper bound of the loss curvature: never diverges,
    # even when one-hot columns are strongly correlated.
    curvature = 0.5 * float(np.linalg.eigvalsh(Z.T @ Z / n).max()) if d else 0.0
    step = 1.0 / (curvature + L2 + 1e-9)
    for _ in range(STEPS):
        G = (softmax(Z @ W + b) - Y) / n
        W -= step * (Z.T @ G + L2 * W)
        b -= min(step, 1.0) * G.sum(axis=0)
    return {"mu": mu, "sd": sd, "W": W, "b": b}


def predict_proba(model, X):
    return softmax(((X - model["mu"]) / model["sd"]) @ model["W"] + model["b"])


def folds_for(n, labels=None):
    order = np.random.default_rng(SEED).permutation(n)
    if labels is not None:
        # Urutkan per kelas lalu bagikan bergiliran: tiap lipatan punya
        # proporsi kelas yang mirip.
        order = order[np.argsort(labels[order], kind="stable")]
    fold = np.empty(n, dtype=int)
    fold[order] = np.arange(n) % FOLDS
    return fold


def cross_validate(records, kinds, styles, y, classes=None):
    """
    Out-of-fold predictions: each row is predicted by a model that never saw
    it. Medians, categories and scaling are refit inside every fold, so no
    information from the test rows leaks into training.
    Returns (model predictions, baseline predictions).
    """
    n = len(records)
    fold = folds_for(n, y if classes else None)
    predicted = np.zeros(n, dtype=int if classes else float)
    baseline = np.zeros(n, dtype=int if classes else float)
    for f in range(FOLDS):
        train, test = np.where(fold != f)[0], np.where(fold == f)[0]
        if not len(test):
            continue
        train_records = [records[i] for i in train]
        specs = fit_design(train_records, kinds, styles)
        X_train = transform(specs, train_records, styles)
        X_test = transform(specs, [records[i] for i in test], styles)
        if classes:
            model = fit_classifier(X_train, y[train], len(classes))
            predicted[test] = predict_proba(model, X_test).argmax(axis=1)
            baseline[test] = np.bincount(y[train], minlength=len(classes)).argmax()
        else:
            predicted[test] = predict_regression(fit_regression(X_train, y[train]), X_test)
            baseline[test] = y[train].mean()
    return predicted, baseline


def squared_distances(Z, C):
    return np.maximum((Z ** 2).sum(axis=1)[:, None] - 2 * Z @ C.T + (C ** 2).sum(axis=1)[None], 0)


def kmeans(Z, k, rng):
    best = None
    for _ in range(KMEANS_INITS):
        centers = [Z[rng.integers(len(Z))]]
        for _ in range(1, k):
            d2 = squared_distances(Z, np.array(centers)).min(axis=1)
            total = d2.sum()
            centers.append(Z[rng.choice(len(Z), p=d2 / total) if total > 0 else rng.integers(len(Z))])
        C = np.array(centers)
        labels = None
        for _ in range(KMEANS_STEPS):
            new_labels = squared_distances(Z, C).argmin(axis=1)
            if labels is not None and np.array_equal(new_labels, labels):
                break
            labels = new_labels
            C = np.array([Z[labels == j].mean(axis=0) if np.any(labels == j) else C[j] for j in range(k)])
        inertia = float(((Z - C[labels]) ** 2).sum())
        if best is None or inertia < best[0]:
            best = (inertia, labels)
    return best[1]


def silhouette(Z, labels, rng):
    idx = np.arange(len(Z))
    if len(idx) > SILHOUETTE_SAMPLE:
        idx = np.sort(rng.choice(len(Z), SILHOUETTE_SAMPLE, replace=False))
    X, L = Z[idx], labels[idx]
    groups = np.unique(L)
    if len(groups) < 2:
        return 0.0
    sq = (X ** 2).sum(axis=1)
    D = np.sqrt(np.maximum(sq[:, None] + sq[None] - 2 * X @ X.T, 0))
    scores = []
    for i in range(len(X)):
        same = L == L[i]
        if same.sum() <= 1:
            scores.append(0.0)
            continue
        a = D[i, same].sum() / (same.sum() - 1)
        b = min(D[i, L == g].mean() for g in groups if g != L[i])
        scores.append((b - a) / max(a, b) if max(a, b) > 0 else 0.0)
    return float(np.mean(scores))


# ---------------------------------------------------------------------------
# Data baru untuk prediksi: "jam_belajar=5; kota=Bandung".
# ---------------------------------------------------------------------------

def parse_assignments(text):
    pairs = []
    for part in re.split(r"[;\n]", str(text or "")):
        match = re.match(r"\s*([^=:]+?)\s*[=:]\s*(.*?)\s*$", part)
        if match:
            pairs.append((match.group(1), match.group(2)))
    return pairs


def effect_label(spec, level):
    if level is None:
        return spec["column"]
    return f"{spec['column']} = {level} (dibanding {spec['reference']})"


class CielMLAnalyst(Component):
    display_name = "Ciel ML Analyst"
    description = (
        "Melatih model machine learning sederhana (prediksi atau pengelompokan) "
        "dari file CSV/TSV pengguna dan melaporkan kualitas model yang benar-benar diukur."
    )
    icon = "brain"

    inputs = [
        MessageTextInput(
            name="file_name",
            display_name="File Name",
            info="Nama file CSV/TSV pengguna. Kosongkan jika hanya ada satu file.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="task",
            display_name="Task",
            info=(
                "predict: memprediksi kolom target (angka atau kategori). "
                "cluster: mengelompokkan baris yang mirip tanpa target."
            ),
            tool_mode=True,
        ),
        MessageTextInput(
            name="target",
            display_name="Target",
            info="Untuk predict: nama kolom yang ingin diprediksi.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="features",
            display_name="Features",
            info="Opsional: kolom yang dipakai sebagai fitur, dipisah koma. Kosongkan untuk semua kolom yang cocok.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="clusters",
            display_name="Clusters",
            info="Opsional untuk cluster: jumlah kelompok (2-10). Kosongkan agar dipilih otomatis.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="predict_for",
            display_name="Predict For",
            info=(
                "Opsional untuk predict: data baru yang ingin diprediksi, format "
                "kolom=nilai dipisah titik koma, misalnya jam_belajar=5; kota=Bandung."
            ),
            tool_mode=True,
        ),
        # Diisi oleh app lewat tweaks (base64 dari JSON {nama_file: {"text",
        # "truncated"}}), bukan oleh Agent, agar isi file tidak lewat model.
        MessageTextInput(
            name="attached_tables",
            display_name="Attached Tables",
            info="JSON file tabel pengguna, dikirim app lewat tweaks.",
            advanced=True,
            tool_mode=False,
        ),
    ]

    outputs = [
        Output(
            name="result",
            display_name="Model Result",
            method="train_model",
            types=["str"],
        ),
    ]

    def train_model(self) -> str:
        tables = load_tables(self.attached_tables)

        if tables is None:
            return (
                "Data file dari aplikasi tidak bisa dibaca, jadi model tidak bisa dilatih. "
                "Sampaikan bahwa ada gangguan teknis. Jangan menebak hasil."
            )

        if not tables:
            return (
                "Tidak ada file CSV/TSV pengguna untuk melatih model. "
                "Minta pengguna melampirkan filenya. Jangan menebak hasil."
            )

        name = str(self.file_name or "").strip()
        if not name and len(tables) == 1:
            name = next(iter(tables))
        if name not in tables:
            lowered = {k.lower(): k for k in tables}
            name = lowered.get(name.lower(), name)
        if name not in tables:
            return f"File '{name}' tidak ditemukan. File yang tersedia: {', '.join(tables)}."

        entry = tables[name]
        header, records, delimiter = parse_table(entry.get("text", ""))
        if not header:
            return f"File {name} kosong atau bukan tabel yang bisa dibaca."
        styles = {h: detect_style([r[h] for r in records], delimiter == ";") for h in header}

        raw_task = str(self.task or "").strip().lower()
        task = TASKS.get(raw_task) or ("predict" if str(self.target or "").strip() else None)
        if task is None:
            return (
                f"Task '{raw_task}' tidak dikenal. Gunakan predict (dengan target) atau cluster. "
                f"Kolom yang tersedia di {name}: {', '.join(header)}."
            )

        target = None
        if task == "predict":
            target = find_column(header, str(self.target or ""))
            if target is None:
                return (
                    f"Untuk predict, isi target dengan kolom yang ingin diprediksi. "
                    f"Kolom yang tersedia di {name}: {', '.join(header)}."
                )

        requested = [c.strip() for c in str(self.features or "").split(",") if c.strip()]
        columns = []
        for column in requested:
            found = find_column(header, column)
            if found is None:
                return f"Kolom '{column}' tidak ada di {name}. Kolom yang tersedia: {', '.join(header)}."
            columns.append(found)
        columns = [c for c in (columns or header) if c != target]

        lines = []
        if entry.get("truncated"):
            lines.append(
                "PERINGATAN: file terlalu besar dan dipotong sebelum dibaca. "
                "Model hanya dilatih dari baris yang terbaca; sampaikan ini ke pengguna."
            )
        if len(records) > MAX_ROWS:
            keep = np.sort(np.random.default_rng(SEED).choice(len(records), MAX_ROWS, replace=False))
            lines.append(
                f"Catatan: file punya {len(records)} baris; model memakai sampel acak {MAX_ROWS} baris."
            )
            records = [records[i] for i in keep]

        if task == "cluster":
            return self.cluster(name, records, columns, styles, lines)
        return self.predict(name, records, target, columns, styles, lines)

    def predict(self, name, records, target, columns, styles, notes):
        dropped = sum(1 for r in records if r[target] == "")
        records = [r for r in records if r[target] != ""]
        if len(records) < MIN_ROWS_PREDICT:
            return (
                f"Data terlalu sedikit untuk melatih model: {len(records)} baris berisi {target}, "
                f"minimal {MIN_ROWS_PREDICT}. Jangan menebak hasil model; statistik biasa bisa "
                "dihitung dengan analyze_table."
            )

        kinds, skipped = choose_features(records, columns, styles)
        if not kinds:
            return f"Tidak ada kolom yang bisa dipakai sebagai fitur untuk memprediksi {target}."

        values = [r[target] for r in records]
        numbers = [to_number(v, styles[target]) for v in values]
        regression = all(x is not None for x in numbers) and len(set(values)) >= REGRESSION_MIN_DISTINCT

        classes = None
        if regression:
            y = np.array(numbers, dtype=float)
        else:
            counts = {}
            for v in values:
                counts[v] = counts.get(v, 0) + 1
            classes = sorted(counts, key=lambda c: (-counts[c], c))
            if len(classes) > MAX_CLASSES:
                return (
                    f"Kolom {target} punya {len(classes)} nilai berbeda: terlalu banyak untuk "
                    "diprediksi sebagai kategori, dan bukan angka yang bisa diprediksi."
                )
            index = {c: i for i, c in enumerate(classes)}
            y = np.array([index[v] for v in values], dtype=int)

        predicted, baseline = cross_validate(records, kinds, styles, y, classes)
        specs = fit_design(records, kinds, styles)
        X = transform(specs, records, styles)
        labels = design_labels(specs)

        n = len(records)
        lines = [f"HASIL MODEL — dilatih langsung dari file {name} ({n} baris dipakai)."]
        lines.extend(notes)
        if regression:
            lines.append(f"Jenis: regresi linear, memprediksi angka {target}.")
        else:
            shown = ", ".join(f"{c} ({int((y == i).sum())})" for i, c in enumerate(classes))
            lines.append(f"Jenis: klasifikasi (regresi logistik), memprediksi kategori {target}: {shown}.")
        lines.append(f"Fitur ({len(kinds)}): {', '.join(kinds)}")
        if skipped:
            lines.append(f"Kolom dilewati: {', '.join(skipped)}")
        if dropped:
            lines.append(f"Baris tanpa nilai {target} dilewati: {dropped}")

        warnings = []
        lines.append(f"Kualitas (uji silang {FOLDS} lipatan: setiap baris diprediksi oleh model yang tidak melihatnya saat latihan):")
        if regression:
            mae = float(np.abs(predicted - y).mean())
            rmse = float(np.sqrt(((predicted - y) ** 2).mean()))
            ss_total = float(((y - y.mean()) ** 2).sum())
            r2 = 1 - float(((predicted - y) ** 2).sum()) / ss_total if ss_total else 0.0
            lines.append(f"- R² = {show(r2)} (1 = sempurna, 0 = sama saja dengan menebak rata-rata)")
            lines.append(
                f"- Rata-rata meleset (MAE) = {show(mae)}; menebak rata-rata saja meleset "
                f"{show(float(np.abs(baseline - y).mean()))}"
            )
            lines.append(f"- RMSE = {show(rmse)}")
            weak, perfect = r2 < 0.1, r2 > 0.99
        else:
            accuracy = float((predicted == y).mean())
            majority = float((baseline == y).mean())
            lines.append(f"- Akurasi = {pct(accuracy)} (menebak kelas terbanyak '{classes[0]}' saja: {pct(majority)})")
            per_class = []
            for i, c in enumerate(classes[:MAX_CATEGORIES]):
                chosen = predicted == i
                precision = float((y[chosen] == i).mean()) if chosen.any() else 0.0
                recall = float((predicted[y == i] == i).mean())
                per_class.append(f"{c}: presisi {pct(precision)}, recall {pct(recall)}")
            lines.append(f"- Per kelas: {'; '.join(per_class)}")
            weak, perfect = accuracy <= majority + 0.02, accuracy == 1.0
            mae = None

        if regression:
            model = fit_regression(X, y)
            strength = np.abs(model["w"])
            effects = model["w"] / model["sd"]
        else:
            model = fit_classifier(X, y, len(classes))
            W = model["W"]
            if len(classes) == 2:
                direction = W[:, 1] - W[:, 0]
                strength = np.abs(direction)
            else:
                strength = np.abs(W - W.mean(axis=1, keepdims=True)).max(axis=1)

        order = [j for j in np.argsort(-strength, kind="stable") if strength[j] > 1e-6][:MAX_EFFECTS_SHOWN]
        if order:
            # Live test: the Agent re-ranked features by their "setiap +1"
            # effects, which compares hours with percentage points.
            lines.append(
                "Fitur paling berpengaruh (model akhir dari semua baris; dengan fitur lain tetap). Urutan ini "
                "sudah adil antar kolom (pengaruh terstandar): pertahankan urutannya dan jangan mengurutkan "
                "ulang dari angka 'setiap +1', karena satuan tiap kolom berbeda."
            )
        for j in order:
            spec, level = labels[j]
            label = effect_label(spec, level)
            if regression and level is None:
                lines.append(
                    f"- {label}: setiap +1, {target} {signed(effects[j])}; naik 1 standar deviasi "
                    f"({show(model['sd'][j])}), {target} {signed(model['w'][j])}"
                )
            elif regression:
                lines.append(f"- {label}: {target} {signed(effects[j])}")
            elif len(classes) == 2:
                trend = "naik" if direction[j] > 0 else "turun"
                when = "makin tinggi nilainya, " if level is None else ""
                lines.append(f"- {label}: {when}peluang '{classes[1]}' {trend}")
            else:
                when = "makin tinggi nilainya, " if level is None else ""
                lines.append(f"- {label}: {when}paling condong ke '{classes[int(W[j].argmax())]}'")

        if str(self.predict_for or "").strip():
            lines.extend(self.predict_new(specs, styles, model, classes, target, mae))

        if weak:
            warnings.append(
                "Model lemah: hampir tidak lebih baik dari tebakan sederhana. Sampaikan ini dengan jelas "
                "dan jangan sarankan memakai prediksinya untuk keputusan."
            )
        if perfect:
            top = effect_label(*labels[order[0]]) if order else "salah satu fitur"
            warnings.append(
                f"Hasil hampir sempurna: cek apakah ada kolom yang sebenarnya bocoran atau turunan dari "
                f"{target} (misalnya {top}). Jika ya, latih ulang tanpa kolom itu."
            )
        if n < 50:
            warnings.append(f"Data sedikit ({n} baris): angka kualitas bisa berubah banyak jika datanya bertambah.")
        warnings.append("Ini hubungan statistik dari data, bukan bukti sebab-akibat.")
        lines.append("Catatan untuk jawaban:")
        lines.extend(f"- {w}" for w in warnings)
        return "\n".join(lines)

    def predict_new(self, specs, styles, model, classes, target, mae):
        by_column = {spec["column"]: spec for spec in specs}
        record, ignored, invalid, defaults, unseen = {}, [], [], [], []
        for key, value in parse_assignments(self.predict_for):
            column = find_column(list(by_column), key)
            if column is None:
                ignored.append(key)
            elif by_column[column]["kind"] == "number" and to_number(value, styles[column]) is None:
                invalid.append(f"{column}={value}")
            else:
                record[column] = value
        if invalid:
            return [f"Prediksi tidak dibuat: nilai bukan angka untuk {', '.join(invalid)}."]
        given = "; ".join(f"{k}={v}" for k, v in record.items() if v != "")
        for column, spec in by_column.items():
            if record.get(column, "") != "":
                if spec["kind"] == "text" and record[column] != spec["reference"] and record[column] not in spec["levels"]:
                    unseen.append(f"{column}={record[column]}")
                continue
            if spec["kind"] == "number":
                defaults.append(f"{column}={show(spec['fill'])} (median)")
            else:
                record[column] = spec["reference"]
                defaults.append(f"{column}={spec['reference']} (terbanyak)")

        X = transform(specs, [record], styles)
        lines = [f"Prediksi untuk data baru ({given or 'tanpa nilai yang diisi'}):"]
        if classes is None:
            value = float(predict_regression(model, X)[0])
            lines.append(f"- Perkiraan {target} = {show(value)} (pada uji silang, rata-rata meleset sekitar {show(mae)})")
        else:
            proba = predict_proba(model, X)[0]
            ranked = np.argsort(-proba, kind="stable")[:3]
            lines.append(f"- Perkiraan {target}: '{classes[ranked[0]]}' (peluang menurut model {pct(proba[ranked[0]])})")
            others = ", ".join(f"'{classes[i]}' {pct(proba[i])}" for i in ranked[1:])
            if others:
                lines.append(f"- Kemungkinan lain: {others}")
        if defaults:
            lines.append(f"- Tidak diisi, memakai nilai umum dari data: {', '.join(defaults)}")
        if unseen:
            lines.append(f"- Nilai yang tidak pernah muncul di data (model tidak tahu efeknya): {', '.join(unseen)}")
        if ignored:
            lines.append(f"- Diabaikan karena bukan fitur model: {', '.join(ignored)}")
        return lines

    def cluster(self, name, records, columns, styles, notes):
        if len(records) < MIN_ROWS_CLUSTER:
            return (
                f"Data terlalu sedikit untuk dikelompokkan: {len(records)} baris, minimal {MIN_ROWS_CLUSTER}. "
                "Jangan menebak hasil."
            )
        kinds, skipped = choose_features(records, columns, styles)
        if not kinds:
            return f"Tidak ada kolom di {name} yang bisa dipakai untuk mengelompokkan."

        specs = fit_design(records, kinds, styles)
        X = transform(specs, records, styles)
        mu, sd = scale(X)
        # Kolom kategori tidak distandarkan: kategori langka akan membesar dan
        # menjadi kelompok sendiri. Dengan 0/1 dibagi akar 2, dua kategori
        # berbeda berjarak 1, setara dengan selisih 1 standar deviasi angka.
        for j, (_, level) in enumerate(design_labels(specs)):
            if level is not None:
                mu[j], sd[j] = 0.0, np.sqrt(2)
        Z = (X - mu) / sd
        rng = np.random.default_rng(SEED)

        raw_k = str(self.clusters or "").strip()
        if raw_k:
            if not raw_k.isdigit() or not 2 <= int(raw_k) <= min(10, len(records) - 1):
                return f"Jumlah kelompok harus angka 2 sampai {min(10, len(records) - 1)}."
            k = int(raw_k)
            labels = kmeans(Z, k, rng)
            score = silhouette(Z, labels, rng)
            how = "diminta"
        else:
            best = None
            for k in AUTO_K:
                if k >= len(records):
                    break
                labels = kmeans(Z, k, rng)
                score = silhouette(Z, labels, rng)
                if best is None or score > best[0]:
                    best = (score, k, labels)
            score, k, labels = best
            how = f"dipilih otomatis dari {AUTO_K.start}–{AUTO_K.stop - 1} dengan skor silhouette tertinggi"

        quality = "jelas" if score > 0.5 else "sedang" if score >= 0.25 else "lemah"
        n = len(records)
        lines = [f"HASIL MODEL — pengelompokan k-means dari file {name} ({n} baris)."]
        lines.extend(notes)
        lines.append(f"Fitur ({len(kinds)}): {', '.join(kinds)}")
        if skipped:
            lines.append(f"Kolom dilewati: {', '.join(skipped)}")
        lines.append(f"Jumlah kelompok: {k} ({how}).")
        lines.append(f"Kejelasan pemisahan (silhouette) = {show(score)}: {quality} (>0,5 jelas; 0,25–0,5 sedang; <0,25 lemah)")

        position = {spec["column"]: j for j, (spec, _) in enumerate(design_labels(specs))}
        groups = sorted(range(k), key=lambda g: -(labels == g).sum())
        for number, g in enumerate(groups, 1):
            members = labels == g
            size = int(members.sum())
            lines.append(f"Kelompok {number} — {size} baris ({pct(size / n)}):")
            traits = []
            for spec in specs:
                column = spec["column"]
                if spec["kind"] == "number":
                    j = position[column]
                    inside, overall = X[members, j].mean(), X[:, j].mean()
                    traits.append((abs(inside - overall) / sd[j], f"{column}: rata-rata {show(inside)} (keseluruhan {show(overall)})"))
                else:
                    values = [records[i][column] or EMPTY for i in np.where(members)[0]]
                    top = max(sorted(set(values)), key=values.count)
                    share = values.count(top) / len(values)
                    overall = sum(1 for r in records if (r[column] or EMPTY) == top) / n
                    traits.append((share - overall, f"{column}: terbanyak {top} ({pct(share)}; keseluruhan {pct(overall)})"))
            traits.sort(key=lambda t: -t[0])
            lines.extend(f"- {text}" for _, text in traits[:4])

        lines.append("Catatan untuk jawaban:")
        lines.append(
            "- Kelompok ditemukan dari pola data, bukan label yang benar. Nama kelompok boleh diberikan "
            "berdasarkan ciri di atas, sebutkan bahwa itu penamaan Ciel."
        )
        if quality == "lemah":
            lines.append("- Pemisahan lemah: data mungkin tidak benar-benar terbagi menjadi kelompok yang jelas.")
        return "\n".join(lines)
