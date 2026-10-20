"""Cek kutipan & kemiripan (Ciel Pro): draf mahasiswa dibandingkan dengan peta sumber.

Tanpa model bahasa: semua pemeriksaan di sini deterministik, jadi hasilnya
tidak bisa dikarang dan bisa diulang.

- Kutipan: setiap sitasi di draf, baik nomor "[n]" maupun gaya APA
  "(Nama, 2024)" / "Nama dkk. (2024)", dicocokkan dengan Daftar Pustaka peta
  sumber (nama penulis dan tahun).
- Kemiripan: setiap kalimat draf dibandingkan, per rangkaian 5 kata, dengan
  cuplikan sumber yang dibaca Ciel saat riset (disimpan bersama peta sumber)
  dan dengan teks ringkasan peta sumber itu sendiri.

Ini bukan pengganti Turnitin: pembandingnya hanya sumber di peta sumber, dan
terjemahan dari sumber berbahasa lain tidak terdeteksi. Laporannya mengatakan
itu juga.

Cuplikan sumber dikirim flow Riset Skripsi (Ciel Reference Builder, v1.1.0)
di akhir jawabannya sebagai satu baris penanda; `split_excerpts` memisahkannya
sebelum peta sumber ditampilkan atau disimpan.
"""

import base64
import binascii
import io
import json
import re
import unicodedata

from writing import reference_section

MAX_DRAFT_CHARS = 60_000
MIN_DRAFT_WORDS = 30

# Sama dengan ciel_reference_builder.py (komponen Langflow tidak bisa mengimpor modul app).
EXCERPTS_MARKER = re.compile(r"\n*<!-- ciel-excerpts:v1 ([A-Za-z0-9_=-]+) -->\s*$")

SHINGLE = 5
MIN_SENTENCE_WORDS = 10
SIMILAR = 0.4
MAX_LISTED = 20

CHECK_FOOTNOTE = (
    "Cek ini hanya membandingkan drafmu dengan peta sumber dan cuplikan sumber yang "
    "dibaca Ciel saat riset, bukan dengan seluruh internet seperti Turnitin, dan "
    "terjemahan dari sumber berbahasa lain tidak terdeteksi. Pakai sebagai bahan "
    "revisi, bukan sebagai jaminan lolos cek plagiarisme kampus."
)

YEAR = r"(?:19|20)\d{2}[a-z]?|t\.t\.|n\.d\."
REFERENCE_LINE = re.compile(r"^\[(\d+)\]\s+(.+)$", re.MULTILINE)
REFERENCE_YEAR = re.compile(r"\((\d{4}|t\.t\.)\)")
REFERENCE_TITLE = re.compile(r"\*([^*]+)\*")
NUMBERED = re.compile(r"\[(\d+(?:\s*[,;–-]\s*\d+)*)\]")
PARENTHETICAL = re.compile(r"\(([^()]*?(?:" + YEAR + r")[^()]*)\)")
CITED_PART = re.compile(r"^(?P<names>.*?\D),?\s+(?P<year>" + YEAR + r")(?:\s*[,:].*)?$")
NARRATIVE = re.compile(
    r"(?P<names>[A-Z][\w'’-]+(?:\s*(?:,|dan|&|and)\s*[A-Z][\w'’-]+)*(?:\s+(?:dkk|et al)\.?)?)"
    r"\s+\((?P<year>" + YEAR + r")\)"
)
OWN_REFERENCES = re.compile(
    r"^[ \t]*(?:#+\s*)?(?:daftar pustaka|daftar referensi|referensi|references|bibliografi)[ \t]*:?[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[\"“A-Z0-9])|\n+")
NAME_STOPWORDS = {"dkk", "et", "al", "dan", "and", "lihat", "dalam", "see", "in", "cf"}


# ------------------------------------------------------------
# Cuplikan sumber dari flow riset
# ------------------------------------------------------------

def split_excerpts(answer):
    """(peta sumber tanpa penanda, {nomor: [cuplikan]}); penanda rusak dibuang tanpa cuplikan."""

    text = str(answer)
    match = EXCERPTS_MARKER.search(text)
    if not match:
        return text, {}

    excerpts = {}
    try:
        items = json.loads(base64.urlsafe_b64decode(match.group(1)).decode("utf-8"))
        for item in items if isinstance(items, list) else []:
            number = str(item.get("n"))
            texts = [str(h) for h in item.get("highlights") or [] if str(h).strip()]
            if number.isdigit() and texts:
                excerpts[number] = texts
    except (binascii.Error, ValueError, AttributeError, UnicodeDecodeError):
        excerpts = {}

    return text[:match.start()].rstrip(), excerpts


