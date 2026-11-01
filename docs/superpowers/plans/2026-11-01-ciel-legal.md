# Ciel Legal Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the gaps between Ciel and the "app launch checklist" in the breakingbreach reel (instagram.com/reel/DfKH360zRG4), measured against Indonesian law (UU 27/2022 PDP, UU 8/1999 Perlindungan Konsumen, PP 80/2019 PMSE, Permenkominfo 5/2020 PSE), so Ciel can keep selling Pro publicly.

**Architecture:** A new `terms.py` mirrors `privacy.py` (pure `*_sections()` + `render_*()`), opened as a new Pengaturan tab. Consent is recorded per account and legal version in a new Supabase table `consents`, checked by a one-time gate after Google login. "Hapus akun" composes the existing delete functions plus one new `ChatStore.delete_account`. Non-code obligations (PSE registration, vendor DPAs, tax, lawyer review) go in `docs/LEGAL.md`.

**Tech Stack:** Python 3.10, Streamlit (1.54 local, 1.65 on Cloud), Supabase PostgREST via `requests`, unittest + `streamlit.testing.v1.AppTest`.

**Spec:** No separate spec doc. The spec is the reel's checklist (captured 2026-11-01, 35 items; ~27 readable) and the gap table below.

### Gap table (reel item → Ciel today → this plan)

| Reel item | Ciel today | Plan |
|---|---|---|
| Privacy policy | `privacy.py`, UU PDP-shaped | Task 1: name recipients + country, cookies, telemetry |
| Terms of service | none | Task 2 |
| Refund policy | none (docs/PRO.md: "dicatat saja") | Task 2 (section in Ketentuan) |
| Checkbox to agree to privacy policy & ToS | none | Task 3 (gate) + Task 4 (login line) |
| Disclose auto-renewals / easy cancel | "Sekali bayar, tanpa tagihan otomatis" already shown | nothing |
| Remove hidden fees | Rp79.000 flat, buyer pays no fee | nothing |
| Stop collecting unnecessary data | Google name/email/photo only | nothing |
| Data retention | 30 days + 5-week backups disclosed | Task 1 adds 10-year purchase records |
| Data access & deletion requests | per-item delete + export | Task 5: one-step "Hapus akun" |
| Audit third-party SDKs & tracking / block trackers until consent | Streamlit `gatherUsageStats` is **on** (default); landing loads Google Fonts | Task 1: turn telemetry off, disclose fonts |
| Publish subprocessor list | "pihak ketiga" without names (test forbids names) | Task 1 (Decision 2) |
| Data processing agreements | not tracked | Task 6 (manual) |
| Label AI-generated content | DOCX exports say "Disusun dengan Ciel…"; chat has no notice | Task 4 |
| Add business contact | email on landing; `OPERATOR_NAME`/`CONTACT_URL` optional | Task 2 shows them; Task 7 sets secrets |
| Unsubscribe / marketing opt-out | Ciel sends no marketing email | nothing (Task 6 records "add before any newsletter") |
| Fake countdown, fake reviews, customer logos, dark patterns, uptime promises | none found in `landing/index.html` | nothing; Task 6 records them as rules |
| Verify image, font, code licences | fonts Fraunces/Geist (OFL), own logo | Task 6 (record + one-off dependency licence scan) |
| Have a qualified lawyer review | — | Task 6 (manual) |

### Decisions for Ciel (defaults used below; change before executing)

1. **Refund rules** (Task 2): full refund when (a) paid but Pro not active within 1×24 jam, or (b) charged twice for one order; if Pro features are down on Ciel's side for more than 3 consecutive days, Pro is extended by the days lost. Request within 7 days of payment with the order number; refund paid within 14 working days. Any other request is reviewed case by case. There is deliberately **no** "uang tidak dapat dikembalikan" sentence: UU 8/1999 Pasal 18(1)(c) bans that standard clause.
2. **Name the recipients** (Task 1): reverses `test_third_parties_are_disclosed_without_brand_names` (commit 2b0db05). Default lists DeepSeek, Exa, Google (Gemini + login), Supabase, Streamlit Community Cloud, ngrok, Mayar, Google Fonts. Langflow stays unnamed: it is software on Ciel's own server, not a recipient.
3. **Consent gate for existing accounts** (Task 3): every signed-in account, including paying ones, sees the gate once on its next visit.

## Global Constraints

