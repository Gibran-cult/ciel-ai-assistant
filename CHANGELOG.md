# Ciel AI Master — Change Log

## Unreleased

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
