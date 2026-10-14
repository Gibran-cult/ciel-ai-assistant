# Ciel AI Master

## Overview

Ciel AI Master is an AI assistant project built around Langflow with long-term memory, tool-based routing, web research, and production-oriented testing and monitoring.

The project is designed to support normal conversation, knowledge retrieval, analysis, research, and persistent long-term memory while keeping production credentials outside the repository.

## Features

- Intelligent agent-based request routing
- Long-term memory search and storage
- Web research assistant
- Data analysis and math-oriented tools
- Production health checks
- Rate limiting
- Logging and observability
- Automated regression testing
- Response quality evaluation
- Performance profiling
- Fallback and resilience testing
- GitHub Actions CI

## Architecture

The main system is centered around a Langflow agent.

The high-level architecture is:

```text
User
  │
  ▼
Ciel AI Master
  │
  ├── LLM
  ├── Long-Term Memory Search
  ├── Long-Term Memory Store
  ├── Math / Analysis Tools
  └── Web Research Assistant
```

## Long-Term Memory

Ciel AI Master uses persistent long-term memory to retrieve information relevant to previous interactions.

Memory search uses a Top K value of 5.

The v1.1.0 optimization reduced retrieved context size by approximately 60.7% at Top K = 5.

## Project Structure

```text
.
├── .github/
├── flow/
│   ├── v1.0.0/ … v1.4.1/
│   └── components/
├── tests/
├── tools/
├── app.py
├── langflow_client.py
├── quality_dashboard.py
├── requirements.txt
├── CHANGELOG.md
├── RELEASE_CHECKLIST.md
└── README.md
```

## Requirements

The project requires Python and the dependencies listed in `requirements.txt`.

The production workflow also uses Langflow and supporting services required by the flow and memory system.

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

Optional: `CHAT_INPUT_ID` (defaults to the Chat Input component ID in the v1.1.0 flow) and `CONTACT_URL` (https:// or mailto: link used by the paid-plan buttons on the pricing page).

Optional for public deployments:

- `RATE_LIMIT_PER_HOUR` (default 20), `RATE_LIMIT_PER_HOUR_LOGIN` (default 60), `RATE_LIMIT_ANON_TOTAL_PER_HOUR` (default 150): hourly message limits, checked before any backend call.
- `[auth]` block (Google OAuth client): enables "Masuk dengan Google". Long-term memory is only available to signed-in users and is private to each account; without `[auth]` memory is disabled.
- `MEMORY_SEARCH_ID`, `MEMORY_STORE_ID`: memory component IDs (defaults match `flow/v1.3.0` and later).

A template is provided in `.streamlit/secrets.toml.example`. For local runs copy it to `.streamlit/secrets.toml` (git-ignored) or use a `.env` file.

## Deployment (Streamlit Community Cloud)

1. Start the backend on the host machine: Langflow (port 7860) with its Ollama and Chroma dependencies, then the ngrok tunnel with Basic Auth pointing at `localhost:7860`.
2. Import `flow/v1.4.1/Ciel_AI_Long-Term_Memory_Master.json` (latest) into Langflow and set `FLOW_ID` to the imported flow.
3. Deploy `app.py` from the `main` branch of this repository.
4. Paste the variables above into App settings -> Secrets, using the template format. For Google login, create an OAuth client (Web application) in Google Cloud Console with `https://<your-app>.streamlit.app/oauth2callback` as the redirect URI, and keep the `[auth]` block at the end of the secrets.
5. Open the app and send a test message. If the backend host or tunnel is down, the app shows a connection error card with a retry button.
6. Existing memories from older flows have no owner. Sign in, copy "ID memory" from the sidebar memory panel, then on the Langflow host run `python tools/migrate_memory_owner.py --user-id <ID> --dry-run`, and again without `--dry-run`.

The deployed app is only available while the host machine, Langflow, and the ngrok tunnel are running.

### Hosting on a low budget

Streamlit Community Cloud (free) is a good fit for the frontend: the app is a thin client and the heavy work runs on the Langflow host. Apps sleep after 12 hours without traffic and have about 1 GB of memory.

The limiting part is the backend host and tunnel. ngrok's free plan is capped at roughly 20,000 HTTP requests and 1 GB of outbound data per month, which is enough for light use. If traffic grows, a Cloudflare Tunnel (free, no request quota) with an inexpensive domain is the next step. A cloud VPS with enough RAM/GPU for Ollama costs far more than the remaining main expense, DeepSeek tokens, which the rate limits keep in check.

## Local Development

Clone the repository:

```powershell
git clone https://github.com/Gibran-cult/ciel-ai-assistant
cd ciel-ai-assistant
```

Install the Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

Configure the required environment variables locally.

## Testing

The repository contains deterministic offline tests and integration-oriented tests.

The offline CI suite includes:

```text
tests.test_memory_v110_contract
tests.test_resilience
tests.test_performance_snapshot
```

Some integration and quality tests require production configuration and are therefore not executed by the offline CI workflow.

## GitHub Actions

GitHub Actions is used for continuous integration.

The CI workflow validates flow JSON files, installs test dependencies, and runs the deterministic offline test suite.

Production credentials are intentionally excluded from CI configuration.

## Versioning

The project uses Git tags and versioned flow snapshots.

Current releases include:

```text
v1.0.0 — Production Baseline
v1.1.0 — Memory Context Optimization
```

The `v1.0.0` snapshot is preserved as the production baseline.

## Security

Sensitive configuration is kept outside source control.

Security measures include environment-based secrets, ngrok Basic Authentication, API authentication, rate limiting, health checks, logging and observability, and failure and recovery testing.

Never commit `.env`, `.streamlit/secrets.toml`, API keys, passwords, or tokens.

## Release Management

Release preparation includes local validation, automated tests, flow snapshot validation, changelog updates, release tagging, GitHub Actions verification, and post-release verification.

See `RELEASE_CHECKLIST.md` for the release workflow.

## Current Status

Current feature release: `v1.1.0`.

The project has completed production hardening, automated CI, release management, memory context optimization, quality evaluation, and performance profiling.