- All user-facing copy in plain Indonesian ("kamu"), no emoji, no English labels (Terms → "Ketentuan", heading "Syarat dan Ketentuan").
- `LEGAL_VERSION = "2026-11-01"` (in `terms.py`); `TERMS_UPDATED = "1 November 2026"`; `PRIVACY_UPDATED = "1 November 2026"`.
- Pro price comes from `pricing.PLANS` (`format_idr(plan["monthly"])`), never typed in `terms.py`.
- Operator and contact come only from `OPERATOR_NAME` / `safe_contact_url(CONTACT_URL)`; with either unset the pages fall back to "pengelola Ciel" wording and never print `None` or an empty link.
- Every operator/contact value goes through `html.escape` (same as `privacy.py`).
- No banned standard clauses (UU 8/1999 Pasal 18): no "tidak dapat/bisa dikembalikan", no "tidak bertanggung jawab atas (segala|apa pun)", no clause letting later terms cut a Pro period already paid.
- Purchase records (`pro_orders`, `pro_members`) are never deleted by app code (10-year tax record retention).
- Do not commit until Ciel has checked the UI in their own browser (preview `ciel-ui-preview`, port 8599) and said "commit"; then commit task by task with the messages given. No Claude attribution lines in commits or the PR.
- Tests run with `py -3.10 -m unittest` (3.14 has no streamlit). Full suite must stay green.
- Dark mode: new elements reuse existing `--c-*` tokens and the login page's classes; check both themes.

## Review Focus

1. **Supabase down while checking or saving consent** → the user is never locked out: the gate is skipped (load failure) or accepted for the session (save failure), and an error is logged. Tests in Task 3.
2. **Every existing signed-in AppTest hits the new gate** → each harness must default to a stored current consent, or dozens of unrelated tests fail. Step in Task 3.
3. **"Hapus akun" fails halfway** (e.g. memory flow times out) → no logout, a notice names what was not deleted, and pressing again retries everything (each delete is idempotent). Tests in Task 5.
4. **Anonymous visitor opens `?page=terms`** (link from landing) → Ketentuan renders without login, inside the Pengaturan dialog. Test in Task 2.
5. **`OPERATOR_NAME` / `CONTACT_URL` unset** → no `None`, no `href=""`, fallback wording. Test in Task 2.

---

### Task 1: Privacy page names recipients, telemetry off

**Files:**
- Modify: `.streamlit/config.toml`
- Modify: `privacy.py` (constant `SUBPROCESSORS`, new section, cookie line, purchase retention, `PRIVACY_UPDATED`)
- Test: `tests/test_privacy.py` (replace `test_third_parties_are_disclosed_without_brand_names`), `tests/test_app_hygiene.py`

**Interfaces:**
- Produces: `privacy.SUBPROCESSORS: tuple[tuple[str, str, str], ...]` = (name, what it does for Ciel, country). `privacy_sections(...)` signature unchanged.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_privacy.py, PrivacyPageTest (replaces the "without_brand_names" test)
def test_recipients_are_named_with_their_country(self):
    sections = dict(__import__("privacy").privacy_sections(
        retention_days=30, memory_enabled=True, data_controls=True, payments="Mayar"))
    text = " ".join(sections["Pihak ketiga yang menerima datamu"])
    for name, country in (("DeepSeek", "Tiongkok"), ("Exa", "Amerika Serikat"),
                          ("Supabase", "Jepang"), ("Mayar", "Indonesia"), ("Google Fonts", "Amerika Serikat")):
        self.assertIn(name, text)
        self.assertIn(country, text)
    self.assertNotIn("Langflow", text)

def test_payment_recipient_only_when_payments_are_on(self):
    sections = dict(__import__("privacy").privacy_sections(
        retention_days=30, memory_enabled=True, data_controls=True))
    self.assertNotIn("Mayar", " ".join(sections["Pihak ketiga yang menerima datamu"]))

def test_cookies_and_telemetry_are_disclosed(self):
    text = self.text(retention_days=30, memory_enabled=True, data_controls=True)
    self.assertIn("tidak memasang cookie iklan atau pelacak", text)
    self.assertIn("statistik pemakaian bawaan Streamlit dimatikan", text)

def test_purchase_records_are_kept_for_tax(self):
    text = self.text(retention_days=30, memory_enabled=True, data_controls=True, payments="Mayar")
    self.assertIn("10 tahun", text)
    self.assertIn("kewajiban pajak", text)

# tests/test_app_hygiene.py
def test_streamlit_usage_stats_are_off(self):
    config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    self.assertRegex(config, r"(?m)^\[browser\]\s*\n(?:.*\n)*?gatherUsageStats\s*=\s*false")
