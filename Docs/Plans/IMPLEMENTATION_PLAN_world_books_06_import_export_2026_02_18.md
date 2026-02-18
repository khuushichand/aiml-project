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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: Not Started

## Dependencies

- External format conversion should share parser utilities with Category 4 bulk workflows.
- Merge behavior copy must be confirmed against backend implementation before release.
