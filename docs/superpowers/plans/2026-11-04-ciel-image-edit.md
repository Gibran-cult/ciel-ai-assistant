# Ciel Image Edit and Illustrations Implementation Plan (Plan 2 of 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let everyone edit a photo in Ciel (crop, rotate, brighten, clean up a document photo, add a label). Pro users also get two AI features: "Minta AI" ("potong soal nomor 3", "lingkari jawabannya", "blur namaku") and illustrations ("siklus air dengan label").

**Architecture:**
- **Edit recipe.** Every edit is a JSON *recipe*: a list of operations (`image_edit.py`) that the app validates and applies with Pillow.
  - Manual edits: the dialog's widgets build a recipe.
  - AI edits: DeepSeek (`deepseek-flash`, which can read images) looks at the photo and writes a recipe.
  - Both kinds pass through the same validator, which is the trust boundary.
- **Illustrations.** DeepSeek writes SVG. `illustration.py` cleans it against a strict allowlist and rasterizes it to PNG with fpdf2 + pypdfium2, both already installed for Plan 1.
- **What is shown on screen.** Only the PNG. Model SVG never reaches the page DOM.
- **Where DeepSeek is called.** Both AI calls go through one small new Langflow flow, *Ciel Image AI*: Chat Input → custom component → Chat Output. So the DeepSeek key stays in Langflow.

**Tech Stack:**
- Python 3.14 (Cloud) / 3.10 (local).
- Streamlit 1.66 (`st.dialog`, `st.image`, `st.download_button`).
- Pillow 13 (already installed), fpdf2 2.9 + pypdfium2 (already installed).
- DeepSeek Chat Completions (`deepseek-flash`, image input through `image_url` data URIs).
- Langflow custom component.

**Spec:** No separate spec doc. Ciel's decisions from 2026-11-04 are recorded in **Decisions** below, and every task argues from them.

## Decisions (spec)

1. **Focus is image editing.**
   - Simple (manual) edits are **free for everyone**, guests included. They make no model call.
   - AI edits and illustrations are **Ciel Pro only**.
2. **Quota.**
   - AI edits and illustrations share one quota: **3 per Pro account per day**.
   - The config key is `AI_IMAGE_PER_DAY`, default `3`.
3. **Model.**
   - **DeepSeek only.** No Gemini or other image model.
   - DeepSeek cannot paint pixels (its API has `deepseek-flash`, which reads images, and `deepseek-v4-pro`). So an AI edit is DeepSeek *choosing* edit operations that the app applies.
   - Illustrations are **SVG diagrams** (labelled, flat style), not painted or photo-style images.
   - Background removal and changing photo content are out of scope.
4. **No storage.** Edited images and illustrations live only in the session. Nothing is saved to Supabase or chat history.
5. **Plan 1's honesty rule carries over.** Until this plan's flow change ships, Ciel keeps saying it cannot edit photos. Afterwards it points to the Edit gambar and Ilustrasi tools; it never claims it can paint or remove backgrounds.

## Global Constraints