# ------------------------------------------------------------
# Draf
# ------------------------------------------------------------

def draft_from_file(name, raw):
    """Teks draf dari file .docx atau .txt; ValueError jika tidak bisa dibaca."""

    if str(name).lower().endswith(".docx"):
        from docx import Document

        try:
            document = Document(io.BytesIO(raw))
        except Exception as error:  # python-docx melempar banyak jenis pada file rusak
            raise ValueError("docx") from error
        return "\n".join(paragraph.text for paragraph in document.paragraphs)

    if b"\x00" in raw[:4096]:
        raise ValueError("binary")
    return raw.decode("utf-8", errors="replace")


def clean_draft(text):
    """Draf yang diperiksa: tanpa spasi berlebih, dipotong di MAX_DRAFT_CHARS."""
    lines = [" ".join(line.split()) for line in str(text or "").splitlines()]
    return "\n".join(lines).strip()[:MAX_DRAFT_CHARS]


def word_count(text):
    return len(re.findall(r"\w+", str(text)))


def without_own_references(draft):
    """Draf sampai sebelum Daftar Pustaka-nya sendiri (daftar itu memang mirip peta sumber)."""
    match = OWN_REFERENCES.search(draft)
    return draft[:match.start()] if match else draft


# ------------------------------------------------------------
# Kutipan
# ------------------------------------------------------------

def fold(text):
    """Huruf kecil tanpa diakritik."""
    text = unicodedata.normalize("NFKD", str(text))
    return "".join(ch for ch in text if not unicodedata.combining(ch)).lower()


def name_tokens(text):
    return {t for t in re.findall(r"\w+", fold(text)) if len(t) >= 3 and t not in NAME_STOPWORDS and not t.isdigit()}


def parse_references(source_map):
    """{nomor: {"authors", "year", "title", "label"}} dari Daftar Pustaka peta sumber."""

    references = {}
    for number, entry in REFERENCE_LINE.findall(reference_section(source_map)):
        year = REFERENCE_YEAR.search(entry)
        title = REFERENCE_TITLE.search(entry)
        before_year = entry[:year.start()].strip().rstrip(".") if year else ""
        authors = "" if before_year.startswith("*") else before_year
        title_text = title.group(1).strip() if title else ""

        first = authors.split(",")[0].strip() if authors else title_text
        label = first.split()[-1] if authors and first else (title_text[:40] or f"Sumber {number}")
        if authors and "," in authors:
            label += " dkk."

        references[number] = {
            "authors": authors,
            "year": year.group(1) if year else "t.t.",
            "title": title_text,
            "label": f"{label}, {year.group(1) if year else 't.t.'}",
        }
    return references


def expand_numbers(group):
    """"1, 3–5" -> ["1", "3", "4", "5"] (rentang dibatasi 20 nomor)."""
    numbers = []
    for part in re.split(r"[,;]", group):
        bounds = [b.strip() for b in re.split(r"[–-]", part) if b.strip()]
        if len(bounds) == 2 and bounds[0].isdigit() and bounds[1].isdigit():
            low, high = int(bounds[0]), int(bounds[1])
            numbers += [str(n) for n in range(low, min(high, low + 19) + 1)] if low <= high else bounds
        else:
            numbers += bounds
    return numbers


def find_citations(draft):
    """[(teks sitasi, "number"|"author", nomor atau (nama, tahun))] dalam urutan kemunculan."""

    found = []

    for match in NUMBERED.finditer(draft):
        for number in expand_numbers(match.group(1)):
            found.append((match.start(), f"[{number}]", "number", number))

    narrative_spans = []
    for match in NARRATIVE.finditer(draft):
        narrative_spans.append(match.span())
        found.append((match.start(), match.group(0), "author", (match.group("names"), match.group("year"))))

    for match in PARENTHETICAL.finditer(draft):
        if any(start <= match.start() < end for start, end in narrative_spans):
            continue
        for part in match.group(1).split(";"):
            cited = CITED_PART.match(part.strip())
            # Nama diawali huruf kapital: "(sejak 2020 hingga 2024)" bukan sitasi.
            if cited and re.match(r"^\W*[A-Z]", cited.group("names")) and name_tokens(cited.group("names")):
                text = f"({part.strip()})"
                found.append((match.start(), text, "author", (cited.group("names"), cited.group("year"))))

    return [(text, kind, value) for _, text, kind, value in sorted(found, key=lambda item: item[0])]


