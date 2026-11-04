"""Memecah jawaban model menjadi segmen yang aman dirender, dan merapikan matematika.

Teks jawaban TIDAK tepercaya. Blok ```ciel-grafik dan ```ciel-kuis berisi JSON
dari model; setiap blok divalidasi ketat, kunci tak dikenal dibuang, dan yang
rusak menjadi `Broken` (alasannya hanya untuk log, tidak pernah ditampilkan
mentah ke pengguna). Rumus grafik hanya divalidasi lewat safe_expr.
"""

import json
import math
import re
from dataclasses import dataclass

from safe_expr import ExpressionError, compile_expression

VISUAL_KINDS = ("fungsi", "batang", "garis", "garis-bilangan", "bangun", "alur")

MAX_GRAFIK = 4
MAX_KUIS = 20
MAX_JSON_CHARS = 4000
MAX_TEXT = 120       # judul, label, satuan: dipotong
MAX_LABEL = 60


@dataclass(frozen=True)
class Markdown:
    text: str


@dataclass(frozen=True)
class Visual:
    spec: dict


@dataclass(frozen=True)
class Quiz:
    soal: str
    pilihan: tuple
    jawaban: "int | str"
    pembahasan: str


@dataclass(frozen=True)
class Broken:
    kind: str     # "grafik" | "kuis"
    reason: str


class _Invalid(ValueError):
    pass


# --------------------------------------------------------------------------- helpers

def _num(value, what):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _Invalid(f"{what}: bukan angka")
    if isinstance(value, float) and not math.isfinite(value):
        raise _Invalid(f"{what}: tidak hingga")
    return value


def _num_or_none(value, what):
    return None if value is None else _num(value, what)


def _text(value, what, limit=MAX_TEXT, required=False):
    if not isinstance(value, str):
        raise _Invalid(f"{what}: bukan teks")
    value = value.strip()
    if required and not value:
        raise _Invalid(f"{what}: kosong")
    return value[:limit]


def _opt_text(spec, key, limit=MAX_TEXT):
    return _text(spec[key], key, limit) if spec.get(key) is not None else ""


def _strict_text(value, what, limit):
    if not isinstance(value, str) or not value.strip():
        raise _Invalid(f"{what}: bukan teks")
    value = value.strip()
    if len(value) > limit:
        raise _Invalid(f"{what}: lebih dari {limit} karakter")
    return value


def _list(value, what, lo, hi):
    if not isinstance(value, list) or not lo <= len(value) <= hi:
        raise _Invalid(f"{what}: harus daftar {lo}-{hi} item")
    return value


def _dict(value, what):
    if not isinstance(value, dict):
        raise _Invalid(f"{what}: bukan objek")
    return value


def _need(spec, key):
    if key not in spec:
        raise _Invalid(f"kunci '{key}' hilang")
    return spec[key]


def _range(value, what):
    pair = [_num(v, what) for v in _list(value, what, 2, 2)]
    return pair


def _points_num(spec):
    raw = spec.get("titik")
    if raw is None:
        return []
    return [_num(v, "titik") for v in _list(raw, "titik", 0, 10)]


# --------------------------------------------------------------------------- grafik

def _fungsi(spec):
    items = _list(_need(spec, "fungsi"), "fungsi", 1, 4)
    funcs = []
    for i, item in enumerate(items):
        item = _dict(item, "fungsi")
        rumus = _text(_need(item, "rumus"), "rumus", 120, required=True)
        try:
            compile_expression(rumus)
        except ExpressionError as exc:
            raise _Invalid(f"rumus ditolak: {exc}") from exc
        label = _text(item["label"], "label", MAX_LABEL) if item.get("label") is not None else ""
        funcs.append({"rumus": rumus, "label": label or f"{'fghk'[i]}(x)"})
    xmin, xmax = _range(_need(spec, "x"), "x")
    if not 0 < xmax - xmin <= 1000:
        raise _Invalid("x: rentang harus 0 < max-min <= 1000")
    y = None
    if spec.get("y") is not None:
        y = _range(spec["y"], "y")
        if not y[0] < y[1]:
            raise _Invalid("y: min harus < max")
    points = []
    for p in _list(spec.get("titik", []), "titik", 0, 10):
        p = _dict(p, "titik")
        points.append({"x": _num(_need(p, "x"), "titik.x"), "y": _num(_need(p, "y"), "titik.y"),
                       "label": _opt_text(p, "label", MAX_LABEL)})
    return {"jenis": "fungsi", "judul": _opt_text(spec, "judul"), "fungsi": funcs,
            "x": [xmin, xmax], "y": y, "titik": points}


def _batang(spec):
    labels = [_text(v, "label", MAX_LABEL, required=True)
              for v in _list(_need(spec, "label"), "label", 1, 12)]
    values = [_num(v, "nilai") for v in _list(_need(spec, "nilai"), "nilai", 1, 12)]
    if len(labels) != len(values):
        raise _Invalid("label dan nilai beda panjang")
    return {"jenis": "batang", "judul": _opt_text(spec, "judul"), "label": labels,
            "nilai": values, "satuan": _opt_text(spec, "satuan", 30)}


