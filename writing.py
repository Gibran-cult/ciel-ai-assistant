"""Fitur menulis Ciel Pro yang memakai peta sumber Riset Skripsi.

Kerangka Bab 1-3: app mengirim peta sumber ke flow "Ciel Penulis" (mode
[KERANGKA], tanpa pencarian web). Model hanya boleh memakai nomor [n] dari
Daftar Pustaka peta sumber; modul ini membuang nomor lain dan menambahkan
Daftar Pustaka itu ke kerangka, sehingga kerangka (dan DOCX-nya) berdiri
sendiri tanpa sumber yang tidak pernah dicari.

Semua fungsi di sini murni (tanpa Streamlit/Langflow) supaya mudah dites.
"""

import re

APPROACHES = ("Kuantitatif", "Kualitatif", "Campuran", "Belum tahu")
MAX_OBJECT_CHARS = 120

# Catatan penutup DOCX kerangka (riset_export.report_docx).
KERANGKA_FOOTNOTE = (
    "Disusun dengan Ciel Pro dari peta sumber Riset Skripsi. Kerangka ini berisi "
    "poin dan pertanyaan pemandu, bukan teks skripsi: baca sumber aslinya dan "
    "tulis setiap bab dengan kata-katamu sendiri."
)

REFERENCES_HEADING = re.compile(r"^##\s+Daftar Pustaka\s*$", re.IGNORECASE | re.MULTILINE)
REFERENCE_ENTRY = re.compile(r"^\[(\d+)\]\s", re.MULTILINE)
MARKER = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
TITLE = re.compile(r"^#\s+Peta Sumber:\s*(.+)$", re.MULTILINE)


def reference_section(source_map):
    """Bagian "## Daftar Pustaka" dari peta sumber (sampai akhir teks), atau "" jika tidak ada."""
    match = REFERENCES_HEADING.search(str(source_map))
    return str(source_map)[match.start():].strip() if match else ""


def allowed_numbers(source_map):
    """Nomor [n] yang ada di Daftar Pustaka peta sumber."""
    return set(REFERENCE_ENTRY.findall(reference_section(source_map)))


def map_topic(source_map, fallback=""):
    match = TITLE.search(str(source_map))
    return match.group(1).strip() if match else fallback


def kerangka_payload(source_map, topic, approach, research_object=""):
    """Teks permintaan mode [KERANGKA] untuk flow Ciel Penulis."""

    lines = [
        "[KERANGKA]",
        f"Topik skripsi: {topic}",
        f"Pendekatan penelitian: {approach}",
    ]

    if research_object:
        lines.append(f"Objek atau lokasi penelitian: {research_object}")

    lines += ["", "PETA SUMBER:", str(source_map).strip()]
    return "\n".join(lines)


def keep_known_citations(text, allowed):
    """Buang nomor [n] yang tidak ada di `allowed`; "[2, 9]" menjadi "[2]" jika 9 tidak dikenal."""

    def replace(match):
        kept = [n.strip() for n in match.group(1).split(",") if n.strip() in allowed]
        return f"[{', '.join(kept)}]" if kept else ""

    cleaned = []
    for line in str(text).splitlines():
        new = MARKER.sub(replace, line)
        if new != line:
            new = re.sub(r"(?<=\S)[ \t]{2,}", " ", new)
            new = re.sub(r"[ \t]+([.,;:])", r"\1", new).rstrip()
        cleaned.append(new)
    return "\n".join(cleaned)


def finish_kerangka(answer, source_map):
    """
    Kerangka dari model -> kerangka yang dikirim ke pengguna: tanpa Daftar
    Pustaka buatan model, tanpa nomor yang tidak ada di peta sumber, lalu
    Daftar Pustaka peta sumber ditempel di akhir.
    """

    text = str(answer)
    # Model diminta tidak menulis Daftar Pustaka; jika tetap menulis, dibuang.
    own = REFERENCES_HEADING.search(text)
    if own:
        text = text[:own.start()]

    text = keep_known_citations(text, allowed_numbers(source_map)).rstrip()
    references = reference_section(source_map)

    if references:
        references = re.sub(r"^##\s+Daftar Pustaka", "## Daftar Pustaka (dari peta sumber)", references, count=1)
        text += "\n\n" + references

    return text
