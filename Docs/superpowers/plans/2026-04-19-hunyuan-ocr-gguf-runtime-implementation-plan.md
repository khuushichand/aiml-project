# Hunyuan OCR GGUF Runtime Implementation Plan

## Stage 1: Registry Contract And Family-Aware Auto Selection
**Goal**: Add a backend-level auto-eligibility hook and use it for generic OCR auto-selection so `hunyuan` can participate without backend-name special cases.
**Success Criteria**: `OCRBackend` exposes `auto_eligible(high_quality: bool)`, `registry.get_backend("auto")` and `registry.get_backend("auto_high_quality")` consult it, and explicit `get_backend("hunyuan")` still bypasses the hook.
**Tests**: `python -m pytest -q tldw_Server_API/tests/Media_Ingestion_Modification/test_ocr_runtime_auto_selection.py tldw_Server_API/tests/Media_Ingestion_Modification/test_hunyuan_ocr_backend.py -k "auto_eligible or explicit_hunyuan"`
**Status**: Complete

## Stage 2: Shared Runtime Parsing For Hunyuan GGUF
**Goal**: Extend OCR runtime parsing so Hunyuan GGUF can load `remote`, `managed`, and `cli` profiles from explicit environment keys instead of the existing `<PREFIX>_OCR_*` shape.
**Success Criteria**: Shared runtime helpers can parse explicit-key Hunyuan llama.cpp config, including distinct model, model path, and argv surfaces for remote vs managed vs cli.
**Tests**: `python -m pytest -q tldw_Server_API/tests/Media_Ingestion_Modification/test_ocr_runtime_support.py tldw_Server_API/tests/Media_Ingestion_Modification/test_hunyuan_llamacpp_runtime.py -k "explicit_keys or hunyuan_llamacpp"`
**Status**: Complete

## Stage 3: Hunyuan Backend GGUF Family Integration
**Goal**: Add the Hunyuan llama.cpp GGUF runtime helper and make `ocr_backend=hunyuan` orchestrate between native and GGUF families while preserving the existing OCR result contract.
**Success Criteria**: `HunyuanOCRBackend` resolves `HUNYUAN_RUNTIME_FAMILY`, uses stricter native readiness checks, delegates GGUF execution to a dedicated helper, and preserves structured OCR output and prompt preset behavior.
**Tests**: `python -m pytest -q tldw_Server_API/tests/Media_Ingestion_Modification/test_hunyuan_llamacpp_runtime.py tldw_Server_API/tests/Media_Ingestion_Modification/test_hunyuan_ocr_backend.py`
**Status**: Complete

## Stage 4: Discovery And PDF Pipeline Coverage
**Goal**: Expose namespaced Hunyuan discovery metadata and verify that PDF OCR ingestion continues to report stable structured metadata for both native and GGUF families.
**Success Criteria**: `/api/v1/ocr/backends` keeps backward-compatible top-level Hunyuan fields, adds `native` and `llamacpp` sub-objects, and PDF OCR tests cover both family paths.
**Tests**: `python -m pytest -q tldw_Server_API/tests/Media_Ingestion_Modification/test_ocr_runtime_discovery.py tldw_Server_API/tests/Media_Ingestion_Modification/test_hunyuan_ocr_pdf_pipeline.py`
**Status**: Complete

## Stage 5: Documentation And Final Verification
**Goal**: Document the new Hunyuan family split and verify the touched OCR scope is green and free of new Bandit findings.
**Success Criteria**: OCR docs describe `HUNYUAN_RUNTIME_FAMILY` and `HUNYUAN_LLAMACPP_*`, targeted OCR tests pass, and Bandit reports no new issues in touched Python files.
**Tests**: `python -m pytest -q tldw_Server_API/tests/Media_Ingestion_Modification` and `python -m bandit -r tldw_Server_API/app/core/Ingestion_Media_Processing/OCR tldw_Server_API/app/api/v1/endpoints/ocr.py tldw_Server_API/app/api/v1/schemas/ocr_schemas.py -f json -o /tmp/bandit_hunyuan_ocr_gguf.json`
**Status**: Complete
