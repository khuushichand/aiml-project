# PRD: Supertonic2 ONNX TTS Hardening and Contract Alignment

## 1. Purpose and Scope

This PRD is **not** for a net-new Supertonic2 implementation. Supertonic2 is already integrated in the codebase.

The scope of this document is to:
- Align product documentation with the implemented architecture.
- Define hardening work that reduces integration drift and user confusion.
- Add explicit language normalization behavior for regional tags (for example `en-US`, `pt-BR`).

Out of scope:
- Model training/fine-tuning.
- New voice-cloning features.
- Replacing ONNX assets with a different runtime stack.

## 2. Current State (Already Implemented)

Supertonic2 exists today in:
- Adapter: `tldw_Server_API/app/core/TTS/adapters/supertonic2_adapter.py`
- Vendor helper: `tldw_Server_API/app/core/TTS/vendors/supertonic2/helper.py`
- Provider enum/registry/model mapping: `tldw_Server_API/app/core/TTS/adapter_registry.py`
- Validation limits and language/format support: `tldw_Server_API/app/core/TTS/tts_validation.py`
- Provider hint inference for request sanitization: `tldw_Server_API/app/core/Audio/tts_service.py`
- Config block: `tldw_Server_API/Config_Files/tts_providers_config.yaml`
- Installer helper: `Helper_Scripts/TTS_Installers/install_tts_supertonic2.py`
- Tests:
  - `tldw_Server_API/tests/TTS/adapters/test_supertonic2_adapter_mock.py`
  - `tldw_Server_API/tests/TTS/test_tts_validation.py`

## 3. Product Goals

1. Ensure docs and PRDs reflect actual module layout and API behavior.
2. Standardize language handling for Supertonic2 so regional tags are accepted and normalized.
3. Make CPU-only behavior explicit and deterministic.
4. Keep `/api/v1/audio/speech` and `/api/v1/audio/voices/catalog` behavior stable.

## 4. Key Contract Corrections

### 4.1 Endpoint and Module References

Use current split audio modules:
- Speech endpoint: `tldw_Server_API/app/api/v1/endpoints/audio/audio_tts.py`
- Audio router aggregator: `tldw_Server_API/app/api/v1/endpoints/audio/audio.py`
- Provider hinting for sanitization: `tldw_Server_API/app/core/Audio/tts_service.py`

Do not reference legacy monolithic path `.../endpoints/audio.py` as the owner of speech/provider-hint logic.

### 4.2 Request Language Contract

For OpenAI-compatible speech requests:
- Primary field: `lang_code`
- Override field: `extra_params.language` (takes precedence when provided)

Do not document a top-level `language` field on `OpenAISpeechRequest`; the internal unified `TTSRequest` uses `language` after conversion.

### 4.3 Vendor Source Reference

Within this repository, the vendored source of truth is:
- `tldw_Server_API/app/core/TTS/vendors/supertonic2/helper.py`

Avoid requiring a local `example_onnx.py` file in this project layout.

## 5. Hardening Requirements

### 5.1 Language Normalization (Approved Requirement)

Supertonic2 must accept regional BCP-47-like tags and normalize to supported base tags.

Supported base tags:
- `en`, `ko`, `es`, `pt`, `fr`

Normalization rules:
1. Trim whitespace.
2. Lowercase.
3. Replace `_` with `-`.
4. Extract base language segment before first `-`.
5. Validate normalized base against provider-supported set.

Examples:
- `EN-US` -> `en`
- `en_GB` -> `en`
- `pt-BR` -> `pt`
- `pt_PT` -> `pt`
- `es-MX` -> `es`
- `fr-CA` -> `fr`
- `ko-KR` -> `ko`

Error behavior:
- If normalized base is not supported, return validation error listing supported tags.

Implementation touchpoints for follow-up PR:
- Normalize during request conversion in `tldw_Server_API/app/core/TTS/tts_service_v2.py` (where `lang_code` and `extra_params.language` are mapped).
- Apply same normalization path before provider-specific language validation in `tldw_Server_API/app/core/TTS/tts_validation.py`.

### 5.2 CPU-Only Enforcement

Supertonic2 runtime policy is CPU-only for production support.

Required behavior:
- If config selects non-CPU mode (for example `device=cuda`), fail fast with a clear initialization error.
- Do not silently downgrade from CUDA to CPU.

### 5.3 Voice Catalog Semantics

`supported_languages` remains provider-level truth for language capability.

For `VoiceInfo.language`:
- Prefer `"multi"` for Supertonic2 voice entries, or
- Keep `"en"` only if compatibility constraints require it and document clearly that validation is provider-level.

### 5.4 Provider Hint Consistency

Model-to-provider hinting for Supertonic2 should remain consistent across all infer helpers:
- `tldw_Server_API/app/core/Audio/tts_service.py`
- `tldw_Server_API/app/services/audiobook_jobs_worker.py`

Accepted prefixes:
- `supertonic2`
- `supertonic-2`
- `tts-supertonic2`

## 6. Non-Functional Requirements

- Lazy model initialization.
- Async lock around engine generation calls.
- Pseudo-streaming only (chunked encoded bytes).
- Structured logging for `voice_id`, `language`, `speed`, and `total_step`.

## 7. Testing Requirements (Follow-Up Hardening PR)

### 7.1 Unit Tests

- Add language normalization tests for Supertonic2:
  - Accept `en-US`, `pt-BR`, `fr-CA`, `es-MX`, `ko-KR`.
  - Reject unsupported bases (for example `de-DE`).
- Verify override precedence:
  - `extra_params.language` overrides `lang_code`.
- Verify CPU-only enforcement:
  - Non-CPU config fails with explicit error.

### 7.2 Integration Tests

- `/api/v1/audio/speech` with `model=tts-supertonic2-1`, `stream=false`, and `lang_code=pt-BR` returns non-empty audio.
- `/api/v1/audio/speech` with `extra_params.language=fr-CA` uses normalized `fr`.
- `/api/v1/audio/voices/catalog` lists Supertonic2 voices when enabled.

### 7.3 Regression Tests

- Existing supported base tags continue to work unchanged.
- Existing model aliases continue to route to `supertonic2`.

## 8. Documentation Updates

Update product and user docs to match current behavior:
- `Docs/Product/TTS_Supertonic2_ONNX.md` (this document)
- `Docs/Published/User_Guides/Setup-Supertonic2.md`

Docs must show `lang_code` examples using regional tags and expected normalization.

## 9. Acceptance Criteria

1. PRD language is aligned with already-landed implementation and current file layout.
2. Regional language normalization behavior is explicitly specified and testable.
3. CPU-only behavior is explicit and deterministic.
4. No stale references to legacy endpoint ownership remain.
