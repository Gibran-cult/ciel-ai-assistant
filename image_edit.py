"""Edit gambar lewat resep JSON: validasi (batas kepercayaan) lalu terapkan dengan Pillow.

Resep dibuat oleh slider manual atau oleh model (DeepSeek). Keluaran model tidak
dipercaya: semuanya lewat `validate_recipe`, yang tidak pernah melempar error.

Koordinat selalu dinormalisasi 0-1 terhadap gambar yang sudah tegak (EXIF),
x ke kanan, y ke bawah. `box` = [x0, y0, x1, y1].
"""

import io
import math
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

MAX_EDIT_PX = 3000
MAX_OPS = 20
MAX_MARKS = 15
MAX_LABEL_CHARS = 80
OPS = ("blur", "adjust", "grayscale", "document", "mark", "arrow", "text",
       "crop", "straighten", "rotate", "flip", "resize")

DEFAULT_COLOR = "#e53935"
_MAX_SCAN = 1000          # paling banyak ini yang diperiksa dari satu resep
_ANNOTATIONS = ("blur", "mark", "arrow", "text")
_SINGLE_USE = ("adjust", "grayscale", "document", "crop", "straighten", "rotate", "flip", "resize")
_STAGE = {"blur": 0, "adjust": 1, "grayscale": 1, "document": 1, "mark": 2, "arrow": 2,
          "text": 2, "crop": 3, "straighten": 4, "rotate": 5, "flip": 6, "resize": 7}
_HEX_DIGITS = set("0123456789abcdefABCDEF")


class EditError(ValueError):
    """Pesan berbahasa Indonesia, aman ditampilkan ke pengguna."""


# --------------------------------------------------------------------------- muat & simpan

def load_for_edit(raw: bytes) -> Image.Image:
    """Buka bytes gambar (frame pertama), tegakkan lewat EXIF, RGB/RGBA, maks MAX_EDIT_PX."""
    try:
        img = Image.open(io.BytesIO(raw))
        if img.format == "JPEG":
            w, h = img.size
            longest = max(w, h)
            if longest > MAX_EDIT_PX:
                scale = MAX_EDIT_PX / longest
                img.draft(None, (max(1, round(w * scale)), max(1, round(h * scale))))
        img.load()
        if img.mode in ("P", "PA", "1"):
            img = img.convert("RGBA" if _has_alpha(img) else "RGB")
        img.thumbnail((MAX_EDIT_PX, MAX_EDIT_PX), Image.LANCZOS, reducing_gap=3.0)
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGBA" if _has_alpha(img) else "RGB")
    except EditError:
        raise
    except Exception as exc:  # Pillow melempar banyak jenis error untuk berkas rusak
        raise EditError("Format ini belum bisa diedit. Pakai JPG atau PNG.") from exc
    if min(img.size) < 1:
        raise EditError("Format ini belum bisa diedit. Pakai JPG atau PNG.")
    return img


def _has_alpha(img: Image.Image) -> bool:
    return "A" in img.getbands() or "transparency" in img.info


def encode(image: Image.Image, fmt: str) -> bytes:
    """PNG (alfa dipertahankan) atau JPG (kualitas 90, alfa diratakan di atas putih)."""
    fmt = str(fmt).lower()
    buf = io.BytesIO()
    if fmt == "png":
        out = image if image.mode in ("RGB", "RGBA") else image.convert("RGBA" if _has_alpha(image) else "RGB")
        out.save(buf, "PNG")
    elif fmt in ("jpg", "jpeg"):
        rgba = image.convert("RGBA")
        flat = Image.new("RGB", rgba.size, "white")
        flat.paste(rgba, mask=rgba.getchannel("A"))
        flat.save(buf, "JPEG", quality=90)
    else:
        raise EditError("Hasil hanya bisa disimpan sebagai PNG atau JPG.")
    return buf.getvalue()


