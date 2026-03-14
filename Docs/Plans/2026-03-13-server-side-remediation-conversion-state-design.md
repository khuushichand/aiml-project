# Server-Side Remediation Conversion State Design

Date: 2026-03-13  
Status: Approved

## Summary

This slice replaces browser-only remediation conversion tracking in quiz results with durable server-side state.

The goal is to make "already converted" and "study linked cards" reliable across reloads, browsers, and devices without coupling quiz state to incidental flashcard search or session storage.

The design keeps one active remediation conversion per missed question, preserves earlier conversions as `superseded`, and moves conversion ownership into a quiz endpoint that creates decks, creates flashcards, and records remediation state in one flow.

## Current Baseline

The existing remediation flow is split between UI state and flashcard creation:

- `ResultsTab.tsx` stores converted missed-question flags in session storage
- `ResultsTab.tsx` stores one deck per attempt in session storage for flashcard-study handoff
- `ResultsTab.tsx` creates a new deck in the client when needed
- `ResultsTab.tsx` bulk-creates flashcards directly through the flashcards API
- `QuizRemediationPanel.tsx` treats conversion state as a simple `alreadyConverted: boolean`

Relevant code anchors:

- `apps/packages/ui/src/components/Quiz/tabs/ResultsTab.tsx`
- `apps/packages/ui/src/components/Quiz/components/QuizRemediationPanel.tsx`
- `apps/packages/ui/src/components/Quiz/hooks/useQuizQueries.ts`
- `apps/packages/ui/src/services/quizzes.ts`
- `apps/packages/ui/src/services/tldw/quiz-flashcards-handoff.ts`
- `apps/packages/ui/src/components/Flashcards/FlashcardsManager.tsx`
- `apps/packages/ui/src/components/Flashcards/tabs/ReviewTab.tsx`
- `tldw_Server_API/app/api/v1/endpoints/quizzes.py`
- `tldw_Server_API/app/api/v1/schemas/quizzes.py`
- `tldw_Server_API/app/api/v1/endpoints/flashcards.py`
- `tldw_Server_API/app/api/v1/schemas/flashcards.py`
- `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`

## Product Decision

Use a dedicated remediation-conversion record owned by the quiz domain.

Do not derive conversion state from flashcards alone.

Do not store remediation conversion history as JSON inside quiz attempts.

This gives users the most reliable experience because:

- conversion state survives session loss
- conversion state is explicit and queryable
- active versus superseded history is first-class
- linked-deck and linked-card metadata can be shown without recomputing from flashcard search

## Recommended Approach

Add a new quiz-owned remediation conversion model and endpoint surface:

- `GET /api/v1/quizzes/attempts/{attempt_id}/remediation-conversions`
- `POST /api/v1/quizzes/attempts/{attempt_id}/remediation-conversions/convert`

`POST .../convert` owns the full conversion action:

- validate the attempt and selected question IDs
- validate that each question belongs to the attempt and was missed in a completed submission
- optionally create a new destination deck
- create the flashcards
- supersede previous active remediation rows when explicitly requested
- insert new active remediation records
- return per-question results and linked flashcard UUIDs

This removes the current "create flashcards first, then mark session state" split that can drift.

## Data Model

Add a new table:

- `quiz_remediation_conversions`

Suggested columns:

- `id`
- `attempt_id`
- `quiz_id`
- `question_id`
- `status` with `active | superseded`
- `superseded_by_id`
- `target_deck_id`
- `target_deck_name_snapshot`
- `flashcard_count`
- `flashcard_uuids_json`
- `source_ref_id`
- `created_at`
- `last_modified`
- `client_id`
- `version`

Rules:

- one `active` row per `attempt_id + question_id`
- `Convert again anyway` creates a new active row and marks the previous active row `superseded`
- superseded rows remain queryable for history and auditability
- linked flashcards are stored by UUID, not internal numeric ID

Indexing:

- `(attempt_id)`
- `(attempt_id, question_id)`
- partial unique index for one active row per `(attempt_id, question_id)`

The stored `source_ref_id` should remain aligned with flashcards:

- `quiz-attempt:{attempt_id}:question:{question_id}`

## API Surface

### Read

`GET /api/v1/quizzes/attempts/{attempt_id}/remediation-conversions`

Returns:

- `attempt_id`
- per-question active remediation summary
- optional `superseded_count`
- optional `orphaned` indicator when linked flashcards no longer exist

The read model should be question-centric because the results surface is already organized around missed questions.

### Convert

`POST /api/v1/quizzes/attempts/{attempt_id}/remediation-conversions/convert`

Request:

- `question_ids: number[]`
- exactly one of:
  - `target_deck_id`
  - `create_deck_name`
- `replace_active: boolean`

Response:

