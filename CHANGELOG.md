# Ciel AI Master — Change Log

## Unreleased

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
