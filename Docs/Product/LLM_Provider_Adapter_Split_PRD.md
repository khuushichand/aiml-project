# LLM Provider Adapter Split – Developer PRD

## 1. Background
- Current state: commercial and local providers are implemented in monolithic modules that mix request shaping, streaming, error mapping, and config handling.
  - Commercial: `tldw_Server_API/app/core/LLM_Calls/legacy_chat_calls.py:1`
  - Local: `tldw_Server_API/app/core/LLM_Calls/legacy_local_calls.py:1`
- Problems observed:
  - Large branching blocks per provider; repeated logic for streaming SSE normalization, tool_choice gating, error normalization, base URL resolution, and timeouts.
  - Hard to add/modify providers safely; test surface area is broad and entangled.
  - Async/sync paths diverge across functions; reuse of common streaming code is inconsistent.
- Precedent: The TTS module already solved this with adapters + registry
  - Registry: `tldw_Server_API/app/core/TTS/adapter_registry.py`
  - Adapters: `tldw_Server_API/app/core/TTS/adapters/*`
  - Centralized resource/circuit breaker helpers and clear capability surfaces.
- Existing reusable building blocks for LLMs:
  - SSE normalization utilities: `tldw_Server_API/app/core/LLM_Calls/sse.py`
  - Streaming helpers: `tldw_Server_API/app/core/LLM_Calls/streaming.py`
  - HTTP client & SSE streaming: `tldw_Server_API/app/core/http_client.py`
  - Provider health/fallback shell: `tldw_Server_API/app/core/Chat/provider_manager.py`
  - Provider param map & legacy dispatch: `tldw_Server_API/app/core/Chat/provider_config.py`

## 2. Problem Statement
The monolithic `legacy_chat_calls.py` and its local analog contain hundreds of lines of provider-specific branching and duplicated streaming/error/parameter handling. This raises maintenance cost, increases regression risk, and slows provider onboarding. We need a pluggable provider adapter architecture that mirrors the TTS pattern, with a registry and small, focused provider modules.

## 3. Objectives & Success Criteria
- Extract provider-specific logic into small adapters under `LLM_Calls/providers/*`, each implementing a unified `ChatProvider` interface.
- Introduce an adapter registry that surfaces:
  - Capabilities (streaming, tools, vision, JSON mode, max token hints)
  - Base URLs and auth requirements
  - Error mapping hooks
  - Streaming hooks that reuse `sse.py` and `streaming.py`
- Preserve API compatibility for existing endpoints and orchestrators:
  - `POST /api/v1/chat/completions` continues to work
  - Legacy function entry points remain as thin wrappers during transition
- Unify error normalization and tool_choice gating in one place.
- Share the centralized HTTP client / SSE helper and circuit-breaker integration.

Success metrics
- Provider onboarding time reduced to ≤1 day for typical OpenAI-compatible providers.
- Code reduction: ≥30% fewer lines in `legacy_chat_calls.py` and `legacy_local_calls.py` by removing branching.
- Test coverage ≥80% for new registry + adapters; all existing LLM tests pass.
- Zero API behavior regressions in `/api/v1/chat/completions` happy-path tests, including streaming.

## 4. Scope
In scope (Phase 1–4)
- Define `ChatProvider` interface and minimal core types (request, response, stream iterators) in `LLM_Calls/providers/base.py`.
- Implement adapter registry in `LLM_Calls/adapter_registry.py` (mirrors TTS): lazy loading by dotted path, capability discovery.
- Extract adapters for top providers used in tests and defaults: OpenAI, Anthropic, Groq, OpenRouter, Google (Gemini), Mistral, HuggingFace, Qwen, DeepSeek, plus a generic OpenAI-compatible adapter used by several custom/local servers.
- Move streaming normalization to a shared path via `sse.py` and `streaming.py`; remove per-provider ad-hoc parsing.
- Centralize error mapping and tool_choice gating utilities.
- Keep legacy dispatch in `provider_config.py` by routing to registry-backed `chat()`/`achat()` wrappers to avoid endpoint changes.
- Update `GET /api/v1/llm/providers` to draw capabilities from the registry (keeping existing metadata shape).
- Add embeddings adapters + registry for OpenAI/HuggingFace/Google and wire the endpoint behind `LLM_EMBEDDINGS_ADAPTERS_ENABLED=1`.

