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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: Not Started

## Dependencies

- Bulk action handling should align with selection model from Plan 01.
- Error and partial-success messaging should align with Plan 13 standards.
