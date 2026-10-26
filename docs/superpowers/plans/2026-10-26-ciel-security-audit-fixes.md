# Ciel Security Audit Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the holes found in the 2026-10-26 security audit: a leaked Langflow key in the public repo, unpinned dependencies, a shared cache that can spread a poisoned answer, and small CI and landing-page gaps.

**Architecture:** No new services. Each fix lives where its invariant belongs: secret and supply-chain rules become offline tests in CI, the cache rule goes into `AnswerCache.put`, the landing page gets a meta CSP. `SECURITY.md` records each control in the task that adds it.

**Tech Stack:** Python 3 `unittest`, Streamlit, pip-tools (`pip-compile --generate-hashes`), GitHub Actions, static HTML on GitHub Pages.

**Spec:** the "Audit findings" section below (no separate spec; Ciel asked for an audit and fixes on 2026-10-26).

## Audit findings (2026-10-26)

Checked with the skills: securing-github-actions-workflows, detecting-supply-chain-attacks-in-ci-cd, implementing-secret-scanning-with-gitleaks, detecting-indirect-prompt-injection, testing-for-broken-access-control, performing-security-headers-audit.

| # | Severity | Finding | Fix |
|---|---|---|---|
| F1 | High | A Langflow API key (`sk-Qcdm…`) is hardcoded in the Math Tutor tool code in `flow/v1.0.0/` and `flow/v1.1.0/Ciel_AI_Long-Term_Memory_Master.json`, and in history (commits `8cebbf2`, `538d07d`, `d2bb989`). The repo is **public**. Network controls limit the damage: Langflow listens on 127.0.0.1, and ngrok applies Basic Auth and a path allowlist. GitHub secret scanning has no pattern for Langflow keys, so it never flagged this. | Ciel revokes the key; Task 1 |
| F2 | High | `requirements.txt` is unpinned (`requests`, `streamlit[auth]>=1.54`, …). Every Streamlit Cloud reboot installs whatever is newest on PyPI, so a hijacked release reaches production with no review. `pip-audit` audits the newest versions, not the deployed ones. | Task 2 |
| F3 | Medium | The shared answer cache serves a guest's answer to everyone for 24 h. An answer bent by a prompt injection in a web page (for example, one carrying a phishing link) would spread to every user. **Ciel's decision:** do not cache answers that contain links. | Task 3 |
| F4 | Low | `pages.yml` checks out without `persist-credentials: false`. No test guards the workflow rules that already hold (SHA pins, no `${{ github.event… }}` in `run:`, explicit `permissions`). | Task 4 |
| F5 | Low | The landing page has no Content-Security-Policy and no Referrer-Policy. GitHub Pages cannot set headers; a `<meta>` CSP is the available control. | Task 5 |

Checked and passing: Midtrans webhook (constant-time signature check plus Status API re-check, order ID regex); `ciel_settle_order` (SECURITY DEFINER, `search_path=public`, no EXECUTE for `anon` or `authenticated`); Supabase tables (RLS on with no policies, so only the service key reaches them; owner filter and ID regex in `chat_store.py`); owner ID derived from the Google `sub`, never from input; HTML rendering escapes all dynamic text and allows only `http(s)` source links; workflows have SHA-pinned actions, `contents: read`, no `pull_request_target`, and no event interpolation.

Accepted and out of scope: Streamlit Community Cloud response headers (not configurable); ML prompt-injection detectors such as LLM Guard or Prompt Guard (too heavy for Cloud RAM; prompt rules, Source Guard and image stripping stay the controls); rewriting Git history (once the key is revoked it is worthless, and rewriting a public repo breaks clones); the Pillow CVE exception (tracked separately).

## Global Constraints