Out of scope (for initial rollout)
- New fallback selection algorithms or large changes to `provider_manager.py` behavior.
- Changes to public API schemas for chat/embeddings requests.
- Provider-specific advanced features not currently supported (vision upload pipelines, files API, advanced JSON schemas).
- Embeddings expansion beyond OpenAI/HuggingFace/Google (additional providers and advanced features).

## 5. Architecture Overview
Components
1. API Layer (unchanged): `tldw_Server_API/app/api/v1/endpoints/chat.py`
   - Builds request payloads, rate limits, and streams responses to clients.
2. Orchestrator/Service Layer (unchanged shape): continues to call into provider dispatch, which is refactored to delegate to the adapter registry.
3. Adapter Registry: `tldw_Server_API/app/core/LLM_Calls/adapter_registry.py`
   - Registers providers via dotted paths; lazily constructs adapters with merged config; exposes `get_adapter(name)` and `get_all_capabilities()`.
4. Base Adapter Interface: `tldw_Server_API/app/core/LLM_Calls/providers/base.py`
   - Defines `ChatProvider` with `chat()`, `stream()`, and optional `achat()`/`astream()` plus `capabilities()` and `normalize_error()`.
5. Provider Adapters: `tldw_Server_API/app/core/LLM_Calls/providers/*.py`
   - Self-contained logic per provider: auth, base URL, payload shaping, error mapping, and streaming using shared helpers.
6. Shared Utilities: reuse existing `sse.py`, `streaming.py`, and `http_client.py`.
7. Circuit Breaker Integration: reuse `provider_manager.py` hooks (record success/failure) and/or leverage existing breaker in Evaluations for future consolidation.

## 6. Interfaces
ChatProvider (Python Protocol or base class)
```python
class ChatProvider(Protocol):
    name: str

    def capabilities(self) -> Dict[str, Any]:
        # {"supports_streaming": True, "supports_tools": True, ...}
        ...

    def chat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        # Returns OpenAI-compatible non-streaming chat completion
        ...

    def stream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Iterable[str]:
        # Yields OpenAI-compatible SSE strings; final [DONE] handled by caller via finalize_stream()
        ...

    async def achat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        ...

    async def astream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> AsyncIterator[str]:
        ...

    def normalize_error(self, exc: Exception) -> ChatAPIError:
        # Map provider exceptions to project Chat*Error types
        ...
```

Request/Response contracts
- Adapters accept already-normalized, OpenAI-like request dicts from the orchestrator.
- Adapters return OpenAI-compatible `chat.completion` JSON for non-streaming and SSE lines for streaming (using `sse_data(...)` frames and `finalize_stream()` at the end by callers).

Tool choice gating
- Provide a shared helper `apply_tool_choice(payload, tools, tool_choice)` that safely sets tool choice only when supported.
- Present in a dedicated utility module used by all adapters to avoid drift.

## 7. Error Mapping
- Central helper converts `requests/httpx` errors and provider JSON error shapes into `ChatAuthenticationError`, `ChatRateLimitError`, `ChatBadRequestError`, `ChatProviderError`, or `ChatAPIError`.
- Adapters call `normalize_error()` when catching provider exceptions; endpoints retain current error-to-HTTP mapping.

## 8. Streaming Normalization
- All adapters must yield normalized SSE via `normalize_provider_line()` and suppress provider-sent `[DONE]` frames.
- Streaming over `httpx` leverages `aiter_sse_lines_httpx()` and `astream_sse()` from `http_client.py` when available; sync paths use `iter_sse_lines_requests()` where applicable.
- A single final `sse_done()` is appended by the orchestrator using `finalize_stream()` to avoid duplicates.

