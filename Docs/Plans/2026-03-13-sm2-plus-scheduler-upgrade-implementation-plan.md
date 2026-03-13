# SM-2+ Scheduler Upgrade Implementation Plan

Date: 2026-03-13
Status: Ready

## Goal

Upgrade the existing flashcard scheduler to an isolated SM-2+ engine with explicit queue state, deck-level settings, backend-selected next-card ordering, and queue-aware review history while preserving the current four-button study UI.

## Review Fixes Baked Into This Plan

- add a real deck update endpoint instead of assuming one exists
- add a backend-selected `review/next` path
- make `next_intervals` required in the review response
- store deck settings as `scheduler_settings_json TEXT`
- extend review history with explicit queue-state transitions
- rewrite due/new/learning filters and analytics to use queue state
- update sync-log payloads for new deck and flashcard fields

## Stage 1: Schema, Contracts, And Migration

**Goal**: Add the DB fields and API schemas required for SM-2+ without changing review behavior yet.

**Success Criteria**:
- `decks` stores `scheduler_settings_json`
- `flashcards` stores `queue_state`, `step_index`, and `suspended_reason`
- `flashcard_reviews` stores previous/next queue state and due timestamps
- sync triggers/log payloads include the new fields
- deck and review schemas expose the new typed data

**Tests**:
- migration/bootstrap tests for new columns
- schema validation tests for scheduler settings
- deck update schema tests
- review response schema tests

**Status**: Not Started

## Stage 2: Pure Scheduler Engine And Next-Card Selection

**Goal**: Move scheduling behavior into a pure scheduler module and add backend-owned next-card selection.

**Success Criteria**:
- a dedicated scheduler module computes transitions for new, learning, review, relearning, and suspended states
- `GET /api/v1/flashcards/review/next` returns the correct next card and required interval previews
- queue ordering is backend-defined: due learning/relearning, then due review, then new

**Tests**:
- scheduler unit tests for all queue transitions
- deterministic fuzz tests
- overdue-handling tests
- endpoint tests for `review/next` ordering and empty-queue behavior

**Status**: Not Started

## Stage 3: Wire Review, Reset, Filters, And Analytics

**Goal**: Replace the embedded DB scheduling path with the new scheduler and make queue-state semantics consistent everywhere.

**Success Criteria**:
- `POST /api/v1/flashcards/review` uses the pure scheduler
- review writes queue-state transitions into `flashcard_reviews`
- reset scheduling clears all new scheduler fields
- `list_flashcards`, `count_flashcards`, and analytics use queue-state semantics instead of legacy heuristics
- deck progress counters are consistent with the new queue model

**Tests**:
- integration tests for review persistence and response payloads
- reset scheduling tests
- list/count tests for `new`, `learning`, `due`, and `all`
- analytics summary regression tests

**Status**: Not Started

## Stage 4: Deck Settings API And WebUI Review Integration

**Goal**: Make deck settings editable and switch the WebUI review flow to backend-selected next cards and server interval previews.

**Success Criteria**:
- `PATCH /api/v1/flashcards/decks/{id}` supports optimistic locking and validation
- frontend deck types and deck mutation path support scheduler settings
- review hooks use `review/next` instead of client-side queue reconstruction
- review buttons display server-provided `next_intervals`
- keyboard shortcuts and rating values remain unchanged

**Tests**:
- endpoint tests for deck update conflicts and validation errors
- frontend hook tests for `review/next`
- review tab tests for interval preview rendering and unchanged shortcut behavior

**Status**: Not Started

## Stage 5: Verification, Docs, And Cleanup

**Goal**: Close the slice with explicit docs and regression evidence.

**Success Criteria**:
- flashcard guide reflects the upgraded scheduler behavior and deck settings
- implementation notes mention backend-selected queue ordering
- targeted backend and frontend suites pass
- Bandit shows no new findings in touched Python scope

**Tests**:
- targeted `pytest` for flashcard scheduler, endpoint, and DB coverage
- targeted `vitest` for review hooks/components
- `python -m bandit -r` over touched backend scheduler/endpoint files

**Status**: Not Started

## Execution Notes

- Keep the request rating values unchanged: `0`, `2`, `3`, `5`.
- Use `scheduler_settings_json TEXT` in the DB layer and typed objects only at the API layer.
- Treat `next_intervals` as required server output, not optional UI sugar.
- Do not leave legacy `last_reviewed_at` / `repetitions` heuristics active anywhere that now has queue-state semantics.
- Preserve cram mode unless a change is strictly required by shared hooks.
