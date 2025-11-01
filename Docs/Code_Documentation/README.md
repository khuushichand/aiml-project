Code Documentation

Purpose
- High-level code map and extension notes for the API, chat/streaming, moderation/guardrails, metrics, audit, and WebUI admin pieces.
- Complements feature docs in Docs/; see also Docs/Moderation-Guardrails.md.

Entry Points
- FastAPI app: tldw_Server_API/app/main.py
  - Includes core routers under prefix /api/v1
  - Tags: health, moderation, authentication, users, media, audio, etc.

Key Directories
- tldw_Server_API/app/api/v1/endpoints/
  - chat.py: Chat Completions endpoint (OpenAI compatible).
  - moderation.py: Admin endpoints for moderation (policy/effective, reload, blocklist managed, user overrides, runtime settings, tester).
  - health.py: Basic health and CSRF setup used by tests.
- tldw_Server_API/app/core/Chat/
  - streaming_utils.py: Normalizes upstream SSE, emits heartbeats, enforces timeouts. Always emits final `data: [DONE]` on normal end.
  - chat_metrics.py: Prometheus/OpenTelemetry metrics registry and helpers (request metrics, streaming metrics, moderation metrics).
  - chat_orchestrator.py, provider_config.py, provider_manager.py: LLM provider integrations (Chat_Functions.py now serves only as a minimal compatibility shim).
- tldw_Server_API/app/core/Moderation/
  - moderation_service.py: Central moderation/guardrails engine and persistence helpers.
- tldw_Server_API/app/core/Audit/
  - unified_audit_service.py: Audit event logging, PII detector, and daily stats.
- tldw_Server_API/WebUI/
  - tabs/admin_content.html: Admin Moderation tab sections and JS helpers.
  - js/api-client.js: Frontend API client used by the Admin UI.

Chat Flow (Non-Streaming)
1) Validate request (size, images, limits) in chat.py
2) Moderation input pass
   - ModerationService.get_effective_policy(user_id)
   - evaluate_action(text, policy, 'input') → (action, redacted?, pattern, category?)
   - track_moderation_input(user_id, action, category)
3) LLM call (perform_chat_api_call)
4) Moderation output pass (non-stream)
   - evaluate_action(text, policy, 'output')
   - Block → 400; Redact → persist redacted version; Warn/Pass → unchanged
5) Persist to DB and return JSON

Chat Flow (Streaming, SSE)
1) Upstream generator from LLM provider
2) streaming_utils.create_streaming_response_with_timeout wraps the generator
   - Normalized lines: text deltas → `data: {"choices":[{"delta":{"content":"..."}}]}`
   - Heartbeats (event: comment) and idle timeout
3) Optional text_transform applies output moderation per delta
   - Redact: replaces text
   - Block: raises StopStreamWithError → emits SSE error and `data: [DONE]`
4) Always emits final `data: [DONE]` on normal completion

Moderation/Guardrails
- moderation_service.ModerationPolicy
  - enabled, input_enabled, output_enabled
  - input_action/output_action: block | redact | warn (defaults)
  - redact_replacement
  - block_patterns: list of PatternRule
  - categories_enabled: Optional[set[str]]
- moderation_service.PatternRule
  - regex: compiled re.Pattern
  - action: Optional[str] per pattern
  - replacement: Optional[str] (used when action=redact)
  - categories: Optional[set[str]] (e.g., {"pii","pii_email"})
- Extended blocklist line grammar (see Docs/Moderation-Guardrails.md):
  - literal
  - /regex/
  - literal -> block|warn
  - literal -> redact:[REPL]
  - /regex/ -> block|warn|redact:[REPL] #cat1,cat2
- Decision API: evaluate_action(text, policy, phase)
  - Returns (action, redacted_text?, matched_pattern?, category?)
  - Applies categories_enabled gating and per-pattern overrides; obeys scan budgets and replacement limits.

Runtime Overrides & Persistence
- Runtime overrides file (JSON): default tldw_Server_API/Config_Files/moderation_runtime_overrides.json
  - keys: {"pii_enabled": bool, "categories_enabled": ["pii","confidential"]}
- Service loads overrides on startup and on reload(); rebuilds policy.
- Admin endpoints (`/api/v1/moderation/settings`) allow updating overrides at runtime and persisting to file.

Admin Endpoints Summary (moderation.py)
- GET /api/v1/moderation/policy/effective?user_id=U: Effective policy snapshot
- POST /api/v1/moderation/reload: Reload config + overrides
- GET /api/v1/moderation/blocklist/managed → {version, items} (ETag)
- POST /api/v1/moderation/blocklist/append (If-Match): Append
- DELETE /api/v1/moderation/blocklist/{id} (If-Match): Delete
- GET /api/v1/moderation/users: List per-user overrides
- GET/PUT/DELETE /api/v1/moderation/users/{user_id}
- POST /api/v1/moderation/test: Try text against effective policy
- GET/PUT /api/v1/moderation/settings: Runtime overrides (optional persist)

Metrics & Audit
- Metrics (chat_metrics.py)
  - chat_moderation_input_flag_total{user_id,action,category}
  - chat_moderation_output_redact_total{user_id,category,streaming}
  - chat_moderation_output_block_total{user_id,category,streaming}
  - chat_moderation_stream_block_total{user_id,category}
  - Category prefers specific subtype (e.g., pii_email) when available
- Audit (unified_audit_service)
  - SECURITY_VIOLATION events on moderation actions with metadata {phase, action, pattern, streaming?}

Testing
- Chat moderation integration tests:
  - tldw_Server_API/tests/Chat_NEW/integration/test_moderation.py
  - tldw_Server_API/tests/Chat_NEW/integration/test_moderation_categories.py
- Run:
  - `python -m pytest -q tldw_Server_API/tests/Chat_NEW/integration/test_moderation.py`
  - `python -m pytest -q tldw_Server_API/tests/Chat_NEW/integration/test_moderation_categories.py`

Extensibility Notes
- Add new categories via blocklist lines with `#category` or by extending built-in rules in moderation_service.
- To persist per-user categories, update their override with `categories_enabled` (comma-separated or list).
- To integrate external moderation services, wrap results into PatternRule or extend evaluate_action to consult providers.

Related Docs
- Moderation/Guardrails details: Docs/Moderation-Guardrails.md

Audit Export API
- Endpoint: `GET /api/v1/audit/export` (admin only; single-user mode treats the sole user as admin)
- Purpose: Export audit logs as JSON or CSV for analysis/compliance
- Query params:
  - `format`: `json` | `csv` (default: `json`)
  - `start_time`, `end_time`: ISO8601 timestamps (e.g., `2025-01-01T00:00:00Z`)
  - `event_type`: list of event types (enum name like `AUTH_LOGIN_SUCCESS` or value like `auth.login.success`)
  - `category`: list of categories (enum name or value)
  - `min_risk_score`: integer threshold
  - `user_id`, `request_id`, `correlation_id`: filters
  - `filename`: override attachment name
- Example:
  - `GET /api/v1/audit/export?format=csv&category=API_CALL&min_risk_score=70&start_time=2025-01-01T00:00:00Z`
  - Returns `text/csv` with `Content-Disposition: attachment; filename=audit_export.csv`
