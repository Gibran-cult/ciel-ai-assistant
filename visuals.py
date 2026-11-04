"""Menggambar spec grafik/diagram jawaban (answer_blocks.Visual.spec) dengan matplotlib.

Di layar: SVG yang warnanya variabel CSS (--c-*), jadi tema terang/gelap berganti
tanpa render ulang. Untuk ekspor: PNG berpalet terang. Memakai Figure langsung
(bukan pyplot) agar aman antar-thread Streamlit; matplotlib diimpor malas.
"""

import functools
import hashlib
import io
import json
import re
import textwrap
import threading
from xml.sax.saxutils import quoteattr

import numpy as np

from safe_expr import compile_expression

# Token terang dari app.py (LIGHT_TOKENS). --c-line-strong aslinya rgba(22,21,19,.18).
LIGHT = {"text": "#161513", "muted": "#4b4a46", "axis": "#1615132e", "s1": "#2b4886",
         "s2": "#2e6a4c", "s3": "#855a00", "s4": "#a33b2c", "fill": "#e6e6e2", "bg": "#fbfbf9"}
SENTINEL = {"text": "#010101", "axis": "#020202", "s1": "#030303", "s2": "#040404",
            "s3": "#050505", "s4": "#060606", "fill": "#070707", "muted": "#080808", "bg": "none"}
_CSS_VAR = {"#010101": "var(--c-text)", "#020202": "var(--c-line-strong)", "#030303": "var(--c-accent)",
            "#040404": "var(--c-ok)", "#050505": "var(--c-warn)", "#060606": "var(--c-err)",
            "#070707": "var(--c-raised)", "#080808": "var(--c-muted)"}
SERIES = ("s1", "s2", "s3", "s4")
WIDTH_IN = 6.4
NOT_TO_SCALE = "(tidak sesuai skala)"

_init_lock = threading.Lock()
_ready = False


def _mpl():
    """Impor malas matplotlib; setel rcParams global sekali (teks SVG tetap teks)."""
    global _ready
    import matplotlib
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    if not _ready:
        with _init_lock:
            # Sengaja global dan disetel sekali: rc_context juga tidak aman antar-thread,
            # dan visuals.py satu-satunya pemakai matplotlib di aplikasi ini.
            matplotlib.rcParams["svg.fonttype"] = "none"
            _ready = True
    return Figure, FigureCanvasAgg


def _g(v):
    return f"{v:.10g}"


def _t(text):
    """Teks pengguna tidak boleh ditafsirkan sebagai mathtext."""
    return str(text).replace("$", r"\$")


# --------------------------------------------------------------------------- alt text

def _ends(i):
    lo, hi = i["dari"], i["sampai"]
    left = "tak hingga" if lo is None else f"{_g(lo)}{' (termasuk)' if i['dari_tutup'] else ''}"
    right = "tak hingga" if hi is None else f"{_g(hi)}{' (termasuk)' if i['sampai_tutup'] else ''}"
    return f"dari {left} sampai {right}"


def _checked(fn):
    """Spec tak valid (bukan dict, jenis asing, kunci hilang) selalu jadi ValueError berbahasa Indonesia."""
    @functools.wraps(fn)
    def wrapper(spec, *args, **kwargs):
        if not isinstance(spec, dict):
            raise ValueError("Spesifikasi visual tidak valid: harus berupa objek.")
        if not isinstance(spec.get("jenis"), str) or spec["jenis"] not in _KINDS:
            raise ValueError("Spesifikasi visual tidak valid: jenis tidak dikenal.")
        try:
            return fn(spec, *args, **kwargs)
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"Spesifikasi visual tidak valid: {exc!r}") from exc
    return wrapper


_KINDS = ("fungsi", "batang", "garis", "garis-bilangan", "bangun", "alur")


