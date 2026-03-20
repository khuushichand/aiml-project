# Deep Research Replayable Events Design

**Date:** 2026-03-07

## Goal

Add persistent, replayable event history for a single deep research run so clients can reconnect to the SSE stream with an `after_id` cursor and receive missed research events in order before resuming the live tail.

## Motivation

The current deep research SSE endpoint provides:

- a fresh reconnect-safe `snapshot`
- live `status`, `progress`, `checkpoint`, `artifact`, and `terminal` events
- no replay support

That is enough for first-use monitoring, but it is not enough for durable reconnects because short-lived events are lost if the client disconnects between polls. The next step is to make the SSE stream durable without widening scope into multi-run feeds or UI work.

## Recommended Approach

Persist research-native events at the real state transition points and replay them from a dedicated per-run event log.

Three alternatives were considered:

1. Poll-and-persist wrapper.
   This would append events when the stream observer notices them. It is cheaper initially, but incorrect because history would depend on whether a client happened to be connected.

2. Source-of-truth event log.
   This appends events where the state actually changes, then makes SSE replay and live tail consume the same persisted event source.

3. Snapshot-only reconnect.
   This would continue using `snapshot` plus live polling and would not actually solve the missed-event problem.

The recommended option is `2`.

## Scope

This design covers:

- a dedicated `research_run_events` table
- append-only research-native event persistence for a single run
- `after_id` replay on the existing SSE endpoint
- ordered replay followed by live tailing from persisted events

This design does not cover:

- multi-run or user-wide event feeds
- `Last-Event-ID` support
- arbitrary event filtering
- WebSocket transport

## Public API Contract

Extend the existing endpoint to:

- `GET /api/v1/research/runs/{session_id}/events/stream?after_id=<int>`

Behavior:

- always emit a fresh `snapshot` first from current run state
- include `latest_event_id` in that snapshot so reconnecting clients know the current persisted watermark
- if `after_id > 0`, replay persisted research events with `id > after_id`
- emit replayed rows in ascending `id` order
- emit each replayed or live persisted event with SSE `id: <row_id>`
- include `event_id` in the JSON payload for every replayable event
- mark replayed rows with `replayed: true` and live-tail rows with `replayed: false`
- remember the highest emitted event ID
- continue tailing new persisted rows after that cursor
- close after emitting a terminal event once the run is terminal and no newer events remain

If `after_id` is ahead of the current event log, the endpoint should not fail. It should emit `snapshot` and then wait for future rows after that cursor.

The `snapshot` is the authoritative current-state baseline. Replayed rows after `snapshot` are historical catch-up events and should not be treated as newer than the opening snapshot unless their `event_id` exceeds the snapshot's `latest_event_id`.

## Event Log Model

Add an append-only `research_run_events` table to the research DB.

Suggested columns:

- `id INTEGER PRIMARY KEY`
- `session_id TEXT NOT NULL`
- `owner_user_id TEXT NOT NULL`
- `event_type TEXT NOT NULL`
- `event_payload_json TEXT NOT NULL`
- `phase TEXT`
- `job_id TEXT`
- `created_at TEXT NOT NULL`

Indexes:

- `(owner_user_id, session_id, id ASC)` for replay and ownership enforcement
- `(session_id, id ASC)` only if a narrower session-local lookup is still useful internally

The event vocabulary should match the existing SSE contract:

- `status`
- `progress`
- `checkpoint`
- `artifact`
- `terminal`

`snapshot` should remain a live computed event only. It should not be stored for every transition because:

- it would duplicate large current-state payloads
- it would blur “current state” vs “historical event”
- replay only needs the current live snapshot once per connection

Replay reads should always be scoped by both `owner_user_id` and `session_id`, even though many deployments use per-user DB files. The service already supports injected shared DB paths, so ownership filtering must be part of the event-read contract rather than an optional optimization.

## Event Payload Rules

Persist compact payloads only.

Every replayable event emitted over SSE should carry:

- SSE `id:` equal to the persisted event row ID
- `event_id` in the JSON payload with the same numeric value
- `replayed` in the JSON payload to distinguish catch-up rows from live tail rows

The stored `event_payload_json` remains compact metadata and does not need to redundantly store `replayed`.

### `status`

Payload:

- `status`
- `phase`
- `control_state`
- `active_job_id`
- `latest_checkpoint_id`
- `completed_at`

### `progress`

Payload:

- `progress_percent`
- `progress_message`

### `checkpoint`

Payload:

- `checkpoint_id`
- `checkpoint_type`
- `status`
- `resolution`
- `phase`
- `has_proposed_payload`

### `artifact`

Payload:

- `artifact_name`
- `artifact_version`
- `content_type`
- `phase`
- `job_id`

### `terminal`

Payload:

- the same compact lifecycle payload used for `status`

Artifact contents, full report text, and other large objects should never be embedded in event rows.

