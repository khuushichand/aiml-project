# Logging

## 1. Descriptive of Current Feature Set

- Purpose: Unified structured logging across the server using Loguru, with stdlib logging interception and convenient context helpers for request/job correlation.
- Capabilities:
  - Stdlib → Loguru interception and trace/PII patching (main startup wiring).
  - Context propagation via `log_context(...)` for `request_id`, `traceparent`, job fields, and Prompt Studio tags.
  - Helpers to ensure `X-Request-ID`/traceparent are present on inbound requests.
  - Bound logger factory `get_ps_logger(...)` for consistent Prompt Studio fields.
- Inputs/Outputs: Structured log lines (console and any configured sinks); no module‑local persistence.
- Related Endpoints (examples using the helpers):
  - Chatbooks imports context helpers: tldw_Server_API/app/api/v1/endpoints/chatbooks.py:20
  - Prompt Studio Evaluations imports context helpers: tldw_Server_API/app/api/v1/endpoints/prompt_studio_evaluations.py:38
- Related Schemas: N/A (no Pydantic models in this module).

## 2. Technical Details of Features

- Architecture & Data Flow
  - Stdlib → Loguru interception: `InterceptHandler` routes `logging` records into Loguru with correct caller depth and exception info: tldw_Server_API/app/main.py:26.
  - Log patcher `_trace_log_patcher` enriches records with `trace_id`, `span_id`, `traceparent`, `request_id`, `session_id` and performs light PII redaction (API keys, tokens): tldw_Server_API/app/main.py:67. Startup confirmation: tldw_Server_API/app/main.py:332.
  - Request ID middleware sets/sanitizes `X-Request-ID` and stores `request.state.request_id`: tldw_Server_API/app/core/Security/request_id_middleware.py:34.

- Key Helpers (this module)
  - `new_request_id()` → random opaque ID (hex): tldw_Server_API/app/core/Logging/log_context.py:31
  - `log_context(**fields)` → context manager that contextualizes and returns a bound logger: tldw_Server_API/app/core/Logging/log_context.py:36
  - `ensure_request_id(request)` → fetch or synthesize `request_id`: tldw_Server_API/app/core/Logging/log_context.py:50
  - `ensure_traceparent(request)` → surface `traceparent` header to `request.state.traceparent`: tldw_Server_API/app/core/Logging/log_context.py:73
  - `get_ps_logger(...)` → bound logger with common Prompt Studio fields: tldw_Server_API/app/core/Logging/log_context.py:98

- Dependencies: `loguru` (core), optional FastAPI `Request` type for annotations.
- Configuration: Global logging is configured in `main.py` (no per‑module env). Security middleware provides `request_id`/`session_id` baggage for correlation.
- Concurrency & Performance: Context helpers are in‑process and low‑overhead; interception avoids duplicate formatting while preserving caller depth.
- Error Handling & Safety: The log patcher scrubs obvious secrets by regex. Do not rely solely on scrubbing—avoid logging secrets altogether.

## 3. Developer-Related/Relevant Information for Contributors

- Folder Structure
  - `log_context.py` — request/job context helpers and Prompt Studio logger binding.
- Coding Patterns
  - In HTTP handlers, call `ensure_request_id(request)` and `ensure_traceparent(request)` early, or use them via existing utility wrappers.
  - For scoped work (jobs/evals), prefer `with log_context(...):` so nested logs inherit fields.
  - When logging Prompt Studio operations, prefer `get_ps_logger(...)` to include standard fields.
- Tests
  - Request/trace propagation unit tests: tldw_Server_API/tests/Logging/test_trace_context.py:1
  - Example endpoint using helpers (imports): tldw_Server_API/app/api/v1/endpoints/chatbooks.py:20, tldw_Server_API/app/api/v1/endpoints/prompt_studio_evaluations.py:38
- Local Dev Tips
  - Send `X-Request-ID` and `traceparent` headers to correlate logs across systems.
  - Enable tracing exporters (see Metrics/Tracing README) to auto‑populate `trace_id`/`span_id` in logs.
- Pitfalls & Gotchas
  - Avoid logging secrets. The redaction is best‑effort and may miss exotic formats.
  - If you create additional handlers via `logging.config.dictConfig`, interception in `main.py` wraps configuration to keep routing through Loguru.

