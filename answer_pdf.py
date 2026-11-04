"""Ekspor jawaban Ciel ke PDF (A4) dan ke gambar PNG untuk dibagikan.

Fungsi murni: teks jawaban masuk, bytes keluar. fpdf2, pypdfium2 dan
matplotlib baru diimpor saat dipakai, jadi mengimpor modul ini murah.
Font: DejaVu Sans dari paket matplotlib (tanpa unduhan). Karakter yang tidak
ada di font (emoji, aksara lain) diganti "?" supaya tidak pernah error.
"""

import datetime
import io
import re
from functools import lru_cache
from pathlib import Path

from answer_blocks import Broken, Markdown, Quiz, Visual, parse_answer
from chat_sources import answer_parts
from riset_export import inline_runs

DOMAIN = "ciel-ai.web.id"
DEFAULT_TITLE = "Jawaban Ciel"
SPILL_NOTE = "Lanjutan ada di chat Ciel."
BROKEN_NOTE = "(grafik tidak bisa ditampilkan)"
MONTHS = ("Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
          "Agustus", "September", "Oktober", "November", "Desember")

PNG_WIDTH_PX = 1080
PNG_PAGE_MM = (120, 600)
PNG_MARGIN_PX = 40
VISUAL_MM = 150
BODY_PT = 11
INK = (28, 31, 38)
MUTED = (107, 114, 128)
ACCENT = (37, 99, 235)
RULE = (209, 213, 219)
TINT = (230, 230, 226)   # latar callout (--c-raised terang)

_DOCUMENT_WORDS = re.compile(
    r"\b(pdf|cetak|dicetak|print|printable|lembar (soal|latihan|kerja)|worksheet|handout|modul)\b",
    re.IGNORECASE,
)


def wants_document(request):
    return bool(_DOCUMENT_WORDS.search(str(request or "")))


def document_title(content, request):
    match = re.search(r"^#[ \t]+(.+?)\s*$", str(content or ""), re.MULTILINE)
    if match:
        return match.group(1).strip()
    words = str(request or "").split()
    title = ""
    for word in words:
        if len(f"{title} {word}".strip()) > 60:
            break
        title = f"{title} {word}".strip()
    return title or DEFAULT_TITLE


def indonesian_date(day=None):
    day = day or datetime.date.today()
    return f"{day.day} {MONTHS[day.month - 1]} {day.year}"


# --------------------------------------------------------------------------- LaTeX -> teks

SYMBOLS = {
    "times": "×", "cdot": "·", "div": "÷", "pm": "±", "le": "≤", "leq": "≤", "ge": "≥", "geq": "≥",
    "ne": "≠", "neq": "≠", "approx": "≈", "pi": "π", "infty": "∞", "theta": "θ", "alpha": "α",
    "beta": "β", "gamma": "γ", "delta": "δ", "Delta": "Δ", "lambda": "λ", "mu": "μ", "sigma": "σ",
    "Sigma": "Σ", "omega": "ω", "Omega": "Ω", "phi": "φ", "int": "∫", "sum": "Σ", "lim": "lim",
    "to": "→", "rightarrow": "→", "in": "∈", "circ": "°", "ldots": "…", "dots": "…",
    "cdots": "…", "mp": "∓", "equiv": "≡", "sim": "~", "angle": "∠", "perp": "⊥", "parallel": "∥",
}
DROP_COMMANDS = ("text", "mathrm", "mathbf", "mathit", "mathbb", "mathcal", "boldsymbol", "bm",
                 "operatorname", "mbox", "vec", "hat", "bar", "overline", "underline",
                 "displaystyle", "textstyle", "left", "right")
