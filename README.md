# Ciel AI Master

## Overview

Ciel is a research assistant and study companion built on Langflow. It answers in Indonesian, chooses its own tools (web research, a knowledge base, math, data analysis, long-term memory), and is designed not to make things up: sources come from tools, numbers are computed by tools, and it says so when it does not know.

The Streamlit app (`app.py`) is a thin public frontend; the Langflow flow, the local models and the memory database run on a separate host behind an ngrok tunnel.

## Features

- **Two persona modes:** warm and casual by default; a terse "Great Sage" analysis mode (conclusion, evidence labeled [Terverifikasi] or [Dugaan], confidence, limits) when the user asks for analysis.
- **Anti-fabrication rules:** research answers end with the sources the tools returned; no invented titles, DOIs or URLs; Indonesian number format without invented currencies.
- **Study companion:** step-by-step explanations, comprehension checks, practice questions.
- **Numbers from the user's own files:** attached CSV/TSV files are computed by Ciel Table Analyst (sum, mean, median, min, max, counts, per group) directly from the file.
- **Per-user long-term memory** with optional Google login; anonymous visitors get no memory.
- **Public-deployment safeguards:** one Langflow session per chat, hourly rate limits, no internal details in error messages (a Request ID instead).
- **Privacy:** a privacy page that follows the deployment's configuration, a "Data saya" panel where signed-in users view and delete their memories and delete their server-side chat history, and a 30-day retention script for server-side messages.
- **Photos** read by a local vision model, and **projects** with shared context files.
- **Testing:** offline CI suite, flow contract tests, and live quality collection with per-case session isolation.

## Architecture

```text
Streamlit app (app.py)  --ngrok-->  Langflow (host PC)
  session per chat                    Chat Input -> Ciel Vision Router -> Agent (DeepSeek)
  tweaks: memory owner,                 +-- Ciel Memory Search / Store  (Chroma + Ollama embeddings)
          user tables, images           +-- Ciel Table Analyst          (user CSV/TSV)
                                        +-- Math Tutor Agent            (Run Flow)
                                        +-- Verified Data Analyst       (Run Flow, built-in dataset)
                                        +-- Knowledge Retriever         (Run Flow)
                                        +-- Web Research Assistant      (Run Flow, Exa)
```

See `docs/ARCHITECTURE.md` for details, including the Langflow configuration that lives outside this repository.

## Long-Term Memory

Memories are stored in a local Chroma database on the Langflow host (`~/.ciel_ai/long_term_memory`) and are private to each signed-in account: the app sends a hashed account ID through tweaks, and the memory components only read and write that owner's memories. Memory search uses Top K = 5 and a compact agent-facing output (about 60.7% less context than v1.0.0).

## Privacy and Data Retention

The "Privasi" page (`privacy.py`) states what is processed and stored; its content follows `CHAT_RETENTION_DAYS`, Google login and `MEMORY_ADMIN_FLOW_ID`, so it only promises what the deployment does.

**Data saya** (signed-in users, needs `MEMORY_ADMIN_FLOW_ID`): list and delete one or all of their memories, and delete their chat history on the Langflow server. Memory actions run in a separate Ciel Memory Admin flow (`flow/components/ciel_memory_admin.py`), called only by the app and never available to the Agent; it acts only on the owner hash the app sends. Chat history is deleted by Langflow session, limited to sessions that start with the user's own key.

**Retention:** Langflow keeps every message until it is deleted. Run `tools/prune_chat_history.py` on the Langflow host to delete messages older than `CHAT_RETENTION_DAYS` (default 30). It reads `LANGFLOW_API_KEY` from the environment or `.env`; long-term memory is not touched.

```powershell
python tools/prune_chat_history.py --days 30 --dry-run
python tools/prune_chat_history.py --days 30
```

To run it daily with Windows Task Scheduler (adjust the paths to your checkout and Python):

```powershell
schtasks /Create /TN "Ciel prune chat history" /SC DAILY /ST 03:00 /TR "cmd /c cd /d C:\path\to\ciel-ai-assistant && python tools\prune_chat_history.py --days 30"
```

## Project Structure

