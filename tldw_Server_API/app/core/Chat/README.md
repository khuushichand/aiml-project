# Chat Module (Developer Guide)

The Chat module powers the `/api/v1/chat/completions` endpoint, orchestrating request validation, prompt templating, provider routing, streaming, auditing, and persistence. This document summarizes the current architecture and the responsibilities of each submodule so you can extend the stack confidently.

---

## Responsibilities at a Glance
- Normalize chat requests (character context, conversations, prompt templates, moderation).
- Apply rate limits, request queuing, and usage tracking before hitting LLM providers.
- Dispatch to 15+ commercial and local providers (sync + async) with consistent error handling.
- Stream results safely back to clients (SSE) while persisting transcripts and metadata.
- Expose metrics, auditing hooks, and document-generation utilities built on conversation history.

---

## Module Map
| File / Folder | Purpose |
| --- | --- |
| `chat_orchestrator.py` | Single entry point for provider calls (`chat_api_call`, `chat_api_call_async`). Maps generic parameters to provider-specific handlers defined in `provider_config`. |
| `chat_service.py` | High-level helpers used by the FastAPI endpoint: request normalization, moderation, persistence, logging, streaming orchestration. |
| `chat_helpers.py` | Validation, character + conversation loading/creation, history assembly, ensuring default persona, etc. |
| `prompt_template_manager.py` + `prompt_templates/` | Jinja2-based templating for system/user/assistant messages with sandboxed rendering and bundled defaults. |
| `provider_config.py` | Declarative provider handler map, async support, and parameter translation tables. |
| `provider_manager.py` | Circuit breaker + health tracking for providers; used for fallback and observability scenarios. |
| `rate_limiter.py` | Token-bucket rate limiter covering global, per-user, per-conversation, and token budgets. |
| `request_queue.py` | Priority queue with backpressure, streaming pipe support, and worker pool management. |
| `streaming_utils.py` | SSE utilities (heartbeat, idle timeout, chunk normalization, cancellation). |
| `chat_metrics.py` | Prometheus/OpenTelemetry metric definitions specific to chat workflows. |
| `Chat_Functions.py` | Backwards-compatible shim that now only exposes `chat`, `chat_api_call`, `DEFAULT_CHARACTER_NAME`, and `approximate_token_count`; import other helpers from their dedicated modules. |
| `chat_exceptions.py` / `Chat_Deps.py` | Exception types used across the stack for consistent error handling. |
| `chat_metrics.py`, `document_generator.py`, `Workflows.py` | Secondary features: telemetry, document production, and workflow automation (delegating to `chat_orchestrator`). |

---

## Request Lifecycle
```
FastAPI endpoint (app/api/v1/endpoints/chat.py)
      │
      ├─► `chat_helpers.validate_request_payload`
      │       (size, multimedia, schema)
      │
      ├─► `chat_service.normalize_request_provider_and_model`
      │       (provider override prefixes, default provider enforcement)
      │
      ├─► Rate limiting (`ConversationRateLimiter`) + queue admission
      │       └─ `RequestQueue` (optional priority/backpressure)
      │
      ├─► Character + conversation context (`chat_helpers.get_or_create_*`)
      │       └─ falls back to default persona if no character supplied
      │
      ├─► Prompt templating (`prompt_template_manager`, `replace_placeholders`)
      │
      ├─► Moderation / topic monitoring hooks
      │
      ├─► Provider call
      │       └─ `chat_service.build_call_params_from_request`
      │       └─ `chat_orchestrator.chat_api_call` or async variant
      │                ◦ parameter translation via `PROVIDER_PARAM_MAP`
      │                ◦ handler from `API_CALL_HANDLERS`
      │
      ├─► Streaming or blocking response handling (`streaming_utils`)
      │
      ├─► Post-processing
      │       └─ persistence (conversation, messages)
      │       └─ usage logging (`Usage.usage_tracker.log_llm_usage`)
      │       └─ audit log (`AuditEventType`)
      │       └─ metrics (`chat_metrics.ChatMetricsCollector`)
      │
      └─► Response to client (JSON or SSE)
```

---

## Provider & Resiliency Layer
- Handlers live in `tldw_Server_API.app.core.LLM_Calls.*` and are mapped via `provider_config.API_CALL_HANDLERS` (sync) and `ASYNC_API_CALL_HANDLERS`.
- `PROVIDER_PARAM_MAP` translates neutral `chat_api_call` kwargs to provider-specific names (e.g., `stop` → `stop_sequences` for Anthropic).
- `provider_manager.ProviderManager` tracks success/failure counts, response times, and integrates circuit breakers (`CircuitBreaker`) for degraded providers. Fallback logic is typically applied in the endpoint/service layer.
- Dynamic API keys are merged with module-level overrides via `chat_service.merge_api_keys_for_provider`, honouring providers that require a key.

---

## Rate Limiting & Queuing
- `ConversationRateLimiter` implements layered token buckets:
  - Global RPM
  - Per-user RPM and per-user tokens/minute
  - Per-conversation RPM
  - Burst tolerances via configurable multiplier
- `RequestQueue` offers optional backpressure for heavy deployments. It supports priority levels (`RequestPriority`), pluggable processors, and streaming channels.
- Both components expose metrics and error messages used by the FastAPI endpoint to return `429` or `503` responses.

---

