# Optional Per-Deck FSRS Design

Date: 2026-03-13
Status: Approved

## Summary

This slice adds FSRS as an optional per-deck scheduler alongside the existing `sm2_plus` path.

The goal is to let new decks and manually switched decks use FSRS without breaking the current shared study loop, queue model, or deck-management flows.

V1 keeps:

- the current four review ratings
- the current `review/next` contract
- the current shared queue states
- the dedicated `Scheduler` tab as the main scheduler control surface

V1 does not:

- replace `sm2_plus`
- auto-migrate existing decks
- reconstruct exact FSRS state from historic SM-2 review logs
- mix scheduler types inside a single deck

## Current Baseline

The repo already has a substantial scheduler foundation:

- deck-scoped scheduler settings
- shared queue states for `new`, `learning`, `review`, `relearning`, and `suspended`
- backend-selected `GET /api/v1/flashcards/review/next`
- backend-computed `next_intervals`
- a dedicated `Scheduler` tab plus creation-flow scheduler controls

Relevant code anchors:

- `tldw_Server_API/app/core/Flashcards/scheduler_sm2.py`
- `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- `tldw_Server_API/app/api/v1/endpoints/flashcards.py`
- `tldw_Server_API/app/api/v1/schemas/flashcards.py`
- `apps/packages/ui/src/services/flashcards.ts`
- `apps/packages/ui/src/components/Flashcards/tabs/SchedulerTab.tsx`
- `apps/packages/ui/src/components/Flashcards/utils/scheduler-settings.ts`
- `apps/packages/ui/src/components/Flashcards/components/DeckSchedulerSettingsEditor.tsx`

## Product Decision

Use FSRS as an optional per-deck scheduler beside the current `sm2_plus` scheduler.

The active scheduler is chosen at the deck level through:

- deck creation flows
- the dedicated `Scheduler` tab

Existing decks remain on `sm2_plus` unless the user manually switches them.

This is the most pragmatic path because:

- it preserves current behavior for existing users
- it avoids a risky global scheduler migration
- it reuses the already-shipped queue model and review endpoints
- it makes stronger Anki-style scheduling available without forcing a rewrite of the broader flashcards module

## Explicit Decisions

- Add `scheduler_type` per deck with values `sm2_plus | fsrs`.
- Keep one `scheduler_settings_json` field on the deck row, but store a typed envelope:
  - `sm2_plus`
  - `fsrs`
- Add `scheduler_state_json` on flashcards for scheduler-specific per-card state.
- Add `scheduler_type` to `flashcard_reviews`.
- Keep learning and relearning queue behavior shared across both schedulers in v1.
- Keep `interval_days` as the canonical compatibility interval used by analytics and maturity counts, even when FSRS is active.
- Bootstrap switched cards into FSRS from the current card snapshot, not by reconstructing historic FSRS memory from old review logs.
- Keep both scheduler configs stored in the deck settings envelope so switching is reversible.

## Deck Data Model

### Storage

Add:

- `scheduler_type TEXT NOT NULL DEFAULT 'sm2_plus'`

Keep:

- `scheduler_settings_json TEXT NOT NULL`

New JSON envelope shape:

```json
{
  "sm2_plus": {
    "new_steps_minutes": [1, 10],
    "relearn_steps_minutes": [10],
    "graduating_interval_days": 1,
    "easy_interval_days": 4,
    "easy_bonus": 1.3,
    "interval_modifier": 1.0,
    "max_interval_days": 36500,
    "leech_threshold": 8,
    "enable_fuzz": false
  },
  "fsrs": {
    "target_retention": 0.9,
    "maximum_interval_days": 36500,
    "enable_fuzz": false
  }
}
```

Why keep one settings blob:

- lower schema churn than splitting into multiple deck JSON columns
- smaller sync-log and API migration surface
- easier compatibility with the existing deck schema/tests

### API Shape

Expose:

- `scheduler_type`
- `scheduler_settings`

`scheduler_settings` is the envelope object, not just the active scheduler config.

This lets the UI:

- edit the active scheduler cleanly
- preserve inactive settings for future switching
- avoid losing per-scheduler edits

## Flashcard Data Model

Add:

- `scheduler_state_json TEXT NOT NULL DEFAULT '{}'`

This stores scheduler-specific state per card.

V1 behavior:

- `sm2_plus` cards may keep `{}` in this field
- `fsrs` cards store derived FSRS memory state here

Keep the shared top-level scheduling fields:

- `queue_state`
- `step_index`
- `suspended_reason`
- `due_at`
- `interval_days`
- `repetitions`
- `lapses`
- `last_reviewed_at`

Those remain the stable compatibility layer for:

- filters
- analytics
- review ordering
- document/manage views

## Review History Model

Add `scheduler_type` to `flashcard_reviews`.

Keep:

- `rating`
- `answer_time_ms`
- `scheduled_interval_days`
- queue transitions
- due timestamp transitions

This gives the repo enough data to explain:

- which scheduler was active for a given review
- what interval the scheduler chose
- how queue state changed

V1 does not need to persist full FSRS state snapshots in review history. The per-card `scheduler_state_json` is sufficient for active scheduling, while review history remains useful for analytics/debugging.

## Shared Queue Semantics

Queue behavior remains shared between `sm2_plus` and FSRS:

- `new`
- `learning`
- `review`
- `relearning`
- `suspended`

The backend-selected `review/next` ordering remains:

1. due learning/relearning
2. due review
3. new

Minute-based learning and relearning steps also remain shared.

In v1, FSRS applies to the review-stage scheduling logic for review cards, not to a separate learning model.

## FSRS Bootstrap For Manually Switched Decks

The biggest risk in this slice is deck switching.

V1 bootstrap rule:

- switching an existing deck from `sm2_plus` to `fsrs` does not trigger a bulk migration
- when a card in that deck is reviewed under FSRS for the first time and has empty `scheduler_state_json`, derive a conservative FSRS state from the current card snapshot:
  - `interval_days`
  - `repetitions`
  - `lapses`
  - `last_reviewed_at`
  - `due_at`
- persist the derived state immediately after the first FSRS review calculation

Why conservative bootstrap:

- it is deterministic
- it avoids rewriting all cards up front
- it acknowledges that historic logs were not collected as FSRS state
- it allows the deck to stabilize naturally as cards continue to be reviewed

Switching back to `sm2_plus`:

- retain `scheduler_state_json`
- stop using it while `sm2_plus` is active
- keep the stored FSRS config for later switching

## Review API Contract

Keep:

- `GET /api/v1/flashcards/review/next`
- `POST /api/v1/flashcards/review`

Extend review responses with:

- `scheduler_type`
- server-computed `next_intervals`

The client does not compute FSRS math.

The backend chooses the active scheduler from the deck, dispatches to the correct scheduler implementation, and returns the shared response shape.

## Scheduler Engine Structure

Add a new pure scheduler module:

- `tldw_Server_API/app/core/Flashcards/scheduler_fsrs.py`

Keep `scheduler_sm2.py`.

Add a small dispatcher layer that:

- reads deck `scheduler_type`
- normalizes the active scheduler config from the envelope
- calls either the SM-2+ or FSRS transition function

This avoids burying a second scheduler inside `ChaChaNotes_DB.py`.

## Analytics And Compatibility Rules

Analytics currently depend on `interval_days` for maturity counts.

V1 decision:

- `interval_days` remains the derived compatibility interval written after every review, regardless of scheduler
- deck progress and `mature_count` continue using `interval_days`

This keeps analytics stable while FSRS is introduced.

It also avoids creating scheduler-specific analytics semantics before the review-history UI slice exists.

## Sync Log Requirements

The current sync payloads only cover the single-scheduler model.

This slice must update sync triggers/payloads so they include:

Deck payloads:

- `scheduler_type`
- envelope `scheduler_settings_json`

Flashcard payloads:

- `scheduler_state_json`
- shared compatibility fields already used by the scheduler UI and review flows

Without this, FSRS state can silently disappear for sync consumers.

## UI Surface

### Scheduler Tab

The `Scheduler` tab remains the main edit surface for existing decks.

Add:

- scheduler-type selector
- type-specific settings panel
- switching warning for existing decks

The warning should state:

- switched decks do not receive a bulk FSRS migration
- cards initialize conservative FSRS state when first reviewed under FSRS
- switching back to `sm2_plus` is allowed

### Deck Creation Flows

The shared deck-creation scheduler editor should be extended to support:

- `sm2_plus` mode
- `fsrs` mode

New decks still default to `sm2_plus`, but users can choose FSRS before creation.

### Review UI

The review screen should remain stable.

V1 additions:

- optional scheduler badge such as `SM-2+` or `FSRS`
- continue using server `next_intervals`

Do not add separate rating buttons or scheduler-specific study flows.

## Validation

Validation must be both local and server-side.

SM-2+ validation remains as-is.

FSRS v1 should keep a small settings surface:

- `target_retention`
- `maximum_interval_days`
- `enable_fuzz`

This avoids exposing a giant tuning surface before there is evidence the product needs it.

## Testing

Backend:

- deck create/update with `scheduler_type=fsrs`
- default deck still uses `sm2_plus`
- lazy FSRS bootstrap on first review after manual switch
- review responses include `scheduler_type`
- `scheduler_state_json` persists and updates
- sync-log payloads include new scheduler fields
- analytics remain stable through derived `interval_days`
- mixed deck scheduler types do not break `review/next`

Frontend:

- scheduler tab switches between SM-2+ and FSRS panels
- deck creation flows can create FSRS decks
- existing deck summaries show scheduler type cleanly
- review UI continues to render server `next_intervals`
- switching existing decks shows the bootstrap warning

## Non-Scope

This slice does not include:

- forced migration of existing decks
- per-card review history UI
- stronger Anki APKG fidelity work
- separate FSRS learning-step behavior
- scheduler-type mixing within a single deck
- importing/exporting scheduler choice to APKG metadata

## Next Planning Target

`Optional per-deck FSRS implementation`