## 9. Configuration
- Adapters resolve config from `load_and_log_configs()`/env, mirroring current semantics (API keys, base URLs, defaults).
- Registry exposes `get_all_capabilities()` for `GET /api/v1/llm/providers`, merging static metadata and adapter-reported capabilities.
- Preserve existing env var overrides (e.g., `OPENAI_API_BASE`, `MOCK_OPENAI_BASE_URL`).

## 10. Migration Plan
Phase 0: Scaffolding
- Add `providers/base.py` with `ChatProvider` interface and small common utils (tool_choice helper).
- Add `adapter_registry.py` with lazy import, status cache, and capability discovery (modeled on TTS registry).

Phase 1: First adapter + shim
- Implement `openai_adapter.py`; route `provider_config.API_CALL_HANDLERS['openai']` to the registry-backed adapter.
- Keep legacy functions (`chat_with_openai`, etc.) as thin wrappers, delegating to adapters.
- Ensure streaming parity by reusing `sse.py` and `streaming.py`.

Phase 2: Core providers
- Port Anthropic, Groq, OpenRouter, Google (Gemini), Mistral.
- Update `llm_providers.py` endpoint to use registry for capability flags.

Phase 3: Remaining providers + cleanup
- Port Qwen, DeepSeek, HuggingFace, and generic OpenAI-compatible adapter used by local/custom servers.
- Remove large branching from `legacy_chat_calls.py` and `legacy_local_calls.py`; leave compatibility wrappers that call the registry.

Phase 4: Embeddings adapters
- Implement embeddings adapters (via `EmbeddingsProvider`) and wire the endpoint behind `LLM_EMBEDDINGS_ADAPTERS_ENABLED=1`, preserving legacy behavior when disabled.

Current Status (Nov 2025)
- Adapters & shims (implementation complete; verification pending)
  - Chat adapters implemented: OpenAI, Anthropic, Groq, OpenRouter, Google (Gemini), Mistral, Qwen, DeepSeek, HuggingFace, Custom OpenAI (v1/v2).
  - Async adapter routing wired for OpenAI, Anthropic, Groq, OpenRouter plus Stage 3 providers (Qwen/DeepSeek/HF/Custom OpenAI).
  - Endpoint providers capability merge uses adapter registry; shape validated by unit test.
- Native HTTP (implementation complete; verification pending)
  - Feature-flagged native httpx paths for OpenAI/Anthropic/Groq/OpenRouter/Google/Mistral; default remains delegate-first.
- Tests (local runs; CI and full-suite verification pending)
  - Adapters unit: 44 passed (STREAMS_UNIFIED=1, LLM_ADAPTERS_ENABLED=1).
  - OpenAI async streaming via orchestrator now passes (fixed in async shim by honoring monkeypatched legacy during streaming; verified on test slice `tldw_Server_API/tests/LLM_Adapters/integration/test_async_adapters_orchestrator.py::test_chat_api_call_async_streaming`).
  - Embeddings adapters: OpenAI/HF/Google wired with unit coverage; endpoint adapter path tested (multi-input + optional L2).
- CI (jobs added; green status not yet verified)
  - llm-adapters-suites: runs unit + subset of integration adapter tests with adapters enabled.
  - llm-adapters-native-matrix: per‑provider native-http unit slices with feature flags.
- Cleanup (pending)
  - Stage 3 monolith cleanup not complete: provider branching removal and helper centralization still pending per checklist.
  - Definition of Done remains unchecked until Stage 0 verification (import sanity check, CI green, full test suite) and Stage 3 cleanup complete.

Latest Changes (Nov 04, 2025)
- Fixed OpenAI async streaming route: async shim now yields SSE lines when legacy is monkeypatched in tests (no network), resolving the prior failure.
- Began monolith cleanup: added deprecation banner to `legacy_chat_calls.py` and preserved thin wrappers; deeper branch pruning staged post-CI stability.
- Action item: re-enable the previously skipped async streaming test in CI after a broader adapter integration run.

