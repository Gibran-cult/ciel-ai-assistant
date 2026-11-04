import io
import unittest

from PIL import Image

from image_edit import (
    MAX_EDIT_PX,
    MAX_MARKS,
    MAX_OPS,
    EditError,
    apply_recipe,
    encode,
    load_for_edit,
    preview,
    validate_recipe,
)


def _bytes(image, fmt, **kw):
    buf = io.BytesIO()
    image.save(buf, fmt, **kw)
    return buf.getvalue()


def two_tone(w, h):
    image = Image.new("RGB", (w, h), (0, 0, 255))
    image.paste((255, 0, 0), (0, 0, w // 2, h))
    return image


def phone_photo_50mp_with_exif_rotation():
    image = Image.new("L", (8660, 5774), 128)
    exif = Image.Exif()
    exif[0x0112] = 6
    return _bytes(image, "JPEG", exif=exif, quality=60)


def png_with_alpha():
    image = Image.new("RGBA", (120, 80), (10, 200, 30, 0))
    image.paste((200, 20, 20, 255), (0, 0, 60, 80))
    return _bytes(image, "PNG")


def cmyk_jpeg():
    return _bytes(Image.new("CMYK", (90, 60), (0, 100, 100, 0)), "JPEG")


def animated_gif():
    frames = [Image.new("P", (50, 40), i) for i in (1, 2, 3)]
    return _bytes(frames[0], "GIF", save_all=True, append_images=frames[1:])


def one_pixel_png():
    return _bytes(Image.new("RGB", (1, 1), "white"), "PNG")


class ImageEditTest(unittest.TestCase):
    def test_validate_drops_and_clamps(self):
        ops, dropped = validate_recipe({"ops": [
            {"op": "crop", "box": [-1, 0.1, 2, 0.9]},
            {"op": "adjust", "brightness": 9},
            {"op": "explode"},
            "nonsense",
            {"op": "text", "text": "x" * 80_000, "at": [0.5, 0.5], "size": 5, "color": "red"},
            {"op": "rotate", "degrees": 45},
        ] + [{"op": "mark", "shape": "rect", "box": [0, 0, 0.1, 0.1], "color": "#00ff00"}] * 200})
        crop = next(o for o in ops if o["op"] == "crop")
        self.assertEqual(crop["box"], [0.0, 0.1, 1.0, 0.9])
        self.assertEqual(next(o for o in ops if o["op"] == "adjust")["brightness"], 2.5)
        text = next(o for o in ops if o["op"] == "text")
        self.assertEqual((len(text["text"]), text["size"], text["color"]), (80, 0.2, "#e53935"))
        self.assertNotIn("rotate", [o["op"] for o in ops])
        self.assertLessEqual(len(ops), MAX_OPS)
        self.assertLessEqual(sum(o["op"] in ("mark", "arrow", "text", "blur") for o in ops), MAX_MARKS)
        self.assertGreater(dropped, 0)
        self.assertEqual(validate_recipe("not a recipe"), ([], 0))

    def test_validate_never_raises_and_last_single_use_wins(self):
        for junk in (None, 5, [None, 3, [], {"op": 7}], {"ops": "x"}, {"ops": [{"op": "crop", "box": "ab"}]},
                     [{"op": "arrow", "from": [0, 0]}], [{"op": "text", "text": "", "at": [0, 0]}],
                     [{"op": "crop", "box": [0, 0, float("nan"), 1]}]):
            ops, dropped = validate_recipe(junk)
            self.assertIsInstance(ops, list)
            self.assertIsInstance(dropped, int)
        ops, dropped = validate_recipe([{"op": "rotate", "degrees": 90}, {"op": "rotate", "degrees": 180}])
        self.assertEqual([(o["op"], o["degrees"]) for o in ops], [("rotate", 180)])
        self.assertEqual(dropped, 1)
        ops, _ = validate_recipe([{"op": "crop", "box": [0.5, 0.5, 0.52, 0.9]}])
        self.assertEqual(ops, [])
        ops, _ = validate_recipe([{"op": "straighten", "degrees": 99},
                                  {"op": "mark", "shape": "star", "box": [0, 0, 1, 1]}])
        self.assertEqual([(o["op"], o["degrees"]) for o in ops], [("straighten", 20.0)])

    def test_stage_order_keeps_coordinates_on_the_original(self):
        # 200x100 red-left/blue-right image; rotate listed first, crop second.
        out = apply_recipe(two_tone(200, 100), [{"op": "rotate", "degrees": 90},
                                                {"op": "crop", "box": [0, 0, 0.5, 1]}])
        self.assertEqual(out.size, (100, 100))
        self.assertEqual(out.getpixel((50, 50))[:3], (255, 0, 0))

    def test_annotations_keep_colour_after_grayscale(self):
        out = apply_recipe(Image.new("RGB", (400, 400), "white"),
                           [{"op": "mark", "shape": "rect", "box": [0.1, 0.1, 0.9, 0.9], "color": "#ff0000"},
                            {"op": "grayscale"}])
        self.assertEqual(out.convert("RGB").getpixel((40, 200)), (255, 0, 0))

    def test_all_ops_run(self):
        ops, dropped = validate_recipe([
            {"op": "blur", "box": [0, 0, 0.3, 0.3]},
            {"op": "adjust", "brightness": 1.2, "contrast": 1.1, "sharpness": 1.5, "saturation": 0.8},
            {"op": "mark", "shape": "ellipse", "box": [0.1, 0.1, 0.5, 0.5]},
            {"op": "arrow", "from": [0.1, 0.1], "to": [0.8, 0.8]},
            {"op": "text", "text": "Halo", "at": [0.5, 0.5], "size": 0.08, "color": "#112233", "background": True},
            {"op": "crop", "box": [0, 0, 0.9, 0.9]},
            {"op": "straighten", "degrees": 5},
            {"op": "rotate", "degrees": 270},
            {"op": "flip", "axis": "horizontal"},
            {"op": "resize", "width": 100},
        ])
        self.assertEqual(dropped, 0)
        out = apply_recipe(two_tone(300, 200), ops)
        self.assertEqual(out.width, 100)

    def test_ellipse_mark_draws_outline_not_fill(self):
        out = apply_recipe(Image.new("RGB", (200, 200), "white"),
                           [{"op": "mark", "shape": "ellipse", "box": [0.1, 0.1, 0.9, 0.9], "color": "#ff0000"}])
        self.assertEqual(out.getpixel((20, 100)), (255, 0, 0))
        self.assertEqual(out.getpixel((100, 100)), (255, 255, 255))
        self.assertEqual(out.getpixel((5, 5)), (255, 255, 255))

    def test_arrow_has_shaft_and_filled_head(self):
        out = apply_recipe(Image.new("RGB", (400, 400), "white"),
                           [{"op": "arrow", "from": [0.1, 0.5], "to": [0.9, 0.5], "color": "#0000ff"}])
        blue = (0, 0, 255)
        self.assertTrue(any(out.getpixel((200, y)) == blue for y in range(197, 203)))
        self.assertEqual(out.getpixel((200, 195)), (255, 255, 255))     # shaft is thin
        self.assertEqual(out.getpixel((352, 197)), blue)                # head is wider than the shaft
        self.assertEqual(out.getpixel((352, 202)), blue)
        self.assertEqual(out.getpixel((20, 200)), (255, 255, 255))      # nothing before the start

    def test_text_background_box_and_clamping(self):
        dark = Image.new("RGB", (300, 200), (20, 20, 20))
        out = apply_recipe(dark, [{"op": "text", "text": "Hi", "at": [0.2, 0.3], "size": 0.1,
                                   "color": "#000000", "background": True}])
        self.assertTrue(all(c > 200 for c in out.getpixel((61, 61))))
        self.assertEqual(out.getpixel((50, 50)), (20, 20, 20))
        edge = apply_recipe(dark, [{"op": "text", "text": "Pojok kanan", "at": [0.98, 0.5], "size": 0.1,
                                    "color": "#000000", "background": True}])
        self.assertEqual(edge.size, (300, 200))
        self.assertTrue(all(c > 200 for c in edge.getpixel((299, 101))))
        self.assertEqual(edge.getpixel((5, 101)), (20, 20, 20))

    def test_rotate_straighten_and_flip_directions(self):
        half = Image.new("RGB", (100, 100), (0, 0, 255))
        half.paste((255, 0, 0), (0, 0, 100, 50))                         # red top, blue bottom
        turned = apply_recipe(half, [{"op": "rotate", "degrees": 90}])   # clockwise: top goes right
        self.assertEqual(turned.getpixel((5, 50)), (0, 0, 255))
        self.assertEqual(turned.getpixel((95, 50)), (255, 0, 0))

        block = Image.new("RGB", (200, 200), "white")
        block.paste((255, 0, 0), (180, 90, 200, 110))                    # right-middle
        tilted = apply_recipe(block, [{"op": "straighten", "degrees": 10}])
        ys = [y for y in range(tilted.height) for x in range(tilted.width)
              if (lambda p: p[0] > 200 and p[1] < 60 and p[2] < 60)(tilted.getpixel((x, y)))]
        self.assertTrue(ys)
        self.assertGreater(sum(ys) / len(ys), tilted.height / 2 + 5)     # clockwise: right side dips down

        corner = Image.new("RGB", (100, 60), "white")
        corner.paste((255, 0, 0), (0, 0, 10, 10))                        # top-left
        h = apply_recipe(corner, [{"op": "flip", "axis": "horizontal"}])
        v = apply_recipe(corner, [{"op": "flip", "axis": "vertical"}])
        self.assertEqual(h.getpixel((95, 5)), (255, 0, 0))
        self.assertEqual(h.getpixel((5, 5)), (255, 255, 255))
        self.assertEqual(v.getpixel((5, 55)), (255, 0, 0))
        self.assertEqual(v.getpixel((5, 5)), (255, 255, 255))

    def test_blur_changes_only_the_box(self):
        image = Image.new("RGB", (200, 200), "white")
        for x in range(0, 200, 4):
            image.paste((0, 0, 0), (x, 0, x + 2, 200))
        out = apply_recipe(image, [{"op": "blur", "box": [0, 0, 0.5, 1]}])
        self.assertEqual(out.getpixel((150, 100)), image.getpixel((150, 100)))
        self.assertEqual(out.getpixel((190, 10)), image.getpixel((190, 10)))
        self.assertNotEqual(out.getpixel((40, 100)), image.getpixel((40, 100)))

    def test_odd_inputs_load_and_save(self):
        cases = [phone_photo_50mp_with_exif_rotation(), png_with_alpha(), cmyk_jpeg(),
                 animated_gif(), one_pixel_png()]
        for raw in cases:
            image = load_for_edit(raw)
            self.assertLessEqual(max(image.size), MAX_EDIT_PX)
            for fmt in ("png", "jpg"):
                Image.open(io.BytesIO(encode(apply_recipe(image, [{"op": "document"}]), fmt))).verify()
        self.assertEqual(Image.open(io.BytesIO(encode(load_for_edit(png_with_alpha()), "png"))).mode, "RGBA")
        with self.assertRaises(EditError):
            load_for_edit(b"%PDF-1.7 not an image")

    def test_exif_upright_and_alpha_flattened_on_white(self):
        image = load_for_edit(phone_photo_50mp_with_exif_rotation())
        self.assertGreater(image.height, image.width)
        flat = Image.open(io.BytesIO(encode(load_for_edit(png_with_alpha()), "jpg"))).convert("RGB")
        self.assertGreater(min(flat.getpixel((100, 40))), 240)

    def test_apply_does_not_mutate_input(self):
        image = two_tone(120, 80)
        before = image.tobytes()
        out = apply_recipe(image, [{"op": "blur", "box": [0, 0, 1, 1]}, {"op": "grayscale"},
                                   {"op": "mark", "shape": "rect", "box": [0, 0, 1, 1]}])
        self.assertIsNot(out, image)
        self.assertEqual(image.tobytes(), before)
        self.assertEqual(image.mode, "RGB")

    def test_preview_is_small_and_same_recipe_applies(self):
        image = two_tone(3000, 2000)
        small = preview(image)
        self.assertEqual(small.size, (900, 600))
        self.assertEqual(image.size, (3000, 2000))
        recipe = [{"op": "crop", "box": [0, 0, 0.5, 0.5]}]
        self.assertEqual(apply_recipe(small, recipe).size, (450, 300))
        self.assertEqual(apply_recipe(image, recipe).size, (1500, 1000))


if __name__ == "__main__":
    unittest.main()
