# Ciel AI Master - Monitoring and Observability

## Purpose

This document describes how Ciel AI Master's behavior can be measured and diagnosed: availability, request logs, response quality, latency, memory retrieval, and resilience.

## Monitoring Layers

1. Availability and health
2. Request logging and Request IDs
3. Response quality
4. Performance and latency
5. Memory retrieval quality
6. Resilience and recovery
7. Quality dashboard

## Availability and Health

Langflow exposes `/health_check` (status of the chat and database services). It is used by `tests/test_ciel_master.py` and in recovery verification. The Streamlit app does not poll it; when the backend or tunnel is down, a request fails and the app shows an error card with a Request ID and a Retry button.

The ngrok tunnel's traffic policy adds Basic Auth and a per-IP rate limit on `/api/v1/run/`.

## Request Logging and Request IDs

`app.py` logs one line per step with a short Request ID (`id=`):

```text
request_start / request_response / request_success      normal requests
http_error (status, first 500 chars of the body)         HTTP errors from Langflow or ngrok
response_parse_error (first 500 chars of the response)   unexpected response shape
request_timeout / connection_error / request_error       network errors (type and message)
image_upload_* (same pattern)                            photo uploads
rate_limited                                             message refused by the hourly limit
```

Users never see response bodies or exception text; they see a short explanation and the Request ID under "Technical details". To investigate a user's report, search the Streamlit Cloud logs for that Request ID.

Logs must not contain API keys, passwords, tokens, or other credentials.

## Response Quality

`tests/collect_quality.py` runs the live checks and writes `tests/results/quality_latest.json`. Each live request uses its own Langflow session and the same tweaks as the app (`tests/live_session.py`), and the answer that is judged is the one users see (`app.final_answer_text`).

Latest recorded run (2026-10-14, production flow v1.5.1 through local Langflow):

- Response quality: 9/9 passed
- Automated checks: 5/5 passed
- Overall status: healthy, score 1.0

When a case fails, the result file lists it under `response_quality.failed_cases` with its reasons and a preview of the answer (up to 1,200 characters).

## Performance Metrics

Latest recorded run:

- First request: 17.4 s
- Warm median: 14.6 s
- Overall median: 14.6 s
- P95: 16.7 s

For comparison, the v1.1.0 baseline recorded a median of 36.2 s and a P95 of 51.1 s. The main contributors to the drop: v1.2.0 stopped sending every message through the local vision model, and v1.5.2 removed the shared test session and shortened sub-agent history. Runs through local Langflow skip ngrok, so public latency is slightly higher. These are observed benchmarks, not service-level guarantees.

## Memory Quality

- Recall at K=1: 83.33%
- Recall at K=3: 83.33%
- Recall at K=5: 100%
- Context reduction at K=5: 60.7%

The memory components keep Top K at 5 with compact agent-facing output, and only return the signed-in user's memories.

## Resilience

The resilience check passes (1/1). Offline tests in `tests/test_resilience.py` cover authentication failures, gateway errors, timeouts, invalid JSON, unexpected response shapes, rate limiting, and that errors do not reveal internal details.

## Quality Dashboard

`quality_dashboard.py` summarizes `tests/results/quality_latest.json`: overall status, automated checks, response quality, memory recall, context reduction, and latency. It reads the result file and does not call production services.

## Operational Workflow

```text
Run python tests/collect_quality.py
        |
        v
tests/results/quality_latest.json  -->  quality_dashboard.py
```

For an operational issue:

```text
User reports an error (Request ID)
    |
    v
Search the Streamlit Cloud logs for the Request ID
    |
    v
Check Langflow /health_check and the ngrok tunnel
    |
    v
Run the live quality collection or a targeted check
    |
    v
Verify recovery with a real request through ngrok
```

## Security Notes

Monitoring data must not expose API keys, passwords, authentication tokens, private credentials, or secret configuration values. Quality artifacts committed to the repository contain only scores, timings, case IDs, failure reasons and answer previews.

## Known Limitations

Monitoring is snapshot-based: there is no continuous time-series storage, alerting, or dedicated metrics backend. Live quality runs are started manually.
