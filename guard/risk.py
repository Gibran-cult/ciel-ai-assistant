"""Tingkat risiko aksi agent (docs/security.md bagian 2).

R0 baca, R1 bisa dibatalkan, R2 wajib konfirmasi, R3 diblokir. Tingkatnya
ditentukan dari jenis aksi dan targetnya. Model tidak ikut menentukan, dan
jenis aksi yang tidak dikenal langsung masuk R3.

Aksi datang dari keluaran model, jadi kolom bertipe salah diperlakukan
sebagai kosong dan tidak pernah memicu exception.
"""

import json
import re
from dataclasses import dataclass, fields
from pathlib import Path

from guard.domains import match_allowed, normalize_host

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
    dest: str | None = None         # jalur tujuan untuk file_move dan download
    # Efek aksi menurut klien, ditulis sebagai jenis aksi. Contoh: klik pada
    # tombol "Tambah ke keranjang" dikirim sebagai kind="tab_click" dengan
    # effect="cart_add", supaya gerbang belanja tetap berlaku untuk klik biasa.
    effect: str | None = None


def action_from(data):
    """Action dari keluaran model.

    Kunci yang tidak dikenal tidak diabaikan: aksinya dijadikan tidak dikenal
    (dan karena itu diblokir), sebab kolom yang dibuang bisa saja kolom yang
    membuat aksi itu berbahaya.
    """

    if not isinstance(data, dict) or "kind" not in data or not set(data) <= ACTION_FIELDS:
        return Action(kind=None)

    return Action(**data)


ACTION_FIELDS = frozenset(field.name for field in fields(Action))


@dataclass(frozen=True)
class RiskVerdict:
    level: str
    reason: str


LEVEL_ORDER = {R0: 0, R1: 1, R2: 2, R3: 3}


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

# Jenis kolom yang jelas bukan rahasia. Jenis lain apa pun, termasuk yang
# tidak dikenal atau bertipe salah, diperlakukan sebagai kolom rahasia:
# kata sandi, PIN, OTP, CVV, dan kode pemulihan punya banyak ejaan.
HARMLESS_FIELDS = frozenset({
    "text", "search", "email", "tel", "url", "number", "textarea", "select",
    "checkbox", "radio", "date", "time",
})


def load_blocked(path):
    """Daftar aplikasi dan situs yang tidak pernah boleh disentuh agent (keputusan D9).

    Berkas yang rusak menggagalkan pemuatan: entri yang salah tulis akan
    diam-diam tidak pernah cocok.
    """

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    apps = tuple(name.strip().lower() for name in data["apps"])
    hosts = tuple(data["host_suffixes"])

    if not all(apps) or any(normalize_host(host) != host for host in hosts):
        raise ValueError("blocked_targets.json rusak")

    return apps, hosts


BLOCKED_APPS, BLOCKED_HOSTS = load_blocked(Path(__file__).with_name("blocked_targets.json"))

# Deret angka: kelompok digit yang dipisah paling banyak dua karakter bukan
# huruf dan bukan angka (spasi, tanda hubung, titik, garis miring, baris baru).
DIGIT_RUN_RE = re.compile(r"\d+(?:[^A-Za-z0-9]{1,2}\d+)*")
DIGITS_RE = re.compile(r"\d+")
TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{19,}(?![A-Za-z0-9_-])")

# Awalan kunci API yang dikenal. Token dengan awalan ini selalu diblokir.
KEY_PREFIXES = ("sk-", "ghp_", "gho_", "github_pat_", "xoxb-", "xoxp-", "AKIA", "AIza")


def luhn_ok(digits):
    total = 0

    for index, char in enumerate(reversed(digits)):
        value = int(char)

        if index % 2:
            value = value * 2 - (9 if value > 4 else 0)

        total += value

    return total % 10 == 0


def card_spans(text):
    """Nomor kartu di dalam teks, termasuk yang menempel ke angka lain.

    Jendela yang diuji selalu dimulai dan berakhir di batas kelompok digit
    ("4111 1111 1111 1111 123" diuji sebagai empat kelompok pertama), tidak
    di setiap posisi digit. Menguji setiap posisi akan membuat hampir semua
    nomor panjang biasa, misalnya NIK, lolos Luhn di salah satu jendela.
    """

    spans = []

    for run in DIGIT_RUN_RE.finditer(text):
        groups = [(run.start() + m.start(), run.start() + m.end(), m.group()) for m in DIGITS_RE.finditer(run.group())]
        index = 0

        while index < len(groups):
            hit = None

            # Paling banyak 19 kelompok, karena kartu paling panjang 19 digit.
            for end in range(min(len(groups), index + 19), index, -1):
                digits = "".join(group[2] for group in groups[index:end])

                if 13 <= len(digits) <= 19 and luhn_ok(digits):
                    hit = end
                    break

            if hit is None:
                index += 1
            else:
                spans.append((groups[index][0], groups[hit - 1][1], "card"))
                index = hit

    return spans