def _garis(spec):
    xs = []
    for v in _list(_need(spec, "x"), "x", 1, 50):
        xs.append(_num(v, "x") if not isinstance(v, str) else _text(v, "x", MAX_LABEL))
    series = []
    for s in _list(_need(spec, "seri"), "seri", 1, 4):
        s = _dict(s, "seri")
        values = [_num(v, "nilai") for v in _list(_need(s, "nilai"), "nilai", 1, 50)]
        if len(values) != len(xs):
            raise _Invalid("seri.nilai tidak sepanjang x")
        series.append({"label": _text(_need(s, "label"), "label", MAX_LABEL, required=True),
                       "nilai": values})
    return {"jenis": "garis", "judul": _opt_text(spec, "judul"), "x": xs,
            "seri": series, "satuan": _opt_text(spec, "satuan", 30)}


def _garis_bilangan(spec):
    intervals = []
    for item in _list(_need(spec, "interval"), "interval", 1, 3):
        item = _dict(item, "interval")
        lo = _num_or_none(_need(item, "dari"), "dari")
        hi = _num_or_none(_need(item, "sampai"), "sampai")
        if lo is not None and hi is not None and lo > hi:
            raise _Invalid("interval: dari > sampai")
        closed = []
        for key, bound in (("dari_tutup", lo), ("sampai_tutup", hi)):
            flag = item.get(key, False)
            if not isinstance(flag, bool):
                raise _Invalid(f"{key}: bukan boolean")
            closed.append(flag and bound is not None)   # tak hingga selalu terbuka
        intervals.append({"dari": lo, "sampai": hi, "dari_tutup": closed[0], "sampai_tutup": closed[1]})
    return {"jenis": "garis-bilangan", "judul": _opt_text(spec, "judul"),
            "interval": intervals, "titik": _points_num(spec)}


def _bangun(spec):
    shape = spec.get("bentuk")
    label = lambda src, key, required: (  # noqa: E731
        _strict_text(_need(src, key), key, 20) if required or src.get(key) is not None else "")
    out = {"jenis": "bangun", "judul": _opt_text(spec, "judul"), "bentuk": shape}
    if shape == "segitiga":
        sisi = _dict(_need(spec, "sisi"), "sisi")
        out["sisi"] = {k: label(sisi, k, True) for k in ("a", "b", "c")}
        out["tinggi"] = label(spec, "tinggi", False)
    elif shape == "persegi-panjang":
        out["panjang"] = label(spec, "panjang", True)
        out["lebar"] = label(spec, "lebar", True)
    elif shape == "lingkaran":
        out["jari_jari"] = label(spec, "jari_jari", True)
    else:
        raise _Invalid("bentuk tidak dikenal")
    return out


def _alur(spec):
    steps = [_strict_text(v, "langkah", 60) for v in _list(_need(spec, "langkah"), "langkah", 2, 8)]
    cycle = spec.get("siklus", False)
    if not isinstance(cycle, bool):
        raise _Invalid("siklus: bukan boolean")
    return {"jenis": "alur", "judul": _opt_text(spec, "judul"), "langkah": steps, "siklus": cycle}


_GRAFIK = {"fungsi": _fungsi, "batang": _batang, "garis": _garis,
           "garis-bilangan": _garis_bilangan, "bangun": _bangun, "alur": _alur}


def _reject_constant(name):
    raise _Invalid(f"konstanta JSON tidak valid: {name}")


def _load(body):
    if len(body) > MAX_JSON_CHARS:
        raise _Invalid("JSON terlalu panjang")
    try:
        data = json.loads(body, parse_constant=_reject_constant)
    except (ValueError, RecursionError) as exc:
        raise _Invalid("bukan JSON valid") from exc
    return _dict(data, "blok")


def _parse_grafik(body):
    spec = _load(body)
    kind = spec.get("jenis")
    if not isinstance(kind, str) or kind not in _GRAFIK:
        raise _Invalid("jenis grafik tidak dikenal")
    return Visual(_GRAFIK[kind](spec))


def _parse_kuis(body):
    spec = _load(body)
    soal = _text(_need(spec, "soal"), "soal", 1000, required=True)
    raw = spec.get("pilihan")
    options = ()
    if raw is not None:
        options = tuple(_strict_text(v, "pilihan", 300) for v in _list(raw, "pilihan", 2, 5))
    answer = _need(spec, "jawaban")
    if options:
        if isinstance(answer, bool) or not isinstance(answer, int) or not 0 <= answer < len(options):
            raise _Invalid("jawaban bukan indeks pilihan yang valid")
    else:
        answer = _strict_text(answer, "jawaban", 300)
    return Quiz(soal, options, answer, _opt_text(spec, "pembahasan", 2000))


# --------------------------------------------------------------------------- split

_OPENER = re.compile(r"^```[ \t]*(ciel-grafik|ciel-kuis)[ \t]*\r?$", re.M)
_CLOSER = re.compile(r"^```[ \t]*\r?$", re.M)