```text
.
├── .github/workflows/ci.yml
├── .streamlit/                  theme and secrets template
├── flow/
│   ├── v1.0.0/ … v1.5.1/        main flow snapshots (latest: v1.5.1)
│   ├── memory_admin/            Ciel Memory Admin flow ("Data saya")
│   └── components/              custom component sources embedded in the flow
├── tests/                       offline tests, live quality scripts, results
├── tools/
│   ├── migrate_memory_owner.py  give pre-v1.3.0 memories an owner
│   └── prune_chat_history.py    delete server-side messages after the retention period
├── app.py                       Streamlit app
├── pricing.py                   pricing page
├── privacy.py                   privacy page
├── quality_dashboard.py
├── langflow_client.py           minimal command-line client
├── requirements.txt
├── CHANGELOG.md
├── RELEASE_CHECKLIST.md
└── README.md
```

## Requirements

Python and the dependencies in `requirements.txt` (`streamlit[auth]>=1.45`, `requests`, `python-dotenv`) for the app. The backend host needs Langflow 1.12.4, Ollama (`qwen2.5vl:3b` for images, `nomic-embed-text-v2-moe` for memory embeddings), Chroma, and ngrok.

## Environment Variables

Production credentials must not be committed to the repository.

```text
NGROK_URL
NGROK_USER
NGROK_PASSWORD
LANGFLOW_API_KEY
FLOW_ID
```

Do not place real credentials, passwords, API keys, or tokens in this README or source control.

Optional:

