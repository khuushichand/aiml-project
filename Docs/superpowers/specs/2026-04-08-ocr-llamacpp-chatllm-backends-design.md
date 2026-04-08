# OCR Llama.cpp And ChatLLM Backends Design

Date: 2026-04-08
Status: Proposed
Owner: Codex brainstorming session

## Summary

Add two new OCR backends, `llamacpp` and `chatllm`, to the existing OCR registry so the server can use OCR-capable multimodal models through three server-configured execution paths:

- remote endpoint invocation
- one-shot local CLI invocation
- managed local process reuse

The API surface stays stable. Clients continue to use the existing OCR request fields such as `enable_ocr`, `ocr_backend`, `ocr_mode`, `ocr_output_format`, and `ocr_prompt_preset`. They do not choose endpoint URLs, model names, binary paths, or model paths. Those stay server-owned.

The design is intentionally OCR-scoped for v1. It does not introduce a new general multimodal execution framework. It extends the current OCR backend model and preserves the current `OCRResult` and `analysis_details.ocr.structured` contract.

## Problem

The current OCR stack already supports multiple execution styles:

- local Python inference
- remote OpenAI-compatible inference
- document or page oriented CLI execution

However, it does not support two deployment patterns that are already useful for local and self-hosted users:

1. OCR-capable GGUF or llama.cpp deployments that expose a reusable endpoint or local binary.
2. ChatLLM-based OCR-capable deployments that may be exposed as an endpoint or as a local binary/process.

Today, users who want OCR through those runtimes must build an external compatibility layer themselves or cannot use those models at all. That creates four gaps:

1. There is no first-class `ocr_backend=llamacpp`.
2. There is no first-class `ocr_backend=chatllm`.
3. The OCR registry has no clean way to express "same OCR contract, different runtime transport."
4. Managed local runtime behavior is inconsistent across OCR backends and not discoverable enough for operators.

## Goals

- Add `llamacpp` and `chatllm` as normal OCR backends in the existing OCR registry.
- Support three execution paths per backend:
  - remote endpoint
  - one-shot local CLI
  - managed local process reuse
- Keep runtime ownership server-side only.
- Preserve the existing OCR request contract.
- Preserve the existing OCR output contract:
  - `text|markdown|json`
  - `ocr_prompt_preset`
  - `OCRResult`
  - `analysis_details.ocr.structured`
- Make both backends eligible for `auto` and `auto_high_quality`.
- Keep OCR integration isolated enough that it does not force a general Local_LLM refactor in this phase.
- Expose useful lightweight discovery metadata through `GET /api/v1/ocr/backends`.

## Non-Goals

- Add request-level overrides for endpoint URLs, model names, binary paths, or model paths.
- Build a general vision runtime layer for non-OCR features in this phase.
- Add multiple named OCR profiles per backend in v1.
- Guarantee model-quality benchmarks or correctness in CI for every external runtime.
- Replace the existing OCR backend contract or PDF pipeline contract.
- Refactor the existing general `Local_LLM` manager to own ChatLLM in this phase.
- Add a new user-visible OCR API surface beyond existing ingestion and evaluation flows.

## Current State

### Existing OCR Architecture

The current OCR pipeline is already pluggable:

- `tldw_Server_API/app/core/Ingestion_Media_Processing/OCR/base.py`
- `tldw_Server_API/app/core/Ingestion_Media_Processing/OCR/registry.py`
- `tldw_Server_API/app/core/Ingestion_Media_Processing/PDF/PDF_Processing_Lib.py`

Backends currently mix several runtime styles:

- CLI oriented:
  - `tesseract`
  - `dots`
  - `mineru` at the document level
- remote OpenAI-compatible:
  - `dots` via vLLM
  - `hunyuan` via vLLM
  - `points` via SGLang
  - `dolphin` via OpenAI-compatible mode
- local Python inference:
  - `points`
  - `deepseek`
  - `hunyuan`
  - `dolphin`

