# Implementation Plan: Workspace Playground - Workspace Management

## Scope

Components: `WorkspaceHeader`, workspace store (`initialize/switch/save/delete`), workspace persistence strategy
Finding IDs: `5.1` through `5.8`

## Finding Coverage

- Core persistence architecture: `5.6`, `5.8`
- Safe lifecycle actions: `5.5`, `5.7`, `5.4`
- Discoverability and metadata in switcher: `5.1`, `5.2`, `5.3`

## Stage 1: Per-Workspace Snapshot Persistence (Critical)
**Goal**: Stop destructive state loss when switching workspaces.
**Success Criteria**:
- Workspace snapshot model stores sources, artifacts, notes, pane state, and chat reference key by `workspaceId`.
- `switchWorkspace` serializes current workspace and restores target snapshot.
- `initializeWorkspace` seeds isolated snapshot without mutating others.
- Rehydration restores last active workspace plus pane state from snapshot.
**Tests**:
- Integration tests for switch/save/restore across 3+ workspaces.
- Regression test proving no data loss on workspace switch.
- Rehydration tests for active workspace and pane collapse state.
**Status**: Complete

## Stage 2: Safe Workspace Lifecycle
**Goal**: Prevent accidental loss and support reversible cleanup.
**Success Criteria**:
- Delete action requires confirmation or supports undo toast.
- Archive/restore workflow exists as soft delete alternative.
- Duplicate workspace performs deep copy with new IDs for derived entities.
**Tests**:
- Integration tests for delete undo and archive restore.
- Unit tests for deep-copy integrity (no shared mutable references).
- Integration test for duplicate containing sources/artifacts/notes/settings.
**Status**: Complete

## Stage 3: Workspace Switcher UX and Metadata
**Goal**: Improve navigation among many saved workspaces.
**Success Criteria**:
- `View all workspaces` opens searchable modal with full saved list.
- Menu rows show source count and relative `lastAccessedAt`.
- Rename affordance is always discoverable (low-opacity idle state).
**Tests**:
- Component tests for all-workspaces modal filtering and selection.
- Unit tests for relative-time formatting.
- Visual regression for rename button discoverability.
**Status**: Complete

## Dependencies

- Stage 1 underpins Category 2 per-workspace chat history and Category 6 cross-pane continuity.

## Progress Notes (2026-02-18)

- Stage 1 implemented in workspace store:
  - Added per-workspace snapshot persistence keyed by `workspaceId` (sources, artifacts, notes, pane state, audio settings, chat reference key).
  - `switchWorkspace` now serializes current workspace snapshot and restores target snapshot.
  - `initializeWorkspace` and `createNewWorkspace` now seed isolated snapshots and saved-workspace metadata.
  - Rehydration now restores active workspace from snapshot and reconciles saved workspace metadata.
- Pane state wiring updated:
  - Desktop workspace layout now uses per-workspace `leftPaneCollapsed` / `rightPaneCollapsed` store fields instead of global pane-open storage keys.
- Files updated:
  - `apps/packages/ui/src/store/workspace.ts`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/index.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/ChatPane/index.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.desktop-layout.test.tsx`
  - `apps/packages/ui/src/store/__tests__/workspace.test.ts`
- Validation:
  - `cd apps/packages/ui && bunx vitest run src/store/__tests__/workspace.test.ts`
  - `cd apps/packages/ui && bunx vitest run src/store/__tests__/workspace.test.ts src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.desktop-layout.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts`
- Stage 2 implemented (safe lifecycle):
  - Added workspace archive/restore workflow in store.
  - Added workspace duplication with deep copy of snapshot data and regenerated IDs for sources/artifacts.
  - Added workspace deletion confirmation in header menu.
  - Added archived workspace section in dropdown with one-click restore-and-switch.
- Additional files updated:
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/WorkspaceHeader.tsx`
- Additional validation:
  - `cd apps/packages/ui && bunx vitest run src/store/__tests__/workspace.test.ts src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.desktop-layout.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts`
- Stage 3 implemented (switcher UX and metadata):
  - Added `View all workspaces` menu entry and searchable modal for full saved workspace list.
  - Added per-workspace metadata display (`sourceCount` + relative `lastAccessedAt`) in dropdown and modal rows.
  - Updated rename affordance to always visible low-opacity idle state (`opacity-40`).
  - Added utility helpers for workspace list filtering and relative-time formatting.
- Stage 3 files updated:
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/workspace-header.utils.ts`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/WorkspaceHeader.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/workspace-header.utils.test.ts`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspaceHeader.test.tsx`
- Stage 3 validation:
  - `cd apps/packages/ui && bunx vitest run src/store/__tests__/workspace.test.ts src/components/Option/WorkspacePlayground/__tests__/WorkspaceHeader.test.tsx src/components/Option/WorkspacePlayground/__tests__/workspace-header.utils.test.ts src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.desktop-layout.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts`