- **Commits and PRs:**
  - No `Co-Authored-By` / "Generated with Claude" lines (Ciel's standing rule).
  - UI tasks (Task 5, Task 6) stop before their commit. Ciel checks them in the browser in **both themes and at phone width** and says "commit". Other tasks commit normally.
- **Deploy order:**
  1. The Ciel Image AI flow is imported and the gateway policy allows it.
  2. Streamlit Cloud gets `IMAGE_FLOW_ID`.
  3. The app ships.
  4. The main flow v1.14.2 prompt is PATCHed last.
  - Without `IMAGE_FLOW_ID` the app hides the AI parts, and manual editing still works.
- **Model output is untrusted:**
  - Never `eval`/`exec` it, and never put it into `unsafe_allow_html`.
  - Recipes go through `image_edit.validate_recipe`. SVG goes through `illustration.clean_svg` and is shown only as PNG (`st.image`).
  - The existing `strip_markdown_images` guard stays as it is.
- **Imports:** load fpdf, pypdfium2 and matplotlib lazily inside functions (as in Plan 1). Pillow is already imported in `app.py`.
- **Dependencies:**
  - No new dependency. `requirements.in` / `requirements.txt` stay unchanged.
  - If an implementer finds one is needed, stop and ask Ciel.
- **Tests:**
  - Every new `tests/test_*.py` is added to the unittest list in `.github/workflows/ci.yml` (enforced by `tests/test_ci_coverage.py`).
  - Tests never call DeepSeek or Langflow. HTTP is mocked as in `tests/test_vision_router.py`.
- **Flow snapshots:**
  - Earlier snapshots stay byte-identical.
  - Snapshots are written with `json.dumps(indent=2, ensure_ascii=False)`, CRLF line endings and no trailing newline (the v1.14.1 convention).
- **Limits** (constants in the module named):
  - `image_edit.MAX_EDIT_PX = 3000` on the longest side after EXIF upright.
  - `image_edit.MAX_OPS = 20`, of which at most `MAX_MARKS = 15` are annotations.
  - `illustration.MAX_SVG_CHARS = 60_000`, `MAX_SVG_ELEMENTS = 1500`, `ILLUSTRATION_PX = 1600` (PNG width).
  - AI instruction ≤ 300 characters. Illustration description ≤ 300 characters.
- **Copy and style:**
  - Visible copy is Indonesian, short and warm, with no AI-slop phrasing.
  - On screen, use only the colour tokens from `app.py` (`--c-text`, `--c-muted`, `--c-line`, `--c-accent`, `--c-ok`, `--c-warn`, `--c-err`, `--c-raised`). The one exception is the white "paper" behind an illustration, because it is a picture.
- **DeepSeek is prepaid.** A zero balance answers 402. AI failures must leave manual editing working and show "AI sedang tidak tersedia", never a stack trace.

## Review Focus

1. **Odd photos.** Each of these opens, edits and downloads without an error, and transparency is kept for PNG output and filled white for JPG:
   - a 50-megapixel phone photo with EXIF rotation;
   - a PNG with transparency;
   - a CMYK JPEG;
   - an animated GIF (first frame);
   - a 1×1 image.

   A file Pillow cannot read (HEIC, PDF) shows "Format ini belum bisa diedit. Pakai JPG atau PNG." Pinned by `test_odd_inputs_load_and_save` (Task 1).
2. **AI returns junk.** Prose, broken JSON, unknown `op`s, coordinates outside 0–1, 200 operations, an 80 000-character label: the junk is dropped or clamped and nothing crashes. If no valid operation is left, the user sees "AI belum menangkap maksudnya. Coba tulis lebih spesifik." Pinned by `test_validate_drops_and_clamps` (Task 1) and `test_reply_that_is_not_json_is_an_error` (Task 3).
3. **Hostile SVG.** All of these are removed or the SVG is rejected, and the PNG never shows them:
   - `<script>`, `onload=`, `<foreignObject>`, `<image href="http…">`, `<use href>`;
   - `fill="url(http…)"`, a `style` attribute, a `<!DOCTYPE>`/`<!ENTITY>` bomb;
   - a 5 MB file.

   Pinned by `test_clean_svg_rejects_and_strips_hostile_parts` (Task 2).
4. **Gate and quota order.** Checks run Pro → quota → DeepSeek:
   - A guest, a free account, or a Pro account that expired while the dialog was open gets the Pro message, and no flow call is made.
   - When the quota is used up, the quota message shows and no flow call is made.

   Pinned by `test_ai_edit_checks_pro_then_quota_before_calling` (Task 5).
5. **DeepSeek down, slow or out of balance.** The AI result is an error card inside the dialog, and the manual edits and preview stay as they were. Pinned by `test_ai_failure_keeps_manual_edits` (Task 5).

---

## File Map

| File | Status | Responsibility |
|---|---|---|
| `image_edit.py` | new | Recipe schema, validation, applying a recipe with Pillow, load/save. Pure. |
| `illustration.py` | new | SVG allowlist cleaner and SVG → PNG. Pure. |
| `flow/components/ciel_image_ai.py` | new | Langflow component: request JSON in, DeepSeek call, recipe JSON or SVG out. |
| `flow/image_ai/v1.0.0/Ciel_Image_AI.json` | new | Flow snapshot (Chat Input → Ciel Image AI → Chat Output). |
| `tools/render_ngrok_policy.py`, `tools/render_nginx_gateway.py` | modify | Optional `IMAGE_FLOW_ID` in the gateway allowlist (run only). |
| `app.py` | modify | Config, quota, gate, `ask_image_ai`, Edit gambar dialog, Ilustrasi dialog. |
| `beranda.py` | modify | Two Beranda templates: "Edit gambar" (free) and "Ilustrasi" (Pro). |
| `privacy.py`, `terms.py`, `pricing.py`, `docs/LEGAL.md` | modify | Disclose photos sent to DeepSeek for AI edits; list the Pro feature. |
| `flow/v1.14.2/Ciel_AI_Long-Term_Memory_Master.json` | new | Prompt v15.2: point to the new tools instead of "belum bisa". |
| `CHANGELOG.md`, `docs/ARCHITECTURE.md`, `RELEASE_CHECKLIST.md`, `README.md` | modify | Document the feature and rollout. |

---

### Task 1: Edit recipe (`image_edit.py`)

**Files:**
- Create: `image_edit.py`
- Test: `tests/test_image_edit.py`
- Modify: `.github/workflows/ci.yml` (add `tests.test_image_edit`)

**Interfaces:**
- Produces:
  - `class EditError(ValueError)`: the message is Indonesian and safe to show.
  - `load_for_edit(raw: bytes) -> PIL.Image.Image`:
    - opens the image (first frame) and turns it upright by EXIF;
    - converts CMYK/P/LA to RGB or RGBA (keeping alpha), and shrinks it to `MAX_EDIT_PX` on the longest side;
    - raises `EditError("Format ini belum bisa diedit. Pakai JPG atau PNG.")` when Pillow cannot open it.
  - `validate_recipe(raw: object) -> tuple[list[dict], int]`:
    - accepts a list, or a dict with key `"ops"`;
    - returns (clean ops in input order, number dropped);
    - never raises.
  - `apply_recipe(image: Image.Image, ops: list[dict]) -> Image.Image`: returns a new image; the input is never mutated.
  - `encode(image: Image.Image, fmt: str) -> bytes`: `fmt` is `"png"` or `"jpg"`. JPG is quality 90, with alpha flattened on white.
  - `preview(image: Image.Image, px: int = 900) -> Image.Image`: a copy shrunk for on-screen preview. Normalized coordinates make the same recipe valid on it.
  - Constants: `MAX_EDIT_PX`, `MAX_OPS`, `MAX_MARKS`, `MAX_LABEL_CHARS = 80`, `OPS` (tuple of op names).

**Recipe schema (fixed; the component prompt in Task 3 describes exactly this):**
- **Coordinates:**
  - Every coordinate is normalized 0–1 against the **uploaded image after EXIF upright**.
  - x goes right and y goes down.
  - A `box` is `[x0, y0, x1, y1]`.
- **Operations:**

| op | fields | rule |
|---|---|---|
| `blur` | `box` | Strong Gaussian blur, radius 3 % of the longest side. Used for names and faces. Annotation-like; counts toward `MAX_MARKS`. |
| `adjust` | `brightness`, `contrast`, `sharpness`, `saturation` (each optional) | Clamped to 0.3–2.5. Missing means 1.0. |
| `grayscale` | none | |
| `document` | none | Clean up a photo of paper: grayscale, `ImageOps.autocontrast(cutoff=2)`, then sharpen once. |
| `mark` | `shape` (`"rect"` or `"ellipse"`), `box`, `color` | Outline only. Line width is `max(2, round(0.006 × longest side))`. |
| `arrow` | `from` `[x,y]`, `to` `[x,y]`, `color` | Line with a filled triangular head. |
| `text` | `text`, `at` `[x,y]` (top-left of the label), `size` (0.02–0.2 of the image height), `color`, `background` (bool) | DejaVu Sans from `matplotlib.get_data_path()` (as `answer_pdf._fonts`). The background is a white box with 85 % opacity. Text is cut to `MAX_LABEL_CHARS`. |
| `crop` | `box` | Each side must be at least 0.05 wide/tall after clamping, else the op is dropped. |
| `straighten` | `degrees` (−20 to 20, positive = clockwise) | `expand=True`, filled white. |
| `rotate` | `degrees` ∈ {90, 180, 270}, clockwise | |
| `flip` | `axis` ∈ {`"horizontal"`, `"vertical"`} | |
| `resize` | `width` (64 to `MAX_EDIT_PX`) | Keeps the aspect ratio. |

- **`color` values:** `#rrggbb`. Anything else becomes `#e53935`.
- **Stage order.** `apply_recipe` applies ops in a fixed stage order regardless of input order, so coordinates always refer to the original frame and annotations keep their colour:
  1. `blur`
  2. tone (`adjust`, `grayscale`, `document`)
  3. annotations (`mark`, `arrow`, `text`, in input order)
  4. `crop`
  5. `straighten`
  6. `rotate`
  7. `flip`
  8. `resize`
- **Repeats:** for single-use ops (`adjust`, `grayscale`, `document`, `crop`, `straighten`, `rotate`, `flip`, `resize`) the **last** one wins.
- **Clamping:** numbers outside their range are clamped, not dropped. Unknown ops, wrong types and ops beyond `MAX_OPS`/`MAX_MARKS` are dropped and counted.

- [ ] **Step 1: Write the failing tests**

```python
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
        self.assertNotIn("rotate", [o["op"] for o in ops])          # 45 is not 90/180/270
        self.assertLessEqual(len(ops), MAX_OPS)
        self.assertLessEqual(sum(o["op"] in ("mark", "arrow", "text", "blur") for o in ops), MAX_MARKS)
        self.assertGreater(dropped, 0)
        self.assertEqual(validate_recipe("not a recipe"), ([], 0))

    def test_stage_order_keeps_coordinates_on_the_original(self):
        # 200x100 red-left/blue-right image; rotate listed first, crop second.
        out = apply_recipe(two_tone(200, 100), [{"op": "rotate", "degrees": 90},
                                                {"op": "crop", "box": [0, 0, 0.5, 1]}])
        self.assertEqual(out.size, (100, 100))        # cropped to the red half, then rotated
        self.assertEqual(out.getpixel((50, 50))[:3], (255, 0, 0))

    def test_annotations_keep_colour_after_grayscale(self):
        out = apply_recipe(Image.new("RGB", (400, 400), "white"),
                           [{"op": "mark", "shape": "rect", "box": [0.1, 0.1, 0.9, 0.9], "color": "#ff0000"},
                            {"op": "grayscale"}])
        self.assertEqual(out.convert("RGB").getpixel((40, 200)), (255, 0, 0))

    def test_blur_changes_only_the_box(self): ...   # pixel outside the box unchanged, inside changed

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

    def test_apply_does_not_mutate_input(self): ...      # input bytes (tobytes()) equal before and after
    def test_preview_is_small_and_same_recipe_applies(self): ...
        # preview of a 3000x2000 image is 900x600; the same crop box gives the same relative region
```

The helpers build the images in memory with Pillow (no fixture files). Put them at the top of the test file. The 50 MP case is a 8660×5774 grayscale image with EXIF Orientation 6.

- [ ] **Step 2: Run them and see them fail**

Run: `python -m unittest tests.test_image_edit -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'image_edit'`

- [ ] **Step 3: Implement `image_edit.py`**

Approach:
- One validator function per op in a dict `{op_name: validator}`.
- `apply_recipe` sorts by a `STAGE = {op: index}` table with a stable sort.
- Use `Image.MAX_IMAGE_PIXELS` as it is already set by the app (90 MP), and use `draft()` for big JPEGs before `thumbnail` so a 50 MP photo does not decode at full size.
- Fonts are loaded lazily and cached with `functools.lru_cache`.

- [ ] **Step 4: Run them and see them pass**

Run: `python -m unittest tests.test_image_edit -v`
Expected: all PASS; the 50 MP case finishes in under 3 s locally.

- [ ] **Step 5: Add `tests.test_image_edit` to `ci.yml`, run `python -m unittest tests.test_ci_coverage`, and commit**

```bash
git add image_edit.py tests/test_image_edit.py .github/workflows/ci.yml
git commit -m "Add edit recipes: validate and apply crop, tone, labels and blur"
```

---

### Task 2: Illustration cleaner and PNG (`illustration.py`)

**Files:**
- Create: `illustration.py`
- Test: `tests/test_illustration.py`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Produces:
  - `class IllustrationError(ValueError)`.
  - `clean_svg(text: str) -> str`:
    - takes model text that may contain prose or a ```svg fence around the `<svg>`;
    - returns a re-serialized, allowlisted SVG string with `xmlns="http://www.w3.org/2000/svg"`, its `viewBox` kept, and no `width`/`height`;
    - raises `IllustrationError` when there is no usable `<svg>` root.
  - `svg_png(svg: str, width: int = ILLUSTRATION_PX) -> bytes`: a PNG with a white background.
  - Constants: `MAX_SVG_CHARS`, `MAX_SVG_ELEMENTS`, `ILLUSTRATION_PX`, `ALLOWED_ELEMENTS`, `ALLOWED_ATTRIBUTES`.

**Allowlist (fixed):**
- **Rejection rules:**
  - Elements outside the allowlist are **removed with their subtree**.
  - Attributes outside the allowlist are removed.
  - Any attribute value containing `url(`, `javascript:`, `data:` or `&` is removed.
  - Input longer than `MAX_SVG_CHARS`, input containing `<!` (DOCTYPE, ENTITY, CDATA), or more than `MAX_SVG_ELEMENTS` elements after cleaning → `IllustrationError`.
  - Parse with `xml.etree.ElementTree.fromstring` only after the `<!` check.
- **Allowed elements:** `svg`, `g`, `rect`, `circle`, `ellipse`, `line`, `polyline`, `polygon`, `path`, `text`, `tspan`, `title`. No `defs`, `marker`, gradients, `use`, `image`, `style` or `foreignObject`, because fpdf2 renders the shapes reliably but these would differ between the PNG and the SVG download.
- **Allowed attributes:** `viewBox x y x1 y1 x2 y2 cx cy r rx ry width height d points transform fill stroke stroke-width stroke-linecap stroke-linejoin stroke-dasharray opacity fill-opacity stroke-opacity font-size font-weight text-anchor dominant-baseline`. `width`/`height` are allowed on shapes only, not on the root. `font-family` is forced to `DejaVu Sans, sans-serif` on the root.

- [ ] **Step 1: Write the failing tests**

```python
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

    def test_png_is_1600_wide_and_not_blank(self):
        png = Image.open(io.BytesIO(svg_png(clean_svg(GOOD))))
        self.assertEqual((png.width, png.height), (1600, 1200))
        self.assertGreater(len(set(png.convert("RGB").getdata())), 3)
        self.assertNotEqual(png.convert("RGB").getpixel((1360, 220)), (255, 255, 255))  # the sun

    def test_importing_illustration_does_not_import_heavy_libs(self): ...  # same shape as test_answer_pdf
```

- [ ] **Step 2: Run them and see them fail**

Run: `python -m unittest tests.test_illustration -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'illustration'`

- [ ] **Step 3: Implement `illustration.py`**

Approach for `svg_png`:
- Make an `fpdf.FPDF` page sized to the viewBox ratio, with DejaVu Sans registered as in `answer_pdf._fonts`.
- Draw with `fpdf.svg.SVGObject(svg).draw_to_page(pdf)`.
- Render page 1 with `pypdfium2` at the scale that gives `width` px.
- If fpdf2 cannot draw `<text>` with the registered DejaVu font, let it fall back to its core Helvetica font (labels are Latin-script Indonesian) and note that in the module docstring. The test above must still pass.

- [ ] **Step 4: Run them and see them pass**

Run: `python -m unittest tests.test_illustration -v`
Expected: all PASS.

- [ ] **Step 5: Add to `ci.yml` and commit**

```bash
git add illustration.py tests/test_illustration.py .github/workflows/ci.yml
git commit -m "Add illustration SVG allowlist and PNG rendering"
```

---

### Task 3: Ciel Image AI component and flow

**Files:**
- Create: `flow/components/ciel_image_ai.py`, `flow/image_ai/v1.0.0/Ciel_Image_AI.json`
- Test: `tests/test_image_ai_component.py`, `tests/test_flow_image_ai_v100_contract.py`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: the recipe schema in Task 1 (described in the edit prompt) and the allowlist in Task 2 (described in the illustration prompt).
- Produces (wire format between the app and the flow):
  - **Request** (Chat Input text, `json.dumps`):
    - Edit: `{"mode": "edit", "instruction": str, "image": "<base64 JPEG>", "width": int, "height": int}`
    - Illustration: `{"mode": "ilustrasi", "instruction": str}`
  - **Reply** (Chat Output text):
    - Edit: a JSON object `{"ops": [...], "catatan": str}`, where `catatan` is ≤ 160 characters in Indonesian telling the user what was done or why nothing could be.
    - Illustration: the SVG text.
  - **Failure:** the component raises `ValueError` whose message starts with `IMAGE_AI_UNAVAILABLE = "Ciel image AI unavailable"`. The same constant is copied into `app.py`.
- Produces (pure helpers, tested without Langflow):
  - `parse_request(text: str) -> dict`: validates mode, instruction length ≤ 300, base64 decodes, image ≤ 1 500 000 bytes; `ValueError` otherwise.
  - `build_payload(request: dict, model: str) -> dict`: the Chat Completions JSON.
  - `reply_text(response_json: dict, mode: str) -> str`.

**DeepSeek call (fixed):**
- Endpoint and timeout: `POST {api_base}/chat/completions`, `timeout=60`.
- Model and settings: `model="deepseek-flash"`, `"thinking": {"type": "disabled"}`, `temperature` 0.2 for edits and 0.7 for illustrations, `max_tokens` 1500 for edits and 8000 for illustrations.
- Edit request:
  - `"response_format": {"type": "json_object"}`.
  - The user message content is `[{"type": "text", "text": <instruction + image size>}, {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,…", "detail": "high"}}]`.
  - Images go in the **user** message only, because DeepSeek rejects images in system messages with a 400.
- Use `requests` in `asyncio.to_thread`, the same pattern as `ciel_vision_router._read_with_api`. The key comes from the global variable `DEEPSEEK_API_KEY` (`SecretStrInput`, value `"DEEPSEEK_API_KEY"`).
- **Edit system prompt** must state:
  - the full op table from Task 1, with normalized coordinates on the image as sent;
  - use only the ops needed;
  - never invent content;
  - when the request needs something the ops cannot do (remove background, change faces, add objects), return `{"ops": [], "catatan": "…"}` explaining that kindly;
  - reply with JSON only.
- **Illustration system prompt** must state:
  - one `<svg viewBox="0 0 800 600">` only;
  - flat educational style, labels in Indonesian, font-size ≥ 22;
  - only the Task 2 elements and attributes;
  - arrowheads as `polygon`;
  - no text outside the SVG;
  - at most 300 elements;
  - decline (reply `TOLAK: <alasan>`) for people's likenesses, violence or sexual content. The app shows the reason.

- [ ] **Step 1: Write the failing component tests** (`tests/test_image_ai_component.py`; load the module from `flow/components` with `importlib`, stubbing `langflow`/`lfx` imports the way `tests/test_vision_router.py` does)

```python
def test_edit_payload_puts_the_image_in_the_user_message(self):
    payload = build_payload(parse_request(edit_request()), "deepseek-flash")
    self.assertEqual(payload["model"], "deepseek-flash")
    self.assertEqual(payload["thinking"], {"type": "disabled"})
    self.assertEqual(payload["response_format"], {"type": "json_object"})
    system, user = payload["messages"]
    self.assertIsInstance(system["content"], str)
    self.assertEqual(user["content"][1]["image_url"]["url"][:23], "data:image/jpeg;base64,")
    for op in ("crop", "mark", "arrow", "text", "blur", "document", "straighten"):
        self.assertIn(op, system["content"])

def test_illustration_payload_has_no_image_and_no_json_mode(self): ...
    # user content is a plain string; no "response_format"; max_tokens 8000; system prompt names "polygon" and "TOLAK:"
def test_parse_request_rejects_bad_input(self):
    for bad in ("", "{}", '{"mode": "paint"}', json.dumps({"mode": "edit", "instruction": "x" * 301}),
                json.dumps({"mode": "edit", "instruction": "ok", "image": "@@@"}),
                json.dumps({"mode": "edit", "instruction": "ok", "image": base64_of(1_600_000)})):
        with self.assertRaises(ValueError):
            parse_request(bad)

def test_reply_that_is_not_json_is_an_error(self):
    with self.assertRaisesRegex(ValueError, "^Ciel image AI unavailable"):
        reply_text({"choices": [{"message": {"content": "Tentu! Berikut langkahnya..."}}]}, "edit")

def test_http_402_and_timeout_become_unavailable(self): ...
    # mocked requests.post: status 402, then requests.Timeout -> both ValueError starting with IMAGE_AI_UNAVAILABLE;
    # the API key never appears in the message
```

- [ ] **Step 2: Run them and see them fail**

Run: `python -m unittest tests.test_image_ai_component -v`
Expected: FAIL (file not found).

- [ ] **Step 3: Implement `flow/components/ciel_image_ai.py`**

It is a `Component` with:
- inputs `input_value` (`MessageTextInput`), `api_key`, `api_base` (`https://api.deepseek.com`, advanced), `model_name` (`deepseek-flash`, advanced);
- one output `reply` returning `Message(text=...)`.

- [ ] **Step 4: Run the component tests and see them pass**

Run: `python -m unittest tests.test_image_ai_component -v`
Expected: all PASS.

- [ ] **Step 5: Build the flow in local Langflow (`http://127.0.0.1:7860`) and export the snapshot**
  1. Create the flow: Chat Input → Ciel Image AI → Chat Output.
  2. On both Chat nodes, set `should_store_message` to **false**, so photos are not kept in Langflow's message table.
  3. Export the flow to `flow/image_ai/v1.0.0/Ciel_Image_AI.json`, normalized to the snapshot convention.
  4. Run one real edit and one real illustration in the Langflow playground. Paste the two replies into the PR description (the edit with the image base64 removed).

- [ ] **Step 6: Write the flow contract test** (`tests/test_flow_image_ai_v100_contract.py`) asserting:
  - exactly three nodes, connected Chat Input → Ciel Image AI → Chat Output;
  - the component code equals `flow/components/ciel_image_ai.py` line by line (the `test_flow_v1130_contract` pattern);
  - `should_store_message` is false on both Chat nodes;
  - the API key field holds the variable name `DEEPSEEK_API_KEY`, never a key;
  - `model_name` is `deepseek-flash`.

  Run: `python -m unittest tests.test_flow_image_ai_v100_contract -v` → PASS.

- [ ] **Step 7: Add both tests to `ci.yml` and commit**

```bash
git add flow/components/ciel_image_ai.py flow/image_ai tests/test_image_ai_component.py tests/test_flow_image_ai_v100_contract.py .github/workflows/ci.yml
git commit -m "Add Ciel Image AI flow: DeepSeek writes edit recipes and SVG illustrations"
```

---

### Task 4: Gateway allows the Image AI flow

**Files:**
- Modify: `tools/render_ngrok_policy.py`, `tools/render_nginx_gateway.py`, `.streamlit/secrets.toml.example` and `deploy/vps/.env.example` (add `IMAGE_FLOW_ID` and `AI_IMAGE_PER_DAY` next to `WRITER_FLOW_ID`)
- Test: `tests/test_gateway_policy.py`, `tests/test_nginx_gateway.py`

**Interfaces:**
- Produces: an optional `IMAGE_FLOW_ID` with the same rules as `WRITER_FLOW_ID`:
  - when it is empty, the policy is byte-identical to today's;
  - when it is set, only `POST /api/v1/run/<id>` (both ID forms) is allowed, under the same tight per-IP run limit;
  - **no** upload path is added, because the image travels inside the run JSON.

- [ ] **Step 1: Add the failing tests:**
  - `test_image_flow_run_is_allowed_but_not_upload` in both gateway test files;
  - `test_no_image_flow_keeps_policy_identical`.
- [ ] **Step 2: Run them and see them fail:** `python -m unittest tests.test_gateway_policy tests.test_nginx_gateway -v`
- [ ] **Step 3: Thread `image_flow_id=None` through `allowed_requests`, `check_settings`, `build_policy`, `main`, and through `FLOW_ID_NAMES`/`build_nginx_config`. Update both docstrings.**
- [ ] **Step 4: Run the tests and see them pass**
- [ ] **Step 5: Commit**

```bash
git add tools/render_ngrok_policy.py tools/render_nginx_gateway.py .streamlit/secrets.toml.example deploy/vps/.env.example tests/test_gateway_policy.py tests/test_nginx_gateway.py
git commit -m "Gateway: allow running the Image AI flow when IMAGE_FLOW_ID is set"
```

---

### Task 5: Edit gambar dialog (free manual edits + Pro "Minta AI")

**Files:**
- Modify: `app.py`, `beranda.py`
- Test: `tests/test_image_edit_app.py` (new, AppTest), `tests/test_beranda.py`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `image_edit.*` (Task 1), the wire format and `IMAGE_AI_UNAVAILABLE` (Task 3).
- Produces in `app.py`:
  - Config:
    - `IMAGE_FLOW_ID = get_config("IMAGE_FLOW_ID")`
    - `IMAGE_AI_ENABLED = bool(IMAGE_FLOW_ID and CHAT_STORE)`
    - `AI_IMAGE_PER_DAY = get_int_config("AI_IMAGE_PER_DAY", 3)`
  - Quota: `FEATURE_QUOTAS["gambar"] = (AI_IMAGE_PER_DAY, "Edit AI & ilustrasi bisa dipakai {limit} kali")`.
  - `IMAGE_AI_KIND = "image_ai"`.
  - `image_ai_refusal() -> CielError | None`: returns `pro_refusal(IMAGE_AI_ENABLED, "Edit AI & ilustrasi", IMAGE_AI_KIND) or check_rate_limit("gambar")`. Pro is checked first, so a free user never uses quota.
  - `ask_image_ai(mode: str, instruction: str, image: PIL.Image.Image | None = None) -> str | CielError`:
    - for edits, sends the image shrunk to 1024 px as a JPEG (quality 85) with its original `width`/`height`;
    - calls `ask_langflow(json.dumps(request), flow_id=IMAGE_FLOW_ID, timeout=90)`;
    - maps an error whose detail contains `IMAGE_AI_UNAVAILABLE` (detected the same way `ask_langflow` already detects `MODEL_UNAVAILABLE`) to `CielError("AI sedang tidak tersedia.\n\nEdit manual tetap bisa dipakai. Coba lagi sebentar lagi.")`.
  - The dialog reads an edit reply with `json.loads` and then `validate_recipe`; a reply that does not parse counts as zero valid ops.
  - `edit_dialog()`: `@st.dialog("Edit gambar", width="large")`.
- Produces in `beranda.py`:
  - `Template("edit_gambar", "Edit gambar", "", False, "edit_gambar")`
  - `Template("ilustrasi", "Ilustrasi", "", True, "ilustrasi")`
  - `templates_for` gains `image_ai_enabled: bool` and hides `ilustrasi` when it is false. `edit_gambar` is always shown.

**Dialog layout (decided; Ciel reviews it in the browser):**
1. `st.file_uploader("Foto", type=["jpg", "jpeg", "png", "webp", "gif"])`. Error: "Format ini belum bisa diedit. Pakai JPG atau PNG." The existing `MAX_IMAGE_BYTES` / `MAX_IMAGE_PIXELS` checks from `read_image` apply, so reuse that size check rather than copying it.
2. Two columns on desktop, stacked on phone:
   - **Left:** the preview (`st.image(preview(apply_recipe(...)))`).
   - **Right:** controls, grouped:
     - "Putar & potong": rotate left/right buttons, flip toggles, four crop sliders 0–45 % for each side.
     - "Warna": sliders for Kecerahan, Kontras and Ketajaman, plus the toggles "Hitam-putih" and "Rapikan dokumen".
     - "Teks": label input, position select (9 positions), size select (Kecil/Sedang/Besar = 0.04/0.07/0.11), colour picker.
     - "Ukuran": width number input.
3. **"Minta AI · Pro":** a text input (≤ 300 characters, placeholder "Contoh: potong soal nomor 3, lalu lingkari jawabannya") and the button "Terapkan".
   - Free or guest users see the lock line and the "Lihat paket Pro" button (the Riset dialog pattern).
   - The AI ops are kept in `st.session_state.edit_ai_ops`, keyed by the upload's SHA-256, and combined with the manual ops as `ai_ops + manual_ops`. Manual single-use ops come later, so they win.
   - The AI's `catatan` shows as a caption.
   - The button "Hapus edit AI" clears the AI ops.
   - A result with zero valid ops shows "AI belum menangkap maksudnya. Coba tulis lebih spesifik."
4. Format select PNG/JPG and `st.download_button("Unduh", …)`. The file name is `<original stem> - edit.<ext>`. The download is built from the full-size image only when the dialog reruns, never kept in session state.

**Wiring:** `render_beranda` handles `action == "edit_gambar"` by setting `st.session_state.open_edit = True`, and `"ilustrasi"` the same way (used in Task 6). The page opens the dialog where `open_riset` is handled today.

- [ ] **Step 1: Write the failing tests** (`tests/test_image_edit_app.py`, AppTest with `ask_langflow` patched; follow `tests/test_cek_kutipan_app.py` for Pro/quota fixtures)

```python
def test_manual_edit_works_for_a_guest_without_any_flow_call(self): ...
def test_ai_edit_checks_pro_then_quota_before_calling(self):
    # guest -> Pro message, no call; free account -> Pro message, no call;
    # Pro with quota used up -> quota message mentions "Edit AI & ilustrasi bisa dipakai 3 kali", no call;
    # Pro with quota -> exactly one ask_langflow call with flow_id=IMAGE_FLOW_ID and mode "edit"
def test_ai_ops_are_applied_and_cleared(self): ...
def test_ai_failure_keeps_manual_edits(self):
    # manual brightness set, ask_langflow returns CielError("... Ciel image AI unavailable ...")
    # -> "AI sedang tidak tersedia" shown, brightness slider value and preview unchanged
def test_ai_section_hidden_without_image_flow(self): ...
```

In `tests/test_beranda.py`, add `test_edit_gambar_always_shown_and_ilustrasi_needs_image_ai`.

- [ ] **Step 2: Run them and see them fail:** `python -m unittest tests.test_image_edit_app tests.test_beranda -v`
- [ ] **Step 3: Implement the config, gate, `ask_image_ai`, the dialog, the Beranda templates and the CSS**

Scope the CSS to `st-key-edit_*` keys, use only the token colours, and use no `font:` shorthand (Plan 1 gotcha: it breaks Material icons).
- [ ] **Step 4: Run the tests and see them pass,** then the whole suite: `python -m unittest discover -s tests -p "test_*.py"`. Expected: no new failures (local secrets can break `test_chat_store`; compare with `main`).
- [ ] **Step 5: Run the app locally (`streamlit run app.py`) and test it in the Browser pane:**
  - a phone photo of a worksheet: Rapikan dokumen + crop + label, then download PNG and JPG;
  - dark and light themes;
  - 375 px width.
- [ ] **Step 6: STOP. Ciel checks it in the browser and says "commit".** Then:

```bash
git add app.py beranda.py tests/test_image_edit_app.py tests/test_beranda.py .github/workflows/ci.yml
git commit -m "Add Edit gambar: free manual edits and Pro AI edits"
```

---

### Task 6: Ilustrasi dialog (Pro)

**Files:**
- Modify: `app.py`
- Test: `tests/test_image_edit_app.py` (extend)

**Interfaces:**
- Consumes:
  - `image_ai_refusal()`, `ask_image_ai("ilustrasi", text)` (Task 5);
  - `clean_svg`, `svg_png`, `IllustrationError` (Task 2).
- Produces: `illustration_dialog()`, `@st.dialog("Ilustrasi")`.

**Dialog:**
- **Inputs:** `st.text_area("Mau ilustrasi apa?", max_chars=300, placeholder="Contoh: siklus air lengkap dengan label penguapan, kondensasi, presipitasi")`, the caption "Gambar diagram dengan label, bukan foto. Kuota 3 per hari." (the number comes from `AI_IMAGE_PER_DAY`), and the button "Buat ilustrasi".
- **Free and guest users:** the lock line and "Lihat paket Pro".
- **Result:**
  - Shown with `st.image(png)` inside `st.container(key="ilustrasi_paper")`, with CSS for a white background and a `var(--c-line)` border.
  - Two download buttons: "Unduh PNG" and "Unduh SVG" (the cleaned SVG; file name `Ilustrasi - <first 5 words>.png/.svg`).
  - The last result is kept in `st.session_state.ilustrasi_last` until the dialog closes.
- **Replies that need handling:**
  - A reply starting with `TOLAK:` shows its reason as an info message. It still counts toward the quota.
  - `IllustrationError` shows "Ilustrasinya gagal digambar. Coba lagi dengan deskripsi lain." and logs the reason with `logger.warning` (no SVG in the log).

- [ ] **Step 1: Write the failing tests:**
  - `test_illustration_is_pro_only_and_uses_the_quota`;
  - `test_illustration_shows_png_never_raw_svg`: asserts no `<svg` text in any markdown/html element and one `st.image`;
  - `test_refusal_reason_is_shown`;
  - `test_broken_svg_shows_friendly_error`.
- [ ] **Step 2: Run them and see them fail:** `python -m unittest tests.test_image_edit_app -v`
- [ ] **Step 3: Implement the dialog and wire the `"ilustrasi"` Beranda action**
- [ ] **Step 4: Run the tests and see them pass,** then the whole suite.
- [ ] **Step 5: Browser check against the local Image AI flow** (needs Task 3's flow in local Langflow and `IMAGE_FLOW_ID` in local secrets):
  - try three prompts: "siklus air", "sel hewan berlabel", "grafik penawaran dan permintaan";
  - check both themes and phone width.
- [ ] **Step 6: STOP. Ciel checks it and says "commit".** Then:

```bash
git add app.py tests/test_image_edit_app.py
git commit -m "Add Pro illustrations drawn as labelled diagrams"
```

---

### Task 7: Privacy, terms and pricing

**Files:**
- Modify: `privacy.py`, `terms.py`, `pricing.py`, `docs/LEGAL.md`
- Test: `tests/test_privacy.py`, `tests/test_terms.py`, `tests/test_pricing.py`

**Decided copy:**
- **`privacy.py` `processing`:** add after the photo line: "Jika kamu memakai Edit AI atau Ilustrasi (Ciel Pro), foto dan instruksimu dikirim ke DeepSeek untuk dipahami. DeepSeek dapat memakai data yang diterimanya untuk melatih model, jadi jangan kirim foto berisi data pribadi atau rahasia. Edit manual diproses di server Ciel saja."
- **`SUBPROCESSORS`:** DeepSeek's role becomes "model AI yang menyusun jawaban, memahami foto untuk Edit AI, dan menggambar ilustrasi".
- **Change note:** "Perubahan <tanggal rilis>: foto yang kamu pilih untuk Edit AI dikirim ke DeepSeek."
- **`terms.LEGAL_VERSION`:** the release date (`YYYY-MM-DD`). This forces the consent gate again, as for v1.13.0.
- **`pricing.py`:** the Pro feature "Edit gambar dengan AI & ilustrasi (3 per hari)". Free gets "Edit gambar".
- **`docs/LEGAL.md`:** DeepSeek row: photos for Edit AI, linked to the DeepSeek privacy policy line already cited.

- [ ] **Step 1: Write the failing tests:**
  - `test_ai_photo_edit_to_deepseek_is_disclosed`;
  - `test_legal_version_is_after_2026_11_03`;
  - `test_pro_lists_ai_image_with_quota`;
  - `test_free_lists_manual_edit`.
- [ ] **Step 2: Run them and see them fail:** `python -m unittest tests.test_privacy tests.test_terms tests.test_pricing -v`
- [ ] **Step 3: Update the copy and constants**
- [ ] **Step 4: Run the tests and see them pass**
- [ ] **Step 5: Commit**

```bash
git add privacy.py terms.py pricing.py docs/LEGAL.md tests/test_privacy.py tests/test_terms.py tests/test_pricing.py
git commit -m "Disclose AI photo edits to DeepSeek and list image features on Pricing"
```

---

### Task 8: Main flow v1.14.2 (prompt v15.2)

**Files:**
- Create: `flow/v1.14.2/Ciel_AI_Long-Term_Memory_Master.json`, `tests/test_flow_v1142_contract.py`
- Modify: `.github/workflows/ci.yml`

**Change:** this is a copy of v1.14.1 where only the Agent `Agent-puarO` system_prompt changes:
- The header goes from v15.1 to v15.2.
- The line containing `belum bisa membuat ilustrasi atau mengedit foto` is replaced by these two lines:
  - `EDIT_TOOL = "- Untuk mengedit foto (potong, putar, rapikan foto catatan, beri label, blur), arahkan pengguna ke tombol Edit gambar di Beranda. Pengguna Pro bisa meminta AI di sana. Ciel tidak bisa menghapus latar atau mengubah isi foto."`
  - `ILLUSTRATION_TOOL = "- Untuk ilustrasi, arahkan pengguna Pro ke Ilustrasi di Beranda: hasilnya diagram berlabel, bukan foto atau lukisan. Di dalam jawaban tetap pakai ciel-grafik untuk grafik."`

- [ ] **Step 1: Write the failing contract test,** modelled on `tests/test_flow_v1141_contract.py`:
  - only the prompt changes;
  - the header is v15.2;
  - each new line appears once, inside the "PDF dan gambar:" block;
  - "belum bisa membuat ilustrasi" is gone;
  - nothing else changes;
  - the prompt examples still parse.
- [ ] **Step 2: Run it and see it fail:** `python -m unittest tests.test_flow_v1142_contract -v`
- [ ] **Step 3: Write the snapshot** with the v1.14.1 serialization (CRLF, `indent=2`, `ensure_ascii=False`, no trailing newline); check that the round trip is byte-identical.
- [ ] **Step 4: Run it and see it pass;** add it to `ci.yml`.
- [ ] **Step 5: Test on a separate copy of the flow in local Langflow** with the cases below, with a small script that posts each case to the test copy and runs `answer_blocks.parse_answer` on the reply. Warn Ciel first: about 6 DeepSeek calls.
  - "bisa edit foto gak?"
  - "rapikan foto catatan ini" (with a photo)
  - "buatkan ilustrasi sel hewan"
  - "hapus background foto ini"

  Expected:
  - the tools are named;
  - no claim of background removal or painting;
  - no `Broken` blocks.
- [ ] **Step 6: Commit**

```bash
git add flow/v1.14.2 tests/test_flow_v1142_contract.py .github/workflows/ci.yml
git commit -m "Flow v1.14.2: point to Edit gambar and Ilustrasi"
```

---

### Task 9: Docs and rollout

**Files:**
- Modify: `CHANGELOG.md`, `docs/ARCHITECTURE.md`, `RELEASE_CHECKLIST.md`, `README.md`, `docs/BACKUP_AND_DISASTER_RECOVERY.md` (the flow list), `SECURITY.md` (DeepSeek key now also used by the Image AI flow)

- [ ] **Step 1: Write the docs:**
  - **ARCHITECTURE:**
    - the recipe stage order;
    - the SVG allowlist;
    - why the screen shows only PNG;
    - the Image AI wire format;
    - quota key `gambar`;
    - `should_store_message` off.
  - **CHANGELOG:** one entry for the app and one for flow v1.14.2.
  - **RELEASE_CHECKLIST:** the rollout order below.
- [ ] **Step 2: Run the full suite** (`python -m unittest discover -s tests -p "test_*.py"`) and commit:

```bash
git add CHANGELOG.md RELEASE_CHECKLIST.md docs README.md SECURITY.md
git commit -m "Document image editing and illustrations"
```

- [ ] **Step 3: Push and open a PR.** Wait for CI to pass and for Ciel to merge.
- [ ] **Step 4: Rollout.** Each step is done with Ciel and checked before the next.
  1. Import `flow/image_ai/v1.0.0/Ciel_Image_AI.json` into production Langflow and note its ID.
  2. Add `IMAGE_FLOW_ID` to `.env`. Run `python tools/render_ngrok_policy.py`, then restart ngrok **not as admin** (the watchdog starts it). Run `python tools/check_gateway.py`.
  3. Add `IMAGE_FLOW_ID` to the Streamlit Cloud secrets. Reboot Cloud if an ImportError shows.
  4. Check the live app:
     - a manual edit as a guest;
     - an AI edit and an illustration on Ciel's Pro account;
     - the 4th AI request of the day shows the quota message.
  5. Back up the production main flow to `~/.ciel_ai/flow_backups/main_before_v1.14.2_<timestamp>.json`, PATCH only the prompt into the **live** data, and check that no other template value changed.
  6. Re-test "bisa edit foto gak?" live.