def match_author(names, year, references):
    """(nomor, status): status "ok", "year" (nama cocok, tahun beda), atau "missing"."""

    cited = name_tokens(names)
    year = year[:4] if year[:1].isdigit() else "t.t."
    best, best_overlap, best_status = None, 0, "missing"

    for number, reference in references.items():
        pool = name_tokens(reference["authors"] or reference["title"])
        overlap = len(cited & pool)
        if not overlap:
            continue
        status = "ok" if reference["year"] == year else "year"
        rank = (status == "ok", overlap)
        if best is None or rank > (best_status == "ok", best_overlap):
            best, best_overlap, best_status = number, overlap, status

    return best, best_status


def check_citations(draft, references):
    """{"ok": {nomor: [teks]}, "year": [(teks, nomor)], "missing": [teks], "unknown_numbers": [teks]}."""

    result = {"ok": {}, "year": [], "missing": [], "unknown_numbers": []}

    for text, kind, value in find_citations(draft):
        if kind == "number":
            if value in references:
                result["ok"].setdefault(value, []).append(text)
            elif text not in result["unknown_numbers"]:
                result["unknown_numbers"].append(text)
            continue

        number, status = match_author(*value, references)
        if status == "ok":
            result["ok"].setdefault(number, []).append(text)
        elif status == "year":
            if (text, number) not in result["year"]:
                result["year"].append((text, number))
        elif text not in result["missing"]:
            result["missing"].append(text)

    return result


# ------------------------------------------------------------
# Kemiripan
# ------------------------------------------------------------

def words(text):
    return re.findall(r"\w+", fold(text))


def shingles(tokens):
    return {tuple(tokens[i:i + SHINGLE]) for i in range(len(tokens) - SHINGLE + 1)}


def sentences(text):
    return [s.strip() for s in SENTENCE_END.split(text) if s and s.strip()]


def is_direct_quote(sentence):
    """Kalimat yang sebagian besar berada di dalam tanda petik: kutipan langsung, bukan salinan diam-diam."""
    quoted = sum(len(q) for q in re.findall(r"[\"“]([^\"”]+)[\"”]", sentence))
    return quoted >= 0.6 * len(sentence)


def map_body(source_map):
    """Teks ringkasan peta sumber tanpa Daftar Pustaka dan tanpa nomor [n]."""
    text = str(source_map)
    references = reference_section(text)
    if references:
        text = text[:text.rfind(references)]
    return NUMBERED.sub(" ", text)


def similar_sentences(draft, source_map, excerpts, topic=""):
    """
    [(kalimat, skor 0-1, label pembanding)] untuk kalimat yang mirip, skor
    tertinggi dulu. Rangkaian kata dari judul topik tidak dihitung: menyebut
    judul skripsi sendiri bukan menyalin.
    """

    corpora = [(f"cuplikan sumber [{n}]", shingles(words(" ".join(texts)))) for n, texts in excerpts.items()]
    corpora.append(("ringkasan peta sumber Ciel", shingles(words(map_body(source_map)))))

    topic_shingles = shingles(words(topic))
    flagged = []
    for sentence in sentences(draft):
        # Sitasi tidak ikut dibandingkan: "(Nama, 2024)" bukan bagian dari kalimat yang disalin.
        tokens = words(PARENTHETICAL.sub(" ", NUMBERED.sub(" ", sentence)))
        if len(tokens) < MIN_SENTENCE_WORDS or is_direct_quote(sentence):
            continue
        own = shingles(tokens) - topic_shingles
        if not own:
            continue
        score, label = max(((len(own & corpus) / len(own), label) for label, corpus in corpora), default=(0, ""))
        if score >= SIMILAR:
            flagged.append((sentence, score, label))

    return sorted(flagged, key=lambda item: -item[1])


# ------------------------------------------------------------
# Laporan
# ------------------------------------------------------------

