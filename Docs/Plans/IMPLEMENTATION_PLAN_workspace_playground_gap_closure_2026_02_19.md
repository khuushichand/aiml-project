# Implementation Plan: Workspace Playground - Remaining Gap Closure

## Scope

This plan addresses all six unresolved review findings:
- Critical broken lorebook diagnostics route (`/playground` 404)
- Drag-to-chat source scoping persists instead of being temporary
- Global search `note:` only covers the currently open draft note
- Source metadata does not persist API-origin `createdAt`
- Studio generated outputs list is not virtualized for large histories
- Workspace export/import has JSON only, no ZIP bundle support

## Finding to Stage Mapping

| Finding | Severity | Stage |
|---|---|---|
| Lorebook diagnostics route points to `/playground` | Critical | Stage 1 |
| Drag-to-chat temporary source scope missing | Important | Stage 2 |
| Global note corpus not indexed in Cmd/Ctrl+K | Important | Stage 3 |
| Source `createdAt` not normalized/stored/rendered | Important | Stage 3 |
| Studio output list not virtualized | Important | Stage 4 |
| ZIP workspace export/import path missing | Nice-to-have | Stage 5 |

## Stage 1: Route Contract Hardening
**Goal**: Remove the broken `/playground` navigation path from workspace diagnostics flows.
**Success Criteria**:
- All workspace chat diagnostics links resolve to valid registered routes.
- Route building for diagnostics uses a shared helper/constant, not inline hardcoded path strings.
- Clicking diagnostics deep links never lands on the 404 route-not-found state.
**Tests**:
- Unit test for diagnostics link builder output.
- ChatPane test asserting rendered diagnostics `href`.
- Route-registry regression test that generated link is a registered route.
**Status**: Complete

## Stage 2: Temporary Drag-to-Chat Scoping Lifecycle
**Goal**: Make drag-to-chat source narrowing session-scoped and reversible.
**Success Criteria**:
- Dropping a source captures prior selected source IDs.
- Temporary chat scope is applied only for the active draft/send flow.
- User can restore prior selection explicitly from chat UI.
- Successful send restores prior selection automatically (unless user intentionally changed scope).
- Source-context change notice remains accurate and non-noisy.
**Tests**:
- Interaction test: drop source -> temporary scope indicator appears.
- Interaction test: restore action rehydrates exact prior selection array.
- Integration test: send with temporary scope -> auto-restore occurs.
- Regression test: no duplicate/false context-change warnings.
**Status**: Complete

## Stage 3: Search and Source Metadata Data-Integrity Pass
**Goal**: Fix data completeness for note search and source metadata display.
**Success Criteria**:
- Global search indexes workspace notes corpus (saved notes list + current draft note).
- `note:` filters return both active draft and persisted workspace notes.
- Selecting a non-current note result loads/focuses the target note in Studio.
- `WorkspaceSource` stores normalized API-origin source creation timestamp.
- Sources UI prefers API-origin timestamp when present, with fallback to `addedAt`.
**Tests**:
- `workspace-global-search` unit tests for note corpus indexing and ranking.
- WorkspacePlayground integration test for selecting non-current note result.
- Source normalization unit tests for `created_at` variants.
- SourcesPane rendering test for created-date fallback chain.
**Status**: Complete

## Stage 4: Studio Output List Virtualization
**Goal**: Keep generated-outputs interactions performant for large artifact counts.
**Success Criteria**:
- Studio outputs switch to virtualization above an item threshold.
- Keyboard focus, hover actions, and row buttons remain fully functional.
- Add/regenerate/delete operations preserve stable scroll behavior.
- Empty/loading states remain unchanged for small lists.
**Tests**:
- StudioPane test: virtualization path activates for large fixture counts.
- Row-action regression tests under virtualized rendering.
- Interaction test: regenerate/delete does not break focus or action targeting.
**Status**: Complete

## Stage 5: ZIP Export/Import Compatibility Layer
**Goal**: Add compressed workspace portability while preserving JSON compatibility.
**Success Criteria**:
- Export supports `.workspace.zip` with manifest + canonical workspace payload.
- Import accepts both `.workspace.zip` and `.workspace.json`.
- Schema/version validation is enforced consistently for JSON and ZIP.
- If ZIP handling fails, existing JSON path remains available and documented.
**Tests**:
- WorkspaceHeader/export tests for ZIP option + filename contract.
- Import tests: valid ZIP, corrupted ZIP, invalid manifest/schema mismatch.
- Roundtrip integration test: export ZIP -> import -> equivalent workspace state.
**Status**: Complete

## Cross-Stage Guardrails

- Backward-compatible persisted store migrations only.
- No regressions to existing `/workspace-playground` navigation.
- Maintain passing WorkspacePlayground test baseline after each stage.
- Keep route, metadata, and export changes feature-flag free unless strictly required.

## Execution Order

1. Stage 1 (critical user-facing breakage)
2. Stage 2 (behavioral correctness for chat source scope)
3. Stage 3 (search and metadata correctness)
4. Stage 4 (performance/scalability)
5. Stage 5 (portability feature completion)

## Validation Plan

Run after each stage and again at completion:
- `source .venv/bin/activate`
- `cd apps/packages/ui`
- `bunx vitest run src/components/Option/WorkspacePlayground/__tests__ src/store/__tests__/workspace.test.ts src/store/__tests__/workspace-events.test.ts src/store/__tests__/workspace-sync-contract.test.ts`

## Status Summary

- Overall status: Complete
- Completed: Stage 1 route-contract hardening
- Completed: Stage 2 temporary drag-to-chat scoping lifecycle
- Completed: Stage 3 search + source metadata data-integrity pass
- Completed: Stage 4 studio output virtualization
- Completed: Stage 5 ZIP export/import compatibility layer
- Next action: None (all stages complete).