## Write Points

Persist events at the actual state transition points, not inside the transport.

### Jobs Phase Execution

In `tldw_Server_API/app/core/Research/jobs.py`, append:

- `status` when phase/status/control-state transitions occur
- `progress` when coarse phase progress updates are written
- `checkpoint` when a run enters `awaiting_*_review`
- `terminal` when a run reaches `completed`, `failed`, or `cancelled`

### Service-Level Control Flow

In `tldw_Server_API/app/core/Research/service.py`, append:

- `status` for pause/resume/cancel transitions
- `checkpoint` or `status` when checkpoint approval moves the run forward

### Artifact Registration

In `tldw_Server_API/app/core/Research/artifact_store.py`, append:

- `artifact` whenever a new artifact version is recorded

### Checkpoint Creation / Resolution

When checkpoint rows are created or resolved, persist `checkpoint` events using compact metadata only. The full checkpoint payload remains available through the snapshot/read APIs and checkpoint rows themselves.

## Atomicity And Consistency

State mutation and event persistence must be transactionally consistent.

For session and checkpoint transitions:

- the state update and the event insert should happen in the same SQLite transaction
- the stream should never observe an event row describing a transition that the current session/checkpoint rows do not yet reflect
- the system should never commit a session/checkpoint transition without the corresponding event row

For artifact writes:

- write the file payload to disk first
- then, in a single DB transaction, record the artifact manifest row and append the `artifact` event row
- if the DB transaction fails after the file write, the orphaned file is acceptable and a retry may overwrite the same path safely, but the manifest and event rows must remain consistent with each other

## Dedupe And Retry Safety

Workers and service methods can retry. The event writer therefore needs lightweight dedupe.

Recommended rule:

- before appending, compare against the latest stored row for the same `(session_id, event_type)`
- if `phase`, `job_id`, and a stable hash of `event_payload_json` are unchanged, suppress the duplicate write

This keeps the design simple while still preventing the most common retry duplicates.

The event log remains append-only; dedupe happens before insert, not by mutating history.

## Streaming Behavior

Once write points are in place, the SSE endpoint should tail persisted event rows instead of deriving live events from direct session polling.

Recommended flow:

1. Load and emit the live `snapshot`
2. Replay persisted rows where `id > after_id`
3. Record the highest emitted event ID
4. Poll `research_run_events` for newer rows for that session
5. Emit them in order
6. When a `terminal` event is emitted and the run is terminal, close

If a client connects to an already-terminal run and `after_id` is already at or beyond the stored terminal row, the stream should still emit:

1. `snapshot`
2. one synthetic `terminal` event derived from current state
3. close

The stream may still consult current session state for:

- the opening `snapshot`
- safety checks around terminal closure

But replay and live tail should come from the same persisted event source.

## Database Migration

Extend `ResearchSessionsDB._ensure_schema()` with additive migration for the new table and indexes.

The migration should:

- create `research_run_events` if it does not exist
- create the replay index on `(owner_user_id, session_id, id)`
- avoid destructive changes

This should follow the same in-place SQLite migration style already used for research sessions.

## Testing Strategy

Add three layers of coverage.

### DB / Service Tests

For the research DB and service layer:

- event rows append successfully
- `list_research_run_events_after(owner_user_id, session_id, after_id)` returns ordered rows
- ownership-scoped reads do not leak rows across users
- latest-event dedupe suppresses identical retries
- transaction-bound writes do not persist state without the matching event row

### Endpoint Tests

For the SSE endpoint:

- `after_id=0` emits `snapshot` then current/future rows
- `after_id=N` replays only newer rows
- replayed rows expose both SSE `id:` and JSON `event_id`
- `snapshot` includes `latest_event_id`
- missing session maps to `404`
- terminal run with replay emits `snapshot`, remaining replay rows, `terminal`, and closes

### End-To-End Test

For deep research reconnect:

- connect once
- consume a few events and remember the highest persisted event ID
- disconnect
- advance the run through more transitions
- reconnect with `after_id=<last_seen>`
- verify only missed events are replayed before the live tail continues

## Error Handling

The endpoint should:

- validate `after_id >= 0`
- return `404` for missing sessions
- return `403` through the existing ownership path if access is not allowed
- tolerate an empty event log by emitting `snapshot` and tailing from the requested cursor

Event writes should fail loudly inside tests, but in production a single event-write failure should be treated as a research-domain failure for that transition point rather than silently dropped. Replay without trustworthy persistence is not acceptable.

## Tradeoffs And Deferred Work

Accepted tradeoffs for v1:

- replay is scoped to one research run only
- `after_id` query param only, no `Last-Event-ID`
- `snapshot` is live and computed, not persisted
- payloads remain compact and metadata-only

Deferred:

- multi-run event feeds
- cursor pagination REST endpoint
- event retention policies
- UI work on top of replay
