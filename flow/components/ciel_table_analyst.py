from langflow.custom import Component
from langflow.io import MessageTextInput, Output

import base64
import binascii
import csv
import io
import json
import re
import statistics


OPERATIONS = (
    "describe", "count", "sum", "mean", "median", "min", "max", "unique", "top_values",
)
MAX_GROUPS = 20
NUMERIC = re.compile(r"^[+-]?[\d.,]*\d[\d.,]*$")

# "comma_decimal": 1.234,5 (Indonesia/Eropa). "dot_decimal": 1,234.5 (Inggris).
STYLE_LABEL = {
    "comma_decimal": "titik = pemisah ribuan, koma = desimal",
    "dot_decimal": "koma = pemisah ribuan, titik = desimal",
}


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


def numeric_values(records, column, style):
    values = [to_number(r[column], style) for r in records]
    return [v for v in values if v is not None], sum(1 for v in values if v is None)


def aggregate(operation, records, column, style):
    if operation == "count":
        return float(len(records)) if column is None else float(sum(1 for r in records if r[column] != ""))
    numbers, _ = numeric_values(records, column, style)
    if not numbers:
        return None
    return {
        "sum": lambda: sum(numbers),
        "mean": lambda: statistics.fmean(numbers),
        "median": lambda: statistics.median(numbers),
        "min": lambda: min(numbers),
        "max": lambda: max(numbers),
    }[operation]()


class CielTableAnalyst(Component):
    display_name = "Ciel Table Analyst"
    description = (
        "Menghitung statistik dari file CSV/TSV yang dilampirkan pengguna "
        "secara langsung dan deterministik, tanpa menjalankan kode."
    )
    icon = "table"

    inputs = [
        MessageTextInput(
            name="file_name",
            display_name="File Name",
            info="Nama file CSV/TSV pengguna. Kosongkan jika hanya ada satu file.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="operation",
            display_name="Operation",
            info=(
                "Salah satu: describe, count, sum, mean, median, min, max, "
                "unique, top_values."
            ),
            tool_mode=True,
        ),
        MessageTextInput(
            name="column",
            display_name="Column",
            info="Nama kolom yang dihitung. Kosongkan untuk describe atau count baris.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="group_by",
            display_name="Group By",
            info="Opsional: nama kolom untuk mengelompokkan hasil.",
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
            display_name="Table Result",
            method="analyze_table",
            types=["str"],
        ),
    ]

    def analyze_table(self) -> str:
        tables = load_tables(self.attached_tables)

        if tables is None:
            return (
                "Data file dari aplikasi tidak bisa dibaca, jadi angka tidak bisa dihitung. "
                "Sampaikan bahwa ada gangguan teknis. Jangan menebak angka."
            )

        if not tables:
            return (
                "Tidak ada file CSV/TSV pengguna yang tersedia untuk dihitung. "
                "Minta pengguna melampirkan filenya. Jangan menebak angka."
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

        operation = str(self.operation or "describe").strip().lower() or "describe"
        if operation not in OPERATIONS:
            return f"Operasi '{operation}' tidak dikenal. Gunakan salah satu: {', '.join(OPERATIONS)}."

        column = find_column(header, str(self.column or ""))
        if str(self.column or "").strip() and column is None:
            return f"Kolom '{self.column}' tidak ada di {name}. Kolom yang tersedia: {', '.join(header)}."
        group_by = find_column(header, str(self.group_by or ""))
        if str(self.group_by or "").strip() and group_by is None:
            return f"Kolom '{self.group_by}' tidak ada di {name}. Kolom yang tersedia: {', '.join(header)}."

        lines = [f"HASIL TERVERIFIKASI — dihitung langsung dari file {name} ({len(records)} baris data)."]
        if entry.get("truncated"):
            lines.append(
                "PERINGATAN: file terlalu besar dan dipotong sebelum dihitung. "
                "Hasil hanya mencakup baris yang terbaca; sampaikan ini ke pengguna."
            )

        if operation == "describe":
            lines.append(f"Kolom ({len(header)}): {', '.join(header)}")
            for h in header:
                numbers, non_numeric = numeric_values(records, h, styles[h])
                empty = sum(1 for r in records if r[h] == "")
                if numbers and non_numeric - empty == 0:
                    lines.append(
                        f"- {h} (angka): jumlah={fmt(sum(numbers))}, rata-rata={fmt(statistics.fmean(numbers))}, "
                        f"min={fmt(min(numbers))}, maks={fmt(max(numbers))}, kosong={empty}"
                    )
                else:
                    distinct = len({r[h] for r in records if r[h] != ""})
                    lines.append(f"- {h} (teks): {distinct} nilai unik, kosong={empty}")
            return "\n".join(lines)

        if operation in ("unique", "top_values"):
            if column is None:
                return "Operasi ini membutuhkan nama kolom."
            counts = {}
            for r in records:
                if r[column] != "":
                    counts[r[column]] = counts.get(r[column], 0) + 1
            ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
            lines.append(f"{column}: {len(counts)} nilai unik.")
            lines.extend(f"- {value}: {count} baris" for value, count in ranked[:MAX_GROUPS])
            if len(ranked) > MAX_GROUPS:
                lines.append(f"(+{len(ranked) - MAX_GROUPS} nilai lain tidak ditampilkan)")
            return "\n".join(lines)

        if operation != "count" and column is None:
            return f"Operasi {operation} membutuhkan nama kolom angka."

        style = styles.get(column, "dot_decimal")
        if operation != "count":
            _, non_numeric = numeric_values(records, column, style)
            empty = sum(1 for r in records if r[column] == "")
            if any(sep in r[column] for r in records for sep in ".,"):
                lines.append(f"Format angka kolom {column} dibaca sebagai: {STYLE_LABEL[style]}.")
            if non_numeric - empty:
                lines.append(f"Catatan: {non_numeric - empty} nilai di {column} bukan angka dan diabaikan.")

        label = f"{operation}({column})" if column else "count(baris)"
        if group_by is None:
            value = aggregate(operation, records, column, style)
            if value is None:
                return f"Kolom {column} tidak berisi angka yang bisa dihitung."
            lines.append(f"{label} = {fmt(value)}")
            return "\n".join(lines)

        groups = {}
        for r in records:
            groups.setdefault(r[group_by] or "(kosong)", []).append(r)
        results = []
        for key, rows in groups.items():
            value = aggregate(operation, rows, column, style)
            if value is not None:
                results.append((key, value))
        results.sort(key=lambda kv: -kv[1])
        lines.append(f"{label} per {group_by} ({len(results)} kelompok):")
        lines.extend(f"- {key}: {fmt(value)}" for key, value in results[:MAX_GROUPS])
        if len(results) > MAX_GROUPS:
            lines.append(f"(+{len(results) - MAX_GROUPS} kelompok lain tidak ditampilkan)")
        return "\n".join(lines)
