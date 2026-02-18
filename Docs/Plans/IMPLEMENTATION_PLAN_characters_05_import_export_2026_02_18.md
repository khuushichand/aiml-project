# Implementation Plan: Characters - Import and Export Workflow

## Scope

Components: `apps/packages/ui/src/components/Option/Characters/Manager.tsx`, import/export utilities in `apps/packages/ui/src/utils/character-export.ts`, backend handlers in `tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py`
Finding IDs: `C-16` through `C-18`

## Finding Coverage

- Import is single-file only; no batch flow: `C-16`
- Import lacks pre-persist preview/confirmation: `C-17`
- YAML support mismatch between docs and accepted formats: `C-18`

## Stage 1: Enable Multi-File Batch Import
**Goal**: Reduce repetitive import overhead for large character libraries.
**Success Criteria**:
- Upload control supports multiple files and drag-drop batching.
- Import pipeline processes files sequentially (or bounded parallel) with per-file status.
- Final summary reports success/failure counts and error details by file.
**Tests**:
- Component tests for multi-file selection and progress state rendering.
- Integration tests for mixed valid/invalid file batches.
- E2E test covering drag-drop batch import flow.
**Status**: Not Started

## Stage 2: Add Import Preview and Confirmation Step
**Goal**: Let users validate imported character details before persistence.
**Success Criteria**:
- Parsed character metadata preview displays name, description, avatar thumbnail, and detected fields.
- User can confirm or cancel before save.
- Preview handles malformed files with actionable error messaging.
**Tests**:
- Unit tests for parser-to-preview model mapping.
- Component tests for confirm/cancel paths.
- Integration tests for preview confirm -> persisted record consistency.
**Status**: Not Started

## Stage 3: Resolve YAML Support Contract
**Goal**: Align UI and documentation with actual supported formats.
**Success Criteria**:
- Either `.yaml`/`.yml` import support is implemented end-to-end, or docs and accept list explicitly remove YAML claims.
- Accept list and parser logic stay in sync.
- Unsupported format errors are clear and localized.
**Tests**:
- Unit tests for format detection and rejection messaging.
- Integration tests for YAML path if implemented, including malformed YAML handling.
- Documentation checklist confirming support matrix alignment.
**Status**: Not Started

## Stage 4: Export/Import Parity Validation
**Goal**: Ensure import enhancements do not break existing export compatibility.
**Success Criteria**:
- JSON/PNG/Markdown/TXT imports still work with preview and batch path enabled.
- Exported files round-trip successfully through new import pipeline.
- Error handling remains deterministic across mixed-format batches.
**Tests**:
- Round-trip integration tests: export -> import -> field parity assertion.
- Regression tests for existing single-file import behaviors.
**Status**: Not Started

## Dependencies

- YAML implementation path may require backend parser extension and schema normalization checks.
- Stage 2 preview should reuse existing character validation utilities to avoid duplicate parsing logic.