This means the OCR subsystem already accepts the idea that one backend can support more than one runtime path.

### Existing OCR Output Contract

The PDF pipeline expects OCR backends to produce either:

- plain text through `ocr_image(...)`
- structured results through `ocr_image_structured(...)`

The resulting data is normalized into `OCRResult` and persisted in `analysis_details.ocr`.

This is already relied on by:

- PDF ingestion
- OCR evaluations
- backend-specific structured output tests

### Existing Llama.cpp Process Management

The repository already has a general llama.cpp lifecycle manager and endpoint surface under:

- `tldw_Server_API/app/core/Local_LLM/`
- `tldw_Server_API/app/api/v1/endpoints/llamacpp.py`

That manager is useful precedent, but it is not a drop-in dependency for OCR backends today because OCR backends run inside library-style ingestion code without request context or direct access to `app.state.llm_manager`.

### ChatLLM State

There is currently no ChatLLM integration in this repository. That means v1 must introduce ChatLLM support only as far as needed for OCR backend execution and discovery.

## Design Principles

### 1. Stay Inside The OCR Abstraction

`llamacpp` and `chatllm` should behave like any other OCR backend. The PDF and image OCR pipelines should not need runtime-specific branches for these backends.

### 2. Server Owns Runtime Selection

The request selects `ocr_backend`. The server selects the actual runtime profile, endpoint, binary, model, and startup policy.

### 3. Shared Runtime Logic, Backend-Owned OCR Semantics

Transport and process execution logic should be shared where practical. Prompt mapping, output parsing, and OCRResult normalization stay backend-owned.

### 4. Managed Startup Must Be Explicit

Managed local runtime startup is potentially expensive and operationally sensitive. It must default to disabled unless the backend configuration explicitly allows it.

### 5. No New Parallel OCR Framework

This phase should add only enough shared code to prevent duplication between `llamacpp` and `chatllm`. It should not create a broad new multimodal platform abstraction.

## Proposed Architecture

### High-Level Structure

Add:

- `tldw_Server_API/app/core/Ingestion_Media_Processing/OCR/backends/llamacpp_ocr.py`
- `tldw_Server_API/app/core/Ingestion_Media_Processing/OCR/backends/chatllm_ocr.py`
- `tldw_Server_API/app/core/Ingestion_Media_Processing/OCR/runtime_support.py`

The new helper module should own only:

- runtime mode resolution
- server-side profile/config parsing
- remote OpenAI-compatible invocation helpers
- safe one-shot CLI execution helpers
- managed runtime readiness and reuse helpers
- lightweight discovery metadata assembly

The new backend modules should own:

- backend name and availability semantics
- preset-to-prompt mapping
- request payload composition for their chosen runtime mode
- parsing of raw model output into `OCRResult`
- backend-specific metadata such as mmproj requirements or native mode labels

## Why Not Reuse `LLMInferenceManager` Directly In V1

The current OCR call path is library-first and request-agnostic. The general local LLM manager is app-state oriented and primarily surfaced through admin endpoints.

Direct reuse in this phase would force at least one of these bigger changes:

- thread the manager through the ingestion pipeline
- create a new global service locator for ingestion
- make OCR backends depend on FastAPI request context

That is too large for the current scope. The v1 design should therefore keep managed OCR runtime control inside OCR-local helper code. A later phase can converge `llamacpp` OCR management with the general Local_LLM layer if the repository decides to inject shared runtime services into ingestion code.

## Execution Modes

Each backend supports one active server-configured mode:

- `remote`
- `managed`
- `cli`
- `auto`

`auto` means "choose the first usable path from the backend's configured preference order."

### Remote Mode

Preferred protocol is OpenAI-compatible multimodal chat/completions.

For `llamacpp`, this is the primary remote mode.

For `chatllm`, the remote path should use OpenAI-compatible transport when available and may fall back to a backend-native adapter only when an OpenAI-compatible deployment is not possible for that runtime.

### Managed Mode

Managed mode refers to a long-lived local process owned by the server process and reused across OCR requests.

