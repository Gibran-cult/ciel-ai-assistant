"""Ciel Source Guard (Langflow custom component).

Sits between the Research Agent and Chat Output of the Web Research Assistant.
It removes every entry under "Sumber:" whose URL Ciel Exa Search did not
return in this run, removes the [n] markers of those entries, and removes
findings whose only markers pointed at removed entries. One line at the end
says how many sources were removed. It never adds other text, and notes
without a "Sumber:" section pass through unchanged.

Why: with few search results the Research Agent sometimes listed sources from
memory (live test 2026-10-17: hai.stanford.edu pages and numbers that a
retrieved article only mentioned by name). Prompt rules reduced this but did
not stop it.
"""

import re

from langflow.custom import Component
from langflow.io import MessageInput, Output
from langflow.schema.message import Message

# Same key in ciel_exa_search.py (components cannot import each other).
RETRIEVED_URLS_KEY = "ciel_retrieved_urls"

SOURCES_HEADING = re.compile(r"^\W*sumber\W*$", re.IGNORECASE)
SOURCE_ENTRY = re.compile(r"^\W*\[(\d+)\]")
MARKER = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
URL = re.compile(r"https?://[^\s<>\"'\[\]]+")


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


def strip_markers(line, removed):
    """Line without markers of removed entries, and whether only removed ones were cited."""
    cited = kept = 0

    def replace(match):
        nonlocal cited, kept
        numbers = [n.strip() for n in match.group(1).split(",")]
        cited += len(numbers)
        remaining = [n for n in numbers if n not in removed]
        kept += len(remaining)
        return f"[{', '.join(remaining)}]" if remaining else ""

    new_line = MARKER.sub(replace, line)
    if new_line != line:
        new_line = re.sub(r"(?<=\S)[ \t]{2,}", " ", new_line)
        new_line = re.sub(r"[ \t]+([.,;:])", r"\1", new_line).rstrip()
    return new_line, cited > 0 and kept == 0


def filter_sources(text, retrieved_urls):
    """(checked text, number of removed sources) for research notes."""
    lines = text.splitlines()
    heading = next((i for i in range(len(lines) - 1, -1, -1) if SOURCES_HEADING.match(lines[i])), None)
    if heading is None:
        return text, 0

    known = {normalize_url(url) for url in retrieved_urls}
    removed = set()
    sources = []
    for line in lines[heading + 1:]:
        entry = SOURCE_ENTRY.match(line)
        if entry and not any(normalize_url(url) in known for url in cited_urls(line)):
            removed.add(entry.group(1))
            continue
        sources.append(line)

    if not removed:
        return text, 0

    def keep(block):
        # Findings can also follow the source list (live test: a finding written after it).
        kept = []
        for line in block:
            if SOURCE_ENTRY.match(line):
                kept.append(line)
                continue
            new_line, only_removed = strip_markers(line, removed)
            if not only_removed:
                kept.append(new_line)
        return kept

    checked = "\n".join(keep(lines[:heading]) + [lines[heading]] + keep(sources)).rstrip()
    note = f"({len(removed)} sumber dihapus karena tidak ada di hasil pencarian Exa.)"
    return f"{checked}\n\n{note}", len(removed)


class CielSourceGuard(Component):
    display_name = "Ciel Source Guard"
    description = (
        "Menghapus sumber di catatan riset yang URL-nya tidak dikembalikan "
        "Ciel Exa Search pada run yang sama."
    )
    icon = "shield-check"
    name = "CielSourceGuard"

    inputs = [
        MessageInput(name="notes", display_name="Research Notes", required=True),
    ]

    outputs = [
        Output(display_name="Message", name="checked_notes", method="check"),
    ]

    def check(self) -> Message:
        text = self.notes.text if isinstance(self.notes.text, str) else ""
        retrieved = self.ctx.get(RETRIEVED_URLS_KEY) or []
        checked, removed = filter_sources(text, retrieved)
        self.status = f"{len(set(retrieved))} URL dari Exa, {removed} sumber dihapus."
        return Message(text=checked)
