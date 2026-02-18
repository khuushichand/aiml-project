# Implementation Plan: Workspace Playground - Performance and Perceived Speed

## Scope

Components: workspace store persistence/rehydration, source processing UI, large list rendering, media fetch behavior
Finding IDs: `8.1` through `8.6`

## Finding Coverage

- Rehydration and startup UX: `8.1`, `8.5`
- Perceived progress and background work visibility: `8.2`
- Large list and repeated fetch efficiency: `8.4`, `8.6`
- Preserve strong behavior: `8.3`

## Stage 1: Rehydration UX and Storage Efficiency
**Goal**: Remove startup flash and reduce unnecessary parse work.
**Success Criteria**:
- Pane skeletons render until persisted state hydration completes.
- Custom storage adapter removes redundant parse/stringify path.
- Date revival occurs once in rehydrate path only.
**Tests**:
- Unit tests for storage adapter behavior.
- Component test for skeleton visibility lifecycle.
- Integration test for hydration completeness before content swap.
**Status**: Complete

## Stage 2: Long-Running Work Visibility
**Goal**: Keep users informed when ingestion continues after optimistic add.
**Success Criteria**:
- Newly added sources show processing badge immediately.
- Background status polling/event update transitions to ready/error.
- Chat/source selection respects processing state.
**Tests**:
- Integration test for optimistic add then async status update.
- Unit tests for status polling reducer and timeout handling.
**Status**: Not Started

## Stage 3: Data Fetch and Rendering Scalability
**Goal**: Reduce repeated requests and maintain smooth scrolling at scale.
**Success Criteria**:
- Existing media list in Add Source uses cache (store or query client).
- Large output/source lists use threshold-based virtualization.
- Current smart-scroll and `aria-live` behavior in chat remains unchanged.
**Tests**:
- Integration test proving cached reopen avoids redundant fetch.
- Component perf test for large-list virtualization threshold.
- Regression tests for chat scroll and live-region behavior.
**Status**: Not Started

## Dependencies

- Source status indicators depend on status model introduced in Category 1.

## Progress Notes (2026-02-18)

- Stage 1 completed:
  - Added a hydration readiness gate to the workspace shell so panes render only after persisted state hydration completes.
  - Added a Workspace Playground loading skeleton to eliminate startup content flash before hydration.
  - Updated initialization flow to avoid creating a fresh workspace before hydration completion.
  - Simplified workspace persistence storage adapter `getItem` to a raw localStorage passthrough; removed redundant parse/stringify from the read path.
  - Kept date revival centralized in `onRehydrateStorage`.
- Files updated:
  - `apps/packages/ui/src/store/workspace.ts`
  - `apps/packages/ui/src/store/__tests__/workspace.test.ts`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/index.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.desktop-layout.test.tsx`
- Validation:
  - `cd apps/packages/ui && bunx vitest run src/store/__tests__/workspace.test.ts src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.desktop-layout.test.tsx --reporter=verbose`
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage2.responsive.test.tsx src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage3.test.tsx src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage3.test.tsx --reporter=verbose`
