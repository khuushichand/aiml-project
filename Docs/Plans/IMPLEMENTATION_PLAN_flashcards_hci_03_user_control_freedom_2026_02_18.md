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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: Not Started

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
