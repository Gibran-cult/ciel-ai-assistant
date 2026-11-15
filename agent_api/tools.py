"""Skema tool dan pengikatannya ke aksi guard (docs/agent-architecture.md bagian 3).

Model hanya menyebut nama tool dan argumennya. Semua yang menentukan risiko
(host tab, jenis kolom, apakah tombol mengirim data, efek tombol) diambil
dari pengamatan klien, tidak dari model. Jadi model yang terpancing tidak
bisa mengaku sedang berada di situs yang diizinkan, atau menyebut kolom
kata sandi sebagai kolom teks.

Tool desktop dan tool belanja belum ada di sini. Keduanya masuk bersama
klien yang menjalankannya (Fase 4 dan 5).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

from guard.domains import check_url, normalize_host
from guard.risk import Action


@dataclass(frozen=True)
class Control:
    """Satu kontrol bernomor di halaman, seperti yang dilaporkan klien."""

    field_type: str | None = None   # jenis kolom isian, misalnya "text" atau "password"
    submits: bool = False           # klik atau ketik di sini mengirim data
    effect: str | None = None       # efek tombol sebagai jenis aksi, misalnya "cart_add"


@dataclass(frozen=True)
class Observation:
    """Hasil satu aksi dari klien."""

    ok: bool
    source: str = "tool"            # salah satu envelope.SOURCES
    text: str = ""                  # isi yang terbaca, tidak tepercaya
    host: str | None = None         # host tab saat ini
    controls: Mapping = field(default_factory=dict)   # nomor rujukan -> Control


@dataclass(frozen=True)
class Bound:
    tool: str
    args: dict
    action: Action


@dataclass(frozen=True)
class Rejected:
    tool: str
    reason: str   # "bad_call" | "tool_unavailable" | "bad_args" | "no_page" | "unknown_ref"


# Nama tool -> argumen. Setiap argumen: ("text", panjang maksimal),
# ("int",), atau ("choice", pilihan).
TOOLS = {
    "ask_user": {"question": ("text", 500)},
    "finish": {"report": ("text", 2000)},
    "tab_read": {},
    "tab_close": {},
    "tab_open": {"url": ("text", 2000)},
    "tab_scroll": {"direction": ("choice", ("up", "down"))},
    "tab_click": {"ref": ("int",)},
    "form_submit": {"ref": ("int",)},
    "tab_type": {"ref": ("int",), "text": ("text", 2000)},
    "tab_select": {"ref": ("int",), "value": ("text", 200)},
}

NO_PAGE_NEEDED = frozenset({"ask_user", "finish", "tab_open"})
TYPING = {"tab_type": "text", "tab_select": "value"}   # tool -> argumen yang berisi teks ketikan
MAX_TOOL_NAME = 40


def fits(value, rule):
    if rule[0] == "text":
        return isinstance(value, str) and 0 < len(value) <= rule[1]

    if rule[0] == "int":
        return type(value) is int

    return isinstance(value, str) and value in rule[1]


def bind(call, page):
    """Ubah usulan model menjadi aksi untuk guard, atau tolak dengan satu alasan."""

    if not isinstance(call, dict) or set(call) != {"tool", "args"} or not isinstance(call["tool"], str):
        return Rejected("unknown", "bad_call")

    tool, args = call["tool"], call["args"]
    schema = TOOLS.get(tool)

    if schema is None:
        return Rejected(tool[:MAX_TOOL_NAME], "tool_unavailable")

    if not isinstance(args, dict) or set(args) != set(schema):
        return Rejected(tool, "bad_args")

    if not all(fits(args[name], rule) for name, rule in schema.items()):
        return Rejected(tool, "bad_args")

    if tool in ("ask_user", "finish"):
        return Bound(tool, args, Action(kind=tool))

    if tool == "tab_open":
        target = check_url(args["url"])

        if target.problem:
            return Rejected(tool, "bad_args")

        return Bound(tool, args, Action(kind=tool, host=target.host))

    # Tool lain bekerja di tab yang sedang terbuka. Host-nya dari klien.
    host = normalize_host(page.host) if isinstance(page, Observation) and page.ok is True else None

    if host is None:
        return Rejected(tool, "no_page")

    if "ref" not in schema:
        return Bound(tool, args, Action(kind=tool, host=host))

    controls = page.controls
    control = controls.get(args["ref"]) if isinstance(controls, Mapping) else None

    if not isinstance(control, Control):
        return Rejected(tool, "unknown_ref")

    typed = TYPING.get(tool)
    field_type = None

    if typed:
        # Jenis kolom yang tidak dilaporkan dihitung sebagai kolom rahasia oleh guard.
        field_type = control.field_type if isinstance(control.field_type, str) else "unknown"

    action = Action(
        kind=tool, host=host, text=args[typed] if typed else None, field_type=field_type,
        submits=control.submits is not False, effect=control.effect,
    )
    return Bound(tool, args, action)
