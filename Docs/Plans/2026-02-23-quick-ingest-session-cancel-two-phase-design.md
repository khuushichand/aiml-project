# Quick Ingest Session-Cancel Two-Phase Design

## Context

Quick ingest in extension/WebUI currently uses a blocking request/response pattern for batch completion, with best-effort progress updates, and no first-class quick-ingest session id/cancel protocol across the modal flow.

The target is a pragmatic long-term design:

1. Phase 1: frontend/extension migration to session-native async quick-ingest flows using existing backend APIs.
2. Phase 2: backend hardening for first-class user-scoped events, batch cancel ergonomics, and lookup efficiency.

## Scope Decisions (Approved)

1. Two-phase plan.
2. Phase 1 includes extension + WebUI quick-ingest modal flows.
3. Phase 1 is strictly no-backend-changes.
4. Cancel UX is immediate terminal cancelled state after user confirmation.
5. `processOnly` in Phase 1 supports client-side abort/best-effort cancel semantics.
6. E2E cancel coverage in Phase 1 includes extension + WebUI modals.
7. Phase 2 backend hardening order:
   1. user-scoped media ingest event stream
   2. batch/session cancel endpoint
   3. batch lookup optimization

## Architecture Options

### Option 1: Minimal Delta Patch

Patch current quick-ingest batch code with lightweight cancel/session support while preserving most existing request shape.

- Pros: fastest initial diff.
- Cons: accumulates coupling and debt; weak long-term model.

### Option 2: Session-Native Quick Ingest (Selected)

Establish a session-native lifecycle for modal quick-ingest flows now, while using existing backend APIs.

- Pros: durable architecture, controlled scope, clean Phase 2 migration.
- Cons: moderate refactor across modal/background/store/test layers.

### Option 3: Full Unified Ingest Engine Now

Converge quick-ingest and context-menu ingest into one engine in Phase 1.

- Pros: strongest consolidation.
- Cons: large blast radius; slower and riskier under no-backend-change constraints.

## Selected Design

Use Option 2.

### Phase 1: Frontend/Extension Session-Native Flow (No Backend Changes)

#### Protocol

1. Start:
   - UI sends `tldw:quick-ingest/start`.
   - Background returns immediate ack: `{ ok: true, sessionId }`.
2. Async events:
   - `tldw:quick-ingest/progress` `{ sessionId, processedCount, totalCount, item? }`
   - `tldw:quick-ingest/completed` `{ sessionId, results, summary }`
   - `tldw:quick-ingest/failed` `{ sessionId, error, partialResults? }`
   - `tldw:quick-ingest/cancelled` `{ sessionId, results?, summary? }`
3. Cancel:
   - UI shows confirm dialog before dispatch.
   - On confirm, UI sends `tldw:quick-ingest/cancel` `{ sessionId, reason }`.
   - UI transitions immediately to terminal cancelled state.

#### Execution Modes

1. `storeRemote`:
   - Submit via existing `POST /api/v1/media/ingest/jobs`.
   - Track job ids by session.
   - Poll existing `GET /api/v1/media/ingest/jobs/{job_id}`.
   - Cancel via existing `DELETE /api/v1/media/ingest/jobs/{job_id}`.
2. `processOnly`:
   - Keep current process endpoints.
   - Add session-scoped AbortControllers for requests/uploads.
   - Cancel is local best-effort abort (explicit copy in UI).

#### State Model

Session state:
- `idle` -> `running` -> terminal `{completed|failed|cancelled}`.

Store/result updates:
- Add first-class `cancelled` last-run state.
- Preserve success/failure totals.
- Add cancelled-aware result outcomes (`cancelled` distinct from `failed`).

#### UX and Copy

1. Cancel action requires explicit confirmation:
   - Title: `Cancel quick ingest?`
   - Body: `This stops remaining items in this run. Completed items are kept.`
   - Buttons: `Keep running` (default), `Cancel ingest` (destructive)
2. After confirm:
   - Immediate terminal card: `Quick ingest cancelled`
   - Summary includes cancelled count.
   - No generic failure toast for user-initiated cancel.

#### Session Safety Rules

1. Every event includes `sessionId`.
2. UI processes events only for active session.
3. Terminal lock prevents late events from overriding cancelled state.

### Phase 2: Backend Hardening

#### 1) User-Scoped Media Ingest Event Stream

Add dedicated user-authorized event stream for media ingest progress/completion/cancel status to reduce polling load and improve delivery semantics.

#### 2) Batch/Session Cancel Endpoint

Add endpoint to cancel by `batch_id`/session in one call instead of per-job deletion loops.

#### 3) Batch Lookup Optimization

Optimize batch job listing/filtering by leveraging indexed grouping in job records instead of payload scan patterns.

#### Implemented API Surface (2026-02-23)

1. `GET /api/v1/media/ingest/jobs/events/stream`
   - SSE stream with ownership enforcement.
   - Supports `batch_id` and `after_id`.
   - Emits initial `snapshot` plus `job` events from `job_events` outbox.

2. `POST /api/v1/media/ingest/jobs/cancel`
   - Cancels by `batch_id` or `session_id` alias in one call.
   - Enforces owner/admin authorization at batch scope.
   - Returns summary counters: `requested`, `cancelled`, `already_terminal` (plus `failed` when applicable).

3. `GET /api/v1/media/ingest/jobs?batch_id=...`
   - Uses indexed `batch_group` filtering first.
   - Falls back to legacy payload-based `batch_id` scan for backward compatibility.

4. `POST /api/v1/media/ingest/jobs`
   - Persists `batch_group=batch_id` for each created job to support indexed lookup/cancel paths.

## Error Handling

1. Start failure:
   - No session created; show failure summary.
2. Mid-run transport failures:
   - Emit failed terminal event with partials if available.
3. Cancellation race:
   - Cancelled terminal state remains authoritative for that session.
4. Process-only abort caveat:
   - Copy clarifies best-effort local cancellation.

## Testing Strategy

### Unit

1. Store records `cancelled` terminal summary.
2. Result normalization maps cancelled/canceled to cancelled outcome.
3. Cancel confirmation gates cancel dispatch.
4. Session-id guard ignores foreign events.
5. Terminal lock blocks stale event overrides.

### Background/Integration

1. Start returns immediate ack/sessionId.
2. StoreRemote sessions emit progress and terminal events via jobs polling.
3. Cancel issues per-job delete for tracked ids.
4. ProcessOnly cancel aborts request/upload controllers and emits cancelled outcomes.

### E2E (Phase 1 Required)

1. Extension modal: cancel mid-process + confirm.
2. WebUI modal: cancel mid-process + confirm.
3. Misclick prevention: keep-running path does not send cancel.
4. ProcessOnly cancel path shows cancelled semantics.
5. Session isolation across sequential runs.

## Non-Goals (Phase 1)

1. No backend API changes.
2. No context-menu ingest flow refactor.
3. No user SSE backend rollout yet.

## Deliverables

1. Approved session-native quick-ingest modal design for extension/WebUI.
2. Two-phase roadmap with explicit backend hardening sequence.
3. Test matrix and success criteria aligned to cancellation-first UX.
