# Ciel Visual Answers Implementation Plan (Plan 1 of 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Ciel's answers easy to read and varied, render math beautifully, draw graphs and diagrams, turn any answer into a shareable image, and export a PDF when the user asks for one.

**Architecture:** The model writes plain markdown with `$…$` math, plus two fenced block types (`ciel-grafik`, `ciel-kuis`) holding strict JSON. The app owns all drawing. A pure parser turns the answer into segments. A matplotlib renderer draws visuals: themed SVG on screen, light PNG for exports. One fpdf2 layout engine builds the PDF, and the answer image is page 1 of that PDF rasterized with pypdfium2. The model never writes image URLs, so the existing `strip_markdown_images` guard stays as it is.

**Tech Stack:** Python 3.14 (Cloud) / 3.10 (local), Streamlit 1.66 (`st.markdown` KaTeX, `st.html`), numpy (already installed through pandas), matplotlib (new), fpdf2 (new), pypdfium2 (new), Langflow flow snapshot v1.14.0.

**Spec:** No separate spec doc. The decisions Ciel made on 2026-11-04 are recorded in **Decisions** below, and every task argues from them.

## Decisions (spec)

1. **Image output covers:** (a) graphs and diagrams inside answers, (b) any answer saved as an image. Illustration and image editing are **Plan 2** (simple edits free for all, AI edits **Pro only**). Until Plan 2 ships, Ciel must not claim it can make illustrations or edit photos.
2. **PDF:** only when the user asks for one ("pdf", "cetak", "lembar soal" …). No PDF button on other answers.
3. **Access:** everything in this plan is for **all users**, free and guests included. It uses no paid API.
4. **Tone:** "manusiawi, gak bikin pusing, gak monoton". Answers open with the answer, keep paragraphs short, and pick a shape that fits the content (steps, table, graph, analogy, quiz) instead of one fixed template.
5. **Math must be "sangat-sangat menarik":** rendered formulas, labelled steps, a highlighted final answer, a check step, a graph when the problem has one, and an optional interactive "Coba sendiri" quiz.

## Global Constraints

