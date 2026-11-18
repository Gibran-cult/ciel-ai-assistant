"""Pembersih SVG ilustrasi dan PNG-nya (illustration.py)."""

import io
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from illustration import IllustrationError, clean_svg, svg_png  # noqa: E402

GOOD = ('<svg viewBox="0 0 800 600"><title>Siklus air</title>'
        '<rect x="0" y="0" width="800" height="600" fill="#e3f2fd"/>'
        '<circle cx="680" cy="110" r="60" fill="#fbc02d"/>'
        '<path d="M100 400 Q 400 300 700 400" stroke="#1565c0" stroke-width="6" fill="none"/>'
        '<polygon points="690,390 710,400 690,410" fill="#1565c0"/>'
        '<text x="400" y="560" font-size="32" text-anchor="middle">Penguapan</text></svg>')


class IllustrationTest(unittest.TestCase):
    def test_good_svg_survives_and_is_wrapped_from_prose(self):
        out = clean_svg("Ini ilustrasinya:\n```svg\n" + GOOD + "\n```\nSemoga membantu!")
        root = ET.fromstring(out)
        self.assertEqual(root.get("viewBox"), "0 0 800 600")
        self.assertIn("Penguapan", out)
        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
        self.assertIsNone(root.get("width"))
        self.assertIsNone(root.get("height"))
        self.assertEqual(root.get("font-family"), "DejaVu Sans, sans-serif")

    def test_clean_svg_rejects_and_strips_hostile_parts(self):
        hostile = GOOD.replace("</svg>",
            '<script>alert(1)</script><foreignObject><div>x</div></foreignObject>'
            '<image href="http://evil.example/x.png"/><use href="#a"/>'
            '<rect onload="alert(1)" style="fill:url(http://evil.example)" fill="url(http://e.x)" width="1" height="1"/>'
            '</svg>')
        out = clean_svg(hostile)
        for needle in ("script", "foreignObject", "image", "use", "onload", "style", "url(", "evil"):
            self.assertNotIn(needle, out)
        for bad in ('<!DOCTYPE svg [<!ENTITY a "aaaa">]><svg>&a;</svg>', "<svg>" + "<g/>" * 2000 + "</svg>",
                    "<svg>" + " " * 5_000_000 + "</svg>", "<html><body>no svg</body></html>", ""):
            with self.assertRaises(IllustrationError):
                clean_svg(bad)

    def test_comments_are_dropped_but_doctype_still_rejected(self):
        commented = GOOD.replace("<rect", "<!-- latar langit -->\n<rect", 1).replace(
            "<circle", "<!-- matahari,\n pojok kanan atas -->\n<circle", 1)
        out = clean_svg("Ini SVG-nya:\n```svg\n" + commented + "\n```")
        self.assertNotIn("<!--", out)
        self.assertNotIn("latar langit", out)
        self.assertIn("Penguapan", out)
        for bad in ('<svg><!-- a --><!DOCTYPE x><g/></svg>', '<svg><!-- tidak ditutup <g/></svg>',
                    '<svg><![CDATA[x]]><!-- b --></svg>'):
            with self.assertRaises(IllustrationError):
                clean_svg(bad)

    def test_namespaced_input_missing_viewbox_and_bad_values(self):
        out = clean_svg('<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300">'
                        '<rect width="10" height="10" fill="data:x" stroke="a&amp;b"/></svg>')
        root = ET.fromstring(out)
        self.assertEqual(root.get("viewBox"), "0 0 400 300")
        rect = root[0]
        self.assertIsNone(rect.get("fill"))
        self.assertIsNone(rect.get("stroke"))
        self.assertEqual(rect.get("width"), "10")
        self.assertEqual(ET.fromstring(clean_svg("<svg><g/></svg>")).get("viewBox"), "0 0 800 600")

    def test_deep_nesting_is_rejected(self):
        with self.assertRaises(IllustrationError):
            clean_svg("<svg>" + "<g>" * 5000 + "</g>" * 5000 + "</svg>")
        clean_svg("<svg>" + "<g>" * 40 + "</g>" * 40 + "</svg>")

    def test_extreme_aspect_viewbox_is_rejected(self):
        for box in ("0 0 1 20", "0 0 20 1"):
            with self.assertRaises(IllustrationError):
                clean_svg('<svg viewBox="%s"><g/></svg>' % box)
        with self.assertRaises(IllustrationError):
            clean_svg('<svg width="10" height="1000"><g/></svg>')

    def test_png_height_is_capped_even_for_hand_made_svg(self):
        png = Image.open(io.BytesIO(svg_png('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 20"><rect width="1" height="1"/></svg>')))
        self.assertLessEqual(png.height, 4 * png.width)

    def test_non_finite_and_hostile_viewboxes_are_replaced(self):
        for box in ("nan nan nan nan", "0 0 1e999 5", "javascript:1 url(x) 5 5", "0 0 &amp; 5",
                    "0 0 0 5", "0 0 -4 5", "0 0 4", "0 0 4 5 6"):
            out = clean_svg('<svg viewBox="%s"><rect width="1" height="1"/></svg>' % box)
            self.assertEqual(ET.fromstring(out).get("viewBox"), "0 0 800 600", box)
            self.assertGreater(len(svg_png(out, 200)), 100)
        out = clean_svg('<svg viewBox="10 20 400.5 300"><g/></svg>')
        self.assertEqual(ET.fromstring(out).get("viewBox"), "10 20 400.5 300")

    def test_namespaced_and_odd_case_attributes_and_script_in_text(self):
        out = clean_svg('<svg xmlns:xlink="http://www.w3.org/1999/xlink" ONLOAD="a()" viewBox="0 0 800 600">'
                        '<rect xlink:href="http://x.y" ONCLICK="a()" Fill="red" width="1" height="1"/>'
                        '<text x="1" y="2">Halo<script>alert(1)</script> dunia</text></svg>')
        for needle in ("xlink", "href", "onload", "onclick", "Fill", "script", "alert"):
            self.assertNotIn(needle.lower(), out.lower().replace("fill-", "") if needle == "Fill" else out.lower())
        self.assertIn("Halo", out)

    def test_svg_png_failure_becomes_illustration_error(self):
        for bad in ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path d="M 1 1 L"/><text><tspan>',
                    "bukan xml", '<svg xmlns="http://www.w3.org/2000/svg" viewBox="nan 0 1 1"/>'):
            with self.assertRaises(IllustrationError):
                svg_png(bad)
        from unittest import mock
        with mock.patch("fpdf.svg.SVGObject.draw_to_page", side_effect=RuntimeError("boom")):
            with self.assertRaises(IllustrationError):
                svg_png(clean_svg(GOOD))

    def test_png_is_1600_wide_and_not_blank(self):
        png = Image.open(io.BytesIO(svg_png(clean_svg(GOOD))))
        self.assertEqual((png.width, png.height), (1600, 1200))
        self.assertGreater(len(set(png.convert("RGB").getdata())), 3)
        self.assertNotEqual(png.convert("RGB").getpixel((1360, 220)), (255, 255, 255))  # the sun

    def test_importing_illustration_does_not_import_heavy_libs(self):
        code = (
            "import sys; sys.path.insert(0, %r); import illustration; "
            "print([m for m in ('fpdf', 'pypdfium2', 'matplotlib') if m in sys.modules])" % str(ROOT)
        )
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
        self.assertEqual(out.stdout.strip(), "[]")


if __name__ == "__main__":
    unittest.main()
