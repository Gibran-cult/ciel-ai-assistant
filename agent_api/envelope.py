"""Amplop data untuk isi tidak tepercaya (docs/security.md bagian 5, lapis 1 dan 6).

Isi halaman, file, layar, dan hasil tool tidak pernah dikirim ke model di
saluran perintah. Semuanya dibungkus di sini, dengan sumber yang disebut,
dan dengan penanda yang tidak bisa ditiru dari dalam isi.
"""

import re
import secrets

SOURCES = frozenset({"page", "file", "screen", "listing", "tool"})
MAX_CHARS = 20_000
NONCE_RE = re.compile(r"[0-9a-f]{8}")
CUT = "\n[dipotong]"

# Tiga tanda berurutan di dalam isi diganti dengan tanda kutip sudut. Sisa
# penggantian paling banyak dua tanda, jadi penanda amplop tidak bisa
# terbentuk lagi dari dalam isi.
SWAPS = (("<<<", "‹‹‹"), (">>>", "›››"))

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


def wrap(source, text, nonce=None):
    """Bungkus isi tidak tepercaya untuk dikirim ke model.

    Setiap amplop punya id acak di kedua penandanya. Model diberi tahu bahwa
    amplop hanya berakhir di penanda penutup dengan id yang sama, jadi
    tiruan penanda di dalam isi (termasuk hasil penggantian di SWAPS) tidak
    bisa dibaca sebagai akhir data.
    """

    if not isinstance(nonce, str) or not NONCE_RE.fullmatch(nonce):
        nonce = secrets.token_hex(4)

    label = source if isinstance(source, str) and source in SOURCES else "unknown"
    body = text if isinstance(text, str) else ""

    if len(body) > MAX_CHARS:
        body = body[:MAX_CHARS] + CUT

    for marker, safe in SWAPS:
        body = body.replace(marker, safe)

    return f"<<<DATA sumber={label} id={nonce}>>>\n{body}\n<<<AKHIR DATA {nonce}>>>"


def flags_injection(text):
    """Benar kalau isi memuat pola perintah yang ditujukan ke AI."""

    return isinstance(text, str) and INJECTION_RE.search(text) is not None
