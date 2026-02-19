## Stage 1: Baseline And Scope
**Goal**: Document the current `/prompts` architecture and lock the initial refactor boundary to the `custom` prompts table flow only.
**Success Criteria**:
- Shared route usage is confirmed for WebUI and extension.
- Existing table architecture, actions, and state ownership are mapped.
- Refactor boundary is explicit: no behavior change in this stage.
**Tests**:
- Manual static validation of source references for:
  - `apps/tldw-frontend/pages/prompts.tsx`
  - `apps/tldw-frontend/extension/routes/option-prompts.tsx`
  - `apps/packages/ui/src/components/Option/Prompt/index.tsx`
**Status**: Complete

## Stage 2: Scaffold The New Workspace Modules
**Goal**: Add compile-safe, typed skeleton modules for the new prompt workspace UI architecture without changing runtime behavior.
**Success Criteria**:
- New scaffold files exist for container, toolbar, table, bulk bar, inspector, column factory, and shared state hook.
- Shared TypeScript contracts are centralized for query state, selection state, panel state, and row view model.
- Existing page behavior remains unchanged because scaffolds are not yet wired in.
**Tests**:
- Targeted eslint/type checks for new files.
**Status**: Complete

## Stage 3: Slice 1 PR (No UX Delta, Structural Extraction)
**Goal**: Extract existing custom prompts table rendering from `index.tsx` into the scaffold modules with no visible UX change.
**Success Criteria**:
- `PromptBody` continues to render the same controls and table behavior.
- Logic remains in place, but JSX/layout is moved into extracted components with prop wiring.
- Existing tests for prompts workspace still pass.
**Tests**:
- `vitest` prompt workspace tests.
- `/prompts` smoke interaction checks.
**Status**: Complete

## Stage 4: Slice 2 PR (UX Delta)
**Goal**: Introduce the improved UX model: simplified columns, right-side inspector panel, and clarified action hierarchy.
**Success Criteria**:
- Row click opens inspector panel instead of immediately entering edit flow.
- Column set aligns to v1 (`title`, `preview`, `tags`, `updated`, `status`, `actions`).
- Inline actions reduced to primary edit + overflow actions.
**Tests**:
- Keyboard/a11y checks for row navigation and focus behavior.
- Prompt actions regression tests (edit/use/delete/sync paths).
**Status**: Complete

## Stage 5: Slice 3 PR (Polish, Accessibility, Cleanup)
**Goal**: Finalize accessibility, remove dead state, and stabilize for merge.
**Success Criteria**:
- 44px+ target sizing for actionable controls.
- Icon-only controls have labels/tooltips.
- Old table-only state and duplicate helpers are removed from `index.tsx`.
**Tests**:
- Lint + type checks.
- Existing prompt workspace tests and smoke tests.
**Status**: In Progress

### Stage 5 Progress Notes
- Increased icon-only action targets in the custom prompts table and row actions to 44px-equivalent sizing (`min-h-11 min-w-11`).
- Preserved existing `data-testid` hooks while updating interaction sizing for touch accessibility.
- Removed prompt preview expansion state/effects (`expandedContentByPromptId`) and simplified preview rendering to consistent clamps.
- Removed now-obsolete usage-sort and content-toggle regression tests; retained broad prompt workspace coverage.
- Migrated custom prompts table rendering from large inline `Table` config in `index.tsx` to `PromptListTable` v1 + `buildPromptTableColumns`.
- Added v1 table adapters for sanity-preserving behavior: existing row/favorite test ids, overflow indicator shell, row keyboard/click guards, selection disable support, and translated column labels.

## Exact Edit Map For Upcoming PR Slices
1. `apps/packages/ui/src/components/Option/Prompt/index.tsx`
   - Slice 1: replace inlined custom table JSX with extracted modules while preserving behavior.
   - Slice 2: wire inspector panel open state and simplified column configuration.
2. `apps/packages/ui/src/components/Option/Prompt/PromptDrawer.tsx`
   - Slice 2: keep as edit surface; invoked from inspector primary action.
3. `apps/packages/ui/src/components/Option/Prompt/PromptActionsMenu.tsx`
   - Slice 2: simplify to primary inline action + overflow emphasis.
4. `apps/packages/ui/src/components/Option/Prompt/SyncStatusBadge.tsx`
   - Slice 2: prefer labeled badge mode in list and inspector metadata.

## Scaffold Files Added In This Plan
- `apps/packages/ui/src/components/Option/Prompt/prompt-workspace-types.ts`
- `apps/packages/ui/src/components/Option/Prompt/usePromptWorkspaceState.ts`
- `apps/packages/ui/src/components/Option/Prompt/prompt-table-columns.tsx`
- `apps/packages/ui/src/components/Option/Prompt/PromptListToolbar.tsx`
- `apps/packages/ui/src/components/Option/Prompt/PromptBulkActionBar.tsx`
- `apps/packages/ui/src/components/Option/Prompt/PromptListTable.tsx`
- `apps/packages/ui/src/components/Option/Prompt/PromptInspectorPanel.tsx`
- `apps/packages/ui/src/components/Option/Prompt/PromptBodyContainer.tsx`
- `apps/packages/ui/src/components/Option/Prompt/workspace-v1.ts`

## Handoff Notes
- This plan intentionally keeps scaffolds non-invasive so current `/prompts` behavior remains stable.
- The next implementation PR should finish Stage 5 by migrating legacy custom table rendering from `index.tsx` to the extracted v1 table/column components while preserving existing `data-testid` hooks used by e2e.