Remaining Work
- Incrementally flip native HTTP flags per provider in CI as suites remain green; then prune provider-specific branches in legacy modules.
- Broaden async tests for Stage 3 providers when native AsyncClient paths are introduced (optional).
- Expand embeddings adapters to more providers as needed and add error‑path tests.

## 11. Backward Compatibility
- Public FastAPI endpoints unchanged; request/response schema remains OpenAI-compatible.
- Legacy `provider_config.API_CALL_HANDLERS` continue to exist, delegating to the registry, so orchestrators and tests remain intact.
- Keep current config keys and env var precedence; deprecate only internal call paths.

## 12. Testing Strategy
- Unit tests
  - Registry init, capability discovery, and adapter lazy loading.
  - Adapter error mapping: map representative provider error JSON/statuses to Chat*Error types.
  - Streaming: ensure `[DONE]` handling, `normalize_provider_line()` behavior, and SSE frame structure.
  - Tool choice gating correctness.
- Integration tests (httpx/requests mocked)
  - `POST /api/v1/chat/completions` non-streaming and streaming across at least OpenAI, Anthropic, Groq, OpenRouter.
  - Ensure legacy tests under `tldw_Server_API/tests/LLM_Calls/` continue to pass.
  - Mock server parity via `mock_openai_server/` where applicable.
- Performance smoke
  - Compare latency and CPU utilization against baseline for streaming and non-streaming requests.

## 13. Metrics & Observability
- Log provider selection and timing at DEBUG without leaking prompt content (continue using `_sanitize_payload_for_logging`).
- Optional adapter-level counters: calls, failures by error class, average response duration.
- Reuse http_client metrics; integrate provider health with `provider_manager.record_success/record_failure`.

## 14. Risks & Mitigations
- Regression in streaming edge cases across providers
  - Mitigation: shared streaming helpers + adapter conformance tests and property tests for SSE framing.
- Hidden coupling to legacy function signatures
  - Mitigation: keep wrappers and use provider_config param map for argument translation during transition.
- Config drift between adapters
  - Mitigation: unify base URL and auth key resolution in shared helpers; document required keys per adapter.
- Test brittleness (network)
  - Mitigation: rely on `httpx` mocking and `mock_openai_server`; ensure CI network-off safe.

## 15. Rollout Plan & Timeline (estimate)
- Week 1: Scaffolding + OpenAI adapter + shim routing, green tests.
- Week 2: Anthropic, Groq, OpenRouter, registry capabilities wiring, providers endpoint updates.
- Week 3: Google, Mistral, Qwen, HuggingFace, DeepSeek; delete major branching in legacy files, keep wrappers.
- Week 4: Stabilization, docs, performance baseline comparison; validate embeddings adapter rollout.

## 16. Acceptance Criteria
- Registry and base adapter modules exist; all in-scope chat adapters (OpenAI, Anthropic, Groq, OpenRouter, Google, Mistral, Qwen, DeepSeek, HuggingFace, Custom OpenAI) are implemented and covered by tests.
- `/api/v1/chat/completions` works for streaming and non-streaming paths with no behavioral regressions in existing tests.
- `GET /api/v1/llm/providers` returns capability info sourced from the registry.
- Code reduction achieved in monolithic files; obvious duplicated streaming/error logic removed.
- Embeddings adapters for OpenAI/HuggingFace/Google are wired behind `LLM_EMBEDDINGS_ADAPTERS_ENABLED=1` with endpoint parity tests.
- Documentation updated: this PRD, adapter authoring guide, and migration notes.

## 17. Deliverables
- Code: `LLM_Calls/providers/*`, `LLM_Calls/adapter_registry.py`, updated legacy wrappers.
- Tests: unit + integration under `tldw_Server_API/tests/LLM_Calls/` following existing markers.
- Docs: this PRD plus a short "Adding a new LLM adapter" guide in `Docs/Design/`.