```

Also update `test_page_covers_the_pdp_checklist` so the expected first section is still "Siapa yang mengelola Ciel".

- [ ] **Step 2: Run to verify they fail**

Run: `py -3.10 -m unittest tests.test_privacy tests.test_app_hygiene -v`
Expected: the four new privacy tests and the hygiene test FAIL (KeyError / assertion).

- [ ] **Step 3: Implement**

- `.streamlit/config.toml`: add `[browser]` with `gatherUsageStats = false` and a one-line comment ("Telemetri bawaan Streamlit mati; halaman Privasi menjanjikan ini").
- `privacy.py`: `SUBPROCESSORS` in this order, with this copy:
  - `("DeepSeek", "model AI yang menyusun jawaban", "Tiongkok")`
  - `("Exa", "pencarian web dan jurnal", "Amerika Serikat")`
  - `("Google (Gemini API)", "membaca foto yang kamu kirim", "Amerika Serikat")`
  - `("Google", "login dengan akun Google", "Amerika Serikat")`
  - `("Supabase", "database riwayat chat, proyek, profil, dan status Pro", "Jepang")`
  - `("Streamlit Community Cloud", "menjalankan tampilan aplikasi", "Amerika Serikat")`
  - `("ngrok", "jalur terenkripsi ke server Ciel", "Amerika Serikat")`
  - `("Google Fonts", "huruf di halaman depan ciel-ai.web.id", "Amerika Serikat")`
  - Mayar is appended only when `payments` is truthy: `(payments, "pembayaran Ciel Pro", "Indonesia")`.
- New section `("Pihak ketiga yang menerima datamu", items)` placed right after "Apa yang terjadi saat kamu mengirim pesan": one `<li>` per entry, `<strong>{name}</strong> ({country}): {role}.`, all escaped, followed by: "Ciel hanya mengirim data yang dibutuhkan untuk tugas masing-masing."
- In `processing`, keep the "luar Indonesia" sentence and point to the new section instead of describing providers generically.
- Add to `stored` (always): "Ciel sendiri tidak memasang cookie iklan atau pelacak; cookie yang dipakai hanya untuk menjaga status login, dan statistik pemakaian bawaan Streamlit dimatikan."
- In the `payments` paragraph add: "Catatan pembelian disimpan 10 tahun karena kewajiban pajak, juga setelah akunmu dihapus."
- `PRIVACY_UPDATED = "1 November 2026"`.

- [ ] **Step 4: Run to verify they pass**

Run: `py -3.10 -m unittest tests.test_privacy tests.test_app_hygiene -v` then `py -3.10 -c "from streamlit import config; config.get_config_options(force_reparse=True); print(config.get_option('browser.gatherUsageStats'))"` from the repo root.
Expected: all PASS; the one-liner prints `False`.

- [ ] **Step 5: Commit** (after Ciel's "commit")

```bash
git add .streamlit/config.toml privacy.py tests/test_privacy.py tests/test_app_hygiene.py
git commit -m "Name the services that receive user data and turn off Streamlit telemetry"
```

---

### Task 2: Syarat dan Ketentuan page (with refund rules)

**Files:**
- Create: `terms.py`
- Modify: `account_settings.py` (`SETTINGS_TABS`, `PAGE_TABS`), `app.py` (`open_settings_from_url` page list, `render_settings_tab`, new `show_terms`)
- Test: `tests/test_terms.py` (new), `tests/test_settings_app.py` (tab list test)

**Interfaces:**
- Consumes: `pricing.PLANS`, `pricing.format_idr`, `pricing.safe_contact_url` (already used by app.py), `PRIVACY_CSS` from `privacy.py` (reuse; wrap in `ciel-privacy` class so styling is shared).
- Produces:
  - `terms.LEGAL_VERSION: str = "2026-11-01"` — bump when Ketentuan **or** Privasi changes materially (comment says so).
  - `terms.TERMS_UPDATED: str = "1 November 2026"`
  - `terms.terms_sections(operator=None, contact_url=None, payments=False) -> list[tuple[str, list[str]]]`
  - `terms.render_terms(operator=None, contact_url=None, payments=False) -> None`
  - Settings tab id `"ketentuan"`, label `"Ketentuan"`, icon `":material/gavel:"`, after `"privasi"`; `PAGE_TABS["terms"] = "ketentuan"` (so `?page=terms` works).
  - `app.show_terms()` → `open_settings("ketentuan")`.

Section titles, in order (the test pins them):
1. "Siapa yang mengelola Ciel" — operator + contact, same fallback wording as privacy.
2. "Ciel adalah AI" — must include: "Jawaban Ciel dibuat oleh AI dan bisa keliru, termasuk sumber yang dikutip." and "Periksa jawaban dan sumbernya sebelum kamu pakai untuk tugas, skripsi, atau keputusan penting."; Ciel is not legal, medical, or financial advice.
3. "Kejujuran akademik" — "Ciel membantu kamu belajar dan mencari sumber, bukan menulis tugas untukmu." and "Kamu tetap bertanggung jawab atas karya yang kamu kumpulkan dan wajib mengikuti aturan kampusmu soal penggunaan AI."
4. "Yang tidak boleh" — no illegal content, no other people's personal data without right, no attacking/overloading the service or bypassing usage limits, no reselling access.
5. "Isi milikmu" — what the user sends stays theirs; Ciel only uses it to answer and as described on the Privasi page.
6. "Ciel Pro" (only when `payments`) — price from `pricing.PLANS`, "Sekali bayar untuk 30 hari, tanpa tagihan otomatis.", paid via `{payments}`, Pro active once payment is confirmed.
7. "Pengembalian dana" (only when `payments`) — Decision 1 copy: the two full-refund cases, the 3-day outage extension, "paling lambat 7 hari setelah membayar", "nomor order", "paling lambat 14 hari kerja", "Permintaan dengan alasan lain tetap kami tinjau satu per satu."
8. "Usia" — under 18 only with parent/guardian permission (same as privacy).
9. "Batas layanan" — free plan limits can change; Ciel aims to be available but can be down for maintenance or provider outages; no uptime number.
10. "Perubahan ketentuan" — announced on this page before taking effect; "Perubahan tidak mengurangi masa Pro yang sudah kamu bayar."; material changes ask for consent again.
11. "Hukum dan sengketa" — hukum Republik Indonesia; musyawarah first; then BPSK or court per UU Perlindungan Konsumen.

- [ ] **Step 1: Write the failing tests** (`tests/test_terms.py`)

```python
import re, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import terms

