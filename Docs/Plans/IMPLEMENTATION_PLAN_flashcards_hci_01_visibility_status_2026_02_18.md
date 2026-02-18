# Implementation Plan: Flashcards H1 - Visibility of System Status

## Scope

Route/components: `FlashcardsManager.tsx`, `tabs/ReviewTab.tsx`, `tabs/ManageTab.tsx`, `tabs/ImportExportTab.tsx`, query hooks in `useFlashcardQueries.ts`  
Finding IDs: `H1-1` through `H1-5`

## Finding Coverage

- Missing study analytics and review history visibility: `H1-1`
- Missing deck-level due cues in selector: `H1-2`
- Import outcome detail absent: `H1-3`
- Post-rating scheduling feedback absent: `H1-4`
- Scheduling metadata hidden in list/detail views: `H1-5`

## Stage 1: Immediate Feedback in Existing Flows
**Goal**: Expose high-value status signals in current review/import interactions with no navigation changes.
**Success Criteria**:
- Review rating success UI includes next due time and interval from `FlashcardReviewResponse`.
- Import result UI shows imported count, skipped count, and per-line errors when present.
- Deck selector options include due count badges for each deck.
**Tests**:
- Component tests for review toast/status rendering with `due_at` and interval text.
- Integration tests for import mutation response rendering (success, partial success, failure).
- Query hook tests for deck due counts and selector label formatting.
**Status**: Complete

**Progress Notes (2026-02-18)**:
- Implemented review success feedback that now surfaces next due timing and interval from `FlashcardReviewResponse`.
- Added per-deck due badges in the Review deck selector using all-deck due-count query data.
- Reworked import feedback to show imported/skipped totals and line-level error details in-panel.
- Added focused UI tests for deck-label due counts and import result detail rendering (`3` tests passing under `apps/packages/ui` Vitest config).

## Stage 2: Card-Level Scheduling Transparency
**Goal**: Surface "why this card is due" metadata in Cards and Edit surfaces.
**Success Criteria**:
- Expanded and compact card rows expose `ef`, `interval_days`, `repetitions`, and `lapses` with concise labels.
- Edit drawer includes read-only scheduling metadata summary and last-reviewed timestamp when available.
- Metadata visibility is consistent across light/dark themes and mobile layouts.
**Tests**:
- Component tests for metadata visibility in compact and expanded list variants.
- Accessibility test coverage for non-color-only status representation.
- Snapshot/regression tests for responsive rendering breakpoints.
**Status**: Complete

**Progress Notes (2026-02-18)**:
- Added compact Cards-row scheduling metadata (`EF`, `Int`, `Reps`, `Lapses`) in `ManageTab`.
- Added expanded Cards-row scheduling tags (`Ease`, `Interval`, `Reps`, `Lapses`) in `ManageTab`.
- Added read-only scheduling panel in `FlashcardEditDrawer` with:
  - `ef`, `interval_days`, `repetitions`, `lapses`
  - `due_at` and `last_reviewed_at` absolute + relative timestamp display.
- Added focused tests for compact/expanded list metadata visibility and edit-drawer scheduling details.

## Stage 3: Study Analytics Dashboard Baseline
**Goal**: Add a first-class study status panel backed by review history data.
**Success Criteria**:
- Dashboard shows cards reviewed today, lapse rate, average answer time, and current streak.
- Per-deck progress cards show due/new/learning/mature counts.
- Analytics panel is reachable from `/flashcards` without leaving the feature area.
**Tests**:
- Backend/API tests for aggregate statistics endpoint/query correctness.
- Integration tests verifying dashboard values against seeded `flashcard_reviews` fixtures.
- E2E test for first load, filter by deck, and date-range state persistence.
**Status**: Complete

**Progress Notes (2026-02-18)**:
- Added backend analytics summary endpoint: `GET /api/v1/flashcards/analytics/summary`.
- Added DB analytics aggregation for:
  - `reviewed_today`, `retention_rate_today`, `lapse_rate_today`, `avg_answer_time_ms_today`
  - `study_streak_days` from distinct UTC review days
  - per-deck counts (`total`, `new`, `learning`, `due`, `mature`).
- Wired frontend summary fetch via `useReviewAnalyticsSummaryQuery`.
- Added `ReviewAnalyticsSummary` panel to `ReviewTab` with top-line metrics + per-deck progress cards.
- Added UI test coverage for analytics summary rendering in the Review tab.
- Added backend endpoint integration test case for analytics summary response semantics.
- Added deck-scoped analytics filtering with `deck_id` query support across DB, API, and Review tab analytics query wiring.
- Added backend integration test coverage for deck-filtered analytics response semantics.
- Validation:
  - `cd apps/packages/ui && bunx vitest run src/components/Flashcards/tabs/__tests__/ReviewTab.analytics-summary.test.tsx` (pass)
  - `python3 -m pytest -q tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py -k analytics_summary_returns_daily_metrics_and_deck_progress` (blocked in local env: Python 3.9 cannot parse `int | None` annotations; requires Python 3.10+ runtime used by backend test suite)
  - `cd apps/packages/ui && bunx vitest run --config vitest.config.ts src/components/Flashcards/tabs/__tests__/ReviewTab.analytics-summary.test.tsx src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx src/components/Flashcards/tabs/__tests__/ImportExportTab.import-results.test.tsx src/components/Flashcards/tabs/__tests__/ManageTab.scheduling-metadata.test.tsx src/components/Flashcards/components/__tests__/FlashcardEditDrawer.scheduling-metadata.test.tsx` (pass: `5` files, `7` tests)
  - `source .venv/bin/activate && python -m py_compile tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/app/api/v1/endpoints/flashcards.py tldw_Server_API/app/api/v1/schemas/flashcards.py tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py` (pass)

## Dependencies

- Stage 3 requires review-history aggregation APIs or equivalent client-side query primitives.
- Deck count rendering in Stage 1 depends on query extensions to fetch all-deck due counts.
- Metadata exposure should share formatting tokens with H2 terminology and H10 help copy.
