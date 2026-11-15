"""Tingkat risiko aksi agent (docs/security.md bagian 2).

R0 baca, R1 bisa dibatalkan, R2 wajib konfirmasi, R3 diblokir. Tingkatnya
ditentukan dari jenis aksi dan targetnya. Model tidak ikut menentukan, dan
jenis aksi yang tidak dikenal langsung masuk R3.

Aksi datang dari keluaran model, jadi kolom bertipe salah diperlakukan
sebagai kosong dan tidak pernah memicu exception.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from guard.domains import match_allowed

R0, R1, R2, R3 = "R0", "R1", "R2", "R3"


@dataclass(frozen=True)
class Action:
    kind: str                       # salah satu kunci ACTION_LEVELS
    host: str | None = None         # untuk aksi browser
    app: str | None = None          # nama aplikasi desktop
    path: str | None = None         # untuk aksi file
    text: str | None = None         # teks yang akan diketik
    field_type: str | None = None   # "password" | "otp" | "card" | "text" | None
    submits: bool = False           # klik atau ketik yang memicu kirim data
    tainted: bool = False           # target berasal dari isi tidak tepercaya


@dataclass(frozen=True)
class RiskVerdict:
    level: str
    reason: str


ACTION_LEVELS = {
    **dict.fromkeys((
        "tab_read", "file_list", "file_read", "ui_read", "screen_capture", "store_verify",
        "cart_read", "search", "memory_search", "ask_user", "finish",
    ), R0),
    **dict.fromkeys((
        "tab_open", "tab_close", "tab_scroll", "tab_click", "tab_type", "tab_select",
        "file_write", "file_move", "folder_create", "app_open", "ui_click", "ui_type",
        "key_press", "cart_add", "checkout_prepare", "memory_store",
    ), R1),
    **dict.fromkeys((
        "form_submit", "file_delete", "message_send", "download", "app_install", "app_uninstall",
        "settings_change", "file_share", "checkout_handoff", "order_cancel",
    ), R2),
    **dict.fromkeys((
        "pay", "shell_run", "run_downloaded", "captcha_solve", "account_create", "oauth_grant",
        "terms_accept",
    ), R3),
}

SECRET_FIELDS = frozenset({"password", "otp", "card"})

# Aksi R1 yang targetnya bisa dibelokkan oleh isi halaman atau file.
TAINTABLE = frozenset({"tab_open", "tab_type", "file_write", "file_move", "ui_type"})

# Aplikasi dan situs yang tidak pernah boleh disentuh agent (keputusan D9).
BLOCKED = json.loads(Path(__file__).with_name("blocked_targets.json").read_text(encoding="utf-8"))
BLOCKED_APPS = tuple(name.lower() for name in BLOCKED["apps"])
BLOCKED_HOSTS = tuple(BLOCKED["host_suffixes"])

# 13 sampai 19 digit, boleh dipisah spasi atau tanda hubung.
CARD_RE = re.compile(r"(?<!\d)\d(?:[ -]?\d){12,18}(?!\d)")
TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{19,}(?![A-Za-z0-9_-])")


def luhn_ok(digits):
    total = 0

    for index, char in enumerate(reversed(digits)):
        value = int(char)

        if index % 2:
            value = value * 2 - (9 if value > 4 else 0)

        total += value

    return total % 10 == 0


def is_key(token):
    if token.startswith("sk-"):
        return True

    return (
        len(token) >= 32
        and any(char.isupper() for char in token)
        and any(char.islower() for char in token)
        and any(char.isdigit() for char in token)
    )


def find_secrets(text):
    """Letak rahasia di dalam teks: daftar (awal, akhir, jenis), urut dari kiri.

    Dipakai looks_like_secret di sini dan redact di guard/audit.py, supaya
    hanya ada satu definisi "rahasia". OTP tidak ditebak dari teks, karena
    angka pendek biasa (kode pos, tahun) akan ikut terblokir. OTP ditangani
    lewat field_type.
    """

    if not isinstance(text, str):
        return []

    found = [
        (match.start(), match.end(), "card")
        for match in CARD_RE.finditer(text)
        if luhn_ok(re.sub(r"[ -]", "", match.group()))
    ]
    found += [
        (match.start(), match.end(), "api_key")
        for match in TOKEN_RE.finditer(text)
        if is_key(match.group())
    ]

    spans = []

    for span in sorted(found):
        if not spans or span[0] >= spans[-1][1]:
            spans.append(span)

    return spans


def looks_like_secret(text):
    """ "card", "api_key", atau None."""

    spans = find_secrets(text)
    return spans[0][2] if spans else None


def classify(action):
    kind = action.kind
    base = ACTION_LEVELS.get(kind) if isinstance(kind, str) else None

    if base is None:
        return RiskVerdict(R3, "unknown_kind")

    if isinstance(action.field_type, str) and action.field_type in SECRET_FIELDS:
        return RiskVerdict(R3, "secret_field")

    if looks_like_secret(action.text):
        return RiskVerdict(R3, "secret_text")

    if isinstance(action.app, str) and any(name in action.app.lower() for name in BLOCKED_APPS):
        return RiskVerdict(R3, "blocked_app")

    if isinstance(action.host, str) and match_allowed(action.host.lower(), BLOCKED_HOSTS):
        return RiskVerdict(R3, "blocked_host")

    # Memori jangka panjang hanya ditulis dari pesan pengguna sendiri, tidak
    # pernah dari isi halaman, email, atau file (pertahanan racun memori).
    if kind == "memory_store" and action.tainted is not False:
        return RiskVerdict(R3, "tainted_memory")

    if base == R1:
        # Nilai yang bukan False (termasuk yang tidak jelas) dihitung sebagai ya.
        if action.submits is not False:
            return RiskVerdict(R2, "submits")

        if action.tainted is not False and kind in TAINTABLE:
            return RiskVerdict(R2, "tainted_target")

    return RiskVerdict(base, kind)