class TermsContentTest(unittest.TestCase):
    def text(self, **kw):
        return " ".join(i for _, items in terms.terms_sections(**kw) for i in items)

    def test_sections_in_order_and_paid_sections_follow_payments(self):
        paid = [t for t, _ in terms.terms_sections(payments="Mayar")]
        self.assertEqual(paid[0], "Siapa yang mengelola Ciel")
        self.assertEqual(paid[-1], "Hukum dan sengketa")
        self.assertIn("Pengembalian dana", paid)
        free = [t for t, _ in terms.terms_sections()]
        self.assertNotIn("Ciel Pro", free)
        self.assertNotIn("Pengembalian dana", free)

    def test_ai_and_academic_notices(self):
        text = self.text()
        self.assertIn("dibuat oleh AI dan bisa keliru", text)
        self.assertIn("aturan kampusmu", text)

    def test_refund_rules(self):
        text = self.text(payments="Mayar")
        for phrase in ("1&times;24 jam", "dua kali", "3 hari", "7 hari setelah membayar", "nomor order", "14 hari kerja", "tetap kami tinjau"):
            self.assertIn(phrase, text)

    def test_price_comes_from_pricing(self):
        from pricing import PLANS, format_idr
        pro = next(p for p in PLANS if p["id"] == "pro")
        self.assertIn(format_idr(pro["monthly"]), self.text(payments="Mayar"))

    def test_no_banned_standard_clauses(self):
        text = self.text(payments="Mayar", operator="X", contact_url="mailto:a@b.c").lower()
        for banned in (r"tidak (dapat|bisa) dikembalikan", r"tidak bertanggung jawab atas (segala|apa pun)"):
            self.assertIsNone(re.search(banned, text), banned)
        self.assertIn("tidak mengurangi masa pro yang sudah kamu bayar", text)

    def test_operator_is_escaped_and_fallback_is_clean(self):
        self.assertIn("<strong>Tim &lt;Ciel&gt;</strong>", self.text(operator="Tim <Ciel>"))
        bare = self.text()
        self.assertIn("pengelola Ciel", bare)
        self.assertNotIn("None", bare)
        self.assertNotIn('href=""', bare)