- No `Co-Authored-By` / "Generated with Claude" lines in commits or PRs (Ciel's standing rule).
- UI tasks (Task 4, Task 6) stop before their commit. Ciel checks them in the browser in **both themes and at phone width** and says "commit". Pure-module tasks commit normally.
- Deploy order: the app (Tasks 1–6) is **live on Streamlit Cloud before** flow v1.14.0 goes live. Otherwise users see raw `ciel-grafik` JSON.
- Use `matplotlib.figure.Figure` directly and never `pyplot` (Streamlit sessions share threads). Set the `Agg` backend. Import matplotlib, fpdf and pypdfium2 lazily inside functions so app start-up does not slow down.
- Never `eval`/`exec` model text. Formulas go through `safe_expr` (AST allowlist, float math).
- Dependencies stay hash-locked. After editing `requirements.in`, regenerate with exactly `uv pip compile requirements.in --universal --python-version 3.14 --generate-hashes -o requirements.txt`. `pip-audit -r requirements.txt` must be clean.
- Every new `tests/test_*.py` is added to the unittest list in `.github/workflows/ci.yml` (`tests/test_ci_coverage.py` enforces this).
- Earlier flow snapshots stay byte-identical. The only flow change is the Agent `system_prompt` in the new `flow/v1.14.0/`.
- Numbers keep the Indonesian format (`2,5`, `1.065.600,71`), inside math as well.
- Fixed block limits: `ciel-grafik` ≤ 4 per answer, `ciel-kuis` ≤ 20 per answer, each block's JSON ≤ 4 000 characters.
- Visible copy is Indonesian. Use only colour tokens from `app.py` (`--c-text`, `--c-muted`, `--c-line`, `--c-accent`, `--c-ok`, `--c-warn`, `--c-err`, `--c-raised`). No new hex colours on screen.

## Review Focus

1. **Currency dollars.** Given "harga $5 dan $10", the user sees `$5` and `$10` as text, not a KaTeX span "5 dan ". Pinned by `test_currency_dollars_are_escaped` (Task 2).
2. **A broken block never breaks the answer.** Bad JSON, an unknown `jenis`, an oversized block or a fence with no closing marker: the rest of the answer still renders, the block shows a short muted note, and raw JSON never appears. Pinned by `test_broken_blocks_degrade` (Task 2) and `test_broken_block_shows_note_not_json` (Task 4).
3. **Hostile or pathological formulas.** `__import__('os')`, `x.__class__`, `9**9**9`, `1/x`, `tan(x)` and a 500-character formula are rejected or plotted with gaps. They never hang, crash or run code. Pinned by `test_rejects_non_math` and `test_singularities_become_gaps` (Task 1), and `test_asymptote_plot_renders` (Task 3).
4. **Dark mode.** Visuals stay readable in both themes, and switching theme needs no re-render (the SVG uses CSS variables). Pinned by `test_svg_uses_theme_tokens_only` (Task 3) plus Ciel's browser check.
5. **Huge or exotic answers in exports.** A 4 000-word answer with 20 quizzes paginates in the PDF. The PNG stops at its maximum height and ends with a "Lanjutan ada di chat Ciel." line. Emoji and non-Latin text never raise. Pinned by `test_long_answer_paginates_and_png_is_capped` and `test_emoji_and_symbols_do_not_raise` (Task 5).

---

### Task 1: Safe formula evaluator

**Files:**
- Create: `safe_expr.py`
- Test: `tests/test_safe_expr.py`

**Interfaces:**
- Produces: `class ExpressionError(ValueError)`, which carries an Indonesian message. Also produces `compile_expression(text: str) -> Callable[[numpy.ndarray], numpy.ndarray]`, which parses once and returns a vectorised function of `x`. Non-finite results become `nan`.
- Grammar: float literals, `x`, `pi`, `e`, `+ - * / **`, unary `-`, parentheses. Functions: `sin cos tan asin acos atan sqrt exp abs ln` (natural log) and `log` (base 10, as Indonesian schools use it). Preprocessing turns `^` into `**`, `×` into `*` and `−` into `-`, and adds implicit multiplication (`2x`, `3(x+1)`, `(x+1)(x-1)`, `2pi`). Limits: ≤ 120 characters, ≤ 60 AST nodes. Every constant becomes a float before evaluation, so no big-int powers can run.

- [ ] **Step 1: Write the failing tests**

```python
class SafeExprTest(unittest.TestCase):
    def test_school_notation(self):
        f = compile_expression("2x^2 - 4x + 3")
        self.assertEqual(f(np.array([1.0]))[0], 1.0)
        self.assertAlmostEqual(compile_expression("log(100) + ln(e)")(np.array([0.0]))[0], 3.0)
        self.assertAlmostEqual(compile_expression("(x+1)(x-1)")(np.array([3.0]))[0], 8.0)

    def test_rejects_non_math(self):
        for text in ("__import__('os')", "x.__class__", "open('a')", "[x]", "x if x else 1",
                     "lambda: 1", "y + 1", "x" * 121):
            with self.subTest(text=text), self.assertRaises(ExpressionError):
                compile_expression(text)

    def test_huge_powers_are_fast_and_finite_or_nan(self):
        start = time.perf_counter()
        y = compile_expression("9**9**9")(np.linspace(-1, 1, 5))
        self.assertLess(time.perf_counter() - start, 0.5)
        self.assertTrue(np.all(np.isnan(y)))

    def test_singularities_become_gaps(self):
        y = compile_expression("1/x")(np.array([-1.0, 0.0, 1.0]))
        self.assertTrue(np.isnan(y[1]))
        self.assertEqual((y[0], y[2]), (-1.0, 1.0))
```

- [ ] **Step 2: Run to verify they fail.** Run `python -m unittest tests.test_safe_expr -v`. Expected: `ModuleNotFoundError: safe_expr`.
- [ ] **Step 3: Implement `compile_expression` in `safe_expr.py`.** Preprocess with regexes, then `ast.parse(mode="eval")`, then walk an allowlist of node types and compile into nested closures over numpy. Evaluate under `np.errstate(all="ignore")` and map `±inf` to `nan`.
- [ ] **Step 4: Run to verify they pass.** Run `python -m unittest tests.test_safe_expr -v`. Expected: 4 tests OK.
- [ ] **Step 5: Add `tests.test_safe_expr` to `ci.yml`, then commit.** Message: `Add a safe formula evaluator for graphs`.

---

### Task 2: Answer segments and math tidy-up

**Files:**
- Create: `answer_blocks.py`
- Test: `tests/test_answer_blocks.py`

**Interfaces:**
- Consumes: `safe_expr.compile_expression` (validation only: the formula must compile).
- Produces (frozen dataclasses):
  - `Markdown(text: str)`
  - `Visual(spec: dict)`, normalised with defaults filled in
  - `Quiz(soal: str, pilihan: tuple[str, ...], jawaban: int | str, pembahasan: str)`
  - `Broken(kind: str, reason: str)`, where `kind` ∈ {"grafik", "kuis"}
  - `VISUAL_KINDS = ("fungsi", "batang", "garis", "garis-bilangan", "bangun", "alur")`
  - `parse_answer(text: str) -> list[Markdown | Visual | Quiz | Broken]`, which runs `tidy_math` on every `Markdown` segment
  - `tidy_math(markdown: str) -> str`
- `ciel-grafik` schemas. Keys are exact; unknown keys are dropped and missing required keys mean `Broken`.

| jenis | required | optional | limits |
|---|---|---|---|
| `fungsi` | `fungsi: [{rumus, label?}]`, `x: [min, max]` | `judul`, `y: [min, max]`, `titik: [{x, y, label?}]` | 1–4 functions; `0 < max-min ≤ 1000`; ≤ 10 points |
| `batang` | `label: [str]`, `nilai: [num]` (same length) | `judul`, `satuan` | 1–12 bars |
| `garis` | `x: [str\|num]`, `seri: [{label, nilai: [num]}]` | `judul`, `satuan` | ≤ 4 series, ≤ 50 points each, lengths equal `x` |
| `garis-bilangan` | `interval: [{dari, sampai, dari_tutup, sampai_tutup}]` (`dari`/`sampai` may be `null` = ∞) | `judul`, `titik: [num]` | ≤ 3 intervals |
| `bangun` | `bentuk` ∈ {`segitiga`, `persegi-panjang`, `lingkaran`} plus its labels: `sisi: {a, b, c}` and optional `tinggi` / `panjang`, `lebar` / `jari_jari` (strings such as `"8 cm"`) | `judul` | labels ≤ 20 chars |
| `alur` | `langkah: [str]` | `judul`, `siklus: bool` | 2–8 steps, ≤ 60 chars each |

- `ciel-kuis`: `soal` (required), `pilihan` (2–5 strings, optional), `jawaban` (an index into `pilihan` when `pilihan` is given, else a string), `pembahasan` (optional).
- `tidy_math` (outside code fences and inline code only): converts `\( … \)` to `$…$` and `\[ … \]` to `$$…$$`. Inside math spans it turns `digit,digit` into `digit{,}digit`, so KaTeX shows no space after the decimal comma. It escapes currency dollars as `\$`: a `$` followed by a digit whose would-be span ends right after whitespace, or a `$` on a line with an odd count of unescaped `$`.

- [ ] **Step 1: Write the failing tests**

```python
GRAFIK = '```ciel-grafik\n{"jenis": "fungsi", "fungsi": [{"rumus": "x^2 - 4x + 3"}], "x": [-1, 5]}\n```'
KUIS = '```ciel-kuis\n{"soal": "Akar dari $x^2=9$?", "pilihan": ["3", "±3"], "jawaban": 1}\n```'

def test_splits_markdown_visual_and_quiz(self):
    segs = parse_answer(f"Intro.\n\n{GRAFIK}\n\nTengah.\r\n\n{KUIS}\n\nPenutup.")
    self.assertEqual([type(s).__name__ for s in segs],
                     ["Markdown", "Visual", "Markdown", "Quiz", "Markdown"])
    self.assertEqual(segs[1].spec["jenis"], "fungsi")
    self.assertEqual(segs[3].jawaban, 1)

def test_broken_blocks_degrade(self):
    cases = ['```ciel-grafik\n{"jenis": "pie"}\n```',
             '```ciel-grafik\n{jenis: fungsi}\n```',
             '```ciel-grafik\n{"jenis": "fungsi", "fungsi": [{"rumus": "__import__(1)"}], "x": [0, 1]}\n```',
             '```ciel-kuis\n{"soal": "a", "pilihan": ["x"], "jawaban": 3}\n```',
             '```ciel-grafik\n' + '{"jenis": "alur", "langkah": ["a"' + ', "a"' * 3000 + ']}\n```',
             'Teks.\n\n```ciel-grafik\n{"jenis": "alur"']           # never closed
    for text in cases:
        with self.subTest(text=text[:40]):
            segs = parse_answer(text)
            self.assertTrue(any(isinstance(s, Broken) for s in segs))
            self.assertFalse(any("{" in s.text for s in segs if isinstance(s, Markdown)))

def test_fifth_visual_is_broken(self):
    segs = parse_answer("\n\n".join([GRAFIK] * 5))
    self.assertEqual([type(s).__name__ for s in segs][-1], "Broken")

def test_currency_dollars_are_escaped(self):
    self.assertEqual(tidy_math("harga $5 dan $10"), r"harga \$5 dan \$10")
    for kept in ("$5x + 3 = 8$", "$x^2$", "$$\\frac{1}{2}$$", "`$5`"):
        self.assertEqual(tidy_math(kept), kept)

def test_decimal_comma_and_delimiters(self):
    self.assertEqual(tidy_math(r"Jadi \(x = 2,5\)."), "Jadi $x = 2{,}5$.")
    self.assertEqual(tidy_math(r"\[y = 0,25x\]"), "$$y = 0{,}25x$$")
    self.assertEqual(tidy_math("1,5 kg"), "1,5 kg")   # outside math: unchanged
```

- [ ] **Step 2: Run to verify they fail.** Run `python -m unittest tests.test_answer_blocks -v`. Expected: `ModuleNotFoundError: answer_blocks`.
- [ ] **Step 3: Implement `parse_answer`, the per-kind validators and `tidy_math` in `answer_blocks.py`.** Fence regex: ```` ^```[ \t]*(ciel-grafik|ciel-kuis)[ \t]*\r?\n(.*?)^```[ \t]*$ ```` with `re.M | re.S`. A fence that opens and never closes runs to the end of the text and becomes `Broken`.
- [ ] **Step 4: Run to verify they pass.** Run `python -m unittest tests.test_answer_blocks -v`. Expected: OK.
- [ ] **Step 5: Add to `ci.yml`, then commit.** Message: `Parse answers into markdown, graph and quiz segments`.

---

### Task 3: Visual renderer (themed SVG on screen, light PNG for export)

**Files:**
- Create: `visuals.py`
- Modify: `requirements.in` (add `matplotlib`), `requirements.txt` (re-lock)
- Test: `tests/test_visuals.py`

**Interfaces:**
- Consumes: `answer_blocks.Visual.spec`, `safe_expr.compile_expression`.
- Produces:
  - `build_figure(spec: dict, palette: dict) -> matplotlib.figure.Figure`
  - `render_svg(spec: dict) -> str`: an `<svg>` string with `width="100%"`, no fixed height, `viewBox` kept, `role="img"`, and `aria-label=describe(spec)`. Every colour in it is a CSS variable.
  - `render_png(spec: dict, width_px: int = 1200) -> bytes`, in the light palette
  - `describe(spec: dict) -> str`: Indonesian alt text, e.g. "Grafik fungsi f(x) = x^2 - 4x + 3 untuk x dari -1 sampai 5"
  - `LIGHT: dict`, a palette with the light token hex values from `app.py`
- Approach for SVG theming: draw with a sentinel palette (`#010101` text, `#020202` axis/grid, `#030303`–`#060606` series, `#070707` fill), set `svg.fonttype = "none"` so labels stay real text in the page font, then swap each sentinel in the `style="…"` attributes for `var(--c-text)`, `var(--c-line-strong)`, `var(--c-accent)`, `var(--c-ok)`, `var(--c-warn)`, `var(--c-err)` and `var(--c-raised)`. Make the figure background transparent.
- Drawing rules: `fungsi` samples 600 points, breaks lines at `nan` and at jumps larger than 10× the robust y-range (asymptotes), auto-clips y to the 2nd–98th percentile when `y` is missing, labels points, and draws axes through 0. `garis-bilangan` draws open and closed circles with shaded intervals. `bangun` is schematic and carries a small "(tidak sesuai skala)" note. `alur` draws rounded boxes with arrows, in a single row on narrow content and a ring when `siklus`. One `judul` above the figure; no chart junk.

- [ ] **Step 1: Write the failing tests**

```python
# PROMPT_EXAMPLE: {jenis: json string} holding the six JSON examples copied verbatim from Task 7.
# visual_from_json(s): wrap s in a ciel-grafik fence, parse_answer it, assert one Visual, return .spec.
# The six example specs from Task 7's prompt copy, passed through answer_blocks.parse_answer
# so the renderer is tested on exactly what the model is taught to write.
SPECS = {kind: visual_from_json(PROMPT_EXAMPLE[kind]) for kind in VISUAL_KINDS}

def valid_fungsi(rumus, x):   # test helper
    return visual_from_json(json.dumps({"jenis": "fungsi", "fungsi": [{"rumus": rumus}], "x": x}))

def valid_alur(langkah):      # test helper
    return visual_from_json(json.dumps({"jenis": "alur", "langkah": langkah}))

def test_every_kind_renders_png_and_svg(self):
    for kind, spec in SPECS.items():
        with self.subTest(kind=kind):
            self.assertTrue(render_png(spec).startswith(b"\x89PNG"))
            self.assertIn("<svg", render_svg(spec))

def test_svg_uses_theme_tokens_only(self):
    for spec in SPECS.values():
        svg = render_svg(spec)
        self.assertNotRegex(svg, r"#0[0-7]0[0-7]0[0-7]")          # no sentinel left
        self.assertNotRegex(svg, r"(fill|stroke):\s*#(?!ffffff00)") # no hard colours
        self.assertIn('width="100%"', svg)
        self.assertIn('role="img"', svg)

def test_asymptote_plot_renders(self):
    spec = valid_fungsi("tan(x)", x=[-6, 6])
    start = time.perf_counter()
    render_png(spec)
    self.assertLess(time.perf_counter() - start, 3)

def test_labels_are_escaped_in_svg(self):
    svg = render_svg(valid_alur(["<script>alert(1)</script>", "b"]))
    self.assertNotIn("<script>", svg)
```

- [ ] **Step 2: Run to verify they fail.** Run `python -m unittest tests.test_visuals -v`. Expected: `ModuleNotFoundError: visuals`.
- [ ] **Step 3: Add `matplotlib` to `requirements.in`, re-lock with the command in Global Constraints, then `pip install --require-hashes -r requirements.txt`.**
- [ ] **Step 4: Implement `visuals.py` with the interfaces above.**
- [ ] **Step 5: Run to verify they pass.** Run `python -m unittest tests.test_visuals tests.test_supply_chain -v`. Expected: OK.
- [ ] **Step 6: Add to `ci.yml`, then commit.** Message: `Draw graphs and diagrams from answer specs`.

---

### Task 4: Render segments in the chat

**Files:**
- Modify: `app.py` (assistant branch of the message loop, around `app.py:5468-5478`, and the CSS block)
- Test: `tests/test_chat_view.py` (new test class)

**Interfaces:**
- Consumes: `answer_blocks.parse_answer`, `Markdown/Visual/Quiz/Broken`, `visuals.render_svg`, `visuals.describe`.
- Produces: `render_answer_body(text: str, key_prefix: str) -> None` in `app.py`. It replaces the two plain `st.markdown(before)` / `st.markdown(after)` calls, while `answer_parts` and the source buttons stay where they are.
- Rendering per segment:
  - `Markdown`: `st.markdown`.
  - `Visual`: `st.html(f'<figure class="ciel-visual">{svg}</figure>')`, with `render_svg` wrapped in `st.cache_data(max_entries=256)` keyed by `json.dumps(spec, sort_keys=True)`.
  - `Quiz`: a `st.container(key=f"{key_prefix}_quiz{n}")` card titled "Coba sendiri". `soal`, `pilihan` and `pembahasan` go through `tidy_math` before `st.markdown`, because they hold math too. With `pilihan` it shows `st.radio` (no default) plus a "Cek jawaban" button, then a green/red line using `--c-ok` / `--c-err` and the `pembahasan`. Without `pilihan` it shows `st.expander("Lihat jawaban")`.
  - `Broken`: `st.caption("Grafik ini tidak bisa ditampilkan.")` or `"Kuis ini tidak bisa ditampilkan."`.
- CSS: answer blockquotes (`[data-testid="stChatMessage"] blockquote`) become a callout with a `--c-raised` background, a 3px `--c-accent` left border and an 8px radius. `.ciel-visual` gets `max-width: 640px; margin: 0.5rem 0`. KaTeX display blocks get `overflow-x: auto`, so long formulas scroll inside themselves instead of the page at 375px.

- [ ] **Step 1: Write the failing AppTest tests** (follow the existing `AnswerDisplayTest` setup and mocks in `tests/test_chat_view.py`):
  - `test_visual_block_renders_as_figure`: an assistant message containing `GRAFIK` produces one `st.html` element whose body contains `<svg` and `ciel-visual`, and no element's text contains `"jenis"`.
  - `test_quiz_checks_the_choice`: selecting index 1 in the radio and clicking "Cek jawaban" shows text containing "Benar".
  - `test_broken_block_shows_note_not_json`: an answer containing `{"jenis": "pie"}` shows the caption "Grafik ini tidak bisa ditampilkan." and no markdown element contains `"pie"`.
  - `test_plain_answer_unchanged`: an answer with no blocks renders exactly the same markdown elements as before.
- [ ] **Step 2: Run to verify they fail.** Run `python -m unittest tests.test_chat_view -v`. Expected: the 4 new tests FAIL; the old ones pass.
- [ ] **Step 3: Implement `render_answer_body` and the CSS.**
- [ ] **Step 4: Run to verify they pass.** Run `python -m unittest tests.test_chat_view tests.test_theme tests.test_app_hygiene -v`. Expected: OK.
- [ ] **Step 5: Ciel's browser check.** Run `streamlit run app.py` and paste a fixture answer (one of each `jenis` plus a quiz) through the cache, or a test chat. Check dark and light themes at 375px and desktop. Look for contrast, hover states and long-formula scrolling. **Wait for "commit".**
- [ ] **Step 6: Commit.** Message: `Show graphs, quizzes and callouts in answers`.

---

### Task 5: PDF and answer-image export

**Files:**
- Create: `answer_pdf.py`, `assets/fonts/Geist-Regular.ttf`, `assets/fonts/Geist-SemiBold.ttf`, `assets/fonts/OFL.txt` (from the official `vercel/geist-font` release, SIL OFL 1.1)
- Modify: `riset_export.py:183` (`report_filename` gains `ext="docx"`), `requirements.in` / `requirements.txt` (add `fpdf2`, `pypdfium2`)
- Test: `tests/test_answer_pdf.py`

**Interfaces:**
- Consumes: `answer_blocks.parse_answer`, `visuals.render_png`, `chat_sources.answer_parts` / `Source(number, title, url, domain)`, `riset_export.inline_runs`, `riset_export.report_filename(topic, prefix, ext)`.
- Produces:
  - `answer_pdf(content: str, title: str) -> bytes`: A4, 18 mm margins, Geist body 11 pt, DejaVu Sans (from `matplotlib.get_data_path()`) as the fallback font for symbols. Layout: header with "Ciel" and the date in Indonesian ("4 November 2026"), then the title, then the body. Body elements: headings, bullets, numbered lists, pipe tables (`pdf.table`), blockquote callouts, inline math through `latex_to_text`, display math as a mathtext PNG (falling back to `latex_to_text` when mathtext raises), visuals as `render_png` at 150 mm wide, and quizzes as numbered "Latihan" items with lettered options. Then "Kunci jawaban" on a new page (answer plus pembahasan), then "Sumber" (number, title, domain, URL). Footer: "Dibuat dengan Ciel · ciel-ai.web.id · {page}".
  - `answer_png(content: str, title: str) -> bytes`: the same layout on a 120 × 600 mm page. Page 1 is rasterized at 1080 px wide and cropped to the content bottom plus margin. When the content spills onto page 2, page 1 ends with "Lanjutan ada di chat Ciel."
  - `latex_to_text(latex: str) -> str`: `\frac{a}{b}` → `a/b` (parenthesised when compound), `^2` → `²` (digits, `n`, `-`), `_1` → `₁`, `\sqrt{x}` → `√x` / `√(…)`. Symbols: `\times ×`, `\cdot ·`, `\div ÷`, `\pm ±`, `\le ≤`, `\ge ≥`, `\ne ≠`, `\approx ≈`, `\pi π`, `\infty ∞`, `\theta θ`, `\alpha α`, `\beta β`, `\Delta Δ`, `\int ∫`, `\sum Σ`, `\lim lim`, `\to →`, `\in ∈`. Strip `{,}`, `\left`, `\right`, `\text{}` and leftover braces.
  - `document_title(content: str, request: str) -> str`: the first `# ` heading, else the request cut to 60 characters on a word boundary, else "Jawaban Ciel".
  - `wants_document(request: str) -> bool`: true on `\b(pdf|cetak|dicetak|print|printable|lembar (soal|latihan|kerja)|worksheet|handout|modul)\b`, case-insensitive.

- [ ] **Step 1: Write the failing tests**

```python
def test_pdf_has_title_quiz_key_and_sources(self):
    text = pdf_text(answer_pdf(MATH_ANSWER_WITH_GRAFIK_KUIS_AND_SUMBER, "Persamaan Kuadrat"))
    for needle in ("Persamaan Kuadrat", "Latihan", "Kunci jawaban", "Sumber", "ciel-ai.web.id"):
        self.assertIn(needle, text)
    self.assertNotIn('"jenis"', text)

def test_latex_to_text(self):
    self.assertEqual(latex_to_text(r"\frac{x+1}{2} \le \sqrt{9} \times \pi"), "(x+1)/2 ≤ √9 × π")
    self.assertEqual(latex_to_text("x^2 + 2{,}5"), "x² + 2,5")

def test_long_answer_paginates_and_png_is_capped(self):
    long = "\n\n".join(["Paragraf " + "kata " * 200] * 20 + [KUIS] * 20)
    self.assertGreater(len(PdfReader(io.BytesIO(answer_pdf(long, "Panjang"))).pages), 3)
    png = Image.open(io.BytesIO(answer_png(long, "Panjang")))
    self.assertEqual(png.width, 1080)
    self.assertLessEqual(png.height, 5400)

def test_emoji_and_symbols_do_not_raise(self):
    answer_pdf("Halo 😊 — 你好 — ∑ ∫ √2", "Uji")
    answer_png("Halo 😊", "Uji")

def test_wants_document(self):
    for yes in ("buatkan PDF-nya", "lembar soal pecahan buat dicetak", "bisa di-print?"):
        self.assertTrue(wants_document(yes))
    for no in ("apa itu fotosintesis", "gambarkan grafik y = x^2", "printilan acara"):
        self.assertFalse(wants_document(no))

def test_report_filename_ext(self):
    self.assertEqual(report_filename("Kuadrat", prefix="Ciel", ext="pdf"), "Ciel - Kuadrat.pdf")
    self.assertTrue(report_filename("x").endswith(".docx"))
```

(`pdf_text` uses `pypdf.PdfReader`, which is already a dependency.)

- [ ] **Step 2: Run to verify they fail.** Run `python -m unittest tests.test_answer_pdf -v`. Expected: `ModuleNotFoundError: answer_pdf`.
- [ ] **Step 3: Add `fpdf2` and `pypdfium2` to `requirements.in`, re-lock, install, and add the font files.**
- [ ] **Step 4: Implement `answer_pdf.py` and the `report_filename` `ext` parameter.**
- [ ] **Step 5: Run to verify they pass.** Run `python -m unittest tests.test_answer_pdf tests.test_ciel_pro tests.test_writing tests.test_supply_chain -v` (the last two cover existing `report_filename` callers). Expected: OK. Open one generated PDF and one PNG and look at them.
- [ ] **Step 6: Add to `ci.yml`, then commit.** Message: `Export answers as PDF and as an image`.

---

### Task 6: Download buttons under answers

**Files:**
- Modify: `app.py` (normal-answer branch after `render_answer_body`, `app.py:5468+`)
- Test: `tests/test_chat_view.py`

**Interfaces:**
- Consumes: `answer_pdf.answer_pdf`, `answer_png`, `document_title`, `wants_document`, `riset_export.report_filename(…, prefix="Ciel", ext=…)`.
- Behaviour: only normal answers (not errors, Riset or Kerangka) get a `st.container(horizontal=True, gap="small")` row:
  - Always: `st.download_button("Simpan gambar", icon=":material/image:", type="tertiary", data=lambda …: answer_png(content, title), file_name=report_filename(title, prefix="Ciel", ext="png"), mime="image/png", key=f"ansimg_{chat}_{index}", on_click="ignore")`.
  - Only when `wants_document(messages[index - 1]["content"])`: `"Unduh PDF"`, icon `:material/picture_as_pdf:`, `type="secondary"`, built the same way with `ext="pdf"` and `mime="application/pdf"`.
  - The title is `document_title(content, previous user text)`. Nothing is generated until the click (lazy `data=`), so a long chat costs nothing extra on rerun.

- [ ] **Step 1: Write the failing AppTest tests**
  - `test_every_answer_has_simpan_gambar`: two normal answers produce two download buttons labelled "Simpan gambar".
  - `test_pdf_button_only_when_asked`: the user message "buatkan lembar soal pecahan pdf" gets "Unduh PDF" under its answer; "apa itu pecahan" does not.
  - `test_riset_and_error_messages_get_no_new_buttons`.
- [ ] **Step 2: Run to verify they fail.** Run `python -m unittest tests.test_chat_view -v`. Expected: the 3 new tests FAIL.
- [ ] **Step 3: Implement the button row.**
- [ ] **Step 4: Run to verify they pass.** Run `python -m unittest tests.test_chat_view tests.test_ciel_pro tests.test_kerangka_app -v`. Expected: OK.
- [ ] **Step 5: Ciel's browser check.** Check both buttons, the downloaded files on the phone, and that the tertiary button doesn't crowd the source buttons in either theme. **Wait for "commit".**
- [ ] **Step 6: Commit.** Message: `Let users save answers as an image and ask for a PDF`.

---

### Task 7: Flow v1.14.0 (prompt v15.0)

**Files:**
- Create: `flow/v1.14.0/Ciel_AI_Long-Term_Memory_Master.json` (a copy of v1.13.0; only the Agent `system_prompt` changes), `tests/test_flow_v1140_contract.py`
- Modify: `tests/quality_rubric.json` (`format` criterion), `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `answer_blocks.parse_answer`, `answer_blocks.VISUAL_KINDS` (the contract test ties the prompt to the parser).
- Prompt edits (exact copy):
  - Section 5, replace the three lines `- Untuk matematika gunakan teks matematika biasa.` / `- Jangan gunakan LaTeX.` / `- Jangan gunakan $, $$, \frac, …` with:
    ```
    - Tulis rumus matematika dengan LaTeX di dalam $...$ (di dalam kalimat) atau $$...$$ (baris sendiri), misalnya $x^2 - 4x + 3 = 0$.
    - Di luar $...$ jangan menulis perintah LaTeX seperti \frac, \sqrt, atau \begin.
    - Jangan pakai $ untuk mata uang; tulis USD 5 atau Rp5.000.
    - Desimal di dalam rumus tetap format Indonesia: $2,5 \times 4 = 10$.
    ```
  - Section 10, after the line that starts `- Jangan menulis gambar markdown`, add: `- Blok ciel-grafik dan ciel-kuis bukan gambar markdown; pakai sesuai bagian 11.`
  - Append a new section at the end:
    ````
    11. TAMPILAN JAWABAN
    Tujuan: jawaban enak dibaca, tidak bikin pusing, dan tidak monoton.

    Dasar:
    - Kalimat pertama langsung menjawab inti pertanyaan.
    - Paragraf pendek, paling banyak 3 kalimat, satu ide per paragraf.
    - Judul ## hanya untuk jawaban panjang. Tebalkan paling banyak 3 frasa kunci.
    - Jawaban akhir, kesimpulan, atau peringatan penting ditulis sebagai kutipan: > **Jawaban:** ...

    Jangan monoton. Pilih bentuk yang paling cocok dengan isinya, dan jangan pakai pola yang sama di setiap jawaban:
    - proses atau urutan: langkah bernomor, atau grafik alur;
    - membandingkan: tabel;
    - konsep abstrak: analogi atau contoh sehari-hari dulu, baru definisinya;
    - angka dari data: grafik batang atau garis;
    - fungsi, persamaan, pertidaksamaan, bangun datar: grafik;
    - setelah menjelaskan konsep: boleh ditutup satu kuis singkat.
    Satu jawaban cukup memakai 1-2 bentuk.

    Soal matematika:
    1. Satu kalimat: apa yang dicari dan ide kuncinya.
    2. **Langkah 1**, **Langkah 2**, dan seterusnya: satu kalimat alasan, lalu rumusnya di $$...$$.
    3. > **Jawaban:** hasil akhirnya.
    4. **Cek:** substitusi balik atau cara cepat memastikan hasilnya benar.
    5. Soal fungsi, grafik, pertidaksamaan, atau bangun: tambahkan satu grafik.
    6. Jika pengguna sedang belajar: tutup dengan satu kuis "Coba sendiri" yang angkanya berbeda.
    Hitung setiap angka dengan Calculator, termasuk kunci kuis dan titik di grafik.

    Grafik dan diagram: tulis blok kode berbahasa ciel-grafik berisi satu objek JSON valid (kutip ganda, tanpa koma di akhir). Aplikasi yang menggambarnya. Paling banyak 2 grafik per jawaban. Angka grafik batang dan garis harus dari data pengguna atau hasil tool.
    ```ciel-grafik
    {"jenis": "fungsi", "judul": "f(x) = x^2 - 4x + 3", "fungsi": [{"rumus": "x^2 - 4x + 3", "label": "f(x)"}], "x": [-1, 5], "titik": [{"x": 1, "y": 0, "label": "(1, 0)"}, {"x": 3, "y": 0, "label": "(3, 0)"}]}
    ```
    Jenis lain:
    - {"jenis": "batang", "label": ["A", "B"], "nilai": [12, 7], "satuan": "siswa"}
    - {"jenis": "garis", "x": ["Jan", "Feb", "Mar"], "seri": [{"label": "Penjualan", "nilai": [5, 8, 6]}]}
    - {"jenis": "garis-bilangan", "interval": [{"dari": 2, "sampai": null, "dari_tutup": false, "sampai_tutup": false}]}
    - {"jenis": "bangun", "bentuk": "segitiga", "sisi": {"a": "6 cm", "b": "8 cm", "c": "10 cm"}}
    - {"jenis": "alur", "langkah": ["Penguapan", "Kondensasi", "Presipitasi"], "siklus": true}
    Rumus memakai x, angka, + - * / ^, kurung, dan sin cos tan sqrt log ln exp abs.

    Kuis: blok kode berbahasa ciel-kuis.
    ```ciel-kuis
    {"soal": "Berapa akar dari $x^2 - 5x + 6 = 0$?", "pilihan": ["2 dan 3", "1 dan 6", "-2 dan -3"], "jawaban": 0, "pembahasan": "$(x-2)(x-3) = 0$."}
    ```
    "jawaban" adalah nomor pilihan, mulai dari 0. Tanpa "pilihan", "jawaban" berupa teks. Paling banyak 3 kuis, kecuali lembar latihan (paling banyak 20).

    PDF dan gambar:
    - Jika pengguna minta PDF, lembar soal, atau dokumen untuk dicetak: tulis isi dokumennya lengkap, diawali judul # ..., lalu satu kalimat bahwa tombol Unduh PDF ada di bawah jawaban. Soal latihan ditulis sebagai blok ciel-kuis supaya kunci jawabannya terpisah di halaman akhir.
    - Jika pengguna minta jawaban dijadikan gambar: bilang tombol Simpan gambar ada di bawah setiap jawaban.
    - Ciel belum bisa membuat ilustrasi atau mengedit foto. Katakan itu dengan jujur jika diminta.
    ````
- `tests/quality_rubric.json` `format` description becomes: `"Rumus memakai $...$ atau $$...$$; tidak ada perintah LaTeX di luar tanda $."`

- [ ] **Step 1: Write the failing contract test `tests/test_flow_v1140_contract.py`** (follow `tests/test_flow_v1130_contract.py`):
  - `test_only_the_system_prompt_changes`: with both prompts blanked, v1.14.0 equals v1.13.0.
  - `test_latex_ban_is_lifted_with_guardrails`: the prompt lacks `"Jangan gunakan LaTeX."` and contains `"Jangan pakai $ untuk mata uang"`.
  - `test_section_11_is_last_and_names_every_kind`: `"11. TAMPILAN JAWABAN"` comes after `"10. KEAMANAN"`, and every name in `VISUAL_KINDS` appears as `"jenis": "<name>"`.
  - `test_prompt_examples_parse`: every `ciel-grafik`/`ciel-kuis` fence in the prompt, plus each one-line JSON under "Jenis lain" wrapped in a fence, parses to `Visual`/`Quiz` and none of them to `Broken`.
  - `test_no_illustration_promise`: the prompt contains `"belum bisa membuat ilustrasi atau mengedit foto"`.
  - `test_embedded_components_match_sources`: same check as v1.13.0.
- [ ] **Step 2: Run to verify it fails.** Run `python -m unittest tests.test_flow_v1140_contract -v`. Expected: FileNotFoundError for the v1.14.0 snapshot.
- [ ] **Step 3: Create the snapshot.** Use a one-off script in the scratchpad (not committed) that loads v1.13.0, edits only `Agent-puarO`'s `system_prompt` value with the exact copy above, and writes the JSON with the same `indent`/`ensure_ascii` style as v1.13.0. Update the rubric.
- [ ] **Step 4: Run to verify it passes.** Run `python -m unittest tests.test_flow_v1140_contract tests.test_flow_v1130_contract tests.test_ci_coverage -v` plus `python -m json.tool flow/v1.14.0/Ciel_AI_Long-Term_Memory_Master.json > /dev/null`. Expected: OK.
- [ ] **Step 5: Add to `ci.yml`, then commit.** Message: `Flow v1.14.0: rendered math, graphs, quizzes and varied answers`.

---

### Task 8: Docs, rollout and live check

**Files:**
- Modify: `CHANGELOG.md` (Unreleased entry), `docs/ARCHITECTURE.md` (an "Answer rendering" section: segments, renderer, exports, why the model never writes image URLs)

- [ ] **Step 1: Write the CHANGELOG and ARCHITECTURE entries, then run the full offline suite with the exact unittest list in `ci.yml`.** Expected: all OK. Commit: `Document visual answers`.
- [ ] **Step 2: Open the PR. After merge, confirm Streamlit Cloud installed matplotlib, fpdf2 and pypdfium2** (app boots, no ImportError; reboot the app if it shows one, per past deploys). Old chats look unchanged.
- [ ] **Step 3: Try v1.14.0 on a separate test flow in Langflow** (RELEASE_CHECKLIST step 11) with this set. Each case must render without a `Broken` note:
  1. "selesaikan x² − 5x + 6 = 0" (steps, callout, check, graph)
  2. "turunan dari x³ − 3x, gambarkan grafiknya"
  3. "selesaikan 2x − 4 > 0" (garis-bilangan)
  4. "luas segitiga alas 6 tinggi 8" (bangun)
  5. "beda mitosis dan meiosis" (table, no graph)
  6. "jelaskan siklus air" (alur)
  7. "ajari aku limit" (concept, then one quiz)
  8. "buatkan lembar 5 soal pecahan pdf" (Unduh PDF button, 5 quizzes, key on the last page)
  9. "harga $5 dan $10, totalnya?" (no stray math)
  10. "buatkan ilustrasi kucing" (honest "belum bisa")

  Also check that consecutive answers 5–7 don't share one template, and that latency on the 16-question set in `docs/OBSERVABILITY.md` has a median no more than 2 s above the 8.4 s baseline. Record the results in `docs/OBSERVABILITY.md`.
- [ ] **Step 4: Deploy the flow to production** per `RELEASE_CHECKLIST.md` "Deploying a Flow Change to Langflow": back up, then `PATCH` only `data`. Re-run cases 1, 8 and 9 on production. Mind the DeepSeek prepaid balance before long runs.