@_checked
def describe(spec):
    """Teks alternatif berbahasa Indonesia. Spec tak valid -> ValueError."""
    kind, judul = spec["jenis"], spec.get("judul") or ""
    pre = f"{judul}. " if judul and kind != "fungsi" else ""
    if kind == "fungsi":
        name = judul or ", ".join(f"{f['label']} = {f['rumus']}" for f in spec["fungsi"])
        return f"Grafik fungsi {name} untuk x dari {_g(spec['x'][0])} sampai {_g(spec['x'][1])}"
    if kind == "batang":
        unit = f" ({spec['satuan']})" if spec["satuan"] else ""
        return pre + "Diagram batang: " + ", ".join(f"{a} {_g(b)}" for a, b in zip(spec["label"], spec["nilai"])) + unit
    if kind == "garis":
        return pre + "Grafik garis " + ", ".join(s["label"] for s in spec["seri"]) + \
            " terhadap " + ", ".join(_g(x) if not isinstance(x, str) else x for x in spec["x"])
    if kind == "garis-bilangan":
        return pre + "Garis bilangan dengan interval " + "; ".join(_ends(i) for i in spec["interval"])
    if kind == "bangun":
        shape = spec["bentuk"]
        if shape == "segitiga":
            return pre + "Segitiga dengan sisi " + ", ".join(f"{k} = {v}" for k, v in spec["sisi"].items())
        if shape == "persegi-panjang":
            return pre + f"Persegi panjang dengan panjang {spec['panjang']} dan lebar {spec['lebar']}"
        return pre + f"Lingkaran dengan jari-jari {spec['jari_jari']}"
    steps = " → ".join(spec["langkah"])
    return pre + ("Diagram alur siklus: " + steps + " → kembali ke awal" if spec["siklus"]
                  else "Diagram alur: " + steps)


# --------------------------------------------------------------------------- fungsi

def _curve_segments(xs, ys):
    """Pecah kurva di nan dan di lompatan (asimtot); nilai besar tapi hingga ikut ditangani."""
    ys = np.where(np.isfinite(ys), ys, np.nan)
    good = ys[np.isfinite(ys)]
    if good.size == 0:
        return []
    lo, hi = np.percentile(good, [2, 98])
    span = max(float(hi - lo), 1e-9)
    cut = np.zeros(len(ys), dtype=bool)               # cut[i]: putus antara i dan i+1
    d = np.abs(np.diff(ys))
    with np.errstate(invalid="ignore"):
        pole = (np.sign(ys[:-1]) != np.sign(ys[1:])) & (np.maximum(np.abs(ys[:-1]), np.abs(ys[1:])) > span)
        cut[:-1] = ~np.isfinite(d) | (d > 10 * span) | pole
    segs, start = [], 0
    for i in range(len(ys)):
        if i == len(ys) - 1 or cut[i]:
            sx, sy = xs[start:i + 1], ys[start:i + 1]
            keep = np.isfinite(sy)
            if keep.any():
                segs.append((sx[keep], sy[keep]))
            start = i + 1
    return segs


def _draw_fungsi(fig, ax, spec, pal):
    x0, x1 = spec["x"]
    xs = np.linspace(x0, x1, 600)
    curves = []
    for fn in spec["fungsi"]:
        with np.errstate(all="ignore"):
            ys = np.asarray(compile_expression(fn["rumus"])(xs), dtype=float)
        curves.append(np.broadcast_to(ys, xs.shape) if ys.shape != xs.shape else ys)
    allv = np.concatenate([c[np.isfinite(c)] for c in curves])
    if allv.size == 0:
        ax.text(0.5, 0.5, "Tidak ada nilai real pada selang ini", transform=ax.transAxes,
                ha="center", va="center", color=pal["muted"], fontsize=10)
    if spec["y"]:
        y0, y1 = spec["y"]
    else:
        if allv.size == 0:
            y0, y1 = -1.0, 1.0
        else:
            y0, y1 = np.percentile(allv, [2, 98])
            for p in spec["titik"]:
                y0, y1 = min(y0, p["y"]), max(y1, p["y"])
            if y1 - y0 < 1e-9:
                y0, y1 = y0 - 1, y1 + 1
            pad = (y1 - y0) * 0.1
            y0, y1 = y0 - pad, y1 + pad
    for i, (fn, ys) in enumerate(zip(spec["fungsi"], curves)):
        first = True
        for sx, sy in _curve_segments(xs, ys):
            ax.plot(sx, sy, color=pal[SERIES[i % 4]], lw=2, label=_t(fn["label"]) if first else None,
                    solid_capstyle="round")
            first = False
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    for pt in spec["titik"]:
        ax.plot([pt["x"]], [pt["y"]], "o", color=pal["text"], ms=5, zorder=5)
        if pt["label"]:
            ax.annotate(_t(pt["label"]), (pt["x"], pt["y"]), xytext=(6, 7), textcoords="offset points",
                        color=pal["text"], fontsize=9)
    for side, pos in (("bottom", y0 <= 0 <= y1), ("left", x0 <= 0 <= x1)):
        if pos:
            ax.spines[side].set_position("zero")
    ax.grid(True, color=pal["axis"], lw=0.6)
    if ax.get_legend_handles_labels()[0] and (len(curves) > 1 or not spec["judul"]):
        ax.legend(frameon=False, labelcolor=pal["text"], loc="best", fontsize=9)


# --------------------------------------------------------------------------- batang / garis