```

`TermsAppTest.test_anonymous_terms_link_opens_the_ketentuan_tab`: same env and AppTest setup as `tests/test_privacy.py::test_app_renders_the_privacy_page`, with `at.query_params["page"] = "terms"`. Asserts: `not at.exception`; markdown contains `<h1>Syarat dan Ketentuan</h1>` and `Terakhir diperbarui:`; `"settabactive_ketentuan"` is among the button keys.

Add `tests.test_terms` to the unittest list in `.github/workflows/ci.yml` (`tests/test_ci_coverage.py` fails otherwise). In `tests/test_settings_app.py::test_settings_lists_tabs_for_the_login_state`, add `ketentuan` to both expected tab lists (after `privasi`).

- [ ] **Step 2: Run to verify they fail**

Run: `py -3.10 -m unittest tests.test_terms tests.test_settings_app -v`
Expected: ImportError for `terms`; the tab-list test FAILs.

- [ ] **Step 3: Implement** `terms.py`, the tab entries, `"terms"` in the `open_settings_from_url` page tuple, the `render_settings_tab` branch (`elif tab == "ketentuan": render_terms(operator=OPERATOR_NAME, contact_url=safe_contact_url(CONTACT_URL), payments=PAYMENT_PROVIDER_NAME if PAYMENTS_ENABLED else False)`), and `show_terms()`. The render reuses `PRIVACY_CSS` and the `ciel-privacy` wrapper; the heading is `<h1>Syarat dan Ketentuan</h1>`, with the intro "Aturan main memakai Ciel dan Ciel Pro." and the updated date line.

- [ ] **Step 4: Run to verify they pass**

Run: `py -3.10 -m unittest tests.test_terms tests.test_settings_app tests.test_privacy -v`
Expected: PASS.

- [ ] **Step 5: Commit** (after Ciel's "commit")

```bash
git add terms.py account_settings.py app.py tests/test_terms.py tests/test_settings_app.py .github/workflows/ci.yml
git commit -m "Add a Syarat dan Ketentuan tab with refund rules"
```

---

### Task 3: Record consent once per account and legal version

**Files:**
- Modify: `docs/chat_store.sql` (table `consents`), `chat_store.py` (two methods), `login.py` (`render_consent`), `app.py` (gate)
- Test: `tests/test_chat_store.py`, `tests/test_consent_app.py` (new), plus every AppTest harness that signs in (see Step 6)

**Interfaces:**
- Consumes: `terms.LEGAL_VERSION`, `app.show_terms`, `app.show_privacy`, `ChatStore._request`.
- Produces:
  - SQL: `create table if not exists public.consents (owner text not null, version text not null, accepted_at timestamptz not null default now(), primary key (owner, version)); alter table public.consents enable row level security;` with a comment saying rows are proof of consent (UU PDP Pasal 22-24) and survive "Hapus akun".
  - `ChatStore.load_consent(owner) -> str | None` — newest accepted `version` (`order=accepted_at.desc`, `limit=1`), `""` when none, `None` when the request fails.
  - `ChatStore.save_consent(owner, version) -> bool` — POST `{"owner", "version"}` with `Prefer: resolution=ignore-duplicates`.
  - `login.render_consent(on_accept, on_logout, on_terms, on_privacy) -> None`.
  - `app.consent_needed() -> bool`, `app.accept_consent() -> None`; session key `consented` holds `(owner, version)`.

Gate rules (`consent_needed`):
- not `logged_in()` or `CHAT_STORE is None` → `False` (no database, no proof to keep; the login page line from Task 4 still applies).
- `st.session_state.get("consented") == (owner, LEGAL_VERSION)` → `False`.
- `stored = CHAT_STORE.load_consent(owner)`; `None` → log `consent_load_failed`, set `consented = (owner, LEGAL_VERSION)` for this session, return `False`.
- `stored == LEGAL_VERSION` → set `consented`, return `False`; otherwise `True`.

`accept_consent`: `save_consent`; on `False` log `consent_save_failed`; always set `consented`.

The gate runs right after the login-view block in `app.py`: `if consent_needed(): render_consent(accept_consent, st.logout, show_terms, show_privacy); st.stop()`. It sits after `settings_dialog()`, so the Ketentuan/Privasi buttons open the dialog over the gate.

`render_consent` copy (reuse login page classes `ciel-loginbrand`/`ciel-loginhead`, container key `consentbox`):
- `<h1>Sebelum mulai</h1>`
- "Ciel memproses pesanmu lewat layanan pihak ketiga, termasuk penyedia model AI di Tiongkok serta server di Jepang dan Amerika Serikat. Rinciannya ada di Kebijakan Privasi."
- checkbox (key `consent_check`): "Saya sudah membaca dan menyetujui Syarat dan Ketentuan serta Kebijakan Privasi Ciel, termasuk pemrosesan data di luar Indonesia."
- primary button `consent_accept` "Setuju dan lanjut", `disabled=not st.session_state.get("consent_check")`
- secondary `consent_logout` "Keluar"; tertiary `consent_terms` "Syarat dan Ketentuan", `consent_privacy` "Kebijakan privasi".

- [ ] **Step 1: Write the failing ChatStore tests** (`tests/test_chat_store.py`, same mocking style as the profile tests)

- `test_load_consent_returns_newest_version_or_empty`: GET to `/rest/v1/consents` with `owner=eq.<owner>`, `order=accepted_at.desc`, `limit=1`; rows `[{"version": "2026-11-01"}]` → `"2026-11-01"`; `[]` → `""`.
- `test_load_consent_failure_is_none`: HTTP 500 → `None`.
- `test_save_consent_posts_owner_and_version_without_duplicates`: POST json `{"owner": SIGNED_IN_OWNER, "version": "2026-11-01"}`, `Prefer` contains `resolution=ignore-duplicates`; returns `True`; HTTP 500 → `False`.
- `test_consent_rejects_bad_owner`: owner `"x; drop"` → no request, `None` / `False`.

- [ ] **Step 2: Write the failing app tests** (`tests/test_consent_app.py`, added to the `ci.yml` unittest list; copy the `start()` harness from `tests/test_settings_app.py`, `rows` keyed by table)

- `test_signed_in_without_consent_sees_the_gate_not_the_composer`: rows `{"consents": []}` → markdown has "Sebelum mulai", `at.chat_input` empty.
- `test_accept_needs_the_checkbox_and_saves_the_version`: `consent_accept` disabled; check `consent_check`, click accept → a POST to `consents` with `LEGAL_VERSION`; next run shows the composer.
- `test_current_consent_skips_the_gate`: rows `{"consents": [{"version": LEGAL_VERSION}]}` → no "Sebelum mulai".
- `test_older_version_asks_again`: rows `{"consents": [{"version": "2026-01-01"}]}` → gate shown.
- `test_database_down_does_not_lock_the_user_out`: `down={"consents"}` → no gate, composer shown, no exception.
- `test_failed_save_still_lets_the_user_in`: GET ok and empty, POST to consents fails → after accept, composer shown.
- `test_anonymous_visitor_never_sees_the_gate`: no user → no "Sebelum mulai".
- `test_gate_terms_button_opens_the_ketentuan_tab`: click `consent_terms` → `settabactive_ketentuan` present.

- [ ] **Step 3: Run to verify they fail**

Run: `py -3.10 -m unittest tests.test_chat_store tests.test_consent_app -v`
Expected: AttributeError (`load_consent`) and gate assertions FAIL.

- [ ] **Step 4: Implement** the SQL, the two `ChatStore` methods, `render_consent`, `consent_needed`, `accept_consent`, and the gate call.

- [ ] **Step 5: Run the new tests**

Run: `py -3.10 -m unittest tests.test_chat_store tests.test_consent_app -v`
Expected: PASS.

- [ ] **Step 6: Fix the signed-in harnesses (Review Focus 2)**

Run: `py -3.10 -m unittest discover -s tests -v 2>&1 | findstr /C:"FAIL" /C:"ERROR"`.
For each failing harness that signs in with Supabase rows, make its default rows include `"consents": [{"version": LEGAL_VERSION}]` (import from `terms`), merged under any rows a test passes. Do not change test expectations beyond this.
Expected after the change: the full suite PASSES.

- [ ] **Step 7: Commit** (after Ciel's "commit")

```bash
git add docs/chat_store.sql chat_store.py login.py app.py tests/ .github/workflows/ci.yml
git commit -m "Ask signed-in users to accept the terms once per legal version and record it"
```

---

### Task 4: Notices on the login page, Beranda, and landing

**Files:**
- Modify: `login.py` (`render_login` gets `on_terms=None`), `app.py` (pass `on_terms=show_terms`), `beranda.py`, `landing/index.html` (footer "Akun" list)
- Test: `tests/test_login.py`, `tests/test_beranda.py` or `tests/test_beranda_app.py`, `tests/test_landing.py`

**Interfaces:**
- Consumes: `app.show_terms` (Task 2).
- Produces: `render_login(..., on_privacy=None, on_terms=None)`; button key `login_terms`; landing link `https://app.ciel-ai.web.id/?page=terms`.

