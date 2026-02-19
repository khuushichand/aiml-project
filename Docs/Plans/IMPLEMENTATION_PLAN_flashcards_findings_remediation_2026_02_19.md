# Implementation Plan: Flashcards Findings Remediation (2026-02-19)

## Scope

This plan remediates the findings identified in the flashcards plan-vs-implementation review:

1. Source attribution fields are persisted but not returned in flashcard API responses.
2. Lapse-rate metric is computed in analytics but not displayed in the Review analytics panel.
3. Generated-card partial-save flow removes drafts by count rather than by actual save result.
4. Large-import confirmation does not apply to APKG imports.

## Stage 1: Restore Source Attribution API Contract
**Goal**: Ensure source metadata is consistently returned end-to-end so source badges/deep-links work in Manage, Review, and Edit surfaces.
**Success Criteria**:
- `Flashcard` API responses include `source_ref_type`, `source_ref_id`, `conversation_id`, and `message_id`.
- DB read paths (`list`, `get by uuid`, `get by uuids`) select and return the source columns.
- Response schema and OpenAPI reflect the source fields.
- Existing source badge/deep-link UI receives real API values without type assertions or fallback-only behavior.
**Tests**:
- Backend integration tests asserting source fields are present on `POST /api/v1/flashcards` response and subsequent `GET /api/v1/flashcards` / `GET /api/v1/flashcards/{uuid}` payloads.
- Frontend integration/component tests covering source badge rendering from real-shaped API payload fixtures in Manage/Review/Edit contexts.
- Contract test (or snapshot assertion) for flashcards schema/OpenAPI response shape including source fields.
**Status**: Complete

**Progress Notes (2026-02-19)**:
- Added source attribution fields to flashcard response schema:
  - `source_ref_type`
  - `source_ref_id`
  - `conversation_id`
  - `message_id`
- Updated flashcard DB read projections to return source fields from:
  - list query
  - single-card fetch query
  - bulk UUID fetch query
- Added backend integration coverage to assert source attribution fields are present and populated across create/list/get endpoint responses.
- Validation status:
  - `python -m py_compile` on changed flashcards schema/DB/test modules passes.
  - Backend endpoint integration subset passes with startup metadata validation override:
    - `PRIVILEGE_METADATA_VALIDATE_ON_STARTUP=0 python -m pytest -q tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py -k "source_attribution_fields_present_in_flashcard_responses or get_flashcard_alias_path_returns_card or create_flashcard_normalizes_model_fields or openapi_flashcard_response_includes_source_fields"`
    - Result: `4 passed, 43 deselected`.
  - Frontend source badge/deep-link coverage in Manage/Review/Edit contexts passes:
    - `bunx vitest run ../packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.scheduling-metadata.test.tsx ../packages/ui/src/components/Flashcards/tabs/__tests__/ReviewTab.edit-in-review.test.tsx ../packages/ui/src/components/Flashcards/components/__tests__/FlashcardEditDrawer.reset-scheduling.test.tsx` (from `apps/tldw-frontend`)
    - Result: `3 passed`, `9 tests passed`.

## Stage 2: Surface Lapse Rate in Review Analytics
**Goal**: Align Review analytics UI with documented and planned metrics by displaying lapse rate alongside existing top-line stats.
**Success Criteria**:
- `ReviewAnalyticsSummary` renders lapse rate with consistent formatting/fallback behavior (`—` when unavailable).
- i18n token(s) for lapse-rate label and any tooltip/help copy are added and used.
- Layout remains stable across mobile/desktop breakpoints (no overflow/regression in summary grid).
**Tests**:
- Update `ReviewTab.analytics-summary.test.tsx` to assert lapse-rate visibility and formatted value.
- Add/adjust component tests for null/undefined lapse-rate fallback rendering.
- Optional visual regression/snapshot update for analytics summary card layout.
**Status**: Complete

**Progress Notes (2026-02-19)**:
- Updated `ReviewAnalyticsSummary` to render `lapse_rate_today` alongside existing top-line metrics.
- Expanded analytics metrics grid to accommodate the additional lapse-rate card without collapsing key summary tiles.
- Added/updated i18n tokens for review analytics labels in English locale resources, including `flashcards.lapseRate`.
- Strengthened Review analytics tests to assert:
  - lapse-rate value rendering when present, and
  - fallback rendering (`—`) when lapse rate is absent.
