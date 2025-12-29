# Claims Budget Guardrails + Adaptive Throttling (Stage 4)

## Goals
- Enforce per-job cost/token guardrails for claims extraction and verification.
- Surface provider cost/latency usage in claims analytics dashboards.
- Add adaptive throttling hooks based on latency, error rate, and remaining budget.

## Scope
- Guardrails apply to LLM-backed extraction and verification paths, with optional strict behavior.
- Provider usage aggregates derive from `llm_usage_log` entries tagged by operation.
- Adaptive throttling relies on in-memory EWMA stats and configured thresholds.

## Budget Model
- `ClaimsJobBudget` tracks `max_cost_usd` and `max_tokens` with `reserve` (pre-call) and `add_usage` (post-call).
- `resolve_claims_job_budget` honors `CLAIMS_JOB_BUDGET_ENABLED` and allows per-request overrides.
- Strict mode (`CLAIMS_JOB_BUDGET_STRICT`) returns empty claims or NEI instead of fallback behavior.

## Adaptive Throttling
- Thresholds:
  - `CLAIMS_ADAPTIVE_THROTTLE_LATENCY_MS` (EWMA latency)
  - `CLAIMS_ADAPTIVE_THROTTLE_ERROR_RATE` (rolling error rate)
  - `CLAIMS_ADAPTIVE_THROTTLE_BUDGET_RATIO` (remaining budget ratio)
- `should_throttle_claims_provider` blocks calls when thresholds are exceeded.
- `suggest_claims_concurrency` reduces concurrency based on the same signals.

## Dashboard Data
- `provider_usage` aggregates by provider/model/operation:
  - `requests`, `errors`, `total_tokens`, `total_cost_usd`
  - `latency_avg_ms`, `latency_p95_ms`

## Metrics
- `claims_provider_budget_exhausted_total`
- `claims_provider_throttled_total`

## Configuration
- [Claims]
  - `CLAIMS_JOB_BUDGET_ENABLED`
  - `CLAIMS_JOB_MAX_COST_USD`
  - `CLAIMS_JOB_MAX_TOKENS`
  - `CLAIMS_JOB_BUDGET_STRICT`
- [ClaimsMonitoring]
  - `CLAIMS_ADAPTIVE_THROTTLE_ENABLED`
  - `CLAIMS_ADAPTIVE_THROTTLE_LATENCY_MS`
  - `CLAIMS_ADAPTIVE_THROTTLE_ERROR_RATE`
  - `CLAIMS_ADAPTIVE_THROTTLE_BUDGET_RATIO`

## Testing Notes
- Unit tests cover budget exhaustion and throttle triggers.
- Dashboard analytics tests assert the `provider_usage` field is present.
