# Implementation Plan: Notes Page - Export & Sharing

## Scope

Components/pages: list export dropdown, single-note export/copy actions, prospective import UI and API endpoints.
Finding IDs: `7.1` through `7.8`

## Finding Coverage

- Preserve existing strong multi-format bulk export baseline: `7.1`, `7.4`
- Improve single-note parity and metadata fidelity: `7.2`, `7.3`, `7.7`
- Add import capability for portability: `7.5`
- Improve long-running export communication and print path: `7.6`, `7.8`

## Stage 1: Single-Note Export and Copy Parity
**Goal**: Make single-note operations match bulk-export flexibility.
**Success Criteria**:
- Add single-note format options (MD/JSON, optional CSV where sensible).
- Include keywords in markdown export via frontmatter or explicit tags line.
- Add copy modes (`content only`, `markdown with title`).
**Tests**:
- Unit tests for format builders and metadata inclusion.
- Integration tests for export menu action routing.
- Clipboard behavior tests for each copy mode.
**Status**: Complete

## Stage 2: Import Workflow (JSON and Markdown)
**Goal**: Enable data portability into notes ecosystem.
**Success Criteria**:
- Add import UI for JSON (matching export format) and markdown files.
- Add/extend backend import endpoint with validation and error reporting.
- Provide duplicate-handling strategy (skip/overwrite/create copy).
**Tests**:
- API tests for valid/invalid import payloads and partial-success reporting.
- Integration tests for file selection, preview, and import completion states.
- Regression tests for round-trip export->import fidelity.
**Status**: Complete

## Stage 3: Bulk Export Feedback and Print/PDF Path
**Goal**: Improve trust during long export and offline sharing workflows.
**Success Criteria**:
- Show preflight warning when projected export size exceeds threshold.
- Add progress feedback (`Exporting X of Y`) for chunked exports.
- Add print-friendly preview stylesheet and evaluate PDF export path.
**Tests**:
- Integration tests for preflight warnings and progress updates.
- Snapshot tests for print stylesheet output.
- Decision record for client-print vs server-PDF architecture.
**Status**: Complete

## Dependencies

- Bulk action handling should align with selection model from Plan 01.
- Error and partial-success messaging should align with Plan 13 standards.

## Progress Notes (2026-02-18)

### Stage 1 completion

- Added reusable single-note export/copy builders:
  - `/apps/packages/ui/src/components/Notes/export-utils.ts`
    - markdown builder with keyword frontmatter support
    - JSON export builder
    - copy-mode builder (`content`, `markdown`)
- Updated single-note actions in:
  - `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
    - single-note copy supports content and markdown modes
    - single-note export supports markdown and JSON formats
    - markdown export path now includes keyword metadata via shared builder
- Updated editor-header action controls in:
  - `/apps/packages/ui/src/components/Notes/NotesEditorHeader.tsx`
    - copy and export now use dropdown action menus for per-format mode selection
- Added Stage 1 tests:
  - `/apps/packages/ui/src/components/Notes/__tests__/export-utils.test.ts`
    - unit coverage for markdown/json/copy builders
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage31.single-note-export-copy.test.tsx`
    - integration coverage for action routing and clipboard/export behavior

### Stage 2 completion

- Added import request/response schemas:
  - `/tldw_Server_API/app/api/v1/schemas/notes_schemas.py`
    - `NotesImportItem`, `NotesImportRequest`, `NotesImportFileResult`, `NotesImportResponse`
- Added notes import endpoint and parsing helpers:
  - `/tldw_Server_API/app/api/v1/endpoints/notes.py`
    - `POST /api/v1/notes/import`
    - supports JSON and markdown file payloads
    - duplicate strategies: `skip`, `overwrite`, `create_copy`
    - per-file partial-success/error reporting
- Added import trigger in list panel:
  - `/apps/packages/ui/src/components/Notes/NotesListPanel.tsx`
    - new Import action, offline/trash disabled states, loading state
- Added import modal workflow in notes manager:
  - `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
    - hidden multi-file input, format detection, note-count preview, duplicate strategy selector
    - import submit flow wired to backend endpoint and partial-success messaging
- Added Stage 2 tests:
  - `/tldw_Server_API/tests/Notes/test_notes_api_integration.py`
    - `test_import_notes_json_creates_notes_and_keywords`
    - `test_import_notes_skip_duplicate_ids`
    - `test_import_notes_round_trip_accepts_export_wrapper_payload`
    - `test_import_notes_partial_success_includes_parse_errors`
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage36.import-workflow.test.tsx`
    - integration coverage for file preview, payload submission, and partial-warning UI
- Validation runs:
  - `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Notes/test_notes_api_integration.py -k "import_notes"`
  - `source .venv/bin/activate && cd apps/packages/ui && bunx vitest run src/components/Notes/__tests__/NotesManagerPage.stage31.single-note-export-copy.test.tsx src/components/Notes/__tests__/NotesManagerPage.stage36.import-workflow.test.tsx`

### Stage 3 completion

- Bulk export feedback path validated and retained:
  - `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
    - preflight confirmation for very large exports
    - chunked export progress state updates
  - `/apps/packages/ui/src/components/Notes/NotesListPanel.tsx`
    - live progress indicator rendering (`Exporting X notes across Y batches`)
- Added print/PDF workflow for single-note exports:
  - `/apps/packages/ui/src/components/Notes/export-utils.ts`
    - `buildSingleNotePrintableHtml`
    - `SINGLE_NOTE_PRINT_STYLES` print stylesheet (`@media print`)
  - `/apps/packages/ui/src/components/Notes/NotesEditorHeader.tsx`
    - export menu now includes `Print / Save as PDF`
  - `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
    - handles `print` export mode and opens print window with actionable failure messaging
- Added Stage 3 tests:
  - `/apps/packages/ui/src/components/Notes/__tests__/export-utils.test.ts`
    - snapshot coverage for print stylesheet
    - sanitization and metadata checks for printable HTML
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage37.print-export.test.tsx`
    - verifies print-window HTML generation and print invocation
    - verifies blocked pop-up error handling
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage30.export-progress.test.tsx`
    - validates chunked export progress updates
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage35.export-preflight.test.tsx`
    - validates export preflight confirmation behavior
- Decision record:
  - `/Docs/Plans/DECISION_RECORD_notes_export_print_pdf_stage3_2026_02_18.md`
- Validation runs:
  - `source .venv/bin/activate && cd apps/packages/ui && bunx vitest run src/components/Notes/__tests__/export-utils.test.ts src/components/Notes/__tests__/NotesManagerPage.stage30.export-progress.test.tsx src/components/Notes/__tests__/NotesManagerPage.stage35.export-preflight.test.tsx src/components/Notes/__tests__/NotesManagerPage.stage37.print-export.test.tsx`
