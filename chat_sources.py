"""Sumber dan dugaan yang tertulis di jawaban Ciel.

Jawaban chat biasa diakhiri blok "Sumber:" ([1] nama — judul — URL — tanggal,
satu baris atau satu entri per baris). Hasil Riset Skripsi dan Kerangka
memakai "## Daftar Pustaka" berformat APA ([n] Penulis. (Tahun). *Judul*.
Situs. URL). Mode analisis memberi label [Terverifikasi]/[Dugaan] per poin.

Modul ini hanya membaca teks. Isi pesan yang tersimpan tidak pernah diubah;
app.py memakai hasilnya untuk tampilan (tombol sumber, panel kanan).
"""

import html
import re
from dataclasses import dataclass
from urllib.parse import urlsplit


SUMBER_LINE = re.compile(r"^\s*\**\s*Sumber\s*\**\s*:\s*\**", re.IGNORECASE)
ENTRY_MARKER = re.compile(r"(?:^|\s)\[(\d+)\]\s")
ENTRY_LINE = re.compile(r"^\s*\[\d+\]\s")
# Square brackets end a URL (as in the source guard): "https://[link]" is not one.
URL = re.compile(r"https?://[^\s<>\"'\[\]]+")
SEPARATOR = re.compile(r"\s+[—–]\s+|\s+-\s+")
GUARD_NOTE = re.compile(r"\(\d+ sumber dihapus[^)]*\)")
REFERENCES_HEADING = re.compile(r"^##\s+Daftar Pustaka\b.*$", re.IGNORECASE | re.MULTILINE)
REFERENCE_ENTRY = re.compile(r"^\[(\d+)\]\s+(.*)$")
ITALIC_TITLE = re.compile(r"\*([^*]+)\*")
LIST_MARKER = re.compile(r"^(?:\d+[.)]|[-*•])\s+")
GUESS_LIMIT = 140
QUESTION_LIMIT = 60


@dataclass(frozen=True)
class Source:
    number: int
    title: str
    domain: str
    url: str


@dataclass(frozen=True)
class AnswerGroup:
    question: str
    sources: list


@dataclass(frozen=True)
class ChatSummary:
    groups: list
    unique_count: int
    guesses: list
    map_entries: int


def _cut(text, limit):
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(" ,.;:") + "…"


def _url(text):
    match = URL.search(text)
    if not match:
        return None, -1
    # Same rule as the source guard: Markdown emphasis and punctuation end
    # a URL, and a closing parenthesis stays only when the URL opened one.
    url = match.group(0)
    while True:
        trimmed = url.rstrip(".,;:*_")
        while trimmed.endswith(")") and trimmed.count(")") > trimmed.count("("):
            trimmed = trimmed[:-1]
        if trimmed == url:
            return url, match.start()
        url = trimmed


def _domain(url):
    """Host without "www.", or None when the URL cannot be parsed."""
    try:
        host = urlsplit(url).hostname or ""
    except ValueError:
        return None
    return host[4:] if host.startswith("www.") else host


def _sumber_entry(number, text):
    url, start = _url(text)
    if url is None or not _domain(url):
        return None
    before = text[:start].strip(" —–-")
    fields = [field.strip() for field in SEPARATOR.split(before) if field.strip()]
    title = fields[1] if len(fields) >= 2 else fields[0] if fields else _domain(url)
    return Source(number, " ".join(title.split()), _domain(url), url)


def split_sources(text):
    """(teks sebelum blok "Sumber:" terakhir, sumber ber-URL http(s), sisa teks).

    Sisa = teks sebelum [1], entri tanpa URL http(s), catatan guard "(N sumber
    dihapus ...)" dan semua teks sesudah blok, supaya tidak ada isi yang hilang
    saat blok dipindah ke tombol. Tanpa blok
    (atau blok tanpa entri bernomor), teks dikembalikan apa adanya.
    """

    text = str(text or "")
    lines = text.split("\n")
    start = next((i for i in range(len(lines) - 1, -1, -1) if SUMBER_LINE.match(lines[i])), None)
    if start is None:
        return text, [], ""

    # The block is the "Sumber:" line plus the entry lines right under it.
    # Anything after it (findings the model wrote below the list, the guard
    # note) is kept as text, never parsed into entries.
    end = start + 1
    while end < len(lines) and ENTRY_LINE.match(lines[end]):
        end += 1
    block = SUMBER_LINE.sub("", lines[start], count=1) + "\n" + "\n".join(lines[start + 1:end])
    notes = GUARD_NOTE.findall(block)
    block = GUARD_NOTE.sub("", block)
    markers = list(ENTRY_MARKER.finditer(block))
    if not markers:
        return text, [], ""

    sources, kept = [], []
    prefix = block[:markers[0].start()].strip()
    if prefix:
        kept.append(prefix)
    for index, marker in enumerate(markers):
        stop = markers[index + 1].start() if index + 1 < len(markers) else len(block)
        number = int(marker.group(1))
        entry_text = block[marker.end():stop].strip()
        source = _sumber_entry(number, entry_text)
        if source:
            # The same URL twice in one list is one source (the first number).
            if all(seen.url != source.url for seen in sources):
                sources.append(source)
        else:
            kept.append(f"[{number}] {entry_text}")

    tail = "\n".join(lines[end:]).strip()
    body = "\n".join(lines[:start])
    return body, sources, "\n\n".join(kept + notes + ([tail] if tail else []))


