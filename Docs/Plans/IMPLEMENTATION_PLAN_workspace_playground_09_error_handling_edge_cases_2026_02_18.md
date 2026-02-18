# Implementation Plan: Workspace Playground - Error Handling and Edge Cases

## Scope

Components: Add Source batch flow, workspace root container, store persistence, generation rehydration, destructive actions
Finding IDs: `9.1` through `9.7`

## Finding Coverage

- Keep positive behavior with better copy: `9.1`
- Error visibility and recovery: `9.2`, `9.3`, `9.4`
- State consistency across sessions/tabs: `9.5`, `9.6`
- Reversible destructive actions: `9.7`

## Stage 1: Actionable Error Surfaces
**Goal**: Replace silent or opaque failures with explicit, recoverable messaging.
**Success Criteria**:
- Batch URL ingestion reports per-item success/failure summary.
- Workspace-level error boundary captures render crashes with reload action.
- Empty-state copy clarifies general chat is available without sources.
**Tests**:
- Integration test for mixed-result batch URL add summary output.
- Component test for error boundary fallback and retry.
- Copy regression test for empty state messaging.
**Status**: Complete

## Stage 2: Persistence Failure and Cross-Tab Resilience
**Goal**: Prevent silent persistence failures and stale-tab overwrite surprises.
**Success Criteria**:
- `QuotaExceededError` handling warns user with remediation guidance.
- Cross-tab storage changes detected and surfaced with reload/sync prompt.
- Optional `BroadcastChannel` sync strategy documented and implemented behind guard.
**Tests**:
- Unit tests simulating quota exceptions during persist.
- Integration tests for storage event prompt in two-tab scenario.
- Unit tests for conflict-resolution prompt throttling.
**Status**: Complete

## Stage 3: Interrupted Work Recovery and Undo Framework
**Goal**: Normalize recovery from refresh interruptions and destructive actions.
**Success Criteria**:
- Rehydration converts stale `generating` artifacts to `failed` with interruption message.
- Shared undo manager handles delete/clear actions consistently with 5-second restore window.
- Soft-delete buffer purges only after undo timeout expires.
**Tests**:
- Unit tests for rehydrate migration of interrupted artifacts.
- Integration tests for undo manager restore/purge lifecycle.
- Regression tests across source/artifact/workspace/note destructive actions.
**Status**: In Progress

## Dependencies

- Undo manager should be consumed by Categories 1, 3, and 5.

## Progress Notes (2026-02-18)

- Stage 1 completed:
  - Added mixed-result batch ingestion feedback for Search tab URL adds:
    - tracks per-URL failures with reasons,
    - shows actionable summary (`Added X of Y; failed URLs + reasons`),
    - keeps full failure summary in modal error state when no URL succeeded.
  - Added a workspace-level render error boundary with recoverable fallback UI and explicit reload action.
  - Updated empty-state no-source guidance to explicitly mention general chat without sources.
- Files updated:
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/SourcesPane/AddSourceModal.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/index.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/source-location-copy.ts`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/AddSourceModal.stage9.error.test.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.error-boundary.test.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts`
- Validation:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.error-boundary.test.tsx src/components/Option/WorkspacePlayground/__tests__/AddSourceModal.stage9.error.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts --reporter=verbose`
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/AddSourceModal.stage1.mobile.test.tsx src/components/Option/WorkspacePlayground/__tests__/AddSourceModal.stage3.performance.test.tsx src/components/Option/WorkspacePlayground/__tests__/AddSourceModal.stage9.error.test.tsx src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.desktop-layout.test.tsx src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.error-boundary.test.tsx src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage2.responsive.test.tsx src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage3.test.tsx src/store/__tests__/workspace.test.ts --reporter=dot`
- Stage 2 completed:
  - Added resilient workspace storage event primitives in `workspace-events.ts`:
    - shared storage key constants,
    - quota event name + payload typing,
    - guarded BroadcastChannel sync helpers,
    - conflict-notice throttling helper.
  - Updated workspace persistence adapter (`createWorkspaceStorage`) to:
    - catch `QuotaExceededError` and emit a browser event instead of failing silently,
    - broadcast storage updates over optional BroadcastChannel sync (`localStorage` flag `tldw:workspace:broadcast-sync=1` or `window.__TLDW_ENABLE_WORKSPACE_BROADCAST_SYNC__ = true`).
  - Added workspace-level UI warnings in `WorkspacePlayground`:
    - quota banner with remediation guidance,
    - cross-tab state-change banner with reload/later actions,
    - throttled conflict prompts to avoid repeated alert spam.
  - Added Stage 2 test coverage:
    - store quota exception event emission test,
    - helper unit tests for broadcast payload validation + throttle logic,
    - integration tests for storage-event conflict prompt and quota warning rendering.
- Stage 2 files updated:
  - `apps/packages/ui/src/store/workspace-events.ts`
  - `apps/packages/ui/src/store/workspace.ts`
  - `apps/packages/ui/src/store/__tests__/workspace-events.test.ts`
  - `apps/packages/ui/src/store/__tests__/workspace.test.ts`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/index.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage9.persistence.test.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage3.test.tsx`
- Stage 2 validation:
  - `cd apps/packages/ui && bunx vitest run src/store/__tests__/workspace.test.ts src/store/__tests__/workspace-events.test.ts src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage9.persistence.test.tsx src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage3.test.tsx --reporter=verbose`
- Stage 3 progress:
  - Added rehydration recovery for interrupted generations:
    - any persisted artifact with `status: "generating"` is migrated to `status: "failed"` on hydrate,
    - failed artifact receives retry guidance (`Generation was interrupted. Click regenerate to try again.`),
    - migration applies to both active workspace artifacts and persisted per-workspace snapshots.
- Stage 3 files updated:
  - `apps/packages/ui/src/store/workspace.ts`
  - `apps/packages/ui/src/store/__tests__/workspace.test.ts`
