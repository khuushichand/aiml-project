# Per-User LLM Token & Cost Tracking (v1)

## Overview

Admins need clear visibility into who is using which LLM provider/model and how much that usage costs. This feature adds reliable, privacy-conscious per-request token and cost tracking across chat and embeddings, with admin reporting and daily aggregation.

## Goals

- Persist per-request LLM usage with `user_id`, `provider`, `model`, tokens, and cost.
- Summarize usage by user/provider/model/time window for admin reporting.
- Work in both single-user (SQLite) and multi-user (Postgres) modes.
- Avoid storing prompts/responses; only totals and metadata.

## Non-Goals (v1)

- Full invoicing/billing workflows.
- Live dashboards beyond JSON endpoints.
- Perfect vendor-grade tokenization for every provider/model (estimate when necessary).

## Personas & Use Cases

- Admin: View daily/monthly cost by user; identify top spenders/models; export for accounting.
- Team Lead: Track model mix and adoption.
- Developer: Diagnose cost regressions per endpoint/provider/model.

## Scope (v1)

- Track Chat Completions and Embeddings (OpenAI-compatible and routed providers).
- Capture tokens and costs (split prompt/completion where available; estimate otherwise).
- Persist per-request rows; provide daily aggregations and admin endpoints.
- No content storage.

## Data Model

Two new tables in the AuthNZ database (SQLite/Postgres). Keys and indexes chosen for common queries.

1) `llm_usage_log`
- id (pk)
- ts (UTC timestamp)
- user_id (int, nullable for unauthenticated/system)
- key_id (int, nullable; API key identifier if applicable)
- endpoint (text; e.g., `POST:/api/v1/chat/completions`)
- operation (text enum: `chat|embeddings|tts|stt|other`)
- provider (text)
- model (text)
- status (int; HTTP status)
- latency_ms (int)
- prompt_tokens (int)
- completion_tokens (int)
- total_tokens (int)
- prompt_cost_usd (real)
- completion_cost_usd (real)
- total_cost_usd (real)
- currency (text; default `USD`)
- estimated (bool; true if tokens/cost estimated)
- request_id (text; correlates with RequestID middleware)

Recommended indexes:
- ts, user_id, (provider, model), (user_id, ts), (operation, ts)

2) `llm_usage_daily`
- day (date)
- user_id (int)
- operation (text)
- provider (text)
- model (text)
- requests (int)
- errors (int)
- input_tokens (bigint)
- output_tokens (bigint)
- total_tokens (bigint)
- total_cost_usd (real)
- latency_avg_ms (real)

Primary key: (day, user_id, operation, provider, model)

## Pricing Catalog

- Source of truth: a small, code-bundled pricing map with model-level input/output per-1K token rates for major providers (OpenAI, Anthropic, Groq, Mistral, etc.).
- Overrides: optional `tldw_Server_API/Config_Files/model_pricing.json` or env `PRICING_OVERRIDES` (JSON string) with same shape.
- Unknown models fall back to a provider baseline, or a minimal sentinel rate, flagged as `estimated=true`.
- Currency: USD only (v1).

## Integration Points

- Chat: `tldw_Server_API/app/api/v1/endpoints/chat.py`
  - After receiving provider response (or error), extract `usage` if provided.
  - If missing, estimate tokens via tokenizer fallback and compute cost via Pricing Catalog.
  - Log one row into `llm_usage_log` with user, provider, model, status, latency, tokens, and cost.

- Embeddings: `tldw_Server_API/app/api/v1/endpoints/embeddings_v5_production_enhanced.py`
  - Token counting already present; compute cost via Pricing Catalog and log usage entry.

- Service Layer: introduce `UsageTracker` (async) to centralize pricing lookup and DB writes.

## Admin APIs (v1)

- `GET /api/v1/admin/llm-usage`
  - Filters: user_id, provider, model, operation, status, start, end, page, limit
  - Returns paginated rows from `llm_usage_log` (no content payloads)

