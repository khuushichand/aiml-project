# Implementation Plan: Flashcards H3 - User Control and Freedom

## Scope

Route/components: `tabs/ReviewTab.tsx`, `tabs/ManageTab.tsx`, `components/FlashcardEditDrawer.tsx`, flashcard mutations in query hooks/service layer  
Finding IDs: `H3-1` through `H3-4`

## Finding Coverage

- No edit affordance during review loop: `H3-1`
- No user-facing scheduling reset for a card: `H3-2`
- Undo coverage limited for non-delete operations: `H3-3`
- No cram/study-outside-schedule mode: `H3-4`

## Stage 1: Edit-In-Review Workflow
**Goal**: Remove forced context switching when a user discovers card errors while studying.
**Success Criteria**:
- Review card includes an "Edit" action that opens `FlashcardEditDrawer` in overlay mode.
- Save/cancel returns user to the same review position with preserved session counters.
- Keyboard shortcut (`E`) opens edit for the active review card.
**Tests**:
- Component tests for edit button visibility and drawer state transitions in review mode.
- Integration tests ensuring review progress counts remain stable through edit/save/cancel.
- E2E flow: review card -> edit typo -> save -> continue rating.
**Status**: Complete

**Progress Notes (2026-02-18)**:
- Added in-review `Edit` action button on the active review card.
- Wired `FlashcardEditDrawer` directly into `ReviewTab` as overlay-mode edit without leaving the review workflow.
- Added edit lifecycle callbacks in review context:
  - save: update mutation + in-place return to review
  - delete: remove current card + continue review queue context.
- Added keyboard shortcut support for edit (`E`) in `useFlashcardShortcuts` and wired it in `ReviewTab`.
- Added inline review shortcut hint text: `"Press E to edit this card"`.
- Added focused tests for:
  - drawer open/close from review card action
  - shortcut callback wiring for edit
  - shortcut parser mapping (`E -> edit`).
- Validation:
  - `cd apps/packages/ui && bunx vitest run --config vitest.config.ts src/components/Flashcards/hooks/__tests__/useFlashcardShortcuts.test.ts src/components/Flashcards/tabs/__tests__/ReviewTab.edit-in-review.test.tsx src/components/Flashcards/tabs/__tests__/ReviewTab.analytics-summary.test.tsx src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx` (pass: `4` files, `8` tests)

## Stage 2: Scheduling Reset and Safe Recovery Controls
**Goal**: Let users recover from poor scheduling states without destructive workarounds.
**Success Criteria**:
- Edit drawer exposes "Reset scheduling" action with confirmation and clear consequences.
- Reset clears/normalizes `ef`, `interval_days`, `repetitions`, and `lapses` to new-card defaults.
- Reset operation is audited in activity log/review history with timestamp.
**Tests**:
- Backend mutation tests for reset semantics and permission checks.
- Integration tests for reset confirmation, API success/failure, and UI state refresh.
- Regression tests ensuring reset does not delete card content or deck/tag associations.
**Status**: Complete

**Progress Notes (2026-02-18)**:
- Added backend scheduling reset pathway:
  - DB method: `reset_flashcard_scheduling(card_uuid, expected_version)`
  - API endpoint: `POST /api/v1/flashcards/{card_uuid}/reset-scheduling`
  - request body: `{ expected_version }` with optimistic-lock conflict handling.
- Reset semantics now normalize scheduling to new-card defaults:
  - `ef=2.5`, `interval_days=0`, `repetitions=0`, `lapses=0`
  - `last_reviewed_at=NULL`, `due_at=now`.
- Added reset control in `FlashcardEditDrawer` with explicit confirmation and consequence copy.
- Wired reset action in both edit contexts:
  - Cards tab (`ManageTab`)
  - Review tab overlay edit (`ReviewTab`).
- Audit coverage:
  - Reset executes as a flashcard update, so existing `flashcards_sync_update` trigger writes a timestamped `sync_log` entry (activity log trail).
- Added test coverage:
  - UI: reset confirmation and callback invocation in edit drawer.
  - Backend integration test case for reset semantics + version conflict path.
- Validation:
  - `cd apps/packages/ui && bunx vitest run --config vitest.config.ts src/components/Flashcards/hooks/__tests__/useFlashcardShortcuts.test.ts src/components/Flashcards/components/__tests__/FlashcardCreateDrawer.cloze-help.test.tsx src/components/Flashcards/components/__tests__/FlashcardEditDrawer.reset-scheduling.test.tsx src/components/Flashcards/components/__tests__/FlashcardEditDrawer.save.test.tsx src/components/Flashcards/components/__tests__/FlashcardEditDrawer.scheduling-metadata.test.tsx src/components/Flashcards/components/__tests__/KeyboardShortcutsModal.rating-scale.test.tsx src/components/Flashcards/tabs/__tests__/ManageTab.scheduling-metadata.test.tsx src/components/Flashcards/tabs/__tests__/ReviewTab.analytics-summary.test.tsx src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx src/components/Flashcards/tabs/__tests__/ReviewTab.edit-in-review.test.tsx` (pass: `10` files, `16` tests)
  - `source .venv/bin/activate && python -m py_compile tldw_Server_API/app/api/v1/schemas/flashcards.py tldw_Server_API/app/api/v1/endpoints/flashcards.py tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py` (pass)
  - `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py -k \"analytics_summary or reset_scheduling\"` (blocked in current venv due missing project runtime dependency `loguru` plugin import).

