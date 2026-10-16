from langflow.custom import Component
from langflow.io import MessageTextInput, Output

import base64
import binascii
import csv
import io
import json
import re
from datetime import datetime
from pathlib import Path


ACTIONS = ("list", "show", "save_file", "add_rows")
NUMERIC = re.compile(r"^[+-]?[\d.,]*\d[\d.,]*$")
MAX_DATASETS = 5
MAX_DATASET_ROWS = 10_000
MAX_DATASET_BYTES = 1_000_000
SHOW_ROWS = 5
LOGIN_REQUIRED = (
    "Dataset pribadi hanya tersedia untuk pengguna yang login. TIDAK ada yang disimpan. "
    "Sampaikan bahwa pengguna perlu masuk dengan Google untuk menyimpan data lintas hari."
)


# ---------------------------------------------------------------------------
# Membaca file: disalin apa adanya dari ciel_table_analyst.py (komponen Langflow
# tidak bisa saling import). tests/test_personal_datasets.py memastikan sama.
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
# Dataset tersimpan: sama persis di Dataset Store, Table Analyst, ML Analyst
# dan Memory Admin.
# ---------------------------------------------------------------------------

def owner_dir(owner):
    """
    Folder of the signed-in user's saved datasets, or None. The owner is the
    app's hash of the account (sent through tweaks, never by the Agent); the
    pattern also keeps it from being used as a path.
    """
    owner = str(owner or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", owner):
        return None
    return Path.home() / ".ciel_ai" / "user_datasets" / owner


def saved_tables(owner):
    """The owner's saved datasets as {name: {"text", "truncated": False}}."""
    folder = owner_dir(owner)
    if folder is None or not folder.is_dir():
        return {}
    return {
        path.stem: {"text": path.read_text(encoding="utf-8"), "truncated": False}
        for path in sorted(folder.glob("*.csv"))
    }


def dataset_name(raw):
    """Nama aman untuk file: huruf kecil, angka, _ dan -, paling banyak 40 karakter."""
    name = re.sub(r"\.(csv|tsv)$", "", str(raw or "").strip().lower())
    name = re.sub(r"[^a-z0-9_-]+", "_", name).strip("_-")
    return name if re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,39}", name) else None


def column_style(values, delimiter):
    """Format angka satu kolom dataset; kolom kosong mengikuti pemisah file."""
    if any(NUMERIC.match(clean(v)) for v in values if v != ""):
        return detect_style(values, delimiter == ";")
    return "comma_decimal" if delimiter == ";" else "dot_decimal"


def restyle(value, source, target):
    """Tulis ulang angka ke format dataset, supaya satu kolom tidak bercampur format."""
    if source == target:
        return value
    number = to_number(value, source)
    if number is None:
        return value
    text = str(int(number)) if number.is_integer() else repr(number)
    return text.replace(".", ",") if target == "comma_decimal" else text


def numeric_columns(header, records):
    """Kolom yang semua nilainya angka (atau kosong); hanya kolom ini yang diformat ulang."""
    return {
        h for h in header
        if all(v == "" or NUMERIC.match(clean(v)) for v in (r[h] for r in records))
    }


def render(header, records, delimiter):
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\n")
    writer.writerow(header)
    writer.writerows([r.get(h, "") for h in header] for r in records)
    return buffer.getvalue()


def parse_rows(text):
    """Baris dari chat: satu baris data per baris teks, format kolom=nilai; kolom=nilai."""
    rows = []
    for line in str(text or "").splitlines():
        pairs = []
        for part in line.split(";"):
            match = re.match(r"\s*([^=:]+?)\s*[=:]\s*(.*?)\s*$", part)
            if match:
                pairs.append((match.group(1), match.group(2)))
        if pairs:
            rows.append(pairs)
    return rows


