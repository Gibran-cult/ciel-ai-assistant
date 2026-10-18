# Ciel AI Master - Backup and Disaster Recovery

## Purpose

This document defines what must be backed up and how to restore Ciel AI Master after file loss, a broken environment, a bad deployment, or loss of the backend host.

## What Git Restores, and What It Does Not

The GitHub repository restores the **software state**: the Streamlit app, tests, documentation, CI, the main flow snapshots (`flow/v1.0.0/` … `flow/v1.5.1/`), and the custom component sources (`flow/components/`). Release tags `v1.0.0` … `v1.5.2` mark known-good states (see `RELEASE_CHECKLIST.md`).

The following parts of production are **not in Git** and need their own protected backup:

| Part | Where it lives | Notes |
|---|---|---|
| App secrets | Streamlit Cloud Secrets, local `.streamlit/secrets.toml` / `.env` | `NGROK_URL`, `NGROK_USER`, `NGROK_PASSWORD`, `LANGFLOW_API_KEY`, `FLOW_ID`, optional `[auth]` and rate limits |
| Langflow global variables | Langflow database | At least `DEEPSEEK_API_KEY` (main Agent and the DeepSeek sub-flows) and `EXA_API_KEY` (Web Research). Flows store only the variable names. |
| Sub-flows | Langflow database | Math Tutor Agent and Knowledge Retriever, called by Run Flow; Web Research Assistant, kept as the rollback path for research. Verified Data Analyst was removed in v1.11.0 (a backup is in the flow backups). |
| Built-in sales dataset | `~/.ciel_ai/builtin_datasets/200_sales_data.csv` on the Langflow host | Read by Ciel Table Analyst (`file_name=200_sales_data`). Copied from Langflow file storage (`200_sales_data (1).csv`, 200 rows); keep a copy with the flow backups. |
| Knowledge base | `~/.langflow/knowledge_bases` on the Langflow host | Knowledge base `TITANIC_DATA_SCIENCE_SOLUTIONS`, used by Knowledge Retriever |
| Long-term memory | `~/.ciel_ai/long_term_memory` (Chroma) on the Langflow host | Per-user memories; cannot be rebuilt from Git |
| ngrok traffic policy | A policy file passed to the ngrok agent (default `~/ngrok-ciel-policy.yml`) | Generated from `.env` by `tools/render_ngrok_policy.py`: per-IP rate limits, Basic Auth credentials and the exact path allowlist. Regenerate it instead of restoring it. |
| Ollama models | Ollama on the Langflow host | `qwen2.5vl:3b` (images), `nomic-embed-text-v2-moe:latest` (memory embeddings); re-pull with `ollama pull` |
| Flow backups | `~/.ciel_ai/flow_backups/` on the Langflow host | Copies taken before each in-place flow change (see below) |
| Retention task | Windows Task Scheduler on the Langflow host | Runs `tools/prune_chat_history.py` daily; recreate it after restoring the host (see `README.md`) |
| Watchdog task | Windows Task Scheduler on the Langflow host | "Ciel backend watchdog" runs `tools/ciel_watchdog.ps1` at logon and every 5 minutes; recreate it with `-Install` after restoring the host |
| Keep-awake variable | GitHub repository variable `STREAMLIT_APP_URL` | Used by `.github/workflows/keep-awake.yml` |

Do not place real secret values in the repository, documentation, issue tracker, or any public backup. Exported flows can contain keys if a node stores one literally; production flows use global variables, but archived flows in the Langflow project "Arsip" still contain literal keys.

## Flow Backups and Rollback

Before every in-place change to a production flow or sub-flow, the live flow is saved to `~/.ciel_ai/flow_backups/` (for example `prod_v1.5.0_before_v1.5.1_<timestamp>.json`, `subflow_Math_Tutor_Agent_before_global_key_<timestamp>.json`).

To roll back, replace the flow's `data` with the backup's `data` through `PATCH /api/v1/flows/<id>` (or import the backup in the Langflow UI), then verify with a real request through ngrok.

Because the sub-flows are not versioned in Git, export them regularly (Langflow UI: Export, or `GET /api/v1/flows/<id>`) to a protected location.

## Recovery Procedure

### 1. Restore the repository

```powershell
git clone https://github.com/Gibran-cult/ciel-ai-assistant
cd ciel-ai-assistant
git checkout v1.5.2        # or main, or another release tag
python -m pip install -r requirements.txt
```

### 2. Restore the backend host

1. Install Langflow 1.12.4 and Ollama; pull `qwen2.5vl:3b` and `nomic-embed-text-v2-moe:latest`.
2. Recreate the Langflow global variables (`DEEPSEEK_API_KEY`, `EXA_API_KEY`) from the protected secret store.
3. Restore `~/.ciel_ai/long_term_memory` and `~/.langflow/knowledge_bases` from their backups.
4. Import the four sub-flows from their exports or from `~/.ciel_ai/flow_backups/`, and upload the Verified Data Analyst dataset.
5. Import `flow/v1.5.1/Ciel_AI_Long-Term_Memory_Master.json`. If the sub-flows got new IDs on import, re-select them in the main flow's four Run Flow nodes.
6. Import `flow/memory_admin/Ciel_Memory_Admin.json` (the "Data saya" flow) and note its ID for `MEMORY_ADMIN_FLOW_ID`.
7. Create a Langflow API key for the app.
8. Start ngrok with the restored traffic policy, pointing at `localhost:7860`, or set `NGROK_URL` in `.env` and run `tools/ciel_watchdog.ps1`, which does it; then reinstall the watchdog task with `-Install`.

### 3. Restore the app configuration

Set the app secrets in Streamlit Cloud (and locally if needed): the ngrok URL and Basic Auth credentials, the new Langflow API key, `FLOW_ID` of the imported main flow, and `MEMORY_ADMIN_FLOW_ID` of the imported admin flow. Do not commit them.

If the memory database could not be restored but older memories without an owner exist, assign them with `tools/migrate_memory_owner.py` (see `README.md`).

## Post-Recovery Verification

1. Offline suite (command in `README.md`) passes.
2. Langflow `/health_check` answers through the tunnel with Basic Auth.
3. A live quality run (`python tests/collect_quality.py`) is healthy.
4. Through ngrok, check by hand: a greeting, a math question (Calculator), a worksheet with several problems (Math Tutor), "total Sales_Amount pada dataset" (Ciel Table Analyst), a research question with sources (Ciel Exa Search), a CSV question with an attached file (Ciel Table Analyst), and an anonymous "ingat namaku …" that is refused without changing the memory count.
5. The public app answers a test message.

A recovery is complete only when all of these pass.

## Disaster Scenarios

### Local working copy lost
Clone the repository, check out the release tag, reinstall dependencies, restore secrets, run the offline suite.

### Bad change on `main`
Find the last good release tag in `RELEASE_CHECKLIST.md`, branch from it, fix, and redeploy through a pull request.

### Bad flow deployment
Restore the flow from `~/.ciel_ai/flow_backups/` (see Flow Backups and Rollback) and verify through ngrok.

### Production configuration lost
Recreate app secrets and Langflow global variables from the protected secret source, then run the verification steps. Do not commit recovered values.

### Backend host lost
Follow the full recovery procedure. Everything listed in "What Git Restores, and What It Does Not" must come from backups.

### Long-term memory lost
Without a separate backup of `~/.ciel_ai/long_term_memory`, the app still works but previously stored memories cannot be reconstructed.

## Recovery Principle

The repository and release tags restore the software state. Protected backups restore the environment state: secrets, Langflow global variables, sub-flows, data, and the tunnel policy. Both are required for a complete production recovery.
