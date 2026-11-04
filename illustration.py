"""Ilustrasi SVG buatan model: pembersih (allowlist) dan PNG-nya.

Batas kepercayaan: teks model masuk ke clean_svg, yang hanya menyisakan elemen
dan atribut dalam allowlist. Aplikasi hanya pernah menampilkan PNG dari
svg_png; SVG model tidak pernah masuk ke DOM halaman.

fpdf2 (SVGObject) dan pypdfium2 baru diimpor saat dipakai. Font: DejaVu Sans
dari paket matplotlib, didaftarkan di PDF perantara; kalau fpdf2 tidak memakai
font itu untuk <text>, hasilnya jatuh ke Helvetica bawaan (label berhuruf Latin).
"""

import io
import re
import xml.etree.ElementTree as ET

MAX_SVG_CHARS = 60_000
MAX_SVG_ELEMENTS = 1500
ILLUSTRATION_PX = 1600

SVG_NS = "http://www.w3.org/2000/svg"
FONT_FAMILY = "DejaVu Sans, sans-serif"
DEFAULT_VIEWBOX = "0 0 800 600"

ALLOWED_ELEMENTS = frozenset({
    "svg", "g", "rect", "circle", "ellipse", "line", "polyline", "polygon",
    "path", "text", "tspan", "title",
})
ALLOWED_ATTRIBUTES = frozenset({
    "viewBox", "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry",
    "width", "height", "d", "points", "transform", "fill", "stroke",
    "stroke-width", "stroke-linecap", "stroke-linejoin", "stroke-dasharray",
    "opacity", "fill-opacity", "stroke-opacity", "font-size", "font-weight",
    "text-anchor", "dominant-baseline",
})
_BAD_VALUE = ("url(", "javascript:", "data:", "&")
_TEXT_ELEMENTS = frozenset({"text", "tspan", "title"})
_NUMBER = re.compile(r"^\s*(\d+(?:\.\d+)?)(?:px)?\s*$")


class IllustrationError(ValueError):
    """Teks model tidak berisi SVG yang bisa dipakai."""


def _local(name):
    return name.rsplit("}", 1)[-1] if isinstance(name, str) else ""


def _clean_element(source, is_root):
    """Salinan elemen yang sudah bersih, atau None kalau elemennya dibuang."""
    tag = _local(source.tag)
    if tag not in ALLOWED_ELEMENTS:
        return None
    attrs = {}
    for key, value in source.attrib.items():
        if key not in ALLOWED_ATTRIBUTES:           # atribut ber-namespace ikut gugur
            continue
        if is_root and key in ("width", "height"):
            continue
        low = str(value).lower()
        if any(bad in low for bad in _BAD_VALUE):
            continue
        attrs[key] = value
    element = ET.Element(tag, attrs)
    if tag in _TEXT_ELEMENTS:
        element.text = source.text
    element.tail = source.tail if tag == "tspan" else None
    for child in source:
        cleaned = _clean_element(child, False)
        if cleaned is not None:
            element.append(cleaned)
    return element


def _count(element):
    return 1 + sum(_count(child) for child in element)


def _extract(text):
    text = str(text or "")
    if len(text) > MAX_SVG_CHARS:
        raise IllustrationError("SVG terlalu panjang")
    start = text.find("<svg")
    end = text.rfind("</svg>")
    if start < 0 or end < start:
        raise IllustrationError("tidak ada elemen svg")
    return text[start:end + len("</svg>")]


def _viewbox(root):
    given = root.get("viewBox")
    if given:
        return given
    width, height = _NUMBER.match(root.get("width", "")), _NUMBER.match(root.get("height", ""))
    if width and height:
        return f"0 0 {width.group(1)} {height.group(1)}"
    return DEFAULT_VIEWBOX


def clean_svg(text):
    """Teks model -> SVG bersih ber-allowlist. IllustrationError kalau tidak layak."""
    raw = _extract(text)
    if "<!" in raw:
        raise IllustrationError("DOCTYPE, ENTITY dan CDATA tidak diizinkan")
    try:
        source = ET.fromstring(raw)
    except ET.ParseError as err:
        raise IllustrationError("SVG tidak valid") from err
    if _local(source.tag) != "svg":
        raise IllustrationError("akar bukan svg")
    root = _clean_element(source, True)
    root.set("viewBox", _viewbox(source) if "viewBox" not in root.attrib else root.get("viewBox"))
    if _count(root) > MAX_SVG_ELEMENTS:
        raise IllustrationError("SVG terlalu rumit")
    root.set("xmlns", SVG_NS)
    root.set("font-family", FONT_FAMILY)
    return ET.tostring(root, encoding="unicode")


def _fonts():
    import matplotlib

    from pathlib import Path
    folder = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    return {"": str(folder / "DejaVuSans.ttf"), "B": str(folder / "DejaVuSans-Bold.ttf")}


def svg_png(svg, width=ILLUSTRATION_PX):
    """SVG bersih -> PNG berlatar putih selebar `width` px."""
    import pypdfium2 as pdfium
    from fpdf import FPDF
    from fpdf.svg import SVGObject
    from PIL import Image

    try:
        root = ET.fromstring(svg)
        box = [float(v) for v in re.split(r"[ ,]+", root.get("viewBox", DEFAULT_VIEWBOX).strip())]
        view_w, view_h = box[2], box[3]
        if view_w <= 0 or view_h <= 0:
            raise ValueError("viewBox kosong")
    except (ET.ParseError, ValueError, IndexError) as err:
        raise IllustrationError("SVG tidak valid") from err

    page_w = 600.0   # pt; unit="pt" supaya fpdf2 menskalakan viewBox ke halaman penuh
    page_h = page_w * view_h / view_w
    pdf = FPDF(unit="pt", format=(page_w, page_h))
    pdf.set_auto_page_break(False)
    pdf.set_margins(0, 0, 0)
    for style, path in _fonts().items():
        pdf.add_font("DejaVu Sans", style, path)
    pdf.add_page()
    try:
        drawing = SVGObject(svg)
        drawing.draw_to_page(pdf, x=0, y=0, debug_stream=None)
    except Exception as err:  # fpdf2 melempar banyak jenis galat untuk SVG aneh
        raise IllustrationError("SVG tidak bisa digambar") from err

    document = pdfium.PdfDocument(bytes(pdf.output()))
    try:
        page = document[0]
        image = page.render(scale=width / page.get_width()).to_pil().convert("RGB")
        page.close()
    finally:
        document.close()
    height = max(1, round(width * view_h / view_w))
    if image.size != (width, height):          # pembulatan ukuran halaman PDF
        image = image.resize((width, height), Image.LANCZOS)
    out = io.BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()
