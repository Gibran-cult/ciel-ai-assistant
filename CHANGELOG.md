# Ciel AI Master — Change Log

## Unreleased

### Personal datasets that grow over time (flow v1.7.0)
- Ciel can now learn from a user's own data over time, without keeping any model. Signed-in users ask Ciel to save a CSV/TSV ("simpan file ini ke datasetku") or to log rows from the chat ("catat: hari ini belajar 3 jam, nilai kuis 80"). The new tool Ciel Dataset Store (`manage_dataset`) grows one dataset per topic, and Table Analyst and ML Analyst read it by name, so statistics and models always use the whole history.
- Storage: `~/.ciel_ai/user_datasets/<owner>/<name>.csv` on the Langflow host. The owner comes from the app (same hash as long-term memory), never from the Agent. Anonymous visitors store nothing, and names cannot leave the owner's folder. Limits: 5 datasets, 10.000 rows and 1 MB each.
- Safety: Ciel saves only on an explicit request. Columns must match to append, the same file is not saved twice, and numbers are rewritten in the dataset's own format. The Agent cannot delete. "Data saya" now lists, downloads and deletes datasets through new Memory Admin actions.
- Privacy page (updated 16 Oktober 2026): describes personal datasets and the right to view, download and delete them, only when login is configured.
- Prompt v14.4 keeps every v14.3 line. Langflow ignores tweaks for fields a flow does not have (checked in `lfx/processing/process.py`), so the new app also works with the v1.6.0 flow.
- Tests (in CI): `tests/test_flow_v170_contract.py` and `tests/test_personal_datasets.py` cover the store, analysts on saved data, isolation between accounts, admin actions, app tweaks and the privacy text. The v1.5.0 and v1.6.0 snapshot tests became historical, as v1.3.0's did in v1.4.1.
- Live test (2026-10-16) through ngrok on a separate "(test)" flow with a fake test account; production untouched, test flows and test data deleted afterwards.
  - Day 1: a 30-row study log saved as dataset `belajar`, and a row typed in the chat appended with the right column names.
  - Later sessions without a file: the average came from all 31 rows; "apa yang paling memengaruhi nilai kuisku?" trained on the saved dataset (R² 0,94, study hours first).
  - Guards: a question about an attached file saved nothing; an anonymous save was refused; "hapus dataset belajarku" was sent to Data saya.
  - Admin actions on a temporary copy of the admin flow: list, download and delete work, another account's dataset is `not_found`, and the memory list still works.
