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

Latest recorded run (2026-10-17, production flow v1.8.0 through local Langflow):

- Response quality: 8/9 passed. The failed case, research_machine_learning_01, answered on topic with dated sources but without the words "machine" or "pembelajaran mesin". Three reruns of that question passed (25-27 s, with sources).
- Automated checks: 4/5 passed (response quality is the one marked failed)
- Overall status: degraded, score 0.8

The first run that day was 7/9: knowledge_overfitting_01 said "data latihan" instead of "training" (the case now accepts "training", "data latihan" or "pelatihan"), and vision_math_01 timed out at 120 s while the vision model loaded with little free memory. Two vision reruns passed in 25.9 s and 15.0 s.

When a case fails, the result file lists it under `response_quality.failed_cases` with its reasons and a preview of the answer (up to 1,200 characters).

## Performance Metrics

Latest recorded run (2026-10-17, flow v1.8.0):

- First request: 6.3 s
- Warm median: 6.8 s
- Overall median: 6.4 s
- P95: 18.7 s

The previous run (2026-10-14, v1.5.1) had 17.4 s, 14.6 s, 14.6 s and 16.7 s.

For comparison, the v1.1.0 baseline recorded a median of 36.2 s and a P95 of 51.1 s. The main contributors to the drop: v1.2.0 stopped sending every message through the local vision model, and v1.5.2 removed the shared test session and shortened sub-agent history. Runs through local Langflow skip ngrok, so public latency is slightly higher. These are observed benchmarks, not service-level guarantees.

### Image questions (2026-10-18, flow v1.10.0)

Measured on the Langflow PC with new images each time (Ollama caches a repeated image, which made earlier runs look faster):

| Setup | Reading the image | Notes |
|---|---|---|
| Local `qwen2.5vl:3b`, original phone photo (3024x4032) | fails | 4,283 tokens, more than the model's 4,096-token context; the Agent was told the image could not be read |
| Local, photo shrunk to 1024 px | 66-68 s | all four problems read correctly |
| Gemini API, photo shrunk to 1024 px | 2.8-9.7 s | all answers correct (limit 6, median 5, derivative 9x² - 2) |

Timing both models on 8 new photos (4 photos at 1024 and 768 px): `gemini-3.5-flash-lite` read every one in 1.3-2.7 s, while `gemini-3.1-flash-lite` took 2.3-10.0 s when it answered and timed out at 20 s three times. Photo size made no clear difference. v1.10.2 reads with `gemini-3.5-flash-lite` first and limits each model to 8 s. Through ngrok on a test copy, four new phone photos then took 7.6-13.8 s per question, with the image read in 1.9-3.7 s; all answers were correct.

In production after the switch, `gemini-3.1-flash-lite` answered HTTP 503 for a while: the router fell back to the local model, and one image question took 153.6 s (136.5 s reading the image). `gemini-3.5-flash-lite` still answered, so v1.10.1 tries it before the local model. After that, image questions through ngrok took 31.2 and 33.1 s with the image read in 10.0 and 21.8 s, and the local model was not used; the rest of the time is the Agent writing a step-by-step solution. On a test copy of v1.10.1, three new photos took 16.8-23.5 s.

Whole image questions on a test copy of v1.10.0 took 11.1-33.1 s; the slow ones spent time before Chat Input (Langflow on a PC with about 700 MB free memory), not in the router.

### Flow v1.9.0: research by the main Agent (2026-10-18, through ngrok)

Ciel's own browser test on v1.8.0 still took 31.8-40.5 s on the Langflow side: research answers were written twice (research sub-agent, then the main Agent), the first memory call after 5 idle minutes reloaded the embedding model (14 s), and analysis ran 3 search rounds in the sub-flow. Same questions as the table below, measured end to end like the app:

| Type | v1.8.0 with source guard | v1.9.0 |
|---|---|---|
| Chat (5 questions) | 4-7.5 s | 4.0-6.3 s |
| Tutor and explanations (3) | 7-40 s | 5.5-10.9 s |
| Web research, fast mode (3) | 9.8, 38.8, 40.4 s | 8.5, 13.8, 13.6 s |
| Analysis mode (1) | 60.2 s | 16.0 s |

Every research and analysis answer listed sources, and every cited URL was one Exa returned in that run (the guard removed nothing). The response quality suite passed 9/9 on a test copy of v1.9.0. A warm embedding call takes 0.04 s; a cold one took 5-14 s.

### Latency by question type (2026-10-17, through ngrok)

Measured end to end like the app (own session per request, app tweaks), before and after flow v1.8.0 and the Langflow host changes below. Same questions both times, taken from real test usage.

