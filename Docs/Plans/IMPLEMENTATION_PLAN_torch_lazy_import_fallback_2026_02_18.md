## Stage 1: Identify Fatal Import Surfaces
**Goal**: Confirm which modules still execute `torch` import at module load and can abort test collection/startup.
**Success Criteria**: List finalized; target modules selected for lazy import refactor.
**Tests**: `rg "^import torch|try:\\s*import torch"` and import smoke checks.
**Status**: Complete

## Stage 2: Refactor to True Lazy Torch Imports
**Goal**: Remove module-level `torch` imports from targeted TTS/STT modules and replace with runtime loader helpers.
**Success Criteria**: No module-level `torch` import remains in targeted files; behavior degrades gracefully when torch unavailable.
**Tests**: `py_compile` on edited modules; direct module import smoke tests.
**Status**: Complete

## Stage 3: Stabilize TTS Adapter Tests
**Goal**: Remove top-level `torch` imports from TTS adapter tests and patch adapter-local helpers instead of `torch.*`.
**Success Criteria**: TTS test module collection no longer aborts from `torch` import.
**Tests**: Focused `pytest` runs on adapter mock tests.
**Status**: Complete

## Stage 4: Regression Verification
**Goal**: Verify prompt integration and related fallback tests still run cleanly.
**Success Criteria**: Prior crash path remains resolved; only unrelated functional failures remain.
**Tests**: Prompt integration suite + lazy import unit tests.
**Status**: Complete

### Progress Notes (2026-02-18)
- Added shared torch import preflight guard in `/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/Utils/torch_import_guard.py` to prevent parent-process aborts when `import torch` is unstable.
- Wired guarded torch loading into:
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/Local_LLM/Huggingface_Handler.py`
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/TTS/adapters/kokoro_adapter.py`
- Reordered Kokoro PyTorch init to validate model path before torch import, so missing-model tests fail fast without attempting torch import.
- Hardened HF unit tests to preflight `transformers/torch` in subprocess and skip module safely when runtime import is not viable:
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/tests/Local_LLM/test_huggingface_handler.py`
- Added guard-specific unit coverage:
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/tests/unit/test_torch_import_guard.py`
