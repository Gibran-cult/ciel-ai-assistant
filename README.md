# Ciel AI Master

## Overview

Ciel is a research assistant and study companion built on Langflow. It answers in Indonesian, chooses its own tools (web research, a knowledge base, math, data analysis, long-term memory), and is designed not to make things up: sources come from tools, numbers are computed by tools, and it says so when it does not know.

The Streamlit app (`app.py`) is a thin public frontend; the Langflow flow, the local models and the memory database run on a separate host behind an ngrok tunnel.

## Features

- **Two persona modes:** warm and casual by default; a terse "Great Sage" analysis mode (conclusion, evidence labeled [Terverifikasi] or [Dugaan], confidence, limits) when the user asks for analysis.
- **Anti-fabrication rules:** research answers end with the sources the tools returned; no invented titles, DOIs or URLs; Indonesian number format without invented currencies.
- **Study companion:** step-by-step explanations, comprehension checks, practice questions.
- **Numbers from the user's own files:** attached CSV/TSV files are computed by Ciel Table Analyst (sum, mean, median, min, max, counts, per group) directly from the file.
- **Machine learning on the user's own files:** Ciel ML Analyst trains a model on an attached CSV/TSV to predict a column (linear or logistic regression), rank the factors that matter, predict a new row, or group similar rows (k-means). Quality is measured with 5-fold cross-validation against a simple baseline, and weak or suspiciously perfect models are flagged.
- **Personal datasets (signed-in users):** Ciel Dataset Store saves data the user asks it to keep, from a file or typed in the chat ("catat: hari ini belajar 3 jam, nilai kuis 80"), and grows it over time. Table Analyst and ML Analyst read saved datasets by name, so statistics and models use the whole history. Users list, download and delete them under "Data saya"; the Agent cannot delete.
- **Per-user long-term memory** with optional Google login; anonymous visitors get no memory.
- **Public-deployment safeguards:** one Langflow session per chat, hourly rate limits, no internal details in error messages (a Request ID instead).
- **Privacy:** a privacy page that follows the deployment's configuration, a "Data saya" panel where signed-in users view and delete their memories and delete their server-side chat history, and a 30-day retention script for server-side messages.
- **Photos** read by a local vision model, and **projects** with shared context files.
- **PDF attachments** (chat and projects): the app extracts the text with `pypdf` before sending it, like any text file (no OCR, so scanned PDFs are refused with a hint to send them as photos; password-protected PDFs are refused; extraction stops at the per-file character limit or 100 pages).
- **Testing:** offline CI suite, flow contract tests, and live quality collection with per-case session isolation.

## Architecture

```text
Streamlit app (app.py)  --ngrok-->  Langflow (host PC)
  session per chat                    Chat Input -> Ciel Vision Router -> Agent (DeepSeek)
  tweaks: memory owner,                 +-- Ciel Memory Search / Store  (Chroma + Ollama embeddings)
          user tables, images           +-- Ciel Table Analyst          (user CSV/TSV)
                                        +-- Ciel ML Analyst             (models on user CSV/TSV)
                                        +-- Ciel Dataset Store          (personal datasets, signed-in)
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
├── .github/workflows/
│   ├── ci.yml
│   └── keep-awake.yml           visits the Streamlit app every 4 hours
├── .streamlit/                  theme and secrets template
├── flow/
│   ├── v1.0.0/ … v1.7.0/        main flow snapshots (latest: v1.7.0)
│   ├── memory_admin/            Ciel Memory Admin flow ("Data saya")
│   └── components/              custom component sources embedded in the flow
├── tests/                       offline tests, live quality scripts, results
├── tools/
│   ├── ciel_watchdog.ps1        restart Ollama, Langflow and ngrok on the host when they are down
│   ├── migrate_memory_owner.py  give pre-v1.3.0 memories an owner
│   ├── prune_chat_history.py    delete server-side messages after the retention period
│   └── wake_streamlit.py        open the Streamlit app and wake it from sleep
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

Python and the dependencies in `requirements.txt` (`streamlit[auth]>=1.54`, `requests`, `python-dotenv`, `pypdf>=6`) for the app. The backend host needs Langflow 1.12.4, Ollama (`qwen2.5vl:3b` for images, `nomic-embed-text-v2-moe` for memory embeddings), Chroma, and ngrok.

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

- `CHAT_INPUT_ID` (default `ChatInput-X8W7I`, the Chat Input in the flow) and `CONTACT_URL` (https:// or mailto: link shown on the pricing page for people interested in paid plans, and on the privacy page as the place to send data requests).
- `OPERATOR_NAME`: who runs Ciel, shown on the privacy page. Set it and `CONTACT_URL` before going public: the privacy page follows UU 27/2022 (PDP), which expects the operator's identity and a way to send data requests.
- `RATE_LIMIT_PER_HOUR` (default 20), `RATE_LIMIT_PER_HOUR_LOGIN` (default 60), `RATE_LIMIT_ANON_TOTAL_PER_HOUR` (default 150): hourly message limits, checked before any backend call.
- `[auth]` block (Google OAuth client): enables "Masuk dengan Google". Long-term memory is only available to signed-in users and is private to each account; without `[auth]` memory is disabled.
- `MEMORY_SEARCH_ID`, `MEMORY_STORE_ID` (defaults match `flow/v1.3.0` and later) `TABLE_ANALYST_ID` (default matches `flow/v1.5.0` and later) `ML_ANALYST_ID` (default matches `flow/v1.6.0` and later) and `DATASET_STORE_ID` (default matches `flow/v1.7.0` and later): component IDs the app sends tweaks to. Langflow ignores tweaks for nodes or fields a flow does not have.
- `MEMORY_ADMIN_FLOW_ID` (and `MEMORY_ADMIN_NODE_ID`, default `CielMemoryAdmin-adm1n`): the Ciel Memory Admin flow behind the "Data saya" panel. Without it, signed-in users cannot view or delete their data from the app, and the privacy page says so.
- `CHAT_RETENTION_DAYS` (default 30): how long server-side chat history is kept, as stated on the privacy page. Use the same value for `tools/prune_chat_history.py`.

A template is provided in `.streamlit/secrets.toml.example`. For local runs copy it to `.streamlit/secrets.toml` (git-ignored) or use a `.env` file.

## Deployment (Streamlit Community Cloud)

1. Start the backend on the host machine: Langflow (port 7860) with its Ollama and Chroma dependencies, then the ngrok tunnel pointing at `localhost:7860` with the Basic Auth traffic policy.
2. Import `flow/v1.7.0/Ciel_AI_Long-Term_Memory_Master.json` (latest) into Langflow and set `FLOW_ID` to the imported flow. The flow calls four sub-flows by Run Flow (Math Tutor Agent, Verified Data Analyst, Knowledge Retriever, Web Research Assistant), which are not in this repository; see `docs/BACKUP_AND_DISASTER_RECOVERY.md`.
3. Deploy `app.py` from the `main` branch of this repository.
4. Paste the variables above into App settings -> Secrets, using the template format. For Google login, create an OAuth client (Web application) in Google Cloud Console with `https://<your-app>.streamlit.app/oauth2callback` as the redirect URI, and keep the `[auth]` block at the end of the secrets.
5. Open the app and send a test message. If the backend host or tunnel is down, the app shows an error card with a Request ID and a Retry button.
6. For "Data saya": import `flow/memory_admin/Ciel_Memory_Admin.json` into Langflow and set `MEMORY_ADMIN_FLOW_ID` to the imported flow. Schedule `tools/prune_chat_history.py` on the host (see Privacy and Data Retention).
7. Existing memories from flows before v1.3.0 have no owner. Sign in, copy "ID memory" from the account menu (top right), then on the Langflow host run `python tools/migrate_memory_owner.py --user-id <ID> --dry-run`, and again without `--dry-run`.