- per-question results with `created | already_exists | superseded_and_created | failed`
- active conversion summary when successful
- created flashcard UUIDs
- structured error details for mixed-result handling

If `replace_active=false` and an active conversion already exists, the endpoint should return an `already_exists` result for that question instead of silently overwriting it.

## Validation Rules

The server must enforce remediation eligibility instead of trusting the UI.

For each requested question:

- attempt exists
- attempt belongs to the current user
- attempt has been completed
- question ID exists in the attempt snapshot
- the question has a graded answer
- the graded answer was incorrect

This prevents direct API callers from creating remediation records for correct, missing, or unsubmitted questions.

## Deck Creation Ownership

The convert endpoint must support the current "create new deck" workflow directly.

Do not require the client to create the deck before calling conversion.

Reason:

- avoids empty orphan decks if conversion later fails
- keeps remediation conversion atomic from the user's perspective
- removes one more client-only side effect from `ResultsTab`

V1 request semantics:

- `target_deck_id` for existing deck conversion
- `create_deck_name` for new deck conversion

Reject requests that provide both or neither.

## Dedupe Policy

The current UI dedupes missed questions with identical prompt and correct answer before flashcard creation.

That behavior conflicts with a per-question conversion record unless it is made explicit.

V1 decision:

- preserve the current flashcard dedupe behavior
- allow multiple question-level remediation records to reference the same created flashcard UUID set

This keeps user-visible card creation behavior stable while still making remediation history question-specific.

Consequences:

- `flashcard_count` is the count of linked created cards for that question's active conversion
- two question records may point at the same UUID array
- the conversion response should make that explicit so the UI does not assume one new card per missed question

## Handoff To Flashcards Study

The current handoff assumes one deck per attempt. That is no longer always true.

V1 handoff rule:

- if all active remediation conversions for the attempt point to the same live deck, keep the existing deck-filtered `Study linked cards` behavior
- if active conversions span multiple decks, hand off using `quiz_id` and `attempt_id` only, without a deck filter

This avoids picking an arbitrary deck and keeps the CTA usable without changing flashcards routing in this slice.

The deck-specific chip shown beside each missed question should come from the active remediation conversion summary.

## Orphaned And Stale Conversion State

A dedicated remediation record can outlive its linked flashcards.

V1 behavior:

- on read, if every linked flashcard UUID is missing or deleted, mark the active remediation conversion summary as `orphaned`
- orphaned conversions remain in history but should not block a fresh conversion
- the UI should surface orphaned conversions as stale and allow a normal reconvert without forcing `replace_active=true`

This keeps the remediation state honest after later flashcard deletion.

## UI Behavior

`ResultsTab` should stop using session storage for remediation conversion state.

Instead it should:

- fetch remediation state for the selected attempt
- derive `alreadyConverted`, deck labels, and stale/orphaned state from the server response
- default "Create remediation flashcards" to only not-yet-active or orphaned missed questions
- show explicit `Convert again anyway` when active conversions already exist

`QuizRemediationPanel` should remain question-centric but gain richer status text:

- `Not converted`
- `Converted`
- `Converted in deck X`
- `Superseded history exists`
- `Linked cards were deleted`

The global "Study linked cards" CTA should follow the multi-deck handoff rule above.

## Backend Implementation Notes

Prefer one DB helper that performs the conversion flow inside a single transaction:

- load and validate attempt/question eligibility
- create a deck when needed
- create flashcards
- supersede old active records when requested
- insert new active remediation rows
- return per-question results

If the flashcard creation helper cannot be reused transactionally without unsafe duplication, the acceptable fallback is:

- keep the convert endpoint orchestration in one request
- use compensating deletion if remediation-row persistence fails after card creation

The transactional path is preferred.

## Testing

Backend tests should cover:

- reading remediation state for one attempt
- converting fresh missed questions
- rejecting correct or ungraded questions
- rejecting conversion on incomplete attempts
- creating a new deck inside conversion
- mixed-result bulk convert with fresh and already-converted questions
- `replace_active=true` superseding the old active row
- deduped card creation while preserving per-question remediation rows
- orphaned conversion read behavior after linked-card deletion
- user isolation

Frontend tests should cover:

- no more session-storage remediation state reads or writes
- results tab loading server-backed remediation state
- already-converted questions excluded by default
- `Convert again anyway` sending `replace_active=true`
- active deck label rendering
- multi-deck handoff dropping the deck filter
- single-deck handoff keeping the deck filter
- orphaned conversion rows showing stale state and allowing reconvert

## Non-Scope

This slice does not add:

- full remediation conversion history browsing UI
- server-driven dedupe explanation UI
- automatic sync from flashcard edits back into remediation records
- migration of old session-storage conversion data

The goal is durable server truth for future attempts, not historical recovery from browser-local state.
