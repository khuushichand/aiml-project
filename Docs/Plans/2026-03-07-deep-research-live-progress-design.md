# Deep Research Live Progress SSE Design

**Date:** 2026-03-07

## Goal

Add a research-native SSE endpoint for deep research runs so clients can watch long-running sessions progress live without polling every state transition manually.

## Motivation

The deep research backend now supports Jobs-backed planning, collecting, synthesizing, packaging, provider-backed execution, read APIs, and run controls. Polling on `GET /api/v1/research/runs/{id}` is sufficient for correctness, but it is not a good UX for live run monitoring, checkpoint handling, or terminal-state detection.

The backend already has proven SSE patterns for media and audio jobs. This slice should reuse that transport style while keeping the event contract research-native instead of leaking raw Jobs internals.

## Recommended Approach

Expose a research-specific SSE endpoint at:

- `GET /api/v1/research/runs/{session_id}/events/stream`

The stream should use:

- fresh snapshot on connect
- live updates from polling-based change detection
- no replay guarantee in v1
- research-native events instead of raw Jobs events

Three alternatives were considered:

1. Research-native SSE wrapper.
   This combines session state, active-job progress, checkpoint state, and artifact manifest changes into one stable contract.

2. Raw Jobs event proxy.
   This is simpler initially, but it is the wrong abstraction because research runs are session-oriented and may span multiple jobs or sit at checkpoints without any active job.

3. Dedicated research event log with replay.
   This is the strongest long-term model, but it is unnecessary for v1 because reconnecting clients can recover from a fresh snapshot and then follow live updates.

The recommended option is `1`.

## Scope

This design covers:

- a research-native SSE endpoint
- initial snapshot payload design
- status, progress, checkpoint, artifact, and terminal events
- polling-based change detection
- stream closure on terminal state

This design does not cover:

- replay via `Last-Event-ID`
- persisted research event logs
- WebSocket transport
- streaming artifact contents

## Endpoint Design

Add:

- `GET /api/v1/research/runs/{session_id}/events/stream`

This endpoint should:

- authenticate exactly like the existing research run read APIs
- authorize only the requested session owner in v1
- emit `text/event-stream`
- send a `snapshot` event first
- continue polling for state changes until the session reaches a terminal state
- emit one `terminal` event and then close

The endpoint should stay thin and delegate polling, normalization, and change detection to a new helper module under:

- `tldw_Server_API/app/core/Research/streaming.py`

## Event Contract

Use a small, fixed event vocabulary:

- `snapshot`
- `status`
- `progress`
- `checkpoint`
- `artifact`
- `terminal`

### Snapshot

The first event on every connection must be `snapshot`.

Because v1 does not support replay, the snapshot must be rich enough for reconnecting clients to recover current state immediately. It should include:

- run state:
  - `id`
  - `status`
  - `phase`
  - `control_state`
  - `progress_percent`
  - `progress_message`
  - `active_job_id`
  - `latest_checkpoint_id`
  - `completed_at`
- current checkpoint metadata when present:
  - `checkpoint_id`
  - `checkpoint_type`
  - `status`
  - `proposed_payload`
  - `resolution`
- current artifact manifest summary:
  - `artifact_name`
  - `artifact_version`
  - `content_type`
  - `phase`
  - `job_id`

The snapshot should not include full artifact contents.

### Status

`status` is the guaranteed event class. It must fire whenever any of these values changes:

- `status`
- `phase`
- `control_state`
- `active_job_id`

This is the primary signal for clients to understand where the run is in its lifecycle.

### Progress

`progress` is best-effort, not guaranteed for every transient value. It should fire when:

- `progress_percent` changes
- `progress_message` changes
- a new observed state implies a new effective progress view

Short-lived phases like planning or packaging may transition faster than the poll interval. That is acceptable as long as `status` still captures the lifecycle transition and the current progress view is emitted when observed.