Behavior:

- if the managed runtime is already running and healthy, use it
- if it is not running and `allow_managed_start=false`, the backend is not immediately usable
- if it is not running and `allow_managed_start=true`, the backend may start it and then reuse it

User preference for this feature:

- default behavior should not auto-start a managed runtime
- opt-in per backend is allowed

### CLI Mode

CLI mode runs a one-shot local command for the current OCR call and then exits.

This is explicitly supported for deployments that want:

- no long-lived process
- local-only execution
- maximum compatibility with a binary already installed on the host

## Runtime Availability Semantics

The backend `available()` result should mean "this backend can service an OCR request now or can legally bring itself to readiness now."

That means:

- `remote`
  - available when required remote config exists and the backend can pass a bounded reachability check
- `cli`
  - available when required binary/model config exists and local paths validate
- `managed`
  - available when:
    - a healthy managed process is already present, or
    - startup is allowed and startup config is valid

Discovery should be richer than `available()` and distinguish:

- configured
- available
- running
- reachable
- allow_managed_start

## Proposed Configuration

V1 uses one server-owned OCR profile per backend.

The request surface stays:

- `ocr_backend=llamacpp`
- `ocr_backend=chatllm`

Everything else stays server-configured.

### Llama.cpp OCR Config

Suggested settings:

- `LLAMACPP_OCR_MODE=auto|remote|managed|cli`
- `LLAMACPP_OCR_ALLOW_MANAGED_START=true|false`
- `LLAMACPP_OCR_TIMEOUT_SEC`
- `LLAMACPP_OCR_PROMPT_PRESET_DEFAULT`
- `LLAMACPP_OCR_MAX_TOKENS`
- `LLAMACPP_OCR_TEMPERATURE`

Remote:

- `LLAMACPP_OCR_URL`
- `LLAMACPP_OCR_MODEL`
- `LLAMACPP_OCR_API_KEY` if needed
- `LLAMACPP_OCR_USE_DATA_URL=true|false`

Managed:

- `LLAMACPP_OCR_SERVER_BINARY`
- `LLAMACPP_OCR_MODEL_PATH`
- `LLAMACPP_OCR_MMPROJ`
- `LLAMACPP_OCR_HOST`
- `LLAMACPP_OCR_PORT`
- `LLAMACPP_OCR_STARTUP_TIMEOUT_SEC`
- `LLAMACPP_OCR_SERVER_ARGS_JSON`

CLI:

- `LLAMACPP_OCR_CLI_BINARY`
- `LLAMACPP_OCR_MODEL_PATH`
- `LLAMACPP_OCR_MMPROJ`
- `LLAMACPP_OCR_CLI_ARGS_JSON`

### ChatLLM OCR Config

Suggested settings:

- `CHATLLM_OCR_MODE=auto|remote|managed|cli`
- `CHATLLM_OCR_ALLOW_MANAGED_START=true|false`
- `CHATLLM_OCR_TIMEOUT_SEC`
- `CHATLLM_OCR_PROMPT_PRESET_DEFAULT`
- `CHATLLM_OCR_MAX_TOKENS`
- `CHATLLM_OCR_TEMPERATURE`

Remote:

- `CHATLLM_OCR_URL`
- `CHATLLM_OCR_MODEL`
- `CHATLLM_OCR_API_KEY` if needed
- `CHATLLM_OCR_REMOTE_PROTOCOL=openai|native`

Managed:

- `CHATLLM_OCR_SERVER_BINARY`
- `CHATLLM_OCR_MODEL_PATH`
- `CHATLLM_OCR_HOST`
- `CHATLLM_OCR_PORT`
- `CHATLLM_OCR_STARTUP_TIMEOUT_SEC`
- `CHATLLM_OCR_SERVER_ARGS_JSON`
- `CHATLLM_OCR_HEALTHCHECK_URL` when managed mode uses a native protocol

CLI:

