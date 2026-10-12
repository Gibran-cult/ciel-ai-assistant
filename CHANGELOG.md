# Ciel AI Master — Change Log

## Unreleased

### UI
- Polished the Streamlit workspace UI: dark theme with teal accent, responsive layout, empty state, working indicator, error card with technical details and retry, informative long-term memory panel.
- Backend status now reflects the last real health check instead of a static label.
- Added `.streamlit/config.toml` theme; `requirements.txt` now requires `streamlit>=1.40` (container keys, button icons).
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
