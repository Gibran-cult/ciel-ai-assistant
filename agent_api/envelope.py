"""Amplop data untuk isi tidak tepercaya (docs/security.md bagian 5, lapis 1 dan 6).

Isi halaman, file, layar, dan hasil tool tidak pernah dikirim ke model di
saluran perintah. Semuanya dibungkus di sini, dengan sumber yang disebut,
dan dengan penanda yang tidak bisa ditiru dari dalam isi.
"""

import re

SOURCES = frozenset({"page", "file", "screen", "listing", "tool"})
MAX_CHARS = 20_000
CLOSE = "<<<AKHIR DATA>>>"
CUT = "\n[dipotong]"

# Deret dua tanda atau lebih diganti semua, supaya sisa penggantian tidak
# bisa bergabung lagi menjadi penanda.
OPENERS = re.compile(r"<{2,}")
CLOSERS = re.compile(r">{2,}")

# Sinyal tambahan saja. Pengaman utamanya tetap mesin kebijakan.
INJECTION_RE = re.compile(
    r"abaikan\s+(?:semua\s+)?(?:instruksi|perintah)"
    r"|ignore\s+(?:all\s+|any\s+)?(?:previous|prior|above)\s+(?:instructions|prompts)"
    r"|\b(?:asisten|assistant|agen|agent)\s+ai\b"
    r"|system\s+prompt|instruksi\s+(?:sistem|baru)\s*:"
    r"|you\s+are\s+now|kamu\s+sekarang\s+adalah"
    r"|jangan\s+beri\s*tahu\s+pengguna|do\s+not\s+tell\s+the\s+user",
    re.IGNORECASE,
)


def wrap(source, text):
    """Bungkus isi tidak tepercaya untuk dikirim ke model."""

    label = source if isinstance(source, str) and source in SOURCES else "unknown"
    body = text if isinstance(text, str) else ""

    if len(body) > MAX_CHARS:
        body = body[:MAX_CHARS] + CUT

    body = OPENERS.sub(lambda found: "‹" * len(found.group()), body)
    body = CLOSERS.sub(lambda found: "›" * len(found.group()), body)
    return f"<<<DATA sumber={label}>>>\n{body}\n{CLOSE}"


def flags_injection(text):
    """Benar kalau isi memuat pola perintah yang ditujukan ke AI."""

    return isinstance(text, str) and INJECTION_RE.search(text) is not None