- [ ] **Step 1: Write the failing tests**

- `tests/test_login.py::test_google_button_comes_with_the_consent_line`: with auth on, markdown contains "Dengan masuk, kamu menyetujui Syarat dan Ketentuan dan Kebijakan Privasi Ciel." and button keys include `login_terms` and `login_privacy`.
- Beranda test (in whichever file renders the empty state with AppTest): markdown contains "Ciel adalah AI dan bisa keliru. Cek sumbernya sebelum kamu pakai."
- `tests/test_landing.py`: add `"terms"` to the known pages in `test_app_links_use_known_pages`, and add `test_footer_links_terms_and_privacy` asserting both `?page=terms` and `?page=privacy` appear inside `<footer`.

- [ ] **Step 2: Run to verify they fail**

Run: `py -3.10 -m unittest tests.test_login tests.test_landing tests.test_beranda tests.test_beranda_app -v`
Expected: the new tests FAIL.

- [ ] **Step 3: Implement**

- Login: the consent line goes under `ciel-loginscope` as its own `<p class="ciel-loginscope">`. Add the `login_terms` tertiary button inside the `loginlegal` container next to `login_privacy`, labelled "Syarat dan Ketentuan".
- Beranda: one quiet line in the existing muted text style under the composer area. Match the existing beranda markup; no new colour.
- Landing: `<li><a href="https://app.ciel-ai.web.id/?page=terms">Ketentuan</a></li>` after Privasi in the "Akun" list. The inline script is untouched, so the CSP hash test stays green.

- [ ] **Step 4: Run to verify they pass**

Run: `py -3.10 -m unittest tests.test_login tests.test_landing tests.test_beranda tests.test_beranda_app -v`
Expected: PASS.

