# Implementation Plan: Watchlists H1 - Visibility of System Status

## Scope

Route/components: `WatchlistsPlaygroundPage`, `SourcesTab`, `JobsTab`, `RunsTab`, `RunDetailDrawer`, `OutputsTab`  
Finding IDs: `H1.1` through `H1.7`

## Finding Coverage

- Missing at-a-glance operations view: `H1.1`, `H1.6`
- Hidden source/job status signals: `H1.2`, `H1.3`
- Weak live and recentness indicators: `H1.4`, `H1.7`
- Low-salience delivery outcomes: `H1.5`

## Stage 1: Surface Existing Status Data in Current Tables
**Goal**: Expose currently available API status fields without changing page architecture.
**Success Criteria**:
- Sources table shows health state (`status`, backoff/defer signal, consecutive stale runs indicator).
- Jobs table renders `next_run_at` with relative + absolute time.
- Runs toolbar shows `last refreshed` timestamp in addition to polling indicator.
- Outputs status tags include icon + concise text for delivery states.
**Tests**:
- Component tests for new columns and status badge rendering.
- Unit tests for status-to-badge mapping and timestamp formatter.
- Regression test ensuring table sorting/filtering still works with new columns.
**Status**: Complete

## Stage 2: Live Run Visibility
**Goal**: Move run details from one-time fetch to live status feedback.
**Success Criteria**:
- `RunDetailDrawer` consumes `/runs/{run_id}/stream` and appends streaming log entries.
- Drawer clearly indicates stream connection state (connected, reconnecting, disconnected).
- Active run rows update progress/status without full page reload.
**Tests**:
- Integration tests for WebSocket connect/reconnect/error handling.
- Component tests for streamed log append and bounded log buffer.
- E2E test for active run progression and completion transition.
**Status**: Complete

## Stage 3: Overview and Notifications
**Goal**: Add a true operational summary surface and completion/failure signals.
**Success Criteria**:
- New overview dashboard card/grid shows source health counts, active jobs, unread items, and recent failed runs.
- Scheduled run completion/failure emits in-app notification with deep link to run details.
- Failed run notifications include short remediation hint and dismiss behavior.
**Tests**:
- Integration tests for overview aggregate data loading and refresh.
- Notification lifecycle tests (emit, click-through, dismiss).
- E2E test validating "system healthy vs degraded" visibility in < 1 click.
**Status**: Complete

## Dependencies

- Streaming work depends on stable event format for `/runs/{run_id}/stream`.
- Overview aggregates should reuse existing stats endpoints before adding new APIs.
- Notification copy and severity taxonomy should align with `H9` error recovery plan.

## Implementation Notes

- 2026-02-18: Hardened Playwright coverage in `apps/extension/tests/e2e/watchlists.spec.ts` for overview health states and failed-run notification click-through navigation.
- 2026-02-18: Added explicit first-run overview callout navigation assertion (`Open Monitors`) to verify cross-tab guidance remains functional.
