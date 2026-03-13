# MinerU PDF OCR Implementation Plan

## Stage 1: Discovery And Adapter Skeleton
**Goal**: Surface MinerU in OCR discovery and create the PDF-oriented adapter module.
**Success Criteria**: `/api/v1/ocr/backends` includes MinerU capability metadata without changing generic OCR registry behavior.
**Tests**: `python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_mineru_discovery.py -v`
**Status**: Complete

## Stage 2: CLI Execution And Normalization
**Goal**: Run MinerU as a document-level CLI tool and normalize its output into a bounded, versioned schema.
**Success Criteria**: Command construction, timeout handling, page reconstruction, table extraction, and bounded artifacts are covered by unit tests.
**Tests**: `python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_mineru_adapter.py -v`
**Status**: Complete

## Stage 3: PDF Pipeline Integration
**Goal**: Route `ocr_backend=mineru` through the document adapter inside the PDF pipeline while preserving non-MinerU flows.
**Success Criteria**: `always` and `fallback` behavior work for MinerU, ignored parameter warnings are attached, and parser text survives MinerU failures.
**Tests**: `python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_mineru_pdf_pipeline.py tldw_Server_API/tests/Media_Ingestion_Modification/test_ocr_structured_output.py -v`
**Status**: Complete

## Stage 4: OCR Evaluation Support
**Goal**: Teach OCR evaluation to read MinerU page slices from the normalized structured payload.
**Success Criteria**: Per-page metrics work when `pages[]` exists, and explicit warnings appear when page slices are unavailable.
**Tests**: `python -m pytest tldw_Server_API/tests/Evaluations/test_mineru_ocr_evaluator.py -v`
**Status**: Complete

## Stage 5: Config Contract, Docs, And Verification
**Goal**: Finalize MinerU config discovery, document the user-facing behavior, and verify the touched scope.
**Success Criteria**: Config metadata is surfaced, docs mention PDF-only opt-in behavior and env vars, focused tests pass, and Bandit is clean on the touched application scope.
**Tests**: `python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_mineru_config_contract.py -v`
**Status**: Complete
