# SM-2+ Scheduler Upgrade Design

Date: 2026-03-13
Status: Approved

## Summary

This design upgrades the existing flashcard scheduler without introducing FSRS or a second review model.

V1 keeps the current four review buttons and ratings, but replaces the thin day-only SM-2 path with:

- explicit queue states for `new`, `learning`, `review`, `relearning`, and `suspended`
- deck-scoped scheduler settings
- backend-selected next-card ordering
- minute-based learning and relearning steps
- improved review interval math for overdue cards, easy bonus, interval modifiers, max interval, leeches, and bounded fuzz
- richer review history for analytics and debugging

The goal is pragmatic scheduler parity: preserve the current user-facing study loop while fixing the weakest parts of the current implementation.

## Current Constraints

The current repo shape matters:

- review math is embedded in `CharactersRAGDB._srs_sm2_update()`
- review selection is client-driven through three list queries
- `due/new/learning` filters are overlapping heuristics, not explicit queue states
- review interval previews are computed in the browser from old SM-2 assumptions
- deck APIs do not currently support updates
- sync-log payloads only include the current deck/flashcard fields

The design must correct those constraints, not build around them.

## Explicit Decisions

- Improve the existing SM-2 path only.
- Do not add FSRS in this slice.
- Keep the current review endpoint and four ratings: `0`, `2`, `3`, `5`.
- Add a backend-selected `next-card` path so queue ordering is unambiguous.
- Make backend interval previews required for the review UI.
- Store deck scheduler settings as JSON text in the DB layer, not as a backend-native JSON type.
- Extend review history to store queue-state transitions explicitly.
- Update sync-log payloads for new deck and flashcard scheduler fields.

## Queue Model

### Flashcard Queue State

Each card gets a persistent `queue_state`:

- `new`
- `learning`
- `review`
- `relearning`
- `suspended`

Additional scheduler state:

- `step_index: integer | null`
- `suspended_reason: "manual" | "leech" | null`

Existing long-term review fields remain:

- `ef`
- `interval_days`
- `repetitions`
- `lapses`
- `due_at`
- `last_reviewed_at`

`due_at` remains the single authoritative next-review timestamp for all active queues.

## Deck Scheduler Settings

### Storage

Add `scheduler_settings_json TEXT NOT NULL DEFAULT '{}'` to `decks`.

This matches current project conventions such as `tags_json` and `settings_json`, keeps SQLite/Postgres behavior aligned, and avoids special-case JSON typing in the DB layer.

### API Shape

Expose a typed `scheduler_settings` object in deck read/write schemas:

- `new_steps_minutes: number[]`
- `relearn_steps_minutes: number[]`
- `graduating_interval_days: number`
- `easy_interval_days: number`
- `easy_bonus: number`
- `interval_modifier: number`
- `max_interval_days: number`
- `leech_threshold: number`
- `enable_fuzz: boolean`

Missing values are defaulted server-side.

### Deck Endpoint

Add:

- `PATCH /api/v1/flashcards/decks/{id}`

The request uses optimistic locking via `expected_version`.

There is no existing deck update path, so this endpoint is part of the design, not a follow-up.

## Review Selection Contract

### New Endpoint

Add:

- `GET /api/v1/flashcards/review/next`

Supported filters:

- `deck_id`

The response should include:

- `card: Flashcard | null`
- `queue_state`
- `next_intervals`
- `selection_reason`

### Queue Ordering

Backend selection order for due-mode study:

1. due `learning` or `relearning` cards
2. due `review` cards
3. `new` cards

This is intentional. Learning and relearning steps are time-sensitive and should not be starved behind untouched cards.

The client should stop reconstructing queue order by calling `listFlashcards()` three times.

## Review Semantics

### New Cards

First review moves `new` cards into `learning`.

Ratings:

- `Again`: reset to learning step `0`
- `Hard`: repeat current step with a modest bump
- `Good`: advance to next step
- `Easy`: graduate immediately to `review` using `easy_interval_days`

If `Good` passes the final learning step:

- move to `review`
- set interval to `graduating_interval_days`
- set `repetitions = 1`

### Learning And Relearning

Learning and relearning steps are minute-based and do not use `ef` for scheduling.

`ef` is not updated during pure learning steps.

Relearning is triggered by `Again` on a review card and uses `relearn_steps_minutes`.

When relearning completes:

- return to `review`
- restore a reduced review interval derived from the pre-lapse interval

### Review Queue

Review cards use improved SM-2 math:

- overdue bonus, capped
- rating-aware interval growth
- `easy_bonus`
- `interval_modifier`
- `max_interval_days`
- optional bounded fuzz

