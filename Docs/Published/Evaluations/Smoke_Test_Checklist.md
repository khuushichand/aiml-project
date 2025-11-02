# Unified Evaluations API - Smoke Test Checklist

Use this checklist to manually verify core Evaluations functionality after changes.

Prereqs
- Server running locally with `AUTH_MODE=single_user` and `SINGLE_USER_API_KEY` set.
- Use `Authorization: Bearer <SINGLE_USER_API_KEY>` or `X-API-KEY: <SINGLE_USER_API_KEY>`.

Auth & Basic
- Auth: Valid key accepted; invalid key returns 401 with structured error.
- CORS: Web requests permitted per configured origins.

Health & Metrics
- GET `/api/v1/evaluations/health` returns status `healthy` or `degraded` (not always-healthy).
- GET `/api/v1/evaluations/metrics` returns JSON; `Accept: text/plain` returns Prometheus text.

OpenAI-Compatible CRUD
- POST `/api/v1/evaluations` creates evaluation (201). Response contains `id`, `name`, `eval_type`, and timestamps.
- GET `/api/v1/evaluations` lists evaluations with pagination fields (`has_more`, `first_id`, `last_id`).
- GET `/api/v1/evaluations/{eval_id}` returns evaluation or 404 structured error.
- PATCH `/api/v1/evaluations/{eval_id}` updates metadata/spec; 404 if missing.
- DELETE `/api/v1/evaluations/{eval_id}` returns 204; subsequent GET is 404.

Datasets
- POST `/api/v1/evaluations/datasets` accepts samples and returns dataset object with `sample_count`.
- GET `/api/v1/evaluations/datasets` lists datasets.
- GET `/api/v1/evaluations/datasets/{dataset_id}` retrieves dataset (with samples).
- DELETE `/api/v1/evaluations/datasets/{dataset_id}` returns 204.

Runs
- POST `/api/v1/evaluations/{eval_id}/runs` returns 202 + run object (status `pending` or `running`).
- GET `/api/v1/evaluations/{eval_id}/runs` lists runs; filter by `status`.
- GET `/api/v1/evaluations/runs/{run_id}` shows progress/results once finished.
- POST `/api/v1/evaluations/runs/{run_id}/cancel` returns cancelled or structured error if not found.

tldw-Specific Evaluations
- POST `/api/v1/evaluations/geval` returns metrics, average score; errors are sanitized.
- POST `/api/v1/evaluations/rag` returns metrics and overall/retrieval/generation scores.
- POST `/api/v1/evaluations/response-quality` returns metrics, `overall_quality`, `format_compliance`.
- POST `/api/v1/evaluations/batch` executes multiple items; returns counts and per-item results.

Webhooks
- POST `/api/v1/evaluations/webhooks` registers webhook (validate events) and returns ID.
- GET `/api/v1/evaluations/webhooks` lists user webhooks.
- DELETE `/api/v1/evaluations/webhooks?url=...` removes matching webhook.
- POST `/api/v1/evaluations/webhooks/test` performs a connectivity test (
  may require reachable endpoint).

Rate Limits
- GET `/api/v1/evaluations/rate-limits` returns tier/limits/usage/remaining.
- Hitting global limiter (IP-based) returns 429 with `Retry-After`. Per-user limiter is TODO.

Error Shape
- Malformed body → 400 with structured `error` object.
- Not found → 404 with structured `error` object and `param`.
- Server failures → 500 with sanitized messages.
