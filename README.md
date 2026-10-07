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
│   ├── v1.0.0/
│   └── v1.1.0/
├── tests/
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
