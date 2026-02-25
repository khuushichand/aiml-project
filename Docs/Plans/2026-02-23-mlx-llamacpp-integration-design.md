# MLX-LM + Llama.cpp Integration Correctness Review Design

Date: 2026-02-23
Owner: Codex + maintainer review
Status: Approved (Option 1)

## Goal
Run a contract-first review of the `mlx-lm` and `llama.cpp` integrations in `tldw_Server_API` and produce a prioritized, test-backed improvement plan focused on correctness and integration consistency.

## Chosen Approach
Option 1: Contract-first review and fix plan.

Why this approach:
- Finds regressions and integration drift without forcing a high-risk refactor.
- Produces explicit expected vs observed behavior and ties each gap to a targeted test.
- Preserves existing valid split behavior (notably the two `llama.cpp` integration planes) while removing ambiguity.

## Scope
In scope:
- Lifecycle correctness (`load/start/stop/unload/status/models`).
- Inference contract consistency (chat/completions, stream/non-stream, embeddings).
- Config precedence and runtime truth alignment.
- Auth/governance consistency for lifecycle endpoints.
- Test coverage gaps for integration contracts.

Out of scope:
- Large abstraction rewrite across local providers.
- New product features.
- Performance tuning not directly tied to correctness.

## Architecture Contract
Treat integrations as contract surfaces, not only code modules.

Contract matrix rows:
1. Lifecycle
2. Inference
3. Config precedence
4. Auth/governance
5. Observability/status shape

Primary contract requirement:
- Every public endpoint/provider path has explicit expected behavior.
- Any divergence is recorded as a gap with severity and a proving test.

## Component Map and Data Flow
### MLX control plane
- `tldw_Server_API/app/api/v1/endpoints/mlx.py`
- `tldw_Server_API/app/core/LLM_Calls/providers/mlx_provider.py`

Contract:
- `/load`, `/unload`, `/status` are consistent with one registry state.

### MLX inference plane
- `tldw_Server_API/app/core/LLM_Calls/adapter_registry.py`
- `tldw_Server_API/app/core/LLM_Calls/embeddings_adapter_registry.py`
- `tldw_Server_API/app/core/LLM_Calls/capability_registry.py`

Contract:
- Chat/embeddings behavior and capabilities match live registry/model state.

### Llama.cpp managed-server plane
- `tldw_Server_API/app/api/v1/endpoints/llamacpp.py`
- `tldw_Server_API/app/core/Local_LLM/LlamaCpp_Handler.py`
- `tldw_Server_API/app/core/Local_LLM/LLM_Inference_Manager.py`

Contract:
- Start/stop/status/models/inference operate against managed process state.

### Llama.cpp provider plane
- `tldw_Server_API/app/core/LLM_Calls/providers/local_adapters.py`
- `tldw_Server_API/app/core/config.py` (`llama_api` config)

Contract:
- `provider=llama.cpp` calls are remote OpenAI-compatible mode unless explicitly bridged.

## Error Handling and Consistency Rules
1. Distinct status codes by condition:
- `503` not configured/unavailable
- `400` invalid request/input
- `429` busy/concurrency cap

2. No silent acceptance of unsupported knobs:
- Reject unsupported controls or surface "accepted but not applied".

3. Explicit plane-specific errors for `llama.cpp`:
- Managed server errors vs remote provider errors must not be conflated.

4. Stable lifecycle/status response envelopes:
- Machine-checkable keys (`status`, `state`, `model`, `host`, `port`, etc.).

5. Consistent lifecycle auth policy across local runtime controls.

## Testing Design
### P0 contract tests
- `llama.cpp` lifecycle endpoint tests:
  - `/api/v1/llamacpp/start_server`
  - `/api/v1/llamacpp/stop_server`
  - `/api/v1/llamacpp/status`
  - `/api/v1/llamacpp/models`
- `mlx` lifecycle + role tests for `/load|/unload|/status`.
- Cross-plane invariant tests (managed server state does not implicitly define provider-mode behavior).

### P1 contract tests
- Config precedence tests (request > env > config defaults).
- Unsupported/no-op parameter behavior tests (reject or explicit reporting).

### P2 contract tests
- Status/metrics field stability tests.

## Initial Gap Inventory (Observed)
### P0
1. Llama.cpp lifecycle endpoint auth consistency is weaker than MLX lifecycle controls.
   - MLX endpoints enforce `require_roles("admin")`; llama.cpp lifecycle endpoints currently do not.

2. Llama.cpp lifecycle endpoint contract coverage is thin.
   - Existing tests heavily cover handler internals and reranking but not lifecycle API endpoint behavior.

3. Two llama.cpp planes are valid but under-documented and easy to misuse.
   - Managed plane (`/api/v1/llamacpp/*`) and provider plane (`provider=llama.cpp`) can appear coupled to operators/UI when they are not.

### P1
4. MLX load request contains fields not passed into `mlx_lm.load(...)` in current adapter path (`quantization`, `max_kv_cache_size`).
   - Risk: user believes knobs are active when they are currently inert.

5. Capability metadata mismatch risk for llama.cpp tools support.
   - `provider_metadata` indicates tools support for `llama.cpp`, while current `LlamaCppAdapter` advertises `supports_tools = False`.

6. MLX embeddings response model name can drift from active session model.
   - Current embed response uses `request.get("model")` instead of canonical active model id.

### P2
7. Apple-only MLX integration tests reduce CI confidence for cross-platform contract regressions.

## Deliverables
1. Contract matrix (expected behavior table).
2. Gap report mapped to files/endpoints.
3. Prioritized improvement backlog (P0/P1/P2).
4. Test plan linking each fix to concrete regression tests.
5. Plane-clarity reference doc:
   - `Docs/API-related/llamacpp_integration_modes.md` (managed plane vs provider plane mapping and troubleshooting).

## Acceptance Criteria
- Every P0 gap has a concrete fix plan and regression test design.
- Contract matrix is complete for both MLX and llama.cpp planes.
- No ambiguity remains about endpoint ownership or runtime state source of truth.

## Risks and Mitigation
- Risk: over-fixing toward a refactor.
  - Mitigation: constrain to contract fixes + tests only.
- Risk: breaking existing UI/admin flow.
  - Mitigation: preserve endpoint shapes and add compatibility tests.