## 18. Deletions & Cleanup (after Phase 3)
- Remove provider-specific branching from `legacy_chat_calls.py` and `legacy_local_calls.py`.
- Consolidate tool_choice handling and error normalization into shared helpers; delete scattered duplicates.
- Keep thin compatibility wrappers only where needed by imported call sites.
- Status: initial pass started (deprecation banner added; wrappers preserved); deeper branch pruning pending CI stability.

## 19. Open Questions
- Should embeddings be part of the same adapter registry or a sibling `EmbeddingsProvider` with shared config?
- Do we want provider-level retry policies configurable via registry (override http_client defaults)?
- Unify circuit breaker implementation across Chat/TTS/Evals into a single shared component?
- Any providers requiring non-HTTP transport (e.g., gRPC) in near term?

## 20. Implementation Guide & Checklist

This guide breaks implementation into clear, verifiable stages. Checkboxes are maintained as a living status view and should reflect current completion.

Stage 0: Scaffolding (foundation)
- [x] Add adapter base and helpers: `LLM_Calls/providers/base.py` (ChatProvider, error mapping, tool_choice helper)
- [x] Add adapter registry: `LLM_Calls/adapter_registry.py` with lazy loading, capability discovery, singleton accessor
- [x] Authoring guide in `Docs/Design/LLM_Adapters_Authoring_Guide.md`
- [ ] Import sanity check: registry import causes no cycles in API layers
- [ ] CI green with no behavior changes

Verification
- [ ] `python -m pytest -m "unit or integration" -q` passes
- [ ] Lint/formatters (if configured) show no new warnings

Stage 1: OpenAI adapter + shim
- [x] Implement `providers/openai_adapter.py` with:
  - [x] Base URL resolution precedence (config/env -> default `https://api.openai.com/v1`)
  - [x] Auth header handling and safe header redaction in logs
  - [x] Non-streaming `chat()` returning OpenAI-compatible `chat.completion`
  - [x] Streaming `stream()` using `iter_sse_lines_requests`/`aiter_sse_lines_httpx` and `sse.py`
  - [x] Error mapping: auth (401/403), rate limit (429), bad request (400/404/422), provider 5xx
  - [x] Tool choice gating via shared helper
  - [x] Sanitized payload logging using existing `_sanitize_payload_for_logging` where applicable
- [x] Wire shim: make `provider_config.API_CALL_HANDLERS['openai']` delegate to registry-backed adapter; preserve function signature
- [x] Tests
  - [x] Unit: adapter non-streaming success, error cases
  - [x] Unit: streaming yields valid SSE chunks and omits provider `[DONE]`
  - [x] Integration: `/api/v1/chat/completions` for OpenAI non-streaming/streaming (httpx mocked or `mock_openai_server`)
- [x] Docs: update PRD status and add adapter-specific notes if needed
- [x] Async shim fix: honor monkeypatched legacy during streaming (yields SSE lines); passes orchestrator async streaming test slice

Stage 2: Core providers (Anthropic, Groq, OpenRouter, Google, Mistral)
- [x] Implement adapters with provider-specific payload shaping and streaming
  - Anthropic: messages/parts conversion, `stop_sequences`, tool_use mapping
  - Groq: OpenAI-compatible; ensure base URL/config and logit_bias/logprobs mapping
  - OpenRouter: top_p/top_k/min_p mapping, per-model routing if needed
  - Google (Gemini): `generationConfig`, parts, `stopSequences`, images/files where minimally necessary
  - Mistral: `random_seed`, `top_k`, tools
- [x] Add registry registrations (by init or a central bootstrap)
- [x] Tests per provider (unit + endpoint-level integration with mocks)
- [x] Providers endpoint: aggregate capabilities from registry and merge with existing `MODEL_METADATA` where applicable

Stage 3: Remaining providers + monolith cleanup
- [x] Implement Qwen, DeepSeek, HuggingFace, generic OpenAI-compatible (for local/custom servers)
- [x] Route `provider_config` handlers to adapters for all migrated providers
- [ ] Remove provider-specific branching from `legacy_chat_calls.py` and `legacy_local_calls.py`, keeping thin wrappers only
- [ ] Centralize tool_choice and error normalization (delete duplicates in monolith)
- [ ] Re-run entire LLM test suite including `tests/LLM_Calls/test_async_streaming_dedup.py` and strict filter tests