class CielDatasetStore(Component):
    display_name = "Ciel Dataset Store"
    description = (
        "Menyimpan dan menambah dataset pribadi pengguna yang login (misalnya log belajar), "
        "agar statistik dan model ML bisa dihitung dari seluruh riwayat datanya."
    )
    icon = "folder"

    inputs = [
        MessageTextInput(
            name="action",
            display_name="Action",
            info=(
                "list: daftar dataset. show: isi singkat satu dataset. save_file: simpan file "
                "CSV/TSV lampiran ke dataset (dibuat baru atau ditambahkan). add_rows: tambah "
                "baris dari chat."
            ),
            tool_mode=True,
        ),
        MessageTextInput(
            name="dataset",
            display_name="Dataset",
            info="Nama dataset, misalnya belajar atau pengeluaran.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="file_name",
            display_name="File Name",
            info="Untuk save_file: nama file lampiran. Kosongkan jika hanya ada satu file.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="rows",
            display_name="Rows",
            info=(
                "Untuk add_rows: satu baris data per baris teks, format kolom=nilai dipisah "
                "titik koma, misalnya tanggal=16-10-2026; jam_belajar=3; nilai_kuis=80."
            ),
            tool_mode=True,
        ),
        # Diisi oleh app lewat tweaks, bukan oleh Agent. Jangan dinamai
        # `user_id`: Component Langflow sudah punya atribut bawaan itu.
        MessageTextInput(
            name="memory_owner",
            display_name="Memory Owner",
            info="ID pemilik dataset, dikirim app lewat tweaks. Kosong = anonim, tidak ada yang disimpan.",
            advanced=True,
            tool_mode=False,
        ),
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
            display_name="Dataset Result",
            method="manage_dataset",
            types=["str"],
        ),
    ]

    def manage_dataset(self) -> str:
        folder = owner_dir(self.memory_owner)
        if folder is None:
            return LOGIN_REQUIRED

        action = str(self.action or "").strip().lower()
        if action not in ACTIONS:
            return f"Action '{action}' tidak dikenal. Gunakan salah satu: {', '.join(ACTIONS)}."

        saved = saved_tables(self.memory_owner)
        if action == "list":
            return self.list_datasets(folder, saved)

        name = dataset_name(self.dataset)
        if name is None:
            return (
                f"Nama dataset '{self.dataset}' tidak bisa dipakai. Gunakan huruf, angka, _ atau -, "
                "paling banyak 40 karakter, misalnya belajar atau pengeluaran_bulanan."
            )

        if action == "show":
            if name not in saved:
                return f"Dataset '{name}' belum ada. Dataset yang tersimpan: {', '.join(saved) or 'belum ada'}."
            header, records, _ = parse_table(saved[name]["text"])
            lines = [f"Dataset '{name}': {len(records)} baris. Kolom: {', '.join(header)}"]
            if records:
                lines.append(f"{min(SHOW_ROWS, len(records))} baris terakhir:")
                lines.extend(
                    "- " + "; ".join(f"{h}={r[h]}" for h in header) for r in records[-SHOW_ROWS:]
                )
            lines.append("Untuk angka atau model dari dataset ini, panggil analyze_table atau train_model dengan file_name=" + name + ".")
            return "\n".join(lines)

        if name not in saved and len(saved) >= MAX_DATASETS:
            return (
                f"Sudah ada {MAX_DATASETS} dataset (batas maksimal): {', '.join(saved)}. "
                "Tambahkan ke dataset yang ada, atau hapus salah satu lewat menu Data saya. Tidak ada yang disimpan."
            )

        if name in saved:
            header, records, delimiter = parse_table(saved[name]["text"])
        else:
            header, records, delimiter = [], [], ";"

        if action == "save_file":
            incoming = self.rows_from_file(header)
        else:
            incoming = self.rows_from_chat(header)
        if isinstance(incoming, str):
            return incoming
        new_header, new_records, source_styles, label = incoming

        if not header:
            header = new_header
            if action == "save_file":
                delimiter = source_styles.pop("__delimiter__")
        source_styles.pop("__delimiter__", None)

        numeric = numeric_columns(header, records + new_records)
        for h in header:
            if h not in numeric:
                continue
            target = column_style([r[h] for r in records], delimiter) if records else (
                source_styles.get(h) or column_style([], delimiter)
            )
            for r in new_records:
                r[h] = restyle(r.get(h, ""), source_styles.get(h, target), target)

        if action == "save_file" and records and len(new_records) <= len(records):
            tail = [[r[h] for h in header] for r in records[-len(new_records):]]
            if tail == [[r.get(h, "") for h in header] for r in new_records]:
                return (
                    f"File ini sepertinya sudah tersimpan: {len(new_records)} baris terakhir dataset '{name}' "
                    "sama persis. Tidak disimpan lagi."
                )

        total = records + new_records
        if len(total) > MAX_DATASET_ROWS:
            return (
                f"Dataset '{name}' akan menjadi {len(total)} baris, melebihi batas {MAX_DATASET_ROWS}. "
                "Tidak ada yang disimpan."
            )
        text = render(header, total, delimiter)
        if len(text.encode("utf-8")) > MAX_DATASET_BYTES:
            return f"Dataset '{name}' akan melebihi batas 1 MB. Tidak ada yang disimpan."

        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{name}.csv"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(path)

        verb = "dibuat" if name not in saved else "diperbarui"
        lines = [
            f"TERSIMPAN — dataset '{name}' {verb}: {len(new_records)} baris baru dari {label}, "
            f"sekarang {len(total)} baris."
        ]
        lines.append(f"Kolom: {', '.join(header)}")
        if action == "add_rows":
            lines.extend("- " + "; ".join(f"{h}={r.get(h, '')}" for h in header) for r in new_records[:SHOW_ROWS])
        lines.append(
            f"Dataset ini hanya bisa dibaca akun pengguna dan bisa dihapus lewat menu Data saya. "
            f"Untuk angka atau model dari seluruh riwayatnya, panggil analyze_table atau train_model dengan file_name={name}."
        )
        return "\n".join(lines)

    def list_datasets(self, folder, saved):
        if not saved:
            return (
                "Belum ada dataset tersimpan. Pengguna bisa meminta Ciel menyimpan file CSV/TSV "
                "atau mencatat data dari chat."
            )
        lines = [f"Dataset tersimpan ({len(saved)} dari maksimal {MAX_DATASETS}):"]
        for name, entry in saved.items():
            header, records, _ = parse_table(entry["text"])
            changed = datetime.fromtimestamp((folder / f"{name}.csv").stat().st_mtime).strftime("%d-%m-%Y %H:%M")
            lines.append(f"- {name}: {len(records)} baris; kolom: {', '.join(header)}; terakhir diubah {changed}")
        lines.append("Gunakan nama dataset sebagai file_name di analyze_table atau train_model.")
        return "\n".join(lines)

    def rows_from_file(self, header):
        tables = load_tables(self.attached_tables)
        if tables is None:
            return "Data file dari aplikasi tidak bisa dibaca. Tidak ada yang disimpan."
        if not tables:
            return "Tidak ada file CSV/TSV lampiran untuk disimpan. Minta pengguna melampirkan filenya."
        requested = str(self.file_name or "").strip()
        if not requested and len(tables) == 1:
            requested = next(iter(tables))
        lowered = {k.lower(): k for k in tables}
        file_name = requested if requested in tables else lowered.get(requested.lower())
        if file_name is None:
            return f"File '{requested}' tidak ditemukan. File lampiran: {', '.join(tables)}."
        entry = tables[file_name]
        if entry.get("truncated"):
            return f"File {file_name} terlalu besar dan terpotong, jadi tidak disimpan agar dataset tidak setengah jadi."

        new_header, new_records, new_delimiter = parse_table(entry.get("text", ""))
        if not new_header or not new_records:
            return f"File {file_name} kosong atau bukan tabel. Tidak ada yang disimpan."
        if header:
            existing = {h.lower(): h for h in header}
            incoming = {h.lower(): h for h in new_header}
            missing = [existing[k] for k in existing if k not in incoming]
            extra = [incoming[k] for k in incoming if k not in existing]
            if missing or extra:
                return (
                    f"Kolom {file_name} tidak sama dengan dataset. Hilang: {', '.join(missing) or '-'}; "
                    f"baru: {', '.join(extra) or '-'}. Tidak ada yang disimpan."
                )
            new_records = [{existing[k.lower()]: v for k, v in r.items()} for r in new_records]
            new_header = header
        styles = {h: detect_style([r[h] for r in new_records], new_delimiter == ";") for h in new_header}
        styles["__delimiter__"] = new_delimiter
        return new_header, new_records, styles, f"file {file_name}"

    def rows_from_chat(self, header):
        rows = parse_rows(self.rows)
        if not rows:
            return "Tidak ada baris yang bisa dibaca. Format: kolom=nilai; kolom=nilai (satu baris data per baris teks)."
        new_header = list(header)
        if not header:
            for pairs in rows:
                for key, _ in pairs:
                    column = re.sub(r"\s+", "_", key.strip())
                    if column and find_column(new_header, column) is None:
                        new_header.append(column)
        records, unknown = [], []
        for pairs in rows:
            record = {h: "" for h in new_header}
            for key, value in pairs:
                column = find_column(new_header, re.sub(r"\s+", "_", key.strip())) or find_column(new_header, key)
                if column is None:
                    unknown.append(key)
                else:
                    record[column] = value
            records.append(record)
        if unknown:
            return (
                f"Kolom {', '.join(sorted(set(unknown)))} tidak ada di dataset. Kolom yang tersedia: "
                f"{', '.join(new_header)}. Tidak ada yang disimpan."
            )
        # Angka yang diketik di chat dibaca sebagai format Indonesia jika ambigu.
        styles = {h: detect_style([r[h] for r in records], True) for h in new_header}
        return new_header, records, styles, "chat"