def _markdown(text):
    if not text.strip():
        return []
    text = text.strip("\r\n")
    try:
        return [Markdown(tidy_math(text))]
    except Exception:  # noqa: BLE001 - lebih baik teks apa adanya daripada gagal
        return [Markdown(text)]


def parse_answer(text: str) -> list:
    """Pecah jawaban jadi Markdown / Visual / Quiz / Broken berurutan."""
    segments: list = []
    counts = {"grafik": 0, "kuis": 0}
    pos = 0
    while True:
        opener = _OPENER.search(text, pos)
        if not opener:
            segments += _markdown(text[pos:])
            return segments
        segments += _markdown(text[pos:opener.start()])
        kind = opener.group(1).removeprefix("ciel-")
        body_start = opener.end() + 1
        closer = _CLOSER.search(text, body_start)
        if closer:
            body, pos = text[body_start:closer.start()], closer.end()
        else:                                     # tidak pernah ditutup: sampai akhir
            segments.append(Broken(kind, "blok tidak ditutup"))
            return segments
        counts[kind] += 1
        limit = MAX_GRAFIK if kind == "grafik" else MAX_KUIS
        if counts[kind] > limit:
            segments.append(Broken(kind, f"lebih dari {limit} blok {kind}"))
            continue
        try:
            segments.append(_parse_grafik(body) if kind == "grafik" else _parse_kuis(body))
        except _Invalid as exc:
            segments.append(Broken(kind, str(exc)))
        except Exception as exc:  # noqa: BLE001 - teks model tak boleh merusak jawaban
            segments.append(Broken(kind, f"galat tak terduga: {type(exc).__name__}"))


# --------------------------------------------------------------------------- tidy_math

_CODE_FENCE = re.compile(r"^(```|~~~)[^\n]*\n.*?(?:^\1[ \t]*\r?$|\Z)", re.M | re.S)
_INLINE_CODE = re.compile(r"(`+)(?!`)(.+?)(?<!`)\1(?!`)")
_PAREN_MATH = re.compile(r"\\\((.+?)\\\)", re.S)
_BRACKET_MATH = re.compile(r"\\\[(.+?)\\\]", re.S)
_DECIMAL_COMMA = re.compile(r"(?<=\d),(?=\d)")


def _fix_commas(math_text):
    return _DECIMAL_COMMA.sub("{,}", math_text)


def _tidy_line(line, in_display):
    """Rapikan satu baris di luar kode. Mengembalikan (baris, masih_di_dalam_$$)."""
    out = []
    i, n = 0, len(line)
    if in_display:
        close = line.find("$$")
        if close == -1:
            return _fix_commas(line), True
        out.append(_fix_commas(line[:close]) + "$$")
        i = close + 2
    while i < n:
        c = line[i]
        if c == "\\" and i + 1 < n:
            out.append(line[i:i + 2])
            i += 2
        elif line.startswith("$$", i):
            j = line.find("$$", i + 2)
            if j == -1:
                out.append("$$" + _fix_commas(line[i + 2:]))
                return "".join(out), True
            out.append("$$" + _fix_commas(line[i + 2:j]) + "$$")
            i = j + 2
        elif c == "$":
            j = _find_closer(line, i + 1)
            body = line[i + 1:j] if j != -1 else ""
            valid = j != -1 and body.strip() and not body[0].isspace() and not body[-1].isspace()
            if valid:
                out.append("$" + _fix_commas(body) + "$")
                i = j + 1
            elif j == -1 or (i + 1 < n and line[i + 1].isdigit()):
                out.append("\\$")      # mata uang, atau $ yatim di baris ganjil
                i += 1
            else:
                out.append("$")
                i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out), False


def _find_closer(line, start):
    k = start
    while k < len(line):
        if line[k] == "\\":
            k += 2
        elif line[k] == "$":
            return k
        else:
            k += 1
    return -1


def _tidy_prose(chunk):
    chunk = chunk.replace("\x00", "")   # NUL dipakai sebagai penanda; buang dari teks model
    stash: list[str] = []

    def hide(match):
        stash.append(match.group(0))
        return f"\x00{len(stash) - 1}\x00"

    chunk = _INLINE_CODE.sub(hide, chunk)
    chunk = _PAREN_MATH.sub(lambda m: "$" + m.group(1).strip() + "$", chunk)
    chunk = _BRACKET_MATH.sub(lambda m: "$$" + m.group(1).strip() + "$$", chunk)
    lines, in_display, result = chunk.split("\n"), False, []
    for line in lines:
        line, in_display = _tidy_line(line, in_display)
        result.append(line)
    chunk = "\n".join(result)
    return re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m.group(1))], chunk)


def tidy_math(markdown: str) -> str:
    """Samakan delimiter matematika dan lindungi $ mata uang, di luar blok kode."""
    out, pos = [], 0
    for fence in _CODE_FENCE.finditer(markdown):
        out.append(_tidy_prose(markdown[pos:fence.start()]))
        out.append(fence.group(0))
        pos = fence.end()
    out.append(_tidy_prose(markdown[pos:]))
    return "".join(out)
