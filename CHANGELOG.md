# Ciel AI Master — Change Log

## Unreleased

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
- Production sub-flow change, made in Langflow on 2026-10-14 (sub-flows are not in this repo; backups in `~/.ciel_ai/flow_backups/subflow_*`): Agent `n_messages` in Web Research Assistant 100 -> 0 and in Math Tutor Agent 100 -> 4. The main Agent already sends sub-agents a complete question. Measured in one chat, the research sub-agent loaded 9,663 and 22,750 characters of unused history on the 2nd and 3rd research question, and 0 after the change. Answers kept their sources, and a math follow-up ("nilai di x = 2") was still answered correctly.

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

### Numbers from the user's own CSV/TSV files (flow v1.5.0)
- Problem: Verified Data Analyst always reads the built-in `200_sales_data` file, and the routing sent every "dataset / CSV" question to it. A question about a user's own CSV could be answered with numbers from the sample dataset, labeled as verified.
- New component **Ciel Table Analyst** (`flow/components/ciel_table_analyst.py`, tool `analyze_table`): describe, count, sum, mean, median, min, max, unique, top values, optionally per group, computed directly from the file without running model-written code. Number format is decided per column ("1.250.000" and "1.234,5" vs "1,234.5"), using Rupiah values or a ";" delimiter as hints for ambiguous values, and the result states how the column was read. Truncated files carry a warning.
- The app keeps attached CSV/TSV files (and project CSV/TSV files) per chat, so follow-up questions work without re-uploading, and sends them through tweaks as base64. Plain JSON did not survive: Langflow runs str inputs through `unescape_string`, which turns every backslash-n into a newline; the tool always answered "no file" in the first live test.
- The prompt now gets only a 20-row preview of each table instead of up to 60k characters, which also cuts tokens.
- Prompt v14.1 routes by data source: user files to Ciel Table Analyst, the built-in sales dataset to Verified Data Analyst, never mixed. Verified Data Analyst's tool description says the same.
- Tests: `tests/test_flow_v150_contract.py` covers the flow contract, the app wiring, number-format detection, the base64 path through a copy of Langflow's `unescape_string`, and the tool's answers on Indonesian-format data. The component was also run with Langflow's real `Component` class.
- Live check on a separate v1.5.0 test flow (production untouched): "total omzet per cabang" on a ";"-separated Rupiah CSV gave Medan 5.205.250 and Makassar 4.130.500, the follow-up "rata-rata unitnya" gave 41,2, both exact; "total Sales_Amount pada dataset" without a file still went to Verified Data Analyst (1.065.600,71).
- Quality run: response quality 8/9 in the collector run, then 9/9 in two reruns of `tests/test_response_quality.py` (26/27 overall). The collector does not record which case failed; the live test scripts send no `session_id`, so all cases share one Langflow session, which is the likely source of the flake. Median latency 18.9 s (v1.4.0: 16.2 s), P95 43.1 s (20.9 s), first request 50.6 s on a freshly imported flow.

### Fix: per-user memory isolation did not work (flow v1.4.1)
- Found in production after switching to v1.4.0: an anonymous visitor's "ingat namaku ..." was stored, and another session could read it.
- Root cause: the memory components' owner input was named `user_id`, but Langflow's `Component` already has a read-only `user_id` (the Langflow account that owns the flow). `self.user_id` returned that account id instead of the app's tweak, so every visitor shared one owner. The offline test missed it because its Langflow stub had no such attribute.
- The input is now `memory_owner` (components, flow snapshot `flow/v1.4.1`, and the app's tweaks). Chroma metadata still uses the `user_id` key, so `tools/migrate_memory_owner.py` is unchanged.
- `tests/test_flow_v141_contract.py`: the Langflow stub now keeps a read-only `user_id`, a regression test shows the v1.4.0 code storing under the Langflow account, and a check rejects component inputs that reuse Langflow attribute names. The behavior tests moved here from `tests/test_flow_v130_contract.py`, which now only checks the historical snapshot.
- Production flow updated in place to v1.4.1 (same `FLOW_ID`; backups in `~/.ciel_ai/flow_backups/`). Verified on the production flow: anonymous store and search are refused with the memory count unchanged; a test owner without memories gets "belum ada memory".
- Deploy this app version with the v1.4.1 flow. With v1.4.1 and an older app (which sends `user_id`), memory is off for everyone; nothing leaks.

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
