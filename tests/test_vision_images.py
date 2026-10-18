import ast
import io
import unittest
from pathlib import Path

from PIL import Image, ImageOps


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
SOURCE = APP_PATH.read_text(encoding="utf-8")


def app_constant(name):
    for node in ast.parse(SOURCE).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == name:
            return ast.literal_eval(node.value)
    raise KeyError(name)


def load():
    namespace = {
        "io": io,
        "Image": Image,
        "ImageOps": ImageOps,
        "VISION_IMAGE_PX": app_constant("VISION_IMAGE_PX"),
        "MAX_IMAGE_BYTES": eval(compile(ast.Expression(next(
            n.value for n in ast.parse(SOURCE).body
            if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) == "MAX_IMAGE_BYTES"
        )), "MAX_IMAGE_BYTES", "eval")),
        "IMAGE_MIME": app_constant("IMAGE_MIME"),
    }
    for node in ast.parse(SOURCE).body:
        if isinstance(node, ast.FunctionDef) and node.name in ("read_image", "fit_for_vision", "file_extension"):
            exec(compile(ast.Module(body=[node], type_ignores=[]), str(APP_PATH), "exec"), namespace)
    return namespace


def image_bytes(size, fmt="JPEG", mode="RGB", orientation=None):
    img = Image.new(mode, size, (200, 30, 30, 0) if mode == "RGBA" else (200, 30, 30))
    out = io.BytesIO()
    if orientation:
        exif = Image.Exif()
        exif[0x0112] = orientation
        img.save(out, format=fmt, exif=exif)
    else:
        img.save(out, format=fmt)
    return out.getvalue()


class Upload:
    def __init__(self, name, data):
        self.name, self._data = name, data

    def getvalue(self):
        return self._data


class FitForVisionTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = load()

    def open(self, image):
        return Image.open(io.BytesIO(image["data"]))

    def test_phone_photo_is_shrunk_to_the_vision_size(self):
        # A 3024x4032 photo needed 4283 tokens and failed the vision model's context.
        image, error = self.app["read_image"](Upload("soal.jpg", image_bytes((3024, 4032))))
        self.assertIsNone(error)
        with self.open(image) as img:
            self.assertEqual(img.size, (768, 1024))
            self.assertEqual(img.format, "JPEG")
        self.assertEqual((image["name"], image["mime"]), ("soal.jpg", "image/jpeg"))

    def test_small_upright_image_is_sent_unchanged(self):
        data = image_bytes((800, 600), fmt="PNG")
        image, error = self.app["read_image"](Upload("grafik.png", data))
        self.assertIsNone(error)
        self.assertEqual(image, {"name": "grafik.png", "data": data, "mime": "image/png"})

    def test_rotated_phone_photo_is_turned_upright(self):
        # EXIF orientation 6: the camera stored it sideways (landscape pixels, portrait photo).
        image = self.app["fit_for_vision"]({"name": "a.jpeg", "data": image_bytes((1200, 900), orientation=6), "mime": "image/jpeg"})
        with self.open(image) as img:
            self.assertEqual(img.size, (768, 1024))
            self.assertEqual(img.getexif().get(0x0112, 1), 1)

    def test_transparent_screenshot_gets_a_white_background(self):
        image = self.app["fit_for_vision"]({"name": "layar.png", "data": image_bytes((2000, 1000), fmt="PNG", mode="RGBA"), "mime": "image/png"})
        with self.open(image) as img:
            self.assertEqual(img.size, (1024, 512))
            self.assertEqual(img.convert("RGB").getpixel((10, 10)), (255, 255, 255))
        self.assertEqual(image["name"], "layar.jpg")

    def test_unreadable_file_is_left_as_is(self):
        image = {"name": "rusak.png", "data": b"not an image", "mime": "image/png"}
        self.assertIs(self.app["fit_for_vision"](image), image)

    def test_size_limit_still_applies(self):
        too_big = Upload("besar.jpg", b"0" * (self.app["MAX_IMAGE_BYTES"] + 1))
        image, error = self.app["read_image"](too_big)
        self.assertIsNone(image)
        self.assertIn("melebihi", error)


if __name__ == "__main__":
    unittest.main()
