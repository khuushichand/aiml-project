# MLX-LM PRD

## Goal
Add MLX-backed local LLM provider (Apple Silicon first) that mirrors llama.cpp support: configurable as a backend/module, loadable at runtime, and callable through existing chat/embedding APIs with management endpoints for lifecycle and settings.

## Success Criteria
- MLX appears in `/api/v1/llm/providers` with capability flags.
- Models can be loaded/unloaded via API/config without server restart.
- `/api/v1/chat/completions` (stream and non-stream) works with `provider=mlx`.
- `/api/v1/embeddings` works with `provider=mlx` when the model supports embeddings; clear error if not.
- Auth/rate limits/logging align with other local providers; tests cover lifecycle and inference.

## In Scope
- Provider plumbing: configuration parsing, lifecycle (list/load/unload), inference for chat and embeddings (when supported), streaming, common sampling controls (temperature, top_p/top_k, repetition penalties, presence/frequency penalties).
- Endpoint exposure: management endpoints plus OpenAI-compatible inference routes.
- Config surfaces: `.env`/`Config_Files/config.txt` keys for model path, max sequence/batch, device selection (auto/MPS/CPU), dtype/quantization hint, compile toggle, prompt template override, sampling defaults. Avoid llama.cpp-specific flags (ngl/mmap/mlock) that MLX-LM does not support.
- Observability: loguru logging and metrics hooks consistent with existing providers.
- Auth/rate limits: reuse dependency patterns and per-endpoint limits.

## Out of Scope
- Training/fine-tuning workflows.
- Weight download/management UI.
- Non-Apple hardware acceleration beyond CPU fallback.

## User Stories
- As an Apple Silicon user, I configure MLX model path and parameters, then see MLX listed as an available provider.
- I can load or unload MLX models over API without restarting the server.
- I can send chat completions with streaming responses via MLX backend.
- I can request embeddings (when supported) via the embeddings endpoint.
- I can inspect running MLX sessions, their settings, and resource usage for debugging.

## Constraints and Assumptions
- Primary target: Apple Silicon (M-series) with CPU fallback acceptable.
- Models are pre-downloaded; user provides model path.
- Follow local provider patterns for prompt formatting, safety checks, and threading controls.
- Keep memory usage predictable; expose max context and batch size controls.
- Repo-id downloads are configurable via config.txt but disabled by default (production default: off); `trust_remote_code` defaults to false and should remain off unless explicitly allowed.

## Architecture and Design
- **New provider module**: `tldw_Server_API/app/core/LLM_Calls/providers/mlx_provider.py` implementing the same interface used by other local providers (e.g., llama.cpp).
- **Provider registration**: make MLX a first-class provider in `adapter_registry`/enums so `provider=mlx` works on `/api/v1/chat/completions` and `/api/v1/embeddings`.
- **Management endpoints**: mirror llama.cpp patterns for load/unload/status with the same auth deps and rate limits.
- **Inference path**: integrate via the existing LLM provider manager/adapter pipeline (OpenAI-compatible routes) rather than a separate Local_LLM stack; management endpoints are Local_LLM-style for lifecycle.
- **Session registry**: centralized MLX session handling for load/unload/status; concurrency-safe with locks; respects rate limits and existing queue/backpressure semantics.
- **Prompt formatting**: prefer tokenizer/chat_template embedded with the model; fallback order: (1) tokenizer/chat_template if present, (2) pass messages through untouched if none, (3) explicit override via config/req; document behavior when no template exists.
- **Streaming**: use `mlx_lm.generate_stream` (or equivalent) and plug into the existing streaming pipeline (SSE/WS).
- **Embeddings**: supported in the first release; detect per-model capability at load using the existing embeddings module/capability probe; return a clear capability error if unavailable; publish capability in status.
- **Config keys** (config.txt or env), aligned to MLX-LM options:
  - `MLX_MODEL_PATH` (local path or repo id)
  - `MLX_MAX_SEQ_LEN`
  - `MLX_MAX_BATCH_SIZE`
  - `MLX_DEVICE` (`auto`|`mps`|`cpu`)
  - `MLX_DTYPE` (`float16`/`bfloat16`/model default) and optional `MLX_QUANTIZATION`
  - `MLX_COMPILE` (bool)
  - `MLX_PROMPT_TEMPLATE` (optional override)
  - `MLX_REVISION`, `MLX_TRUST_REMOTE_CODE` (bool), `MLX_TOKENIZER` (override), `MLX_ADAPTER`, `MLX_ADAPTER_WEIGHTS`
  - `MLX_MAX_KV_CACHE_SIZE` / preallocation toggle if exposed by mlx-lm
  - Sampling defaults (temperature, top_p, top_k, repetition penalties, presence/frequency penalties, batch size)