Stage 4: Embeddings adapters (scaffold → endpoint wiring)
- [x] Add `EmbeddingsProvider` to base interface (`providers/base.py`).
- [x] Create `embeddings_adapter_registry.py` with `get_embeddings_registry()`.
- [x] Implement `providers/openai_embeddings_adapter.py` (delegate-first; optional native HTTP behind `LLM_EMBEDDINGS_NATIVE_HTTP_OPENAI`).
- [x] Wire adapter path into `POST /api/v1/embeddings` (enhanced v5 endpoint) behind feature flag `LLM_EMBEDDINGS_ADAPTERS_ENABLED=1`.
  - When enabled, route via registry adapter for supported providers and map response to OpenAI-compatible shape.
  - Preserve existing behavior (circuit breaker, batching, caching) when flag is disabled.
- [x] Add minimal unit test that exercises the adapter-backed endpoint with a stub adapter.
- [x] Extend registry with HF/Google embeddings adapters: `providers/huggingface_embeddings_adapter.py`, `providers/google_embeddings_adapter.py`.
- [x] Add native HTTP unit tests for HuggingFace and Google embeddings (mocked httpx).
- [x] Add endpoint unit test for multiple inputs and optional L2 normalization under `LLM_EMBEDDINGS_L2_NORMALIZE=1`.

Stage 5: Embeddings expansion (future)
- [ ] Expand embeddings adapters to additional providers beyond OpenAI/HuggingFace/Google
- [ ] Add advanced embeddings features (e.g., provider-specific batching, dimensions overrides) where needed
- [ ] Extend endpoint parity tests for new providers/features

Observability, Health, and Operations
- [ ] Integrate `provider_manager.record_success/record_failure` in orchestrator paths that call adapters
- [ ] Ensure http_client metrics emit for adapter calls; add optional adapter-level counters
- [ ] Keep prompt-safe logs using existing sanitization utilities

Rollout & Safety
- [x] Feature flag `LLM_ADAPTERS_ENABLED=1` exists; per-provider flags allow canary routing
- [ ] Canary enable providers (OpenAI first) in non-prod, then prod
- [ ] Rollback plan: flip flag to revert routing to legacy functions

Compatibility & Parity Checks
- [ ] Streaming: exactly one final `[DONE]` from the endpoint (no duplicates)
- [ ] Tool calling: identical behavior for `tool_choice` and `tools` presence
- [ ] Error taxonomy: same HTTP status mapping at FastAPI layer
- [ ] Environment precedence for base URLs and keys matches legacy behavior

Definition of Done (Phase 1–4)
- [ ] Registry and base adapter in place with docs
- [ ] All in-scope chat adapters implemented and covered by tests
- [ ] `/api/v1/chat/completions` streaming and non-streaming regression tests pass
- [ ] Providers endpoint reports registry-backed capabilities
- [ ] Embeddings adapters wired behind `LLM_EMBEDDINGS_ADAPTERS_ENABLED=1` with endpoint parity tests
- [ ] Monolith branching removed; wrappers remain for compatibility; duplicated helpers deleted

Reference Artifacts
- Base/Registry: `tldw_Server_API/app/core/LLM_Calls/providers/base.py`, `tldw_Server_API/app/core/LLM_Calls/adapter_registry.py`
- Shared Streaming: `tldw_Server_API/app/core/LLM_Calls/sse.py`, `tldw_Server_API/app/core/LLM_Calls/streaming.py`, `tldw_Server_API/app/core/http_client.py`
- Legacy Dispatch: `tldw_Server_API/app/core/Chat/provider_config.py` (to be updated to delegate)
- Health/Fallback: `tldw_Server_API/app/core/Chat/provider_manager.py`