| Type | Before (median / max) | After (median / max) |
|---|---|---|
| Chat (5 questions) | 21.7 s / 31.6 s | 5.3 s / 8.1 s |
| Tutor and explanations (3) | 18.8 s / 40.5 s | 6.9 s / 17.8 s |
| Web research, fast mode (3, run 4 times) | 22.8 s / 146.7 s | about 22 s / 37 s |
| Analysis mode with deep research (1) | 157.3 s | 44.6 s |

### Research sub-flow: thinking off (2026-10-17)

The Web Research Assistant was called directly, 9 runs per setting on three fast-mode questions:

| Setting | Median | Max | Runs citing a URL not in the recorded search output |
|---|---|---|---|
| Thinking on, Exa 3 results (before) | 12.5 s | 16.7 s | 4 of 9 |
| Thinking off, Exa 3 results | 10.4 s | 15.3 s | 1 of 9 |
| Thinking off, Exa 5 results, source rule (production) | 10.7 s | 11.5 s | 2 of 9 |

Every flagged run shows only one recorded `search` call and cites more URLs than one search returns. In one case the notes cited hai.stanford.edu pages and numbers that a retrieved article only mentioned by name, so the sources came from memory. A later probe recorded Exa's own responses next to the Agent's `content_blocks`: in 9 of 9 runs both showed 2 searches (10 URLs), so a search that Langflow failed to record was not observed. Through the main flow (ngrok), fast research took 7.5-27.3 s and analysis 49.0 s after the change.

### Ciel Source Guard (in production since 2026-10-17)

`flow/components/ciel_exa_search.py` (the Exa toolkit plus a record, in the graph context, of every URL Exa returns) and `flow/components/ciel_source_guard.py` (between the Research Agent and Chat Output) remove "Sumber:" entries whose URL Exa did not return in that run, their `[n]` markers, and findings that cited only those entries. One line says how many were removed. On a test copy of the sub-flow: 9 normal runs removed nothing (every cited URL came from Exa), 10.8-25.1 s with only about 500 MB of free memory. Two runs where the prompt was tweaked to add a fake source lost both the fake URL and its finding, and kept the real sources. Deep research on that copy took 23-37 s in 4 runs, with each Exa call taking 0.4-7.6 s.

After the production install, measured through ngrok: fast research 38.8, 9.8 and 40.4 s, and analysis 60.2 s, all with sources. The guard itself takes under 0.1 s, and the research sub-flow took about 15 s. Most of the variation comes from the main Agent's DeepSeek calls (thinking on): its first step before calling research usually takes 2.4-7 s (14.1 s in the slowest run), and writing the final answer takes 5-16 s. An earlier run after the install timed out at 300 s and could not be reproduced (ngrok also dropped twice in that period). The Agent message of the main flow still shows the research sub-agent's searches and their durations; the sub-flow's own stored message now holds only the checked notes.

Production traces before the change (108 runs, 13-17 Oct): median 29.9 s, P90 127 s, none under 10 s. Fact questions answered without web research take 7-11 s. Fast research still varies with how long DeepSeek thinks while writing the notes (6-13 s).

### Langflow host settings that affect latency

- `LANGFLOW_VERTEX_BUILDS_STORAGE_ENABLED=false` in `%APPDATA%\com.LangflowDesktop\data\.env`. After every layer of the graph, Langflow 1.12 logs each component's build result one by one (`lfx/graph/graph/base.py`, `_execute_tasks`), at 1-3.6 s per component. With 11 components in the first layer, every request waited about 11-17 s before the Agent started, even "iya boleh". These rows only feed the build view in the Langflow editor; messages (the Agent's chat history) and transactions are still stored.
- `LANGFLOW_DEACTIVATE_TRACING=true`. Tracing had written about 3 GB to the `span` table. That data was deleted and the database compacted on 2026-10-17 (3.2 GB to 232 MB; backup in `~/.ciel_ai/langflow_db_backups/`). While the database was that large and the PC was short of memory, storing a chat message took 11-12 s, and two requests stalled for 8 and 14 minutes.
- The backend shares the PC's 8 GB of RAM with everyday apps. When available memory dropped to about 160 MB (committed memory near its limit), Langflow, Ollama and ngrok all timed out. Close unused apps before others test Ciel.

- Langflow 1.12 derives `Message.text` from the message's text blocks, and assigning it replaces every text block with one joined block. Chat Output assigns it, so a component between the Agent and Chat Output must keep only the final answer's text block, or the app shows earlier rounds as well (seen on the first v1.9.0 test).

### Measuring a slow request

`GET /api/v1/monitor/transactions?flow_id=<FLOW_ID>` lists every component run with a timestamp, so the gap between Chat Input, Ciel Vision Router, Agent and Chat Output shows where the time went. The Agent message's `content_blocks` (from `GET /api/v1/monitor/messages`) give the duration of each tool call and each text step. Message timestamps are taken when an answer starts streaming, not when it ends, so do not use them as response times.

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
