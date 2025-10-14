# Chat Module – Developer Guide

This guide explains the Chat module’s architecture, key components, and how to extend or maintain it. It targets developers and maintainers working on provider integrations, request handling, streaming, and system reliability.

## Goals & Scope

- OpenAI‑compatible Chat API (`/api/v1/chat/completions`) with streaming (SSE) and non‑streaming responses
- Multiple LLM providers (commercial and local) through a unified dispatch layer
- Consistent validation (Pydantic schemas) and rich error mapping
- Optional rate limiting, queuing/back‑pressure, and metrics/tracing
- Character sessions, dictionaries, world books integration through adjacent subsystems

## Authentication

- Supports `Authorization: Bearer <token>`, legacy `Token: <token>`, and single‑user `X-API-KEY` headers.
- Actual enforcement depends on deployment settings (`AUTH_MODE`, config flags). See `main.py` auth wiring and `core/Auth` utilities.

## Persistence

- Requests are ephemeral by default; set `save_to_db: true` to persist conversations/messages.
- Config toggles for default persistence are read from `[Chat-Module]` and environment (e.g., `CHAT_SAVE_DEFAULT`).
- Non‑stream responses include `tldw_conversation_id` in the JSON payload for client state.

## Directory Map

 - `tldw_Server_API/app/core/Chat/`
  - `Chat_Functions.py` – Legacy central dispatcher used by the API endpoint today; provider mappings are no longer duplicated here
  - `chat_orchestrator.py` – Modern dispatcher/utilities (build inputs, assemble context) that use `provider_config.py` mappings
  - `chat_helpers.py` – Request shaping helpers, conversion from API schemas, dictionary/character hooks
  - `provider_manager.py` & `provider_config.py` – Provider health/fallback management and authoritative handler/parameter mappings
  - `rate_limiter.py` – Module‑level rate limiting primitives & startup initialization
  - `request_queue.py` – Optional in‑memory queue for back‑pressure and concurrency control
  - `streaming_utils.py` – Streaming helpers (yielding tokens/chunks to clients)
  - `chat_metrics.py` – Metrics emitters (counters, histograms)
  - `chat_exceptions.py` – Typed exceptions + mapping utilities
  - `Chat_Deps.py` – Shared dependency types and error helpers
  - `document_generator.py` – Structured output helpers for document‑like responses
  - `prompt_template_manager.py` (+ `prompt_templates/`) – Prompt templating utilities

Related:
- API schemas: `tldw_Server_API/app/api/v1/schemas/chat_request_schemas.py`
- LLM provider calls: `tldw_Server_API/app/core/LLM_Calls/` (both cloud and local backends)
- Character sessions & world books: `tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py`, notes DB
- Chat dictionaries: `Config_Files` + `core/config.py` (Chat‑Dictionaries section)
- Provider listing/health: `tldw_Server_API/app/api/v1/endpoints/llm_providers.py`

## Request Flow (High‑Level)

1. FastAPI endpoint parses request into `ChatCompletionRequest` (Pydantic) – OpenAI‑compatible schema.
2. `chat_helpers.py` and endpoint logic build the internal payload, apply defaults, and optionally enrich messages with:
   - Character info (system prompts, world books) when requested
   - Chat dictionaries (keyword substitutions, token budgeting)
3. The endpoint now dispatches via `chat_orchestrator.chat_api_call(...)`, which sources mappings from `provider_config.py`. A compatibility shim remains in `Chat_Functions.chat_api_call` for legacy callers and tests.
4. `LLM_Calls/*` executes the provider‑specific request (cloud or local APIs). Streaming responses are normalized to SSE frames via `streaming_utils`.
5. `chat_exceptions` ensures errors from providers, validation, or networking are translated to module exceptions and proper HTTP responses.
6. `chat_metrics` records counters, latencies, sizes, and success/failure labels.

## Provider Dispatch

- Authoritative mappings live in `provider_config.py`:
  - `API_CALL_HANDLERS` maps provider keys (e.g., `openai`, `anthropic`, `groq`, `mistral`, `vllm`, `ollama`) to call functions in `core/LLM_Calls`.
  - `PROVIDER_PARAM_MAP` translates generic chat arguments (e.g., `messages_payload`, `system_message`, `top_p`, `max_tokens`) into each provider’s expected keyword names.
- `Chat_Functions.py` no longer duplicates these mappings. `provider_config.py` is the single source of truth for handler/parameter mappings.
- At app startup, `main.py` seeds the `provider_manager` from `provider_config.API_CALL_HANDLERS` for health/fallback.

Provider selection notes:
- Requests may specify models with a provider prefix (e.g., `anthropic/claude-3-opus`). The endpoint extracts the provider and model automatically.
- Provider fallback is available via `provider_manager`; controlled by `[Chat-Module].enable_provider_fallback` (disabled by default for stability).

### Adding a Provider (Checklist)

1. Implement provider call(s) in `core/LLM_Calls/` (cloud or local). Prefer a single entrypoint that accepts keyword args from the mapping.
2. Register the handler in `provider_config.API_CALL_HANDLERS`.
3. Add a param mapping in `provider_config.PROVIDER_PARAM_MAP` (map generic → provider kwarg names).
4. Add configuration in `provider_config.py` if needed (API base URL, default model, key names, timeouts).
5. Add tests under `tldw_Server_API/tests/Chat/` (schema validation, dispatch to new provider, basic error mapping, optional integration smoke).
6. Update docs and verify `GET /api/v1/llm/providers` reflects the provider (if you expose it).

