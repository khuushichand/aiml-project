# Unified Evaluations – Readiness Summary

Scope
- Unified, production‑grade endpoints for Evaluations: OpenAI‑compatible CRUD + runs + datasets, tldw‑specific evals (G‑Eval, RAG, response‑quality), webhooks, health/metrics, and basic rate limiting.

Recent Changes
- Deduplicated overlapping routes in `evaluations_unified.py`.
- Corrected health check to perform a real DB probe (no longer always healthy).
- Kept `BackgroundTasks` for non‑blocking run creation semantics.
- Standardized single‑user auth to `SINGLE_USER_API_KEY` (removed `API_BEARER` fallback).
- Added explicit TODOs to integrate per‑user usage limits in unified endpoints.

Deferred / TODO
- Per‑user usage limiting (via `user_rate_limiter`) for `/geval`, `/rag`, `/response-quality`, `/batch`.
- Promote and gate heavy tests with markers as needed.

Operational Notes
- Health reflects DB availability; failures surface as `degraded` with DB `disconnected`.
- Metrics endpoint supports JSON and Prometheus text based on `Accept` header.
- Error messaging is sanitized to avoid sensitive leakage; logs contain full context via loguru.

Next Steps
- Implement per‑user usage limits with appropriate headers and cost/token accounting.
- Finalize test promotion and CI configuration for evaluations suite.

