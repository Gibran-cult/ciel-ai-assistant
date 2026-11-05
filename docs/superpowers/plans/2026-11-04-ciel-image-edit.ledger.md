<!-- SDD ledger carried to the cloud session; delete this file before opening the PR. -->
# SDD ledger — plan: docs/superpowers/plans/2026-11-04-ciel-image-edit.md

Spec: no separate spec doc; the plan's "Decisions (spec)" section is the authority (Ciel's choices, 2026-11-04).
Branch: claude/ciel-image-edit-plan, branched from origin/main d84f3dd; plan committed cb1d5ea.

## Pre-flight scan

| Pair / task | Produces → consumes | Finding |
|---|---|---|
| T1 ↔ T3 | recipe op table → edit system prompt | Consistent: T3 says the prompt states the full T1 table. |
| T1 ↔ T5 | load_for_edit, validate_recipe, apply_recipe, preview, encode, EditError → dialog | Consistent. The uploader accepts jpg/jpeg/png/webp/gif; T1's error copy matches T5's. |
| T2 ↔ T6 | clean_svg, svg_png, IllustrationError → dialog | Consistent. T6 checks `TOLAK:` before clean_svg. |
| T3 ↔ T5/T6 | wire JSON + IMAGE_AI_UNAVAILABLE → ask_image_ai | Consistent. Failure travels as a Langflow 500 detail and is detected like MODEL_UNAVAILABLE. |
| T3 ↔ T4 | run endpoint only (image inside the run JSON) → gateway | Consistent: no upload path. |
| T5 ↔ T6 | image_ai_refusal, ask_image_ai, Beranda "ilustrasi" action → dialog | Consistent (same file app.py, T6 builds on T5). |
| T5 ↔ T7 | quota copy "3 per hari" | Consistent. |
| T7 ↔ T9 | LEGAL_VERSION date | See ruling R3. |
| T1 self | tests vs schema | Checked: rotate 45 dropped; brightness 9→2.5; crop clamp; text colour "red"→#e53935; size 5→0.2; 50 MP case < 90 MP cap; stage-order pixel test consistent. OK. |
| T2 self | tests vs allowlist | Checked: hostile needles do not occur in the cleaned GOOD svg; entity, 2001 elements, 5 MB, no-svg and empty all raise; sun pixel at (1360,220) for 800×600→1600×1200. OK. |
| T3 self | files created vs touched; Step 5 needs local Langflow + 2 real DeepSeek calls | See ruling R2. |
| T4 self | tests vs code | OK. |
| T5 self | "STOP before commit" vs SDD continuous run | See ruling R1. |
| T6 self | same as T5 | See ruling R1. |
| T7 self | LEGAL_VERSION = "release date" | See ruling R3. |
| T8 self | line to replace is "- Ciel belum bisa membuat ilustrasi atau mengedit foto. Katakan itu dengan jujur jika diminta." inside "PDF dan gambar:" block | Verified in v1.14.1 snapshot. OK. |
| T9 self | Steps 3–4 push/PR/rollout | See ruling R1. |

Ruling R1: Execution order 1,2,3,4,7,8,9(steps 1–2 only),5,6. Tasks 5 and 6 are implemented and reviewed with temporary LOCAL WIP commits (never pushed) so each has a review base; after the final whole-branch review those WIP commits are soft-reset so the UI work sits uncommitted for Ciel's browser check, and committed only after Ciel says "commit". Task 9 steps 3–4 (push, PR, production rollout) wait for Ciel. — Ciel's standing rule (memory ui-anti-slop-review-before-commit) and the plan's Global Constraints outrank SDD's continuous run; clustering the UI tasks last means one browser check instead of two interruptions. — If wrong: Ciel sees local WIP commits that were reset; nothing pushed, nothing lost.
Ruling R2: T3 Step 5 may build the node via local Langflow's custom_component API, create a TEMPORARY flow in local Langflow (127.0.0.1:7860) for the two real playground calls (1 edit + 1 illustration, ~2 DeepSeek calls), and must delete that flow afterwards. No production flow is touched. — The plan requires real replies in the PR; Ciel approved the same temp-flow pattern on 2026-11-04. — If wrong: one stray test flow / two tiny DeepSeek charges.
Ruling R3: T7 sets LEGAL_VERSION and the change note to "2026-11-04" (implementation date); RELEASE_CHECKLIST (T9) notes to bump it to the real rollout date if rollout is later. — The plan says "release date", unknown now. — If wrong: one constant to edit at rollout.