def key_kind(token):
    """ "api_key" untuk awalan kunci yang dikenal, "token" untuk deret acak panjang, atau None.

    Deret acak harus memuat cukup banyak angka dan huruf besar kecil, supaya
    nama file dan judul produk yang panjang tidak ikut tertangkap.
    """

    if token.startswith(KEY_PREFIXES):
        return "api_key"

    if (
        len(token) >= 32
        and sum(char.isdigit() for char in token) >= 6
        and sum(char.isupper() for char in token) >= 4
        and sum(char.islower() for char in token) >= 4
    ):
        return "token"

    return None


def find_secrets(text):
    """Letak rahasia di dalam teks: daftar (awal, akhir, jenis), urut dari kiri.

    Jenisnya "card", "api_key", atau "token". Dipakai classify di sini dan
    redact di guard/audit.py, supaya hanya ada satu definisi "rahasia". OTP
    tidak ditebak dari teks, karena angka pendek biasa (kode pos, tahun) akan
    ikut terblokir. OTP ditangani lewat field_type.
    """

    if not isinstance(text, str):
        return []

    found = card_spans(text)

    for match in TOKEN_RE.finditer(text):
        kind = key_kind(match.group())

        if kind:
            found.append((match.start(), match.end(), kind))

    spans = []

    for span in sorted(found):
        if not spans or span[0] >= spans[-1][1]:
            spans.append(span)

    return spans


def looks_like_secret(text):
    """Jenis rahasia pertama di dalam teks: "card", "api_key", "token", atau None."""

    spans = find_secrets(text)
    return spans[0][2] if spans else None


def secret_field(field_type):
    if field_type is None:
        return False

    return not isinstance(field_type, str) or field_type.strip().casefold() not in HARMLESS_FIELDS


def classify(action):
    kind = action.kind
    base = ACTION_LEVELS.get(kind) if isinstance(kind, str) else None

    if base is None:
        return RiskVerdict(R3, "unknown_kind")

    reason = kind
    effect = action.effect

    # Efek dari klien hanya bisa menaikkan tingkat risiko, tidak menurunkannya.
    if effect is not None:
        effect_level = ACTION_LEVELS.get(effect) if isinstance(effect, str) else None

        if effect_level is None:
            return RiskVerdict(R3, "unknown_kind")

        if LEVEL_ORDER[effect_level] > LEVEL_ORDER[base]:
            base, reason = effect_level, effect

    # Target diperiksa lebih dulu daripada isi: aplikasi atau situs yang
    # diblokir tetap diblokir, apa pun yang mau dikerjakan di sana.
    if isinstance(action.host, str):
        host = normalize_host(action.host)

        if host is None:
            return RiskVerdict(R3, "bad_host")

        if match_allowed(host, BLOCKED_HOSTS):
            return RiskVerdict(R3, "blocked_host")

    if isinstance(action.app, str) and any(name in action.app.lower() for name in BLOCKED_APPS):
        return RiskVerdict(R3, "blocked_app")

    if secret_field(action.field_type):
        return RiskVerdict(R3, "secret_field")

    secrets = {kind_found for _, _, kind_found in find_secrets(action.text)}

    if secrets & {"card", "api_key"}:
        return RiskVerdict(R3, "secret_text")

    # Memori jangka panjang hanya ditulis dari pesan pengguna sendiri, tidak
    # pernah dari isi halaman, email, atau file (pertahanan racun memori).
    if "memory_store" in (kind, effect) and action.tainted is not False:
        return RiskVerdict(R3, "tainted_memory")

    if base == R1:
        # Nilai yang bukan False (termasuk yang tidak jelas) dihitung sebagai ya.
        if action.submits is not False:
            return RiskVerdict(R2, "submits")

        # Aksi apa pun yang targetnya datang dari isi halaman, email, atau file.
        if action.tainted is not False:
            return RiskVerdict(R2, "tainted_target")

        # Deret acak panjang mungkin kunci, mungkin tautan. Tanya pengguna.
        if "token" in secrets:
            return RiskVerdict(R2, "possible_secret")

    return RiskVerdict(base, reason)
