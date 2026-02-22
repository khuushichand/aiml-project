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
**Status**: Complete

**Implementation Notes (2026-02-18)**:
- Added `ManageSortBy` options and sorting pipeline support in `useManageQuery`.
  - Server-side order mapping: `due -> due_at`, `created -> created_at`, other modes fall back to `due_at`.
  - Client-side sorting modes: `due`, `created`, `ease`, `last_reviewed`, `front_alpha`.
- Added Cards tab sort selector in `ManageTab` with options:
  - Due date
  - Created
  - Ease factor
  - Last reviewed
  - Front (A-Z)
- Applied selected sort mode consistently to the cross-results bulk fetch path used by bulk actions.
- Added multi-tag filter chips with autocomplete suggestions sourced from existing card tags.
- Added bulk add/remove tag actions in the floating selection bar, including modal-driven multi-tag input and chunked updates.

**Validation Completed**:
- `useFlashcardQueries.sorting.test.ts` (sort mapping + client sort behavior)
- `ManageTab.scheduling-metadata.test.tsx` (sort control + multi-tag chip/suggestion behavior)
- `ManageTab.undo-stage3.test.tsx` (bulk add/remove tag update payloads)
- `src/components/Flashcards/**/__tests__/*.test.tsx` + `flashcards-shortcut-hint-telemetry.test.ts` (full flashcards regression run)

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
**Status**: Complete

**Implementation Notes (2026-02-18)**:
- Added JSON/JSONL import path in UI with explicit import mode selector (`Delimited` vs `JSON / JSONL`) and auto-detection hinting (`JSON`, `JSONL`, or unknown).
- Added frontend service upload support for `/api/v1/flashcards/import/json` and corresponding mutation hook.
- Extended export UI with:
  - deck + tag + text query filters
  - include-reverse toggle
  - CSV/TSV delimiter selector
  - include-header and extended-header toggles
  - live export preview summary with count + effective filters
- Updated CSV/TSV export download naming to align with delimiter (`.tsv` for tab, `.csv` otherwise).

**Validation Completed**:
- `ImportExportTab.import-results.test.tsx`:
  - JSON/JSONL import routing
  - export option/query/filter parameter mapping
  - existing import result and rollback regressions
- `src/components/Flashcards/**/__tests__/*.test.tsx` + `flashcards-shortcut-hint-telemetry.test.ts` (full flashcards regression run)

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
**Status**: Complete

**Implementation Notes (2026-02-18)**:
- Added backend endpoint `POST /api/v1/flashcards/generate` that wraps the existing workflows `flashcard_generate` adapter and normalizes generated card payloads.
- Added frontend service and mutation support for generation requests with config:
  - `text`, `num_cards`, `card_type`, `difficulty`, `focus_topics`, `provider`, `model`
- Added new Generate panel in Flashcards Transfer tab:
  - text input + generation config controls
  - editable generated-card preview (front/back/tags)
  - save-to-deck flow with automatic deck fallback creation when no decks exist
- Added generation failure guidance that points users to provider/model checks and lower-complexity retries.

**Validation Completed**:
- `ImportExportTab.import-results.test.tsx`:
  - generate preview/edit/save flow
  - existing import/export regressions retained
- `src/components/Flashcards/**/__tests__/*.test.tsx` + `flashcards-shortcut-hint-telemetry.test.ts` (full flashcards regression run)
- `python -m compileall` for modified backend flashcards endpoint/schema/test modules

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
**Status**: Complete

**Implementation Notes (2026-02-18)**:
- Added cross-surface generate handoff helpers (`buildFlashcardsGenerateRoute`, parser helpers for search/hash routes) so source pages can deep-link to Flashcards Transfer with prefilled generation text/context.
- Updated `FlashcardsManager` to detect generate intent on load and open the Transfer tab automatically.
- Updated Generate panel to:
  - consume deep-link prefill text/context
  - show source-context notice
  - attach `source_ref_type` / `source_ref_id` on saved generated cards when launched from context
- Added Media entry point:
  - Content viewer Actions menu now includes "Generate flashcards from content"
  - routes to `/flashcards` with media context + content prefill
- Added Notes entry point:
  - Notes header action "Generate cards" routes to `/flashcards` with note content + note source metadata
- Added Chat surface entry point:
  - Sidepanel "Save to Notes" modal now includes "Generate flashcards"
  - opens options `/flashcards` route with message/session context and selected text prefill
- Permissions/quota behavior remains consistent by funneling all entry points through existing flashcard generate/create APIs (same server-side validation and limits used by native Transfer flow).

**Validation Completed**:
- `flashcards-generate-handoff.test.ts`:
  - route build mapping
  - search/hash parse behavior
- `FlashcardsManager.consistency.test.tsx`:
  - transfer tab auto-opens when generate intent is present in URL
- `ImportExportTab.import-results.test.tsx`:
  - deep-link prefill render
  - source attribution persisted on generated-card save
- Regression coverage:
  - `src/components/Flashcards/**/__tests__/*.test.tsx` + `flashcards-shortcut-hint-telemetry.test.ts`
  - `ContentViewer.stage4.accessibility.test.tsx`
  - `ContentViewer.stage14.export.test.tsx`
  - `NotesManagerPage.stage3.toolbar-metrics.test.tsx`

## Dependencies

- Stage 3 and Stage 4 depend on stable `flashcard_generate` adapter contracts.
- Stage 1 tag/sort behavior should align with existing query pagination constraints.
- Stage 2 and Stage 3 UX copy should reuse H2/H10 language for consistency.

## Post-Completion Remediation (2026-02-19)

- Follow-up plan: `Docs/Plans/IMPLEMENTATION_PLAN_flashcards_findings_remediation_2026_02_19.md` (Stages 3 and 4).
- Resolved generated-card partial-save retention bug in `ImportExportTab`:
  - previous behavior removed drafts by aggregate success count;
  - updated behavior removes only successfully saved drafts by stable draft ID, preserving failed drafts for retry.
- Extended APKG import flow with large-import confirmation parity:
  - APKG size-based estimated card count
  - APKG large-file threshold gating
  - APKG-specific confirm modal summary (file name, size, estimated items).