- `GET /api/v1/admin/llm-usage/summary`
  - Params: start, end, group_by ∈ {user, provider, model, operation, day}
  - Aggregates: requests, errors, tokens_in/out/total, total_cost_usd, avg_latency_ms

- `GET /api/v1/admin/llm-usage/top-spenders`
  - Params: start, end, limit
  - Returns top users by `total_cost_usd`

- Optional (v1.1): `GET /api/v1/admin/llm-usage/export.csv` with same filters

All endpoints require admin role (existing `require_admin`).

## Configuration

- `LLM_USAGE_ENABLED` (default: true) to control feature toggle.
- `PRICING_OVERRIDES` (JSON) or file `Config_Files/model_pricing.json`.

## Privacy & Security

- Do not persist prompts/responses.
- Store `user_id` and `key_id` only; no API key material.
- No IP/UA duplication (already in `usage_log`).
- RBAC: admin-only endpoints.

## Performance

- Single-row inserts with appropriate indexes.
- Non-blocking writes (fire-and-forget task) where safe; never fail the request due to logging.
- Daily aggregation mirrors `usage_aggregator` pattern.

## Testing Strategy

- Unit:
  - PricingCatalog selection and override precedence.
  - Cost calculation with split prompt/completion rates.
  - Token estimation fallback path marks `estimated=true`.

- Integration:
  - Chat and embeddings write usage rows with expected fields.
  - Error paths write status ≥ 400 with zero cost.
  - Admin endpoints aggregate and filter accurately.

## Rollout Plan

Phase 1: Schema + Pricing + UsageTracker + Instrument Chat/Embeddings + Basic Tests

Phase 2: Admin endpoints (list/summary/top) + Tests

Phase 3: Aggregator job + optional CSV export + Tests

Phase 4: Extend coverage (TTS/STT), optional audit event mirroring, and WebUI (if desired)

## Acceptance Criteria

- Each chat/embedding request writes a `llm_usage_log` row with user, provider, model, tokens, and cost (or estimated).
- Admin can query raw usage and summaries filtered by user/provider/model/date.
- Aggregation produces per-day totals by user/provider/model/operation.
- No content stored.
- Works on SQLite and Postgres.

## Open Questions

- Keep IP/UA in this log? Proposed: No (already present in `usage_log`).
- Multiple currencies? Proposed: v1 stays on USD only.
- Pricing update cadence? Proposed: code defaults + optional overrides via file/env.

---

## Implementation Stages (with Success Criteria and Tests)

### Stage 1: Schema & Core Services
Goal: Add DB tables and core `UsageTracker` + `PricingCatalog`.
Success Criteria:
- Schema present in both SQLite and Postgres migration files.
- `UsageTracker.log_llm_usage(...)` writes rows.
- `PricingCatalog` loads defaults and overrides; calculates costs.
Tests:
- Unit tests for PricingCatalog and basic insert via DatabasePool.

### Stage 2: Instrumentation in Chat/Embeddings
Goal: Log usage in chat.py and embeddings endpoint.
Success Criteria:
- On success/error, one log row per request with correct fields.
- Unknown models set `estimated=true`.
Tests:
- Integration tests mocking provider responses and verifying inserts.

### Stage 3: Admin Endpoints
Goal: Admin can query logs and summaries.
Success Criteria:
- `GET /admin/llm-usage` returns paginated rows with filters.
- `GET /admin/llm-usage/summary` groups correctly.
- `GET /admin/llm-usage/top-spenders` returns correct ranking.
Tests:
- Integration tests hitting endpoints and asserting shapes and numbers.

### Stage 4: Aggregator & CSV (Optional)
Goal: Daily aggregation and optional CSV export.
Success Criteria:
- Background aggregator computes `llm_usage_daily` per day.
- CSV endpoint returns expected columns.
Tests:
- Unit tests for aggregator SQL and CSV formatting.