## Progress
Task 1: dispatched (BASE cb1d5ea, implementer a86b9195fe3823d70, sonnet)
Task 1: implementer DONE b3b3202; review dispatched (reviewer ae65cf8afa5219fd5)
Task 1: review — Spec ✅, quality Approved; 1 Important (no pixel tests for arrow/text/ellipse) → fix round 1 (also covers ⚠️ rotate/straighten/flip direction).
Task 1: minor (deferred): I;16/I 16-bit PNG turns near-white on convert (image_edit.py:96-98)
Task 1: minor (deferred): dead `except EditError: raise`; DecompressionBombError shows "Format ini belum bisa diedit"; non-JPEG 90-180MP decodes full size (image_edit.py:96-100)
Task 1: minor (deferred): straighten can exceed MAX_EDIT_PX (3846 px at 20° on 3000) (image_edit.py:461)
Task 1: minor (deferred): RGBA blur not premultiplied (image_edit.py:364-369)
Task 1: minor (deferred): OPS/_STAGE/_VALIDATORS parallel tables; _ANNOTATIONS includes blur (naming) (image_edit.py:65-73,260)
Task 1: minor (deferred): blanket except in validators has no logging (image_edit.py:283-306)
Task 1: minor (deferred): text without background offset by pad from `at` (image_edit.py:420)
Task 1: minor (deferred): load_default(size=) needs Pillow>=10.1 (fallback only) (image_edit.py:326)
Task 1: note for Task 3 prompt: resize also caps height at MAX_EDIT_PX, so result width can be smaller than requested.
Task 1: fix round 1/5 (2 addressed, 0 open; commits b3b3202..fcc6c12)
Task 1: minor (deferred): lambda in list comprehension at tests/test_image_edit.py:65-66 hard to read
Task 1: complete (commits cb1d5ea..fcc6c12, review clean)
Task 2: dispatched (BASE fcc6c12)
Task 2: implementer DONE_WITH_CONCERNS 5c116d0 — tests need `py -3.14` locally (fpdf2 2.9 not on 3.10); implementer pip-installed fpdf2 2.9.0, pypdfium2, matplotlib into the user's Python 3.14 (side effect outside worktree, same versions as requirements; tell Ciel). fpdf2 ignores <title> in PNG.
Ruling R4: Local test runs for modules needing fpdf2/pypdfium2 use `py -3.14`; CI (3.14, hash-locked requirements) is the authority. — fpdf2 2.9.0 cannot install on local 3.10. — If wrong: none; CI still gates.
Task 2: review — Spec ❌, Needs fixes: 4 Important (unbounded PNG height via viewBox; raw viewBox bypasses filter; nan/inf + RecursionError escape IllustrationError; missing hazard tests) → fix round 1
Task 2: minor (deferred): nested <svg> allowed with width/height (illustration.py:101)
Task 2: minor (deferred): removed child's tail text lost
Task 2: minor (deferred): leading "<svg" mention in prose breaks extraction; try each <svg start
Task 2: minor (deferred): fpdf2 ignores <title> in PNG
Task 2: fix round 1/5 (4 addressed, 0 open; commits 5c116d0..29f907e)
Task 2: minor (deferred): self-closing <svg/> fails extraction (fails closed)
Task 2: complete (commits fcc6c12..29f907e, review clean)
Task 3: dispatched (BASE 29f907e)
Task 3: stopped mid-run (user shut the laptop down); nothing committed, working tree clean, no temporary flow left in Langflow (checked). Re-dispatch Task 3 from BASE 29f907e.
Ruling R5: In the cloud, local Langflow (127.0.0.1:7860) is unreachable. Task 3 Step 5 (live run on a temp flow) and Task 8 Step 5 (flow test copy) are DEFERRED until Ciel's laptop is back; the offline tests are the gate. — The laptop is off. — If wrong: the live replies are added later; nothing ships before then anyway.
Ruling R6 (replaces the uncommitted part of R1): In the cloud, uncommitted work cannot come back to the laptop, so Tasks 5 and 6 are COMMITTED on this branch (subject prefix "UI (awaiting Ciel's browser check):") and pushed. No PR, no merge, and no rollout until Ciel has checked the UI in the browser and says "commit"/ok. — Uncommitted cloud work would be lost. — If wrong: Ciel asks for changes, which become fix commits on the same branch.
Ruling R4 note: tests needing fpdf2 2.9 / pypdfium2 need Python >= 3.11 with requirements.txt installed (CI uses 3.14).
Cloud session 2026-11-05: superpowers skills are not installed here, so tasks run inline (same TDD steps, self-review instead of subagent review). Venv: Python 3.13 + requirements.txt + chromadb. Baseline at 3e091a1: 4 errors, all pre-existing (test_ciel_master, test_response_quality need live config; test_chat_view quiz x2 fail on 3.13 AppTest).
Task 3: complete (commits 29f907e..56138f5, 48b8761 fake-key fix found by test_secrets). Step 5 deferred (R5).
Ruling R7: The flow snapshot is assembled by script from already-exported nodes (Penulis Chat Input/Output, Vision Router custom-node shape) because Langflow is unreachable. — Contract test pins code, edges, store flags, key variable. — If wrong: Langflow refuses the import on the laptop; re-export from Langflow and the contract test still applies.
Ruling R8: Snapshots use the REAL v1.14.1 bytes: indent=2, ensure_ascii=False, LF, no trailing newline. The plan's "CRLF" is wrong (v1.14.1 has 0 CR bytes; only LF round-trips). Applied to v1.14.2 and image_ai v1.0.0 (3b19ae6). — Byte check. — If wrong: one re-serialization.
Task 4: complete (d5d31f9). Ruling R9: IMAGE_FLOW_ID goes in deploy/vps/.env.example (gateway); AI_IMAGE_PER_DAY only in .streamlit/secrets.toml.example, because the VPS .env holds no app limits (KERANGKA_PER_DAY is not there either). — If wrong: one line.
Task 7: complete (0cdd5be, 4f82ce7). Ruling R10: landing/index.html also lists the two new plan lines, because tests/test_landing.py requires the landing to mirror pricing.PLANS. PRIVACY_UPDATED -> "4 November 2026" with the change note. — If wrong: revert two <li>.
Task 8: complete (11f3316). Step 5 deferred (R5).
Task 9 steps 1-2: complete (610b379). Full suite: same 4 pre-existing errors, no new ones.
Task 5: complete, committed as "UI (awaiting Ciel's browser check)" per R6 (2ce7243). Task 6: same (c1126f7).
Ruling R11: Edit gambar and Ilustrasi stay open through a session flag (edit_open / ilustrasi_open) cleared by on_dismiss, not the pop-once pattern of Riset/Kerangka. — AppTest reruns the whole script after every widget change, and a full-page rerun would otherwise close the dialog mid-edit. Checked in headless Chromium: X and Escape close it, and it does not come back on the next rerun. — If wrong: switch back to pop-once.
Ruling R12: The on-screen preview applies the recipe to preview(image) (900 px) without the resize op; "Unduh" builds the full-size result with a deferred callable (st.download_button data=callable), so nothing big is kept in session state. — The plan's apply-then-shrink would redo a 3000 px edit on every slider move. — If wrong: preview cost only.
Ruling R13: image_size_error() is split out of read_image() so chat attachments and Edit gambar share the 5 MB / 90 MP check (the plan's "reuse that size check"). tests/test_vision_images.py, test_ciel_pro.py and test_resilience.py load app pieces by name, so they got the new names.
Fix: Python write_text had turned app.py (CRLF) into LF; the two unpushed UI commits were rewritten with CRLF so their diffs are +408/+128 lines, not the whole file. Content identical (git diff --ignore-cr-at-eol is empty).
Browser (headless, no Pro, no flow): Edit gambar desktop+375 px, dark+light, 0 exceptions; download 'worksheet - edit.png' rotated correctly. Ilustrasi and the Pro AI part were NOT browser-checked (need a Pro account and the flow).
OPEN QUESTION for Ciel: the shared 5 MB limit refuses many 50 MP phone photos (often 8-15 MB) with "ukuran melebihi 5 MB". The plan says reuse the limit; Review Focus #1 expects 50 MP photos to open. Not changed; Ciel decides (e.g. a separate 20 MB limit for Edit gambar).
Final whole-branch review: done inline. Full suite = same 4 pre-existing errors as baseline.