- `CHATLLM_OCR_CLI_BINARY`
- `CHATLLM_OCR_MODEL_PATH`
- `CHATLLM_OCR_CLI_ARGS_JSON`

### Safe Argument Encoding

Command configuration should use JSON arrays of argv tokens rather than shell strings.

Examples:

- `["--model", "{model_path}", "--image", "{image_path}", "--prompt", "{prompt}"]`
- `["--host", "{host}", "--port", "{port}"]`

This keeps execution shell-free and allows controlled placeholder substitution without shell interpolation.

## Prompting And Output Contract

The new backends must support the current OCR contract, not a runtime-specific contract.

### Prompt Presets

Both backends should accept the existing OCR presets:

- `general`
- `doc`
- `table`
- `spotting`
- `json`

Each backend maps those presets plus `ocr_output_format` into a backend-appropriate prompt.

The backend, not the shared runtime helper, owns the final prompt text.

### Output Formats

Both backends are expected to support:

- `text`
- `markdown`
- `json`

`json` means "request structured output and attempt to parse it into the current OCR structured result contract."

### Structured Output Rules

If structured JSON is returned and parses successfully:

- populate `OCRResult.raw`
- derive `OCRResult.text`
- populate `blocks`, `tables`, and `pages` when derivable
- preserve backend metadata in `meta`

If `json` is requested but parsing fails:

- degrade to text or markdown rather than failing the entire OCR job
- add warnings
- preserve raw model output for debugging

This matches the error-tolerant pattern already used by other OCR backends.

## Data Flow

The call path remains:

1. PDF pipeline decides OCR is needed.
2. Registry resolves `llamacpp` or `chatllm`.
3. Backend resolves its server-owned runtime profile.
4. Backend asks the shared runtime helper to execute through:
   - remote
   - managed
   - cli
5. Backend normalizes the runtime output into `OCRResult`.
6. PDF pipeline stores:
   - `analysis_details.ocr`
   - `analysis_details.ocr.structured`
   - text replacement or append behavior according to existing OCR mode logic

No new request schema or PDF pipeline branch should be required beyond selecting the new backend names.

## Discovery And Auto Selection

## Discovery

`GET /api/v1/ocr/backends` should expose lightweight details for both new backends, including:

- `available`
- `configured`
- `mode`
- `supports_structured_output`
- `supports_json`
- `auto_eligible`
- `auto_high_quality_eligible`
- remote details:
  - `url_configured`
  - `remote_reachable`
- managed details:
  - `managed_configured`
  - `managed_running`
  - `allow_managed_start`
- cli details:
  - `cli_configured`

### Auto Selection

Both backends should be eligible for:

- `auto`
- `auto_high_quality`

Selection rules:

- `OCR.backend_priority` remains the authoritative override for both auto modes.
- Without an override, use these defaults:
  - `auto`: `tesseract`, `nemotron_parse`, `points`, `deepseek`, `hunyuan`, `dots`, `dolphin`, `llamacpp`, `chatllm`
  - `auto_high_quality`: `llamacpp`, `chatllm`, `nemotron_parse`, `hunyuan`, `deepseek`, `points`, `dots`, `dolphin`, `tesseract`

These defaults keep plain `auto` conservative while still making both new backends eligible, and they let `auto_high_quality` prefer the server-curated multimodal runtime backends first.

## Managed Runtime Design

Managed runtime ownership should be OCR-local for v1.

Suggested behavior:

- one managed process per backend profile
- module-level handle guarded by a lock
- health/readiness check before reuse
- explicit cleanup on shutdown if the repository later wires OCR-local cleanup into app lifespan hooks

For `llamacpp`, the managed runtime implementation should reuse the same safety patterns already present in `LlamaCpp_Handler`:

- no shell execution
- validated path allowlists
- readiness polling
- process group termination
- bounded startup timeout

For `chatllm`, the same operational behaviors apply even if the exact startup command differs.

## Error Handling

Errors should remain consistent with the current OCR philosophy:

- backend unavailable:
  - backend resolution returns `None` for selection
  - discovery reports why