def reference_sources(text):
    """Entri ber-URL di "## Daftar Pustaka" terakhir (Riset Skripsi, Kerangka)."""

    text = str(text or "")
    headings = list(REFERENCES_HEADING.finditer(text))
    if not headings:
        return []

    sources = []
    for line in text[headings[-1].end():].split("\n"):
        if line.startswith("## "):
            break
        entry = REFERENCE_ENTRY.match(line.strip())
        if not entry:
            continue
        number, body = int(entry.group(1)), entry.group(2)
        url, start = _url(body)
        if url is None or not _domain(url):
            continue
        title = ITALIC_TITLE.search(body)
        title = title.group(1).strip() if title else body[:start].strip(" .") or _domain(url)
        if all(seen.url != url for seen in sources):
            sources.append(Source(number, " ".join(title.split()), _domain(url), url))
    return sources


def answer_sources(text):
    """Sumber dari blok "Sumber:", atau dari Daftar Pustaka jika blok itu tidak ada."""

    return split_sources(text)[1] or reference_sources(text)


def guesses(text):
    """Teks tiap poin berlabel [Dugaan], tanpa label dan penanda daftar."""

    found = []
    for line in str(text or "").split("\n"):
        if "[Dugaan]" not in line:
            continue
        item = LIST_MARKER.sub("", line.replace("[Dugaan]", "").strip()).strip()
        if item:
            found.append(_cut(item, GUESS_LIMIT))
    return found


def summarize(messages):
    """Ringkasan sumber dan dugaan satu chat untuk header dan panel kanan."""

    groups, found, map_entries, question = [], [], 0, ""
    for message in messages or []:
        content = str(message.get("content", ""))
        if message.get("role") == "user":
            question = content
            continue
        if message.get("error"):
            continue
        body, sources, _ = split_sources(content)
        sources = sources or reference_sources(content)
        if sources:
            groups.append(AnswerGroup(_cut(question, QUESTION_LIMIT), sources))
        found.extend(guesses(body))
        if message.get("kind") == "riset_skripsi":
            map_entries = len(reference_sources(content))

    groups.reverse()
    unique = {source.url for group in groups for source in group.sources}
    return ChatSummary(groups, len(unique), found, map_entries)


# ------------------------------------------------------------
# Tampilan (app.py)
# ------------------------------------------------------------

BADGES = (("[Dugaan]", ":orange-badge[Dugaan]"), ("[Terverifikasi]", ":blue-badge[Terverifikasi]"))


def _badges(text):
    for label, badge in BADGES:
        text = text.replace(label, badge)
    return text


def answer_parts(text):
    """(markdown sebelum tombol, sumber untuk tombol, markdown sesudah tombol).

    Tanpa HTML; isi tersimpan tetap utuh. Blok "Sumber:" pindah ke tombol
    (source_buttons_html) bila ada entri ber-URL; entri tanpa URL, catatan
    guard dan teks sesudah blok tampil di bawah tombol. Tanpa entri ber-URL
    jawaban tampil apa adanya. Label [Dugaan]/[Terverifikasi] jadi badge.
    """

    text = str(text or "")
    body, sources, leftover = split_sources(text)
    if not sources:
        return _badges(text), [], ""
    return _badges(body.rstrip()), sources, _badges(leftover)


def source_label(source):
    """Accessible name of a source link."""
    return f"Sumber {source.number}: {source.title}, {source.domain} (buka di tab baru)"


def source_buttons_html(sources):
    """Deretan tombol sumber bernomor; setiap teks di-escape, hanya link http(s)."""

    links = "".join(
        f'<a class="ciel-src" href="{html.escape(source.url, quote=True)}" target="_blank" rel="noopener noreferrer" '
        f'aria-label="{html.escape(source_label(source), quote=True)}">'
        f"<b>{source.number}</b>{html.escape(source.domain)}<span>{html.escape(source.title)}</span></a>"
        for source in sources
        if source.url.startswith(("https://", "http://"))
    )
    return f'<div class="ciel-srcs" aria-label="Sumber">{links}</div>' if links else ""


def count_line(summary):
    """"8 sumber · 1 belum ketemu"; bagian yang nol tidak ditulis."""

    parts = []
    if summary.unique_count:
        parts.append(f"{summary.unique_count} sumber")
    if summary.guesses:
        parts.append(f"{len(summary.guesses)} belum ketemu")
    return " · ".join(parts)