SUP = dict(zip("0123456789n+-=()i", "⁰¹²³⁴⁵⁶⁷⁸⁹ⁿ⁺⁻⁼⁽⁾ⁱ"))
SUB = dict(zip("0123456789+-=()ni", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₙᵢ"))

_SIMPLE = re.compile(r"^[\w.,°²³¹⁰⁴⁵⁶⁷⁸⁹ⁿ₀-₉]+$")
_FRAC = re.compile(r"\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}")
_SQRT_N = re.compile(r"\\sqrt\s*\[([^\[\]{}]*)\]\s*\{([^{}]*)\}")
_SQRT = re.compile(r"\\sqrt\s*\{([^{}]*)\}")
_SQRT_BARE = re.compile(r"\\sqrt\s*(\w)")
_SUP = re.compile(r"\^\s*(?:\{([^{}]*)\}|(\w|[+\-]))")
_SUB = re.compile(r"_\s*(?:\{([^{}]*)\}|(\w))")


def _wrap(text):
    text = text.strip()
    return text if _SIMPLE.match(text) else f"({text})"


def _script(match, table, mark):
    inner = match.group(1) if match.group(1) is not None else match.group(2)
    inner = inner.strip()
    if inner and all(ch in table for ch in inner):
        return "".join(table[ch] for ch in inner)
    return f"{mark}{_wrap(inner)}" if inner else ""


def latex_to_text(latex):
    s = str(latex or "")
    s = s.replace("{,}", ",").replace("\\{", "\x00").replace("\\}", "\x01").replace("\\\\", " ")
    s = re.sub(r"\\[,;:! ]", " ", s)
    s = re.sub(r"\\q?quad\b", " ", s)
    s = re.sub(r"\\(?:" + "|".join(DROP_COMMANDS) + r")(?![A-Za-z])", "", s)
    s = re.sub(r"\\([A-Za-z]+)(?![A-Za-z])", lambda m: SYMBOLS.get(m.group(1), m.group(0)), s)
    s = s.replace("^°", "°").replace("^ °", "°")

    for _ in range(12):                       # dari kurung terdalam ke luar
        before = s
        s = _FRAC.sub(lambda m: f"{_wrap(m.group(1))}/{_wrap(m.group(2))}", s)
        s = _SQRT_N.sub(lambda m: "".join(SUP.get(c, c) for c in m.group(1)) + "√" + _wrap(m.group(2)), s)
        s = _SQRT.sub(lambda m: "√" + _wrap(m.group(1)), s)
        s = _SQRT_BARE.sub(lambda m: "√" + m.group(1), s)
        s = _SUP.sub(lambda m: _script(m, SUP, "^"), s)
        s = _SUB.sub(lambda m: _script(m, SUB, "_"), s)
        if s == before:
            break

    s = re.sub(r"\\([A-Za-z]+)", r"\1", s)    # perintah tak dikenal: namanya saja
    s = s.replace("{", "").replace("}", "").replace("\x00", "{").replace("\x01", "}")
    return re.sub(r"[ \t]+", " ", s).strip()


# --------------------------------------------------------------------------- fonts & teks

@lru_cache(maxsize=1)
def _fonts():
    import matplotlib
    from fontTools.ttLib import TTFont

    folder = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    files = {"": "DejaVuSans.ttf", "B": "DejaVuSans-Bold.ttf", "I": "DejaVuSans-Oblique.ttf"}
    paths = {style: str(folder / name) for style, name in files.items()}
    mono = str(folder / "DejaVuSansMono.ttf")
    allowed = None
    for path in (*paths.values(), mono):
        cmap = set(TTFont(path).getBestCmap())
        allowed = cmap if allowed is None else allowed & cmap
    return paths, mono, frozenset(allowed)


_INVISIBLE = dict.fromkeys(map(ord, "\ufe0f\u200d\u200b\u200c\ufeff"))


def _clean(text):
    """Teks yang aman ditulis: huruf yang tak ada di font diganti '?'."""
    _, _, allowed = _fonts()
    text = str(text).replace("\t", " ").translate(_INVISIBLE)
    return "".join(ch if ord(ch) in allowed else "?" for ch in text if ch == " " or ch.isprintable())


_BADGE = re.compile(r":\w+-badge\[([^\]]*)\]")
_DISPLAY_ONE_LINE = re.compile(r"^\s*\$\$(.+?)\$\$\s*$")
_INLINE_MATH = re.compile(r"(?<![\\$])\$(?!\$)([^$\n]+?)\$")


def _inline(text):
    """Satu baris markdown -> [(teks, tebal, miring)] dengan matematika jadi teks."""
    text = _BADGE.sub(r"[\1]", text)
    text = _INLINE_MATH.sub(lambda m: latex_to_text(m.group(1)), text)
    text = text.replace("\\$", "$").replace("`", "")
    return [(_clean(piece), bold, italic) for piece, bold, italic in inline_runs(text)]


# --------------------------------------------------------------------------- markdown -> elemen

HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
BULLET = re.compile(r"^(\s*)[-*+•]\s+(.*)$")
NUMBERED = re.compile(r"^(\s*)(\d+)[.)]\s+(.*)$")
RULE_LINE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")


def _split_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip() for cell in line.split("|")]


def _markdown_elements(text):
    lines = str(text).replace("\r\n", "\n").split("\n")
    out, paragraph, i = [], [], 0

    def flush():
        if paragraph:
            out.append(("p", " ".join(paragraph)))
            paragraph.clear()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            flush()
        elif stripped.startswith("```"):
            flush()
            body = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                body.append(lines[i])
                i += 1
            out.append(("code", "\n".join(body)))
        elif stripped.startswith("$$"):
            flush()
            one = _DISPLAY_ONE_LINE.match(line)
            if one:
                out.append(("math", one.group(1).strip()))
            else:
                body = [stripped[2:]]
                while i + 1 < len(lines) and "$$" not in body[-1]:
                    i += 1
                    body.append(lines[i])
                out.append(("math", " ".join(body).replace("$$", "").strip()))
        elif HEADING.match(stripped):
            flush()
            m = HEADING.match(stripped)
            out.append(("h", len(m.group(1)), m.group(2).strip()))
        elif RULE_LINE.match(line):
            flush()
            out.append(("hr",))
        elif stripped.startswith("|") and i + 1 < len(lines) and TABLE_SEPARATOR.match(lines[i + 1]):
            flush()
            rows = [_split_row(line)]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(_split_row(lines[i]))
                i += 1
            i -= 1
            out.append(("table", rows))
        elif stripped.startswith(">"):
            flush()
            quote = [re.sub(r"^\s*>\s?", "", stripped)]
            while i + 1 < len(lines) and lines[i + 1].strip().startswith(">"):
                i += 1
                quote.append(re.sub(r"^\s*>\s?", "", lines[i].strip()))
            out.append(("quote", " ".join(q for q in quote if q)))
        elif BULLET.match(line):
            flush()
            m = BULLET.match(line)
            out.append(("li", len(m.group(1)) // 2, "•", m.group(2)))
        elif NUMBERED.match(line):
            flush()
            m = NUMBERED.match(line)
            out.append(("li", len(m.group(1)) // 2, f"{m.group(2)}.", m.group(3)))
        else:
            paragraph.append(stripped)
        i += 1
    flush()
    return out


# --------------------------------------------------------------------------- penggambar

def _math_png(latex):
    """PNG rumus (mathtext) atau None bila tak bisa digambar."""
    try:
        import matplotlib
        matplotlib.use("Agg", force=False)
        from matplotlib import mathtext
        from matplotlib.font_manager import FontProperties

        buf = io.BytesIO()
        mathtext.math_to_image(f"${latex.replace('{,}', ',')}$", buf, prop=FontProperties(size=15), dpi=220, format="png")
        return buf.getvalue()
    except Exception:
        return None


def _new_pdf(png):
    from fpdf import FPDF

    paths, mono, _ = _fonts()

    class Page(FPDF):
        def footer(self):
            if png:
                return
            self.set_y(-12)
            self.set_font("DejaVu", "", 8)
            self.set_text_color(*MUTED)
            self.cell(0, 6, _clean(f"Dibuat dengan Ciel · {DOMAIN} · {self.page_no()}"), align="C")

    pdf = Page(format=PNG_PAGE_MM if png else "A4", unit="mm")
    pdf.set_margins(8 if png else 18, 8 if png else 18, 8 if png else 18)
    pdf.set_auto_page_break(True, margin=16 if png else 20)
    for style, path in paths.items():
        pdf.add_font("DejaVu", style, path)
    pdf.add_font("Mono", "", mono)
    pdf.set_title("Ciel")
    pdf.set_creator("Ciel")
    pdf.add_page()
    return pdf


class _Writer:
    def __init__(self, png):
        self.png = png
        self.pdf = _new_pdf(png)
        self.base_left = self.pdf.l_margin
        self.quiz_count = 0
        self.keys = []

    # ---- util
    @property
    def spilled(self):
        return self.png and self.pdf.page_no() > 1

    def _ensure(self, height):
        pdf = self.pdf
        if pdf.get_y() + height > pdf.page_break_trigger:
            pdf.add_page()

    def _font(self, bold=False, italic=False, size=BODY_PT):
        self.pdf.set_font("DejaVu", "B" if bold else ("I" if italic else ""), size)

    def _runs(self, runs, size=BODY_PT, line=5.6, force_bold=False, color=INK):
        pdf = self.pdf
        pdf.set_text_color(*color)
        for text, bold, italic in runs:
            self._font(bold or force_bold, italic, size)
            pdf.write(line, text)
        pdf.ln(line)

    # ---- elemen
    def title_block(self, title):
        pdf = self.pdf
        self._font(True, size=13)
        pdf.set_text_color(*ACCENT)
        pdf.cell(0, 7, "Ciel")
        self._font(size=9)
        pdf.set_text_color(*MUTED)
        pdf.set_x(self.base_left)
        pdf.cell(0, 7, indonesian_date(), align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(*RULE)
        pdf.line(self.base_left, pdf.get_y() + 1, pdf.w - pdf.r_margin, pdf.get_y() + 1)
        pdf.ln(5)
        self._font(True, size=19 if not self.png else 16)
        pdf.set_text_color(*INK)
        pdf.multi_cell(0, 8.5, _clean(title), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    def heading(self, level, text):
        size = {1: 16, 2: 14, 3: 12.5}.get(level, 11.5)
        self._ensure(size * 0.9)
        self.pdf.ln(3 if level > 1 else 4)
        self._runs(_inline(text), size=size, line=size * 0.5, force_bold=True)
        self.pdf.ln(1)

    def paragraph(self, text):
        self._runs(_inline(text))
        self.pdf.ln(2.2)

    def list_item(self, depth, label, text):
        pdf = self.pdf
        indent = self.base_left + 3 + depth * 6
        width = 7 if label != "•" else 5
        self._ensure(12)
        pdf.set_x(indent)
        self._font()
        pdf.set_text_color(*INK)
        pdf.write(5.6, label)
        pdf.set_left_margin(indent + width)
        pdf.set_x(indent + width)
        self._runs(_inline(text))
        pdf.set_left_margin(self.base_left)
        pdf.ln(0.8)

    def quote(self, text):
        pdf = self.pdf
        self._ensure(14)
        page, top = pdf.page_no(), pdf.get_y()
        marked = "".join(
            f"**{t}**" if bold else (f"__{t}__" if italic else t)
            for t, bold, italic in ((t.replace("__", "_ _").replace("**", "* *"), b, i) for t, b, i in _inline(text))
        )
        pdf.set_left_margin(self.base_left + 0.8)
        pdf.set_x(self.base_left + 0.8)
        pdf.set_fill_color(*TINT)
        pdf.set_text_color(55, 65, 81)
        self._font()
        pdf.multi_cell(0, 5.6, marked, markdown=True, fill=True, padding=2.5, new_x="LMARGIN", new_y="NEXT")
        pdf.set_left_margin(self.base_left)
        if pdf.page_no() == page:
            pdf.set_draw_color(*ACCENT)
            pdf.set_line_width(0.8)
            pdf.line(self.base_left + 0.4, top, self.base_left + 0.4, pdf.get_y())
            pdf.set_line_width(0.2)
        pdf.ln(2.5)

    def code(self, text):
        pdf = self.pdf
        pdf.set_font("Mono", "", 9.5)
        pdf.set_text_color(*INK)
        pdf.set_fill_color(243, 244, 246)
        for line in _clean(text).split("\n"):
            pdf.multi_cell(0, 5, line or " ", fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2.2)

    def hr(self):
        pdf = self.pdf
        pdf.set_draw_color(*RULE)
        pdf.line(self.base_left, pdf.get_y() + 1, pdf.w - pdf.r_margin, pdf.get_y() + 1)
        pdf.ln(4)

    def table(self, rows):
        pdf = self.pdf
        width = max(len(r) for r in rows)
        pdf.ln(2)
        pdf.ln(2)
        pdf.set_text_color(*INK)
        self._font(size=10)
        pdf.set_draw_color(*RULE)
        with pdf.table(text_align="LEFT", line_height=5.4, padding=1.4) as table:
            for row in rows:
                cells = (row + [""] * width)[:width]
                line = table.row()
                for cell in cells:
                    line.cell(_clean("".join(t for t, _, _ in _inline(cell))))
        pdf.ln(2.5)

    def math(self, latex):
        pdf = self.pdf
        data = _math_png(latex)
        if data is None:
            self._runs([(_clean(latex_to_text(latex)), False, True)])
            pdf.ln(1.5)
            return
        from PIL import Image

        img = Image.open(io.BytesIO(data))
        epw = pdf.w - pdf.l_margin - pdf.r_margin
        w = min(img.width / 220 * 25.4, epw)
        h = w * img.height / img.width
        self._ensure(h + 4)
        pdf.image(io.BytesIO(data), x=pdf.l_margin + (epw - w) / 2, y=pdf.get_y() + 1, w=w)
        pdf.set_y(pdf.get_y() + h + 4)

    def visual(self, spec):
        from visuals import render_png

        try:
            data = render_png(spec, 1200)
        except ValueError:
            self.muted(BROKEN_NOTE)
            return
        from PIL import Image

        img = Image.open(io.BytesIO(data))
        pdf = self.pdf
        epw = pdf.w - pdf.l_margin - pdf.r_margin
        w = min(VISUAL_MM, epw)
        h = w * img.height / img.width
        self._ensure(h + 4)
        pdf.image(io.BytesIO(data), x=pdf.l_margin + (epw - w) / 2, y=pdf.get_y() + 1, w=w)
        pdf.set_y(pdf.get_y() + h + 4)

    def muted(self, text):
        self._runs([(_clean(text), False, True)], size=9.5, color=MUTED)
        self.pdf.ln(1.5)

    def quiz(self, quiz):
        self.quiz_count += 1
        n = self.quiz_count
        self._ensure(26)
        self.pdf.ln(1.5)
        self._runs([(f"Latihan {n}", True, False)], size=9.5, line=5, color=MUTED)
        self._runs(_inline(quiz.soal))
        for index, option in enumerate(quiz.pilihan):
            self.list_item(0, f"{chr(65 + index)}.", str(option))
        self.keys.append((n, quiz))
        self.pdf.ln(1.5)

    # ---- bagian
    def markdown(self, text):
        for el in _markdown_elements(text):
            if self.spilled:
                return
            kind = el[0]
            if kind == "p":
                self.paragraph(el[1])
            elif kind == "h":
                self.heading(el[1], el[2])
            elif kind == "li":
                self.list_item(el[1], el[2], el[3])
            elif kind == "table":
                self.table(el[1])
            elif kind == "quote":
                self.quote(el[1])
            elif kind == "math":
                self.math(el[1])
            elif kind == "code":
                self.code(el[1])
            elif kind == "hr":
                self.hr()

    def segments(self, text):
        for seg in parse_answer(text):
            if self.spilled:
                return
            if isinstance(seg, Markdown):
                self.markdown(seg.text)
            elif isinstance(seg, Visual):
                self.visual(seg.spec)
            elif isinstance(seg, Quiz):
                self.quiz(seg)
            elif isinstance(seg, Broken):
                self.muted(BROKEN_NOTE if seg.kind == "grafik" else "(latihan tidak bisa ditampilkan)")

    def key_section(self):
        if not self.keys:
            return
        if not self.png:
            self.pdf.add_page()
        self.heading(2, "Kunci jawaban")
        for n, quiz in self.keys:
            if self.spilled:
                return
            if isinstance(quiz.jawaban, int) and 0 <= quiz.jawaban < len(quiz.pilihan):
                answer = f"{chr(65 + quiz.jawaban)}. {quiz.pilihan[quiz.jawaban]}"
            else:
                answer = str(quiz.jawaban)
            self.list_item(0, f"{n}.", f"**{answer}**" if "*" not in answer else answer)
            if quiz.pembahasan:
                self.pdf.set_left_margin(self.base_left + 10)
                self._runs(_inline(quiz.pembahasan), size=10, line=5, color=(55, 65, 81))
                self.pdf.set_left_margin(self.base_left)

    def sources_section(self, sources):
        if not sources:
            return
        self.heading(2, "Sumber")
        for source in sources:
            if self.spilled:
                return
            self._ensure(14)
            self.list_item(0, f"[{source.number}]", f"{source.title} ({source.domain})")
            self.pdf.set_left_margin(self.base_left + 13)
            self._runs([(_clean(source.url), False, False)], size=8.5, line=4.4, color=MUTED)
            self.pdf.set_left_margin(self.base_left)


def _compose(content, title, png):
    writer = _Writer(png)
    before, sources, after = answer_parts(str(content or ""))
    title = _clean(title or DEFAULT_TITLE) or DEFAULT_TITLE
    before = re.sub(r"^\s*#[ \t]+" + re.escape(title) + r"[ \t]*\n", "", before, count=1)
    writer.title_block(title)
    writer.segments(before)
    writer.key_section()
    writer.sources_section(sources)
    if after.strip():
        writer.segments(after)
    return writer


def answer_pdf(content, title):
    """Jawaban sebagai PDF A4 (bytes)."""
    writer = _compose(content, title, png=False)
    return bytes(writer.pdf.output())


def answer_png(content, title):
    """Jawaban sebagai PNG selebar 1080 px, dipotong tepat di akhir isi."""
    import pypdfium2 as pdfium
    from PIL import Image, ImageChops

    writer = _compose(content, title, png=True)
    pdf = writer.pdf
    if pdf.page_no() > 1:
        _write_spill_note(pdf)
    else:
        _write_footer(pdf)

    document = pdfium.PdfDocument(bytes(pdf.output()))
    try:
        page = document[0]
        image = page.render(scale=PNG_WIDTH_PX / page.get_width()).to_pil().convert("RGB")
        page.close()
    finally:
        document.close()

    background = Image.new("RGB", image.size, (255, 255, 255))
    box = ImageChops.difference(image, background).getbbox()
    bottom = min(image.height, (box[3] if box else 0) + PNG_MARGIN_PX)
    image = image.crop((0, 0, image.width, max(bottom, PNG_MARGIN_PX * 2)))
    out = io.BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _write_footer(pdf):
    pdf.set_auto_page_break(False)
    pdf.set_font("DejaVu", "", 8)
    pdf.set_text_color(*MUTED)
    pdf.ln(2)
    pdf.cell(0, 6, _clean(f"Dibuat dengan Ciel · {DOMAIN}"), align="C")


def _write_spill_note(pdf):
    """Catatan di dasar halaman 1 saat isi melewati satu gambar."""
    pdf.page = 1
    pdf.set_auto_page_break(False)
    pdf.set_y(pdf.h - 13)
    pdf.set_font("DejaVu", "I", 9)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 6, SPILL_NOTE, align="C")