- OCR execution failure:
  - produce warnings and structured error details
  - do not turn the whole PDF job into a hard failure unless the broader processing path already would
- JSON parse failure:
  - degrade to text or markdown
  - attach warnings
- managed startup not allowed:
  - report unavailable, not a silent fallback to process creation
- remote unreachable:
  - log clearly
  - return OCR warning or fallback according to backend mode policy

The runtime helper should classify common failure categories:

- configuration error
- startup error
- healthcheck timeout
- invocation timeout
- invalid response shape
- parse failure

## Security And Operational Constraints

- No shell interpolation.
- Command execution uses argv lists only.
- Binary and model paths must be validated against allowed directories.
- Requests must not be able to override server-owned runtime settings.
- Timeouts must be bounded for:
  - startup
  - remote requests
  - CLI execution
- Temporary image files must be cleaned up.
- API keys or secrets must not be logged.
- Managed processes must bind to safe local interfaces by default.
- Discovery endpoints should surface capability state without leaking sensitive secrets.

## Testing Strategy

This feature should be tested as an adapter and contract feature, not as a model-quality benchmark feature.

### Required Automated Tests

1. Registry tests
   - `llamacpp` and `chatllm` appear in backend discovery
   - discovery metadata reflects configured versus available state

2. Auto selection tests
   - both backends can participate in `auto`
   - both backends can participate in `auto_high_quality`
   - `OCR.backend_priority` still overrides default ordering

3. Remote invocation tests
   - successful OpenAI-compatible response
   - unreachable endpoint
   - malformed response

4. CLI invocation tests
   - successful one-shot execution
   - nonzero exit
   - timeout
   - invalid binary or model path

5. Managed runtime tests
   - process already running
   - process absent with autostart disabled
   - process absent with autostart enabled
   - startup timeout
   - readiness failure

6. Output normalization tests
   - `text`
   - `markdown`
   - valid `json`
   - invalid `json` with fallback and warnings

7. PDF pipeline tests
   - integration through `process_pdf_task(...)`
   - structured output lands under `analysis_details.ocr.structured`
   - existing replacement or append logic still works

### Manual Or Optional Integration Coverage

- live remote endpoint with an OCR-capable llama.cpp deployment
- live remote or local ChatLLM deployment
- representative scanned PDF smoke tests

These should remain optional or manual because they depend on heavyweight external runtimes.

## Documentation Changes

Implementation should update:

- `Docs/OCR/OCR_Providers.md`
- `Docs/API-related/OCR_API_Documentation.md`
- `Docs/Operations/Env_Vars.md`
- new backend-specific docs, for example:
  - `Docs/OCR/LlamaCpp-OCR.md`
  - `Docs/OCR/ChatLLM-OCR.md`

## Rollout Plan

Phase the work in this order:

1. Add shared OCR runtime helper and backend profile parsing.
2. Add `llamacpp` OCR backend.
3. Add `chatllm` OCR backend.
4. Extend discovery metadata and auto-selection tests.
5. Add PDF pipeline integration tests and docs.

This sequence keeps the largest unknown, ChatLLM runtime details, from blocking the initial helper and llama.cpp path.

## Acceptance Criteria

This design is successful when all of the following are true:

- users can select `ocr_backend=llamacpp` or `ocr_backend=chatllm`
- the server uses only server-owned runtime configuration
- each backend can operate through remote, managed, or CLI execution as configured
- managed autostart is disabled by default but can be enabled per backend
- both backends participate in `auto` and `auto_high_quality`
- structured OCR results still conform to `OCRResult` and `analysis_details.ocr.structured`
- failure modes degrade gracefully and do not introduce shell-based execution risk

## Follow-Up Work Outside This Phase

- multiple named OCR profiles per backend
- convergence with the general `Local_LLM` manager if ingestion gains shared runtime injection
- richer structured block and bbox normalization across OCR-capable multimodal models
- backend quality benchmarking and profile recommendation docs
