"""Ciel Source Guard (Langflow custom component).

Sits between the Agent and Chat Output of the main flow (v1.9.0, where the
Agent searches with Ciel Exa Search itself). When the run searched, it removes
every line under "Sumber:" whose URLs Ciel Exa Search did not return, the [n]
markers of those entries, and findings whose only markers pointed at removed
entries. One line at the end says how many sources were removed.

It never adds other text. Answers from runs without a search pass through
unchanged, and so do source lines without a URL (an attached file, the
Knowledge Base). The Agent message is filtered in place, block by block,
because the app shows the last text block of the message. Text from earlier
Agent rounds is dropped so the stored answer is the final answer only.

Why: with few search results the research agent sometimes listed sources from
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
    """(checked text, number of removed sources). Without retrieved URLs nothing was searched."""
    lines = text.splitlines()
    heading = next((i for i in range(len(lines) - 1, -1, -1) if SOURCES_HEADING.match(lines[i])), None)
    if heading is None or not retrieved_urls:
        return text, 0

    known = {normalize_url(url) for url in retrieved_urls}
    removed_numbers = set()
    removed_lines = 0
    sources = []
    for line in lines[heading + 1:]:
        urls = cited_urls(line)
        if urls and not any(normalize_url(url) in known for url in urls):
            removed_lines += 1
            entry = SOURCE_ENTRY.match(line)
            if entry:
                removed_numbers.add(entry.group(1))
            continue
        sources.append(line)

    if not removed_lines:
        return text, 0

    def keep(block):
        # Findings can also follow the source list (live test: a finding written after it).
        kept = []
        for line in block:
            if SOURCE_ENTRY.match(line):
                kept.append(line)
                continue
            new_line, only_removed = strip_markers(line, removed_numbers)
            if not only_removed:
                kept.append(new_line)
        return kept

    checked = "\n".join(keep(lines[:heading]) + [lines[heading]] + keep(sources)).rstrip()
    note = f"({removed_lines} sumber dihapus karena tidak ada di hasil pencarian.)"
    return f"{checked}\n\n{note}", removed_lines


def text_contents(message):
    """Text items of a message's content blocks (flat or grouped under .contents)."""
    for block in getattr(message, "content_blocks", None) or []:
        for item in getattr(block, "contents", None) or [block]:
            if getattr(item, "type", None) == "text" and isinstance(getattr(item, "text", None), str):
                yield item


def keep_final_answer_only(message):
    """Drop the text of earlier Agent rounds; tool blocks and the final answer stay.

    Chat Output assigns Message.text, which joins every text block into one
    (live v1.9.0 test: the app then showed a tool round's text and the answer
    one after the other). With only the final answer left, the joined text is
    the answer.
    """
    blocks = getattr(message, "content_blocks", None)
    if not isinstance(blocks, list):
        return
    texts = [block for block in blocks if getattr(block, "type", None) == "text"]
    if len(texts) > 1:
        blocks[:] = [block for block in blocks if getattr(block, "type", None) != "text" or block is texts[-1]]


class CielSourceGuard(Component):
    display_name = "Ciel Source Guard"
    description = (
        "Menghapus sumber yang URL-nya tidak dikembalikan Ciel Exa Search "
        "pada run yang sama."
    )
    icon = "shield-check"
    name = "CielSourceGuard"

    inputs = [
        MessageInput(name="notes", display_name="Answer", required=True),
    ]

    outputs = [
        Output(display_name="Message", name="checked_notes", method="check"),
    ]

    def check(self) -> Message:
        retrieved = self.ctx.get(RETRIEVED_URLS_KEY) or []
        message = self.notes
        if isinstance(message, str):
            message = Message(text=message)

        # Langflow 1.12 derives Message.text from the text blocks, and assigning
        # it replaces every text block with one joined block (the app would then
        # show earlier rounds too). So filter inside the blocks and assign text
        # only for a message without blocks, and only when it changed.
        removed = 0
        items = list(text_contents(message))
        for item in items:
            item.text, count = filter_sources(item.text, retrieved)
            removed += count
        if not items and isinstance(message.text, str):
            checked, removed = filter_sources(message.text, retrieved)
            if removed:
                message.text = checked
        keep_final_answer_only(message)

        self.status = f"{len(set(retrieved))} URL dari Exa, {removed} sumber dihapus."
        return message