- Validation status:
  - `bunx vitest run ../packages/ui/src/components/Flashcards/tabs/__tests__/ReviewTab.analytics-summary.test.tsx` (from `apps/tldw-frontend`) passes.
  - Focused flashcards source/analytics UI regression subset passes:
    - `bunx vitest run ../packages/ui/src/components/Flashcards/tabs/__tests__/ReviewTab.analytics-summary.test.tsx ../packages/ui/src/components/Flashcards/tabs/__tests__/ReviewTab.edit-in-review.test.tsx ../packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.scheduling-metadata.test.tsx ../packages/ui/src/components/Flashcards/components/__tests__/FlashcardEditDrawer.reset-scheduling.test.tsx` (from `apps/tldw-frontend`)
    - Result: `4 passed`, `12 tests passed`.

## Stage 3: Correct Generated-Card Partial Save Retention
**Goal**: Make generated-card save behavior deterministic and lossless by removing only successfully persisted drafts.
**Success Criteria**:
- Save flow tracks per-card outcomes (success/failure) by stable draft identity, not aggregate count.
- On partial success, only successfully saved drafts are removed; failed drafts remain editable/retryable.
- User feedback (`saved/failed`) remains accurate and consistent with actual outcomes.
**Tests**:
- Add `ImportExportTab.import-results.test.tsx` coverage for interleaved success/failure save scenarios and post-save draft list contents.
- Add regression test for all-success and all-failure save paths to verify no behavior regressions.
**Status**: Complete

**Progress Notes (2026-02-19)**:
- Fixed generated-card partial-save retention logic in `ImportExportTab` to remove saved drafts by stable draft identity (draft `id`) instead of aggregate `created` count.
- The save flow now tracks successful draft IDs during persistence and retains only failed drafts for user retry/edit.
- Added regression coverage for:
  - interleaved success/failure save outcomes (only failed draft remains),
  - all-success save path (drafts clear after successful save), and
  - all-failure save path (all drafts remain for retry).
- Validation status:
  - `bunx vitest run ../packages/ui/src/components/Flashcards/tabs/__tests__/ImportExportTab.import-results.test.tsx -t "supports generate preview, edit, and save flow|retains only failed generated drafts after partial save|keeps generated drafts when all generated-card saves fail"` (from `apps/tldw-frontend`) passes.
  - Result: `3 passed`, `13 skipped` (targeted subset).

## Stage 4: Apply Large-Import Confirmation to APKG
**Goal**: Extend high-risk import confirmation behavior so APKG imports also receive pre-execution confirmation when large.
**Success Criteria**:
- APKG mode computes/uses an estimated import item count (or equivalent large-file threshold) before import execution.
- Large APKG imports trigger the same confirmation modal pathway used for delimited/JSON imports.
- Confirmation copy in APKG mode includes relevant APKG-specific summary details (file name/size and estimated items where available).
**Tests**:
- Add `ImportExportTab.import-results.test.tsx` test that APKG large-import path requires confirmation before mutation call.
- Add APKG-mode summary content assertions in confirm modal.
- Regression tests for small APKG imports to ensure no unnecessary confirmation prompts.
**Status**: Complete

**Progress Notes (2026-02-19)**:
- Extended large-import confirmation gating to APKG mode.
- Added APKG import-size heuristics:
  - estimated card count derived from file size (`APKG_ESTIMATED_BYTES_PER_CARD`), and
  - explicit APKG large-file byte threshold (`LARGE_IMPORT_CONFIRM_THRESHOLD_APKG_BYTES`).
- Updated confirmation modal copy for APKG imports to include:
  - file name,
  - file size in bytes, and
  - estimated import card count.
- Added APKG-focused test coverage for:
  - baseline APKG routing through the APKG mutation path,
  - large APKG requiring explicit confirmation before mutation,
  - small APKG bypassing confirmation.