`Again` on a review card:

- increments `lapses`
- reduces `ef`
- enters `relearning` if relearn steps exist
- otherwise falls back to a short review interval

### Leeches

When `lapses >= leech_threshold`:

- set `queue_state = "suspended"`
- set `suspended_reason = "leech"`

V1 does not auto-tag or auto-bury leeches.

## Filter And Analytics Semantics

Current `due/new/learning` semantics are overlapping heuristics and must be replaced.

### List / Count Filters

Retain the existing `due_status` parameter for compatibility, but redefine it as disjoint queue semantics:

- `new`: `queue_state = "new"`
- `learning`: `queue_state IN ("learning", "relearning")`
- `due`: `queue_state = "review"` and `due_at <= now`
- `all`: all active non-deleted cards

The review-next endpoint is the only source of queue ordering.

### Analytics

Deck progress counters should use queue state, not `last_reviewed_at` and `repetitions` heuristics.

Recommended meanings:

- `new`: queue state `new`
- `learning`: queue state `learning` or `relearning`
- `due`: queue state `review` with `due_at <= now`
- `mature`: queue state `review` with a mature interval threshold

V1 can keep the existing `mature` field name, but the calculation must be rewritten.

## Review API Contract

Keep:

- `POST /api/v1/flashcards/review`

Keep request:

- `card_uuid`
- `rating`
- `answer_time_ms`

Extend the response. The response must include:

- existing review fields
- `queue_state`
- `step_index`
- `suspended_reason`
- required `next_intervals` for `again`, `hard`, `good`, `easy`

`next_intervals` is required because the current client preview logic cannot correctly model learning steps, relearning, overdue handling, or deck overrides.

## Scheduler Module Split

Move scheduling logic into a dedicated pure module, for example:

- `tldw_Server_API/app/core/Flashcards/scheduler_sm2.py`

Input:

- current card scheduler state
- normalized deck scheduler settings
- rating
- current timestamp

Output:

- updated card scheduler state
- next interval preview payload
- review-log transition payload

The DB layer should only:

- load card + deck settings
- call the scheduler
- persist updates
- append the review log

## Review History

Extend `flashcard_reviews` so queue-state transitions are explicit.

Keep current fields and add:

- `previous_queue_state TEXT`
- `next_queue_state TEXT`
- `previous_due_at DATETIME`
- `next_due_at DATETIME`

This is the minimum needed for future analytics and debugging once minute-based queues exist.

## Reset Behavior

Reset scheduling must clear the new scheduler state as well as the old review fields:

- `queue_state = "new"`
- `step_index = NULL`
- `suspended_reason = NULL`
- `ef = 2.5`
- `interval_days = 0`
- `repetitions = 0`
- `lapses = 0`

`due_at` should be reset to an immediately reviewable timestamp so reset cards re-enter the queue cleanly.

## Migration And Sync

### Backfill

Backfill existing cards as:

- `review` if they have review history or review progression
- `new` otherwise

Set:

- `step_index = NULL`
- `suspended_reason = NULL`

Set all existing decks to default `scheduler_settings_json`.

### Sync Logging

Update deck and flashcard sync triggers/payloads so scheduler state changes are not dropped from sync logs.

Specifically:

- deck sync payloads must include `scheduler_settings_json`
- flashcard sync payloads must include `queue_state`, `step_index`, and `suspended_reason`

## Testing

### Pure Scheduler Tests

- new to learning transitions
- learning step progression
- graduation to review
- review overdue handling
- lapse to relearning
- relearning exit
- leech suspension
- fuzz bounds and determinism
- deck-setting overrides
- next interval preview generation

### Integration Tests

- `PATCH /decks/{id}` validation and optimistic locking
- `GET /review/next` ordering
- `POST /review` response shape and persistence
- list/count/analytics semantics by queue state
- reset scheduling clears new fields

### Frontend Tests

- review screen consumes backend `next_intervals`
- review query switches to backend-selected next card
- keyboard shortcuts and button values remain unchanged
- due counts and analytics continue to render with new semantics

## Non-Scope

- FSRS
- sibling burying
- fifth review button
- per-user deck scheduler overrides
- exact Anki parity
- cram-mode scheduler changes

## Success Criteria

This design succeeds if:

- scheduler behavior is driven by an isolated pure module
- the backend owns next-card selection
- learning and relearning use real minute-based steps
- deck settings can be updated safely
- review history captures queue transitions explicitly
- the current review UI keeps its four-button interaction model while showing correct interval previews