def _draw_batang(fig, ax, spec, pal):
    labels, values = spec["label"], spec["nilai"]
    bars = ax.bar(range(len(values)), values, color=pal["s1"], width=0.6)
    ax.bar_label(bars, labels=[_g(v) for v in values], color=pal["text"], fontsize=9, padding=2)
    ax.set_xticks(range(len(values)), [_t(s) for s in labels])
    if len(labels) > 6 or max(len(s) for s in labels) > 8:
        for tick in ax.get_xticklabels():
            tick.set_rotation(30)
            tick.set_horizontalalignment("right")
    ax.margins(y=0.15)
    if spec["satuan"]:
        ax.set_ylabel(_t(spec["satuan"]), color=pal["text"])
    ax.grid(True, axis="y", color=pal["axis"], lw=0.6)
    ax.set_axisbelow(True)
    ax.axhline(0, color=pal["muted"], lw=1)


def _draw_garis(fig, ax, spec, pal):
    cats = any(isinstance(v, str) for v in spec["x"])
    xs = list(range(len(spec["x"]))) if cats else spec["x"]
    for i, s in enumerate(spec["seri"]):
        ax.plot(xs, s["nilai"], "-o", color=pal[SERIES[i]], lw=2, ms=5, label=_t(s["label"]))
    if cats:
        ax.set_xticks(xs, [_t(v) for v in spec["x"]])
    if len(spec["seri"]) > 1:
        ax.legend(frameon=False, labelcolor=pal["text"], fontsize=9)
    ylabel = _t(spec["seri"][0]["label"] if len(spec["seri"]) == 1 else "")
    if spec["satuan"]:
        ylabel = f"{ylabel} ({_t(spec['satuan'])})" if ylabel else _t(spec["satuan"])
    if ylabel:
        ax.set_ylabel(ylabel, color=pal["text"])
    ax.grid(True, color=pal["axis"], lw=0.6)
    ax.set_axisbelow(True)


# --------------------------------------------------------------------------- garis bilangan

