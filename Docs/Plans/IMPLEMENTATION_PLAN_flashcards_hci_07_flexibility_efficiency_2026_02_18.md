# Implementation Plan: Flashcards H7 - Flexibility and Efficiency of Use

## Scope

Route/components: `tabs/ManageTab.tsx`, `tabs/ImportExportTab.tsx`, `useFlashcardQueries.ts`, flashcard generation adapter integration surfaces  
Finding IDs: `H7-1` through `H7-5`

## Finding Coverage

- LLM card generation exists server-side but has no UI entry point: `H7-1`
- JSON/JSONL import is supported in API but missing in UI: `H7-2`
- Tag filtering is single-tag/no autocomplete: `H7-3`
- Sorting options are absent beyond due-date default: `H7-4`
- Bulk tag operations are missing from selection action bar: `H7-5`

## Stage 1: High-Leverage Management Controls
**Goal**: Improve throughput for power users in existing Cards workflows.
**Success Criteria**:
- Cards tab includes sort selector (due, created, ease, last reviewed, alpha where supported).
- Tag filter includes autocomplete suggestions and multi-tag query mode.
- Selection bar includes bulk add/remove tag actions.
**Tests**:
- Query hook tests for sort and multi-tag parameter serialization.
- Component tests for tag autocomplete behavior and selected-filter chips.
- E2E tests for bulk tag add/remove and list refresh correctness.
**Status**: Not Started

## Stage 2: Import Surface Parity (JSON/JSONL + Extended Options)
**Goal**: Expose backend import/export flexibility directly in the UI.
**Success Criteria**:
- Import panel supports JSON array and JSONL file ingestion with format detection.
- Export controls expose delimiter/header/reverse-card options already available in API.
- Users can preview export item count and effective filters before download.
**Tests**:
- Integration tests for JSON/JSONL import success/failure paths.
- Contract tests for export option mapping to endpoint query params.
- E2E tests for filtered export count and downloaded format expectations.
**Status**: Not Started

## Stage 3: LLM Generation MVP in Flashcards UI
**Goal**: Deliver first-class text-to-cards generation in-product.
**Success Criteria**:
- New "Generate cards" flow accepts input text and config (provider/model/difficulty/count/focus).
- Generated cards are previewable/editable before commit to deck.
- Generation failures produce actionable remediation (provider/model/token/context hints).
**Tests**:
- Integration tests for generate request/response mapping and validation.
- Component tests for preview-edit-commit loop and cancel behavior.
- E2E tests for full generation workflow from prompt to saved cards.
**Status**: Not Started

## Stage 4: Cross-Feature Generation Entry Points
**Goal**: Leverage tldw media and note context to generate cards from source artifacts.
**Success Criteria**:
- Media, notes, and chat surfaces can deep-link into prefilled flashcard generation flow.
- Source attribution is attached automatically to generated cards when launched from context.
- Permissions and quota limits are enforced consistently across entry points.
**Tests**:
- Integration tests for prefilled generation payload from each source type.
- E2E tests for "generate from source" to review-ready deck flow.
- Security tests for unauthorized source references and provider misuse.
**Status**: Not Started

## Dependencies

- Stage 3 and Stage 4 depend on stable `flashcard_generate` adapter contracts.
- Stage 1 tag/sort behavior should align with existing query pagination constraints.
- Stage 2 and Stage 3 UX copy should reuse H2/H10 language for consistency.