- Validation status:
  - `bunx vitest run ../packages/ui/src/components/Flashcards/tabs/__tests__/ImportExportTab.import-results.test.tsx -t "routes APKG imports through the APKG upload mutation|requires confirmation before importing large APKG files|imports small APKG files without confirmation"` (from `apps/tldw-frontend`) passes.
  - Combined Stage 3/4 generated-save + APKG subset also passes:
    - `bunx vitest run ../packages/ui/src/components/Flashcards/tabs/__tests__/ImportExportTab.import-results.test.tsx -t "supports generate preview, edit, and save flow|retains only failed generated drafts after partial save|keeps generated drafts when all generated-card saves fail|routes APKG imports through the APKG upload mutation|requires confirmation before importing large APKG files|imports small APKG files without confirmation"` (from `apps/tldw-frontend`)
    - Result: `6 passed`, `12 skipped` (targeted subset).

## Stage 5: Regression Sweep and Plan/Docs Reconciliation
**Goal**: Validate fixes holistically and reconcile status language in existing flashcards plan docs with shipped behavior.
**Success Criteria**:
- Targeted backend and frontend flashcards test suites pass for touched areas.
- No new TypeScript/Pydantic schema mismatch between API and client types for flashcards.
- Relevant existing plan docs/index are updated to reflect remediation completion state and any revised acceptance criteria.
**Tests**:
- Backend: flashcards endpoint integration subset (source fields, analytics summary, APKG import).
- Frontend: flashcards tab/component tests for analytics summary, source badges, import confirmation, and generate-save flow.
- Optional smoke run across `/flashcards` Review/Manage/Transfer tabs.
**Status**: Complete

**Progress Notes (2026-02-19)**:
- Completed targeted backend regression sweep for source-attribution API contract:
  - `PRIVILEGE_METADATA_VALIDATE_ON_STARTUP=0 python -m pytest -q tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py -k "source_attribution_fields_present_in_flashcard_responses or get_flashcard_alias_path_returns_card or create_flashcard_normalizes_model_fields or openapi_flashcard_response_includes_source_fields"`
  - Result: `4 passed`, `43 deselected`.
- Completed targeted frontend regression sweep for touched flashcards surfaces:
  - `bunx vitest run ../packages/ui/src/components/Flashcards/tabs/__tests__/ReviewTab.analytics-summary.test.tsx ../packages/ui/src/components/Flashcards/tabs/__tests__/ReviewTab.edit-in-review.test.tsx ../packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.scheduling-metadata.test.tsx ../packages/ui/src/components/Flashcards/components/__tests__/FlashcardEditDrawer.reset-scheduling.test.tsx ../packages/ui/src/components/Flashcards/tabs/__tests__/ImportExportTab.import-results.test.tsx -t "renders analytics metrics and deck progress cards|renders a fallback for missing lapse rate|opens edit drawer from the review card and returns to review on cancel|supports multi-tag filter chips with suggestions|confirms and invokes reset scheduling callback|supports generate preview, edit, and save flow|retains only failed generated drafts after partial save|keeps generated drafts when all generated-card saves fail|routes APKG imports through the APKG upload mutation|requires confirmation before importing large APKG files|imports small APKG files without confirmation"` (from `apps/tldw-frontend`)
  - Result: `5 files passed`, `11 tests passed`, targeted skips only.
- Additional full-file check on `ImportExportTab.import-results.test.tsx` confirms functional tests pass; remaining failure is an unrelated snapshot harness/setup issue (`SnapshotClient.setup()` not initialized in this invocation context).
- Reconciled related plan/docs references:
  - Updated HCI index paths to current completed-plan location.
  - Added post-remediation snapshot in HCI index referencing this remediation plan.
  - Added remediation addenda to:
    - `IMPLEMENTATION_PLAN_flashcards_hci_06_recognition_recall_2026_02_18.md`
    - `IMPLEMENTATION_PLAN_flashcards_hci_07_flexibility_efficiency_2026_02_18.md`
    - `IMPLEMENTATION_PLAN_flashcards_apkg_import_roundtrip_2026_02_18.md`

## Sequencing and Dependencies

- Stage 1 should land before Stage 5 and before any closure of H6/H7 source-attribution completion claims.
- Stage 3 and Stage 4 can proceed in parallel after Stage 1 begins.
- Stage 2 is frontend-only and can run in parallel with Stage 3/4.
- Stage 5 is final gating and documentation reconciliation.
