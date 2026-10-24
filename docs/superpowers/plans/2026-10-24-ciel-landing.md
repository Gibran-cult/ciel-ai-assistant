# Ciel Landing Page (release 2 of 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A static landing page in `landing/index.html`, published with GitHub Pages, that introduces Ciel honestly and sends visitors to the Streamlit app.

**Architecture:** One self-contained HTML file (inline CSS and JS, Google Fonts only), transcribed from the artifact's "Landing page" artboard (`project/Main.dc.html`) with its template syntax replaced by plain HTML and a small script. `tests/test_landing.py` pins prices, links and claims; `.github/workflows/pages.yml` deploys the folder.

**Tech Stack:** HTML/CSS/vanilla JS, GitHub Actions (configure-pages, upload-pages-artifact, deploy-pages), Python unittest.

**Spec:** `docs/superpowers/specs/2026-10-20-ciel-redesign-design.md`, section 7, decisions 6, 7, 8, 10, 11 and appendix A.

## Global Constraints

- App URL: `https://ciel-ai-assistant-hywsyrnfpyhxc5e9pjgaho.streamlit.app/`. "Masuk"/"Masuk dengan Google" → `?page=login`; Pro card → `?page=pricing`; privacy → `?page=privacy`; "Buka aplikasi"/"coba tanpa masuk"/Gratis card → the bare URL.
- Prices and plan features come from `PLANS` in `pricing.py`: Gratis Rp0, Pro Rp79.000 per 30 hari. No per-hour numbers, no Tim plan.
- Only real answers from spec appendix A, dated "20 Oktober 2026". Fake-journal quotes are verbatim: "Aku nggak bisa meringkas jurnal itu, karena sejauh pencarianku, jurnal tersebut tidak ada." and "Mau aku lanjut cari penelitian asli yang paling dekat dengan topik ini?". Never the SmSA sentence or the two unverified "similar" papers.
- Every artboard claim the app does not back up is rewritten (decision 11). Illustrations that are not real runs carry the label "Contoh".
- No placeholders (`[EMAIL]`, `[@akun]`, `[Syarat ...]`) and no TikTok/Instagram/email until Ciel gives them.
- Scripts: none from a CDN. Stylesheets: Google Fonts only. `prefers-reduced-motion: reduce` stops the 3D logo, the curtain and the picker's auto-rotation.
- Casual Indonesian ("kamu"), no emoji, no English UI labels.
- Ciel reads the final copy and the local preview, and says "commit", before anything is committed. GitHub Pages is switched on only after PR Gibran-cult/ciel-ai-assistant#53 is live, and only after asking Ciel. No attribution lines.

## Claims rewritten from the artboard

| Artboard | Landing | Why |
|---|---|---|
| Hero picker: fake journal answered in a yellow box, "Riset Skripsi", "Oktober 2026" | Plain answer quoting the real refusal, "Chat", 0 sumber, "20 Oktober 2026" | The real test was a normal chat; yellow labels only exist in analysis mode |
| Vaswani/Koto "1 sumber ketemu", invented wording | Summaries of the real answers, "4 sumber", real URLs | Appendix A |
| "Gratis buat mahasiswa", "Rp0/bulan", "Gratis" fact | "Gratis untuk mulai", Gratis + Pro cards | Pro is on sale (decision 7) |
| "Kamu bisa lihat sumber mana yang lagi dibaca" with a live reading list | "Ciel nyari dan baca sumber dulu", status card like the app's real indicator | The app has no live list |
| "Kotak kuning muncul tiap ada bagian yang sumbernya belum ketemu", "ditandai kuning kalau nggak ada" | Yellow marks dugaan in mode analisis; elsewhere Ciel says it plainly | Labels come only from analysis mode |
| "Ingatan buat tiap proyek", "ingatan proyekmu", "Ciel ingat semuanya" | Memory belongs to the account, after signing in, viewable and deletable | Memory is per account |
| "Kenapa harus login Google?" | "Harus masuk pakai Google?" — no, guests can chat | Sign-in is optional |
| "Sekitar 2 menit" | "Chat biasa selesai di bawah semenit di uji kami; Riset Skripsi bisa beberapa menit" | Appendix A timings |

---

### Task 1: Landing content contract and page

**Files:**
- Create: `tests/test_landing.py`, `landing/index.html`
- Modify: `.github/workflows/ci.yml` (add `tests.test_landing`)

- [ ] **Step 1: Write the failing tests** — `test_prices_and_plans_match_pricing_py` (names, "Rp0", "Rp79.000", every Pro feature string from `PLANS`, no "Rp149.000"/"Tim"); `test_app_links_use_known_pages` (every href to the app is the bare URL or `?page=login|pricing|privacy`; every "Masuk" link is `?page=login`); `test_no_placeholders_or_contact_stubs`; `test_only_the_real_test_date`; `test_fake_journal_is_quoted_verbatim`; `test_rewritten_claims_are_gone` (the left column above, plus "SmSA", "Amini", "Nazariah"); `test_no_third_party_scripts_or_styles`; `test_reduced_motion_is_respected`.
- [ ] **Step 2: Run** `python -m unittest tests.test_landing` → FAIL (file missing).
- [ ] **Step 3: Build** `landing/index.html` from `Main.dc.html`: same sections, CSS and 3D logo; `sc-if`/`{{}}` replaced by `hidden` attributes and a script for the picker (auto-rotation every 6 s, stops once touched, while the drawer is open, when the tab is hidden, or under reduced motion), the tabs (real `role="tab"`/`aria-selected`/`aria-controls`) and the drawer (Escape closes it, focus returns to the burger). The pricing section is two cards.
- [ ] **Step 4: Run** `python -m unittest tests.test_landing` → PASS.

### Task 2: GitHub Pages workflow

**Files:**
- Create: `.github/workflows/pages.yml`
- Test: `tests/test_landing.py` (`test_pages_workflow_deploys_the_landing_folder`)

- [ ] **Step 1: Test** — on `push` to `main` with `paths: [landing/**]` plus `workflow_dispatch`; `permissions: pages: write, id-token: write, contents: read`; uploads `path: landing`; every `uses:` pinned to a 40-character SHA with a version comment (checkout v7.0.1 `3d3c42e5aac5ba805825da76410c181273ba90b1`, configure-pages v6.0.0 `45bfe0192ca1faeb007ade9deae92b16b8254a0d`, upload-pages-artifact v5.0.0 `fc324d3547104276b827a68afc52ff2a11cc49c9`, deploy-pages v5.0.1 `368f82528645a54fb793d4d04e342629a3f51346`).
- [ ] **Step 2: Run** → FAIL. **Step 3:** write the workflow. **Step 4: Run** → PASS.

### Task 3: Browser check, Ciel's review, commit, PR

- [ ] Serve `landing/` locally; check 1440/768/390 px, no horizontal scroll, reduced motion, keyboard (tabs, drawer, picker), contrast ≥ 4.5:1.
- [ ] Give Ciel the preview link and the copy table above; wait for "commit".
- [ ] Commit and open a PR stacked on `claude/ciel-design-53a998` (retarget to `main` once #53 merges).
- [ ] After #53 is live: ask Ciel, then enable Pages (source: GitHub Actions) and run the workflow.
