## Stage 1: Planning Artifact + Baseline
**Goal**: Capture an execution checklist and baseline behavior for qwen3-tts runtime hardening.
**Success Criteria**:
- Baseline command outputs and crash signatures are documented.
- Stage checklist is decision-complete and maps to implementation/test tasks.
**Tests**:
- `python -m pytest -q tldw_Server_API/tests/TTS_NEW/unit/adapters/test_qwen3_tts_adapter.py tldw_Server_API/tests/TTS_NEW/unit/test_tts_validation_qwen3.py`
- `python -m pytest -q tldw_Server_API/tests/TTS_NEW/integration/test_qwen3_streaming.py tldw_Server_API/tests/TTS_NEW/integration/test_qwen3_voice_prompt_reuse.py`
- `python -m pytest -q tldw_Server_API/tests/TTS/test_tts_service_v2.py`
- `python -m bandit -r tldw_Server_API/app/core/TTS/adapters/qwen3_tts_adapter.py tldw_Server_API/app/core/TTS/tts_service_v2.py tldw_Server_API/app/core/TTS/tts_validation.py -f json -o /tmp/bandit_tts_review_20260307.json`
**Status**: Complete

### Baseline Evidence
- `test_tts_service_v2.py` passes.
- `test_tts_validation_qwen3.py` passes.
- Initial qwen adapter/integration suite reproduced crash signatures listed below.

### Reproduced Crash Signatures
- Fatal abort while importing `torch` from qwen adapter helper path:
  - call chain includes `qwen3_tts_adapter.py::_resolve_torch_dtype -> import torch`
- Fatal abort in integration path due to eager STT import stack:
  - call chain includes `faster_whisper -> ctranslate2 -> torch`

## Stage 2: Fix crash-prone torch probing in qwen adapter
**Goal**: Remove direct torch import probing from helper paths.
**Success Criteria**:
- `_resolve_torch_dtype` does not import torch.
- `_resolve_auto_model` uses non-fatal VRAM detection with fallback behavior.
**Tests**:
- qwen adapter unit tests
- new unit tests for dtype/VRAM probe logic
**Status**: Complete

## Stage 3: Fix provider/model normalization and mode routing
**Goal**: Normalize model IDs and tighten qwen mode resolution.
**Success Criteria**:
- Trailing slash and whitespace model IDs resolve provider correctly.
- Mode routing only matches explicit model tokens.
**Tests**:
- `tests/TTS/test_tts_adapters.py`
- qwen adapter unit tests for mode routing
**Status**: Complete

## Stage 4: Tokenizer decode correctness + upstream #234 guard
**Goal**: Guarantee WAV output contract and add chunked_decode compatibility shim.
**Success Criteria**:
- `response_format=wav` always returns valid WAV.
- Optional `chunked_decode` shim is deterministic and logged.
**Tests**:
- tokenizer integration tests
- new tokenizer service unit tests for compatibility patch behavior
**Status**: Complete

## Stage 5: Compatibility hardening for upstream drift
**Goal**: Return actionable errors for known upstream incompatibilities.
**Success Criteria**:
- Known RoPE/default and path-shape errors are remapped to clear guidance.
- Setup doc includes compatibility notes and mitigations.
**Tests**:
- qwen adapter unit tests for error mapping
- docs link and content checks if applicable
**Status**: Complete

## Stage 6: Test stabilization and coverage closure
**Goal**: Ensure qwen tests are deterministic and isolated from unrelated heavy imports.
**Success Criteria**:
- qwen unit/integration suites pass in CPU-only CI contexts.
- Existing TTS regression suites remain green.
**Tests**:
- targeted qwen tests
- `tests/TTS/test_tts_service_v2.py`
**Status**: Complete

## Stage 7: Streaming behavior upgrades (Phase 2)
**Goal**: Add boundary smoothing, busy handling, cooperative cancel semantics, and metrics.
**Success Criteria**:
- Backward-compatible streaming behavior improvements are implemented behind defaults.
- Existing streaming API contracts remain intact.
**Tests**:
- qwen streaming tests
- additional streaming-focused tests
**Status**: Complete

## Verification Results

- `python -m pytest -q tldw_Server_API/tests/TTS/test_tts_service_v2.py` -> `27 passed`
- `python -m pytest -q tldw_Server_API/tests/TTS_NEW/unit/test_tts_validation_qwen3.py` -> `9 passed`
- `python -m pytest -q tldw_Server_API/tests/TTS_NEW/unit/adapters/test_qwen3_tts_adapter.py` -> `14 passed`
- `python -m pytest -q tldw_Server_API/tests/TTS_NEW/integration/test_qwen3_streaming.py tldw_Server_API/tests/TTS_NEW/integration/test_qwen3_voice_prompt_reuse.py` -> `3 passed`
- `python -m pytest -q tldw_Server_API/tests/TTS_NEW/integration/test_tokenizer_endpoints.py tldw_Server_API/tests/TTS_NEW/unit/test_tokenizer_service_qwen3.py tldw_Server_API/tests/TTS/test_tts_adapters.py::TestTTSAdapterFactory::test_get_provider_for_model_alias` -> `12 passed`
- `python -m bandit -r <touched_paths> -f json -o /tmp/bandit_qwen3_tts_runtime_hardening.json`:
  - No new high/medium findings in changed code.
  - Remaining low-severity findings are pre-existing generic checks (`B105`/`B112`) in tokenizer modules.