### Checkpoint

`checkpoint` should fire when:

- `latest_checkpoint_id` changes
- the active checkpoint metadata changes
- the session enters an `awaiting_*_review` phase

Payload should include the current checkpoint summary only, not full historical checkpoint lists.

### Artifact

`artifact` should fire only for newly observed artifact versions after connection setup. Payload should include:

- `artifact_name`
- `artifact_version`
- `content_type`
- `phase`
- `job_id`

Historical artifacts must not be re-emitted as live events on reconnect.

### Terminal

`terminal` should fire once when the session reaches:

- `completed`
- `failed`
- `cancelled`

For already-terminal runs, the stream should emit:

1. `snapshot`
2. `terminal`
3. close

## Polling And Source Of Truth

The stream helper should poll both:

- the research session row
- the active Jobs row when an active numeric job ID exists

The research session remains authoritative for:

- lifecycle state
- checkpoint position
- pause/resume/cancel state

The active job row may provide fresher progress data. The stream helper should therefore:

- use session state as the base snapshot
- optionally overlay active-job progress when it is newer or more specific
- never let raw Jobs state override research lifecycle state

This is intentionally different from the existing polling read path in `ResearchService.get_session(...)`, which currently only consults the job row when session progress fields are `None`.

## Artifact Baseline And Dedupe

Artifact events need explicit baseline semantics.

On connect, the stream should baseline the latest seen `(artifact_name, artifact_version)` pairs from the current artifact manifest. Those artifacts belong in the `snapshot`, not as immediate live `artifact` events.

After that baseline is established:

- emit `artifact` only when a higher version of an existing artifact appears
- emit `artifact` when a brand-new artifact name appears
- ignore older or duplicate manifest entries

This keeps reconnect behavior stable and prevents historical artifact spam.

## Operational Limits

Follow the repo’s existing SSE pattern:

- poll every `0.5s` to `1.0s`
- use `SSEStream`
- support a bounded test-mode max duration to prevent hanging tests
- keep the stream open while a run is paused or waiting for human review
- close after a final `terminal` event

The stream should send compact JSON payloads and avoid large in-memory buffering.

## Error Handling

The endpoint should:

- return `404` for missing sessions
- return `403` for unauthorized access through the existing auth path
- tolerate transient job lookup failures by falling back to session-only state
- treat malformed artifact or checkpoint rows as absent auxiliary data, not fatal stream errors

If the stream helper itself hits an unexpected unrecoverable error, it should use the existing SSE error path and close cleanly.

## Testing Strategy

Add three levels of coverage.

### Unit / Helper Tests

For `tldw_Server_API/app/core/Research/streaming.py`:

- snapshot shaping includes checkpoint metadata and artifact manifest summary
- status changes emit `status`
- progress changes emit `progress`
- checkpoint changes emit `checkpoint`
- new artifact versions emit `artifact`
- already-baselined artifacts do not emit again
- terminal sessions emit `terminal`

### Endpoint Tests

For `tldw_Server_API/tests/Research/test_research_runs_endpoint.py`:

- stream returns `text/event-stream`
- authorized caller receives `snapshot` first
- missing session maps to `404`
- terminal run emits `snapshot` then `terminal`

### End-To-End Test

For `tldw_Server_API/tests/e2e/test_deep_research_runs.py`:

- create a run
- connect to the research SSE endpoint
- observe the initial `snapshot`
- advance the run through at least one checkpoint or terminal transition
- verify the expected event sequence at a coarse level

## Implementation Notes

The best fit is:

- keep `research_runs.py` as the HTTP surface
- add stream-shaping helpers in `app/core/Research/streaming.py`
- extend research schemas for snapshot/checkpoint/artifact summary payloads
- keep polling-only `GET /runs/{id}` unchanged except where shared models benefit from the richer snapshot contract

This keeps the new transport additive and avoids destabilizing the existing polling APIs.