- Fixed after the live run (prompt): the Agent listed datasets even when the user named one, and twice said a message "terkirim dua kali". The second came from Langflow showing the current message again in the chat history; it was stored once. Retest: named datasets go straight to the tool, and two rows logged in a row got no duplicate remark.
- Google login: `[auth]` and `MEMORY_ADMIN_FLOW_ID` were added to the deployed app's secrets on 2026-10-16, and sign-in works. The Google OAuth app was then published (Branding completed, status "In production"), so any Google account can sign in.
- Production (2026-10-16, after #23 was merged with CI green): the main flow was patched in place to v1.7.0 (same FLOW_ID), and the "Ciel Memory Admin" flow to the version with dataset actions (same ID). Before patching, both were checked against their previous repo versions (same nodes, values and edges), so no production-only change was overwritten. Backups: `~/.ciel_ai/flow_backups/prod_v1.6.0_before_v1.7.0_20261016_033534.json` and `admin_before_datasets_20261016_033534.json`. After the patch: 14 nodes including `CielDatasetStore-d4tA5`, prompt v14.4; the admin node has the `dataset_name` input.
- Verified through ngrok against production with a fake test account: a 30-row file saved as dataset `belajar`; "apa yang paling memengaruhi nilai kuisku?" trained on the saved dataset (study hours first, R² 0,94); an anonymous visitor's file question was answered without saving anything; the admin flow listed, exported and deleted the dataset, and the memory list still worked. The test data was deleted afterwards.
- Checked by the owner in a browser with a real signed-in account: the dataset part of "Data saya" works and looks right.

### Machine learning on the user's own files (flow v1.6.0)
- New tool Ciel ML Analyst (`flow/components/ciel_ml_analyst.py`, tool `train_model`) on the same CSV/TSV files the app already sends to Ciel Table Analyst. `task=predict` trains a linear regression (numeric target) or logistic regression (category target) and reports the strongest factors in the column's own units; `predict_for` predicts a new row. `task=cluster` groups similar rows with k-means, choosing the number of groups by silhouette unless the user gives it.
- Anti-fabrication for models: quality is measured with 5-fold cross-validation and compared with a simple baseline (mean or most common class). Weak models, near-perfect results (possible target leakage), small files, truncated or sampled files are flagged under "Catatan untuk jawaban", together with "hubungan statistik, bukan sebab-akibat".
- numpy only, fixed seed, no new dependency on the Langflow host (scikit-learn is not installed there). Row numbers and ID-like columns are skipped automatically.
- Prompt v14.3: routes prediction and grouping questions on user files to the tool, forbids derived target columns as features, requires the model quality in the answer, and lets the study-companion mode explain ML with the user's own data. Every v14.2 line is kept.
- App: sends the same encoded tables to `ML_ANALYST_ID` (default `CielMLAnalyst-m7Lq2`). Langflow ignores tweaks for node IDs that are not in the flow, so the new app also works with the v1.5.1 flow.
- Tests (in CI): `tests/test_flow_v160_contract.py` (node wiring, embedded code and hash, only the ML node, its edge and the prompt change from v1.5.1, prompt lines) and `tests/test_ml_analyst.py` (recovers known effects from synthetic data, beats the baseline, flags weak and leaky models, cluster recovery, determinism, input errors, Langflow string processing, file-reading helpers identical to Table Analyst). The helper check caught a lost non-breaking space in the first copy of `clean()`.
- Live test (2026-10-15) on a separate flow "Ciel AI Long-Term Memory Master v1.6.0 (test)" through ngrok, production flow untouched, with the app's payload (20-row preview + base64 tweaks): important factors, new-row prediction ("belajar 6 jam, kehadiran 90"), pass/fail classification, customer segments and a plain average per city. Each went to the right tool (the average stayed with analyze_table); the Agent left out the derived `lulus`/`nilai` columns by itself; the three planted customer segments were found (silhouette 0,70); tool numbers matched a local run exactly. 18–32 s per answer.
- Fixed after the live run: the Agent re-ranked factors by their "setiap +1" effects (hours against percentage points) and put a weaker factor first. Regression effects now also give the change for +1 standard deviation, and the tool says the order is already comparable and must be kept. Retest: correct order, standard-deviation figures quoted.
- Production (2026-10-16, after #21 was merged with CI green): the production flow was patched in place to v1.6.0, keeping the same FLOW_ID. Before patching, the production flow was checked against `flow/v1.6.0`'s base `flow/v1.5.1`: same nodes, values and edges, so no production-only change was overwritten. Backup: `~/.ciel_ai/flow_backups/prod_v1.5.1_before_v1.6.0_20261015_214444.json`. After the patch: 13 nodes including `CielMLAnalyst-m7Lq2`, prompt v14.3.
- Verified through ngrok against production: important factors (kept the tool's order, quoted the standard-deviation figures, left out `lulus`), customer segments (3 segments, silhouette 0,70), a plain average per city (still `analyze_table`), and a question without a file (answered without tools). 19–35 s per answer. The "(test)" flow was deleted afterwards.
- Not yet checked: a CSV upload through the deployed Streamlit app.

### Cleaner chat composer
- Focusing the message box drew a second, square box around the text inside the rounded composer: the app-wide `:focus-visible` outline also applied to the composer's textarea. The textarea's outline is now off; the composer's own border, which turns ink navy on focus, stays the single focus indicator. Checked in the browser.

### Running 24/7
- Problem: Ciel stopped answering when nobody was watching. Streamlit Community Cloud sleeps the app after 12 hours without visitors, and on the host only Ollama started by itself; Langflow Desktop and the ngrok tunnel were started by hand and stayed down after a crash or reboot.
- `.github/workflows/keep-awake.yml` + `tools/wake_streamlit.py`: every 4 hours a headless browser opens the app, presses the wake button if the app sleeps, and waits for the app to render (also inside Cloud's iframe). Needs the repository variable `STREAMLIT_APP_URL`; skips without it. A failed run emails the owner. Page load only: no ngrok requests or model tokens.
- `tools/ciel_watchdog.ps1`: checks Ollama, Langflow (`/health_check`) and the ngrok tunnel (agent API on 4040) and starts what is down, in that order. Desktop gets a 10-minute boot window, counted from when its processes started, before it is restarted. A stale ngrok agent is stopped first, since it holds the static domain. The tunnel only starts with the traffic policy file, and the script checks once that the public URL answers 401 without credentials, stopping the tunnel otherwise. Healthy runs send nothing through the tunnel, so the watchdog does not use ngrok's monthly request quota. `-Install` registers the Task Scheduler task "Ciel backend watchdog" (at logon + every 5 minutes, hidden with `conhost --headless`).
- `tests/test_keep_alive.py` (in CI): the wake script imports without Playwright and finds the app in any frame; the schedule stays well inside 12 hours; the URL comes from a variable via `env`; the watchdog never starts a tunnel without the policy and contains no tunnel URL or credentials.
- Checked: watchdog dry runs on the host (healthy in 1 s, wrong tunnel and missing policy detected, headless launch writes the log); wake script against the local app (awake, exit 0), a simulated sleeping page that loads the app in an iframe after the button (woken, exit 0) and an error page (exit 1).
- After deploying: the keep-awake workflow passed against the deployed app ("awake", 51 s). The first restart test failed: the running ngrok had been started from an administrator PowerShell window, so the task, which has no admin rights, could not stop it, and would have started a second agent that cannot bind the same static domain. The watchdog now logs that the agent cannot be stopped and starts nothing. With ngrok started by the task: from nothing in 13 s, after killing the agent in 11 s, Basic Auth active (401 without credentials, `/health_check` ok with them), and the next healthy run logs nothing.
- Langflow restart test, first try: after Desktop was closed, the watchdog reopened it but gave up after its 4-minute window; Desktop took about 5 minutes (2 min 40 s before it even launched the backend), and the next run would have killed it mid-boot. Also found: Desktop does not respawn a backend that died, so its window stays open with nothing behind it. The boot window is now 10 minutes counted from when Desktop's processes were created (so a later run does not restart a booting Desktop), and a Desktop open for 5 minutes without any backend process is restarted right away. Retest: Desktop closed, healthy again in 137 s; backend killed with Desktop left open, restarted at 312 s and healthy in 130 s; afterwards `/health_check` through the tunnel with credentials returned ok.

### Privacy page reviewed against UU 27/2022 (PDP)
- Review found the page silent on processing outside Indonesia and on children, the two high-priority gaps for a public study companion. Article references were checked against the law's text; this is a product checklist, not legal advice.
- Added: who runs Ciel (new `OPERATOR_NAME` config) and where to send requests (`CONTACT_URL`) (Pasal 5); purpose and basis (consent, withdrawable) (Pasal 20-21); third-party AI model and web search providers whose servers can be outside Indonesia, without brand names (Pasal 56); the full list of data-subject rights and that requests are recorded and answered (Pasal 6-14); users under 18 use Ciel with a parent or guardian's permission (Pasal 25); written notice within 3x24 hours if a data protection failure affects them (Pasal 46); changes announced on the page before they apply, with a "Terakhir diperbarui" date (Pasal 21 ayat 2).
- Before going public: set `OPERATOR_NAME` and `CONTACT_URL` in the deployment secrets, and have a procedure for the 3x24-hour breach notice the page now promises.
- `tests/test_privacy.py`: the page covers every checklist item, discloses third parties without brand names, and the app passes the operator name.

### Hide-on-scroll navbar works on Streamlit Cloud
- Problem: on the deployed app the top bar never slid away when scrolling down. The script bound its scroll listener to `section.stMain` once; when that element is replaced after the script ran (the Cloud app shell can remount it), the listener stays on the detached element. Reproduced locally by swapping the element: the bar stayed visible. Not a version issue: Streamlit 1.65 (what Cloud installs) has the same DOM and worked locally.
- The listener now sits on `document` in the capture phase and uses whichever element scrolls (ignoring the sidebar); the run-once guard moved to `window`. A container seen for the first time counts from the top, so the first scroll after load is not dropped (found while testing with a real mouse wheel).
- Checked on Streamlit 1.54 and 1.65: normal scrolling, after the scroll container is replaced, inside an iframe (as on Cloud), sidebar scrolling ignored, and real mouse-wheel scrolling. Not yet checked on the deployed app itself.

### Warm, minimal redesign and a sign-in page
- Anti "AI slop" pass after a design review (structure and copy, not colors):
  - Fonts: headings and labels inside markdown (plan names, prices, FAQ questions, sidebar labels) rendered in Streamlit's Source Sans instead of Geist, because only `p`/`li` were overridden; the markdown container now sets Geist. Weight 560 (not loaded) became 600. Pills and labels no longer use the monospace face; it stays for code, file names and sizes.
  - One tagline instead of three: the top bar and sidebar show only the wordmark. The home hero says "Kalau sumbernya tidak ada, Ciel bilang tidak tahu." and, instead of a four-item feature list, shows a sample analysis-mode answer in the flow's real format ("Analisis dimulai.", Kesimpulan, Dasar with [Terverifikasi]/[Dugaan] labels, Tingkat keyakinan, Batasan), marked as illustrative data. Starter prompts lost their arrow glyphs.
  - Pricing: no monthly/yearly toggle and no disabled "Segera hadir" buttons for plans that can't be bought. Gratis is the one plan card; Pro and Tim are listed under "Sedang disiapkan" with "Rencana Rp…/bulan". `plan_price`/`YEARLY_MONTHS_CHARGED` removed, `planned_price` added.
  - Sign-in page shows only working controls: no disabled email/password form (a note says it is coming), no Google button unless `[auth]` is configured, and "Lanjut tanpa masuk" becomes the primary action when it is the only one.
  - Privacy page, "Apa yang terjadi saat kamu mengirim pesan": dropped "(Langflow yang berjalan di komputer pengelola)" and the sentence naming DeepSeek and Exa as third-party processors, at the owner's request. The page now says messages go to Ciel's server and that photos and memory embeddings are processed on Ciel's own server.
  - Indonesian labels in the sidebar and error card ("Chat baru", "Proyek", "Riwayat", "Semua chat", "Hapus chat", "Coba lagi", "Detail teknis", badge "Gagal").
  - Errors: messages no longer start with an emoji and no longer tell public users to check ngrok or Langflow Desktop. What users read is a plain sentence with advice; HTTP status, Request ID and cause sit under "Detail teknis". A `CielError` (str subclass) now marks a failure instead of the leading emoji (`ERROR_MARKERS` removed).
  - Tests: every `ask_langflow`/`upload_images` failure is a `CielError` whose title and advice are ASCII and free of backend names; normal text starting with an emoji is not an error; pricing has a single button and no billing toggle; the sign-in page has no inputs or disabled buttons.
- New light palette "Kertas & Tinta": neutral paper canvas (`#f3f2ee`), off-white cards (`#fcfbf9`), warm ink-black text (`#1c1b19`) and warm greys, so the ink-navy accent (`#203a72`) is the only cool colour on screen and marks actions, the current page and verified claims; highlighter gold (`#f4dc6e`) marks guesses. It replaced a first pass ("Gading & Navy Tinta") whose cool navy-tinted greys clashed with its yellowish ivory canvas and made the accent blend into body text. The `--c-*` tokens in `CIEL_CSS` and `.streamlit/config.toml` match, so pricing, privacy and sign-in follow automatically. Fraunces (serif) for the wordmark and page titles; softer radii and light shadows on cards, the user bubble and the composer. Every text pair passes WCAG AA (body 15.4:1, faintest text 5.1:1, success/error 5.7–5.8:1), input borders 3.7:1.
- New sign-in page at `?page=login` (`login.py`), opened from "Masuk" in the sidebar (shown whenever the user is not signed in; it replaces the sidebar's direct "Masuk dengan Google" button). "Masuk dengan Google" calls the existing `st.login` and is disabled with an explanation when `[auth]` is not configured. Email and password sign-in is UI only: fields and button are disabled and marked "Segera hadir", since there is no account backend. Notes under the form follow the configured rate limits and login state; "Lanjut tanpa masuk" returns to chat, which still works without signing in.
- Navigation moved to the top bar: "Harga", "Privasi" (text links, the current page underlined) and "Masuk" (outline button) sit right of the wordmark in one flex row that stays on one line on phones, where the sidebar is collapsed. Signed in, "Masuk" becomes an account menu with the long-term memory status and ID, "Data saya" (moved unchanged) and "Keluar". The sidebar now holds only New chat, Projects, History and Clear chat; the "About long-term memory" text moved into the sign-in page notes. The main area's top padding clears Streamlit's header toolbar so it no longer covers the nav. The top bar is sticky (on Streamlit's layout wrapper, under a now-solid header), so the nav stays reachable on long pages, on desktop and phone. While scrolling it follows the page pixel for pixel (scrolling down pushes it up behind the header, scrolling up pulls it back); when scrolling stops it glides fully in or out by the last direction, so a small scroll up always brings it back. It always shows at the top and when the nav has keyboard focus. Nav links get an underline that grows from the centre on hover; the current page keeps an accent underline. This runs as a small script through `st.html(..., unsafe_allow_javascript=True)` (`NAV_SCROLL_JS`); the state lives on `<body>` so reruns don't reset it. `streamlit[auth]>=1.54`, the version this was tested on. Privacy page and README point to the account menu instead of the sidebar.
- `tests/test_login.py` (in CI): notes follow the configuration and never promise email sign-in, the page renders without the composer, every sign-in control is disabled without `[auth]`, and "Lanjut tanpa masuk" returns to chat; the nav is in the top bar and not the sidebar, "Masuk" opens the sign-in page, and a signed-in user (mocked `st.user` with `[auth]`) gets the account menu with memory status, "Data saya" and "Keluar". Checked in the browser at desktop and 375px (chat, pricing, privacy, sign-in); the signed-in menu was not checked with a real Google account.

### Privacy page, "Data saya" and chat retention
- Problem: users were not told what Ciel stores or sends to third parties, could not see or delete their long-term memories ("Memory belum dapat dilihat atau dihapus dari aplikasi"), and Langflow kept every message of every session indefinitely.
- New "Privasi" page (`privacy.py`, sidebar): what happens to a message (DeepSeek, Exa, local models), what is stored and for how long, how to control it, and what not to send. The content follows the configuration: retention days, whether login/memory is active, whether data controls are available, and `CONTACT_URL`.
- New "Data saya" panel for signed-in users: list memories, delete one, delete all (with a confirmation checkbox), and delete their own chat history on the Langflow server (with a confirmation checkbox). Chat history is deleted by Langflow session and only for sessions starting with the user's own key.
- Memory actions go to a separate flow with the new Ciel Memory Admin component (`flow/components/ciel_memory_admin.py`), set up with `MEMORY_ADMIN_FLOW_ID`. It is not an Agent tool, takes the owner only from the app's tweak, and only touches that owner's memories. Without `MEMORY_ADMIN_FLOW_ID` the panel says data controls are not active and the privacy page does not promise them.
- The admin flow is in `flow/memory_admin/Ciel_Memory_Admin.json` (Ciel Memory Admin -> Chat Output with "store messages" off). Created in Langflow as a new flow next to production. Live check through ngrok with throwaway owners: anonymous and unknown actions refused; list shows only the owner's memories; another owner's ID returns `not_found`; delete one and delete all remove only the owner's memories (collection size unchanged afterwards); the flow stores no messages; deleting chat history removed the user's two test sessions and kept another user's session.
- Retention: `tools/prune_chat_history.py` deletes Langflow messages older than `CHAT_RETENTION_DAYS` (default 30), with `--dry-run`; meant to run daily on the Langflow host (Task Scheduler example in README). Long-term memory is not affected.
- `tests/test_privacy.py` (in CI): the admin component against a real Chroma database (owner isolation for list, delete and delete all; anonymous and unknown actions refused; no reserved input names), the app's admin request and session filtering/batching, the privacy page content and rendering, and the retention script's timestamp parsing, paging, deletion and dry run.

### Pricing page matches what the app offers
- Problem: the pricing page sold Pro (Rp79.000/month) for long-term memory, photo attachments and projects, which every visitor already gets for free, and the free plan listed less than the app provides. Plans are not enforced and there is no payment system.
- The free plan now lists everything available (research with sources, math, CSV/TSV analysis, photos and text files, projects, session history), plus long-term memory "perlu login" when Google login is configured and the hourly message limits. Limits and login state come from `app.py` (`RATE_LIMIT_*`, `[auth]`), so the page follows the configuration.
- Pro and Tim are shown as plans: tag "Segera hadir", prices labeled "Rencana", buttons always disabled (also when `CONTACT_URL` is set). Pro no longer claims features the free plan has; it plans higher message limits. `CONTACT_URL` now adds a "Hubungi kami" link for people interested in paid plans.
- Header and FAQ describe the current state: Ciel is free with hourly limits; paid plans are not open; memory needs login (or is not active when login is not configured); why limits exist.
- `tests/test_pricing.py` checks that unavailable plans claim no free feature, only available plans are highlighted, paid buttons stay disabled with a contact URL, and the free plan and FAQ follow the limits and login state passed by the app. Checked in the browser.

## v1.5.2 — 2026-10-14

App hardening, tests, documentation and Langflow operations. The main flow is unchanged since v1.5.1 (`flow/v1.5.1`).

### Langflow configuration changes (made in Langflow; sub-flows are not in this repo)
- Sub-agent history: Agent `n_messages` in the Web Research Assistant sub-flow 100 -> 0, in Math Tutor Agent 100 -> 4. The main Agent already sends sub-agents a complete question. Measured in one chat, the research sub-agent loaded 9,663 and 22,750 characters of unused history on the 2nd and 3rd research question, and 0 after the change; answers kept their sources and a math follow-up was still answered correctly. The production flow's default session had accumulated ~490k characters of research history, which every live test run loaded.
- API keys: the literal DeepSeek `api_key` in the production sub-flows Verified Data Analyst (2 nodes) and Math Tutor Agent (1 node) now points at the global variable `DEEPSEEK_API_KEY`, the one the main flow and Web Research already use. No production flow stores a literal key anymore. Verified through ngrok.
- Old flows: the 22 flows not used by production (experiments, earlier versions, backups, test flows) moved to a new Langflow project "Arsip"; nothing was deleted. "Starter Project" holds only the 5 production flows. Archived flows still contain one DeepSeek key copied into 10 flows and one Google key; clean them before exporting or sharing an archived flow.
- Langflow API keys: deleted the 5 never-used "MCP Project Starter Project - langflow" keys; only the app's key remains. The key exposed in the public v1.0.0/v1.1.0 snapshots was already rejected (HTTP 403). No local MCP client referenced Langflow.
- DeepSeek temperature: not changed. `deepseek-flash` ignores it: at temperature 0 four runs gave four different answers, while an out-of-range value was rejected by DeepSeek itself, so the value is sent. This matches DeepSeek's documentation (temperature has no effect in thinking mode).
- Every in-place change has a backup in `~/.ciel_ai/flow_backups/` on the Langflow host.

### Documentation and release tags
- README, RELEASE_CHECKLIST, docs/OBSERVABILITY, docs/BACKUP_AND_DISASTER_RECOVERY, docs/ARCHITECTURE and docs/PRODUCTION_READINESS_REVIEW describe the current state instead of v1.1.0. BACKUP_AND_DISASTER_RECOVERY now covers the parts that are not in Git: sub-flows, Langflow global variables, the ngrok traffic policy, and the Chroma memory database.
- Release tags v1.2.0 to v1.5.2 point at the commits listed in RELEASE_CHECKLIST.md.

### Remove unused code
- Removed `check_backend_health` from `app.py` (117 lines). It was left behind when the backend status panel was removed and was never called. The `/health_check` endpoint itself is unchanged and is still used by `tests/test_ciel_master.py` and the recovery checks in `docs/`.
- `tests/test_app_hygiene.py` (in CI) fails when a top-level function or constant in `app.py` is never referenced; run against the previous `main` it flags exactly `check_backend_health`.
- Checked that `app.py` still renders with Streamlit's `AppTest` (no exceptions; chat input, sidebar and starter prompts present).

### Error messages no longer show internal details to users
- Three error paths showed raw technical text to public users: an unknown Langflow response shape printed the whole response JSON (flow structure, tool content), and other request errors and image-upload errors printed the raw exception, which can contain the ngrok host and URL.
- Users now get a short explanation and a Request ID (shown under "Technical details" in the existing error card). The response JSON (first 500 characters) and the exception type and text go to the server log under the same Request ID. The title lines are unchanged, so the error card and Retry work as before.
- Checked in the browser against a mock Langflow that returned an unexpected shape with a marker string: the card showed the explanation and Request ID, the marker was not on the page, and the server log had it under that Request ID.
- `tests/test_resilience.py`: unknown response shape, `InvalidURL` / `TooManyRedirects` / `ChunkedEncodingError` on requests, and upload errors must not show the host or raw JSON, must show a Request ID, and must log the detail.

### Quality run with isolated sessions, and two test fixes
- First full collector run with the session-isolated scripts (production flow v1.5.1 with the sub-agent `n_messages` change, through local Langflow): first request 50.6 -> 16.8 s, median 18.9 -> 15.5 s, P95 43.1 -> 29.8 s compared with the previous v1.5.0 run that used the shared default session. Response quality 8/9; the collector named the failing case for the first time: `research_machine_learning_01`, "Tidak menemukan: 'machine'". Two reruns of that question answered about machine learning with dates and sources and contained the term. `tests/results/quality_latest.json` holds this run, labeled v1.5.1.
- `research_machine_learning_01` now accepts "machine" or "pembelajaran mesin" (`expected_any`): an Indonesian answer may use the Indonesian term. A test checks that an unrelated answer still fails.
- Failed cases keep the answer: `test_response_quality.py` prints a 1,200-character preview for failed cases (160 for passed ones), and `collect_quality.py` stores it as `failed_cases[].answer_preview` and prints its start. The failing answer of the run above was not recorded because this did not exist yet.
- Live run with these fixes (same setup): response quality 9/9, automated checks 5/5, status healthy, memory recall K=5 100%; first request 17.4 s, median 14.6 s, P95 16.7 s. `tests/results/quality_latest.json` holds this run.

### Live test scripts: one session per request, app tweaks, user-visible answer
- Problem: `tests/test_response_quality.py`, `tests/test_performance_snapshot.py` and `tests/test_ciel_master.py` sent no `session_id`, so every live test used the production flow's default Langflow session. Its research sub-agent history had grown to ~490k characters (until the sub-agent's `n_messages` was lowered on 2026-10-14), test cases influenced each other, and a 9/9 suite flaked to 8/9. The scripts also judged `data.text`, which in Langflow 1.12 joins every Agent round, so duplicated text was evaluated instead of the answer users see.
- New `tests/live_session.py`, used by all three scripts: a fresh `session_id` per request (`livetest-<label>-<id>`), the tweaks the app sends for an anonymous visitor (memory off, no tables), and `answer_from()`, which runs `app.final_answer_text` loaded from `app.py`, so tests and app share one implementation.
- `tests/collect_quality.py` records failing response-quality cases with their reasons (`response_quality.failed_cases`) and prints them, so a degraded run says which case failed.
- `tests/test_live_scripts.py` (offline, in CI) checks that every run payload in the live scripts has `session_id` and `tweaks`, that none reads `["data"]["text"]` directly, that two cases get two sessions and the vision case keeps its image tweak, and the failed-case parser.

## v1.5.1 — 2026-10-14

### Project files are no longer resent with every message
- Problem: project file text (up to 150k characters) was added to every message in a project chat. Langflow stores each message with that text and the Agent loads the last 10 messages, so from the 3rd turn the same file reached the model several times in one request (up to 6 copies).
- The app now sends project file text only for a new chat, when the project files change (`project_signature`), or every `PROJECT_CONTEXT_REFRESH_TURNS = 4` turns, before the last copy leaves the Agent's 10-message window. Other turns name the files ("isinya sudah dikirim di pesan sebelumnya") so the Agent uses the copy in its history. The record is kept per chat and updated only after a successful answer.
- Budgets: `MAX_CONTEXT_CHARS` 150,000 -> 80,000 and `MAX_FILE_CHARS` 60,000 -> 40,000 per text file, so the at most two copies in a request stay modest. CSV/TSV files are unaffected (preview in the prompt, full file to Ciel Table Analyst).
- Simulation with the app's own functions (60k-character project file, 10 turns, 1.5k-character answers): peak context per request 368k -> 88k characters, total over 10 turns 2.76M -> 0.62M (-78%), copies of the file per request at most 2 instead of 6. `tests/test_project_context.py` keeps that bound over 12 turns and checks that the file is always visible to the Agent.
- Live on the test flow: after sending a proposal once, turns 2-4 sent about 200 characters instead of 1,400, and the Agent answered three detail questions from it correctly (supervisor, a budget line, risk and harvest week).

### Fix: duplicated answers and English-format numbers (flow v1.5.1)
- **Duplicated or glued answers.** In Langflow 1.12.4 `Message.text` (and `data.text`) joins every text block of every Agent round: text written before a tool call, an answer the model wrote twice, and internal narration. Users saw answers twice ("…23,685 … 23,69.Rata-rata Quantity_Sold…"), text glued without a space ("…filenya ya.Ini hasilnya"), and on research questions the agent's narration ("Saya akan mencari… Pertama, mari cek tanggal…"). `ask_langflow` now returns the last text block the model wrote (`final_answer_text`), skipping Langflow's own "Output" blocks, and falls back to `data.text` when there are no content blocks.
  - Checked on real responses (greeting, math, research, CSV): the new answer is always the end of the old text, so nothing from the final answer is lost. Research 7,600 -> 2,186 chars with the "Sumber:" list intact; math 1,296 -> 519 (the sub-agent's full explanation no longer repeats the final one).
  - `tests/assets/langflow_agent_message.json` is a trimmed real Langflow message used by `tests/test_resilience.py`.
- **Number format.** Verified Data Analyst and other tools write English-format numbers ("23.685" = 23,685), which read as thousands in Indonesian. Prompt v14.2 (flow `v1.5.1`, prompt-only change) tells the Agent to write Indonesian format (1.065.600,71; 23,685), convert tool output, not mix formats, and not add a currency the data does not state (it had written "Rp 1.065.600,71" for the unit-less Sales_Amount). Live on the test flow: 4/4 answers in Indonesian format, 3/3 without an invented currency.

## v1.5.0 — 2026-10-14

### Numbers from the user's own CSV/TSV files (flow v1.5.0)
- Problem: Verified Data Analyst always reads the built-in `200_sales_data` file, and the routing sent every "dataset / CSV" question to it. A question about a user's own CSV could be answered with numbers from the sample dataset, labeled as verified.
- New component **Ciel Table Analyst** (`flow/components/ciel_table_analyst.py`, tool `analyze_table`): describe, count, sum, mean, median, min, max, unique, top values, optionally per group, computed directly from the file without running model-written code. Number format is decided per column ("1.250.000" and "1.234,5" vs "1,234.5"), using Rupiah values or a ";" delimiter as hints for ambiguous values, and the result states how the column was read. Truncated files carry a warning.
- The app keeps attached CSV/TSV files (and project CSV/TSV files) per chat, so follow-up questions work without re-uploading, and sends them through tweaks as base64. Plain JSON did not survive: Langflow runs str inputs through `unescape_string`, which turns every backslash-n into a newline; the tool always answered "no file" in the first live test.
- The prompt now gets only a 20-row preview of each table instead of up to 60k characters, which also cuts tokens.
- Prompt v14.1 routes by data source: user files to Ciel Table Analyst, the built-in sales dataset to Verified Data Analyst, never mixed. Verified Data Analyst's tool description says the same.
- Tests: `tests/test_flow_v150_contract.py` covers the flow contract, the app wiring, number-format detection, the base64 path through a copy of Langflow's `unescape_string`, and the tool's answers on Indonesian-format data. The component was also run with Langflow's real `Component` class.
- Live check on a separate v1.5.0 test flow (production untouched): "total omzet per cabang" on a ";"-separated Rupiah CSV gave Medan 5.205.250 and Makassar 4.130.500, the follow-up "rata-rata unitnya" gave 41,2, both exact; "total Sales_Amount pada dataset" without a file still went to Verified Data Analyst (1.065.600,71).
- Quality run: response quality 8/9 in the collector run, then 9/9 in two reruns of `tests/test_response_quality.py` (26/27 overall). The collector does not record which case failed; the live test scripts send no `session_id`, so all cases share one Langflow session, which is the likely source of the flake. Median latency 18.9 s (v1.4.0: 16.2 s), P95 43.1 s (20.9 s), first request 50.6 s on a freshly imported flow.

## v1.4.1 — 2026-10-14

### Fix: per-user memory isolation did not work (flow v1.4.1)
- Found in production after switching to v1.4.0: an anonymous visitor's "ingat namaku ..." was stored, and another session could read it.
- Root cause: the memory components' owner input was named `user_id`, but Langflow's `Component` already has a read-only `user_id` (the Langflow account that owns the flow). `self.user_id` returned that account id instead of the app's tweak, so every visitor shared one owner. The offline test missed it because its Langflow stub had no such attribute.
- The input is now `memory_owner` (components, flow snapshot `flow/v1.4.1`, and the app's tweaks). Chroma metadata still uses the `user_id` key, so `tools/migrate_memory_owner.py` is unchanged.
- `tests/test_flow_v141_contract.py`: the Langflow stub now keeps a read-only `user_id`, a regression test shows the v1.4.0 code storing under the Langflow account, and a check rejects component inputs that reuse Langflow attribute names. The behavior tests moved here from `tests/test_flow_v130_contract.py`, which now only checks the historical snapshot.
- Production flow updated in place to v1.4.1 (same `FLOW_ID`; backups in `~/.ciel_ai/flow_backups/`). Verified on the production flow: anonymous store and search are refused with the memory count unchanged; a test owner without memories gets "belum ada memory".
- Deploy this app version with the v1.4.1 flow. With v1.4.1 and an older app (which sends `user_id`), memory is off for everyone; nothing leaks.

## v1.4.0 — 2026-10-14

### Ciel identity: anti-fabrication research + study companion (flow v1.4.0)
- New flow snapshot `flow/v1.4.0`: identical to v1.3.0 except the Agent system prompt (v14.0, 8.7k -> 13.4k chars; DeepSeek caches the unchanged prefix).
- **Two persona modes.** Default is warm and casual ("aku"/"kamu"). When the user explicitly asks for analysis ("analisis", "bedah", "kaji", ...), Ciel switches to a terse "Great Sage" style that opens with "Analisis dimulai." and answers as Kesimpulan / Dasar (each point labeled [Terverifikasi] or [Dugaan]) / Tingkat keyakinan / Batasan.
- **Anti-ngarang rules** for every mode: never invent titles, authors, DOIs, URLs or quotes; research answers end with a "Sumber:" list of sources the tools actually returned; non-trivial numbers go through Math Tutor or Verified Data Analyst; no fabricated bibliographies for theses (point to Google Scholar, Garuda, SINTA instead).
- **Study companion:** step-by-step explanations with a short comprehension check or practice offer; practice questions are given without answers first; learning topics and recurring mistakes may be stored in (per-user) long-term memory.
- App copy (tagline, empty state, capabilities, starter prompts, working indicator) now presents this identity, including an example "Analisis: ..." prompt.
- `tests/test_flow_v140_contract.py` checks that only the system prompt changed and that the earlier rules are kept.
- Live validation (2026-10-14, v1.4.0 imported as a separate test flow in local Langflow 1.12.4, production flow untouched, requests sent to `127.0.0.1:7860` instead of through ngrok):
  - `tests/collect_quality.py`: 5/5 automated checks, response quality 9/9, memory recall K=5 100%. Median latency 36.2 s -> 16.2 s, P95 51.1 s -> 20.9 s versus the v1.1.0 baseline. Most of the gain likely comes from v1.2.0 no longer sending every message through the vision model; the baseline may also have gone through ngrok, so the numbers are not a strict A/B.
  - Style check: "halo" -> casual mode; "analisis kelebihan RAG" -> Great Sage structure with every point labeled [Dugaan] because no sources were fetched; "ajari aku turunan" -> step-by-step explanation ending with a comprehension question.
  - The first analysis answer had 9 points and a casual closing offer, so the prompt now limits Dasar to 5 points and ends at Batasan. Re-run: 5 points, 52 s -> 37 s.

## v1.3.0 — 2026-10-14

### Public-ready isolation and cost control (flow v1.3.0)
- **Conversation isolation.** `ask_langflow` now sends a `session_id` (`<user>-<chat id>`). Before, every request used Langflow's default session, so the Agent's last 10 messages (`n_messages`) were shared by all visitors and "New chat" did not reset the Agent's context. Each chat now has its own history, which also keeps prompts shorter.
- **Per-user long-term memory.** New flow snapshot `flow/v1.3.0`: Ciel Memory Search/Store (sources in `flow/components/ciel_memory_search.py` and `ciel_memory_store.py`) take a `user_id` input that the app sets through `tweaks`. It is not a tool argument, so the Agent cannot choose it. Store tags each memory with `user_id`; Search filters on it and skips the embedding call when the user has no memories. Empty `user_id` (anonymous visitor) disables memory: nothing is stored or read.
- **Optional Google login** (`st.login`, configured by an `[auth]` block in secrets). Signed-in users get memory keyed by a hash of their account; without `[auth]` the app runs anonymously with memory off. `requirements.txt` now needs `streamlit[auth]>=1.45`.
- **Rate limit** before any backend call: `RATE_LIMIT_PER_HOUR` (anonymous, default 20), `RATE_LIMIT_PER_HOUR_LOGIN` (default 60), and a shared `RATE_LIMIT_ANON_TOTAL_PER_HOUR` (default 150) so reloading the page does not reset the anonymous budget. Over the limit, the existing error card is shown.
- **Lower Streamlit memory use.** After a successful answer, attached photos in chat history are replaced by ~360 px JPEG thumbnails and the file-context payload is dropped. Originals are kept only while Retry may need them.
- Memory Store no longer returns the memory ID, total count, or DB path to the Agent. Removed the unconnected `Research Agent API Tool` node.
- `tools/migrate_memory_owner.py` assigns memories saved by older flows to one account (`--dry-run` first).
- New offline tests: `tests/test_flow_v130_contract.py` (contract plus a real Chroma isolation test with Langflow stubbed) and `tests/test_rate_limit.py`; `tests/test_resilience.py` checks `session_id`/`tweaks` in the payload. CI runs them.
- Upgrade: import `flow/v1.3.0` into Langflow, update `FLOW_ID` if the import created a new flow, then deploy the app. The app's tweaks need the v1.3.0 memory components; with an older flow, memory stays shared.
- Not changed: DeepSeek temperature (still 1). Lowering it for more consistent tool routing should be decided with `tests/collect_quality.py` against the live backend.

## v1.2.0 — 2026-10-14

### Pricing page
- Added a pricing page (`?page=pricing`, sidebar item "Harga & paket") with Gratis, Pro, and Tim plans, a monthly/yearly toggle (yearly = 10 months), and an FAQ.
- Plan data, Rupiah formatting, and rendering live in `pricing.py`; `app.py` only adds routing and the sidebar item.
- New optional config `CONTACT_URL` (https:// or mailto:). Paid plan buttons link there; without it they render as disabled "Segera hadir". There is no payment integration or plan enforcement yet.
- Added `tests/test_pricing.py` (formatting, yearly math, URL allow-list, render) to the offline CI suite; CI now installs `streamlit`.

### Fix: image messages failing with "Backend mengalami internal error"
- Root cause: the Ollama vision preprocessor (`qwen2.5vl:3b`, 4096-token context) sat between Chat Input and Agent and received the full message, including project-file context. Messages over ~4096 tokens failed with HTTP 500 (`request (5203 tokens) exceeds the available context size`). The Agent also only ever saw the vision model's output, never the original question or file context.
- Replaced it with `Ciel Vision Router` (`flow/components/ciel_vision_router.py`): text-only messages pass straight to the Agent without calling the vision model; with images, the vision model gets only the images plus a short instruction, and its reading is appended to the original message. If the vision model fails, the Agent still answers and says the image could not be read.
- Measured locally: image + 20k-char project context 500 -> 200 (39 s); image only ~90 s -> 28 s; text only unchanged.
- New flow snapshot `flow/v1.2.0` (hardcoded API key in the Math Tutor API Tool code redacted) with an offline contract test.
- `ask_langflow` now logs the Langflow error body (first 500 chars) on HTTP errors so failures can be diagnosed from server logs. The user-facing message is unchanged.

### Security: remove hardcoded Langflow API key from the Math Tutor tool
- The "Math Tutor API Tool" custom component called this same Langflow over HTTP with an API key written in its code; that key is in the public `flow/v1.0.0` and `flow/v1.1.0` snapshots. It is replaced by a native Run Flow tool (`Math-Tutor-Agent_tool`) that runs the Math Tutor Agent flow in-process, so no key is needed. Verified: derivative question routed to Math Tutor and answered correctly.
- `ask_langflow` request timeout raised from 120 s to 240 s: image messages that call several tools took up to ~107 s locally, too close to the old limit once ngrok latency is added.

### UI
- Polished the Streamlit workspace UI: dark theme with teal accent, responsive layout, empty state, working indicator, error card with technical details and retry, informative long-term memory panel.
- Sidebar now has New chat, chat History, and Projects; Connection, Configuration, and backend status panels were removed.
- Added Add files: text files can be attached in the composer or stored as project files, and are inserted into the prompt as context. `ask_langflow` is unchanged.
- Chat history and projects live in the browser session only (not persisted).
- Added photo attachments (png, jpg, jpeg, bmp): images are uploaded to Langflow (`/api/v1/files/upload/{flow_id}`) and passed to the Chat Input component through `tweaks`. `ask_langflow` only gained an optional `tweaks` argument.
- New optional config `CHAT_INPUT_ID` (default `ChatInput-X8W7I`, the Chat Input ID in the v1.1.0 flow).
- Visual refresh: flat neutral ink palette without glow, 6-12 px radii, Geist font (loaded from Google Fonts, falls back to system fonts), plain-text hero and spec-style capability list, caret working indicator, letter avatars. WCAG AA contrast checked for text and form-control borders.
- Added `.streamlit/config.toml` theme; `requirements.txt` now requires `streamlit>=1.43` (container keys, button icons, chat input file attachments).
- No changes to `ask_langflow`, `check_backend_health`, flow, memory, or tests.

### CI / Automation
- Added GitHub Actions CI workflow.
- Added automated flow JSON validation.
- Added automated offline test execution.
- Added CI dependency installation for `requests` and `chromadb`.
- Scoped CI to deterministic offline tests that do not require production credentials.

## v1.1.0 — Memory Context Optimization

### Changes
- Optimized Ciel Memory Search output for lower agent context usage.
- Kept Memory Search Top K at 5.
- Removed query, distance, and metadata from the agent-facing memory output.
- Preserved retrieved memory contents and ranking order.

### Validation
- Memory contract tests: 6/6 PASS.
- Full local unittest discovery: 16/16 PASS.
- Multi-query recall benchmark: 100% recall at Top K = 5.
- Context reduction: approximately 60.7% at Top K = 5.
- No changes were made to the v1.0.0 baseline snapshot.

## v1.0.0 — Production Baseline

### Flow Snapshot
- Baseline snapshot stored at:
  `flow/v1.0.0/Ciel_AI_Long-Term_Memory_Master.json`
- Snapshot is tracked in the current main repository history.
- No production-flow changes were introduced by the versioning step.

### Git History Note
- Tag `v1.0.0` is preserved as the production baseline.
- The current flow snapshots are maintained in the current main repository lineage.
- Previous repository history is intentionally preserved rather than force-merged.
