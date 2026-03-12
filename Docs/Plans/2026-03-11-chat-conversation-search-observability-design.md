# Chat Conversation Search Observability Design

## Goal

Add low-cost observability to the `/api/v1/chats/conversations` endpoint so request pressure regressions can be diagnosed before they become user-visible rate-limit complaints.

## Context

The chat conversation search path now has multiple execution strategies:

- no text query
- live search via FTS/BM25
- deleted/trash search via DB-side text matching

That reduced request pressure, but it also made performance regressions harder to reason about from endpoint behavior alone. The next pragmatic step is request-level observability that is cheap in steady state, bounded in label cardinality, and local to the endpoint that owns the behavior.

## Non-Goals

- No new telemetry pipeline or audit subsystem
- No per-query-text logging
- No DB-layer metrics emitted from `CharactersRAGDB`
- No attempt to observe FastAPI validation errors that happen before the endpoint handler runs

## Approach

Instrument only `list_chat_conversations` in `tldw_Server_API/app/api/v1/endpoints/chat.py`.

The endpoint will derive a bounded observability shape before calling the DB helper:

- `deleted_scope=active|include_deleted|deleted_only`
- `query_strategy=none|fts|deleted_text`
- `outcome=success|validation|server_error`

The endpoint will then emit:

- request counter metric
- request duration histogram
- one debug log on success

Unexpected failure logging will reuse the existing error path, enriched with the same bounded request-shape fields instead of creating a second failure log event.

## Metrics

Use the in-process metrics registry directly via `get_metrics_registry().increment(...)` and `get_metrics_registry().observe(...)`.

Do not use `log_counter` / `log_histogram` from `metrics_logger.py` for this endpoint because those helpers also emit info-level log entries on every call, which is too noisy for a hot chat path.

Metric names:

- `chat_conversation_search_requests_total`
- `chat_conversation_search_duration_seconds`

Metric labels:

- `query_strategy`
- `order_by`
- `deleted_scope`
- `outcome`

This keeps cardinality bounded while still separating the meaningful execution modes.

## Debug Logging

Emit one success `logger.debug(...)` event per request with richer request/response shape data that stays out of metric labels:

- `query_present`
- `query_strategy`
- `deleted_scope`
- `character_scope`
- `date_field`
- `limit`
- `offset`
- `total`
- `returned`
- `has_more`
- `db_ms`
- `enrichment_ms`
- `total_ms`

The debug log must not include the raw search text.

## Timing Model

Track three timings inside the endpoint:

- `db_ms`: `search_conversations_page(...)`
- `enrichment_ms`: keyword lookup, message counts, and response item assembly
- `total_ms`: full handler duration

Only `total_ms` is emitted as a histogram metric. Phase timings stay debug-only to avoid extra metric series while still making regressions debuggable.

## Error Handling

Metrics and debug logging are best-effort only. Any exception raised while recording metrics or logs must be swallowed after a debug message so endpoint behavior does not change.

Outcome mapping:

- `success`: normal response path
- `validation`: handler-local `InputError` or explicit endpoint `HTTPException` raised due to request semantics inside the handler
- `server_error`: unexpected exceptions mapped to the existing 500 response path

FastAPI validation failures for malformed query parameters are out of scope because they occur before the handler executes.

## Testing

Add focused endpoint tests in `tldw_Server_API/tests/Chat/unit/test_chat_conversations_api.py`:

- success path emits bounded metric labels
- validation path emits `outcome=validation`
- deleted/trash search emits `query_strategy=deleted_text`
- histogram is recorded once with a non-negative duration
- success debug logging omits raw query text and includes shape fields

Avoid asserting exact timing values or full log string formatting.

## Residual Risk

This slice gives request-level visibility, not full DB tracing. If later debugging needs per-query SQL timing or PostgreSQL plan visibility, that should be a separate, narrower backend diagnostics change rather than expanding this endpoint instrumentation into the DB abstraction.
