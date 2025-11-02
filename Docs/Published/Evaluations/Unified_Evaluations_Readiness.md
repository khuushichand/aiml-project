# Unified Evaluations - Readiness Summary

Scope
- Unified, production-grade endpoints for Evaluations: OpenAI-compatible CRUD + runs + datasets, tldw-specific evals (G-Eval, RAG, response-quality), OCR (`/ocr`, `/ocr-pdf`), webhooks, health/metrics, pipeline presets/cleanup, A/B test scaffolding, and basic rate limiting.

Recent Changes
- Deduplicated overlapping routes in `evaluations_unified.py` (single `/api/v1/evaluations` surface).
- Health check now performs a real DB probe and circuit-breaker check; returns `healthy`/`degraded`.
- Run creation is non-blocking via internal asyncio tasks; `BackgroundTasks` parameter is present for future integration.
- Standardized single-user auth to `SINGLE_USER_API_KEY` (Bearer or `X-API-KEY`).
- Added OCR evaluation endpoints (`/ocr`, `/ocr-pdf`).
- Added RAG pipeline presets (`/rag/pipeline/presets` CRUD) and cleanup endpoint (`/rag/pipeline/cleanup`).
- Added embeddings A/B test endpoints (create/run/status/results/export/significance/events/delete) with admin gating.

Deferred / TODO
- Integrate per-user usage limiting (`user_rate_limiter`) directly into `/geval`, `/rag`, `/response-quality`, `/batch` handlers (global/IP limiter exists).
- Flesh out A/B test orchestration (progress granularity, richer metrics, error paths) as needed.
- Promote and gate heavy tests with markers as needed.

Operational Notes
- Health reflects DB availability and circuit state; failures surface as `degraded` with DB `disconnected`.
- Metrics endpoint supports JSON and Prometheus text via `Accept` negotiation.
- Error messages are sanitized; detailed context is logged via loguru.
- Rate limits: global/IP limiter enforced; per-user usage summary available at `GET /api/v1/evaluations/rate-limits`.
- Admin gating: heavy runs (e.g., A/B test runner) require admin unless `EVALS_HEAVY_ADMIN_ONLY` is disabled.

Next Steps
- Integrate per-user usage limits with appropriate headers and cost/token accounting across unified endpoints.
- Harden A/B test runner and results reporting; expand examples in the API reference.