def quote(text, limit=400):
    text = " ".join(str(text).split())
    if len(text) > limit:
        text = text[:limit - 1].rstrip() + "…"
    # Teks draf ditampilkan apa adanya, bukan sebagai Markdown.
    return re.sub(r"([\\`*_\[\]<>#|])", r"\\\1", text)


def check_report(draft, source_map, excerpts, topic):
    """Laporan Markdown cek kutipan & kemiripan."""

    body = without_own_references(clean_draft(draft))
    references = parse_references(source_map)
    citations = check_citations(body, references)
    flagged = similar_sentences(body, source_map, excerpts, topic)

    total_words = word_count(body)
    flagged_words = sum(word_count(sentence) for sentence, _, _ in flagged)
    share = round(100 * flagged_words / total_words) if total_words else 0
    cited_numbers = set(citations["ok"]) | {number for _, number in citations["year"]}
    uncited = [n for n in references if n not in cited_numbers]
    problems = len(citations["year"]) + len(citations["missing"]) + len(citations["unknown_numbers"])
    matched = sum(len(texts) for texts in citations["ok"].values())

    compared = (
        f"peta sumber dan cuplikan {len(excerpts)} sumbernya"
        if excerpts
        else "teks peta sumber (peta sumber ini dibuat sebelum Ciel menyimpan cuplikan sumber)"
    )

    lines = [
        f"# Cek Kutipan & Kemiripan: {quote(topic, 160)}",
        "",
        f"Draf {total_words} kata dibandingkan dengan {compared}.",
        "",
        "## Ringkasan",
        "",
        f"- Sitasi yang cocok dengan peta sumber: {matched}. Perlu dicek: {problems}.",
        (
            f"- Kalimat yang terlalu mirip: {len(flagged)} (sekitar {share}% dari draf)."
            if flagged
            else "- Kalimat yang terlalu mirip: tidak ada."
        ),
    ]

    if uncited:
        lines.append(f"- Sumber peta yang belum kamu kutip: {', '.join(f'[{n}]' for n in uncited)}.")

    if problems:
        lines += ["", "## Sitasi yang perlu dicek", ""]
        for text, number in citations["year"][:MAX_LISTED]:
            lines.append(
                f"- {quote(text)}: namanya cocok dengan [{number}] ({quote(references[number]['label'])}), "
                "tapi tahunnya beda. Samakan dengan tahun di sumber aslinya."
            )
        for text in citations["missing"][:MAX_LISTED]:
            lines.append(
                f"- {quote(text)}: tidak ada di peta sumber. Kalau ini sumber lain, "
                "pastikan ada di daftar pustakamu dan kamu sudah membacanya."
            )
        for text in citations["unknown_numbers"][:MAX_LISTED]:
            lines.append(f"- {quote(text)}: nomor ini tidak ada di Daftar Pustaka peta sumber.")

    if citations["ok"]:
        lines += ["", "## Sitasi yang cocok", ""]
        for number in sorted(citations["ok"], key=int):
            lines.append(f"- [{number}] {quote(references[number]['label'])}: dikutip {len(citations['ok'][number])} kali.")

    if flagged:
        lines += ["", "## Kalimat yang terlalu mirip", ""]
        for index, (sentence, score, label) in enumerate(flagged[:MAX_LISTED], 1):
            advice = (
                "Ringkasan itu bukan teks sumber asli: baca sumbernya, tulis dengan kata-katamu, lalu kutip sumbernya."
                if label.startswith("ringkasan")
                else "Parafrasekan dengan kata-katamu dan cantumkan sitasinya, atau jadikan kutipan langsung bertanda petik."
            )
            lines += [
                f"{index}. > {quote(sentence)}",
                "",
                f"   {round(score * 100)}% rangkaian katanya sama dengan {label}. {advice}",
                "",
            ]
        if len(flagged) > MAX_LISTED:
            lines.append(f"Dan {len(flagged) - MAX_LISTED} kalimat lain dengan kemiripan lebih rendah.")

    if not problems and not flagged:
        lines += ["", "Tidak ada sitasi yang janggal atau kalimat yang terlalu mirip dengan sumber di peta ini."]

    lines += ["", CHECK_FOOTNOTE]
    return "\n".join(lines).replace("\n\n\n", "\n\n").strip()