- [ ] **Step 5: Commit** (after Ciel's "commit")

```bash
git add login.py app.py beranda.py landing/index.html tests/test_login.py tests/test_landing.py tests/test_beranda*.py
git commit -m "Show the AI and consent notices on login, Beranda and the landing footer"
```

---

### Task 5: "Hapus akun" deletes all of a user's data in one step

**Files:**
- Modify: `chat_store.py` (`delete_account`), `app.py` (`delete_my_account`, section in `render_data_settings`), `privacy.py` (rights text)
- Test: `tests/test_chat_store.py`, `tests/test_privacy.py` (`AppDataControlsTest`), `tests/test_settings_app.py`

**Interfaces:**
- Consumes: `delete_server_chat_history()`, `memory_admin("delete_all")`, `memory_admin("delete_all_datasets")` (all existing, all return `{"ok": bool, ...}`), `CHAT_STORE`, `st.logout`.
- Produces:
  - `ChatStore.delete_account(owner) -> bool` — DELETE `chats`, `projects`, `profiles` for the owner; tries all three even if one fails; `True` only if all succeed. Never touches `pro_orders`, `pro_members`, `consents`.
  - `app.delete_my_account() -> None` — runs the four deletions in this order: server history, memories, datasets, database rows. If all succeed: `st.session_state.clear()` then `st.logout()`. Otherwise it sets `settings_notice = ("error", "Sebagian data belum terhapus: <parts>. Coba lagi.")`, where parts are the Indonesian names of what failed ("riwayat pesan di server", "memory", "dataset", "chat dan proyek").
  - UI: shown only when `logged_in() and CHAT_STORE and MEMORY_ADMIN_FLOW_ID`, as the last block of Data saya. Heading "Hapus akun". Copy: "Semua chat, proyek, profil, memory, dan datasetmu dihapus permanen, lalu kamu keluar. Akun Google-mu tidak terhapus. Catatan pembelian Pro tetap disimpan 10 tahun karena kewajiban pajak, dan masa Pro yang tersisa tetap tercatat jika kamu masuk lagi dengan akun yang sama." Checkbox `confirm_delete_account` "Saya paham semua dataku akan dihapus permanen". Button `delete_account` "Hapus akun dan semua data", `type="secondary"`, disabled until checked, `on_click=delete_my_account`.

- [ ] **Step 1: Write the failing tests**

- `tests/test_chat_store.py::test_delete_account_removes_only_own_rows_from_three_tables`: three DELETE calls to `chats`, `projects`, `profiles`, each `owner=eq.<owner>`; none to `pro_orders`/`pro_members`/`consents`; returns `True`.
- `test_delete_account_keeps_going_after_a_failure`: `projects` returns 500 → all three still attempted, returns `False`.
- `tests/test_privacy.py::AppDataControlsTest::test_delete_account_logs_out_only_when_everything_is_gone`: load `delete_my_account` with `load_app_functions`, stub the four deletions and `st` (`session_state` dict + `logout` Mock). All ok → `logout` called once, session cleared. Memory fails → `logout` not called, notice contains "memory" and the other parts are not listed.
- `tests/test_settings_app.py::test_delete_account_needs_confirmation_and_is_hidden_without_data_controls`: with `MEMORY_ADMIN_FLOW_ID` set, `delete_account` is disabled until `confirm_delete_account` is checked; without it the button is absent.
- `tests/test_privacy.py`: rights text with data controls contains "<strong>Hapus akun</strong>".

- [ ] **Step 2: Run to verify they fail**

Run: `py -3.10 -m unittest tests.test_chat_store tests.test_privacy tests.test_settings_app -v`
Expected: the new tests FAIL.

- [ ] **Step 3: Implement** `delete_account`, `delete_my_account`, the Data saya block (reuse the "Hapus semua memoriku" checkbox+button pattern at app.py ~5030), and append to the `data_controls` rights sentence: "atau hapus semuanya sekaligus lewat <strong>Hapus akun</strong>."

- [ ] **Step 4: Run to verify they pass**

Run: `py -3.10 -m unittest tests.test_chat_store tests.test_privacy tests.test_settings_app -v`
Expected: PASS.

- [ ] **Step 5: Commit** (after Ciel's "commit")

```bash
git add chat_store.py app.py privacy.py tests/test_chat_store.py tests/test_privacy.py tests/test_settings_app.py
git commit -m "Let users delete their account data in one step"
```

---

### Task 6: Legal register for the steps code cannot do

**Files:**
- Create: `docs/LEGAL.md`
- Modify: `RELEASE_CHECKLIST.md` (Pre-Release item), `CHANGELOG.md`, `docs/PRO.md` (refund handling), `.github/workflows/ci.yml` (add `tests.test_legal_docs`)
- Test: `tests/test_legal_docs.py` (new, one test)

`docs/LEGAL.md` sections, each line an unchecked box with owner "Ciel" unless marked done:
1. **Disclaimer**: not legal advice; review by a qualified lawyer before relying on it (reel's last item).
2. **Where each reel item lives**: the gap table from this plan, with file paths.
3. **Registrations**: PSE Lingkup Privat registration at Komdigi through OSS (Permenkominfo 5/2020; required before serving the public, or access can be blocked). It needs an NIB from OSS RBA, so choose the KBLI with help (the NPWP has KLU 62199). Record dates and numbers here once done.
4. **Vendor terms / DPAs**: accept or read the data processing terms of Supabase (DPA in the dashboard), Google Cloud for Gemini paid tier, Exa, DeepSeek (check API data retention and training use), Streamlit Community Cloud, ngrok, Mayar merchant agreement. Note the link and date for each.
5. **Secrets before going public**: `OPERATOR_NAME` (name shown as pengelola) and `CONTACT_URL` set in Streamlit Cloud.
6. **Tax and records**: keep Mayar payout and order records 10 years; ask a tax adviser about PPh Final UMKM (PP 55/2022).
7. **Refund handling**: how to refund a Mayar payment by hand and mark the order (SQL `update public.pro_orders set midtrans_status = 'refunded' ... ; update public.pro_members set expires_at = now() ...`). Cross-link `docs/PRO.md`.
8. **Product rules** (from the reel): no fake countdowns, fake reviews, unapproved customer logos, uptime numbers, confirmshaming; any future marketing email needs opt-in and an unsubscribe link; bump `terms.LEGAL_VERSION` on material changes to Ketentuan or Privasi.
9. **Licences**: fonts Fraunces and Geist (SIL OFL 1.1), logo by Ciel; run `py -3.10 -m pip install pip-licenses && py -3.10 -m pip_licenses --from=mixed --order=license` once and record any GPL/AGPL/unknown entries.

- [ ] **Step 1: Write the failing test**

```python
def test_legal_register_lists_the_manual_obligations(self):
    text = (ROOT / "docs" / "LEGAL.md").read_text(encoding="utf-8")
    for item in ("PSE", "OSS", "OPERATOR_NAME", "CONTACT_URL", "DPA", "10 tahun", "LEGAL_VERSION", "bukan nasihat hukum"):
        self.assertIn(item, text)
    self.assertIn("docs/LEGAL.md", (ROOT / "RELEASE_CHECKLIST.md").read_text(encoding="utf-8"))
```

- [ ] **Step 2: Run to verify it fails** — `py -3.10 -m unittest tests.test_legal_docs -v` → FAIL (file missing).
- [ ] **Step 3: Write** `docs/LEGAL.md`, add to `RELEASE_CHECKLIST.md` Pre-Release: "- [ ] Changes to Privasi or Ketentuan bump `terms.LEGAL_VERSION` and the page dates; open items in `docs/LEGAL.md` reviewed.", add a CHANGELOG entry, and replace the refund line in `docs/PRO.md` with a pointer to `docs/LEGAL.md` §7.
- [ ] **Step 4: Run to verify it passes** — same command → PASS; then the full suite `py -3.10 -m unittest discover -s tests` → OK.
- [ ] **Step 5: Commit** (after Ciel's "commit")

```bash
git add docs/LEGAL.md RELEASE_CHECKLIST.md CHANGELOG.md docs/PRO.md tests/test_legal_docs.py .github/workflows/ci.yml
git commit -m "Add a legal register for registrations, vendor terms and refunds"
```

---

### Task 7: Ship (needs Ciel at each step)

- [ ] **Step 1:** Start the preview (`.claude/launch.json` → `ciel-ui-preview`, port 8599) and send Ciel the links to check, in light and dark: login page, consent gate (signed in), Pengaturan → Ketentuan / Privasi / Data saya → Hapus akun, Beranda notice. Wait for "commit", then make the Task 1–6 commits.
- [ ] **Step 2:** With Ciel's explicit approval, apply the `consents` migration to production Supabase (`nibbamicnqdxtmaacrio`) via `apply_migration` named `consents`. Verify with `list_tables` that the table exists with RLS on.
- [ ] **Step 3:** Ciel sets `OPERATOR_NAME` and `CONTACT_URL` in Streamlit Cloud secrets (built-in browser, Ciel signs in).
- [ ] **Step 4:** Push the branch, open the PR (body ends with the Claude Code line the harness gives, no co-author lines), bind it with ccd_pr, let CI run.
- [ ] **Step 5:** After merge: reboot the Cloud app if it shows an ImportError, then on the live site check `?page=terms`, the gate on a signed-in account (accept once, reload, no gate), and that a row appears in `public.consents`.
