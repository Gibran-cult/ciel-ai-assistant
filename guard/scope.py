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

    def __post_init__(self):
        # Lingkup dibuat kode server. Tipe yang salah adalah bug di sana, dan
        # harus ketahuan saat lingkup dibuat: kinds="tab_read" (teks, bukan
        # frozenset) akan diam-diam cocok dengan potongan teks apa pun.
        for name in ("hosts", "apps", "kinds"):
            value = getattr(self, name)

            if not isinstance(value, frozenset) or not all(isinstance(item, str) for item in value):
                raise TypeError(f"{name} harus frozenset berisi teks")

        for name in ("folders", "writable_folders"):
            value = getattr(self, name)

            if not isinstance(value, tuple) or not all(isinstance(item, str) for item in value):
                raise TypeError(f"{name} harus tuple berisi teks")

        if type(self.spend_cap) is not int:
            raise TypeError("spend_cap harus int rupiah")


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
DENIED_ANYWHERE = frozenset({
    ".ssh", ".gnupg", ".aws", ".kube", ".docker", ".config", ".mozilla", ".netrc",
    ".git-credentials", "appdata", "system32", "keychains", "ntuser.dat",
})

# Nama yang hanya terlarang di pangkal drive atau pangkal sistem berkas.
# Folder "Library" atau "windows" di dalam folder tugas pengguna itu biasa.
DENIED_AT_ROOT = frozenset({
    "windows", "program files", "program files (x86)", "programdata", "etc", "library",
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

    style = result[0]
    parts = [part for part in re.split(r"[\\/]", result[1].casefold()) if part]

    if parts and DRIVE.fullmatch(parts[0]):
        parts = parts[1:]

    for index, part in enumerate(parts):
        # Windows membuka folder yang sama lewat beberapa ejaan: titik atau
        # spasi di akhir (".ssh."), nama pendek ("SSH~1"), dan alur data
        # (".ssh::$INDEX_ALLOCATION"). Ejaan seperti itu selalu ditolak,
        # karena teks jalurnya tidak lagi menunjukkan folder yang sebenarnya.
        cleaned = part.rstrip(". ")

        if cleaned != part or ":" in part or SHORT_NAME.search(part) or cleaned in DENIED_ANYWHERE:
            return True

        if index == 0 and cleaned in DENIED_AT_ROOT:
            return True

        # ~/Library di macOS: kunci, profil browser, dan data aplikasi.
        if style == "posix" and index == 2 and parts[0] == "users" and cleaned == "library":
            return True

    return False


def in_scope(action, scope):
    kind = action.kind

    if isinstance(kind, str) and kind in ALWAYS_INSIDE:
        return INSIDE

    if not isinstance(kind, str) or kind not in scope.kinds:
        return ScopeVerdict(False, "kind")

    # Efek aksi (misalnya klik yang menambah barang ke keranjang) juga harus
    # ada di rencana yang disetujui pengguna.
    effect = action.effect

    if effect is not None and (not isinstance(effect, str) or effect not in scope.kinds):
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

    # Jalur tujuan diperiksa seperti jalur tulis. Pindah file wajib punya
    # tujuan: tanpa itu file bisa dipindah keluar dari folder tugas, atau
    # masuk ke folder yang dijalankan sistem saat laptop menyala.
    dest = action.dest

    if dest is not None or kind == "file_move":
        if denied(dest):
            return ScopeVerdict(False, "path_denied")

        if not any(contains_path(folder, dest) for folder in scope.writable_folders):
            return ScopeVerdict(False, "path")

    return INSIDE