## Stage 3: Expanded Undo and Session Control
**Goal**: Extend user control beyond review rating undo.
**Success Criteria**:
- Undo support added for bulk move and single-card edit (bounded window).
- Import workflow provides reversible staging or explicit rollback for recent batch.
- UI clearly communicates when undo is possible and when it expires.
**Tests**:
- Mutation tests for undo token lifecycle and expiration behavior.
- Integration tests for edit undo and bulk-move undo flows.
- Accessibility tests for timer announcements and undo affordances.
**Status**: Complete

**Progress Notes (2026-02-18)**:
- Added bounded undo support in Cards workflow for:
  - single-card edit save
  - single-card move
  - bulk move.
- Undo windows now use explicit expiry messaging in notification copy:
  - `"Undo within 30s ..."`
- Implemented rollback behavior:
  - edit undo restores previous card fields (deck/content/template/tags) using optimistic versioning.
  - move undo restores previous deck assignments for moved cards.
- Added integration tests validating:
  - undo notification is offered after edit and move mutations
  - invoking undo executes rollback mutation paths with expected payloads/version handling.
- Added import rollback support:
  - Import now offers a bounded undo window (`30s`) for each successful batch.
  - Undo uses imported card UUIDs from API response, resolves latest versions, and deletes imported cards in chunks.
  - Flashcard queries are invalidated after rollback to keep Cards/Review/metrics synchronized.
- Added import undo test coverage:
  - `ImportExportTab.import-results.test.tsx` now validates undo notification copy, duration, and rollback mutation behavior.
- Validation:
  - `cd apps/packages/ui && bunx vitest run --config vitest.config.ts src/components/Flashcards/hooks/__tests__/useFlashcardShortcuts.test.ts src/components/Flashcards/components/__tests__/FlashcardCreateDrawer.cloze-help.test.tsx src/components/Flashcards/components/__tests__/FlashcardEditDrawer.reset-scheduling.test.tsx src/components/Flashcards/components/__tests__/FlashcardEditDrawer.save.test.tsx src/components/Flashcards/components/__tests__/FlashcardEditDrawer.scheduling-metadata.test.tsx src/components/Flashcards/components/__tests__/KeyboardShortcutsModal.rating-scale.test.tsx src/components/Flashcards/tabs/__tests__/ManageTab.scheduling-metadata.test.tsx src/components/Flashcards/tabs/__tests__/ManageTab.undo-stage3.test.tsx src/components/Flashcards/tabs/__tests__/ReviewTab.analytics-summary.test.tsx src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx src/components/Flashcards/tabs/__tests__/ReviewTab.edit-in-review.test.tsx` (pass: `11` files, `18` tests)
  - `cd apps/packages/ui && bunx vitest run --config vitest.config.ts src/components/Flashcards/tabs/__tests__/ImportExportTab.import-results.test.tsx` (pass: `1` file, `2` tests)
  - `cd apps/packages/ui && bunx vitest run --config vitest.config.ts src/components/Flashcards/tabs/__tests__/ManageTab.undo-stage3.test.tsx src/components/Flashcards/tabs/__tests__/ReviewTab.edit-in-review.test.tsx src/components/Flashcards/components/__tests__/FlashcardCreateDrawer.cloze-help.test.tsx src/components/Flashcards/components/__tests__/FlashcardEditDrawer.reset-scheduling.test.tsx src/components/Flashcards/components/__tests__/FlashcardEditDrawer.save.test.tsx` (pass: `5` files, `8` tests)

## Stage 4: Cram/Preview Study Mode
**Goal**: Support intentional study sessions outside SRS due queue.
**Success Criteria**:
- Review mode toggle supports "Due only" and "Cram/Preview" scopes.
- Cram mode can filter by deck and tags and optionally skip schedule updates.
- Session summary differentiates cram reviews from scheduled reviews.
**Tests**:
- Query tests for due-filter bypass and deck/tag subset behavior.
- E2E tests for cram session start, card traversal, and completion summary.
- Regression tests ensuring default due-only behavior remains unchanged.
**Status**: Not Started

## Dependencies

- Stage 1 depends on edit drawer reusability in Review context and optimistic lock handling.
- Stage 2 and Stage 3 should reuse H9 error messaging and retry semantics.
- Stage 4 scope controls should align with H7 filtering patterns and performance constraints.