- `CHAT_INPUT_ID` (default `ChatInput-X8W7I`, the Chat Input in the flow) and `CONTACT_URL` (https:// or mailto: link shown on the pricing page for people interested in paid plans; paid plans cannot be bought yet, so their buttons stay disabled).
- `RATE_LIMIT_PER_HOUR` (default 20), `RATE_LIMIT_PER_HOUR_LOGIN` (default 60), `RATE_LIMIT_ANON_TOTAL_PER_HOUR` (default 150): hourly message limits, checked before any backend call.
- `[auth]` block (Google OAuth client): enables "Masuk dengan Google". Long-term memory is only available to signed-in users and is private to each account; without `[auth]` memory is disabled.
- `MEMORY_SEARCH_ID`, `MEMORY_STORE_ID` (defaults match `flow/v1.3.0` and later) and `TABLE_ANALYST_ID` (default matches `flow/v1.5.0` and later): component IDs the app sends tweaks to.
- `MEMORY_ADMIN_FLOW_ID` (and `MEMORY_ADMIN_NODE_ID`, default `CielMemoryAdmin-adm1n`): the Ciel Memory Admin flow behind the "Data saya" panel. Without it, signed-in users cannot view or delete their data from the app, and the privacy page says so.
- `CHAT_RETENTION_DAYS` (default 30): how long server-side chat history is kept, as stated on the privacy page. Use the same value for `tools/prune_chat_history.py`.

A template is provided in `.streamlit/secrets.toml.example`. For local runs copy it to `.streamlit/secrets.toml` (git-ignored) or use a `.env` file.

## Deployment (Streamlit Community Cloud)

1. Start the backend on the host machine: Langflow (port 7860) with its Ollama and Chroma dependencies, then the ngrok tunnel pointing at `localhost:7860` with the Basic Auth traffic policy.
2. Import `flow/v1.5.1/Ciel_AI_Long-Term_Memory_Master.json` (latest) into Langflow and set `FLOW_ID` to the imported flow. The flow calls four sub-flows by Run Flow (Math Tutor Agent, Verified Data Analyst, Knowledge Retriever, Web Research Assistant), which are not in this repository; see `docs/BACKUP_AND_DISASTER_RECOVERY.md`.
3. Deploy `app.py` from the `main` branch of this repository.
4. Paste the variables above into App settings -> Secrets, using the template format. For Google login, create an OAuth client (Web application) in Google Cloud Console with `https://<your-app>.streamlit.app/oauth2callback` as the redirect URI, and keep the `[auth]` block at the end of the secrets.
5. Open the app and send a test message. If the backend host or tunnel is down, the app shows an error card with a Request ID and a Retry button.
6. For "Data saya": import `flow/memory_admin/Ciel_Memory_Admin.json` into Langflow and set `MEMORY_ADMIN_FLOW_ID` to the imported flow. Schedule `tools/prune_chat_history.py` on the host (see Privacy and Data Retention).
7. Existing memories from flows before v1.3.0 have no owner. Sign in, copy "ID memory" from the sidebar memory panel, then on the Langflow host run `python tools/migrate_memory_owner.py --user-id <ID> --dry-run`, and again without `--dry-run`.

Later flow updates are applied in place on the existing flow (same `FLOW_ID`); see the flow deployment steps in `RELEASE_CHECKLIST.md`.

The deployed app is only available while the host machine, Langflow, and the ngrok tunnel are running.

### Hosting on a low budget

Streamlit Community Cloud (free) is a good fit for the frontend: the app is a thin client and the heavy work runs on the Langflow host. Apps sleep after 12 hours without traffic and have about 1 GB of memory.

The limiting part is the backend host and tunnel. ngrok's free plan is capped at roughly 20,000 HTTP requests and 1 GB of outbound data per month, which is enough for light use. If traffic grows, a Cloudflare Tunnel (free, no request quota) with an inexpensive domain is the next step. A cloud VPS with enough RAM/GPU for Ollama costs far more than the remaining main expense, DeepSeek tokens, which the rate limits keep in check.

## Local Development

```powershell
git clone https://github.com/Gibran-cult/ciel-ai-assistant
cd ciel-ai-assistant
python -m pip install -r requirements.txt
streamlit run app.py
```

Configure the variables above in `.streamlit/secrets.toml` or `.env` first.

## Testing

**Offline suite** (deterministic, no credentials; this is what CI runs):

```powershell
python -m unittest tests.test_memory_v110_contract tests.test_flow_v120_contract tests.test_flow_v130_contract tests.test_flow_v140_contract tests.test_flow_v141_contract tests.test_flow_v150_contract tests.test_flow_v151_contract tests.test_resilience tests.test_rate_limit tests.test_project_context tests.test_live_scripts tests.test_app_hygiene tests.test_performance_snapshot tests.test_pricing tests.test_privacy
```

It covers the flow snapshots (contract tests per version, including running the custom components against a real Chroma database with Langflow stubbed), the app's request and error handling, rate limiting, project context, table encoding, and code hygiene.

**Live quality collection** (calls the real backend; needs the variables above):

```powershell
python tests/collect_quality.py
```

It runs response quality, resilience, memory retrieval and performance checks and writes `tests/results/quality_latest.json`. Every live request uses its own Langflow session and the same tweaks as the app (`tests/live_session.py`), and failing cases are recorded with their reasons and an answer preview. `quality_dashboard.py` summarizes the result file.

## Versioning

Git tags mark releases; `flow/vX.Y.Z/` holds the main flow snapshot of each release that changed the flow.

```text
v1.0.0 — Production baseline
v1.1.0 — Memory context optimization
v1.2.0 — Vision router, pricing page, workspace UI
v1.3.0 — Public-ready isolation: session per chat, per-user memory, rate limits
v1.4.0 — Ciel identity: two persona modes, anti-fabrication, study companion
v1.4.1 — Fix per-user memory isolation (memory_owner)
v1.5.0 — Numbers from the user's own CSV/TSV files (Ciel Table Analyst)
v1.5.1 — Clean final answers, Indonesian number format, no repeated project files
v1.5.2 — Session-isolated live tests, safe error messages, cleanup, docs, Langflow operations
```

See `CHANGELOG.md` for details and measurements.

## Security

Sensitive configuration is kept outside source control: app secrets in Streamlit Secrets or `.env`, model and search API keys in Langflow global variables (no production flow stores a literal key).

Other measures: ngrok Basic Auth and a per-IP rate limit in the traffic policy, Langflow API key authentication, per-user memory isolation, hourly message limits in the app, and error messages that show users a Request ID instead of internal details (details go to the server log).

Never commit `.env`, `.streamlit/secrets.toml`, API keys, passwords, or tokens.

## Release Management

See `RELEASE_CHECKLIST.md` for the release workflow, including how flow changes are deployed to Langflow and rolled back.

## Current Status

Current release: `v1.5.2` (main flow `v1.5.1`).

Latest live quality run (2026-10-14, production flow through local Langflow): response quality 9/9, automated checks 5/5, status healthy, median latency 14.6 s, P95 16.7 s. Offline suite: 108 tests passing.