## Prompt Templates
- Templates reside under `prompt_templates/*.json` and are loaded via `load_template`. The path is sandboxed to prevent traversal.
- Models: `PromptTemplate`, `PromptTemplatePlaceholders` (Pydantic). Sandboxed Jinja environment (`safe_render`) prevents template injection.
- Defaults: `DEFAULT_RAW_PASSTHROUGH_TEMPLATE` ensures there is always a no-op template when none is selected.
- `apply_template_to_string` is used when constructing final system/user messages just before sending to providers.

---

## Streaming & Moderation
- `streaming_utils.StreamingResponseHandler` wraps provider streams, tracks heartbeats, enforces idle timeout, enforces max response size, and handles provider-specific SSE normalization (`_extract_text_from_upstream_sse`).
- Moderation and topic monitoring services (`Moderation.moderation_service`, `Monitoring.topic_monitoring_service`) are invoked from `chat_service.moderate_input_messages` and post-response redaction hooks.
- Streaming responses integrate with FastAPI via `create_streaming_response_with_timeout`.

---

## Persistence & Document Generation
- `chat_helpers.get_or_create_conversation` stores transcript metadata in `ChaChaNotes_DB`.
- `chat_service.save_conversation_message` (see file) persists message payloads, with placeholder resolution and per-message metadata.
- `document_generator.DocumentGeneratorService` uses chat history to produce timeline, study guide, briefing, summary, Q&A, and meeting notes documents, delegating to `chat_orchestrator.chat_api_call`.
- `Workflows.py` calls into `chat_orchestrator.chat` to execute legacy scripted flows without relying on deprecated `App_Function_Libraries` paths.

---

## Metrics & Logging
- Metrics enumerated in `chat_metrics.ChatMetricsCollector` feed OpenTelemetry meters (`chat_requests_total`, streaming stats, tokens, DB operations, moderation outcomes).
- Loguru is used throughout for structured logging; metrics and audit hooks provide provider/model labels for downstream dashboards.
- Usage tracking integrates with `Usage.usage_tracker` to record per-call token/cost estimates.

---

## Configuration & Settings
- Provider defaults and fallbacks read from `Config_Files/config.txt` via `config.load_and_log_configs()` and `provider_config`.
- Rate limiter defaults are set in `rate_limiter.RateLimitConfig`; override via environment variables or injecting custom configs when instantiating the limiter.
- Streaming idle/heartbeat intervals are read from the `[Chat-Module]` section in the config file (see `streaming_utils` constants).
- Prompt template directory is relative to the module but can be extended by writing new JSON files.

---

## Testing
Recommended suites after modifying chat logic:
```bash
python -m pytest tldw_Server_API/tests/Chat -v
python -m pytest tldw_Server_API/tests/Character_Chat_NEW/unit/test_chat_dictionary_unit.py -v
python -m pytest tldw_Server_API/tests/integration/test_phase1_integration.py -k chat -v
```
Key coverage:
- Unit tests around request validation/rate limiter (`tests/unit/test_character_rate_limiter.py`, shared patterns).
- Integration tests covering the `/chat/completions` pipeline (mocked providers).
- Provider-specific contract tests in `tldw_Server_API/tests/LLM_Calls/*` (ensure parameter maps stay aligned).

Set `TEST_MODE=1` in the environment when running tests to disable background loops (queue workers, provider health checks) that assume a long-running process.

---

## Extending the Module
1. **Add a new provider**: implement handler(s) in `LLM_Calls`, register sync/async functions in `provider_config.API_CALL_HANDLERS`, and map parameters in `PROVIDER_PARAM_MAP`. Update tests to cover the new provider.
2. **Adjust request processing**: modify `chat_service` or `chat_helpers`; keep endpoint logic thin and maintain placeholder, template, and moderation flows.
3. **Enhance rate limiting**: extend `RateLimitConfig` and the FastAPI dependency that instantiates `ConversationRateLimiter`. Ensure metrics reflect new counters.
4. **Introduce new templates**: drop JSON files into `prompt_templates/` and reference them in requests via `prompt_template_name`.
5. **Streaming changes**: update `StreamingResponseHandler` to handle new SSE formats; keep `_extract_text_from_upstream_sse` tolerant to provider quirks.
6. **Document generator**: extend `DocumentType` and default prompts, ensure chat history retrieval is efficient (batch DB reads).

Always update this README and `REFACTORING_PLAN.md` when architectural decisions change. Treat `Chat_Functions.py` as a minimal compatibility shim; import from the focused modules (`chat_orchestrator`, `chat_history`, `chat_dictionary`, `chat_characters`) for new work and plan to retire the shim once remaining callers migrate.

---

## Quick Reference Snippets
```python
# Dispatch a provider call programmatically
from tldw_Server_API.app.core.Chat.chat_orchestrator import chat_api_call
response = chat_api_call(
    api_endpoint="openai",
    messages_payload=[{"role": "user", "content": "Hello!"}],
    api_key="sk-...",
    model="gpt-4o-mini",
    temp=0.7,
    streaming=False,
)

# Apply a prompt template
tmpl = load_template("my_custom_template")
templated_system = apply_template_to_string(tmpl.system_message_template, data)

# Enforce chat rate limits
allowed, err = await conversation_rate_limiter.check_rate_limit(
    user_id="user_123",
    conversation_id="conv_456",
    estimated_tokens=512,
)

# Queue a request (when using RequestQueue)
queue = get_request_queue()
future = await queue.enqueue(request_id="req-1", request_data=request_obj, priority=RequestPriority.HIGH)
result = await future
```

With this guide, you should be able to navigate the Chat module quickly, identify where a behaviour lives, and implement changes without breaking the larger orchestration. Keep the provider abstraction, rate limiting, and streaming guarantees front of mind when extending functionality.