def _draw_bilangan(fig, ax, spec, pal):
    marks = [v for i in spec["interval"] for v in (i["dari"], i["sampai"]) if v is not None] + list(spec["titik"])
    lo, hi = (min(marks), max(marks)) if marks else (-1.0, 1.0)
    if 0 not in marks and lo < 0 < hi:
        marks.append(0)
    span = max(hi - lo, 2.0)
    xl, xr = lo - span * 0.45, hi + span * 0.45
    ax.set_xlim(xl, xr)
    ax.set_ylim(-1, 1.4)
    ax.yaxis.set_visible(False)
    for side in ("left", "top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_position(("data", 0))
    ax.spines["bottom"].set_color(pal["muted"])
    ax.spines["bottom"].set_linewidth(1.5)
    ax.plot([1], [0], ">", color=pal["muted"], transform=ax.get_yaxis_transform(), clip_on=False)
    ax.plot([0], [0], "<", color=pal["muted"], transform=ax.get_yaxis_transform(), clip_on=False)
    ticks = sorted({round(float(m), 10) for m in marks})
    ax.set_xticks(ticks, [_g(t) for t in ticks])
    ax.tick_params(axis="x", colors=pal["text"], labelsize=10, pad=8)
    for iv in spec["interval"]:
        a = xl if iv["dari"] is None else iv["dari"]
        b = xr if iv["sampai"] is None else iv["sampai"]
        ax.plot([a, b], [0, 0], color=pal["s1"], lw=6, alpha=0.55, solid_capstyle="butt", zorder=3)
        for val, closed in ((iv["dari"], iv["dari_tutup"]), (iv["sampai"], iv["sampai_tutup"])):
            if val is not None:
                ax.plot([val], [0], "o", ms=11, mec=pal["s1"], mew=2, zorder=6,
                        mfc=pal["s1"] if closed else pal["fill"])
    for p in spec["titik"]:
        ax.plot([p], [0], "o", ms=6, color=pal["text"], zorder=7)


# --------------------------------------------------------------------------- bangun

def _label(ax, pal, xy, text, **kw):
    if text:
        ax.text(*xy, _t(text), color=pal["text"], fontsize=11, ha="center", va="center", **kw)


def _draw_bangun(fig, ax, spec, pal):
    from matplotlib.patches import Circle, Polygon, Rectangle
    style = dict(fc=pal["fill"], ec=pal["s1"], lw=2.2)
    shape = spec["bentuk"]
    if shape == "segitiga":
        ax.add_patch(Polygon([(0, 0), (5, 0), (1.6, 3)], closed=True, **style))
        _label(ax, pal, (2.5, -0.4), spec["sisi"]["a"])
        _label(ax, pal, (0.35, 1.7), spec["sisi"]["b"])
        _label(ax, pal, (3.8, 1.8), spec["sisi"]["c"])
        if spec["tinggi"]:
            ax.plot([1.6, 1.6], [0, 3], "--", color=pal["muted"], lw=1.3)
            ax.add_patch(Rectangle((1.6, 0), 0.22, 0.22, fc="none", ec=pal["muted"], lw=1.1))
            _label(ax, pal, (1.15, 1.2), spec["tinggi"])
        ax.set_xlim(-1.4, 6.0)
        ax.set_ylim(-1.0, 3.5)
    elif shape == "persegi-panjang":
        ax.add_patch(Rectangle((0, 0), 5, 3, **style))
        _label(ax, pal, (2.5, -0.5), spec["panjang"])
        _label(ax, pal, (5.9, 1.5), spec["lebar"])
        ax.set_xlim(-0.8, 7.0)
        ax.set_ylim(-1.1, 3.5)
    else:
        ax.add_patch(Circle((0, 0), 2, **style))
        ax.plot([0, 2], [0, 0], color=pal["muted"], lw=1.6)
        ax.plot([0], [0], "o", color=pal["text"], ms=5)
        _label(ax, pal, (1.0, 0.35), spec["jari_jari"])
        ax.set_xlim(-2.8, 2.8)
        ax.set_ylim(-2.5, 2.5)
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.text(1, 0, NOT_TO_SCALE, transform=ax.transAxes, ha="right", va="bottom", fontsize=8, color=pal["muted"])


# --------------------------------------------------------------------------- alur

def _wrap(text, width):
    return "\n".join(textwrap.wrap(_t(text), width=width, break_long_words=True) or [""])


def _box(ax, pal, cx, cy, w, h, text):
    from matplotlib.patches import FancyBboxPatch
    patch = FancyBboxPatch((cx - w / 2, cy - h / 2), w, h, boxstyle="round,pad=0,rounding_size=0.14",
                           fc=pal["fill"], ec=pal["s1"], lw=1.8, zorder=3)
    ax.add_patch(patch)
    ax.text(cx, cy, text, ha="center", va="center", fontsize=10, color=pal["text"], zorder=4, linespacing=1.15)
    return patch


def _arrow(ax, pal, a, b, pa, pb, rad=0.0):
    from matplotlib.patches import FancyArrowPatch
    ax.add_patch(FancyArrowPatch(a, b, patchA=pa, patchB=pb, arrowstyle="-|>", mutation_scale=14,
                                 connectionstyle=f"arc3,rad={rad}", color=pal["muted"], lw=1.6,
                                 shrinkA=3, shrinkB=3, zorder=2))


def _draw_alur(fig, ax, spec, pal):
    steps, n = spec["langkah"], len(spec["langkah"])
    ax.set_axis_off()
    ax.set_aspect("equal")
    if spec["siklus"]:
        w = 1.75
        texts = [_wrap(s, 12) for s in steps]
        h = 0.3 + 0.2 * max(t.count("\n") + 1 for t in texts)
        rx, ry = (2.5, 1.9) if n > 3 else (2.2, 1.5)
        pts = [(rx * np.sin(2 * np.pi * i / n), ry * np.cos(2 * np.pi * i / n)) for i in range(n)]
        patches = [_box(ax, pal, x, y, w, h, t) for (x, y), t in zip(pts, texts)]
        for i in range(n):
            j = (i + 1) % n
            _arrow(ax, pal, pts[i], pts[j], patches[i], patches[j], rad=-0.25 if n > 2 else -0.5)
        ax.set_xlim(-rx - w / 2 - 0.2, rx + w / 2 + 0.2)
        ax.set_ylim(-ry - h / 2 - 0.2, ry + h / 2 + 0.2)
    elif n <= 4:
        texts = [_wrap(s, max(8, int((WIDTH_IN * 0.92 / n - 0.55) * 10))) for s in steps]
        h = 0.4 + 0.2 * max(t.count("\n") + 1 for t in texts)
        w, gap = 1.9, 0.6
        xs = [i * (w + gap) for i in range(n)]
        patches = [_box(ax, pal, x, 0, w, h, t) for x, t in zip(xs, texts)]
        for i in range(n - 1):
            _arrow(ax, pal, (xs[i], 0), (xs[i + 1], 0), patches[i], patches[i + 1])
        ax.set_xlim(-w / 2 - 0.1, xs[-1] + w / 2 + 0.1)
        ax.set_ylim(-h / 2 - 0.1, h / 2 + 0.1)
    else:
        texts = [_wrap(s, 28) for s in steps]
        h = 0.3 + 0.2 * max(t.count("\n") + 1 for t in texts)
        w, gap = 4.2, 0.45
        ys = [-i * (h + gap) for i in range(n)]
        patches = [_box(ax, pal, 0, y, w, h, t) for y, t in zip(ys, texts)]
        for i in range(n - 1):
            _arrow(ax, pal, (0, ys[i]), (0, ys[i + 1]), patches[i], patches[i + 1])
        ax.set_xlim(-w / 2 - 0.1, w / 2 + 0.1)
        ax.set_ylim(ys[-1] - h / 2 - 0.1, h / 2 + 0.1)


# --------------------------------------------------------------------------- figure

_DRAW = {"fungsi": _draw_fungsi, "batang": _draw_batang, "garis": _draw_garis,
         "garis-bilangan": _draw_bilangan, "bangun": _draw_bangun, "alur": _draw_alur}
_HEIGHT = {"fungsi": 3.8, "batang": 3.6, "garis": 3.6, "garis-bilangan": 2.0, "bangun": 3.4}


def _height(spec):
    if spec["jenis"] != "alur":
        return _HEIGHT[spec["jenis"]]
    n = len(spec["langkah"])
    return 5.2 if spec["siklus"] else (2.0 if n <= 4 else min(1.0 + 0.62 * n, 6.4))


@_checked
def build_figure(spec, palette):
    """Gambar spec ke Figure baru (tanpa pyplot). `palette` berisi kunci seperti LIGHT.

    Spec tak valid -> ValueError (pesan Indonesia)."""
    Figure, FigureCanvasAgg = _mpl()
    pal = dict(palette)
    kind = spec["jenis"]
    fig = Figure(figsize=(WIDTH_IN, _height(spec)), dpi=100, layout="constrained")
    FigureCanvasAgg(fig)
    fig.set_facecolor(pal["bg"])
    ax = fig.add_subplot()
    ax.set_facecolor("none")
    if kind in ("fungsi", "batang", "garis"):
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("bottom", "left"):
            ax.spines[side].set_color(pal["muted"])
        ax.tick_params(colors=pal["text"], labelsize=9)
    _DRAW[kind](fig, ax, spec, pal)
    if spec.get("judul"):
        ax.set_title(_t(spec["judul"]), color=pal["text"], fontsize=12, fontweight="bold", pad=10)
    return fig


@_checked
def render_png(spec, width_px=1200):
    """PNG berpalet terang. Spec tak valid -> ValueError."""
    fig = build_figure(spec, LIGHT)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=width_px / WIDTH_IN, facecolor=LIGHT["bg"])
    return buf.getvalue()