Later flow updates are applied in place on the existing flow (same `FLOW_ID`); see the flow deployment steps in `RELEASE_CHECKLIST.md`.

The deployed app is only available while the host machine, Langflow, and the ngrok tunnel are running. See Running 24/7 below.

### Running 24/7

Three things stop Ciel when nobody is watching: Streamlit Cloud puts the app to sleep after 12 hours without visitors, Langflow Desktop and ngrok do not come back by themselves after a crash or a restart of the host, and the host itself can sleep or reboot.

**Frontend.** `.github/workflows/keep-awake.yml` opens the app in a headless browser every 4 hours (`tools/wake_streamlit.py`) and presses "Yes, get this app back up!" if it is asleep. A plain HTTP ping does not count as a visit. Set the app URL once under the repository's Settings -> Secrets and variables -> Actions -> Variables as `STREAMLIT_APP_URL`; until then the workflow skips. A run fails when the app does not render, and GitHub emails the owner. GitHub pauses scheduled workflows after 60 days without repository activity; re-enable it in the Actions tab if that happens. The visit only loads the page, so it uses no ngrok requests or DeepSeek tokens.

**Backend.** `tools/ciel_watchdog.ps1` checks Ollama, Langflow and the ngrok tunnel and starts whatever is down. Checks run on the host only, so a healthy run sends nothing through the tunnel. The tunnel is never started without the traffic policy file, and after starting it the script checks once that the public URL refuses requests without credentials (401). It reads `NGROK_URL` from the environment or `.env` and assumes the policy at `~/ngrok-ciel-policy.yml` (`NGROK_POLICY_FILE` overrides it). Log: `~/.ciel_ai/logs/watchdog.log`. Install it from a checkout that stays in place (not a temporary worktree):

```powershell
powershell -ExecutionPolicy Bypass -File tools\ciel_watchdog.ps1 -DryRun
powershell -ExecutionPolicy Bypass -File tools\ciel_watchdog.ps1 -Install
```

`-Install` registers the Task Scheduler task "Ciel backend watchdog" (at logon and every 5 minutes, also on battery); `-Uninstall` removes it. Langflow Desktop is a windowed app, so the task runs in the signed-in user's session: after a reboot the backend comes back once the user signs in. Let the watchdog start ngrok, or start it from a normal window: the task has no administrator rights and cannot restart an ngrok started as administrator (the log says so).

**Host.** Keep the laptop plugged in; set "Sleep" to Never on power (already the case) and "When I close the lid" to Do nothing (Control Panel -> Power Options -> Choose what closing the lid does); set Windows Update active hours so restarts happen at night. These are system settings and are not changed by the scripts.

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
python -m unittest tests.test_memory_v110_contract tests.test_flow_v120_contract tests.test_flow_v130_contract tests.test_flow_v140_contract tests.test_flow_v141_contract tests.test_flow_v150_contract tests.test_flow_v151_contract tests.test_resilience tests.test_rate_limit tests.test_project_context tests.test_live_scripts tests.test_app_hygiene tests.test_performance_snapshot tests.test_pricing tests.test_privacy tests.test_login tests.test_keep_alive
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
