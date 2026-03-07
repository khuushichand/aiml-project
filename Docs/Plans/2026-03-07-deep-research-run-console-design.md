# Deep Research Run Console Design

**Date:** 2026-03-07

## Goal

Add a dedicated frontend deep-research console that lets users create runs, monitor them live, approve checkpoints, inspect artifacts, and read final bundles from a single page.

## Motivation

The deep research backend now supports:

- Jobs-backed research sessions
- provider-backed planning, collecting, synthesizing, and packaging
- run controls
- artifact and bundle reads
- replayable SSE streams with `after_id`

That backend is now strong enough to deserve a real user-facing surface. Polling raw endpoints manually is fine for development, but it is not a credible product experience for a long-running research workflow.

The frontend already has:

- `apiClient` and auth header helpers in `apps/tldw-frontend/lib/api.ts`
- an SSE utility in `apps/tldw-frontend/lib/sse.ts`
- a poll-plus-stream page pattern in `apps/tldw-frontend/pages/notifications.tsx`

This slice should build on those seams rather than inventing a separate research client stack.

## Recommended Approach

Build a dedicated run console page at:

- `apps/tldw-frontend/pages/research/index.tsx`

and add one small backend API expansion:

- `GET /api/v1/research/runs`

Three approaches were considered:

1. Full research workspace page.
   This would build creation, live monitoring, history, checkpoint handling, artifact reading, and polished report browsing all in one large slice.

2. Backend list API plus thin run console page.
   This adds a small history API, then builds a focused page around creation, recent runs, selected-run live state, checkpoint approval, artifact reads, and bundle reads.

3. Debug console only.
   This would expose the feature quickly with raw JSON panels, but it would likely be replaced rather than extended.

The recommended option is `2`.

It is the smallest slice that becomes a real product surface instead of another placeholder.

## Scope

This design covers:

- a dedicated deep-research page in the web app
- a recent-runs list endpoint
- selected-run polling plus replayable SSE consumption
- read-only checkpoint details with approve-only actions
- lazy artifact and bundle loading
- basic run controls on the selected run

This design does not cover:

- checkpoint patch editing
- structured plan/source/outline editors
- cross-run live SSE feeds
- pagination-heavy research history
- embedding deep research inside chat in this slice

## Backend Additions

Add:

- `GET /api/v1/research/runs`

The endpoint should:

- authenticate like the existing research run endpoints
- return only the current user’s sessions
- order by `created_at DESC` in v1 because this page is a newly-created run console, not a most-recently-updated operations board
- default to a bounded recent list in v1
- return a dedicated list-item shape with at least:
  - `id`
  - `query`
  - `status`
  - `phase`
  - `control_state`
  - `progress_percent`
  - `progress_message`
  - `active_job_id`
  - `latest_checkpoint_id`
  - `completed_at`
  - `created_at`
  - `updated_at`

This requires a small expansion in the research DB/service layer:

- owner-scoped session listing in `ResearchSessionsDB`
- a `ResearchService.list_sessions(...)` helper
- a dedicated `ResearchRunListItemResponse` schema instead of reusing `ResearchRunResponse`

No new write-side research domain objects are needed.

## Frontend Page Architecture

Create a dedicated page at:

- `apps/tldw-frontend/pages/research/index.tsx`

Do not reuse:

- `apps/tldw-frontend/pages/for/researchers.tsx`

That route is marketing content today and should remain separate from the application workflow.

The page should have two main columns.

### Left Column

- create-run form
- recent run history list

Each run row should show:

- query preview
- status
- phase
- control state
- progress message when present

### Right Column

- selected run header
- pause/resume/cancel actions when valid
- live status and progress summary
- checkpoint card when present
- artifact list with lazy read-on-open behavior
- bundle/report section for completed runs

This should be a stacked console, not a complex tabbed workspace. The backend object model is already stage-based and vertical enough that a stacked detail view is the lowest-friction UI.

## Data Flow

### Create Run

The page submits:

- `query`
- optionally `source_policy`
- optionally `autonomy_mode`

On success:

- prepend the created run to the recent-runs list
- select it immediately
- begin live monitoring

### Recent Runs List

Use React Query to call:

- `GET /api/v1/research/runs`

The list should poll at a modest interval. It does not need live SSE updates in v1 because the selected run will get direct stream updates.