- Do not widen the answer cache (only anonymous answers fill it, TTL 1 day): see `docs/superpowers/plans/2026-10-25-ciel-answer-cache.md`.
- No new runtime dependency in `requirements.in`. Tests use only the standard library.
- Never write a real secret into code, tests, docs, commits or chat. Build test fixtures that look like secrets by string concatenation, so the scanner never matches its own file.
- Commits have no Claude attribution lines (Ciel's standing rule).
- Production steps (Langflow key revocation, Cloud reboot) are Ciel's, one at a time, with Ciel's go-ahead.
- Run tests the way CI does: the module list in `.github/workflows/ci.yml`, run with `python -m unittest -v <modules>`. A local `.streamlit/secrets.toml` with `[auth]` breaks `test_login`; run from a clean cwd with `PYTHONPATH` set if needed.

## Review Focus

1. **Ordinary answers that mention a file or a version** ("simpan sebagai data.csv", "Python 3.12"): they must still be cached. The link rule must not treat `data.csv` or `3.12` as a domain. Covered by `test_answers_without_links_are_still_cached` (Task 3).
2. **Every Langflow key shape in a flow JSON**, including keys inside JSON-escaped component code (`\"sk-…\"`): the scanner must catch them. Covered by `test_patterns_catch_known_secret_shapes` (Task 1).
3. **Placeholders that look like keys** (`DEEPSEEK_API_KEY`, `sk-REVOKED`, `.streamlit/secrets.toml.example` values): they must not fail CI. Covered by `test_placeholders_are_not_secrets` (Task 1).
4. **A Dependabot PR that bumps a pin**: it must still pass the lock test (hash present, `==` pin). Covered by `test_requirements_are_locked_with_hashes` (Task 2), which checks the format, not specific versions.
5. **Landing script edited later without updating the CSP hash**: the page would silently lose its script. Covered by `test_csp_hash_matches_inline_script` (Task 5).

---

### Task 0 (Ciel, manual, before Task 1 is merged): Revoke the leaked Langflow key

- [ ] **Step 1:** On the Langflow host: Langflow → Settings → API Keys. Delete the key whose prefix is `sk-Qcdm`. If it is the key the app uses (`LANGFLOW_API_KEY`), first follow the `LANGFLOW_API_KEY` row of the rotation table in `SECURITY.md` (create the new key, update `.env` and Streamlit Secrets, then delete the old one).
- [ ] **Step 2:** Run `python tools/check_gateway.py` on the host and send one message in the live app. Expected: all probes pass and Ciel answers.
- [ ] **Step 3:** Tell the implementer the revocation date, which goes into `SECURITY.md` in Task 1.

### Task 1: Redact the leaked key and fail CI on committed secrets

**Files:**
- Modify: `flow/v1.0.0/Ciel_AI_Long-Term_Memory_Master.json`, `flow/v1.1.0/Ciel_AI_Long-Term_Memory_Master.json` (one occurrence each, inside the Math Tutor tool's `code` value)
- Create: `tests/test_secrets.py`
- Modify: `.github/workflows/ci.yml` (add `tests.test_secrets` to the unittest list), `SECURITY.md`

**Interfaces:**
- Produces: `SECRET_PATTERNS: dict[str, re.Pattern]` and `find_secrets(text: str) -> list[str]` (returns the names of the patterns that match) in `tests/test_secrets.py`.

- [ ] **Step 1: Write the failing test `tests/test_secrets.py`**

`SECRET_PATTERNS` holds exactly these names and regexes:
- `langflow`: `sk-[A-Za-z0-9_-]{20,}`
- `jwt` (Supabase service and anon keys): `eyJhbGciOi[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.`
- `google_api`: `AIza[0-9A-Za-z_-]{35}`
- `google_oauth`: `GOCSPX-[A-Za-z0-9_-]{20,}`
- `github`: `gh[pousr]_[A-Za-z0-9]{36}`
- `midtrans`: `(?:SB-)?Mid-server-[A-Za-z0-9_-]{16,}`
- `private_key`: `-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----`

Tests:
- `test_tracked_files_have_no_secrets`: for every path from `git ls-files` (run with `subprocess` at the repo root) that decodes as UTF-8, `find_secrets` is empty; on failure the message lists `path: pattern names` only, never the match.
- `test_patterns_catch_known_secret_shapes`: for each pattern, a fixture built by concatenation (for example `"sk-" + "Ab3_" * 6`, and the same wrapped in JSON-escaped code `'API_KEY = \\"' + "sk-" + "Ab3_" * 6 + '\\"'`) gives a non-empty `find_secrets`.
- `test_placeholders_are_not_secrets`: `find_secrets` is empty for `"DEEPSEEK_API_KEY"`, `"sk-REVOKED"`, `'api_key = "your-langflow-key"'` and the full text of `.streamlit/secrets.toml.example`.

- [ ] **Step 2: Run `python -m unittest -v tests.test_secrets`.** Expected: `test_tracked_files_have_no_secrets` FAILS and names both flow files with `langflow`; the other two pass.

- [ ] **Step 3: Redact.** In both flow files, replace the key text with `sk-REVOKED` using a raw text replace (read the file, `str.replace`, write it back with the same encoding and newlines). Do not re-serialize the JSON: the files must change by exactly one line each. Check with `git diff --stat`: 2 files, 1 line each.

- [ ] **Step 4: Run `python -m unittest -v tests.test_secrets` and the full CI module list.** Expected: all pass, and the flow JSON validation step (`python -m json.tool` on both files) succeeds.

- [ ] **Step 5: Docs.** In the "Leaked or vulnerable code and secrets" row of `SECURITY.md`, add: "`tests/test_secrets.py` fails CI when a tracked file holds a key-shaped string (Langflow, Supabase JWT, Google, GitHub, Midtrans, private keys); it covers keys GitHub's scanner does not know." Under "Owner checklist", add: "Langflow key leaked in flow v1.0.0/v1.1.0, revoked <date from Task 0>."

- [ ] **Step 6: Commit**

```bash
git add tests/test_secrets.py flow/v1.0.0/Ciel_AI_Long-Term_Memory_Master.json flow/v1.1.0/Ciel_AI_Long-Term_Memory_Master.json .github/workflows/ci.yml SECURITY.md
git commit -m "Redact the leaked Langflow key and fail CI on committed secrets"
```

### Task 2: Lock dependencies with hashes

**Files:**
- Create: `requirements.in` (today's `requirements.txt` content, unchanged)
- Replace: `requirements.txt` (output of pip-compile)
- Create: `tests/test_supply_chain.py`
- Modify: `.github/workflows/ci.yml`, `SECURITY.md`

**Interfaces:**
- Produces: `tests/test_supply_chain.py` with `ROOT: Path` and `WORKFLOWS: list[Path]` (all of `.github/workflows/*.yml`), which Task 4 extends.

- [ ] **Step 1: Write the failing test** `test_requirements_are_locked_with_hashes` in `tests/test_supply_chain.py`. For every requirement entry in `requirements.txt` (join `\` continuations; skip comments and blank lines), the name is followed by `==<version>`, and at least one `--hash=sha256:` follows it. Also assert that `requirements.in` exists and contains `streamlit[auth]`.

- [ ] **Step 2: Run `python -m unittest -v tests.test_supply_chain`.** Expected: FAIL (no `==` and no hashes).

- [ ] **Step 3: Compile.** Ask Ciel for the Python version of the Streamlit Cloud app (Cloud → app → Settings → General). Then, in a venv with that Python: `pip install pip-tools`, and `pip-compile --generate-hashes --strip-extras --output-file requirements.txt requirements.in`. Keep the header pip-compile writes, because Dependabot uses it to recognise a pip-compile pair and update both files.

- [ ] **Step 4: Make CI install what production installs.** In `ci.yml`, set `python-version` in the Setup Python step to Cloud's version. Replace the "Install test dependencies" command with two calls: `python -m pip install --require-hashes -r requirements.txt`, then `python -m pip install chromadb` (test-only, so it stays out of the lock). Leave the `pip-audit -r requirements.txt` line as it is; it now audits the exact deployed versions. Add `tests.test_supply_chain` to the unittest list. If moving off Python 3.10 changes the Pillow advisory set, keep the ignore list identical; if the audit then fails on a Pillow ID that is not in the list, stop and report it to Ciel rather than adding it.

- [ ] **Step 5: Run the test and the full CI module list locally.** Expected: all pass.

- [ ] **Step 6: Docs.** In the `SECURITY.md` secrets row, add: "Dependencies are locked with hashes (`requirements.in` → `pip-compile --generate-hashes` → `requirements.txt`); a release swapped on PyPI fails the install instead of reaching production." Add a line to the `RELEASE_CHECKLIST.md` dependency section, if one exists, saying: edit `requirements.in`, then re-run pip-compile.

- [ ] **Step 7: Commit**

```bash
git add requirements.in requirements.txt tests/test_supply_chain.py .github/workflows/ci.yml SECURITY.md RELEASE_CHECKLIST.md
git commit -m "Lock dependencies with hashes and install the lock in CI"
```

- [ ] **Step 8 (Ciel, after merge):** Reboot the Cloud app and open it. If the deploy fails, revert this commit and reboot again. (An ImportError right after a deploy needs a reboot; see the redesign notes.)

### Task 3: Keep answers with links out of the shared cache

**Files:**
- Modify: `answer_cache.py` (`AnswerCache.put`, plus a new module-level regex)
- Test: `tests/test_answer_cache.py`
- Modify: `SECURITY.md`

**Interfaces:**
- Produces: `has_link(text: str) -> bool` in `answer_cache.py`. `AnswerCache.put(key, answer)` returns without storing (and without recording the first ask) when `has_link(answer)` is true.

- [ ] **Step 1: Write the failing tests** in a new `class SharedAnswerSafetyTest(unittest.TestCase)` in `tests/test_answer_cache.py`, each calling `put` twice with the same key, as the existing tests do:
  - `test_answers_with_links_are_not_cached`: each answer is 40+ characters and contains one of: `https://contoh.com/a`, `http://x.id`, `www.contoh.com`, `[klik](https://a.b)`, `buka masuk-akun-ciel.com sekarang`, `daftar di ciel-login.xyz`. After two `put` calls, `get(key)` is `None`.
  - `test_answers_without_links_are_still_cached`: answers containing `simpan sebagai data.csv`, `pakai Python 3.12`, `nilai 2.5 dan 3.75`, `file laporan.docx` and `contoh: a.b = c` (each 40+ characters). After two `put` calls, `get(key)` returns the answer.

- [ ] **Step 2: Run `python -m unittest -v tests.test_answer_cache`.** Expected: `test_answers_with_links_are_not_cached` FAILS; the rest pass.

- [ ] **Step 3: Implement `has_link`.** The regex matches, case-insensitively: a URL scheme (`https?://`), `www.`, or a domain-shaped token `\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|net|org|id|io|co|xyz|app|dev|link|site|me|info|ly|gl|top|click|online|shop)\b`. Call it in `put` next to the `MIN_ANSWER_CHARS` check. Comment, in the file's Indonesian style: a link in a shared answer could come from a prompt injection in a web page, and it would reach every user.

- [ ] **Step 4: Run `tests.test_answer_cache` and `tests.test_answer_cache_app`.** Expected: all pass.

- [ ] **Step 5: Docs.** In the `SECURITY.md` prompt-injection row, add: "The shared answer cache never stores an answer that contains a link, so an injected link cannot spread beyond one conversation."

- [ ] **Step 6: Commit**

```bash
git add answer_cache.py tests/test_answer_cache.py SECURITY.md
git commit -m "Keep answers with links out of the shared answer cache"
```

### Task 4: Guard the workflow rules with tests

**Files:**
- Modify: `.github/workflows/pages.yml` (the checkout step gets `with: persist-credentials: false`)
- Modify: `tests/test_supply_chain.py`

**Interfaces:**
- Consumes: `ROOT` and `WORKFLOWS` from Task 2.

- [ ] **Step 1: Write the failing tests** (plain text and regex; no YAML library):
  - `test_actions_are_pinned_to_commit_shas`: every `uses:` value matches `[\w.-]+/[\w./-]+@[0-9a-f]{40}`.
  - `test_checkouts_do_not_persist_credentials`: every `actions/checkout` step is followed, within its own step block, by `persist-credentials: false`.
  - `test_run_steps_do_not_interpolate_event_data`: no workflow contains `${{ github.event.` or `${{ github.head_ref`.
  - `test_workflows_declare_permissions`: every workflow has a top-level `permissions:` key, and none has `write-all` or `pull_request_target`.

- [ ] **Step 2: Run `python -m unittest -v tests.test_supply_chain`.** Expected: only `test_checkouts_do_not_persist_credentials` FAILS, on `pages.yml`.

- [ ] **Step 3: Add `persist-credentials: false` to the checkout in `pages.yml`.**

- [ ] **Step 4: Run the test module again.** Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/pages.yml tests/test_supply_chain.py
git commit -m "Stop persisting checkout credentials in the Pages workflow and test workflow rules"
```

### Task 5: Content-Security-Policy for the landing page

**Files:**
- Modify: `landing/index.html` (`<head>`, after the viewport meta)
- Test: `tests/test_landing.py`
- Modify: `SECURITY.md`

- [ ] **Step 1: Write the failing tests** in the existing landing test class:
  - `test_csp_hash_matches_inline_script`: the page has exactly one inline `<script>`. Its sha256 (base64 of the exact bytes between the tags) appears as `'sha256-…'` in the CSP meta's `script-src`.
  - `test_csp_is_strict`: the CSP meta `content` contains `default-src 'none'`, `base-uri 'none'`, `form-action 'none'`, `object-src 'none'`, and no `'unsafe-eval'` or `*`. The page also has `<meta name="referrer" content="strict-origin-when-cross-origin">`.

- [ ] **Step 2: Run `python -m unittest -v tests.test_landing`.** Expected: both new tests FAIL.

- [ ] **Step 3: Add the meta tags.** The policy is: `default-src 'none'; script-src 'sha256-<hash>'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self' data:; base-uri 'none'; form-action 'none'; object-src 'none'`. `'unsafe-inline'` for styles is needed for the page's `<style>` block and `style=` attributes; scripts stay hash-only. `frame-ancestors` is not allowed in a meta CSP, so leave it out.

- [ ] **Step 4: Run the test module, then open `landing/index.html` in the browser pane.** Expected: tests pass; fonts load, the intro curtain clears, and the console has no CSP violation.

- [ ] **Step 5: Docs.** Add a `SECURITY.md` row "Landing page": "Static page on GitHub Pages; a meta CSP allows only its own hashed script and Google Fonts."

- [ ] **Step 6: Commit**

```bash
git add landing/index.html tests/test_landing.py SECURITY.md
git commit -m "Add a Content-Security-Policy to the landing page"
```

### Task 6 (Ciel, manual, any time): Close the open owner items

- [ ] Rotate the ngrok Basic Auth password (still open since 2026-10-18; it has 24 characters and the runbook asks for 32+). Follow the `NGROK_PASSWORD` row in `SECURITY.md`.
- [ ] GitHub → Settings → Actions → General → Workflow permissions: "Read repository contents", and "Allow GitHub Actions to create and approve pull requests" off.
- [ ] Confirm two-factor authentication on every account in the owner checklist.
