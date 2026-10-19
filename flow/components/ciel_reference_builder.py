"""Ciel Reference Builder (Langflow custom component, flow Ciel Riset Skripsi).

Sits after Ciel Source Guard. The Agent ends its source map with a "Sumber:"
list of `[n] URL` lines only; the guard has already removed lines whose URL
Exa did not return. This component replaces that list with "## Daftar Pustaka"
in APA 7 style, written from the metadata Ciel Scholar Search recorded for each
URL (author, year, title). The model never writes an author or a year.

- Entries are renumbered 1..n in order of the list and every [n] marker in
  the text follows, so the numbers have no gaps after the guard.
- An entry whose URL has no recorded metadata is dropped with its markers
  (the guard passes everything through when no search ran).
- Missing author: the title moves to the front, as APA does. Missing date:
  "(t.t.)". The source is the journal when the page title is "Article |
  Journal" (OJS), otherwise the URL's domain; DOI links stand alone.
- Author names are kept as Exa gives them: turning Indonesian names into
  "Surname, I." automatically is too often wrong.
- The guard's note "(N sumber dihapus ...)" stays, after the list.
"""

import re
from urllib.parse import urlsplit

from langflow.custom import Component
from langflow.io import MessageInput, Output
from langflow.schema.message import Message

# Same keys in ciel_scholar_search.py and ciel_source_guard.py
# (components cannot import each other).
RETRIEVED_SOURCES_KEY = "ciel_retrieved_sources"

SOURCES_HEADING = re.compile(r"^\W*sumber\W*$", re.IGNORECASE)
SOURCE_ENTRY = re.compile(r"^\W*\[(\d+)\]")
MARKER = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
URL = re.compile(r"https?://[^\s<>\"'\[\]]+")
YEAR = re.compile(r"^(\d{4})")

REFERENCES_HEADING = "## Daftar Pustaka"
REFERENCES_NOTE = (
    "Daftar pustaka disusun otomatis dari data sumber hasil pencarian. "
    "Periksa nama penulis, tahun, dan judul di sumber aslinya sebelum mengutip."
)


def cited_urls(line):
    """URLs in a line; a closing parenthesis is kept only when the URL opened one (Markdown links)."""
    urls = []
    for url in URL.findall(line):
        while url.endswith(")") and url.count(")") > url.count("("):
            url = url[:-1]
        urls.append(url)
    return urls


def normalize_url(url):
    url = url.strip().lower().split("#", 1)[0]
    url = re.sub(r"^https?://", "", url)
    url = re.sub(r"^www\.", "", url)
    return url.rstrip("/.,;:*_")


def clean(text):
    """One line of plain text: no Markdown emphasis, collapsed spaces, no trailing period."""
    text = re.sub(r"[*_`]", "", str(text or ""))
    return " ".join(text.split()).rstrip(". ")


def site_name(url):
    host = urlsplit(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def apa_entry(number, source):
    """[n] Penulis. (Tahun). *Judul*. Jurnal atau situs. URL"""
    author = clean(source.get("author"))
    title = clean(source.get("title"))
    year = YEAR.match(str(source.get("published_date") or "").strip())
    year = year.group(1) if year else "t.t."
    site = site_name(source["url"])

    # OJS article pages (most Indonesian journals) are titled "Article | Journal":
    # the journal name says more than the domain.
    if " | " in title:
        title, journal = (clean(part) for part in title.rsplit(" | ", 1))
        site = journal or site

    # A DOI link stands alone in APA 7; "doi.org" is not a site name.
    if site == "doi.org":
        site = ""

    title = title or site_name(source["url"])

    if author:
        parts = [f"{author}.", f"({year}).", f"*{title}*."]
    else:
        parts = [f"*{title}*.", f"({year})."]

    if site and site != title.lower():
        parts.append(f"{site}.")

    parts.append(source["url"])
    return f"[{number}] " + " ".join(parts)


def renumber(line, numbers):
    """Markers rewritten with `numbers` ({old: new}); markers not in it are removed."""

    def replace(match):
        new = [numbers[n.strip()] for n in match.group(1).split(",") if n.strip() in numbers]
        return f"[{', '.join(new)}]" if new else ""

    new_line = MARKER.sub(replace, line)
    if new_line != line:
        new_line = re.sub(r"(?<=\S)[ \t]{2,}", " ", new_line)
        new_line = re.sub(r"[ \t]+([.,;:])", r"\1", new_line).rstrip()
    return new_line


def build_references(text, sources):
    """(text with the Sumber list replaced by Daftar Pustaka, number of entries)."""
    lines = text.splitlines()
    heading = next((i for i in range(len(lines) - 1, -1, -1) if SOURCES_HEADING.match(lines[i])), None)
    if heading is None:
        return text, 0

    known = {}
    for source in sources or []:
        known.setdefault(normalize_url(source["url"]), source)

    numbers = {}
    entries = []
    trailing = []
    for line in lines[heading + 1:]:
        entry = SOURCE_ENTRY.match(line)
        if not entry:
            if line.strip():
                trailing.append(line.strip())
            continue
        source = next((known[normalize_url(url)] for url in cited_urls(line) if normalize_url(url) in known), None)
        if source is None or entry.group(1) in numbers:
            continue
        numbers[entry.group(1)] = str(len(entries) + 1)
        entries.append(apa_entry(len(entries) + 1, source))

    body = [renumber(line, numbers) for line in lines[:heading]]
    while body and not body[-1].strip():
        body.pop()

    if entries:
        # Blank lines between entries: Markdown would join adjacent lines into one paragraph.
        section = [REFERENCES_HEADING, ""] + "\n\n".join(entries).split("\n") + ["", REFERENCES_NOTE]
    else:
        section = [REFERENCES_HEADING, "Tidak ada sumber hasil pencarian yang bisa dicantumkan."]

    if trailing:
        section += ["", *trailing]

    return "\n".join(body + [""] + section), len(entries)


def text_contents(message):
    """Text items of a message's content blocks (flat or grouped under .contents)."""
    for block in getattr(message, "content_blocks", None) or []:
        for item in getattr(block, "contents", None) or [block]:
            if getattr(item, "type", None) == "text" and isinstance(getattr(item, "text", None), str):
                yield item


class CielReferenceBuilder(Component):
    display_name = "Ciel Reference Builder"
    description = (
        "Mengganti daftar Sumber dengan Daftar Pustaka APA 7 yang disusun dari "
        "metadata Ciel Scholar Search, dan menomori ulang sitasi [n]."
    )
    icon = "book-open"
    name = "CielReferenceBuilder"

    inputs = [
        MessageInput(name="notes", display_name="Answer", required=True),
    ]

    outputs = [
        Output(display_name="Message", name="with_references", method="build"),
    ]

    def build(self) -> Message:
        sources = self.ctx.get(RETRIEVED_SOURCES_KEY) or []
        message = self.notes
        if isinstance(message, str):
            message = Message(text=message)

        # Same rule as Ciel Source Guard: edit text blocks in place, and assign
        # Message.text only for a message without blocks.
        count = 0
        items = list(text_contents(message))
        for item in items:
            item.text, found = build_references(item.text, sources)
            count += found
        if not items and isinstance(message.text, str):
            built, count = build_references(message.text, sources)
            if built != message.text:
                message.text = built

        self.status = f"{len(sources)} hasil Exa, {count} entri daftar pustaka."
        return message