def _svg_unique_ids(svg, spec):
    """Beberapa SVG di satu halaman tidak boleh berbagi id (clipPath, marker)."""
    salt = "v" + hashlib.sha1(json.dumps(spec, sort_keys=True, default=str).encode()).hexdigest()[:8] + "-"
    for old in sorted(set(re.findall(r'\bid="([^"]+)"', svg)), key=len, reverse=True):
        svg = svg.replace(f'id="{old}"', f'id="{salt}{old}"').replace(f"#{old})", f"#{salt}{old})")
        svg = svg.replace(f'href="#{old}"', f'href="#{salt}{old}"')
    return svg


@_checked
def render_svg(spec):
    """SVG bertema variabel CSS. Spec tak valid -> ValueError."""
    fig = build_figure(spec, SENTINEL)
    buf = io.BytesIO()
    fig.savefig(buf, format="svg", transparent=True, metadata={"Date": None, "Creator": "Ciel"})
    svg = buf.getvalue().decode("utf-8")
    svg = svg[svg.index("<svg"):]
    svg = re.sub(r"<style[^>]*>.*?</style>", "", svg, flags=re.S)   # '*{...}' bocor ke halaman
    svg = re.sub(r"<metadata>.*?</metadata>", "", svg, flags=re.S)
    svg = re.sub(r'font:\s*([\d.]+)px\s*[^;"]*', r"font-size: \1px; font-family: inherit", svg)
    svg = re.sub(r"#0[0-8]0[0-8]0[0-8]", lambda m: _CSS_VAR.get(m.group(0), m.group(0)), svg)
    svg = _svg_unique_ids(svg, spec)
    root = re.match(r"<svg\b[^>]*>", svg).group(0)
    new_root = re.sub(r'\s(width|height)="[^"]*"', "", root)
    new_root = new_root[:-1] + f' width="100%" role="img" aria-label={quoteattr(describe(spec))}>'
    return new_root + svg[len(root):]