def preview(image: Image.Image, px: int = 900) -> Image.Image:
    """Salinan yang dikecilkan untuk tampilan layar; koordinat ternormalisasi tetap berlaku."""
    out = image.copy()
    out.thumbnail((px, px), Image.LANCZOS)
    return out


# --------------------------------------------------------------------------- validasi

def _num(value, lo=None, hi=None):
    """Angka hingga (bukan bool/NaN/inf) dijepit ke [lo, hi]; selain itu None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    if not math.isfinite(number):
        return None
    if lo is not None:
        number = max(lo, number)
    if hi is not None:
        number = min(hi, number)
    return number


def _unit(value):
    return _num(value, 0.0, 1.0)


def _box(value):
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    nums = [_unit(v) for v in value]
    if any(n is None for n in nums):
        return None
    x0, y0, x1, y1 = nums
    return [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]


def _point(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    nums = [_unit(v) for v in value]
    return None if any(n is None for n in nums) else nums


def _color(value):
    if (isinstance(value, str) and len(value) == 7 and value[0] == "#"
            and all(ch in _HEX_DIGITS for ch in value[1:])):
        return value.lower()
    return DEFAULT_COLOR


def _v_blur(raw):
    box = _box(raw.get("box"))
    if box is None or box[2] <= box[0] or box[3] <= box[1]:
        return None
    return {"op": "blur", "box": box}


def _v_adjust(raw):
    out = {"op": "adjust"}
    for key in ("brightness", "contrast", "sharpness", "saturation"):
        if key in raw:
            number = _num(raw[key], 0.3, 2.5)
            if number is not None:
                out[key] = number
    return out if len(out) > 1 else None


def _v_plain(name):
    return lambda raw: {"op": name}


def _v_mark(raw):
    box = _box(raw.get("box"))
    if raw.get("shape") not in ("rect", "ellipse") or box is None:
        return None
    return {"op": "mark", "shape": raw["shape"], "box": box, "color": _color(raw.get("color"))}


def _v_arrow(raw):
    start, end = _point(raw.get("from")), _point(raw.get("to"))
    if start is None or end is None:
        return None
    return {"op": "arrow", "from": start, "to": end, "color": _color(raw.get("color"))}


def _v_text(raw):
    text = raw.get("text")
    at = _point(raw.get("at"))
    if not isinstance(text, str) or at is None:
        return None
    text = " ".join(text.split())[:MAX_LABEL_CHARS].strip()
    if not text:
        return None
    size = _num(raw.get("size"), 0.02, 0.2)
    return {"op": "text", "text": text, "at": at, "size": 0.06 if size is None else size,
            "color": _color(raw.get("color")), "background": raw.get("background") is True}


def _v_crop(raw):
    box = _box(raw.get("box"))
    if box is None or box[2] - box[0] < 0.05 or box[3] - box[1] < 0.05:
        return None
    return {"op": "crop", "box": box}


def _v_straighten(raw):
    degrees = _num(raw.get("degrees"), -20.0, 20.0)
    return None if degrees is None else {"op": "straighten", "degrees": degrees}


def _v_rotate(raw):
    degrees = _num(raw.get("degrees"))
    if degrees not in (90.0, 180.0, 270.0):
        return None
    return {"op": "rotate", "degrees": int(degrees)}


def _v_flip(raw):
    axis = raw.get("axis")
    return {"op": "flip", "axis": axis} if axis in ("horizontal", "vertical") else None


def _v_resize(raw):
    width = _num(raw.get("width"), 64, MAX_EDIT_PX)
    return None if width is None else {"op": "resize", "width": int(round(width))}


_VALIDATORS = {
    "blur": _v_blur, "adjust": _v_adjust, "grayscale": _v_plain("grayscale"),
    "document": _v_plain("document"), "mark": _v_mark, "arrow": _v_arrow, "text": _v_text,
    "crop": _v_crop, "straighten": _v_straighten, "rotate": _v_rotate, "flip": _v_flip,
    "resize": _v_resize,
}


def validate_recipe(raw: object) -> "tuple[list[dict], int]":
    """Resep mentah -> (op bersih sesuai urutan masukan, jumlah yang dibuang). Tidak pernah melempar."""
    try:
        items = raw.get("ops") if isinstance(raw, dict) else raw
        if not isinstance(items, (list, tuple)):
            return [], 0
        dropped = max(0, len(items) - _MAX_SCAN)
        clean = []
        for item in items[:_MAX_SCAN]:
            op = None
            if isinstance(item, dict):
                validator = _VALIDATORS.get(item.get("op")) if isinstance(item.get("op"), str) else None
                if validator is not None:
                    try:
                        op = validator(item)
                    except Exception:
                        op = None
            if op is None:
                dropped += 1
            else:
                clean.append(op)

        last = {}
        for index, op in enumerate(clean):
            if op["op"] in _SINGLE_USE:
                last[op["op"]] = index
        kept, marks = [], 0
        for index, op in enumerate(clean):
            name = op["op"]
            if name in _SINGLE_USE and last[name] != index:
                dropped += 1
            elif len(kept) >= MAX_OPS or (name in _ANNOTATIONS and marks >= MAX_MARKS):
                dropped += 1
            else:
                marks += name in _ANNOTATIONS
                kept.append(op)
        return kept, dropped
    except Exception:
        return [], 0


# --------------------------------------------------------------------------- terapkan

@lru_cache(maxsize=1)
def _font_path():
    try:
        import matplotlib
        path = Path(matplotlib.get_data_path()) / "fonts" / "ttf" / "DejaVuSans.ttf"
        return str(path) if path.exists() else None
    except Exception:
        return None


@lru_cache(maxsize=64)
def _font(px: int):
    path = _font_path()
    if path:
        return ImageFont.truetype(path, px)
    return ImageFont.load_default(size=px)


def _px_box(box, w, h):
    x0, y0 = int(round(box[0] * w)), int(round(box[1] * h))
    x1, y1 = int(round(box[2] * w)), int(round(box[3] * h))
    return x0, y0, max(x1, x0 + 1), max(y1, y0 + 1)


def _rgb_only(img, fn):
    """Jalankan fn pada kanal RGB; kanal alfa (kalau ada) dibiarkan."""
    if img.mode != "RGBA":
        return fn(img)
    out = fn(img.convert("RGB"))
    out.putalpha(img.getchannel("A"))
    return out


def _gray(img):
    return img.convert("L").convert("RGB")


def _adjust(img, op):
    def run(rgb):
        for key, enhancer in (("brightness", ImageEnhance.Brightness), ("contrast", ImageEnhance.Contrast),
                              ("saturation", ImageEnhance.Color), ("sharpness", ImageEnhance.Sharpness)):
            if key in op:
                rgb = enhancer(rgb).enhance(op[key])
        return rgb
    return _rgb_only(img, run)


def _document(img):
    def run(rgb):
        return ImageOps.autocontrast(_gray(rgb), cutoff=2).filter(ImageFilter.SHARPEN)
    return _rgb_only(img, run)


def _blur(img, op):
    box = _px_box(op["box"], *img.size)
    radius = 0.03 * max(img.size)
    region = img.crop(box).filter(ImageFilter.GaussianBlur(radius))
    img.paste(region, box[:2])
    return img


def _line_width(img):
    return max(2, round(0.006 * max(img.size)))


def _draw_mark(img, op):
    box = _px_box(op["box"], *img.size)
    draw = ImageDraw.Draw(img)
    shape = draw.rectangle if op["shape"] == "rect" else draw.ellipse
    shape(box, outline=op["color"], width=_line_width(img))


def _draw_arrow(img, op):
    w, h = img.size
    x0, y0 = op["from"][0] * (w - 1), op["from"][1] * (h - 1)
    x1, y1 = op["to"][0] * (w - 1), op["to"][1] * (h - 1)
    length = math.hypot(x1 - x0, y1 - y0)
    if length < 1:
        return
    lw = _line_width(img)
    head = min(length, max(6 * lw, 0.03 * max(w, h)))
    ux, uy = (x1 - x0) / length, (y1 - y0) / length
    bx, by = x1 - ux * head, y1 - uy * head
    half = head * 0.5
    draw = ImageDraw.Draw(img)
    draw.line([(x0, y0), (bx, by)], fill=op["color"], width=lw)
    draw.polygon([(x1, y1), (bx - uy * half, by + ux * half), (bx + uy * half, by - ux * half)],
                 fill=op["color"])


def _draw_text(img, op):
    w, h = img.size
    px = max(8, round(op["size"] * h))
    pad = max(2, round(px * 0.25))
    font = _font(px)
    left, top, right, bottom = font.getbbox(op["text"])
    if right - left > w - 2 * pad:       # label lebih lebar dari gambar: kecilkan huruf
        px = max(8, int(px * (w - 2 * pad) / max(1, right - left)))
        font = _font(px)
        left, top, right, bottom = font.getbbox(op["text"])
    tw, th = right - left, bottom - top
    x = int(min(max(0, round(op["at"][0] * w)), max(0, w - tw - 2 * pad)))
    y = int(min(max(0, round(op["at"][1] * h)), max(0, h - th - 2 * pad)))
    if op["background"]:
        bg_w, bg_h = min(w - x, tw + 2 * pad), min(h - y, th + 2 * pad)
        patch = Image.new("RGBA", (bg_w, bg_h), (255, 255, 255, 217))
        region = img.crop((x, y, x + bg_w, y + bg_h))
        region.alpha_composite(patch)
        img.paste(region, (x, y))
    ImageDraw.Draw(img).text((x + pad - left, y + pad - top), op["text"], font=font, fill=op["color"])


def apply_recipe(image: Image.Image, ops: "list[dict]") -> Image.Image:
    """Terapkan resep ke salinan `image` dengan urutan tahap tetap; input tidak diubah."""
    ops, _ = validate_recipe(ops)
    ops = sorted(ops, key=lambda op: _STAGE[op["op"]])      # stabil: urutan masukan dalam tahap sama
    had_alpha = _has_alpha(image)
    img = image.convert("RGBA" if had_alpha else "RGB")     # selalu salinan baru
    drawn = False
    for op in ops:
        name = op["op"]
        if name == "blur":
            img = _blur(img, op)
        elif name == "adjust":
            img = _adjust(img, op)
        elif name == "grayscale":
            img = _rgb_only(img, _gray)
        elif name == "document":
            img = _document(img)
        elif name in ("mark", "arrow", "text"):
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            drawn = True
            {"mark": _draw_mark, "arrow": _draw_arrow, "text": _draw_text}[name](img, op)
        else:
            if drawn and not had_alpha and img.mode == "RGBA":
                img, drawn = img.convert("RGB"), False
            img = _geometry(img, op)
    if not had_alpha and img.mode != "RGB":
        img = img.convert("RGB")
    return img


def _geometry(img, op):
    name = op["op"]
    w, h = img.size
    white = (255, 255, 255, 255) if img.mode == "RGBA" else (255, 255, 255)
    if name == "crop":
        return img.crop(_px_box(op["box"], w, h))
    if name == "straighten":
        return img.rotate(-op["degrees"], resample=Image.BICUBIC, expand=True, fillcolor=white)
    if name == "rotate":
        turn = {90: Image.Transpose.ROTATE_270, 180: Image.Transpose.ROTATE_180,
                270: Image.Transpose.ROTATE_90}[op["degrees"]]
        return img.transpose(turn)
    if name == "flip":
        return img.transpose(Image.Transpose.FLIP_LEFT_RIGHT if op["axis"] == "horizontal"
                             else Image.Transpose.FLIP_TOP_BOTTOM)
    # resize
    new_w = op["width"]
    new_h = max(1, round(h * new_w / w))
    if new_h > MAX_EDIT_PX:
        new_w, new_h = max(1, round(w * MAX_EDIT_PX / h)), MAX_EDIT_PX
    return img.resize((new_w, new_h), Image.LANCZOS)
