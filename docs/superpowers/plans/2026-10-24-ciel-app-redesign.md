# Ciel App Redesign (release 1 of 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the Streamlit app to the artifact's look (dark by default), replace the empty chat page with the Beranda (centred composer + prompt templates), and turn the chat page into three columns with a sources rail.

**Architecture:** Pure logic goes in two new modules with unit tests: `chat_sources.py` (reads "Sumber:" blocks, "## Daftar Pustaka" entries and `[Dugaan]` points from answer text) and `beranda.py` (templates, WIB greeting, relative times, latest Riset map). `app.py` keeps rendering and CSS, as today; `login.py` and `pricing.py` change in place. Stored messages are never rewritten: every transformation happens at display time.

**Tech Stack:** Python 3, Streamlit 1.54 locally / 1.65 on Community Cloud, `streamlit.testing.v1.AppTest`, pytest/unittest.

**Spec:** `docs/superpowers/specs/2026-10-20-ciel-redesign-design.md` (sections 1–6 and 8). Section 7, the landing page, is release 2 and has its own plan, written after this one ships.

## Global Constraints

- **No commits until Ciel has checked the result in the browser and says "commit".** Tasks end with tests passing, not with a commit. Task 9 makes the one commit and the PR. No `Co-Authored-By`/"Generated with Claude" lines (Ciel's rule).
- Langflow flows are not changed. No new DeepSeek, Langflow or ngrok calls per rerun; memory listing happens at most once per session.
- Model output is never rendered with `unsafe_allow_html=True`. HTML built by the app escapes every model-derived string (`html.escape`) and only links `http://`/`https://` URLs.
- Every widget colour rule that can appear in a popover or dialog uses `:is(.stApp, [data-testid="stPopoverBody"], [data-testid="stDialog"])`.
- Dark is the default theme. Dark tokens (verbatim from the spec): bg `#0e0d0c`, surface `#181715`, raised `#24231f`, raised-strong `#2a2926`, text `#f4f4f2`, muted `#b4b3ad`, faint `#959490`, accent `#9db3e8`, accent-ink `#141a2a`, gold `#e9d06a`, gold-ink `#2e2606`, primary `#f4f4f2`, on-primary `#141311`, gap-bg `#2b2716`. Light tokens: bg `#f1f1ee`, raised `#e6e6e2`, text `#161513`, muted `#4b4a46`, accent `#2b4886`, gold `#e9d06a`, gold-ink `#3d3209`, primary `#161513`, on-primary `#f1f1ee`. Other tokens: implementer's choice, passing the AA tests. `--c-control` must not be `#4a4843`.
- Fonts: Geist (UI), Fraunces (wordmark, Beranda greeting). Easing `cubic-bezier(0.32,0.72,0,1)`. Everything animated stops under `prefers-reduced-motion: reduce`.
- Copy is Indonesian, casual "kamu" voice, no emoji, no English UI labels.
- Times shown to users are WIB (`Asia/Jakarta`).
- Existing behaviour stays: archive/delete chat, project files, Data saya, Riset Skripsi/Kerangka/Cek kutipan dialogs and buttons, Coba lagi, Unduh DOCX/CSV, pricing, privacy, login, rate limits, Pro gate.

## Review Focus

1. **Hostile or broken source lines.** A "Sumber:" or Daftar Pustaka entry whose URL is `javascript:...` or whose title contains `<script>` must show no link and only escaped text. Pinned in Task 2 (`test_rejects_non_http_urls_and_keeps_text`) and Task 6 (`test_source_html_is_escaped`).
2. **Old chats from Supabase.** Messages without `kind`, `elapsed` or `topic`, error messages, and chats saved before this release must render without errors. Pinned in Task 6 (`test_old_chat_without_new_fields_renders`).
3. **Guest on the Beranda.** No memory panel, no `memory_admin` call, the Pro templates still visible (the dialog explains Pro). Pinned in Task 5 (`test_guest_beranda_never_lists_memories`).
4. **Memory listing fails or is slow.** The Beranda still renders, the panel is hidden, and later reruns do not call again. Pinned in Task 5 (`test_memory_listing_runs_once_even_when_it_fails`).
5. **Theme choice saved before this release.** A visitor with `ciel-theme = "light"` in localStorage keeps light; anything else, or blocked storage, gets dark. Pinned in Task 1 (`test_saved_light_choice_survives_and_default_is_dark`).

---

### Task 1: Dark-default tokens and theme switch

**Files:**
- Modify: `app.py:62-144` (comments, `DARK_TOKENS`, `:root` block), `app.py:1007-1058` (`UI_JS`), `app.py:294-323` (toggle icon rules)
- Modify: `.streamlit/config.toml`
- Test: `tests/test_theme.py`

**Interfaces:**
- Produces: module constant `LIGHT_TOKENS` (replaces `DARK_TOKENS`); `CIEL_CSS` holds the dark tokens in `:root { ... }` and `:root[data-ciel-theme="light"] {{{LIGHT_TOKENS}}}`; app line `st.markdown(CIEL_CSS.replace("{{{LIGHT_TOKENS}}}", "{" + LIGHT_TOKENS + "}"), unsafe_allow_html=True)`. New tokens `--c-primary`, `--c-on-primary`, `--c-gap-bg` exist in both sets. `<html data-ciel-theme>` is always `"dark"` or `"light"` after UI_JS runs.

- [ ] **Step 1: Rewrite the token tests in `tests/test_theme.py`**

`setUpClass` reads dark tokens from the first `:root {` block and light tokens from `LIGHT_TOKENS`. Replace `test_every_light_colour_token_has_a_dark_value` with a two-way parity check, and `test_dark_tokens_follow_the_device_and_the_toggle` with:

```python
def test_dark_is_the_default_and_light_is_opt_in(self):
    self.assertIn(':root[data-ciel-theme="light"] {{{LIGHT_TOKENS}}}', self.css)
    self.assertNotIn("prefers-color-scheme", self.css)
    self.assertIn('CIEL_CSS.replace("{{{LIGHT_TOKENS}}}", "{" + LIGHT_TOKENS + "}")', APP_PATH.read_text(encoding="utf-8"))
    self.assertEqual(self.dark["--c-bg"], "#0e0d0c")
    self.assertEqual(self.dark["--c-primary"], "#f4f4f2")
    self.assertEqual(self.light["--c-bg"], "#f1f1ee")
    self.assertEqual(self.light["--c-primary"], "#161513")
```

Extend the AA pairs in `test_text_pairs_pass_wcag_aa_in_both_themes` with `("--c-on-primary", "--c-primary")`, `("--c-gold-ink", "--c-gold")`, `("--c-text", "--c-gap-bg")`, `("--c-faint", "--c-raised-strong")`.

In `ThemeScriptTest`, replace the prefersDark assertions with:

```python
def test_saved_light_choice_survives_and_default_is_dark(self):
    self.assertIn("root.dataset.cielTheme = saved === 'light' ? 'light' : 'dark';", self.js)
    self.assertNotIn("prefers-color-scheme", self.js)
    self.assertIn("localStorage.setItem(KEY, next)", self.js)
    self.assertEqual(self.js.count("try {"), 2)
```

Add a config check: `.streamlit/config.toml` contains `base = "dark"` and `backgroundColor = "#0e0d0c"`.

- [ ] **Step 2: Run the tests and see them fail**

Run: `python -m pytest tests/test_theme.py -q`
Expected: FAIL (`LIGHT_TOKENS` missing, prefers-color-scheme still present).

- [ ] **Step 3: Implement the token swap**

In `app.py`, make `:root` the dark set and `LIGHT_TOKENS` the light set (values from Global Constraints; choose the unpinned ones so every AA pair passes; light `--c-mark-piece` dark enough for ≥3:1 on `#f1f1ee`). Move the light toggle icon (moon) to `:root[data-ciel-theme="light"] .ciel-theme-toggle` and make the sun the default; delete both `prefers-color-scheme` blocks. In `UI_JS`, drop `prefersDark`; on start set `root.dataset.cielTheme = saved === 'light' ? 'light' : 'dark';` (inside the existing try; the catch sets `'dark'`); `effectiveTheme()` returns `root.dataset.cielTheme`. Set `.streamlit/config.toml` to `base = "dark"`, `primaryColor = "#9db3e8"`, `backgroundColor = "#0e0d0c"`, `secondaryBackgroundColor = "#181715"`, `textColor = "#f4f4f2"`, and update its "Keep in step" comment. Rewrite the VISUAL SYSTEM comment to describe the new palette.

- [ ] **Step 4: Run the tests and see them pass**

Run: `python -m pytest tests/test_theme.py tests/test_login.py -q`
Expected: PASS.

---

### Task 2: `chat_sources.py`, the answer-text reader

**Files:**
- Create: `chat_sources.py`
- Test: `tests/test_chat_sources.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class Source: number: int; title: str; domain: str; url: str`
  - `split_sources(text: str) -> tuple[str, list[Source], str]`: (text before the last "Sumber:" block, sources with http(s) URLs, leftover = URL-less entries and the guard note "(N sumber dihapus ...)" joined by newlines). No block → `(text, [], "")`.
  - `reference_sources(text: str) -> list[Source]`: entries under "## Daftar Pustaka" or "## Daftar Pustaka (dari peta sumber)". Text unchanged.
  - `answer_sources(text: str) -> list[Source]`: `split_sources(text)[1]` if non-empty, else `reference_sources(text)`.
  - `guesses(text: str) -> list[str]`: text of every line containing `[Dugaan]`, label and list marker removed, cut to 140 characters at a word boundary with "…".
  - `@dataclass(frozen=True) class AnswerGroup: question: str; sources: list[Source]`
  - `@dataclass(frozen=True) class ChatSummary: groups: list[AnswerGroup]; unique_count: int; guesses: list[str]; map_entries: int`
  - `summarize(messages: list[dict]) -> ChatSummary`: one group per non-error assistant message with sources, newest first; `question` = preceding user message content cut to 60 characters; `unique_count` = distinct URLs in the chat; `guesses` from all non-error assistant messages in order; `map_entries` = `len(reference_sources(...))` of the last message with `kind == "riset_skripsi"`, else 0.

- [ ] **Step 1: Write the failing tests**

Fixtures: the two "Sumber:" lines from spec appendix A (Vaswani, Koto) as one-line strings; a Riset answer built from `tests/test_riset_components.py` (`## Daftar Pustaka\n\n[1] Sari, D. (2023). *Literasi Digital dan Kinerja UMKM*. jurnal.ugm.ac.id. https://jurnal.ugm.ac.id/jbs/article/view/123` … ending with `(1 sumber dihapus karena tidak ada di hasil pencarian.)`); a Kerangka tail with `## Daftar Pustaka (dari peta sumber)`.

```python
def test_one_line_sumber_block_from_the_live_app(self):
    body, sources, leftover = split_sources("Ringkasan.\n\n" + VASWANI_SUMBER)
    self.assertEqual(body.rstrip(), "Ringkasan.")
    self.assertEqual([s.number for s in sources], [1, 2, 3, 4])
    self.assertEqual(sources[0].url, "https://arxiv.org/abs/1706.03762")
    self.assertEqual(sources[0].domain, "arxiv.org")
    self.assertEqual(sources[0].title, "Attention Is All You Need (Vaswani dkk., 2017)")
    self.assertEqual(leftover, "")

def test_one_entry_per_line_and_hyphen_separator(self): ...  # "Sumber:\n[1] Nama - Judul - https://x.org/a"
def test_answer_without_sources_is_untouched(self):
    self.assertEqual(split_sources(FAKE_JOURNAL_REFUSAL), (FAKE_JOURNAL_REFUSAL, [], ""))
def test_urlless_entries_and_guard_note_stay_as_leftover(self): ...
def test_rejects_non_http_urls_and_keeps_text(self):
    _, sources, leftover = split_sources("x\n\nSumber: [1] Evil — <script>a</script> — javascript:alert(1)")
    self.assertEqual(sources, [])
    self.assertIn("<script>a</script>", leftover)   # escaping is the renderer's job
def test_daftar_pustaka_entries_from_riset_and_kerangka(self):
    self.assertEqual([s.url for s in reference_sources(RISET_TEXT)][0], "https://jurnal.ugm.ac.id/jbs/article/view/123")
    self.assertEqual(len(reference_sources(KERANGKA_TEXT)), 2)
def test_guesses_strip_the_label(self):
    self.assertEqual(guesses("1. Nilai terendah di geometri. [Dugaan]\n2. Rata-rata 78. [Terverifikasi]"), ["Nilai terendah di geometri."])
def test_summary_groups_newest_first_and_counts_unique_urls(self): ...
def test_summary_skips_error_messages_and_counts_the_last_map(self): ...
```

- [ ] **Step 2: Run and see them fail**

Run: `python -m pytest tests/test_chat_sources.py -q`
Expected: FAIL (`ModuleNotFoundError: chat_sources`).

- [ ] **Step 3: Implement `chat_sources.py`**

Find the last line matching `^\s*(\*\*)?Sumber:?(\*\*)?` (case-insensitive); split the rest on `\[(\d+)\]` markers; split each entry on ` — ` or ` - `; the URL is the first `https?://\S+` token (trailing `.,;)` stripped); title = the field before the URL field that is not the source name when there are ≥3 fields, else the first field; domain = `urllib.parse.urlsplit(url).hostname` minus `www.`. Daftar Pustaka entries: lines matching `^\[(\d+)\]\s+` under the heading until the next `## ` heading; title = text between the first pair of `*`; URL = last `https?://` token.

- [ ] **Step 4: Run and see them pass**

Run: `python -m pytest tests/test_chat_sources.py -q`
Expected: PASS.

---

### Task 3: `beranda.py`, Beranda logic

**Files:**
- Create: `beranda.py`
- Modify: `app.py:3160` (`RISET_KIND` imported from `beranda` instead of defined)
- Test: `tests/test_beranda.py`

**Interfaces:**
- Produces:
  - `RISET_KIND = "riset_skripsi"`
  - `@dataclass(frozen=True) class Template: key: str; label: str; text: str; pro: bool; action: str` with `action` in `"fill"`, `"riset"`, `"kerangka"`
  - `TEMPLATES: tuple[Template, ...]`, in this order, with this exact copy:
    - `cari_jurnal`, "Cari jurnal", "", pro, `riset`
    - `jelasin`, "Jelasin konsep", "Jelasin [konsep] pelan-pelan pakai contoh angka, lalu kasih 2 soal latihan.", fill
    - `analisis`, "Analisis metode", "Analisis: [metode] cocok nggak buat data [jenis data]-ku?", fill
    - `cek_referensi`, "Cek referensi", "Cek apakah referensi ini beneran ada: [tempel referensi]", fill
    - `ringkas_file`, "Ringkas file proyek", "Ringkas file proyek ini dan tandai klaim yang belum ada sumbernya.", fill
    - `kerangka`, "Kerangka Bab 1–3", "", pro, `kerangka`
  - `templates_for(has_files: bool, has_map: bool, riset_enabled: bool, writer_enabled: bool) -> list[Template]`
  - `latest_riset(chats: Iterable[dict], project_id: str | None) -> tuple[dict, int] | None`: newest (by `updated`) non-archived chat in the context (`project_id is None` = every chat) holding a non-error message with `kind == RISET_KIND`; returns the chat and that message's index.
  - `greeting(now: float, name: str | None) -> str`: WIB hour 4–10 "Pagi", 11–14 "Siang", 15–17 "Sore", else "Malam"; "Malam, Raka." with the first word of `name`, "Malam." without.
  - `relative_time(then: float, now: float) -> str`: WIB; same day "21.42"; previous day "Kemarin"; 2–6 days back "Sen"/"Sel"/"Rab"/"Kam"/"Jum"/"Sab"/"Min"; older "15 Okt", or "15 Okt 2025" when the year differs.

- [ ] **Step 1: Write the failing tests**

```python
def test_templates_follow_the_context(self):
    keys = [t.key for t in templates_for(has_files=False, has_map=False, riset_enabled=True, writer_enabled=True)]
    self.assertEqual(keys, ["cari_jurnal", "jelasin", "analisis", "cek_referensi"])
    keys = [t.key for t in templates_for(True, True, True, True)]
    self.assertEqual(keys, ["cari_jurnal", "jelasin", "analisis", "cek_referensi", "ringkas_file", "kerangka"])
    self.assertNotIn("cari_jurnal", [t.key for t in templates_for(True, True, False, True)])
    self.assertNotIn("kerangka", [t.key for t in templates_for(True, True, True, False)])
def test_fill_templates_keep_their_brackets(self): ...  # exact strings above
def test_latest_riset_in_project_and_everywhere(self): ...  # project-only vs None; archived and error maps ignored
def test_greeting_uses_wib(self):
    # 2026-10-20 14:00 UTC = 21:00 WIB
    self.assertEqual(greeting(1792504800, "Raka Pradipta"), "Malam, Raka.")
    self.assertEqual(greeting(1792504800, None), "Malam.")
def test_relative_time(self): ...  # same day, Kemarin, weekday, "15 Okt", other year
```

(Compute the epoch constants in the test with `datetime(..., tzinfo=ZoneInfo("Asia/Jakarta")).timestamp()` rather than literals.)

- [ ] **Step 2: Run and see them fail**

Run: `python -m pytest tests/test_beranda.py -q`
Expected: FAIL (`ModuleNotFoundError: beranda`).

- [ ] **Step 3: Implement `beranda.py`** with `zoneinfo.ZoneInfo("Asia/Jakarta")`; add `tzdata` to `requirements.txt` only if `ZoneInfo("Asia/Jakarta")` fails on the Windows dev box (Cloud is Linux and has it).

- [ ] **Step 4: Run and see them pass**

Run: `python -m pytest tests/test_beranda.py tests/test_ciel_pro.py tests/test_kerangka_app.py -q`
Expected: PASS.

---

### Task 4: Shell: shapes, sidebar rows, top bar crumb, curtain

**Files:**
- Modify: `app.py` CSS sections Base/Top bar/Sidebar/Dialog/Buttons/Messages/Composer/Projects (`app.py:146-911`), `render_history_row` (`app.py:3578`), sidebar block (`app.py:3660-3850`), HEADER block (`app.py:4042-4100`), `UI_JS`
- Test: `tests/test_theme.py`, `tests/test_login.py`

**Interfaces:**
- Consumes: tokens from Task 1; `relative_time` from Task 3.
- Produces: CSS classes `.ciel-crumb`, `.ciel-curtain`, `.ciel-copy` (styled here, used by Task 6); history button labels `"<judul>  ·  <waktu>"` plus `"  ·  Riset"` for chats holding a Riset map.

- [ ] **Step 1: Write the failing contract tests**

In `tests/test_theme.py` add:

```python
def test_primary_buttons_are_pills_on_the_primary_token(self):
    scope = ':is(.stApp, [data-testid="stPopoverBody"], [data-testid="stDialog"])'
    rule = self.css.split(f'{scope} .stButton > button[kind="primary"] {{', 1)[1].split("}", 1)[0]
    for line in ("background: var(--c-primary);", "color: var(--c-on-primary);", "border-radius: 999px;"):
        self.assertIn(line, rule)
def test_user_messages_are_right_aligned_bubbles(self): ...  # :has(stChatMessageAvatarUser) rule has margin-left: auto and max-width: 80%
def test_curtain_plays_once_per_session(self):
    js = app_constants()["UI_JS"]
    self.assertIn("sessionStorage.getItem('ciel-curtain')", js)
    self.assertIn(".ciel-curtain", self.css)
    self.assertIn("prefers-reduced-motion", js)
```

In `tests/test_login.py`, keep `test_sign_in_lives_in_the_top_bar_and_page_links_stay_hidden` passing and add `test_top_bar_shows_the_crumb`: AppTest with a project selected shows "Proyek · <name>"; with none, "Semua chat".

- [ ] **Step 2: Run and see them fail**

Run: `python -m pytest tests/test_theme.py tests/test_login.py -q`
Expected: FAIL on the new tests.

- [ ] **Step 3: Restyle**

Primary/secondary buttons, download and link buttons → pills; sidebar list rows keep 8px corners (artboard `.navi`), active row = raised background without the inset accent bar. Cards and panels: one bezel (5px padding, 22px radius, `inset 0 0 0 1px` line) around a 17px-radius core, never nested. Composer: floating tray (6px padding, 28px radius, blurred translucent surface) around the existing chat input. User message: bubble on surface, 16px radius, `margin-left: auto; max-width: 80%`, no avatar box. Assistant avatar: the mark only. Dialogs: surface, 17px radius. Top bar: replace the wordmark+status chip with `<p class="ciel-crumb">Proyek · <b>nama</b></p>` (`html.escape`) or `Semua chat`; the wordmark lives in the sidebar head. History label: `short(title, 30)` plus `relative_time(chat["updated"], time.time())`, plus "Riset" when `latest_riset([chat], chat["project_id"])` is not None; the "Riwayat" eyebrow reads "Chat di proyek ini" when a project is active. Curtain: UI_JS adds `<div class="ciel-curtain" aria-hidden="true">` with the mark (CSS mask, since `st.html` strips SVG) once per `sessionStorage['ciel-curtain']`, removes it after 800 ms, skips it under reduced motion or blocked storage; `pointer-events: none`.

- [ ] **Step 4: Run and see them pass**

Run: `python -m pytest tests/test_theme.py tests/test_login.py tests/test_app_hygiene.py -q`
Expected: PASS.

---

### Task 5: Beranda in place of the empty chat page

**Files:**
- Modify: `app.py` CHAT INPUT + EMPTY STATE blocks (`app.py:4162-4230`), new `render_beranda()` and callbacks near `queue_prompt` (`app.py:3152`); remove `STARTER_PROMPTS`, `SAMPLE_ANSWER_HTML` and their CSS (`.ciel-hero`, `.ciel-sample*`, `.st-key-starters`)
- Test: create `tests/test_beranda_app.py`; update tests that reference the removed starters/sample (`grep -rn "starter_\|SAMPLE_ANSWER\|ciel-hero" tests`)

**Interfaces:**
- Consumes: `TEMPLATES`, `templates_for`, `latest_riset`, `greeting`, `relative_time` (Task 3); `open_riset_dialog`, `open_kerangka_dialog`, `select_chat`, `load_my_memories`.
- Produces: `COMPOSER_KEY = "composer"` (the one `st.chat_input` key, also used by Task 6); `fill_composer(text: str) -> None`; `open_kerangka_from(chat_id: str, map_index: int, topic: str) -> None`; `session_memories() -> list[dict]` (calls `load_my_memories()` at most once per session, guarded by `st.session_state.memories_loaded`, returns `[]` on any failure or when not signed in or `MEMORY_ADMIN_FLOW_ID` is unset).

- [ ] **Step 1: Write the failing AppTest tests** (pattern: `tests/test_kerangka_app.py`, patching `st.user`, `is_pro`, `memory_admin`)

```python
def test_beranda_shows_greeting_composer_and_templates(self): ...   # "Malam." etc via patched time; chat_input present; buttons "Cari jurnal", "Jelasin konsep", "Analisis metode", "Cek referensi"
def test_fill_template_puts_text_in_the_composer(self):
    at.button(key="tpl_jelasin").click().run()
    self.assertEqual(at.session_state["composer"], "Jelasin [konsep] pelan-pelan pakai contoh angka, lalu kasih 2 soal latihan.")
def test_project_with_files_and_a_map_shows_all_six(self): ...
def test_kerangka_template_opens_the_latest_map(self): ...          # active_chat set, open_kerangka == {"topic": ..., "map_index": ...}
def test_submitting_from_beranda_shows_the_chat(self): ...          # ask_langflow patched; after submit, no tpl_ buttons, one user + one assistant message
def test_guest_beranda_never_lists_memories(self): ...              # memory_admin mock not called; no "Yang Ciel ingat"
def test_memory_listing_runs_once_even_when_it_fails(self): ...      # memory_admin raises/returns error; two reruns; called once; panel absent
def test_lanjutkan_riset_lists_three_latest_chats(self): ...
```

- [ ] **Step 2: Run and see them fail**

Run: `python -m pytest tests/test_beranda_app.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

When there are no messages and no pending request, render the Beranda in a keyed container (`key="beranda"`, max-width ~660px, centred): greeting (Fraunces) from `greeting(time.time(), st.user name if logged_in())`; subline `"<proyek> · N chat · M file proyek"` or `"Semua chat · N chat"`; `st.chat_input(placeholder, key=COMPOSER_KEY, accept_file="multiple", ...)` inside it, placeholder "Tanya soal skripsimu" in a project, "Tanyakan sesuatu kepada Ciel..." otherwise; template buttons in a horizontal container, keys `tpl_<key>`, label `"<label> · Pro"` when `pro`; `fill` → `on_click=fill_composer`; `riset` → `open_riset_dialog`; `kerangka` → `open_kerangka_from(*latest_riset(...), topic)`. Then the two panels (Lanjutkan riset: 3 newest non-archived chats in context, each a button → `select_chat`; Yang Ciel ingat: up to 4 rows from `session_memories()`), each hidden when empty. In the chat view, call `st.chat_input` at top level with the same key. Keep the submit handling (`unpack_chat_input`, length check, `make_pending`) in one function used by both call sites. After a Beranda submit, the same run must render the chat, not the Beranda: render the Beranda inside an `st.empty()` slot and empty it once a value arrives.

- [ ] **Step 4: Run and see them pass**

Run: `python -m pytest tests/test_beranda_app.py tests/test_ciel_master.py tests/test_kerangka_app.py tests/test_ciel_pro.py -q`
Expected: PASS.

---

### Task 6: Three-column chat with the sources rail

**Files:**
- Modify: CHAT HISTORY block (`app.py:4232-4315`), assistant reply creation (`app.py` "reply = {" in PROCESS NEW MESSAGE), new helpers `render_answer`, `render_rail`, `source_buttons_html`, `UI_JS` (copy button), CSS
- Test: create `tests/test_chat_view.py`

**Interfaces:**
- Consumes: `split_sources`, `answer_sources`, `summarize`, `ChatSummary` (Task 2); `COMPOSER_KEY`, `session_memories` (Task 5).
- Produces: assistant replies gain `"elapsed": int` (seconds from send to answer); `source_buttons_html(sources: list[Source]) -> str`; `answer_markdown(text: str) -> str` (labels → `:orange-badge[Dugaan]` / `:blue-badge[Terverifikasi]`, "Sumber:" block removed via `split_sources`, leftover appended as plain text).

- [ ] **Step 1: Write the failing tests**

```python
def test_answer_markdown_moves_sumber_to_buttons_and_keeps_leftover(self): ...
def test_daftar_pustaka_stays_in_the_text(self):
    self.assertIn("## Daftar Pustaka", answer_markdown(RISET_TEXT))
def test_labels_become_badges_without_html(self):
    md = answer_markdown("1. Geometri lemah. [Dugaan]")
    self.assertIn(":orange-badge[Dugaan]", md)
    self.assertNotIn("<span", md)
def test_source_html_is_escaped(self):
    html_out = source_buttons_html([Source(1, '<img src=x onerror=1>', "evil.org", "https://evil.org/a?b=<c>")])
    self.assertNotIn("<img", html_out)
    self.assertIn('href="https://evil.org/a?b=&lt;c&gt;"', html_out)
def test_rail_lists_sources_guesses_and_riset_facts(self): ...   # AppTest: seeded chat from appendix A + analysis answer + riset message with elapsed
def test_rail_hidden_when_chat_has_nothing_to_show(self): ...    # no element with key "rail"
def test_header_counts(self): ...                                 # "4 sumber", "2 sumber · 1 belum ketemu", title only when both zero
def test_old_chat_without_new_fields_renders(self): ...           # messages without kind/elapsed/topic + an error message; no exception, retry button present
def test_copy_button_script_targets_finished_answers(self):
    js = app_constants()["UI_JS"]
    self.assertIn("navigator.clipboard", js)
    self.assertIn("execCommand('copy')", js)
    self.assertIn("Tersalin", js)
```

- [ ] **Step 2: Run and see them fail**

Run: `python -m pytest tests/test_chat_view.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

With messages present: header (`st.markdown` of escaped title, 18px/600, plus counts from `summarize`); if the summary has sources, guesses, session memories or a Riset map, `convo, rail = st.columns([7, 3], gap="large")` with the rail in `st.container(key="rail")`, otherwise one column. Answers: `st.markdown(answer_markdown(content))` (no `unsafe_allow_html`), then `st.markdown(source_buttons_html(...), unsafe_allow_html=True)` for "Sumber:" sources only, then the existing Riset/Kerangka buttons. Rail sections in order (spec 4): Sumber di chat ini (groups, subtitle only when >1 group), Belum ketemu (items on `--c-gap-bg`), Yang Ciel ingat (`session_memories()`, no new call), Riset ini (riset chats: "Riset Skripsi", `map_entries` sources, `elapsed` as "1 m 52 d" when present). CSS: composer width follows the conversation column at ≥1200px; below 1200px the columns stack with the rail after the conversation; at ≤640px one column. Record `elapsed` with `time.time()` taken when the pending request starts. Copy button: the UI_JS observer adds `<button class="ciel-copy">Salin jawaban</button>` to each assistant `stChatMessage` that has no `.ciel-thinking` and no error card, copies its `stMarkdownContainer` `innerText`, shows "Tersalin" for 1.5 s, hides itself if both clipboard paths fail.

- [ ] **Step 4: Run and see them pass**

Run: `python -m pytest tests/test_chat_view.py tests/test_chat_sources.py tests/test_ciel_master.py tests/test_cek_kutipan_app.py tests/test_kerangka_app.py -q`
Expected: PASS.

---

### Task 7: Masuk page

**Files:**
- Modify: `login.py`, `app.py:4146-4159` (pass `on_privacy=show_privacy`)
- Test: `tests/test_login.py`

**Interfaces:**
- Produces: `render_login(auth_enabled=False, on_google=None, on_back=None, rate_limits=(20, 60), signed_in_as=None, history_saved=False, on_privacy=None)`; widget keys `login_google`, `login_skip`, `login_tochat` unchanged; new key `login_privacy`.

- [ ] **Step 1: Write the failing tests**

```python
def test_two_column_layout_with_example_project(self):   # "Masuk ke Ciel", "Begini proyekmu nanti", "Contoh proyek." caption present
def test_google_button_copy_and_scope_note(self):          # button "Lanjutkan dengan Google"; "Ciel cuma minta nama, email, dan foto profil dari akun Google kamu."
def test_privacy_link_and_no_terms_link(self):              # button key login_privacy calls on_privacy; no "Syarat layanan"
```

Update existing tests that assert the old heading/button copy ("Masuk dengan Google").

- [ ] **Step 2: Run and see them fail**

Run: `python -m pytest tests/test_login.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement** per spec 5 and artboard Masuk (`st.columns([5, 7])`; left: heading, one-line intro "Satu akun Google buat semua proyekmu. Riwayat chat dan yang Ciel ingat ikut tersimpan di akunmu." when `history_saved`, otherwise without the history clause; pill; scope note; `login_notes()` list; "Lanjut tanpa masuk"; privacy link. Right: example-project card as escaped static HTML: chats 12, file proyek 2, belum ketemu 2, three remembered items, caption "Contoh proyek. Isinya mulai kosong, lalu keisi sendiri sambil kamu ngobrol sama Ciel."; no "Sumber tersimpan" counter, no deadlines). One column at ≤900px.

- [ ] **Step 4: Run and see them pass**

Run: `python -m pytest tests/test_login.py -q`
Expected: PASS.

---

### Task 8: Pricing history bullet

**Files:**
- Modify: `pricing.py:24-130` (`PLANS` free features, `free_plan_extras`, `faq_items`, `render_pricing`), `app.py:4124-4132` (pass `history_saved=CHAT_STORE is not None`)
- Test: `tests/test_pricing.py`

**Interfaces:**
- Produces: `free_plan_extras(rate_limits, memory_enabled, history_saved=False) -> tuple[str, ...]`; `faq_items(memory_enabled, pro_for_sale=False, history_saved=False)`; `render_pricing(..., history_saved=False)`.

- [ ] **Step 1: Write the failing test**

```python
def test_history_line_follows_where_history_is_saved(self):
    self.assertNotIn("Riwayat chat selama sesi", PLANS[0]["features"])
    self.assertIn("Riwayat chat tersimpan di akun setelah masuk", free_plan_extras((10, 60), True, history_saved=True))
    self.assertIn("Riwayat chat selama sesi", free_plan_extras((10, 60), True, history_saved=False))
```

Plus the matching FAQ answer check.

- [ ] **Step 2: Run and see it fail**

Run: `python -m pytest tests/test_pricing.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement** the move; FAQ history answer for `history_saved=True`: "Setelah masuk, riwayat chat dan proyek tersimpan di akunmu dan bisa kamu hapus. Long-term memory menyimpan konteks penting di backend Ciel dan hanya bisa dibaca akunmu sendiri."

- [ ] **Step 4: Run and see it pass**

Run: `python -m pytest tests/test_pricing.py -q`
Expected: PASS.

---

### Task 9: Verification, Ciel's check, commit and PR

**Files:**
- Create (scratchpad only, never committed): `<scratchpad>/harness/ciel_harness.py`

- [ ] **Step 1: Full suite**

Run: `python -m pytest -q`
Expected: all pass. If a test fails only because of local secrets (`.streamlit/secrets.toml`), rerun with them moved aside, and say so.

- [ ] **Step 2: Harness for signed-in and data-heavy states**

A wrapper that patches `st.user`, `is_pro`, `memory_admin` and seeds `st.session_state.chats` with appendix A answers, an analysis answer with `[Dugaan]`, a Riset map from the test fixtures, and a Kerangka answer; then `exec`s `app.py`. Run it with `python -m streamlit run <harness> --server.port 8599`.

- [ ] **Step 3: Browser matrix**

On Streamlit 1.54 and on 1.65 (scratch venv: `python -m venv <scratchpad>/st165 && <scratchpad>/st165/Scripts/pip install streamlit==1.65.* -r requirements.txt`), dark and light: Beranda (guest, signed in, project with and without files/map), chat with sources + guesses, Riset chat, Masuk, Harga, Privasi, all three dialogs, account popover, a disabled button on hover, at 1440, 1100 and 390 px. Disable transitions, then run a contrast scan (computed text colour vs the real composited background ≥ 4.5:1) on every visible text node, hover-only elements forced visible. Fix anything found, with a test in `tests/test_theme.py` for each selector fix.

- [ ] **Step 4: Hand over to Ciel**

Keep the preview running (`.claude/launch.json` entry `ciel-ui-preview`, port 8599, pointing at `app.py` in this worktree), give the localhost link, list what to look at, and wait. Do not commit until Ciel says "commit".

- [ ] **Step 5: After "commit"**

```bash
git add app.py beranda.py chat_sources.py login.py pricing.py .streamlit/config.toml requirements.txt tests/ docs/superpowers/
git commit -m "Redesign Ciel: dark-first look, Beranda with prompt templates, chat with sources rail"
git push -u origin HEAD
gh pr create --title "Redesign Ciel app (release 1 of 2)" --body "<summary, test results, what Ciel checked>"
```

No attribution lines. `.superpowers/` and `.impeccable/` stay uncommitted (add both to `.gitignore` in this commit).
