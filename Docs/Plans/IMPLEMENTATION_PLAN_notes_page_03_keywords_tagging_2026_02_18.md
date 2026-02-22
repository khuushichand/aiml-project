# Implementation Plan: Notes Page - Keywords & Tagging

## Scope

Components/pages: keyword select controls, keyword picker modal, backend keyword lifecycle endpoints/services.
Finding IDs: `3.1` through `3.7`

## Finding Coverage

- Preserve strong current patterns: `3.1`, `3.2`, `3.7`
- Frequency and prioritization visibility: `3.3`
- Hierarchy/visual differentiation improvements: `3.4`
- Keyword management lifecycle (rename/merge/delete): `3.5`
- Assisted keyword generation: `3.6`

## Stage 1: Frequency-Aware Keyword Selection UX
**Goal**: Improve keyword decision speed with data-informed signals.
**Success Criteria**:
- Show per-keyword note counts in filter dropdown and picker modal.
- Add sorting options by frequency and lexical order.
- Add recently used keyword section in picker modal.
**Tests**:
- Component tests for count rendering and sort-mode toggles.
- Integration tests for count accuracy against backend responses.
- Accessibility tests for grouped keyword navigation in modal.
**Status**: Complete

## Stage 2: Keyword Management Surface
**Goal**: Enable safe cleanup of keyword taxonomy drift.
**Success Criteria**:
- Provide keyword management entry point from browse-keywords modal.
- Add rename, merge, and delete workflows with confirmation and conflict handling.
- Extend backend API if required to support rename/merge operations atomically.
**Tests**:
- API tests for rename/merge/delete transactional correctness.
- Integration tests for UI state updates after management actions.
- Regression tests ensuring note-keyword relationships remain intact post-merge.
**Status**: Complete

## Stage 3: Visual Hierarchy and Assisted Suggestions
**Goal**: Improve keyword readability and reduce manual tagging overhead.
**Success Criteria**:
- Add optional visual hierarchy cues (frequency tint or user-defined color tags).
- Introduce AI-assisted keyword suggestion flow from note content.
- Keep suggestion acceptance explicit (no silent auto-attach).
**Tests**:
- Component tests for color/frequency rendering fallbacks.
- Integration tests for suggestion generation and selective acceptance.
- Safety tests ensuring no keywords attach without explicit user action.
**Status**: Complete

## Dependencies

- Keyword counts and filter semantics must align with Plans 01 and 04.
- AI suggestion strategy should reuse model/provider controls from Plan 08 where possible.

## Progress Notes (2026-02-18)

- Completed Stage 1 in:
  - `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
    - Added keyword-picker sort modes: frequency descending, alpha ascending, alpha descending.
    - Added recently-used keyword memory and surfaced it in picker reopen flows.
    - Wired recent-keyword updates from picker apply and direct filter-token changes.
  - `/apps/packages/ui/src/components/Notes/KeywordPickerModal.tsx`
    - Added sort control UI and recently-used keyword section at top.
    - Preserved per-keyword count rendering in both main list and recent actions.
- Added Stage 1 verification in:
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage24.keyword-picker-prioritization.test.tsx`
    - Validates frequency-default ordering, alphabetical sort toggles, and recent-keyword surfacing.
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage15.keyword-counts.test.tsx`
    - Confirms per-keyword count rendering remains correct in dropdown and modal.
- Completed Stage 2 backend/API lifecycle support in:
  - `/tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
    - Added atomic keyword rename with optimistic-lock version checks.
    - Added atomic keyword merge that migrates note/conversation/collection/flashcard links and soft-deletes source keyword.
  - `/tldw_Server_API/app/api/v1/schemas/notes_schemas.py`
    - Added `KeywordUpdate`, `KeywordMergeRequest`, and `KeywordMergeResponse` schemas.
  - `/tldw_Server_API/app/api/v1/endpoints/notes.py`
    - Added `PATCH /api/v1/notes/keywords/{keyword_id}` for rename workflow.
    - Added `POST /api/v1/notes/keywords/{keyword_id}/merge` for merge workflow.
- Completed Stage 2 UI management surface in:
  - `/apps/packages/ui/src/components/Notes/KeywordPickerModal.tsx`
    - Added in-modal "Manage keywords" entry point.
  - `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
    - Added keyword manager modal with rename, merge, and delete flows.
    - Added action-level conflict handling and post-action keyword/note refresh.
- Added Stage 2 verification in:
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage25.keyword-management.test.tsx`
    - Validates manager entrypoint and rename/merge/delete workflows.
  - `/tldw_Server_API/tests/Notes_NEW/unit/test_keyword_management_db.py`
    - Validates rename conflict behavior and merge relationship integrity at DB layer.
  - `/tldw_Server_API/tests/Notes_NEW/integration/test_notes_api.py`
    - Added API integration cases for rename and merge endpoint behavior.
- Completed Stage 3 visual hierarchy + assisted suggestion flow in:
  - `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
    - Added frequency-tone keyword labels for filter/editor/suggestion surfaces.
    - Replaced one-shot keyword-confirm prompt with a selectable suggestion modal.
    - Enforced explicit apply for suggested keywords (no automatic attachment).
  - `/apps/packages/ui/src/components/Notes/KeywordPickerModal.tsx`
    - Added frequency-tone visual markers to picker keyword labels with neutral fallback.
- Added Stage 3 verification in:
  - `/apps/packages/ui/src/components/Notes/__tests__/KeywordPickerModal.stage26.frequency-tone.test.tsx`
    - Validates high/medium/low frequency tones and neutral fallback when counts are missing.
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage10.ai-content-assist.test.tsx`
    - Validates selectable keyword suggestions apply only after explicit user confirmation.
    - Validates cancel path does not attach suggested keywords.