### Selected Run Detail

When a run is selected:

- fetch `GET /api/v1/research/runs/{id}`
- open `GET /api/v1/research/runs/{id}/events/stream`

The stream reducer should:

- replace local selected-run state on `snapshot`
- patch local state on `status`, `progress`, `checkpoint`, `artifact`, and `terminal`
- remember the highest replayable event ID
- reconnect using `after_id=<last_seen>`

The stream should be the primary source of truth for the selected run’s live state. Polling remains useful for initial load and recovery.

State ownership should be explicit:

- React Query owns fetch lifecycles for:
  - recent-runs list
  - selected-run initial detail
  - lazy artifact reads
  - lazy bundle reads
- a local reducer owns the live selected-run view after the initial fetch
- user actions should invalidate the list/detail queries, but the selected-run reducer remains the immediate live UI source while SSE is connected

### Checkpoint Approval

For v1, checkpoint handling should be:

- read-only checkpoint payload summary
- approve button only

Approval calls the existing endpoint with an empty patch payload. After approval:

- refresh selected-run detail
- invalidate the recent-runs list
- let the SSE stream continue driving later state transitions

### Artifact And Bundle Loading

Artifact reads should stay lazy:

- `GET /api/v1/research/runs/{id}/artifacts/{name}`

Bundle reads should also stay lazy:

- `GET /api/v1/research/runs/{id}/bundle`

This avoids over-fetching and keeps the selected-run view responsive even when research artifacts become larger.

## SSE Client Contract

The current frontend helper in:

- `apps/tldw-frontend/lib/sse.ts`

is chat-oriented. It ignores `event:` semantics and does not surface SSE `id:` values. That is not sufficient for research replay.

This repo also already has a richer SSE parser/subscriber pattern in:

- `apps/tldw-frontend/lib/api/notifications.ts`

This slice should extract a shared low-level structured SSE reader from that stronger notifications-style path, then let research clients consume:

- `event`
- `id`
- parsed JSON payloads
- completion markers

The research UI should not parse SSE frames ad hoc inside the page. A small shared structured SSE helper is the right seam, and `streamSSE(...)` can remain as a compatibility wrapper for chat-style consumers.

## Error Handling

The page should handle three broad failure modes cleanly.

### Load Failures

If the recent-runs list or selected-run detail fails:

- show an inline error state
- keep previously loaded UI visible when possible
- allow manual refresh

### Stream Failures

If the research SSE stream fails:

- keep the last known selected-run state
- show a nonfatal stream warning
- reconnect after a short delay using `after_id`
- leave polling in place as a safety net

### Action Failures

If create, approve, pause, resume, cancel, artifact read, or bundle read fails:

- show a toast or inline error
- do not clear the selected-run state
- allow retry

## Testing Strategy

Add backend and frontend coverage.

### Backend

For the new list endpoint:

- owner-scoped reads
- newest-first ordering
- bounded result set behavior
- endpoint schema compatibility with `ResearchRunResponse`

### Frontend

Add focused tests for:

- a minimal reusable page test wrapper that provides the providers this page needs:
  - QueryClient
  - toast context
  - a lightweight layout/router-safe shell
- create-run form selecting the new run
- recent-runs list rendering
- selected-run detail load
- checkpoint approve action
- artifact lazy load
- completed bundle lazy load
- SSE snapshot plus replay update handling
- reconnect with `after_id`

The frontend tests do not need to exercise full visual polish. They should prove the data flow and reducer behavior.

## Operational Constraints

Keep the first page intentionally narrow:

- one selected run at a time
- one recent-runs list query
- one live SSE connection for the selected run
- no background preloading of every artifact or bundle

This keeps the UI cheap to run and avoids creating a second orchestration layer in the browser.

## Out Of Scope

This slice does not include:

- inline checkpoint editing
- report authoring tools
- multi-run event dashboards
- chat-mode integration
- export-format customization beyond existing backend package/export support

## Summary

The right next step is a dedicated deep-research console at `/research` backed by one new recent-runs list endpoint and a frontend that combines:

- React Query for list/detail reads
- replayable SSE for the selected run
- approve-only checkpoint handling
- lazy artifact and bundle reads

That gives the backend a credible first-class user surface without overscoping into a full collaborative research studio.
