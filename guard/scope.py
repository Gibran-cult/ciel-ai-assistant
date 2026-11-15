"""Lingkup tugas (docs/security.md bagian 2 dan 3).

Lingkup dibuat sekali dari rencana yang disetujui pengguna: situs, aplikasi,
folder, jenis aksi, dan batas belanja untuk tugas itu. Model tidak bisa
mengubahnya, jadi teks suntikan di halaman tidak bisa menambah kemampuan.

Pemeriksaan jalur di sini bekerja pada teks jalur saja, karena server tidak
punya disk pengguna. Klien desktop mengulangnya dengan jalur nyata (Fase 5).
"""

import ntpath
import posixpath
import re
from dataclasses import dataclass

from guard.domains import match_allowed, normalize_host


@dataclass(frozen=True)
class TaskScope:
    hosts: frozenset = frozenset()     # domain yang boleh disentuh
    apps: frozenset = frozenset()      # nama aplikasi, huruf kecil
    folders: tuple = ()                # folder yang boleh dibaca, jalur absolut
    writable_folders: tuple = ()       # folder yang boleh dibaca dan ditulis
    kinds: frozenset = frozenset()     # jenis aksi yang ada di rencana
    spend_cap: int = 0                 # rupiah; 0 berarti tugas ini tidak boleh belanja


@dataclass(frozen=True)
class ScopeVerdict:
    inside: bool
    reason: str | None   # None, "kind", "host", "app", "path", "path_denied"


INSIDE = ScopeVerdict(True, None)

ALWAYS_INSIDE = frozenset({"ask_user", "finish"})
HOST_PREFIXES = ("tab_", "cart_", "checkout_", "form_", "store_", "order_")
APP_PREFIXES = ("ui_", "app_", "key_", "screen_")
PATH_PREFIXES = ("file_", "folder_")
WRITE_KINDS = frozenset({"file_write", "file_move", "folder_create", "file_delete"})

# Bagian jalur yang tidak pernah boleh disentuh, walau ada di dalam folder
# yang diizinkan: kunci, kredensial, dan folder sistem.
DENIED_PARTS = frozenset({
    ".ssh", ".gnupg", ".aws", "appdata", "windows", "system32",
    "program files", "program files (x86)", "library", "keychains",
})

WINDOWS_STYLE = re.compile(r"^[A-Za-z]:|\\")
DRIVE = re.compile(r"[a-z]:")
SHORT_NAME = re.compile(r"~\d")


def normalized(path):
    """(gaya, jalur) setelah '..' diselesaikan, atau None kalau bukan teks."""

    if not isinstance(path, str) or not path:
        return None

    if WINDOWS_STYLE.search(path):
        return "nt", ntpath.normpath(path).casefold()

    return "posix", posixpath.normpath(path)


def absolute(path):
    """Seperti normalized, tetapi None untuk jalur yang tidak absolut."""

    result = normalized(path)

    if result is None:
        return None

    style, norm = result

    if style == "nt":
        drive, rest = ntpath.splitdrive(norm)
        return result if drive and rest.startswith("\\") else None

    return result if norm.startswith("/") else None


def contains_path(folder, path):
    """Benar kalau path sama dengan folder atau berada di bawahnya."""

    base, target = absolute(folder), absolute(path)

    if base is None or target is None or base[0] != target[0]:
        return False

    separator = "\\" if base[0] == "nt" else "/"
    root = base[1].rstrip(separator) + separator
    return target[1] == base[1] or target[1].startswith(root)


def denied(path):
    result = normalized(path)

    if result is None:
        return False

    parts = [part for part in re.split(r"[\\/]", result[1].casefold()) if part]

    for index, part in enumerate(parts):
        if index == 0 and DRIVE.fullmatch(part):
            continue

        # Windows membuka folder yang sama lewat beberapa ejaan: titik atau
        # spasi di akhir (".ssh."), nama pendek ("SSH~1"), dan alur data
        # (".ssh::$INDEX_ALLOCATION"). Ejaan seperti itu selalu ditolak,
        # karena teks jalurnya tidak lagi menunjukkan folder yang sebenarnya.
        cleaned = part.rstrip(". ")

        if cleaned != part or ":" in part or SHORT_NAME.search(part) or cleaned in DENIED_PARTS:
            return True

    return False


def in_scope(action, scope):
    kind = action.kind

    if isinstance(kind, str) and kind in ALWAYS_INSIDE:
        return INSIDE

    if not isinstance(kind, str) or kind not in scope.kinds:
        return ScopeVerdict(False, "kind")

    if kind.startswith(HOST_PREFIXES):
        host = normalize_host(action.host)

        if host is None or not match_allowed(host, scope.hosts):
            return ScopeVerdict(False, "host")

    elif kind.startswith(APP_PREFIXES):
        app = action.app

        if not isinstance(app, str) or app.lower() not in scope.apps:
            return ScopeVerdict(False, "app")

    elif kind.startswith(PATH_PREFIXES):
        path = action.path

        if denied(path):
            return ScopeVerdict(False, "path_denied")

        folders = scope.writable_folders if kind in WRITE_KINDS else scope.folders + scope.writable_folders

        if not any(contains_path(folder, path) for folder in folders):
            return ScopeVerdict(False, "path")

    return INSIDE
