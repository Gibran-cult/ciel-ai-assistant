# Ciel AI Master - Monitoring and Observability

## Purpose

This document describes the monitoring and observability mechanisms currently available for Ciel AI Master.

The goal is to make production behavior measurable across availability, quality, resilience, memory retrieval, and latency without changing the production flow architecture.

## Monitoring Layers

Ciel AI Master monitoring is organized into these layers:

1. Availability and health
2. Request and runtime logging
3. Response quality
4. Performance and latency
5. Memory retrieval quality
6. Resilience and recovery
7. Production quality dashboard

## Availability and Health

The production setup includes a health-check path used to detect backend availability.

Health monitoring is intended to distinguish a healthy backend from a failed or unavailable runtime and support recovery verification.

The health check is part of the production hardening work completed before the final production-readiness review.

## Logging and Observability

The production setup includes logging and observability so runtime behavior can be inspected during failures, performance investigation, and recovery testing.

Logs should be treated as operational diagnostics rather than as a substitute for automated tests.

Sensitive values such as API keys, passwords, tokens, and other credentials must not be written to logs.

## Response Quality

The production quality collector records response-quality test results in:

`tests/results/quality_latest.json`

The latest recorded snapshot reports:

- Passed: 9
- Failed: 0
- Total: 9
- Pass rate: 100%
- Status: healthy

This snapshot represents the recorded quality evaluation for version `v1.1.0`.

## Performance Metrics

The quality snapshot records these performance metrics:

- First request: 26.675 seconds
- Warm median: 38.581 seconds
- Overall median: 36.157 seconds
- P95: 51.143 seconds

These values are diagnostic measurements and should be interpreted as observed benchmark results rather than hard service-level guarantees.

Performance profiling separates model execution, agent execution, memory operations, direct research execution, and nested research execution so that latency bottlenecks can be isolated.

## Memory Quality

The quality snapshot records long-term memory retrieval metrics.

Current values:

- Recall at K=1: 83.33%
- Recall at K=3: 83.33%
- Recall at K=5: 100%
- Context reduction at K=5: 60.7%

The current memory configuration keeps Top K at 5 and uses compact agent-facing memory output.

## Resilience

The quality snapshot records resilience test results.

Current recorded result:

- Passed: 1
- Failed: 0
- Total: 1
- Pass rate: 100%

Resilience testing is intended to verify that backend failures can be detected and that the application can recover to normal operation.

## Automated Checks

The latest quality snapshot records:

- Automated checks passed: 5
- Automated checks failed: 0
- Total automated checks: 5

The GitHub Actions workflow is intentionally scoped to deterministic offline tests and does not require production credentials.

## Quality Dashboard

`quality_dashboard.py` provides a production quality summary from the collected results.

The dashboard surfaces:

- overall status,
- automated check count,
- response-quality results,
- memory recall,
- context reduction,
- first-request latency,
- warm median latency,
- overall median latency,
- P95 latency.

The dashboard consumes the collected result file rather than calling production services directly.

## Operational Workflow

A practical monitoring workflow is:

```text
Run quality / regression collection
        |
        v
tests/results/quality_latest.json
        |
        v
quality_dashboard.py
        |
        +-- Overall status
        +-- Quality
        +-- Memory
        +-- Performance
        +-- Automated checks
```

For an operational issue:

```text
Issue detected
    |
    v
Check health / availability
    |
    v
Inspect logs
    |
    v
Check latency and quality snapshot
    |
    v
Run targeted regression or resilience checks
    |
    v
Verify recovery
```

## Production Baseline

The current feature release is `v1.1.0`.

The latest recorded quality snapshot reports an overall status of `healthy` with score `1.0`.

This monitoring document describes the current observability layer; it does not change the production flow itself.

## Security Notes

Monitoring data must not expose:

- API keys
- passwords
- authentication tokens
- private credentials
- secret configuration values

Operational logs and quality artifacts should remain safe to store in the repository only when they contain no sensitive information.

## Known Limitations

The current monitoring is primarily snapshot-based rather than a full time-series monitoring platform.

The quality dashboard summarizes collected benchmark results but does not provide continuous alerting, historical trend storage, or a dedicated metrics backend.

These are future improvements rather than requirements for the current v1.1.0 production baseline.
