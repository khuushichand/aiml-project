# Deep Research Run Controls And Progress Design

**Date:** 2026-03-07

## Goal

Add first-class pause, resume, cancel, and progress reporting to deep research runs so the backend matches the long-running, resumable Jobs-backed design already implemented for planning, collecting, synthesizing, and packaging.

## Motivation

The provider-backed deep research backend now executes real multi-phase runs, but its API surface still only supports creation, polling by session ID, artifact reads, bundle reads, and checkpoint approval. That leaves a gap between the domain model and the operational model: runs are durable and async, but users cannot pause, resume, or cancel them through the research API, and the polling endpoint does not yet expose progress fields from the active Jobs slice.

This slice closes that gap without introducing streaming transport or unsafe mid-phase interruption.

## Recommended Approach

Use session-local control state as the authoritative control plane for research runs.

Three alternatives were considered:

1. Session-local control state.
   This adds explicit research-session control state plus progress fields, and keeps the API domain-specific instead of leaking raw Jobs semantics.

2. Jobs-only control surface.
   This would infer everything from the active job row. It is weaker because a research session can outlive any one job slice and can also sit at human checkpoints with no active job.

3. Queue-level controls.
   This is useful for operators but wrong for user-facing run controls because it affects all research runs, not one session.

The recommended option is `1`.

## Scope

This design covers:

- `POST /api/v1/research/runs/{id}/pause`
- `POST /api/v1/research/runs/{id}/resume`
- `POST /api/v1/research/runs/{id}/cancel`
- polling progress fields on `GET /api/v1/research/runs/{id}`
- phase-boundary honoring of pause/cancel requests

This design does not cover:

- SSE or WebSocket progress streaming
- immediate mid-phase interruption
- global queue controls for research

## Domain Model

Extend the research session record with:

- `control_state`
  Values: `running`, `pause_requested`, `paused`, `cancel_requested`, `cancelled`
- `progress_percent`
  Nullable float representing coarse-grained progress
- `progress_message`
  Nullable string with user-facing progress text

The research session remains the canonical domain object. The active Job remains the executable slice, but no longer serves as the sole source of truth for run controls.

## State Model

Session status and phase continue to represent lifecycle progress. `control_state` represents operator intent and run-control outcome.

Rules:

- `pause`
  Allowed from `queued`, `processing`, and `waiting_human`
- `resume`
  Allowed only from `paused`
- `cancel`
  Allowed from any nonterminal session and is irreversible

Terminal states remain:

- `completed`
- `failed`
- `cancelled`

Checkpoint phases remain unchanged:

- `awaiting_plan_review`
- `awaiting_source_review`
- `awaiting_outline_review`

## API Design

### Existing Polling Endpoint

`GET /api/v1/research/runs/{id}` will expand to include:

- `control_state`
- `progress_percent`
- `progress_message`

This keeps polling clients on a single endpoint for run state, phase, control state, and progress.

### New Control Endpoints

Add:

- `POST /api/v1/research/runs/{id}/pause`
- `POST /api/v1/research/runs/{id}/resume`
- `POST /api/v1/research/runs/{id}/cancel`

Each endpoint returns the updated `ResearchRunResponse`.

### Endpoint Semantics

`pause`

- If the session is in an executable phase with active work, set `control_state = pause_requested`
- If the session is queued with no active work, or waiting at a checkpoint, move directly to `control_state = paused`
- If already paused, return the existing session state
- Reject terminal sessions

`resume`

- Allowed only from `control_state = paused`
- If the session phase is executable and no active job is attached, enqueue the current phase
- If the session phase is a human checkpoint, restore `status = waiting_human` without enqueueing a job
- Set `control_state = running`

`cancel`

- Allowed from any nonterminal session
- Set `status = cancelled`, `control_state = cancelled`, clear `active_job_id`
- Best-effort cancel the active job in Jobs if one exists
- Reject resume after cancellation

## Worker Behavior

The worker will remain phase-boundary safe.

It should not attempt to interrupt collection or synthesis in the middle of a phase. Instead, each phase handler will:

- set a coarse progress message at phase start
- update progress when the phase completes
- check `control_state` before doing work
- honor `pause_requested` after the current phase completes by transitioning to `paused` instead of advancing
- honor `cancel_requested` by finalizing the session as `cancelled` instead of advancing

Suggested progress values:

- planning: `10`
- collecting: `45`
- synthesizing: `75`
- packaging: `95`
- completed: `100`

Example progress messages:

- `planning research`
- `collecting sources`
- `synthesizing report`
- `packaging results`

The emphasis is consistency and visibility, not exact percent accuracy.

## Service Responsibilities

`ResearchService` will own:

- validation of control transitions
- enqueue-on-resume behavior
- best-effort active-job cancellation
- read-model composition for polling responses

`ResearchSessionsDB` will own persistence of control and progress fields.

`jobs.py` phase handlers will own:

- updating coarse progress fields
- reading control state at safe boundaries
- stopping advancement when pause/cancel intent is present

## Database Changes

Additive schema updates to `research_sessions`:

- `control_state TEXT NOT NULL DEFAULT 'running'`
- `progress_percent REAL`
- `progress_message TEXT`

As with previous research-session migrations, `_ensure_schema()` should use `PRAGMA table_info(...)` and `ALTER TABLE ... ADD COLUMN` so existing databases migrate in place.

## Error Handling

Reject invalid control transitions clearly:

- resume from non-paused session
- pause or cancel terminal session
- resume cancelled session

Domain state is authoritative even if Jobs cancellation is best-effort. That prevents races where Jobs and research-session rows temporarily disagree.

## Testing Strategy

Service tests:

- pause from `queued`, `processing`, `waiting_human`
- resume from `paused`
- cancel from nonterminal states
- invalid-transition rejection
- no double-enqueue on resume

Worker tests:

- phase completion honors `pause_requested`
- phase completion honors `cancel_requested`
- progress fields are updated through planning, collecting, synthesizing, and packaging

Endpoint and e2e tests:

- create run, pause, poll status
- resume a paused run and verify enqueue behavior
- cancel a run and verify resume is rejected
- paused checkpoint run resumes without creating a job

## Risks And Constraints

### Mid-Phase Interruption

Not included in v1. Current collection and synthesis work is not yet structured around cooperative cancellation checks at sub-phase granularity.

### Resume Safety

Resume must only enqueue when:

- the phase is executable
- `active_job_id` is empty
- the session is paused

This prevents duplicate jobs.

### Polling-Only Progress

This slice intentionally defers SSE or WebSocket progress transport. The Jobs layer already supports progress fields, so polling can provide useful visibility without adding a second transport contract now.

## Outcome

After this slice, deep research runs will support:

- explicit pause
- explicit resume
- explicit cancel
- polling-based progress visibility

That completes the minimum viable control plane for long-running, resumable async research runs.