## Validation & Schemas

- `chat_request_schemas.py` defines OpenAI‑compatible request models, messages, tools, and response‑format constraints.
- `chat_validators.py` provides additional validators (IDs, temperatures, max tokens, stop sequences, and `MAX_REQUEST_SIZE`).
- The endpoint validates:
  - Message roles and content constraints (assistant/tool message rules)
  - `logprobs/top_logprobs` relationships
  - Tool definitions size limits
  - Request size limits (`MAX_REQUEST_SIZE`), see `chat_validators.py`
  - Model strings with provider prefixes like `anthropic/claude-3-opus` (provider extracted automatically)
  - Image inputs on user messages via `image_url` content parts (expects data URI with base64; validated/sanitized)

## Error Handling

- All module errors should use `chat_exceptions.py` subclasses:
  - `ChatAuthenticationError`, `ChatRateLimitError`, `ChatValidationError`, `ChatProviderError`, `ChatConfigurationError`, `ChatDatabaseError`, …
- Use the `ErrorHandler` context manager to normalize exceptions and log details with safe formatting and request context.
- Provider HTTP/transport exceptions are converted to module exceptions with proper status codes.

## Streaming

- Providers that support streaming return an iterator/generator.
- `streaming_utils.py` normalizes provider chunks and emits OpenAI‑style Server‑Sent Events (`text/event-stream`).
- The endpoint wraps streams with heartbeats, idle timeouts, and finalization signals.
- Errors in streams are emitted as SSE error frames and logged with context.
- Event framing:
  - Emits an initial `event: stream_start` with `{ conversation_id, model, timestamp }`.
  - Emits `: heartbeat ...` comments at intervals.
  - Emits `data: {"choices":[{"delta":{"content":"..."}}]}` for token deltas and a `[DONE]` equivalent on completion.

## Rate Limiting & Queuing

- `rate_limiter.py` exposes a `RateLimitConfig` and `initialize_rate_limiter()` called on app startup (see `main.py`), and is enforced in the chat endpoint.
- `request_queue.py` exists for back‑pressure and concurrency control; it is initialized in `main.py` but not yet wired into the chat endpoint (integration planned).
- Apply limits to high‑cost routes (completions, tools) and consider per‑user/per‑IP strategies.
- In `TEST_MODE=true`, the rate limiter’s key function bypasses client IP to avoid false positives in tests.

## Metrics & Tracing

- `chat_metrics.py` provides counters and histograms (e.g., `chat_api_call_attempt/success`, durations).
- Uses the unified telemetry/metrics facades in `app/core/Metrics` for Prometheus and tracing compatibility.
- Label cardinality should remain bounded (`provider`, `model`, `status`). Avoid dynamic or free‑form labels.

## Configuration

- Configuration sources:
  - `Config_Files/config.txt` (`[Chat-Module]`, `[Chat-Dictionaries]`, and provider sections)
  - Environment variables (override file settings)
- `provider_config.py` defines handler/parameter mappings; `provider_manager.py` manages health/circuit‑breaker/fallback.
- Common toggles: default provider/model, streaming timeouts, max tokens, safety filters, rate‑limit config, request queue sizes.

## Images & Multimodal Input

- User messages support mixed content: text parts and `image_url` parts with data URIs.
- Image data (base64) is validated and can be persisted when `save_to_db` is enabled.
- Large images are processed via the chunked image processor when available.

## Character, Dictionaries, and World Books

- Character sessions and world books live primarily under `api/v1/endpoints/characters_endpoint.py` and the notes DB layer. The Chat module consumes their outputs to enrich prompts (`chat_helpers.py`).
- Chat dictionaries can be applied to user content (replacement rules, token budgeting). They’re configured under `Chat-Dictionaries` in config, surfaced via UI, and exposed via `/api/v1/chat/dictionaries/*` endpoints.

## Testing

- Unit tests:
  - Schema validation (`tests/Chat/test_chat_request_schemas.py`)
  - Prompt templates (`tests/Chat/test_prompt_template_manager.py`)
  - Dispatch shape and mapping (update tests when changing provider mappings)
- Integration tests:
  - Endpoint flow for `/api/v1/chat/completions` (`tests/Chat/test_chat_completions_integration.py`, `tests/Chat/test_chat_endpoint.py`)
  - Streaming normalization (`tests/Chat/test_chat_endpoint_streaming_normalization.py`)
  - Consider provider mocks for deterministic behavior

## Maintenance Notes

- Treat `provider_config.py` as authoritative for handler/parameter mappings going forward; avoid duplicating translation in provider call sites. The legacy duplicate in `Chat_Functions.py` has been removed to prevent drift.
- Log safe: escape curly braces and large payloads before logging (see existing patterns in exception handling).
- Preserve OpenAI response compatibility in streaming and non‑streaming outputs to avoid client regressions.
- Be careful when altering schema constraints; downstream clients (UI and tools) rely on them.

Additional endpoint behavior to note:
- Non‑stream responses include `tldw_conversation_id` in the JSON body for ease of client‑side state tracking.

---

For design changes, include a short proposal under `Docs/Design/` and link to affected providers and endpoints.