- **Dependency wiring**: add MLX to provider selection logic and request schemas; align auth/rate-limit dependencies with existing providers.
- **Resource guardrails**: default to a single active MLX model/session with `MLX_MAX_CONCURRENT=1`, no batching, and overflow rejected with 429 (future batching TBD); document eviction/swap policy if multiple models are allowed.
- **Warmup/compile behavior**: default to compile+warmup enabled on load to avoid first-token stalls; make it configurable. If compile/warmup OOMs, return a clear error and keep the prior model active.

## API Surface
- **Management (new)**
  - `POST /api/v1/llm/providers/mlx/load`: body includes `model_path`, optional params (max_seq_len, max_batch_size, device, dtype/quantization, compile, template override, sampling params, batch size). Supports override flag to swap an active model; rejects if active and override is false.
  - `POST /api/v1/llm/providers/mlx/unload`: body includes `model_id` or name; cancels/drains in-flight requests with a “Model Unavailable due to swapping” message.
  - `GET /api/v1/llm/providers/mlx/status`: returns loaded models, settings, memory use, capabilities (chat/embeddings), and queue depth.
- **Inference (existing routes)**
  - `/api/v1/chat/completions` with `provider=mlx` behaves like llama.cpp provider; supports streaming.
  - `/api/v1/embeddings` with `provider=mlx` when enabled; otherwise returns capability error.
- **Auth and rate limits**: enforce via existing API_Deps; align limits with other local providers.

## Validation and Testing
- Unit: provider init, config parsing, capability gating, prompt template selection, parameter validation.
- Integration: load → chat completion (stream and non-stream), embeddings (if supported), unload; error cases for missing/bad model paths.
- Embeddings: capability detection and error path (e.g., load embedding-capable model such as `mlx-community/gte-small-mlx`; expect capability error when invoking embeddings on a chat-only model).
- Concurrency: parallel chat requests under rate limits; session registry thread/async safety.
- Streaming: verify OpenAI-compatible chunk shape/SSE framing and WS parity using `generate_stream`.
- Performance smoke: context and token throughput within expected bounds on M-series; stable memory behavior under back-to-back requests.
- CI portability: add CPU-only smoke/skip markers for non-Apple runners (no MPS); keep integration coverage meaningful without hard-failing on missing Metal.

## Observability
- Log model loads/unloads, errors, inference timing, token counts, and parameter overrides.
- Metrics hooks for load time, active sessions, request latency, queue depth, and token throughput, maintaining parity with other providers.

## Security
- Auth enforced on management endpoints; lifecycle endpoints are admin-only/allowlist-gated via the resource governance module with per-tenant/provider quotas and rate limits; no anonymous load/unload.
- Validate file paths (prevent traversal outside allowed roots when applicable).
- Repo-id downloads are disabled by default; enabling them is explicit in config.txt. `trust_remote_code` defaults to false and should only be toggled when the deployment explicitly allows it.
- Do not log secrets or full prompts unless debug-level logging is explicitly enabled.

## Error Contracts
- Capability errors: embeddings on chat-only models return a clear capability error with HTTP 400/422 and provider-specific code.
- Load failures: bad path, compile/warmup OOM, or invalid config return 400 with reason; when swapping, failure preserves the prior model.
- Overflow: when `MLX_MAX_CONCURRENT` is exceeded, reject with HTTP 429 and no queue (future batching TBD).
- Unload while in-flight: return “Model Unavailable due to swapping” and drain in-flight requests gracefully.

## Migration and Docs
- Update provider docs with config keys, Apple Silicon setup notes, and example requests.
- Add examples to README/Docs for MLX usage (`pip install mlx-lm` note; Python 3.10+; macOS/Metal with MPS acceleration; CPU fallback expectations; no Windows support).
- Add troubleshooting section (missing model path, unsupported embeddings, resource exhaustion).

## Decisions (updates)
- Embeddings ship in the first release; use capability flag only to signal per-model availability.
- No dedicated queue/backpressure policy beyond existing provider defaults.
- Prompt templates: default to the model’s embedded template/behavior; allow optional override, only ship defaults if a given MLX model requires one.

## Rollout Plan
- **Phase 1**: Provider scaffolding, config wiring, management endpoints, non-streaming chat happy path.
- **Phase 2**: Streaming, embeddings capability (if supported), concurrency/backpressure polish.
- **Phase 3**: Docs/examples, expanded tests/benchmarks, troubleshooting guidance.

## Next Steps
- Finalize config key names and management endpoint paths.
- Document prompt template behavior (default to model-embedded; optional override) and examples.
- Align capability flag/error response wording for models without embeddings and pick the default embedding test model(s).
- Set default concurrency/eviction policy (`MLX_MAX_CONCURRENT`, single-session default) and confirm streaming hook targets (`generate_stream` → SSE/WS).
