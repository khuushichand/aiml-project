# Implementation Plan: World Books - Import and Export

## Scope

Components: Import modal, JSON parsing/validation, preview UI, format conversion, and export entry points.
Finding IDs: `6.1` through `6.6`

## Finding Coverage

- Import guidance and conflict semantics: `6.1`, `6.5`
- Import preview depth and diagnostics: `6.2`
- Ecosystem interoperability: `6.3`
- Export breadth and ergonomics: `6.4`
- UI consistency with design system: `6.6`

## Stage 1: Document and Validate Native Import Flow
**Goal**: Make native import behavior predictable for first-time users.
**Success Criteria**:
- Add inline format help with expected JSON schema and required fields.
- Improve human-readable parse/validation errors for common failure cases.
- Add explicit merge-on-conflict tooltip based on verified backend merge semantics.
**Tests**:
- Unit tests for error classification and message mapping.
- Component tests for format-help expansion and conflict-tooltip visibility.
- Integration tests for required-field and malformed-JSON validation behavior.
**Status**: Complete

## Stage 2: Expand Import Preview Depth
**Goal**: Let users inspect payload quality before committing import.
**Success Criteria**:
- Extend preview to include world-book settings (scan depth, token budget, recursive flags).
- Add expandable first-N entries preview (keywords + truncated content).
- Keep performance acceptable for large files by limiting initial preview render.
**Tests**:
- Component tests for settings and entry preview rendering.
- Regression tests for preview truncation/expansion behavior.
- Performance sanity test for large import file preview.
**Status**: Complete

## Stage 3: Add SillyTavern and Kobold Conversion Support
**Goal**: Support common external lorebook formats without manual rewrite.
**Success Criteria**:
- Detect native vs SillyTavern vs Kobold input formats.
- Convert supported external fields into internal world-book and entry schema.
- Show conversion warnings for unsupported/approximate field mappings.
**Tests**:
- Unit tests with fixed conversion fixtures for both external formats.
- Integration tests for detected format -> converted preview -> successful import.
- Contract tests ensuring converted entries pass existing validators.
**Status**: Complete

## Stage 4: Improve Export UX and File Picker Consistency
**Goal**: Make export/import operations consistent and scalable.
**Success Criteria**:
- Add `Export All` and selected-book export options in the page header/actions.
- Replace raw file input with styled Ant Design upload control or drop zone.
- Keep single-book export path intact for row-level quick actions.
**Tests**:
- Integration tests for single-book and all-books export payload generation.
- Component tests for upload control interactions and accepted-file constraints.
- Regression tests for file-selection and submit flow parity with existing behavior.
**Status**: Complete

## Dependencies

- External format conversion should share parser utilities with Category 4 bulk workflows.
- Merge behavior copy must be confirmed against backend implementation before release.

## Progress Notes (2026-02-18)

- Implemented Stage 1 import guidance and validation UX in `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/Manager.tsx`:
  - added expandable **Format help** content in the import modal with expected native JSON structure and required fields.
  - added merge-on-conflict tooltip guidance (`Merge on conflict help`) with backend-aligned behavior copy.
  - improved file-parse and validation handling with clearer user-facing errors:
    - malformed JSON messaging.
    - missing `world_book` field detection for native-shaped payloads.
    - missing/empty entries detection (`found 0 entries`).
- Implemented Stage 1 import validation helpers in `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/worldBookInteropUtils.ts`:
  - `getWorldBookImportJsonErrorMessage`
  - `validateWorldBookImportConversion`
  - `WORLD_BOOK_IMPORT_MERGE_HELP_TEXT`
- Added/updated tests:
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/__tests__/worldBookInteropUtils.test.ts`
    - adds JSON parse message mapping coverage and conversion validation coverage.
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.importExportStage1.test.tsx`
    - covers format-help expansion, merge-tooltip visibility, malformed JSON handling, and required-field validation paths.
- Validation run:
  - `bunx vitest run src/components/Option/WorldBooks/__tests__` (from `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui`)
  - result: **25 passed / 25 files**, **72 passed / 72 tests**.
- Implemented Stage 2 import preview depth in `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/Manager.tsx`:
  - preview now includes world-book settings (scan depth, token budget, recursive scanning, enabled).
  - added expandable first-5 entry preview with keyword tags, truncated content preview, and "showing first N of total" copy.
- Implemented Stage 3 conversion flow coverage:
  - validated Kobold conversion path end-to-end in `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.importExportStage3.test.tsx`.
  - added conversion contract coverage for SillyTavern and Kobold payload validity in `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/__tests__/worldBookInteropUtils.test.ts`.
- Implemented Stage 4 export/upload UX in `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/Manager.tsx`:
  - added header-level `Export All` action.
  - added selection-bar `Export selected` action.
  - kept row-level single-book export, refactored through shared export helper.
  - replaced raw file input with Ant Design `Upload` trigger button for import file selection.
- Added/updated Stage 4 tests:
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.importExportStage4.test.tsx`
    - verifies single export, export-all bundle, selected-export bundle, and upload control behavior.
  - adjusted import upload helpers to target Ant Upload's file input in:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.importExportStage1.test.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.importExportStage2.test.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.importExportStage3.test.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.bulkOperationsStage4.test.tsx`
- Validation run (targeted import/export scope):
  - `bunx vitest run src/components/Option/WorldBooks/__tests__/WorldBooksManager.importExportStage1.test.tsx src/components/Option/WorldBooks/__tests__/WorldBooksManager.importExportStage2.test.tsx src/components/Option/WorldBooks/__tests__/WorldBooksManager.importExportStage3.test.tsx src/components/Option/WorldBooks/__tests__/WorldBooksManager.importExportStage4.test.tsx src/components/Option/WorldBooks/__tests__/WorldBooksManager.bulkOperationsStage4.test.tsx`
  - result: **5 passed / 5 files**, **11 passed / 11 tests**.
